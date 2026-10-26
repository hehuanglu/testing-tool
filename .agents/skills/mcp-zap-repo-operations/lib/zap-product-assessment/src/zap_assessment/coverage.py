"""Coverage predicate v2, independent of the pilot's status-code collector.

Inputs are a locked assertion contract and normalized raw exchanges plus boundary
records. No self-declared ``verified`` or ``oracleResult`` input is consulted.
This module does not attest a boundary's honesty or implement bundle verification.
"""
import hashlib
import json
import math
import re
from decimal import Decimal
from urllib.parse import urlsplit

BINDING_FIELDS = ('assessmentId', 'planHash', 'targetBinding', 'buildRef', 'actorRef',
                  'resourceRef', 'operation', 'techniqueId', 'phaseId', 'oracleVersion')
CONTEXT_FIELDS = ('assessmentId', 'planHash', 'targetBinding', 'buildRef', 'phaseId', 'oracleVersion')
MISSING = object()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False,
                      allow_nan=False).encode('utf-8')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _binding(value):
    return isinstance(value, dict) and all(
        isinstance(value.get(k), str) and bool(value[k]) for k in BINDING_FIELDS)


def _time(value):
    return type(value) in (int, float) and math.isfinite(value)


def _pointer(value, pointer):
    if not isinstance(pointer, str) or (pointer and not pointer.startswith('/')):
        return MISSING
    for part in pointer.split('/')[1:] if pointer else []:
        if '~' in part.replace('~1', '').replace('~0', ''):
            return MISSING
        part = part.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict):
            value = value.get(part, MISSING)
        elif isinstance(value, list) and part.isdigit() and str(int(part)) == part:
            value = value[int(part)] if int(part) < len(value) else MISSING
        else:
            return MISSING
    return value


def _equal(left, right):
    # bool must not compare equal to numeric fixture IDs/balances.
    if left is MISSING or right is MISSING:
        return False
    if type(left) is bool or type(right) is bool:
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float, Decimal)) and isinstance(right, (int, float, Decimal)):
        return Decimal(str(left)) == Decimal(str(right))
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(_equal(v, right[k]) for k, v in left.items())
    if isinstance(left, list):
        return len(left) == len(right) and all(_equal(a, b) for a, b in zip(left, right))
    return left == right


