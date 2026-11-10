"""Task responsibility readback over existing case/observation records.

No transport, authority grant or universal scanner. Inventory comes from product
sources before workload selection. Executors keep their own admission and journal.
"""
import copy
from .discovery import TRACKS, secret_check


def validate_inventory(inventory):
    if inventory.get('track') not in TRACKS or not inventory.get('productLocation'):
        raise ValueError('task product/track required')
    cases=inventory.get('cases',[]);ids=[c['caseId'] for c in cases]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate task responsibility')
    for c in cases:
        if not c.get('evidenceRefs') or not c.get('requiredEvidence'):
            raise ValueError('responsibility needs product provenance and observation requirements')
        for action in c.get('actions',[]):
            if action.get('effect') not in ('read','mutation','start') or not action.get('id'):raise ValueError('action impact/id required')
        if c.get('disposition')=='not-applicable':
            if c.get('gapKind') in ('auth','role','fixture','capability','configuration') or not c.get('applicability'):
                raise ValueError('prerequisite is not inapplicability')
        if c.get('disposition')=='user-excluded' and not c.get('scopeBasis'):
            raise ValueError('only user changes scope')
    from .business_discovery import validate_discovery_review
    validate_discovery_review(inventory)
    secret_check(inventory)
    return inventory


def inventory_from_operations(doc,track,*,complete=False):
    """Discovery facts, independent of admitted operations, campaigns and registry.

    A technique decision is deliberately open. Tester replaces/refines it using
    actual input/risk and retains the source responsibility ID when allocating.
    No blanket rule x field matrix or automatic inapplicability is generated.
    """
    if track not in TRACKS:raise ValueError('unknown track')
    cases=[]
    for o in doc.get('operations',[]):
        if track=='be-anonymous' and o['protected'] or track=='be-authenticated' and not o['protected']:continue
        cases.append({'caseId':o['id'],'operationId':o['id'],'method':o['method'],
            'path':o['pathTemplate'],'evidenceRefs':o['evidenceRefs'],
            'requiredEvidence':['technique-decision','result-read'],
            'input':copy.deepcopy(o.get('input',{})),
            'question':'Select and execute meaningful techniques for this operation and its roles/state',
            'prerequisites':[]})
    return validate_inventory({'productLocation':doc.get('productLocation',doc.get('product',{}).get('location')),
        'track':track,'complete':complete,'cases':cases,'authObservations':copy.deepcopy(doc.get('authObservations',doc.get('auth')))})


def reconcile(inventory,observations,prerequisites,workload_cases=(),*,operations=(),attempts=(),pending_effects=()):
    """Join against task inventory; deleting a workload row never deletes its duty."""
    from .product_workflow import reconcile_responsibilities
    validate_inventory(inventory)
    cases=copy.deepcopy(inventory['cases']);ids={c['caseId'] for c in cases}
    extra=[c for c in workload_cases if c['caseId'] not in ids]
    # Newly discovered work is retained immediately, but requires inventory review.
    cases.extend(copy.deepcopy(extra))
    for c in cases:
        c['requireResultRead']=True
    checked=copy.deepcopy(observations)
    from .business_discovery import review_business_coverage
    from .question_evidence import collect_pending_effects, resolve_question_evidence, resolved_effect_ids, operation_index
    pending=collect_pending_effects(operations,attempts,pending_effects)
    evidence={}
    new_workflow=inventory.get('workflowVersion')==1
    resolved=set()
    if new_workflow:
        ops=operation_index(operations)
        from .question_evidence import validate_observation_links
        for observation in checked.values():
            validate_observation_links(observation,ops)
            resolved.update(resolved_effect_ids(observation,ops,pending))
        pending=[{**e,'resolved':e['actionId'] in resolved} for e in pending]
    for c in cases:
        seen=checked.setdefault(c['caseId'],{})
        if new_workflow:
            seen.setdefault('evidenceLinks',[])
            resolution=resolve_question_evidence(c,seen,operations,pending)
            evidence[c['caseId']]=resolution
            seen['evidenceUnits']=resolution['supportedUnits']
            seen['resultRead']=bool(resolution['supportOperationIds'])
            seen['outcomeUnknown']=bool(resolution['unresolvedEffectIds']) or bool(seen.get('outcomeUnknown') and not seen.get('resolvedEffects'))
        else:
            mismatch=[k for k in ('actorRef','role','state','relation') if c.get(k) not in (None,'product-defined') and seen.get(k)!=c[k]]
            if mismatch:seen['evidenceUnits']=[];seen['missingContext']=mismatch
            old_context=c.get('coverageContext',{})
            if any(k in seen.get('coverageContext',{}) and v!=seen['coverageContext'][k] for k,v in old_context.items()):
                seen.setdefault('contextDiagnostics',[]).append('legacy-context-conflict')
    result=reconcile_responsibilities(cases,checked,prerequisites)
    missing=[]
    if inventory.get('complete') is not True or not cases:missing.append('product inventory completeness unresolved')
    if extra:missing.append('new workload responsibilities must be added to product inventory')
    outside=set(observations)-{c['caseId'] for c in cases}
    if outside:missing.append('observations outside product inventory')
    discovery=review_business_coverage(inventory)
    if new_workflow and discovery['reviewStatus']=='gaps':
        missing.extend('feature-unmapped:'+i for i in discovery['unmappedFeatures'])
        missing.extend('case-unreviewed:'+i for i in discovery['unreviewedCases'])
        missing.extend('source-unresolved:'+i for i in discovery['unresolvedSources'])
        missing.extend(discovery['diagnostics'])
    result['discoveryReview']=discovery
    result['observations']=copy.deepcopy(observations)
    result['prerequisites']=copy.deepcopy(prerequisites)
    result['questionEvidence']=evidence
    result['pendingEffects']=copy.deepcopy(pending)
    result['consumedActionIds']=[o['actionId'] for o in operation_index(operations).values()
        if o.get('actionId') and o.get('status',o.get('executionStatus'))!='planned']
    result['inventoryGaps']=missing
    result['openResponsibilities']=[r for r in result['cases'] if r['status'] in ('eligible','blocked')]
    result['taskCompletion']='complete' if not missing and not result['openResponsibilities'] else 'partial'
    result['handoffClosesTask']=result['taskCompletion']=='complete'
    result['scope']=copy.deepcopy({k:inventory[k] for k in ('productLocation','track','environment','origin') if k in inventory})
    result['inventory']=copy.deepcopy(inventory)
    if extra:result['inventory']['cases']=copy.deepcopy(cases);result['inventory']['complete']=False
    result['nextActions']=[{'caseId':r['caseId'],'action':'reconcile-state' if r.get('outcomeUnknown') else
        'resolve-prerequisites' if r['status']=='blocked' else 'execute',
        'dependencies':r.get('dependencies',[])} for r in result['openResponsibilities']]
    result['completionSummary']=compose_completion_summary(result)
    return result


