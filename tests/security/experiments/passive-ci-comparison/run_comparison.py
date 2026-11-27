#!/usr/bin/env python3
"""Qualify two ZAP CI entrypoints against one disposable HTTP fixture."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.parse import urlsplit

EXPERIMENT = Path(__file__).resolve().parent
SECURITY = EXPERIMENT.parents[1]
REPO = SECURITY.parents[1]
sys.path.insert(0, str(SECURITY))

from fixtures.csp_demo import FixtureServer
from run_zap_suite import STATUSES, atomic_json, classify, render_plan, run_process
from zap_report import ReportError, load_fresh_report

CASE = json.loads((SECURITY / "cases/csp-docs.json").read_text())
PROTECTED_REQUEST = next(request for request in CASE["requests"] if request["id"] == CASE["expect"]["absentOn"])
IMAGE = (SECURITY / "zap-image.txt").read_text().strip()
ACTION_SHA = "c41784dfded31e10c69d78896700f48e5fd5fa3a"
ZAP_OPTIONS = [
    "-config", "alert.maxInstances=0",
    "-config", "alert.mergeissues=false",
    "-config", "autoupdate.checkOnStart=false",
    "-config", "autoupdate.installOnStart=false",
    "-config", "autoupdate.downloadNewRelease=false",
    "-config", "autoupdate.promptToInstall=false",
    "-config", "autoupdate.start.check=false",
    "-config", "autoupdate.start.download=false",
    "-config", "autoupdate.start.install=false",
]
SCENARIOS = {
    "C01": ("healthy", False, False, ("primary", "repeat")),
    "C02": ("csp-regression", False, False, ("primary",)),
    "C03": ("healthy", True, False, ("primary",)),
    "C04": ("wrong-page", False, False, ("primary",)),
    "C05": ("duplicate-docs", False, True, ("primary",)),
    "C06": ("missing-control", False, False, ("primary",)),
    "C07": ("healthy", False, False, ("primary", "recovery")),
}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def checked_output(command):
    return subprocess.check_output(command, text=True, timeout=30).strip()


def tested_sha():
    return os.environ.get("REGRESSION_TESTED_COMMIT_SHA") or checked_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"])


def force_timeout(scenario, trial):
    return scenario == "C07" and trial == "primary"


def new_fixture(scenario):
    return FixtureServer(CASE, uuid.uuid4().hex, SCENARIOS[scenario][0]).start()


def prepare_plan(root, fixture, scenario, report_dir):
    _, omit, repeat, _trials = SCENARIOS[scenario]
    suite_plan = render_plan(CASE, fixture.origin, report_dir, "docs" if omit else None,
                             repeat_request_id="docs" if repeat else None)
    plan = read(EXPERIMENT / "af-plan.json")
    plan["env"] = suite_plan["env"]
    plan["jobs"][1]["requests"] = suite_plan["jobs"][1]["requests"]
    for test in plan["jobs"][2]["tests"]:
        test.update(url=fixture.origin + PROTECTED_REQUEST["path"],
                    responseBodyRegex=re.escape(CASE["requireResponses"]["protectedBodyMarker"]))
    plan["jobs"][3]["parameters"]["reportDir"] = str(report_dir)
    atomic_json(root / "af-plan.yaml", plan)


def stop_fixture(root, fixture):
    fixture.stop()
    atomic_json(root / "receipt.json", {"origin": fixture.origin,
                "runId": fixture.server.run_id, "responses": fixture.evidence(), "cleanup": True})


def fixture_process(root, scenario):
    root.mkdir(parents=True, exist_ok=False)
    fixture = new_fixture(scenario)
    stopped = False

    def request_stop(_signum, _frame):
        nonlocal stopped
        stopped = True

    signal.signal(signal.SIGTERM, request_stop)
    try:
        plan_dir = Path("/zap/wrk") / root.relative_to(Path(os.environ["GITHUB_WORKSPACE"]))
        root.chmod(0o777)  # The action uses the image's own UID.
        prepare_plan(root, fixture, scenario, plan_dir)
        atomic_json(root / "ready.json", {"pid": os.getpid(), "origin": fixture.origin,
                                         "startedNs": time.time_ns()})
        while not stopped:
            time.sleep(0.1)
    finally:
        stop_fixture(root, fixture)


def ready_action(root):
    ready = read(root / "ready.json")
    origin = urlsplit(ready["origin"])
    if origin.scheme != "http" or origin.hostname != "127.0.0.1":
        raise ValueError("AF fixture must be runner-loopback")
    with socket.create_connection((origin.hostname, origin.port), timeout=3):
        pass
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    plan = (root / "af-plan.yaml").relative_to(workspace)
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"plan={plan}\nzap_options={' '.join(ZAP_OPTIONS)}\n")


def job_test_results(log_path):
    results = {}
    for line in log_path.read_text(errors="replace").splitlines():
        # Keep the upstream message as well as the projected status.
        if "test" not in line.lower():
            continue
        for name in ("docs-content", "docs-csp"):
            if name in line:
                match = re.search(r"\b(pass(?:ed)?|fail(?:ed|ure)?)\b", line, re.IGNORECASE)
                if match:
                    results[name] = {"passed": match[1].lower().startswith("pass"), "line": line}
    return results


def row(root, implementation, scenario, trial, actual, reason, native_exit, gate_exit,
        *, action_outcome=None, locators=None, cleanup=False, run_id=None):
    atomic_json(root / "trial.json", {
        "scenario": scenario, "trial": trial, "implementation": implementation,
        "caseId": CASE["id"], "testedSha": tested_sha(),
        "actionSha": ACTION_SHA if action_outcome is not None else None,
        "imageDigest": IMAGE.split("@")[1], "actual": actual, "reason": reason,
        "nativeExit": native_exit, "caseGateExit": gate_exit, "actionOutcome": action_outcome,
        "cleanup": cleanup, "runId": run_id, "locators": locators or {},
    })


def read_af(root, scenario, trial, native_exit, started_ns, *, timed_out=False, action_outcome=None):
    receipt = read(root / "receipt.json")
    locators = {name: file for name, file in {
        "receipt": "receipt.json", "log": "zap.log", "plan": "af-plan.yaml",
        "report": "zap-report.json", "jobTests": "af-job-tests.json", "instances": "af-instances.json",
    }.items() if (root / file).is_file()}
    actual, reason = "EXECUTION_ERROR", "TIMEOUT"
    if not timed_out:
        try:
            if native_exit is None:
                raise ReportError("ACTION_CONTAINER_MISSING")
            if native_exit not in (0, 2):
                raise ReportError("ZAP_NATIVE_EXIT_NONZERO")
            if action_outcome is not None and action_outcome != ("success" if native_exit == 0 else "failure"):
                raise ReportError("ACTION_OUTCOME_MISMATCH")
            _raw, report = load_fresh_report(root / "zap-report.json", started_ns)
            tests = job_test_results(root / "zap.log")
            atomic_json(root / "af-job-tests.json", tests)
            locators["jobTests"] = "af-job-tests.json"
            instances = [{"pointer": instance.pointer, "alertId": instance.native_id,
                          "origin": instance.origin, "method": instance.method, "path": instance.path,
                          "responseId": instance.response_id}
                         for instance in report.instances if instance.alert_ref == CASE["expect"]["alertRef"]]
            atomic_json(root / "af-instances.json", instances)
            locators["instances"] = "af-instances.json"
            if set(tests) != {"docs-content", "docs-csp"}:
                raise ReportError("AF_URL_TEST_RESULTS_MISSING")
            responses = receipt["responses"]
            actual, reason = classify(CASE, receipt["origin"], responses, report)
            if actual == "PASS" and not all(item["passed"] for item in tests.values()):
                actual, reason = "MISSING_EVIDENCE", "AF_URL_TEST_NOT_SATISFIED"
            if actual == "REGRESSION":
                protected_count = sum(item["requestId"] == PROTECTED_REQUEST["id"] for item in responses)
                # URL tests report the site node, which can represent a different response on repeated GETs.
                if protected_count == 1 and (not tests["docs-content"]["passed"] or tests["docs-csp"]["passed"]):
                    actual, reason = "MISSING_EVIDENCE", "AF_URL_TEST_INCONSISTENT"
        except ReportError as exc:
            actual, reason = "EXECUTION_ERROR", str(exc)
    row(root, "af", scenario, trial, actual, reason, native_exit, int(actual != "PASS"),
        action_outcome=action_outcome, locators=locators, cleanup=receipt["cleanup"], run_id=receipt["runId"])


def engine(root, scenario, trial):
    fixture = new_fixture(scenario)
    home = root / "zap-home"
    home.mkdir()
    try:
        prepare_plan(root, fixture, scenario, root)
        timeout = 0.01 if force_timeout(scenario, trial) else 180
        native_exit, timed_out, started = run_process(
            ["/zap/zap.sh", "-cmd", "-dir", str(home), *ZAP_OPTIONS,
             "-autorun", str(root / "af-plan.yaml")], root / "zap.log", timeout)
    finally:
        try:
            stop_fixture(root, fixture)
        finally:
            shutil.rmtree(home)
    read_af(root, scenario, trial, native_exit, started, timed_out=timed_out)


def collect_action(root, scenario, trial, action_outcome):
    ready = read(root / "ready.json")
    workspace = Path(os.environ["GITHUB_WORKSPACE"])
    plan = str(Path("/zap/wrk") / (root / "af-plan.yaml").relative_to(workspace))
    native_exit = None
    matches = []
    try:
        ids = checked_output(["docker", "ps", "--all", "--quiet"]).splitlines()
        if ids:
            inspected = json.loads(checked_output(["docker", "inspect", *ids]))
            matches = [container for container in inspected if
                       container["Config"]["Image"] == IMAGE and plan in container["Args"] and
                       any(mount["Source"] == str(workspace) and mount["Destination"] == "/zap/wrk"
                           for mount in container["Mounts"])]
        if len(matches) == 1:
            container = matches[0]
            native_exit = container["State"]["ExitCode"] if not container["State"]["Running"] else None
            with (root / "zap.log").open("wb") as log:
                subprocess.run(["docker", "logs", container["Id"]], stdout=log,
                               stderr=subprocess.STDOUT, check=True, timeout=30)
    finally:
        try:
            if matches:
                subprocess.run(["docker", "rm", "-f", *(item["Id"] for item in matches)],
                               check=True, timeout=30)
        finally:
            os.kill(ready["pid"], signal.SIGTERM)
            deadline = time.monotonic() + 10
            while not (root / "receipt.json").is_file() and time.monotonic() < deadline:
                time.sleep(0.1)
    read_af(root, scenario, trial, native_exit, ready["startedNs"], action_outcome=action_outcome)


def local_trial(root, implementation, scenario, trial):
    mode, omit, repeat, _trials = SCENARIOS[scenario]
    root.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, REGRESSION_TESTED_COMMIT_SHA=tested_sha())
    if implementation == "suite":
        options = ["--fixture-mode", mode]
        if omit:
            options.extend(["--omit-request-id", "docs"])
        if repeat:
            options.extend(["--repeat-request-id", "docs"])
        if force_timeout(scenario, trial):
            options.extend(["--deadline", "0.01"])
        command = ["bash", str(SECURITY / "run_zap_suite.sh"), "--cases", str(SECURITY / "cases"),
                   "--out", str(root / "suite"), *options]
    else:
        command = ["docker", "run", "--rm", "--network", "none", "--hostname", "localhost",
                   "--user", f"{os.getuid()}:{os.getgid()}",
                   "--env", "HOME=/tmp",
                   "--env", f"REGRESSION_TESTED_COMMIT_SHA={env['REGRESSION_TESTED_COMMIT_SHA']}",
                   "--mount", f"type=bind,src={SECURITY},dst=/workspace/security,readonly",
                   "--mount", f"type=bind,src={root},dst=/zap/wrk/output",
                   IMAGE, "python3",
                   "/workspace/security/experiments/passive-ci-comparison/run_comparison.py",
                   "--implementation", "af", "--scenario", scenario, "--trial", trial,
                   "--phase", "engine", "--out", "/zap/wrk/output"]
    with (root / "launcher.log").open("wb") as log:
        process = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=220)
    if implementation == "suite" and (root / "suite/suite-results.json").is_file():
        result = read(root / "suite/suite-results.json")
        if result["caseCount"] != 1 or result["testedCommitSha"] != tested_sha() or result["imageDigest"] != IMAGE.split("@")[1]:
            raise ValueError("SUITE_RUN_BINDING_MISMATCH")
        case = result["cases"][0]
        locators = {"suiteResult": "suite/suite-results.json", "launcher": "launcher.log"}
        for name in ("evidencePath", "logPath", "planPath", "reportPath"):
            if case[name] is not None:
                locators[name] = "suite/" + case[name]
        row(root, implementation, scenario, trial, case["status"], case["reason"],
            case["nativeExit"], process.returncode, locators=locators,
            cleanup=not (root / "suite" / CASE["id"] / "zap-home").exists() and
            not case["reason"].startswith("FIXTURE_CLEANUP_ERROR"),
            run_id=result["runId"])
    if not (root / "trial.json").is_file():
        row(root, implementation, scenario, trial, "EXECUTION_ERROR", "LAUNCHER_RESULT_MISSING",
            process.returncode, 1, locators={"launcher": "launcher.log"})


def qualify(root, implementation, scenarios):
    # Load the oracle only after the runners have each retained their actual results.
    expectations = read(EXPERIMENT / "expected.json")
    rows = []
    for scenario in scenarios:
        trials = SCENARIOS[scenario][3]
        run_ids = set()
        for trial, expected in zip(trials, expectations[scenario][implementation], strict=True):
            directory = root / scenario / trial
            path = directory / "trial.json"
            result = read(path) if path.is_file() else {
                "scenario": scenario, "trial": trial, "implementation": implementation,
                "caseId": CASE["id"], "testedSha": tested_sha(), "imageDigest": IMAGE.split("@")[1],
                "actual": "EXECUTION_ERROR", "reason": "TRIAL_ARTIFACT_MISSING", "caseGateExit": 1,
                "nativeExit": None, "actionSha": None, "cleanup": False, "locators": {},
            }
            locators = result["locators"]
            missing = [name for name, relative in locators.items() if
                       not (directory / relative).resolve().is_relative_to(directory.resolve()) or
                       not (directory / relative).is_file()]
            required = {"suiteResult", "evidencePath", "logPath", "planPath"} if implementation == "suite" else {
                "receipt", "log", "plan"}
            if not force_timeout(scenario, trial):
                required |= {"reportPath"} if implementation == "suite" else {"report", "jobTests", "instances"}
            missing.extend(sorted(required - set(locators)))
            expected_reason = "TIMEOUT" if force_timeout(scenario, trial) else None
            expected_reason = {
                "C02": "PROTECTED_ALERT_PRESENT", "C03": "REQUIRED_RESPONSE_MISSING",
                "C04": "RESPONSE_CONTENT_MISMATCH", "C05": "PROTECTED_ALERT_PRESENT",
                "C06": "CONTROL_ALERT_MISSING",
            }.get(scenario, expected_reason)
            accepted = (expected in STATUSES and result["actual"] == expected and
                        (expected_reason is None or result["reason"] == expected_reason) and
                        result["caseGateExit"] == int(expected != "PASS") and result["cleanup"] and not missing and
                        (result["scenario"], result["trial"], result["implementation"], result["caseId"],
                         result["testedSha"], result["imageDigest"]) ==
                        (scenario, trial, implementation, CASE["id"], tested_sha(), IMAGE.split("@")[1]))
            run_id = result.get("runId")
            accepted = accepted and bool(run_id) and run_id not in run_ids
            if run_id:
                run_ids.add(run_id)
            if implementation == "af" and os.environ.get("GITHUB_ACTIONS") == "true" and not force_timeout(scenario, trial):
                accepted = accepted and result["actionSha"] == ACTION_SHA and result["actionOutcome"] in ("success", "failure")
            rows.append(dict(result, expected=expected, expectedReason=expected_reason,
                             missingArtifacts=missing, qualification="matched" if accepted else "mismatch",
                             equivalence="equivalent" if accepted else "unverified",
                             artifact=(str(path.relative_to(root)) if path.is_file() else None)))
    passed = bool(rows) and all(result["qualification"] == "matched" for result in rows)
    atomic_json(root / "comparison-results.json", {"qualification": "passed" if passed else "failed",
                                                    "results": rows})
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation", choices=("suite", "af"), required=True)
    parser.add_argument("--scenario", choices=("all", *SCENARIOS), required=True)
    parser.add_argument("--out", type=lambda value: Path(value).resolve(), required=True)
    parser.add_argument("--phase", choices=("run", "local-trial", "engine", "fixture", "ready-action", "collect-action", "assert"),
                        default="run")
    parser.add_argument("--trial", choices=("primary", "repeat", "recovery"), default="primary")
    parser.add_argument("--action-outcome", choices=("success", "failure", "cancelled", "skipped"))
    args = parser.parse_args()
    root = args.out
    scenarios = SCENARIOS if args.scenario == "all" else (args.scenario,)
    if args.phase == "assert":
        return qualify(root, args.implementation, scenarios)
    if args.phase != "run":
        if len(scenarios) != 1 or args.trial not in SCENARIOS[args.scenario][3]:
            parser.error("single-phase invocation requires a valid scenario and trial")
        trial = root / args.scenario / args.trial if args.phase != "engine" else root
        if args.phase == "fixture":
            fixture_process(trial, args.scenario)
        elif args.phase == "ready-action":
            ready_action(trial)
        elif args.phase == "collect-action":
            collect_action(trial, args.scenario, args.trial, args.action_outcome)
        elif args.phase == "engine":
            engine(trial, args.scenario, args.trial)
        else:
            local_trial(trial, args.implementation, args.scenario, args.trial)
        return 0
    if root.exists() and any(root.iterdir()):
        parser.error("comparison output must be new or empty")
    root.mkdir(parents=True, exist_ok=True)
    for scenario in scenarios:
        for trial in SCENARIOS[scenario][3]:
            directory = root / scenario / trial
            try:
                local_trial(directory, args.implementation, scenario, trial)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                row(directory, args.implementation, scenario, trial, "EXECUTION_ERROR",
                    f"TRIAL_SETUP:{type(exc).__name__}:{exc}", None, 1)
    return qualify(root, args.implementation, scenarios)


if __name__ == "__main__":
    raise SystemExit(main())
