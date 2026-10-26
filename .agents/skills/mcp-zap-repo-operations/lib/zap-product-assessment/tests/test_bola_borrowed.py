import base64
import copy
import hashlib
import json
import tempfile
import time
import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from zap_assessment.bola import DirectClient, LIST, check_config, make_bola_plan, run_bola
from zap_assessment.bola_borrowed import WORKER, preflight, resolve_login_inputs, token_matches_actor
from zap_assessment.contracts import Blocked, canonical, digest, utcnow


def inputs():
    config = {'schemaVersion': '1.4', 'adapter': 'finalsource-account-read-v1',
        'productId': 'borrowed-synthetic-account', 'environment': {'kind': 'synthetic', 'identity': 'unit-target', 'evidenceRef': 'unit-owned-fixture'},
        'origin': 'http://127.0.0.1:18080', 'targetBuildRef': 'sha256:'+'b'*64,
        'binding': {'containerId': 'a'*64, 'imageId': 'sha256:'+'b'*64, 'networkId': 'c'*64,
                    'address': '127.0.0.1', 'startedAt': '2026-10-18T00:00:00Z'},
        'fixture': {'accountId': 101, 'ownerId': 11, 'nonOwnerId': 22, 'provenanceRef': 'unit-owned-fixture'},
        'credentials': {'A': {'loginEnv': 'UNIT_A_LOGIN'}, 'B': {'loginEnv': 'UNIT_B_LOGIN'}},
        'anonymous': True, 'requestTimeoutSeconds': 1, 'totalTimeoutSeconds': 30, 'maxRate': 2, 'retentionDays': 14,
        'jwt': {'issuer': 'unit-fixture', 'audience': 'unit-client', 'algorithm': 'HS256'},
        'runtime': {'kind': 'docker-isolated-client', 'imageId': 'sha256:'+'d'*64,
                    'workerSha256': hashlib.sha256(WORKER.read_bytes()).hexdigest()}}
    now = utcnow()
    authority = {'schemaVersion': '1.4', 'recordId': 'unit-authority', 'owner': 'unit-fixture-owner',
        'issuer': 'unit-fixture-harness', 'reviewer': 'pending-human-review', 'approvalRef': 'unit-synthetic-only',
        'validFrom': now.isoformat(), 'validUntil': (now+timedelta(hours=1)).isoformat(), 'configHash': digest(config),
        'fixtureMode': 'borrowed-read-only', 'assumed': False, 'productId': config['productId'],
        'environmentIdentity': 'unit-target', 'operations': ['actor-login', 'account-list-ownership',
            'account-detail-owner', 'account-detail-cross-user', 'account-detail-anonymous']}
    return config, authority


def jwt(subject, **overrides):
    claims = {'sub': subject, 'exp': int(time.time())+900, 'iss': 'unit-fixture', 'aud': 'unit-client', **overrides}
    enc = lambda x: base64.urlsafe_b64encode(canonical(x)).rstrip(b'=').decode()
    return enc({'alg': 'HS256'})+'.'+enc(claims)+'.unit-signature-not-cryptographic-proof'