def continue_work(inventory,observations,prerequisites,handlers,*,persist,attempts=(),max_actions=32,stop=False,operations=()):
    """Execute eligible actions, including preparation, then reconcile their readback.

    handlers map reviewed action IDs to existing executor/fixture/repair adapters.
    Each callback returns actual observations/prerequisites, never an exit code as
    coverage. Caller owns target/actor admission; durable intent is written BEFORE
    dispatch. Reusing an action ID from an ACK/unknown intent is forbidden. A new
    allocation after repair must omit acknowledged mutations and unknown starts.
    No arbitrary shell command or import from a workload is executed here.
    """
    obs=copy.deepcopy(observations);pre=copy.deepcopy(prerequisites);events=[]
    from .question_evidence import operation_index
    operation_rows=copy.deepcopy(list(operation_index(operations).values()))
    new_workflow=inventory.get('workflowVersion')==1
    decisions=[]
    from .work_selection import select_next_work
    for row in (() if new_workflow else {r['actionId']:r for r in attempts}.values()):
        if row['state'] in ('intent','unknown') and row.get('effect') in ('mutation','start') and row['actionId'] not in obs.get(row['caseId'],{}).get('resolvedActionIds',[]):
            obs[row['caseId']]={**obs.get(row['caseId'],{}),'outcomeUnknown':True}
    def record(row):
        persist(copy.deepcopy(row));events.append(copy.deepcopy(row))
    for _ in range(max_actions):
        current=reconcile(inventory,obs,pre,operations=operation_rows,attempts=list(attempts)+events)
        current.update(observations=obs,operations=operation_rows,continuationStoppedByUser=stop)
        decision=select_next_work(inventory,current,pre,list(attempts)+events,set(handlers))
        decisions.append(decision)
        if stop or current['taskCompletion']=='complete' or decision['selectedActionId'] is None:break
        c=next(c for c in inventory['cases'] if any(a['id']==decision['selectedActionId'] for a in c.get('actions',[])))
        a=next(a for a in c['actions'] if a['id']==decision['selectedActionId'])
        base={'actionId':a['id'],'caseId':c['caseId'],'kind':a['kind'],'effect':a.get('effect','read')}
        if c.get('coverageContext'):base['coverageContext']=copy.deepcopy(c['coverageContext'])
        record({**base,'state':'intent','replay':False})
        try:
            value=handlers[a['id']](copy.deepcopy(a))
            if not isinstance(value,dict):raise ValueError('action must return readback')
            operation_rows.extend(copy.deepcopy(value.get('operations',[])))
            updates=value.get('observations',{})
            if set(updates)-{r['caseId'] for r in inventory['cases']}:raise ValueError('action observation outside inventory')
            for cid,row in updates.items():
                old=obs.get(cid,{})
                if new_workflow:
                    # Full context equality is necessary to accumulate current support.
                    # Conflicting observations remain available for review, not unioned.
                    old_context={l['operationId']:l['context'] for l in old.get('evidenceLinks',[]) if l['role']=='support'}
                    new_context={l['operationId']:l['context'] for l in row.get('evidenceLinks',[]) if l['role']=='support'}
                    compatible=not old_context or not new_context or all(v==w for v in old_context.values() for w in new_context.values())
                    from .question_evidence import resolve_question_evidence, collect_pending_effects
                    pending=collect_pending_effects(operation_rows,list(attempts)+events)
                    incoming=resolve_question_evidence(next(c for c in inventory['cases'] if c['caseId']==cid),
                        {**row,'evidenceLinks':row.get('evidenceLinks',[])},operation_rows,pending)
                    prior=resolve_question_evidence(next(c for c in inventory['cases'] if c['caseId']==cid),
                        {**old,'evidenceLinks':old.get('evidenceLinks',[])},operation_rows,pending)
                    merged={**copy.deepcopy(old),**copy.deepcopy(row)}
                    if compatible:
                        merged['evidenceLinks']=copy.deepcopy(old.get('evidenceLinks',[]))+copy.deepcopy(row.get('evidenceLinks',[]))
                        # During validation our own durable intent is still pending.
                        # Retain a fact-backed outcome label until ACK; reconciliation
                        # still withholds units for every unresolved effect.
                        def has_read_support(proof):
                            return bool(proof['supportOperationIds']) and all(
                                d=='pending-effects-require-readback' for d in proof['contextDiagnostics'])
                        supported_outcomes=([old.get('outcome')] if has_read_support(prior) else [])+([row.get('outcome')] if has_read_support(incoming) else [])
                        merged['outcome']='violated' if 'violated' in supported_outcomes else 'matched' if 'matched' in supported_outcomes else 'unknown'
                    else:
                        merged['contextHistory']=copy.deepcopy(old.get('contextHistory',[]))+[copy.deepcopy(old)]
                        merged['contextDiagnostics']=['continuation-context-conflict-review-required']
                    merged['resolvedEffects']=copy.deepcopy(old.get('resolvedEffects',[]))+copy.deepcopy(row.get('resolvedEffects',[]))
                    # Derive claimed units afresh from links; no copying requirements.
                    merged.pop('evidenceUnits',None);merged.pop('observationUnits',None)
                    reconcile(inventory,{**obs,cid:merged},pre,operations=operation_rows,attempts=list(attempts)+events)
                    obs[cid]=merged
                else:
                    same_context=all(old.get(k)==row.get(k) for k in ('actorRef','role','state','relation'))
                    context_conflict=old.get('coverageContext') is not None and row.get('coverageContext') is not None and old['coverageContext']!=row['coverageContext']
                    resolved=old.get('resolvedActionIds',[])
                    if row.get('stateReconciled'):
                        resolved=list(dict.fromkeys(resolved+[e['actionId'] for e in list(attempts)+events if e['caseId']==cid and e['state'] in ('intent','unknown')]))
                    if old.get('outcomeUnknown') and not row.get('stateReconciled'):raise ValueError('unknown outcome requires state readback')
                    obs[cid]={**copy.deepcopy(old),**copy.deepcopy(row),
                        'evidenceUnits':sorted((set(old.get('evidenceUnits',[])) if same_context else set())|set(row.get('evidenceUnits',[]))),
                        'resolvedActionIds':resolved,
                        'outcome':'violated' if 'violated' in (old.get('outcome'),row.get('outcome')) else row.get('outcome'),
                        'outcomeUnknown':False if row.get('stateReconciled') else old.get('outcomeUnknown',False)}
                    if context_conflict:obs[cid]['contextDiagnostics']=['legacy-context-conflict']
            pre.update(value.get('prerequisites',{}))
            record({**base,'state':'acknowledged','resultRead':True})
        except Exception as e:
            if a.get('effect') in ('mutation','start'):
                obs[c['caseId']]={**obs.get(c['caseId'],{}),'outcomeUnknown':True}
            record({**base,'state':'unknown' if a.get('effect') in ('mutation','start') else 'failed',
                    'errorType':type(e).__name__,'replay':False})
    result=reconcile(inventory,obs,pre,operations=operation_rows,attempts=list(attempts)+events)
    result.update(observations=obs,prerequisites=pre,actionsPerformed=events,actionHistory=list(attempts)+events,
                  continuationStoppedByUser=stop,wholeTrackComplete=False if inventory.get('phaseOnly') else result['handoffClosesTask'])
    result['operations']=operation_rows
    result['selectionDecisions']=decisions
    result['workSelection']=select_next_work(inventory,result,pre,list(attempts)+events,set(handlers))
    return result


