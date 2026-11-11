"""Disposable CSP fixture and response witness for passive-http-v1."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Lock, Thread


MODES = {"healthy", "csp-regression", "missing-control", "wrong-status", "wrong-media"}


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
        status = 401 if server.mode == "wrong-status" and request_id == "docs" else 200
        media_type = ("application/json" if server.mode == "wrong-media" and request_id == "docs"
                      else "text/html")
        csp = None
        if request_id == "docs" and server.mode not in ("csp-regression", "healthy"):
            csp = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"
        if request_id == "control" and server.mode == "missing-control":
            csp = "default-src 'self'; frame-ancestors 'none'; form-action 'self'"
        body = (b'{"fixture":"csp-demo"}' if media_type == "application/json"
                else b"<!doctype html><title>ZAP regression fixture</title>")
        self.send_response(status)
        self.send_header("Content-Type", media_type + ("; charset=utf-8" if media_type == "text/html" else ""))
        self.send_header("Content-Length", str(len(body)))
        if csp is not None:
            self.send_header("Content-Security-Policy", csp)
        self.end_headers()
        try:
            self.wfile.write(body)
            self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError):
            return
        record = {
            "requestId": request_id,
            "method": "GET",
            "path": self.path,
            "status": status,
            "mediaType": media_type,
            "cspPresent": csp is not None,
            "cspNonEmpty": bool(csp and csp.strip()),
            "runId": server.run_id,
            "caseId": server.case_id,
        }
        with server.record_lock:
            server.records.append(record)


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
        self.server.record_lock = Lock()
        self.thread = Thread(target=self.server.serve_forever,
                             name="csp-demo-" + case["id"], daemon=True)

    @property
    def origin(self):
        return f"http://127.0.0.1:{self.server.server_port}"

    def start(self):
        self.thread.start()
        return self

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            raise RuntimeError("fixture thread did not stop")

    def evidence(self):
        with self.server.record_lock:
            return list(self.server.records)
