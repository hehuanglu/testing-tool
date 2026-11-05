"""Pure, offline round closure and aggregate accounting; never dispatch or accept risk.

Review declarations are tester interpretations. They must name original clauses,
current questions and retained residuals; they cannot supply observation evidence.
"""
import copy

from .business_discovery import records, references, strings

CLOSED = ('completed', 'completed-with-limitations')
STATUSES = ('in-progress', 'checkpointed', *CLOSED, 'stopped-by-user')
DISPOSITIONS = ('tested-question', 'grounded-na', 'external-or-method-limit',
                'conclusion-limit', 'separate-remediation', 'unresolved')
SATISFIED = ('observed', 'not-applicable', 'user-excluded')


def _questions(projection):
    return records(list({q['id']: q for c in projection.get('criteria', [])
                         for q in c.get('questions', [])}.values()), 'closure questions')


def _residuals(projection):
    from .residual_review import CATEGORIES
    return {r['id']: r for key in CATEGORIES for r in (projection or {}).get(key, [])}


def review_aggregate_obligations(scope, assessment, question_projection, residual_projection):
    """Account for parent clauses once, retaining independent child evidence gates."""
    questions = records(scope.get('questions', []), 'aggregate questions')
    projected = records(question_projection, 'projected aggregate questions')
    residuals = _residuals(residual_projection)
    review = (assessment or {}).get('aggregateReviews')
    if review is None:
        review = dict(version=1, rows=[])
    if not isinstance(review, dict) or type(review.get('version')) is not int or review['version'] != 1:
        raise ValueError('unsupported aggregateReviews version')
    if not isinstance(review.get('rows'), list):
        raise ValueError('aggregateReviews rows required')
    seen = set(); states = []; diagnostics = []; unresolved = []
    sources = records(scope.get('sources', []), 'aggregate sources')
    sources.update(records((assessment or {}).get('residualReview', {}).get('sources', []), 'aggregate residual sources'))
    # A retained child can itself need accounting. Evaluate leaves before their
    # parents; never reuse a caller's observed label for an unreviewed aggregate.
    projected = {i:dict(q,coverage='partial') if q.get('questionRole')=='retained-aggregate' and q.get('coverage')!='user-excluded' else q for i,q in projected.items()}
    def depth(row):
        if not isinstance(row,dict):raise ValueError('aggregate review object required')
        current=row.get('aggregateQuestionId');visited=set()
        references([current],questions,'aggregate question')
        while current is not None:
            if current in visited:raise ValueError('question refinement cycle')
            visited.add(current)
            if current not in questions:raise ValueError('unresolved refined question')
            current=questions[current].get('refinesQuestionId')
        return len(visited)
    for row in sorted(review['rows'], key=depth, reverse=True):
        if not isinstance(row, dict):raise ValueError('aggregate review object required')
        qid = row.get('aggregateQuestionId')
        references([qid], questions, 'aggregate question')
        if qid in seen or questions[qid].get('questionRole') != 'retained-aggregate':
            raise ValueError('duplicate or non-aggregate review')
        seen.add(qid)
        if row.get('scopeRevision') != scope.get('revision'):
            raise ValueError('aggregate review scope revision mismatch')
        source_refs = row.get('sourceRefs')
        if not isinstance(source_refs, list):raise ValueError('aggregate sourceRefs list required')
        for ref in source_refs:
            if not isinstance(ref, dict):raise ValueError('aggregate source reference object required')
            references([ref.get('sourceRef')], sources, 'aggregate source')
            if not isinstance(ref.get('sourcePointer'), str) or not ref['sourcePointer'].startswith('/'):
                raise ValueError('aggregate source pointer required')
        strings(row.get('unmappedClauses'), 'aggregate unmapped clauses')
        atoms = records(row.get('obligationAtoms'), 'aggregate atoms')
        pending = bool(row['unmappedClauses'] or not source_refs or not row.get('coverageBasis') or not atoms)
        atom_states = []; missing_ids = []
        for atom in atoms.values():
            if atom.get('disposition') not in DISPOSITIONS:raise ValueError('invalid aggregate disposition')
            references(atom.get('questionIds', []), questions, 'aggregate child')
            references(atom.get('residualItemIds', []), residuals, 'aggregate residual')
            for child in atom.get('questionIds', []):
                if child == qid or questions[child].get('refinesQuestionId') != qid:
                    raise ValueError('aggregate atom must reference a direct refinement')
            linked = [projected.get(i, {}) for i in atom.get('questionIds', [])]
            rs = [residuals[i] for i in atom.get('residualItemIds', [])]
            if any(not set(r.get('criterionIds', [])) & set(questions[qid]['criterionIds']) for r in rs):
                raise ValueError('aggregate residual criterion boundary mismatch')
            disposition = atom['disposition']; valid = bool(atom.get('text') and atom.get('basis'))
            answered = bool(linked) and all(q.get('coverage') in SATISFIED for q in linked)
            covered = False
            if disposition == 'tested-question':
                # An unanswered finite child is accounted, but still a testing gap.
                valid = valid and bool(linked); covered = answered
            elif disposition == 'grounded-na':
                valid = valid and bool(atom.get('applicabilityBasis')) and all(q.get('coverage') in SATISFIED for q in linked)
                covered = valid
            elif disposition == 'external-or-method-limit':
                valid = valid and bool(rs) and all(r.get('kind') in ('dependency', 'method-limit') for r in rs)
            elif disposition == 'conclusion-limit':
                valid = valid and bool(rs) and all(r.get('kind') == 'generalization-limit' for r in rs) and all(q.get('coverage') in SATISFIED for q in linked)
                covered = valid
            elif disposition == 'separate-remediation':
                valid = valid and bool(rs) and all(r.get('kind') == 'remediation' for r in rs) and (answered or bool(atom.get('assignmentBasis')) and not linked)
                covered = valid
            else:
                valid = False
            if not valid:
                pending = True; diagnostics.append(dict(code='aggregate-atom-needs-review', questionId=qid, atomId=atom['id']))
            if not covered:
                missing_ids.append(atom['id']); unresolved.append(dict(aggregateQuestionId=qid, **copy.deepcopy(atom)))
            atom_states.append(dict(id=atom['id'], disposition=disposition, accounted=bool(valid), coverage='observed' if covered else 'partial'))
        children = {i for a in atoms.values() for i in a.get('questionIds', [])}
        expected = {q['id'] for q in questions.values() if q.get('refinesQuestionId') == qid}
        if expected - children:
            pending = True; diagnostics.append(dict(code='aggregate-unmapped-children', questionId=qid, questionIds=sorted(expected-children)))
        state = dict(aggregateQuestionId=qid, accountingStatus='pending' if pending else 'accounted',
            coverage='observed' if not pending and not missing_ids else 'partial',
            unansweredObligationIds=missing_ids, obligationAtoms=atom_states,
            coverageBasis=row.get('coverageBasis'), unmappedClauses=copy.deepcopy(row['unmappedClauses']))
        states.append(state)
        projected[qid] = {**projected.get(qid,{}), 'coverage':state['coverage']}
    for q in questions.values():
        if q.get('questionRole') == 'retained-aggregate' and q['id'] not in seen:
            states.append(dict(aggregateQuestionId=q['id'], accountingStatus='pending', coverage='partial',
                unansweredObligationIds=[q['id']], obligationAtoms=[], unmappedClauses=['aggregate-review-missing']))
    return dict(version=1, states=states, unresolvedAtoms=unresolved, diagnostics=diagnostics)


