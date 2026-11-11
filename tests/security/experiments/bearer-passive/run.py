#!/usr/bin/env python3
"""Experimental static-bearer requestor qualification; run inside the ZAP image."""

import argparse
import json
import os
import signal
import subprocess
import tempfile
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path != "/private":
            self.send_error(404)
            return
        authorized = self.headers.get("Authorization") == "Bearer " + self.server.expected_token
        status = 200 if authorized else 401
        body = (b'{"actor":"fixture-user","marker":"private-ok"}' if authorized
                else b'{"error":"auth-lost"}')
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
        self.wfile.flush()
        self.server.records.append({"path": self.path, "status": status,
                                    "actorWitness": authorized,
                                    "markerWitness": authorized})


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_zap(plan, home, log):
    with log.open("wb") as stream:
        process = subprocess.Popen(["/zap/zap.sh", "-cmd", "-dir", str(home),
                                    "-autorun", str(plan)], stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=180), False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
            return process.returncode, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("good", "bad"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    expected = os.environ.get("EXPECTED_BEARER_TOKEN")
    supplied = os.environ.get("BEARER_TOKEN")
    if not expected or not supplied:
        raise SystemExit("bearer token environment is required")
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.expected_token = expected
    server.records = []
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    native_exit = None
    status = "EXECUTION_ERROR"
    reason = "UNCLASSIFIED"
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary)
            home = private / "home"; home.mkdir()
            plan = private / "plan.json"
            write_json(plan, {
                "env": {"contexts": [{"name": "bearer", "urls": [origin]}],
                        "parameters": {"failOnError": True, "failOnWarning": False}},
                "jobs": [
                    {"type": "requestor", "requests": [{"url": origin + "/private",
                                                          "method": "GET",
                                                          "headers": ["Authorization: Bearer " + supplied]}]},
                    {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
                    {"type": "report", "parameters": {"template": "traditional-json",
                                                         "reportDir": str(out),
                                                         "reportFile": "zap-report"}},
                ],
            })
            native_exit, timed_out = run_zap(plan, home, private / "zap-private.log")
        records = list(server.records)
        if timed_out:
            status, reason = "EXECUTION_ERROR", "TIMEOUT"
        elif native_exit != 0 or not (out / "zap-report.json").is_file():
            status, reason = "EXECUTION_ERROR", "ZAP_OR_REPORT_FAILURE"
        elif not records:
            status, reason = "MISSING_EVIDENCE", "REQUIRED_RESPONSE_MISSING"
        elif records[-1]["status"] != 200 or not records[-1]["actorWitness"]:
            status, reason = "MISSING_EVIDENCE", "AUTH_LOST"
        else:
            status, reason = "PASS", "STATIC_BEARER_ACTOR_AND_MARKER_WITNESSED"
        expected_status = "PASS" if args.mode == "good" else "MISSING_EVIDENCE"
        expected_reason = ("STATIC_BEARER_ACTOR_AND_MARKER_WITNESSED"
                           if args.mode == "good" else "AUTH_LOST")
        result = {"schemaVersion": 1, "profile": "bearer-passive-v1",
                  "mode": args.mode, "status": status, "reason": reason,
                  "nativeExit": native_exit, "responses": records,
                  "expected": {"status": expected_status, "reason": expected_reason}}
        write_json(out / "result.json", result)
        artifact_bytes = b"".join(path.read_bytes() for path in out.rglob("*") if path.is_file())
        if expected.encode() in artifact_bytes or supplied.encode() in artifact_bytes:
            raise SystemExit("secret canary leaked into artifact")
        if (status, reason) != (expected_status, expected_reason):
            raise SystemExit(f"unexpected result: {status}/{reason}")
        return 0
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
