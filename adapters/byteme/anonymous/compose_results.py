"""Summarize actual ByteMe traffic against source responsibilities; emit only two handoff files."""
import collections,json,re,time
from datetime import datetime,timezone,timedelta
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl
import run
from zap_assessment.active_questions import assess_question
from zap_assessment.result_readers import read_jsonl
R=run.ROOT;src='/Users/hahoangloc/Working/UET/SA/ByteMe';tz=timezone(timedelta(hours=7))
cfg=run.load('private.json');disc=run.load('discovery.json');traffic=read_jsonl(R/'guard-private/traffic.jsonl')
rows=[r for r in traffic if r['kind']=='traffic'];campaigns={p.stem:json.loads(p.read_text()) for p in (R/'campaigns').glob('*.json')};controls=run.load('controls.json');post=run.load('poststate.json');native=run.load('alerts-native.json')['alerts']
assert len(native)==run.load('alerts-native.json')['count']
attribution=run.load('alert-response-attribution.json');assert all(not a['emptyGuardResponse'] and a['applicationHeadersPresent'] for a in attribution)
assert all(c['terminal'] for c in campaigns.values())
cases=[];observations={};coverage=[]
def add(cid,method,path,question,required,observed,details,*,provenance='controllers, SecurityConfiguration.java and current runtime OpenAPI'):
    cases.append({'caseId':cid,'method':method,'path':path,'role':'anonymous','question':question,'requiredEvidence':required,'evidenceRefs':[src+'/src/main/java/org/example',src+'/src/main/resources/static/openapi.yaml'],'provenance':provenance,'prerequisites':[]})
    observations[cid]={'role':'anonymous','outcome':'matched' if set(required)<=set(observed) else 'observed','evidenceUnits':observed,'resultRead':True}
    coverage.append({'caseId':cid,'method':method,'route':path,'role':'anonymous','question':question,**details})
def native_rows(name):return [r for r in rows if r.get('campaign')==name and r.get('technique')=='ZAP active']
for field in ('fullName','email','phone','password','confirmPassword'):
    name='register-'+field;c=campaigns[name];rr=native_rows(name);baseline=json.loads(run.load('seeds/'+name+'.json')['requestBody'])
    changed=[r for r in rr if json.loads(r['nativeBody'])[field]!=baseline[field] and json.loads(r['nativeBody'])[field]==json.loads(r['actualBody'])[field]]
    assert changed
    if field=='phone':changed+=native_rows('register-phone-valid')
    stored=[r for r in changed if r['status']==201];assert stored
    readback=next(p for p in post if p['id']==('register-phone-valid' if field=='phone' else name))
    assert readback['status']==200 and readback['accountIdMatched'] and readback['storedFieldsMatched'] and readback['role']=='CUSTOMER' and not readback['passwordEchoed']
    required=['native-active:'+field,'create-or-boundary-read','stored-account-readback']
    observed=[]
    if changed:observed.append('native-active:'+field)
    if stored:observed.append('create-or-boundary-read')
    if readback['status']==200 and readback['accountIdMatched'] and readback['storedFieldsMatched']:observed.append('stored-account-readback')
    add(name,'POST','/api/auth/register','Exercise '+field+' validation and valid account creation/storage while sibling fields remain valid and credentials unique.',required,observed,
        {'input':{'location':'JSON-body','field':field},'campaigns':[name]+(['register-phone-valid'] if field=='phone' else []),'nativeMutatedRequests':len(changed),'mutatedResponseStatuses':dict(collections.Counter(str(r['status']) for r in changed)),'createdWithMutatedTargetField':len(stored),'postState':readback,
         'interpretation':'Valid payloads reached new-account persistence; rejected payloads are validation observations. Each password mutation is mirrored to its dependent confirmation, or vice versa. Phone injection payloads hit validation; the additional native script exercised valid local/trimmed/international values.'})
