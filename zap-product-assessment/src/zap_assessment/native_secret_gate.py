"""Private native sink collection and semantic G3 replay, not JSON admission.

Raw history/JDBC streams and source values stay in the isolated caller. The
collector reads actual API pages; the replayer recomputes controls and zero cases
from those bytes. Current collectors cover history/session, not all 143 pairs.
No product or platform acceptance follows from diagnostic samples.
"""
from dataclasses import dataclass
import base64
import json
import math
import re
import threading
import time

from .delegated_attestation import ProofReplay
from .errors import Blocked, SecretLeak
from .private_db import strict_json, control_forms
from .scanner_secret_audit import audit_database
from .secret_audit import CanaryAuditor
from .secret_inventory import SINKS, LIFECYCLE
from .credential_broker import BrokerBinding
from .finalsource_delegated import TargetBinding

MAX = 8 * 1024 * 1024
SQL_TYPES = frozenset((-7,-6,-5,-4,-3,-2,-1,0,1,2,3,4,5,6,7,8,12,16,91,92,93,
                       2004,2005,2011,-9,-15,-16,2013,2014))
REASON_CODES=frozenset('native_'+s for s in (
    'sink_byte_budget','history_count_invalid','history_snapshot_required',
    'history_changed_during_collection','history_inventory_budget','history_byte_budget',
    'history_page_invalid','history_message_or_identity_invalid','history_total_or_eof_mismatch',
    'history_collection_contract','history_collection_deadline','history_page_nonprogress',
    'db_stream_budget','db_record_after_terminal','db_table_invalid','db_cell_or_type_invalid',
    'db_duplicate_cell','db_cell_encoding_invalid','db_terminal_invalid','db_format_unsupported',
    'db_incomplete','zero_case_has_no_requests','history_forbidden_match','history_positive_missed',
    'g3_private_inventory_invalid','g3_binding_or_freshness_invalid','g3_duplicate_pair',
    'g3_wrong_gate_or_reference','g3_actual_sink_matrix_incomplete','g3_product_source_acceptance_absent'))


class HistoryShapeIssue(Blocked):
    """Only fixed field names/type enums, never a native value or ID."""
    def __init__(self,row,ids):
        super().__init__('native_history_message_or_identity_invalid')
        fields=('id','requestHeader','requestBody','responseHeader','responseBody')
        self.shape={k:type(row[k]).__name__ if isinstance(row,dict) and k in row else 'missing' for k in fields}
        value=row.get('id') if isinstance(row,dict) else None
        self.shape['idRepeated']=isinstance(value,str) and value in ids
        self.shape['idPositiveDecimal']=isinstance(value,str) and bool(re.fullmatch('[1-9][0-9]*',value))


def encode(value):
    raw = json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()
    if len(raw) > MAX:
        raise Blocked('native_sink_byte_budget')
    return raw


def count_value(value):
    if type(value) is int and value >= 0:
        return value
    if isinstance(value, str) and re.fullmatch('0|[1-9][0-9]*', value):
        return int(value)
    raise Blocked('native_history_count_invalid')


@dataclass(frozen=True, repr=False)
class NativeHistory:
    before: bytes
    pages: tuple
    eof: bytes
    after: bytes

    def __repr__(self): return '<NativeHistory private>'


def history_rows(snapshot):
    if not isinstance(snapshot, NativeHistory):
        raise Blocked('native_history_snapshot_required')
    before = strict_json(snapshot.before); after = strict_json(snapshot.after)
    if (set(before) != {'numberOfMessages'} or set(after) != {'numberOfMessages'}
            or count_value(before['numberOfMessages']) != count_value(after['numberOfMessages'])):
        raise Blocked('native_history_changed_during_collection')
    total = count_value(before['numberOfMessages']); rows = []; ids = set(); size = 0
    if total > 100000 or not isinstance(snapshot.pages, tuple):
        raise Blocked('native_history_inventory_budget')
    for raw in snapshot.pages:
        size += len(raw)
        if size > MAX: raise Blocked('native_history_byte_budget')
        page = strict_json(raw)
        if set(page) != {'messages'} or not isinstance(page['messages'], list) or not page['messages']:
            raise Blocked('native_history_page_invalid')
        for row in page['messages']:
            if (not isinstance(row, dict) or not isinstance(row.get('id'), str)
                    or not re.fullmatch('[1-9][0-9]*', row['id']) or row['id'] in ids
                    or any(not isinstance(row.get(k), str) for k in
                           ('requestHeader','requestBody','responseHeader','responseBody'))):
                raise HistoryShapeIssue(row,ids)
            ids.add(row['id']); rows.append(row)
    if strict_json(snapshot.eof) != {'messages': []} or len(rows) != total:
        raise Blocked('native_history_total_or_eof_mismatch')
    return rows


