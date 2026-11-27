import json
import unittest
from pathlib import Path
from urllib.request import urlopen

from fixtures.csp_demo import DOCS_MARKER, LOGIN_MARKER, RESPONSE_ID_HEADER, FixtureServer


CASE = json.loads((Path(__file__).parent / "cases/csp-docs.json").read_text())


class CSPFixtureTests(unittest.TestCase):
    def observe(self, mode, *paths):
        fixture = FixtureServer(CASE, mode, mode).start()
        try:
            responses = []
            for path in paths:
                with urlopen(fixture.origin + path, timeout=3) as response:
                    responses.append((response.status, response.headers.get_content_type(),
                                      response.headers.get("Content-Security-Policy"),
                                      response.headers[RESPONSE_ID_HEADER], response.read()))
            return responses, fixture.evidence()
        finally:
            fixture.stop()

    def test_duplicate_sequence_resets_with_new_fixture(self):
        for _ in range(2):
            responses, receipt = self.observe("duplicate-docs", "/docs", "/docs", "/control")
            first, second, _control = responses
            self.assertIn(DOCS_MARKER.encode(), first[4])
            self.assertIsNone(first[2])
            self.assertIn(LOGIN_MARKER.encode(), second[4])
            self.assertTrue(second[2])
            self.assertEqual([row["sequence"] for row in receipt], [1, 2, 3])
            self.assertEqual([row["responseId"] for row in receipt], [row[3] for row in responses])
            self.assertEqual([row["bodyMarkers"] for row in receipt[:2]], [[DOCS_MARKER], [LOGIN_MARKER]])

    def test_wrong_page_has_same_status_media_type_and_csp(self):
        healthy, _ = self.observe("healthy", "/docs")
        wrong, receipt = self.observe("wrong-page", "/docs")
        self.assertEqual(healthy[0][:3], wrong[0][:3])
        self.assertIn(LOGIN_MARKER.encode(), wrong[0][4])
        self.assertEqual(receipt[0]["bodyMarkers"], [LOGIN_MARKER])

    def test_omitted_docs_leaves_only_control_receipt(self):
        _, receipt = self.observe("healthy", "/control")
        self.assertEqual([row["requestId"] for row in receipt], ["control"])
