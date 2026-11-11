import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from run_zap_suite import (CaseError, classify, discover_cases, main, suite_result,
                           validate_case)
from zap_report import parse_report


ROOT = Path(__file__).resolve().parent


def stable_case():
    return json.loads((ROOT / "cases" / "csp-docs.json").read_text(encoding="utf-8"))


def parsed(paths):
    return parse_report({"site": [{"@name": "http://127.0.0.1:8080", "alerts": [{
        "alertRef": "10038-1",
        "count": str(len(paths)),
        "instances": [{"uri": "http://127.0.0.1:8080" + path, "method": "GET"}
                      for path in paths],
    }]}]})


def responses(case, *, csp=True):
    rows = []
    for request in case["requests"]:
        rows.append({"requestId": request["id"], "method": request["method"],
                     "path": request["path"], "status": 200, "mediaType": "text/html",
                     "cspNonEmpty": csp if request["id"] == "docs" else False})
    return rows


class FakeFixture:
    def __init__(self, case, *, cleanup_error=False):
        self.case = case
        self.origin = "http://127.0.0.1:8080"
        self.cleanup_error = cleanup_error
        self.stopped = False

    def start(self):
        return self

    def evidence(self):
        return responses(self.case)

    def stop(self):
        self.stopped = True
        if self.cleanup_error:
            raise RuntimeError("injected cleanup failure")


