"""Adjudicate a bounded, allowlisted application receipt against the contract matrix."""

from collections import defaultdict

from security_framework.evidence import add_check, assertion, fail_run, finish, outcome, put_evidence
from security_framework.run import identity

ACTORS = ("anonymous", "USER", "ADMIN", "SUPER_ADMIN", "other-USER")
AUTH_ACTORS = ACTORS[1:]
IDENTITY = "jwtIdentity"
AUTH_CONDITIONS = {
    ("missing", "anonymous"): 401, ("malformed", "anonymous"): 401,
    ("expired", "USER"): 401, ("duplicate", "USER"): 401,
    ("public-invalid", "anonymous"): 401, ("public-no-token", "anonymous"): 200,
    ("inactive", "USER"): 401, ("unverified", "USER"): 401,
    ("restored", "USER"): 200, ("wrong-password", "USER"): 401,
}
ROLE_LIFECYCLE = {
    ("before-demotion", "ADMIN"): 200, ("demote", "SUPER_ADMIN"): 200,
    ("old-token-denied", "ADMIN"): 403, ("old-token-current-role", "ADMIN"): 200,
    ("restore-admin", "SUPER_ADMIN"): 200,
}
ROLE_RULES = {
    ("root-immutable", "SUPER_ADMIN"): 403,
    ("root-not-assignable", "SUPER_ADMIN"): 400,
    ("pending-not-promotable", "SUPER_ADMIN"): 409,
}


def matrix_plan(path):
    expected = defaultdict(dict)
    operations = set()
    operation_ids = set()
    lines = path.read_text(encoding="utf-8").splitlines()
    if lines[0].split() != ["id", "case", "method", "path", *ACTORS]:
        raise ValueError("matrix header mismatch")
    for row in lines[1:]:
        operation, group, method, route, *statuses = row.split()
        if (len(statuses) != len(ACTORS) or (method, route) in operations
                or operation in operation_ids):
            raise ValueError("matrix inventory mismatch")
        operations.add((method, route))
        operation_ids.add(operation)
        if group != "public":
            for actor, status in zip(ACTORS, statuses):
                if status != "-":
                    expected[group][operation, actor] = int(status)
    expected["BB-AUTH"] = AUTH_CONDITIONS
    expected["BB-ROLE-LIFECYCLE"] = ROLE_LIFECYCLE
    expected["BB-ROLE-RULES"] = ROLE_RULES
    return operations, expected


def http_status(value):
    return type(value) is int and 100 <= value <= 599


def check_identities(result, observed):
    if not isinstance(observed, dict) or set(observed) != set(AUTH_ACTORS):
        return "MISSING_EVIDENCE"
    for row in observed.values():
        if (not isinstance(row, dict) or set(row) != {"actor", "status", "loginStatus", "noSession"}
                or row["actor"] not in (*AUTH_ACTORS, "unknown")
                or not http_status(row["status"]) or not http_status(row["loginStatus"])
                or type(row["noSession"]) is not bool):
            return "INVALID_EVIDENCE"
    put_evidence(result, "jwtAcquisition", "suite-assertion", {
        actor: {key: row[key] for key in ("loginStatus", "noSession")}
        for actor, row in observed.items()
    })
    reason = identity(result, IDENTITY, {"actors": AUTH_ACTORS}, observed)
    if reason:
        return reason
    if any(row["status"] != 200 or row["loginStatus"] != 200 or not row["noSession"]
           for row in observed.values()):
        return "AUTHENTICATION_FAILURE"
    return None


def adjudicate(result, suite, raw, expected, *, observe_handler=True):
    if (not isinstance(raw, dict) or set(raw) != {"runId", "identities", "groups"}
            or raw["runId"] != result["runId"] or not isinstance(raw["groups"], dict)
            or set(raw["groups"]) - set(expected)):
        return fail_run(result, suite, "INVALID_EVIDENCE")
    reason = check_identities(result, raw["identities"])
    for case_id in suite.cases:
        keys = [key for key in ("provenance", IDENTITY, "jwtAcquisition") if key in result["evidence"]]
        rows = raw["groups"].get(case_id)
        if reason:
            status = outcome("ERROR", reason)
        elif not isinstance(rows, list) or len(rows) != len(expected[case_id]):
            status = outcome("ERROR", "MISSING_EVIDENCE")
        else:
            try:
                accepted, mismatches = check_rows(case_id, rows, expected[case_id], observe_handler=observe_handler)
                put_evidence(result, case_id, "suite-assertion", accepted)
                keys.append(case_id)
                status = assertion(not mismatches, "APPLICATION_CONTRACT_MISMATCH")
            except (TypeError, ValueError):
                status = outcome("ERROR", "INVALID_EVIDENCE")
        add_check(result, suite, case_id, status, keys)
    return finish(result)


def check_rows(case_id, rows, expected, *, observe_handler=True):
    fields = {"operation", "actor", "status", "responseMatches", "stateMatches"}
    booleans = {"responseMatches", "stateMatches"}
    if observe_handler:
        fields.add("handlerRecorded")
        booleans.add("handlerRecorded")
    missing = set(expected)
    accepted = []
    mismatches = []
    for row in rows:
        if (not isinstance(row, dict)
                or set(row) != fields
                or not http_status(row["status"])
                or any(type(row[key]) is not bool for key in booleans)):
            raise ValueError("invalid application observation")
        key = row["operation"], row["actor"]
        if key not in missing:
            raise ValueError("unknown or duplicate matrix cell")
        missing.remove(key)
        expected_status = expected[key]
        handler_expected = (expected_status < 400 or case_id == "BB-ROLE-RULES"
                            or row["actor"] == "other-USER" or row["operation"] == "wrong-password")
        projected = {**row, "expectedStatus": expected_status}
        if observe_handler:
            projected["handlerExpected"] = handler_expected
        accepted.append(projected)
        if (row["status"] != expected_status or not row["responseMatches"] or not row["stateMatches"]
                or (observe_handler and row["handlerRecorded"] != handler_expected)):
            mismatches.append(key)
    return accepted, mismatches
