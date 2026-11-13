"""Run inside the pinned ZAP image with Docker networking disabled."""

import json
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
from urllib.parse import urlsplit


PROTECTED = "/docs"
CONTROL = "/control"
CSP_MISSING = "10038-1"


class Fixture(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in (PROTECTED, CONTROL):
            self.send_error(404)
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        if self.path == PROTECTED:
            self.send_header("Content-Security-Policy", "default-src 'self'")
        self.end_headers()
        self.wfile.write(b"<!doctype html><title>ZAP smoke test</title>")
        self.server.observed_paths.add(self.path)


def run_zap(origin, directory):
    plan = directory / "plan.yaml"
    plan.write_text(
        f"""env:
  contexts:
    - name: fixture
      urls: ["{origin}"]
  parameters:
    failOnError: true
    failOnWarning: true
jobs:
  - type: requestor
    requests:
      - url: "{origin}{PROTECTED}"
        responseCode: 200
      - url: "{origin}{CONTROL}"
        responseCode: 200
  - type: passiveScan-wait
    parameters:
      maxDuration: 1
  - type: report
    parameters:
      template: traditional-json
      reportDir: "{directory}"
      reportFile: zap-report
""",
        encoding="utf-8",
    )
    result = subprocess.run(
        ["/zap/zap.sh", "-cmd", "-autorun", str(plan)],
        stdout=sys.stderr,
        stderr=sys.stderr,
        timeout=180,
        check=False,
    )
    report_path = directory / "zap-report.json"
    report = report_path.read_text(encoding="utf-8") if report_path.is_file() else None
    if report is not None:
        sys.stdout.write(report)
    result.check_returncode()
    if report is None:
        raise ValueError("ZAP report is missing")
    return json.loads(report)


def main():
    with TemporaryDirectory() as temporary, HTTPServer(("127.0.0.1", 0), Fixture) as fixture:
        fixture.observed_paths = set()
        worker = Thread(target=fixture.serve_forever, daemon=True)
        worker.start()
        try:
            origin = f"http://127.0.0.1:{fixture.server_port}"
            report = run_zap(origin, Path(temporary))
        finally:
            fixture.shutdown()
            worker.join()

    missing_paths = {PROTECTED, CONTROL} - fixture.observed_paths
    if missing_paths:
        raise ValueError(f"Missing fixture traffic: {', '.join(sorted(missing_paths))}")

    alert_paths = {
        urlsplit(instance["uri"]).path
        for site in report["site"]
        if site["@name"] == origin
        for alert in site["alerts"]
        if alert["alertRef"] == CSP_MISSING
        for instance in alert["instances"]
    }
    if CONTROL not in alert_paths:
        raise ValueError(f"Expected ZAP alert {CSP_MISSING} on {CONTROL}")
    if PROTECTED in alert_paths:
        raise ValueError(f"CSP regression: ZAP raised {CSP_MISSING} on {PROTECTED}")
    print(f"PASS: {CSP_MISSING} detected on {CONTROL}, absent on {PROTECTED}", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        sys.exit(f"FAIL: {error}")
