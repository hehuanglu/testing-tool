"""Selected-run pm-alerts/1.0 synthesis with native classification and private raw references."""
from collections import Counter
from pathlib import Path
import json
from .fe_authenticated_contract import load,save,digest,canonical
from .fe_authenticated_verify import verify
from .fe_authenticated_auth import pointer
from .fe_authenticated_semantics import request,sha
from .discovery_handoff import normalize

def apply_triage(groups,triage):
    """Attach reviewed assessments without changing native severity or inventing evidence."""
    lookup={g['findingId']:g for g in groups};seen=set()
    required={'findingId','nativeRuleId','nativeAlertIds','verificationStatus','rationale','impact','remediation','reproduction','evidenceRefs'}
    for row in triage:
        if set(row)!=required or row['findingId'] in seen or row['findingId'] not in lookup:raise ValueError('unknown/duplicate or incomplete triage')
        g=lookup[row['findingId']];seen.add(row['findingId'])
        if str(row['nativeRuleId'])!=g['nativeRuleId'] or sorted(row['nativeAlertIds'])!=sorted(x['nativeAlertId'] for x in g['instances']):raise ValueError('triage native attribution mismatch')
        if row['verificationStatus'] not in ('observed','configuration-only','unconfirmed') or any(not isinstance(row[k],str) or not row[k].strip() for k in ('rationale','impact','remediation','reproduction')):raise ValueError('triage assessment absent')
        if not row['evidenceRefs']:raise ValueError('triage evidence absent')
        for proof in row['evidenceRefs']:
            if set(proof)-{'path','sha256','jsonPointer','access'} or not Path(proof['path']).is_file() or digest(proof['path'])!=proof['sha256']:raise ValueError('triage evidence drift')
        g['testerAssessment']={k:row[k] for k in ('verificationStatus','rationale','impact','remediation','reproduction','evidenceRefs')}
    return seen

