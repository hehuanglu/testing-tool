"""Pinned ZAP worker. The only forwarded product traffic is an anonymous locations GET."""

from contextlib import contextmanager
from http.client import HTTPConnection, HTTPException
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import time

from security_framework.engine import UPDATES, execute_plan
from security_framework.evidence import put_evidence, validate_scan_evidence

HOST = "127.0.0.1"
APP_PORT = 8085
PROXY_PORT = 8090
LOCATIONS = "/api/locations"
CONTROL = "/__pilot_passive_control"
CSP_CONTROL = "10038-1"
HOP_HEADERS = {"connection", "content-length", "keep-alive", "proxy-authenticate", "proxy-authorization",
               "te", "trailer", "transfer-encoding", "upgrade", "set-cookie"}
MAX_BODY = 65536


def fetch(port, path):
    connection = HTTPConnection(HOST, port, timeout=4)
    try:
        connection.request("GET", path)
        response = connection.getresponse()
        body = response.read(MAX_BODY + 1)
        if len(body) > MAX_BODY:
            raise ValueError("oversized fixture response")
        return response.status, response.getheaders(), body
    finally:
        connection.close()


def ready_locations():
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            status, headers, body = fetch(APP_PORT, LOCATIONS)
            if status == 200 and isinstance(json.loads(body), list):
                return status, headers, body
        except (OSError, HTTPException, ValueError):
            pass
        time.sleep(0.5)
    raise TimeoutError("application unavailable")


@contextmanager
def relay():
    events = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *unused):
            pass

        def do_GET(self):
            if self.path not in (LOCATIONS, CONTROL) or any(
                    self.headers.get(header) for header in ("Authorization", "Cookie", "Proxy-Authorization")):
                events.append({"route": "outside-reviewed-scope", "status": 404, "origin": "relay"})
                self.send_error(404)
                return
            if self.path == CONTROL:
                status, headers, body = (200, [("Content-Type", "text/html; charset=utf-8")],
                                         b"<!doctype html><title>Passive detector control</title>")
                source = "synthetic-control"
            else:
                status, headers, body = fetch(APP_PORT, LOCATIONS)
                source = "bus-booking"
            events.append({"route": self.path, "status": status, "origin": source})
            self.send_response_only(status)
            for key, value in headers:
                if key.lower() not in HOP_HEADERS:
                    self.send_header(key, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    with ThreadingHTTPServer((HOST, 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://{HOST}:{server.server_port}", events
        finally:
            server.shutdown()
            thread.join(timeout=3)


def proxy_witness(directory, origin, events, direct):
    home = directory / "proxy-home"
    home.mkdir()
    args = ["/zap/zap.sh", "-Xmx768m", "-daemon", "-dir", str(home), "-host", HOST,
            "-port", str(PROXY_PORT), "-config", "api.enabled=false", "-config", "view.mode=safe"]
    for key in UPDATES:
        args.extend(("-config", key + "=false"))
    with (home / "console").open("wb") as console:
        child = subprocess.Popen(args, stdout=console, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if child.poll() is not None:
                    raise OSError("proxy stopped")
                try:
                    with socket.create_connection((HOST, PROXY_PORT), timeout=0.5):
                        break
                except OSError:
                    time.sleep(0.25)
            else:
                raise TimeoutError("proxy unavailable")
            status, _, body = fetch(PROXY_PORT, origin + LOCATIONS)
            return {"method": "GET", "path": LOCATIONS, "status": status,
                    "directStatus": direct[0], "bodyMatchesDirect": body == direct[2],
                    "upstreamWitnesses": list(events), "mode": "safe", "apiEnabled": False}
        finally:
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    child.wait(timeout=5)


def plan(origin, directory):
    return {
        "env": {"contexts": [{"name": "bus-booking-public", "urls": [origin]}],
                "parameters": {"failOnError": True, "failOnWarning": False}},
        "jobs": [
            {"type": "requestor", "requests": [
                {"url": origin + route, "method": "GET", "responseCode": 200}
                for route in (LOCATIONS, CONTROL)
            ]},
            {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
            {"type": "report", "parameters": {
                "template": "traditional-json", "reportDir": str(directory), "reportFile": "zap-report",
            }},
        ],
    }


def verify_witnesses(evidence):
    witness = evidence["proxyWitness"]["data"]
    expected_events = [{"route": LOCATIONS, "status": 200, "origin": "bus-booking"}]
    if (witness != {"method": "GET", "path": LOCATIONS, "status": 200, "directStatus": 200,
                    "bodyMatchesDirect": True, "upstreamWitnesses": expected_events, "mode": "safe",
                    "apiEnabled": False} or evidence["proxyWitness"]["producer"] != "suite-assertion"):
        return "PROXY_WITNESS_MISMATCH"
    if (evidence["scannerEvents"]["data"] !=
            [*expected_events, {"route": CONTROL, "status": 200, "origin": "synthetic-control"}]
            or evidence["scannerEvents"]["producer"] != "fixture"):
        return "SCANNER_WITNESS_MISMATCH"
    validate_scan_evidence(evidence)
    rows = evidence["zapReport"]["data"]["ruleInstances"]
    if any(row["path"] not in (LOCATIONS, CONTROL) for row in rows):
        return "SCANNER_REPORT_SCOPE_MISMATCH"
    if not any(row["path"] == CONTROL and str(row["alertRef"]) == CSP_CONTROL for row in rows):
        return "DETECTOR_CONTROL_MISSING"
    return None


def scanner(result):
    direct = ready_locations()
    with TemporaryDirectory(prefix="bus-booking-zap-") as temporary, relay() as (origin, events):
        directory = Path(temporary)
        witness = proxy_witness(directory, origin, events, direct)
        put_evidence(result, "proxyWitness", "suite-assertion", witness)
        events.clear()
        error = execute_plan(result, directory, origin, plan(origin, directory), lambda: list(events))
    return error or verify_witnesses(result["evidence"])


def main():
    result = {"runId": sys.argv[1], "evidence": {}}
    try:
        lane = sys.argv[2] if len(sys.argv) > 2 else "passive"
        if lane == "passive":
            result["reason"] = scanner(result)
        else:
            from .authenticated import run
            if lane not in ("authenticated-passive", "authenticated-passive-bad-password"):
                raise ValueError("unknown scanner lane")
            result["reason"] = run(result, bad_password=lane.endswith("-bad-password"))
    except TimeoutError:
        result["reason"] = "INCOMPLETE_EXECUTION"
    except (OSError, ValueError, KeyError, HTTPException, subprocess.SubprocessError):
        result["reason"] = "SCANNER_EVIDENCE_FAILURE"
    print(json.dumps(result, allow_nan=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
