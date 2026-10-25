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


def reconcile(inventory,observations,prerequisites,workload_cases=()):
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
    for c in cases:
        seen=checked.get(c['caseId'],{})
        mismatch=[k for k in ('actorRef','role','state','relation') if c.get(k) not in (None,'product-defined') and seen.get(k)!=c[k]]
        if mismatch:seen['evidenceUnits']=[];seen['missingContext']=mismatch
    result=reconcile_responsibilities(cases,checked,prerequisites)
    missing=[]
    if inventory.get('complete') is not True or not cases:missing.append('product inventory completeness unresolved')
    if extra:missing.append('new workload responsibilities must be added to product inventory')
    outside=set(observations)-{c['caseId'] for c in cases}
    if outside:missing.append('observations outside product inventory')
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
    return result


def continue_work(inventory,observations,prerequisites,handlers,*,persist,attempts=(),max_actions=32,stop=False):
    """Execute eligible actions, including preparation, then reconcile their readback.

    handlers map reviewed action IDs to existing executor/fixture/repair adapters.
    Each callback returns actual observations/prerequisites, never an exit code as
    coverage. Caller owns target/actor admission; durable intent is written BEFORE
    dispatch. Reusing an action ID from an ACK/unknown intent is forbidden. A new
    allocation after repair must omit acknowledged mutations and unknown starts.
    No arbitrary shell command or import from a workload is executed here.
    """
    seen={r['actionId'] for r in attempts};obs=copy.deepcopy(observations);pre=copy.deepcopy(prerequisites);events=[]
    for row in {r['actionId']:r for r in attempts}.values():
        if row['state'] in ('intent','unknown') and row.get('effect') in ('mutation','start') and row['actionId'] not in obs.get(row['caseId'],{}).get('resolvedActionIds',[]):
            obs[row['caseId']]={**obs.get(row['caseId'],{}),'outcomeUnknown':True}
    def record(row):
        persist(copy.deepcopy(row));events.append(copy.deepcopy(row))
    for _ in range(max_actions):
        current=reconcile(inventory,obs,pre)
        if stop or current['taskCompletion']=='complete':break
        candidates=[]
        for c in inventory['cases']:
            state=next(r for r in current['cases'] if r['caseId']==c['caseId'])
            if state['status'] not in ('eligible','blocked'):continue
            for a in c.get('actions',[]):
                if a['id'] in seen:continue
                if state['status']=='blocked' and a['kind']=='execute':continue
                if obs.get(c['caseId'],{}).get('outcomeUnknown') and a['kind']!='reconcile-state':continue
                if any(pre.get(k) is not True for k in a.get('requires',[])):continue
                # A failed/unknown mutation blocks only actions declaring that dependency.
                if any(obs.get(k,{}).get('outcomeUnknown') for k in a.get('dependsOnCases',[])):continue
                candidates.append((c,a))
        chosen=next(((c,a) for c,a in candidates if a['id'] in handlers),None)
        if chosen is None:break
        c,a=chosen;seen.add(a['id']);base={'actionId':a['id'],'caseId':c['caseId'],'kind':a['kind'],'effect':a.get('effect','read')}
        record({**base,'state':'intent','replay':False})
        try:
            value=handlers[a['id']](copy.deepcopy(a))
            if not isinstance(value,dict):raise ValueError('action must return readback')
            updates=value.get('observations',{})
            if set(updates)-{r['caseId'] for r in inventory['cases']}:raise ValueError('action observation outside inventory')
            for cid,row in updates.items():
                old=obs.get(cid,{})
                same_context=all(old.get(k)==row.get(k) for k in ('actorRef','role','state','relation'))
                resolved=old.get('resolvedActionIds',[])
                if row.get('stateReconciled'):
                    resolved=list(dict.fromkeys(resolved+[e['actionId'] for e in list(attempts)+events if e['caseId']==cid and e['state'] in ('intent','unknown')]))
                if old.get('outcomeUnknown') and not row.get('stateReconciled'):raise ValueError('unknown outcome requires state readback')
                obs[cid]={**copy.deepcopy(old),**copy.deepcopy(row),
                    'evidenceUnits':sorted((set(old.get('evidenceUnits',[])) if same_context else set())|set(row.get('evidenceUnits',[]))),
                    'resolvedActionIds':resolved,
                    'outcome':'violated' if 'violated' in (old.get('outcome'),row.get('outcome')) else row.get('outcome'),
                    'outcomeUnknown':False if row.get('stateReconciled') else old.get('outcomeUnknown',False)}
            pre.update(value.get('prerequisites',{}))
            record({**base,'state':'acknowledged','resultRead':True})
        except Exception as e:
            if a.get('effect') in ('mutation','start'):
                obs[c['caseId']]={**obs.get(c['caseId'],{}),'outcomeUnknown':True}
            record({**base,'state':'unknown' if a.get('effect') in ('mutation','start') else 'failed',
                    'errorType':type(e).__name__,'replay':False})
    result=reconcile(inventory,obs,pre)
    result.update(observations=obs,prerequisites=pre,actionsPerformed=events,actionHistory=list(attempts)+events,
                  continuationStoppedByUser=stop,wholeTrackComplete=False if inventory.get('phaseOnly') else result['handoffClosesTask'])
    return result


