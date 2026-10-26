"""Independent semantic replay of v2 proof contracts.

This audit deliberately does not import the coverage builder, its predicate,
helpers, or self-declared verdicts. Shared JSON schemas describe shape only.
"""
import copy
from decimal import Decimal
import hashlib
import json
import re
from urllib.parse import urlsplit

from .contracts import canonical
from .evidence import EvidenceInvalid

ABSENT = object()
CONTEXT = ('assessmentId', 'planHash', 'targetBinding', 'buildRef', 'phaseId', 'oracleVersion')


class ProofUnavailable(Exception):
    pass


def _index(rows, key):
    result = {}
    for row in rows:
        if row[key] in result:
            raise EvidenceInvalid('duplicate_semantic_identifier')
        result[row[key]] = row
    return result


def _typed(value):
    if value is ABSENT:
        return ('missing',)
    if value is None or isinstance(value, (str, bool)):
        return type(value).__name__, value
    if isinstance(value, (int, float, Decimal)):
        return 'number', Decimal(str(value))
    if isinstance(value, list):
        return 'array', tuple(map(_typed, value))
    return 'object', tuple(sorted((k, _typed(v)) for k, v in value.items()))


def _project(value, pointer):
    for encoded in pointer.split('/')[1:] if pointer else []:
        key = encoded.replace('~1', '/').replace('~0', '~')
        if isinstance(value, dict) and key in value:
            value = value[key]
        elif isinstance(value, list) and re.fullmatch('0|[1-9][0-9]*', key) and int(key) < len(value):
            value = value[int(key)]
        else:
            return ABSENT
    return value