class SuiteTests(unittest.TestCase):
    def test_stable_case_and_runtime_validator_parity_corpus(self):
        case = stable_case()
        self.assertIs(validate_case(case, "csp-docs.json"), case)
        invalid = []
        changed = copy.deepcopy(case); changed["extra"] = True; invalid.append(changed)
        changed = copy.deepcopy(case); changed["requests"][0]["path"] = "/docs?q=1"; invalid.append(changed)
        changed = copy.deepcopy(case); changed["requests"][0]["method"] = "POST"; invalid.append(changed)
        changed = copy.deepcopy(case); changed["requests"][1]["id"] = "docs"; invalid.append(changed)
        changed = copy.deepcopy(case); changed["expect"]["presentOn"] = "missing"; invalid.append(changed)
        for value in invalid:
            with self.subTest(value=value), self.assertRaises(CaseError):
                validate_case(value, "csp-docs.json")

    def test_classification_order(self):
        case = stable_case()
        origin = "http://127.0.0.1:8080"
        self.assertEqual(classify(case, origin, responses(case), parsed(["/control"])),
                         ("PASS", "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER"))
        self.assertEqual(classify(case, origin, responses(case, csp=False), parsed(["/control", "/docs"])),
                         ("REGRESSION", "PROTECTED_ALERT_PRESENT"))
        self.assertEqual(classify(case, origin, responses(case)[:1], parsed([])),
                         ("MISSING_EVIDENCE", "REQUIRED_RESPONSE_MISSING"))
        self.assertEqual(classify(case, origin, responses(case), parsed([])),
                         ("MISSING_EVIDENCE", "CONTROL_ALERT_MISSING"))
        self.assertEqual(classify(case, origin, responses(case, csp=False), parsed(["/control"])),
                         ("MISSING_EVIDENCE", "INCONSISTENT_OBSERVATION"))

    def test_add_delete_empty_duplicate_and_symlink_fail_closed(self):
        case = stable_case()
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertEqual(discover_cases(root), [])
            (root / "csp-docs.json").write_text(json.dumps(case), encoding="utf-8")
            second = copy.deepcopy(case); second["id"] = "csp-docs-two"
            second["source"]["caseId"] = "csp-docs-two"
            (root / "csp-docs-two.json").write_text(json.dumps(second), encoding="utf-8")
            self.assertEqual(len(discover_cases(root)), 2)
            (root / "csp-docs-two.json").unlink()
            self.assertEqual(len(discover_cases(root)), 1)
            duplicate = copy.deepcopy(case)
            (root / "other.json").write_text(json.dumps(duplicate), encoding="utf-8")
            with self.assertRaisesRegex(CaseError, "duplicate case ID"):
                discover_cases(root)
            (root / "other.json").unlink()
            outside = root.parent / "outside-case.json"
            outside.write_text(json.dumps(case), encoding="utf-8")
            (root / "linked.json").symlink_to(outside)
            with self.assertRaises(CaseError):
                discover_cases(root)

    def test_runtime_failure_does_not_suppress_later_case_result(self):
        first = stable_case()
        second = copy.deepcopy(first); second["id"] = "csp-docs-two"
        second["source"]["caseId"] = "csp-docs-two"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); cases = root / "cases"; cases.mkdir(); out = root / "out"
            (cases / "csp-docs.json").write_text(json.dumps(first), encoding="utf-8")
            (cases / "csp-docs-two.json").write_text(json.dumps(second), encoding="utf-8")
            rows = [
                {"id": "csp-docs", "caseHash": "a" * 64,
                 "status": "EXECUTION_ERROR", "reason": "fixture"},
                {"id": "csp-docs-two", "caseHash": "b" * 64,
                 "status": "PASS", "reason": "fixture"},
            ]
            with patch("run_zap_suite.execute_case", side_effect=rows) as execute:
                self.assertEqual(main(["--cases", str(cases), "--out", str(out)]), 1)
            self.assertEqual(execute.call_count, 2)
            result = json.loads((out / "suite-results.json").read_text())
            self.assertEqual([row["id"] for row in result["cases"]],
                             ["csp-docs", "csp-docs-two"])
            self.assertEqual(result["counts"]["EXECUTION_ERROR"], 1)
            self.assertEqual(result["counts"]["PASS"], 1)

    def test_fixture_initialization_failure_is_recorded_and_later_case_runs(self):
        first = stable_case()
        second = copy.deepcopy(first); second["id"] = "z-csp-docs"
        second["source"]["caseId"] = "z-csp-docs"
        calls = []

        def fixture_factory(case, _run_id, _mode):
            calls.append(case["id"])
            if len(calls) == 1:
                raise OSError("injected bind failure")
            return FakeFixture(case)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); cases = root / "cases"; cases.mkdir(); out = root / "out"
            (cases / "csp-docs.json").write_text(json.dumps(first), encoding="utf-8")
            (cases / "z-csp-docs.json").write_text(json.dumps(second), encoding="utf-8")
            with (patch.dict("run_zap_suite.FIXTURES", {"csp-demo": fixture_factory}, clear=True),
                  patch("run_zap_suite.run_process", return_value=(0, False, 0)),
                  patch("run_zap_suite.load_fresh_report",
                        return_value=({}, parsed(["/control"])))):
                self.assertEqual(main(["--cases", str(cases), "--out", str(out)]), 1)
            result = json.loads((out / "suite-results.json").read_text())
            self.assertEqual(calls, ["csp-docs", "z-csp-docs"])
            self.assertEqual([(row["status"], row["reason"]) for row in result["cases"]], [
                ("EXECUTION_ERROR", "FIXTURE_SETUP_ERROR:OSError"),
                ("PASS", "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER"),
            ])
            self.assertTrue((out / "csp-docs" / "evidence.json").is_file())
            self.assertTrue((out / "csp-docs" / "plan.yaml").is_file())
            self.assertTrue((out / "csp-docs" / "zap.log").is_file())

    def test_fixture_cleanup_failure_is_recorded_and_later_case_runs(self):
        first = stable_case()
        second = copy.deepcopy(first); second["id"] = "z-csp-docs"
        second["source"]["caseId"] = "z-csp-docs"
        fixtures = []

        def fixture_factory(case, _run_id, _mode):
            fixture = FakeFixture(case, cleanup_error=not fixtures)
            fixtures.append(fixture)
            return fixture

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); cases = root / "cases"; cases.mkdir(); out = root / "out"
            (cases / "csp-docs.json").write_text(json.dumps(first), encoding="utf-8")
            (cases / "z-csp-docs.json").write_text(json.dumps(second), encoding="utf-8")
            with (patch.dict("run_zap_suite.FIXTURES", {"csp-demo": fixture_factory}, clear=True),
                  patch("run_zap_suite.run_process", return_value=(0, False, 0)),
                  patch("run_zap_suite.load_fresh_report",
                        return_value=({}, parsed(["/control"])))):
                self.assertEqual(main(["--cases", str(cases), "--out", str(out)]), 1)
            result = json.loads((out / "suite-results.json").read_text())
            self.assertEqual([(row["status"], row["reason"]) for row in result["cases"]], [
                ("EXECUTION_ERROR", "FIXTURE_CLEANUP_ERROR:RuntimeError"),
                ("PASS", "CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER"),
            ])
            self.assertTrue(all(fixture.stopped for fixture in fixtures))

    def test_suite_metadata_separates_tested_commit_from_pr_head(self):
        with patch.dict("run_zap_suite.os.environ", {
                "TESTED_COMMIT_SHA": "merge-commit",
                "PULL_REQUEST_HEAD_SHA": "pr-head",
                "ZAP_IMAGE_DIGEST": "sha256:image",
        }, clear=True):
            result = suite_result("run", [])
        self.assertEqual(result["testedCommitSha"], "merge-commit")
        self.assertEqual(result["pullRequestHeadSha"], "pr-head")
        self.assertNotIn("commitSha", result)


if __name__ == "__main__":
    unittest.main()
