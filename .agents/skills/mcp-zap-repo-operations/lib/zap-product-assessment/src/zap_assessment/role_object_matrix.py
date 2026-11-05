"""Explicit native comparison groups; semantic roles are reviewed facts, not oracles."""
from datetime import datetime

from .business_discovery import records, strings
from .question_evidence import bound_context, read_pointer

MATRIX_VARIANTS = frozenset({'actorRef', 'fixtureRef', 'role', 'relation', 'objectRef'})
RELATIONS = {'owner-positive': 'owner', 'owner-after': 'owner', 'nonowner-negative': 'nonowner',
             'anonymous-negative': 'anonymous', 'session-before': 'session-control',
             'session-after': 'session-control'}
CONTROL_ROLES = frozenset({'owner-after', 'session-before', 'session-after'})


def _text(value):
    if not isinstance(value, str) or not value.strip() or value in ('unknown', 'unresolved', 'product-defined'):
        raise ValueError('matrix exact known text required')
    return value


def _selector(value):
    if not isinstance(value, dict) or set(value) != {'method', 'route', 'query'}:
        raise ValueError('matrix explicit method/route/query selector required')
    if (value['method'] not in ('GET', 'HEAD') or not isinstance(value['route'], str)
            or not value['route'].startswith('/') or any(c in value['route'] for c in '*{}?#')):
        raise ValueError('matrix exact read selector required')
    query = value['query']
    if (not isinstance(query, list) or any(not isinstance(pair, list) or len(pair) != 2
            or not all(isinstance(v, str) for v in pair) or not pair[0]
            or any('*' in v for v in pair) for pair in query)):
        raise ValueError('matrix exact query pairs required; empty list means no query')
    return value


def _time(value):
    _text(value)
    try:
        instant = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValueError('matrix original capture timestamp required') from None
    if instant.tzinfo is None:
        raise ValueError('matrix capture timestamp requires timezone')
    return instant