def validate_round_definition(definition):
    if not isinstance(definition, dict) or type(definition.get('version')) is not int or definition['version'] != 1:
        raise ValueError('unsupported assessmentRound version')
    if not all(isinstance(definition.get(k), str) and definition[k].strip() for k in
               ('id', 'objective', 'scopeBasis', 'assessmentId', 'product', 'environment', 'scopeRevision')):
        raise ValueError('assessmentRound identity/objective/scope required')
    if definition.get('status') not in STATUSES:raise ValueError('invalid assessmentRound status')
    universe = definition.get('reviewUniverse')
    if not isinstance(universe, dict):raise ValueError('round reviewUniverse required')
    for key in ('criterionIds', 'questionIds', 'caseIds', 'sourceIds', 'residualSourceIds', 'inventoryRefs'):
        strings(universe.get(key, []), 'round universe ' + key)
    request = definition.get('userRequest')
    if request is not None and (not isinstance(request, dict) or request.get('kind') not in ('pause','stop') or not isinstance(request.get('source'), str) or not request['source'].strip()):
        raise ValueError('explicit user pause/stop source required')
    if definition['status']=='stopped-by-user' and (not request or request['kind']!='stop'):
        raise ValueError('stopped-by-user requires explicit user stop source')
    return definition


class RoundFinalizationError(ValueError):
    def __init__(self, review):
        super().__init__('round-finalization-ineligible')
        self.review = copy.deepcopy(review)


