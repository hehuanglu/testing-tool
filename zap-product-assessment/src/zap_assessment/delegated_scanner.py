"""MCP scanner integration candidate; no provisioning or P0 admission override.

Reuses real schema discovery, scoped operation IDs, chunks/EOF/UTF8 readback and
the durable no-replay ledger. The isolated runtime must supply actual policy,
identity/traffic attribution and operational gate replay. This is not an entry
that accepts an arbitrary product URL/credentials.
"""
import hashlib

from .delegated_attestation import OperationLedger
from .evidence import read_report
from .errors import Blocked
from .transport import Scanner, field


class DelegatedScanner(Scanner):
    def __init__(self, mcp, engine, request, *, ledger, admit, policy_name):
        super().__init__(mcp, engine, request)
        if not isinstance(ledger, OperationLedger) or not callable(admit) or policy_name != 'delegated-finalsource-query-1':
            raise Blocked('delegated_scanner_contract_invalid')
        self.ledger = ledger; self.admit = admit; self.policy_name = policy_name
        self.owned_operations = {}

    def start(self, kind, url):
        raise Blocked('delegated_scanner_explicit_operation_reference_required')

    def seed(self, url):
        if self.admit('seed', url) is not True:
            raise Blocked('delegated_scanner_seed_admission_lost')
        return super().seed(url)

    def start_once(self, operation_ref, kind, url):
        if kind not in ('crawl', 'active'):
            raise Blocked('delegated_scanner_kind_invalid')
        # admit must replay holder/identity/policy/resource and validate exact URL.
        if self.admit(kind, url) is not True:
            raise Blocked('delegated_scanner_admission_lost')
        self.ledger.reserve(operation_ref, kind)
        tool = 'zap_crawl_start' if kind == 'crawl' else 'zap_attack_start'
        args = {'targetUrl': url, **({'strategy': 'http'} if kind == 'crawl' else
                {'recurse': 'false', 'policy': self.policy_name})}
        # No exception/retry loop: a missing ACK is an unresolved durable intent.
        text = self.mcp.call(tool, args)
        if field(text, 'Execution Mode').lower() != 'direct':
            raise Blocked('delegated_scanner_queue_not_admitted')
        native_id = field(text, 'Operation ID')
        self.ledger.acknowledge(operation_ref, native_id)
        self.owned_operations[native_id] = kind
        return native_id

    def stop(self, kind, op):
        if self.owned_operations.get(op) != kind:
            raise Blocked('delegated_scanner_stop_ownership_missing')
        return super().stop(kind, op)

    def status(self, kind, op):
        if self.owned_operations.get(op) != kind:
            raise Blocked('delegated_scanner_operation_ownership_missing')
        return super().status(kind, op)

    def report_readback(self, origin, *, max_bytes=8 * 1024 * 1024):
        if self.admit('report', origin) is not True:
            raise Blocked('delegated_scanner_report_admission_lost')
        if (not self.owned_operations or not all(self.status(kind, op) for op, kind in self.owned_operations.items())
                or not self.passive()):
            raise Blocked('delegated_scanner_producer_or_passive_not_terminal')
        output = {}
        for format_name in ('json', 'html'):
            text = self.mcp.call('zap_report_generate', {'format': format_name, 'baseUrl': origin})
            path = field(text, 'Path')
            pages_before = len(getattr(self, 'chunk_observations', []))
            def bounded_chunk(path, offset, sha):
                if self.admit('report-chunk', origin) is not True:
                    raise Blocked('delegated_scanner_report_admission_lost')
                return self.chunk(path, offset, sha)
            raw = read_report(bounded_chunk, path, max_bytes)
            output[format_name] = {'bytes': raw, 'sha256': hashlib.sha256(raw).hexdigest(),
                                   'chunks': self.chunk_observations[pages_before:]}
        # Caller must audit all original bytes in holder before public export.
        return output
