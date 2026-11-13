#!/usr/bin/env python3
"""Experimental OpenAPI passive import and transport qualification."""

import argparse
import json
import os
import signal
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path == "/items":
            status, body = 200, b'{"items":[{"id":"one"}]}'
        elif self.path == "/health":
            status, body = 200, b'{"status":"ok"}'
        else:
            status, body = 404, b'{"error":"not-found"}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body); self.wfile.flush()
        self.server.records.append({"method": "GET", "path": self.path, "status": status})


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute(command, cwd, log):
    with log.open("wb") as stream:
        process = subprocess.Popen(command, cwd=cwd, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=240), False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            return process.returncode, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("good", "missing-route"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    Path(os.environ.get("HOME", "/tmp/zap-openapi-home")).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler); server.records = []
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        route = "/items" if args.mode == "good" else "/missing"
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            spec = private / "openapi.json"
            zap_home = private / "zap-home"; zap_home.mkdir()
            write_json(spec, {"openapi": "3.0.3", "info": {"title": "ZAP fixture", "version": "1"},
                              "servers": [{"url": origin}], "paths": {route: {"get": {
                                  "operationId": "listItems", "responses": {"200": {
                                      "description": "fixture response", "content": {
                                          "application/json": {"schema": {"type": "object"}}}}}}}}})
            native_exit, timed_out = execute([
                "/zap/zap-api-scan.py", "-t", str(spec), "-f", "openapi", "-S",
                "-T", "2", "-D", "1", "-J", str(out / "zap-report.json"),
                "-r", str(out / "zap-report.html"),
                "-z", "-dir " + str(zap_home),
            ], out, out / "zap-api-scan.log")
        records = list(server.records)
        if timed_out:
            status, reason = "EXECUTION_ERROR", "TIMEOUT"
        elif native_exit not in (0, 1, 2) or not (out / "zap-report.json").is_file():
            status, reason = "EXECUTION_ERROR", "IMPORT_OR_REPORT_FAILURE"
        elif any(row == {"method": "GET", "path": "/items", "status": 200} for row in records):
            status, reason = "PASS", "OPENAPI_IMPORTED_AND_ITEMS_REQUEST_WITNESSED"
        elif records:
            status, reason = "MISSING_EVIDENCE", "REQUIRED_ROUTE_NOT_COVERED"
        else:
            status, reason = "EXECUTION_ERROR", "IMPORT_PRODUCED_NO_TRAFFIC"
        expected = ({"status": "PASS", "reason": "OPENAPI_IMPORTED_AND_ITEMS_REQUEST_WITNESSED"}
                    if args.mode == "good" else
                    {"status": "MISSING_EVIDENCE", "reason": "REQUIRED_ROUTE_NOT_COVERED"})
        result = {"schemaVersion": 1, "profile": "openapi-passive-v1", "mode": args.mode,
                  "status": status, "reason": reason, "nativeExit": native_exit,
                  "responses": records, "expected": expected}
        write_json(out / "result.json", result)
        if (status, reason) != (expected["status"], expected["reason"]):
            raise SystemExit(f"unexpected result: {status}/{reason}")
        return 0
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
