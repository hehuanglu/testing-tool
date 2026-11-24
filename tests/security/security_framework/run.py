"""Run a reviewed suite against a disposable local fixture and emit CI artifacts."""

import argparse
from contextlib import ExitStack
from importlib import import_module
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from uuid import uuid4

from .engine import execute_plan, validate_loopback
from .evidence import (EXIT, add_check, evidence_keys, fail_run, finish, markdown, outcome, put_evidence,
                       start, valid_outcome, validate_child)
from .execution import APPLICATION, PASSIVE, Engine, ExecutionError
from .manifest import NATIVE_JWT, ROOT, SCANNER_METHODS, read_suite, restriction_reason

CONTAINER_TIMEOUT = 220
IMAGE_PIN = re.compile(r"[a-z0-9./_-]+@sha256:[0-9a-f]{64}\Z")


def blocked(result, suite):
    for case_id, case in suite.cases.items():
        kind = suite.profiles[case["authProfile"]]["kind"]
        reason = restriction_reason(case["method"], kind)
        if reason is None:
            continue
        put_evidence(result, case_id, "capability-boundary",
                     {"dispatched": False, "reason": reason})
        add_check(result, suite, case_id, outcome("BLOCKED", reason), [case_id])
    return [case for case in suite.cases.values() if case["id"] not in result["checks"]]


def identity(result, key, profile, observed):
    """Require application-resolved subjects and success status for every expected actor."""
    if not isinstance(observed, dict) or not observed:
        return "INCOMPLETE_EXECUTION"
    projection = {}
    reasons = set()
    for actor in profile["actors"]:
        row = observed.get(actor)
        if row is None:
            reasons.add("INCOMPLETE_EXECUTION")
            continue
        if not isinstance(row, dict) or type(row.get("status")) is not int:
            reasons.add("INVALID_EVIDENCE")
            continue
        resolved = row.get("actor")
        reported = resolved if resolved in (*profile["actors"], "anonymous", None) else "unrecognized"
        projection[actor] = {"actor": reported, "status": row["status"]}
        if resolved != actor or not 200 <= row["status"] < 300:
            reasons.add("AUTHENTICATION_FAILURE")
    if projection:
        put_evidence(result, key, "application-identity", projection)
    return next((reason for reason in ("AUTHENTICATION_FAILURE", "INVALID_EVIDENCE", "INCOMPLETE_EXECUTION")
                 if reason in reasons), None)


def scan_fixture(request):
    return execute_plan(*request)


def observe_application(request):
    evaluate, case, origin, evidence, profile = request
    return evaluate(case, origin, evidence, profile)


FIXTURE_PASSIVE = Engine("zap-passive", PASSIVE, scan_fixture)
FIXTURE_HTTP = Engine("live-http", APPLICATION, observe_application)


def worker(suite, run_id):
    result = start(suite, run_id)
    cases = blocked(result, suite)
    if not cases:
        return finish(result)
    try:
        adapter = import_module(f"suites.{suite.name}.adapter")
        with ExitStack() as resources:
            scanner_cases = [case for case in cases if case["method"] in SCANNER_METHODS]
            application_cases = [case for case in cases if case["method"] not in SCANNER_METHODS]
            FIXTURE_PASSIVE.admit(suite, scanner_cases)
            FIXTURE_HTTP.admit(suite, application_cases)
            directory, origin, observe = adapter.Adapter(suite.scenario).prepare(resources)
            validate_loopback(origin)
            scan_error = None
            if scanner_cases:
                profiles = {case["authProfile"]: suite.profiles[case["authProfile"]]
                            for case in scanner_cases if
                            suite.profiles[case["authProfile"]]["kind"] != "none"}

                def scanner_identity(events):
                    reasons = [identity(result, "scannerIdentity-" + profile_id, profile,
                                        adapter.scanner_identities(events, profile))
                               for profile_id, profile in profiles.items()]
                    return ("AUTHENTICATION_FAILURE" if "AUTHENTICATION_FAILURE" in reasons
                            else next((reason for reason in reasons if reason), None))

                definition = adapter.build_plan(origin, directory, suite.scenario, profiles)
                after_report = getattr(adapter, "after_report", None)
                scan_error = FIXTURE_PASSIVE.run(suite, scanner_cases, (
                    result, directory, origin, definition, observe,
                    scanner_identity if profiles else None,
                    (lambda path: after_report(path, suite.scenario)) if after_report else None,
                ))

            for case in cases:
                case_id = case["id"]
                profile = suite.profiles[case["authProfile"]]
                required = evidence_keys(case, profile)
                if scan_error and case in scanner_cases:
                    add_check(result, suite, case_id, outcome("ERROR", scan_error),
                              [key for key in dict.fromkeys([*required, "scannerEvents"])
                               if key in result["evidence"]])
                    continue
                try:
                    if case in scanner_cases:
                        status, rows, identities = adapter.evaluate(case, origin, result["evidence"], profile)
                    else:
                        status, rows, identities = FIXTURE_HTTP.run(
                            suite, [case], (adapter.evaluate, case, origin, result["evidence"], profile))
                    for key, data in rows.items():
                        put_evidence(result, key, "suite-assertion", data)
                    if case["method"] not in SCANNER_METHODS and profile["kind"] != "none":
                        reason = identity(result, case_id + "-identity", profile, identities)
                        if reason:
                            status = outcome("ERROR", reason)
                    if (valid_outcome(status) and status["verdict"] in {"PASS", "FAIL"} and
                            not all(key in result["evidence"] for key in required)):
                        status = outcome("ERROR", "MISSING_EVIDENCE")
                except (OSError, TypeError, KeyError, ValueError):
                    status = outcome("ERROR", "APPLICATION_EVIDENCE_FAILURE")
                add_check(result, suite, case_id, status,
                          [key for key in required if key in result["evidence"]])
    except ExecutionError as error:
        return fail_run(result, suite, error.args[0])
    except (OSError, subprocess.SubprocessError):
        return fail_run(result, suite, "INFRASTRUCTURE_FAILURE")
    except Exception:
        # Fixture/adapter exceptions may carry credentials; keep only the classification.
        return fail_run(result, suite, "SUITE_EXECUTION_FAILURE")
    return finish(result)


