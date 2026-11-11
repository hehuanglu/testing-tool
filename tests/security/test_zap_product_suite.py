import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("run_zap_product_suite",
                                              ROOT / "run_zap_product_suite.py")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ProductSuiteTests(unittest.TestCase):
    def setUp(self):
        self.case = json.loads((ROOT / "product-cases/byteme-swagger-csp.json").read_text())

    def test_committed_case_matches_registry(self):
        MODULE.validate_case(self.case, "byteme-swagger-csp.json")
        registry = json.loads((ROOT / "product_adapters.json").read_text())["adapters"]["byteme-v1"]
        self.assertEqual(self.case["target"]["commitSha"], registry["commitSha"])
        self.assertEqual(self.case["target"]["repository"], registry["repository"])

    def test_add_delete_discovery_needs_no_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            first = copy.deepcopy(self.case)
            second = copy.deepcopy(self.case)
            second["id"] = "byteme-swagger-csp-copy"
            second["source"]["caseId"] = second["id"]
            (folder / (first["id"] + ".json")).write_text(json.dumps(first))
            (folder / (second["id"] + ".json")).write_text(json.dumps(second))
            self.assertEqual(len(MODULE.discover_cases(folder)), 2)
            (folder / (second["id"] + ".json")).unlink()
            self.assertEqual(len(MODULE.discover_cases(folder)), 1)
            (folder / (first["id"] + ".json")).unlink()
            self.assertEqual(MODULE.discover_cases(folder), [])

    def test_product_and_detector_origins_are_both_required(self):
        changed = copy.deepcopy(self.case)
        changed["requests"][1]["origin"] = "product"
        with self.assertRaises(MODULE.AdapterError):
            MODULE.validate_case(changed, changed["id"] + ".json")

    def test_unpinned_or_dirty_contract_is_rejected_before_runtime(self):
        changed = copy.deepcopy(self.case)
        changed["target"]["commitSha"] = "short"
        with self.assertRaises(MODULE.AdapterError):
            MODULE.validate_case(changed, changed["id"] + ".json")

    def test_repository_binding_accepts_only_optional_dot_git_suffix(self):
        canonical = MODULE.canonical_repository_url
        self.assertEqual(canonical("https://github.com/hehuanglu/ByteMe.git"),
                         canonical("https://github.com/hehuanglu/ByteMe/"))
        self.assertNotEqual(canonical("https://github.com/hehuanglu/ByteMe.git"),
                            canonical("https://github.com/another/ByteMe.git"))


if __name__ == "__main__":
    unittest.main()
