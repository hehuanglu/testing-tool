"""Disposable CSP fixture and response witness for passive-http-v1."""

from __future__ import annotations

import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread


DOCS_MARKER = "zap-ci-docs-page"
LOGIN_MARKER = "zap-ci-login-page"
CONTROL_MARKER = "zap-ci-detector-control"
RESPONSE_ID_HEADER = "X-Fixture-Response-Id"
CSP = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"
MODES = {"healthy", "csp-regression", "missing-control", "wrong-status", "wrong-media",
         "wrong-page", "duplicate-docs"}


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        server = self.server
        request_id = server.request_by_path.get(self.path)
        if request_id is None:
            self.send_error(404)
            return
        with server.record_lock:
            server.sequence += 1
            if request_id == "docs":
                server.docs_count += 1
            self.send_fixture_response(request_id, server.sequence, server.docs_count)

    def send_fixture_response(self, request_id, sequence, docs_count):
        server = self.server
        is_docs = request_id == "docs"
        status = 401 if server.mode == "wrong-status" and is_docs else 200
        media_type = ("application/json" if server.mode == "wrong-media" and is_docs
                      else "text/html")
        has_csp = is_docs and server.mode != "csp-regression"
        marker = DOCS_MARKER if is_docs else CONTROL_MARKER
        if is_docs and server.mode == "wrong-page":
            marker = LOGIN_MARKER
        if is_docs and server.mode == "duplicate-docs":
            has_csp = docs_count != 1
            if has_csp:
                marker = LOGIN_MARKER
        if request_id == "control" and server.mode == "missing-control":
            has_csp = True
        csp = CSP if has_csp else None
        body = (b'{"fixture":"csp-demo"}' if media_type == "application/json"
                else f"<!doctype html><title>{marker}</title>".encode("ascii"))
        response_id = f"{server.run_id}-{sequence}"
        self.send_response(status)
        self.send_header("Content-Type", media_type + ("; charset=utf-8" if media_type == "text/html" else ""))
        self.send_header("Content-Length", str(len(body)))
        self.send_header(RESPONSE_ID_HEADER, response_id)
        if csp is not None:
            self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        server.records.append({
            "requestId": request_id,
            "method": "GET",
            "path": self.path,
            "url": f"http://127.0.0.1:{server.server_port}{self.path}",
            "status": status,
            "mediaType": media_type,
            "cspPresent": csp is not None,
            "cspNonEmpty": bool(csp and csp.strip()),
            "sequence": sequence,
            "responseId": response_id,
            "bodyMarkers": [value for value in (DOCS_MARKER, LOGIN_MARKER, CONTROL_MARKER)
                            if value.encode("ascii") in body],
            "bodySha256": hashlib.sha256(body).hexdigest(),
            "runId": server.run_id,
            "caseId": server.case_id,
        })


class FixtureServer:
    def __init__(self, case, run_id: str, mode: str = "healthy"):
        if mode not in MODES:
            raise ValueError("unsupported CSP fixture qualification mode")
        self.case = case
        self.mode = mode
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        self.server.daemon_threads = True
        self.server.mode = mode
        self.server.run_id = run_id
        self.server.case_id = case["id"]
        self.server.request_by_path = {row["path"]: row["id"] for row in case["requests"]}
        self.server.records = []
        self.server.sequence = 0
        self.server.docs_count = 0
        self.server.record_lock = Lock()
        self.thread = Thread(target=self.server.serve_forever,
                             name="csp-demo-" + case["id"], daemon=True)
        self.started = False

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self):
        self.thread.start()
        self.started = True
        return self

    def stop(self):
        try:
            if self.started or self.thread.is_alive():
                self.server.shutdown()
                self.thread.join(timeout=5)
                if self.thread.is_alive():
                    raise RuntimeError("fixture thread did not stop")
        finally:
            self.server.server_close()

    def evidence(self):
        with self.server.record_lock:
            return list(self.server.records)
