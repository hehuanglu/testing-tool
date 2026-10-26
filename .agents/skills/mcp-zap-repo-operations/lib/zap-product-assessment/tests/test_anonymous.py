import copy,hashlib,http.client,json,tempfile,threading,time,unittest
from pathlib import Path
from unittest.mock import Mock,patch
from test_discovery_transport import modern
from test_research import BIND
from zap_assessment.anonymous import compile_plan,validate_plan,expected_response,validate_exports
from zap_assessment.anonymous_guard import authorize,serve
from zap_assessment.anonymous_runner import AnonymousRun
from zap_assessment.evidence import read_report,EvidenceInvalid
from zap_assessment.anonymous_product import admit_recipe,login_policy_cases,setup
from zap_assessment.research_product import SURFACE


def plan():
 d=modern();d['auth']=None;d['fixtures']=[];d['product']['origins']=d['product']['origins'][:1];d['product']['origins'][0]['url']='http://127.0.0.1:9001'
 d['operations']=[{**d['operations'][0],'id':i,'method':m,'pathTemplate':p,'protected':prot,'input':{'query':[]}} for i,m,p,prot in [('read','GET','/data',False),('write','POST','/session',False),('deny','PATCH','/things/{id}',True)]]
 pr={'environment':d['product']['environment'],'targetBinding':BIND,'scannerOrigins':['http://127.0.0.1:9001'],'directOrigins':[]}
 cases=[{'id':i,'operationId':o,'method':m,'path':p,'body':b,'category':cat,'fixtureRefs':[] if i=='r' else ['f'],'expected':{'statuses':[st],'contentType':'application/json','equals':{},'present':[]}} for i,o,m,p,b,cat,st in [('r','read','GET','/data',None,'public-success',200),('w','write','POST','/session',{'email':'owned@example.test','field':'marker'},'public-validation',400),('d','deny','PATCH','/things/owned',{'field':'x'},'protected-denial',401)]]
 return compile_plan(d,live_binding=BIND,observed_transport=pr,run_id='test-run',cases=cases,campaigns=[{'id':'active','caseId':'w','ruleIds':[40012,40018],'vectors':['JSON-body'],'mutableKeys':['field'],'maxForwarded':20,'strength':'LOW','baselineSeed':True}],authority={'environment':d['product']['environment'],'source':'unit authority','discoveryRead':True,'active':True,'publicMutation':True,'deniedMutation':True,'fixtureSetup':True},fixtures=[{'id':'f','runId':'test-run','ownership':'test owned','preparationEvidence':['test.json'],'cleanup':'retention'}],dispositions=[{'operationId':o['id'],'disposition':'protected-denial' if o['protected'] else 'public-exercise','reason':'unit'} for o in d['operations']])

