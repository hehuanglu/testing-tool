"""Disposable synthetic app and a sanitized, server-side request witness."""

from contextlib import contextmanager
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
from threading import Thread
from urllib.parse import parse_qs, urlsplit

ACTORS = ("reader", "editor")
PASSWORD = "synthetic-fixture-password"
CSP = "default-src 'none'; frame-ancestors 'none'"
CSP_OPEN = ("/public/subject", "/public/control")
CSP_AUTH = ("/private/subject", "/private/control")


class App(ThreadingHTTPServer):
    def __init__(self, scenario, address=("127.0.0.1", 0), *, log_events=False):
        super().__init__(address, Handler)
        self.scenario = scenario
        self.log_events = log_events
        self.sessions = {}
        self.events = []
        self.revision = 0


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def reply(self, status, body, *, csp=True, cookie=None, links=None):
        kind = "application/json" if isinstance(body, dict) else "text/html"
        payload = (json.dumps(body) if isinstance(body, dict) else body).encode()
        event = {"method": self.command, "path": self.route, "status": status,
                 "actor": self.actor, "csp": csp, "revision": self.server.revision}
        if self.claim:
            event["loginActor"] = self.claim
        if links is not None:
            event["links"] = links
        self.server.events.append(event)
        if self.server.log_events:
            print(json.dumps(event), flush=True)
        self.send_response(status)
        self.send_header("Content-Type", kind + "; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if csp:
            self.send_header("Content-Security-Policy", CSP)
        if cookie:
            self.send_header("Set-Cookie", f"session={cookie}; Path=/; HttpOnly; SameSite=Strict")
        self.end_headers()
        self.wfile.write(payload)

    def handle_request(self):
        self.route = urlsplit(self.path).path
        cookie = SimpleCookie(self.headers.get("Cookie", "")).get("session")
        actor = self.server.sessions.get(cookie.value) if cookie else None
        self.actor = actor or "anonymous"
        self.claim = None
        method = self.command
        route = self.route
        scenario = self.server.scenario
        if route == "/login" and method == "GET":
            return self.reply(200, "<html>logged-out</html>")
        if route == "/login" and method == "POST":
            body = parse_qs(self.rfile.read(int(self.headers.get("Content-Length", "0"))).decode())
            claim = body.get("username", [""])[0]
            self.claim = claim if claim in ACTORS else "unknown"
            if claim not in ACTORS or body.get("password") != [PASSWORD]:
                return self.reply(401, "<html>logged-out</html>")
            token = secrets.token_hex(16)
            self.server.sessions[token] = claim
            self.actor = claim
            return self.reply(200, "<html>signed-in</html>", cookie=token)

        if route in ("/", "/ready") and method == "GET":
            return self.reply(200, "<html>ready</html>")
        if route in CSP_OPEN and method == "GET":
            csp = route != CSP_OPEN[1] and scenario != "public-csp-regression"
            return self.reply(200, "<html>public</html>", csp=csp)
        protected = route.startswith(("/private/", "/identity/", "/explore/", "/policy/"))
        if not protected:
            return self.reply(404, "<html>missing</html>")
        if not actor:
            return self.reply(401, {"marker": "logged-out"})
        if route in CSP_AUTH and method == "GET":
            csp = route != CSP_AUTH[1] and scenario != "private-csp-regression"
            return self.reply(200, "<html>signed-in</html>", csp=csp)
        if route.startswith("/identity/") and method == "GET":
            return self.reply(200, {"marker": "signed-in", "actor": actor})
        if route == f"/explore/{actor}/" and method == "GET":
            links = [] if scenario == "coverage-regression" and actor == "editor" else [
                f"/explore/{actor}/profile"]
            anchors = "".join(f'<a href="{path}">Profile API</a>' for path in links)
            return self.reply(200, f"<html>signed-in {anchors}</html>", links=links)
        if route == f"/explore/{actor}/profile" and method == "GET":
            return self.reply(200, {"marker": "signed-in", "actor": actor, "resource": "profile"})
        if route == "/policy/state" and method == "GET":
            return self.reply(200, {"actor": actor, "revision": self.server.revision})
        if route == "/policy/update" and method == "POST":
            if actor == "reader" or scenario == "authorization-regression":
                return self.reply(403, {"actor": actor, "decision": "denied"})
            self.server.revision += 1
            return self.reply(200, {"actor": actor, "decision": "allowed"})
        return self.reply(404, {"marker": "signed-in"})

    do_GET = handle_request
    do_POST = handle_request


@contextmanager
def fixture(scenario):
    with App(scenario) as app:
        thread = Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            yield app, f"http://127.0.0.1:{app.server_port}"
        finally:
            app.shutdown()
            thread.join()


if __name__ == "__main__":
    App("baseline", ("0.0.0.0", 8080), log_events=True).serve_forever()
