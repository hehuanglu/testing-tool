"""Regressions for restricted admission and fail-closed evidence validation."""

from copy import deepcopy
from pathlib import Path
from subprocess import CompletedProcess
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from security_framework.engine import execute_plan, validate_plan
from security_framework.evidence import (add_check, fail_run, finish, outcome, put_evidence,
                                         start, validate_child)
from security_framework.manifest import read_suite
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

    def test_wrong_identity_takes_precedence_over_a_missing_actor(self):
        profile = self.suite.profiles["fixture-form"]
        result = start(self.suite, "run")
        reason = identity(result, "identity", profile, {"editor": {"actor": "unknown-secret", "status": 200}})
        self.assertEqual(reason, "AUTHENTICATION_FAILURE")
        self.assertEqual(result["evidence"]["identity"]["data"]["editor"]["actor"], "unrecognized")

    def test_missing_container_evidence_and_infrastructure_error(self):
        for process, expected in ((CompletedProcess([], 0, b"", b""), "MISSING_EVIDENCE"),
                                  (CompletedProcess([], 0, b"{}", b""), "INVALID_EVIDENCE"),
                                  (CompletedProcess([], 125, b"", b""), "INFRASTRUCTURE_FAILURE")):
            with self.subTest(expected=expected), patch("security_framework.run.subprocess.run", return_value=process):
                result = run_container(self.suite, "run", "image")
                self.assertEqual((result["verdict"], result["exitCode"]), ("ERROR", 2))
                self.assertEqual(set(result["decisiveChecks"].values()), {expected})

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
