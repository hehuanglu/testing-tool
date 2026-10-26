#!/usr/bin/env python3
"""Pinned offline W11 conformance/handoff; no authority or independent approval."""
from itertools import combinations
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from zap_assessment.contracts import canonical
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.verification import BundleReader, strict_json
from zap_assessment.business_verification import verify_business_bundle
from zap_assessment.unified_verification import verify_unified_bundle
from zap_assessment.regression import reference, read_document, compare_request
from zap_assessment.safety_io import atomic_bytes
from w6_business_campaign import source_pins as business_pins
from w9_unified_campaign import source_pins as unified_pins

VERSION = 'w11-conformance-handoff/v1'
ROLES = ('primary', 'alternate', 'repeat', 'unified')


def require(value, reason):
    if not value: raise EvidenceInvalid('acceptance_' + reason)


def sha(raw): return hashlib.sha256(raw).hexdigest()


def source_pins():
    result = unified_pins()
    for name in ('scripts/w11_acceptance.py', 'scripts/w10_regression.py'):
        result[name] = sha((ROOT / name).read_bytes())
    return result


def generalization(views):
    """Decide from verified wire facts, never the adapter name alone."""
    if len(views) != 3: return {'status': 'blocked', 'reasons': ['three_business_runs_required']}
    p, a, r = views; reasons = []
    if [v['adapter'] for v in views] != ['finalsource-shaped', 'alternate-ledger', 'alternate-ledger']: reasons.append('adapter_roles')
    if len({v['runId'] for v in views}) != 3: reasons.append('fresh_run_identity')
    for field in ('wireIds', 'subjectIds'):
        if any(set(map(str, x[field])) & set(map(str, y[field])) for x, y in combinations(views, 2)): reasons.append('fresh_' + field)
    if not all(type(v) is int for v in p['wireIds']) or not all(isinstance(v, str) for view in (a, r) for v in view['wireIds']): reasons.append('distinct_id_types')
    for field in ('sourcePins', 'assertionShape', 'gaps'):
        if not all(v[field] == p[field] for v in views): reasons.append('same_' + field)
    if any(v['required'] != 66 or v['passed'] != 66 or v['proofComplete'] is not True for v in views): reasons.append('full_required_assertions')
    if p['routes'] == a['routes'] or p['routes'] == r['routes'] or a['routes'] != r['routes']: reasons.append('distinct_routes')
    if any(set(map(tuple, p['routes'][op])) & set(map(tuple, a['routes'].get(op, []))) for op in p['routes']): reasons.append('wire_route_overlap')
    if p['envelope'] != 'data' or a['envelope'] != r['envelope'] or a['envelope'] != 'result.value': reasons.append('distinct_response_envelopes')
    return {'status': 'blocked' if reasons else 'pass', 'reasons': reasons,
            'requiredPerRun': 66, 'runIds': [v['runId'] for v in views], 'adapters': [v['adapter'] for v in views]}


def business_view(ref):
    with BundleReader(ref['bundle']) as reader:
        require(sha(reader.read('manifest.json')) == ref['manifestSha256'], 'input_manifest_drift')
        result = verify_business_bundle(ref['bundle'], ref['planSha256'])
        p = strict_json(reader.read('plan.json')); f = strict_json(reader.read('fixture.json'))
        o = strict_json(reader.read('observations.json'))
        require(p['sourcePins'] == business_pins(), 'business_not_final_source')
        resources = {r['resourceRef']: r for r in f['resources']}; routes = {}; envelopes = set()
        for c, row in zip(f['transitions'], o['cases'], strict=True):
            request = row['exchange']['request']; path = request['path']
            for resource in resources.values(): path = path.replace('/' + str(resource['wireId']), '/<id>')
            routes.setdefault(c['operation'], set()).add((request['method'], path))
            if row['exchange']['status'] < 400:
                body = row['exchange']['body']
                if set(body) == {'data'}: envelopes.add('data')
                elif set(body) == {'result'} and isinstance(body['result'], dict) and set(body['result']) == {'value'}: envelopes.add('result.value')
                else: envelopes.add('unknown')
        shape = sorted([[c['caseId'], c['actorRef'], c['operation'], c['resourceRef'], sorted(c['input']), c.get('positiveCaseId')]
                        for c in f['transitions']])
        value = {'runId': p['runId'], 'adapter': f['adapter'], 'wireIds': [r['wireId'] for r in f['resources']],
                 'subjectIds': [a['subject'] for a in f['actors'] if a['actorRef'] != 'anonymous'],
                 'sourcePins': p['sourcePins'], 'assertionShape': shape, 'required': len(f['transitions']),
                 'passed': result['applicationOracleCounts']['pass'], 'proofComplete': result['evidenceStatus'] == 'complete',
                 'routes': {k: sorted([list(x) for x in v]) for k, v in sorted(routes.items())},
                 'envelope': next(iter(envelopes)) if len(envelopes) == 1 else 'mixed-or-unknown',
                 'gaps': f['coverageGaps'], 'planHash': ref['planSha256'], 'manifestSha256': ref['manifestSha256']}
        reader.unchanged(); return value


