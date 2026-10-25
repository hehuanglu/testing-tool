"""Independent counterexamples; unit tests do not fabricate actual scan evidence."""
from copy import deepcopy
import json
import tempfile
import unittest
from zap_assessment.active_fixture import fixture, exercise, WITNESSES
from zap_assessment.active_verification import oracle, sql_effect, ExecutableHTML, plugin_rows, verify_active_bundle, sha
from zap_assessment.contracts import ROOT
from zap_assessment.evidence import EvidenceInvalid


class ActiveTests(unittest.TestCase):
    def row(self, variant, technique, value):
        from urllib.parse import urlencode
        config = fixture(8101); status, kind, body, sink = exercise(variant, config, technique, value)
        param = 'name' if technique == 'sqli' else 'q'
        return config, {'fixtureTag': config['tag'], 'variant': variant, 'technique': technique,
            'method': 'GET', 'input': value, 'parameter': param, 'valid': True, 'sink': sink, 'status': status,
            'contentType': kind, 'response': body.decode(), 'responseBodySha256': sha(body),
            'url': 'http://127.0.0.1:18080/' + technique + '?' + urlencode({param: value})}

    def test_baseline_semantics_preserved(self):
        for variant in ('vulnerable', 'fixed'):
            config, row = self.row(variant, 'sqli', fixture(8101)['names'][0])
            self.assertEqual(row['sink']['rows'], [config['names'][0]])
            self.assertTrue(oracle(row, config, variant))

    def test_real_sql_injection_and_parameterized_control(self):
        for variant, expected in [('vulnerable', 2), ('fixed', 0)]:
            config, row = self.row(variant, 'sqli', WITNESSES['sqli'])
            self.assertEqual(len(row['sink']['rows']), expected)
            self.assertTrue(oracle(row, config, variant))

    def test_sql_error_is_actual_sqlite_exception(self):
        config, row = self.row('vulnerable', 'sqli', "'")
        self.assertEqual(row['status'], 500); self.assertIsNotNone(row['sink']['error'])
        self.assertTrue(oracle(row, config, 'vulnerable'))
        config, row = self.row('fixed', 'sqli', "'")
        self.assertEqual(row['status'], 200); self.assertIsNone(row['sink']['error'])
        self.assertTrue(oracle(row, config, 'fixed'))

    def test_zero_rows_for_absent_value_is_not_injection_effect(self):
        config, row = self.row('vulnerable', 'sqli', 'S4feV4lu3')
        self.assertTrue(oracle(row, config, 'vulnerable')); self.assertFalse(sql_effect(row, config))
        for attack in ("'", WITNESSES['sqli']):
            config, row = self.row('vulnerable', 'sqli', attack)
            self.assertTrue(oracle(row, config, 'vulnerable')); self.assertTrue(sql_effect(row, config))
            config, row = self.row('fixed', 'sqli', attack)
            self.assertTrue(oracle(row, config, 'fixed')); self.assertFalse(sql_effect(row, config))

    def test_xss_html_parser_context(self):
        for variant, expected in [('vulnerable', True), ('fixed', False)]:
            config, row = self.row(variant, 'xss', WITNESSES['xss'])
            parser = ExecutableHTML(); parser.feed(row['response']); self.assertEqual(parser.active, expected)
            self.assertTrue(oracle(row, config, variant))

    def test_escaped_event_attribute_is_text(self):
        for variant, expected in [('vulnerable', True), ('fixed', False)]:
            config, row = self.row(variant, 'xss', '<img src=x onerror=alert(937)>')
            parser = ExecutableHTML(); parser.feed(row['response']); self.assertEqual(parser.active, expected)
            self.assertTrue(oracle(row, config, variant))

    def test_unicode_and_html_characters(self):
        for variant in ('vulnerable', 'fixed'):
            for t in ('sqli', 'xss'):
                config, row = self.row(variant, t, 'Việt & < > "')
                self.assertTrue(oracle(row, config, variant))

    def test_missing_sink_cannot_verify(self):
        config, row = self.row('fixed', 'sqli', 'alpha')
        for sink in (None, {'kind': 'missing'}):
            v = deepcopy(row); v['sink'] = sink; self.assertFalse(oracle(v, config, 'fixed'))

    def test_invalid_seed_flag_cannot_hide_valid_request(self):
        config, row = self.row('fixed', 'sqli', 'alpha'); row['valid'] = False
        with self.assertRaisesRegex(EvidenceInvalid, 'seed_validation'): oracle(row, config, 'fixed')

    def test_recomputed_response_hash_does_not_forge_sql_state(self):
        config, row = self.row('fixed', 'sqli', WITNESSES['sqli'])
        row['sink']['rows'] = config['names']; row['response'] = json.dumps({'items': config['names']})
        row['responseBodySha256'] = sha(row['response'].encode())
        with self.assertRaisesRegex(EvidenceInvalid, 'sql_execution_replay'): oracle(row, config, 'fixed')

    def test_recomputed_response_hash_does_not_forge_html_safety(self):
        config, row = self.row('vulnerable', 'xss', WITNESSES['xss'])
        row['sink']['rendered'] = '&lt;script&gt;alert(937)&lt;/script&gt;'
        with self.assertRaisesRegex(EvidenceInvalid, 'html_render_replay'): oracle(row, config, 'vulnerable')

    def test_received_parameter_not_trusted_without_wire_query(self):
        config, row = self.row('fixed', 'xss', 'one'); row['input'] = 'different'
        with self.assertRaisesRegex(EvidenceInvalid, 'received_input'): oracle(row, config, 'fixed')

    def test_wrong_fixture_variant_and_tag(self):
        config, row = self.row('fixed', 'xss', 'one')
        with self.assertRaisesRegex(EvidenceInvalid, 'arrival_build_binding'): oracle(row, config, 'vulnerable')
        row['fixtureTag'] = 'other'
        with self.assertRaisesRegex(EvidenceInvalid, 'arrival_build_binding'): oracle(row, config, 'fixed')

    def test_json_is_not_an_html_xss_sink(self):
        config, row = self.row('vulnerable', 'xss', WITNESSES['xss']); row['contentType'] = 'application/json'
        with self.assertRaisesRegex(EvidenceInvalid, 'html_sink_context'): oracle(row, config, 'vulnerable')

    def test_wrong_method_or_route_does_not_verify(self):
        for key, value in [('method', 'POST'), ('url', 'http://127.0.0.1:18080/other?q=one'), ('parameter', 'other')]:
            config, row = self.row('fixed', 'xss', 'one'); row[key] = value
            with self.assertRaises(EvidenceInvalid): oracle(row, config, 'fixed')

    def test_dynamic_fixtures_have_same_shape_different_data(self):
        self.assertNotEqual(fixture(8)['tag'], fixture(9)['tag'])
        self.assertNotEqual(fixture(8)['names'], fixture(9)['names'])
        self.assertEqual([v['ruleId'] for v in fixture(8)['vectors']], ['40018', '40012'])

    def test_progress_parser_is_execution_data_only(self):
        row = ['x', '40018', 'sqli', 'Complete', '0', '0', '0']
        self.assertEqual(plugin_rows({'a': [{'Plugin': row}]}), [row])

    def test_external_plan_pin_mandatory(self):
        with tempfile.TemporaryDirectory() as path:
            with self.assertRaisesRegex(EvidenceInvalid, 'external_plan_pin_required'): verify_active_bundle(path, None)

    def test_cli_has_no_target_or_credential_arguments(self):
        text = (ROOT / 'scripts/w8_active_campaign.py').read_text()
        self.assertNotIn("add_argument('--target", text)
        self.assertNotIn("add_argument('--password", text)


if __name__ == '__main__': unittest.main()
