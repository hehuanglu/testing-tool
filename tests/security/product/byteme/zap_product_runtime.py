#!/usr/bin/env python3
"""Run one ByteMe passive HTTP case in an isolated ZAP container.

The target lifecycle is owned by the host adapter. This process owns only the
ZAP daemon and a loopback detector-control origin. Product and detector traffic
are both sent by ZAP and read back from ZAP history before classification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from anti_framing import evaluate_anti_framing


ZAP_CONFIG = (
    "api.disablekey=true",
    "alert.maxInstances=0",
    "alert.mergeissues=false",
    "autoupdate.checkOnStart=false",
    "start.checkForUpdates=false",
    "start.downloadNewRelease=false",
    "start.checkAddonUpdates=false",
    "start.installAddonUpdates=false",
)


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("wb") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


class ControlHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format, *_args):
        return

    def do_GET(self):
        if self.path != "/control":
            self.send_error(404)
            return
        body = b"<!doctype html><title>detector control</title>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def api(origin, component, operation, name, **params):
    query = urllib.parse.urlencode({key: str(value) for key, value in params.items()})
    url = f"{origin}/JSON/{component}/{operation}/{name}/"
    if query:
        url += "?" + query
    with urllib.request.urlopen(url, timeout=10) as response:
        value = json.loads(response.read().decode("utf-8"))
    if isinstance(value, dict) and value.get("code") and value.get("message"):
        raise RuntimeError(f"ZAP API {value['code']}: {value['message']}")
    return value


def wait_api(origin, deadline):
    last = None
    while time.monotonic() < deadline:
        try:
            value = api(origin, "core", "view", "version")
            version = value.get("version")
            if version:
                return version
        except Exception as error:  # daemon can reset while booting
            last = error
        time.sleep(0.5)
    raise TimeoutError("ZAP_API_START_TIMEOUT") from last


def wait_passive(origin, deadline):
    while time.monotonic() < deadline:
        value = api(origin, "pscan", "view", "recordsToScan")
        if int(value.get("recordsToScan", "-1")) == 0:
            return
        time.sleep(0.5)
    raise TimeoutError("ZAP_PASSIVE_SCAN_TIMEOUT")


def headers(raw):
    rows = raw.splitlines()
    result = {}
    for row in rows[1:]:
        if not row.strip():
            break
        if ":" in row:
            key, value = row.split(":", 1)
            result.setdefault(key.strip().lower(), []).append(value.strip())
    return rows[0] if rows else "", result


def message_url(message):
    request_line, request_headers = headers(message.get("requestHeader", ""))
    parts = request_line.split()
    if len(parts) < 2:
        return None, None
    method, target = parts[0].upper(), parts[1]
    if target.startswith("http://") or target.startswith("https://"):
        return method, target
    host = (request_headers.get("host") or [None])[-1]
    if not host:
        return method, None
    return method, "http://" + host + target


def response_witness(message, request_id, expected_url):
    method, actual_url = message_url(message)
    status_line, response_headers = headers(message.get("responseHeader", ""))
    match = re.match(r"^HTTP/\S+\s+(\d{3})(?:\s|$)", status_line)
    body = message.get("responseBody", "")
    csp = (response_headers.get("content-security-policy") or [None])[-1]
    content_type = (response_headers.get("content-type") or [""])[-1]
    media_type = content_type.split(";", 1)[0].strip().lower()
    return {
        "actualUrl": actual_url,
        "bodyLength": len(body.encode("utf-8")),
        "bodySha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
        "cspNonEmpty": bool(csp and csp.strip()),
        "cspPresent": csp is not None,
        "policyHeaders": {
            name: list(response_headers.get(name, []))
            for name in ("content-security-policy",
                         "content-security-policy-report-only",
                         "x-frame-options")
            if response_headers.get(name)
        },
        "expectedUrl": expected_url,
        "mediaType": media_type,
        "messageId": str(message.get("id", "")),
        "method": method,
        "requestId": request_id,
        "responseHeaderNames": sorted(response_headers),
        "status": int(match.group(1)) if match else None,
        "swaggerUiMarker": ("swagger ui" in body.lower() and "swagger-ui" in body.lower()),
    }


def find_message(messages, expected_url):
    matches = []
    for message in messages:
        method, url = message_url(message)
        if method == "GET" and url == expected_url:
            matches.append(message)
    return matches[-1] if matches else None


def alert_row(alert):
    return {
        "alert": alert.get("alert"),
        "alertId": str(alert.get("id", "")),
        "alertRef": str(alert.get("alertRef", "")),
        "confidence": alert.get("confidence"),
        "method": str(alert.get("method", "")).upper(),
        "param": alert.get("param"),
        "pluginId": str(alert.get("pluginId", "")),
        "risk": alert.get("risk"),
        "url": alert.get("url"),
    }


def matching_alerts(alerts, *, url, method, alert_ref):
    return [row for row in alerts
            if (row.get("url"), row.get("method"), row.get("alertRef"))
            == (url, method, alert_ref)]


def classify(case, responses, alerts, url_by_id):
    by_id = {row["requestId"]: row for row in responses}
    for request in case["requests"]:
        witness = by_id.get(request["id"])
        if witness is None:
            return "MISSING_EVIDENCE", "REQUIRED_RESPONSE_MISSING"
        if case["profile"] == "anti-framing-http-v1":
            if witness.get("status") != case["requireResponses"]["status"]:
                return "MISSING_EVIDENCE", "RESPONSE_STATUS_MISMATCH"
            if witness.get("mediaType") != case["requireResponses"]["mediaType"]:
                return "MISSING_EVIDENCE", "RESPONSE_MEDIA_TYPE_MISMATCH"
        if witness.get("actualUrl") != url_by_id[request["id"]] or witness.get("method") != "GET":
            return "MISSING_EVIDENCE", "RESPONSE_IDENTITY_MISMATCH"
        if (case["profile"] != "anti-framing-http-v1"
                and witness.get("status") != case["requireResponses"]["status"]):
            return "MISSING_EVIDENCE", "RESPONSE_STATUS_MISMATCH"
        if (case["profile"] != "anti-framing-http-v1"
                and witness.get("mediaType") != case["requireResponses"]["mediaType"]):
            return "MISSING_EVIDENCE", "RESPONSE_MEDIA_TYPE_MISMATCH"
    expect = case["expect"]
    if case["profile"] == "anti-framing-http-v1":
        product = by_id[expect["evaluateOn"]]
        if not product.get("swaggerUiMarker"):
            return "MISSING_EVIDENCE", "SWAGGER_DOCUMENT_MARKER_MISSING"
        evaluation = evaluate_anti_framing(product.get("policyHeaders", {}))
        product["antiFraming"] = evaluation
        if evaluation["state"] == "protected":
            return "PASS", "ANTI_FRAMING_POLICY_PROTECTED"
        if evaluation["state"] == "unprotected":
            return "REGRESSION", "ANTI_FRAMING_POLICY_UNPROTECTED"
        return "MISSING_EVIDENCE", "ANTI_FRAMING_POLICY_INDETERMINATE"
    control = expect["presentOn"]
    product = expect["absentOn"]
    control_hits = matching_alerts(alerts, url=url_by_id[control], method="GET",
                                   alert_ref=expect["alertRef"])
    if not control_hits:
        return "MISSING_EVIDENCE", "CONTROL_ALERT_MISSING"
    product_hits = matching_alerts(alerts, url=url_by_id[product], method="GET",
                                   alert_ref=expect["alertRef"])
    if product_hits:
        return "REGRESSION", "PROTECTED_ALERT_PRESENT"
    csp = by_id.get(expect["requireNonEmptyCspOn"])
    if not csp or not csp.get("cspNonEmpty"):
        return "MISSING_EVIDENCE", "INCONSISTENT_OBSERVATION"
    return "PASS", "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER"


def run(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    case = json.loads(Path(args.case).read_text(encoding="utf-8"))
    started = time.monotonic()
    deadline = started + args.deadline
    control = ThreadingHTTPServer(("127.0.0.1", 0), ControlHandler)
    control.daemon_threads = True
    control_thread = Thread(target=control.serve_forever, name="detector-control", daemon=True)
    control_thread.start()
    api_port_socket = socket.socket()
    api_port_socket.bind(("127.0.0.1", 0))
    api_port = api_port_socket.getsockname()[1]
    api_port_socket.close()
    api_origin = f"http://127.0.0.1:{api_port}"
    zap_home = out / "zap-home"
    zap_home.mkdir(exist_ok=True)
    zap_log = (out / "zap.log").open("wb")
    config_args = [value for config in ZAP_CONFIG for value in ("-config", config)]
    process = subprocess.Popen([
        "/zap/zap.sh", "-daemon", "-host", "127.0.0.1", "-port", str(api_port),
        "-dir", str(zap_home), *config_args,
    ], stdout=zap_log, stderr=subprocess.STDOUT, start_new_session=True)
    result = None
    try:
        version = wait_api(api_origin, deadline)
        product_origin = args.product_origin.rstrip("/")
        control_origin = f"http://127.0.0.1:{control.server_port}"
        url_by_id = {}
        sent = []
        for request in case["requests"]:
            origin = product_origin if request["origin"] == "product" else control_origin
            path = request["path"]
            if args.fault_mode in ("wrong-response", "wrong-media") and request["origin"] == "product":
                path = "/openapi.yaml"
            elif args.fault_mode == "wrong-status" and request["origin"] == "product":
                path = "/anti-framing-control-not-found"
            url = origin + path
            url_by_id[request["id"]] = origin + request["path"]
            if request["id"] == args.omit_request_id:
                continue
            request_text = (f"GET {url} HTTP/1.1\r\n"
                            f"Host: {urllib.parse.urlsplit(url).netloc}\r\n"
                            "Accept: text/html\r\nConnection: close\r\n\r\n")
            response = api(api_origin, "core", "action", "sendRequest",
                           request=request_text, followRedirects="false")
            receipt_ids = [str(row.get("id", ""))
                           for row in response.get("sendRequest", [])
                           if isinstance(row, dict)]
            sent.append({"requestId": request["id"], "url": url,
                         "apiReceiptMessageIds": receipt_ids})
        wait_passive(api_origin, deadline)
        raw_messages = api(api_origin, "core", "view", "messages", start=0, count=1000)
        messages = raw_messages.get("messages", [])
        responses = []
        native_messages = []
        for request in case["requests"]:
            expected = url_by_id[request["id"]]
            actual = expected
            if args.fault_mode in ("wrong-response", "wrong-media") and request["origin"] == "product":
                actual = product_origin + "/openapi.yaml"
            elif args.fault_mode == "wrong-status" and request["origin"] == "product":
                actual = product_origin + "/anti-framing-control-not-found"
            message = find_message(messages, actual)
            if message is not None:
                responses.append(response_witness(message, request["id"], expected))
                if args.retain_native_message:
                    native_messages.append({
                        "expectedUrl": expected,
                        "message": message,
                        "requestId": request["id"],
                    })
        raw_alerts = api(api_origin, "core", "view", "alerts", start=0, count=1000)
        alerts = [alert_row(row) for row in raw_alerts.get("alerts", [])]
        status, reason = classify(case, responses, alerts, url_by_id)
        atomic_json(out / "zap-history.json", {
            "readback": "ZAP core messages API",
            "responses": responses,
            "sentReceipts": sent,
        })
        atomic_json(out / "zap-alerts.json", {
            "alerts": alerts,
            "readback": "ZAP core alerts API",
        })
        atomic_json(out / "evidence.json", {
            "detectorControlOrigin": control_origin,
            "detectorControlPurpose": (
                "Confirms ZAP rule 10038-1 only; not ByteMe evidence."
                if case["profile"] == "passive-http-v1" else None),
            "productOrigin": product_origin,
            "responses": responses,
            "matchedAlertIds": ({
                request["id"]: [row["alertId"] for row in matching_alerts(
                    alerts, url=url_by_id[request["id"]], method="GET",
                    alert_ref=case["expect"]["alertRef"])]
                for request in case["requests"]
            } if case["profile"] == "passive-http-v1" else {}),
            "zapVersion": version,
        })
        if args.retain_native_message:
            atomic_json(out / "native-message.json", {
                "purpose": "private-assessment-native-readback",
                "responses": native_messages,
                "zapVersion": version,
            })
        result = {"status": status, "reason": reason, "nativeExit": 0,
                  "zapVersion": version}
    except TimeoutError as error:
        result = {"status": "EXECUTION_ERROR", "reason": str(error), "nativeExit": None}
    except Exception as error:
        result = {"status": "EXECUTION_ERROR",
                  "reason": "ZAP_RUNTIME_ERROR:" + type(error).__name__, "nativeExit": None}
        (out / "runtime-error.txt").write_text(type(error).__name__ + ": " + str(error) + "\n",
                                               encoding="utf-8")
    finally:
        try:
            if process.poll() is None:
                try:
                    api(api_origin, "core", "action", "shutdown")
                except Exception:
                    os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)
        finally:
            zap_log.close()
            control.shutdown()
            control.server_close()
            control_thread.join(timeout=5)
            shutil.rmtree(zap_home, ignore_errors=True)
    if not (out / "evidence.json").exists():
        atomic_json(out / "evidence.json", {"responses": []})
    atomic_json(out / "runtime-result.json", result)
    return 0 if result["status"] == "PASS" else 1


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--product-origin", required=True)
    parser.add_argument("--omit-request-id")
    parser.add_argument("--retain-native-message", action="store_true")
    parser.add_argument("--fault-mode",
                        choices=("none", "wrong-response", "wrong-status", "wrong-media"),
                        default="none")
    parser.add_argument("--deadline", type=float, default=180.0)
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