def validate_request(p):
    require(isinstance(p, dict) and set(p) == {'contractVersion', 'bundles', 'regression', 'sourcePins', 'independentAcceptance', 'securityApproval'}, 'request_fields')
    require(p['contractVersion'] == VERSION and p['sourcePins'] == source_pins(), 'version_or_source')
    require(p['independentAcceptance'] == 'pending' and p['securityApproval'] is False, 'no_self_approval')
    require(isinstance(p['bundles'], dict) and set(p['bundles']) == set(ROLES), 'required_bundle_roles')
    for ref in p['bundles'].values():
        require(isinstance(ref, dict) and set(ref) == {'bundle', 'planSha256', 'manifestSha256'}, 'bundle_ref_fields')
        require(isinstance(ref['bundle'], str) and Path(ref['bundle']).is_absolute(), 'absolute_bundle_path')
        reference(ref['bundle'], ref['planSha256'], ref['manifestSha256'])
    r = p['regression']
    require(isinstance(r, dict) and set(r) == {'request', 'requestSha256', 'result', 'resultSha256'}, 'regression_ref')
    require(all(isinstance(r[k], str) and Path(r[k]).is_absolute() for k in ('request', 'result')), 'absolute_regression_path')
    require(all(isinstance(r[k], str) and re.fullmatch('[0-9a-f]{64}', r[k]) for k in ('requestSha256', 'resultSha256')), 'regression_hash')
    return p


