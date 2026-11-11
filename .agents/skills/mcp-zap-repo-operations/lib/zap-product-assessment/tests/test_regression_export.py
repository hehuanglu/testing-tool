import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from zap_assessment.regression_export import ExportError, build_case, canonical_bytes, generate


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "regression"


class RegressionExportTests(unittest.TestCase):
    def load(self, name):
        return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))

    def test_synthetic_export_is_deterministic_and_noop(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "cases"
            first = generate(EXAMPLES / "csp-reviewed-input.json", out)
            self.assertEqual(first[0], "CREATED")
            payload = first[1].read_bytes()
            second = generate(EXAMPLES / "csp-reviewed-input.json", out)
            self.assertEqual(second[0], "UNCHANGED")
            self.assertEqual(payload, second[1].read_bytes())
            case = json.loads(payload)
            self.assertNotIn("observed", case)
            self.assertNotIn("timestamp", payload.decode())
            self.assertEqual(hashlib.sha256(payload).hexdigest(), hashlib.sha256(second[2]).hexdigest())

    def test_product_qualification_export_pins_target_without_run(self):
        case = build_case(self.load("byteme-csp-qualification-input.json"))
        self.assertEqual(case["source"]["kind"], "product-qualification")
        self.assertEqual(case["fixture"], "byteme-v1")
        self.assertEqual(case["target"]["commitSha"],
                         "510f6415b6af535ceec77213f0b0c7d5082123f7")
        self.assertEqual({row["origin"] for row in case["requests"]},
                         {"product", "detector-control"})

    def test_product_qualification_source_must_match_target(self):
        value = self.load("byteme-csp-qualification-input.json")
        value["ci"]["target"]["commitSha"] = "0" * 40
        with self.assertRaises(ExportError) as raised:
            build_case(value)
        self.assertEqual(raised.exception.field, "source")

    def test_existing_changed_file_requires_review_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "cases"
            _, target, _ = generate(EXAMPLES / "csp-reviewed-input.json", out)
            target.write_text('{"reviewer":"changed"}\n', encoding="utf-8")
            before = hashlib.sha256(target.read_bytes()).hexdigest()
            status, _, candidate = generate(EXAMPLES / "csp-reviewed-input.json", out)
            self.assertEqual(status, "REVIEW_REQUIRED")
            self.assertEqual(before, hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(json.loads(candidate)["id"], "csp-docs")

    def test_missing_prerequisites_and_unsupported_operation_are_specific(self):
        base = self.load("csp-reviewed-input.json")
        cases = []
        missing = copy.deepcopy(base); missing["ci"].pop("fixture")
        cases.append((missing, "INVALID_INPUT", "input/ci"))
        missing = copy.deepcopy(base); missing["ci"]["expect"]["basis"] = ""
        cases.append((missing, "INVALID_INPUT", "input/ci/expect/basis"))
        unsupported = copy.deepcopy(base); unsupported["ci"]["requests"][0]["method"] = "POST"
        cases.append((unsupported, "UNSUPPORTED_OPERATION", "case/requests/0/method"))
        bad_route = copy.deepcopy(base); bad_route["ci"]["requests"][0]["path"] = "/docs?private=yes"
        cases.append((bad_route, "INVALID_INPUT", "case/requests/0/path"))
        for value, code, field in cases:
            with self.subTest(code=code, field=field):
                with self.assertRaises(ExportError) as raised:
                    build_case(value)
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(raised.exception.field, field)

    def test_v3_run_exact_links_export_and_stale_variants_reject(self):
        mapping = self.load("csp-run-mapping.json")
        run = self.load("csp-run-v3-synthetic.json")
        case = build_case(mapping, run, "csp-docs")
        self.assertEqual(case["source"]["kind"], "assessment-run-v3")
        self.assertEqual(case["source"]["planRevision"], "P-SYNTHETIC-1")
        self.assertEqual(len(case["source"]["evidence"]), 1)
        mutations = []
        changed = copy.deepcopy(run); changed["criteriaWorkflow"]["planRevision"] = "stale"
        mutations.append(changed)
        changed = copy.deepcopy(run)
        changed["criteriaWorkflow"]["caseResults"][0]["evidenceLinks"][0]["operationId"] = "missing"
        mutations.append(changed)
        changed = copy.deepcopy(run)
        changed["criteriaWorkflow"]["caseResults"][0]["evidenceLinks"][0]["resultPath"] = "/missing"
        mutations.append(changed)
        changed = copy.deepcopy(run); changed["operations"][0]["coverageContext"]["build"] = "other"
        mutations.append(changed)
        changed = copy.deepcopy(run)
        changed["criteriaWorkflow"]["caseResults"][0]["evidenceLinks"][0]["role"] = "context"
        mutations.append(changed)
        for index, changed in enumerate(mutations):
            with self.subTest(index=index), self.assertRaises(ExportError):
                build_case(mapping, changed, "csp-docs")

    def test_real_cli_candidate_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary) / "cases"
            env = dict(os.environ, PYTHONPATH=str(ROOT / "src"))
            command = [sys.executable, "-m", "zap_assessment.cli", "regression", "generate",
                       "--input", str(EXAMPLES / "csp-reviewed-input.json"), "--out-dir", str(out)]
            created = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(created.returncode, 0, created.stderr)
            self.assertEqual(json.loads(created.stdout)["status"], "CREATED")
            target = out / "csp-docs.json"
            target.write_text('{"changed":true}\n', encoding="utf-8")
            before = target.read_bytes()
            review = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(review.returncode, 2)
            self.assertEqual(json.loads(review.stdout)["id"], "csp-docs")
            self.assertEqual(json.loads(review.stderr)["status"], "REVIEW_REQUIRED")
            self.assertEqual(target.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
