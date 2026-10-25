"""Generic v2 bundle generator with independent, explicit fixture expectations.

No production builder/verifier is imported, and no network is used. This is
synthetic evidence, never a target/boundary attestation or secret-safe publisher.
"""
import copy
import hashlib
import json
from pathlib import Path

TRACKS = ['api-ownership-business', 'active-controls', 'browser-business',
          'evidence-verification', 'regression', 'alternate-product']
RUNTIME_GATES = ['G3', 'G4', 'G5', 'G6', 'G7', 'G8', 'G9', 'G10', 'G11', 'G12-D']


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode()


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def seal(observations, ref, source='target'):
    rec = observations['exchanges'][ref]
    observations['boundaries'][ref] = {
        'source': source, 'binding': copy.deepcopy(rec['binding']),
        **{k: rec[k] for k in ('requestId', 'responseId', 'at', 'authEpoch', 'clockId', 'authMode')},
        'requestSha256': sha(encoded(rec['request'])), 'responseSha256': sha(encoded(rec['response']))}


def make_bundle(root, *, tag='alpha', variants=('pass',), envelope='payload', route='/ledger/items', reverse=False):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=False)
    context = {'assessmentId': 'assessment-' + tag, 'targetBinding': 'target-' + tag,
               'buildRef': 'build-' + tag, 'planHash': '$self'}
    actors, resources, assertions, phases, expected_results = [], [], [], [], []
    observations = {'schemaVersion': '2.0', 'exchanges': {}, 'boundaries': {},
                    'phases': {}, 'reuseRecords': {}, 'cleanup': 'not_applicable'}
    for index, variant in enumerate(variants):
        suffix = tag + '-' + str(index)
        owner, viewer, guest = ('owner-' + suffix, 'viewer-' + suffix, 'guest-' + suffix)
        owner_subject, viewer_subject = 3001 + index * 100, 4002 + index * 100
        key, resource_ref, phase = 'record-' + suffix, 'resource-' + suffix, 'phase-' + suffix
        base = {**context, 'actorRef': viewer, 'resourceRef': resource_ref,
                'operation': 'PATCH ' + route + '/{recordKey}', 'techniqueId': 'direct-api',
                'phaseId': phase, 'oracleVersion': 'adapter-ownership/2.0'}
        path, state = route + '/' + key, {'record_key': key, 'owned_by': owner_subject, 'amount': '100.00'}
        pointer = '/' + envelope + '/record'
        actors.extend([
            {'actorRef': owner, 'subject': owner_subject, 'role': 'member', 'authMode': 'authenticated', 'identityResourceRef': 'principal-' + owner},
            {'actorRef': viewer, 'subject': viewer_subject, 'role': 'member', 'authMode': 'authenticated', 'identityResourceRef': 'principal-' + viewer},
            {'actorRef': guest, 'subject': None, 'role': 'anonymous', 'authMode': 'anonymous', 'identityResourceRef': 'principal-' + guest}])
        resources.append({'resourceRef': resource_ref, 'wireId': key, 'ownerActorRef': owner,
                          'ownerSubject': owner_subject, 'idPointer': pointer + '/record_key',
                          'ownerPointer': pointer + '/owned_by'})

        def exchange(label, actor, at, body, *, method='GET', status=200, identity=False):
            ref = suffix + '-' + label
            request = {'method': method, 'path': '/principal/me' if identity else path}
            binding = {**base, 'actorRef': actor, 'operation': method + ' ' + request['path'],
                       'resourceRef': 'principal-' + actor if identity else resource_ref,
                       'techniqueId': 'identity-control' if identity else 'state-control'}
            rec = {'binding': binding, 'request': request,
                   'response': {'status': status, 'contentType': 'application/json', 'body': encoded(body).decode()},
                   'requestId': ref + '-req', 'responseId': ref + '-resp', 'at': at,
                   'authEpoch': 'epoch-' + actor, 'clockId': 'clock-' + phase, 'authMode': 'authenticated'}
            observations['exchanges'][ref] = rec
            seal(observations, ref)
            return {'ref': ref, 'binding': copy.deepcopy(binding), 'request': copy.deepcopy(request), 'statuses': [status]}

        identities = {}
        for actor, subject in [(owner, owner_subject), (viewer, viewer_subject)]:
            proof = exchange('identity-' + actor, actor, 10, {'principal': {'uid': subject, 'capability': 'member'}}, identity=True)
            identities[actor] = {'subject': subject, 'role': 'member', 'subjectPointer': '/principal/uid',
                                 'rolePointer': '/principal/capability', 'maxAgeSeconds': 5, 'proof': proof}
        owner_spec = exchange('positive', owner, 11, {envelope: {'record': state}})
        before = exchange('before', owner, 11.5, {envelope: {'record': state}})
        after = exchange('after', owner, 13, {envelope: {'record': state}})
        primary_spec = exchange('main', viewer, 12, {'failure': {'kind': 'DENIED'}}, method='PATCH', status=404)
        main = observations['exchanges'][primary_spec['ref']]
        main.update(binding=copy.deepcopy(base), request={'method': 'PATCH', 'path': path, 'body': {'amount': '80.00'}})
        oracle = {'kind': 'denial', 'statuses': [404],
                  'responseEquals': [{'pointer': '/failure/kind', 'value': 'DENIED'}],
                  'forbiddenPointers': [pointer + '/record_key', pointer + '/amount']}
        expected = 'pass'
        if variant == 'violation':
            observations['exchanges'][after['ref']]['response']['body'] = encoded({envelope: {'record': {**state, 'amount': '0.00'}}}).decode()
            seal(observations, after['ref'])
            expected = 'fail'
        elif variant in ('disclosure', 'disclosure-missing-post'):
            main['response']['body'] = encoded({'failure': {'kind': 'DENIED'}, envelope: {'record': {'amount': '100.00'}}}).decode()
            expected = 'fail'
        elif variant in ('blocked', 'missing-post', 'phase-failed', 'unsupported'):
            expected = 'inconclusive'
        if variant == 'blocked':
            main['response']['status'] = oracle['statuses'][0] = 403
        if variant == 'read':
            base.update(actorRef=owner, operation='GET ' + route + '/{recordKey}')
            main.update(binding=copy.deepcopy(base), request={'method': 'GET', 'path': path}, authEpoch='epoch-' + owner)
            main['response'].update(status=200, body=encoded({envelope: {'record': state}}).decode())
            oracle = {'kind': 'resource-read', 'statuses': [200], 'responseEquals': [{'pointer': pointer + '/amount', 'value': '100.00'}]}
        elif variant == 'validation400':
            main['response'].update(status=400, body=encoded({'failure': {'kind': 'INVALID'}}).decode())
            oracle.update(kind='validation', statuses=[400], responseEquals=[{'pointer': '/failure/kind', 'value': 'INVALID'}])
        elif variant == 'anonymous-denial':
            base['actorRef'] = guest
            main.update(binding=copy.deepcopy(base), authMode='anonymous', authEpoch='anonymous')
            main['response']['status'] = oracle['statuses'][0] = 401
        elif variant == 'unsupported':
            base['techniqueId'] = 'SQLi'
            main['binding'] = copy.deepcopy(base)
        elif variant == 'transition':
            base['actorRef'] = owner
            main.update(binding=copy.deepcopy(base), authEpoch='epoch-' + owner)
            main['response'].update(status=200, body=encoded({'accepted': True}).decode())
            oracle = {'kind': 'state-transition', 'statuses': [200],
                      'responseEquals': [{'pointer': '/accepted', 'value': True}]}
            observations['exchanges'][after['ref']]['response']['body'] = encoded({envelope: {'record': {**state, 'amount': '80.00'}}}).decode()
            seal(observations, after['ref'])
        assertion = {'schemaVersion': '2.0', 'assertionId': 'assertion-' + suffix,
                     'required': True, 'trackId': TRACKS[0], 'binding': copy.deepcopy(base),
                     'request': copy.deepcopy(main['request']), 'primaryRef': primary_spec['ref'],
                     'identities': identities, 'resource': copy.deepcopy(resources[-1]),
                     'ownerPositive': owner_spec, 'preState': before, 'postState': after,
                     'statePointer': pointer, 'expectedPreState': state, 'oracle': oracle}
        if variant == 'transition':
            assertion['expectedPostState'] = {**state, 'amount': '80.00'}
        seal(observations, primary_spec['ref'], 'guard' if variant == 'blocked' else 'target')
        phase_state = {'status': 'completed', 'clockId': 'clock-' + phase}
        if variant in ('phase-failed', 'reuse'):
            phase_state.update(status='failed', failedAt=14)
        if variant == 'reuse':
            assertion['reusePolicy'] = 'completed-before-phase-failure'
            refs = [r for r, rec in observations['exchanges'].items() if rec['binding']['phaseId'] == phase]
            observations['reuseRecords'][assertion['assertionId']] = {
                'recordRef': 'reuse-' + suffix, 'binding': copy.deepcopy(base), 'clockId': 'clock-' + phase,
                'completedAt': 13, 'authEpochs': {owner: 'epoch-' + owner, viewer: 'epoch-' + viewer},
                'stateBeforeRef': before['ref'], 'stateAfterRef': after['ref'], 'exchangeRefs': refs}
        if variant in ('missing-post', 'disclosure-missing-post'):
            observations['exchanges'].pop(after['ref'])
            observations['boundaries'].pop(after['ref'])
        observations['phases'][phase] = phase_state
        assertions.append(assertion)
        phases.append({'phaseId': phase, 'trackId': TRACKS[0], 'required': True})
        expected_results.append({'assertionId': assertion['assertionId'], 'oracleResult': expected})
    fixture = {'schemaVersion': '2.0', **{k: v for k, v in context.items() if k != 'planHash'},
               'actors': actors, 'resources': resources}
    reports = [{'reportId': 'json-' + tag, 'format': 'json', 'sourcePath': '/zap/wrk/result-' + tag + '.json'},
               {'reportId': 'html-' + tag, 'format': 'html', 'sourcePath': '/zap/wrk/result-' + tag + '.html'}]
    plan = {'schemaVersion': '2.0', 'planKind': 'coverage-verification', 'verificationOnly': True,
            **{k: v for k, v in context.items() if k != 'planHash'}, 'fixtureHash': sha(encoded(fixture)),
            'requiredTracks': TRACKS, 'phases': phases, 'assertions': assertions,
            'reports': reports, 'unprovenRuntimeGates': RUNTIME_GATES}
    if reverse:
        plan['assertions'].reverse(); plan['phases'].reverse(); plan['requiredTracks'] = list(reversed(TRACKS))
        fixture['actors'].reverse(); fixture['resources'].reverse(); plan['fixtureHash'] = sha(encoded(fixture))
    plan_hash = sha(encoded(plan))
    def resolve(value):
        if isinstance(value, dict):
            return {k: plan_hash if k == 'planHash' and v == '$self' else resolve(v) for k, v in value.items()}
        if isinstance(value, list):
            return [resolve(v) for v in value]
        return value
    observations = resolve(observations)
    for ref, event in list(observations['boundaries'].items()):
        seal(observations, ref, event['source'])
    counts = {k: sum(r['oracleResult'] == k for r in expected_results) for k in ('pass', 'fail', 'inconclusive')}
    failed = any(p['status'] == 'failed' for p in observations['phases'].values())
    summary = {'schemaVersion': '2.0', 'assessmentId': context['assessmentId'],
               'executionStatus': 'failed' if failed else 'completed',
               'evidenceStatus': 'incomplete',
               'coverageEvidenceStatus': 'incomplete' if failed or counts['inconclusive'] or 'disclosure-missing-post' in variants else 'complete',
               'securityVerdict': 'fail' if counts['fail'] else 'inconclusive',
               'cleanupStatus': 'not_applicable', 'gateDecision': 'block', 'applicationOracleCounts': counts,
               'tracks': [{'trackId': t, 'status': ('fail' if counts['fail'] else 'inconclusive' if failed or counts['inconclusive'] else 'pass') if t == TRACKS[0] else 'not_run'} for t in TRACKS]}
    documents = {'plan': 'contract/plan-' + tag + '.json', 'fixture': 'binding/resources-' + tag + '.json',
                 'observations': 'observations/raw-' + tag + '.json', 'coverage': 'derived/claims-' + tag + '.json',
                 'summary': 'derived/summary-' + tag + '.json'}
    values = {'plan': plan, 'fixture': fixture, 'observations': observations,
              'coverage': {'schemaVersion': '2.0', 'assertions': list(reversed(expected_results)) if reverse else expected_results}, 'summary': summary}
    for key, name in documents.items():
        p = root / name; p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(encoded(values[key]))
    report_records = []
    for desc in reports:
        content = encoded({'text': 'Tiếng Việt 🧪\u0085 — dữ liệu ' + tag}).decode() if desc['format'] == 'json' else '<html><p>Việt 🧪 ' + tag + '</p></html>'
        raw = content.encode(); name = 'reports/' + desc['reportId'] + '.data'; (root / name).parent.mkdir(exist_ok=True); (root / name).write_bytes(raw)
        offsets = [0, len(content) // 3, 2 * len(content) // 3, len(content)]; chunks = []
        for i, (start, end) in enumerate(zip(offsets, offsets[1:])):
            path = 'pages/' + desc['reportId'] + '-' + str(i) + '.json'; p = root / path; p.parent.mkdir(exist_ok=True)
            page = {'reportPath': desc['sourcePath'], 'offset': start, 'nextOffset': end if end < len(content) else None,
                    'charactersReturned': end - start, 'endOfFile': end == len(content), 'totalCharacters': len(content),
                    'offsetUnit': 'unicodeCodePoints', 'artifactSha256': sha(raw), 'content': content[start:end]}
            p.write_bytes(encoded(page)); chunks.append(path)
        report_records.append({'reportId': desc['reportId'], 'artifactPath': name, 'chunkPaths': list(reversed(chunks)) if reverse else chunks})
    manifest = {'schemaVersion': '2.0', 'assessmentId': context['assessmentId'], 'planHash': plan_hash,
                'documents': documents, 'reports': report_records, 'artifacts': []}
    repack(root, manifest, reverse=reverse)
    return {'root': root, 'planHash': plan_hash, 'manifest': manifest, 'expectedResults': expected_results,
            'expectedSummary': summary, 'documents': documents}


def repack(root, manifest=None, *, reverse=False):
    root = Path(root)
    if manifest is None:
        manifest = json.loads((root / 'manifest.json').read_bytes())
    manifest['artifacts'] = [{'path': str(p.relative_to(root)), 'bytes': p.stat().st_size, 'sha256': sha(p.read_bytes())}
                             for p in sorted(root.rglob('*')) if p.is_file() and p.name not in ('manifest.json', 'manifest.sha256')]
    if reverse:
        manifest['artifacts'].reverse()
    (root / 'manifest.json').write_bytes(encoded(manifest))
    (root / 'manifest.sha256').write_text(sha(encoded(manifest)) + '\n')
    return manifest