def evaluate(assertion, evidence):
    """Return separate observation/execution/oracle dimensions with reason codes.

    G1 supports bound direct API reads, denials, validation and state transitions.
    Active sink proof is not inferred from a completed scanner lifecycle. Reuse of
    a failed phase needs an explicit record and completed state/auth/timing proof.
    """
    reasons = set()
    result = {'observed': False, 'requested': False, 'targetRequested': False,
              'techniqueExecuted': False, 'responseSource': 'unknown',
              'oracleResult': 'inconclusive', 'reasonCodes': []}

    def finish(oracle='inconclusive'):
        if reasons & {'disclosure_detected', 'post_state_mismatch'}:
            oracle = 'fail'
        result['oracleResult'] = oracle
        result['reasonCodes'] = sorted(reasons)
        return result

    if not isinstance(assertion, dict) or not isinstance(evidence, dict):
        reasons.add('invalid_contract_or_evidence')
        return finish()
    binding = assertion.get('binding', {})
    exchanges = evidence.get('exchanges', {})
    boundaries = evidence.get('boundaries', {})
    used = {}
    if not isinstance(exchanges, dict) or not isinstance(boundaries, dict):
        reasons.add('invalid_evidence_inventory')
        return finish()
    primary = exchanges.get(assertion.get('primaryRef'))
    if isinstance(primary, dict):
        result['requested'] = isinstance(primary.get('request'), dict)
        result['observed'] = isinstance(primary.get('response'), dict)
    if assertion.get('schemaVersion') != '2.0' or not _binding(binding):
        reasons.add('missing_required_binding')
        return finish()

    def exchange(spec):
        if not isinstance(spec, dict) or not _binding(spec.get('binding')):
            reasons.add('missing_control_binding')
            return None
        expected = spec['binding']
        if any(expected[k] != binding[k] for k in CONTEXT_FIELDS):
            reasons.add('wrong_control_context')
            return None
        rec = exchanges.get(spec.get('ref'))
        if not isinstance(rec, dict):
            reasons.add('missing_exchange')
            return None
        actual = rec.get('binding', {})
        if any(actual.get(k) != expected[k] for k in BINDING_FIELDS):
            reasons.update('wrong_' + k for k in BINDING_FIELDS if actual.get(k) != expected[k])
            return None
        if not isinstance(spec.get('request'), dict) or rec.get('request') != spec['request']:
            reasons.add('request_mismatch')
            return None
        verb, _, template = expected['operation'].partition(' ')
        request = rec['request']
        url = urlsplit(request.get('path', ''))
        parts = re.split(r'(\{[^}]+\})', template)
        route = ''.join('[^/]+' if p.startswith('{') and p.endswith('}') else re.escape(p) for p in parts)
        if (verb not in ('GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS', 'TRACE')
                or request.get('method') != verb or not template.startswith('/')
                or url.scheme or url.netloc or url.fragment or not re.fullmatch(route, url.path)):
            reasons.add('operation_request_mismatch')
            return None
        if not isinstance(rec.get('response'), dict):
            reasons.add('missing_response')
            return None
        status = rec['response'].get('status')
        if type(status) is not int or not 100 <= status <= 599:
            reasons.add('invalid_http_status')
            return None
        event = boundaries.get(spec.get('ref'))
        if not isinstance(event, dict):
            reasons.add('missing_boundary_correlation')
            return None
        source = event.get('source', 'unknown')
        if (not rec.get('requestId') or not rec.get('responseId') or not rec.get('authEpoch')
                or not rec.get('clockId') or not _time(rec.get('at'))):
            reasons.add('incomplete_boundary_correlation')
            return None
        if (event.get('binding') != actual or any(event.get(k) != rec.get(k) for k in
                ('requestId', 'responseId', 'at', 'authEpoch', 'clockId', 'authMode'))):
            reasons.add('boundary_correlation_mismatch')
            return None
        try:
            hashes_match = (event.get('requestSha256') == digest(rec['request'])
                            and event.get('responseSha256') == digest(rec['response']))
        except (ValueError, TypeError):
            hashes_match = False
        if not hashes_match:
            reasons.add('boundary_content_mismatch')
            return None
        if spec.get('ref') == assertion.get('primaryRef'):
            result['responseSource'] = source if source in ('target', 'guard', 'infrastructure') else 'unknown'
        if source != 'target':
            reasons.add({'guard': 'guard_response', 'infrastructure': 'infrastructure_response'}.get(source, 'unknown_response_source'))
            return None
        if spec.get('ref') == assertion.get('primaryRef'):
            result['targetRequested'] = True
            result['techniqueExecuted'] = binding['techniqueId'] == 'direct-api'
        used[spec['ref']] = rec
        expected_statuses = spec.get('statuses', [])
        if (not expected_statuses or any(type(s) is not int or not 100 <= s <= 599 for s in expected_statuses)
                or status not in expected_statuses):
            reasons.add('unexpected_control_status')
            return None
        return rec

    def data(rec):
        if rec is None:
            return MISSING
        response = rec['response']
        media = response.get('contentType', '').split(';')[0].strip().lower()
        if media != 'application/json' and not media.endswith('+json'):
            reasons.add('non_json_or_login_page')
            return MISSING
        def unique(pairs):
            value = {}
            for key, item in pairs:
                if key in value:
                    raise ValueError('duplicate JSON field')
                value[key] = item
            return value
        def invalid(_):
            raise ValueError('invalid JSON number')
        try:
            return json.loads(response['body'], parse_float=Decimal,
                              parse_constant=invalid, object_pairs_hook=unique)
        except (KeyError, ValueError, TypeError):
            reasons.add('invalid_response_json')
            return MISSING

    def identity(rec):
        if rec is None:
            return False
        actor = rec['binding']['actorRef']
        if actor == 'anonymous':
            if rec.get('authMode') == 'anonymous' and rec['authEpoch'] == 'anonymous':
                return True
            reasons.add('anonymous_binding_mismatch')
            return False
        identities = assertion.get('identities', {})
        identity = identities.get(actor) if isinstance(identities, dict) else None
        if not isinstance(identity, dict) or not isinstance(identity.get('proof'), dict):
            reasons.add('missing_identity')
            return False
        proof = identity['proof']
        if (proof.get('binding', {}).get('actorRef') != actor
                or proof.get('binding', {}).get('resourceRef') != 'identity:' + actor):
            reasons.add('wrong_identity_binding')
            return False
        observed = exchange(proof)
        obj = data(observed)
        if obj is MISSING:
            return False
        if (identity.get('subject') is None or identity.get('role') is None
                or not _equal(_pointer(obj, identity.get('subjectPointer')), identity['subject'])
                or not _equal(_pointer(obj, identity.get('rolePointer')), identity['role'])):
            reasons.add('identity_mismatch')
            return False
        max_age = identity.get('maxAgeSeconds')
        if (not _time(max_age) or not 0 < max_age <= 5
                or observed['clockId'] != rec['clockId']
                or not 0 <= rec['at'] - observed['at'] <= max_age
                or rec.get('authMode') != 'authenticated'
                or observed.get('authMode') != 'authenticated'
                or observed['authEpoch'] != rec['authEpoch']):
            reasons.add('auth_gap')
            return False
        return True

    oracle = assertion.get('oracle', {})
    statuses = oracle.get('statuses', [])
    if not statuses or any(type(s) is not int for s in statuses):
        reasons.add('missing_status_contract')
        return finish()
    main = exchange({'ref': assertion.get('primaryRef'), 'binding': binding,
                     'request': assertion.get('request'), 'statuses': statuses})
    if main is None:
        return finish()
    result['targetRequested'] = True
    if binding['actorRef'] != 'anonymous' and main['response'].get('status') == 401:
        reasons.add('auth_gap')
        return finish()
    phase = evidence.get('phases', {}).get(binding['phaseId'], {})
    reuse = evidence.get('reuseRecords', {}).get(assertion.get('assertionId'))
    needs_reuse = (phase.get('status') == 'failed'
                   and assertion.get('reusePolicy') == 'completed-before-phase-failure'
                   and isinstance(reuse, dict))
    if phase.get('status') != 'completed' and not needs_reuse:
        reasons.add('phase_not_completed_or_reuse_unproven')
    if binding['techniqueId'] != 'direct-api':
        reasons.add('unsupported_technique_or_sink_unproven')
    else:
        result['techniqueExecuted'] = True
    main_data = data(main)
    identity_ok = identity(main)
    resource = assertion.get('resource', {})
    owner_spec = assertion.get('ownerPositive')
    owner = exchange(owner_spec) if owner_spec else None
    if owner is None:
        reasons.add('missing_owner_positive')
    owner_data = data(owner)
    owner_ok = identity(owner)
    if (resource.get('resourceRef') != binding['resourceRef'] or resource.get('wireId') is None
            or not resource.get('ownerActorRef') or resource.get('ownerSubject') is None):
        reasons.add('missing_resource_binding')
    elif owner is not None:
        owner_identity = assertion.get('identities', {}).get(resource['ownerActorRef'], {})
        if (owner['binding']['resourceRef'] != binding['resourceRef']
                or owner['binding']['actorRef'] != resource['ownerActorRef']
                or not _equal(owner_identity.get('subject', MISSING), resource['ownerSubject'])
                or not _equal(_pointer(owner_data, resource.get('idPointer')), resource['wireId'])
                or not _equal(_pointer(owner_data, resource.get('ownerPointer')), resource['ownerSubject'])):
            reasons.add('owner_resource_mismatch')
        if owner['clockId'] != main['clockId'] or owner['at'] >= main['at']:
            reasons.add('owner_positive_not_before_request')
    # Missing prerequisites cannot be patched by a status, an error page, or an input flag.
    if reasons or not identity_ok or not owner_ok or main_data is MISSING:
        return finish()

    kind = oracle.get('kind')
    if kind not in ('resource-read', 'denial', 'validation', 'state-transition'):
        reasons.add('unsupported_oracle')
        return finish()
    if kind == 'resource-read' and (
            not _equal(_pointer(main_data, resource.get('idPointer')), resource['wireId'])
            or not _equal(_pointer(main_data, resource.get('ownerPointer')), resource['ownerSubject'])):
        reasons.add('response_resource_mismatch')
        return finish()
    checks = oracle.get('responseEquals', [])
    if not checks or any(not isinstance(c, dict) or 'value' not in c or not c.get('pointer') for c in checks):
        reasons.add('missing_response_oracle')
        return finish()
    response_ok = all(_equal(_pointer(main_data, c['pointer']), c['value']) for c in checks)
    if not response_ok:
        reasons.add('response_oracle_mismatch')
    if kind == 'denial':
        pointers = oracle.get('forbiddenPointers')
        if not isinstance(pointers, list) or not pointers or not all(isinstance(p, str) and p.startswith('/') for p in pointers):
            reasons.add('missing_disclosure_oracle')
            return finish()
        if any(_pointer(main_data, p) is not MISSING for p in pointers):
            reasons.add('disclosure_detected')
    mutation = assertion['request'].get('method') not in ('GET', 'HEAD', 'OPTIONS')
    if mutation or kind in ('validation', 'state-transition') or needs_reuse:
        before = exchange(assertion.get('preState'))
        after = exchange(assertion.get('postState'))
        if before is None or after is None:
            reasons.add('missing_post_state' if after is None else 'missing_pre_state')
            return finish('fail' if 'disclosure_detected' in reasons else 'inconclusive')
        pre_data, post_data = data(before), data(after)
        before_ok, after_ok = identity(before), identity(after)
        if not before_ok or not after_ok or pre_data is MISSING or post_data is MISSING:
            return finish()
        if any(r['binding']['resourceRef'] != binding['resourceRef'] or
               r['binding']['actorRef'] != resource['ownerActorRef'] for r in (before, after)):
            reasons.add('state_resource_mismatch')
            return finish()
        if any(not _equal(_pointer(obj, resource.get('idPointer')), resource['wireId'])
               or not _equal(_pointer(obj, resource.get('ownerPointer')), resource['ownerSubject'])
               for obj in (pre_data, post_data)):
            reasons.add('state_resource_mismatch')
            return finish()
        if (before['clockId'] != main['clockId'] or after['clockId'] != main['clockId']
                or not before['at'] < main['at'] < after['at']):
            reasons.add('state_order_mismatch')
            return finish()
        pre = _pointer(pre_data, assertion.get('statePointer'))
        post = _pointer(post_data, assertion.get('statePointer'))
        if pre is MISSING or post is MISSING or 'expectedPreState' not in assertion:
            reasons.add('missing_state_or_precondition')
            return finish()
        if not _equal(pre, assertion['expectedPreState']):
            reasons.add('precondition_mismatch')
            return finish()
        expected_post = pre if kind in ('resource-read', 'denial', 'validation') else assertion.get('expectedPostState', MISSING)
        if expected_post is MISSING:
            reasons.add('missing_post_state_oracle')
            return finish()
        if not _equal(post, expected_post):
            reasons.add('post_state_mismatch')
    if needs_reuse:
        completed, failed = reuse.get('completedAt'), phase.get('failedAt')
        epochs = {r['binding']['actorRef']: r['authEpoch'] for r in used.values()}
        if (reuse.get('binding') != binding or not reuse.get('recordRef')
                or reuse.get('clockId') != main['clockId'] or phase.get('clockId') != main['clockId']
                or reuse.get('authEpochs') != epochs
                or reuse.get('stateBeforeRef') != assertion.get('preState', {}).get('ref')
                or reuse.get('stateAfterRef') != assertion.get('postState', {}).get('ref')
                or set(reuse.get('exchangeRefs', [])) != set(used)
                or not _time(completed) or not _time(failed)
                or not all(r['clockId'] == main['clockId'] and r['at'] <= completed for r in used.values())
                or not completed < failed):
            reasons.add('invalid_phase_reuse')
    violations = {'response_oracle_mismatch', 'disclosure_detected', 'post_state_mismatch'}
    return finish('fail' if reasons & violations else 'inconclusive' if reasons else 'pass')