def collect_history(engine, *, page_size=100, clock=time.monotonic, timeout=8):
    if type(page_size) is not int or not 1 <= page_size <= 1000 or not 0 < timeout <= 8:
        raise Blocked('native_history_collection_contract')
    began = clock(); before = engine('core','view','numberOfMessages', {})
    if not isinstance(before, dict) or set(before) != {'numberOfMessages'}:
        raise Blocked('native_history_count_invalid')
    total = count_value(before['numberOfMessages'])
    if total > 100000: raise Blocked('native_history_inventory_budget')
    pages = []; offset = 0; size = 0
    while offset < total:
        if clock() - began > timeout: raise Blocked('native_history_collection_deadline')
        # CoreAPI 2.17 PaginationConstraintsChecker counts positive starts from
        # one. Using zero-based offset2 as start2 repeats the last row of page1.
        page = engine('core','view','messages', {'start': str(offset+1), 'count': str(min(page_size,total-offset))})
        raw = encode(page); size += len(raw)
        if size > MAX or not isinstance(page, dict) or set(page) != {'messages'}:
            raise Blocked('native_history_page_invalid')
        rows = page['messages']
        if not isinstance(rows,list) or not 1 <= len(rows) <= min(page_size,total-offset):
            raise Blocked('native_history_page_nonprogress')
        pages.append(raw); offset += len(rows)
    eof = engine('core','view','messages', {'start': str(total+1), 'count': '1'})
    after = engine('core','view','numberOfMessages', {})
    if not 0 <= clock()-began <= timeout: raise Blocked('native_history_collection_deadline')
    snapshot = NativeHistory(encode(before), tuple(pages), encode(eof), encode(after))
    history_rows(snapshot)
    return snapshot


def strict_database(raw):
    """Typed framing checks additional to the existing all-table JDBC auditor."""
    if not isinstance(raw, bytes) or not raw or len(raw) > MAX:
        raise Blocked('native_db_stream_budget')
    tables = set(); cells = set(); complete = None
    for line in raw.splitlines():
        row = strict_json(line)
        if not isinstance(row,dict) or complete is not None:
            raise Blocked('native_db_record_after_terminal')
        kind = row.get('kind')
        if kind == 'table':
            if (set(row) != {'kind','name'} or not isinstance(row['name'],str)
                    or not re.fullmatch('[A-Z0-9_]{1,256}',row['name']) or row['name'] in tables):
                raise Blocked('native_db_table_invalid')
            tables.add(row['name'])
        elif kind == 'cell':
            if (set(row) != {'kind','table','row','column','sqlType','base64'}
                    or row['table'] not in tables or type(row['row']) is not int or row['row'] < 1
                    or not isinstance(row['column'],str) or not re.fullmatch('[A-Za-z0-9_]{1,256}',row['column'])
                    or type(row['sqlType']) is not int or row['sqlType'] not in SQL_TYPES):
                raise Blocked('native_db_cell_or_type_invalid')
            key = (row['table'],row['row'],row['column'])
            if key in cells: raise Blocked('native_db_duplicate_cell')
            cells.add(key)
            try: base64.b64decode(row['base64'],validate=True)
            except Exception: raise Blocked('native_db_cell_encoding_invalid') from None
        elif kind == 'complete':
            if (set(row) != {'kind','tables','rows','cells','decodedBytes'}
                    or any(type(row[k]) is not int or row[k] < 0 for k in ('tables','rows','cells','decodedBytes'))):
                raise Blocked('native_db_terminal_invalid')
            complete = row
        else: raise Blocked('native_db_format_unsupported')
    if (complete is None or not tables or 'HISTORY' not in tables
            or len(cells) != complete['cells'] or len(tables) != complete['tables']
            or any(key[1] > complete['rows'] for key in cells)):
        raise Blocked('native_db_incomplete')


