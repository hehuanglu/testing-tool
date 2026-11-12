import unittest

from anti_framing import evaluate_anti_framing


class AntiFramingOracleTests(unittest.TestCase):
    def evaluate(self, **headers):
        return evaluate_anti_framing({key.replace("_", "-"): value
                                      for key, value in headers.items()})

    def test_xfo_deny_and_sameorigin_protect_without_frame_ancestors(self):
        for value in ("DENY", "sameorigin"):
            with self.subTest(value=value):
                result = self.evaluate(x_frame_options=[value])
                self.assertEqual(result["state"], "protected")
                self.assertFalse(result["browserEnforcementTested"])

        result = self.evaluate(content_security_policy=["default-src 'none'"],
                               x_frame_options=["DENY"])
        self.assertEqual(result["state"], "protected")

    def test_enforcing_frame_ancestors_none_protects(self):
        self.assertEqual(self.evaluate(
            content_security_policy=["frame-ancestors 'none'"])["state"], "protected")

    def test_http_self_requires_origin_match_evaluation(self):
        self.assertEqual(self.evaluate(
            content_security_policy=["default-src *; frame-ancestors 'self'"])["state"],
            "indeterminate")

    def test_report_only_default_src_and_frame_src_do_not_protect(self):
        cases = [
            {"content_security_policy_report_only": ["frame-ancestors 'none'"]},
            {"content_security_policy": ["default-src 'none'"]},
            {"content_security_policy": ["frame-src 'none'"]},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.evaluate(**headers)["state"], "unprotected")

    def test_enforcing_csp_precedes_xfo(self):
        result = self.evaluate(content_security_policy=["frame-ancestors *"],
                               x_frame_options=["DENY"])
        self.assertEqual(result["state"], "unprotected")
        self.assertEqual(result["mechanism"], "csp-frame-ancestors")

    def test_malformed_or_conflicting_values_never_pass(self):
        cases = [
            {"content_security_policy": ["frame-ancestors 'self' https://"]},
            {"content_security_policy": ["frame-ancestors 'none' 'self'"]},
            {"x_frame_options": ["DENY", "SAMEORIGIN"]},
            {"x_frame_options": ["ALLOW-FROM https://example.test"]},
            {"content_security_policy": ["frame-ancestors https://a.example",
                                           "frame-ancestors https://b.example"]},
        ]
        for headers in cases:
            with self.subTest(headers=headers):
                self.assertEqual(self.evaluate(**headers)["state"], "indeterminate")


if __name__ == "__main__":
    unittest.main()
