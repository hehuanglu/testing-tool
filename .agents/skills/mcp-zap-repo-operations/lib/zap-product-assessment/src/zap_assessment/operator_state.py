"""Validate scheduling metadata separately from approved workflow content."""
import copy
from datetime import datetime, timezone
from pathlib import PurePath

from .business_discovery import records, strings
from .contracts import digest
from .criteria_delegation import effective_resources
from .criteria_workflow import approval_digest


KINDS = {'source-review', 'evidence-review', 'prepare', 'dispatch', 'readback', 'resource-review', 'delivery'}
REPAIR_KINDS = {'reader', 'adapter', 'fixture-preparation', 'binding', 'journal-integrity',
                'store-integrity', 'executor-capability'}
STAGES = ('open', 'reproducing', 'implementing', 'verifying', 'verified')
REPAIR_STATES = {*STAGES, 'waiting_dependency', 'superseded'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def text(value):
    return isinstance(value, str) and bool(value.strip())


def timestamp(value):
    require(text(value) and 'T' in value, 'RFC3339 timestamp required')
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    require(parsed.utcoffset() is not None, 'timezone-aware timestamp required')
    return parsed.astimezone(timezone.utc)


def refs(value, label, *, required=False):
    result = strings(value, label)
    require(not required or bool(result), label + ' required')
    return result


def waiting(value):
    require(isinstance(value, dict), 'waiting dependency required')
    for key in ('reason', 'reopenCondition', 'nextStep'):
        require(text(value.get(key)), 'waiting ' + key + ' required')
    refs(value.get('basisRefs'), 'waiting basis', required=True)
    refs(value.get('missingEvidence', []), 'missing evidence')


def default_operator(run):
    workflow = run['criteriaWorkflow']
    cases = [case['id'] for case in workflow['plan']['cases']]
    return dict(version=1, assessmentId=run['assessmentId'], planDigest=approval_digest(workflow, 'plan'),
                activeBlockId='default', blocks=[dict(id='default', caseIds=cases, order=0,
                    exitCondition='Review assigned obligations')], workItems=[], repairs=[], delivery=None,
                stopRecord=None)


def validate_rebase(previous, operator):
    mapping = operator.get('rebase')
    require(isinstance(mapping, dict) and mapping.get('previousPlanDigest') == previous['planDigest'],
            'explicit schedule rebase required')
    for name in ('blocks', 'workItems'):
        rows = mapping.get(name)
        require(isinstance(rows, dict) and set(rows) == {row['id'] for row in previous[name]},
                'rebase requires a complete old-to-new ID mapping')
        require(all(value is None or value in {row['id'] for row in operator[name]} for value in rows.values()),
                'invalid rebase destination')


def validate_operator(run, operator, *, allow_stale=False):
    require(isinstance(operator, dict) and operator.get('version') == 1 and
            operator.get('assessmentId') == run['assessmentId'], 'operator identity mismatch')
    require(not set(operator) - {'version', 'assessmentId', 'planDigest', 'activeBlockId', 'blocks',
                                'workItems', 'repairs', 'delivery', 'stopRecord', 'rebase'},
            'unexpected operator field')
    workflow = run['criteriaWorkflow']
    stale = operator.get('planDigest') != approval_digest(workflow, 'plan')
    require(text(operator.get('planDigest')) and (not stale or allow_stale), 'operator plan digest mismatch')
    if stale:
        return
    plan = workflow['plan']
    cases = records(plan['cases'], 'plan cases')
    blocks = records(operator.get('blocks'), 'blocks')
    works = records(operator.get('workItems'), 'work items')
    require(operator.get('activeBlockId') in blocks or operator.get('activeBlockId') is None,
            'unknown active block')
    assigned = set()
    for block in blocks.values():
        require(set(block) == {'id', 'caseIds', 'order', 'exitCondition'}, 'invalid block fields')
        members = set(refs(block.get('caseIds'), 'block cases'))
        require(not assigned & members and members <= cases.keys(), 'duplicate or unknown block case')
        require(type(block.get('order')) is int and text(block.get('exitCondition')), 'invalid block metadata')
        assigned.update(members)
    require(assigned == cases.keys(), 'each case requires exactly one block')
    graph = {}
    for wid, work in works.items():
        require(not set(work) - {'id', 'caseIds', 'blockId', 'kind', 'mode', 'phase', 'order',
                'dependsOnWorkIds', 'resourceIds', 'state', 'basisRefs', 'nextStep', 'actionRef',
                'readbackOf', 'notBefore', 'completionRefs', 'waiting', 'subjectRefs', 'controlRefs',
                'executionBinding'},
                'unexpected work field')
        require(work.get('kind') in KINDS and work.get('mode') in ('offline', 'runtime')
                and work.get('phase') in ('execution', 'ttl-readback', 'closure')
                and work.get('state') in ('ready', 'in_progress', 'waiting', 'done')
                and type(work.get('order')) is int and text(work.get('nextStep')), 'invalid work metadata')
        members = set(refs(work.get('caseIds'), 'work cases'))
        block = blocks.get(work.get('blockId'))
        require(block and members <= set(block['caseIds']), 'work outside block')
        refs(work.get('basisRefs'), 'work basis', required=True)
        refs(work.get('completionRefs', []), 'work completion', required=work['state'] == 'done')
        graph[wid] = refs(work.get('dependsOnWorkIds', []), 'work dependencies')
        require(set(graph[wid]) <= works.keys(), 'unknown work dependency')
        if work['state'] == 'waiting':
            waiting(work.get('waiting'))
            require(set(refs(work['waiting'].get('dependsOnWorkIds', []), 'waiting work dependencies'))
                    <= set(graph[wid]), 'waiting dependency outside work dependencies')
        resources = set(refs(work.get('resourceIds', []), 'work resources'))
        action = work.get('actionRef')
        binding = work.get('executionBinding')
        if binding is not None:
            require(work['mode'] == 'runtime' and isinstance(binding, dict) and
                    set(binding) == {'taskId', 'workerId', 'packetDigest', 'packetRef'} and
                    all(text(value) for value in binding.values()) and '://' not in binding['packetRef'],
                    'executionBinding requires runtime work and a private packet path')
            require(len(binding['packetDigest']) == 64 and
                    all(char in '0123456789abcdef' for char in binding['packetDigest']),
                    'invalid execution packet digest')
        if work['mode'] == 'runtime':
            require(work['kind'] in ('dispatch', 'readback') and isinstance(action, dict) and
                    set(action) == {'caseId', 'actionId'} and action['caseId'] in members,
                    'runtime work requires an approved action reference')
            descriptors = records(cases[action['caseId']].get('actions', []), 'case actions')
            descriptor = descriptors.get(action['actionId'])
            require(descriptor is not None and descriptor.get('readbackOf') == work.get('readbackOf')
                    and (work['kind'] == 'readback') == bool(work.get('readbackOf')),
                    'runtime action differs from approved descriptor')
            require(set(effective_resources(plan, [cases[cid] for cid in members])) <= resources,
                    'runtime work must declare effective resources')
        else:
            require(action is None and work.get('readbackOf') is None and work['kind'] != 'dispatch',
                    'offline work cannot dispatch a bound action')
        if work.get('notBefore') is not None:
            timestamp(work['notBefore'])
        if work['phase'] == 'ttl-readback':
            require(work['mode'] == 'runtime' and descriptor.get('effect') == 'read',
                    'TTL work requires an approved read action')
            timestamp(work.get('notBefore'))
            refs(work.get('subjectRefs'), 'TTL subject', required=True)
            refs(work.get('controlRefs', []), 'TTL controls')
    visiting, visited = set(), set()

    def visit(wid):
        require(wid not in visiting, 'work dependency cycle')
        if wid in visited:
            return
        visiting.add(wid)
        for dependency in graph[wid]:
            visit(dependency)
        visiting.remove(wid)
        visited.add(wid)

    for wid in graph:
        visit(wid)
    repairs = records(operator.get('repairs'), 'repairs')
    for repair in repairs.values():
        validate_repair(repair, cases, works)
        if repair['status'] == 'superseded':
            require(repair.get('replacementId') in repairs and repair['replacementId'] != repair['id'],
                    'replacement repair required')
    for work in works.values():
        dependency = (work.get('waiting') or {}).get('repairId')
        require(dependency is None or dependency in repairs, 'unknown repair dependency')
    delivery = operator.get('delivery')
    if delivery is not None:
        require(isinstance(delivery, dict) and set(delivery) ==
                {'fileId', 'worksheetId', 'status', 'sourceDigest', 'verifiedAt', 'readbackRefs'}
                and text(delivery['fileId']) and text(delivery['worksheetId'])
                and delivery['status'] in ('verified', 'pending') and text(delivery['sourceDigest']),
                'invalid delivery receipt')
        if delivery['status'] == 'verified':
            timestamp(delivery['verifiedAt'])
            refs(delivery['readbackRefs'], 'delivery readback', required=True)
    stop = operator.get('stopRecord')
    if stop is not None:
        require(isinstance(stop, dict) and stop.get('kind') in ('host-interruption', 'context-handoff')
                and stop.get('source') in ('user', 'host') and text(stop.get('reason')), 'invalid stop record')
        refs(stop.get('basisRefs'), 'stop basis', required=True)


REPAIR_ORIGINAL = {'id', 'kind', 'affectedCaseIds', 'affectedWorkIds', 'affectedResourceIds',
                   'symptom', 'reproductionRefs', 'reproductionDigest', 'contextRef', 'expectedBehavior',
                   'authorityRef', 'allowedPaths', 'prohibitedEffects', 'acceptanceChecks', 'resumeWorkIds'}
REPAIR_MUTABLE = {'status', 'dependency', 'resumeStatus', 'replacementId', 'verificationRefs',
                  'verificationLevel', 'reproductionOutcome', 'changedFileRefs', 'positiveCheckRefs',
                  'negativeCheckRefs', 'verificationResult'}


def validate_repair(repair, cases, works):
    require(not set(repair) - REPAIR_ORIGINAL - REPAIR_MUTABLE - {'version', 'revision', 'history', 'fingerprint'},
            'unexpected repair field')
    require(repair.get('kind') in REPAIR_KINDS and repair.get('status') in REPAIR_STATES, 'invalid repair type/state')
    require(all(text(repair.get(key)) for key in ('symptom', 'expectedBehavior', 'authorityRef')), 'repair scope required')
    for key in ('reproductionRefs', 'prohibitedEffects', 'acceptanceChecks'):
        refs(repair.get(key), key, required=True)
    for key, options in (('affectedCaseIds', cases), ('affectedWorkIds', works), ('resumeWorkIds', works)):
        require(set(refs(repair.get(key), key)) <= options.keys(), 'unknown repair scope')
    refs(repair.get('affectedResourceIds'), 'affected resources')
    paths = refs(repair.get('allowedPaths'), 'allowed paths')
    require(all(not PurePath(path).is_absolute() and '..' not in PurePath(path).parts for path in paths),
            'repair paths must be relative and bounded')
    require(repair.get('version') == 1 and type(repair.get('revision')) is int and
            repair['revision'] >= 1 and isinstance(repair.get('history'), list), 'invalid repair revision')
    if repair['status'] == 'waiting_dependency':
        waiting(repair.get('dependency'))
        require(repair.get('resumeStatus') in STAGES[:-1], 'repair resume status required')
    if repair['status'] == 'verified':
        require(repair.get('verificationLevel') in ('offline-checked', 'runtime-observed') and
                text(repair.get('reproductionOutcome')) and repair.get('verificationResult') == 'passed',
                'verified repair requires reproduction and successful verification')
        for key in ('changedFileRefs', 'verificationRefs', 'positiveCheckRefs', 'negativeCheckRefs', 'resumeWorkIds'):
            refs(repair.get(key), key, required=True)


def change_repair(operator, proposal, *, opening):
    from .assessment_store import conflict
    updated = copy.deepcopy(operator)
    require(isinstance(proposal, dict) and text(proposal.get('id')), 'repair ID required')
    items = records(updated['repairs'], 'repairs')
    if opening:
        require(not set(proposal) - REPAIR_ORIGINAL - {'status', 'dependency', 'verificationRefs', 'history'},
                'unexpected repair proposal field')
        require(proposal.get('status', 'open') == 'open' and not proposal.get('history')
                and proposal.get('dependency') is None and not proposal.get('verificationRefs'),
                'new repair must be open')
        refs(proposal.get('reproductionRefs'), 'occurrence reproduction', required=True)
        refs(proposal.get('affectedWorkIds'), 'affected work')
        require(text(proposal.get('symptom')), 'repair symptom required')
        fingerprint = digest([proposal['kind'], sorted(proposal['affectedWorkIds']),
                              ' '.join(proposal['symptom'].casefold().split()),
                              proposal.get('reproductionDigest') or digest(proposal['reproductionRefs']),
                              proposal.get('contextRef'), operator['planDigest']])
        existing = next((row for row in items.values() if row.get('fingerprint') == fingerprint
                         and row['status'] != 'superseded'), None)
        occurrence_id = proposal['id']
        occurrence_digest = digest(proposal)
        for row in items.values():
            prior = next((event for event in row['history'] if event.get('proposalId') == occurrence_id), None)
            if row['id'] == occurrence_id or prior:
                same = row.get('fingerprint') == fingerprint and (
                    prior is None or prior.get('proposalDigest', occurrence_digest) == occurrence_digest)
                if not same:
                    raise conflict('repair-id-conflict', 'Occurrence ID belongs to a different report')
                return updated
        if existing:
            existing['revision'] += 1
            event = dict(kind='occurrence', proposalId=occurrence_id,
                         proposalDigest=occurrence_digest, reproductionRefs=proposal['reproductionRefs'])
            if existing['status'] == 'verified':
                event['kind'] = 'reopened-after-verification'
                event['previousVerification'] = {key: existing.pop(key) for key in
                                                 sorted(REPAIR_MUTABLE - {'status'}) if key in existing}
                existing['status'] = 'open'
            existing['history'].append(event)
        else:
            if proposal['id'] in items:
                raise conflict('repair-id-conflict', 'Repair ID already exists')
            updated['repairs'].append(dict(copy.deepcopy(proposal), fingerprint=fingerprint, version=1,
                                           revision=1, status='open', history=[dict(kind='opened',
                                               proposalId=occurrence_id, proposalDigest=occurrence_digest)]))
        return updated
    current = items.get(proposal['id'])
    require(current is not None and not set(proposal) - REPAIR_MUTABLE - {'id', 'revision', 'dependencyRefs'},
            'invalid repair update')
    if proposal.get('revision') != current['revision']:
        raise conflict('stale-repair', 'Repair revision has advanced')
    old, new = current['status'], proposal.get('status')
    allowed = {'superseded'}
    if old in STAGES[:-1]:
        allowed.update((STAGES[STAGES.index(old) + 1], 'waiting_dependency'))
    if old == 'waiting_dependency':
        allowed.add(current['resumeStatus'])
    require(old != 'superseded' and new in allowed, 'invalid repair transition')
    if old == 'waiting_dependency' and new != 'superseded':
        refs(proposal.get('dependencyRefs'), 'dependency reconciliation', required=True)
    changes = {key: copy.deepcopy(value) for key, value in proposal.items() if key in REPAIR_MUTABLE}
    if new == 'waiting_dependency':
        changes['resumeStatus'] = old
    if new == 'verified':
        reopened = next((event for event in reversed(current['history'])
                         if event['kind'] == 'reopened-after-verification'), None)
        if reopened:
            prior = reopened['previousVerification']
            for key in ('verificationRefs', 'positiveCheckRefs', 'negativeCheckRefs'):
                refs(changes.get(key), key, required=True)
                require(set(changes[key]) - set(prior.get(key, [])),
                        'reverification requires new ' + key)
    current.update(changes)
    current['revision'] += 1
    current['history'].append(dict(kind='transition', previous=old, status=new,
                                   details=changes, dependencyRefs=proposal.get('dependencyRefs', [])))
    return updated
