"""W10 decision counterexamples. Normalized unit views are not runtime proof."""
from copy import deepcopy
import unittest
from zap_assessment.regression import compare_views


class RegressionTests(unittest.TestCase):
    def views(self):
        a = {'runId': 'A', 'build': 'build-A', 'scanner': {'version': '2.17', 'addons': ['a']},
             'facets': {k: ['same'] for k in ('scope', 'coverage', 'auth', 'policy', 'fixture', 'oracle')},
             'assertions': [{'technique': t, 'verified': True, 'oracleVulnerable': True, 'detected': True} for t in ('sqli', 'xss')],
             'blockers': [], 'evidenceHash': 'a', 'planHash': 'a'}
        b = deepcopy(a); b.update(runId='B', build='build-B', evidenceHash='b', planHash='b')
        for r in b['assertions']: r.update(oracleVulnerable=False, detected=False)
        return a, b

    def test_fixed_oracle_equivalent_exercise(self):
        a, b = self.views(); r = compare_views(a, b)
        self.assertEqual(r['remediationVerified'], ['sqli', 'xss']); self.assertEqual(r['exitCode'], 0)

    def test_unchanged_vulnerable_fails_even_when_scanner_silent(self):
        a, b = self.views()
        for row in b['assertions']: row['oracleVulnerable'] = True
        r = compare_views(a, b)
        self.assertEqual(r['observedRemoved'], ['sqli', 'xss']); self.assertEqual(r['remediationVerified'], [])
        self.assertEqual(r['securityVerdict'], 'fail'); self.assertEqual(r['exitCode'], 1)

    def test_missing_or_different_comparability_never_resolves(self):
        for key in ('scope', 'coverage', 'auth', 'policy', 'fixture', 'oracle'):
            for missing in (False, True):
                with self.subTest(key=key, missing=missing):
                    a, b = self.views()
                    if missing: b['facets'].pop(key)
                    else: b['facets'][key] = ['changed']
                    r = compare_views(a, b)
                    self.assertEqual(r['remediationVerified'], []); self.assertEqual(r['exitCode'], 2)
                    self.assertIn(key, r['comparabilityReasons'])

    def test_unknown_and_changed_scanner_block(self):
        for value in (None, {'version': 'changed'}):
            a, b = self.views(); b['scanner'] = value
            r = compare_views(a, b); self.assertEqual(r['remediationVerified'], [])
            self.assertEqual(r['exitCode'], 2); self.assertIn('scanner', r['comparabilityReasons'])

    def test_missing_required_assertion_or_sink_never_resolves(self):
        for missing in (False, True):
            a, b = self.views()
            if missing: b['assertions'].pop()
            else: b['assertions'][0]['verified'] = False
            r = compare_views(a, b); self.assertEqual(r['remediationVerified'], [])
            self.assertEqual(r['exitCode'], 2)

    def test_seed_is_review_candidate_not_enforce_success(self):
        a, b = self.views(); r = compare_views(a, b, mode='seed')
        self.assertEqual(r['exitCode'], 3); self.assertEqual(r['gateDecision'], 'review_required')
        self.assertEqual(r['remediationVerified'], [])

    def test_same_run_or_unpinned_build_block(self):
        for field, value in (('runId', 'A'), ('build', None)):
            a, b = self.views(); b[field] = value
            r = compare_views(a, b); self.assertEqual(r['exitCode'], 2)
            self.assertEqual(r['remediationVerified'], [])

    def test_unified_secret_failure_is_not_erased_by_fixed_active(self):
        a, b = self.views(); b['blockers'] = ['browser-secret-failure']
        r = compare_views(a, b); self.assertEqual(r['exitCode'], 1)
        self.assertEqual(r['gateDecision'], 'block'); self.assertEqual(r['securityVerdict'], 'fail')

    def test_absent_legacy_and_unknown_current_never_pass(self):
        a, b = self.views()
        for baseline, current in ((None, b), (a, None), (None, None)):
            r = compare_views(baseline, current)
            self.assertEqual(r['exitCode'], 2); self.assertEqual(r['remediationVerified'], [])

    def test_intentional_surface_removal_is_disposition_not_remediation(self):
        a, b = self.views()
        r = compare_views(a, b, amendments=[{'technique': 'sqli', 'disposition': 'removed-from-attack-surface'}])
        self.assertEqual(r['remediationVerified'], []); self.assertEqual(r['exitCode'], 2)
        self.assertEqual(len(r['scopeDispositions']), 1)

    def test_already_fixed_baseline_is_not_new_remediation(self):
        a, b = self.views()
        for row in a['assertions']: row.update(oracleVulnerable=False, detected=False)
        self.assertEqual(compare_views(a, b)['exitCode'], 2)

    def test_oracle_unknown_and_new_alert_fail_closed(self):
        a, b = self.views(); b['assertions'][0]['oracleVulnerable'] = None
        self.assertEqual(compare_views(a, b)['exitCode'], 2)
        b['assertions'][0]['detected'] = True
        self.assertEqual(compare_views(a, b)['exitCode'], 1)

    def test_target_build_change_is_expected_comparison_variable(self):
        a, b = self.views(); r = compare_views(a, b)
        self.assertTrue(r['comparable']); self.assertNotEqual(r['targetBuilds']['A'], r['targetBuilds']['B'])


