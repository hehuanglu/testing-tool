"""W10 offline A→B comparison. Only replayed W8/W9 evidence can enter the CLI.

This contract does not reinterpret historical scanner diff v3's `resolved` field.
An active-synthetic exit 0 is a bounded development result, never R1/R2 admission.
"""
from pathlib import Path
import hashlib
import os
import re
import stat

from .contracts import canonical, digest, ROOT
from .evidence import EvidenceInvalid
from .verification import BundleReader, strict_json
from .active_fixture import ORIGIN, RULES
from .active_verification import verify_active_bundle
from .unified_verification import verify_unified_bundle

VERSION = 'assessment_regression/v1'
REQUEST_VERSION = 'assessment_regression_request/v1'
FACETS = ('scope', 'coverage', 'auth', 'policy', 'fixture', 'oracle')
TECHNIQUES = tuple(RULES)


def require(value, reason):
    if not value: raise EvidenceInvalid('regression_' + reason)


def read_document(path):
    """Bounded regular JSON with a stable no-follow file descriptor."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as f:
        before = os.fstat(f.fileno())
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1 and before.st_size <= 1024**2, 'document_type_or_size')
        raw = f.read(1024**2 + 1); after = os.fstat(f.fileno())
        require(len(raw) == before.st_size and (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
                == (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns), 'document_changed')
    return raw, strict_json(raw)


def source_pins():
    # Pin all Python verifier dependencies rather than trusting a result summary.
    result = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted((ROOT / 'src/zap_assessment').rglob('*.py'))}
    for name in ('scripts/w10_regression.py', '../mcp-zap-server/.github/actions/zap-security-gate/mcp_zap_gate.py',
                 '../mcp-zap-server/.github/actions/zap-security-gate/run-assessment-regression.sh'):
        result[name] = hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
    return result


def reference(bundle, pin, manifest_sha=None):
    require(isinstance(pin, str) and re.fullmatch('[0-9a-f]{64}', pin), 'plan_pin')
    if manifest_sha is None:
        with BundleReader(bundle) as reader:
            manifest_sha = hashlib.sha256(reader.read('manifest.json')).hexdigest(); reader.unchanged()
    require(isinstance(manifest_sha, str) and re.fullmatch('[0-9a-f]{64}', manifest_sha), 'manifest_pin')
    return {'bundle': str(Path(bundle).absolute()), 'planSha256': pin, 'manifestSha256': manifest_sha}


def make_request(baseline, current, kind='active', mode='enforce', amendments=None):
    value = {'contractVersion': REQUEST_VERSION, 'kind': kind, 'mode': mode,
             'baseline': baseline, 'current': current, 'requiredTechniques': list(TECHNIQUES),
             'scopeAmendments': amendments or [], 'verifierPins': source_pins(),
             'securityApproval': False, 'R1R2Admission': False}
    validate_request(value); return value


def validate_request(p):
    require(isinstance(p, dict) and set(p) == {'contractVersion', 'kind', 'mode', 'baseline', 'current',
            'requiredTechniques', 'scopeAmendments', 'verifierPins', 'securityApproval', 'R1R2Admission'}, 'request_fields')
    require(p['contractVersion'] == REQUEST_VERSION and p['kind'] in ('active', 'unified') and p['mode'] in ('enforce', 'seed'), 'request_version_or_mode')
    require(p['requiredTechniques'] == list(TECHNIQUES) and p['securityApproval'] is False and p['R1R2Admission'] is False, 'required_scope')
    require(p['verifierPins'] == source_pins(), 'verifier_source_drift')
    for ref in (p['baseline'], p['current']):
        if ref is None: continue
        require(isinstance(ref, dict) and set(ref) == {'bundle', 'planSha256', 'manifestSha256'}, 'reference_fields')
        require(isinstance(ref['bundle'], str) and Path(ref['bundle']).is_absolute(), 'absolute_bundle_path')
        reference(ref['bundle'], ref['planSha256'], ref['manifestSha256'])
    require(p['current'] is not None, 'current_required')
    require(isinstance(p['scopeAmendments'], list), 'amendment_type')
    seen = set()
    for row in p['scopeAmendments']:
        require(isinstance(row, dict) and set(row) == {'contractVersion', 'technique', 'disposition', 'reason'}
                and row['contractVersion'] == 'scope_amendment/v1' and row['technique'] in TECHNIQUES
                and row['technique'] not in seen and row['disposition'] == 'removed-from-attack-surface'
                and isinstance(row['reason'], str) and 1 <= len(row['reason'].strip()) <= 1024, 'amendment_fields')
        seen.add(row['technique'])
    return p


def scanner_inventory(scans, image):
    inventories = []
    for s in scans:
        v = s['before']; addons = v.get('addons')
        if not v.get('version') or v['version'] == 'unknown' or not isinstance(addons, list) or not addons: return None
        rows = []
        for r in addons:
            if not all(isinstance(r.get(k), str) and r[k] and r[k] != 'unknown' for k in ('id', 'version', 'status')): return None
            rows.append({k: r[k] for k in ('id', 'version', 'status')})
        if len({r['id'] for r in rows}) != len(rows): return None
        inventories.append({'image': image, 'version': v['version'], 'addons': sorted(rows, key=lambda r: r['id'])})
    return inventories[0] if inventories and all(v == inventories[0] for v in inventories) else None


def active_view(folder, pin):
    # Outer snapshot spans verification and extraction, preventing post-verify swaps.
    with BundleReader(folder) as reader:
        result = verify_active_bundle(folder, pin)
        p = strict_json(reader.read('plan.json')); f = strict_json(reader.read('fixture.json'))
        o = strict_json(reader.read('observations.json'))
        shape = [{k: v[k] for k in ('technique', 'ruleId', 'method', 'path', 'parameter', 'sink')} for v in f['vectors']]
        policy = []
        for scan in sorted(o['scans'], key=lambda s: s['technique']):
            before = scan['before']
            policy.append({'technique': scan['technique'], 'rules': sorted(before['rules'], key=lambda r: str(r['id'])),
                           'scripts': sorted(before['scripts'], key=lambda r: (r['type'], r['name'])),
                           'proxy': before['proxy'], 'vectors': before['vectors']})
        assertions = [{'technique': r['technique'], 'verified': r['verified'], 'oracleVulnerable': r['oracleVulnerable'],
                       'detected': bool(r['alertIds'])} for r in result['assertions']]
        fidelity_sources = {k: v for k, v in p['sourcePins'].items()
                            if k.endswith(('active_worker.py', 'traffic.py', 'egress.py', 'TrafficProbe.java'))}
        facets = {'scope': {'origin': ORIGIN, 'vectors': shape, 'mode': p['mode'], 'fidelitySources': fidelity_sources},
                  'coverage': [{'technique': r['technique'], 'verified': r['verified']} for r in assertions],
                  'auth': {'mode': 'anonymous', 'continuity': 'not-applicable-owned-anonymous-fixture'},
                  'policy': policy,
                  'fixture': {'source': p['sourcePins']['src/zap_assessment/active_fixture.py'], 'vectors': shape,
                              'rowCount': len(f['names']), 'seedSemantics': 'unique-tagged-first-row-positive-parameter-binding'},
                  'oracle': {'version': p['contractVersion'], 'source': p['sourcePins']['src/zap_assessment/active_verification.py']}}
        view = {'runId': p['runId'], 'build': p['targetBuildHash'], 'planHash': pin,
                'evidenceHash': hashlib.sha256(reader.read('manifest.json')).hexdigest(),
                'scanner': scanner_inventory(o['scans'], p['image']), 'facets': facets,
                'assertions': assertions, 'blockers': []}
        reader.unchanged(); return view


def load_view(ref, kind, side):
    if ref is None: return None
    folder = Path(ref['bundle']); pin = ref['planSha256']
    with BundleReader(folder) as reader:
        manifest_raw = reader.read('manifest.json')
        require(hashlib.sha256(manifest_raw).hexdigest() == ref['manifestSha256'], 'input_manifest_changed')
        manifest = strict_json(manifest_raw)
        if manifest.get('contractVersion') not in ('w8-owned-active-1', 'w9-owned-unified-diagnostic-1'):
            reader.unchanged(); return None  # Historical/unknown coverage never gains vNext semantics.
        if kind == 'active':
            require(manifest['contractVersion'] == 'w8-owned-active-1', 'evidence_kind')
            value = active_view(folder, pin)
        else:
            result = verify_unified_bundle(folder, pin)
            p = strict_json(reader.read('plan.json')); matrix = strict_json(reader.read('track-matrix.json'))
            phase = 'active-vulnerable' if side == 'baseline' else 'active-fixed'
            row = next(r for r in matrix if r['phase'] == phase)
            value = active_view(folder / 'children' / phase, row['childPlanHash'])
            value['parentPlanHash'] = pin
            value['parentEvidenceHash'] = hashlib.sha256(reader.read('manifest.json')).hexdigest()
            value['facets']['scope']['requiredTracks'] = p['requiredTracks']
            value['facets']['scope']['stateModel'] = p['stateModel']
            value['facets']['auth']['businessEpochPolicy'] = p['epochPolicy']
            value['facets']['auth']['businessContinuity'] = 'replayed-child-identity-epoch-and-parent-bindings'
            value['facets']['fixture']['businessAdapter'] = p['adapter']
            value['facets']['coverage'] = {'active': value['facets']['coverage'], 'missing': result['missingRequiredTracks'],
                                         'failed': result['failedFunctionalTracks']}
            value['blockers'] = ['unified-operational-unverified']
            for r in matrix:
                if r['phase'] in ('session', 'api', 'ui') and r['result']['securityVerdict'] == 'fail':
                    value['blockers'].append('observed-security-failure:' + r['phase'])
        reader.unchanged(); return value


def compare_views(a, b, mode='enforce', amendments=()):
    """Pure decision core; CLI callers cannot supply these normalized views."""
    reasons = []; removed = []; fixed = []; unchanged = []; added = []
    if a is None: reasons.append('baseline_absent_or_legacy_coverage')
    if b is None: reasons.append('current_legacy_coverage')
    aa = {r['technique']: r for r in a['assertions']} if a else {}
    bb = {r['technique']: r for r in b['assertions']} if b else {}
    if a and b:
        if not a.get('scanner') or not b.get('scanner') or a['scanner'] != b['scanner']: reasons.append('scanner')
        for key in FACETS:
            if key not in a['facets'] or key not in b['facets'] or a['facets'][key] != b['facets'][key]: reasons.append(key)
        if not a.get('build') or not b.get('build'): reasons.append('build_pin_missing')
        if a['runId'] == b['runId']: reasons.append('same_run_reused')
    if set(aa) != set(TECHNIQUES) or set(bb) != set(TECHNIQUES): reasons.append('required_assertions_missing')
    if any(r.get('verified') is not True for r in [*aa.values(), *bb.values()]): reasons.append('equivalent_exercise_unproven')
    for t in TECHNIQUES:
        ar, br = aa.get(t), bb.get(t)
        if ar and br and ar['detected'] and not br['detected']: removed.append(t)
        if br and br['detected'] and (not ar or not ar['detected']): added.append(t)
        if br and br['oracleVulnerable'] is True: unchanged.append(t)
    if amendments: reasons.append('versioned_scope_amendment_requires_review')
    scanner_status = ('unknown' if not a or not b or not a.get('scanner') or not b.get('scanner')
                      else 'matching' if a['scanner'] == b['scanner'] else 'different')
    comparable = not reasons
    if comparable and mode == 'enforce':
        fixed = [t for t in TECHNIQUES if aa[t]['oracleVulnerable'] is True and bb[t]['oracleVulnerable'] is False
                 and aa[t]['detected'] and not bb[t]['detected']]
    blockers = sorted(set((a or {}).get('blockers', []) + (b or {}).get('blockers', [])))
    security_fail = bool(unchanged or any(r['detected'] for r in bb.values()) or any(x.startswith('observed-security-failure:') or x == 'browser-secret-failure' for x in blockers))
    if mode == 'seed': code = 3; decision = 'review_required'; fixed = []
    elif security_fail: code = 1; decision = 'block'
    elif not comparable or blockers or len(fixed) != len(TECHNIQUES): code = 2; decision = 'block'
    else: code = 0; decision = 'allow-synthetic'
    return {'contractVersion': VERSION, 'mode': mode, 'comparable': comparable, 'comparabilityReasons': reasons,
            'scannerComparison': {'status': scanner_status},
            'comparisons': {k: 'incomparable' if k in reasons or not a or not b else 'matching' for k in FACETS},
            'observedRemoved': removed, 'observedAdded': added, 'remediationVerified': fixed,
            'remediationScope': 'selected-anonymous-active-techniques',
            'vulnerabilityPresent': unchanged, 'scopeDispositions': list(amendments), 'requiredTechniques': list(TECHNIQUES),
            'targetBuilds': {'A': (a or {}).get('build'), 'B': (b or {}).get('build')},
            'inputs': {'A': {k: a[k] for k in ('planHash', 'evidenceHash', 'runId')} if a else None,
                       'B': {k: b[k] for k in ('planHash', 'evidenceHash', 'runId')} if b else None},
            'blockers': blockers, 'securityVerdict': 'fail' if security_fail else 'inconclusive',
            'gateDecision': decision, 'exitCode': code,
            'G11Synthetic': 'pass' if code == 0 else 'blocked', 'R1R2Admission': False, 'securityApproval': False}


def compare_request(path, expected_sha):
    raw, p = read_document(path)
    require(isinstance(expected_sha, str) and re.fullmatch('[0-9a-f]{64}', expected_sha)
            and hashlib.sha256(raw).hexdigest() == expected_sha and raw == canonical(p), 'external_request_pin')
    validate_request(p)
    a = load_view(p['baseline'], p['kind'], 'baseline'); b = load_view(p['current'], p['kind'], 'current')
    result = compare_views(a, b, p['mode'], p['scopeAmendments'])
    require(source_pins() == p['verifierPins'], 'verifier_changed_during_compare')
    return {'requestSha256': expected_sha, 'kind': p['kind'], **result}