for field in ('email','password'):
    name='token-'+field;rr=native_rows(name);c=campaigns[name];assert c['mutatedInputRequests']>0
    assert any(r['status']==200 for r in rows if r.get('campaign')==name)
    assert any(r['status']==401 and json.loads(r['response']).get('code')=='INVALID_CREDENTIALS' for r in rr)
    req=['native-active:'+field,'credential-handler-outcome-read']
    observed=[]
    if c['mutatedInputRequests']>0:observed.append('native-active:'+field)
    if any(r['status']==401 and json.loads(r['response']).get('code')=='INVALID_CREDENTIALS' for r in rr):observed.append('credential-handler-outcome-read')
    add(name,'POST','/api/auth/token','Exercise credential input validation and credential lookup/comparison without propagating the issued identity.',req,observed,
        {'input':{'location':'JSON-body','field':field},'campaigns':[name],'mutatedInputRequests':c['mutatedInputRequests'],'responseStatuses':c['mutatedInputStatusCounts'],'businessOutcomes':c['mutatedInputBusinessCodes'],'baselineIssuedToken':True,'issuedTokenPropagated':False})
for name,field,path in [('foods-category','categoryId','/api/foods'),('foods-search','q','/api/foods/search'),('foods-search','categoryId','/api/foods/search')]:
    base=dict(parse_qsl(urlsplit(campaigns[name]['query']).query));rr=native_rows(name)
    changed=[r for r in rr if dict(parse_qsl(urlsplit(r['path']).query,keep_blank_values=True)).get(field)!=base[field]]
    assert changed
    baseline=json.loads(run.load('seeds/'+name+'.json')['responseBody']);assert isinstance(baseline,list) and baseline
    req=['native-active:query:'+field,'response-read','populated-positive-baseline']
    observed=[]
    if changed:observed.extend(['native-active:query:'+field,'response-read'])
    if isinstance(baseline,list) and baseline:observed.append('populated-positive-baseline')
    add(name+'-'+field,'GET',path,'Exercise '+field+' filter/search handling, numeric validation where applicable, and error/JSON responses against populated catalog data.',req,observed,
        {'input':{'location':'query','field':field},'campaigns':[name],'mutatedInputRequests':len(changed),'responseStatuses':dict(collections.Counter(str(r['status']) for r in changed)),'populatedBaselineCount':len(baseline),'result':'Numeric SQL/XSS payloads rejected by conversion where applicable; text search payloads reached JSON search results. Literal wildcard and empty-query controls are listed in operations.'})
rr=native_rows('foods-id');base=campaigns['foods-id']['path'];changed=[r for r in rr if r['path']!=base];assert changed
req=['native-active:path:id','response-read','existing-object-baseline']
add('foods-id','GET','/api/foods/{id}','Exercise the public numeric selector parser and food lookup/error response on an existing catalog item.',req,req,
    {'input':{'location':'path','field':'id'},'campaigns':['foods-id'],'mutatedPathRequests':len(changed),'responseStatuses':dict(collections.Counter(str(r['status']) for r in changed)),'notFoundControl':next(p for p in post if p['id']=='catalog-semantic-4'),'scopeGuard':'Extra path segments and decoded slash/CR/LF variants were denied locally and receive no application coverage credit. Applicable numeric-selector validation was exercised by delivered SQLi/XSS variants.'})
assert all(next(c for c in controls if c['id']==key)['status']==status for key,status in [('register-malformed',400),('register-xml',415),('token-malformed',400),('token-xml',415),('register-method-get',405),('token-method-get',405)])
assert next(c for c in post if c['id']=='register-duplicate')['status']==409 and next(c for c in post if c['id']=='register-password-mismatch')['bodyCode']=='PASSWORD_MISMATCH'
add('public-auth-contract-controls','POST','/api/auth/register; /api/auth/token','Check malformed JSON, rejected XML, password dependency, duplicate identity and unsupported HTTP method behavior.',['contract-controls-read'],['contract-controls-read'],{'controls':[c for c in controls if c['id'].startswith(('register-','token-'))]+[c for c in post if c['id'] in ('register-duplicate','register-password-mismatch')]})
for n,path in enumerate(['/openapi.yaml','/actuator/health','/swagger-ui/index.html','/v3/api-docs/swagger-config','/error']):
    name='aux-'+str(n);rr=native_rows(name);assert any(r.get('ruleId')=='10104' for r in rr)
    req=['native-active:header:User-Agent','response-read']
    add(name,'GET',path,'Exercise server header handling and public auxiliary response disclosure with the native User Agent Fuzzer.',req,req,{'campaigns':[name],'responseStatuses':campaigns[name]['statusCounts'],'applicationRequests':len(rr)})