class AdmissionTests(unittest.TestCase):
 def test_recipe_surface_protection_and_environment_rejected_before_setup(self):
  extra={('GET','/docs-json'),('HEAD','/api/health'),('OPTIONS','/api/auth/login')}
  public={('GET','/api/health'),('POST','/api/auth/login'),('POST','/api/auth/register')}|extra
  doc={'product':{'environment':'finalsource-zap-test'},'operations':[{'method':m,'pathTemplate':p,'protected':(m,p) not in public} for m,p in sorted(SURFACE|extra)]}
  admit_recipe(doc)
  for change in [lambda d:d['operations'].append({'method':'POST','pathTemplate':'/new','protected':False}),lambda d:d['operations'].pop(),lambda d:d['product'].update(environment='other'),lambda d:d['operations'][0].update(protected=not d['operations'][0]['protected'])]:
   d=copy.deepcopy(doc);change(d)
   with patch('zap_assessment.anonymous_product.validate_discovery'),patch('zap_assessment.anonymous_product.Product') as product,patch('zap_assessment.anonymous_product.binding') as live,self.assertRaisesRegex(ValueError,'no mutation permitted'):
    setup(d,Path('/unused'),'test-run')
   product.assert_not_called();live.assert_not_called()
 def test_login_policy_cases_have_finite_failures_then_correct_password_denial(self):
  doc={'operations':[{'method':'POST','pathTemplate':'/api/auth/login','protected':False,'id':'login'}]}
  cases=login_policy_cases(doc,'run@example.test','correct-private',{'maxAttempts':5})
  self.assertEqual(len(cases),6);self.assertEqual(len({c['id'] for c in cases}),6)
  self.assertTrue(all(c['body']['password']=='wrong-run-policy-password' for c in cases[:-1]));self.assertEqual(cases[-1]['body']['password'],'correct-private')
  c=cases[-1];message={'responseHeader':'HTTP/1.1 401 Unauthorized\r\nContent-Type: application/json\r\nX-Zpa-Response-Origin: app\r\n','responseBody':json.dumps({'success':False,'statusCode':401,'message':'Incorrect email or password.','path':'/api/auth/login'})}
  self.assertTrue(expected_response(c,message)['matched'])
  self.assertFalse(expected_response(c,{**message,'responseBody':'{}'})['matched'])
  for count in [0,21]:
   with self.assertRaises(ValueError):login_policy_cases(doc,'run@example.test','private',{'maxAttempts':count})
 def test_implementation_pin_covers_direct_adapter_dependency(self):
  from zap_assessment.anonymous_runner import implementation_pin
  files={Path(p).name for p in implementation_pin()}
  self.assertTrue({'research_product.py','research.py','discovery_handoff.py'}<=files)
 def test_backend_only_without_auth(self):
  p=plan();self.assertIsNone(p['discovery']['auth']);self.assertNotIn('actor',p);validate_plan(p,BIND,p['transportBinding'])
 def test_public_get_needs_no_credential_fixture_or_mutation_authority(self):
  p=plan();p['cases']=p['cases'][:1];p['campaigns']=[];p['fixtures']=[]
  for row in p['dispositions']:
   if row['operationId']!='read':row.update(disposition='not-run',reason='Read-only subset')
  p['authority'].update(active=False,publicMutation=False,deniedMutation=False,fixtureSetup=False)
  validate_plan(p,BIND,p['transportBinding']);self.assertNotIn('actor',p);self.assertIsNone(p['discovery']['auth'])
 def test_authority_binding_inventory_ids_conflicts_fail_closed(self):
  changes=[lambda p:p['authority'].update(publicMutation=False),lambda p:p['authority'].update(deniedMutation=False),lambda p:p['authority'].update(active=False),lambda p:p.update(origin='http://outside:9001'),lambda p:p['targetBinding'].update(address='other'),lambda p:p['cases'][2].update(path='/things/{id}'),lambda p:p['cases'][2].update(fixtureRefs=['missing']),lambda p:p['cases'][2]['expected'].update(statuses=[200]),lambda p:p['discovery']['conflicts'].append({'description':'conflict','blocking':True,'evidenceRefs':['source']}),lambda p:p['cases'][0].update(headers={'Authorization':'private'}),lambda p:p['dispositions'].pop(),lambda p:p['discovery']['operations'][0].update(semantics='changed'),lambda p:p['fixtures'][0].update(preparationEvidence=[]),lambda p:p['limits'].update(concurrency=2),lambda p:p['limits'].update(reserveBytes=1),lambda p:p.update(notAfter=p['lockedAt']+99999)]
  for mutate in changes:
   p=plan();mutate(p)
   with self.subTest(mutate=mutate),self.assertRaises(ValueError):validate_plan(p,BIND,p['transportBinding'])
 def test_unsupported_vector_and_origin_proof(self):
  p=plan();p['campaigns'][0]['vectors']=['headers']
  with self.assertRaisesRegex(ValueError,'vector'):validate_plan(p,BIND,p['transportBinding'])
  p=plan();pr=copy.deepcopy(p['transportBinding']);pr['scannerOrigins']=[]
  with self.assertRaisesRegex(ValueError,'independently bound'):validate_plan(p,BIND,pr)
 def test_expected_app_json_semantics(self):
  c=plan()['cases'][0];c['expected']['equals']={'/ok':True};m={'responseHeader':'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Zpa-Response-Origin: app\r\n','responseBody':'{"ok":true}'}
  self.assertTrue(expected_response(c,m)['matched'])
  for new in [{**m,'responseHeader':m['responseHeader'].replace(' app',' guard')},{**m,'responseBody':'<html>login</html>'},{**m,'responseBody':'{"ok":false}'},{**m,'responseHeader':m['responseHeader'].replace('application/json','text/html')}]:self.assertFalse(expected_response(c,new)['matched'])

