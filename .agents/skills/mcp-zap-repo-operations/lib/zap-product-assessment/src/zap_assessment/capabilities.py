"""Versioned capability claims and conservative P0 admission, entirely offline.

The registry describes evidence; it never grants authority. W3 implements no
runtime gate attestor. Existing v1 entry contracts remain their own admission path.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import stat
import sys
from jsonschema import Draft202012Validator, FormatChecker
from .contracts import Blocked, ROOT

WORKSPACE = ROOT.parent
REGISTRY = ROOT/'profiles/capability-registry.json'
INVENTORY = ROOT/'profiles/secret-sink-inventory.json'
SUMMARY = ROOT/'docs/remediation/CAPABILITIES_GENERATED.md'
P0_MODES = {'native':'p0-native', 'delegated':'p0-delegated', 'business':'p0-business'}
BLOCKED_CAPABILITIES = frozenset((*P0_MODES.values(), 'browser-e2e', 'canonical-origin', 'shared-ha'))
from .secret_inventory import SINKS, LIFECYCLE, ENCODINGS
CAPABILITIES = frozenset(('verification-v2','anonymous-http','bola-account-read',*BLOCKED_CAPABILITIES))


def _object(pairs):
    result={}
    for key,value in pairs:
        if key in result: raise Blocked('duplicate registry JSON key')
        result[key]=value
    return result


def _json(blob):
    try:
        return json.loads(blob,object_pairs_hook=_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(Blocked('nonfinite registry JSON')))
    except (ValueError,UnicodeError) as exc: raise Blocked('invalid registry JSON') from exc


def _read_relative(path):
    """No-follow each component; bounded regular files; errors contain no values."""
    parts=PurePosixPath(path).parts
    if (not isinstance(path,str) or not parts or path.startswith('/') or '\\' in path
            or any(p in ('.','..') for p in parts) or '/'.join(parts)!=path):
        raise Blocked('unsafe registry reference')
    if any(p.startswith('.') or p in ('private','credentials','runs') for p in parts):
        raise Blocked('secret or runtime source reference refused')
    fd=None
    try:
        fd=os.open(WORKSPACE,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        for part in parts[:-1]:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd)
            os.close(fd);fd=next_fd
        file_fd=os.open(parts[-1],os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        with os.fdopen(file_fd,'rb') as stream:
            s=os.fstat(stream.fileno())
            if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>4*1024*1024:
                raise Blocked('unreadable registry reference')
            content=stream.read(4*1024*1024+1);after=os.fstat(stream.fileno())
            if len(content)!=s.st_size or (s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)!=(after.st_ino,after.st_size,after.st_mtime_ns,after.st_ctime_ns):
                raise Blocked('registry reference changed during read')
            return content
    except OSError as exc: raise Blocked('unreadable registry reference') from exc
    finally:
        if fd is not None:os.close(fd)


def _validate(kind,value):
    schema=_json((ROOT/'schemas/remediation'/f'{kind}.schema.json').read_bytes())
    if list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(value)):
        raise Blocked('invalid '+kind+' contract')


def validate_registry(value, *, readback=False):
    _validate('capability-registry',value)
    caps=value['capabilities'];refs=value['references']
    if {c['capabilityId'] for c in caps}!=CAPABILITIES or len(caps)!=len(CAPABILITIES):
        raise Blocked('missing or duplicate capability')
    ids={r['referenceId'] for r in refs}
    if len(ids)!=len(refs):raise Blocked('duplicate capability reference')
    by_ref={r['referenceId']:r for r in refs}
    for ref in refs:
        # References may name source or historical metadata only, never raw responses.
        path=ref['path']
        allowed = path.startswith(('zap-product-assessment/src/','zap-product-assessment/scripts/',
                                  'zap-product-assessment/docs/remediation/','mcp-zap-server/docs/scanning/'))
        metadata={'credential-audit.json','manifest.json','acceptance.json','binding-acceptance.json','verification.json','pilot-final.json',
                  'gate-results.json','source-final.json','historical-p0-readback.json','legacy-readback.json','runtime-inventory.json'}
        allowed |= path.startswith(('test-artifacts/','zap-product-assessment/docs/evidence/')) and PurePosixPath(path).name in metadata
        if not allowed:raise Blocked('non-metadata capability reference')
        if path.startswith('/') or '\\' in path or any(p.startswith('.') for p in PurePosixPath(path).parts):
            raise Blocked('unsafe registry reference')
        if readback and hashlib.sha256(_read_relative(path)).hexdigest()!=ref['sha256']:
            raise Blocked('capability reference hash drift')
    used=set()
    for cap in caps:
        if not set(cap['evidenceRefs'])<=ids or not cap['evidenceRefs']:
            raise Blocked('missing capability evidence reference')
        used.update(cap['evidenceRefs'])
        expected_policy = ('offline-only' if cap['capabilityId']=='verification-v2'
                           else 'existing-contract' if cap['capabilityId'] in {'anonymous-http','bola-account-read'}
                           else 'blocked')
        if cap['executionPolicy']!=expected_policy or cap['gateStatus']!=expected_policy:
            raise Blocked('capability policy exceeds implemented admission contract')
        if cap['capabilityId'] in BLOCKED_CAPABILITIES:
            if cap['executionPolicy']!='blocked' or cap['gateStatus']!='blocked':
                raise Blocked('runtime gate attestor not implemented for candidate mode')
        if cap['evidenceLevel']=='pilot-verified' and not any(by_ref[r]['classification']=='historical-pilot' for r in cap['evidenceRefs']):
            raise Blocked('pilot claim missing historical evidence')
        if cap['executionPolicy']=='existing-contract' and cap['capabilityId'] not in {'anonymous-http','bola-account-read'}:
            raise Blocked('only existing versioned entry contracts can admit live work')
        if cap['capabilityId']=='verification-v2' and cap['executionPolicy']!='offline-only':
            raise Blocked('v2 publication/runtime not enabled')
    if used!=ids:raise Blocked('orphan capability reference')
    return value


def load_registry():
    return validate_registry(_json(REGISTRY.read_bytes()))


def require_p0_mode(mode):
    """Fail before credential resolution, receipt reads, output or Docker access.

    A future mode implementation must supply a real contract-specific runtime
    attestor; changing data in a registry cannot supply that implementation.
    """
    if not isinstance(mode,str) or mode not in P0_MODES:raise Blocked('unknown P0 mode')
    # Fixed execution ceiling independent of registry labels and working directory.
    raise Blocked('W3 mode blocked: '+P0_MODES[mode]+'; G3/G4/G5/G6 proof required')


def check_readiness(value):
    _validate('secret-sink-inventory',value)
    sinks=value['sinks']
    if {s['sinkId'] for s in sinks}!=SINKS or len(sinks)!=len(SINKS):
        raise Blocked('missing or duplicate secret sink')
    if set(value['requiredLifecycle'])!=LIFECYCLE or len(value['requiredLifecycle'])!=len(LIFECYCLE):
        raise Blocked('missing lifecycle case')
    if set(value['encodings'])!=ENCODINGS or len(value['encodings'])!=len(ENCODINGS):
        raise Blocked('encoding inventory incomplete')
    if {m['mode'] for m in value['modes']}!={'native','delegated','browser','business'} or len(value['modes'])!=4:
        raise Blocked('secret mode inventory incomplete')
    for s in sinks:
        if set(s['requiredFor'])!={'native','delegated','browser','business'}:
            raise Blocked('sink mode omitted without a locked contract')
    missing=[{'sinkId':s['sinkId'],'reason':'access_and_seeded_control_and_lifecycle_unproven'} for s in sinks]
    return {'inventoryStatus':'pass','g3Status':'blocked','sinkCount':len(sinks),
            'lifecycleCount':len(LIFECYCLE),'encodingCount':len(ENCODINGS),
            'operationalModesEnabled':[],'missingProof':missing,
            'limitation':'Readiness only; no sink access, secret resolution or canary audit performed'}


def render_summary(registry):
    lines=['# Capability registry — generated snapshot','',
           'Generated by `python -m zap_assessment.capabilities summary`; edit the registry, then regenerate.',
           '', 'Registry data grants no authority. Historical proof does not attest the current runtime.', '']
    refs={r['referenceId']:r for r in registry['references']}
    for cap in registry['capabilities']:
        lines += ['## '+cap['capabilityId'],'',
                  f"{cap['evidenceLevel']}; execution: {cap['executionPolicy']}; gate: {cap['gateStatus']}; contract: {cap['contractVersion']}.",
                  '',cap['scope'],'', 'Limits: '+cap['limitations'], '', 'Known failures: '+ '; '.join(cap['knownFailures']), '',
                  'Pins: '+cap['sourceImagePins'], '', 'Evidence: '+', '.join(
                      '['+r+'](../../..'+'/'+refs[r]['path']+')' for r in cap['evidenceRefs']), '']
    return '\n'.join(lines)+'\n'


def check():
    r=validate_registry(load_registry(),readback=True)
    readiness=check_readiness(_json(INVENTORY.read_bytes()))
    if SUMMARY.read_text()!=render_summary(r):raise Blocked('generated capability summary drift')
    return {'registryStatus':'pass','capabilityCount':len(r['capabilities']),
            'referenceCount':len(r['references']),**readiness,'securityApproval':False,'targetRequests':0}


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['check','summary']);args=p.parse_args(argv)
    try:
        if args.command=='summary':sys.stdout.write(render_summary(load_registry()))
        else:print(json.dumps(check(),ensure_ascii=False,indent=2))
        return 0
    except (Blocked,OSError):
        print(json.dumps({'registryStatus':'blocked','gateDecision':'block','reason':'registry, reference, inventory or summary invalid','securityApproval':False}));return 2

if __name__=='__main__':sys.exit(main())