def audit_zero(history, database, auditor):
    rows = history_rows(history)
    if not rows: raise Blocked('native_zero_case_has_no_requests')
    for row in rows:
        if auditor.matches(encode(row)):
            raise SecretLeak('native_history_forbidden_match')
    strict_database(database)
    db = audit_database(auditor, database)
    return {'historyMessages':len(rows), 'historyForbiddenMatches':0,
            'database':db, 'rawValuesIncluded':False}


def audit_positive(history, database, secret):
    from .live_sink_probe import header_seed, inspect_history_control
    rows = history_rows(history); forms = control_forms(secret); auditor = CanaryAuditor([secret]); found=[]
    for encoding, form in forms.items():
        matches = [r for r in rows if header_seed(r['requestHeader'].encode()) == form]
        if not matches or not all(auditor.matches(encode(r)) for r in matches):
            raise Blocked('native_history_positive_missed')
        found.append({'encoding':encoding,'detected':True,'occurrences':len(matches)})
    strict_database(database)
    db = inspect_history_control(database, secret)
    return {'historyMessages':len(rows),'historyControls':found,'database':db,'rawValuesIncluded':False}


@dataclass(frozen=True, repr=False)
class NativePair:
    lifecycle: str
    binding: object
    target: object
    epoch: object
    source_kind: str
    zero_history: NativeHistory
    zero_database: bytes
    positive_history: NativeHistory
    positive_database: bytes
    collected_at: float
    expires_at: float

    def __repr__(self): return '<NativePair private>'


class NativeG3Replay(ProofReplay):
    """Concrete private-byte replay for history/session pairs in a larger gate.

    Never deserialize pairs or a secret from controller evidence. Only the
    trusted isolated collector can install them. Matrix completeness is computed
    from replayed samples, not supplied statuses. Other sinks/providers remain
    missing; this implementation does not claim platform acceptance.
    """
    def __init__(self, *, secret, pairs):
        if not isinstance(secret,str) or len(secret)<12 or not isinstance(pairs,tuple):
            raise Blocked('native_g3_private_inventory_invalid')
        self._secret=secret; self._pairs=pairs; self._lock=threading.RLock()

    def inspect(self, *, binding, target, epoch, now):
        with self._lock:
            if (not isinstance(binding,BrokerBinding) or not isinstance(target,TargetBinding)
                    or type(now) not in (int,float) or not math.isfinite(now)):
                raise Blocked('native_g3_binding_or_freshness_invalid')
            seen=set(); summaries=[]
            for pair in self._pairs:
                if (not isinstance(pair,NativePair) or pair.lifecycle not in LIFECYCLE
                        or pair.binding != binding or pair.target != target or pair.epoch != epoch
                        or pair.source_kind != 'owned-native-canary'
                        or any(type(t) not in (int,float) or not math.isfinite(t)
                               for t in (pair.collected_at,pair.expires_at))
                        or pair.expires_at > binding.expires_at
                        or not pair.collected_at <= now < pair.expires_at):
                    raise Blocked('native_g3_binding_or_freshness_invalid')
                keys={(s,pair.lifecycle) for s in ('zap-history','zap-session-db')}
                if seen & keys: raise Blocked('native_g3_duplicate_pair')
                zero=audit_zero(pair.zero_history,pair.zero_database,CanaryAuditor([self._secret]))
                positive=audit_positive(pair.positive_history,pair.positive_database,self._secret)
                seen.update(keys);summaries.append({'lifecycle':pair.lifecycle,'zero':zero,'positive':positive})
            required={(s,l) for s in SINKS for l in LIFECYCLE}
            return {'contract':'private-native-g3-replay/1.0','requiredPairs':len(required),
                    'nativePairsReplayed':len(seen),'missingPairs':[{'sinkId':s,'lifecycle':l} for s,l in sorted(required-seen)],
                    'samples':summaries,'sourceValuesIncluded':False,'platformAcceptance':False}

    def verify(self, gate, evidence, *, binding, target, epoch, now):
        if gate != 'G3' or evidence != (b'private-native-g3-replay/1.0',):
            raise Blocked('native_g3_wrong_gate_or_reference')
        result=self.inspect(binding=binding,target=target,epoch=epoch,now=now)
        if result['missingPairs']:
            raise Blocked('native_g3_actual_sink_matrix_incomplete')
        # Current source kind is diagnostic. Product source/collector acceptance
        # is separate; an owned fixture cannot admit a product binding.
        raise Blocked('native_g3_product_source_acceptance_absent')
