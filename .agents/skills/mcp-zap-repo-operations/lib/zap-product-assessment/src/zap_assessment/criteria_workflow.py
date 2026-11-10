"""Versioned criteria-first review, without dispatch or legacy semantic migration.

This checks approval bindings, evidence joins and terminal dispositions. It cannot
verify the human behind an approval source or infer a security oracle from HTTP.
The coordinator remains responsible for those semantic judgments.
"""
import copy
import hashlib
import json

from .business_discovery import records, references, strings, validate_question_fields
from .question_evidence import (collect_run_pending,
    operation_index, read_pointer, resolve_question_evidence,
    resolved_effect_ids, validate_observation_links)

VERDICTS = ('met', 'unmet', 'not_evaluable')
LIMITATION_REASONS = {'method_boundary', 'access', 'policy', 'capability',
    'environment', 'budget_exhausted', 'not_applicable'}
EFFECTS = {'read', 'mutation', 'start'}
FIXED_CATALOG_ID = 'OWASP-2025-CWE-MITRE-4.20'
FIXED_CATALOG_VERSION = '2026-09-26'
FIXED_CATALOG_SHA256 = '7765c109fcbcc957801351768648a1b0134e02088698bed6456dcc709af66f8c'
FIXED_REQUIREMENTS_SHA256 = '2c1cb4b067595b24a6e2d6cb3806999c60926c97b9aba895e24e71598e3cc7ee'
FIXED_CATEGORY_COUNTS = {'A01': 7, 'A02': 6, 'A03': 1, 'A04': 6, 'A05': 5,
                         'A06': 6, 'A07': 5, 'A08': 5, 'A09': 3, 'A10': 6}
FIXED_CRITERION_IDS = tuple(
    f'SEC-{category}-{ordinal:02d}'
    for category, count in FIXED_CATEGORY_COUNTS.items()
    for ordinal in range(1, count + 1))


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(label + ' required')
    return value


def _object(value, label):
    if not isinstance(value, dict):
        raise ValueError(label + ' object required')
    return value