class GuardTests(unittest.TestCase):
 def test_scope_body_identity_cookie_budgets(self):
  p=plan();mode={'caseId':'w','campaignId':'active'};headers={'Host':'127.0.0.1:9001','Content-Type':'application/json'}
  def auth(**kw):return authorize(kw.get('p',p),mode,kw.get('method','POST'),kw.get('url',p['origin']+'/session'),kw.get('headers',headers),kw.get('body',b'{"email":"owned@example.test","field":"payload"}'),kw.get('now',time.time()))
  self.assertEqual(auth()[1]['id'],'active')
  for kw in [{'method':'DELETE'},{'url':'http://outside.test/session'},{'body':b'{"email":"other@example.test","field":"x"}'},{'headers':{**headers,'Authorization':'private'}},{'headers':{**headers,'Cookie':'identity=x'}},{'body':b'{"email":"owned@example.test","field":"Bearer private"}'},{'now':p['notAfter']+1},{'body':b'x'*20000},{'url':p['origin']+'/session?token=x'}]:
   with self.subTest(kw=kw),self.assertRaises(ValueError):auth(**kw)
  p['anonymousState']['cookies']={'csrf':{'identity':False,'evidenceRefs':['contract']}};auth(headers={**headers,'Cookie':'csrf=opaque'})
 def test_real_proxy_redirect_size_cookie_stop_and_duplicate(self):
  from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
  class App(BaseHTTPRequestHandler):
   def log_message(self,*a):pass
   def do_GET(self):
    if self.path=='/slow':time.sleep(.2)
    self.send_response(302 if self.path=='/redirect' else 200);self.send_header('Content-Type','application/json');self.send_header('Set-Cookie','identity=private');self.send_header('Location','http://outside.test/');self.end_headers();self.wfile.write(b'x'*100 if self.path=='/big' else b'{"ok":true}')
  app=ThreadingHTTPServer(('127.0.0.1',0),App);threading.Thread(target=app.serve_forever,daemon=True).start()
  try:
   with tempfile.TemporaryDirectory() as t:
    root=Path(t);p=plan();p['origin']='http://127.0.0.1:'+str(app.server_port);p['targetBinding']['address']='127.0.0.1';p['limits']['responseBytes']=20;p['limits']['requestTimeoutSeconds']=.05;base=p['cases'][0];p['cases']=[{**base,'id':path,'path':'/'+path} for path in ['data','redirect','big','slow']]
    (root/'plan').write_text(json.dumps(p));(root/'mode').write_text(json.dumps({'caseId':'data'}));guard=serve(root/'plan',root/'mode',root/'capture',port=0);threading.Thread(target=guard.serve_forever,daemon=True).start()
    def get(path):
     c=http.client.HTTPConnection('127.0.0.1',guard.server_port);c.request('GET',p['origin']+'/'+path,headers={'Host':p['origin'].split('//')[1]});r=c.getresponse();v=(r.status,dict(r.headers),r.read());c.close();return v
    response=get('data');self.assertEqual(response[0],200);self.assertNotIn('Set-Cookie',response[1]);self.assertEqual(response[1]['X-Zpa-Response-Origin'],'app');self.assertEqual(get('data')[0],403)
    for path in ['redirect','big']:
     (root/'mode').write_text(json.dumps({'caseId':path}));self.assertEqual(get(path)[0],403)
    (root/'mode').write_text(json.dumps({'caseId':'slow'}));self.assertEqual(get('slow')[0],502)
    (root/'STOP').write_text('stop');self.assertEqual(get('data')[0],403)
    rows=[json.loads(x) for x in (root/'capture/proxy.jsonl').read_text().splitlines()];self.assertTrue(any(x['action']=='app-response-blocked' for x in rows));self.assertTrue(any(x.get('reason')=='response-size' for x in rows));guard.shutdown();guard.server_close()
  finally:app.shutdown();app.server_close()

