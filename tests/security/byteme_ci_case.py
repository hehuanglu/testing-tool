"""Stdlib validation for the ByteMe event-checkout case contract."""

import re

ADAPTER = "byteme-ci-v1"
REPOSITORY = "https://github.com/hehuanglu/ByteMe.git"
SLUG = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SHA = re.compile(r"[0-9a-f]{40}")
DIGEST = re.compile(r"[0-9a-f]{64}")
POINTER = re.compile(r"/(?:[^~/\x00-\x1f]|~[01])+(?:/(?:[^~/\x00-\x1f]|~[01])+)*")
LOCAL_PATH = re.compile(r"(^|[\s(])/(?:Users|home|private|tmp)/|[A-Za-z]:[\\/]")


def fields(value, names):
    return isinstance(value, dict) and set(value) == set(names.split())


def matches(pattern, value):
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def nonempty_list(value):
    return isinstance(value, list) and bool(value)


def require(condition, label):
    if not condition:
        raise ValueError(f"invalid event-checkout case field: {label}")


def validate_case(case, filename):
    require(fields(case, "schemaVersion source id profile fixture target provenance "
                         "requests requireResponses expect"), "case")
    require(case["schemaVersion"] == 2 and matches(SLUG, case["id"])
            and filename == case["id"] + ".json", "identity")
    require(case["fixture"] == ADAPTER and case["profile"] == "anti-framing-http-v1",
            "fixture/profile")
    require(case["target"] == {"adapter": ADAPTER, "repository": REPOSITORY,
                               "revisionPolicy": "event-checkout"}, "target")
    provenance = case["provenance"]
    require(fields(provenance, "reviewedProductCommitSha parentCaseSha256")
            and matches(SHA, provenance["reviewedProductCommitSha"])
            and matches(DIGEST, provenance["parentCaseSha256"]), "provenance")
    source = case["source"]
    require(fields(source, "kind assessmentId caseId criterionIds planRevision planDigest evidence")
            and source["kind"] == "assessment-run-v3"
            and all(nonempty(source[key]) for key in ("assessmentId", "caseId", "planRevision"))
            and matches(DIGEST, source["planDigest"]), "source")
    criteria = source["criterionIds"]
    require(nonempty_list(criteria) and all(map(nonempty, criteria))
            and len(set(criteria)) == len(criteria), "source/criterionIds")
    require(nonempty_list(source["evidence"]), "source/evidence")
    for row in source["evidence"]:
        require(fields(row, "operationId resultPath sha256") and nonempty(row["operationId"])
                and matches(POINTER, row["resultPath"]) and matches(DIGEST, row["sha256"]),
                "source/evidence")
    require(nonempty_list(case["requests"]), "requests")
    ids = set()
    for row in case["requests"]:
        require(fields(row, "id method origin path") and matches(SLUG, row["id"])
                and row["id"] not in ids and row["method"] == "GET"
                and row["origin"] == "product", "requests")
        path = row["path"]
        require(isinstance(path, str) and path.startswith("/") and not path.startswith("//")
                and not re.search(r"[?#\\\x00-\x20\x7f]", path)
                and not {".", ".."}.intersection(path.split("/")), "requests/path")
        ids.add(row["id"])
    require(case["requireResponses"] == {"status": 200, "mediaType": "text/html"},
            "requireResponses")
    expect = case["expect"]
    require(fields(expect, "basis evaluateOn trustedAncestors assumption")
            and nonempty(expect["basis"]) and not LOCAL_PATH.search(expect["basis"])
            and isinstance(expect["evaluateOn"], str) and expect["evaluateOn"] in ids
            and expect["trustedAncestors"] == ["'self'"]
            and expect["assumption"] == "modern-user-agent-csp3-html-xfo", "expect")
    return case