def approval_digest(workflow, kind):
    """Stable content binding; only the plan digest is an approval boundary.

    The criteria digest remains a useful immutable content identity and is folded
    into the plan digest.  It is not a separate user-approval gate.
    """
    if kind not in ('criteria', 'plan'):
        raise ValueError('approval kind must be criteria or plan')
    keys = ('version', 'context', 'criteriaRevision', 'criteria')
    if workflow.get('version') == 3:
        keys = ('version', 'catalog', 'context', 'criteriaRevision', 'criteria')
    payload = {key: workflow.get(key) for key in keys}
    if kind == 'plan':
        payload = {'criteriaDigest': approval_digest(workflow, 'criteria'),
                   'planRevision': workflow.get('planRevision'), 'plan': workflow.get('plan')}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(',', ':'),
        ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def validate_workflow(workflow):
    """Validate structural v2 input, returning a copy; incomplete reviews are legal."""
    w = copy.deepcopy(_object(workflow, 'criteriaWorkflow'))
    if type(w.get('version')) is not int or w['version'] not in (2, 3):
        raise ValueError('criteriaWorkflow version 2 or 3 required; v1 is not migrated')
    for field in ('criteriaRevision', 'planRevision'):
        _text(w.get(field), field)
    context = _object(w.get('context'), 'workflow context')
    validate_question_fields({'coverageContext': context})
    for field in ('product', 'environment'):
        _text(context.get(field), 'context ' + field)
        if context[field] in ('unknown', 'unresolved', 'product-defined'):
            raise ValueError('explicit workflow context required')
    criteria = records(w.get('criteria'), 'criteria')
    if not criteria:
        raise ValueError('at least one assigned criterion required')
    plan = _object(w.get('plan'), 'plan')
    cases = records(plan.get('cases'), 'plan cases')
    authority = _object(plan.get('authority'), 'plan authority')
    for field in ('source', 'target'):
        _text(authority.get(field), 'authority ' + field)
    effects = set(strings(authority.get('allowedEffects'), 'authority effects'))
    if not effects or effects - EFFECTS:
        raise ValueError('invalid authority effects')
    fixed_catalog = w.get('catalog')
    if w['version'] == 3 and fixed_catalog is None:
        raise ValueError('criteriaWorkflow version 3 requires the bundled fixed catalog')
    if w['version'] == 3:
        fixed_catalog = _object(fixed_catalog, 'catalog')
        for field in ('id', 'version', 'sha256', 'source'):
            _text(fixed_catalog.get(field), 'catalog ' + field)
        if type(fixed_catalog.get('criterionCount')) is not int or fixed_catalog['criterionCount'] < 1:
            raise ValueError('catalog criterionCount positive integer required')
        if fixed_catalog['criterionCount'] != len(criteria):
            raise ValueError('workflow criteria must account for every fixed catalog criterion')
        expected_catalog = {'id': FIXED_CATALOG_ID, 'version': FIXED_CATALOG_VERSION,
                            'sha256': FIXED_CATALOG_SHA256, 'criterionCount': len(FIXED_CRITERION_IDS)}
        if any(fixed_catalog.get(key) != value for key, value in expected_catalog.items()):
            raise ValueError('workflow must bind the bundled fixed catalog identity')
        if tuple(criteria) != FIXED_CRITERION_IDS:
            raise ValueError('workflow criteria must preserve all fixed SEC IDs in catalog order')
    for criterion in criteria.values():
        for field in ('rawText', 'source', 'requirement', 'oracle'):
            _text(criterion.get(field), 'criterion ' + field)
        selected = criterion.get('selected', True)
        if type(selected) is not bool:
            raise ValueError('criterion selected must be boolean')
        if w['version'] == 3 and 'selected' not in criterion:
            raise ValueError('version 3 criterion selected decision required')
        if w['version'] == 3 or 'selected' in criterion:
            _text(criterion.get('selectionReason'), 'criterion selection reason')
            if selected:
                _text(criterion.get('testApproach'), 'selected criterion test approach')
        if criterion.get('applicability') not in ('applicable', 'not_applicable', 'unknown'):
            raise ValueError('invalid criterion applicability')
        if criterion.get('stoppingRule') not in ('all_cases', 'counterexample'):
            raise ValueError('explicit criterion stoppingRule required')
        if w['version'] == 3 and criterion.get('stoppingRule') != 'all_cases':
            raise ValueError('version 3 fixed-catalog criteria require all_cases')
        references(criterion.get('caseIds'), cases, 'criterion cases')
        if selected and criterion['applicability'] != 'not_applicable' and not criterion['caseIds']:
            raise ValueError('assigned criterion needs a planned evaluation case')
        if not selected and criterion['caseIds']:
            raise ValueError('unselected criterion cannot carry execution cases')
        if criterion['applicability'] == 'not_applicable':
            _text(criterion.get('applicabilityBasis'), 'not_applicable product basis')
            if criterion['caseIds']:
                raise ValueError('not_applicable criterion cannot carry execution cases')
    action_ids = set()
    strings(plan.get('resourceIds', []), 'plan resource IDs')
    for case in cases.values():
        references(case.get('criterionIds'), criteria, 'case criteria')
        if not case['criterionIds']:
            raise ValueError('case must serve an assigned criterion')
        for field in ('objective', 'expectedBehavior', 'expectationBasis'):
            _text(case.get(field), 'case ' + field)
        if not strings(case.get('requiredEvidence'), 'required evidence'):
            raise ValueError('case requires finite evidence obligations')
        validate_question_fields(case)
        if 'requireZapMessageEvidence' in case and type(case['requireZapMessageEvidence']) is not bool:
            raise ValueError('requireZapMessageEvidence must be boolean')
        actual = _object(case.get('coverageContext'), 'case coverageContext')
        if any(actual.get(k) != v for k, v in context.items()):
            raise ValueError('case workflow context mismatch')
        reasons = strings(case.get('allowedLimitations', []), 'allowed limitations')
        if set(reasons) - (LIMITATION_REASONS - {'not_applicable'}):
            raise ValueError('invalid planned limitation reason')
        strings(case.get('resourceIds', []), 'case resource IDs')
        declared = set(strings(case.get('effects', []), 'case effects'))
        if not declared or declared - effects:
            raise ValueError('case effects exceed approved authority')
        actions = records(case.get('actions', []), 'case actions')
        for aid, action in actions.items():
            if aid in action_ids:
                raise ValueError('action ID must be unique across the plan')
            action_ids.add(aid)
            if action.get('caseId') != case['id'] or action.get('effect') not in declared:
                raise ValueError('action descriptor exceeds its approved case')
            if 'fixtureOptions' in action:
                if not strings(action['fixtureOptions'], 'fixture options') or 'fixtureRef' in action:
                    raise ValueError('fixture options require a nonempty list and no fixed fixture')
                if not actual.get('fixtureClass'):
                    raise ValueError('fixture options require an approved fixture class')
            if 'readbackOf' in action:
                _text(action['readbackOf'], 'readback action ID')
                if action['effect'] != 'read':
                    raise ValueError('readback action must be read-only')
        references(case.get('dependsOnCases', []), cases, 'case dependencies')
        if case['id'] in case.get('dependsOnCases', []):
            raise ValueError('case cannot depend on itself')
        for criterion_id in case['criterionIds']:
            if case['id'] not in criteria[criterion_id]['caseIds']:
                raise ValueError('criterion/case mapping must be reciprocal')
    for criterion in criteria.values():
        for case_id in criterion['caseIds']:
            if criterion['id'] not in cases[case_id]['criterionIds']:
                raise ValueError('criterion/case mapping must be reciprocal')
    # A cyclic plan cannot be made executable by marking every case a dependency.
    visiting, done = set(), set()
    def visit(cid):
        if cid in visiting:
            raise ValueError('cyclic case dependencies')
        if cid in done:
            return
        visiting.add(cid)
        for dep in cases[cid].get('dependsOnCases', []):
            visit(dep)
        visiting.remove(cid); done.add(cid)
    for cid in cases:
        visit(cid)
    approvals = w.get('approvals', [])
    if not isinstance(approvals, list):
        raise ValueError('approvals list required')
    for approval in approvals:
        _object(approval, 'approval')
        if approval.get('kind') not in ('criteria', 'plan'):
            raise ValueError('invalid approval kind')
        if w['version'] == 3 and approval.get('kind') != 'plan':
            raise ValueError('version 3 accepts only Gate 2 plan approval')
        for field in ('revision', 'digest', 'source'):
            _text(approval.get(field), 'approval ' + field)
    for key, identity, allowed in (('caseResults', 'caseId', cases),
                                   ('criterionResults', 'criterionId', criteria)):
        for ident in records(w.get(key, []), key, identity):
            if ident not in allowed:
                raise ValueError('result outside approved ' + key)
    request = w.get('userRequest')
    if request is not None:
        _object(request, 'userRequest')
        if request.get('kind') not in ('stop', 'pause'):
            raise ValueError('invalid user request')
        _text(request.get('source'), 'user request source')
    return w


