"""Per-actor delegated auth candidate. Does not grant P0/runtime admission.

Transport and identity parsing belong to the adapter. Credentials are never part
of the journal API. A lock serializes identity, forwarding, refresh and loss: after
the loss latch no new protected request may enter the transport. An earlier proof
does not prove continuity up to a later request; those intervals remain uncertain.
"""
from __future__ import annotations

import threading
import time
import uuid

from .errors import Blocked


class AuthLost(Blocked):
    """Reason codes only; do not attach a target response or transport exception."""


class ProducerStop:
    """Bounded request/terminal callbacks; timeout or exception means quarantine.

    Callbacks must address the already-owned producer, never a shared stop-all.
    A timeout cannot cancel a callback; the owned resource must remain quarantined.
    """

    def __init__(self, request, terminal, request_timeout=10, terminal_timeout=120):
        if not 0 < request_timeout <= 10 or not 0 < terminal_timeout <= 120:
            raise ValueError('invalid stop budget')
        self.request = request
        self.terminal = terminal
        self.request_timeout = request_timeout
        self.terminal_timeout = terminal_timeout
        self.result = None

    @staticmethod
    def _call(callback, timeout):
        answer = []

        def invoke():
            try:
                answer.append(callback() is True)
            except Exception:
                answer.append(False)

        worker = threading.Thread(target=invoke, daemon=True)
        worker.start()
        worker.join(timeout)
        return not worker.is_alive() and answer == [True]

    def stop(self):
        if self.result is not None:
            return self.result
        began = time.monotonic()
        requested = self._call(self.request, self.request_timeout)
        request_finished = time.monotonic()
        terminal = self._call(self.terminal, self.terminal_timeout)
        self.result = {
            'stopRequested': requested, 'terminalConfirmed': terminal,
            'requestElapsedSeconds': request_finished - began,
            'terminalElapsedSeconds': time.monotonic() - request_finished,
            'cleanupStatus': 'stopped' if requested and terminal else 'quarantine',
            'stopUnconfirmed': not (requested and terminal),
        }
        return self.result