def apply_completion(run,reconciliation):
    """Presentation cannot discard open duties or promote executor exit/terminal."""
    result=copy.deepcopy(run)
    result['taskCompletion']='complete' if reconciliation['taskCompletion']=='complete' and not any(reconciliation.get(k) for k in ('openResponsibilities','inventoryGaps','executionGaps')) else 'partial'
    result['responsibilityReconciliation']=copy.deepcopy(reconciliation)
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
                check(item)
        elif isinstance(value,list):
            for item in value:check(item)
    check(result)


def compact_results(output,run,alerts,reconciliation,*,secrets=(),overwrite=False):
    """Two derived files; existing alert attribution/counts survive presentation."""
    from pathlib import Path
    from .discovery_handoff import clean
    out=Path(output)
    if out.is_symlink():raise ValueError('report destination symlink')
    out.mkdir(mode=0o700,parents=True,exist_ok=overwrite)
    if overwrite and any(p.name not in ('RUN.json','ALERTS.json') or p.is_symlink() for p in out.iterdir()):
        raise ValueError('overwrite only a two-file assessment destination')
    result=apply_completion(run,reconciliation)
    import base64
    from urllib.parse import quote,quote_plus
    secret_values=set()
    for secret in secrets:
        if isinstance(secret,str) and secret:
            secret_values.update((secret,quote(secret,safe=''),quote_plus(secret),base64.b64encode(secret.encode()).decode()))
    secret_values=sorted(secret_values,key=len,reverse=True)
    # Raw assurance/package fields belong to working artifacts, not the PM report.
    def compact(value):
        if isinstance(value,dict):return {k:('[private]' if k.lower().replace('-','').replace('_','') in ('password','passwordvalue','token','accesstoken','refreshtoken','setuptoken','authorization','cookie','setcookie','secret','apikey') else compact(v)) for k,v in value.items() if k not in
            ('evidenceRef','evidenceRefs','evidenceStatus','implementationPins','evidenceReadback','technicalFolder','requestHeader','responseHeader','requestBody','responseBody')}
        if isinstance(value,list):return [compact(v) for v in value]
        if isinstance(value,str):
            for secret in secret_values:value=value.replace(secret,'[private]')
            value=clean(value)
            for secret in secret_values:value=value.replace(secret,'[private]')
            return value
        return value
    alert_result=copy.deepcopy(alerts)
    if isinstance(alert_result,dict):
        alert_result['taskCompletion']=result['taskCompletion']
        if isinstance(alert_result.get('scope'),dict):alert_result['scope']['taskCompletion']=result['taskCompletion']
    compact_run=compact(result);compact_alerts=compact(alert_result)
    validate_result_ids(compact_run)
    # Prepare both serializations before replacing either existing result.
    import json
    from .safety_io import atomic_bytes
    serialized=[(name,json.dumps(value,ensure_ascii=False,indent=2).encode()) for name,value in
                [('RUN.json',compact_run),('ALERTS.json',compact_alerts)]]
    if overwrite:
        import os,tempfile
        with tempfile.TemporaryDirectory(prefix='.assessment-',dir=out.parent) as staging:
            for name,data in serialized:atomic_bytes(Path(staging)/name,data)
            for name,data in serialized:os.replace(Path(staging)/name,out/name)
            fd=os.open(out,os.O_RDONLY)
            try:os.fsync(fd)
            finally:os.close(fd)
    else:
        for name,data in serialized:atomic_bytes(out/name,data)
    return result


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
