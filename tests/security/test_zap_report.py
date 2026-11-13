import json
import tempfile
import unittest
from pathlib import Path

from zap_report import ReportError, matching_instances, parse_report


def report(instances, *, alert_ref="10038-1", count=None):
    alert = {"alertRef": alert_ref, "instances": instances}
    if count is not None:
        alert["count"] = str(count)
    return {"@version": "2.17.0", "site": [{"@name": "http://127.0.0.1:8080", "alerts": [alert]}]}


class ReportTests(unittest.TestCase):
    def test_two_instances_preserve_pointer_and_optional_native_id(self):
        parsed = parse_report(report([
            {"uri": "http://127.0.0.1:8080/control", "method": "GET", "id": "native-1"},
            {"uri": "http://127.0.0.1:8080/docs", "method": "GET"},
        ]))
        self.assertEqual(len(parsed.instances), 2)
        self.assertEqual(parsed.instances[0].pointer, "/site/0/alerts/0/instances/0")
        self.assertEqual(parsed.instances[0].native_id, "native-1")
        self.assertIsNone(parsed.instances[1].native_id)
        self.assertFalse(parsed.capped)

    def test_match_is_exact_on_origin_method_path_query_and_alert_ref(self):
        parsed = parse_report(report([
            {"uri": "http://127.0.0.1:8080/docs", "method": "GET"},
        ]))
        good = dict(origin="http://127.0.0.1:8080", method="GET", path="/docs",
                    alert_ref="10038-1")
        self.assertEqual(len(matching_instances(parsed, **good)), 1)
        variants = [
            dict(good, origin="http://127.0.0.1:8081"),
            dict(good, method="POST"),
            dict(good, path="/docs?q=1"),
            dict(good, alert_ref="10038"),
        ]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(matching_instances(parsed, **variant), [])

    def test_missing_structures_and_bad_instances_fail_closed(self):
        bad = [
            {},
            {"site": {}},
            {"site": [{"@name": "http://x", "alerts": {}}]},
            {"site": [{"@name": "http://x", "alerts": [{"alertRef": "10038-1"}]}]},
            report([{"uri": "/relative", "method": "GET"}]),
            report([{"uri": "http://127.0.0.1:8080/docs"}]),
        ]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ReportError):
                parse_report(value)

    def test_count_larger_than_instances_marks_report_capped(self):
        parsed = parse_report(report([
            {"uri": "http://127.0.0.1:8080/docs", "method": "GET"}
        ], count=2))
        self.assertTrue(parsed.capped)


if __name__ == "__main__":
    unittest.main()
