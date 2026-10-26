"""Offline FE integrity and semantics verifier. Integrity success is never scan completion."""
import hashlib,json,stat
from pathlib import Path
from urllib.parse import urlsplit
from .fe_anonymous_contract import canonical,digest,load,schema
from .journal import Journal
from .evidence import read_report

def verify(root,expected_plan_hash):
    root=Path(root).resolve()
    if root.stat().st_mode & 0o077:raise ValueError('raw root is not private')
    manifest=load(root/'EVIDENCE_INDEX.json')
    if digest(root/'EVIDENCE_INDEX.json')!=(root/'EVIDENCE_INDEX.sha256').read_text().strip():raise ValueError('index digest mismatch')
    plan=load(root/'PLAN.json');schema(plan,'fe-anonymous-plan-v1.schema.json')
    if canonical(plan)!=expected_plan_hash or manifest['planHash']!=expected_plan_hash:raise ValueError('external plan hash mismatch')
    seen=set()
    for row in manifest['artifacts']:
        relative=Path(row['path']);p=root/relative
        if relative.is_absolute() or '..' in relative.parts or row['path'] in seen or p.is_symlink() or not p.resolve().is_relative_to(root):raise ValueError('artifact path/duplicate')
        seen.add(row['path'])
        if p.stat().st_mode & 0o077 or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:raise ValueError('artifact integrity/privacy mismatch '+row['path'])
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file()}-{'EVIDENCE_INDEX.json','EVIDENCE_INDEX.sha256'}
    if actual!=seen:raise ValueError('unindexed/missing artifact')
    if canonical(plan['journeys'])!=plan['journeysSha256'] or canonical(plan['discovery'])!=plan['discoverySha256']:raise ValueError('inventory hash drift')
    Journal(root/'journal.jsonl',plan['runId'],expected_plan_hash)
    run=load(root/'RUN.json')
    if run!=manifest['result']:raise ValueError('run/index status mismatch')
    checks=load(root/'CHECKS.json');ids=[r['journeyId'] for r in checks]
    if len(ids)!=len(set(ids)) or not set(ids)<=set(plan['journeyIds']):raise ValueError('duplicate/unplanned UI check')
    journeys={j['id']:j for j in plan['journeys']['journeys']};records=[load(p) for p in sorted((root/'broker').glob('[0-9]*.json'))]
    events_path=root/'broker/request-events.jsonl'
    if events_path.exists():
        latest={}
        for line in events_path.read_text().splitlines():
            event=json.loads(line);latest[event['sequence']]=event
        if latest!={r['sequence']:r for r in records}:raise ValueError('durable request lifecycle/final record drift')
    if manifest.get('schemaVersion')=='fe-anonymous-evidence/2.0' and records and not events_path.exists():raise ValueError('durable request events absent')
    for c in checks:
        if c['outcome']=='not-run':continue
        j=journeys[c['journeyId']];o=load(root/c['uiRef'])
        valid=o['journeyId']==c['journeyId'] and o['profileFresh'] is True and o.get('profileClosed') is True
        if o.get('browser',{}).get('acceptInsecureCerts') is not False:valid=False
        if c['outcome']=='pass':
            if not valid or o['outcome']!='observed' or [a['predicate'] for a in o['assertions']]!=j['expected'] or not all(a['passed'] is True for a in o['assertions']):raise ValueError('forged/incomplete UI assertion')
            state=o['initialState']
            allowed={name for r in plan['requestPolicies'] for name in r.get('anonymousCookies',[]) if r.get('cookieProvenance')}
            if state['storageKeys'] or state['sessionKeys'] or set(state['cookieNames'])-allowed or state['serviceWorkerControlled']:raise ValueError('stale identity/profile')
            extended=state['extendedState']
            if extended.get('captureError') or extended.get('cacheNames') or extended.get('serviceWorkerRegistrations') or extended.get('indexedDBNames') or extended.get('indexedDBNames') is None:raise ValueError('initial extended state absent/stale')
            if len(o['steps'])!=len(j['steps']) or not o['finalState']['secure']:raise ValueError('UI action/secure context incomplete')
            if [s['action'] for s in o['steps']]!=[s['action'] for s in j['steps']]:raise ValueError('UI action mismatch')
            if bool(o['finalState']['storageKeys'] or o['finalState']['sessionKeys']) and not j.get('transition'):raise ValueError('identity phase misattribution')
            if not o.get('screenshot'):raise ValueError('UI screenshot absent')
            screenshot=root/'browser'/c['journeyId']/'screen.png'
            if digest(screenshot)!=o['screenshot']['sha256'] or screenshot.stat().st_size!=o['screenshot']['bytes']:raise ValueError('UI screenshot hash mismatch')
            if load(root/'browser'/c['journeyId']/'RESULT.json')!=o:raise ValueError('worker/controller UI evidence differs')
            from .fe_anonymous_analysis import evaluate_predicate
            if not all(evaluate_predicate(o['finalState'],p) for p in j['expected']):raise ValueError('captured DOM contradicts UI assertion')
        relevant=[r for r in records if r.get('caseId')==c['journeyId']]
        if [n['expected'] for n in c['network']]!=j['network']:raise ValueError('missing/extra network assertion')
        for network in c['network']:
            expected=network['expected']
            if expected not in j['network']:raise ValueError('unplanned network claim')
            attempted=[r for r in relevant if r['method']==expected['method'] and urlsplit(r['url']).path==expected['path']]
            rows=[r for r in attempted if r.get('forwarded')]
            passed=not attempted if expected.get('absent') else bool(rows) and all(r['status'] in expected['statuses'] for r in rows)
            if network['passed']!=passed or network['sequences']!=[r['sequence'] for r in rows]:raise ValueError('UI/API origin claim mismatch')
            if c['outcome']=='pass' and not passed:raise ValueError('failed network claimed pass')
        if 'unknown' in c:
            from .fe_anonymous_analysis import transport_accounting
            if any(c.get(k)!=v for k,v in transport_accounting(relevant).items()):raise ValueError('transport accounting drift')
        if c['forwarded']!=sum(bool(r.get('forwarded')) for r in relevant):raise ValueError('forwarded accounting mismatch')
    complete=run['evidenceStatus']=='complete'
    if complete:
        fresh=load(root/'FRESH_SESSION.json')
        if fresh['sites']!={'sites':[]} or int(fresh['messages']['numberOfMessages'])!=0 or fresh['active']!={'scans':[]}:raise ValueError('native session freshness absent')
        messages=load(root/'messages.json');alerts=load(root/'alerts-native.json')
        if messages['count']!=len(messages['messages']) or len({m['id'] for m in messages['messages']})!=messages['count']:raise ValueError('history duplication/loss')
        if alerts['count']!=len(alerts['alerts']):raise ValueError('alert count drift')
        from .fe_anonymous_analysis import correlate,response_policies
        if load(root/'TRAFFIC_CORRELATION.json')!=correlate(plan,records,messages['messages']):raise ValueError('native/browser traffic join drift')
        if load(root/'RESPONSE_POLICY_OBSERVATIONS.json')!=response_policies(messages['messages']):raise ValueError('response policy observation drift')
        native_ids={str(m['id']) for m in messages['messages']}
        if any(str(a.get('messageId')) not in native_ids for a in alerts['alerts']):raise ValueError('alert history reference absent')
        for fmt in ('json','html'):
            rb=load(root/('reports/'+fmt+'-readback.json'));blob=(root/('reports/native.'+fmt)).read_bytes()
            if rb['endOfFile'] is not True or rb['bytes']!=len(blob) or rb['sha256']!=hashlib.sha256(blob).hexdigest():raise ValueError('report EOF/length/hash')
            path=rb['pages'][0]['reportPath'];pages=[]
            for f in sorted((root/'tools').glob('*zap_report_read_chunk-request.json')):
                q=load(f)
                if q['arguments']['reportPath']!=path:continue
                r=load(f.with_name(f.name.replace('-request.json','-response.json')))
                text='\n'.join(c['text'] for c in r['content'] if c.get('type')=='text')
                if text.startswith('"'):text=json.loads(text)
                pages.append(json.loads(text))
            it=iter(pages)
            if read_report(lambda *a:next(it),path,32*1024**2)!=blob or next(it,None) is not None:raise ValueError('chunk reconstruction drift')
        # Any forwarded broker response must be actual verified target, never a synthetic guard denial.
        for r in records:
            if r.get('forwarded') and (r.get('reason')!='app' or r.get('upstreamCertificateSha256')!=plan['selection']['certificate']['derSha256'] or r.get('upstreamSNI')!=urlsplit(plan['selection']['origin']).hostname):raise ValueError('response origin/TLS mismatch')
    if manifest.get('schemaVersion')=='fe-anonymous-evidence/2.0':
        from .fe_anonymous_contract import admission
        branches=admission(plan)
        if load(root/'ADMISSION.json')!=branches:raise ValueError('branch admission metadata drift')
        denied={b['id'] for b in branches if b['kind']=='journey' and not b['admitted']}
        if any(c['journeyId'] in denied and c['outcome']!='not-run' for c in checks):raise ValueError('unpermitted journey executed')
    semantics=None
    if complete:
        from .fe_anonymous_semantics import check
        semantics=check(root,plan,records,messages['messages'],load(root/'OPERATIONS.json'),require_all=(run.get('workloadCompletion') or run.get('taskCompletion'))=='complete')
    if (run.get('workloadCompletion') or run.get('taskCompletion'))=='complete':
        if semantics and semantics['unknownMutations']:raise ValueError('unknown mutation reconciliation/retention unresolved')
        if not complete or run['executionStatus']!='completed' or run['cleanupStatus']!='clean' or not run.get('targetBindingUnchanged'):raise ValueError('completion prerequisite absent')
        if set(ids)!={j['id'] for j in plan['journeys']['journeys']} or not ids or any(c['outcome']!='pass' for c in checks) or any(o['disposition']=='gap' for o in plan['journeys']['responsibilities']):raise ValueError('obligations incomplete')
        ops=load(root/'OPERATIONS.json')
        if any(o['kind']=='crawl' for o in ops):
            caps=load(root/'CLIENT_BROWSER_CAPABILITIES.json')
            if not caps or any(r.get('status')!=200 or r.get('effectiveAcceptInsecureCerts') is not False for r in caps):raise ValueError('native crawler TLS capability absent')
        if not all(o.get('deliveryProven',True) and o.get('terminal') is True for o in ops) or {o.get('campaignId') for o in ops if o['kind']=='active'}!={c['id'] for c in plan['journeys']['campaigns']}:raise ValueError('native active incomplete')
    from .product_scope import task_readback
    from .product_scope import fe_readback
    ui=[{'id':c['journeyId'],'completed':c['outcome'] in ('pass','assertion-mismatch')} for c in checks]
    delivery=[{'campaignId':key,'delivered':value.get('deliveryProven')} for key,value in (semantics or {}).get('delivery',{}).items()]
    ops=load(root/'OPERATIONS.json') if (root/'OPERATIONS.json').exists() else []
    # Semantic reader already independently validated native terminal and delivery.
    converted=[{**o,'finalStatus':'Completed: yes' if o.get('terminal') else ''} for o in ops]
    scope=fe_readback(plan,{'journeys':ui,'delivery':delivery,'missing':[]},converted)
    return {'responsibilityReconciliation':scope,'taskCompletion':scope['taskCompletion'],'workloadCompletion':run.get('workloadCompletion',run.get('taskCompletion')),'semanticsVersion':'independent/2.0','historicalEvidenceVersion':manifest.get('schemaVersion','unversioned'),'semanticDerivation':semantics,'integrityVerified':True,'artifactCount':len(seen),'evidenceComplete':complete,'result':run,'meaning':'artifact consistency only; unresolved obligations remain partial; no approval'}
