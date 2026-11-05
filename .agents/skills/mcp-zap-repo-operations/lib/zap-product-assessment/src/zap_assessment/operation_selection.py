"""Deterministic offline decisions over reviewed facts and explicit scheduling data."""
from datetime import timezone

from .contracts import digest
from .criteria_workflow import approval_digest
from .operator_state import timestamp
from .question_evidence import operation_index


def delivery_digest(run, review):
    """Bind delivery to reviewed report content, independent of verification time."""
    workflow = run['criteriaWorkflow']
    return digest(dict(assessmentId=run['assessmentId'],
                       criteriaDigest=approval_digest(workflow, 'criteria'),
                       planDigest=approval_digest(workflow, 'plan'),
                       criterionResults=review['criterionResults'], caseResults=review['caseResults'],
                       operations=run.get('operations', [])))


def select_next(run, operator, review, coordinator_inspection, *, evidence_index=(), now, managed=False):
    if now.utcoffset() is None:
        raise ValueError('aware selection time required')
    workflow = run['criteriaWorkflow']
    plan = workflow['plan']
    plan_digest = approval_digest(workflow, 'plan')
    cases = {row['id']: row for row in plan['cases']}
    reviewed = {row['caseId']: row for row in review.get('caseResults', [])}
    obligations = {row['caseId'] for row in review.get('nextWork', []) if 'caseId' in row}
    inspection = coordinator_inspection or {}
    effects = {row['actionId']: row for row in inspection.get('knownPendingEffects', [])}
    for row in review.get('pendingEffects', []):
        effects[row['actionId']] = {**effects.get(row['actionId'], {}), **row}
    degraded = not inspection.get('effectsAllowed', True)
    stopped = bool(workflow.get('userRequest')) or bool(operator.get('stopRecord'))
    stale = operator['planDigest'] != plan_digest
    status = review.get('assessmentStatus', 'recovery_required')
    result = dict(decisionVersion=1, planDigest=plan_digest, mode=(
        'stopped' if stopped else 'recovery-only' if degraded else 'normal'),
        assessmentStatus=status, criterionCounts=review.get('criterionCounts'),
        pendingActionIds=sorted(effects), pendingCertainty=inspection.get('pendingCertainty', 'complete'),
        readyWorkIds=[], deferred=[], blockedCases={}, nextAction=None, nextWakeAt=None,
        canConcludeTurn=False, conclusionReason=None)
    candidates = {}
    for row in evidence_index:
        cid = row['caseId']
        if cid not in cases or cid in candidates:
            raise ValueError('unknown or duplicate case in retained evidence index')
        candidates[cid] = {key: row[key] for key in
                           ('directAcks', 'candidateSourceEvidence', 'relatedRuntimeRefs') if row.get(key)}

    def choose(kind, reason=None, **fields):
        result['nextAction'] = dict(kind=kind, reasonCode=reason or kind, refs=[], **fields)
        return result

    def conclude(reason):
        result.update(canConcludeTurn=True, conclusionReason=reason)
        return result

    approved = bool(review.get('approvalStatus')) and all(review['approvalStatus'].values())
    if not approved and not stopped and not degraded:
        return choose(status)
    if stale and not stopped and not degraded and not effects:
        return choose('rebase-schedule', 'stale-plan-digest')

    repairs = {row['id']: row for row in operator['repairs']}
    works = {} if stale else {row['id']: row for row in operator['workItems']}
    blocks = {row['id']: row for row in operator['blocks']}
    leases = inspection.get('leases', {})
    binding_facts = inspection.get('executionBindings', {})
    repair_blocks = {
        wid: [rid for rid, repair in repairs.items() if repair['status'] not in ('verified', 'superseded')
              and (wid in repair['affectedWorkIds'] or work['mode'] == 'runtime'
                   and set(work['resourceIds']) & set(repair['affectedResourceIds']))]
        for wid, work in works.items()
    }
    ready, ttl, closure, wake = [], [], [], []
    consumed = set(effects) | set(inspection.get('consumedActionIds', []))
    operations = operation_index(run.get('operations', []))
    consumed.update(operations)
    consumed.update(row.get('actionId') for row in operations.values())
    for event in run.get('actionHistory', []):
        if isinstance(event, dict):
            row = event.get('data', event)
            if isinstance(row, dict):
                consumed.add(row.get('actionId'))
    limited_cases = set()
    for cid, row in reviewed.items():
        if row.get('limitation') and not row['limitation']['remainingFeasibleActions']:
            limited_cases.add(cid)
            result['blockedCases'][cid] = row['limitation']['reopenCondition']
    for effect in effects.values():
        if effect.get('caseId'):
            result['blockedCases'][effect['caseId']] = 'reconcile-original-effect'

    def defer(work, reason, dependencies=(), earliest=None, refs=None):
        result['deferred'].append(dict(workId=work['id'], reasonCode=reason, dependsOn=list(dependencies),
            refs=refs if refs is not None else work['basisRefs'], earliestAt=earliest.isoformat() if earliest else None))

    for wid, work in works.items():
        if work['state'] == 'done':
            continue
        member_ids = set(work['caseIds'])
        original = effects.get(work.get('readbackOf'))
        runtime = work['mode'] == 'runtime'
        readback = original is not None and runtime
        if stopped and not readback and work['kind'] != 'resource-review':
            defer(work, 'user-boundary')
            continue
        if degraded and (runtime or work['kind'] not in ('source-review', 'evidence-review', 'prepare')
                         or member_ids & set(result['blockedCases'])):
            defer(work, 'coordinator-integrity')
            continue
        if work['kind'] == 'delivery':
            defer(work, 'final-delivery-only')
            continue
        if repair_blocks[wid]:
            defer(work, 'repair-open', repair_blocks[wid])
            continue
        deps = [dep for dep in work['dependsOnWorkIds'] if works[dep]['state'] != 'done' or repair_blocks[dep]]
        if deps:
            defer(work, 'work-dependency', deps)
            continue
        when = timestamp(work['notBefore']) if work.get('notBefore') else None
        wait = work.get('waiting') or {}
        waiting_repair = wait.get('repairId')
        unresolved_repair = waiting_repair and repairs[waiting_repair]['status'] != 'verified'
        if work['state'] == 'waiting' and (unresolved_repair or not (
                when or wait.get('dependsOnWorkIds') or waiting_repair)):
            defer(work, 'waiting-dependency', refs=wait['basisRefs'])
            continue
        case_deps = sorted({dep for cid in member_ids for dep in cases[cid].get('dependsOnCases', [])
                           if reviewed.get(dep, {}).get('outcome') not in ('matched', 'violated')})
        if case_deps and not readback and not degraded:
            defer(work, 'case-dependency', case_deps)
            continue
        action = work.get('actionRef') or {}
        preparation = None
        task_id = None
        if runtime:
            if action['actionId'] in consumed:
                defer(work, 'consumed-action')
                continue
            if work.get('readbackOf') and not readback and work['phase'] != 'ttl-readback':
                defer(work, 'missing-original-effect')
                continue
            if not readback and any(not effect.get('caseId') or effect['caseId'] in member_ids for effect in effects.values()):
                defer(work, 'pending-effect')
                continue
            binding = binding_facts.get(wid, {})
            binding_status = binding.get('status')
            task_id = binding.get('taskId') if binding_status == 'verified' else None
            if task_id and not readback and any(effect.get('taskId') == task_id for effect in effects.values()):
                defer(work, 'pending-shared-task-effect')
                continue
            if readback and (not original.get('taskId') or
                    (task_id and task_id != original['taskId']) or not all(
                    leases.get(resource, {}).get('taskId') == original['taskId']
                    and leases[resource]['assessmentId'] == run['assessmentId'] for resource in work['resourceIds'])):
                defer(work, 'original-reader-ownership-unproven')
                continue
            occupied = [resource for resource in work['resourceIds'] if resource in leases and
                        not (task_id or readback)]
            if binding_status == 'conflict':
                defer(work, 'execution-binding-conflict', occupied, refs=binding['refs'])
                continue
            if occupied and any(leases[resource]['assessmentId'] != run['assessmentId'] or
                                any(effect.get('taskId') == leases[resource]['taskId'] for effect in effects.values())
                                for resource in occupied):
                defer(work, 'resource-conflict', occupied)
                continue
            if occupied or binding_status in ('unavailable', 'unleased'):
                preparation = binding.get('refs', work['basisRefs'])
                if inspection.get('journalPath'):
                    preparation = [*preparation, inspection['journalPath']]
            if effects and not readback and any(not row.get('taskId') or not any(
                    lease['taskId'] == row['taskId'] and lease['assessmentId'] == run['assessmentId']
                    for lease in leases.values()) for row in effects.values()):
                defer(work, 'runtime-isolation-unproven')
                continue
        if when and when > now:
            wake.append(when)
            defer(work, 'not-before', earliest=when)
            continue
        category = ttl if work['phase'] == 'ttl-readback' else closure if work['phase'] == 'closure' else ready
        kind = work['kind']
        reason = ('pending-effect-readback' if readback else
                  'verified-execution-binding' if task_id else 'ready-work')
        if category is ttl:
            reason = 'ttl-revalidate-control'
            if not work.get('controlRefs'):
                kind, reason = 'prepare', 'ttl-control-required'
        if preparation is not None:
            kind = 'prepare'
            reason = 'acquire-execution-lease' if binding_status == 'unleased' else 'resolve-execution-binding'
        priority = 0 if readback and preparation is None else 1 if kind == 'evidence-review' else 2
        block = blocks[work['blockId']]
        fields = dict(kind=kind, workId=wid, blockId=block['id'], reasonCode=reason,
                      refs=work['basisRefs'], nextStep=work['nextStep'])
        if preparation is not None:
            step = ('Check task eligibility and acquire the exact packet lease' if binding_status == 'unleased'
                    else 'Verify and persist the original packet binding for this work')
            fields.update(refs=preparation, caseId=action['caseId'], nextStep=step)
        elif action:
            fields.update(action)
        elif len(member_ids) == 1:
            fields['caseId'] = next(iter(member_ids))
        category.append(((priority, block['id'] != operator['activeBlockId'], block['order'], work['order'], wid), fields))

    result['nextWakeAt'] = min(wake).astimezone(timezone.utc).isoformat() if wake else None
    result['readyWorkIds'] = [fields['workId'] for group in (ready, ttl, closure) for _, fields in sorted(group)]
    if ready and min(ready)[0][0] <= 1:
        result['nextAction'] = min(ready)[1]
        return result
    if not stopped and not degraded:
        for cid in sorted(obligations):
            if cid not in candidates or not candidates[cid] or cid in result['blockedCases']:
                continue
            if all(reviewed.get(dep, {}).get('outcome') in ('matched', 'violated')
                   for dep in cases[cid].get('dependsOnCases', [])):
                return _case_action(result, cases[cid], reviewed[cid], candidates[cid])
    if ready:
        result['nextAction'] = min(ready)[1]
        return result
    if not stopped:
        for rid, repair in sorted(repairs.items()):
            if repair['status'] in ('open', 'reproducing', 'implementing', 'verifying'):
                return choose('repair', 'repair-' + repair['status'], repairId=rid)
    if degraded:
        kind = 'recover-leases' if inspection.get('openTransactions') else 'inspect-recovery'
        result = choose(kind, 'coordinator-recovery-required')
        if effects or inspection.get('pendingCertainty') == 'prefix-only':
            result['nextAction']['pendingSupervision'] = True
        return result
    if stopped:
        if closure or ttl:
            result['nextAction'] = min(closure + ttl)[1]
            return result
        if effects:
            choose('reconcile-original-effect', 'pending-supervision', actionId=sorted(effects)[0])
            return conclude('explicit-stop-with-pending-supervision')
        if any(lease['assessmentId'] == run['assessmentId'] for lease in leases.values()):
            return choose('resource-review', 'owned-resource-disposition')
        return conclude('explicit-stop-boundary')

    for cid in sorted(obligations):
        if cid in result['blockedCases']:
            continue
        deps = [dep for dep in cases[cid].get('dependsOnCases', [])
                if reviewed.get(dep, {}).get('outcome') not in ('matched', 'violated')]
        if deps:
            result['deferred'].append(dict(caseId=cid, reasonCode='case-dependency', dependsOn=deps,
                                           refs=[], earliestAt=None))
            continue
        linked = [work for work in works.values() if cid in work['caseIds']]
        if linked and any(work['state'] != 'done' for work in linked):
            continue
        return _case_action(result, cases[cid], reviewed[cid], {}, managed=managed)
    if ttl:
        result['nextAction'] = min(ttl)[1]
        return result
    if effects:
        return choose('reconcile-original-effect', 'prepare-reader', actionId=sorted(effects)[0])
    if closure:
        result['nextAction'] = min(closure)[1]
        return result
    if obligations or wake or any(w['state'] != 'done' and w['kind'] != 'delivery' for w in works.values()):
        choose('review-dependencies', 'remaining-dependencies')
        return conclude('waiting-on-recorded-dependencies')
    for row in review.get('criterionResults', []):
        if row['verdict'] is None and row['applicability'] != 'applicable':
            return choose('review-applicability', criterionId=row['criterionId'])
    if not review.get('eligibleForCompletion'):
        diagnostics = review.get('diagnostics', [])
        resource_prefixes = ('resource-', 'unreviewed-resources:', 'active-coordinator-lease:',
                             'uncontrolled-resource:', 'stopped-producer-', 'retained-producer-')
        kind = 'resource-review' if any(item.startswith(resource_prefixes) for item in diagnostics) else 'review-closure'
        return choose(kind, diagnostics=diagnostics)
    source = delivery_digest(run, review)
    receipt = operator.get('delivery') or {}
    if receipt.get('status') == 'verified' and receipt.get('sourceDigest') == source:
        choose('workflow-done', sourceDigest=source)
        return conclude('verified-final-delivery')
    return choose('verify-final-delivery', sourceDigest=source)


def _case_action(result, case, row, candidates, *, managed=False):
    evidence = row.get('evidence', {})
    missing = set(evidence.get('missingUnits', case['requiredEvidence']))
    if evidence.get('contextDiagnostics'):
        missing.update(case['requiredEvidence'])
    result['nextAction'] = dict(kind=('prepare' if managed else
        'reconcile-case' if candidates or evidence else 'inspect-case'),
        reasonCode='retained-evidence' if candidates else 'case-obligation-without-ready-work',
        caseId=case['id'], criterionIds=case['criterionIds'], refs=[],
        missingUnits=[unit for unit in case['requiredEvidence'] if unit in missing],
        diagnostics=row.get('diagnostics', []), retainedCandidates=candidates,
        feasibleActions=row.get('limitation', {}).get('remainingFeasibleActions', []))
    return result