def _approval_status(w):
    kinds = ('plan',) if w['version'] == 3 else ('criteria', 'plan')
    return {kind: any(a['kind'] == kind and a['revision'] == w[kind + 'Revision']
            and a['digest'] == approval_digest(w, kind) for a in w['approvals'])
            for kind in kinds}


def _limitation(row, allowed):
    value = _object(row.get('limitation'), 'terminal limitation')
    if value.get('reason') not in allowed:
        raise ValueError('limitation reason is not approved for this obligation')
    for field in ('basis', 'reopenCondition'):
        _text(value.get(field), 'limitation ' + field)
    for field in ('missingEvidence', 'attemptedAlternatives', 'unavailableAlternatives',
                  'remainingFeasibleActions'):
        strings(value.get(field), 'limitation ' + field)
    if not value['missingEvidence']:
        raise ValueError('limitation must name missing evidence')
    if not value['attemptedAlternatives'] and not value['unavailableAlternatives']:
        raise ValueError('limitation must account for available alternatives')
    return copy.deepcopy(value)


def _resource_review(run, w, operations, pending):
    diagnostics, limitations = [], []
    review = w.get('resourceReview', {})
    if not isinstance(review, dict) or review.get('reviewed') is not True or not review.get('basis'):
        return ['resource-review-required'], []
    rows = records(review.get('resources', []), 'reviewed resources')
    known = run.get('resources', [])
    if not isinstance(known, list):
        raise ValueError('v2 run.resources must be an explicit resource list')
    known_rows = records(known, 'known resources')
    required = (set(known_rows) | set(w['plan'].get('resourceIds', [])) |
                {rid for c in w['plan']['cases'] for rid in c.get('resourceIds', [])})
    if required - set(rows):
        diagnostics.append('unreviewed-resources:' + ','.join(sorted(required - set(rows))))
    for rid, row in rows.items():
        _text(row.get('basis'), 'resource disposition basis')
        if row.get('status') not in ('stopped', 'retained', 'contained'):
            diagnostics.append('uncontrolled-resource:' + rid)
            continue
        oid = row.get('operationId')
        if oid not in operations:
            raise ValueError('resource readback operation missing')
        if any(operations[oid].get('coverageContext', {}).get(k) != v for k, v in w['context'].items()):
            raise ValueError('resource readback workflow context mismatch')
        fact = read_pointer(operations[oid], row.get('resultPath'))
        if not isinstance(fact, dict) or fact.get('resourceId') != rid or fact.get('status') != row['status']:
            raise ValueError('resource disposition does not match exact readback')
        if row['status'] == 'stopped' and fact.get('producerActive') is not False:
            diagnostics.append('stopped-producer-not-confirmed:' + rid)
        if row['status'] == 'retained':
            if fact.get('producerActive') is not False:
                diagnostics.append('retained-producer-not-contained:' + rid)
            _text(row.get('retentionBasis'), 'retention authority basis')
        if row['status'] == 'contained' and fact.get('contained') is not True:
            diagnostics.append('resource-containment-unproven:' + rid)
    contained = records(w.get('containedEffects', []), 'contained effects', 'actionId')
    pending_ids = {e['actionId'] for e in pending}
    if set(contained) - pending_ids:
        raise ValueError('contained effect references unknown pending action')
    for effect in pending:
        aid = effect['actionId']; row = contained.get(aid)
        if not row:
            diagnostics.append('pending-effect:' + aid)
            continue
        for field in ('lastKnownState', 'unknownImpact', 'unavailableReaderReason', 'reopenCondition'):
            _text(row.get(field), 'contained effect ' + field)
        if row.get('noReplay') is not True:
            raise ValueError('contained unknown effect requires noReplay')
        oid = row.get('operationId')
        if oid not in operations:
            raise ValueError('contained effect readback operation missing')
        expected = effect.get('coverageContext') or w['context']
        if any(operations[oid].get('coverageContext', {}).get(k) != v for k, v in expected.items()):
            raise ValueError('contained effect readback context mismatch')
        fact = read_pointer(operations[oid], row.get('resultPath'))
        if not isinstance(fact, dict) or fact.get('actionId') != aid or fact.get('contained') is not True:
            raise ValueError('contained effect needs exact containment readback')
        if effect.get('caseId') and fact.get('caseId') != effect['caseId']:
            raise ValueError('contained effect readback case mismatch')
        limitations.append(copy.deepcopy(row))
    # External continuation/resource summaries cannot be hidden by an empty v2 review.
    continuation = run.get('continuation') or {}
    if continuation.get('pendingOperations'):
        represented = {e.get('operationId') for e in pending} | pending_ids
        for row in continuation['pendingOperations']:
            if not isinstance(row, dict) or not ({row.get('actionId'), row.get('operationRef')} & represented):
                diagnostics.append('unreconciled-continuation-operation')
    return diagnostics, limitations


