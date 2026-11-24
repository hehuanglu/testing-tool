"""Regressions for restricted admission and fail-closed evidence validation."""

from copy import deepcopy
import json
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from security_framework.engine import execute_plan, validate_plan
from security_framework.evidence import (add_check, fail_run, finish, outcome, put_evidence,
                                         start, validate_child)
from security_framework.execution import APPLICATION, Engine, ExecutionError, run_project
from security_framework.manifest import read_suite
from security_framework.native_jwt import CONTROL, CONTROL_RULE, MODE, NativeJwt
from security_framework.receipt import suite_receipt
from security_framework.run import identity, run_container


class FrameworkTest(TestCase):
    def setUp(self):
        self.suite = read_suite("feasibility_fixture", "application-only")

    def passing_child(self):
        child = start(self.suite, "run")
        for case_id, case in self.suite.cases.items():
            profile = self.suite.profiles[case["authProfile"]]
            identity_key = f"{case_id}-identity"
            put_evidence(child, identity_key, "application-identity",
                         {actor: {"actor": actor, "status": 200} for actor in profile["actors"]})
            for key in case["requiredEvidence"]:
                put_evidence(child, key, "suite-assertion", {"witness": True})
            add_check(child, self.suite, case_id, outcome("PASS", "ASSERTIONS_SATISFIED"),
                      [*case["requiredEvidence"], identity_key])
        return finish(child)

    def test_valid_child_is_bound_to_its_inputs_and_process(self):
        child = self.passing_child()
        self.assertEqual(validate_child(child, self.suite, "run", 0), child)
        for run, code in (("different-run", 0), ("run", 2)):
            with self.assertRaises(ValueError):
                validate_child(child, self.suite, run, code)
        child["inputSha256"] = {}
        with self.assertRaises(ValueError):
            validate_child(child, self.suite, "run", 0)

    def test_missing_case_or_observation_cannot_pass(self):
        full = self.passing_child()
        case_id = next(iter(self.suite.cases))
        for remove in ("check", "evidence", "reference"):
            child = deepcopy(full)
            if remove == "check":
                del child["checks"][case_id]
            elif remove == "evidence":
                del child["evidence"][self.suite.cases[case_id]["requiredEvidence"][0]]
            else:
                child["checks"][case_id]["evidenceRefs"].pop(0)
            with self.subTest(remove=remove), self.assertRaises((KeyError, ValueError)):
                validate_child(child, self.suite, "run", 0)

    def test_unknown_verdict_and_bad_identity_cannot_pass(self):
        baseline = self.passing_child()
        case_id = next(iter(self.suite.cases))
        child = deepcopy(baseline)
        child["checks"][case_id]["verdict"] = "UNKNOWN"
        with self.assertRaises(ValueError):
            validate_child(child, self.suite, "run", 0)
        child = deepcopy(baseline)
        child["evidence"][f"{case_id}-identity"]["data"]["editor"]["actor"] = "reader"
        with self.assertRaises(ValueError):
            validate_child(child, self.suite, "run", 0)

    def test_fixture_failure_after_assertions_cannot_pass(self):
        child = fail_run(self.passing_child(), self.suite, "SUITE_EXECUTION_FAILURE")
        self.assertEqual((child["verdict"], child["exitCode"]), ("ERROR", 2))

    def test_receipt_separates_assertion_failure_from_execution_and_acceptance(self):
        original = self.passing_child()
        key = next(iter(original["checks"]))
        original["checks"][key].update(verdict="FAIL", reason="AUTHORIZATION_ASSERTION_VIOLATED")
        result = suite_receipt(finish(original), self.suite, 1, "a" * 64, {"clean": True})
        self.assertEqual(result["execution"]["status"], "COMPLETED")
        self.assertEqual(result["acceptance"]["status"], "NOT_EVALUATED")
        objective = result["objectives"][original["checks"][key]["objectiveId"]]
        self.assertEqual(objective["checks"][key]["status"], "FAIL")
        self.assertEqual({item["producer"] for item in objective["checks"][key]["witnesses"]},
                         {"application-identity", "suite-assertion"})
        with self.assertRaises(ValueError):
            suite_receipt(original, self.suite, 0, "a" * 64, {"clean": True})

    def test_receipt_preserves_execution_error_classes(self):
        for reason in ("INFRASTRUCTURE_FAILURE", "MISSING_EVIDENCE", "INVALID_EVIDENCE"):
            with self.subTest(reason=reason):
                child = fail_run(start(self.suite, "run"), self.suite, reason)
                receipt = suite_receipt(child, self.suite, 2, "b" * 64, {"clean": True})
                self.assertEqual(receipt["execution"]["classification"], reason)

    def test_wrong_identity_takes_precedence_over_a_missing_actor(self):
        profile = self.suite.profiles["fixture-form"]
        result = start(self.suite, "run")
        reason = identity(result, "identity", profile, {"editor": {"actor": "unknown-secret", "status": 200}})
        self.assertEqual(reason, "AUTHENTICATION_FAILURE")
        self.assertEqual(result["evidence"]["identity"]["data"]["editor"]["actor"], "unrecognized")

    def test_missing_container_evidence_and_infrastructure_error(self):
        for process, expected in ((CompletedProcess([], 0, b"", b""), "MISSING_EVIDENCE"),
                                  (CompletedProcess([], 1, b"", b"worker failed"), "MISSING_EVIDENCE"),
                                  (CompletedProcess([], 0, b"{}", b""), "INVALID_EVIDENCE"),
                                  (CompletedProcess([], 125, b"", b""), "INFRASTRUCTURE_FAILURE")):
            with self.subTest(expected=expected), patch("security_framework.run.subprocess.run", return_value=process):
                result = run_container(self.suite, "run", "image")
                self.assertEqual((result["verdict"], result["exitCode"]), ("ERROR", 2))
                self.assertEqual(set(result["decisiveChecks"].values()), {expected})

    def test_docker_connection_error_with_exit_one_is_an_infrastructure_failure(self):
        for message in (b"failed to connect to the docker API at unix:///private/fixture.sock",
                        b"Cannot connect to the Docker daemon at unix:///private/fixture.sock"):
            process = CompletedProcess([], 1, b"", message)
            with self.subTest(message=message), patch("security_framework.run.subprocess.run", return_value=process):
                result = run_container(self.suite, "run", "image")
                self.assertEqual((result["verdict"], result["exitCode"]), ("ERROR", 2))
                self.assertEqual(set(result["decisiveChecks"].values()), {"INFRASTRUCTURE_FAILURE"})
                self.assertEqual(result["evidence"]["containerExit"]["data"], {"exit": 1})
                self.assertNotIn("/private/fixture.sock", json.dumps(result))

    def test_unqualified_cases_never_dispatch(self):
        for scenario, reason in (("active-blocked", "ACTIVE_EXECUTION_RESTRICTED"),
                                 ("jwt-blocked", "AUTH_PROFILE_UNQUALIFIED")):
            suite = read_suite("feasibility_fixture", scenario)
            with self.subTest(scenario=scenario), patch("security_framework.run.subprocess.run") as process:
                result = run_container(suite, "run", "image")
                self.assertEqual((result["verdict"], result["exitCode"]), ("BLOCKED", 3))
                self.assertEqual(set(result["decisiveChecks"].values()), {reason})
                process.assert_not_called()

    @staticmethod
    def passive_plan(origin, directory):
        return {"env": {"contexts": [{"name": "test", "urls": [origin]}],
                        "parameters": {"failOnError": True, "failOnWarning": False}},
                "jobs": [{"type": "requestor", "requests": [{"url": origin + "/health", "method": "GET",
                                                           "responseCode": 200}]},
                         {"type": "passiveScan-wait", "parameters": {"maxDuration": 0}},
                         {"type": "report", "parameters": {"template": "traditional-json",
                                                           "reportDir": str(directory),
                                                           "reportFile": "zap-report"}}]}

    def test_engine_success_requires_terminal_job_receipts(self):
        origin = "http://127.0.0.1:9876"
        for exit_code, expected in ((0, "INCOMPLETE_EXECUTION"), (1, "SCANNER_FAILURE")):
            with self.subTest(exit_code=exit_code), TemporaryDirectory() as temporary:
                directory = Path(temporary)
                native_exits = [({"exit": 0, "timedOut": False}, ""),
                                ({"exit": exit_code, "timedOut": False}, "Automation plan succeeded")]
                result = start(self.suite, "run")
                with patch("security_framework.engine.run_zap", side_effect=native_exits):
                    reason = execute_plan(result, directory, origin, self.passive_plan(origin, directory),
                                          lambda: [])
                self.assertEqual(reason, expected)
                self.assertNotIn("zapReport", result["evidence"])

    def test_unqualified_jobs_and_destinations_are_refused(self):
        origin = "http://127.0.0.1:9876"
        directory = Path("/private/fixture")
        plan = self.passive_plan(origin, directory)
        self.assertEqual(validate_plan(plan, origin, directory), ["requestor", "passiveScan-wait", "report"])
        for hazard in ("other-origin", "write", "active"):
            mutated = deepcopy(plan)
            if hazard == "active":
                mutated["jobs"].insert(1, {"type": "activeScan"})
            elif hazard == "write":
                mutated["jobs"][0]["requests"][0]["method"] = "POST"
            else:
                mutated["jobs"][0]["requests"][0]["url"] = "http://127.0.0.1:1234/health"
            with self.subTest(hazard=hazard), self.assertRaises(ValueError):
                validate_plan(mutated, origin, directory)



