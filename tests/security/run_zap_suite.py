#!/usr/bin/env python3
"""Portable stdlib-only runner for fixed ZAP regression cases."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path

from fixtures.csp_demo import FixtureServer
from zap_report import ReportError, load_fresh_report, matching_instances


STATUSES = ("PASS", "REGRESSION", "MISSING_EVIDENCE", "EXECUTION_ERROR")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
FIXTURES = {"csp-demo": FixtureServer}
CASE_FIELDS = {"schemaVersion", "source", "id", "profile", "fixture", "requests",
               "requireResponses", "expect"}
REQUEST_FIELDS = {"id", "method", "path"}
RESPONSE_FIELDS = {"status", "mediaType"}
EXPECT_FIELDS = {"basis", "alertRef", "presentOn", "absentOn", "requireNonEmptyCspOn"}


class CaseError(ValueError):
    pass


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("wb") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def _exact(value, fields, label):
    if not isinstance(value, dict) or set(value) != fields:
        raise CaseError(label + " fields must be exactly " + ", ".join(sorted(fields)))


def _slug(value, label):
    if not isinstance(value, str) or not SLUG.fullmatch(value):
        raise CaseError(label + " must be a lowercase slug")


def _route(value, label):
    if (not isinstance(value, str) or not value.startswith("/") or value.startswith("//")
            or "?" in value or "#" in value or "\r" in value or "\n" in value
            or "\\" in value or any(part in (".", "..") for part in value.split("/"))):
        raise CaseError(label + " must be a literal route without query, fragment or traversal")


def validate_case(value, filename=None):
    _exact(value, CASE_FIELDS, "case")
    if value["schemaVersion"] != 1:
        raise CaseError("schemaVersion must be 1")
    _slug(value["id"], "id")
    if filename is not None and filename != value["id"] + ".json":
        raise CaseError("filename must equal <id>.json")
    source = value["source"]
    if not isinstance(source, dict) or source.get("kind") not in ("synthetic-demo", "assessment-run-v3"):
        raise CaseError("source kind is unsupported")
    if source["kind"] == "synthetic-demo":
        _exact(source, {"kind", "path", "caseId"}, "synthetic source")
        _slug(source["caseId"], "source caseId")
        path = source["path"]
        if not isinstance(path, str) or not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise CaseError("synthetic source path must be repository-relative")
        if source["caseId"] != value["id"]:
            raise CaseError("synthetic source caseId must equal id")
    else:
        _exact(source, {"kind", "assessmentId", "caseId", "criterionIds", "planRevision",
                        "planDigest", "evidence"}, "assessment source")
        if not all(isinstance(source.get(key), str) and source[key]
                   for key in ("assessmentId", "caseId", "planRevision")):
            raise CaseError("assessment source identity is incomplete")
        if not re.fullmatch(r"[0-9a-f]{64}", source.get("planDigest", "")):
            raise CaseError("assessment source planDigest is invalid")
        if (not isinstance(source.get("criterionIds"), list) or not source["criterionIds"]
                or not all(isinstance(row, str) and row for row in source["criterionIds"])
                or len(source["criterionIds"]) != len(set(source["criterionIds"]))):
            raise CaseError("assessment source criterionIds are invalid")
        if not isinstance(source.get("evidence"), list) or not source["evidence"]:
            raise CaseError("assessment source evidence is required")
        for row in source["evidence"]:
            _exact(row, {"operationId", "resultPath", "sha256"}, "source evidence")
            if (not isinstance(row["operationId"], str) or not row["operationId"]
                    or not isinstance(row["resultPath"], str) or not row["resultPath"].startswith("/")
                    or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
                raise CaseError("source evidence locator is invalid")
    if value["profile"] != "passive-http-v1":
        raise CaseError("only passive-http-v1 is supported")
    if value["fixture"] not in FIXTURES:
        raise CaseError("fixture is not in the registry")
    requests = value["requests"]
    if not isinstance(requests, list) or not requests:
        raise CaseError("at least one request is required")
    ids = []
    for index, request in enumerate(requests):
        _exact(request, REQUEST_FIELDS, f"requests/{index}")
        _slug(request["id"], f"requests/{index}/id")
        if request["method"] != "GET":
            raise CaseError("passive-http-v1 supports GET only")
        _route(request["path"], f"requests/{index}/path")
        ids.append(request["id"])
    if len(ids) != len(set(ids)):
        raise CaseError("request IDs must be unique")
    _exact(value["requireResponses"], RESPONSE_FIELDS, "requireResponses")
    status = value["requireResponses"]["status"]
    media = value["requireResponses"]["mediaType"]
    if type(status) is not int or not 100 <= status <= 599:
        raise CaseError("required response status is invalid")
    if not isinstance(media, str) or not media:
        raise CaseError("required response mediaType is invalid")
    expect = value["expect"]
    _exact(expect, EXPECT_FIELDS, "expect")
    if not isinstance(expect["basis"], str) or not expect["basis"].strip():
        raise CaseError("expectation basis is required")
    if expect["alertRef"] != "10038-1":
        raise CaseError("passive-http-v1 supports alertRef 10038-1 only")
    for field in ("presentOn", "absentOn", "requireNonEmptyCspOn"):
        if expect[field] not in ids:
            raise CaseError("expect." + field + " must reference a request")
    if expect["presentOn"] == expect["absentOn"]:
        raise CaseError("positive control and protected request must differ")
    return value


def discover_cases(directory: Path):
    if directory.is_symlink() or not directory.is_dir():
        raise CaseError("cases directory must be a real directory")
    cases = []
    seen = set()
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        if path.is_symlink() or path.resolve().parent != directory.resolve():
            raise CaseError("symlink or escaped case path is not allowed: " + path.name)
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise CaseError(path.name + " is unreadable: " + type(error).__name__) from None
        validate_case(value)
        if value["id"] in seen:
            raise CaseError("duplicate case ID: " + value["id"])
        if path.name != value["id"] + ".json":
            raise CaseError("filename must equal <id>.json")
        seen.add(value["id"])
        cases.append((path, value))
    return cases


def render_plan(case, origin, case_dir: Path, omit_request_id=None):
    requests = []
    for request in case["requests"]:
        if request["id"] == omit_request_id:
            continue
        requests.append({"url": origin + request["path"], "method": request["method"]})
    return {
        "env": {
            "contexts": [{"name": "fixture", "urls": [origin]}],
            "parameters": {"failOnError": True, "failOnWarning": False},
        },
        "jobs": [
            {"type": "passiveScan-config", "parameters": {"maxAlertsPerRule": 0}},
            {"type": "requestor", "requests": requests},
            {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
            {"type": "report", "parameters": {
                "template": "traditional-json",
                "reportDir": str(case_dir),
                "reportFile": "zap-report",
            }},
        ],
    }


def run_process(command, log_path: Path, timeout: float):
    started_ns = time.time_ns()
    timed_out = False
    native_exit = None
    with log_path.open("wb") as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                   start_new_session=True)
        try:
            native_exit = process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGTERM)
            try:
                native_exit = process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                native_exit = process.wait(timeout=5)
    return native_exit, timed_out, started_ns


def _case_result(case, case_hash, status, reason, native_exit, case_dir, out_dir,
                 report_exists=False):
    relative = lambda name: str((case_dir / name).relative_to(out_dir))
    result = {
        "id": case["id"],
        "sourceKind": case["source"]["kind"],
        "caseHash": case_hash,
        "status": status,
        "reason": reason,
        "nativeExit": native_exit,
        "casePath": relative("case.json"),
        "planPath": relative("plan.yaml"),
        "evidencePath": relative("evidence.json"),
        "logPath": relative("zap.log"),
        "reportPath": relative("zap-report.json") if report_exists else None,
    }
    return result


def _fixture_evidence(fixture):
    if fixture is None:
        return []
    try:
        return fixture.evidence()
    except Exception:
        return []


def _ensure_failure_artifacts(case_dir: Path, records, error_name: str):
    atomic_json(case_dir / "evidence.json", {"responses": records})
    if not (case_dir / "plan.yaml").exists():
        (case_dir / "plan.yaml").write_text("{}\n", encoding="utf-8")
    if not (case_dir / "zap.log").exists():
        (case_dir / "zap.log").write_text(error_name + "\n", encoding="utf-8")


def classify(case, origin, records, report):
    by_id = {}
    for row in records:
        by_id.setdefault(row.get("requestId"), []).append(row)
    request_by_id = {row["id"]: row for row in case["requests"]}
    for request in case["requests"]:
        witnesses = by_id.get(request["id"], [])
        if not witnesses:
            return "MISSING_EVIDENCE", "REQUIRED_RESPONSE_MISSING"
        witness = witnesses[-1]
        if witness.get("path") != request["path"] or witness.get("method") != request["method"]:
            return "MISSING_EVIDENCE", "RESPONSE_IDENTITY_MISMATCH"
        if witness.get("status") != case["requireResponses"]["status"]:
            return "MISSING_EVIDENCE", "RESPONSE_STATUS_MISMATCH"
        if witness.get("mediaType") != case["requireResponses"]["mediaType"]:
            return "MISSING_EVIDENCE", "RESPONSE_MEDIA_TYPE_MISMATCH"
    if report.capped:
        return "MISSING_EVIDENCE", "REPORT_INSTANCES_INCOMPLETE"
    expect = case["expect"]
    control = request_by_id[expect["presentOn"]]
    protected = request_by_id[expect["absentOn"]]
    control_hits = matching_instances(report, origin=origin, method=control["method"],
                                      path=control["path"], alert_ref=expect["alertRef"])
    if not control_hits:
        return "MISSING_EVIDENCE", "CONTROL_ALERT_MISSING"
    protected_hits = matching_instances(report, origin=origin, method=protected["method"],
                                        path=protected["path"], alert_ref=expect["alertRef"])
    if protected_hits:
        return "REGRESSION", "PROTECTED_ALERT_PRESENT"
    csp_witnesses = by_id.get(expect["requireNonEmptyCspOn"], [])
    if not csp_witnesses or not csp_witnesses[-1].get("cspNonEmpty"):
        return "MISSING_EVIDENCE", "INCONSISTENT_OBSERVATION"
    return "PASS", "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER"


def execute_case(case, out_dir: Path, run_id: str, fixture_mode: str,
                 omit_request_id: str | None, deadline: float):
    case_payload = canonical_bytes(case)
    case_hash = hashlib.sha256(case_payload).hexdigest()
    case_dir = out_dir / case["id"]
    case_dir.mkdir(parents=False, exist_ok=False)
    (case_dir / "case.json").write_bytes(case_payload)
    home = case_dir / "zap-home"
    fixture = None
    fixture_started = False
    native_exit = None
    report_exists = False
    result = None
    cleanup_error = None
    try:
        home.mkdir()
        fixture = FIXTURES[case["fixture"]](case, run_id, fixture_mode)
        fixture.start()
        fixture_started = True
        plan = render_plan(case, fixture.origin, case_dir, omit_request_id)
        plan_path = case_dir / "plan.yaml"
        plan_path.write_bytes(canonical_bytes(plan))
        command = [
            "/zap/zap.sh", "-cmd", "-dir", str(home),
            "-config", "alert.maxInstances=0",
            "-config", "alert.mergeissues=false",
            "-autorun", str(plan_path),
        ]
        native_exit, timed_out, started_ns = run_process(command, case_dir / "zap.log", deadline)
        if timed_out:
            records = fixture.evidence()
            atomic_json(case_dir / "evidence.json", {"responses": records})
            result = _case_result(case, case_hash, "EXECUTION_ERROR", "TIMEOUT", native_exit,
                                  case_dir, out_dir)
        elif native_exit != 0:
            records = fixture.evidence()
            atomic_json(case_dir / "evidence.json", {"responses": records})
            report_exists = (case_dir / "zap-report.json").is_file()
            result = _case_result(case, case_hash, "EXECUTION_ERROR",
                                  "ZAP_NATIVE_EXIT_NONZERO", native_exit,
                                  case_dir, out_dir, report_exists)
        else:
            try:
                _raw, parsed = load_fresh_report(case_dir / "zap-report.json", started_ns)
                report_exists = True
            except ReportError as error:
                records = fixture.evidence()
                atomic_json(case_dir / "evidence.json", {"responses": records})
                result = _case_result(case, case_hash, "EXECUTION_ERROR",
                                      "REPORT_INVALID:" + str(error), native_exit,
                                      case_dir, out_dir,
                                      (case_dir / "zap-report.json").is_file())
            else:
                records = fixture.evidence()
                atomic_json(case_dir / "evidence.json", {
                    "responses": records,
                    "matchedAlertPointers": [row.pointer for row in parsed.instances
                                              if row.alert_ref == case["expect"]["alertRef"]],
                })
                status, reason = classify(case, fixture.origin, records, parsed)
                result = _case_result(case, case_hash, status, reason, native_exit,
                                      case_dir, out_dir, report_exists)
    except Exception as error:
        records = _fixture_evidence(fixture)
        _ensure_failure_artifacts(case_dir, records, type(error).__name__)
        prefix = "RUNNER_ERROR" if fixture_started else "FIXTURE_SETUP_ERROR"
        result = _case_result(case, case_hash, "EXECUTION_ERROR",
                              prefix + ":" + type(error).__name__, native_exit,
                              case_dir, out_dir, (case_dir / "zap-report.json").is_file())
    finally:
        if fixture is not None:
            try:
                fixture.stop()
            except Exception as error:
                cleanup_error = error
        shutil.rmtree(home, ignore_errors=True)
    if cleanup_error is not None:
        records = _fixture_evidence(fixture)
        _ensure_failure_artifacts(case_dir, records, type(cleanup_error).__name__)
        with (case_dir / "zap.log").open("a", encoding="utf-8") as log:
            log.write("fixture cleanup failed: " + type(cleanup_error).__name__ + "\n")
        if result is None or result["status"] != "EXECUTION_ERROR":
            result = _case_result(case, case_hash, "EXECUTION_ERROR",
                                  "FIXTURE_CLEANUP_ERROR:" + type(cleanup_error).__name__,
                                  native_exit, case_dir, out_dir,
                                  (case_dir / "zap-report.json").is_file())
    if result is None:
        raise RuntimeError("case execution produced no result")
    return result


def suite_result(run_id, cases, *, suite_error=None):
    counts = {status: 0 for status in STATUSES}
    for case in cases:
        counts[case["status"]] += 1
    value = {
        "schemaVersion": 1,
        "runId": run_id,
        "testedCommitSha": os.environ.get("TESTED_COMMIT_SHA", "local"),
        "pullRequestHeadSha": os.environ.get("PULL_REQUEST_HEAD_SHA") or None,
        "imageDigest": os.environ.get("ZAP_IMAGE_DIGEST", "unknown"),
        "caseCount": len(cases),
        "counts": counts,
        "status": ("ERROR" if suite_error else "EMPTY" if not cases else
                   "PASS" if counts["PASS"] == len(cases) else "FAIL"),
        "cases": cases,
    }
    if suite_error:
        value["suiteError"] = suite_error
    return value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--fixture-mode", default="healthy")
    parser.add_argument("--omit-request-id")
    parser.add_argument("--deadline", type=float, default=180.0)
    args = parser.parse_args(argv)
    home = os.environ.get("HOME")
    if home:
        Path(home).mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    out_dir = Path(args.out)
    if out_dir.exists() and any(out_dir.iterdir()):
        print("output directory must be new or empty", file=sys.stderr)
        return 1
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        discovered = discover_cases(Path(args.cases))
    except (OSError, CaseError) as error:
        result = suite_result(run_id, [], suite_error=str(error))
        atomic_json(out_dir / "suite-results.json", result)
        atomic_json(out_dir / "run-metadata.json", {
            "runId": run_id, "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        })
        return 1
    for _path, case in discovered:
        results.append(execute_case(case, out_dir, run_id, args.fixture_mode,
                                    args.omit_request_id, args.deadline))
    result = suite_result(run_id, results)
    atomic_json(out_dir / "suite-results.json", result)
    atomic_json(out_dir / "run-metadata.json", {
        "runId": run_id,
        "runnerSha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "reportAdapterSha256": hashlib.sha256((Path(__file__).parent / "zap_report.py").read_bytes()).hexdigest(),
        "caseHashes": {row["id"]: row["caseHash"] for row in results},
    })
    return 0 if result["status"] in ("PASS", "EMPTY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