def apply_completion(run,reconciliation):
    """Presentation cannot discard open duties or promote executor exit/terminal."""
    if 'criteriaWorkflow' in run or run.get('workflowVersion') == 2:
        raise ValueError('legacy completion cannot evaluate v2; use criteria-review/report')
    if (reconciliation.get('inventory') or {}).get('workflowVersion')==1:
        from .question_evidence import pending_effects_from_run
        refreshed=reconcile(reconciliation['inventory'],reconciliation.get('observations',{}),
            reconciliation.get('prerequisites',{}),operations=run.get('operations',[]),
            attempts=run.get('actionHistory',[])+reconciliation.get('actionHistory',[]),
            pending_effects=pending_effects_from_run(run)+reconciliation.get('pendingEffects',[]))
        reconciliation={**copy.deepcopy(reconciliation),**refreshed}
    result=copy.deepcopy(run)
    result['taskCompletion']='complete' if reconciliation['taskCompletion']=='complete' and not any(reconciliation.get(k) for k in ('openResponsibilities','inventoryGaps','executionGaps')) else 'partial'
    result['responsibilityReconciliation']=copy.deepcopy(reconciliation)
    result['completionSummary']=compose_completion_summary(reconciliation,task_completion=result['taskCompletion'])
    result['notPerformed']=copy.deepcopy(reconciliation['openResponsibilities'])+[{ 'kind':'execution','reason':reason} for reason in reconciliation.get('executionGaps',[])]+[{'kind':'inventory','reason':reason} for reason in reconciliation.get('inventoryGaps',[])]
    result['nextSteps']=copy.deepcopy(reconciliation['nextActions'])+[{ 'action':'reconcile-execution','reason':reason} for reason in reconciliation.get('executionGaps',[])]+[{'action':'discover','reason':reason} for reason in reconciliation.get('inventoryGaps',[])]
    return result


