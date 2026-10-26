"""G2 tamper cases. Expected acceptance is declared before verifier execution."""
import copy
import json
import os
from pathlib import Path
import shutil

from .verification_fixture import encoded, repack, seal, sha


def document(bundle, key):
    return json.loads((bundle['root'] / bundle['documents'][key]).read_bytes())


def save(bundle, key, value):
    (bundle['root'] / bundle['documents'][key]).write_bytes(encoded(value))


def main_ref(obs):
    return next(ref for ref, row in obs['exchanges'].items() if row['binding']['techniqueId'] in ('direct-api', 'SQLi'))


def mutate_document(key, mutate):
    def apply(bundle):
        value = document(bundle, key)
        mutate(value)
        save(bundle, key, value)
        repack(bundle['root'])
    return apply


def rewrite_manifest(bundle, mutate):
    value = json.loads((bundle['root'] / 'manifest.json').read_bytes())
    mutate(value)
    (bundle['root'] / 'manifest.json').write_bytes(encoded(value))
    (bundle['root'] / 'manifest.sha256').write_text(sha(encoded(value)) + '\n')


def reanchor(bundle, *, keep_old_pin=False):
    old = bundle['planHash']
    new = sha((bundle['root'] / bundle['documents']['plan']).read_bytes())
    obs = document(bundle, 'observations')
    for rec in [*obs['exchanges'].values(), *obs['boundaries'].values(), *obs['reuseRecords'].values()]:
        if rec['binding']['planHash'] == old:
            rec['binding']['planHash'] = new
    save(bundle, 'observations', obs)
    manifest = json.loads((bundle['root'] / 'manifest.json').read_bytes())
    manifest['planHash'] = new
    repack(bundle['root'], manifest)
    if not keep_old_pin:
        bundle['planHash'] = new