def review_round_closure(round_definition, scope_projection, reconciliation, residual_projection, work_selection, resource_state):
    """Recompute eligibility from current projections. Caller status is never proof.

    resource_state is prepared from the RUN's owned resources, pending effects and
    continuation.resourceDisposition. No live liveness claim is made here.
    """
    result = dict(version=1, decision='review-needed', eligibleStatus=None, nextWork=[],
        diagnostics=[], limitations=[], reopenConditions=[], unansweredObligationIds=[], reviewExtent=None)
    def diagnostic(code, **extra):result['diagnostics'].append(dict(code=code, **extra))
    if round_definition is None:
        diagnostic('missing-round-definition');return result
    definition = validate_round_definition(round_definition)
    scope = scope_projection.get('securityScope') or {}
    rec = reconciliation or {}; residual = residual_projection or {}; selection = work_selection or {}
    if definition['scopeRevision'] != (scope.get('revision') or (rec.get('inventory') or {}).get('scopeRevision')):
        raise ValueError('round scope revision mismatch')
    for key in ('assessmentId', 'product', 'environment'):
        if scope.get(key) is not None and definition[key] != scope[key]:raise ValueError('round '+key+' mismatch')
    universe = definition['reviewUniverse'];result['reviewExtent'] = copy.deepcopy(universe)
    qs = _questions(scope_projection);cs = {c['caseId']:c for c in rec.get('cases', [])}
    criteria = records(scope_projection.get('criteria', []), 'closure criteria')
    sources = records(scope.get('sources', []), 'closure sources')
    residual_sources = records((scope_projection.get('residualReview') or {}).get('sources', []), 'closure residual sources')
    for key, known in (('criterionIds', criteria), ('questionIds', qs), ('caseIds', cs), ('sourceIds', sources), ('residualSourceIds', residual_sources)):
        declared = universe.get(key, [])
        references(declared, known, 'round '+key)
        if set(known) - set(declared):diagnostic('round-universe-omission', field=key, ids=sorted(set(known)-set(declared)))
    if not any(universe.get(k) for k in ('criterionIds','questionIds','caseIds','inventoryRefs')):diagnostic('empty-round-universe')
    if scope and scope.get('complete') is not True:diagnostic('scope-universe-incomplete')
    if scope_projection.get('inventoryGaps'):diagnostic('scope-inventory-gaps')
    inventories = records(scope_projection.get('reviewInventories', []), 'round inventories')
    references(universe.get('inventoryRefs', []), inventories, 'round inventory')
    if set(inventories) - set(universe.get('inventoryRefs', [])):diagnostic('round-inventory-omission')
    for inv in inventories.values():
        if inv.get('scopeRevision') != definition['scopeRevision']:raise ValueError('round inventory revision mismatch')
        strings(inv.get('unitIds'), 'inventory units');strings(inv.get('reviewedUnitIds'), 'reviewed inventory units')
        references(inv['reviewedUnitIds'], inv['unitIds'], 'reviewed inventory unit')
        if not inv.get('basis') or set(inv['unitIds']) != set(inv['reviewedUnitIds']):diagnostic('round-inventory-not-reviewed', inventoryId=inv['id'])
    inv = rec.get('inventory') or {}
    if inv and (rec.get('inventoryGaps') or rec.get('executionGaps')):diagnostic('responsibility-inventory-gaps')
    discovery = rec.get('discoveryReview') or {}
    if inv and discovery.get('reviewStatus') != 'reviewed':diagnostic('discovery-review-incomplete')
    # A selected/delta discovery review alone cannot close the broad assignment.
    if inv and discovery.get('extent', {}).get('kind') != 'assigned-scope' and not inventories:
        diagnostic('whole-round-inventory-review-missing')
    aggregates = scope_projection.get('aggregateAccounting', {})
    for state in aggregates.get('states', []):
        if state['accountingStatus'] != 'accounted':diagnostic('aggregate-accounting-pending', questionId=state['aggregateQuestionId'])
    result['diagnostics'].extend(copy.deepcopy(aggregates.get('diagnostics', [])))
    active_criteria = {i for i,c in criteria.items() if c.get('disposition') != 'user-excluded' and c.get('applicability', {}).get('status') != 'not-applicable'}
    open_qs = {i:q for i,q in qs.items() if set(q.get('criterionIds', [])) & active_criteria and q.get('coverage') not in SATISFIED}
    open_cs = {i:c for i,c in cs.items() if c.get('status') not in SATISFIED}
    unanswered = set(open_qs) | set(open_cs)
    for cid in active_criteria:
        criterion = criteria[cid]
        if (not any(cid in q.get('criterionIds', []) for q in qs.values()) or
            criterion.get('applicability', {}).get('status') == 'unknown' or criterion.get('unresolved')):
            unanswered.add(cid)
    if scope:
        extent = residual.get('reviewExtent') or {}
        if residual.get('residualReviewStatus') != 'supplied' or extent.get('kind') != 'all-declared-residuals':diagnostic('whole-round-residual-review-missing')
        if set(criteria) - set(extent.get('criterionIds', [])):diagnostic('residual-criteria-omitted')
        if residual.get('unreviewedRefs'):diagnostic('unreviewed-residuals', refs=copy.deepcopy(residual['unreviewedRefs']))
        result['diagnostics'].extend(copy.deepcopy(residual.get('reviewDiagnostics', [])))
        if residual.get('unclassified'):diagnostic('unclassified-residuals')
    # Known runnable work always survives a caller's empty action list/offline mode.
    for key in ('actionableReadback', 'actionableExecution', 'preparationNeeded', 'investigationNeeded'):
        for row in residual.get(key, []):
            duty = row.get('underlyingDutyId', row['id'])
            existing = next((w for w in result['nextWork'] if w.get('id') == duty), None)
            if existing is not None:existing['residualItemIds'].append(row['id'])
            else:result['nextWork'].append(dict(id=duty,residualItemIds=[row['id']],action=row.get('effectiveActionClass', row.get('actionClass')),nextStep=row.get('nextStep')))
    for row in selection.get('orderedCandidates', []) + selection.get('missingHandlers', []) + selection.get('nextPreparation', []):
        result['nextWork'].append(copy.deepcopy(row))
    limitations = residual.get('externalDependencies', []) + residual.get('methodLimits', [])
    limited_qs = {q for row in limitations for q in row.get('questionIds', [])}
    limited_cs = {c for row in limitations for c in row.get('caseIds', [])}
    limited_criteria = {c for row in limitations for c in row.get('criterionIds', [])}
    for state in aggregates.get('states', []):
        qid = state['aggregateQuestionId']
        atoms = [a for a in aggregates.get('unresolvedAtoms', []) if a['aggregateQuestionId'] == qid]
        if state['accountingStatus'] == 'accounted' and atoms and all(a['disposition'] == 'external-or-method-limit' for a in atoms):limited_qs.add(qid)
    for row in limitations:
        relevant_criteria = set(row.get('criterionIds', [])) & active_criteria
        has_open_duty = (set(row.get('questionIds', [])) & set(open_qs) or set(row.get('caseIds', [])) & set(open_cs) or
            relevant_criteria & unanswered or any(set(q.get('criterionIds', [])) & relevant_criteria for q in open_qs.values()))
        if relevant_criteria and not has_open_duty:
            diagnostic('limitation-not-mapped-to-unanswered-duty', itemId=row['id'])
        condition = (row.get('dependency') or {}).get('resumptionCondition') or row.get('reopenCondition')
        if not condition:diagnostic('limitation-reopen-condition-missing', itemId=row['id'])
        result['limitations'].append(dict(id=row['id'], kind=row['kind'], basis=row.get('basis'), reopenCondition=condition))
        if condition:result['reopenConditions'].append(dict(itemId=row['id'], condition=condition))
    resources = resource_state or {}; unsafe = False
    ops = records(resources.get('operations', []), 'closure operations')
    for resource in resources.get('resources', []):
        rid = resource.get('resourceRef')
        if not rid:raise ValueError('owned resource reference required')
        readbacks = resource.get('readbackRefs', [])
        for ref in readbacks:
            references([ref.get('operationId')], ops, 'resource readback')
            from .question_evidence import read_pointer
            actual = read_pointer(ops[ref['operationId']], ref.get('resultPath'))
            if 'expectedValue' not in ref or actual != ref['expectedValue']:
                unsafe = True;diagnostic('resource-readback-not-contained', resourceRef=rid)
            if ops[ref['operationId']].get('status',ops[ref['operationId']].get('executionStatus')) not in ('completed','partial'):
                unsafe = True;diagnostic('resource-readback-not-terminal', resourceRef=rid)
        if resource.get('cleanupNextStep'):
            result['nextWork'].append(dict(resourceRef=rid, action='cleanup', nextStep=resource['cleanupNextStep']))
        if resource.get('disposition') not in ('stopped-retain', 'released', 'contained') or not readbacks:
            unsafe = True;diagnostic('resource-containment-unverified', resourceRef=rid)
    effects = {e['actionId']:e for e in resources.get('pendingEffects', []) if not e.get('resolved')}
    for effect in effects.values():
        if effect.get('readerNextStep'):
            result['nextWork'].append(dict(actionId=effect['actionId'], action='reconcile-state', nextStep=effect['readerNextStep']));continue
        limitation = effect.get('unavailableReadback') or {}
        fields = ('exactEffect', 'lastKnownState', 'unavailableReason', 'unknownImpact', 'noReplayRule', 'resourceDisposition', 'reopenCondition')
        if not all(limitation.get(k) for k in fields) or limitation.get('contained') is not True:
            unsafe = True;diagnostic('unknown-effect-not-contained', actionId=effect['actionId'])
        else:
            references(effect.get('questionIds', []), qs, 'contained effect question')
            if effect.get('caseId'):references([effect['caseId']], cs, 'contained effect case')
            limited_qs.update(effect.get('questionIds', []))
            if effect.get('caseId'):limited_cs.add(effect['caseId'])
            result['limitations'].append(dict(id=effect['actionId'], kind='unknown-effect', **copy.deepcopy(limitation)))
            result['reopenConditions'].append(dict(itemId=effect['actionId'], condition=limitation['reopenCondition']))
    if resources.get('pendingOperations') or resources.get('unknownResources'):
        unsafe = True;diagnostic('pending-producer-or-resource')
    unexplained = (set(open_qs)-limited_qs) | (set(open_cs)-limited_cs) | (unanswered-set(open_qs)-set(open_cs)-limited_criteria)
    # Empty workloads or missing readers are not external limitations.
    if unexplained and not result['nextWork']:diagnostic('unanswered-duties-without-next-action', ids=sorted(unexplained))
    result['unansweredObligationIds'] = sorted(unanswered)
    request = definition.get('userRequest')
    if request is not None:
        if not isinstance(request, dict) or request.get('kind') not in ('pause', 'stop') or not request.get('source'):
            raise ValueError('explicit user pause/stop source required')
        result['decision'] = 'stopped-by-user' if request['kind'] == 'stop' else 'checkpoint-required'
    elif unsafe:result['decision'] = 'checkpoint-required'
    elif result['nextWork']:result['decision'] = 'continue'
    elif result['diagnostics']:result['decision'] = 'review-needed'
    else:
        result['decision'] = 'ready-to-close'
        result['eligibleStatus'] = 'completed-with-limitations' if unanswered or any(l['kind']=='unknown-effect' for l in result['limitations']) else 'completed'
    return result


