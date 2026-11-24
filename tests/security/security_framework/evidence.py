"""Stable exit contract, check receipts, traceability, and report rendering."""

import json
import re

from .manifest import NATIVE_JWT, SCANNER_METHODS, restriction_reason
from .native_jwt import CONTROL, CONTROL_RULE, MODE, identity_status

EXIT = {"PASS": 0, "FAIL": 1, "ERROR": 2, "BLOCKED": 3}
PRECEDENCE = ("ERROR", "BLOCKED", "FAIL", "PASS")
REASON = re.compile(r"[A-Z][A-Z0-9_]{0,79}\Z")
EVIDENCE_ID = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,127}\Z")
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
PRODUCERS = {"application-identity", "automation-framework", "capability-boundary",
             "fixture", "runner", "suite-assertion", "zap-report"}


def outcome(verdict, reason):
    return {"verdict": verdict, "reason": reason}


def assertion(satisfied, reason):
    return outcome("PASS", "ASSERTIONS_SATISFIED") if satisfied else outcome("FAIL", reason)


def start(suite, run_id):
    return {"schemaVersion": 1, "suite": suite.name, "scenario": suite.scenario, "runId": run_id,
            "inputSha256": suite.inputs, "checks": {}, "evidence": {}}


def add_check(result, suite, case_id, status, evidence_ids=()):
    case = suite.cases[case_id]
    objective = suite.objectives[case["objectiveId"]]
    if not valid_outcome(status):
        status = outcome("ERROR", "INVALID_EVIDENCE")
    result["checks"][case_id] = {
        **status, "objectiveId": objective["id"], "cwe": objective["cwe"], "method": case["method"],
        "specification": case["specification"], "authProfile": case["authProfile"],
        "expected": case["expected"],
        "evidenceRefs": [f"#/evidence/{key}" for key in evidence_ids],
    }


def valid_outcome(status):
    return (isinstance(status, dict) and isinstance(status.get("verdict"), str)
            and status["verdict"] in EXIT
            and isinstance(status.get("reason"), str) and REASON.fullmatch(status["reason"]))


def finish(result):
    checks = result["checks"]
    if not checks or not all(valid_outcome(row) for row in checks.values()):
        raise ValueError("missing or unknown check verdicts")
    for verdict in PRECEDENCE:
        decisive = {key: row["reason"] for key, row in checks.items() if row["verdict"] == verdict}
        if decisive:
            result.update(verdict=verdict, exitCode=EXIT[verdict], decisiveChecks=decisive)
            return result
    raise ValueError("no decisive verdict")


def fail_run(result, suite, reason):
    for case_id in suite.cases:
        previous = result["checks"].get(case_id, {})
        if previous.get("verdict") != "BLOCKED":
            references = [ref.removeprefix("#/evidence/") for ref in previous.get("evidenceRefs", [])]
            add_check(result, suite, case_id, outcome("ERROR", reason), references)
    return finish(result)


def put_evidence(result, key, producer, data):
    if (not isinstance(key, str) or not EVIDENCE_ID.fullmatch(key) or key in result["evidence"]
            or producer not in PRODUCERS or not isinstance(data, (list, dict)) or not data):
        raise ValueError("duplicate or empty evidence")
    json.dumps(data, allow_nan=False)
    result["evidence"][key] = {"producer": producer, "data": data}


def evidence_keys(case, profile):
    keys = list(case["requiredEvidence"])
    if case["method"] in SCANNER_METHODS:
        keys.extend(("scannerExecution", "zapReport"))
        if profile["kind"] == NATIVE_JWT:
            keys.extend(("scannerEvents", "scannerOwnership", "runtimeCleanup"))
        if profile["kind"] != "none":
            keys.append("scannerIdentity-" + profile["id"])
    elif profile["kind"] != "none":
        keys.append(case["id"] + "-identity")
    return list(dict.fromkeys(keys))


def validate_scan_evidence(evidence):
    native = evidence["scannerExecution"]["data"]
    report = evidence["zapReport"]["data"]
    types = native["expectedJobTypes"]
    phases = [[job, state] for job in types for state in ("started", "finished")]
    if (evidence["scannerExecution"]["producer"] != "automation-framework"
            or evidence["zapReport"]["producer"] != "zap-report"
            or len(types) < 3 or types[:-2] != ["requestor"] * (len(types) - 2)
            or types[-2:] != ["passiveScan-wait", "report"]
            or native["preflight"] != {"exit": 0, "timedOut": False}
            or native["execution"] != {"exit": 0, "timedOut": False}
            or native["preflightRequests"] != 0 or native["jobReceipts"] != phases
            or native["planReportedSuccessful"] is not True
            or not SHA256.fullmatch(native["planSha256"])
            or not SHA256.fullmatch(report["sha256"])
            or report["capped"] is not False or report["version"] != "2.17.0"
            or not isinstance(report["ruleInstances"], list)):
        raise ValueError("invalid native execution or report evidence")