class ActorSession:
    """A single actor in a single run, with no automatic re-login or resume.

    Adapter interface: login(), refresh(token), identity(token), protected(token,
    method, path, body), logout(token). Each returns an ephemeral response object.
    identity() returns a strictly parsed {subject, role, buildRef} object; malformed
    JSON, login HTML and HTTP errors must raise. HTTP adapters have timeout <=8s.
    """

    def __init__(self, *, actor, subject, role, build_ref, run_id, plan_hash,
                 transport, record, producer, allow_refresh=False, poll_seconds=5,
                 clock=time.monotonic, response_safe=None, response_content_type='application/json',
                 response_oracle=None):
        if not 0 < poll_seconds <= 5:
            raise ValueError('identity poll exceeds budget')
        if (not all(isinstance(v, str) and v for v in
                   (actor, subject, build_ref, run_id, plan_hash))
                or (role is not None and (not isinstance(role, str) or not role))):
            raise ValueError('missing auth binding')
        # None explicitly means a subject-only protocol with no observed role.
        # Existing role-bearing contracts still require exact role equality.
        self.actor, self.subject, self.role = actor, subject, role
        self.build_ref, self.run_id, self.plan_hash = build_ref, run_id, plan_hash
        self.transport, self.record, self.producer = transport, record, producer
        self.allow_refresh, self.poll_seconds, self.clock = allow_refresh, poll_seconds, clock
        # An absent response secret policy is unsupported, not an implicit allow.
        self.response_safe = response_safe or (lambda response: False)
        if response_content_type not in ('application/json', 'text/html'):
            raise ValueError('unsupported response contract')
        self.response_content_type = response_content_type
        if response_content_type=='text/html' and not callable(response_oracle):
            raise ValueError('HTML transport requires a protected body oracle')
        self.response_oracle=response_oracle
        self.lock = threading.RLock()
        self.token = None
        self.epoch = None
        self.state = 'new'
        self.last_proof = None
        self.sequence = 0
        self.writer_failed = False
        self.closed = threading.Event()
        self.monitor = None
        self.stop_worker = None

    def _request_stop(self):
        # The producer detecting loss must return before it can terminate. Do
        # not await its terminal state while holding its forwarding lock.
        if self.stop_worker is not None:
            return

        def stop():
            result = self.producer.stop()
            with self.lock:
                if not self.writer_failed:
                    try:
                        self._event('producer_stop', **result)
                    except AuthLost:
                        pass  # snapshot retains writerFailed + stop result

        self.stop_worker = threading.Thread(target=stop, daemon=True)
        self.stop_worker.start()

    def _event(self, event, **fields):
        self.sequence += 1
        row = {'event': event, 'sequence': self.sequence, 'atMonotonic': self.clock(),
               'runId': self.run_id, 'planHash': self.plan_hash,
               'buildRef': self.build_ref, 'actorRef': self.actor,
               'authEpoch': self.epoch, **fields}
        try:
            self.record(row)
        except Exception:
            self.writer_failed = True
            self.token = None
            self.state = 'lost'
            self.closed.set()
            self._request_stop()
            raise AuthLost('auth_journal_failed') from None

    def _lose(self, reason):
        if self.state in ('lost', 'closed'):
            return
        self.token = None
        self.state = 'lost'
        self.closed.set()
        # Stop is attempted even if the durable journal is unavailable.
        self._event('auth_lost', reason=reason, uncertainSince=self.last_proof)
        self._request_stop()

    def await_stop(self):
        """An unconfirmed asynchronous stop never implies clean cleanup."""
        worker = self.stop_worker
        if worker:
            worker.join(self.producer.request_timeout + self.producer.terminal_timeout + 1)
            if worker.is_alive():
                raise AuthLost('producer_stop_unconfirmed')
        return self.producer.result

    def _proof(self, token):
        try:
            identity = self.transport.identity(token)
        except Exception:
            self._lose('identity_unavailable')
            raise AuthLost('identity_unavailable') from None
        if (not isinstance(identity, dict) or identity != {
                'subject': self.subject, 'role': self.role, 'buildRef': self.build_ref}):
            self._lose('identity_binding_changed')
            raise AuthLost('identity_binding_changed')
        now = self.clock()
        self._event('identity_proof', subjectRef=self.subject, roleRef=self.role,
                    continuity='point-in-time', uncertainSince=self.last_proof)
        self.last_proof = now

    def bootstrap(self):
        with self.lock:
            # Lost/revoked/closed sessions cannot be revived by a login control.
            if self.state != 'new':
                raise AuthLost('explicit_new_session_required')
            try:
                token = self.transport.login()
                if not isinstance(token, str) or not token:
                    raise ValueError()
            except Exception:
                self._lose('login_failed')
                raise AuthLost('login_failed') from None
            self.epoch = uuid.uuid4().hex
            self._proof(token)
            self.token, self.state = token, 'ready'
            self._event('epoch_started', cause='explicit_bootstrap')

    def _ready(self):
        if self.state != 'ready' or not self.token:
            raise AuthLost('auth_not_ready')

    def poll(self):
        with self.lock:
            self._ready()
            self._proof(self.token)

    def start_monitor(self):
        with self.lock:
            self._ready()
            if self.monitor is not None:
                raise ValueError('monitor already started')

            def watch():
                while not self.closed.wait(self.poll_seconds):
                    try:
                        self.poll()
                    except AuthLost:
                        return

            self.monitor = threading.Thread(target=watch, daemon=True)
            self.monitor.start()

    def protected(self, method, path, body=None):
        with self.lock:
            self._ready()
            self._proof(self.token)
            request_id = uuid.uuid4().hex
            self._event('protected_start', requestId=request_id, inFlight=1,
                        continuity='uncertain-between-identity-and-response')
            try:
                result = self.transport.protected(self.token, method, path, body)
            except Exception:
                self._lose('protected_transport_error')
                raise AuthLost('protected_transport_error') from None
            if (not isinstance(result, dict) or type(result.get('status')) is not int
                    or not 100 <= result['status'] <= 599):
                self._lose('protected_response_contract')
                raise AuthLost('protected_response_contract')
            self._event('protected_response_received', requestId=request_id,
                        status=result['status'], inFlight=0)
            try:
                safe = self.response_safe(result) is True
            except Exception:
                safe = False
            if not safe:
                self._lose('response_secret_policy')
                raise AuthLost('response_secret_policy')
            if result.get('status') == 401:
                self._lose('target_401')
                raise AuthLost('target_401')
            if self.response_content_type != result.get('contentType'):
                self._lose('protected_response_contract')
                raise AuthLost('protected_response_contract')
            try:
                accepted=self.response_oracle is None or self.response_oracle(result,method,path,body) is True
            except Exception:accepted=False
            if not accepted:
                self._lose('protected_body_oracle_failed')
                raise AuthLost('protected_body_oracle_failed')
            self._event('protected_finish', requestId=request_id, status=result['status'], inFlight=0)
            return result

    def refresh(self):
        with self.lock:
            self._ready()
            if not self.allow_refresh:
                raise AuthLost('refresh_not_in_contract')
            # A permitted refresh must not silently undo a revocation/role test.
            self._proof(self.token)
            try:
                token = self.transport.refresh(self.token)
                if not isinstance(token, str) or not token:
                    raise ValueError()
            except Exception:
                self._lose('refresh_rejected')
                raise AuthLost('refresh_rejected') from None
            previous = self.epoch
            # Validate the new identity BEFORE admitting the replacement token.
            # Proofs from this check bind the new epoch, not the previous one.
            self.epoch = uuid.uuid4().hex
            self.last_proof = None
            self._proof(token)
            self.token = token
            self._event('epoch_started', cause='refresh', previousEpoch=previous)

    def logout(self):
        with self.lock:
            self._ready()
            token = self.token
            # Latch first; a failed logout response cannot re-admit protected work.
            self._lose('explicit_logout')
            try:
                self.transport.logout(token)
            except Exception:
                raise AuthLost('logout_unconfirmed') from None

    def cancel(self, reason='cancel'):
        if reason not in ('cancel', 'cleanup', 'restart', 'exception'):
            raise ValueError('invalid cancellation reason')
        with self.lock:
            self._lose(reason)

    def close(self):
        self.cancel('cleanup')
        with self.lock:
            self.token = None
            self.state = 'closed'
            self.closed.set()
        if self.monitor and self.monitor is not threading.current_thread():
            self.monitor.join(9)
            if self.monitor.is_alive():
                raise AuthLost('monitor_stop_unconfirmed')
        self.await_stop()

    def snapshot(self):
        with self.lock:
            return {'actorRef': self.actor, 'authEpoch': self.epoch, 'state': self.state,
                    'lastProofMonotonic': self.last_proof, 'writerFailed': self.writer_failed,
                    'stop': self.producer.result or ({'stopUnconfirmed': True, 'cleanupStatus': 'pending'}
                                                   if self.stop_worker else None)}
