#!/usr/bin/env python3
"""Verify a downloaded ByteMe regression artifact against GitHub run identity."""

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

from write_summary import read_json, render

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from byteme_ci_case import ADAPTER, DIGEST, SHA, SLUG, validate_case
from run_zap_product_suite import STATUSES


SUITE_FIELDS = set("""adapterRegistrySha256 caseCount cases counts expectedProductCommitSha github
imageDigest pullRequestBaseSha pullRequestHeadSha runId runnerCommitSha runnerSha256
schemaVersion status testedProductCommitSha""".split())
TOP_LEVEL = {"suite-results.json", "run-metadata.json", "fallback-cleanup.json", "summary.md",
             "junit.xml"}
CASE_FILES = {"case.json", "result.json", "target-identity.json", "cleanup.json",
              "build.log", "readiness.log", "scanner-container.log", "adapter-error.txt",
              "scan/evidence.json", "scan/zap-history.json", "scan/runtime-result.json"}
FORBIDDEN = re.compile(
    rb"-----BEGIN [A-Z ]*PRIVATE KEY-----|gh[pousr]_[A-Za-z0-9]{20,}|"
    rb"github_pat_[A-Za-z0-9_]{20,}|Bearer [A-Za-z0-9_.=-]{16,}|"
    rb"(?:DB|MYSQL(?:_ROOT)?)_PASSWORD=|/Users/|/home/runner/|/private/var/|"
    rb'"(?:requestHeader|responseHeader|requestBody|responseBody)"'
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def stage(source, destination):
    destination.mkdir(parents=True, exist_ok=False)
    if (source / "suite-results.json").is_file():
        suite = read_json(source / "suite-results.json")
        allowed = set(TOP_LEVEL)
        for row in suite["cases"]:
            case_id = row["id"]
            require(SLUG.fullmatch(case_id), "invalid case ID")
            allowed.update(f"{case_id}/{name}" for name in CASE_FILES)
    else:
        allowed = {"bootstrap.json", "fallback-cleanup.json", "summary.md", "junit.xml"}
    paths = []
    for name in sorted(allowed):
        path = source / name
        require(not path.is_symlink() and not path.parent.is_symlink()
                and path.resolve().is_relative_to(source.resolve()), "unsafe artifact path")
        if path.is_file():
            require(not FORBIDDEN.search(path.read_bytes()), "private material detected")
            paths.append((name, path))
    require(paths, "no allowlisted files were produced")
    for name, path in paths:
        target = destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)


def checked_files(root):
    files = {}
    for path in root.rglob("*"):
        require(not path.is_symlink(), "artifact contains a symlink")
        if path.is_dir():
            continue
        require(path.is_file(), "artifact contains a non-regular file")
        relative = path.relative_to(root).as_posix()
        first, _, tail = relative.partition("/")
        require(relative in TOP_LEVEL or (SLUG.fullmatch(first) and tail in CASE_FILES),
                "file outside artifact allowlist")
        contents = path.read_bytes()
        require(not FORBIDDEN.search(contents), "private material detected in artifact")
        files[relative] = hashlib.sha256(contents).hexdigest()
    require(TOP_LEVEL <= files.keys(), "missing suite files")
    return files


def verify_case(root, files, suite, row):
    case_id = row["id"]
    require(SLUG.fullmatch(case_id), "invalid case ID")
    require(row["adapter"] == ADAPTER and row["variant"] == "upstream-original",
            "unexpected case adapter or variant")
    base = root / case_id
    expected_paths = {"cleanupPath": "cleanup.json", "targetIdentityPath": "target-identity.json",
                      "evidencePath": "scan/evidence.json"}
    for key, filename in expected_paths.items():
        require((key == "evidencePath" and row[key] is None)
                or (row[key] == filename and f"{case_id}/{filename}" in files),
                "artifact locator mismatch")
    case_file = base / "case.json"
    case = validate_case(read_json(case_file), case_id + ".json")
    require(files[f"{case_id}/case.json"] == row["caseHash"], "case hash mismatch")
    require(read_json(base / "result.json") == row, "case result differs from suite")
    identity = read_json(base / row["targetIdentityPath"])
    for key in ("expectedProductCommitSha", "testedProductCommitSha", "runnerCommitSha",
                "adapterRegistrySha256"):
        require(identity[key] == suite[key], "case identity differs from suite")
    require(identity["reviewedProductCommitSha"] == row["reviewedProductCommitSha"]
            == case["provenance"]["reviewedProductCommitSha"], "reviewed SHA mismatch")
    prep = identity["sourcePreparation"]
    if prep:
        require(prep["appliedPatches"] == [], "unexpected source patches")
    cleanup = read_json(base / row["cleanupPath"])
    if cleanup["status"] == "COMPLETE":
        require(len(cleanup["records"]) == 6 and all(r["state"] in ("removed", "absent")
                                                    for r in cleanup["records"]),
                "cleanup record mismatch")
    elif cleanup["status"] == "UNVERIFIED":
        require(row["status"] == "EXECUTION_ERROR" and "preCleanupStatus" in row,
                "unverified cleanup must retain previous outcome")
    else:
        require(cleanup["status"] == "NOT_NEEDED" and not cleanup["records"],
                "unexpected cleanup state")
    if row["reason"] == "BUILD_FAILED":
        require(row["evidencePath"] is None and (base / "build.log").is_file(),
                "unexpected evidence for a failed build")
    if row["status"] != "EXECUTION_ERROR":
        require(row["evidencePath"] and prep and identity["backendImage"]["id"]
                and identity["zapImage"]["id"] and identity["databaseImage"]["id"],
                "missing evidence or image identity")
    if row["evidencePath"]:
        evidence = read_json(base / row["evidencePath"])
        history = read_json(base / "scan/zap-history.json")
        require(evidence["responses"] == history["responses"], "response readback mismatch")
        for response in evidence["responses"]:
            require(set(response["policyHeaders"]) <= {"content-security-policy",
                    "content-security-policy-report-only", "x-frame-options"}, "header allowlist")
        if row["status"] in ("PASS", "REGRESSION"):
            witness = next((r for r in evidence["responses"]
                            if r["requestId"] == case["expect"]["evaluateOn"]), None)
            request = next(r for r in case["requests"] if r["id"] == case["expect"]["evaluateOn"])
            require(witness and witness["actualUrl"] == witness["expectedUrl"]
                    == evidence["productOrigin"] + request["path"]
                    and witness["status"] == 200 and witness["mediaType"] == "text/html"
                    and witness["method"] == "GET" and witness["swaggerUiMarker"]
                    and witness["messageId"] and DIGEST.fullmatch(witness["bodySha256"])
                    and witness["antiFraming"]["state"] ==
                    ("protected" if row["status"] == "PASS" else "unprotected"),
                    "incomplete framing-policy witness")