def evaluate(request_path, expected_sha):
    raw, p = read_document(request_path)
    require(isinstance(expected_sha, str) and sha(raw) == expected_sha and raw == canonical(p), 'external_request_pin')
    validate_request(p); refs = p['bundles']
    views = [business_view(refs[k]) for k in ('primary', 'alternate', 'repeat')]
    general = generalization(views)
    with BundleReader(refs['unified']['bundle']) as reader:
        require(sha(reader.read('manifest.json')) == refs['unified']['manifestSha256'], 'unified_manifest_drift')
        unified = verify_unified_bundle(refs['unified']['bundle'], refs['unified']['planSha256'])
        plan = strict_json(reader.read('plan.json')); matrix = strict_json(reader.read('track-matrix.json'))
        require(plan['sourcePins'] == unified_pins() and plan['adapter'] == 'alternate-ledger', 'unified_final_alternate_source')
        api = next(r for r in matrix if r['phase'] == 'api')
        require(api['childPlanHash'] == views[1]['planHash'] and api['childManifestSha256'] == views[1]['manifestSha256'], 'unified_alternate_api_link')
        reader.unchanged()
    regression = compare_request(p['regression']['request'], p['regression']['requestSha256'])
    result_raw, _ = read_document(p['regression']['result'])
    require(sha(result_raw) == p['regression']['resultSha256'] and result_raw == canonical(regression), 'regression_replay_disagreement')
    diagnostic = general['status'] == 'pass' and unified['orchestrationVerdict'] == 'verified' and regression['exitCode'] == 0
    require(p['sourcePins'] == source_pins(), 'source_changed_during_acceptance')
    return {'contractVersion': VERSION, 'requestSha256': expected_sha, 'executionStatus': 'completed',
            'evidenceStatus': 'complete', 'cleanupStatus': unified['cleanupStatus'],
            'securityVerdict': unified['securityVerdict'], 'gateDecision': 'block',
            'conformanceVerdict': 'pass' if diagnostic else 'blocked', 'G7SyntheticGeneralization': general['status'],
            'G12DReproducibility': 'prepared' if diagnostic else 'blocked', 'G12DOperational': 'blocked',
            'independentAcceptance': 'pending', 'securityApproval': False, 'R1R2Admission': False,
            'generalization': general, 'wireConformance': [{k: v[k] for k in ('runId', 'adapter', 'required', 'passed', 'routes', 'envelope', 'planHash', 'manifestSha256')} for v in views],
            'coverageGaps': views[0]['gaps'], 'unified': unified,
            'activeRegression': {'requestSha256': regression['requestSha256'], 'remediationVerified': regression['remediationVerified'], 'scope': regression['remediationScope']},
            'remainingBlockers': ['G3/G4 operational broker and sink/lifecycle proof', 'G8 browser secret persistence',
                                  'G10 product/MCP/single-live-DB integration', 'G11 product regression adapter', 'independent acceptance'],
            'exitCode': 0 if diagnostic else 1}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    for role in ROLES:
        prepare.add_argument('--' + role + '-bundle', type=Path, required=True)
        prepare.add_argument('--' + role + '-plan-sha', required=True)
    prepare.add_argument('--regression-request', type=Path, required=True); prepare.add_argument('--regression-request-sha', required=True)
    prepare.add_argument('--regression-result', type=Path, required=True); prepare.add_argument('--output', type=Path, required=True)
    for name in ('run', 'verify'):
        c = sub.add_parser(name); c.add_argument('--request', type=Path, required=True); c.add_argument('--expect-request-sha', required=True)
        if name == 'run': c.add_argument('--output', type=Path, required=True)
        else: c.add_argument('--result', type=Path, required=True)
    a = p.parse_args(argv)
    try:
        if a.command == 'prepare':
            require(not a.output.exists(), 'output_exists')
            refs = {k: reference(getattr(a, k + '_bundle').absolute(), getattr(a, k + '_plan_sha')) for k in ROLES}
            result_raw, _ = read_document(a.regression_result)
            value = {'contractVersion': VERSION, 'bundles': refs, 'sourcePins': source_pins(),
                     'regression': {'request': str(a.regression_request.absolute()), 'requestSha256': a.regression_request_sha,
                                    'result': str(a.regression_result.absolute()), 'resultSha256': sha(result_raw)},
                     'independentAcceptance': 'pending', 'securityApproval': False}
            validate_request(value); raw = canonical(value); a.output.parent.mkdir(parents=True, exist_ok=True); atomic_bytes(a.output, raw)
            print(json.dumps({'requestSha256': sha(raw), 'request': str(a.output.absolute())})); return 0
        result = evaluate(a.request, a.expect_request_sha)
        if a.command == 'verify':
            require(read_document(a.result)[0] == canonical(result), 'result_disagrees_with_replay')
            print(json.dumps({'verified': True, 'gateDecision': result['gateDecision'], 'securityVerdict': result['securityVerdict'], 'independentAcceptance': 'pending'})); return 0
        a.output.mkdir(mode=0o700, parents=True, exist_ok=False); raw = canonical(result); atomic_bytes(a.output / 'result.json', raw)
        atomic_bytes(a.output / 'manifest.json', canonical({'contractVersion': VERSION, 'requestSha256': a.expect_request_sha,
                     'artifacts': [{'path': 'result.json', 'bytes': len(raw), 'sha256': sha(raw)}]}))
        print(json.dumps(result)); return result['exitCode']
    except (EvidenceInvalid, OSError, KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        print(json.dumps({'evidenceStatus': 'invalid', 'gateDecision': 'block', 'reason': str(exc) if isinstance(exc, EvidenceInvalid) else 'acceptance_invalid_input',
                          'independentAcceptance': 'pending', 'securityApproval': False}), file=sys.stderr); return 2


if __name__ == '__main__': sys.exit(main())