def task_readback(plan,observations=None,prerequisites=None):
    d=plan.get('discovery',{})
    inv=plan.get('responsibilityInventory') or d.get('responsibilityInventory')
    if inv is None and plan.get('track') not in TRACKS:
        return {'taskCompletion':'partial','handoffClosesTask':False,'cases':[],'openResponsibilities':[],
                'inventoryGaps':['task track/product inventory unresolved'],'nextActions':[{'action':'discover'}],
                'scope':{'productLocation':d.get('productLocation'),'track':plan.get('track')},'inventory':None}
    if inv is None:
        # A legacy workload can still be executed/verified. It cannot attest scope.
        inv={'productLocation':d.get('productLocation',d.get('product',{}).get('location','unresolved')),
             'track':plan.get('track'),'complete':False,'cases':[]}
    return reconcile(inv,observations or {},prerequisites or {})


def fe_readback(plan,check,operations):
    """Use independent semantic checker outputs; UI traffic never supplies active units."""
    inv=plan['discovery'].get('responsibilityInventory')
    if not inv:return task_readback(plan)
    observations={}
    journeys={r['id']:r for r in check.get('journeys',[])}
    delivery={r['campaignId']:r for r in check.get('delivery',[])}
    from .transport import field
    terminal={o.get('campaignId') for o in operations if field(o.get('finalStatus',''),'Completed')=='yes'}
    for c in inv['cases']:
        units=[]
        for unit,b in c.get('observationBindings',{}).items():
            ids=b.get('ids',[])
            if not ids:continue
            specs={r['id']:r for r in plan.get('journeys',{}).get('journeys',[])+plan.get('campaigns',[])}
            if c.get('actorRef') and any(specs.get(i,{}).get('actorRef')!=c['actorRef'] for i in ids):continue
            auth=plan.get('journeys',{}).get('auth',{}).get('identity',{})
            if plan.get('track')=='fe-anonymous' and c.get('role') in ('anonymous','ANONYMOUS'):auth={'expectedRole':c['role']}
            if c.get('role') and any(auth.get('roleByActor',{}).get(specs.get(i,{}).get('actorRef'),auth.get('expectedRole'))!=c['role'] for i in ids):continue
            if ('active' in unit.lower() or 'native' in unit.lower()) and b['kind']!='active':raise ValueError('UI cannot supply active evidence')
            if b['kind']=='ui' and all(journeys.get(i,{}).get('completed') for i in ids):units.append(unit)
            if b['kind']=='active' and unit.startswith('active:'):
                parts=unit.split(':',2)
                if len(parts)!=3 or any(specs.get(i,{}).get('vector')!=parts[1] or parts[2] not in specs.get(i,{}).get('vectorFields',[]) for i in ids):continue
            if b['kind']=='active' and all(delivery.get(i,{}).get('delivered') and i in terminal and
                not any(i in m for m in check.get('missing',[])) for i in ids):units.append(unit)
        if c.get('techniqueBasis') and c.get('observationBindings'):units.append('technique-decision')
        if units:observations[c['caseId']]={'outcome':'violated' if any(f.get('journeyId') in {i for b in c.get('observationBindings',{}).values() for i in b.get('ids',[])} for f in check.get('browserObservations',[])) else 'matched',
            'evidenceUnits':units,'resultRead':True,**{k:c[k] for k in ('actorRef','role') if k in c}}
    result=reconcile(inv,observations,{})
    result['observations']=observations
    if check.get('missing') or check.get('errors'):
        result.update(taskCompletion='partial',handoffClosesTask=False,executionGaps=check.get('missing',[])+check.get('errors',[]))
    return result