def cases():
    result = []
    def case(name, *, accept=False, variant='pass', mutate=None, **options):
        result.append({'caseId': name, 'expectedVerified': accept, 'variant': variant,
                       'options': options, 'mutate': mutate})
    for variant in ('pass', 'read', 'validation400', 'anonymous-denial', 'violation', 'blocked',
                    'missing-post', 'unsupported', 'phase-failed', 'reuse', 'transition', 'disclosure', 'disclosure-missing-post'):
        case('faithful-' + variant, accept=True, variant=variant)
    case('new-ids-directories-envelope-order', accept=True, variants=('pass', 'violation'), envelope='differentEnvelope', route='/api/collections/funds', reverse=True)

    def corrupt(bundle):
        p = bundle['root'] / bundle['documents']['observations']
        p.write_bytes(p.read_bytes() + b' ')
    case('corrupt-bytes', mutate=corrupt)
    case('changed-sha', mutate=lambda b: rewrite_manifest(b, lambda m: m['artifacts'][0].update(sha256='0' * 64)))
    case('corrupt-checksum-bytes', mutate=lambda b: (b['root'] / 'manifest.sha256').write_bytes(b'\xff' * 64))
    case('missing-manifest-checksum', mutate=lambda b: (b['root'] / 'manifest.sha256').unlink())
    case('duplicate-artifact', mutate=lambda b: rewrite_manifest(b, lambda m: m['artifacts'].append(copy.deepcopy(m['artifacts'][0]))))
    case('duplicate-claim', mutate=mutate_document('coverage', lambda c: c['assertions'].append(copy.deepcopy(c['assertions'][0]))))
    for path in ('../outside.json', '/absolute.json', 'observations\\raw.json', 'a/../b.json', 'a//b.json'):
        case('unsafe-path-' + str(len(result)), mutate=lambda b, path=path: rewrite_manifest(b, lambda m: m['artifacts'][0].update(path=path)))
    case('extra-unlisted', mutate=lambda b: (b['root'] / 'extra.json').write_text('{}'))
    def extra(bundle):
        (bundle['root'] / 'extra.json').write_text('{}')
        repack(bundle['root'])
    case('extra-listed-but-unreferenced', mutate=extra)

    def file_link(bundle):
        p = bundle['root'] / bundle['documents']['observations']
        outside = bundle['root'].parent / 'outside-controlled.json'
        shutil.copyfile(p, outside)
        p.unlink(); p.symlink_to(outside)
    case('file-symlink', mutate=file_link)
    def directory_link(bundle):
        parent = (bundle['root'] / bundle['documents']['observations']).parent
        outside = bundle['root'].parent / 'outside-controlled-directory'
        parent.rename(outside); parent.symlink_to(outside, target_is_directory=True)
    case('directory-symlink', mutate=directory_link)
    def hardlink(bundle):
        p = bundle['root'] / bundle['documents']['observations']
        outside = bundle['root'].parent / 'controlled-hardlink.json'
        os.link(p, outside)
    case('hardlink', mutate=hardlink)

    def missing_response(obs):
        obs['exchanges'][main_ref(obs)].pop('response')
    case('missing-response-rehashed', mutate=mutate_document('observations', missing_response))
    def duplicate_request(obs):
        refs = list(obs['exchanges'])
        obs['exchanges'][refs[1]]['requestId'] = obs['exchanges'][refs[0]]['requestId']
        seal(obs, refs[1])
    case('duplicate-request-id-rehashed', mutate=mutate_document('observations', duplicate_request))
    def duplicate_key(bundle):
        p = bundle['root'] / bundle['documents']['observations']
        p.write_bytes(b'{"schemaVersion":"2.0",' + p.read_bytes()[1:])
        repack(bundle['root'])
    case('duplicate-json-key-rehashed', mutate=duplicate_key)

    for field in ('actorRef', 'buildRef', 'resourceRef', 'phaseId', 'planHash', 'assessmentId',
                  'targetBinding', 'techniqueId', 'operation', 'oracleVersion'):
        def binding(obs, field=field):
            ref = main_ref(obs)
            obs['exchanges'][ref]['binding'][field] = '0' * 64 if field == 'planHash' else 'foreign-' + field
            seal(obs, ref)
        case('wrong-binding-' + field + '-rehashed', mutate=mutate_document('observations', binding))

    def identity_body(obs):
        ref = next(r for r, v in obs['exchanges'].items() if v['binding']['techniqueId'] == 'identity-control' and 'viewer-' in v['binding']['actorRef'])
        obs['exchanges'][ref]['response']['body'] = encoded({'principal': {'uid': -1, 'capability': 'member'}}).decode()
        seal(obs, ref)
    case('wrong-identity-body-all-checksums-recomputed', mutate=mutate_document('observations', identity_body))
    def extreme_decimal(obs):
        ref = next(r for r, v in obs['exchanges'].items() if v['binding']['techniqueId'] == 'identity-control' and 'viewer-' in v['binding']['actorRef'])
        obs['exchanges'][ref]['response']['body'] = '{"principal":{"uid":1e9999999999999999999999999999999999999999,"capability":"member"}}'
        seal(obs, ref)
    case('extreme-decimal-response-rehashed', mutate=mutate_document('observations', extreme_decimal))
    def stale_identity(obs):
        ref = next(r for r, v in obs['exchanges'].items() if v['binding']['techniqueId'] == 'identity-control' and 'viewer-' in v['binding']['actorRef'])
        obs['exchanges'][ref]['at'] = 1; seal(obs, ref)
    case('expired-identity-window-rehashed', mutate=mutate_document('observations', stale_identity))
    def changed_epoch(obs):
        ref = main_ref(obs); obs['exchanges'][ref]['authEpoch'] = 'foreign-epoch'; seal(obs, ref)
    case('auth-epoch-changed-rehashed', mutate=mutate_document('observations', changed_epoch))
    def late_positive(obs):
        ref = next(r for r in obs['exchanges'] if r.endswith('-positive'))
        obs['exchanges'][ref]['at'] = 13; seal(obs, ref)
    case('owner-positive-after-request-rehashed', mutate=mutate_document('observations', late_positive))
    def changed_state(obs):
        ref = next(r for r in obs['exchanges'] if r.endswith('-after'))
        raw = json.loads(obs['exchanges'][ref]['response']['body'])
        raw['payload']['record']['amount'] = '0.00'
        obs['exchanges'][ref]['response']['body'] = encoded(raw).decode()
        seal(obs, ref)
    case('post-state-changed-all-checksums-recomputed', mutate=mutate_document('observations', changed_state))
    def login(obs):
        ref = main_ref(obs)
        obs['exchanges'][ref]['response'].update(contentType='text/html', body='<html>Login</html>')
        seal(obs, ref)
    case('login-page200-all-checksums-recomputed', variant='read', mutate=mutate_document('observations', login))
    def wrong_read_resource(obs):
        ref = main_ref(obs); body = json.loads(obs['exchanges'][ref]['response']['body'])
        body['payload']['record']['record_key'] = 'different-resource'
        obs['exchanges'][ref]['response']['body'] = encoded(body).decode(); seal(obs, ref)
    case('wrong-read-resource-body-rehashed', variant='read', mutate=mutate_document('observations', wrong_read_resource))
    def json_error(obs):
        ref = main_ref(obs); obs['exchanges'][ref]['response']['body'] = encoded({'error': {'code': 'LOGIN_REQUIRED'}}).decode(); seal(obs, ref)
    case('json-error200-all-checksums-recomputed', variant='read', mutate=mutate_document('observations', json_error))
    def disclosure(obs):
        ref = main_ref(obs); obs['exchanges'][ref]['response']['body'] = encoded({'failure': {'kind': 'DENIED'}, 'payload': {'record': {'amount': '100.00'}}}).decode(); seal(obs, ref)
    case('disclosure-with-forged-pass-rehashed', mutate=mutate_document('observations', disclosure))
    case('self-declared-verified', mutate=mutate_document('coverage', lambda c: c['assertions'][0].update(verified=True)))
    case('guard-self-declared-pass', variant='blocked', mutate=mutate_document('coverage', lambda c: c['assertions'][0].update(oracleResult='pass')))
    case('missing-required-claim', variants=('pass', 'pass'), mutate=mutate_document('coverage', lambda c: c['assertions'].pop()))
    case('false-security-pass', mutate=mutate_document('summary', lambda s: s.update(securityVerdict='pass', gateDecision='allow')))
    case('wrong-summary-count', mutate=mutate_document('summary', lambda s: s['applicationOracleCounts'].update(**{'pass': 99})))
    case('duplicate-track-summary', mutate=mutate_document('summary', lambda s: s['tracks'].__setitem__(1, copy.deepcopy(s['tracks'][0]))))
    case('failed-phase-summary-complete', variant='phase-failed', mutate=mutate_document('summary', lambda s: s.update(executionStatus='completed', evidenceStatus='complete')))
    case('unknown-schema-version', mutate=lambda b: rewrite_manifest(b, lambda m: m.update(schemaVersion='9.0')))
    case('nested-wrong-version', mutate=mutate_document('observations', lambda o: o.update(schemaVersion='1.4')))
    case('wrong-fixture-pin', mutate=mutate_document('fixture', lambda f: f['resources'][0].update(wireId='forged-resource')))

    def changed_plan(bundle):
        p = document(bundle, 'plan'); p['assertions'][0]['oracle']['responseEquals'][0]['value'] = 'FORGED'
        save(bundle, 'plan', p); reanchor(bundle, keep_old_pin=True)
    case('changed-plan-internal-hashes-recomputed-external-pin-fixed', mutate=changed_plan)
    def duplicate_contract(bundle):
        p = document(bundle, 'plan'); p['assertions'].append(copy.deepcopy(p['assertions'][0]))
        save(bundle, 'plan', p); reanchor(bundle)
    case('trusted-pin-cannot-excuse-duplicate-contract', mutate=duplicate_contract)
    def fixture_ownership(bundle):
        f, p = document(bundle, 'fixture'), document(bundle, 'plan')
        f['resources'][0]['ownerSubject'] = -7
        p['assertions'][0]['resource']['ownerSubject'] = -7
        save(bundle, 'fixture', f); p['fixtureHash'] = sha(encoded(f)); save(bundle, 'plan', p); reanchor(bundle)
    case('trusted-pin-cannot-excuse-invalid-fixture-ownership', mutate=fixture_ownership)
    def cross_phase_contract(bundle):
        p = document(bundle, 'plan'); p['assertions'][0]['ownerPositive']['binding']['phaseId'] = p['phases'][1]['phaseId']
        save(bundle, 'plan', p); reanchor(bundle)
    case('trusted-pin-cannot-excuse-mixed-control-phase', variants=('pass', 'pass'), mutate=cross_phase_contract)

    def reuse_late(obs):
        next(iter(obs['reuseRecords'].values()))['completedAt'] = 15
    case('reuse-after-phase-failure', variant='reuse', mutate=mutate_document('observations', reuse_late))
    def reuse_epoch(obs):
        rec = next(iter(obs['reuseRecords'].values()))
        rec['authEpochs'][next(iter(rec['authEpochs']))] = 'different-epoch'
    case('reuse-wrong-epoch', variant='reuse', mutate=mutate_document('observations', reuse_epoch))

    def page_mutation(bundle, mutate):
        m = json.loads((bundle['root'] / 'manifest.json').read_bytes())
        p = bundle['root'] / m['reports'][0]['chunkPaths'][0]
        value = json.loads(p.read_bytes()); mutate(value); p.write_bytes(encoded(value)); repack(bundle['root'])
    case('report-page-content-rehashed', mutate=lambda b: page_mutation(b, lambda p: p.update(content=p['content'] + 'x', charactersReturned=p['charactersReturned'] + 1)))
    case('report-page-wrong-origin-path', mutate=lambda b: page_mutation(b, lambda p: p.update(reportPath='/zap/wrk/foreign.json')))
    case('report-page-wrong-sha', mutate=lambda b: page_mutation(b, lambda p: p.update(artifactSha256='0' * 64)))
    case('report-premature-eof', mutate=lambda b: page_mutation(b, lambda p: p.update(endOfFile=True, nextOffset=None)))
    def missing_chunk(bundle):
        rewrite_manifest(bundle, lambda m: m['reports'][0]['chunkPaths'].pop(1))
    case('report-missing-chunk', mutate=missing_chunk)
    def duplicate_offset(bundle):
        m = json.loads((bundle['root'] / 'manifest.json').read_bytes())
        p = bundle['root'] / m['reports'][0]['chunkPaths'][1]
        value = json.loads(p.read_bytes()); value['offset'] = 0; p.write_bytes(encoded(value)); repack(bundle['root'])
    case('report-duplicate-offset', mutate=duplicate_offset)
    def orphan_page(bundle):
        m = json.loads((bundle['root'] / 'manifest.json').read_bytes()); p = bundle['root'] / m['reports'][0]['chunkPaths'][-1]
        value = json.loads(p.read_bytes()); value['offset'] += 1; p.write_bytes(encoded(value)); repack(bundle['root'])
    case('report-noncontiguous-unicode-offset', mutate=orphan_page)
    return result