def validate_matrix(matrix, mappings, operations):
    """Check finite cohorts, exact same-object comparisons and ordered controls."""
    if not isinstance(matrix, dict) or type(matrix.get('version')) is not int or matrix['version'] != 1:
        raise ValueError('comparisonMatrix version 1 required')
    participants = records(matrix.get('participants'), 'matrix participants')
    if len(participants) < 2:
        raise ValueError('matrix needs distinct participants')
    actors, identities = set(), set()
    for participant in participants.values():
        for key in ('actorRef', 'fixtureRef', 'role', 'identityRef'):
            _text(participant.get(key))
        if participant['actorRef'] in actors or participant['identityRef'] in identities:
            raise ValueError('matrix participants require distinct actors and observed identities')
        actors.add(participant['actorRef']); identities.add(participant['identityRef'])
    groups = records(matrix.get('groups'), 'matrix groups')
    if not groups:
        raise ValueError('matrix finite comparison groups required')
    facts, times, membership = {}, {}, {oid: set() for oid in mappings}
    for oid, mapping in mappings.items():
        op = operations[oid]; actual = bound_context(op)
        fact = read_pointer(op, mapping.get('matrixContextPath'))
        if not isinstance(fact, dict) or fact != mapping.get('matrixContext'):
            raise ValueError('matrix context pointer or exact binding mismatch')
        if set(fact) != {'participantId', 'identityRef', 'semanticRole', 'groupIds', 'objectRef', 'selector', 'observedAt'}:
            raise ValueError('matrix exact observation fields required')
        participant = participants.get(fact['participantId'])
        if participant is None or any(actual.get(k) != participant[k] for k in ('actorRef', 'fixtureRef', 'role')):
            raise ValueError('matrix participant actor/fixture/role mismatch')
        if fact['identityRef'] != participant['identityRef'] or actual.get('objectRef') != _text(fact['objectRef']):
            raise ValueError('matrix observed identity or object mismatch')
        role = fact['semanticRole']
        if role not in RELATIONS or actual.get('relation') != RELATIONS[role]:
            raise ValueError('matrix semantic role/relation mismatch')
        selector = _selector(fact['selector'])
        if any(selector[k] != actual.get(k) for k in ('method', 'route')):
            raise ValueError('matrix selector differs from native operation context')
        if not strings(fact['groupIds'], 'matrix group IDs') or set(fact['groupIds']) - set(groups):
            raise ValueError('matrix unknown comparison group')
        if not mapping['observationUnits'] and role not in CONTROL_ROLES:
            raise ValueError('matrix baseline and negative require actual observation units')
        capture_path = mapping.get('capturedAtPath')
        if (not isinstance(capture_path, str) or capture_path == mapping['matrixContextPath']
                or capture_path.startswith(mapping['matrixContextPath'] + '/')
                or read_pointer(op, capture_path) != fact['observedAt']):
            raise ValueError('matrix original capture time binding mismatch')
        facts[oid], times[oid] = fact, _time(fact['observedAt'])

    def member(group, oid, participant_id, semantic_role, *, target=False):
        if oid not in facts or participant_id not in participants:
            raise ValueError('matrix missing baseline, negative or control operation')
        fact = facts[oid]
        if fact['participantId'] != participant_id or fact['semanticRole'] != semantic_role:
            raise ValueError('matrix member actor or semantic role mismatch')
        if target and (fact['objectRef'] != group['objectRef'] or fact['selector'] != group['selector']):
            raise ValueError('matrix comparison must use same exact object and selector')
        membership[oid].add(group['id'])
        return fact

    for group in groups.values():
        _text(group.get('objectRef')); _selector(group.get('selector'))
        kind = group.get('kind')
        if kind not in ('object-authorization', 'missing-identity'):
            raise ValueError('matrix explicit comparison kind required')
        owner, other = group.get('ownerParticipantId'), group.get('negativeParticipantId')
        if owner == other or owner not in participants or other not in participants:
            raise ValueError('matrix owner and negative must be distinct named participants')
        if participants[owner]['role'] == 'anonymous':
            raise ValueError('matrix owner control must have authenticated identity')
        anonymous = participants[other]['role'] == 'anonymous'
        if (kind == 'missing-identity') != anonymous or anonymous and participants[other]['identityRef'] != 'anonymous':
            raise ValueError('matrix anonymous comparison requires explicit anonymous participant')
        baseline, negative, after = (group.get(k) for k in
            ('baselineOperationId', 'negativeOperationId', 'ownerAfterOperationId'))
        if len({baseline, negative, after}) != 3:
            raise ValueError('matrix distinct baseline/negative/after operations required')
        member(group, baseline, owner, 'owner-positive', target=True)
        member(group, negative, other, 'anonymous-negative' if anonymous else 'nonowner-negative', target=True)
        member(group, after, owner, 'owner-after', target=True)
        if not times[baseline] < times[negative] < times[after]:
            raise ValueError('matrix baseline/negative/owner-after capture order mismatch')
        controls = group.get('sessionControls')
        if not isinstance(controls, list):
            raise ValueError('matrix pre/post session controls required')
        controlled = set()
        for control in controls:
            if not isinstance(control, dict):
                raise ValueError('matrix exact session control required')
            pid = control.get('participantId')
            if pid in controlled or pid not in ({owner} if anonymous else {owner, other}):
                raise ValueError('matrix wrong or duplicate session control participant')
            before_id, after_id = control.get('beforeOperationId'), control.get('afterOperationId')
            before_fact = member(group, before_id, pid, 'session-before')
            after_fact = member(group, after_id, pid, 'session-after')
            if (before_fact['objectRef'] != after_fact['objectRef'] or before_fact['selector'] != after_fact['selector']
                    or before_fact['objectRef'] == group['objectRef'] or before_fact['selector'] == group['selector']
                    or not times[before_id] < times[baseline] or not times[negative] < times[after_id]):
                raise ValueError('matrix session control object/selector/capture order mismatch')
            controlled.add(pid)
        if controlled != ({owner} if anonymous else {owner, other}):
            raise ValueError('matrix missing authenticated participant pre/post session controls')
    for oid, fact in facts.items():
        if membership[oid] != set(fact['groupIds']):
            raise ValueError('matrix operation has unlisted or missing group membership')


def matrix_link_diagnostics(allocation, observation):
    """All named baseline/control reads must survive the same evidence review."""
    if 'comparisonMatrix' not in allocation:
        return []
    for mapping in allocation['operations']:
        matching = [link for link in observation['evidenceLinks'] if link['operationId'] == mapping['operationId']]
        if len(matching) != 1:
            return ['matrix-group-readback-links-required']
        link = matching[0]
        if (link.get('resultRead') is not True or not isinstance(link.get('basis'), str) or not link['basis'].strip()
                or link.get('compatibility') or link.get('role') != ('support' if mapping['observationUnits'] else 'context')
                or any(link.get(k) != mapping[k] for k in ('context', 'resultPath', 'observationUnits'))):
            return ['matrix-group-readback-links-required']
    return []