def verify(root, args):
    files = checked_files(root)
    suite = read_json(root / "suite-results.json")
    require(set(suite) == SUITE_FIELDS | ({"suiteError"} if "suiteError" in suite else set())
            and suite["schemaVersion"] == 2, "unexpected suite schema")
    for key in ("adapterRegistrySha256", "runnerSha256"):
        require(DIGEST.fullmatch(suite[key]), "invalid suite digest")
    for key, expected in (("testedProductCommitSha", args.product_sha),
                          ("expectedProductCommitSha", args.product_sha),
                          ("runnerCommitSha", args.runner_sha),
                          ("pullRequestHeadSha", args.pr_head_sha),
                          ("pullRequestBaseSha", args.pr_base_sha)):
        require(suite[key] == expected and (expected is None or SHA.fullmatch(expected)),
                f"mismatched {key}")
    require(suite["github"] == {"repository": "hehuanglu/ByteMe", "event": args.event,
                               "runId": args.run_id, "runAttempt": args.attempt},
            "mismatched GitHub event metadata")
    metadata = read_json(root / "run-metadata.json")
    require(metadata and all(suite.get(k) == v for k, v in metadata.items()),
            "mismatched run metadata")
    rows = suite["cases"]
    counts = {status: sum(row["status"] == status for row in rows) for status in STATUSES}
    require(len({row["id"] for row in rows}) == suite["caseCount"] == len(rows)
            == sum(counts.values()) and suite["counts"] == counts, "incorrect case counts")
    expected_status = ("ERROR" if "suiteError" in suite else
                       "PASS" if rows and counts["PASS"] == len(rows) else "FAIL")
    require(suite["status"] == expected_status == args.status, "unexpected suite outcome")
    if args.reason:
        require(args.reason in {suite.get("suiteError", {}).get("code"),
                                *(row["reason"] for row in rows)}, "unexpected reason")
    for row in rows:
        verify_case(root, files, suite, row)
    require({name.partition("/")[0] for name in files if "/" in name} ==
            {row["id"] for row in rows}, "orphan artifact case directory")
    fallback = read_json(root / "fallback-cleanup.json")
    require(fallback["status"] == ("COMPLETE" if any(
        read_json(root / row["id"] / "cleanup.json")["status"] != "NOT_NEEDED"
        for row in rows) else "NO_INVENTORY"), "fallback cleanup was not verified")
    require(all(row["state"] in ("removed", "absent") for row in fallback["records"]),
            "fallback cleanup left unreconciled resources")
    summary, junit = render(suite, fallback)
    require((root / "summary.md").read_text(encoding="utf-8") == summary
            and (root / "junit.xml").read_bytes() == junit + b"\n", "summary/JUnit mismatch")
    manifest = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(manifest).hexdigest()


def main():
    if len(sys.argv) == 4 and sys.argv[1] == "stage":
        try:
            stage(Path(sys.argv[2]), Path(sys.argv[3]))
        except (OSError, KeyError, TypeError, ValueError) as error:
            print(f"Artifact staging failed: {error}", file=sys.stderr)
            return 1
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    for option in ("run-id", "attempt", "event", "product-sha", "runner-sha", "status"):
        parser.add_argument("--" + option, required=True)
    for option in ("pr-head-sha", "pr-base-sha", "reason"):
        parser.add_argument("--" + option)
    args = parser.parse_args()
    try:
        digest = verify(args.root, args)
    except (OSError, KeyError, TypeError, ValueError) as error:
        print(f"Artifact verification failed: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"verified": True, "manifestSha256": digest}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
