"""W5 development oracles use actual loopback HTTP and target-owned session state."""
import importlib.util
import json
from pathlib import Path
import threading
import time
import unittest
import subprocess
import sys
import os

from zap_assessment.auth_lifecycle import AuthLost, ProducerStop
from zap_assessment.w5_fixture import Target, server, session
from zap_assessment.secret_audit import CanaryAuditor

SPEC = importlib.util.spec_from_file_location('w5_p0_guard', Path(__file__).resolve().parents[1]/'scripts/finalsource_p0_guard.py')
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)


class AuthLifecycleTests(unittest.TestCase):
    observations = None
    binding = None

    def setUp(self):
        self.target = Target()
        self.context = server(self.target)
        self.port = self.context.__enter__()
        self.events = []
        self.sessions = []
        self.receipts = []

    def make(self, actor='A', **options):
        if self.binding:
            options.update(run_id=self.binding[0], plan_hash=self.binding[1])
        candidate = session(self.target, self.port, self.events, actor, **options)
        self.sessions.append(candidate)
        return candidate

    def tearDown(self):
        try:
            for candidate in self.sessions:
                candidate.close()
        finally:
            self.context.__exit__(None, None, None)
        # Audit all emitted evidence; never include the canary values themselves.
        observation = {'caseId': self._testMethodName, 'events': self.events,
                       'target': self.target.rows, 'receipts': self.receipts,
                       'sessions': [s.snapshot() for s in self.sessions]}
        self.assertFalse(CanaryAuditor(self.target.canaries).matches(json.dumps(observation).encode()))
        if self.observations is not None:
            self.observations.append(observation)

    def count(self, path):
        return sum(row.get('path') == path for row in self.target.rows)

    def read(self, candidate):
        return candidate.protected('GET', '/api/v1/accounts')

    def assert_latched(self, candidate):
        candidate.await_stop()
        before = self.count('/api/v1/accounts')
        for _ in range(3):
            with self.assertRaises(AuthLost):
                self.read(candidate)
        with self.assertRaises(AuthLost):
            candidate.bootstrap()
        self.assertEqual(before, self.count('/api/v1/accounts'))
        self.assertIsNone(candidate.token)
        self.assertIn(candidate.state, ('lost', 'closed'))
        loss = [r for r in self.events if r['event'] == 'auth_lost' and r['actorRef'] == candidate.actor]
        self.assertTrue(loss)
        latch = loss[-1]['atMonotonic']
        # Fixture arrival log is independent of the guard event emitter.
        self.assertFalse(any(r.get('path') == '/api/v1/accounts' and
                             r['atMonotonic'] > latch and r['actorRef'] == candidate.actor
                             for r in self.target.rows))

    def test_success_and_actor_isolation(self):
        a, b = self.make(), self.make('B')
        a.bootstrap(); b.bootstrap()
        self.assertEqual('A', json.loads(self.read(a)['body'])['actorRef'])
        self.assertEqual('B', json.loads(self.read(b)['body'])['actorRef'])
        self.assertNotEqual(a.epoch, b.epoch)
        self.target.fault('revoke', 'A')
        with self.assertRaises(AuthLost):
            a.poll()
        self.assert_latched(a)
        self.assertEqual('B', json.loads(self.read(b)['body'])['actorRef'])

    def test_login_failure_never_forwards(self):
        self.target.login_failure = True
        a = self.make()
        with self.assertRaises(AuthLost):
            a.bootstrap()
        self.assert_latched(a)
        self.assertEqual(0, self.count('/api/v1/accounts'))

    def test_natural_expiry_is_enforced_by_target(self):
        self.target.ttl = .15
        a = self.make(poll_seconds=.03)
        a.bootstrap(); self.read(a); a.start_monitor()
        self.assertTrue(a.closed.wait(2), 'natural expiry not detected')
        a.monitor.join(2)
        self.assert_latched(a)
        expired = [r for r in self.target.rows if r.get('path') == '/identity' and not r['authenticated']]
        self.assertTrue(expired)
        self.assertGreaterEqual(expired[0]['atMonotonic'], expired[0]['serverExpiry'])
        self.receipts.append({'naturalExpiryObserved': True,
                              'detectionDelaySeconds': expired[0]['atMonotonic'] - expired[0]['serverExpiry']})

    def test_invalid_token_is_denied_by_target(self):
        a = self.make(); a.bootstrap()
        a.token = 'intentionally-invalid-synthetic-token'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)
        self.assertEqual(0, self.count('/api/v1/accounts'))

    def test_refresh_success_creates_new_epoch_and_revalidates(self):
        a = self.make(allow_refresh=True); a.bootstrap()
        old = a.epoch
        self.read(a); a.refresh(); self.read(a)
        self.assertNotEqual(old, a.epoch)
        proof_epochs = {e['authEpoch'] for e in self.events if e['event'] == 'identity_proof'}
        self.assertEqual({old, a.epoch}, proof_epochs)
        self.assertEqual(1, self.count('/refresh'))
        self.assertEqual(1, self.count('/login'))

    def test_refresh_failure_latches_and_cannot_relogin(self):
        a = self.make(allow_refresh=True); a.bootstrap()
        self.target.reject_refresh = True
        with self.assertRaises(AuthLost):
            a.refresh()
        self.assert_latched(a)
        self.assertEqual(1, self.count('/login'))

    def test_refresh_requires_explicit_contract(self):
        a = self.make(); a.bootstrap()
        with self.assertRaises(AuthLost):
            a.refresh()
        self.assertEqual(0, self.count('/refresh'))
        self.read(a)  # Disallowed control itself did not revoke a live target session.

    def test_refresh_wrong_identity_never_admits_new_token(self):
        a = self.make(allow_refresh=True); a.bootstrap()
        self.target.identity_mode = 'wrong-actor'
        with self.assertRaises(AuthLost):
            a.refresh()
        self.assert_latched(a)

    def test_logout_is_distinct_from_refresh_and_latches_first(self):
        a = self.make(allow_refresh=True); a.bootstrap(); self.read(a)
        a.logout(); self.assert_latched(a)
        self.assertEqual(1, self.count('/logout'))
        self.assertEqual(0, self.count('/refresh'))
        self.assertEqual(1, self.count('/login'))
        self.assertTrue(all(row['revoked'] for row in self.target.sessions.values()))

    def test_revocation_prevents_refresh_and_relogin(self):
        a = self.make(allow_refresh=True); a.bootstrap(); self.read(a)
        self.target.fault('revoke')
        with self.assertRaises(AuthLost):
            a.poll()
        with self.assertRaises(AuthLost):
            a.refresh()
        self.assert_latched(a)
        self.assertEqual(0, self.count('/refresh'))

    def test_role_change_rechecks_scope(self):
        a = self.make(); a.bootstrap(); self.target.fault('role-change')
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)

    def test_build_drift_rejected(self):
        a = self.make(); a.bootstrap(); self.target.build = 'different-build'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)

    def test_wrong_actor_identity_rejected(self):
        self.target.identity_mode = 'wrong-actor'
        a = self.make()
        with self.assertRaises(AuthLost):
            a.bootstrap()
        self.assert_latched(a)

    def test_identity_login_html_200_rejected(self):
        a = self.make(); a.bootstrap(); self.target.identity_mode = 'html'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)

    def test_protected_login_html_200_rejected(self):
        a = self.make(); a.bootstrap(); self.target.protected_mode = 'html'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)

    def test_html_transport_requires_explicit_body_oracle(self):
        with self.assertRaises(ValueError):
            self.make(response_content_type='text/html')

    def test_html_login_200_cannot_pass_declared_html_oracle(self):
        a=self.make(response_content_type='text/html',
                    response_oracle=lambda response,method,path,body: '<protected-echo>' in response['body'])
        a.bootstrap();self.target.protected_mode='html'
        with self.assertRaises(AuthLost):self.read(a)
        self.assert_latched(a)

    def test_target_401_after_valid_identity_latches(self):
        a = self.make(); a.bootstrap(); self.target.protected_mode = '401'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)
        self.assertEqual(1, self.count('/api/v1/accounts'))

    def test_response_echo_secret_is_not_exported(self):
        a = self.make(); a.bootstrap(); self.target.protected_mode = 'echo-secret'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)

    def test_response_cookie_is_not_exported(self):
        a = self.make(); a.bootstrap(); self.target.protected_mode = 'cookie'
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)

    def test_transport_exception_does_not_persist_message(self):
        a = self.make(); a.bootstrap()
        def failure(*args):
            raise ValueError(self.target.passwords['A'])
        a.transport.protected = failure
        with self.assertRaisesRegex(AuthLost, '^protected_transport_error$'):
            self.read(a)
        self.assert_latched(a)

    def test_cancel_and_restart_cannot_resume_memory_token(self):
        a = self.make(); a.bootstrap(); old = a.epoch
        a.cancel('restart'); self.assert_latched(a)
        # New process/session starts without a token. Only explicit login admits it.
        restarted = self.make()
        with self.assertRaises(AuthLost):
            self.read(restarted)
        restarted.bootstrap(); self.read(restarted)
        self.assertNotEqual(old, restarted.epoch)
        self.assertEqual(2, self.count('/login'))

    def test_expired_session_during_outage_does_not_resume(self):
        self.target.ttl = .08
        a = self.make(); a.bootstrap(); a.cancel('restart')
        time.sleep(.1)
        with self.assertRaises(AuthLost):
            self.read(a)
        self.assert_latched(a)
        self.assertEqual(0, self.count('/api/v1/accounts'))

    def test_real_process_sigkill_restart_live_and_expired(self):
        def child(bootstrap):
            process = subprocess.Popen([sys.executable, '-m', 'zap_assessment.w5_fixture', '--child'],
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, text=True,
                                       env={**os.environ, 'PYTHONPATH': str(Path(__file__).resolve().parents[1]/'src')})
            self.addCleanup(dispose, process)
            config = {'port': self.port, 'bootstrap': bootstrap}
            if self.binding:
                config.update(runId=self.binding[0], planHash=self.binding[1])
            if bootstrap:
                config['password'] = self.target.passwords['A']
            process.stdin.write(json.dumps(config) + '\n'); process.stdin.flush()
            return process, json.loads(process.stdout.readline())

        def dispose(process):
            if process.poll() is None:
                process.kill()
            process.wait(timeout=3)
            for stream in (process.stdin, process.stdout, process.stderr):
                stream.close()

        for expired in (False, True):
            self.target.ttl = .12 if expired else 10
            old, ready = child(True)
            self.assertEqual([0, 0], ready['coreLimit'])
            self.assertEqual('ready', ready['snapshot']['state'])
            old.kill(); old.wait(timeout=3)
            self.assertLess(old.returncode, 0)
            if expired:
                time.sleep(.15)
            fresh, empty = child(False)
            self.assertEqual('new', empty['snapshot']['state'])
            self.assertIsNone(empty['snapshot']['authEpoch'])
            fresh.stdin.write(json.dumps('protected') + '\n'); fresh.stdin.flush()
            self.assertEqual('blocked', json.loads(fresh.stdout.readline())['result'])
            fresh.stdin.write(json.dumps('close') + '\n'); fresh.stdin.flush()
            fresh.wait(timeout=3)
            self.receipts.append({'processKilled': True, 'targetSessionExpiredDuringOutage': expired,
                                  'restartWithoutCredentialBlocked': True, 'coreLimit': [0, 0]})
        self.assertEqual(0, self.count('/api/v1/accounts'))

    def test_owned_producer_actually_stops_after_auth_loss(self):
        stop_requested = threading.Event()
        ended = threading.Event()
        a = self.make(producer=ProducerStop(lambda: (stop_requested.set() or True),
                                           lambda: ended.wait(1), terminal_timeout=2),
                      poll_seconds=.02)
        a.bootstrap()
        # Stop acknowledgement does not acquire the session lock. The producer
        # loop cooperates before creating its next operation.
        def produce():
            try:
                while not stop_requested.wait(.01):
                    try:
                        self.read(a)
                    except AuthLost:
                        break
            finally:
                ended.set()
        worker = threading.Thread(target=produce)
        worker.start()
        self.addCleanup(worker.join, 3)
        # Start monitor only after proving that the producer sent target traffic.
        deadline = time.monotonic() + 1
        while self.count('/api/v1/accounts') == 0 and time.monotonic() < deadline:
            time.sleep(.005)
        self.assertGreater(self.count('/api/v1/accounts'), 0)
        self.target.fault('revoke')
        a.start_monitor()
        self.assertTrue(stop_requested.wait(2))
        self.assertTrue(ended.wait(2))
        worker.join(2)
        self.assert_latched(a)
        self.assertFalse(a.snapshot()['stop']['stopUnconfirmed'])
        self.receipts.append({'ownedProducerEnded': True, 'stop': a.snapshot()['stop']})

    def test_stop_timeout_quarantines(self):
        release = threading.Event()
        stop = ProducerStop(lambda: release.wait(1), lambda: False,
                            request_timeout=.02, terminal_timeout=.02)
        a = self.make(producer=stop); a.bootstrap()
        try:
            a.cancel()
            a.await_stop()
            self.assertTrue(a.snapshot()['stop']['stopUnconfirmed'])
            self.assertEqual('quarantine', a.snapshot()['stop']['cleanupStatus'])
            self.assert_latched(a)
        finally:
            release.set()

    def test_stop_exception_quarantines(self):
        def failure():
            raise RuntimeError('not confirmed')
        a = self.make(producer=ProducerStop(failure, lambda: True)); a.bootstrap(); a.cancel()
        a.await_stop()
        self.assertTrue(a.snapshot()['stop']['stopUnconfirmed'])
        self.assert_latched(a)

    def test_journal_failure_stops_without_forward(self):
        a = self.make(); a.bootstrap()
        def failure(_):
            raise OSError('synthetic ENOSPC')
        a.record = failure
        with self.assertRaises(AuthLost):
            self.read(a)
        a.await_stop()
        self.assertTrue(a.snapshot()['writerFailed'])
        self.assertIsNone(a.token)
        self.assertTrue(a.snapshot()['stop']['terminalConfirmed'])
        self.assertEqual(0, self.count('/api/v1/accounts'))

    def test_inflight_and_concurrent_latch_have_no_new_forward(self):
        a = self.make(); a.bootstrap(); self.target.protected_mode = 'in-flight'
        errors = []
        def read():
            try:
                self.read(a)
            except AuthLost:
                errors.append('lost')
        request = threading.Thread(target=read)
        request.start()
        self.assertTrue(self.target.request_entered.wait(1))
        self.target.fault('revoke')
        cancel = threading.Thread(target=a.cancel)
        cancel.start(); self.target.release_request.set()
        request.join(2); cancel.join(2)
        self.assertFalse(request.is_alive() or cancel.is_alive())
        self.assertEqual(['lost'], errors)
        self.assert_latched(a)
        self.assertEqual(1, self.count('/api/v1/accounts'))
        self.assertTrue(any(e['event'] == 'protected_start' and e['inFlight'] == 1 for e in self.events))

    def test_p0_guard_injection_preserves_marker_and_read_scope(self):
        a = self.make()
        # No credentials path is even present in this candidate config.
        guard = GUARD.State({'mode': 'delegated', 'actor': 'A', 'accounts': [],
                             'fixturePrefix': 'unused'}, lifecycle=a)
        guard.login('A')
        self.assertIsNone(guard.mirror('GET', '/api/v1/accounts', {'Authorization': 'Bearer scan-marker-B'}, None))
        self.assertIsNone(guard.mirror('POST', '/api/v1/accounts', {}, {}))
        self.assertEqual(0, self.count('/api/v1/accounts'))
        self.assertEqual(200, guard.mirror('GET', '/api/v1/accounts', {}, None)['status'])
        self.target.fault('revoke')
        self.assertEqual(401, guard.mirror('GET', '/api/v1/accounts', {}, None)['status'])
        self.assertEqual(401, guard.mirror('GET', '/api/v1/accounts', {}, None)['status'])
        with self.assertRaises(ValueError):
            guard.control({'op': 'request', 'method': 'GET', 'path': '/api/v1/accounts'})
        self.assert_latched(a)

    def test_p0_guard_actor_binding_is_required(self):
        a = self.make()
        with self.assertRaises(ValueError):
            GUARD.State({'mode': 'delegated', 'actor': 'B'}, lifecycle=a)


if __name__ == '__main__':
    unittest.main()