def review_workflow(run):
    """Compute current assessment status; never use discovery as assigned scope.

    Invalid references/contracts raise ValueError. Missing plan approval, incomplete
    observations and remaining work are diagnostics, not fabricated verdicts.
    """
    if run.get('reportProjection'):
        raise ValueError('report projection is not executable; use private working RUN')
    w = validate_workflow(run.get('criteriaWorkflow'))
    w.setdefault('approvals', [])
    approvals = _approval_status(w)
    operations = operation_index(run.get('operations', []))
    for operation in operations.values():
        if operation.get('status', operation.get('executionStatus')) == 'planned':
            raise ValueError('planned action cannot be an actual operation')
    from .evidence_allocation import allocation_index
    allocations = allocation_index(run, w, operations)
    coordinator_state = None
    if run.get('coordinatorState'):
        from pathlib import Path
        from .criteria_delegation import Coordinator
        state = run['coordinatorState']
        if state.get('assessmentId') != run.get('assessmentId') or not Path(state['directory']).is_dir():
            raise ValueError('missing or foreign coordinator state')
        coordinator_state = Coordinator(state['directory'], state['assessmentId']).review_state()
    snapshot = coordinator_state or {'activeTaskIds': [], 'pendingEffects': []}
    pending = collect_run_pending(run, snapshot['pendingEffects'])
    coordinator_diagnostics = ['active-coordinator-lease:' + task_id
                               for task_id in snapshot['activeTaskIds']]
    resolution = {'resolvedEffects': w.get('resolutions', [])}
    validate_observation_links(resolution, operations)
    resolved = resolved_effect_ids(resolution, operations, pending)
    pending = [effect for effect in pending if effect['actionId'] not in resolved]
    diagnostics, next_work, limitations = coordinator_diagnostics, [], []
    if not approvals.get('criteria', True):
        diagnostics.append('criteria-approval-required')
    if not approvals['plan']:
        diagnostics.append('plan-approval-required')
    cases = {c['id']: c for c in w['plan']['cases']}
    results = {r['caseId']: r for r in w.get('caseResults', [])}
    claims = {r['criterionId']: r for r in w.get('criterionResults', [])}
    reviewed_cases = {}
    for cid, case in cases.items():
        row = results.get(cid)
        result = {'caseId': cid, 'outcome': None, 'basis': None}
        if row:
            _text(row.get('basis'), 'case result basis')
            outcome = row.get('outcome')
            if outcome not in ('matched', 'violated', 'not_evaluable', None):
                raise ValueError('invalid case outcome')
            result['basis'] = row['basis']
            if outcome in ('matched', 'violated') or 'evidenceLinks' in row:
                if 'evidenceLinks' not in row:
                    raise ValueError('v2 requires evidenceLinks, never legacy unit labels')
                question = dict(case, caseId=cid)
                evidence = resolve_question_evidence(question, row, operations, pending,
                    allocation=allocations.get(cid), workflow=w, assessment_id=run.get('assessmentId'))
                result['evidence'] = evidence
                if not evidence['missingUnits'] and not evidence['contextDiagnostics'] and evidence['supportOperationIds']:
                    # Assessment identity remains exact. Other planned dimensions
                    # may use the resolver's reviewed finite compatibility, but
                    # the operation must still carry their actual observed values.
                    for oid in evidence['supportOperationIds']:
                        actual = operations[oid].get('coverageContext', {})
                        if (any(actual.get(k) != v for k, v in w['context'].items()) or
                            any(actual.get(k) in (None, 'unknown', 'unresolved', 'product-defined')
                                for k in case['coverageContext'])):
                            raise ValueError('support operation must bind the planned context')
                    if outcome in ('matched', 'violated'):
                        result['outcome'] = outcome
                else:
                    result['diagnostics'] = evidence['contextDiagnostics'] + ['missing-unit:' + u for u in evidence['missingUnits']]
            if outcome == 'not_evaluable' or (outcome is None and 'limitation' in row):
                limitation = _limitation(row, case.get('allowedLimitations', []))
                if set(limitation['missingEvidence']) - set(case['requiredEvidence']):
                    raise ValueError('limitation evidence outside case obligations')
                result['limitation'] = limitation
                # An applicable case cannot terminate as N/A. Retain old v2
                # limitations for recovery, but never close missing evidence
                # merely because the caller declares no remaining actions.
                result.setdefault('diagnostics', []).append('unresolved-evidence-limitation')
                next_work.extend({'caseId': cid, 'action': action} for action in limitation['remainingFeasibleActions'])
        reviewed_cases[cid] = result
    criterion_results = []
    waived = set()
    for criterion in w['criteria']:
        cid = criterion['id']; claim = claims.get(cid, {})
        if claim and claim.get('verdict') not in (*VERDICTS, None):
            raise ValueError('invalid criterion verdict')
        rows = [reviewed_cases[i] for i in criterion['caseIds']]
        outcomes = [r['outcome'] for r in rows]
        verdict, basis = None, None
        selected = criterion.get('selected', True)
        if not selected:
            if claim.get('verdict') is not None:
                diagnostics.append('excluded-criterion-has-verdict:' + cid)
        elif criterion['applicability'] == 'unknown':
            diagnostics.append('criterion-applicability-unresolved:' + cid)
            next_work.append({'criterionId': cid, 'action': 'resolve-product-applicability'})
        elif criterion['applicability'] == 'not_applicable':
            if claim.get('verdict') == 'not_evaluable':
                limitation = _limitation(claim, {'not_applicable'})
                if not limitation['remainingFeasibleActions']:
                    verdict, basis = 'not_evaluable', criterion['applicabilityBasis']
                    limitations.append({'criterionId': cid, **limitation})
        elif 'violated' in outcomes:
            if None not in outcomes or criterion['stoppingRule'] == 'counterexample':
                verdict = 'unmet'
                basis = 'Approved oracle contradicted by case evidence'
                if criterion['stoppingRule'] == 'counterexample':
                    waived.update(r['caseId'] for r in rows if r['outcome'] is None)
        elif outcomes and all(outcome == 'matched' for outcome in outcomes):
            if criterion['applicability'] == 'applicable':
                verdict, basis = 'met', 'Every approved case has sufficient matching observations'
        if not all(approvals.values()):
            # Observations remain reusable candidates, but current unapproved
            # criteria/plan content cannot receive a final verdict.
            verdict, basis = None, None
        if claim.get('verdict') is not None and claim['verdict'] != verdict:
            # Pending work remains visible rather than accepting an unsupported claim.
            diagnostics.append('unsupported-criterion-verdict:' + cid)
        if claim.get('basis'):
            _text(claim['basis'], 'criterion result basis')
            if verdict:
                basis = claim['basis']
        result = {'criterionId': cid, 'verdict': verdict, 'basis': basis,
                  'applicability': criterion['applicability'], 'caseIds': criterion['caseIds'],
                  'stoppingRule': criterion['stoppingRule'], 'selected': selected,
                  'selectionReason': criterion.get('selectionReason'),
                  'testApproach': criterion.get('testApproach')}
        if not selected:
            result['disposition'] = 'out_of_scope_for_run'
        if verdict == 'not_evaluable':
            result['limitations'] = [r['limitation'] for r in rows if r.get('limitation')]
            if criterion['applicability'] == 'not_applicable':
                result['limitations'] = [copy.deepcopy(claim['limitation'])]
        criterion_results.append(result)
    # A case shared with another criterion is waived only if every parent permits it.
    for cid in list(waived):
        parents = [r for r in criterion_results if cid in r['caseIds']]
        if any(p['verdict'] != 'unmet' or p['stoppingRule'] != 'counterexample' for p in parents):
            waived.remove(cid)
    next_work = [row for row in next_work if row.get('caseId') not in waived]
    for cid, row in reviewed_cases.items():
        if row['outcome'] is None:
            if cid in waived:
                row['disposition'] = 'not-required-after-approved-counterexample'
            else:
                next_work.append({'caseId': cid, 'action': 'resolve-approved-evidence-obligation'})
        if row.get('limitation') and cid not in waived:
            limitations.append({'caseId': cid, **row['limitation']})
    resource_diagnostics, effect_limits = _resource_review(run, w, operations, pending)
    diagnostics.extend(resource_diagnostics); limitations.extend(effect_limits)
    counts = {verdict: sum(r['selected'] and r['verdict'] == verdict for r in criterion_results) for verdict in VERDICTS}
    counts['pending'] = sum(r['selected'] and r['verdict'] is None for r in criterion_results)
    counts['excluded'] = sum(not r['selected'] for r in criterion_results)
    counts['notApplicable'] = sum(r['applicability'] == 'not_applicable' and r['verdict'] == 'not_evaluable' for r in criterion_results)
    eligible = all(approvals.values()) and not counts['pending'] and not next_work and not diagnostics
    request = w.get('userRequest')
    if request:
        status = 'stopped_by_user' if request['kind'] == 'stop' else 'waiting_dependency'
        eligible = False
    elif not approvals.get('criteria', True):
        status = 'awaiting_criteria_approval'
    elif not approvals['plan']:
        status = 'awaiting_plan_approval'
    elif eligible:
        status = 'completed'
    else:
        status = 'executing'
    return {'workflowVersion': w['version'], 'assessmentStatus': status, 'eligibleForCompletion': eligible,
            'approvalStatus': approvals, 'criteriaRevision': w['criteriaRevision'],
            'planRevision': w['planRevision'], 'criterionResults': criterion_results,
            'criterionCounts': counts, 'caseResults': list(reviewed_cases.values()),
            'pendingEffects': copy.deepcopy(pending),
            'diagnostics': diagnostics, 'nextWork': next_work, 'limitations': limitations,
            'meaning': 'Completion evaluates approved criteria; it is not a product safety verdict'}
