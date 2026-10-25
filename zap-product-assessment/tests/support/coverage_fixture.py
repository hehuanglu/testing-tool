"""Synthetic G1 evidence authored without importing the implementation.

No network, credentials, product IDs or security approval. Request/response hashes
use the explicitly documented normalized JSON byte representation, not HTTP bytes.
"""
import copy
import hashlib
import json


def sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def seal(evidence, ref):
    rec = evidence['exchanges'][ref]
    evidence['boundaries'][ref] = {
        'source': 'target', 'binding': copy.deepcopy(rec['binding']),
        **{k: rec[k] for k in ('requestId', 'responseId', 'at', 'authEpoch', 'clockId', 'authMode')},
        'requestSha256': sha(rec['request']), 'responseSha256': sha(rec['response'])}


def fixture():
    binding = {'assessmentId': 'synthetic-g1-001', 'planHash': 'a' * 64,
               'targetBinding': 'isolated-fixture-only', 'buildRef': 'build-fixed-001',
               'actorRef': 'B', 'resourceRef': 'wallet-owned-a',
               'operation': 'PUT /v2/wallets/{walletKey}', 'techniqueId': 'direct-api',
               'phaseId': 'api-phase-1', 'oracleVersion': 'ownership-no-disclosure/2.0'}
    path = '/v2/wallets/fixture-wallet-7'
    evidence = {'exchanges': {}, 'boundaries': {}, 'phases': {'api-phase-1': {'status': 'completed'}}}

    def record(ref, actor, at, body, status=200, resource=None, method='GET', technique='state-control'):
        b = {**binding, 'actorRef': actor, 'resourceRef': resource or binding['resourceRef'],
             'operation': method + ' ' + (path if resource is None else '/identity'), 'techniqueId': technique}
        request = {'method': method, 'path': path if resource is None else '/identity'}
        evidence['exchanges'][ref] = {
            'binding': b, 'request': request,
            'response': {'status': status, 'contentType': 'application/json',
                         'body': json.dumps(body, ensure_ascii=False)},
            'requestId': ref + '-request', 'responseId': ref + '-response',
            'at': at, 'authEpoch': actor + '-epoch-1', 'clockId': 'fixture-monotonic-1',
            'authMode': 'authenticated'}
        seal(evidence, ref)
        return {'ref': ref, 'binding': copy.deepcopy(b), 'request': copy.deepcopy(request), 'statuses': [status]}

    identities = {}
    for actor, subject in [('A', 701), ('B', 902)]:
        proof = record('identity-' + actor, actor, 10, {'subject': {'id': subject, 'role': 'member'}},
                       resource='identity:' + actor, technique='identity-control')
        identities[actor] = {'subject': subject, 'role': 'member', 'subjectPointer': '/subject/id',
                             'rolePointer': '/subject/role', 'maxAgeSeconds': 5, 'proof': proof}
    state = {'id': 'fixture-wallet-7', 'ownerId': 701, 'balance': '100.00'}
    owner = record('owner-positive', 'A', 11, {'data': state}, technique='owner-control')
    before = record('before', 'A', 11.5, {'data': state})
    after = record('after', 'A', 13, {'data': state})
    record('primary', 'B', 12, {'error': {'code': 'NO_ACCESS'}}, status=404, method='PUT', technique='direct-api')
    evidence['exchanges']['primary']['binding'] = copy.deepcopy(binding)
    evidence['exchanges']['primary']['request'] = {'method': 'PUT', 'path': path, 'body': {'balance': '90.00'}}
    seal(evidence, 'primary')
    assertion = {
        'schemaVersion': '2.0', 'assertionId': 'synthetic-denial-1', 'binding': binding,
        'primaryRef': 'primary', 'request': copy.deepcopy(evidence['exchanges']['primary']['request']),
        'identities': identities,
        'resource': {'resourceRef': binding['resourceRef'], 'wireId': state['id'],
                     'ownerActorRef': 'A', 'ownerSubject': 701,
                     'idPointer': '/data/id', 'ownerPointer': '/data/ownerId'},
        'ownerPositive': owner, 'preState': before, 'postState': after,
        'statePointer': '/data', 'expectedPreState': state,
        'oracle': {'kind': 'denial', 'statuses': [404],
                   'responseEquals': [{'pointer': '/error/code', 'value': 'NO_ACCESS'}],
                   'forbiddenPointers': ['/data/id', '/data/balance']}}
    return assertion, evidence


