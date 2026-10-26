import copy
import hashlib
import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from zap_assessment.contracts import *
from zap_assessment.evidence import *
from zap_assessment.executor import Executor,InjectedCrash
from zap_assessment.journal import Journal,Ownership
from zap_assessment.pilot import fixture_inputs
from zap_assessment.transport import LostAck,MCP

class FakeClock:
    def __init__(self): self.t=0
    def __call__(self): return self.t
    def sleep(self,n): self.t+=n

class FakeRuntime:
    def __init__(self,run,folder,journal,fault=None): self.run=run; self.folder=folder; self.journal=journal; self.fault=fault; self.stopped=False
    def provision(self):
        from zap_assessment.adapters import prepare_synthetic
        prepare_synthetic(self.plan,self.folder)
        return {'transport':'FAKE — not ZAP integration proof','session':self.run}
    def wait_health(self,*args):
        if self.fault=='health': raise TimeoutError()
    def configure_rate(self,*args): return {'rate':2}
    def request(self,*args): return {'status':200,'body':json.dumps({'build':'synthetic-v1','productId':(self.folder/'fixture/product.txt').read_text()})}
    def observations(self): return {'forbiddenRequests':0,'requests':[]}
    def terminate(self):self.stopped=True; return True
    def cleanup(self):
        self.journal.append('intent',{'action':'fake-stop','createdByRun':self.run})
        if self.fault=='stop': raise ConnectionError()
        self.stopped=True; return True

class FakeScanner:
    def __init__(self,fault=None): self.fault=fault; self.starts=0; self.status_calls=0
    def health(self): return {'version':'fake'}
    def start(self,*args):
        self.starts+=1
        if self.fault in ('lost_ack','stop'): raise LostAck()
        return 'operation-'+str(self.starts)
    def status(self,*args): self.status_calls+=1; return self.fault!='crawl_timeout'
    def import_schema(self,*args):
        if self.fault=='import_ack': raise LostAck()
    def seed(self,*args): return {'sendRequest':[{'responseHeader':'HTTP/1.1 200 OK\r\n'}]}
    def passive(self): return self.fault!='backlog'
    def report(self,*args): return '/zap/wrk/fake.json'
    def findings(self,*args): return {'summary':'synthetic'}
    def chunk(self,path,offset,sha):
        raw=canonical({'site':[{'@name':'http://127.0.0.1:18080','alerts':[]}],'data':'Việt 🧪'})
        content=raw.decode()
        if self.fault=='secret':
            content='authorization: bearer unexpected-canary';raw=content.encode()
        data={'reportPath':path,'offset':offset,'nextOffset':None,'charactersReturned':len(content),'endOfFile':True,'totalCharacters':len(content),'offsetUnit':'unicodeCodePoints','artifactSha256':hashlib.sha256(raw).hexdigest(),'content':content}
        if self.fault=='hash': data['artifactSha256']='0'*64
        if self.fault=='truncated': data['totalCharacters']+=1
        return data