class BorrowedTests(unittest.TestCase):
    def test_plan_and_preflight_are_read_only_without_credentials(self):
        c, a = inputs();plan = make_bola_plan(c, a)
        def selected(args, *unused, **kwargs):
            if args[:2] == ['image', 'inspect']:
                return (c['runtime']['imageId']+'\n').encode()
            if args[:2] == ['network', 'inspect']:
                return canonical({'id': c['binding']['networkId'], 'driver': 'bridge', 'scope': 'local', 'ingress': False})
            self.fail('unexpected preflight side effect')
        with patch('zap_assessment.bola.binding_readback', return_value={**c['binding'], 'running': True}), \
             patch('zap_assessment.bola_borrowed.command', side_effect=selected) as cmd, \
             patch('zap_assessment.bola_borrowed.resolve_login_inputs', side_effect=AssertionError('no credentials')):
            result = preflight(plan)
        self.assertFalse(result['credentialValuesRead'])
        self.assertEqual(result['httpRequests'], 0)
        self.assertEqual(result['resourcesCreated'], 0)
        self.assertEqual(cmd.call_count, 2)

    def test_binding_drift_blocks_before_runtime_and_secret_resolution(self):
        c, a = inputs();plan = make_bola_plan(c, a)
        with tempfile.TemporaryDirectory() as output, \
             patch('zap_assessment.bola.binding_readback', side_effect=Blocked('binding drift')), \
             patch('zap_assessment.bola_borrowed.resolve_login_inputs') as resolve, \
             patch('zap_assessment.bola_borrowed.DockerBolaRunner.prepare') as prepare:
            result = run_bola(plan, output, plan.hash, {})
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertEqual(result['executionStatus'], 'not_started')
            resolve.assert_not_called();prepare.assert_not_called()

    def test_assumptions_and_health_only_authority_are_not_executable(self):
        c, a = inputs()
        assumed = copy.deepcopy(a);assumed['assumed'] = True
        with self.assertRaises(Blocked):
            make_bola_plan(c, assumed)
        health = copy.deepcopy(a);health['operations'] = ['health', 'crawl', 'import', 'seed']
        with self.assertRaises(Blocked):
            make_bola_plan(c, health)
        c['environment']['kind'] = 'test';c['productId'] = 'finalsource';c['retentionDays'] = 30
        a.update(productId='finalsource', owner='synthetic-test-owner', configHash=digest(c))
        with self.assertRaises(Blocked):
            make_bola_plan(c, a)

    def test_production_and_unknown_runtime_capabilities_are_rejected(self):
        c, a = inputs();c['environment']['kind'] = 'production'
        with self.assertRaises(Blocked):
            check_config(c)
        c, a = inputs();c['runtime']['arbitraryCommand'] = 'echo should-never-run'
        with self.assertRaises(Blocked):
            check_config(c)

    def test_token_claims_only_consistent_with_correct_actor(self):
        c, a = inputs()
        self.assertTrue(token_matches_actor(jwt(22), 'B', c))
        for value in (jwt(11), jwt(22, exp=1), jwt(22, iss='other'), jwt(22, aud='other'), jwt('22'), 'opaque'):
            self.assertFalse(token_matches_actor(value, 'B', c))

    def test_A_credentials_on_B_slot_never_reach_runner(self):
        c, a = inputs();client = DirectClient(make_bola_plan(c, a), {'A': jwt(11), 'B': jwt(22)})
        client.runner = Mock()
        client.bound_credentials = dict(client.credentials)
        client.credentials['B'] = client.credentials['A']
        with self.assertRaises(Blocked):
            client.get('B', LIST+'/101')
        client.runner.exchange.assert_not_called()
        self.assertEqual(client.dispatch, [])

    def test_without_isolated_runner_borrowed_requests_are_refused(self):
        c, a = inputs();client = DirectClient(make_bola_plan(c, a), {})
        with self.assertRaises(Blocked):
            client.request('A', '/api/auth/login', 'POST', {'email': 'unit@fixture.invalid', 'password': 'unit'})

    def test_scope_cannot_expand_to_writes_or_other_object(self):
        c, a = inputs();client = DirectClient(make_bola_plan(c, a), {})
        client.runner = Mock()
        for method, path in [('POST', LIST), ('DELETE', LIST+'/101'), ('GET', LIST+'/102'),
                             ('POST', '/api/auth/register'), ('GET', 'http://169.254.169.254/')]:
            with self.assertRaises(Blocked):
                client.request('A', path, method)
        client.runner.exchange.assert_not_called()

    def test_missing_or_same_login_inputs_cannot_run(self):
        c, a = inputs()
        with self.assertRaises(Blocked):
            resolve_login_inputs(c, {})
        payload = json.dumps({'email': 'same@fixture.invalid', 'password': 'unit-only'})
        with self.assertRaises(Blocked):
            resolve_login_inputs(c, {'UNIT_A_LOGIN': payload, 'UNIT_B_LOGIN': payload})

    def test_plan_mismatch_blocks_before_docker_and_secrets(self):
        c, a = inputs();plan = make_bola_plan(c, a)
        with tempfile.TemporaryDirectory() as output, patch('zap_assessment.bola_borrowed.preflight') as pf:
            with self.assertRaises(Blocked):
                run_bola(plan, output, '0'*64, {})
            pf.assert_not_called()

    def test_worker_refuses_expired_authority_before_connect(self):
        from zap_assessment.bola_http import exchange
        with patch('zap_assessment.bola_http.http.client.HTTPConnection') as connection:
            with self.assertRaises(ValueError):
                exchange('http://127.0.0.1:18080', 'GET', LIST, {}, None, 1, time.time()-1)
            connection.return_value.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()
