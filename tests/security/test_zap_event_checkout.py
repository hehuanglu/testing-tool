import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import run_zap_product_suite as runner
from product.byteme.zap_product_runtime import classify


SECURITY = Path(__file__).resolve().parent
REVIEWED = SECURITY / "product-assessment-cases/byteme-swagger-anti-framing.json"


class EventCheckoutTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.product = self.root / "product"
        self.product.mkdir()
        self.git("init", "-q")
        self.git("remote", "add", "origin", "https://github.com/hehuanglu/ByteMe")
        self.cases = self.root / "cases"
        self.cases.mkdir()
        original = REVIEWED.read_bytes()
        self.case = json.loads(original)
        reviewed = self.case["target"]["commitSha"]
        self.case.update(schemaVersion=2, fixture="byteme-ci-v1", target={
            "adapter": "byteme-ci-v1", "repository": "https://github.com/hehuanglu/ByteMe.git",
            "revisionPolicy": "event-checkout",
        }, provenance={"reviewedProductCommitSha": reviewed,
                       "parentCaseSha256": hashlib.sha256(original).hexdigest()})
        self.case["expect"]["basis"] = "Reviewed Swagger framing policy."
        self.path = self.cases / (self.case["id"] + ".json")
        self.path.write_text(json.dumps(self.case))
        for filename in self.adapter("0" * 40).registry["requiredFiles"]:
            path = self.product / filename
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture\n")
        self.git("add", ".")
        self.commit("initial fixture")
        self.sha = self.git("rev-parse", "HEAD")

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.product), *args],
                                       text=True, stderr=subprocess.PIPE).strip()

    def commit(self, message):
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", message, "--allow-empty")

    def adapter(self, sha, variant="upstream-original", fault="none", omit=None, retain=False):
        return runner.ByteMeAdapter(
            self.case, self.root / "case-output", self.product, variant, fault, omit, 90,
            "0" * 32 + "-" + "0" * 8, retain, sha, {"runnerCommitSha": "f" * 40})

    def test_two_commits_are_independently_admitted_and_keep_historical_provenance(self):
        self.assertEqual(self.adapter(self.sha).verify_bindings(), self.sha)
        self.commit("second fixture")
        second = self.git("rev-parse", "HEAD")
        self.assertNotEqual(self.sha, second)
        self.assertEqual(self.adapter(second).verify_bindings(), second)
        self.assertNotEqual(self.case["provenance"]["reviewedProductCommitSha"], second)
        self.assertIn(runner.ADAPTER_LABEL + "=byteme-ci-v1", self.adapter(second).label_args())
        with self.assertRaisesRegex(runner.AdapterError, "expected commit"):
            self.adapter(self.sha).verify_bindings()

    def test_binding_failures_happen_before_effects(self):
        adapter = self.adapter("f" * 40)
        with patch.object(adapter, "prepare_source") as prepare, \
                patch.object(adapter, "create_network") as network, \
                patch.object(adapter, "cleanup_all") as cleanup:
            result = adapter.execute()
        self.assertEqual(result["reason"], "SOURCE_SHA_MISMATCH")
        for method in (prepare, network, cleanup):
            method.assert_not_called()
        (self.product / "dirty").touch()
        with self.assertRaises(runner.AdapterError) as error:
            self.adapter(self.sha).verify_bindings()
        self.assertEqual(error.exception.code, "SOURCE_DIRTY")
        (self.product / "dirty").unlink()
        self.git("remote", "set-url", "origin", "https://github.com/other/ByteMe.git")
        with self.assertRaises(runner.AdapterError) as error:
            self.adapter(self.sha).verify_bindings()
        self.assertEqual(error.exception.code, "SOURCE_REPOSITORY_MISMATCH")
        self.git("remote", "set-url", "origin", "https://github.com/hehuanglu/ByteMe.git")
        self.git("rm", "-q", "Dockerfile")
        self.commit("remove fixture file")
        with self.assertRaises(runner.AdapterError) as error:
            self.adapter(self.git("rev-parse", "HEAD")).verify_bindings()
        self.assertEqual(error.exception.code, "UNSUPPORTED_LAYOUT")

    def test_forbids_qualification_controls(self):
        for args in (("fixed-control",), ("upstream-original", "wrong-status"),
                     ("upstream-original", "none", "swagger-index"),
                     ("upstream-original", "none", None, True)):
            with self.subTest(args=args), self.assertRaises(runner.AdapterError) as error:
                self.adapter(self.sha, *args).verify_bindings()
            self.assertEqual(error.exception.code, "CONTROL_NOT_ALLOWED")

    def run_suite(self, out, expected=None):
        env = dict(os.environ)
        for key in ("GITHUB_SHA", "EXPECTED_RUNNER_SHA", "EXPECTED_PRODUCT_SHA",
                    "REGRESSION_TESTED_COMMIT_SHA"):
            env.pop(key, None)
        command = [sys.executable, "-B", str(SECURITY / "run_zap_product_suite.py"),
                   "--cases", str(self.cases), "--out", str(out), "--require-cases",
                   "--product-source", str(self.product), "--expected-product-sha",
                   expected or self.sha]
        result = subprocess.run(command, env=env, capture_output=True, text=True)
        return result.returncode, json.loads((out / "suite-results.json").read_text())

    def test_empty_invalid_and_conflicting_sha_results(self):
        _, result = self.run_suite(self.root / "binding", "f" * 40)
        self.assertEqual(result["cases"][0]["reason"], "SOURCE_SHA_MISMATCH")
        self.assertEqual(result["testedProductCommitSha"], self.sha)
        self.assertNotEqual(result["runnerCommitSha"], self.sha)
        self.assertNotIn("testedCommitSha", result)
        self.path.write_text("{bad json")
        code, result = self.run_suite(self.root / "invalid")
        self.assertEqual((code, result["status"], result["suiteError"]["code"]),
                         (1, "ERROR", "INVALID_CASE"))
        self.path.unlink()
        self.cases.rmdir()
        code, result = self.run_suite(self.root / "empty")
        self.assertEqual((code, result["status"], result["suiteError"]["code"], result["caseCount"]),
                         (1, "ERROR", "EMPTY_SUITE", 0))

    def test_cleanup_failure_preserves_prior_outcome(self):
        adapter = self.adapter(self.sha)
        with (patch.object(adapter, "prepare_source", return_value={}),
              patch.object(adapter, "create_network"),
              patch.object(adapter, "build_image", return_value={}),
              patch.object(adapter, "resolve_image", return_value={}),
              patch.object(adapter, "start_database"), patch.object(adapter, "start_backend"),
              patch.object(adapter, "run_scanner",
                           return_value={"status": "PASS", "reason": "ANTI_FRAMING_POLICY_PROTECTED"}),
              patch.object(adapter, "cleanup_all", side_effect=RuntimeError)):
            result = adapter.execute()
        self.assertEqual(result["status"], "EXECUTION_ERROR")
        self.assertEqual(result["preCleanupStatus"], "PASS")
        self.assertEqual(result["preCleanupReason"], "ANTI_FRAMING_POLICY_PROTECTED")

    def test_oracle_distinguishes_regression_from_incomplete_response(self):
        url = "http://byteme-backend:8080/swagger-ui/index.html"
        urls = {"swagger-index": url}
        response = {"requestId": "swagger-index", "actualUrl": url, "method": "GET",
                    "status": 200, "mediaType": "text/html", "swaggerUiMarker": True,
                    "policyHeaders": {}}
        self.assertEqual(classify(self.case, [copy.deepcopy(response)], [], urls),
                         ("REGRESSION", "ANTI_FRAMING_POLICY_UNPROTECTED"))
        self.assertEqual(classify(self.case, [{**response, "status": 404}], [], urls),
                         ("MISSING_EVIDENCE", "RESPONSE_STATUS_MISMATCH"))
        self.assertEqual(classify(self.case, [], [], urls),
                         ("MISSING_EVIDENCE", "REQUIRED_RESPONSE_MISSING"))

    def test_timeout_kills_child_process_group(self):
        marker = self.root / "escaped-child"
        child = f"import time; from pathlib import Path; time.sleep(.35); Path({str(marker)!r}).touch()"
        parent = ("import subprocess, sys, time; "
                  "subprocess.Popen([sys.executable, '-c', sys.argv[1]]); time.sleep(5)")
        with self.assertRaises(subprocess.TimeoutExpired):
            runner.command([sys.executable, "-c", parent, child], timeout=.2)
        time.sleep(.4)
        self.assertFalse(marker.exists())
