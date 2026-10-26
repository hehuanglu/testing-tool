"""Offline integrity and semantic readback; returns partial honestly for interrupted runs."""
import json
from pathlib import Path
from .fe_authenticated_contract import load,digest,canonical
from .fe_authenticated_semantics import derive
from .transport import field

def verify(root,expected_plan_hash):
    root=Path(root).resolve();index=load(root/'EVIDENCE_INDEX.json')
    if digest(root/'EVIDENCE_INDEX.json')!=(root/'EVIDENCE_INDEX.sha256').read_text().strip():raise ValueError('evidence seal mismatch')
    p=load(root/'PLAN.json')
    if canonical(p)!=expected_plan_hash or index['planHash']!=expected_plan_hash:raise ValueError('plan mismatch')
    seen=set()
    for row in index['artifacts']:
        path=root/row['path']
        if not path.resolve().is_relative_to(root) or path.is_symlink() or row['path'] in seen:raise ValueError('unsafe/duplicate artifact')
        seen.add(row['path'])
        if path.stat().st_size!=row['bytes'] or digest(path)!=row['sha256']:raise ValueError('artifact drift '+row['path'])
    records=[load(f) for f in sorted((root/'broker').glob('[0-9]*.json'))];messages=load(root/'messages.json');run=load(root/'RUN.json')
    if len(messages['messages'])!=messages['count'] or len({str(m['id']) for m in messages['messages']})!=messages['count']:raise ValueError('history count/duplicate')
    result=derive(root,p,records,messages['messages']);errors=result['errors']
    if p.get('implementationPins') and (not (root/'IMPLEMENTATION_PINS_END.json').exists() or load(root/'IMPLEMENTATION_PINS_END.json')!=p['implementationPins']):errors.append('implementation drift during run')
    if p['campaigns'] and load(root/'OPERATIONS.json') and not (root/'MATERIALIZED_CAMPAIGNS.json').exists():errors.append('materialized native campaign evidence absent')
    if p['journeys']['recipe']=='finalsource-fe-auth/1.0' and run['executionStatus']=='completed':
        from .fe_authenticated_evidence_finalsource import cleanup_readback
        try:result['fixtureCleanup']=cleanup_readback(root,result['ownedIds'])
        except (ValueError,KeyError,FileNotFoundError) as e:result['missing'].append('fixture cleanup/retention proof: '+str(e))
    if (root/'UNKNOWN_STARTS.json').exists():
        reconciliation=root/'UNKNOWN_START_RECONCILIATION.json'
        if not reconciliation.exists() or not load(reconciliation)['statuses'] or any(str(s['status'])!='100' for s in load(reconciliation)['statuses'].values()):result['missing'].append('unknown native start requires independent terminal inventory reconciliation')
    counter_path=root/'COUNTERS.json'
    if counter_path.exists():
        expected={'brokerRequests':len(records),'policyRequests':sum(r.get('method')!='CONNECT' for r in records),'appArrivals':sum(r.get('forwarded') is True for r in records),'unknownRequests':sum(r.get('transportState') in ('sent','response-headers','unknown') for r in records),'campaignAppArrivals':{c['id']:sum(r.get('campaignId')==c['id'] and r.get('forwarded') is True and r.get('method')==c['method'] for r in records) for c in p['campaigns']}}
        if expected['policyRequests']>p['limits']['maxRequests']:errors.append('global policy request cap exceeded')
        if load(counter_path)!=expected:errors.append('broker/app/campaign counter contradiction')
    else:result['missing'].append('final independently comparable counters absent')
    events=[json.loads(line) for line in (root/'broker/request-events.jsonl').read_text().splitlines()]
    latest={}
    for event in events:latest[event['sequence']]=event
    if len(records)!=len(latest) or any(latest.get(row['sequence'])!=row for row in records):errors.append('durable broker lifecycle/final-row contradiction')
    for op in load(root/'OPERATIONS.json'):
        if not op.get('operationId') or field(op.get('finalStatus',''),'Completed')!='yes' or field(op.get('finalStatus',''),'Progress')!='100%':result['missing'].append('native terminal/stop '+str(op.get('campaignId')))
    for group in p['journeys']['sessionGroups']:
        path=root/'browser'/group['id']/'GROUP.json'
        if not path.exists():result['missing'].append('session group terminal '+group['id']);continue
        g=load(path)
        if g.get('browser',{}).get('acceptInsecureCerts') is not False:errors.append('browser TLS trust bypass')
        driver=root/'browser/bin/geckodriver'
        if not driver.exists() or digest(driver)!=g.get('driverSha256'):errors.append('browser driver binary pin mismatch')
        disposal=root/'browser'/group['id']/'PROFILE_DISPOSAL.json'
        if not disposal.exists() or (root/'browser'/group['id']/'profile').exists():result['missing'].append('owned profile disposal proof '+group['id'])
        first=next(j for j in p['journeys']['journeys'] if j['sessionGroup']==group['id'])
        first_path=root/'browser'/group['id']/(first['id']+'.json')
        if first_path.exists():
            steps=load(first_path).get('steps',[])
            if steps and any(steps[0]['state'].get(key) for key in ('storageKeys','sessionKeys','cookieNames','serviceWorkerControlled')):errors.append('fresh browser profile contains prior identity')
        if not g.get('profileClosed') or not g.get('profileDisposed'):result['missing'].append('profile disposal '+group['id'])
    passive=load(root/'PASSIVE.json')
    if len(passive)<2 or any(field(x['raw'],'Completed')!='yes' or field(x['raw'],'Records remaining')!='0' for x in passive[-2:]):errors.append('passive settle missing')
    for fmt in ('json','html'):
        doc=load(root/('reports/'+fmt+'-readback.json'));path=root/('reports/native.'+fmt)
        if digest(path)!=doc['sha256'] or path.stat().st_size!=doc['bytes']:errors.append('report hash/size')
        pages=doc['pages'];cursor=0
        for page in pages:
            if page['offset']!=cursor:errors.append('report page offset gap')
            cursor=page['nextOffset']
        if not pages or pages[-1].get('endOfFile') is not True:errors.append('report EOF absent')
        if fmt=='json':json.loads(path.read_bytes())
        elif b'</html>' not in path.read_bytes().lower():errors.append('HTML EOF absent')
    for sample in load(root/'RESOURCES.json')['samples']:
        if min(sample['hostFree'],sample.get('dockerFree',sample['hostFree']))<p['limits']['reserveBytes']:errors.append('resource reserve breach')
    if run['cleanupStatus']!='clean':result['missing'].append('scanner cleanup unconfirmed')
    result.update(integrityStatus='pass',rawStatuses={k:run[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},reviewerApproval=None)
    result['workloadCompletion']='complete' if not errors and not result['missing'] and run['executionStatus']=='completed' else 'partial'
    from .product_scope import fe_readback
    result['responsibilityReconciliation']=fe_readback(p,result,load(root/'OPERATIONS.json'))
    result['taskCompletion']=result['responsibilityReconciliation']['taskCompletion']
    if errors or result['missing']:
        result['taskCompletion']='partial'
        result['responsibilityReconciliation'].update(taskCompletion='partial',handoffClosesTask=False,executionGaps=errors+result['missing'])
    if errors:raise ValueError('semantic rejection: '+'; '.join(dict.fromkeys(errors))[:2000])
    return result
