#!/usr/bin/env python3
"""Experimental one-rule reflected-XSS active scan on a disposable fixture."""

import argparse
import html
import json
import os
import signal
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import parse_qs, urlsplit


RULE_ID = "40012"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path != "/search":
            self.send_error(404); return
        query = parse_qs(parsed.query).get("q", [""])[0]
        if self.server.mode == "auth-lost":
            status, rendered = 401, "authentication required"
        else:
            status = 200
            rendered = query if self.server.mode == "vulnerable" else html.escape(query, quote=True)
        body = ("<!doctype html><title>Search</title><div id=result>" + rendered + "</div>").encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body); self.wfile.flush()
        self.server.records.append({"path": parsed.path, "status": status,
                                    "parameter": "q", "activeRule": self.headers.get("X-ZAP-Scan-ID")})


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def execute(plan, home, log):
    with log.open("wb") as stream:
        process = subprocess.Popen(["/zap/zap.sh", "-cmd", "-dir", str(home),
                                    "-autorun", str(plan)], stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
        try:
            return process.wait(timeout=300), False
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait(timeout=5)
            return process.returncode, True


def xss_instances(report):
    matches = []
    for site in report.get("site", []):
        for alert in site.get("alerts", []):
            if alert.get("pluginid") != RULE_ID:
                continue
            for instance in alert.get("instances", []):
                if urlsplit(instance.get("uri", "")).path == "/search" and instance.get("param") == "q":
                    matches.append({"alertRef": alert.get("alertRef"), "method": instance.get("method"),
                                    "path": "/search", "param": "q"})
    return matches


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("vulnerable", "fixed", "auth-lost"), required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    Path(os.environ.get("HOME", "/tmp/zap-active-home")).mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    server.mode = args.mode; server.records = []
    thread = Thread(target=server.serve_forever, daemon=True); thread.start()
    try:
        origin = f"http://127.0.0.1:{server.server_port}"
        with tempfile.TemporaryDirectory() as temporary:
            private = Path(temporary); home = private / "home"; home.mkdir()
            plan = private / "plan.json"
            write_json(plan, {
                "env": {"contexts": [{"name": "xss-fixture", "urls": [origin]}],
                        "parameters": {"failOnError": True, "failOnWarning": False}},
                "jobs": [
                    {"type": "requestor", "requests": [{"url": origin + "/search?q=seed",
                                                          "method": "GET"}]},
                    {"type": "activeScan", "parameters": {"context": "xss-fixture",
                                                             "url": origin + "/search?q=seed",
                                                             "maxRuleDurationInMins": 1,
                                                             "maxScanDurationInMins": 2,
                                                             "threadPerHost": 1,
                                                             "injectPluginIdInHeader": True},
                     "policyDefinition": {"defaultStrength": "Low", "defaultThreshold": "Off",
                                          "rules": [{"id": 40012, "name": "Reflected XSS",
                                                     "strength": "Low", "threshold": "Low"}]}},
                    {"type": "report", "parameters": {"template": "traditional-json",
                                                         "reportDir": str(out),
                                                         "reportFile": "zap-report"}},
                ],
            })
            native_exit, timed_out = execute(plan, home, out / "zap.log")
        report_path = out / "zap-report.json"
        report = json.loads(report_path.read_text()) if report_path.is_file() else {}
        zap_version = report.get("@version") if isinstance(report, dict) else None
        matches = xss_instances(report)
        active_witness = any(row.get("activeRule") == RULE_ID for row in server.records)
        has_200 = any(row["status"] == 200 for row in server.records)
        if timed_out:
            status, reason = "EXECUTION_ERROR", "TIMEOUT"
        elif native_exit != 0 or not report_path.is_file():
            status, reason = "EXECUTION_ERROR", "ZAP_OR_REPORT_FAILURE"
        elif not active_witness or not has_200:
            status, reason = "MISSING_EVIDENCE", "ACTIVE_RULE_OR_RESPONSE_WITNESS_MISSING"
        elif matches:
            status, reason = "REGRESSION", "NATIVE_REFLECTED_XSS_ALERT_PRESENT"
        else:
            status, reason = "PASS", "NATIVE_REFLECTED_XSS_ALERT_ABSENT_WITH_RULE_WITNESS"
        expected = {
            "vulnerable": ("REGRESSION", "NATIVE_REFLECTED_XSS_ALERT_PRESENT"),
            "fixed": ("PASS", "NATIVE_REFLECTED_XSS_ALERT_ABSENT_WITH_RULE_WITNESS"),
            "auth-lost": ("MISSING_EVIDENCE", "ACTIVE_RULE_OR_RESPONSE_WITNESS_MISSING"),
        }[args.mode]
        write_json(out / "result.json", {"schemaVersion": 1, "profile": "active-xss-v1",
                   "mode": args.mode, "status": status, "reason": reason,
                   "nativeExit": native_exit, "ruleId": RULE_ID,
                   "zapVersion": zap_version,
                   "activeRequestWitness": active_witness, "responseCount": len(server.records),
                   "nativeMatches": matches,
                   "expected": {"status": expected[0], "reason": expected[1]}})
        if (status, reason) != expected:
            raise SystemExit(f"unexpected result: {status}/{reason}")
        return 0
    finally:
        server.shutdown(); server.server_close(); thread.join(timeout=5)


if __name__ == "__main__":
    raise SystemExit(main())