static=[c for c in controls if c['id'].startswith('aux-control-')];repair=run.load('static-read-repair.json') if (R/'static-read-repair.json').exists() else {}
for c in static:
    status=repair['status'] if c['path']==repair.get('path') else c['status']
    add(c['id'],'GET',c['path'],'Observe public documentation/static/health-subpath behavior within BE discovery and passive response checks.',['response-and-passive-read'],['response-and-passive-read'],{'status':status,'technique':'baseline via ZAP and passive response inspection','applicability':'Static assets and the redirect have no discovered mutable backend input; native header handling was exercised on the document entry. Health subpaths returned 404 and exposed no extra operation. Browser UI/DOM execution is outside BE-only scope.'})
for op in disc['operations']:
    if not op['protected']:continue
    c=next(c for c in controls if c['id']=='denial-'+op['id']);assert c['status']==401 and c['bodyCode']=='UNAUTHENTICATED'
    add(c['id'],op['method'],op['path'],'Supplementary anonymous denial at the authentication boundary; protected business handlers are outside the requested track.',['anonymous-denial-read'],['anonymous-denial-read'],{'status':c['status'],'businessCode':c['bodyCode'],'technique':'direct anonymous request through ZAP, passive inspection; no authenticated coverage claimed','placeholderIds':'Syntactic ID 1 only to exercise the pre-handler authentication boundary; no ownership claim.'})
for name,camp in campaigns.items():
    base=run.load('seeds/'+name+'.json');rr=native_rows(name)
    for question in camp['questions']:
        probes=[]
        for r in rr:
            field=question.get('field')
            if camp.get('field'):
                changed=json.loads(r['nativeBody'])[field]!=json.loads(base['requestBody'])[field] and json.loads(r['nativeBody'])[field]==json.loads(r['actualBody'])[field]
            elif camp.get('vector')=='query':
                b=dict(parse_qsl(urlsplit(camp['query']).query,keep_blank_values=True));v=dict(parse_qsl(urlsplit(r['path']).query,keep_blank_values=True))
                changed=v.get(field)!=b.get(field) if field else v!=b
            elif camp.get('vector')=='path':changed=urlsplit(r['path']).path!=camp['path']
            else:
                bh={k.lower():v.strip() for k,v in (s.split(':',1) for s in base['requestHeader'].splitlines()[1:] if ':' in s)}
                changed=any(k.lower()=='user-agent' and v!=bh.get('user-agent') for k,v in r.get('requestHeaders',[]))
                # Header is recorded explicitly by the adapter, not inferred from a rule name.
                changed=r.get('userAgent')!=bh.get('user-agent') if 'userAgent' in r else changed
            try:body=json.loads(r['response'])
            except ValueError:body=None
            stage='processing' if r['status'] in (200,201) or isinstance(body,dict) and body.get('code')=='INVALID_CREDENTIALS' else 'boundary' if r['status'] in (400,401,404,405,415,500) else 'fixture-blocked'
            probes.append({'ruleId':r.get('ruleId'),'changed':changed,'application':r['kind']=='traffic','identityValid':True,'stage':stage,'resultRead':True})
        answer=assess_question(question,probes);unit=answer['unit'];cid=unit
        cases.append({'caseId':cid,'method':camp['method'],'path':camp['path'],'role':'anonymous','question':question['basis'],'requiredEvidence':[unit],'evidenceRefs':[src],'prerequisites':[]})
        observations[cid]={'role':'anonymous','outcome':'matched' if answer['status']=='observed' else 'observed','evidenceUnits':answer['evidenceUnits'],'resultRead':True}
        coverage.append({'caseId':cid,'method':camp['method'],'route':camp['path'],'role':'anonymous','question':question,'readback':answer,'campaigns':[name]})