class RegressionContractTests(unittest.TestCase):
    def test_locked_scope_cannot_omit_xss_or_switch_to_product(self):
        from zap_assessment.regression import make_request, validate_request
        from zap_assessment.evidence import EvidenceInvalid
        ref = {'bundle': '/nonexistent', 'planSha256': 'a' * 64, 'manifestSha256': 'b' * 64}
        p = make_request(None, ref)
        for field, value in (('requiredTechniques', ['sqli']), ('kind', 'product'), ('securityApproval', True), ('R1R2Admission', True)):
            v = deepcopy(p); v[field] = value
            with self.assertRaises(EvidenceInvalid): validate_request(v)

    def test_source_drift_and_unpaired_pin_refused(self):
        from zap_assessment.regression import make_request, validate_request, reference
        from zap_assessment.evidence import EvidenceInvalid
        p = make_request(None, reference('/nonexistent', 'a' * 64, 'b' * 64)); p['verifierPins'] = {}
        with self.assertRaises(EvidenceInvalid): validate_request(p)
        with self.assertRaises(EvidenceInvalid): reference('/nonexistent', 'invalid')

    def test_amendment_requires_explicit_version_reason_and_disposition(self):
        from zap_assessment.regression import make_request, reference
        from zap_assessment.evidence import EvidenceInvalid
        ref = reference('/nonexistent', 'a' * 64, 'b' * 64)
        with self.assertRaises(EvidenceInvalid): make_request(None, ref, amendments=[{'technique': 'sqli'}])
        row = {'contractVersion': 'scope_amendment/v1', 'technique': 'sqli', 'disposition': 'removed-from-attack-surface', 'reason': 'Route retired in version 2'}
        self.assertEqual(make_request(None, ref, amendments=[row])['scopeAmendments'], [row])

    def test_scanner_addon_order_is_not_drift_but_missing_inventory_is_unknown(self):
        from zap_assessment.regression import scanner_inventory
        a = {'id': 'a', 'version': '1', 'status': 'release'}; b = {**a, 'id': 'b'}
        scans = [{'before': {'version': '2.17', 'addons': [a, b]}}, {'before': {'version': '2.17', 'addons': [b, a]}}]
        self.assertIsNotNone(scanner_inventory(scans, 'image'))
        scans[0]['before']['addons'] = []
        self.assertIsNone(scanner_inventory(scans, 'image'))

    def test_strict_json_symlink_duplicate_keys_and_external_pin(self):
        import tempfile
        from pathlib import Path
        from zap_assessment.regression import compare_request, read_document
        from zap_assessment.evidence import EvidenceInvalid
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'request.json'; p.write_text('{"mode":1,"mode":2}')
            with self.assertRaises(EvidenceInvalid): read_document(p)
            p.write_text('{}')
            with self.assertRaises(EvidenceInvalid): compare_request(p, '0' * 64)
            link = Path(d) / 'link'; link.symlink_to(p)
            with self.assertRaises(OSError): read_document(link)

    def test_manifest_cannot_be_replaced_after_reference_locked(self):
        import tempfile
        from pathlib import Path
        from zap_assessment.regression import reference, load_view
        from zap_assessment.evidence import EvidenceInvalid
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'manifest.json'; p.write_text('{"contractVersion":"w8-owned-active-1"}')
            ref = reference(d, 'a' * 64)
            p.write_text('{"contractVersion":"legacy"}')
            with self.assertRaisesRegex(EvidenceInvalid, 'input_manifest_changed'): load_view(ref, 'active', 'current')


if __name__ == '__main__': unittest.main()
