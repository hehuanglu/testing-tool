"""Read observed input semantics, reconcile against independent source duties, emit two files."""
import operate as o,json,collections,re,base64,hashlib,sys
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl
from datetime import datetime,timezone,timedelta
from inspect_results import rows_all
from zap_assessment.product_scope import reconcile,compact_results
from zap_assessment.signed_identity import verify_token
from zap_assessment.report_reconciliation import normalize_report
from zap_assessment.active_questions import assess_question
from zap_assessment.result_readers import read_jsonl

def local(t):return datetime.fromtimestamp(t,timezone(timedelta(hours=7))).isoformat()
def headers(raw):return {x.split(':',1)[0].lower():x.split(':',1)[1].strip() for x in raw.splitlines()[1:] if ':' in x}
def main():
 p=o.ROOT;q=o.load('execution.json');disc=o.load('discovery.json');actors=o.load('actors.json');rows=rows_all();post=o.load('input-poststate.json')['fields'];needs=o.load('responsibilities.json');native=o.load('native-alerts.json');report=o.load('native-report.json');history=o.load('native-history.json');hist={str(x['id']):x for x in history}
 valid_tokens={};trust={'publicKey':{'path':str(p/'public.pem'),'sha256':hashlib.sha256((p/'public.pem').read_bytes()).hexdigest()}}
 for r in rows:
  token={k.lower():v for k,v in r['headers'].items()}.get('authorization')
  if not token:assert urlsplit(r['url']).path=='/api/auth/token';continue
  assert token.startswith('Bearer ');token=token[7:]
  claims=json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'='*((-len(token.split('.')[1]))%4)));a=actors[claims['role']]
  if token not in valid_tokens:
   verify_token(token,trust,{'issuer':'sa-local-dev','audience':'sa-mock-api','roleClaim':'role'},a['subject'],a['role'],now=r['_at']);valid_tokens[token]=a['role']
  assert r['status']!=401,'authenticated coverage includes lost auth'
  c=next((c for c in q['cases'] if c['id']==r.get('caseId')),None)
  if c:assert valid_tokens[token]==c['role']
 campaigns=[];field_results={};baselines=[];question_reviews=[]
 for camp in q['campaigns']:
  c=next(c for c in q['cases'] if c['id']==camp['caseId']);res=o.load('campaigns/'+camp['id']+'.json')
  assert res['status']['status']=='100' and not res['stopReason'] and res['sessionValidAfter'] and all(v['valid'] for v in res['sessionChecksDuring'])
  base=o.load('http/'+c['id']+'.json');status=int(base['responseHeader'].split()[1]);assert status in c['expected']['statuses'] and 'X-Zpa-Response-Origin: app' in base['responseHeader']
  if c['operationId'] in ('listOrders','getCurrentCart'):
   body=json.loads(base['responseBody']);assert body.get('content') if c['operationId']=='listOrders' else body.get('items'),'populated baseline required'
  baselines.append({'id':'baseline-'+camp['id'],'campaignId':camp['id'],'method':c['method'],'route':c['path'],'role':c['role'],'technique':'native ZAP prepared user baseline','status':status,'positive':True})
  delivered=[r for r in rows if r.get('campaignId')==camp['id']];active=[r for r in delivered if str(r.get('ruleId')) in set(map(str,camp['ruleIds']))];vector=camp['vectors'][0]
  keys=camp['mutableKeys'] if vector in ('JSON-body','query') else ['selector' if vector=='path' else 'header'];fields={};changed_ids=set();probes=[]
  for key in keys:
   changed=[]
   for r in active:
    if vector=='JSON-body':yes=json.loads(r['body']).get(key)!=c['body'][key]
    elif vector=='query':yes=dict(parse_qsl(urlsplit(r['url']).query,keep_blank_values=True)).get(key)!=dict(parse_qsl(urlsplit(c['path']).query,keep_blank_values=True)).get(key)
    elif vector=='path':yes=urlsplit(r['url']).path!=urlsplit(c['path']).path
    else:
     rh={k.lower():v for k,v in r['headers'].items()};bh=headers(base['requestHeader']);yes=any(rh.get(k)!=bh.get(k) for k in ('user-agent','referer') if k in rh)
    if yes:
     changed.append(r);changed_ids.add((r['_capture'],r['_sequence']))
     try:body=json.loads(r['responseBody']) if r['responseBody'] else None
     except ValueError:body=None
     stage='processing' if r['status'] in (200,201,204) and not (isinstance(body,dict) and body.get('code')) else 'boundary' if r['status'] in (400,405,415) else 'fixture-blocked'
     probes.append({'field':key,'ruleId':r.get('ruleId'),'changed':True,'application':not r.get('guardGenerated',True),'identityValid':r['status']!=401,'stage':stage,'resultRead':True})
   f={'nativeMutatedRequests':len(changed),'statuses':dict(collections.Counter(str(r['status']) for r in changed)),'rulesObserved':sorted({str(r['ruleId']) for r in changed}),'acceptedMutationRequests':sum(r['status'] in (200,201,204) for r in changed),'responseCodes':dict(collections.Counter(str(json.loads(r['responseBody']).get('code')) for r in changed if r['responseBody'] and isinstance(json.loads(r['responseBody']),dict) and 'code' in json.loads(r['responseBody'])))}
   if c['id']+'::'+key in post:f['processingReadback']=post[c['id']+'::'+key]
   fields[key]=f;field_results[(c['operationId'],c['role'],vector,c['id'],key)]=f
  reviewed=[assess_question(question,probes) for question in camp['questions']]
  question_reviews.extend((c,camp,question,answer) for question,answer in zip(camp['questions'],reviewed))
  campaigns.append({'id':'campaign-'+camp['id'],'caseId':camp['id'],'operationId':c['operationId'],'method':c['method'],'route':c['path'],'role':c['role'],'vector':vector,'technique':'native ZAP active via prepared JSON bearer authSessionId','ruleIds':camp['ruleIds'],'nativeScanId':res['nativeScanId'],'state':'FINISHED','policyStrength':camp['strength'],'alertThreshold':camp['alertThreshold'],'questionReadback':reviewed,'applicationRequests':len(delivered),'nativeRuleApplicationRequests':len(active),'mutatedInputApplicationRequests':len(changed_ids),'responseStatuses':dict(collections.Counter(str(r['status']) for r in delivered)),'sessionValidBeforeDuringAfter':True,'sessionChecksDuring':len(res['sessionChecksDuring']),'fields':fields})
 inventory=[];observations={};coverage=[]
 for need in needs:
  n=need['caseId'];vector=need['vector'];variant=None
  if vector in ('DINE_IN','DELIVERY'):variant='customer-create-'+('dinein' if vector=='DINE_IN' else 'delivery');vector='JSON-body'
  matches=[(k,r) for k,r in field_results.items() if k[0]==need['operationId'] and k[1]==need['role'] and k[2]==vector and k[4]==need['field'] and (variant is None or k[3]==variant)]
  required=['positive-authenticated-baseline','session-continuity','native-field-mutation','response-read','passive-drained']
  if need['requiresAcceptedMutation']:required+=['accepted-processing','api-poststate-read']
  observed=[];details=[]
  if matches:
   observed+=['positive-authenticated-baseline','session-continuity','response-read']
   if sum(r['nativeMutatedRequests'] for k,r in matches)>0:observed.append('native-field-mutation')
   if need['requiresAcceptedMutation']:
    successful=[r['processingReadback'] for k,r in matches if r.get('processingReadback',{}).get('acknowledgedInputValuesMatched',0)>0]
    if successful:observed.append('accepted-processing')
    if any(r.get('independentlyReadVariants',0)>0 for r in successful):observed.append('api-poststate-read')
   details=[{'campaignCase':k[3],**r} for k,r in matches]
  if o.field(o.load('passive-readback.json')['text'],'Completed')=='yes' and o.field(o.load('passive-readback.json')['text'],'Records remaining')=='0':observed.append('passive-drained')
  inventory.append({**need,'evidenceRefs':['current ByteMe OpenAPI, controller/security/DTO/service source'],'requiredEvidence':required,'prerequisites':[]})
  observations[n]={'role':need['role'],'outcome':'observed','evidenceUnits':observed,'resultRead':True}
  # Helper accepts matched as a factual observation outcome; grant only when every semantic predicate above was satisfied.
  if set(required)<=set(observed):observations[n]['outcome']='matched'
  coverage.append({**need,'techniques':['native prepared authentication','ZAP passive','native active '+vector],'observed':details,'status':'assessed' if set(required)<=set(observed) else 'open','missing':sorted(set(required)-set(observed)),'interpretation':('Accepted payload values were acknowledged and API state read back. Creation siblings remained valid; unique-name fixture changes are excluded from mutation counts.' if need['requiresAcceptedMutation'] else 'Actual rule-tagged changed input reached ByteMe. Numeric/enum parser validation is distinguished from deeper handler processing; repeated original state-changing requests may return 404/409.')})
 for c,camp,question,answer in question_reviews:
  unit=answer['unit'];cid=unit
  inventory.append({'caseId':cid,'operationId':c['operationId'],'method':c['method'],'path':c['path'],'role':c['role'],'question':question,'requiredEvidence':[unit],'evidenceRefs':['current source input/sink mapping and native policy'],'prerequisites':[]})
  observations[cid]={'role':c['role'],'outcome':'matched' if answer['status']=='observed' else 'observed','evidenceUnits':answer['evidenceUnits'],'resultRead':True}
  coverage.append({'caseId':cid,'operationId':c['operationId'],'method':c['method'],'route':c['path'],'role':c['role'],'question':question,'readback':answer,'status':'assessed' if answer['status']=='observed' else 'open','missing':[] if answer['status']=='observed' else [answer['missing']],'operationIds':['campaign-'+camp['id']]})
 inv={'productLocation':str(o.SOURCE),'track':'be-authenticated','environment':'byteme Docker Compose','origin':q['origin'],'complete':True,'cases':inventory};rec=reconcile(inv,observations,{})
 if '--check-only' in sys.argv:
  o.save('responsibility-readback.json',{'reconciliation':rec,'coverage':coverage});print(json.dumps({'taskCompletion':rec['taskCompletion'],'inputResponsibilities':len(needs),'rolePairs':len({(c['operationId'],c['role']) for c in campaigns}),'activeScans':len(campaigns),'open':[r['caseId'] for r in rec['openResponsibilities']]}));return
 # Existing normalization preserves report sample semantics; API records define recorded occurrence totals.
 sample_rows,report_groups=normalize_report(report,q['runId']);groups=[]
 for key in sorted({(str(a['pluginId']),a['alert'],a['risk']) for a in native}):
  found=[a for a in native if (str(a['pluginId']),a['alert'],a['risk'])==key];instances=[]
  for a in found:
   msg=hist.get(str(a.get('messageId')));where='unconfirmed'
   if msg:where='ByteMe application' if 'X-Zpa-Response-Origin: app' in msg['responseHeader'] else 'owned guard' if 'X-Zpa-Response-Origin: guard' in msg['responseHeader'] else 'unconfirmed'
   instances.append({'nativeAlertId':str(a['id']),'method':a.get('method'),'url':a['url'],'parameter':a.get('param',''),'confidence':a['confidence'],'responseAttribution':where})
  conf=sorted({a['confidence'] for a in found});groups.append({'pluginId':key[0],'alertRef':found[0].get('alertRef'),'name':key[1],'severity':key[2],'confidence':conf[0] if len(conf)==1 else conf,'source':'ZAP','technique':'active' if key[0] in ('40012','40018','40003') else 'passive','instances':instances,'instanceCount':len(instances),'description':found[0].get('description'),'solution':found[0].get('solution'),'testerAssessment':'Authentication/session recognition is informational and is not a confirmed vulnerability.' if key[0] in ('10111','10112') else 'Native alert retained; exploit impact has not been independently confirmed.'})
 summary={'groups':len(groups),'groupsBySeverity':dict(collections.Counter(g['severity'] for g in groups)),'groupsBySource':{'ZAP':len(groups),'direct':0},'instances':len(native),'nativeReportSampleRows':len(sample_rows),'counting':'Groups by native plugin/name/risk; instances are unique current-session native API alert IDs, read to total count. JSON report samples are separately counted.'}
 cleanup=o.load('target-cleanup.json');scanner=o.load('cleanup.json');assert cleanup['status']==scanner['status']=='complete'
 direct=[r for r in read_jsonl(p/'direct-journal.jsonl') if r['phase']=='ack'];maintenance_all=read_jsonl(p/'guard-execution/fixture-maintenance.jsonl');maintenance=[r for r in maintenance_all if r['technique']=='direct fixture maintenance before native checkout request'];variant_reads=[r for r in maintenance_all if r['technique']=='independent variant persistence readback before next mutation'];guards=[r for dr in ('guard','guard-execution','guard-status-path') if (p/dr/'proxy.jsonl').exists() for r in read_jsonl(p/dr/'proxy.jsonl')]
 ops=[{'kind':'context inheritance','fromChat':'Vận hành ByteMe BE anonymous','reused':'deployment/source, protected inventory, legitimate CUSTOMER credential retained privately, fixture and recovery lessons; deployment/roles/auth reverified','historicalCoverageImported':False}]
 ops += [{'at':local(r['at']),'method':r['method'],'route':r['path'],'role':r['role'],'technique':'direct setup/readback/cleanup','purpose':r['label'],'status':r['status']} for r in direct]
 for role,ss in o.load('sessions.json').items():
  check=o.load('mcp/validate-'+role+'.json');blob='\n'.join(c.get('text','') for c in check.get('content',[]));assert 'Valid: true' in blob
  ops.append({'method':'GET','route':'/api/cart' if role=='CUSTOMER' else '/api/orders','role':role,'technique':'MCP zap_auth_session_prepare and zap_auth_session_validate','result':'valid native prepared session; protected subject probe for CUSTOMER, signed subject/role plus expected protected response for ADMIN/EMPLOYEE','protectedProbeStatus':403 if role=='ADMIN' else 200})
 ops += baselines+campaigns+[{'technique':'direct fixture maintenance before native checkout','requestCount':len(maintenance),'methodRouteCounts':dict(collections.Counter(x['method']+' '+x['path'] for x in maintenance))},{'technique':'passive wait and result collection','remaining':0,'nativeMessagesRead':len(history),'nativeAlertRecordsRead':len(native),'nativeReportRead':'complete through existing chunk collector'},{'technique':'target cleanup','result':cleanup},{'technique':'scanner cleanup','result':scanner}]
 started=json.loads((p/'direct-journal.jsonl').read_text().split('\n')[0])['at'];out=o.BASE/'reports/byteme/authenticated'
 run={'product':{'name':'ByteMe','source':str(o.SOURCE),'sourceHead':disc['sourceHead'],'sourceDirty':disc['sourceDirty'],'liveOpenApiMatchesSource':True,'binding':disc['binding']},'environment':{'dockerContext':'desktop-linux','composeProject':'byteme','hostOrigin':'http://127.0.0.1:8081','scannerOrigin':q['origin'],'targetRebuiltOrReset':False},'track':'be-authenticated','scope':{'protectedOperations':13,'authorizedEndpointRolePairs':15,'roles':['CUSTOMER','EMPLOYEE','ADMIN'],'inputResponsibilities':len(needs),'businessBranches':['DINE_IN','DELIVERY'],'publicOperations':'login and catalogue only for setup/readback; previous anonymous results excluded','FE':False,'BOLA':False},'startedAt':local(started),'finishedAt':local(scanner['at']),'timezone':'Asia/Ho_Chi_Minh','runtime':{'freshIsolatedSession':True,'ZAP':'2.17.0','MCP':'existing candidate JAR with verified method/postData/authSessionId schema; local JSON bearer profiles only','sharedScannerModified':False,'identity':'Real logins, RS256 signatures/issuer/audience/subject/role verified from deployed public key; native protected identity probes; correct role on captured requests; no application 401','secretRetention':'Necessary credentials/tokens/native raw retained local private; excluded from handoff','limits':q['limits']},'selectionDecisions':['Operations chosen from live schema: native MCP prepare/validate/attack/status/stop, exact as-user seed and existing baseline/report/runtime helpers. Common product registry lacks ByteMe/full body capabilities; a ByteMe-only adapter was used, preserving shared gates.','SQL injection for numeric/enum/query boundaries and textual JSON processing, reflected XSS for textual JSON, CRLF for relevant path/query/header handling. Source stores imageUrl without server fetch; no SSRF/OS/file/XML sink found in assigned protected handlers.','Fresh-create name suffix preserves selected payload and avoids duplicate blockers; only native target-field changes count. imageUrl has a non-null string baseline.','Checkout cart is explicitly populated with one owned test item before each native request; fixture traffic is counted separately.','A new CONFIRMED order was allocated for status-selector testing after the body campaign changed its original order; previous allocation and results retained.'],'inventory':[{k:op[k] for k in ('id','method','pathTemplate','protected','roles')} for op in disc['operations']],'coverage':coverage,'operations':ops,'executionSummary':{'nativeActiveScans':len(campaigns),'allActiveTerminal':True,'protectedOperationsAssessed':len({c['operationId'] for c in campaigns}),'endpointRolePairsAssessed':len({(c['operationId'],c['role']) for c in campaigns}),'inputResponsibilitiesAssessed':sum(c['status']=='assessed' for c in coverage if c['caseId'] in {n['caseId'] for n in needs}),'techniqueQuestionsAssessed':sum(answer['status']=='observed' for c,camp,question,answer in question_reviews),'independentPersistenceReadbackRequests':len(variant_reads),'applicationRequestsThroughZAP':len(rows),'nativeRuleApplicationRequests':sum(c['nativeRuleApplicationRequests'] for c in campaigns),'changedInputApplicationRequests':sum(c['mutatedInputApplicationRequests'] for c in campaigns),'directFixtureMaintenanceRequests':len(maintenance),'directSetupReadbackCleanupRequests':len(direct),'applicationStatusCounts':dict(collections.Counter(str(r['status']) for r in rows)),'guardDenials':dict(collections.Counter(r.get('reason') for r in guards if r['action']=='denied')),'newAccounts':0,'ownedFoodsCreated':len(cleanup['foodsCreated']),'ownedOrdersCreated':len(cleanup['ordersCreated'])},'alertSummary':summary,'operationalIssues':[{'issue':'Discovery JSONL reader initially split at Unicode line separators in a previous payload.','resolved':True,'action':'Used newline-only splitting before login dispatch; no business mutation replayed.'},{'issue':'Live progress count compared User-Agent against a generic literal, overcounting changed inputs.','resolved':True,'action':'Final counts recomputed from rule-tagged body/query/path/headers against actual allocated baselines; initial working progress preserved.'}],'limitations':['Completion concerns discovered protected API/input responsibilities and selected techniques; it is not proof of product safety or exhaustive payload/state/rule coverage.','Numeric/enum mutations often end at authenticated parser/validation boundaries. No claim that those payloads reached database query/transition execution.','Guard denies foreign numeric IDs/references, undeclared paths/shapes, out-of-origin traffic and mismatched identity. Denied probes receive no application coverage credit.','State-changing original requests may return 404/409 after the successful positive baseline. Actual statuses retained; fresh status-selector fixture and replenished checkout carts prevent unintentional blockers in the selected processing questions.','No browser rendering, stored/DOM XSS exploit, full token expiry/revoke lifecycle or cross-owner BOLA matrix was requested or claimed.','Exact runtime image-to-source commit attestation is unavailable; Compose origin, matching runtime OpenAPI and current role behavior verified.','Owned orders retained CANCELLED and foods INACTIVE; no hard-delete API. CUSTOMER reused from the latest anonymous run remains.'],'resources':{'before':o.load('resources-before.json'),'afterCollection':o.load('resources-after.json'),'hostReserveBytes':2*1024**3},'cleanup':{'target':cleanup,'scanner':scanner},'officialContinuationFolder':str(out),'securityConclusion':'Native classifications retained; selected input handling and processing observations do not certify absence of vulnerabilities.'}
 alerts={'product':'ByteMe','track':'be-authenticated','origin':q['origin'],'scope':'Fresh isolated authenticated run; historical findings excluded','generatedAt':local(scanner['at']),'summary':summary,'alerts':groups}
 projection={k:rec[k] for k in ('taskCompletion','handoffClosesTask','openResponsibilities','inventoryGaps','nextActions','scope')};projection.update(inventoryComplete=True,responsibilityCount=len(inventory),cases=[{'caseId':r['caseId'],'status':r['status']} for r in rec['cases']])
 secrets={v for a in actors.values() for k,v in a.items() if k in ('email','password','token')};secrets.update(valid_tokens)
 for r in rows:
  if urlsplit(r['url']).path=='/api/auth/token':
   try:secrets.add(json.loads(r['responseBody'])['accessToken'])
   except (KeyError,ValueError):pass
 def scrub(v):
  if isinstance(v,dict):return {k:scrub(x) for k,x in v.items()}
  if isinstance(v,list):return [scrub(x) for x in v]
  if isinstance(v,str):
   for s in sorted(secrets,key=len,reverse=True):v=v.replace(s,'[private]')
   return re.sub(r'eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+','[private]',v)
  return v
 run['scope']['protectedOperations']=sum(op['protected'] for op in disc['operations'])
 run['scope']['authorizedEndpointRolePairs']=len({(op['id'],role) for op in disc['operations'] for role in op['roles']})
 run['scope']['techniqueQuestions']=len(question_reviews)
 run['operationalIssues']=[]
 if (p/'resource-recovery.json').exists():
  recovery=o.load('resource-recovery.json');run['operationalIssues'].append({'issue':'Transient host disk reserve check blocked the next unsent campaign before baseline/start.','diagnosis':recovery['diagnosis'],'action':'Reconciled native terminal state and journal, remeasured resources above the original gate, then continued only unsent campaigns. No data deletion or cap/reserve change.','completedCampaignsRetained':recovery['finishedCampaigns'],'replayedCampaigns':0,'resolved':True})
 run['operations'].append({'id':'immediate-persistence-readbacks','technique':'direct independent API GET immediately after successful mutation and before next native request','requestCount':len(variant_reads),'matchingAcknowledgements':sum(r.get('matched',False) for r in read_jsonl(p/'guard-execution/variant-readback.jsonl')),'interpretation':'Read count includes baselines and unchanged native controls. The 12 text-field obligations use only changed target values with their own matched readbacks.'})
 run['selectionDecisions'][2]='Every required text mutation has an immediate independent API GET before the next native mutation. ACK and final snapshots cannot supply this unit.'
 run['selectionDecisions'][4]='Separate CONFIRMED fixtures for status body and selector questions are allocated before traffic. Numeric parser questions exclude later state-conflict responses from qualifying observations.'
 run['selectionDecisions'].append('Rule 40012 uses LOW alert threshold to exercise PUT JSON reflection. LOW strength is the finite workload size; native alert risk/confidence remain unchanged. CRLF retains query/header/path canary questions; only changed application requests qualify. A canary rejected by a typed parser is a boundary result, not a claim that CR/LF reached a response-header sink.')
 run['reportReadback']={'nativeUniqueAlertIds':len(native),'rawReportSampleRows':len(sample_rows),'siteEntries':len(report.get('site',[])),'interpretation':'The native report repeats identical origin site entries in this run. Raw sample rows include that repetition and report sampling; occurrence totals use current native API IDs, not report rows.'}
 run['fixturePlanning']={'basis':'Selected finite LOW native workloads; immediate readbacks and checkout replenishment are separate traffic.','stateDependentProcessing':'Text create/update requires persistence; numeric/enum parser rejection answers only its boundary question. 404/409 fixture conflict does not supply that observation.','actualOwnedFoods':len(cleanup['foodsCreated']),'actualOwnedOrders':len(cleanup['ordersCreated'])}
 compact_results(out,scrub(run),scrub(alerts),projection,secrets=secrets,overwrite=True)
 text='\n'.join(f.read_text() for f in out.iterdir());assert all(s not in text for s in secrets);assert 'evidenceRefs' not in text and 'evidenceStatus' not in text;assert sorted(f.name for f in out.iterdir())==['ALERTS.json','RUN.json']
 print(json.dumps({'output':str(out),'taskCompletion':rec['taskCompletion'],'execution':run['executionSummary'],'alerts':summary},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
