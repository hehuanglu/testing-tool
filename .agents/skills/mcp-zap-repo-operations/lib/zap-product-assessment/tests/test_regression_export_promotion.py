import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from zap_assessment.regression_export import CATALOG, KNOWN_CATALOG_PREFIX, ExportError, promote


REPO = Path(__file__).resolve().parents[6]
SECURITY = REPO / "tests/security"
INPUT = SECURITY / "product-assessment-cases/byteme-swagger-anti-framing.json"
sys.path.insert(0, str(SECURITY))
from byteme_ci_case import validate_case


class PromotionTests(unittest.TestCase):
    def setUp(self):
        self.temp = self.enterContext(tempfile.TemporaryDirectory())
        self.root = Path(self.temp)
        self.out = self.root / "output"
        self.original = json.loads(INPUT.read_bytes())

    def promote_case(self, case):
        path = self.root / (case["id"] + ".json")
        path.write_text(json.dumps(case), encoding="utf-8")
        return promote(path, self.out, "event-checkout")

    def test_deterministic_preserves_semantics_and_normalizes_catalog_reference(self):
        status, target, payload = promote(INPUT, self.out, "event-checkout")
        self.assertEqual(status, "CREATED")
        self.assertEqual(promote(INPUT, self.out, "event-checkout"), ("UNCHANGED", target, payload))
        migrated = validate_case(json.loads(payload), target.name)
        for key in ("id", "source", "profile", "requests", "requireResponses"):
            self.assertEqual(migrated[key], self.original[key])
        self.assertEqual(migrated["expect"], {
            **self.original["expect"], "basis": self.original["expect"]["basis"].replace(
                KNOWN_CATALOG_PREFIX + CATALOG + "#", CATALOG + "#"),
        })
        self.assertEqual(migrated["provenance"], {
            "parentCaseSha256": hashlib.sha256(INPUT.read_bytes()).hexdigest(),
            "reviewedProductCommitSha": self.original["target"]["commitSha"],
        })
        target.write_bytes(b"review in progress")
        self.assertEqual(promote(INPUT, self.out, "event-checkout"),
                         ("REVIEW_REQUIRED", target, payload))
        self.assertEqual(target.read_bytes(), b"review in progress")

    def test_rejects_synthetic_qualification_and_unsupported_profiles(self):
        for case in (
            json.loads((SECURITY / "cases/csp-docs.json").read_text()),
            json.loads((SECURITY / "product-anti-framing-cases/"
                        "byteme-swagger-anti-framing-qualification.json").read_text()),
            {**self.original, "profile": "unsupported"},
        ):
            with self.subTest(profile=case["profile"], source=case["source"]["kind"]):
                with self.assertRaises(ExportError) as error:
                    self.promote_case(case)
                self.assertEqual(error.exception.code, "UNSUPPORTED_OPERATION")

    def test_rejects_bad_source_or_route_with_schema_runtime_parity(self):
        changes = (
            ("source", "planDigest", "0" * 63),
            ("source", "planRevision", "  "),
            ("source", "criterionIds", ["SEC-A06-06", "SEC-A06-06"]),
            ("source", "evidence", [{"operationId": "op-1", "resultPath": "/bad~2",
                                     "sha256": "0" * 64}]),
            ("target", "repository", "https://github.com/other/ByteMe.git"),
            ("expect", "basis", "Private basis /home/author/review.md"),
            ("requests", "path", "//other"),
            ("requests", "path", "/unsafe/../swagger"),
            ("requests", "path", "/unsafe path"),
            ("requests", "path", "/swagger\n"),
            ("requests", "path", "/foo/.."),
            ("requests", "path", "/./foo"),
            ("requests", "path", "/foo\x00"),
            ("requests", "path", "/foo?bar"),
            ("requests", "origin", "detector-control"),
            ("requireResponses", "status", 404),
        )
        _, target, payload = promote(INPUT, self.root / "reference", "event-checkout")
        v2 = json.loads(payload)
        for section, key, value in changes:
            with self.subTest(section=section, key=key, value=value):
                v1_bad = copy.deepcopy(self.original)
                v2_bad = copy.deepcopy(v2)
                for case in (v1_bad, v2_bad):
                    (case[section][0] if section == "requests" else case[section])[key] = value
                with self.assertRaises(ExportError):
                    self.promote_case(v1_bad)
                with self.assertRaises(ValueError):
                    validate_case(v2_bad, target.name)

    def test_rejects_symlink_input_and_output(self):
        alias = self.root / INPUT.name
        alias.symlink_to(INPUT)
        with self.assertRaises(ExportError):
            promote(alias, self.out, "event-checkout")
        self.out.mkdir()
        (self.out / INPUT.name).symlink_to(INPUT)
        with self.assertRaises(ExportError):
            promote(INPUT, self.out, "event-checkout")


if __name__ == "__main__":
    unittest.main()