def _object(rec):
    media = rec['response']['contentType'].split(';')[0].strip().lower()
    if not re.fullmatch(r'application/(?:json|[a-z0-9!#$&^_.+-]+\+json)', media):
        raise ProofUnavailable('not_json_or_login_page')
    def unique(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ProofUnavailable('ambiguous_response_json')
            result[key] = value
        return result
    def constant(_):
        raise ProofUnavailable('ambiguous_response_json')
    try:
        return json.loads(rec['response']['body'], object_pairs_hook=unique,
                          parse_float=Decimal, parse_constant=constant)
    except (ValueError, TypeError, ArithmeticError, UnicodeError, RecursionError):
        raise ProofUnavailable('invalid_response_json')


class IndependentAudit:
    def __init__(self, plan, fixture, observations, plan_hash):
        self.plan, self.fixture, self.obs, self.plan_hash = plan, fixture, observations, plan_hash
        self.actors = _index(fixture['actors'], 'actorRef')
        self.resources = _index(fixture['resources'], 'resourceRef')
        self.phases = _index(plan['phases'], 'phaseId')
        self.assertions = _index(plan['assertions'], 'assertionId')
        self.contracts = {key: self.expand(value) for key, value in self.assertions.items()}
        self.specs = {}
        self._validate_contracts()
        self._validate_records()

    def expand(self, source):
        result = copy.deepcopy(source)
        specs = [result, *(i['proof'] for i in result['identities'].values())]
        specs.extend(result[k] for k in ('ownerPositive', 'preState', 'postState') if k in result)
        for spec in specs:
            if spec['binding']['planHash'] != '$self':
                raise EvidenceInvalid('plan_binding_requires_self_reference')
            spec['binding']['planHash'] = self.plan_hash
        return result

    @staticmethod
    def main_spec(assertion):
        return {'ref': assertion['primaryRef'], 'binding': assertion['binding'],
                'request': assertion['request'], 'statuses': assertion['oracle']['statuses']}

    def _register(self, spec, assertion):
        b, primary = spec['binding'], assertion['binding']
        if any(b[k] != primary[k] for k in CONTEXT):
            raise EvidenceInvalid('control_context_disagrees_with_assertion')
        if b['actorRef'] not in self.actors:
            raise EvidenceInvalid('unknown_contract_actor')
        old = self.specs.get(spec['ref'])
        if old is not None and old != spec:
            raise EvidenceInvalid('conflicting_exchange_contract')
        self.specs[spec['ref']] = spec

    def _validate_contracts(self):
        for key in ('assessmentId', 'targetBinding', 'buildRef'):
            if self.plan[key] != self.fixture[key]:
                raise EvidenceInvalid('fixture_context_mismatch')
        if len({a['identityResourceRef'] for a in self.actors.values()}) != len(self.actors):
            raise EvidenceInvalid('duplicate_identity_resource')
        if set(self.resources) & {a['identityResourceRef'] for a in self.actors.values()}:
            raise EvidenceInvalid('identity_resource_alias')
        for resource in self.resources.values():
            owner = self.actors.get(resource['ownerActorRef'])
            if not owner or owner['authMode'] != 'authenticated' or _typed(owner['subject']) != _typed(resource['ownerSubject']):
                raise EvidenceInvalid('fixture_ownership_mismatch')
        for actor in self.actors.values():
            if actor['authMode'] == 'authenticated' and actor['subject'] is None:
                raise EvidenceInvalid('authenticated_actor_subject_missing')
        for phase in self.phases.values():
            if phase['trackId'] not in self.plan['requiredTracks']:
                raise EvidenceInvalid('unknown_phase_track')
        for a in self.contracts.values():
            b = a['binding']
            if (any(b[k] != self.plan[k] for k in ('assessmentId', 'targetBinding', 'buildRef'))
                    or b['phaseId'] not in self.phases or b['actorRef'] not in self.actors
                    or a['trackId'] != self.phases[b['phaseId']]['trackId']):
                raise EvidenceInvalid('assertion_context_mismatch')
            resource = self.resources.get(b['resourceRef'])
            if resource is None or _typed(a['resource']) != _typed(resource):
                raise EvidenceInvalid('assertion_fixture_binding_mismatch')
            self._register(self.main_spec(a), a)
            for actor_ref, identity in a['identities'].items():
                actor = self.actors.get(actor_ref)
                proof = identity['proof']['binding']
                if (not actor or actor['authMode'] != 'authenticated'
                        or _typed(identity['subject']) != _typed(actor['subject']) or identity['role'] != actor['role']
                        or proof['actorRef'] != actor_ref or proof['resourceRef'] != actor['identityResourceRef']):
                    raise EvidenceInvalid('identity_contract_fixture_mismatch')
                self._register(identity['proof'], a)
            for key in ('ownerPositive', 'preState', 'postState'):
                if key in a:
                    proof = a[key]
                    if proof['binding']['actorRef'] != resource['ownerActorRef'] or proof['binding']['resourceRef'] != resource['resourceRef']:
                        raise EvidenceInvalid('control_owner_resource_binding_mismatch')
                    self._register(proof, a)

    @staticmethod
    def _route(binding, request):
        method, _, path = binding['operation'].partition(' ')
        url = urlsplit(request['path'])
        regex = ''.join('[^/]+' if part.startswith('{') and part.endswith('}') else re.escape(part)
                        for part in re.split(r'(\{[^}]+\})', path))
        return (path.startswith('/') and method == request['method'] and not url.scheme
                and not url.netloc and not url.fragment and bool(re.fullmatch(regex, url.path)))

    def _validate_records(self):
        if self.obs['phases'].keys() != self.phases.keys():
            raise EvidenceInvalid('phase_inventory_mismatch')
        if not self.obs['boundaries'].keys() <= self.obs['exchanges'].keys():
            raise EvidenceInvalid('orphan_boundary_record')
        if not self.obs['exchanges'].keys() <= self.specs.keys():
            raise EvidenceInvalid('unreferenced_exchange')
        if not self.obs['reuseRecords'].keys() <= self.contracts.keys():
            raise EvidenceInvalid('unreferenced_reuse_record')
        request_ids, response_ids = set(), set()
        for ref, rec in self.obs['exchanges'].items():
            spec = self.specs[ref]
            if rec['binding'] != spec['binding'] or _typed(rec['request']) != _typed(spec['request']):
                raise EvidenceInvalid('exchange_binding_or_request_mismatch')
            if not self._route(rec['binding'], rec['request']):
                raise EvidenceInvalid('operation_request_mismatch')
            if rec['requestId'] in request_ids or rec['responseId'] in response_ids:
                raise EvidenceInvalid('duplicate_request_or_response_identity')
            request_ids.add(rec['requestId']); response_ids.add(rec['responseId'])
            phase = self.obs['phases'][rec['binding']['phaseId']]
            actor = self.actors[rec['binding']['actorRef']]
            if rec['clockId'] != phase['clockId'] or rec['authMode'] != actor['authMode']:
                raise EvidenceInvalid('exchange_clock_or_actor_mode_mismatch')
            if phase['status'] == 'completed' and 'completedAt' in phase and phase['completedAt'] < rec['at']:
                raise EvidenceInvalid('phase_completed_before_exchange')
            event = self.obs['boundaries'].get(ref)
            if event is not None:
                for key in ('binding', 'requestId', 'responseId', 'at', 'authEpoch', 'clockId', 'authMode'):
                    if _typed(event[key]) != _typed(rec[key]):
                        raise EvidenceInvalid('boundary_correlation_mismatch')
                for payload in ('request', 'response'):
                    if event[payload + 'Sha256'] != hashlib.sha256(canonical(rec[payload])).hexdigest():
                        raise EvidenceInvalid('boundary_content_mismatch')

    def _exchange(self, spec, used):
        if not spec:
            raise ProofUnavailable('required_control_missing')
        rec = self.obs['exchanges'].get(spec['ref'])
        event = self.obs['boundaries'].get(spec['ref'])
        if rec is None or event is None:
            raise ProofUnavailable('exchange_or_boundary_missing')
        if event['source'] != 'target':
            raise ProofUnavailable('response_not_from_target')
        used.add(spec['ref'])
        if rec['response']['status'] not in spec['statuses']:
            raise ProofUnavailable('response_status_not_in_contract')
        return rec

    def _identity(self, assertion, record, used):
        actor_ref = record['binding']['actorRef']
        actor = self.actors[actor_ref]
        if actor['authMode'] == 'anonymous':
            if record['authEpoch'] != 'anonymous':
                raise ProofUnavailable('anonymous_epoch_mismatch')
            return
        identity = assertion['identities'].get(actor_ref)
        if identity is None:
            raise ProofUnavailable('identity_proof_missing')
        witness = self._exchange(identity['proof'], used)
        body = _object(witness)
        if (_typed(_project(body, identity['subjectPointer'])) != _typed(actor['subject'])
                or _typed(_project(body, identity['rolePointer'])) != _typed(actor['role'])):
            raise ProofUnavailable('actor_or_role_not_confirmed')
        if (witness['authEpoch'] != record['authEpoch'] or witness['clockId'] != record['clockId']
                or not 0 <= record['at'] - witness['at'] <= identity['maxAgeSeconds']):
            raise ProofUnavailable('auth_epoch_or_freshness_gap')

    def _owned_object(self, assertion, spec, used):
        record = self._exchange(spec, used)
        self._identity(assertion, record, used)
        body, resource = _object(record), assertion['resource']
        if (_typed(_project(body, resource['idPointer'])) != _typed(resource['wireId'])
                or _typed(_project(body, resource['ownerPointer'])) != _typed(resource['ownerSubject'])):
            raise ProofUnavailable('object_or_ownership_not_confirmed')
        return record, body

    def _state(self, a, main, used):
        before, pre = self._owned_object(a, a.get('preState'), used)
        after, post = self._owned_object(a, a.get('postState'), used)
        if not before['at'] < main['at'] < after['at']:
            raise ProofUnavailable('state_control_order_invalid')
        if 'statePointer' not in a or 'expectedPreState' not in a:
            raise ProofUnavailable('state_precondition_missing')
        pre, post = _project(pre, a['statePointer']), _project(post, a['statePointer'])
        if pre is ABSENT or post is ABSENT or _typed(pre) != _typed(a['expectedPreState']):
            raise ProofUnavailable('state_precondition_unmet')
        if a['oracle']['kind'] == 'state-transition':
            if 'expectedPostState' not in a:
                raise ProofUnavailable('post_state_oracle_missing')
            expected = a['expectedPostState']
        else:
            expected = pre
        return _typed(post) == _typed(expected)

    def _phase_reuse(self, a, main, used):
        phase = self.obs['phases'][a['binding']['phaseId']]
        if phase['status'] == 'completed':
            return True
        record = self.obs['reuseRecords'].get(a['assertionId'])
        if phase['status'] != 'failed' or a.get('reusePolicy') != 'completed-before-phase-failure' or not record:
            return False
        epochs = {self.obs['exchanges'][r]['binding']['actorRef']: self.obs['exchanges'][r]['authEpoch'] for r in used}
        return (record['binding'] == a['binding'] and record['clockId'] == main['clockId']
                and record['clockId'] == phase['clockId'] and record['authEpochs'] == epochs
                and set(record['exchangeRefs']) == used
                and record['stateBeforeRef'] == a.get('preState', {}).get('ref')
                and record['stateAfterRef'] == a.get('postState', {}).get('ref')
                and 'failedAt' in phase and record['completedAt'] < phase['failedAt']
                and all(self.obs['exchanges'][r]['at'] <= record['completedAt'] for r in used))

    def assertion(self, a):
        used, violations = set(), []
        try:
            main = self._exchange(self.main_spec(a), used)
            if self.actors[a['binding']['actorRef']]['authMode'] != 'anonymous' and main['response']['status'] == 401:
                raise ProofUnavailable('protected_authentication_lost')
            if a['binding']['techniqueId'] != 'direct-api':
                raise ProofUnavailable('technique_or_sink_not_supported')
            self._identity(a, main, used)
            positive, _ = self._owned_object(a, a.get('ownerPositive'), used)
            if positive['at'] >= main['at']:
                raise ProofUnavailable('positive_control_not_before_request')
            body = _object(main)
            oracle = a['oracle']
            if oracle['kind'] == 'resource-read':
                resource = a['resource']
                if any(_typed(_project(body, resource[p])) != _typed(resource[v])
                       for p, v in [('idPointer', 'wireId'), ('ownerPointer', 'ownerSubject')]):
                    raise ProofUnavailable('read_resource_not_confirmed')
            if any(_typed(_project(body, c['pointer'])) != _typed(c['value']) for c in oracle['responseEquals']):
                violations.append('response_oracle_violated')
            if oracle['kind'] == 'denial':
                if not oracle.get('forbiddenPointers'):
                    raise ProofUnavailable('disclosure_oracle_missing')
                if any(_project(body, pointer) is not ABSENT for pointer in oracle['forbiddenPointers']):
                    violations.append('disclosure_confirmed')
            reuse_needed = self.obs['phases'][a['binding']['phaseId']]['status'] != 'completed'
            if a['request']['method'] not in ('GET', 'HEAD', 'OPTIONS') or oracle['kind'] in ('validation', 'state-transition') or reuse_needed:
                if not self._state(a, main, used):
                    violations.append('post_state_oracle_violated')
            if not self._phase_reuse(a, main, used):
                raise ProofUnavailable('phase_incomplete_or_reuse_not_proven')
            outcome = 'fail' if violations else 'pass'
            reasons = violations
            complete = True
        except ProofUnavailable as unavailable:
            # Confirmed disclosure/state violations survive later incomplete proof.
            outcome = 'fail' if set(violations) & {'disclosure_confirmed', 'post_state_oracle_violated'} else 'inconclusive'
            reasons = [*violations, str(unavailable)]
            complete = False
        return {'assertionId': a['assertionId'], 'oracleResult': outcome, 'proofComplete': complete, 'reasonCodes': reasons}

    def run(self):
        results = [self.assertion(a) for a in self.contracts.values()]
        outcomes = {r['assertionId']: r['oracleResult'] for r in results}
        counts = {key: sum(r['oracleResult'] == key for r in results) for key in ('pass', 'fail', 'inconclusive')}
        phase_states = [p['status'] for p in self.obs['phases'].values()]
        execution = next((s for s in ('failed', 'timed_out', 'cancelled', 'running', 'not_started') if s in phase_states), 'completed')
        tracks = {}
        for track in self.plan['requiredTracks']:
            ids = [a['assertionId'] for a in self.contracts.values() if a['trackId'] == track]
            incomplete = any(self.obs['phases'][p['phaseId']]['status'] != 'completed'
                             for p in self.phases.values() if p['trackId'] == track)
            tracks[track] = ('not_run' if not ids else 'fail' if any(outcomes[i] == 'fail' for i in ids)
                             else 'inconclusive' if incomplete or any(outcomes[i] != 'pass' for i in ids) else 'pass')
        return results, {'assessmentId': self.plan['assessmentId'], 'executionStatus': execution,
                         'evidenceStatus': 'incomplete',  # required runtime tracks/gates remain unproven in this schema
                         'coverageEvidenceStatus': 'incomplete' if execution != 'completed' or any(not r['proofComplete'] for r in results) else 'complete',
                         'securityVerdict': 'fail' if counts['fail'] else 'inconclusive',
                         'cleanupStatus': 'not_applicable', 'gateDecision': 'block',
                         'applicationOracleCounts': counts, 'tracks': tracks}