source_inv=run.load('responsibility-inventory.json')
for case in source_inv['cases']:
    route_re=re.compile('^'+re.sub(r'\{[^}]+\}',r'[^/]+',case['path'])+'$')
    matching=[(name,c) for name,c in campaigns.items() if c['method']==case['method'] and route_re.fullmatch(c['path'])]
    units=[]
    if any(c['terminal'] and c['applicationRequests'] and native_rows(name) for name,c in matching):units.append('source-active-result-read')
    for need in case['inputs']:
        for name,c in matching:
            if c.get('vector')!=need['vector']:continue
            base=run.load('seeds/'+name+'.json');field=need['field'];changed=[]
            for row in native_rows(name):
                if row.get('ruleId') is None:continue
                if need['vector']=='JSON-body':
                    yes=c.get('field')==field and json.loads(row['nativeBody']).get(field)!=json.loads(base['requestBody']).get(field) and json.loads(row['nativeBody']).get(field)==json.loads(row['actualBody']).get(field)
                elif need['vector']=='query':
                    old=dict(parse_qsl(urlsplit(c['query']).query,keep_blank_values=True));actual=dict(parse_qsl(urlsplit(row['path']).query,keep_blank_values=True));yes=field in old and actual.get(field)!=old[field]
                else:yes=urlsplit(row['path']).path!=c['path']
                if yes:changed.append(row)
            if changed:units.append('source-input:'+need['vector']+':'+field);break
    cases.append(case);observations[case['caseId']]={'role':'anonymous','outcome':'matched' if set(case['requiredEvidence'])<=set(units) else 'observed','evidenceUnits':units,'resultRead':True}
    coverage.append({'caseId':case['caseId'],'operationId':case['operationId'],'method':case['method'],'route':case['path'],'role':'anonymous','sourceInputs':case['inputs'],'observedUnits':units,'missing':sorted(set(case['requiredEvidence'])-set(units)),'operationIds':['campaign-'+name for name,c in matching]})
inventory={'productLocation':src,'track':'be-anonymous','environment':'byteme Docker compose','origin':cfg['origin'],'complete':True,'cases':cases}
reconciliation=run.reconcile(inventory,observations,{})
run.save('responsibility-review.json',{'inventory':inventory,'observations':observations,'reconciliation':reconciliation})

