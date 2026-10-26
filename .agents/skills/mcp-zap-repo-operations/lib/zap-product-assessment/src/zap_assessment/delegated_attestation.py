"""Runtime pin/epoch/admission mechanism for an isolated delegated holder.

ProofReplay is trusted executable verification, never a JSON 'allow' flag. The
production G3/platform collectors are still required; this module supplies no
default proof provider and enables no CLI/P0 mode. Unit fake replayers demonstrate
ordering/denial mechanics only, not semantic acceptance of product evidence.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
import hashlib
import math
import re
import threading
import time

from .credential_broker import BrokerBinding
from .errors import Blocked
from .finalsource_delegated import TargetBinding
from .secret_audit import CanaryAuditor

GATES = frozenset(('authority', 'G3', 'G4', 'G5', 'G6', 'platform'))


class ProofReplay(ABC):
    """Implemented by trusted collector/verifier code, source-pinned with holder.

    Replay actual evidence bytes for every gate, raising on incomplete semantics.
    A successful return is NOT synthesized from gateDecision/status/checksums.
    Implementations must verify actual sink access/control/decoder/lifecycle,
    human authority/scope/expiry, independent actor/epoch/transport, policy/rule
    attribution, calibrated resource and stop/ownership, plus platform boundaries. Diagnostic evidence cannot serve
    as the operational implementation of this interface.
    """
    @abstractmethod
    def verify(self, gate, evidence, *, binding, target, epoch, now):
        raise Blocked('operational_proof_replayer_absent')


@dataclass(frozen=True)
class RuntimeSnapshot:
    target: TargetBinding
    scanner_id: str
    scanner_image: str
    holder_id: str
    holder_image: str
    observed_at: float  # monotonic clock shared with holder, not wall time


class RuntimeAttestor:
    def __init__(self, *, binding, target, scanner_id, scanner_image, holder_id, holder_image,
                 source_root, source_pins, evidence_root, evidence_pins, replay, observe,
                 stop, clock=time.time, monotonic=time.monotonic):
        if (not isinstance(binding, BrokerBinding) or not isinstance(target, TargetBinding)
                or not isinstance(replay, ProofReplay) or not callable(observe) or not callable(stop)
                or not source_pins or set(evidence_pins) != GATES):
            raise Blocked('delegated_attestor_contract_invalid')
        for value in (scanner_id, holder_id):
            if not isinstance(value, str) or not re.fullmatch('[0-9a-f]{64}', value):
                raise Blocked('delegated_attestor_resource_invalid')
        if scanner_id == holder_id:
            raise Blocked('delegated_holder_not_isolated')
        for value in (scanner_image, holder_image):
            if not isinstance(value, str) or not re.fullmatch('sha256:[0-9a-f]{64}', value):
                raise Blocked('delegated_attestor_image_invalid')
        self.binding = binding; self.target = target
        self.resources = (scanner_id, scanner_image, holder_id, holder_image)
        self.source_root = source_root; self.source_pins = dict(source_pins)
        self.evidence_root = evidence_root
        self.evidence_pins = {k: tuple(v) for k, v in evidence_pins.items()}
        self.replay = replay; self.observe = observe; self.stop = stop
        self.clock = clock; self.monotonic = monotonic; self.epoch = None
        self.latched = False; self.resolution_reserved = False; self.lock = threading.RLock()

    @staticmethod
    def _pinned(root, path, checksum):
        if not isinstance(checksum, str) or not re.fullmatch('[0-9a-f]{64}', checksum):
            raise Blocked('delegated_evidence_pin_invalid')
        try:
            raw = CanaryAuditor.read_file(root, path)
            if hashlib.sha256(raw).hexdigest() != checksum:
                raise ValueError()
            return raw
        except Exception:
            raise Blocked('delegated_evidence_missing_corrupt_or_changed') from None

    def _check(self, binding, target, epoch):
        if (self.latched or binding != self.binding or target != self.target
                or epoch != self.epoch or self.clock() >= binding.expires_at):
            raise Blocked('delegated_binding_epoch_or_expiry_lost')
        for path, checksum in self.source_pins.items():
            self._pinned(self.source_root, path, checksum)
        snapshot = self.observe()
        now = self.monotonic()
        if (not isinstance(snapshot, RuntimeSnapshot) or snapshot.target != target
                or (snapshot.scanner_id, snapshot.scanner_image, snapshot.holder_id, snapshot.holder_image) != self.resources
                or type(snapshot.observed_at) not in (int, float) or not math.isfinite(snapshot.observed_at)
                or not 0 <= now - snapshot.observed_at <= 5):
            raise Blocked('delegated_runtime_drift_or_stale')
        for gate in sorted(GATES):
            refs = self.evidence_pins[gate]
            if not refs:
                raise Blocked('delegated_required_proof_missing')
            blobs = tuple(self._pinned(self.evidence_root, path, checksum) for path, checksum in refs)
            # The replay must consume the actual bytes and return None on
            # verified semantics. Boolean/JSON receipts are explicitly refused.
            if self.replay.verify(gate, blobs, binding=binding, target=target,
                                  epoch=epoch, now=self.clock()) is not None:
                raise Blocked('delegated_replay_return_contract')
        # Replay can take time; repeat cheap deadline/runtime observation before
        # resolving/dispatching. Full source/evidence gets replayed on next call.
        # Re-read pins after replay as well. Evidence/source mutation while a
        # verifier is running must not be admitted on an earlier byte snapshot.
        for path, checksum in self.source_pins.items():
            self._pinned(self.source_root, path, checksum)
        for refs in self.evidence_pins.values():
            for path, checksum in refs:
                self._pinned(self.evidence_root, path, checksum)
        current = self.observe(); now = self.monotonic()
        if (self.clock() >= binding.expires_at or not isinstance(current, RuntimeSnapshot)
                or current.target != target or current.scanner_id != snapshot.scanner_id
                or current.scanner_image != snapshot.scanner_image or current.holder_id != snapshot.holder_id
                or current.holder_image != snapshot.holder_image
                or not 0 <= now - current.observed_at <= 5):
            raise Blocked('delegated_runtime_changed_during_replay')

    def _guard(self, binding, target, epoch):
        try:
            self._check(binding, target, epoch)
            return True
        except Exception:
            self.latched = True
            # Stop callback must target the owned producer. It should schedule
            # bounded stop, never await terminal while holding a dispatch lock.
            try: self.stop()
            except Exception: pass
            raise Blocked('delegated_runtime_admission_lost') from None

    def before_resolve(self, binding, target):
        with self.lock:
            if self.resolution_reserved or self.epoch is not None:
                raise Blocked('delegated_source_no_replay')
            self._guard(binding, target, None)
            # Reserve before I/O; a lost ACK cannot cause source/login replay.
            self.resolution_reserved = True
            return True

    def bind_epoch(self, epoch):
        with self.lock:
            if (self.latched or not self.resolution_reserved or self.epoch is not None
                    or not isinstance(epoch, str) or not re.fullmatch('[0-9a-f]{32}', epoch)):
                raise Blocked('delegated_epoch_bind_refused')
            self.epoch = epoch

    def during_bootstrap(self, binding, target):
        with self.lock:
            if not self.resolution_reserved or self.epoch is not None:
                raise Blocked('delegated_bootstrap_not_ready')
            return self._guard(binding, target, None)

    def before_dispatch(self, binding, target, epoch):
        with self.lock:
            if not self.resolution_reserved or self.epoch is None:
                raise Blocked('delegated_epoch_not_ready')
            return self._guard(binding, target, epoch)


class OperationLedger:
    """Durable intent before start; uncertain ACK permits reconcile/stop only."""
    def __init__(self, journal):
        self.journal = journal; self.lock = threading.RLock()

    def reserve(self, operation_ref, kind):
        if kind not in ('login', 'crawl', 'active') or not re.fullmatch('[a-zA-Z0-9_-]{1,80}', operation_ref):
            raise Blocked('delegated_operation_invalid')
        with self.lock:
            if any(e['kind'] == 'delegated_operation_intent' and e['data']['operationRef'] == operation_ref
                   for e in self.journal.events):
                raise Blocked('delegated_operation_no_replay')
            self.journal.append('delegated_operation_intent', {'operationRef': operation_ref, 'producerKind': kind})

    def acknowledge(self, operation_ref, native_id):
        if not isinstance(native_id, str) or not re.fullmatch('[a-zA-Z0-9_-]{1,128}', native_id):
            raise Blocked('delegated_native_operation_invalid')
        with self.lock:
            intents = [e for e in self.journal.events if e['kind'] == 'delegated_operation_intent'
                       and e['data']['operationRef'] == operation_ref]
            acks = [e for e in self.journal.events if e['kind'] == 'delegated_operation_ack'
                    and e['data']['operationRef'] == operation_ref]
            if len(intents) != 1 or acks:
                raise Blocked('delegated_operation_ack_refused')
            self.journal.append('delegated_operation_ack', {'operationRef': operation_ref, 'nativeId': native_id})