def change_response(evidence, ref='primary', *, status=None, body=None, content_type=None):
    rec = evidence['exchanges'][ref]
    if status is not None:
        rec['response']['status'] = status
    if body is not None:
        rec['response']['body'] = json.dumps(body, ensure_ascii=False)
    if content_type is not None:
        rec['response']['contentType'] = content_type
    seal(evidence, ref)


def case_catalog():
    """Return independent expected outcomes, including rehashed semantic negatives."""
    cases = []

    def add(case_id, mutate, expected='inconclusive', reason=None):
        assertion, evidence = fixture()
        mutate(assertion, evidence)
        cases.append({'caseId': case_id, 'expected': expected, 'expectedReason': reason,
                      'assertion': assertion, 'evidence': evidence})

    add('C06-denial404', lambda a, e: None, 'pass')

    def read(a, e):
        a['binding'].update(actorRef='A', operation='GET /v2/wallets/{walletKey}')
        a['request'] = {'method': 'GET', 'path': '/v2/wallets/fixture-wallet-7'}
        a['oracle'] = {'kind': 'resource-read', 'statuses': [200],
                       'responseEquals': [{'pointer': '/data/balance', 'value': '100.00'}]}
        r = e['exchanges']['primary']
        r.update(binding=copy.deepcopy(a['binding']), request=copy.deepcopy(a['request']), authEpoch='A-epoch-1')
        change_response(e, status=200, body={'data': a['expectedPreState']})
    add('positive-owner-read', read, 'pass')

    def validation(a, e):
        a['oracle'].update(kind='validation', statuses=[400],
                           responseEquals=[{'pointer': '/error/code', 'value': 'INVALID_INPUT'}])
        change_response(e, status=400, body={'error': {'code': 'INVALID_INPUT'}})
    add('C06-validation400', validation, 'pass')

    def transition(a, e):
        a['binding']['actorRef'] = 'A'
        e['exchanges']['primary'].update(binding=copy.deepcopy(a['binding']), authEpoch='A-epoch-1')
        a['oracle'] = {'kind': 'state-transition', 'statuses': [200],
                       'responseEquals': [{'pointer': '/updated', 'value': True}]}
        a['expectedPostState'] = {**a['expectedPreState'], 'balance': '90.00'}
        change_response(e, status=200, body={'updated': True})
        change_response(e, 'after', body={'data': a['expectedPostState']})
    add('positive-state-transition', transition, 'pass')

    def guard403(a, e):
        a['oracle']['statuses'] = [403]
        change_response(e, status=403)
        e['boundaries']['primary']['source'] = 'guard'
    add('C01-guard403', guard403, reason='guard_response')
    add('unknown-source', lambda a, e: e['boundaries']['primary'].update(source='unknown'), reason='unknown_response_source')
    add('infrastructure-response', lambda a, e: e['boundaries']['primary'].update(source='infrastructure'), reason='infrastructure_response')

    def auth_loss(a, e):
        a['oracle']['statuses'] = [401]
        change_response(e, status=401, body={'authLost': True})
    add('C01-authLoss401', auth_loss, reason='auth_gap')

    def login(a, e):
        a['oracle']['statuses'] = [200]
        change_response(e, status=200, content_type='text/html')
        e['exchanges']['primary']['response']['body'] = '<html><form>Login</form></html>'
        seal(e, 'primary')
    add('C02-login200', login, reason='non_json_or_login_page')

    for field in ('actorRef', 'buildRef', 'resourceRef', 'phaseId', 'planHash', 'assessmentId',
                  'targetBinding', 'techniqueId', 'operation', 'oracleVersion'):
        def wrong(a, e, field=field):
            e['exchanges']['primary']['binding'][field] = 'wrong-' + field
            seal(e, 'primary')
        add('C03-wrong-' + field, wrong, reason='wrong_' + field)

    add('C04-missing-owner', lambda a, e: a.pop('ownerPositive'), reason='missing_owner_positive')
    add('missing-post-state', lambda a, e: a.pop('postState'), reason='missing_post_state')
    add('missing-identity', lambda a, e: a['identities'].pop('B'), reason='missing_identity')
    add('unproven-boundary', lambda a, e: e['boundaries'].pop('primary'), reason='missing_boundary_correlation')

    def owner_wrong(a, e):
        change_response(e, 'owner-positive', body={'data': {**a['expectedPreState'], 'id': 'another-wallet'}})
    add('owner-body-wrong-resource', owner_wrong, reason='owner_resource_mismatch')

    def identity_wrong(a, e):
        change_response(e, 'identity-B', body={'subject': {'id': 701, 'role': 'member'}})
    add('identity-wrong-actor', identity_wrong, reason='identity_mismatch')

    def stale(a, e):
        e['exchanges']['identity-B']['at'] = 1
        seal(e, 'identity-B')
    add('expired-identity-window', stale, reason='auth_gap')

    def epoch(a, e):
        e['exchanges']['primary']['authEpoch'] = 'B-epoch-2'
        seal(e, 'primary')
    add('changed-auth-epoch', epoch, reason='auth_gap')

    add('failed-phase', lambda a, e: e['phases'][a['binding']['phaseId']].update(status='failed'),
        reason='phase_not_completed_or_reuse_unproven')

    def reuse(a, e):
        a['reusePolicy'] = 'completed-before-phase-failure'
        e['phases'][a['binding']['phaseId']].update(status='failed', failedAt=14, clockId='fixture-monotonic-1')
        e['reuseRecords'] = {a['assertionId']: {
            'recordRef': 'synthetic-reuse-record-1', 'binding': copy.deepcopy(a['binding']),
            'clockId': 'fixture-monotonic-1', 'completedAt': 13,
            'authEpochs': {'A': 'A-epoch-1', 'B': 'B-epoch-1'},
            'exchangeRefs': list(e['exchanges']), 'stateBeforeRef': 'before', 'stateAfterRef': 'after'}}
    add('explicit-completed-assertion-reuse', reuse, 'pass')

    def reuse_late(a, e):
        reuse(a, e)
        e['phases'][a['binding']['phaseId']]['failedAt'] = 12.5
    add('reuse-after-failure', reuse_late, reason='invalid_phase_reuse')

    def reuse_epoch(a, e):
        reuse(a, e)
        e['reuseRecords'][a['assertionId']]['authEpochs']['B'] = 'B-other'
    add('reuse-wrong-auth-epoch', reuse_epoch, reason='invalid_phase_reuse')

    def self_verified(a, e):
        a['identities'].pop('B')
        e.update(verified=True, oracleResult='pass')
        e['exchanges']['primary'].update(verified=True, oracleResult='pass')
    add('forged-verified-flag', self_verified, reason='missing_identity')

    def changed_state(a, e):
        a['oracle']['statuses'] = [403]
        change_response(e, status=403)
        change_response(e, 'after', body={'data': {**a['expectedPreState'], 'balance': '0.00'}})
    add('C05-denial403-state-changed', changed_state, 'fail', 'post_state_mismatch')

    def disclosure(a, e):
        change_response(e, body={'error': {'code': 'NO_ACCESS'}, 'data': {'balance': '100.00'}})
    add('denial-with-disclosure', disclosure, 'fail', 'disclosure_detected')

    def forged_body_marker(a, e):
        change_response(e, body={'error': {'code': 'NO_ACCESS'}, 'guardGenerated': True})
    add('body-marker-does-not-override-boundary', forged_body_marker, 'pass')

    def boundary_hash(a, e):
        e['exchanges']['primary']['response']['body'] = '{"error":{"code":"changed"}}'
    add('raw-response-hash-mismatch', boundary_hash, reason='boundary_content_mismatch')

    def active(a, e):
        a['binding']['techniqueId'] = 'SQLi'
        e['exchanges']['primary']['binding'] = copy.deepcopy(a['binding'])
        e['activeLifecycleComplete'] = True
        seal(e, 'primary')
    add('complete-without-sink-proof', active, reason='unsupported_technique_or_sink_unproven')

    def anonymous(a, e):
        a['binding']['actorRef'] = 'anonymous'
        a['oracle']['statuses'] = [401]
        e['exchanges']['primary'].update(binding=copy.deepcopy(a['binding']), authEpoch='anonymous', authMode='anonymous')
        change_response(e, status=401)
    add('positive-explicit-anonymous-denial401', anonymous, 'pass')
    return cases
