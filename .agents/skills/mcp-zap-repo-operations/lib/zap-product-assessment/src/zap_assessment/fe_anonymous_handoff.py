"""PM native findings + separately attributed browser observations; private raw retained."""
from collections import Counter
from pathlib import Path
import json
from urllib.parse import urlsplit
from .fe_anonymous_contract import load,save,digest,canonical
from .fe_anonymous_verify import verify
from .discovery_handoff import normalize

def handoff(lineage,output):
    root=Path(lineage['run']).resolve();p=load(root/'PLAN.json');readback=verify(root,lineage['planHash']);r=load(root/'RUN.json')
    out=Path(output).resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False);folder=out/'fe-anonymous';folder.mkdir(mode=0o700)
    raw=load(root/'alerts-native.json')['alerts'] if (root/'alerts-native.json').exists() else []
    msgs={str(m['id']):m for m in load(root/'messages.json')['messages']} if (root/'messages.json').exists() else {}
    joined=load(root/'TRAFFIC_CORRELATION.json')['exchanges'] if (root/'TRAFFIC_CORRELATION.json').exists() else []
    target_ids={mid for x in joined for mid in x['nativeMessageIds']}
    kept=[];excluded=[]
    for index,a in enumerate(raw):
        m=msgs.get(str(a.get('messageId')),{});header=m.get('responseHeader','').lower()
        if str(a.get('messageId')) not in target_ids or 'x-zpa-guard:' in header or not header.startswith('http/') or header.startswith('http/1.0 0'):
            excluded.append({'nativeAlertId':a.get('id'),'reason':'guard-or-unattributed response; not target finding'});continue
        kept.append(a)
    groups,other=normalize(kept,raw_ref=str(root/'alerts-native.json'),raw_sha=digest(root/'alerts-native.json') if raw else None)
    indices={str(a['id']):i for i,a in enumerate(raw)}
    for g in groups:
        g.update(track='fe-anonymous',trackResult=str(folder/'ALERTS.json'));refs=[]
        for i in g['instances']:
            index=indices[i['nativeAlertId']];i['actor']='anonymous request; terminal identity transition separately observed';i['evidenceRef']=str(root/'alerts-native.json')+'#/alerts/'+str(index)
            refs.append({'path':str(root/'alerts-native.json'),'sha256':digest(root/'alerts-native.json'),'jsonPointer':'/alerts/'+str(index),'access':'private-local'})
        g['evidenceRefs']=refs
    # Exact known fixture values supplement the existing normalizer. Raw stays private.
    values=load(root/'private/fixture-values.json') if (root/'private/fixture-values.json').exists() else {}
    sensitive={v for k,v in values.items() if isinstance(v,str) and len(v)>=8}
    for message in msgs.values():
        try:
            body=json.loads(message.get('responseBody',''))
            def tokens(value):
                if isinstance(value,dict):
                    for k,v in value.items():
                        if isinstance(v,str) and v and any(s in k.lower() for s in ('token','password','secret')):sensitive.add(v)
                        else:tokens(v)
                elif isinstance(value,list):
                    for v in value:tokens(v)
            tokens(body)
        except (ValueError,TypeError):pass
    def minimize(value):
        if isinstance(value,str):
            for secret in sorted(sensitive,key=len,reverse=True):value=value.replace(secret,'[private-fixture]')
            return value
        if isinstance(value,list):return [minimize(v) for v in value]
        if isinstance(value,dict):return {k:minimize(v) for k,v in value.items()}
        return value
    groups=minimize(groups)
    if lineage.get('triage'):
        ref=lineage['triage']
        if digest(ref['path'])!=ref['sha256']:raise ValueError('triage evidence drift')
        triage=load(ref['path'])
        for g in groups:
            matching=[t for t in triage['groups'] if t['nativeRuleId']==g['nativeRuleId'] and t['name']==g['name']]
            if len(matching)!=1:raise ValueError('triage must map every native group exactly once')
            g['agentAssessment']=minimize(matching[0]);g['agentAssessmentRef']=ref
    summary={'alertGroups':len(groups),'instances':sum(g['instanceCount'] for g in groups),'groupsBySeverity':dict(Counter(g['severity'] for g in groups))}
    payload={'schemaVersion':'pm-alerts/1.0','product':{'location':p['discovery']['productLocation'],'environment':p['selection']['environment']},'run':p['runId'],**r,
      'scope':{'track':'fe-anonymous','taskCompletion':r['taskCompletion'],'journeyIds':p['journeyIds'],'responsibilities':p['journeys']['responsibilities'],'otherTracksExecuted':False},'alerts':groups,'excludedGuardObservations':excluded+other,'summary':summary,
      'evidenceReadback':readback,'technicalFolder':str(folder),'limitations':['Native severity/confidence unchanged; zero alerts is not a safety verdict','UI assertions are browser evidence, not native ZAP alerts','Raw reports, profiles and credentials remain private local','Unresolved obligations keep task partial']}
    from .product_scope import task_readback,apply_completion
    payload=apply_completion(payload,readback['responsibilityReconciliation'])
    save(folder,'ALERTS.json',payload);save(out,'ALERTS.json',payload)
    save(folder,'EVIDENCE_INDEX.json',{'rawRoot':str(root),'index':{'path':str(root/'EVIDENCE_INDEX.json'),'sha256':digest(root/'EVIDENCE_INDEX.json')},'readback':readback})
    save(folder,'BROWSER_OBSERVATIONS.json',{'source':'browser-webdriver','nativeZAPAlerts':False,'checks':load(root/'CHECKS.json')})
    save(folder,'SCOPE.json',p['journeys']['responsibilities']);save(folder,'SELECTION.json',lineage)
    checks=load(root/'CHECKS.json')
    save(folder,'COVERAGE.json',{'taskCompletion':r['taskCompletion'],'responsibilities':p['journeys']['responsibilities'],'checks':checks,'operations':load(root/'OPERATIONS.json'),'rawRoot':str(root),'scopeNote':'Selected native scalar probes are bounded; guard responses are not application exercises. Protected routes are guest checks; direct fixture setup is separate.'})
    save(folder,'PINS.json',{'productSources':p['journeys']['sources'],'implementationPins':p['implementationPins'],'selection':p['selection'],'runtimePins':load(root/'RUNTIME_PINS.json') if (root/'RUNTIME_PINS.json').exists() else None})
    save(folder,'REPORT_INDEX.json',{'reports':[{'path':str(root/('reports/native.'+fmt)),'sha256':digest(root/('reports/native.'+fmt)),'readback':load(root/('reports/'+fmt+'-readback.json')),'access':'private-local'} for fmt in ('json','html') if (root/('reports/native.'+fmt)).exists()],'trafficCorrelation':str(root/'TRAFFIC_CORRELATION.json'),'responsePolicies':str(root/'RESPONSE_POLICY_OBSERVATIONS.json'),'selfContained':False})
    text='# FE anonymous technical review\n\nCanonical origin: '+p['selection']['origin']+'.\n\nExecution: '+r['executionStatus']+'; obligations: '+r['taskCompletion']+'. Read CHECKS, OPERATIONS, broker records and native messages before deriving coverage. UI validation is not an API request; transition ends anonymous phase. Guard denials are excluded. Native alerts retain original classifications; browser observations are separate.\n\nRaw evidence private: '+str(root)+'. No release approval or safety conclusion.\n'
    (folder/'TECHNICAL_REVIEW.md').write_text(text)
    (folder/'REPRODUCE.md').write_text('# Reproduce\n\nUse scripts/fe_anonymous_research.py discover then plan with current independently inspected selection/authority. Create a new run/profile/fixture; verify using its exact plan hash. Do not replay uncertain POST/start. Source/runtime/image pins are in private PLAN.json; raw reports JSON/HTML include EOF readback.\n')
    gaps=[o for o in p['journeys']['responsibilities'] if o['disposition']=='gap']
    (folder/'KNOWN_GAPS.md').write_text('# Known gaps\n\n'+json.dumps({'responsibilities':gaps,'failedOrUnrun':[c for c in load(root/'CHECKS.json') if c['outcome']!='pass'],'runtimeErrors':load(root/'ERRORS.json')},ensure_ascii=False,indent=2)+'\n')
    save(folder,'CLEANUP_RETENTION.json',load(root/'CLEANUP_RETENTION.json'))
    return payload