def validate_result_ids(result):
    """Check joins after redaction, when collisions could otherwise be hidden."""
    operations=result.get('operations',[])
    ids=[r['id'] for r in operations if 'id' in r]
    if len(ids)!=len(set(ids)):raise ValueError('duplicate report operation ID')
    for name in ('coverage',):
        cases=[r['caseId'] for r in result.get(name,[]) if 'caseId' in r]
        if len(cases)!=len(set(cases)):raise ValueError('duplicate report case ID')
    def check(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key=='operationIds' and any(i not in ids for i in item):
                    raise ValueError('unresolved report operation reference')
                if key=='evidenceLinks' or key=='resolvedEffects':
                    from .question_evidence import validate_observation_links
                    validate_observation_links({key:item},operations)
                if key!='securityScope':check(item)
        elif isinstance(value,list):
            for item in value:check(item)
    check(result)


def compact_results(output,run,alerts,reconciliation=None,*,security_scope=None,
                    scope_assessment=None,previous_scope=None,secrets=(),overwrite=False,finalize_round=False):
    """Three derived reports, prepared and validated before publication.

    New destinations publish a staged directory. Overwrites replace individual
    files after staging; they are NOT a crash-atomic bundle transaction. Historical
    journals/pins/raw artifacts are never rewritten by this helper.
    """
    if 'criteriaWorkflow' in run:
        if any(value is not None for value in (reconciliation,security_scope,scope_assessment,previous_scope)):
            raise ValueError('criteria workflow reports use the approved plan; legacy inventories cannot add assignments')
        from .criteria_reporting import publish_reports
        return publish_reports(output,run,alerts,finalize=finalize_round,overwrite=overwrite,secrets=secrets)
    if run.get('workflowVersion') == 2:
        raise ValueError('criteria workflow requires criteriaWorkflow state; never fall back to legacy completion')
    import json
    import os
    import tempfile
    from pathlib import Path
    from .discovery_handoff import clean
    from .safety_io import atomic_bytes
    from .security_scope import canonical_alerts,normalize_scope,project_scope,validate_bundle,stable_id

    requested=Path(output).absolute()
    if requested.is_symlink():raise ValueError('report destination symlink')
    # Resolve the parent once (macOS /var and /tmp are system symlinks).
    # The destination itself and every file inside it must remain regular.
    out=requested.parent.resolve()/requested.name
    names=('RUN.json','ALERTS.json','SCOPE_ALERTS.json')
    def destination_check():
        if requested.is_symlink() or out.is_symlink():
            raise ValueError('report destination symlink')
        if out.exists():
            if not overwrite:raise FileExistsError(out)
            if not out.is_dir() or any(p.name not in names or p.is_symlink() or not p.is_file() for p in out.iterdir()):
                raise ValueError('overwrite only a report destination with regular RUN/ALERTS/SCOPE_ALERTS files')
    destination_check()
    result=apply_completion(run,reconciliation) if reconciliation is not None else copy.deepcopy(run)
    if reconciliation is None and run.get('responsibilityReconciliation'):
        reconciliation=copy.deepcopy(run['responsibilityReconciliation'])
        result=apply_completion(run,reconciliation)
    if reconciliation is not None:
        reconciliation=result['responsibilityReconciliation']
    for operation in result.get('operations',[]):
        if operation.get('status',operation.get('executionStatus'))=='planned':
            raise ValueError('planned actions belong in nextSteps, not performed operations')
        if not operation.get('id'):operation['id']='operation-'+stable_id('legacy-operation',operation)
    alert_result=canonical_alerts(alerts)
    if scope_assessment is None:
        scope_assessment=run.get('scopeAssessment')
    previous_scope=previous_scope or run.get('securityScope')
    security_scope=security_scope if security_scope is not None else previous_scope
    if security_scope is not None:
        security_scope=normalize_scope(security_scope,previous_scope)
        projection=project_scope(security_scope,scope_assessment,result,alert_result,reconciliation)
        # A supplied track inventory is assigned work too; scoped-only reports do
        # not invent whole-product track requirements.
        track_open=reconciliation is not None and result.get('taskCompletion')!='complete'
        result['taskCompletion']='complete' if projection['scopeCompletion']=='complete' and not track_open else 'partial'
        result['securityScope']=security_scope
        result['scopeCompletion']=projection['scopeCompletion']
        result['scopeAssessment']=copy.deepcopy(scope_assessment or {})
        result['residualWork']=copy.deepcopy(projection['residualWork'])
        result['coveragePresentation']=copy.deepcopy(projection['coveragePresentation'])
        result['notPerformed']=[r for r in result.get('notPerformed',[]) if r.get('kind')!='security-scope']
        result['nextSteps']=[r for r in result.get('nextSteps',[]) if r.get('kind')!='security-scope']
        result['notPerformed'].extend({'kind':'security-scope',**copy.deepcopy(r)} for r in projection['openWork'])
        result['nextSteps'].extend({'kind':'security-scope','action':'review-decomposition' if r['nextStep']=='review-decomposition' else 'resolve-scope-question',**copy.deepcopy(r)} for r in projection['openWork'])
        result['scopeInventoryGaps']=projection['inventoryGaps']
        result['nextSteps'].extend({'kind':'security-scope','action':'review-assigned-scope','reason':g} for g in projection['inventoryGaps'])
    else:
        if reconciliation is None:
            # Legacy completion is preserved only as historical, without new
            # reconciliation it cannot attest the current assignment.
            result['historicalTaskCompletion']=result.get('taskCompletion','unknown')
            result['taskCompletion']='partial'
        projection={'scopeStatus':'not-provided','scopeCompletion':'unresolved','criteria':[],
                    'limitations':['User security scope not provided/mapped; no scoped completion claim.'],
                    'summary':{'criteria':0,'uniqueFindings':len(alert_result['alerts']),'criterionAssociations':0}}
    from .round_closure import CLOSED, RoundFinalizationError, review_current_round, validate_round_definition
    if 'assessmentRound' in result or finalize_round:
        review = review_current_round(result, projection, reconciliation)
        if finalize_round and review['eligibleStatus'] is None:
            raise RoundFinalizationError(review)
        if result.get('assessmentRound'):
            definition = validate_round_definition(result['assessmentRound'])
            # A prior finalized status is re-evaluated after any input change.
            previous_closure = definition.pop('closure', None)
            if finalize_round:
                from datetime import datetime, timezone
                definition['status'] = review['eligibleStatus']
                definition['closure'] = dict(scopeRevision=definition['scopeRevision'],
                    finalizedAt=datetime.now(timezone.utc).isoformat(), reason=review['eligibleStatus'],
                    inputRefs=dict(scopeRevision=definition['scopeRevision'],inputStateId=review['inputStateId'],
                        reviewUniverse=copy.deepcopy(definition['reviewUniverse']),
                        criterionIds=definition['reviewUniverse'].get('criterionIds', []),
                        questionIds=definition['reviewUniverse'].get('questionIds', []),
                        caseIds=definition['reviewUniverse'].get('caseIds', []),
                        operationIds=[o['id'] for o in result.get('operations', [])],
                        findingIds=[f['findingId'] for f in alert_result['alerts']]), review=review)
            elif definition['status'] in CLOSED:
                if previous_closure and previous_closure.get('review') == review and review['eligibleStatus'] == definition['status']:
                    definition['closure'] = previous_closure
                else:
                    definition['status'] = 'in-progress'
                    definition['reopenBasis'] = 'Current scope/results/resources differ from the finalized closure review; reconcile without replay'
            if definition.get('userRequest'):
                definition['status']='stopped-by-user' if definition['userRequest']['kind']=='stop' else 'checkpointed'
            result['roundClosureReview'] = review
            projection['roundClosureReview'] = copy.deepcopy(review)
            projection['assessmentRound'] = copy.deepcopy(definition)
    result['completionSummary']=compose_completion_summary(reconciliation,projection,alert_result,task_completion=result['taskCompletion'], assessment_round=result.get('assessmentRound'))
    if 'selectedTracks' in result:
        result['selectedTracksMeaning']='historical-selected-track-labels'
    result['trackSummary']=copy.deepcopy(result['completionSummary'].get('trackSummary', []))
    result['handoffClosesTask']=result['taskCompletion']=='complete'
    context=copy.deepcopy(run.get('assessmentContext',{}))
    for key in ('assessmentId','product','environment'):
        values=[d[key] for d in (context,run,alert_result,security_scope or {}) if d.get(key) is not None and d[key]!='unknown']
        if values and any(v!=values[0] for v in values):raise ValueError('report '+key+' mismatch')
        context[key]=values[0] if values else 'unknown'
    context['scopeRevision']=(security_scope or {}).get('revision') or ((reconciliation or {}).get('inventory') or {}).get('scopeRevision') or context.get('scopeRevision') or 'unknown'
    for report in (result,alert_result,projection):
        report['taskCompletion']=result['taskCompletion']
        report['taskCompletionMeaning']='assigned-obligation-coverage'
        report['roundClosed']=bool(result.get('assessmentRound', {}).get('status') in CLOSED)
        from .coverage_presentation import round_outcome
        report['roundOutcome']=round_outcome(result.get('assessmentRound'),result['taskCompletion'])
        if result.get('assessmentRound'):
            report['assessmentRound']=copy.deepcopy(result['assessmentRound'])
            report['completionSummary']=copy.deepcopy(result['completionSummary'])
        report['assessmentContext']=copy.deepcopy(context)
        report['reportGeneration']={'kind':'recomposition','performsRetest':False,
            'writeGuarantee':'staged new directory; overwrite is per-file atomic, not bundle crash-atomic'}
    if isinstance(alert_result.get('scope'),dict):alert_result['scope']['taskCompletion']=result['taskCompletion']
    alert_result['canonicalSummary']=copy.deepcopy(projection['summary'])
    import base64
    from urllib.parse import quote,quote_plus
    secret_values=set()
    for secret in secrets:
        if isinstance(secret,str) and secret:
            secret_values.update((secret,quote(secret,safe=''),quote_plus(secret),base64.b64encode(secret.encode()).decode()))
    secret_values=sorted(secret_values,key=len,reverse=True)
    # Raw assurance/package fields belong to working artifacts, not the PM report.
    def compact(value):
        if isinstance(value,dict):
            sanitized={}
            for k,v in value.items():
                if k in ('evidenceRef','evidenceRefs','evidenceStatus','implementationPins','evidenceReadback','technicalFolder','requestHeader','responseHeader','requestBody','responseBody','raw','rawData','rawRequest','rawResponse','credentials'):continue
                if not isinstance(k,str):raise ValueError('report object keys must be strings')
                key=compact(k)
                if key in sanitized:raise ValueError('duplicate report key after redaction')
                sanitized[key]=('[private]' if k.lower().replace('-','').replace('_','') in
                    ('password','passwordvalue','token','accesstoken','refreshtoken','setuptoken','sessiontoken','authorization','cookie','setcookie','secret','clientsecret','apikey','privatekey') else compact(v))
            return sanitized
        if isinstance(value,(list,tuple)):return [compact(v) for v in value]
        if isinstance(value,str):
            for secret in secret_values:value=value.replace(secret,'[private]')
            import html
            value=clean(html.escape(value))
            for secret in secret_values:value=value.replace(secret,'[private]')
            return value
        return value
    compact_run=compact(result);compact_alerts=compact(alert_result);compact_scope=compact(projection)
    # One generation label detects an interrupted per-file overwrite, including
    # reports with identical context/completion. It is not a liveness attestation.
    from uuid import uuid4
    bundle_id=str(uuid4())
    for report in (compact_run,compact_alerts,compact_scope):
        report['reportGeneration']['bundleId']=bundle_id
    validate_result_ids(compact_run)
    validate_bundle(compact_run,compact_alerts,compact_scope)
    # Validate every serialization before touching an existing destination.
    serialized=[(name,json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False).encode()) for name,value in
                zip(names,(compact_run,compact_alerts,compact_scope))]
    out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.assessment-',dir=out.parent) as staging:
        staged=Path(staging)/'reports';staged.mkdir(mode=0o700)
        for name,data in serialized:atomic_bytes(staged/name,data)
        staged_reports=[json.loads((staged/name).read_bytes()) for name in names]
        validate_result_ids(staged_reports[0])
        validate_bundle(*staged_reports)
        destination_check()
        if out.exists():
            for name,data in serialized:os.replace(staged/name,out/name)
        else:
            # Destination is fresh; no existing reports are removed for publication.
            os.rename(staged,out)
        fd=os.open(out.parent if not overwrite else out,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    return compact_run


def remaining_actions(cases,events):
    """Allocation rollover after repairs/caps; ACK and unknown actions are not replayed."""
    consumed={e['actionId'] for e in events if e.get('state') in ('intent','acknowledged','unknown')}
    result=copy.deepcopy(cases)
    for case in result:case['actions']=[a for a in case.get('actions',[]) if a['id'] not in consumed]
    return result


def select_techniques(inventory,case_id,units,basis):
    """Refine a product question before allocating. Preserve prior obligations."""
    if not basis or not units:raise ValueError('product rationale and meaningful techniques required')
    result=copy.deepcopy(inventory);case=next(c for c in result['cases'] if c['caseId']==case_id)
    case['techniqueBasis']=basis
    case['requiredEvidence']=list(dict.fromkeys(case['requiredEvidence']+list(units)))
    return validate_inventory(result)


def compose_completion_summary(reconciliation=None, projection=None, alerts=None, *, task_completion=None, assessment_round=None):
    """One derived assignment/DAST summary; never modify attempt/finding history."""
    rec=reconciliation or {};projection=projection or {};alerts=alerts or {}
    inventory=rec.get('inventory') or {}
    unresolved=[r['caseId'] for r in rec.get('openResponsibilities',[])]
    unresolved += [r['criterionId'] for r in projection.get('openWork',[])]
    gaps=list(rec.get('inventoryGaps',[]))+list(rec.get('executionGaps',[]))+list(projection.get('inventoryGaps',[]))
    status=task_completion or ('complete' if rec.get('taskCompletion')=='complete' and projection.get('scopeCompletion','complete')=='complete' else 'partial')
    questions=[q for c in projection.get('criteria',[]) if c.get('disposition')!='user-excluded' and c.get('applicability',{}).get('status')!='not-applicable' for q in c.get('questions',[]) if q.get('disposition')!='user-excluded']
    questions=list({q['id']:q for q in questions}.values())
    scope=projection.get('securityScope',{})
    mapped=scope.get('workflowVersion')==1
    # Accounted parents are counted through their atoms, not as duplicate tests.
    questions=[q for q in questions if q.get('aggregateAccounting',{}).get('accountingStatus')!='accounted']
    dast=[q for q in questions if q.get('methodClass') in ('zap-dast','zap-ui','zap-business-observation')]
    unknown=[q['id'] for q in questions if q.get('methodClass') in (None,'unresolved')]
    dast_ids=[q['id'] for q in dast]
    mapping_gaps=[]
    if mapped:
        for criterion in projection.get('criteria',[]):
            if criterion.get('disposition')=='user-excluded' or criterion.get('applicability',{}).get('status')=='not-applicable':continue
            assigned=[q for q in criterion.get('questions',[]) if q.get('disposition')!='user-excluded']
            if not assigned:mapping_gaps.append('criterion-method-mapping-unresolved:'+criterion['id'])
            if any(q in dast for q in assigned) and (criterion.get('unresolved') or criterion.get('applicability',{}).get('status')=='unknown'):
                mapping_gaps.append('criterion-expectation-unresolved:'+criterion['id'])
    dast_gaps=[q['id'] for q in dast if q['coverage'] not in ('observed','user-excluded')]+unknown+mapping_gaps
    if inventory.get('track') in TRACKS:
        dast_ids += [c['caseId'] for c in inventory.get('cases',[]) if c.get('disposition') not in ('not-applicable','user-excluded')]
        dast_gaps += [c['caseId'] for c in rec.get('openResponsibilities',[])]+list(rec.get('inventoryGaps',[]))+list(rec.get('executionGaps',[]))
    elif questions and not mapped:
        dast_gaps.append('legacy-method-mapping-unreviewed')
    if dast_ids or unknown:
        if scope.get('complete') is not True and scope:dast_gaps.append('scope-mapping-completeness-unresolved')
        dast_status='partial' if dast_gaps else 'complete'
    else:dast_status='partial' if dast_gaps else 'not-assigned'
    finding_rows=alerts.get('alerts',[])
    uncertainty=[q['id'] for q in questions if q.get('securityAssessment')=='inconclusive']+[c['caseId'] for c in rec.get('openResponsibilities',[])]
    from .coverage_presentation import work_units
    discovery=rec.get('discoveryReview', {})
    track_summary=[]
    if inventory.get('track') in TRACKS:
        track_summary.append(dict(track=inventory['track'], status=rec.get('taskCompletion', 'partial'),
            reviewExtent='assigned-track' if discovery.get('extent', {}).get('kind')=='assigned-scope' and not inventory.get('phaseOnly') else 'delta',
            extentBasis=discovery.get('extent', {}).get('kind', 'declared-inventory'),
            sourceInventoryIds=[inventory.get('id', 'responsibilityInventory')],
            caseIds=[c['caseId'] for c in inventory.get('cases', [])]))
    summary = dict(assignment=dict(status=status,unresolvedIds=list(dict.fromkeys(unresolved)),gaps=gaps),
        dast=dict(status=dast_status,questionIds=list(dict.fromkeys(dast_ids)),gaps=list(dict.fromkeys(dast_gaps)),
            questionIdsMeaning='references-not-independent-test-count', workUnits=work_units(dast, rec)),
        discovery=dict(status=rec.get('discoveryReview',{}).get('reviewStatus','legacy-unreviewed'),
            scope=copy.deepcopy(rec.get('scope',{})), **{k:copy.deepcopy(discovery[k]) for k in
                ('extent','featureGroupsReviewed','mappedFeatureGroups','noAdditionalQuestionGroups') if k in discovery}),
        trackSummary=track_summary,
        securityOutcome=dict(findingIds=[f['findingId'] for f in finding_rows],uncertaintyQuestionIds=uncertainty,
            violatedQuestionIds=[q['id'] for q in questions if q.get('securityAssessment')=='violation-supported']+[c['caseId'] for c in rec.get('cases',[]) if c.get('outcome')=='violated']),
        remediation=dict(status='not-assigned'))
    if assessment_round:
        summary['round'] = dict(id=assessment_round['id'], status=assessment_round['status'],
            closureReason=assessment_round.get('closure', {}).get('reason'),
            unansweredObligationIds=assessment_round.get('closure', {}).get('review', projection.get('roundClosureReview', {})).get('unansweredObligationIds', []))
    return summary
