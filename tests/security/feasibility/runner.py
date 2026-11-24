"""Standalone fixture execution and CI verdicts. Run through run.py."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from tempfile import TemporaryDirectory
import time

from app_assertions import EXPECTED_AUTHORIZATION, authorize
from fixture import ACTORS, CSP_AUTH, CSP_OPEN, fixture
from plan import generate
from zap_report import ReportError, load_fresh_report

METHODS = ("passive", "authenticatedPassive", "apiExploration", "authorization", "automation")
SCENARIOS = ("baseline", "public-csp-regression", "private-csp-regression",
             "coverage-regression", "authorization-regression", "bad-password", "warning",
             "bad-plan", "scanner-failure", "incomplete", "missing-evidence", "invalid-evidence",
             "active-blocked")
EXIT = {"PASS": 0, "FAIL": 1, "ERROR": 2, "BLOCKED": 3}
VERSION = "2.17.0"
RULE = "10038-1"
UPDATES = ("autoupdate.checkOnStart", "autoupdate.checkAddonUpdates", "autoupdate.downloadNewRelease",
           "autoupdate.installAddonUpdates", "autoupdate.installScannerRules",
           "autoupdate.start.checkOnStart", "autoupdate.start.checkAddonUpdates",
           "autoupdate.start.downloadNewRelease", "autoupdate.start.installAddonUpdates",
           "autoupdate.start.installScannerRules")


def outcome(verdict, reason):
    return {"verdict": verdict, "reason": reason}


def check(satisfied, reason):
    return outcome("PASS", "ASSERTIONS_SATISFIED") if satisfied else outcome("FAIL", reason)


def result_for(scenario):
    return {"schemaVersion": 1, "scenario": scenario, "checks": {}, "evidence": {}}


def finish(result):
    checks = result["checks"]
    for verdict in ("ERROR", "BLOCKED", "FAIL", "PASS"):
        reasons = {name: row["reason"] for name, row in checks.items() if row["verdict"] == verdict}
        if reasons:
            result.update(verdict=verdict, exitCode=EXIT[verdict], decisiveChecks=reasons)
            return result
    raise ValueError("empty or invalid checks")


def failed_checks(result, reason):
    result["checks"].update({name: outcome("ERROR", reason) for name in METHODS
                             if name not in result["checks"]})
    return finish(result)


def run_zap(directory, flag, plan, app=None):
    home = directory / ("preflight-home" if flag == "-autocheck" else "run-home")
    home.mkdir()
    log = home / "console"
    args = ["/zap/zap.sh", "-Xmx768m", "-cmd", "-dir", str(home), flag, str(plan)]
    for key in UPDATES:
        args.extend(("-config", key + "=false"))
    timeout = False
    with log.open("wb") as stream:
        process = subprocess.Popen(args, start_new_session=True, stdout=stream, stderr=subprocess.STDOUT)
        try:
            if app is not None:
                deadline = time.monotonic() + 25
                while not app.events and process.poll() is None and time.monotonic() < deadline:
                    time.sleep(0.01)
                if app.events and process.poll() is None:
                    os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            timeout = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    stdout = log.read_text(errors="replace")
    return {"exit": process.returncode, "timedOut": timeout}, stdout


def observed(events, method, path):
    return [event for event in events if (event["method"], event["path"]) == (method, path)]


def evaluate_csp(events, alerts, paths, actor):
    subject, control = paths
    rows = {path: observed(events, "GET", path) for path in paths}
    if any(not rows[path] for path in paths):
        return outcome("ERROR", "INCOMPLETE_EXECUTION")
    if any(not any(row["status"] == 200 and row["actor"] == actor for row in rows[path])
           for path in paths):
        reason = "AUTHENTICATION_FAILURE" if actor in ACTORS else "INCOMPLETE_EXECUTION"
        return outcome("ERROR", reason)
    if not all(row["csp"] is False for row in rows[control]) or control not in alerts:
        return outcome("ERROR", "DETECTOR_CONTROL_MISSING")
    if any((not row["csp"]) != (subject in alerts) for row in rows[subject] if row["status"] == 200):
        return outcome("ERROR", "INVALID_EVIDENCE")
    return check(subject not in alerts, "CSP_REGRESSION")


def identity_checks(events):
    guest = observed(events, "GET", "/identity/guest")
    if not guest:
        return outcome("ERROR", "INCOMPLETE_EXECUTION")
    if any(row["actor"] != "anonymous" or row["status"] != 401 for row in guest):
        return outcome("FAIL", "ANONYMOUS_IDENTITY_ASSERTION")
    for actor in ACTORS:
        logins = [row for row in observed(events, "POST", "/login") if row.get("loginActor") == actor]
        identity = observed(events, "GET", f"/identity/{actor}")
        if any(row["status"] == 401 for row in logins) or any(
                row["status"] != 200 or row["actor"] != actor for row in identity):
            return outcome("ERROR", "AUTHENTICATION_FAILURE")
        if not identity or not any(row["status"] == 200 and row["actor"] == actor for row in logins):
            return outcome("ERROR", "INCOMPLETE_EXECUTION")
    return check(True, "")


def exploration(events):
    for actor in ACTORS:
        index = f"/explore/{actor}/"
        resource = index + "profile"
        starts = observed(events, "GET", index)
        if not starts:
            return outcome("ERROR", "INCOMPLETE_EXECUTION")
        if any(row["actor"] != actor or row["status"] != 200 for row in starts):
            return outcome("ERROR", "AUTHENTICATION_FAILURE")
        if any(resource not in row.get("links", []) for row in starts):
            return outcome("FAIL", "API_LINK_MISSING")
        visits = observed(events, "GET", resource)
        if not visits:
            return outcome("ERROR", "INCOMPLETE_EXECUTION")
        if any(row["actor"] != actor or row["status"] != 200 for row in visits):
            return outcome("ERROR", "AUTHENTICATION_FAILURE")
    return check(True, "")


def execute(scenario):
    result = result_for(scenario)
    evidence = result["evidence"]
    checks = result["checks"]
    if scenario == "active-blocked":
        checks["authenticatedActive"] = outcome("BLOCKED", "ACTIVE_EXECUTION_RESTRICTED")
        evidence.update(dispatched=False, priorAuditEvidence="B01")
        return finish(result)

    with TemporaryDirectory() as temporary, fixture(scenario) as (app, origin):
        directory = Path(temporary)
        plan = directory / "plan.json"
        definition = generate(origin, directory, scenario)
        if scenario == "incomplete":
            definition["jobs"][0]["requests"].pop(0)
        plan.write_text(json.dumps(definition), encoding="utf-8")
        evidence["planSha256"] = hashlib.sha256(plan.read_bytes()).hexdigest()
        preflight, _ = run_zap(directory, "-autocheck", plan)
        evidence["preflight"] = preflight
        evidence["preflightRequests"] = len(app.events)
        if preflight["timedOut"]:
            return failed_checks(result, "INCOMPLETE_EXECUTION")
        if preflight["exit"] != 0 or app.events:
            return failed_checks(result, "PLAN_VALIDATION_FAILURE")

        start = time.time_ns()
        execution, log = run_zap(directory, "-autorun", plan,
                                 app if scenario == "scanner-failure" else None)
        evidence.update(execution=execution, scannerFixtureEvents=list(app.events))
        receipts = re.findall(r"^Job (\S+) (started|finished)(?:, time taken: [^\n]+)?$", log, re.M)
        expected_receipts = [(job["type"], state) for job in definition["jobs"]
                             for state in ("started", "finished")]
        evidence["jobReceipts"] = [list(receipt) for receipt in receipts]
        evidence["planReportedSuccessful"] = "Automation plan succeeded" in log
        if execution["timedOut"]:
            return failed_checks(result, "INCOMPLETE_EXECUTION")
        if execution["exit"] not in (0, 2):
            return failed_checks(result, "SCANNER_FAILURE")
        identity = identity_checks(evidence["scannerFixtureEvents"])
        if identity["reason"] == "AUTHENTICATION_FAILURE":
            return failed_checks(result, "AUTHENTICATION_FAILURE")
        if execution["exit"] == 2:
            return failed_checks(result, "SCANNER_WARNING")
        if not evidence["planReportedSuccessful"] or receipts != expected_receipts:
            return failed_checks(result, "INCOMPLETE_EXECUTION")

        report_path = directory / "zap-report.json"
        evidence["faultInjection"] = None
        if scenario == "missing-evidence" and report_path.is_file():
            report_path.unlink()
            evidence["faultInjection"] = "removedGeneratedReport"
        if scenario == "invalid-evidence" and report_path.is_file():
            report_path.write_text('{"site": {}}', encoding="utf-8")
            evidence["faultInjection"] = "replacedGeneratedReportWithInvalidShape"
        if not report_path.is_file():
            return failed_checks(result, "MISSING_EVIDENCE")
        try:
            raw, report = load_fresh_report(report_path, start)
            if report.capped or report.version != VERSION or not any(
                    site["@name"] == origin for site in raw["site"]):
                raise ReportError("unqualified report")
        except (ReportError, OSError, ValueError, TypeError):
            return failed_checks(result, "INVALID_EVIDENCE")

        rows = [{"path": row.path, "method": row.method, "alertRef": row.alert_ref,
                 "pointer": row.pointer} for row in report.instances
                if row.origin == origin and row.method == "GET" and row.alert_ref == RULE]
        evidence["report"] = {"sha256": hashlib.sha256(report_path.read_bytes()).hexdigest(),
                              "version": report.version, "capped": report.capped,
                              "ruleInstances": rows}
        alerts = {row["path"] for row in rows}

        events = evidence["scannerFixtureEvents"]
        checks["passive"] = evaluate_csp(events, alerts, CSP_OPEN, "anonymous")
        checks["authenticatedPassive"] = (
            evaluate_csp(events, alerts, CSP_AUTH, "reader") if identity["verdict"] == "PASS" else identity
        )
        checks["apiExploration"] = exploration(events) if identity["verdict"] == "PASS" else identity
        try:
            identities, authorization = authorize(origin)
        except (OSError, ValueError):
            checks["authorization"] = outcome("ERROR", "APPLICATION_EVIDENCE_FAILURE")
        else:
            evidence["applicationIdentities"] = identities
            evidence["authorization"] = {"expected": EXPECTED_AUTHORIZATION, "observed": authorization}
            checks["authorization"] = (
                outcome("ERROR", "AUTHENTICATION_FAILURE") if authorization is None else
                check(authorization == EXPECTED_AUTHORIZATION, "AUTHORIZATION_ASSERTION_VIOLATED")
            )
        # This verdict belongs to the whole AF-backed security workload, including its assertions.
        checks["automation"] = next((row for verdict in ("ERROR", "FAIL")
                                     for row in checks.values() if row["verdict"] == verdict),
                                    outcome("PASS", "ASSERTIONS_SATISFIED"))
        return finish(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS)
    args = parser.parse_args()
    try:
        result = execute(args.scenario)
    except (OSError, subprocess.SubprocessError):
        result = failed_checks(result_for(args.scenario), "INFRASTRUCTURE_FAILURE")
    print(json.dumps(result, sort_keys=True))
    return result["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
