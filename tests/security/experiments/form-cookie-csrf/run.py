#!/usr/bin/env python3
"""Experimental form/cookie/CSRF authentication lifecycle through AF."""

import argparse
import json
import os
import signal
import subprocess
import tempfile
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def reply(self, status, body, headers=()):
        payload = body.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for name, value in headers: self.send_header(name, value)
        self.end_headers(); self.wfile.write(payload); self.wfile.flush()

    def do_GET(self):
        if self.path == "/login":
            self.server.records.append({"kind": "login-page", "status": 200})
            self.reply(200, '<form><input name="csrf" value="csrf-fixture">login-form</form>')
            return
        if self.path != "/private":
            self.send_error(404); return
        cookie = SimpleCookie(self.headers.get("Cookie", ""))
        authorized = cookie.get("session") is not None and cookie["session"].value in self.server.sessions
        if authorized:
            self.server.private_successes += 1
            self.server.records.append({"kind": "private", "status": 200,
                                        "actorWitness": True, "markerWitness": True})
            self.reply(200, "private-ok actor-alice")
            if self.server.mode == "revoke" and self.server.private_successes == 1:
                self.server.sessions.clear()
        else:
            self.server.records.append({"kind": "private", "status": 401,
                                        "actorWitness": False, "markerWitness": False})
            self.reply(401, "auth-lost login-form")

    def do_POST(self):
        if self.path != "/login":
            self.send_error(404); return
        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode())
        valid = (form.get("username") == ["alice"] and form.get("password") == ["password"]
                 and form.get("csrf") == [self.server.expected_csrf])
        if valid:
            token = "session-" + str(len(self.server.sessions) + 1)
            self.server.sessions.add(token)
            self.server.records.append({"kind": "login-submit", "status": 200, "csrfWitness": True})
            self.reply(200, "login-success", [("Set-Cookie", f"session={token}; HttpOnly; SameSite=Strict")])
        else:
            self.server.records.append({"kind": "login-submit", "status": 403, "csrfWitness": False})
            self.reply(403, "auth-lost invalid-csrf")


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute(plan, home, log):
    with log.open("wb") as stream:
        process = subprocess.Popen(["/zap/zap.sh", "-cmd", "-dir", str(home),
                                    "-autorun", str(plan)], stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try: return process.wait(timeout=240), False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            return process.returncode, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("healthy", "revoke", "bad-csrf"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    Path(os.environ.get("HOME", "/tmp/zap-form-home")).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.mode = args.mode; server.expected_csrf = "wrong" if args.mode == "bad-csrf" else "csrf-fixture"
    server.sessions = set(); server.records = []; server.private_successes = 0
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary); home = private / "home"; home.mkdir(); plan = private / "plan.json"
            write_json(plan, {
                "env": {"contexts": [{"name": "form-fixture", "urls": [origin],
                    "authentication": {"method": "form", "parameters": {
                        "loginPageUrl": origin + "/login", "loginRequestUrl": origin + "/login",
                        "loginRequestBody": "username={%username%}&password={%password%}&csrf=csrf-fixture"},
                        "verification": {"method": "response", "loggedInRegex": "(?:login-success|private-ok)",
                                         "loggedOutRegex": "(?:auth-lost|login-form)"}},
                    "sessionManagement": {"method": "cookie", "parameters": {}},
                    "users": [{"name": "alice", "credentials": {"username": "alice", "password": "password"}}]}],
                    "parameters": {"failOnError": True, "failOnWarning": False}},
                "jobs": [
                    {"type": "requestor", "parameters": {"user": "alice"}, "requests": [
                        {"name": "private-before", "url": origin + "/private", "method": "GET"},
                        {"name": "private-after", "url": origin + "/private", "method": "GET"}]},
                    {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
                    {"type": "report", "parameters": {"template": "traditional-json",
                                                         "reportDir": str(out), "reportFile": "zap-report"}}]})
            native_exit, timed_out = execute(plan, home, out / "zap.log")
        private_rows = [row for row in server.records if row["kind"] == "private"]
        login_rows = [row for row in server.records if row["kind"] == "login-submit" and row["status"] == 200]
        if timed_out:
            status, reason = "EXECUTION_ERROR", "TIMEOUT"
        elif native_exit != 0 or not (out / "zap-report.json").is_file():
            status, reason = "EXECUTION_ERROR", "ZAP_OR_REPORT_FAILURE"
        elif (args.mode == "revoke" and len(login_rows) >= 2 and private_rows
              and private_rows[-1]["status"] == 200 and private_rows[-1]["actorWitness"]):
            status, reason = "PASS", "SESSION_REFRESH_WITNESSED"
        elif len(private_rows) >= 2 and all(row["status"] == 200 for row in private_rows[-2:]) and login_rows:
            status, reason = "PASS", "FORM_COOKIE_CSRF_AUTH_WITNESSED"
        elif any(row["status"] == 401 for row in private_rows) or not login_rows:
            status, reason = "MISSING_EVIDENCE", "AUTH_LOST"
        else:
            status, reason = "MISSING_EVIDENCE", "AUTH_WITNESS_INCOMPLETE"
        expected_status = "PASS" if args.mode in ("healthy", "revoke") else "MISSING_EVIDENCE"
        if args.mode == "healthy": expected_reasons = {"FORM_COOKIE_CSRF_AUTH_WITNESSED"}
        elif args.mode == "revoke": expected_reasons = {"SESSION_REFRESH_WITNESSED"}
        else: expected_reasons = {"AUTH_LOST", "AUTH_WITNESS_INCOMPLETE"}
        result = {"schemaVersion": 1, "profile": "form-cookie-csrf-v1", "mode": args.mode,
                  "status": status, "reason": reason, "nativeExit": native_exit,
                  "records": server.records, "expectedStatus": expected_status,
                  "expectedReasons": sorted(expected_reasons)}
        write_json(out / "result.json", result)
        if status != expected_status or reason not in expected_reasons:
            raise SystemExit(f"unexpected result: {status}/{reason}")
        return 0
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
