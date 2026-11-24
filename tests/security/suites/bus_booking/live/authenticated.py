"""Bus Booking fixture and backend witnesses for native ZAP JWT Requestor."""

from contextlib import contextmanager
from hmac import compare_digest
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import secrets
from tempfile import TemporaryDirectory
from threading import Thread
import time

from security_framework.engine import execute_plan
from security_framework.evidence import put_evidence
from security_framework.native_jwt import CONTROL, CONTROL_RULE, MARKER, MODE, NativeJwt, identity_status

from .scanner import APP_PORT, HOST, HOP_HEADERS, MAX_BODY, ready_locations

LOGIN = "/api/auth/login"
PROFILE = "/api/auth/me"
ROLE = "USER"
CONTROL_EVENT = {"phase": "passive-control", "status": 200}


def exchange(port, method, path, body=None, headers=None):
    connection = HTTPConnection(HOST, port, timeout=5)
    try:
        connection.request(method, path, body, headers or {})
        response = connection.getresponse()
        data = response.read(MAX_BODY + 1)
        if len(data) > MAX_BODY:
            raise ValueError("oversized fixture response")
        return response.status, response.getheaders(), data
    finally:
        connection.close()


def post(path, data):
    return exchange(APP_PORT, "POST", path, json.dumps(data).encode(),
                    {"Content-Type": "application/json"})


def provision(email, password):
    ready_locations()
    status, _, body = post("/api/auth/register", {
        "email": email, "password": password, "fullName": "Native scanner fixture", "phone": "0901234567",
    })
    account = json.loads(body)
    if status != 201 or account.get("role") != ROLE or type(account.get("id")) is not int:
        raise ValueError("fixture registration failed")
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        status, _, body = exchange(8025, "GET", "/api/v1/messages")
        if status == 200:
            for message in json.loads(body).get("messages") or []:
                if any(recipient["Address"] == email for recipient in message["To"]):
                    otp = re.search(r"(?<!\d)\d{6}(?!\d)", message["Snippet"])
                    if otp and post("/api/auth/verify-email", {"email": email, "code": otp[0]})[0] == 204:
                        return account["id"]
        time.sleep(0.5)
    raise TimeoutError("fixture verification unavailable")


@contextmanager
def scoped_backend(email, password, subject):
    events = []
    issued_token = None

    class Relay(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def reject(self):
            events.append({"phase": "outside-scope", "status": 404})
            self.respond(404, (), b"")

        def respond(self, status, headers, body):
            self.send_response_only(status)
            for name, value in headers:
                if name.lower() not in HOP_HEADERS:
                    self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def do_POST(self):
            nonlocal issued_token
            size = self.headers.get("Content-Length", "")
            if (self.path != LOGIN or not size.isdigit() or not 0 < int(size) <= 4096
                    or self.headers.get_content_type() != "application/json"
                    or any(key in self.headers for key in ("Authorization", "Cookie", "Transfer-Encoding"))):
                self.reject()
                return
            try:
                submitted = json.loads(self.rfile.read(int(size)))
            except (ValueError, TimeoutError):
                self.reject()
                return
            if submitted != {"email": email, "password": password}:
                self.reject()
                return
            status, headers, body = post(LOGIN, submitted)
            data = json.loads(body)
            token = data.get("token")
            if status == 200 and data.get("tokenType") == "Bearer" and isinstance(token, str) and token:
                issued_token = token
            events.append({"phase": "login", "status": status})
            self.respond(status, headers, body)

        def do_GET(self):
            marker = self.headers.get(MARKER)
            authorization = self.headers.get("Authorization")
            if self.path == LOGIN and not (marker or authorization or self.headers.get("Cookie")):
                # ZAP fetches an optional login page before submitting JSON. Keep it inside the relay.
                events.append({"phase": "login-page", "status": 204})
                self.respond(204, (), b"")
                return
            if self.path == CONTROL and not (marker or authorization or self.headers.get("Cookie")):
                events.append(CONTROL_EVENT)
                self.respond(200, [("Content-Type", "text/html; charset=utf-8")],
                             b"<!doctype html><title>Passive detector control</title>")
                return
            if (self.path != PROFILE or marker not in (None, "anonymous", "authenticated")
                    or self.headers.get("Cookie") or len(self.headers.get_all("Authorization", [])) > 1
                    or (authorization and not authorization.startswith("Bearer "))):
                self.reject()
                return
            # Forward only the Bearer header. In particular, the Requestor marker stays in the fixture.
            sent = {"Authorization": authorization} if authorization else {}
            status, headers, body = exchange(APP_PORT, "GET", PROFILE, headers=sent)
            row = {"phase": marker or "poll", "status": status, "bearer": bool(authorization)}
            if marker == "anonymous":
                row["challenge"] = any(k.lower() == "www-authenticate" and v == "Bearer" for k, v in headers)
            if authorization:
                data = json.loads(body) if status == 200 else {}
                row.update(issuedTokenMatches=bool(issued_token and compare_digest(authorization[7:], issued_token)),
                           principalMatches=data.get("id") == subject and data.get("email") == email,
                           verified=data.get("emailVerified") is True,
                           role=ROLE if data.get("role") == ROLE else "unrecognized")
            events.append(row)
            self.respond(status, headers, body)

    with ThreadingHTTPServer((HOST, 0), Relay) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://{HOST}:{server.server_port}", events
        finally:
            server.shutdown()
            thread.join(timeout=3)


def verify(result):
    evidence = result["evidence"]
    record = evidence["scannerEvents"]
    events = record["data"]
    reason = identity_status(events, ROLE)
    if reason:
        return reason
    if record["producer"] != "fixture" or [row for row in events if row["phase"] == "passive-control"] != [CONTROL_EVENT]:
        return "SCANNER_WITNESS_MISMATCH"
    rows = evidence["zapReport"]["data"]["ruleInstances"]
    if any(row["path"] not in (PROFILE, CONTROL, LOGIN) for row in rows):
        return "SCANNER_REPORT_SCOPE_MISMATCH"
    if not any(row["path"] == CONTROL and row["alertRef"] == CONTROL_RULE for row in rows):
        return "DETECTOR_CONTROL_MISSING"
    return None


def run(result, *, bad_password):
    email = "native-scanner@security.example.com"
    password = "Fixture!" + secrets.token_hex(16)
    subject = provision(email, password)
    supplied_password = password + "-wrong" if bad_password else password
    native = NativeJwt(LOGIN, PROFILE, "email", "password", "token", subject)
    with TemporaryDirectory(prefix="bus-booking-zap-jwt-") as temporary, scoped_backend(
            email, supplied_password, subject) as (origin, events):
        directory = Path(temporary)
        reason = execute_plan(
            result, directory, origin, native.plan(origin, directory), lambda: list(events),
            lambda observed: identity_status(observed, ROLE), native_jwt=native,
            extra_environment={"FIXTURE_USER_EMAIL": email, "FIXTURE_USER_PASSWORD": supplied_password},
        )
    if reason:
        return reason
    reason = verify(result)
    if reason:
        return reason
    put_evidence(result, "scannerIdentity-scanner-jwt-user", "application-identity",
                 {ROLE: {"actor": ROLE, "status": 200}})
    put_evidence(result, "scannerOwnership", "suite-assertion", {
        "mode": MODE, "principalEvidence": "backend response",
        "credentialProvisioning": "registration and Mailpit OTP", "applicationClientLogin": False,
        "sessionExpiry": "MISSING", "sessionRenewal": "MISSING",
    })
    return None
