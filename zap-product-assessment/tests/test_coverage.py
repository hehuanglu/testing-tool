import copy
import unittest

from zap_assessment.coverage import evaluate
from support.coverage_fixture import case_catalog, change_response, fixture, seal


class BoundCoverageTests(unittest.TestCase):
    def test_independent_g1_case_catalog(self):
        for case in case_catalog():
            with self.subTest(case=case['caseId']):
                result = evaluate(case['assertion'], case['evidence'])
                self.assertEqual(result['oracleResult'], case['expected'])
                if case['expectedReason']:
                    self.assertIn(case['expectedReason'], result['reasonCodes'])
                if case['expected'] == 'pass':
                    self.assertTrue(result['observed'])
                    self.assertTrue(result['requested'])
                    self.assertTrue(result['targetRequested'])
                    self.assertTrue(result['techniqueExecuted'])
                    self.assertEqual(result['responseSource'], 'target')

    def test_guard_source_does_not_depend_on_json_marker(self):
        a, e = fixture()
        e['boundaries']['primary']['source'] = 'guard'
        r = evaluate(a, e)
        self.assertEqual(r['responseSource'], 'guard')
        self.assertFalse(r['targetRequested'])
        self.assertFalse(r['techniqueExecuted'])
        self.assertNotEqual(r['oracleResult'], 'pass')

    def test_owner_positive_must_precede_denial(self):
        a, e = fixture()
        e['exchanges']['owner-positive']['at'] = 13
        seal(e, 'owner-positive')
        self.assertIn('owner_positive_not_before_request', evaluate(a, e)['reasonCodes'])

    def test_controls_cannot_relabel_a_different_phase(self):
        a, e = fixture()
        a['ownerPositive']['binding']['phaseId'] = 'foreign-phase'
        e['exchanges']['owner-positive']['binding']['phaseId'] = 'foreign-phase'
        seal(e, 'owner-positive')
        self.assertIn('wrong_control_context', evaluate(a, e)['reasonCodes'])

    def test_main_request_is_compared_with_locked_template(self):
        a, e = fixture()
        e['exchanges']['primary']['request']['path'] = '/v2/wallets/foreign'
        seal(e, 'primary')
        self.assertIn('request_mismatch', evaluate(a, e)['reasonCodes'])

    def test_missing_disclosure_oracle_is_inconclusive(self):
        a, e = fixture()
        a['oracle'].pop('forbiddenPointers')
        self.assertIn('missing_disclosure_oracle', evaluate(a, e)['reasonCodes'])

    def test_mixed_clock_and_post_state_order_cannot_pass(self):
        for field, value in [('clockId', 'other-clock'), ('at', 11)]:
            a, e = fixture()
            e['exchanges']['after'][field] = value
            seal(e, 'after')
            self.assertNotEqual(evaluate(a, e)['oracleResult'], 'pass')

    def test_wrong_post_state_resource_is_inconclusive(self):
        a, e = fixture()
        a['postState']['binding']['resourceRef'] = 'foreign'
        e['exchanges']['after']['binding']['resourceRef'] = 'foreign'
        seal(e, 'after')
        self.assertIn('state_resource_mismatch', evaluate(a, e)['reasonCodes'])

    def test_boolean_identity_is_not_numeric_user_id(self):
        a, e = fixture()
        a['identities']['B']['subject'] = 1
        change_response(e, 'identity-B', body={'subject': {'id': True, 'role': 'member'}})
        self.assertIn('identity_mismatch', evaluate(a, e)['reasonCodes'])

    def test_duplicate_json_keys_cannot_select_the_matching_actor(self):
        a, e = fixture()
        e['exchanges']['identity-B']['response']['body'] = '{"subject":{"id":701,"id":902,"role":"member"}}'
        seal(e, 'identity-B')
        self.assertIn('invalid_response_json', evaluate(a, e)['reasonCodes'])

    def test_missing_state_precondition_cannot_pass(self):
        a, e = fixture()
        a.pop('expectedPreState')
        self.assertIn('missing_state_or_precondition', evaluate(a, e)['reasonCodes'])

    def test_disclosure_remains_fail_if_post_state_missing(self):
        a, e = fixture()
        change_response(e, body={'error': {'code': 'NO_ACCESS'}, 'data': {'balance': '100.00'}})
        a.pop('postState')
        self.assertEqual(evaluate(a, e)['oracleResult'], 'fail')

    def test_confirmed_disclosure_remains_fail_if_later_proof_invalid(self):
        a, e = fixture()
        change_response(e, body={'error': {'code': 'NO_ACCESS'}, 'data': {'balance': '100.00'}})
        change_response(e, 'after', content_type='text/html')
        self.assertEqual(evaluate(a, e)['oracleResult'], 'fail')

    def test_raw_post_state_must_belong_to_bound_resource(self):
        a, e = fixture()
        a['statePointer'] = '/data/balance'
        a['expectedPreState'] = '100.00'
        change_response(e, 'after', body={'data': {'id': 'foreign', 'ownerId': 701, 'balance': '100.00'}})
        self.assertIn('state_resource_mismatch', evaluate(a, e)['reasonCodes'])

    def test_operation_label_cannot_disagree_with_request(self):
        a, e = fixture()
        a['binding']['operation'] = 'GET /other-route'
        e['exchanges']['primary']['binding'] = copy.deepcopy(a['binding'])
        seal(e, 'primary')
        self.assertIn('operation_request_mismatch', evaluate(a, e)['reasonCodes'])

    def test_json_error_200_is_not_resource_read_pass(self):
        case = next(c for c in case_catalog() if c['caseId'] == 'positive-owner-read')
        change_response(case['evidence'], body={'error': 'not_authenticated'})
        self.assertNotEqual(evaluate(case['assertion'], case['evidence'])['oracleResult'], 'pass')

    def test_anonymous_cannot_inherit_authenticated_epoch(self):
        a, e = fixture()
        a['binding']['actorRef'] = 'anonymous'
        e['exchanges']['primary']['binding'] = copy.deepcopy(a['binding'])
        seal(e, 'primary')
        self.assertIn('anonymous_binding_mismatch', evaluate(a, e)['reasonCodes'])

    def test_missing_schema_binding_never_uses_verified_flag(self):
        a, e = fixture()
        a.pop('binding')
        e['verified'] = True
        self.assertEqual(evaluate(a, e)['oracleResult'], 'inconclusive')

    def test_bad_status_does_not_erase_proven_request_execution(self):
        a, e = fixture()
        change_response(e, status=503, body={'error': 'unavailable'})
        r = evaluate(a, e)
        self.assertEqual(r['responseSource'], 'target')
        self.assertTrue(r['targetRequested'])
        self.assertTrue(r['techniqueExecuted'])
        self.assertEqual(r['oracleResult'], 'inconclusive')

    def test_unmatched_boundary_does_not_claim_target_source(self):
        a, e = fixture()
        e['boundaries']['primary']['responseId'] = 'unrelated-response'
        r = evaluate(a, e)
        self.assertEqual(r['responseSource'], 'unknown')
        self.assertFalse(r['targetRequested'])

    def test_reuse_does_not_mark_phase_complete(self):
        case = next(c for c in case_catalog() if c['caseId'] == 'explicit-completed-assertion-reuse')
        a, e = case['assertion'], case['evidence']
        before = copy.deepcopy(e)
        self.assertEqual(evaluate(a, e)['oracleResult'], 'pass')
        self.assertEqual(e, before)
        self.assertEqual(e['phases'][a['binding']['phaseId']]['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