class RecoveryTests(unittest.TestCase):
 def test_lost_active_ack_no_duplicate_start(self):
  with tempfile.TemporaryDirectory() as t:
   r=AnonymousRun.__new__(AnonymousRun);r.p=plan();r.out=Path(t);r.ops=[];r.current=Mock();r.mode=Mock();r.j=Mock();r.bind_baseline=Mock();r.rt=Mock();r.rt.capture.glob.return_value=[];r.cancelled=threading.Event();calls=[];listed=0
   def engine(comp,kind,name,args=None):
    nonlocal listed
    calls.append(name)
    if name=='scanners':return {'scanners':[{'id':40012,'enabled':'true'},{'id':40018,'enabled':'true'}]}
    if name=='scans':listed+=1;return {'scans':[] if listed==1 else [{'id':'7','progress':'100'}]}
    if name=='sendRequest':return {'sendRequest':[{'responseHeader':'HTTP/1.1 400 Bad Request\r\nContent-Type: application/json\r\nX-Zpa-Response-Origin: app\r\n','responseBody':'{}'}]}
    if name=='scan':raise ConnectionError('lost ACK')
    if name=='status':return {'status':'100'}
    return {}
   r.engine=engine;r.attack(r.p['campaigns'][0]);self.assertEqual(calls.count('sendRequest'),1);self.assertLess(calls.index('sendRequest'),calls.index('scan'));self.assertEqual(calls.count('scan'),1);self.assertEqual(r.ops[0]['nativeScanId'],'7');self.assertTrue(r.ops[0]['terminal'])
 def test_unresolved_ack_no_retry(self):
  r=AnonymousRun.__new__(AnonymousRun);r.j=Mock();r.engine=Mock(return_value={'scans':[]})
  with patch('zap_assessment.anonymous_runner.time.sleep'),self.assertRaisesRegex(RuntimeError,'no retry'):r.reconcile_start(set())
 def test_report_truncated_missing_eof_offset_and_hash(self):
  data='abc';page={'reportPath':'/zap/wrk/r.json','offset':0,'nextOffset':None,'charactersReturned':3,'endOfFile':True,'totalCharacters':3,'offsetUnit':'unicodeCodePoints','artifactSha256':hashlib.sha256(data.encode()).hexdigest(),'content':data};self.assertEqual(read_report(lambda *a:page,'/zap/wrk/r.json',10),b'abc')
  for change in [{'totalCharacters':4},{'artifactSha256':'0'*64},{'offset':2},{'endOfFile':False,'nextOffset':None},{'content':'a','charactersReturned':1}]:
   with self.subTest(change=change),self.assertRaises(EvidenceInvalid):read_report(lambda *a:{**page,**change},'/zap/wrk/r.json',10)


class StopStateTests(unittest.TestCase):
 def test_interrupted_finished_at_fifty_percent_is_terminal(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'config').mkdir();(root/'guard').mkdir();(root/'guard/accounting.json').write_text('{"inFlight":0}')
   r=AnonymousRun.__new__(AnonymousRun);r.p=plan();r.out=root;r.rt=Mock();r.rt.config=root/'config';r.rt.capture=root/'guard';r.j=Mock();r.ops=[{'nativeScanId':'7','terminal':False}];calls=[];scans=0
   def engine(component,kind,name,args=None):
    nonlocal scans
    calls.append(name)
    if name=='scans':
     scans+=1;return {'scans':[{'id':'7','state':'RUNNING' if scans==1 else 'FINISHED','progress':'50'}]}
    return {}
   r.engine=engine;self.assertTrue(r.stop());self.assertTrue(r.ops[0]['terminal']);self.assertEqual(calls.count('stop'),1)

class ExportTests(unittest.TestCase):
 def test_missing_refs_pages_and_duplicates_are_incomplete(self):
  self.assertTrue(validate_exports([{'id':1}],[{'id':'a','messageId':1}],1,1))
  for messages,alerts,mc,ac in [([],[],1,0),([{'id':1},{'id':1}],[],2,0),([{'id':1}],[{'id':'a','messageId':2}],1,1),([{'id':1}],[{'id':'a','messageId':1}],1,2)]:
   with self.assertRaises(ValueError):validate_exports(messages,alerts,mc,ac)

