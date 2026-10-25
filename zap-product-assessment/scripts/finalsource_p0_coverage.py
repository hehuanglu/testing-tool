#!/usr/bin/env python3
"""Collect legacy pilot observations without promoting them to v2 oracle proof.

A published/historical bundle is read-only: use --output with a fresh directory.
The reusable bound predicate lives in zap_assessment.coverage; legacy observations
lack its required correlations and remain explicitly inconclusive.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from zap_assessment.coverage import digest, evaluate

METHODS = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options', 'trace'}


def load(path):
    return json.loads(path.read_bytes())


def write(path, value):
    with path.open('x') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    path.chmod(0o600)


def build(root, output=None):
    root = root.resolve()
    output = Path(output).resolve() if output is not None else root
    if output == root:
        if (root / 'manifest.json').exists() or any((root / n).exists() for n in ('coverage.json', 'COVERAGE_VI.md', 'input-index.json')):
            raise ValueError('source bundle is immutable or already has coverage; use a fresh --output')
    elif output.exists() or output.is_relative_to(root):
        raise ValueError('--output must be fresh and outside the source bundle')
    schema_file = root / 'native-browser-a2/controls/current-openapi.json'
    schema = json.loads(load(schema_file)['response']['body'])
    operations = [(m.upper(), path) for path, definition in schema['paths'].items()
                  for m in definition if m in METHODS]
    source_refs = set([str(schema_file.relative_to(root))])

    def read(path):
        source_refs.add(str(path.relative_to(root)))
        return load(path)

    patterns = []
    for method, template in sorted(operations, key=lambda op: (op[1].count('{'), -len(op[1]))):
        parts = re.split(r'(\{[^}]+\})', template)
        pattern = ''.join('[^/]+' if p.startswith('{') and p.endswith('}') else re.escape(p) for p in parts)
        patterns.append((method, template, re.compile(pattern)))

    def route(method, path):
        concrete = urlsplit(path).path
        for verb, template, pattern in patterns:
            if verb == method and pattern.fullmatch(concrete):
                return template
        return concrete

    rows = {(method, path, actor): {
        'method': method, 'endpoint': path, 'actor': actor,
        'operationActorRef': digest([method, path, actor]), 'resourceBinding': None,
        'sourceDiscovered': True, 'javascriptDiscovered': False,
        'observed': False, 'requested': False, 'targetRequested': False,
        'techniqueExecuted': False, 'activeLifecycleCompleted': False,
        'responseSource': 'unknown', 'oracleResult': 'not_run', 'status': 'not_run',
        'reasonCodes': ['no_observation'], 'observations': []
    } for method, path in operations for actor in ('anonymous', 'A', 'B')}
    unmapped = []

    def add(method, path, actor, status, technique, evidence, phase_status='unknown', source_hint='unknown', **extra):
        path = urlsplit(path).path  # Never re-export query values or raw response bodies.
        endpoint = route(method, path)
        key = (method, endpoint, actor)
        if key not in rows:
            unmapped.append({'method': method, 'path': path, 'actor': actor,
                             'evidence': evidence, 'reason': 'outside_locked_operation_actor_inventory'})
            return
        ref = f'{evidence}#{len(rows[key]["observations"])}'
        recorded = {'request': {'method': method, 'path': path}}
        if type(status) is int and 100 <= status <= 599:
            recorded['response'] = {'status': status}
        # Legacy files do not carry all binding keys or boundary request/response hashes.
        # Calling the same predicate prevents the old collector from status-promoting.
        assertion = {'schemaVersion': '2.0', 'primaryRef': ref,
                     'binding': {'operation': method + ' ' + endpoint, 'actorRef': actor}}
        assessment = evaluate(assertion, {'exchanges': {ref: recorded}})
        reasons = set(assessment['reasonCodes']) | {'missing_boundary_correlation', 'missing_identity', 'missing_owner_positive'}
        if source_hint == 'guard':
            reasons.add('guard_indicator')
        if method not in ('GET', 'HEAD', 'OPTIONS'):
            reasons.add('unproven_post_state')
        if phase_status != 'completed':
            reasons.add('phase_not_completed_or_reuse_unproven')
        row = rows[key]
        row['requested'] |= assessment['requested']
        row['observed'] |= assessment['observed']
        row['oracleResult'] = row['status'] = 'inconclusive'
        row['reasonCodes'] = sorted((set(row['reasonCodes']) - {'no_observation'}) | reasons)
        row['observations'].append({
            'path': path, 'statusCode': status, 'technique': technique,
            'evidence': evidence, 'phaseStatus': phase_status, 'responseSource': 'unknown',
            'sourceHint': source_hint, 'oracleResult': assessment['oracleResult'],
            'reasonCodes': sorted(reasons), **extra})
        return row

    native, delegated, deviations = [], [], []
    for phase in sorted(root.iterdir()):
        if not phase.is_dir():
            continue
        outcome = read(phase / 'outcome.json') if (phase / 'outcome.json').exists() else {}
        phase_status = outcome.get('executionStatus', 'unknown')
        for f in sorted((phase / 'controls').glob('*.json')):
            value = read(f)
            request, response = value.get('request', {}), value.get('response', {})
            if request.get('op') == 'request':
                add(request.get('method', 'GET'), request['path'], request.get('actor') or 'anonymous',
                    response.get('status'), 'direct API control', str(f.relative_to(root)), phase_status)
            elif request.get('op') == 'login' and request.get('actor') in ('A', 'B'):
                add('POST', '/api/auth/login', request['actor'], response.get('status'),
                    'recorded login control', str(f.relative_to(root)), phase_status)
        if not (phase / 'plan.json').exists():
            continue
        plan = read(phase / 'plan.json')
        actor = plan.get('actor')
        if actor not in ('A', 'B'):
            continue
        if plan.get('mode') == 'native':
            native.append(phase.name)
            ui = phase / 'ui-journeys.json'
            if not ui.exists() and phase.name == 'native-browser-a2':
                ui = phase / 'ui-journeys-extracted.json'
            journey = read(ui) if ui.exists() else {}
            journey = journey.get('result', journey)
            js = bool(journey.get('loggedIn') and not journey.get('error'))
            guard = phase / 'guard/guard.jsonl'
            if guard.exists():
                source_refs.add(str(guard.relative_to(root)))
                for line in guard.read_text().splitlines():
                    event = json.loads(line)
                    if event.get('source') == 'upstream' and event.get('method') == 'GET' and event.get('path', '').startswith('/api/'):
                        row = add('GET', event['path'], actor, event.get('status'),
                                  'browser traffic recorded at legacy guard', str(guard.relative_to(root)),
                                  phase_status, 'target')
                        if row is not None:
                            row['javascriptDiscovered'] |= js
        elif plan.get('mode') == 'delegated':
            delegated.append(phase.name)
            deviating = (phase / 'policy-review.json').exists() and not read(phase / 'policy-review.json').get('conformance')
            if deviating:
                deviations.append(phase.name)
            messages_file = phase / 'messages.json'
            messages = read(messages_file).get('messages', []) if messages_file.exists() else []
            for message in messages:
                parts = message.get('requestHeader', '').split('\r\n')[0].split(' ')
                status = re.search(r'^HTTP/\S+\s+(\d+)', message.get('responseHeader', ''))
                if len(parts) < 2 or not status:
                    continue
                try:
                    body = json.loads(message.get('responseBody', ''))
                except ValueError:
                    body = {}
                generated = isinstance(body, dict) and (body.get('guardGenerated') or body.get('authLost'))
                row = add(parts[0], parts[1], actor, int(status[1]), 'recorded ZAP mirror request',
                          str(messages_file.relative_to(root)), phase_status, 'guard' if generated else 'unknown',
                          messageId=message.get('id'))
                if row is not None and deviating:
                    row['reasonCodes'] = sorted(set(row['reasonCodes']) | {'policy_deviation'})
        ops_file = phase / 'operations.json'
        for op in read(ops_file) if ops_file.exists() else []:
            if op.get('kind') == 'activeScan' and op.get('terminal'):
                key = ('GET', route('GET', op['path']), actor)
                if key in rows:
                    rows[key]['activeLifecycleCompleted'] = True
                    rows[key]['observations'].append({
                        'technique': 'active lifecycle only', 'evidence': str(ops_file.relative_to(root)),
                        'operationId': op.get('operationId'), 'scanId': op.get('scanId'),
                        'oracleResult': 'inconclusive', 'reasonCodes': ['sink_unproven']})
                    rows[key]['reasonCodes'] = sorted(set(rows[key]['reasonCodes']) | {'sink_unproven'})
    result = {
        'schemaVersion': '2.0', 'evaluationKind': 'legacy-observation-reevaluation-candidate',
        'legacyBundleUpgraded': False, 'securityApproval': False,
        'operationDenominator': len(operations), 'actorRows': len(rows),
        'sourceEvidence': str(schema_file.relative_to(root)),
        'resourceBindings': None, 'bindingStatus': 'legacy_required_binding_missing',
        'nativeBrowserPhases': native, 'delegatedPhases': delegated, 'policyDeviatingPhases': deviations,
        'statuses': dict(Counter(r['oracleResult'] for r in rows.values())), 'rows': list(rows.values()),
        'unmappedObservations': unmapped,
        'limitations': ['Legacy observations lack v2 boundary correlation and complete assertion bindings',
                        'No new application-oracle-pass or active sink proof from legacy status codes',
                        'Collector does not implement semantic bundle verification (W2)',
                        'All required operation/actor rows retained, including missing fixture proof']}
    if output != root:
        output.mkdir(parents=True, mode=0o700)
    # Only metadata and references leave the historical bundle, never raw credentials/bodies.
    write(output / 'coverage.json', result)
    if (root / 'coverage.json').exists() and output != root:
        previous = read(root / 'coverage.json')
        old = {(r['method'], r['endpoint'], r['actor']): r for r in previous['rows']}
        write(output / 'reevaluation-diff.json', {
            'previousStatuses': previous.get('statuses'), 'candidateStatuses': result['statuses'],
            'rows': [{'method': r['method'], 'endpoint': r['endpoint'], 'actor': r['actor'],
                      'previousStatus': old.get(k, {}).get('status', 'absent'), 'candidateOracleResult': r['oracleResult'],
                      'reasonCodes': r['reasonCodes']} for k, r in rows.items()]})
    write(output / 'input-index.json', {'artifacts': [
        {'path': ref, 'sha256': hashlib.sha256((root / ref).read_bytes()).hexdigest()}
        for ref in sorted(source_refs)]})
    return {key: value for key, value in result.items() if key not in ('rows', 'unmappedObservations')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args(argv)
    print(json.dumps(build(args.bundle, args.output), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