def round_resource_state(run, reconciliation):
    """Retain unknowns; a prose 'stopped' sentence is never readback."""
    from .question_evidence import collect_pending_effects, pending_effects_from_run
    pending = collect_pending_effects(run.get('operations', []), run.get('actionHistory', []),
        (reconciliation or {}).get('pendingEffects', []) + pending_effects_from_run(run))
    resolved = {e['actionId'] for e in (reconciliation or {}).get('pendingEffects', []) if e.get('resolved')}
    from .question_evidence import resolved_effect_ids
    for observation in list(run.get('scopeAssessment', {}).get('questionObservations', {}).values()) + list((reconciliation or {}).get('observations', {}).values()):
        resolved.update(resolved_effect_ids(observation, {o['id']:o for o in run.get('operations', [])}, pending))
    for e in pending:
        if e['actionId'] in resolved:e['resolved'] = True
    continuation = run.get('continuation', {})
    declared = run.get('resourceState', {})
    owned = run.get('ownedResources', [])
    by_ref = {r['resourceRef']:r for r in continuation.get('resourceDisposition', [])}
    by_ref.update({r['resourceRef']:r for r in declared.get('resources', [])})
    for resource in owned:
        ref = resource if isinstance(resource, str) else resource['resourceRef']
        by_ref.setdefault(ref, dict(resourceRef=ref, disposition='unknown'))
    return dict(resources=list(by_ref.values()), operations=run.get('operations', []),
        pendingEffects=pending, pendingOperations=continuation.get('pendingOperations', []) +
            [o['id'] for o in run.get('operations', []) if o.get('status',o.get('executionStatus')) in ('running','accepted','pending','queued') and o.get('effect') in ('start','mutation')],
        unknownResources=continuation.get('unknownOutcomes', []))