class AssessmentTests(unittest.TestCase):
    def setUp(self): self.args=fixture_inputs(); self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def plan(self): return make_plan(*self.args)
    def executor(self,fault=None):
        self.scanner=FakeScanner(fault); self.runtimes=[]; c=FakeClock()
        def factory(*args):
            r=FakeRuntime(*args,fault=fault); self.runtimes.append(r); return r
        return Executor(self.root,factory,lambda rt:self.scanner,c,c.sleep)
    def test_deterministic_immutable_plan(self):
        plan=self.plan(); self.assertEqual(plan.hash,self.plan().hash)
        d=plan.data; d['product']['attackOrigins']=['http://evil.invalid']; self.assertEqual(plan.hash,self.plan().hash)
    def test_invalid_profiles_no_network_or_side_effects(self):
        for change in [{'password':'secret'},{'command':'sh anything'},{'credentialRefs':{'token':'inline'}},{'attackOrigins':['http://127.0.0.1:18080/']},{'dependencyOrigins':['https://evil.invalid']},{'extra':1}]:
            args=copy.deepcopy(self.args); args[0].update(change)
            with patch('socket.getaddrinfo',side_effect=AssertionError('network forbidden')):
                with self.assertRaises(Blocked): make_plan(*args)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_production_and_mislabeled_staging_refused(self):
        for kind in ['production','staging','test']:
            args=copy.deepcopy(self.args); args[0]['environment']['kind']=kind
            with self.assertRaises(Blocked):make_plan(*args)
    def test_expired_missing_and_wrong_identity_authority(self):
        for mode in ['expired','missing','identity','scope','ops','budget']:
            args=copy.deepcopy(self.args); reg=args[2]; a=reg.records['fixture-authority']
            if mode=='expired': a['validUntil']=(utcnow()-timedelta(seconds=1)).isoformat()
            if mode=='missing':reg.records={}
            if mode=='identity':a['environmentIdentity']='other'
            if mode=='scope':a['attackOrigins']=['http://other.invalid']
            if mode=='ops':a['operations']=['health']
            if mode=='budget':a['maxRuntimeSeconds']=1
            with self.assertRaises(Blocked):make_plan(*args)
    def test_draft_structural_only(self):
        draft=json.loads((ROOT/'profiles'/'example-existing.draft.json').read_text());validate('product',draft)
        with self.assertRaises(Blocked):AuthorityRegistry({}).get(draft['authorizationRef'])
    def test_external_schema_refs_and_server_override_block(self):
        for payload in [{'$ref':'http://evil.invalid/schema'},{'servers':[{'url':'http://127.0.0.1:8090'}]},{'servers':[{'url':'http://127.0.0.1:18080/path'}]}]:
            args=list(copy.deepcopy(self.args)); schema=json.loads(args[3]); schema['x-untrusted']=payload; args[3]=canonical(schema); args[0]['schema']['sha256']=hashlib.sha256(args[3]).hexdigest()
            with self.assertRaises(Blocked):make_plan(*args)
    def test_unapproved_schema_methods_block(self):
        args=list(copy.deepcopy(self.args)); schema=json.loads(args[3]);schema['paths']['/api/items']['delete']={};args[3]=canonical(schema);args[0]['schema']['sha256']=hashlib.sha256(args[3]).hexdigest()
        with self.assertRaises(Blocked):make_plan(*args)
    def test_schema_hash_mismatch(self):
        args=list(self.args);args[3]+=b' '
        with self.assertRaises(Blocked):make_plan(*args)
    def test_origin_ambiguity(self):
        for url in ['http://127.1','http://2130706433','http://a@localhost','http://a\\b','http://a/#fragment','http://a:80','http://a.','http://[::1%25lo]']:
            with self.assertRaises(Blocked,msg=url):origin(url,True)
    def test_dns_rebinding_ipv6_and_redirect_scope(self):
        scope=Scope(['http://fixture.invalid'],['127.0.0.1'],lambda _:['127.0.0.1']);scope.check('http://fixture.invalid/a')
        scope.resolver=lambda _:['169.254.169.254']
        with self.assertRaises(Blocked):scope.check('http://fixture.invalid/a')
        with self.assertRaises(Blocked):scope.check('http://[::1]/')
        with self.assertRaises(Blocked):scope.check('http://evil.invalid/redirect')
    def test_two_clean_runs_isolated_and_verifiable(self):
        ex=self.executor(); plan=self.plan(); r1=ex.run(plan);r2=ex.run(plan)
        self.assertNotEqual(r1['runId'],r2['runId'])
        m1=verify_bundle(r1['bundle']);m2=verify_bundle(r2['bundle']);self.assertNotEqual(m1['provenance']['session'],m2['provenance']['session'])
        self.assertEqual(r1['gateDecision'],'allow');self.assertTrue(all(r.stopped for r in self.runtimes))
    def test_lost_ack_never_retries_start(self):
        r=self.executor('lost_ack').run(self.plan()); self.assertEqual(self.scanner.starts,1);self.assertEqual(r['gateDecision'],'block');self.assertEqual(r['cleanupStatus'],'clean')
    def test_import_lost_ack_never_replays(self):
        r=self.executor('import_ack').run(self.plan()); self.assertEqual(self.scanner.starts,1);self.assertEqual(r['evidenceStatus'],'incomplete')
    def test_interrupted_recovery_stop_only_no_duplicate(self):
        ex=self.executor()
        with self.assertRaises(InjectedCrash):ex.run(self.plan(),'interrupted',True)
        self.assertEqual(self.scanner.starts,1)
        r=ex.recover(self.root/'interrupted');self.assertEqual(self.scanner.starts,1);self.assertEqual(r['executionStatus'],'cancelled');self.assertEqual(r['cleanupStatus'],'clean')
    def test_stop_unconfirmed_quarantines_retains_ownership(self):
        r=self.executor('stop').run(self.plan());self.assertEqual(r['cleanupStatus'],'incomplete');self.assertEqual(r['gateDecision'],'block')
        lock=self.root/r['runId']/'ownership.lock';self.assertTrue(json.loads(lock.read_text())['quarantined']);self.assertFalse((lock.parent/'bundle').exists())
    def test_backlog_timeout_blocks_success(self):
        r=self.executor('backlog').run(self.plan());self.assertEqual(r['executionStatus'],'timed_out');self.assertEqual(r['evidenceStatus'],'incomplete');self.assertEqual(r['gateDecision'],'block')
    def test_crawl_timeout_stops_before_export(self):
        r=self.executor('crawl_timeout').run(self.plan());self.assertEqual(r['executionStatus'],'timed_out');self.assertEqual(r['cleanupStatus'],'clean')
    def test_report_hash_and_truncation_block_publication(self):
        for fault in ['hash','truncated']:
            r=self.executor(fault).run(self.plan());self.assertEqual(r['evidenceStatus'],'invalid');self.assertFalse((self.root/r['runId']/'bundle').exists())
    def test_expiry_between_plan_and_start_has_zero_effect(self):
        plan=self.plan();data=plan.data;data['authority']['validUntil']=(utcnow()-timedelta(seconds=1)).isoformat();plan=Plan(canonical(data))
        ex=self.executor()
        with self.assertRaises(Blocked):ex.run(plan)
        self.assertEqual(self.runtimes,[]);self.assertEqual(list(self.root.iterdir()),[])
    def test_keyboard_cancel_confirms_owned_cleanup(self):
        ex=self.executor()
        self.scanner.start=lambda *args:(_ for _ in ()).throw(KeyboardInterrupt())
        r=ex.run(self.plan());self.assertEqual(r['executionStatus'],'cancelled');self.assertEqual(r['cleanupStatus'],'clean')
    def test_injected_target_instructions_do_not_change_plan(self):
        plan=self.plan();before=plan.encoded;self.executor().run(plan);self.assertEqual(plan.encoded,before)
        self.assertNotIn('169.254.169.254',str(plan.data['effectiveEgress']))
    def test_journal_tamper_and_transition_rejected(self):
        j=Journal(self.root/'j','run','a'*64)
        with self.assertRaises(Blocked):j.transition('RUNNING')
        j.transition('PROFILE_VALIDATED');text=j.path.read_text();j.path.write_text(text.replace('PROFILE_VALIDATED','PLAN_LOCKED'))
        with self.assertRaises(Blocked):Journal(j.path,'run','a'*64)
    def test_journal_intent_precedes_start_ack(self):
        r=self.executor().run(self.plan());ev=Journal(self.root/r['runId']/'journal.jsonl',r['runId'],self.plan().hash).events
        start=[e for e in ev if e['data'].get('action')=='start-crawl'];self.assertEqual([e['kind'] for e in start],['intent','ack'])
    def test_concurrent_lock_and_foreign_cleanup_rejected(self):
        lock=Ownership(self.root/'lock','A');lock.acquire()
        with self.assertRaises(FileExistsError):Ownership(lock.path,'B').acquire()
        with self.assertRaises(Blocked):Ownership(lock.path,'B').release()
        self.assertTrue(lock.path.exists())
    def test_traversal_symlink_and_unicode_chunks(self):
        for name in ['../report','/tmp/report','a/b','a\\b']:
            with self.assertRaises(EvidenceInvalid):write_file(self.root,name,b'')
        (self.root/'evil').symlink_to('/tmp')
        with self.assertRaises(EvidenceInvalid):write_file(self.root,'evil',b'')
        raw=read_report(FakeScanner().chunk,'/zap/wrk/fake.json',10000);self.assertIn('🧪',raw.decode())
    def test_secret_canaries_and_encoded_values_block(self):
        import base64
        secret='canary/private/unique'
        for b in [secret.encode(),base64.b64encode(secret.encode())]:
            with self.assertRaises(EvidenceInvalid):secret_check(b,[secret])
    def test_missing_and_tampered_required_artifact(self):
        r=self.executor().run(self.plan());root=Path(r['bundle']);(root/'report.json').write_text('{}')
        with self.assertRaises(EvidenceInvalid):verify_bundle(root)
    def test_disk_full_never_publishes_complete_manifest(self):
        ex=self.executor()
        with patch('zap_assessment.executor.publish',side_effect=OSError('disk full')):r=ex.run(self.plan())
        self.assertEqual(r['gateDecision'],'block');self.assertFalse((self.root/r['runId']/'bundle').exists())
    def test_secret_report_stops_and_quarantines_without_export(self):
        r=self.executor('secret').run(self.plan())
        self.assertEqual(r['evidenceStatus'],'invalid');self.assertEqual(r['cleanupStatus'],'retained_by_policy')
        self.assertTrue(self.runtimes[0].stopped);self.assertTrue((self.root/r['runId']/'ownership.lock').exists())
        self.assertFalse((self.root/r['runId']/'bundle').exists())
    def test_quarantine_can_recover_after_stop_connectivity_returns(self):
        ex=self.executor('stop');r=ex.run(self.plan());self.assertEqual(r['cleanupStatus'],'incomplete')
        ex.runtime_factory=lambda *args:FakeRuntime(*args)
        recovered=ex.recover(self.root/r['runId']);self.assertEqual(recovered['cleanupStatus'],'clean')
        self.assertFalse((self.root/r['runId']/'ownership.lock').exists())
    def test_journal_disk_failure_still_stops_owned_engine(self):
        ex=self.executor();original=Journal.append
        def append(j,kind,data):
            if kind=='intent' and data.get('action')=='start-crawl':
                j.io_failed=True;raise OSError('disk full')
            return original(j,kind,data)
        with patch.object(Journal,'append',append):r=ex.run(self.plan())
        self.assertEqual(self.scanner.starts,0);self.assertTrue(self.runtimes[0].stopped)
        self.assertEqual(r['evidenceStatus'],'invalid');self.assertEqual(r['gateDecision'],'block')
    def test_forged_plan_scope_and_unknown_execution_field_no_effect(self):
        ex=self.executor();d=self.plan().data;d['shell']='touch /tmp/should-never-exist'
        with self.assertRaises(Blocked):ex.run(Plan(canonical(d)))
        d=self.plan().data;d['effectiveEgress']=['http://evil.invalid']
        with self.assertRaises(Blocked):ex.run(Plan(canonical(d)))
        self.assertEqual(self.runtimes,[])
    def test_bundle_verifier_rejects_false_allow_and_missing_track(self):
        r=self.executor().run(self.plan());root=Path(r['bundle']);m=json.loads((root/'manifest.json').read_bytes())
        m['tracks']=m['tracks'][:1]
        raw=canonical(m);(root/'manifest.json').write_bytes(raw);(root/'manifest.sha256').write_text(hashlib.sha256(raw).hexdigest())
        with self.assertRaises((Blocked,EvidenceInvalid)):verify_bundle(root)
    def test_tool_output_cannot_request_arbitrary_tool(self):
        called=[];client=MCP(lambda *args:called.append(args))
        with self.assertRaises(Blocked):client.call('shell',{'cmd':'touch anything'})
        self.assertEqual(called,[])
    def test_unavailable_target_has_no_start_and_blocks(self):
        ex=self.executor('health');r=ex.run(self.plan())
        self.assertEqual(self.scanner.starts,0);self.assertEqual(r['executionStatus'],'timed_out');self.assertEqual(r['gateDecision'],'block')
    def test_secret_quarantine_recovery_requires_owner_disposition(self):
        ex=self.executor('secret');r=ex.run(self.plan());count=len(self.runtimes)
        with self.assertRaises(Blocked):ex.recover(self.root/r['runId'])
        self.assertEqual(len(self.runtimes),count);self.assertTrue((self.root/r['runId']/'ownership.lock').exists())
    def test_fractional_rate_rejected_before_side_effect(self):
        args=copy.deepcopy(self.args);args[1]['maxRate']=.5
        with self.assertRaises(Blocked):make_plan(*args)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_partial_manifest_is_never_published_as_bundle(self):
        import zap_assessment.evidence as ev
        original=ev.write_file
        def fail(root,name,data):
            if name=='manifest.sha256':raise OSError('disk full')
            return original(root,name,data)
        with patch.object(ev,'write_file',fail):r=self.executor().run(self.plan())
        self.assertEqual(r['gateDecision'],'block');self.assertFalse((self.root/r['runId']/'bundle').exists())
        self.assertTrue((self.root/r['runId']/'staging/manifest.json').exists())
    def test_replaced_container_id_is_not_owned_cleanup(self):
        from zap_assessment.runtime import DockerRuntime
        j=Journal(self.root/'owner-journal','run','a'*64)
        j.append('intent',{'action':'container-create','resource':'zpa-run-zap','createdByRun':'run'})
        j.append('ack',{'action':'container-create','resource':'zpa-run-zap','containerId':'original-id'})
        rt=DockerRuntime('run',self.root,j)
        fake=[{'Id':'replacement-id','Config':{'Labels':{'zpa.run':'run'}}}]
        with patch('zap_assessment.runtime.docker',return_value=json.dumps(fake)) as call:
            with self.assertRaises(Blocked):rt.check_owner('zpa-run-zap')
        self.assertEqual(call.call_args.args[0],['inspect','zpa-run-zap'])
    def test_unverified_active_cannot_become_executable(self):
        args=copy.deepcopy(self.args);args[1]['active']=True;args[1]['operations'].append('active');args[1]['destructiveLevel']='synthetic-mutations'
        args[2].records['fixture-authority']['operations'].append('active');args[2].records['fixture-authority']['destructiveLevel']='synthetic-mutations'
        with self.assertRaises(Blocked):make_plan(*args)
        self.assertEqual(list(self.root.iterdir()),[])
    def test_schema_callbacks_cannot_hide_required_operations(self):
        args=list(copy.deepcopy(self.args));schema=json.loads(args[3]);schema['paths']['/health']['get']['callbacks']={'hidden':{'post':{}}};args[3]=canonical(schema);args[0]['schema']['sha256']=hashlib.sha256(args[3]).hexdigest()
        with self.assertRaises(Blocked):make_plan(*args)
    def test_unicode_multi_page_offset_and_hash_pinning(self):
        content='Việt🧪-𐍈-end';sha=hashlib.sha256(content.encode()).hexdigest();seen=[]
        def reader(path,offset,expected):
            seen.append(expected);text=content[offset:offset+2];end=offset+len(text);eof=end==len(content)
            return {'reportPath':path,'offset':offset,'nextOffset':None if eof else end,'charactersReturned':len(text),'endOfFile':eof,'totalCharacters':len(content),'offsetUnit':'unicodeCodePoints','artifactSha256':sha,'content':text}
        self.assertEqual(read_report(reader,'/zap/wrk/unicode.json',10000),content.encode())
        self.assertIsNone(seen[0]);self.assertTrue(all(x==sha for x in seen[1:]));self.assertGreater(len(seen),1)
    def test_status_semantics(self):
        self.assertEqual(decide('completed','complete','clean',True),('pass','allow',0))
        self.assertEqual(decide('completed','complete','clean',True,confirmed=True),('fail','block',1))
        self.assertEqual(decide('completed','complete','clean',True,untriaged=True),('inconclusive','review_required',3))
        for e in ['pending','incomplete','invalid']:
            self.assertEqual(decide('completed',e,'clean',True)[1:2],('block',))
        self.assertEqual(decide('completed','complete','incomplete',True)[1],'block')

if __name__=='__main__':unittest.main()
