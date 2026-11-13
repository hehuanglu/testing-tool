#!/usr/bin/env python3
"""Reproducible live qualification for the ByteMe product adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


SECURITY = Path(__file__).resolve().parents[2]
ROOT = SECURITY.parents[1]
CASE_DIRS = {
    "csp": SECURITY / "product-cases",
    "anti-framing": SECURITY / "product-anti-framing-cases",
}
RUNNER = SECURITY / "run_zap_product_suite.sh"
SCENARIOS = {
    "fixed": ("fixed-control", "none", None, "PASS",
              "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER", 0),
    "original": ("upstream-original", "none", None, "REGRESSION",
                 "PROTECTED_ALERT_PRESENT", 1),
    "regression": ("regression-control", "none", None, "REGRESSION",
                   "PROTECTED_ALERT_PRESENT", 1),
    "missing": ("fixed-control", "none", "swagger-index", "MISSING_EVIDENCE",
                "REQUIRED_RESPONSE_MISSING", 1),
    "wrong-response": ("fixed-control", "wrong-response", None, "MISSING_EVIDENCE",
                       "RESPONSE_IDENTITY_MISMATCH", 1),
    "startup-failure": ("fixed-control", "startup-failure", None, "EXECUTION_ERROR",
                        "ADAPTER_ERROR:AdapterError", 1),
    "scanner-timeout": ("fixed-control", "scanner-timeout", None, "EXECUTION_ERROR",
                        "ZAP_API_START_TIMEOUT", 1),
    "cleanup-failure": ("fixed-control", "cleanup-failure", None, "EXECUTION_ERROR",
                        "INJECTED_CLEANUP_FAILURE", 1),
}
ANTI_FRAMING_SCENARIOS = {
    "original": ("upstream-original", "none", None, "PASS",
                 "ANTI_FRAMING_POLICY_PROTECTED", 0),
    "csp-none": ("anti-csp-none", "none", None, "PASS",
                 "ANTI_FRAMING_POLICY_PROTECTED", 0),
    "absent": ("anti-no-protection", "none", None, "REGRESSION",
               "ANTI_FRAMING_POLICY_UNPROTECTED", 1),
    "report-only": ("anti-report-only", "none", None, "REGRESSION",
                    "ANTI_FRAMING_POLICY_UNPROTECTED", 1),
    "wide-csp-xfo": ("anti-wide-csp-xfo", "none", None, "REGRESSION",
                     "ANTI_FRAMING_POLICY_UNPROTECTED", 1),
    "missing": ("upstream-original", "none", "swagger-index", "MISSING_EVIDENCE",
                "REQUIRED_RESPONSE_MISSING", 1),
    "wrong-status": ("upstream-original", "wrong-status", None, "MISSING_EVIDENCE",
                     "RESPONSE_STATUS_MISMATCH", 1),
    "wrong-media": ("upstream-original", "wrong-media", None, "MISSING_EVIDENCE",
                    "RESPONSE_MEDIA_TYPE_MISMATCH", 1),
    "malformed": ("anti-malformed", "none", None, "MISSING_EVIDENCE",
                  "ANTI_FRAMING_POLICY_INDETERMINATE", 1),
}
FORBIDDEN = ("-----BEGIN PRIVATE KEY-----", "ByteMeDemo!2026", "MYSQL_PASSWORD=",
             "DB_PASSWORD=", '"responseBody"')


def digest_tree(path: Path):
    rows = []
    for item in sorted(path.rglob("*")):
        if item.is_file():
            rows.append((str(item.relative_to(path)), hashlib.sha256(item.read_bytes()).hexdigest()))
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def assert_artifact(directory: Path, expected_status, expected_reason, expected_exit,
                    actual_exit, source_sha, profile):
    if actual_exit != expected_exit:
        raise AssertionError(f"exit {actual_exit}, expected {expected_exit}")
    suite = json.loads((directory / "suite-results.json").read_text(encoding="utf-8"))
    if suite["caseCount"] != 1:
        raise AssertionError("qualification scenario must retain exactly one case result")
    result = suite["cases"][0]
    if (result["status"], result["reason"]) != (expected_status, expected_reason):
        raise AssertionError(f"actual {(result['status'], result['reason'])}, "
                             f"expected {(expected_status, expected_reason)}")
    case_dir = directory / result["id"]
    for key in ("targetIdentityPath", "cleanupPath"):
        if not (case_dir / result[key]).is_file():
            raise AssertionError(f"retained artifact reference {key} does not exist")
    evidence_path = result.get("evidencePath")
    if evidence_path is not None and not (case_dir / evidence_path).is_file():
        raise AssertionError("retained evidence reference does not exist")
    identity = json.loads((case_dir / result["targetIdentityPath"]).read_text(encoding="utf-8"))
    if identity["actualCommitSha"] != source_sha or identity["expectedCommitSha"] != source_sha:
        raise AssertionError("target source SHA binding mismatch")
    cleanup = json.loads((case_dir / result["cleanupPath"]).read_text(encoding="utf-8"))
    if any(row["state"] not in ("removed", "absent") for row in cleanup["records"]):
        raise AssertionError("owned resource cleanup is incomplete")
    if any(path.name == "zap-home" for path in case_dir.rglob("zap-home")):
        raise AssertionError("temporary ZAP home leaked into artifact")
    for path in case_dir.rglob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for canary in FORBIDDEN:
            if canary in text:
                raise AssertionError(f"forbidden artifact canary {canary!r} in {path}")
    if expected_status != "EXECUTION_ERROR":
        if evidence_path is None:
            raise AssertionError("non-execution result must retain ZAP evidence")
        evidence = json.loads((case_dir / evidence_path).read_text(encoding="utf-8"))
        if evidence.get("zapVersion") != "2.17.0":
            raise AssertionError("unexpected ZAP version")
        if profile == "csp":
            if evidence.get("detectorControlPurpose") != (
                    "Confirms ZAP rule 10038-1 only; not ByteMe evidence."):
                raise AssertionError("detector control provenance missing")
        elif evidence.get("detectorControlPurpose") is not None:
            raise AssertionError("anti-framing evidence must not claim a detector control")
        if profile == "anti-framing" and expected_status in ("PASS", "REGRESSION"):
            responses = evidence.get("responses", [])
            if (len(responses) != 1 or not responses[0].get("swaggerUiMarker")
                    or responses[0].get("antiFraming", {}).get("state") not in
                    ("protected", "unprotected")):
                raise AssertionError("anti-framing semantic response evidence is incomplete")
    if expected_reason == "INJECTED_CLEANUP_FAILURE":
        if result.get("preCleanupStatus") != "PASS":
            raise AssertionError("cleanup failure did not retain the preceding PASS result")
    return suite, identity, cleanup


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--product-source", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--scenario",
                        choices=("all", *sorted(set(SCENARIOS) | set(ANTI_FRAMING_SCENARIOS))),
                        default="all")
    parser.add_argument("--profile", choices=("csp", "anti-framing"), default="csp")
    parser.add_argument("--deadline", type=float, default=600.0)
    args = parser.parse_args(argv)
    out = Path(args.out).resolve()
    if out.exists() and any(out.iterdir()):
        raise SystemExit("qualification output must be new or empty")
    out.mkdir(parents=True, exist_ok=True)
    source = Path(args.product_source).resolve()
    source_sha = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"],
                                         text=True).strip()
    scenarios = SCENARIOS if args.profile == "csp" else ANTI_FRAMING_SCENARIOS
    if args.scenario != "all" and args.scenario not in scenarios:
        raise SystemExit(f"scenario {args.scenario!r} is unavailable for {args.profile}")
    selected = list(scenarios) if args.scenario == "all" else [args.scenario]
    records = []
    for name in selected:
        variant, fault, omit, status, reason, expected_exit = scenarios[name]
        scenario_out = out / name
        command = ["bash", str(RUNNER), "--cases", str(CASE_DIRS[args.profile]), "--out", str(scenario_out),
                   "--product-source", str(source), "--variant", variant,
                   "--fault-mode", fault, "--deadline", str(args.deadline)]
        if omit:
            command.extend(["--omit-request-id", omit])
        completed = subprocess.run(command, cwd=ROOT, env=os.environ.copy())
        suite, identity, cleanup = assert_artifact(
            scenario_out, status, reason, expected_exit, completed.returncode, source_sha,
            args.profile)
        records.append({
            "actual": {"reason": suite["cases"][0]["reason"],
                       "status": suite["cases"][0]["status"]},
            "artifactSha256": digest_tree(scenario_out),
            "cleanupRecords": len(cleanup["records"]),
            "expected": {"exit": expected_exit, "reason": reason, "status": status},
            "name": name,
            "targetActualCommitSha": identity["actualCommitSha"],
            "variant": variant,
        })
    result = {"caseSource": "product-qualification", "profile": args.profile, "product": "ByteMe",
              "productCommitSha": source_sha, "scenarioCount": len(records),
              "scenarios": records, "status": "PASS"}
    (out / "byteme-qualification-results.json").write_text(
        json.dumps(result, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "PASS", "scenarios": len(records)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