def handoff(lineage,output):
    if set(lineage)-{'run','planHash','repeatabilityRefs','interruptionRef','triage'}:raise ValueError('unreviewed lineage fields')
    root=Path(lineage['run']).resolve();p=load(root/'PLAN.json');check=verify(root,lineage['planHash']);run=load(root/'RUN.json');raw=load(root/'alerts-native.json')['alerts'];messages=load(root/'messages.json')['messages'];origin=p['selection']['origin']
    records=[load(f) for f in (root/'broker').glob('[0-9]*.json')];parsed={str(m['id']):request(m,origin) for m in messages};kept=[];excluded=[]
    for a in raw:
        m=parsed.get(str(a.get('messageId')))
        if not m or not any(r.get('forwarded') and r['method']==m['method'] and r['url']==m['url'] and r.get('responseBodySha256')==sha(m['response'].encode()) for r in records):excluded.append({'nativeAlertId':str(a.get('id')),'reason':'guard or unattributed response'});continue
        kept.append(a)
    groups,other=normalize(kept,raw_ref=str(root/'alerts-native.json'),raw_sha=digest(root/'alerts-native.json'));indices={str(a['id']):i for i,a in enumerate(raw)};secrets=set()
    auth=p['journeys']['auth']
    for m in parsed.values():
        if not m:continue
        if m['headers'].get('authorization'):secrets.add(m['headers']['authorization']);secrets.add(m['headers']['authorization'].removeprefix('Bearer '))
        try:
            body=json.loads(m['body'])
            for k in (auth['usernameField'],auth['passwordField']):
                if isinstance(body.get(k),str):secrets.add(body[k])
        except (ValueError,TypeError,AttributeError):pass
        try:
            token=pointer(json.loads(m['response']),auth['tokenPointer'])
            if isinstance(token,str):secrets.add(token)
        except (ValueError,TypeError,KeyError,IndexError):pass
    def minimize(value):
        if isinstance(value,str):
            for s in sorted(secrets,key=len,reverse=True):
                if len(s)>=4:value=value.replace(s,'[private]')
            return value
        if isinstance(value,list):return [minimize(x) for x in value]
        if isinstance(value,dict):return {k:minimize(v) for k,v in value.items()}
        return value
    out=Path(output).resolve();out.mkdir(parents=True,mode=0o700,exist_ok=False);folder=out/'fe-authenticated';folder.mkdir(mode=0o700)
    for g in groups:
        g.update(track='fe-authenticated',trackResult=str(folder/'ALERTS.json'));refs=[]
        for instance in g['instances']:
            idx=indices[instance['nativeAlertId']];instance['evidenceRef']=str(root/'alerts-native.json')+'#/alerts/'+str(idx);refs.append({'path':str(root/'alerts-native.json'),'sha256':digest(root/'alerts-native.json'),'jsonPointer':'/alerts/'+str(idx),'access':'private-local'})
        g['evidenceRefs']=refs
    apply_triage(groups,lineage.get('triage',[]))
    groups=minimize(groups);summary={'alertGroups':len(groups),'instances':sum(g['instanceCount'] for g in groups),'groupsBySeverity':dict(Counter(g['severity'] for g in groups))}
    payload={'schemaVersion':'pm-alerts/1.0','product':{'location':p['discovery']['productLocation'],'environment':p['selection']['environment']},'run':p['runId'],**{k:run[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},'taskCompletion':check['taskCompletion'],'scope':{'track':'fe-authenticated','recipe':p['journeys']['recipe'],'responsibilities':p['journeys']['responsibilities'],'otherTracksExecuted':False},'alerts':groups,'browserObservations':minimize(check.get('browserObservations',[])),'excludedGuardObservations':excluded+other,'summary':summary,'technicalFolder':str(folder),'reviewerApproval':None,'limitations':['Native severity/confidence retained; impact requires triage.','Browser findings have separate attribution; setup is not FE/native coverage.','Raw credentials/PII/screenshots remain local private; linked raw is not a portable public bundle.','A/B/interruption are separate lineage evidence; only selected run contributes alerts.']}
    from .product_scope import apply_completion
    payload=apply_completion(payload,check['responsibilityReconciliation'])
    save(out,'ALERTS.json',payload);save(folder,'ALERTS.json',payload)
    for name,value in [('BROWSER_OBSERVATIONS.json',minimize(check.get('browserObservations',[]))),('FIXTURE_CLEANUP.json',load(root/'FIXTURE_CLEANUP.json') if (root/'FIXTURE_CLEANUP.json').exists() else {'status':'retain','reason':'interrupted/control run'}),('LINEAGE.json',lineage),('COVERAGE.json',minimize(check)),('SCOPE.json',p['journeys']['responsibilities']),('CLEANUP_RETENTION.json',load(root/'CLEANUP_RETENTION.json')),('EVIDENCE_REFS.json',{'rawRoot':str(root),'index':{'path':str(root/'EVIDENCE_INDEX.json'),'sha256':digest(root/'EVIDENCE_INDEX.json')},'reports':[{'path':str(root/('reports/native.'+f)),'sha256':digest(root/('reports/native.'+f)),'access':'private-local'} for f in ('json','html')]}),('PINS.json',{'source':p['journeys']['sources'],'implementation':p.get('implementationPins'),'runtime':load(root/'RUNTIME_PINS.json')})]:save(folder,name,value)
    (folder/'TECHNICAL_REVIEW.md').write_text('# FE authenticated\n\nRead COVERAGE.json and SCOPE.json before interpreting alerts. Browser and native identity are independently verified by protected response against owned actor provenance. Each UI operation requires captured actions, DOM, screenshots, matching network and post-state. Native coverage requires changed payload delivered with the admitted principal over verified app TLS.\n\nRaw evidence is local private: '+str(root)+'. Native findings are not automatic exploit confirmation. Reviewer approval remains null.\n')
    (folder/'REPRODUCE.md').write_text('# Reproduce\n\nUse the pinned recipe and fresh deployment binding, authority and owned actor fixtures. Run product_assessment.py fe-authenticated discover, plan, run, verify and handoff. Keep credentials in a private actor file. Use fresh profiles and IDs; never replay unknown mutation/start. Read native full reports and identity/delivery/post-state evidence.\n')
    (folder/'KNOWN_GAPS.md').write_text('# Remaining evidence\n\n'+json.dumps({'taskCompletion':check['taskCompletion'],'missing':check['missing'],'runtimeErrors':load(root/'ERRORS.json')},ensure_ascii=False,indent=2)+'\n')
    return {'summary':summary,'taskCompletion':check['taskCompletion'],'alerts':str(out/'ALERTS.json')}