def review_current_round(run, projection, reconciliation, prerequisites=None):
    """Shared report/CLI composition. No I/O, stale closure status is ignored."""
    from .work_selection import select_next_work
    rec = reconciliation or {};inv = rec.get('inventory') or {}
    selection = select_next_work(inv, rec, prerequisites or {}, run.get('actionHistory', []), set(),
        residual_work=projection.get('residualWork')) if inv else {}
    current = {**projection, 'reviewInventories': run.get('reviewInventories', [])}
    review = review_round_closure(run.get('assessmentRound'), current, rec, projection.get('residualWork'),
        selection, round_resource_state(run, rec))
    # Semantic input identity invalidates a finalized review after changed retained
    # results/build/scope, without retaining raw payloads or a filesystem manifest.
    from .security_scope import stable_id
    from .discovery_handoff import clean
    import html
    def semantic(value):
        if isinstance(value, dict):
            return {k:semantic(v) for k,v in value.items() if k not in
                ('evidenceRef','evidenceRefs','evidenceStatus','implementationPins','evidenceReadback','technicalFolder',
                 'requestHeader','responseHeader','requestBody','responseBody','raw','rawData','rawRequest','rawResponse','credentials')}
        if isinstance(value, (list, tuple)):return [semantic(v) for v in value]
        return clean(html.escape(value)) if isinstance(value, str) else value
    known_routes = {r['id'] for r in run.get('inventory', []) if isinstance(r, dict) and r.get('id')} if isinstance(run.get('inventory'), list) else set()
    known_features = {f['id'] for f in inv.get('discoveryReview', {}).get('features', [])}
    for kind,known in (('routes',known_routes),('features',known_features)):
        reviewed = {i for row in run.get('reviewInventories', []) if row.get('kind') == kind for i in row.get('unitIds', [])}
        # An assigned-scope discovery can supply its own feature accounting.
        if kind=='features' and rec.get('discoveryReview', {}).get('extent', {}).get('kind')=='assigned-scope':reviewed |= known
        if known - reviewed:
            review['diagnostics'].append(dict(code='known-inventory-units-omitted',kind=kind,ids=sorted(known-reviewed)))
    if run.get('responsibilityInventory') and not inv:
        review['diagnostics'].append(dict(code='missing-retained-responsibility-reconciliation'))
    if review['diagnostics'] and review['eligibleStatus']:
        review['eligibleStatus']=None;review['decision']='review-needed'
    review['inputStateId'] = stable_id('round-closure-input', semantic(dict(
        definition={k:run.get('assessmentRound', {}).get(k) for k in ('id','objective','scopeBasis','assessmentId','product','environment','scopeRevision','reviewUniverse')},
        scope=projection.get('securityScope'), assessment=run.get('scopeAssessment'),
        operations=run.get('operations', []), actionHistory=run.get('actionHistory', []),
        reconciliation=rec, resources=round_resource_state(run, rec),
        inventories=run.get('reviewInventories', []), build=run.get('currentTestedBuild'),
        findings=projection.get('summary'))))
    return review
