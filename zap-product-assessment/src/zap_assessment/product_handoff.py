"""Existing pm-alerts/1.0 handoff, native/direct attribution kept separate."""
import json
from pathlib import Path
from .research import digest,verify_manifest
from .bola_research import save
from .discovery_handoff import normalize

def native_handoff(p,out):
    out=Path(out);run=json.loads((out/'RUN.json').read_text());verify=verify_manifest(out)
    alerts=json.loads((out/'ALERTS.json').read_text())['alerts'];groups,excluded=normalize(alerts,raw_ref=str(out/'ALERTS.json'),raw_sha=digest(out/'ALERTS.json'))
    handoff=out/'handoff';technical=handoff/'technical';technical.mkdir(parents=True,mode=0o700,exist_ok=False);technical_readme(p,out,technical)
    payload={'schemaVersion':'pm-alerts/1.0','product':p['discovery']['product'],'run':p['runId'],**{k:run[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},
        'scope':{'coverageGaps':p.get('coverageGaps',[]),'track':p['track'],'recipe':p['recipe'],'otherTracksExecuted':False},'alerts':groups,'excludedGuardObservations':excluded,
        'summary':{'alertGroups':len(groups),'instances':sum(g['instanceCount'] for g in groups)},'evidenceReadback':verify,
        'taskCompletion':run.get('taskCompletion','partial'),'responsibilityReconciliation':run.get('responsibilityReconciliation'),
        'limitations':['Runtime only in scope actually exercised; enabled rules are not coverage','Native raw artifacts private; independent triage pending']}
    save(handoff,'ALERTS.json',payload);save(technical,'EVIDENCE.json',{'rawRoot':str(out),'manifest':str(out/'EVIDENCE_INDEX.json'),'coverage':str(out/'COVERAGE.json'),'workflowSha256':p['discoverySha256']})
    return payload


def direct_handoff(p,out):
    from .product_bola import verify
    out=Path(out);readback=verify(out);run=json.loads((out/'RUN.json').read_text());checks=json.loads((out/'CHECKS.json').read_text())
    groups=[]
    for check in checks:
        if check['outcome']!='violated':continue
        groups.append({'findingId':'DIRECT-'+check['caseId'],'source':'direct','name':'Policy/post-state discrepancy in locked case '+check['caseId'],
           'severity':'unverified','confidence':'requires-independent-triage','description':'; '.join(check['reasons']),
           'instances':[{'caseId':check['caseId'],'evidenceRef':str(out/'OBSERVATIONS.json')}],
           'evidenceRefs':[{'path':str(out/'CHECKS.json'),'sha256':digest(out/'CHECKS.json')}],
           'impact':{'status':'unverified'},'remediation':'Review policy and preserved observations before selecting a correction.'})
    target=out/'handoff';technical=target/'technical';technical.mkdir(parents=True,mode=0o700,exist_ok=False);technical_readme(p,out,technical)
    dimensions=direct_dimensions(json.loads((out/'PLAN.json').read_text()),checks,run,p.get('coverageGaps',[]))
    save(technical,'CASE_POLICY_COVERAGE.json',dimensions)
    save(target,'ALERTS.json',{'schemaVersion':'pm-alerts/1.0','product':p['discovery']['product'],'run':p['runId'],**{k:run[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},
       'taskCompletion':run.get('taskCompletion','partial'),'responsibilityReconciliation':run.get('responsibilityReconciliation'),
       'scope':{'coverageGaps':p.get('coverageGaps',[]),'track':'bola-ownership','recipe':p['recipe']},'alerts':groups,'summary':{'alertGroups':len(groups),'instances':len(groups)},
       'evidenceReadback':readback,'limitations':['Direct observations; not ZAP alerts or authenticated DAST','Case outcomes, policy certainty and coverage are separate: technical/CASE_POLICY_COVERAGE.json']})
    save(technical,'EVIDENCE.json',{'observations':str(out/'OBSERVATIONS.json'),'checker':str(out/'CHECKS.json'),'manifest':str(out/'EVIDENCE_INDEX.json')})


def anonymous_handoff(p,out):
    from .anonymous_runner import verify
    out=Path(out);readback=verify(out);run=json.loads((out/'RUN.json').read_text())
    from .product_scope import task_readback,apply_completion
    run=apply_completion(run,task_readback(p))
    if not (out/'alerts-native.json').exists():return None
    raw=json.loads((out/'alerts-native.json').read_text())['alerts'];messages={str(m['id']):m for m in json.loads((out/'messages.json').read_text())['messages']}
    attributed=[];excluded=[]
    for a in raw:
        m=messages.get(str(a.get('messageId')),{})
        if 'x-zpa-response-origin: app' in m.get('responseHeader','').lower():attributed.append(a)
        else:excluded.append({'nativeAlertId':a.get('id'),'source':'guard-or-unattributed','reason':'not app coverage'})
    groups,other=normalize(attributed,raw_ref=str(out/'alerts-native.json'),raw_sha=digest(out/'alerts-native.json'))
    # normalize uses selected indexes; rebind pointers to original native occurrence positions.
    positions={str(a['id']):i for i,a in enumerate(raw)}
    for group in groups:
        refs=[]
        for instance in group['instances']:
            index=positions[instance['nativeAlertId']];instance['evidenceRef']=str(out/'alerts-native.json')+'#/alerts/'+str(index)
            refs.append({'path':str(out/'alerts-native.json'),'jsonPointer':'/alerts/'+str(index),'sha256':digest(out/'alerts-native.json'),'access':'private-local'})
        group['evidenceRefs']=refs
    target=out/'handoff';technical=target/'technical';technical.mkdir(parents=True,mode=0o700,exist_ok=False);technical_readme(p,out,technical)
    save(target,'ALERTS.json',{'schemaVersion':'pm-alerts/1.0','product':p['discovery']['product'],'run':p['runId'],**{k:run[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},
       'taskCompletion':run.get('taskCompletion','partial'),'responsibilityReconciliation':run.get('responsibilityReconciliation'),
       'scope':{'coverageGaps':p.get('coverageGaps',[]),'track':'be-anonymous','recipe':p['recipe']},'alerts':groups,'excludedGuardObservations':excluded+other,
       'summary':{'alertGroups':len(groups),'instances':sum(g['instanceCount'] for g in groups)},'evidenceReadback':readback,
       'limitations':['Protected denial is not authenticated business coverage','Rules enabled are not proof of exercise; check OPERATIONS/COVERAGE']})
    save(technical,'EVIDENCE.json',{'rawRoot':str(out),'nativeManifest':str(out/'manifest.json'),'coverage':str(out/'COVERAGE.json')})


def technical_readme(p,out,technical):
    text=("# Hướng dẫn tester\n\nTrack: "+p['track']+". Recipe: "+p['recipe']+".\n\n"
          "Raw root private: "+str(out)+". Đọc PLAN/discovery/authority và evidence index trước khi tái lập. "
          "Native: report JSON/HTML, MCP journal/operation IDs và COVERAGE. Direct: OBSERVATIONS/CHECKS với expected policy khóa trước. "
          "Setup và oracle có count/lane riêng; không cộng vào ZAP coverage.\n\n"
          "Để tái kiểm: dùng source pins và common CLI trong docs/multi-product-backend.md; tạo run/fixtures mới trong scope hiện còn hiệu lực. "
          "Không replay mutation hoặc start uncertain; reconcile exact ledger và operation IDs. Raw credential/history chỉ private local, không publish. "
          "Giữ năm trạng thái độc lập; verifier exit0 không là approval hoặc security pass.\n")
    (technical/'README_VI.md').write_text(text)


def direct_dimensions(plan,checks,run,coverage_gaps):
    """Presentation only: retain raw verdict even when a violated case coexists with unknowns."""
    from collections import Counter
    by_id={c['caseId']:c for c in checks}
    if len(by_id)!=len(checks):raise ValueError('duplicate selected check; choose lineage before aggregation')
    cases=[]
    for c in plan['cases']:
        check=by_id.get(c['id'])
        group='collection' if c.get('pagination') else 'cross-owner' if c.get('relation')=='nonowner' else 'owner-positive' if c.get('relation')=='owner' else 'state/control'
        cases.append({'caseId':c['id'],'group':group,'outcome':check['outcome'] if check else 'not-run',
                      'reasons':check.get('reasons',[]) if check else ['observation absent'],'operationId':c['request']['operationRef']})
    if set(by_id)-{c['caseId'] for c in cases}:raise ValueError('check outside locked cases')
    return {'caseOutcomes':dict(Counter(c['outcome'] for c in cases)),'cases':cases,
            'policy':{'status':plan['policyStatus'],'evidenceRefs':sorted({ref for c in plan['cases'] for ref in c.get('policyEvidenceRefs',[])}),
                      'uncertainty':'Independent policy expectation unresolved' if plan['policyStatus']=='source-hypothesis' else 'Acceptance references remain in locked workflow'},
            'coverage':{'plannedCases':len(cases),'observedCases':len(checks),'gaps':coverage_gaps},
            'rawStatuses':{k:run[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')},
            'findingsCaseIds':[c['caseId'] for c in cases if c['outcome']=='violated'],
            'meaning':'matched observations do not imply accepted policy, track completion or product safety'}


def compose_handoff(selection,output):
    """Compose selected lineage evidence; never infer fresh execution or count retries.

    Each unit is a reviewed obligation identifier. A retry must replace its predecessor
    in the selection, rather than add another count. Native occurrences retain their
    original severity/confidence and evidence location across aggregation.
    """
    import copy
    from collections import Counter
    legacy_tracks=('be-anonymous','be-authenticated','bola-ownership')
    tracks=tuple(selection.get('tracks',legacy_tracks))
    if not tracks or len(set(tracks))!=len(tracks) or not set(tracks)<=set((*legacy_tracks,'fe-anonymous','fe-authenticated')):raise ValueError('invalid explicit track selection')
    statuses=('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')
    rows=selection['runs'];seen=set();loaded=[];location=None;actor_labels={}
    direct=selected_direct_dimensions(selection.get('directRuns',[]))
    for row in rows:
        if row['track'] not in tracks or not row.get('units') or not row.get('retentionReason'):raise ValueError('lineage selection incomplete')
        for unit in row['units']:
            key=(row['track'],unit)
            if key in seen:raise ValueError('duplicate lineage unit; select one attempt')
            seen.add(key)
        path=Path(row['path']);blob=path.read_bytes()
        if digest(path)!=row['sha256']:raise ValueError('selected handoff drift')
        payload=json.loads(blob)
        if row.get('actorEvidence'):
            actor_ref=row['actorEvidence'];actor_path=Path(actor_ref['path'])
            if digest(actor_path)!=actor_ref['sha256']:raise ValueError('actor presentation evidence drift')
            actor=json.loads(actor_path.read_text())
            if actor.get('nativeValidated') is not True or not actor.get('role') or not actor.get('subject'):raise ValueError('actor presentation needs native identity evidence')
            actor_labels[row['path']]=str(actor['role'])+' / subject '+str(actor['subject'])
        if payload.get('schemaVersion')!='pm-alerts/1.0':raise ValueError('selected handoff schema')
        current=payload['product']['location']
        if location is not None and current!=location:raise ValueError('mixed product lineage')
        location=current;loaded.append((row,payload))
    if {r['track'] for r,_ in loaded}!=set(tracks):raise ValueError('selected tracks required; default remains three backend tracks')
    out=Path(output);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    all_alerts=[];selected=[]
    for track in tracks:
        folder=out/track;folder.mkdir(mode=0o700);groups={};origins=[];excluded=[]
        for row,payload in loaded:
            if row['track']!=track:continue
            origins.append({**row,'run':payload['run'],'rawStatuses':{k:payload[k] for k in statuses},'scope':payload['scope']})
            for alert in payload['alerts']:
                key=(alert['source'],alert.get('nativeRuleId'),alert['name'],alert['severity'],alert['confidence'])
                if key not in groups:
                    groups[key]=copy.deepcopy(alert);groups[key]['instances']=[];groups[key]['evidenceRefs']=[];groups[key]['sourceFindings']=[]
                g=groups[key]
                g['sourceFindings'].append({'findingId':alert.get('findingId'),'handoffPath':row['path']})
                for instance in alert['instances']:
                    # Native IDs restart for each run. Only evidence identity deduplicates.
                    if instance.get('evidenceRef') not in {v.get('evidenceRef') for v in g['instances']} or not instance.get('evidenceRef'):
                        safe=copy.deepcopy(instance)
                        if row['path'] in actor_labels:safe['actor']=actor_labels[row['path']]
                        if 'otherInfo' in safe:
                            from .discovery_handoff import clean
                            safe['otherInfo']=clean(safe['otherInfo'])
                        g['instances'].append(safe)
                for ref in alert['evidenceRefs']:
                    if ref not in g['evidenceRefs']:g['evidenceRefs'].append(copy.deepcopy(ref))
            excluded.extend(payload.get('excludedGuardObservations',[]))
        alerts=list(groups.values())
        for index,g in enumerate(alerts):g['findingId']=track+'-'+str(index+1).zfill(3);g['track']=track;g['trackResult']=str(folder/'ALERTS.json');g['instanceCount']=len(g['instances'])
        result={'schemaVersion':'pm-alerts/1.0','product':loaded[0][1]['product'],'run':selection['runId'],'track':track,
            'scope':{'track':track,'taskCompletion':'partial','selectedLineage':origins,'coverageNote':selection['coverageNote']},
            'alerts':alerts,'excludedGuardObservations':excluded,'summary':{'alertGroups':len(alerts),'instances':sum(g['instanceCount'] for g in alerts),'groupsBySeverity':dict(Counter(g['severity'] for g in alerts))},
            'limitations':['Selected retained and continuation evidence; not all tracks rerun','Raw statuses preserved per selected run; policy and case outcomes remain separate','Raw native artifacts private local']}
        result.update(aggregate_statuses([r['rawStatuses'] for r in origins]))
        if track=='bola-ownership' and direct:
            result['summary'].update(directCases=direct['coverage']['plannedCases'],directOutcomes=direct['caseOutcomes'])
            save(folder,'CASE_POLICY_COVERAGE.json',direct)
        save(folder,'ALERTS.json',result);save(folder,'EVIDENCE.json',origins)
        all_alerts.extend(alerts);selected.extend(origins)
    payload={'schemaVersion':'pm-alerts/1.0','product':loaded[0][1]['product'],'run':selection['runId'],
        'scope':{'taskCompletion':'partial','tracks':list(tracks),'coverageNote':selection['coverageNote']},'alerts':all_alerts,
        'summary':{'alertGroups':len(all_alerts),'instances':sum(g['instanceCount'] for g in all_alerts),'groupsBySeverity':dict(Counter(g['severity'] for g in all_alerts))},
        'selectedLineage':selected,'technicalFolder':str(out),'limitations':['Task completion, case outcomes and policy certainty are independent','No whole-product security verdict; no approval implied']}
    payload.update(aggregate_statuses([r['rawStatuses'] for r in selected]))
    if direct:payload['summary'].update(directCases=direct['coverage']['plannedCases'],directOutcomes=direct['caseOutcomes'])
    payload['responsibilityReconciliations']=[copy.deepcopy(data['responsibilityReconciliation']) for _,data in loaded if data.get('responsibilityReconciliation')]
    payload['openResponsibilities']=[copy.deepcopy(r) for rec in payload['responsibilityReconciliations'] for r in rec.get('openResponsibilities',[])]
    payload['nextSteps']=[copy.deepcopy(r) for rec in payload['responsibilityReconciliations'] for r in rec.get('nextActions',[])]
    save(out,'ALERTS.json',payload);save(out,'SELECTION.json',selection)
    return payload


def selected_direct_dimensions(rows):
    """Read selected raw cases by logical unit, preserving superseded attempts in place."""
    import copy
    if not rows:return None
    cases=[];checks=[];units=set();sources=[];policies=[];statuses=[]
    for row in rows:
        docs={}
        for name in ('plan','checks','run'):
            ref=row[name];p=Path(ref['path'])
            if digest(p)!=ref['sha256']:raise ValueError('direct lineage evidence drift')
            docs[name]=json.loads(p.read_text())
        by_case={c['id']:c for c in docs['plan']['cases']};by_check={c['caseId']:c for c in docs['checks']}
        if len(by_case)!=len(docs['plan']['cases']) or len(by_check)!=len(docs['checks']):raise ValueError('duplicate raw direct case')
        policies.append(docs['plan']['policyStatus']);statuses.append(docs['run'])
        for chosen in row['cases']:
            unit=chosen['unitId'];cid=chosen['caseId']
            if unit in units:raise ValueError('duplicate direct lineage unit; supersede prior attempt')
            units.add(unit)
            if cid not in by_case or cid not in by_check:raise ValueError('selected direct case missing')
            c=copy.deepcopy(by_case[cid]);c['id']=unit;cases.append(c)
            check=copy.deepcopy(by_check[cid]);check['caseId']=unit;checks.append(check)
            sources.append({'caseId':unit,'originalCaseId':cid,'plan':row['plan'],'checks':row['checks'],'run':row['run']})
    policy=policies[0] if len(set(policies))==1 else 'source-hypothesis'
    result=direct_dimensions({'cases':cases,'policyStatus':policy},checks,aggregate_statuses(statuses),[])
    result['selectedSources']=sources;result['rawRunStatuses']=statuses
    result['coverage']['meaning']='selected logical cases only; superseded raw observations retained, not recounted'
    return result


def aggregate_statuses(rows):
    """Conservative derived summary; all original status tuples remain in lineage."""
    result={}
    for key,preferred in [('executionStatus','completed'),('evidenceStatus','complete'),('cleanupStatus','clean')]:
        result[key]=next((r[key] for r in rows if r[key]!=preferred),preferred)
    verdicts={r['securityVerdict'] for r in rows}
    result['securityVerdict']=next(iter(verdicts)) if len(verdicts)==1 else 'inconclusive'
    gates={r['gateDecision'] for r in rows}
    result['gateDecision']='block' if 'block' in gates else 'review_required' if 'review_required' in gates else rows[0]['gateDecision']
    return result
