import copy
import hashlib
import json
import socket
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from zap_assessment.bola import (DirectClient, LIST, SEQUENCE, check_config, make_bola_plan,
                                 oracle, run_bola, strict_json)
from zap_assessment.bola_fixture import account_fixture
from zap_assessment.contracts import Blocked, canonical
from zap_assessment.evidence import EvidenceInvalid, verify_bundle


class BolaTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def execute(self, config, authority, env):
        plan = make_bola_plan(config, authority())
        result = run_bola(plan, self.temp.name, plan.hash, env)
        return result, verify_bundle(result['bundle'])

    def test_plan_is_read_only_and_reads_no_credentials(self):
        with account_fixture() as (config, authority, env, arrivals):
            with patch('zap_assessment.bola.DirectClient.get', side_effect=AssertionError('no target call')):
                make_bola_plan(config, authority())
            self.assertEqual(arrivals, [])

    def test_same_credential_cannot_pass_and_sends_zero_requests(self):
        with account_fixture() as (config, authority, env, arrivals):
            env['BOLA_TEST_B'] = env['BOLA_TEST_A']
            result, manifest = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertEqual(arrivals, [])
            self.assertEqual(manifest['executionStatus'], 'not_started')

    def test_missing_credential_cannot_pass_and_sends_zero_requests(self):
        with account_fixture() as (config, authority, env, arrivals):
            env.pop('BOLA_TEST_B')
            result, _ = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertEqual(arrivals, [])

    def test_swapped_wire_credentials_stop_before_cross_user_get(self):
        with account_fixture() as (config, authority, env, arrivals):
            original = DirectClient.get
            def swapped(client, actor, path):
                return original(client, {'A': 'B', 'B': 'A'}.get(actor, actor), path)
            with patch.object(DirectClient, 'get', swapped):
                result, _ = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertFalse(any(a['path'].endswith('/101') for a in arrivals))

    def test_reusing_A_on_B_wire_is_not_BOLA_pass(self):
        with account_fixture() as (config, authority, env, arrivals):
            original = DirectClient.get
            def reused(client, actor, path):
                return original(client, 'A' if actor == 'B' else actor, path)
            with patch.object(DirectClient, 'get', reused):
                result, _ = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertFalse(any(a['path'].endswith('/101') for a in arrivals))

    def test_scope_guard_blocks_before_socket(self):
        with account_fixture() as (config, authority, env, arrivals):
            plan = make_bola_plan(config, authority())
            client = DirectClient(plan, {'A': env['BOLA_TEST_A'], 'B': env['BOLA_TEST_B']})
            for path in ('/api/v1/accounts/102', '/api/v1/accounts/101?x=1',
                         'http://169.254.169.254/', '/api/auth/login', LIST+'/../accounts'):
                with self.subTest(path=path), self.assertRaises(Blocked):
                    client.get('B', path)
            with self.assertRaises(Blocked):
                client.get('admin', LIST)
            self.assertEqual(arrivals, [])

    def test_production_and_unpinned_origins_are_rejected(self):
        with account_fixture() as (config, authority, env, arrivals):
            for value in ('http://localhost:3000', 'http://169.254.169.254', 'http://8.8.8.8',
                          'http://127.0.0.1:1/path', 'http://127.0.0.1:1#x'):
                candidate = copy.deepcopy(config)
                candidate['origin'] = value
                with self.subTest(origin=value), self.assertRaises(Blocked):
                    check_config(candidate)
            config['environment']['kind'] = 'production'
            with self.assertRaises(Blocked):
                check_config(config)

    def test_unbound_product_is_rejected(self):
        with account_fixture() as (config, authority, env, arrivals):
            config['productId'] = 'finalsource'
            config['environment']['kind'] = 'staging'
            with self.assertRaises(Blocked):
                check_config(config)

    def test_expired_or_changed_authority_and_plan_refuse_traffic(self):
        with account_fixture() as (config, authority, env, arrivals):
            a = authority()
            a['validUntil'] = '2020-01-01T00:00:00Z'
            with self.assertRaises(Blocked):
                make_bola_plan(config, a)
            a = authority()
            config['fixture']['accountId'] = 102
            with self.assertRaises(Blocked):
                make_bola_plan(config, a)
            plan = make_bola_plan(config, authority())
            with self.assertRaises(Blocked):
                run_bola(plan, self.temp.name, '0'*64, env)
            self.assertEqual(arrivals, [])

    def test_redirect_does_not_reach_canary(self):
        with account_fixture('redirect') as (config, authority, env, arrivals):
            result, _ = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertEqual(len(arrivals), 1)

    def test_timeout_bounded_and_not_pass(self):
        with account_fixture('timeout') as (config, authority, env, arrivals):
            config['requestTimeoutSeconds'] = 0.1
            started = time.monotonic()
            result, _ = self.execute(config, authority, env)
            self.assertLess(time.monotonic()-started, 1)
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertEqual(result['executionStatus'], 'timed_out')

    def test_response_size_limit_no_false_pass(self):
        with account_fixture('oversize') as (config, authority, env, arrivals):
            result, _ = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'inconclusive')

    def test_duplicate_json_is_rejected(self):
        with self.assertRaises(Blocked):
            strict_json(b'{"success":false,"success":true}')

    def test_trickling_headers_hit_absolute_deadline(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        class SlowHeader(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass
            def do_GET(self):
                try:
                    for byte in b'HTTP/1.1 200 OK\r\n':
                        self.connection.sendall(bytes([byte]))
                        time.sleep(0.04)
                except OSError:
                    pass
        server = ThreadingHTTPServer(('127.0.0.1', 0), SlowHeader)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with account_fixture() as (config, authority, env, arrivals):
                config['origin'] = 'http://127.0.0.1:'+str(server.server_port)
                config['requestTimeoutSeconds'] = 0.1
                started = time.monotonic()
                result, _ = self.execute(config, authority, env)
                self.assertLess(time.monotonic()-started, 0.7)
                self.assertEqual(result['executionStatus'], 'timed_out')
                self.assertEqual(result['securityVerdict'], 'inconclusive')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)

    def test_bundle_verifier_replays_oracle_and_checks_journal(self):
        with account_fixture() as (config, authority, env, arrivals):
            result, manifest = self.execute(config, authority, env)
            self.assertEqual(result['securityVerdict'], 'pass')
            bundle = Path(result['bundle'])
            raw = b''.join(p.read_bytes() for p in bundle.iterdir())
            for value in [*env.values(), 'Synthetic Private Bank A', '9876', 'Private synthetic purchase']:
                self.assertNotIn(value.encode(), raw)
            self.assertEqual([a['actor'] for a in arrivals], [a for a, _, _ in SEQUENCE])
            self.assertFalse(any(a['cookiePresent'] for a in arrivals))
            for index, assertion in ((5, 'identityValid'), (6, 'ownerObjectValid'), (7, 'membershipValid')):
                changed = copy.deepcopy(manifest['tracks'][0]['observed'])
                changed[index]['response'][assertion] = False
                self.assertEqual(oracle(changed, 'completed')[0], 'inconclusive')
            changed = copy.deepcopy(manifest['tracks'][0]['observed'])
            changed[4]['response']['status'] = 401
            changed[4]['response']['denialValid'] = False
            self.assertEqual(oracle(changed, 'completed')[0], 'inconclusive')
            track = manifest['tracks'][0]
            track['observed'][4]['credentialSlot'] = 'A'
            raw = canonical(track)
            (bundle/'bola-evidence.json').write_bytes(raw)
            for a in manifest['artifacts']:
                if a['path'] == 'bola-evidence.json':
                    a.update(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            raw = canonical(manifest)
            (bundle/'manifest.json').write_bytes(raw)
            (bundle/'manifest.sha256').write_text(hashlib.sha256(raw).hexdigest()+'\n')
            with self.assertRaises(EvidenceInvalid):
                verify_bundle(bundle)


if __name__ == '__main__':
    unittest.main()