class EngineContractTest(TestCase):
    def test_restriction_precedes_product_startup(self):
        for scenario, reason in (("active-blocked", "ACTIVE_EXECUTION_RESTRICTED"),
                                 ("jwt-blocked", "AUTH_PROFILE_UNQUALIFIED"),
                                 ("anonymous-only", "ENGINE_CAPABILITY_MISMATCH")):
            suite = read_suite("feasibility_fixture", scenario)
            with self.subTest(scenario=scenario), patch.object(self, "prepare", create=True) as prepare:
                with self.assertRaisesRegex(ExecutionError, reason):
                    run_project(suite, Engine("mockmvc", APPLICATION, self.fail), self)
                prepare.assert_not_called()

    def test_teardown_on_adapter_or_engine_failure(self):
        suite = read_suite("feasibility_fixture", "application-only")
        for phase in ("prepare", "execute", "cleanup", "success"):
            events = []

            def close():
                events.append("cleanup")
                if phase == "cleanup":
                    raise ExecutionError("TEARDOWN_FAILURE")

            def prepare(resources):
                resources.callback(close)
                if phase == "prepare":
                    raise ExecutionError("FIXTURE_FAILURE")
                return "ready"

            def execute(fixture):
                self.assertEqual(fixture, "ready")
                if phase == "execute":
                    raise ExecutionError("ENGINE_FAILURE")
                return "observed"

            with self.subTest(phase=phase), patch.object(self, "prepare", create=True, side_effect=prepare):
                engine = Engine("mockmvc", APPLICATION, execute)
                if phase == "success":
                    self.assertEqual(run_project(suite, engine, self), "observed")
                else:
                    with self.assertRaises(ExecutionError):
                        run_project(suite, engine, self)
                self.assertEqual(events, ["cleanup"])