class LifecycleTests(unittest.TestCase):
 def test_total_artifact_growth_budget_includes_non_guard_exports(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);(root/'reports').mkdir();(root/'reports/backend.json').write_bytes(b'x'*11)
   r=AnonymousRun.__new__(AnonymousRun);r.out=root;r.p=plan();r.p['limits']['artifactBytes']=10;r.samples=[];r.rt=Mock();r.rt.sample.return_value={'hostFree':10*1024**3,'dockerFree':10*1024**3,'ramAvailable':4*1024**3}
   with self.assertRaisesRegex(RuntimeError,'artifact byte budget'):r.resources()
   self.assertEqual(r.samples[-1]['artifactBytes'],11)
 def test_product_wrapper_fails_for_poststate_mismatch_or_data_cleanup_failure(self):
  import importlib.util
  from types import SimpleNamespace
  spec=importlib.util.spec_from_file_location('anonymous_entry_test',Path(__file__).resolve().parents[1]/'scripts/be_anonymous_research.py');entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
  for mismatch,cleanup_error in [(False,False),(True,False),(False,True)]:
   with self.subTest(mismatch=mismatch,cleanup_error=cleanup_error),tempfile.TemporaryDirectory() as t:
    root=Path(t);discovery=root/'discovery.json';discovery.write_text('{}');out=root/'new-run'
    def setup_stub(doc,dest,rid):
     entry.save(dest,'poststate-before.json',{'owned':'before'});return {'userId':1,'token':'unit-private'},{'accountId':2},Mock()
    status={'executionStatus':'completed','evidenceStatus':'complete','securityVerdict':'requires-triage','cleanupStatus':'clean','gateDecision':'review_required'}
    with patch.object(entry,'setup',side_effect=setup_stub),patch.object(entry,'plan',return_value={}),patch.object(entry,'AnonymousRun') as run,patch.object(entry,'oracle',return_value={'owned':'after' if mismatch else 'before'}),patch.object(entry,'cleanup_product',side_effect=RuntimeError('cleanup') if cleanup_error else None,return_value={'accountAbsenceVerified':True}):
     run.return_value.execute.return_value=status
     rc=entry.product_run(SimpleNamespace(discovery=discovery,output=out,interrupt_after=None))
    self.assertEqual(rc,2 if mismatch or cleanup_error else 0)
    result=json.loads((out/'RESULT.json').read_bytes());self.assertEqual(result['gateDecision'],'block' if mismatch or cleanup_error else 'review_required')
 def test_normal_cancel_timeout_cleanup_failure_keep_partial_evidence(self):
  for error,cleanup_error in [(None,False),(InterruptedError('cancel'),False),(TimeoutError('deadline'),False),(None,True)]:
   with self.subTest(error=error,cleanup_error=cleanup_error),tempfile.TemporaryDirectory() as t:
    p=plan();r=AnonymousRun(p,Path(t)/'run',lambda:(BIND,p['transportBinding']));r.resources=Mock();r.rt=Mock();r.configure=Mock();r.monitor=Mock();r.stop=Mock(return_value=True);r.export=Mock()
    def seed(c):r.coverage.append({'observed':{'matched':True}})
    def attack(*a):
     if error:raise error
     r.ops.append({'techniqueExercised':True})
    r.seed=seed;r.attack=attack
    if cleanup_error:r.rt.cleanup.side_effect=RuntimeError('cleanup failed')
    with patch('zap_assessment.anonymous_runner.RecordedMCP') as mcp:
     mcp.return_value.initialize.return_value={};result=r.execute()
    r.stop.assert_called_once();r.export.assert_called_once();r.rt.cleanup.assert_called_once()
    self.assertEqual(result['cleanupStatus'],'incomplete' if cleanup_error else 'clean')
    self.assertEqual(result['executionStatus'],'cancelled' if isinstance(error,InterruptedError) else 'failed' if error else 'completed')
    self.assertTrue((Path(t)/'run/manifest.json').exists())
 def test_seed_ack_loss_never_redispatch(self):
  with tempfile.TemporaryDirectory() as t:
   r=AnonymousRun.__new__(AnonymousRun);r.p=plan();r.out=Path(t);r.current=Mock();r.mode=Mock();r.engine=Mock(side_effect=ConnectionError('lost'));r.j=Mock();r.rt=Mock();r.rt.capture.glob.return_value=[]
   with self.assertRaises(ConnectionError):r.seed(r.p['cases'][1])
   self.assertEqual(r.engine.call_count,1);self.assertTrue(any(c.args[0]=='reconcile' and c.args[1]['retry'] is False for c in r.j.append.call_args_list))

if __name__=='__main__':unittest.main()
