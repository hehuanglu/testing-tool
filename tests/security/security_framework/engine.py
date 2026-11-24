"""Standalone Automation Framework runner adapted from the qualified feasibility lane."""

import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time
from urllib.parse import urlsplit

from zap_report import ReportError, load_fresh_report

from .evidence import put_evidence
from .manifest import digest, require

VERSION = "2.17.0"
JOBS = {"requestor", "passiveScan-wait", "report"}
UPDATES = ("autoupdate.checkOnStart", "autoupdate.checkAddonUpdates", "autoupdate.downloadNewRelease",
           "autoupdate.installAddonUpdates", "autoupdate.installScannerRules",
           "autoupdate.start.checkOnStart", "autoupdate.start.checkAddonUpdates",
           "autoupdate.start.downloadNewRelease", "autoupdate.start.installAddonUpdates",
           "autoupdate.start.installScannerRules")
TRANSITION = re.compile(r"^Job (\S+) (started|finished)(?:, time taken: [^\n]+)?$", re.M)


def validate_loopback(origin):
    address = urlsplit(origin)
    require(address.scheme == "http" and address.hostname == "127.0.0.1" and address.port
            and origin == f"http://127.0.0.1:{address.port}", "fixture origin")


def validate_plan(plan, origin, directory):
    """Admit the tested job subset and bind every request to the owned fixture."""
    validate_loopback(origin)

    def local(url):
        actual = urlsplit(url)
        require(f"{actual.scheme}://{actual.netloc}" == origin and not actual.query
                and not actual.fragment and not re.search(r"[\s\\]", url), "plan destination")

    require(set(plan) == {"env", "jobs"}, "plan root")
    env = plan["env"]
    require(set(env) == {"contexts", "parameters"} and env["parameters"] == {
        "failOnError": True, "failOnWarning": False,
    }, "plan environment")
    require(isinstance(env["contexts"], list) and env["contexts"], "plan contexts")

    for context in env["contexts"]:
        require(set(context) <= {"name", "urls", "includePaths", "excludePaths", "authentication",
                                 "sessionManagement", "users"}, "plan context")
        require(isinstance(context["urls"], list) and context["urls"], "plan context URLs")
        for url in context["urls"]:
            local(url)
        auth = context.get("authentication")
        if auth:
            require(set(auth) == {"method", "parameters", "verification"}
                    and auth["method"] == "form", "plan authentication")
            params = auth["parameters"]
            require(set(params) <= {"loginPageUrl", "loginRequestUrl", "loginRequestBody"}
                    and "loginRequestBody" in params, "plan form parameters")
            local(params["loginRequestUrl"])
            if "loginPageUrl" in params:
                local(params["loginPageUrl"])
            require(set(auth["verification"]) == {"method", "loggedInRegex", "loggedOutRegex"}
                    and auth["verification"]["method"] == "response", "plan auth verification")
            require(context.get("sessionManagement") == {"method": "cookie", "parameters": {}},
                    "plan session")
        else:
            require("users" not in context and "sessionManagement" not in context,
                    "plan anonymous context")

    jobs = plan["jobs"]
    require(isinstance(jobs, list) and len(jobs) >= 3, "plan job sequence")
    types = [job["type"] for job in jobs]
    require(set(types) <= JOBS and types[:-2] == ["requestor"] * (len(jobs) - 2)
            and types[-2:] == ["passiveScan-wait", "report"], "passive plan job sequence")
    for job in jobs[:-2]:
        require(set(job) <= {"type", "name", "parameters", "requests"}
                and set(job.get("parameters", {})) <= {"user"} and job["requests"], "requestor job")
        for request in job["requests"]:
            require(set(request) <= {"name", "url", "method", "responseCode"}
                    and request.get("method", "GET") == "GET", "literal GET request")
            require(type(request.get("responseCode")) is int
                    and 100 <= request["responseCode"] <= 599, "expected HTTP status")
            local(request["url"])
    require(set(jobs[-2]) <= {"type", "name", "parameters"}
            and jobs[-2].get("parameters") == {"maxDuration": 0}, "passive drain")
    require(set(jobs[-1]) <= {"type", "name", "parameters"} and jobs[-1]["parameters"] == {
        "template": "traditional-json", "reportDir": str(directory), "reportFile": "zap-report",
    }, "native report")
    return types


def run_zap(directory, flag, plan):
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
            process.wait(timeout=90)
        except subprocess.TimeoutExpired:
            timeout = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait(timeout=5)
    return {"exit": process.returncode, "timedOut": timeout}, log.read_text(errors="replace")


def execute_plan(result, directory, origin, definition, observe, identity_check=None, after_report=None):
    """Return an error reason, or None when scanner and native report are usable."""
    try:
        types = validate_plan(definition, origin, directory)
    except (KeyError, TypeError, ValueError, AttributeError):
        return "PLAN_VALIDATION_FAILURE"

    plan = directory / "plan.json"
    plan.write_text(json.dumps(definition, allow_nan=False), encoding="utf-8")
    native = {"planSha256": digest(plan)}
    put_evidence(result, "scannerExecution", "automation-framework", native)
    preflight, _ = run_zap(directory, "-autocheck", plan)
    native["preflight"] = preflight
    native["preflightRequests"] = len(observe())
    if preflight["timedOut"]:
        return "INCOMPLETE_EXECUTION"
    if preflight["exit"] or native["preflightRequests"]:
        return "PLAN_VALIDATION_FAILURE"

    started = time.time_ns()
    execution, console = run_zap(directory, "-autorun", plan)
    receipts = TRANSITION.findall(console)
    native.update(execution=execution, jobReceipts=[list(receipt) for receipt in receipts],
                  expectedJobTypes=types, planReportedSuccessful="Automation plan succeeded" in console)
    events = observe()
    if events:
        put_evidence(result, "scannerEvents", "fixture", events)
    if execution["timedOut"]:
        return "INCOMPLETE_EXECUTION"
    if execution["exit"] not in (0, 2):
        return "SCANNER_FAILURE"
    identity_reason = identity_check(events) if identity_check else None
    if identity_reason == "AUTHENTICATION_FAILURE":
        return identity_reason
    if execution["exit"] == 2:
        return "SCANNER_WARNING"
    if identity_reason:
        return identity_reason
    if (not native["planReportedSuccessful"] or receipts !=
            [(job, state) for job in types for state in ("started", "finished")]):
        return "INCOMPLETE_EXECUTION"

    report_path = Path(directory) / "zap-report.json"
    if after_report:
        after_report(report_path)
    if not report_path.is_file():
        return "MISSING_EVIDENCE"
    try:
        raw, report = load_fresh_report(report_path, started)
        if (report.capped or report.version != VERSION or
                {site["@name"] for site in raw["site"]} != {origin}):
            raise ReportError("unqualified report")
        report_hash = digest(report_path)
    except (ReportError, KeyError, OSError, ValueError, TypeError):
        return "INVALID_EVIDENCE"

    rows = [{"path": row.path, "method": row.method, "alertRef": row.alert_ref, "pointer": row.pointer}
            for row in report.instances if row.origin == origin and row.method == "GET" and "?" not in row.path]
    put_evidence(result, "zapReport", "zap-report",
                 {"sha256": report_hash, "version": report.version, "capped": report.capped,
                  "ruleInstances": rows})
    return None
