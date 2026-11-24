"""Compare complete in-process and live HTTP observations and exercise evidence controls."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

from security_framework.evidence import put_evidence, start, validate_child
from security_framework.manifest import read_suite

from ..adapter import MATRIX
from ..assertions.oracle import adjudicate, matrix_plan
from .run import CASE_ID, checked_result
from .scanner import verify_witnesses

ROW_FIELDS = {"operation", "actor", "status", "expectedStatus", "responseMatches", "stateMatches"}
ORIGINS = ("projectCommit", "openApiSha256", "designSha256", "pomSha256", "authorizationFixtureSha256")


def load(path, scenario):
    suite = read_suite("bus_booking", scenario)
    result = json.loads(path.read_text(encoding="utf-8"))
    validate_child(result, suite, result["runId"], 0)
    return result, suite


def normalized(result, suite):
    evidence = result["evidence"]
    data = {key: evidence[key]["data"] for key in ("jwtAcquisition", "jwtIdentity")}
    for case in suite.cases:
        data[case] = [{field: row[field] for field in sorted(ROW_FIELDS)} for row in evidence[case]["data"]]
    return data


def check_controls(live, suite, passive, passive_suite, expected):
    data = normalized(live, suite)
    identities = {actor: {**row, **data["jwtAcquisition"][actor]} for actor, row in data["jwtIdentity"].items()}
    groups = {case: [{key: value for key, value in row.items() if key != "expectedStatus"} for row in data[case]]
              for case in suite.cases}
    raw = {"runId": live["runId"], "identities": identities, "groups": groups}
    controls = []
    for label, change, verdict, reason in (
        ("missing-http-cell", lambda rows: rows.pop(), "ERROR", "MISSING_EVIDENCE"),
        ("http-state-mismatch", lambda rows: rows[0].update(stateMatches=False),
         "FAIL", "APPLICATION_CONTRACT_MISMATCH"),
    ):
        fixture = deepcopy(raw)
        change(fixture["groups"]["BB-ROLE"])
        result = start(suite, live["runId"])
        put_evidence(result, "provenance", **live["evidence"]["provenance"])
        adjudicate(result, suite, fixture, expected, observe_handler=False)
        checked = checked_result(result, suite)
        if (checked["verdict"], checked["checks"]["BB-ROLE"]["reason"]) != (verdict, reason):
            raise ValueError("unexpected live HTTP evidence-control verdict")
        controls.append({"control": label, "verdict": verdict, "exitCode": checked["exitCode"], "reason": reason})

    incomplete = deepcopy(passive)
    del incomplete["evidence"]["zapReport"]
    checked = checked_result(incomplete, passive_suite)
    if checked["exitCode"] != 2 or checked["checks"][CASE_ID]["reason"] != "INVALID_EVIDENCE":
        raise ValueError("unexpected missing ZAP report verdict")
    controls.append({"control": "missing-zap-report", "verdict": "ERROR", "exitCode": 2,
                     "reason": "INVALID_EVIDENCE"})
    return controls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mockmvc", type=Path)
    parser.add_argument("http_first", type=Path)
    parser.add_argument("http_repeat", type=Path)
    parser.add_argument("passive", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    mock, mock_suite = load(args.mockmvc, "baseline")
    first, live_suite = load(args.http_first, "live-http")
    repeat, _ = load(args.http_repeat, "live-http")
    passive, passive_suite = load(args.passive, "live-passive")
    comparable = (mock, first, repeat)
    source = mock["evidence"]["provenance"]["data"]
    if len({run["runId"] for run in (*comparable, passive)}) != 4:
        raise ValueError("comparison requires four independent runs")
    if any(run["evidence"]["provenance"]["data"][key] != source[key] for run in comparable for key in ORIGINS):
        raise ValueError("in-process and live provenance disagree")
    if any(passive["evidence"]["provenance"]["data"][key] != source[key] for key in ORIGINS[:-1]):
        raise ValueError("passive provenance differs from the authorization runs")
    if mock_suite.cases != live_suite.cases:
        raise ValueError("authorization case registry differs across lanes")
    if any(normalized(run, live_suite) != normalized(mock, mock_suite) for run in (first, repeat)):
        raise ValueError("authorization observations differ across lanes")
    for run in (first, repeat):
        for case in live_suite.cases:
            if any(set(row) != ROW_FIELDS for row in run["evidence"][case]["data"]):
                raise ValueError("live HTTP evidence includes unsupported fields")
    if verify_witnesses(passive["evidence"]):
        raise ValueError("ZAP evidence does not support the reported verdict")

    _, expected = matrix_plan(MATRIX)
    protected = [name for name in expected if name not in ("BB-AUTH", "BB-ROLE-LIFECYCLE", "BB-ROLE-RULES")]
    summary = {
        "projectCommit": source["projectCommit"], "sharedCaseIds": list(live_suite.cases),
        "protectedAuthorizationCells": sum(len(expected[case]) for case in protected),
        "otherConditionCells": sum(len(expected[case]) for case in set(expected) - set(protected)),
        "matchedResponseStateAndIdentity": True, "handlerWitnessLane": "mockmvc",
        "runIds": {"mockmvc": mock["runId"], "httpFirst": first["runId"],
                   "httpRepeat": repeat["runId"], "passive": passive["runId"]},
        "copiedEvidenceControls": check_controls(first, live_suite, passive, passive_suite, expected),
    }
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(summary, output, indent=2, sort_keys=True)
        output.write("\n")
    print("PASS live HTTP comparison and evidence controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