def validate_native_jwt_evidence(evidence, profile):
    actor, = profile["actors"]
    execution = evidence["scannerExecution"]["data"]
    events = evidence["scannerEvents"]
    ownership = evidence["scannerOwnership"]
    cleanup = evidence["runtimeCleanup"]
    rows = evidence["zapReport"]["data"]["ruleInstances"]
    if (execution.get("mode") != MODE or events["producer"] != "fixture"
            or identity_status(events["data"], actor)
            or [row for row in events["data"] if row["phase"] == "passive-control"]
                != [{"phase": "passive-control", "status": 200}]
            or ownership["producer"] != "suite-assertion" or ownership["data"].get("mode") != MODE
            or ownership["data"].get("applicationClientLogin") is not False
            or cleanup != {"producer": "runner", "data": {
                "containersRemoved": True, "temporaryDirectoryRemoved": True}}
            or not any(row["path"] == CONTROL and row["alertRef"] == CONTROL_RULE for row in rows)):
        raise ValueError("invalid native JWT witness")


def validate_identity_evidence(evidence, key, profile):
    record = evidence[key]
    if record["producer"] != "application-identity":
        raise ValueError("missing application identity producer")
    for actor in profile["actors"]:
        row = record["data"][actor]
        if (row["actor"] != actor or type(row["status"]) is not int
                or not 200 <= row["status"] < 300):
            raise ValueError("invalid effective identity")


def validate_child(child, suite, run_id, process_exit):
    expected = start(suite, run_id)
    checks = child["checks"]
    evidence = child["evidence"]
    if (any(child[field] != expected[field]
            for field in ("schemaVersion", "suite", "scenario", "runId", "inputSha256"))
            or type(child["schemaVersion"]) is not int or type(child["exitCode"]) is not int
            or child["exitCode"] != process_exit or not isinstance(checks, dict)
            or set(checks) != set(suite.cases) or not isinstance(evidence, dict)):
        raise ValueError("mismatched result envelope")

    verification = start(suite, run_id)
    for key, record in evidence.items():
        if set(record) != {"producer", "data"}:
            raise ValueError("invalid evidence record")
        put_evidence(verification, key, record["producer"], record["data"])
    scanner_verified = False
    for case_id, check in checks.items():
        references = check["evidenceRefs"]
        if not isinstance(references, list) or len(set(references)) != len(references):
            raise ValueError("bad evidence references")
        keys = []
        for ref in references:
            if not isinstance(ref, str) or not ref.startswith("#/evidence/"):
                raise ValueError("bad evidence reference")
            key = ref.removeprefix("#/evidence/")
            if key not in evidence:
                raise ValueError("unresolved evidence reference")
            keys.append(key)
        case = suite.cases[case_id]
        profile = suite.profiles[case["authProfile"]]
        restricted_reason = restriction_reason(case["method"], profile["kind"])
        if restricted_reason:
            if ((check["verdict"], check["reason"]) != ("BLOCKED", restricted_reason)
                    or keys != [case_id] or evidence[case_id] != {
                        "producer": "capability-boundary",
                        "data": {"dispatched": False, "reason": restricted_reason},
                    }):
                raise ValueError("untrusted restriction outcome")
        elif check["verdict"] in {"PASS", "FAIL"}:
            if not set(evidence_keys(case, profile)).issubset(keys):
                raise ValueError("missing adjudication evidence")
            scanner = case["method"] in SCANNER_METHODS
            if scanner and not scanner_verified:
                validate_scan_evidence(evidence)
                scanner_verified = True
            if profile["kind"] != "none":
                identity_key = "scannerIdentity-" + profile["id"] if scanner else case_id + "-identity"
                validate_identity_evidence(evidence, identity_key, profile)
            if profile["kind"] == NATIVE_JWT:
                validate_native_jwt_evidence(evidence, profile)
        add_check(verification, suite, case_id, outcome(check["verdict"], check["reason"]), keys)
        if verification["checks"][case_id] != check:
            raise ValueError("mismatched check metadata")
    finish(verification)
    if any(child[field] != verification[field] for field in ("verdict", "exitCode", "decisiveChecks")):
        raise ValueError("mismatched aggregate verdict")
    return child


def markdown(result):
    lines = ["# Security suite result", "",
             f'**{result["verdict"]}** (exit {result["exitCode"]})', "",
             f'Suite `{result["suite"]}`, scenario `{result["scenario"]}`, run `{result["runId"]}`.']
    image = result.get("scannerImage")
    if image:
        lines.extend(["", f"Scanner image `{image}`."])
    for key, row in result["checks"].items():
        lines.extend(["", f'## {key}', "",
                      f'**{row["verdict"]}** — `{row["reason"]}`.',
                      f'Objective `{row["objectiveId"]}` · {", ".join(row["cwe"])}.',
                      f'Specification `{row["specification"]}`.'])
        if row["evidenceRefs"]:
            refs = ", ".join(f'`{ref}`' for ref in row["evidenceRefs"])
            lines.append(f"JSON evidence {refs}.")
    return "\n".join(lines) + "\n"