def run_container(suite, run_id, image):
    result = start(suite, run_id)
    cases = blocked(result, suite)
    if not cases:
        return finish(result)
    if any(suite.profiles[case["authProfile"]]["kind"] == NATIVE_JWT for case in cases):
        return fail_run(result, suite, "PRODUCT_FIXTURE_REQUIRED")
    name = f"security-suite-{run_id}"
    command = [
        "docker", "run", "--rm", "--name", name, "--pull", "never", "--network", "none",
        "--hostname", "localhost", "--entrypoint", "python3", "-e", "PYTHONPATH=/suite",
        "-v", f"{ROOT}:/suite:ro", image, "-m", "security_framework.run", "--worker",
        "--suite", suite.name, "--scenario", suite.scenario, "--run-id", run_id,
    ]
    try:
        process = subprocess.run(command, capture_output=True, timeout=CONTAINER_TIMEOUT, check=False)
    except subprocess.TimeoutExpired:
        try:
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15, check=False)
        except (OSError, subprocess.SubprocessError):
            pass
        return fail_run(result, suite, "CONTAINER_TIMEOUT")
    except OSError:
        return fail_run(result, suite, "INFRASTRUCTURE_FAILURE")

    # Docker Desktop can exit 1 before starting the worker when its API is unreachable.
    daemon_unreachable = (
        process.returncode == 1
        and not process.stdout.strip()
        and process.stderr.lower().startswith((
            b"failed to connect to the docker api at ",
            b"cannot connect to the docker daemon at ",
        ))
    )
    if process.returncode not in EXIT.values() or daemon_unreachable:
        put_evidence(result, "containerExit", "runner", {"exit": process.returncode})
        return fail_run(result, suite, "INFRASTRUCTURE_FAILURE")
    if not process.stdout.strip():
        return fail_run(result, suite, "MISSING_EVIDENCE")
    try:
        child = json.loads(process.stdout)
        return validate_child(child, suite, run_id, process.returncode)
    except (KeyError, ValueError, TypeError, AttributeError):
        return fail_run(result, suite, "INVALID_EVIDENCE")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", required=True)
    parser.add_argument("--scenario", default="baseline")
    parser.add_argument("--out", type=Path, help="new artifact directory")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--run-id", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        suite = read_suite(args.suite, args.scenario)
    except (OSError, ValueError, TypeError):
        print("ERROR MANIFEST_VALIDATION_FAILURE", file=sys.stderr)
        return EXIT["ERROR"]
    if args.worker:
        if not args.run_id or not re.fullmatch(r"[0-9a-f]{32}", args.run_id):
            parser.error("invalid worker run ID")
        result = worker(suite, args.run_id)
        print(json.dumps(result, sort_keys=True, allow_nan=False))
        return result["exitCode"]
    if args.out is None or args.out.exists():
        parser.error("--out must name a new directory")
    run_id = uuid4().hex
    try:
        image = (ROOT / "zap-image.txt").read_text(encoding="utf-8").strip()
        if not IMAGE_PIN.fullmatch(image):
            raise ValueError("image must be pinned")
    except (OSError, ValueError):
        result = fail_run(start(suite, run_id), suite, "INFRASTRUCTURE_FAILURE")
    else:
        result = run_container(suite, run_id, image)
        result["scannerImage"] = image
    result["executionEnvironment"] = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
    try:
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / "report.md").write_text(markdown(result), encoding="utf-8")
        (args.out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True,
                                                        allow_nan=False) + "\n", encoding="utf-8")
    except (OSError, ValueError):
        print("ERROR EVIDENCE_WRITE_FAILURE", file=sys.stderr)
        return EXIT["ERROR"]
    print(f'{result["verdict"]} {args.out / "result.json"}')
    return result["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
