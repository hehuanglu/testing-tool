"""Offline control qualification from application receipts, native history and broker records."""
import json
from pathlib import Path
from urllib.parse import urlsplit
from .fe_authenticated_contract import load,save,canonical,pins,digest
from .fe_authenticated_verify import verify

def qualify(folder):
    folder=Path(folder).resolve();control=load(folder/'CONTROL_RESULT.json');begin=load(folder/'IMPLEMENTATION_PINS_BEGIN.json')
    if begin!=control['sourcePins'] or begin!=pins() or control['implementationDrift']:raise ValueError('control does not qualify current pins')
    root=folder/'runtime';p=load(root/'PLAN.json')
    if p.get('schemaVersion')!='fe-authenticated-research-plan/1.0' or not p.get('implementationPins') or p['implementationPins']!=begin:raise ValueError('control is calibration/diagnostic only; common compiled plan required')
    fault=control.get('fault');arrival_path=folder/'arrivals/arrivals.jsonl';arrivals=[json.loads(line) for line in arrival_path.read_text().splitlines()] if arrival_path.exists() else []
    records=[load(f) for f in sorted((root/'broker').glob('[0-9]*.json'))];unmatched=[]
    actor=load(root/'private/ACTORS_INITIAL.json')['actor-a'];principal=str(actor['subject'])
    if not any(digest(proof['path'])==proof['sha256'] and (doc:=load(proof['path'])).get(actor['username'],{}).get('subject')==actor['subject'] and doc[actor['username']]['role']==actor['role'] for proof in actor['provenance']):raise ValueError('control independent actor authority absent')
    used=set()
    for r in records:
        if not r.get('forwarded'):continue
        u=urlsplit(r['url']);matching=[(i,a) for i,a in enumerate(arrivals) if i not in used and a['method']==r['method'] and a['path']==u.path and a['query']==u.query and a['bodySha256']==r['requestBodySha256'] and a['responseSha256']==r['responseBodySha256'] and a['status']==r['status'] and 0<=r['at']-a['at']<=15]
        matches=[a for i,a in matching]
        if matching:used.add(min(matching,key=lambda pair:abs(pair[1]['at']-r['at']))[0])
        if not matches:unmatched.append(r['sequence'])
        if r.get('credentialFingerprint') and u.path!=p['journeys']['auth']['loginPath'] and r.get('status') not in (401,403) and fault!='wrong-actor' and not any(str(a['principal'])==principal for a in matches):raise ValueError('application principal mismatch')
    if not fault and len(used)!=len(arrivals):raise ValueError('app arrival counter exceeds independently paired responses')
    if unmatched:raise ValueError('app/native/broker response join absent '+str(unmatched))
    rejection=None;derived=None
    if fault=='controller-crash':
        recovery=load(root/'recovery-01/RECOVERY.json')
        if recovery['startReplayed'] or recovery['mutationReplayed'] or recovery['cleanupStatus']!='clean' or not recovery['stoppedNativeIds'] or not recovery['reportsReadFully']:raise ValueError('controller crash stop/export proof absent')
        from .journal import Journal
        Journal(root/'journal.jsonl',p['runId'],canonical(p))
        for fmt in ('json','html'):
            doc=load(root/('recovery-01/reports/'+fmt+'-readback.json'))
            if not doc['pages'][-1]['endOfFile']:raise ValueError('crash report EOF absent')
        derived='partial after hard controller loss; exact owned resources stopped/exported'
    else:
        run=load(root/'RUN.json')
        if run['cleanupStatus']!='clean' or run['evidenceStatus']!='complete':raise ValueError('fault/positive stop-export-cleanup not complete')
        try:derived=verify(root,canonical(p))
        except ValueError as e:rejection=str(e)
        if not fault:
            if rejection or derived['taskCompletion']!='complete':raise ValueError('positive control semantic gap: '+str(rejection or derived['missing']))
            alerts=load(root/'alerts-native.json')['alerts'];detected={str(a['pluginId']) for a in alerts}
            for rule in ('40012','40018'):
                if (rule in detected)!=(control['variant']=='vulnerable'):raise ValueError('vulnerable/fixed detector contrast '+rule)
            if {x['campaignId'] for x in derived['delivery']}!={'native-query','native-json-body','native-json-put'} or not all(x['delivered'] for x in derived['delivery']):raise ValueError('query/POST/PUT delivery proof absent')
            if len(derived['ownedIds'])!=2 or len(derived['postStates'])!=2:raise ValueError('intermediate/terminal ownership persistence proof absent')
        else:
            if not rejection and derived.get('taskCompletion')=='complete':raise ValueError('fault falsely classified complete')
            observed_path=root/'FAULT_OBSERVED.json';observed=load(observed_path) if observed_path.exists() else {}
            if fault in ('tls-ca','tls-hostname','tls-pin'):
                if arrivals or any(r.get('forwarded') or r.get('transportState')=='unknown' for r in records) or not any(r.get('reason')=='transport-error' for r in records):raise ValueError('TLS denial not proven before app send')
            elif fault=='wrong-password':
                if load(root/'OPERATIONS.json') or not any(a['path']==p['journeys']['auth']['loginPath'] and a['status']==401 for a in arrivals) or any(r.get('observedPrincipal') for r in records):raise ValueError('wrong password false protected coverage')
            elif fault in ('wrong-actor','browser-loss','native-loss'):
                slot='browser' if fault=='browser-loss' else 'native'
                failures=[r for r in records if r.get('authSlot')==slot and r.get('identityFailure')]
                if not failures or not any(r.get('authSlot')!=slot and r.get('observedPrincipal')==principal for r in records):raise ValueError('separate browser/native loss proof absent')
                if observed.get('afterLossAppCount')!=observed.get('afterAppCount') or not any(r.get('policyLatched') and not r.get('forwarded') for r in records):raise ValueError('post-loss latch denial proof absent')
                if fault=='wrong-actor' and not any(a['principal']=='controlled-wrong-person' for a in arrivals):raise ValueError('wrong protected actor not observed by app')
            elif fault in ('stale-credential','scope','pre-send'):
                if not observed or observed['beforeAppCount']!=observed['afterAppCount']:raise ValueError('denied request reached app or proof absent')
                reasons={'stale-credential':'unregistered-or-stale-credential','scope':'connect-origin','pre-send':'transport-error'}
                if not any(r.get('reason')==reasons[fault] and not r.get('forwarded') for r in records):raise ValueError('guard/pre-send proof absent')
                if fault=='scope' and (len(observed.get('protocol',[]))!=2 or observed.get('management',{}).get('ipv6ManagementReachable') is not False or observed.get('boundary',{}).get('zap') is not True):raise ValueError('scope protocol/kernel/management proof absent')
            elif fault in ('commit-drop','broker-crash'):
                if observed.get('afterAppCount')!=observed.get('beforeAppCount',-1)+1 or not any(r.get('caseId')=='fault-'+fault and r.get('transportState') in ('sent','response-headers','unknown') for r in records):raise ValueError('unknown committed mutation ledger absent')
                owners={user for a in arrivals for user,rows in a['rows'].items() if any(row['title']=='owned-uncertain-marker' for row in rows)}
                latest=arrivals[-1]['rows'];mutations=[row for user in owners for row in latest.get(user,[]) if row['title']=='owned-uncertain-marker']
                if len(owners)!=1 or len(mutations)!=1:raise ValueError('uncertain mutation ownership/counter/replay mismatch')
            elif fault=='resource':
                samples=load(root/'RESOURCES.json')['samples']
                if not observed.get('monitorErrors') or not any(s.get('injectedQualificationSample') and s['hostFree']==0 for s in samples):raise ValueError('controlled monitor breach stop absent')
            elif fault=='cancel':
                if not observed.get('cancelSet') or run['executionStatus']!='interrupted':raise ValueError('cancel did not interrupt')
            elif fault=='native-restart':
                if not observed.get('rejectionType') or not observed.get('oldSessionId'):raise ValueError('stale native handle not rejected')
            elif fault=='lost-ack':
                unknown=load(root/'UNKNOWN_STARTS.json');reconciled=load(root/'UNKNOWN_START_RECONCILIATION.json')
                if unknown['replayed'] or not unknown['observedNewScans'] or not reconciled['statuses'] or any(str(s['status'])!='100' for s in reconciled['statuses'].values()):raise ValueError('lost ACK exact stop-only reconciliation absent')
            else:raise ValueError('unknown fault qualification')
    result={'qualification':'pass','fault':fault,'variant':control['variant'],'sourcePins':begin,'applicationArrivals':len(arrivals),'forwardedBrokerResponses':sum(bool(r.get('forwarded')) for r in records),'unmatched':unmatched,'independent':derived,'expectedSemanticRejection':rejection,'reviewerApproval':None}
    save(folder,'QUALIFICATION_READBACK.json',result);return result

if __name__=='__main__':
    import sys
    result=qualify(sys.argv[1]);print(json.dumps({k:result[k] for k in ('qualification','fault','variant','applicationArrivals')}))
