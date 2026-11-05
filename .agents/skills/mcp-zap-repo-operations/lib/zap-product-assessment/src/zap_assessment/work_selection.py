"""Stable, read-only work proposals, shared with guarded continuation."""
from .question_evidence import collect_pending_effects, affected


def select_next_work(inventory, reconciliation, prerequisites, attempts, available_action_ids, *, residual_work=None, round_closure=None):
    seen = {r.get('data', r).get('actionId') for r in attempts}
    seen.update(reconciliation.get('consumedActionIds',[]))
    seen.update(o['actionId'] for o in reconciliation.get('operations',[]) if o.get('actionId') and o.get('status',o.get('executionStatus'))!='planned')
    observations = reconciliation.get('observations', {})
    pending = collect_pending_effects(reconciliation.get('operations', []), attempts,
        reconciliation.get('pendingEffects', []))
    # Reconciliation has validated resolutions against all original pending rows.
    resolved={e['actionId'] for e in reconciliation.get('pendingEffects',[]) if e.get('resolved')}
    pending=[e for e in pending if e['actionId'] not in resolved]
    states = {r['caseId']: r for r in reconciliation['cases']}
    candidates = [];deferred = [];missing = []
    stop = reconciliation.get('continuationStoppedByUser') is True
    new_workflow = inventory.get('workflowVersion') == 1
    priorities = {c['caseId']: c.get('priority', 'normal') for c in inventory['cases']}
    ranks = {'high': 0, 'normal': 1, 'low': 2}
    for case in inventory['cases']:
        cid = case['caseId'];state = states[cid]
        if state['status'] not in ('eligible', 'blocked'):
            continue
        actions = case.get('actions', [])
        if not actions:
            missing.append(dict(caseId=cid, actionId=None, kind='prepare-adapter', reasonCodes=['missing-handler'], nextPreparation='prepare-adapter'))
        for action in actions:
            aid = action['id'];kind = action['kind']
            reasons = []
            if stop:reasons.append('user-stop')
            if aid in seen:reasons.append('action-already-attempted')
            unknown = bool(state.get('outcomeUnknown') or not new_workflow and observations.get(cid, {}).get('outcomeUnknown'))
            unknown = unknown or new_workflow and any(affected(case, e, observations.get(cid, {})) for e in pending if not e.get('resolved'))
            if unknown and kind != 'reconcile-state':reasons.append('pending-effect')
            if state['status'] == 'blocked' and kind == 'execute':reasons.append('case-prerequisites')
            if any(prerequisites.get(k) is not True for k in action.get('requires', [])):reasons.append('action-prerequisites')
            if any(states.get(k, {}).get('outcomeUnknown') or not new_workflow and observations.get(k, {}).get('outcomeUnknown') for k in action.get('dependsOnCases', [])):
                reasons.append('dependent-unknown-effect')
            row = dict(caseId=cid, actionId=aid, kind=kind, reasonCodes=reasons)
            if reasons:
                deferred.append(row);continue
            if aid not in available_action_ids:
                missing.append({**row, 'reasonCodes': ['missing-handler'], 'nextPreparation': 'prepare-adapter'})
                continue
            priority = ranks[priorities[cid]]
            if kind == 'reconcile-state':rank = (0, 0);reason = 'reconcile-related-state'
            elif action.get('usesExistingResult') is True and action.get('effect') == 'read':rank = (1, priority);reason = 'read-existing-result'
            elif kind == 'execute':rank = (2 + priority, 0);reason = 'ready-question'
            else:
                high_unblock = (action.get('selectionBasis') and any(priorities[k] == 'high' for k in action.get('unblocksCaseIds', [])))
                rank = (3.5, 0) if high_unblock else (5, priority)
                reason = 'prepare-high-impact-dependency' if high_unblock else 'prepare-dependency'
            row['reasonCodes'] = [reason]
            row['_rank'] = rank if new_workflow else (0, 0)
            candidates.append(row)
    candidates.sort(key=lambda r: r['_rank'])
    for row in candidates:row.pop('_rank')
    discovery_gaps=reconciliation.get('inventoryGaps',[])
    proposal = dict(orderedCandidates=candidates, deferred=deferred, missingHandlers=missing,inventoryGaps=list(discovery_gaps),
        nextPreparation=[dict(caseId=r['caseId'], actionId=r['actionId'], action='prepare-adapter') for r in missing]+
            ([dict(action='review-discovery',reasonCode='inventory-review-gap')] if discovery_gaps else []),
        reasonCodes=list(dict.fromkeys([code for r in candidates + deferred + missing for code in r['reasonCodes']]+
            (['inventory-review-gap'] if discovery_gaps else []))),
        selectedActionId=candidates[0]['actionId'] if candidates else None)
    import copy
    proposal['executionProposal'] = copy.deepcopy(proposal)
    residual = residual_work or dict(residualReviewStatus='not-supplied', decision='review-needed',
        reviewExtent=None, unreviewedRefs=[], reviewDiagnostics=[dict(code='residual-review-not-supplied')],
        reasons=['Legacy execution remains available; residual backlog has not been reviewed'])
    proposal['residualReviewStatus'] = residual['residualReviewStatus']
    proposal['planningProposal'] = [dict(category=category, **copy.deepcopy(row)) for category in
        ('actionableReadback', 'actionableExecution', 'preparationNeeded', 'investigationNeeded', 'unclassified')
        for row in residual.get(category, [])]
    proposal['planningProposal'].extend(dict(category='preparationNeeded', **copy.deepcopy(row)) for row in proposal['nextPreparation'])
    decision = residual['decision']
    if stop:
        decision = 'review-needed'
    elif candidates or missing:
        decision = 'continue'
    proposal['reviewedScopeDecision'] = dict(decision=decision, reviewExtent=copy.deepcopy(residual.get('reviewExtent')),
        decisionScope='reviewed-scope-only', unreviewedRefs=copy.deepcopy(residual.get('unreviewedRefs', [])),
        reviewDiagnostics=copy.deepcopy(residual.get('reviewDiagnostics', [])),
        reasons=copy.deepcopy(residual.get('reasons', [])) + (['User stop honored; proposals retained without dispatch'] if stop else []))
    if round_closure is not None:
        proposal['roundClosureDecision'] = copy.deepcopy(round_closure)
    return proposal
