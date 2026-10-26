"""W11 acceptance decision negatives. Unit views are not runtime evidence."""
from copy import deepcopy
import sys
import unittest
from zap_assessment.contracts import ROOT
sys.path.insert(0, str(ROOT / 'scripts'))
from w11_acceptance import generalization


class AcceptanceTests(unittest.TestCase):
    def views(self):
        values = []
        for name, adapter, ids, method, route, envelope in (
                ('p', 'finalsource-shaped', [1, 2], 'PUT', '/api/v1/accounts/id', 'data'),
                ('a', 'alternate-ledger', ['k-a', 'k-b'], 'PATCH', '/vault/wallets/id', 'result.value'),
                ('r', 'alternate-ledger', ['k-c', 'k-d'], 'PATCH', '/vault/wallets/id', 'result.value')):
            values.append({'runId': name, 'adapter': adapter, 'wireIds': ids, 'subjectIds': [name+'A', name+'B'],
                           'sourcePins': {'oracle': 'same'}, 'assertionShape': ['all-required'],
                           'required': 66, 'passed': 66, 'proofComplete': True,
                           'routes': {'account.update': [[method, route]]}, 'envelope': envelope,
                           'gaps': ['same-explicit-gap'], 'planHash': name, 'manifestSha256': name})
        return values

    def test_different_routes_envelopes_ids_same_core_pass(self):
        self.assertEqual(generalization(self.views())['status'], 'pass')

    def test_renamed_copy_cannot_prove_alternate_product(self):
        for key in ('routes', 'envelope', 'wireIds'):
            v = self.views(); v[1][key] = deepcopy(v[0][key])
            self.assertEqual(generalization(v)['status'], 'blocked')

    def test_reused_run_or_resource_ids_cannot_prove_freshness(self):
        for key in ('runId', 'wireIds', 'subjectIds'):
            v = self.views(); v[2][key] = deepcopy(v[1][key])
            self.assertEqual(generalization(v)['status'], 'blocked')

    def test_core_or_required_assertion_change_is_not_generalization(self):
        for key in ('sourcePins', 'assertionShape', 'gaps'):
            v = self.views(); v[1][key] = ['different']
            self.assertEqual(generalization(v)['status'], 'blocked')

    def test_missing_or_failed_required_case_never_passes(self):
        for key, value in (('required', 65), ('passed', 65), ('proofComplete', False)):
            v = self.views(); v[1][key] = value
            self.assertEqual(generalization(v)['status'], 'blocked')

    def test_numeric_alternate_ids_are_not_string_id_coverage(self):
        v = self.views(); v[1]['wireIds'] = [3, 4]
        self.assertEqual(generalization(v)['status'], 'blocked')

    def test_missing_repeat_is_not_complete_acceptance(self):
        self.assertEqual(generalization(self.views()[:2])['status'], 'blocked')

    def test_unknown_or_mixed_envelope_does_not_count(self):
        v = self.views(); v[1]['envelope'] = 'mixed-or-unknown'
        self.assertEqual(generalization(v)['status'], 'blocked')

    def test_partially_shared_route_is_detected(self):
        v = self.views()
        for i in (1, 2): v[i]['routes']['account.read'] = [['GET', '/api/v1/accounts/id']]
        v[0]['routes']['account.read'] = [['GET', '/api/v1/accounts/id']]
        self.assertIn('wire_route_overlap', generalization(v)['reasons'])

    def test_request_cannot_self_approve_or_remove_required_role(self):
        from w11_acceptance import validate_request, source_pins, VERSION
        from zap_assessment.evidence import EvidenceInvalid
        ref = {'bundle': '/nonexistent', 'planSha256': 'a' * 64, 'manifestSha256': 'b' * 64}
        value = {'contractVersion': VERSION, 'bundles': {k: ref for k in ('primary', 'alternate', 'repeat', 'unified')},
                 'regression': {'request': '/request', 'requestSha256': 'c' * 64, 'result': '/result', 'resultSha256': 'd' * 64},
                 'sourcePins': source_pins(), 'independentAcceptance': 'pending', 'securityApproval': False}
        validate_request(value)
        for field, wrong in (('independentAcceptance', 'approved'), ('securityApproval', True), ('sourcePins', {})):
            v = deepcopy(value); v[field] = wrong
            with self.assertRaises(EvidenceInvalid): validate_request(v)
        value['bundles'].pop('repeat')
        with self.assertRaises(EvidenceInvalid): validate_request(value)


if __name__ == '__main__': unittest.main()