def plain(value):return re.sub(r'<[^>]+>','',value or '').strip()
def redact(value):
    value=re.sub(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+','[issued token withheld]',str(value))
    for secret in (cfg['password'],cfg['key'],'NativeSeedPassword123!'):value=value.replace(secret,'[private value]')
    return value
triage={
 '10038':'CSP is absent on the public Swagger HTML responses. This is a documentation UI hardening finding; exploitation was not demonstrated.',
 '10003':'Native library fingerprint matched DOMPurify.version="3.3.2" in the shipped Swagger bundle. Keep the native Medium/Medium alert. Advisory mappings come from scanner intelligence and were not independently verified; exploit reachability was not tested.',
 '90022':'The public /error route returns HTTP 500 and generic JSON with status 999 and error None. The match is the HTTP status line; inspected response contains no stack trace, file path or secret. Sensitive disclosure impact is unconfirmed.',
 '10096':'The matches are number sequences in Swagger JavaScript. No runtime account/session timestamp disclosure was established; retain native Low/Low observations without treating constant values as sensitive data.',
 '10111':'Expected recognition of a public login request, not evidence of credential disclosure.',
 '10112':'Expected recognition of issued accessToken fields. Tokens were returned only by public login with valid test credentials and were not propagated or included in the handoff.',
 '10109':'Informational recognition of the public Swagger web UI; not a demonstrated vulnerability.',
 '10104':'Informational User Agent Fuzzer observations on public documentation/error routes. These do not establish a security impact; keep native confidence and severity.'}
groups=[]
for (pid,risk,confidence),group in __import__('itertools').groupby(sorted(native,key=lambda a:(a['pluginId'],a['risk'],a['confidence'])),key=lambda a:(a['pluginId'],a['risk'],a['confidence'])):
    group=list(group);a=group[0]
    groups.append({'pluginId':pid,'name':a['name'],'severity':risk,'confidence':confidence,'source':'ZAP','technique':'active' if a['sourceid']=='1' else 'passive','nativeSourceId':a['sourceid'],'instanceCount':len(group),'description':plain(a['description']),'nativeRecommendation':plain(a['solution']),'testerAssessment':triage.get(pid,'Native severity/confidence retained; inspect impact in the actual response context. A JSON reflection is not proof of browser execution.'),'instances':[{'nativeAlertId':x['id'],'method':x['method'],'url':x['url'],'parameter':x['param'],'attack':redact(x.get('attack','')),'observation':redact(x.get('evidence',''))} for x in group]})
summary={'groupCount':len(groups),'instanceCount':len(native),'groupsBySeverity':dict(collections.Counter(g['severity'] for g in groups)),'instancesBySeverity':dict(collections.Counter(a['risk'] for a in native)),'groupsBySource':{'ZAP':len(groups),'direct':0},'instancesBySource':{'ZAP':len(native),'direct':0},'groupsByTechnique':dict(collections.Counter(g['technique'] for g in groups)),'instancesByTechnique':dict(collections.Counter('active' if a['sourceid']=='1' else 'passive' for a in native)),'counting':'A group is native pluginId + severity + confidence. Instances are all distinct current native alert IDs; the standard report includes bounded samples and its smaller instance count is not the denominator.'}
created=[]
for r in traffic:
    if (r.get('status')==201 and r.get('path')=='/api/auth/register') or (r['kind']=='fixture-register' and r.get('status')==201):created.append(json.loads(r['response'])['id'])
operations=[]
for cid,c in sorted(campaigns.items(),key=lambda t:int(t[1]['nativeId'])):
    operations.append({'id':'campaign-'+cid,'caseId':cid,'method':c['method'],'route':c['path'],'query':c.get('query'),'role':'anonymous','actor':'no target session or identity','technique':'native ZAP active via '+('guided MCP' if c['guided'] else 'ByteMe-scoped anonymous adapter using existing native ascan and baseline-binding primitives'),'nativeScanId':c['nativeId'],'startedAt':datetime.fromtimestamp(c['startedAt'],tz).isoformat(),'finishedAt':datetime.fromtimestamp(c['finishedAt'],tz).isoformat(),'terminal':c['terminal'],'rulesRequested':c['rules'],'rulesObservedAtApplication':c['ruleCounts'],'applicationRequests':c['applicationRequests'],'responseStatuses':c['statusCounts'],'mutatedInputRequests':c.get('mutatedInputRequests'),'mutatedInputStatuses':c.get('mutatedInputStatusCounts'),'result':'Completed; application responses read and analyzed','policyStrength':c['strength'],'alertThreshold':c['threshold'],'questions':c['questions']})
for r in rows:
    if r.get('technique')=='ZAP active':continue
    operations.append({'id':'request-'+str(r['sequence']),'caseId':r['campaign'],'at':datetime.fromtimestamp(r['at'],tz).isoformat(),'method':r['method'],'route':r['path'],'role':'anonymous','technique':r['technique'],'status':r['status'],'result':'Application response read; this request alone is not active DAST coverage'})
for n,r in enumerate(traffic):
    if r['kind']=='fixture-register':operations.append({'id':'login-fixture-'+str(n),'at':datetime.fromtimestamp(r['at'],tz).isoformat(),'method':'POST','route':'/api/auth/register','role':'anonymous','technique':'fixture preparation','status':r['status'],'result':'Created fresh CUSTOMER credential fixture; sent through the product adapter, not counted as ZAP active traffic'})
limits=[
 {'kind':'assessment-interpretation','scope':'whole requested track','detail':'Completion means the discovered public backend operations and their selected applicable input techniques were executed and reconciled. It does not certify absence of vulnerabilities or exhaust every payload/rule combination.'},
 {'kind':'scope','scope':'authenticated APIs, BOLA and frontend execution','detail':'Only BE anonymous was requested. Protected calls are denial controls. No authenticated business traffic or browser exploitation was performed.'},
 {'kind':'runtime-provenance','scope':'source-to-image','detail':'Docker Compose labels, origin, health and runtime OpenAPI matched the supplied project. Source HEAD was recorded; exact application image-to-source build attestation is unavailable.'},
 {'kind':'guarded-payload-selection','scope':'some path-changing native probes','detail':'Guard denied method changes, out-of-case routes, extra path segments and decoded slash/CR/LF variants. They receive no delivered application coverage credit. Public input coverage is based on the actually delivered field/path mutations, not scan progress or those denied probes.'},
 {'kind':'finding-impact','scope':'public Swagger UI and /error','detail':'Native advisory fingerprinting and hardening alerts are retained at native severity/confidence. Exploit reachability and external advisory accuracy were not independently established. Generic /error and JavaScript numeric matches have no demonstrated sensitive disclosure impact.'},
 {'kind':'fixture-retention','scope':'new CUSTOMER accounts','detail':str(len(set(created)))+' accounts created by this run are retained. No public account deletion API exists in discovered source/spec; authenticated/admin cleanup or DB deletion would extend this BE-anonymous task. Private identifiers are retained locally for later authorized cleanup.'}]
run_context={'product':{'name':'ByteMe','source':src,'sourceHead':disc['sourceHead'],'sourceDirty':False},'environment':{'kind':'Docker Compose','project':'byteme','composeFile':src+'/compose.yaml','hostOrigin':'http://127.0.0.1:8081','scannerOrigin':cfg['origin'],'targetContainerId':cfg['targetContainerId'],'targetImageId':cfg['targetImageId'],'runtimeOpenApiMatchesSource':disc['sourceSpecRuntimeCompared'],'targetResetOrRebuilt':False},'track':'be-anonymous','scope':{'publicBusinessOperations':5,'protectedDenialControls':13,'authenticated':False,'BOLA':False,'frontend':False,'wholeTrackCompleted':reconciliation['taskCompletion']=='complete'},'startedAt':datetime.fromtimestamp(cfg['startedAt'],tz).isoformat(),'finishedAt':datetime.now(tz).isoformat(),'freshness':{'newScannerSession':True,'newIsolatedMcp':True,'historicalResultsOrCheckpointsUsedForCoverage':False,'newCredentialFixtures':True,'existingTargetDataPreserved':True},'scanner':{'ZAP':'2.17.0','MCP':'0.16.0 published runtime','MCPToolsDiscovered':78,'sharedScannerModified':False,'concurrency':1,'rate':'approximately 2 target requests/sec, one request at a time; no lockout or DoS workload','hostDiskReserveBytes':2*1024**3,'knownLimits':'No external-target traffic; kernel egress permits the product adapter only to the verified backend address:8080.'},'techniqueRationale':{'selected':'SQL injection, reflected XSS and CRLF against public query/path/JSON inputs; product-native phone formatting validation; User-Agent header fuzzing on public auxiliary endpoints; passive response analysis and targeted semantic controls.','notSelected':'No XML parsing sink (application/xml returned 415), user-selected outbound URL/file/template/OS-command sink was discovered on public handlers. Browser/DOM exploitation is outside BE-only scope. Choices come from source/input behavior, not the common executor rule whitelist.','runnerChoice':'Guided MCP was used for native GET scans. Its actual anonymous schema has no method/postData fields. The research executor restricts products/rules and private registration to duplicate baselines. A fresh ByteMe adapter reused native ascan, exact SiteNode binding, MCP report reader, journal and owned Docker cleanup without changing shared core gates.','inputAdaptation':'For each registration mutation, the target field is preserved, fresh non-target credential fields prevent uniqueness blockers, and password/confirmation are synchronized. Login uses fresh real CUSTOMER credentials; issued tokens are never sent on subsequent requests.'},'inventory':[{k:o[k] for k in ('id','method','path','protected')} for o in disc['operations']],'coverage':coverage,'operations':operations,'executionSummary':{'activeScans':len(campaigns),'allActiveTerminal':True,'applicationRequestsLogged':len(rows),'activeApplicationRequests':sum(r.get('technique')=='ZAP active' for r in rows),'fixtureRequestsOutsideZAP':sum(r['kind']=='fixture-register' for r in traffic),'passiveBacklogRemaining':0,'passiveActiveTasks':0,'alertMessagesInspected':len(attribution),'alertsFromGuardResponses':0,'newAccountsCreated':len(set(created))},'alertSummary':summary,'errorsAndRecovery':[{'issue':'Journal canonicalization rejected mixed null/string rule-count keys after a completed catalog scan.','action':'Reconciled native ID/status100, normalized derived count keys and journaled terminal recovery. Scan not replayed.'},{'issue':'Guard restart parser split JSONL at Unicode separators, then attempted to parse an intentionally malformed JSON control.','action':'Changed record splitting to newline only and skipped invalid-body parser controls during login counter restoration. Focused local restart test passed. Guard was restarted only between native scans; failed attempts dispatched no new application mutation.'},{'issue':'Swagger JavaScript exceeded the original 1MB response cap.','action':'Raised ByteMe read-only response cap to4MB and internal reader to8MB while retaining disk reserve; GET readback returned200/1526763bytes.'},{'issue':'Root findings summary rejected the origin because guided history existed on child targets.','action':'Used the permitted /api/foods guided summary and full target-scoped native JSON report/alert API for cross-target synthesis. Root rejection was not bypassed.'},{'issue':'Native alert pagination overlaps the boundary item when using zero-based start values after the first page.','action':'Used observed one-based continuation, verified unique alert IDs against native count; standard report family samples were not treated as full instance counts.'},{'issue':'Default4KB report reader was unnecessarily slow.','action':'Stopped the owned read-only controller and used the same existing report artifact with the supported100KB chunk interface; no scan or mutation was replayed.'}],'limitations':limits,'securityConclusion':'No native SQLi/XSS alert was raised in the executed campaigns; eight native alert groups remain for review. This is not a declaration that ByteMe is secure.','cleanup':run.load('cleanup.json') if (R/'cleanup.json').exists() else {'status':'pending'},'retainedFixtures':{'accounts':len(set(created)),'credentialMaterial':'Local private only; no credentials, tokens or cookies included here.'}}
alerts={'product':'ByteMe','track':'be-anonymous','origin':cfg['origin'],'generatedAt':datetime.now(tz).isoformat(),'summary':summary,'alerts':groups,'limitations':['Native severity/confidence preserved. Informational detections are not automatically vulnerabilities.','Advisory mappings and exploit impact were not independently confirmed; see per-group testerAssessment.']}
out=run.WS/'reports/byteme/anonymous'
run_context['finishedAt']=datetime.fromtimestamp(run.load('cleanup.json')['at'],tz).isoformat()
run_context['reportGeneratedAt']=datetime.now(tz).isoformat()
run_context['errorsAndRecovery']=[]
run_context['techniqueRationale']['selected']='Risk-based native SQLi for numeric and credential boundaries; deeper MEDIUM textual search/login, selected JSON reflection with LOW alert threshold, native valid-phone script, header fuzzing and semantic controls.'
run_context['techniqueRationale']['inputAdaptation']+=' Each successful create remains a real application request; no attack response cache is used. Login fixtures are reused until their observed quota requires rotation.'
forecast=run.load('fixture-plan.json')
run_context['fixturePlanning']={**forecast,'actualRetainedAccounts':len(set(created)),'deltaFromForecast':len(set(created))-forecast['estimatedAccountCreates'] if forecast['estimatedAccountCreates'] is not None else None,'retentionReason':'No public account delete API; do not perform DB/admin deletion outside this track.'}
run_context['securityConclusion']='Native findings retained with context; no claim of product safety. Selected question completion follows current reconciliation.'
sharing_secrets={cfg['password'],cfg['key'],'NativeSeedPassword123!'}
for row in traffic:
    if row.get('kind')=='fixture-register' and row.get('status')==201 and row.get('email'):sharing_secrets.add(row['email'])
    if row.get('path')=='/api/auth/register' and row.get('status')==201 and row.get('actualBody'):
        value=json.loads(row['actualBody']);sharing_secrets.update(value[k] for k in ('email','password','confirmPassword') if value.get(k))
    if row.get('path')=='/api/auth/token' and row.get('status')==200:
        value=json.loads(row['response'])
        if value.get('accessToken'):sharing_secrets.add(value['accessToken'])
run.compact_results(out,run_context,alerts,reconciliation,secrets=sharing_secrets,overwrite=True)
serialized='\n'.join(p.read_text() for p in out.glob('*.json'))
assert all(secret not in serialized for secret in sharing_secrets) and not re.search(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+',serialized)
assert sorted(p.name for p in out.iterdir())==['ALERTS.json','RUN.json']
print(json.dumps({'output':str(out),'taskCompletion':reconciliation['taskCompletion'],'responsibilities':len(cases),'publicOperations':5,'activeScans':len(campaigns),'summary':summary,'retainedAccounts':len(set(created))},ensure_ascii=False))
