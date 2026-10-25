"""Comparison metadata for the fixed W5 synthetic canary family.

The source runtime generates hex64 seeds and W5-canary-<hex64> values. Only
SHA-256/length pairs leave that runtime. This is not a generic password oracle,
credential resolver or operational secret gate.
"""
import base64
import hashlib
import re
from collections import Counter

from .secret_audit import CanaryAuditor

# Public, deliberately noncredential JDBC reader control. It does not replace
# seeded controls using actual source canaries in each operational sink.
PUBLIC_DB_CONTROL='W5-canary-'+''.join('0' for _ in range(64))


def fingerprints(canaries):
    forms=set()
    for value in canaries:
        raw=value.encode()
        if not re.fullmatch(rb'(?:[0-9a-f]{64}|W5-canary-[0-9a-f]{64})',raw):
            raise ValueError('unsupported opaque canary family')
        forms.add(raw)
        forms.update((base64.b64encode(raw),base64.b64encode(raw).rstrip(b'='),
                      base64.urlsafe_b64encode(raw),base64.urlsafe_b64encode(raw).rstrip(b'=')))
    return [{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for raw in sorted(forms)]


class FingerprintPattern:
    # The prefixes/alphabet here are public canary FORMAT, never seed material.
    # Lookahead also detects a canary embedded in a larger encoded string.
    candidates=tuple(re.compile(pattern) for pattern in (
        rb'(?=([0-9a-f]{64}))',
        rb'(?=(W5-canary-[0-9a-f]{64}))',
        rb'(?=([MNOYZ][A-Za-z0-9+/_-]{85}(?:==)?))',
        rb'(?=(VzUtY2FuYXJ5[A-Za-z0-9+/_-]{87}=?))'))

    def __init__(self,rows):
        if not isinstance(rows,list) or not rows or len(rows)>1024:raise ValueError('opaque inventory invalid')
        values=set()
        for row in rows:
            if (not isinstance(row,dict) or set(row)!={'bytes','sha256'}
                    or type(row['bytes']) is not int or row['bytes'] not in (64,74,86,88,99,100)
                    or not isinstance(row['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',row['sha256'])):
                raise ValueError('opaque fingerprint invalid')
            values.add((row['bytes'],row['sha256']))
        if len(values)!=len(rows):raise ValueError('duplicate opaque fingerprint')
        self.values=values

    def search(self,view):
        for pattern in self.candidates:
            for match in pattern.finditer(view):
                raw=match[1]
                if (len(raw),hashlib.sha256(raw).hexdigest()) in self.values:return True
        return False


class OpaqueCanaryAuditor(CanaryAuditor):
    """Reuse the same bounded encoding transforms without any raw secret."""
    def __init__(self,rows):self._pattern=FingerprintPattern(rows)


def validate_source_boundary(value, *, source_kind='owned-guard-memory-generated'):
    if source_kind not in ('owned-guard-memory-generated','owned-guard-private-file-reference'):
        raise ValueError('unsupported private source kind')
    if (not isinstance(value,dict) or set(value)!={'fingerprints','controls','sourceValuesIncluded','sourceKind'}
            or value['sourceValuesIncluded'] is not False or value['sourceKind']!=source_kind):
        raise ValueError('private source receipt invalid')
    controls=value['controls']
    if (not isinstance(controls,dict) or set(controls)!={'tested','detected','missed','encodingSteps','maxDecodedViewsPerStep','scope'}
            or controls['tested']!=816 or controls['detected']!=816 or controls['missed']!=0
            or controls['encodingSteps']!=2 or controls['maxDecodedViewsPerStep']!=128):
        raise ValueError('private source controls incomplete')
    OpaqueCanaryAuditor(value['fingerprints'])
    if Counter(row['bytes'] for row in value['fingerprints'])!={64:1,74:67,86:1,88:1,99:67,100:67}:
        raise ValueError('private source comparison inventory incomplete')


def source_controls(canaries):
    """Runs only inside the allowed source runtime; exports counts, no values."""
    from urllib.parse import quote
    import json
    rows=fingerprints(canaries);auditor=OpaqueCanaryAuditor(rows);tested=missed=0
    for value in canaries:
        raw=value.encode()
        forms=[raw,base64.b64encode(raw),base64.urlsafe_b64encode(raw),
            base64.b64encode(raw).rstrip(b'='),base64.urlsafe_b64encode(raw).rstrip(b'='),
            quote(value,safe='').encode(),b''.join(('%%%02X'%b).encode() for b in raw),
            b''.join(('%%%02x'%b).encode() for b in raw),
            json.dumps(value).encode(),b''.join(('\\u%04x'%b).encode() for b in raw),
            quote(base64.b64encode(raw).decode(),safe='').encode(),
            b'embedded-prefix:'+base64.b64encode(raw).rstrip(b'=')+b':suffix']
        for blob in forms:
            tested+=1;missed+=not auditor.matches(blob)
    if missed:raise ValueError('opaque source controls missed')
    return {'fingerprints':rows,'controls':{'tested':tested,'detected':tested,'missed':missed,
        'encodingSteps':2,'maxDecodedViewsPerStep':128,
        'scope':'private source canary comparisons; not per-sink operational controls'},
        'sourceValuesIncluded':False,'sourceKind':'owned-guard-memory-generated'}
