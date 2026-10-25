import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zap_assessment.bola import DirectClient, LIST, LOGIN, make_bola_plan, run_bola
from zap_assessment.bola_operational import (OwnedAccountFixture, login_assertion,
                                            membership_valid, run_profile)
from zap_assessment.contracts import ROOT, Blocked, canonical
from zap_assessment.evidence import EvidenceInvalid, verify_bundle


class OperationalTests(unittest.TestCase):
    def setUp(self):
        self.profile = json.loads((ROOT/'profiles/finalsource-synthetic.bola.json').read_bytes())
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_profile_cannot_become_a_product_profile(self):
        candidate = copy.deepcopy(self.profile)
        candidate['productId'] = 'finalsource'
        with patch('zap_assessment.bola_operational.OwnedAccountFixture') as provision:
            with self.assertRaises(Blocked):
                run_profile(candidate, self.temp.name)
            provision.assert_not_called()

    def test_list_membership_does_not_assert_identity(self):
        self.assertTrue(membership_valid(200, {'success': True, 'data': {'user_id': 'forged', 'accounts': []}}, 101, False))
        self.assertFalse(membership_valid(200, {'success': True, 'data': {'user_id': 22, 'accounts': [{'id': 101}]}}, 101, False))

    def test_unexpected_login_or_membership_payload_is_not_a_control_pass(self):
        config = {'fixture': {'ownerId': 11, 'nonOwnerId': 22}}
        for body in ([], None, 'opaque', 42, {'success': True, 'data': None}):
            response, token = login_assertion(200, body, 4, 'A', config)
            self.assertFalse(response['identityValid'])
            self.assertIsNone(token)
            self.assertFalse(membership_valid(200, body, 101, True))

    def test_wrong_login_identity_stops_before_business_gets(self):
        owned = OwnedAccountFixture(self.profile, 'login-wrong-identity')
        self.addCleanup(owned.close)
        plan = make_bola_plan(owned.config, owned.authority())
        result = run_bola(plan, self.temp.name, plan.hash, owned.env, owned)
        manifest = verify_bundle(result['bundle'])
        self.assertEqual(result['securityVerdict'], 'inconclusive')
        self.assertEqual([x['method'] for x in owned.state['arrivals']], ['POST', 'POST'])
        self.assertFalse(manifest['tracks'][0]['observed'][1]['response']['identityValid'])
        self.assertTrue(owned.closed)

    def test_login_auth_failure_is_not_retried_or_passed(self):
        owned = OwnedAccountFixture(self.profile, 'login-failure')
        self.addCleanup(owned.close)
        plan = make_bola_plan(owned.config, owned.authority())
        result = run_bola(plan, self.temp.name, plan.hash, owned.env, owned)
        self.assertEqual(result['securityVerdict'], 'inconclusive')
        self.assertEqual(len(owned.state['arrivals']), 2)
        self.assertEqual(result['cleanupStatus'], 'clean')

    def test_preflight_refuses_swapped_logical_secrets_before_requests(self):
        owned = OwnedAccountFixture(self.profile)
        self.addCleanup(owned.close)
        plan = make_bola_plan(owned.config, owned.authority())
        bad_env = dict(owned.env)
        bad_env['BOLA_LOGIN_B'] = bad_env['BOLA_LOGIN_A']
        result = run_bola(plan, self.temp.name, plan.hash, bad_env, owned)
        self.assertEqual(result['securityVerdict'], 'inconclusive')
        self.assertEqual(result['executionStatus'], 'not_started')
        self.assertEqual(owned.state['arrivals'], [])
        verify_bundle(result['bundle'])

    def test_preflight_requires_manifest_ownership(self):
        owned = OwnedAccountFixture(self.profile)
        self.addCleanup(owned.close)
        owned.manifest['createdByRun'] = 'different-run'
        plan = make_bola_plan(owned.config, owned.authority())
        with self.assertRaises(Blocked):
            owned.preflight(plan, owned.env)
        self.assertEqual(owned.state['arrivals'], [])

    def test_post_scope_cannot_expand_to_resource_mutation(self):
        owned = OwnedAccountFixture(self.profile)
        self.addCleanup(owned.close)
        client = DirectClient(make_bola_plan(owned.config, owned.authority()), {})
        for path in (LIST, LIST+'/101', '/api/auth/register', 'http://127.0.0.1:1/api/auth/login'):
            with self.assertRaises(Blocked):
                client.request('A', path, 'POST', {'email': 'test', 'password': 'test'})
        self.assertEqual(owned.state['arrivals'], [])


if __name__ == '__main__':
    unittest.main()
