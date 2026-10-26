"""Derived private-local handoff, preserving native reports and classification."""
from collections import Counter,defaultdict
import hashlib,json,re
from pathlib import Path
from urllib.parse import urlsplit
from .anonymous_product import save
from .anonymous_runner import verify
from .discovery_handoff import clean,safe_url


def redacted(v):
 if v is None:return None
 v=clean(v)
 return re.sub(r'[A-Za-z0-9_.+\-]+@example\.test','[run-email]',v)


def read(path):return json.loads(Path(path).read_bytes())


def summarize(root):
 root=Path(root);n=root/'native';verification=verify(n);alerts=read(n/'alerts-native.json')['alerts'] if (n/'alerts-native.json').exists() else []
 messages={str(m['id']):m for m in read(n/'messages.json')['messages']} if (n/'messages.json').exists() else {}
 native=read(n/'reports/backend.json') if (n/'reports/backend.json').exists() else {};report_ids=set();report_counts=Counter()
 for site in native.get('site',[]):
  for a in site['alerts']:
   report_counts[str(a['pluginid'])]+=len(a.get('instances',[]));report_ids.update(str(v['id']) for v in a.get('instances',[]) if 'id' in v)
 groups={};excluded=[];all_counts=Counter();missing=[]
 for index,a in enumerate(alerts):
  mid=str(a.get('messageId'));msg=messages.get(mid);rid=str(a['pluginId']);all_counts[rid]+=1
  if not msg:missing.append(str(a['id']));continue
  if 'x-zpa-response-origin: app' not in msg.get('responseHeader','').lower():
   excluded.append({'nativeAlertId':a['id'],'nativeRuleId':rid,'messageId':mid,'reason':'guard-generated or unverified response attribution','evidence':str(n/'alerts-native.json')+'#/alerts/'+str(index)});continue
  key=(rid,a['name'],a['risk'],a['confidence'])
  if key not in groups:
   groups[key]={'findingId':'AN-ZAP-'+rid,'source':'ZAP','nativeRuleId':rid,'nativeSeverity':a['risk'],'nativeConfidence':a['confidence'],'severity':a['risk'],'confidence':a['confidence'],'name':redacted(a['name']),'description':redacted(a['description']),
    'impact':{'verification':'unverified','description':'Dấu hiệu theo native rule; chưa chứng minh khai thác hoặc ảnh hưởng dữ liệu.'},'remediation':redacted(a.get('solution')),
    'expectedBehavior':'Không xuất hiện dấu hiệu theo rule trên response ứng dụng. Informational alerts chỉ mô tả surface/session, không tự là lỗ hổng.',
    'observedBehavior':'Xem native evidence và vị trí từng instance. Guard responses được tách riêng.',
    'reproduction':'Đọc method/path/parameter và native request/response private của instance; tái chạy entry cùng fixture mới, không replay mutation trên dữ liệu cũ.',
    'retest':'Đối chiếu cùng cases/rules trên build sửa được PM chọn; hiện chưa có fixed product build.',
    'agentTriage':{'status':'pending-independent-review','exploitConfirmed':False},'instances':[],'evidenceRefs':[]}
  g=groups[key];uri=safe_url(a['url']);status=int(msg['responseHeader'].split()[1])
  instance={'nativeAlertId':str(a['id']),'messageId':mid,'method':a['method'],'url':redacted(uri),'path':urlsplit(uri).path,'parameter':redacted(a.get('param')),'attack':redacted(a.get('attack')),'evidence':redacted(a.get('evidence')),'status':status,'responseOrigin':'app-via-guard','nativeReportDetail':str(a['id']) in report_ids,'messageDetailAvailable':True,'ruleAttribution':{'activeNativeHeader':next((x.split(':',1)[1].strip() for x in msg['requestHeader'].split('\r\n') if x.lower().startswith('x-zap-scan-id:')),None),'passiveMessageProducer':'unavailable unless correlated by campaign/HTTP evidence'},'evidenceRef':str(n/'alerts-native.json')+'#/alerts/'+str(index),'httpEvidenceRef':str(n/'messages.json')+'#message-id='+mid}
  g['instances'].append(instance);g['evidenceRefs'].append({'path':str(n/'alerts-native.json'),'jsonPointer':'/alerts/'+str(index),'sha256':hashlib.sha256((n/'alerts-native.json').read_bytes()).hexdigest(),'access':'private-local'})
  if rid in ('90022','10023') and urlsplit(uri).path=='/docs-json' and status==200:
   g['agentTriage']['documentationMatch']='Evidence khớp mô tả lỗi trong schema HTTP200; chưa chứng minh actual server error hoặc stack trace. Giữ native severity, reviewer disposition pending.'
   g['impact']['description']='Cần phân biệt nội dung tài liệu API với lỗi runtime; instance docs HTTP200 chưa chứng minh lỗi server.'
 result=list(groups.values())
 for g in result:g['instanceCount']=len(g['instances'])
 reconcile={'apiOccurrencesByRule':dict(all_counts),'nativeReportDetailsByRule':dict(report_counts),'apiAlertCount':len(alerts),'reportDetailCount':sum(report_counts.values()),'reportDetailMissingButMessageAvailable':sum(not x['nativeReportDetail'] for g in result for x in g['instances']),'missingMessageRefs':missing,'excludedGuardOrUnattributed':excluded,'meaning':'Native API occurrence export supplements capped native report instances. No invented response detail or suppressed snapshot-only occurrence.'}
 return {'verification':verification,'alerts':result,'reconciliation':reconcile,'excluded':excluded}


