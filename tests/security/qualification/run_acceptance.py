#!/usr/bin/env python3
"""Run real-ZAP controls through the same local/CI entrypoint."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


SECURITY = Path(__file__).resolve().parents[1]
REPO = SECURITY.parents[1]
WRAPPER = SECURITY / "run_zap_suite.sh"
CASES = SECURITY / "cases"


SCENARIOS = {
    "LIVE-01": {"args": [], "exit": 0, "status": "PASS",
                "reason": "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER"},
    "LIVE-02": {"args": ["--fixture-mode", "csp-regression"], "exit": 1,
                "status": "REGRESSION", "reason": "PROTECTED_ALERT_PRESENT"},
    "LIVE-03": {"args": ["--omit-request-id", "docs"], "exit": 1,
                "status": "MISSING_EVIDENCE", "reason": "REQUIRED_RESPONSE_MISSING"},
    "LIVE-04": {"args": ["--fixture-mode", "missing-control"], "exit": 1,
                "status": "MISSING_EVIDENCE", "reason": "CONTROL_ALERT_MISSING"},
    "LIVE-05-status": {"args": ["--fixture-mode", "wrong-status"], "exit": 1,
                "status": "MISSING_EVIDENCE", "reason": "RESPONSE_STATUS_MISMATCH"},
    "LIVE-05-media": {"args": ["--fixture-mode", "wrong-media"], "exit": 1,
                "status": "MISSING_EVIDENCE", "reason": "RESPONSE_MEDIA_TYPE_MISMATCH"},
    "LIVE-06": {"args": ["--deadline", "0.01"], "exit": 1,
                "status": "EXECUTION_ERROR", "reason": "TIMEOUT"},
}


def run_one(name, specification, root, cases=CASES):
    output = root / name
    command = ["bash", str(WRAPPER), "--cases", str(cases), "--out", str(output),
               *specification["args"]]
    process = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=240)
    result_path = output / "suite-results.json"
    if not result_path.is_file():
        raise AssertionError(f"{name}: suite-results.json missing; stderr={process.stderr[-1000:]}")
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if len(result.get("cases", [])) != 1:
        raise AssertionError(f"{name}: expected exactly one case")
    case = result["cases"][0]
    actual = {"exit": process.returncode, "status": case["status"], "reason": case["reason"]}
    expected = {key: specification[key] for key in ("exit", "status", "reason")}
    if actual != expected:
        raise AssertionError(f"{name}: expected {expected}, got {actual}")
    if name == "LIVE-02":
        evidence = json.loads((output / case["evidencePath"]).read_text(encoding="utf-8"))
        pointers = evidence.get("matchedAlertPointers", [])
        if len(pointers) < 2:
            raise AssertionError("LIVE-02: expected distinct control and docs alert instances")
    return {
        "scenarioId": name,
        "mode": "live-local",
        "command": command,
        "expected": expected,
        "actual": actual,
        "status": "passed",
        "outputLocator": str(result_path),
    }


def run_suite_lifecycle(root):
    cases = root / "SUITE-01-cases"
    cases.mkdir()
    first = json.loads((CASES / "csp-docs.json").read_text(encoding="utf-8"))
    second = json.loads(json.dumps(first))
    second["id"] = "csp-docs-two"
    second["source"]["caseId"] = "csp-docs-two"
    (cases / "csp-docs.json").write_text(json.dumps(first), encoding="utf-8")
    (cases / "csp-docs-two.json").write_text(json.dumps(second), encoding="utf-8")
    rows = []
    for name, expected_count in (("SUITE-01-two", 2), ("SUITE-01-one", 1),
                                 ("SUITE-01-empty", 0)):
        if expected_count == 1:
            (cases / "csp-docs-two.json").unlink()
        elif expected_count == 0:
            (cases / "csp-docs.json").unlink()
        output = root / name
        command = ["bash", str(WRAPPER), "--cases", str(cases), "--out", str(output)]
        process = subprocess.run(command, cwd=REPO, capture_output=True, text=True, timeout=300)
        result_path = output / "suite-results.json"
        result = json.loads(result_path.read_text(encoding="utf-8"))
        expected_status = "EMPTY" if expected_count == 0 else "PASS"
        actual = {"exit": process.returncode, "caseCount": result["caseCount"],
                  "status": result["status"]}
        expected = {"exit": 0, "caseCount": expected_count, "status": expected_status}
        if actual != expected:
            raise AssertionError(f"{name}: expected {expected}, got {actual}")
        rows.append({"scenarioId": name, "mode": "live-local", "command": command,
                     "expected": expected, "actual": actual, "status": "passed",
                     "outputLocator": str(result_path)})
    return rows


def verify_artifacts(root):
    result_path = root / "LIVE-01" / "suite-results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    missing = []
    for case in result["cases"]:
        for key in ("casePath", "planPath", "evidencePath", "logPath", "reportPath"):
            if case.get(key) and not (result_path.parent / case[key]).is_file():
                missing.append(case[key])
    payload = b"".join(path.read_bytes() for path in result_path.parent.rglob("*") if path.is_file())
    if missing or b"secret-canary" in payload:
        raise AssertionError(f"ART-01 failed: missing={missing}, canary={b'secret-canary' in payload}")
    return {"scenarioId": "ART-01", "mode": "live-local", "command": ["artifact-readback"],
            "expected": {"referencesExist": True, "secretCanaryPresent": False},
            "actual": {"referencesExist": True, "secretCanaryPresent": False},
            "status": "passed", "outputLocator": str(result_path.parent)}


def run_portable(root):
    portable = root / "PORT-01-bundle"
    shutil.copytree(SECURITY, portable / "security", ignore=shutil.ignore_patterns("__pycache__"))
    output = portable / "output"
    command = ["bash", str(portable / "security" / "run_zap_suite.sh"), "--cases",
               str(portable / "security" / "cases"), "--out", str(output)]
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    process = subprocess.run(command, cwd=portable, env=environment,
                             capture_output=True, text=True, timeout=300)
    result_path = output / "suite-results.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    actual = {"exit": process.returncode, "status": result["status"],
              "caseCount": result["caseCount"]}
    expected = {"exit": 0, "status": "PASS", "caseCount": 1}
    if actual != expected:
        raise AssertionError(f"PORT-01: expected {expected}, got {actual}")
    return {"scenarioId": "PORT-01", "mode": "live-local", "command": command,
            "expected": expected, "actual": actual, "status": "passed",
            "outputLocator": str(result_path)}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--scenario", default="all",
                        choices=["all", *SCENARIOS])
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)
    root = Path(args.out).resolve()
    if root.exists() and any(root.iterdir()):
        raise SystemExit("qualification output must be new or empty")
    root.mkdir(parents=True, exist_ok=True)
    selected = SCENARIOS if args.scenario == "all" else {args.scenario: SCENARIOS[args.scenario]}
    rows = []
    try:
        for name, specification in selected.items():
            rows.append(run_one(name, specification, root))
        if "LIVE-06" in selected:
            cleanup_name = "LIVE-06-followup"
            rows.append(run_one(cleanup_name, SCENARIOS["LIVE-01"], root))
        if args.scenario == "all":
            rows.extend(run_suite_lifecycle(root))
            rows.append(verify_artifacts(root))
            rows.append(run_portable(root))
    except BaseException as error:
        summary = {"schemaVersion": 1, "status": "failed", "scenarios": rows,
                   "failure": f"{type(error).__name__}: {error}"}
        (root / "qualification-results.json").write_text(
            json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        raise
    summary = {"schemaVersion": 1, "status": "passed", "scenarios": rows}
    (root / "qualification-results.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "passed", "scenarioCount": len(rows),
                      "output": str(root / "qualification-results.json")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