class NativeJwtTest(TestCase):
    def test_admission_is_limited_to_the_rendered_loopback_plan(self):
        directory = Path("/private/fixture")
        origin = "http://127.0.0.1:9876"
        native = NativeJwt("/login", "/me", "email", "password", "token", 7)
        plan = native.plan(origin, directory)
        self.assertEqual(validate_plan(plan, origin, directory, native_jwt=native),
                         ["requestor", "requestor", "passiveScan-wait", "report"])
        with self.assertRaises(ValueError):
            validate_plan(plan, origin, directory)
        for field in ("extra-job", "other-route", "header", "session", "poll-url", "credentials"):
            changed = deepcopy(plan)
            context = changed["env"]["contexts"][0]
            if field == "extra-job":
                changed["jobs"].insert(2, {"type": "activeScan"})
            elif field == "other-route":
                changed["jobs"][1]["requests"][0]["url"] = origin + "/other"
            elif field == "header":
                changed["jobs"][1]["requests"][0]["headers"].append("Authorization: Bearer injected")
            elif field == "session":
                context["sessionManagement"]["parameters"]["Authorization"] = "Bearer external"
            elif field == "poll-url":
                context["authentication"]["verification"]["pollUrl"] = "http://192.0.2.1/me"
            else:
                context["users"][0]["credentials"]["password"] = "inline"
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_plan(changed, origin, directory, native_jwt=native)

    def test_native_jwt_requires_product_fixture_entry_point(self):
        suite = read_suite("bus_booking", "live-authenticated-passive")
        with patch("security_framework.run.subprocess.run") as process:
            result = run_container(suite, "run", "image")
        process.assert_not_called()
        self.assertEqual(result["decisiveChecks"], {"BB-LIVE-JWT-PASSIVE": "PRODUCT_FIXTURE_REQUIRED"})

    def test_missing_or_conflicting_native_evidence_cannot_pass(self):
        suite = read_suite("bus_booking", "live-authenticated-passive")
        case, = suite.cases.values()
        child = start(suite, "run")
        jobs = ["requestor", "requestor", "passiveScan-wait", "report"]
        put_evidence(child, "scannerExecution", "automation-framework", {
            "mode": MODE, "expectedJobTypes": jobs, "preflight": {"exit": 0, "timedOut": False},
            "execution": {"exit": 0, "timedOut": False}, "preflightRequests": 0,
            "jobReceipts": [[job, state] for job in jobs for state in ("started", "finished")],
            "planReportedSuccessful": True, "planSha256": "a" * 64,
        })
        profile = {"status": 200, "bearer": True, "issuedTokenMatches": True,
                   "principalMatches": True, "verified": True, "role": "USER"}
        put_evidence(child, "scannerEvents", "fixture", [
            {"phase": "anonymous", "status": 401, "bearer": False, "challenge": True},
            {"phase": "passive-control", "status": 200}, {"phase": "login-page", "status": 204},
            {"phase": "login", "status": 200}, {"phase": "poll", **profile},
            {"phase": "authenticated", **profile},
        ])
        put_evidence(child, "scannerIdentity-scanner-jwt-user", "application-identity",
                     {"USER": {"actor": "USER", "status": 200}})
        put_evidence(child, "scannerOwnership", "suite-assertion", {"mode": MODE, "applicationClientLogin": False})
        put_evidence(child, "zapReport", "zap-report", {
            "sha256": "b" * 64, "version": "2.17.0", "capped": False,
            "ruleInstances": [{"path": CONTROL, "method": "GET", "alertRef": CONTROL_RULE}],
        })
        put_evidence(child, "runtimeCleanup", "runner", {"containersRemoved": True, "temporaryDirectoryRemoved": True})
        add_check(child, suite, case["id"], outcome("PASS", "NATIVE_JWT_PASSIVE_VERIFIED"), case["requiredEvidence"])
        finish(child)
        self.assertEqual(validate_child(child, suite, "run", 0), child)
        for contradiction in ("mode", "role", "token", "login", "poll", "detector", "cleanup", "external-client"):
            changed = deepcopy(child)
            evidence = changed["evidence"]
            events = evidence["scannerEvents"]["data"]
            if contradiction == "mode":
                del evidence["scannerExecution"]["data"]["mode"]
            elif contradiction == "role":
                events[-1]["role"] = "ADMIN"
            elif contradiction == "token":
                events[-1]["issuedTokenMatches"] = False
            elif contradiction == "login":
                events[3]["status"] = 401
            elif contradiction == "poll":
                del events[4]
            elif contradiction == "detector":
                evidence["zapReport"]["data"]["ruleInstances"].clear()
            elif contradiction == "cleanup":
                evidence["runtimeCleanup"]["data"]["containersRemoved"] = False
            else:
                evidence["scannerOwnership"]["data"]["applicationClientLogin"] = True
            with self.subTest(contradiction=contradiction), self.assertRaises(ValueError):
                validate_child(changed, suite, "run", 0)
