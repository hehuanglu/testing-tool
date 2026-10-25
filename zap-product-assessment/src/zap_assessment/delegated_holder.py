"""Holder-local wiring of existing broker/session and finalsource adapter.

Instantiate ONLY inside an independently verified isolated holder. This Python
object is not process/platform isolation. No host CLI accepts a credential value
or reference through this module, and no default operational ProofReplay exists.
"""
from .credential_broker import CredentialBroker
from .delegated_attestation import RuntimeAttestor
from .errors import Blocked
from .finalsource_delegated import FinalsourceAdapter, GetPolicy


class DelegatedHolder:
    def __init__(self, *, attestor, source, producer, record, forbidden_roots, operations,
                 timeout=5, poll_seconds=5):
        if not isinstance(attestor, RuntimeAttestor):
            raise Blocked('delegated_holder_attestor_required')
        self.attestor = attestor; self.binding = attestor.binding; self.target = attestor.target
        self.phase = 'new'; self.policy = GetPolicy(operations)
        adapter = FinalsourceAdapter(binding=self.binding, target=self.target, policy=self.policy,
            require_current=self._current, record=record, timeout=timeout)
        self.broker = CredentialBroker(binding=self.binding, source=source, adapter=adapter,
            producer=producer, record=record, check_current=lambda binding: self._current(binding, self.target),
            forbidden_roots=forbidden_roots, operations=[('GET', path) for path in self.policy.operations],
            allow_refresh=False, poll_seconds=poll_seconds)

    def _current(self, binding, target):
        if self.phase == 'new':
            self.attestor.before_resolve(binding, target); self.phase = 'bootstrapping'
            return True
        if self.phase == 'bootstrapping':
            return self.attestor.during_bootstrap(binding, target)
        if self.phase != 'ready' or self.broker.snapshot()['state'] != 'ready':
            raise Blocked('delegated_holder_not_ready')
        return self.attestor.before_dispatch(binding, target, self.broker.snapshot()['authEpoch'])

    def bootstrap(self):
        if self.phase != 'new':
            raise Blocked('delegated_holder_bootstrap_no_replay')
        try:
            snapshot = self.broker.bootstrap(self.binding)
            self.attestor.bind_epoch(snapshot['authEpoch']); self.phase = 'ready'
            self.broker.start_monitor(self.binding)
            return self.broker.snapshot()
        except Exception:
            self.phase = 'lost'; self.broker.cancel('exception')
            raise Blocked('delegated_holder_bootstrap_failed') from None

    def dispatch(self, method, path, body=None):
        # Response bytes go only to the last-hop boundary, never host control RPC.
        try:
            self.policy.check(method, path, body)
            return self.broker.protected(self.binding, method, path, body)
        except Exception:
            self.phase = 'lost'; self.broker.cancel('exception')
            raise Blocked('delegated_holder_dispatch_failed') from None

    def audit(self, blob):
        return self.broker.audit_bytes(self.binding, blob)

    def close(self):
        self.phase = 'closed'
        return self.broker.close()

    def destroy(self):
        self.phase = 'closed'; self.broker.destroy()