def handoff(root):
 root=Path(root).resolve();out=root/'technical';out.mkdir(mode=0o700,exist_ok=True)
 runs=[p for p in sorted(root.glob('product-*')) if (p/'native/manifest.json').exists()];interrupts=[p for p in sorted(root.glob('interrupted-*')) if (p/'native/manifest.json').exists()]
 data={p.name:summarize(p) for p in [*runs,*interrupts]};selected=runs[-1] if runs else None
 groups=data[selected.name]['alerts'] if selected else [];source='ZAP public business case via core.sendRequest'
 if selected and (selected/'native/http/login-minimum.json').exists():
  reg=read(selected/'native/http/register-minimum.json');login=read(selected/'native/http/login-minimum.json');ok=reg['responseHeader'].split()[1]=='201' and login['responseHeader'].split()[1]=='200'
  if ok:groups.append({'findingId':'AN-BUSINESS-PASSWORD-MINIMUM','source':source,'nativeRuleId':None,'nativeSeverity':None,'nativeConfidence':None,'severity':'Medium','confidence':'High (observed case)','name':'Đăng ký và đăng nhập chấp nhận mật khẩu một ký tự','description':'Fixture mới đăng ký với password và confirmation dài một ký tự, nhận201; login cùng password nhận200. Không phải native ZAP vulnerability rule.','impact':{'verification':'acceptance-observed, exploit-unverified','description':'Mật khẩu rất ngắn làm giảm khả năng chống đoán mật khẩu; chưa đo hiệu quả lockout hoặc khai thác tài khoản khác.'},'remediation':'Chọn và kiểm chính sách độ dài/chất lượng mật khẩu phù hợp product; giữ thông báo lỗi chung và kiểm cơ chế hạn chế login trên fixture riêng.','agentTriage':{'status':'pending-independent-review','severityAssignedBy':'agent','exploitConfirmed':False},'expectedBehavior':'Product nên có chính sách password được xác định; source hiện minLength1, case kiểm đúng feature đó.','observedBehavior':'Registration201 + login200 với một ký tự qua ZAP, không gửi token tiếp vào workload.','reproduction':'Entry product-run tạo email thuộc run; cases register-minimum rồi login-minimum. Raw bodies/token private.','retest':'Cùng cases trên fixed build được chọn; chưa có build sửa.','instanceCount':1,'instances':[{'method':'POST','path':'/api/auth/register và /api/auth/login','statuses':[201,200],'responseOrigin':'app-via-guard'}],'evidenceRefs':[{'path':str(selected/'native/http'/name),'sha256':hashlib.sha256((selected/'native/http'/name).read_bytes()).hexdigest(),'access':'private-local'} for name in ['register-minimum.json','login-minimum.json']]})
 comparisons=[]
 if len(runs)>=2:
  a,b=runs[-2:];pa=read(a/'native/PLAN.json');pb=read(b/'native/PLAN.json')
  def logical(p):return [(c['id'],c['operationId'],c['method'],c['category'],c['expected']['statuses']) for c in p['cases']]
  same=read(a/'native/implementation-pins.json')==read(b/'native/implementation-pins.json')
  ca=read(a/'native/COVERAGE.json')['cases'];cb=read(b/'native/COVERAGE.json')['cases']
  observed=lambda cs:[(c['caseId'],c['observed'].get('status'),c['observed']['matched']) for c in cs]
  comparisons.append({'runs':[a.name,b.name],'sameImplementation':same,'sameLogicalCases':logical(pa)==logical(pb),'compatibleObservedCoverage':observed(ca)==observed(cb),'sameRulesAndVectors':pa['campaigns']==pb['campaigns'],'sameTargetBuild':pa['targetBinding']==pb['targetBinding'],'freshRunIds':pa['runId']!=pb['runId'],'freshFixtures':read(a/'fixtures.json')['actorId']!=read(b/'fixtures.json')['actorId'],'notRemediationProof':True})
 controls=[read(p/'CONTROL_RESULT.json') for p in sorted(root.glob('controls-*')) if p.is_dir() and (p/'CONTROL_RESULT.json').exists()]
 qualification={'repeatability':comparisons,'interruptedRuns':[{'run':p.name,'result':read(p/'RESULT.json'),'stop':read(p/'native/STOP_ACCOUNTING.json')} for p in interrupts],
 'selectedTechniqueControls':[{'functionalQualification':v['functionalQualification'],'ruleAlertCounts':v['ruleAlertCounts'],'sourceSha256':v['sourceSha256']} for v in controls],
 'fixedProductBuildRegression':{'status':'pending','dependency':'PM selects an existing fixed finalsource build with image/source provenance and same logical scope. No product logic was modified; no build B invented.'},'independentReview':'pending, no reviewer approval created'}
 execution='completed' if selected and read(selected/'RESULT.json')['executionStatus']=='completed' else 'partial'
 summary={'schemaVersion':'pm-alerts/1.0','product':'finalsource-zap-test backend','run':selected.name if selected else None,'executionStatus':execution,'evidenceStatus':'complete' if selected and data[selected.name]['verification']['evidenceComplete'] else 'incomplete','securityVerdict':'requires-triage','cleanupStatus':read(selected/'RESULT.json')['cleanupStatus'] if selected else 'pending','gateDecision':'review_required' if execution=='completed' else 'block','trackQualification':'partial; fixed-product regression and independent review pending',
 'scope':{'track':'be-anonymous','public':['GET health','POST login/register: success/validation/boundary/duplicate/minimum-password'], 'protected':'16 exact method/path anonymous denial controls, separate direct owned-state oracle','documentation':'GET docs-json separate','protocol':'HEAD health / OPTIONS CORS separate','activeRules':[40012,40018],'activeVectors':'JSON-body; locked run email; login password and register fullName only; other fields blocked/unexercised'},
 'grouping':'Source/native-rule/name/severity/confidence; counts use selected fresh run, repeats are separate evidence, not added bugs.',
 'summary':{'groupsBySeverity':dict(Counter(g['severity'] for g in groups)),'groupsBySource':dict(Counter(g['source'] for g in groups)),'alertGroups':len(groups),'nativeInstances':sum(g['instanceCount'] for g in groups if g['source']=='ZAP'),'businessCaseFindings':sum(g['source']!= 'ZAP' for g in groups)},'alerts':groups,
 'limitations':['Native medium/low docs error matches are HTTP200 schema text, not demonstrated runtime error/exploit.','Active email/other JSON fields are denied by guard; no all-vector or all-rule coverage claim.','Denied mutations have post-state for run-owned account/goals/transaction list only; no global database nonmutation proof. Transaction denial body omits category_id because there is no category-create API.','Login rate-limit/lockout and timing are not asserted; no brute-force campaign.','Only finalsource test qualified; generic metadata/backend-only unit proof does not prove arbitrary products or HTTPS/GraphQL/SOAP execution.','Raw reports/HTTP contain credentials/tokens/PII; private local. This JSON reduces data and points to private evidence; technical folder is not a public self-contained bundle.','Fixed product build regression and independent review pending.'],
 'rawEvidence':[{'run':p.name,'path':str(p/'native'),'access':'private-local','integrity':data[p.name]['verification']} for p in [*runs,*interrupts]]}
 for p in [*runs,*interrupts]:save(out,'reconciliation-'+p.name+'.json',data[p.name]['reconciliation'])
 save(root,'ALERTS.json',summary);save(out,'QUALIFICATION.json',qualification)
 save(out,'EVIDENCE_INDEX.json',{'findings':[{'id':g['findingId'],'refs':g['evidenceRefs']} for g in groups],'runs':summary['rawEvidence'],'excluded':{k:v['excluded'] for k,v in data.items()},'privateRaw':True})
 return {'alerts':str(root/'ALERTS.json'),'groups':summary['summary'],'productRuns':len(runs),'interruptedRuns':len(interrupts),'qualification':'partial'}
