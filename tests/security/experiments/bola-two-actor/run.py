#!/usr/bin/env python3
"""Experimental two-actor BOLA oracle through ZAP requestor traffic."""

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
        if self.path != "/objects/alpha":
            self.send_error(404); return
        actor = self.headers.get("X-Actor")
        marker = False
        if actor == "A":
            status, marker = 200, True
        elif actor == "B" and self.server.mode == "vulnerable":
            status, marker = 200, True
        elif actor == "B" and self.server.mode == "fixed":
            status = 403
        else:
            status = 401
        body = (b'{"object":"alpha","owner":"A","marker":"owner-data"}' if marker
                else json.dumps({"error": "forbidden" if status == 403 else "auth-lost"}).encode())
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body); self.wfile.flush()
        self.server.records.append({"actor": actor or "missing", "object": "alpha",
                                    "status": status, "ownerDataMarker": marker})


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute(plan, home, log):
    with log.open("wb") as stream:
        process = subprocess.Popen(["/zap/zap.sh", "-cmd", "-dir", str(home),
                                    "-autorun", str(plan)], stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=180), False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            return process.returncode, True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("fixed", "vulnerable", "auth-lost"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.mode = args.mode; server.records = []
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        actor_b = "missing" if args.mode == "auth-lost" else "B"
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary); home = private / "home"; home.mkdir()
            plan = private / "plan.json"
            write_json(plan, {
                "env": {"contexts": [{"name": "bola", "urls": [origin]}],
                        "parameters": {"failOnError": True, "failOnWarning": False}},
                "jobs": [
                    {"type": "requestor", "requests": [
                        {"name": "owner-control", "url": origin + "/objects/alpha",
                         "method": "GET", "headers": ["X-Actor: A"]},
                        {"name": "other-actor", "url": origin + "/objects/alpha",
                         "method": "GET", "headers": ["X-Actor: " + actor_b]},
                    ]},
                    {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
                    {"type": "report", "parameters": {"template": "traditional-json",
                                                         "reportDir": str(out),
                                                         "reportFile": "zap-report"}},
                ],
            })
            native_exit, timed_out = execute(plan, home, private / "zap-private.log")
        records = list(server.records)
        if timed_out:
            status, reason = "EXECUTION_ERROR", "TIMEOUT"
        elif native_exit != 0 or not (out / "zap-report.json").is_file():
            status, reason = "EXECUTION_ERROR", "ZAP_OR_REPORT_FAILURE"
        elif len(records) != 2 or records[0] != {"actor": "A", "object": "alpha",
                                                "status": 200, "ownerDataMarker": True}:
            status, reason = "MISSING_EVIDENCE", "OWNER_CONTROL_MISSING"
        elif records[1]["status"] == 200 and records[1]["ownerDataMarker"]:
            status, reason = "REGRESSION", "OTHER_ACTOR_READ_OWNER_OBJECT"
        elif records[1]["status"] == 403:
            status, reason = "PASS", "OTHER_ACTOR_DENIED_WITH_OWNER_CONTROL"
        else:
            status, reason = "MISSING_EVIDENCE", "AUTH_LOST"
        expected = {
            "fixed": ("PASS", "OTHER_ACTOR_DENIED_WITH_OWNER_CONTROL"),
            "vulnerable": ("REGRESSION", "OTHER_ACTOR_READ_OWNER_OBJECT"),
            "auth-lost": ("MISSING_EVIDENCE", "AUTH_LOST"),
        }[args.mode]
        write_json(out / "result.json", {"schemaVersion": 1, "profile": "bola-two-actor-v1",
                   "mode": args.mode, "status": status, "reason": reason,
                   "nativeExit": native_exit, "responses": records,
                   "cleanup": {"readOnly": True, "resetRequired": False,
                               "postState": {"object": "alpha", "owner": "A"}},
                   "expected": {"status": expected[0], "reason": expected[1]}})
        if (status, reason) != expected:
            raise SystemExit(f"unexpected result: {status}/{reason}")
        return 0
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
