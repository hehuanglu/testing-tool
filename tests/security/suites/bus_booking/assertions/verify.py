"""Compare two clean result bundles and exercise the oracle with sanitized controls."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from uuid import uuid4

from security_framework.evidence import fail_run, put_evidence, start, validate_child
from security_framework.manifest import read_suite

from ..adapter import MATRIX, ExecutionError, command
from .oracle import adjudicate, matrix_plan

ROW_FIELDS = {"operation", "actor", "status", "responseMatches", "stateMatches", "handlerRecorded"}


def application_rows(baseline, suite):
    evidence = baseline["evidence"]
    return {
        "runId": baseline["runId"],
        "identities": {
            actor: {**row, **evidence["jwtAcquisition"]["data"][actor]}
            for actor, row in evidence["jwtIdentity"]["data"].items()
        },
        "groups": {
            case: [{key: value for key, value in row.items() if key in ROW_FIELDS}
                   for row in evidence[case]["data"]]
            for case in suite.cases
        },
    }


def verify_process(suite, code, timeout, expected):
    result = start(suite, uuid4().hex)
    try:
        command([sys.executable, "-c", code], timeout=timeout, reason="APPLICATION_TEST_PROCESS_FAILURE")
    except ExecutionError as error:
        result = fail_run(result, suite, error.args[0])
    validate_child(result, suite, result["runId"], 2)
    if set(result["decisiveChecks"].values()) != {expected}:
        raise ValueError("unexpected process control result")
    return {"exitCode": result["exitCode"], "verdict": result["verdict"], "reason": expected}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first", type=Path)
    parser.add_argument("second", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    suite = read_suite("bus_booking", "baseline")
    _, expected = matrix_plan(MATRIX)
    first, second = [json.loads(path.read_text(encoding="utf-8")) for path in (args.first, args.second)]
    for result in (first, second):
        validate_child(result, suite, result["runId"], 0)
    if first["runId"] == second["runId"] or any(first[key] != second[key] for key in ("evidence", "checks")):
        raise ValueError("clean baseline receipts disagree")
    controls = []
    baseline = application_rows(first, suite)

    def verify(name, changes, verdict, reason, case="BB-ADMIN-WRITE"):
        observations = deepcopy(baseline)
        changes(observations)
        result = start(suite, baseline["runId"])
        put_evidence(result, "provenance", **first["evidence"]["provenance"])
        adjudicate(result, suite, observations, expected)
        validate_child(result, suite, result["runId"], result["exitCode"])
        check = result["checks"][case]
        if (result["verdict"], check["verdict"], check["reason"]) != (verdict, verdict, reason):
            raise ValueError(f"unexpected control verdict for {name}")
        controls.append({"id": name, "case": case, "verdict": verdict,
                         "exitCode": result["exitCode"], "reason": reason})

    def change_cell(evidence, **values):
        row = next(row for row in evidence["groups"]["BB-ADMIN-WRITE"]
                   if row["operation"] == "location-create" and row["actor"] == "USER")
        row.update(values)

    def remove_cell(evidence):
        evidence["groups"]["BB-ADMIN-WRITE"].pop()

    def wrong_subject(evidence):
        evidence["identities"]["ADMIN"]["actor"] = "USER"

    mismatch = "APPLICATION_CONTRACT_MISMATCH"
    verify("response-status-mismatch", lambda evidence: change_cell(evidence, status=200), "FAIL", mismatch)
    verify("persisted-state-mismatch", lambda evidence: change_cell(evidence, stateMatches=False), "FAIL", mismatch)
    verify("controller-selection-mismatch", lambda evidence: change_cell(evidence, handlerRecorded=True), "FAIL", mismatch)
    verify("missing-observation", remove_cell, "ERROR", "MISSING_EVIDENCE")
    verify("invalid-observation", lambda evidence: change_cell(evidence, status="403"), "ERROR", "INVALID_EVIDENCE")
    verify("wrong-effective-identity", wrong_subject, "ERROR", "AUTHENTICATION_FAILURE")
    verify("stale-receipt", lambda evidence: evidence.update(runId="0" * 32), "ERROR", "INVALID_EVIDENCE")
    process_controls = {
        "nonzero-child": verify_process(suite, "raise SystemExit(7)", 5, "APPLICATION_TEST_PROCESS_FAILURE"),
        "timeout-child": verify_process(suite, "import time; time.sleep(5)", 0.25, "PROCESS_TIMEOUT"),
    }
    summary = {"baselineRunIds": [first["runId"], second["runId"]],
               "applicationEvidenceMatched": True, "controlsUseCopiedObservations": True,
               "caseCounts": {key: len(rows) for key, rows in expected.items()},
               "controls": controls, "processControls": process_controls}
    with args.out.open("x", encoding="utf-8") as output:
        json.dump(summary, output, indent=2, sort_keys=True)
        output.write("\n")
    print(f"PASS repeatability, {len(controls)} oracle controls and {len(process_controls)} process controls")
    return 0


if __name__ == "__main__":
    sys.exit(main())
