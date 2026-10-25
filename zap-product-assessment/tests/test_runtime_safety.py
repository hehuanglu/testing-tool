"""W4 development contracts. Fake controller records are not live ZAP proof."""
import copy,errno,hashlib,json,os,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.contracts import Blocked,canonical,digest,make_plan
from zap_assessment.pilot import fixture_inputs
from zap_assessment.journal import Journal
from zap_assessment.safety_io import ReservedStop,atomic_bytes
from zap_assessment.runtime_safety import ResourceGate,EffectivePolicy,SafetySupervisor,GIB
from zap_assessment.executor import Executor
from test_assessment import FakeRuntime,FakeScanner,FakeClock

INV={'addons':[{'id':'network','version':'1'}],'scripts':[{'name':'disabled','type':'active','enabled':False,'sha256':'1'*64}], 'rules':[{'id':'40012','enabled':True},{'id':'100043','enabled':False}], 'inputVectors':['query']}

def contract(plan=None,calibration_root=None):
    c={'schemaVersion':'runtime-safety/1.0','planHash':plan.hash if plan else 'a'*64,
            'growth':{'host':GIB,'docker':GIB},'calibration':{'classification':'owned-synthetic','evidenceSha256':'b'*64},
            'policy':INV,'sampleSeconds':5,'reserveBytes':2*GIB,'ramHeadroomBytes':4*GIB,'stopSeconds':120,
            'runtimePins':plan.data['runtime'] if plan else {},'sourceDigest':__import__('zap_assessment.executor',fromlist=['implementation_digest']).implementation_digest()}
    if plan is not None and calibration_root is not None:
        # Deliberate fictitious calibration metadata for controller unit fixtures;
        # never published as real scanner calibration/acceptance.
        data={'schemaVersion':'runtime-calibration/1.1','measurementKind':'scanner-topology','sourceDigest':c['sourceDigest'],'runtimePins':c['runtimePins'],'workflowHash':digest(plan.data['workflow']),'productHash':digest(plan.data['product']),'growth':c['growth'],'ramPeakBytes':GIB,'completedPhases':['startup','crawl','settle','report','cleanup'],'observations':[{'at':0,'hostGrowth':1,'dockerGrowth':1},{'at':1,'hostGrowth':1024,'dockerGrowth':1024}]}
        import uuid
        f=Path(calibration_root)/(uuid.uuid4().hex+'-synthetic-calibration.json');f.write_bytes(canonical(data))
        c['calibration'].update(evidenceRef=str(f),evidenceSha256=hashlib.sha256(f.read_bytes()).hexdigest())
    return c
def sample():return {'hostFree':20*GIB,'dockerFree':20*GIB,'ramAvailable':8*GIB,'dockerAvailable':True}
def event(rule='40012',producer='active',**extra):
    return {'requestId':'req-1','producer':producer,'ruleId':rule,'forwarded':True,'boundaryCorrelated':True,
            'targetAllowed':True,'credentialForwarded':False,'unsupportedVectors':[],**extra}

class SafetyTests(unittest.TestCase):
    def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
    def tearDown(self):self.tmp.cleanup()
    def test_engine_false_string_remains_disabled_and_unknown_is_refused(self):
        from zap_assessment.runtime import engine_bool
        for raw,expected in [('false',False),('true',True),(False,False),(True,True)]:
            self.assertIs(engine_bool(raw),expected)
        for raw in (None,0,1,'unknown','TRUE',''):
            with self.subTest(raw=raw),self.assertRaises(Blocked):engine_bool(raw)
    def test_resource_thresholds_and_unknown_growth(self):
        c=contract();gate=ResourceGate(c,sample,FakeClock());gate.preflight()
        for field in ('hostFree','dockerFree','ramAvailable','dockerAvailable'):
            s=sample();s[field]=False if field=='dockerAvailable' else 0
            with self.subTest(field=field),self.assertRaises(Blocked):ResourceGate(c,lambda:s,FakeClock()).preflight()
        c['growth']['docker']=None
        with self.assertRaises(Blocked):ResourceGate(c,sample,FakeClock()).preflight()
    def test_resource_growth_formula_and_latch(self):
        c=contract();c['growth']['host']=5*GIB
        s=sample();s['hostFree']=11*GIB
        with self.assertRaises(Blocked):ResourceGate(c,lambda:s,FakeClock()).preflight()
        s=sample();clock=FakeClock();gate=ResourceGate(contract(),lambda:s,clock);gate.preflight()
        s['dockerFree']=2*GIB;clock.sleep(5)
        with self.assertRaises(Blocked):gate.check()
        s['dockerFree']=20*GIB
        with self.assertRaises(Blocked):gate.check()
    def test_no_fixed_eight_gib_floor_but_growth_and_reserve_still_apply(self):
        s=sample();s['hostFree']=4*GIB;s['dockerFree']=4*GIB
        ResourceGate(contract(),lambda:s,FakeClock()).preflight()
        for field in ('hostFree','dockerFree'):
            low=dict(s);low[field]-=1
            with self.subTest(field=field),self.assertRaises(Blocked):
                ResourceGate(contract(),lambda:low,FakeClock()).preflight()
    def test_inventory_and_disabled_script_emission_block(self):
        audit=EffectivePolicy(INV);audit.snapshot('before',INV)
        for key in ('addons','scripts','rules','inputVectors'):
            changed=copy.deepcopy(INV);changed[key]=[]
            with self.subTest(key=key),self.assertRaises(Blocked):EffectivePolicy(INV).snapshot('during',changed)
        with self.assertRaises(Blocked):audit.traffic([event('100043')],complete=True)
    def test_contained_disabled_or_unknown_producer_still_latches_policy(self):
        for record in (event('100043',forwarded=False,targetAllowed=False),event(None,forwarded=False),
                       event(None,producer='unknown',forwarded=False),event('40012',producer='background',forwarded=False)):
            audit=EffectivePolicy(INV)
            with self.subTest(record=record),self.assertRaises(Blocked):audit.traffic([record],complete=True)
            self.assertIsNotNone(audit.failure)
        # Known HTTP-mode crawl rejecting an unsupported HTTPS hop remains an
        # explicit transport denial, never a verified active application test.
        audit=EffectivePolicy(INV);audit.traffic([event(None,producer='crawl',forwarded=False,targetAllowed=False,unsupportedVectors=['https-transport'])],complete=True)
    def test_enabled_rule_cannot_emit_when_workflow_disallows_active(self):
        for forwarded in (True,False):
            audit=EffectivePolicy(INV,active_execution_allowed=False)
            with self.subTest(forwarded=forwarded),self.assertRaisesRegex(Blocked,'outside workflow policy'):
                audit.traffic([event('40012',forwarded=forwarded)],complete=True)
    def test_unknown_passive_background_attribution_and_missing_after(self):
        for record in (event(producer='unknown'),event(boundaryCorrelated=False),event(targetAllowed=False),event(credentialForwarded=True),event(unsupportedVectors=['query'])):
            with self.subTest(record=record),self.assertRaises(Blocked):EffectivePolicy(INV).traffic([record],complete=True)
        audit=EffectivePolicy(INV);audit.snapshot('before',INV)
        with self.assertRaises(Blocked):audit.finalize()
        audit=EffectivePolicy(INV);audit.snapshot('before',INV)
        audit.snapshot('during',INV);audit.snapshot('after',INV)
        audit.traffic([event(rule=None,producer='passive'),event(requestId='req-2',rule=None,producer='background')],complete=True)
        result=audit.finalize();self.assertEqual(1,result['trafficByProducer']['passive']);self.assertEqual(1,result['trafficByProducer']['background'])
    def test_reserved_channel_survives_writer_fault_and_rejects_torn_slot(self):
        r=ReservedStop(self.root/'reserve','run','a'*64);r.record({'cleanupStatus':'incomplete','stopUnconfirmed':True})
        with patch('zap_assessment.safety_io.atomic_bytes',side_effect=OSError(errno.ENOSPC,'fault')):
            r.record({'cleanupStatus':'clean','stopUnconfirmed':False})
        result=ReservedStop.read(self.root/'reserve');self.assertEqual('clean',result['data']['cleanupStatus'])
        # Corrupt newest slot; previous authenticated frame remains recoverable.
        with (self.root/'reserve').open('r+b') as f:f.seek(r.slot_offset);f.write(b'BROKEN')
        self.assertTrue(ReservedStop.read(self.root/'reserve')['data']['stopUnconfirmed']);r.close()
    def test_atomic_short_write_never_exposes_final_name(self):
        original=os.write
        def short(fd,data):return original(fd,data[:max(1,len(data)//2)])
        with patch('zap_assessment.safety_io.os.write',side_effect=short):atomic_bytes(self.root/'complete',b'payload'*100)
        self.assertEqual(b'payload'*100,(self.root/'complete').read_bytes())
        with patch('zap_assessment.safety_io.os.write',return_value=0),self.assertRaises(OSError):atomic_bytes(self.root/'never',b'payload')
        self.assertFalse((self.root/'never').exists())
    def test_truncated_journal_recovery_preserves_original(self):
        plan=make_plan(*fixture_inputs());folder=self.root/'interrupted';folder.mkdir();(folder/'staging').mkdir();(folder/'staging/plan.json').write_bytes(plan.encoded)
        j=Journal(folder/'journal.jsonl','interrupted',plan.hash);j.transition('PROFILE_VALIDATED');j.transition('PLAN_LOCKED');j.transition('PREFLIGHT_PASSED');j.transition('RESOURCES_READY');j.transition('RUNNING')
        from zap_assessment.journal import Ownership
        Ownership(folder/'ownership.lock','interrupted').acquire()
        with j.path.open('ab') as f:f.write(b'{"seq":')
        original=j.path.read_bytes();ex=Executor(self.root,lambda *a:FakeRuntime(*a),lambda r:FakeScanner())
        result=ex.recover(folder);self.assertEqual('clean',result['cleanupStatus']);self.assertEqual(original,j.path.read_bytes());self.assertGreater(len(list(folder.glob('recovery-journal-*.jsonl'))),0)
    def test_permanent_journal_fault_still_stops_and_records_out_of_band(self):
        plan=make_plan(*fixture_inputs());runtimes=[];scanner=FakeScanner();clock=FakeClock()
        def factory(*a):r=FakeRuntime(*a);runtimes.append(r);return r
        original=Journal.append
        def fail(j,kind,data):
            if kind=='intent' and data.get('action')=='start-crawl':j.io_failed=True;j.emergency=True
            if j.io_failed:raise OSError(errno.ENOSPC,'fault')
            return original(j,kind,data)
        with patch.object(Journal,'append',fail):result=Executor(self.root,factory,lambda r:scanner,clock,clock.sleep).run(plan,'fault')
        self.assertTrue(runtimes[0].stopped);self.assertEqual(0,scanner.starts);self.assertEqual('block',result['gateDecision'])
        self.assertFalse((self.root/'fault/bundle').exists());self.assertEqual('clean',ReservedStop.read(self.root/'fault/stop-reserve.bin')['data']['cleanupStatus'])
    def test_supervisor_contract_pin_drift_and_preflight_zero_provision(self):
        plan=make_plan(*fixture_inputs());j=Journal(self.root/'j','run',plan.hash)
        rt=FakeRuntime('run',self.root,j);rt.plan=plan;rt.resource_sample=sample
        c=contract(plan,self.root)
        with self.assertRaises(Blocked):SafetySupervisor(rt,j,c,'0'*64).preflight()
        c['planHash']='b'*64
        with self.assertRaises(Blocked):SafetySupervisor(rt,j,c,digest(c)).preflight()
    def test_container_label_missing_and_wrong_image_block_cleanup(self):
        from zap_assessment.runtime import DockerRuntime
        j=Journal(self.root/'j','run','a'*64);j.append('intent',{'action':'container-create','resource':'zpa-run-zap','createdByRun':'run','expectedImageId':'sha256:expected'})
        rt=DockerRuntime('run',self.root,j)
        for row in ({'Id':'id','Image':'sha256:expected','Config':{'Labels':None}}, {'Id':'id','Image':'sha256:wrong','Config':{'Labels':{'zpa.run':'run'}}}):
            with patch('zap_assessment.runtime.docker',return_value=json.dumps([row])),self.assertRaises(Blocked):rt.check_owner('zpa-run-zap')

    def test_guard_policy_denies_scope_method_path_credentials_and_redirect_hop(self):
        from zap_assessment.egress import policy_target,Denied
        origin='http://127.0.0.1:18080';headers={'Host':'127.0.0.1:18080'}
        self.assertEqual('/safe',policy_target('GET',origin+'/safe',headers,origin,['/safe']))
        for method,url,h in [('POST',origin+'/safe',headers),('GET',origin+'/other',headers),
                             ('GET','http://169.254.169.254/canary',{'Host':'169.254.169.254'}),
                             ('GET',origin+'/safe',headers|{'Authorization':'Bearer fixture-canary'}),
                             ('GET',origin+'/safe?x=1',headers),('GET',origin+'/%73afe',headers)]:
            with self.subTest(url=url),self.assertRaises(Denied):policy_target(method,url,h,origin,['/safe'])

    def test_supervisor_worker_latches_docker_loss_and_confirms_own_stop(self):
        plan=make_plan(*fixture_inputs());j=Journal(self.root/'watch','run',plan.hash);rt=FakeRuntime('run',self.root,j);rt.plan=plan
        state=sample();rt.resource_sample=lambda:state;rt.policy_inventory=lambda:copy.deepcopy(INV);rt.policy_traffic=lambda:{'events':[],'complete':True}
        c=contract(plan,self.root);s=SafetySupervisor(rt,j,c,digest(c));s.preflight();s.start();state['dockerAvailable']=False
        deadline=time.monotonic()+7
        while s.failure is None and time.monotonic()<deadline:time.sleep(.05)
        s.close();self.assertIsNotNone(s.failure);self.assertTrue(s.stop_confirmed);self.assertTrue(rt.stopped)
        with self.assertRaises(Blocked):s.checkpoint()

    def test_success_and_deviation_use_same_executor_and_partial_namespace(self):
        from zap_assessment.evidence import verify_bundle
        for drift in (False,True):
            root=self.root/str(drift);plan=make_plan(*fixture_inputs());scanner=FakeScanner();clock=FakeClock();runtimes=[]
            def factory(*args):
                rt=FakeRuntime(*args);rt.resource_sample=sample;rt.policy_inventory=lambda:copy.deepcopy(INV)
                rt.policy_traffic=lambda:{'events':[event('100043')] if drift else [],'complete':True};runtimes.append(rt);return rt
            c=contract(plan,self.root)
            result=Executor(root,factory,lambda r:scanner,clock,clock.sleep,safety_factory=lambda rt,j:SafetySupervisor(rt,j,c,digest(c),clock)).run(plan)
            self.assertTrue(runtimes[0].stopped)
            if drift:
                self.assertEqual(0,scanner.starts);self.assertEqual('block',result['gateDecision']);self.assertTrue((root/result['runId']/'partial-evidence/status.json').exists());self.assertFalse((root/result['runId']/'bundle').exists())
            else:
                self.assertEqual('allow',result['gateDecision']);self.assertIn('runtimeSafety',verify_bundle(result['bundle'])['provenance'])

    def test_uncalibrated_live_entry_refuses_without_docker_provision(self):
        from zap_assessment.pilot import live_executor
        with patch('zap_assessment.runtime.docker',side_effect=AssertionError('Docker called')):
            result=live_executor(self.root).run(make_plan(*fixture_inputs()),'uncalibrated')
        self.assertEqual('block',result['gateDecision']);self.assertEqual('clean',result['cleanupStatus']);self.assertFalse((self.root/'uncalibrated/bundle').exists())

    def test_stop_covers_owned_auxiliary_resources(self):
        from zap_assessment.runtime import DockerRuntime
        j=Journal(self.root/'aux','run','a'*64);rt=DockerRuntime('run',self.root,j);rt.names.append('zpa-run-extra')
        seen=[]
        def state(name,**kw):return {'State':{'Running':not any(a[0]=='stop' and a[-1]==name for a in seen)}}
        with patch.object(rt,'check_owner',side_effect=state),patch('zap_assessment.runtime.docker',side_effect=lambda args,**kw:seen.append(args) or ''):
            rt.terminate()
        self.assertIn('zpa-run-extra',[a[-1] for a in seen if a[0]=='stop'])

    def test_calibration_tamper_rehashed_does_not_excuse_source_or_workload_drift(self):
        plan=make_plan(*fixture_inputs());j=Journal(self.root/'calibration-j','run',plan.hash);rt=FakeRuntime('run',self.root,j);rt.plan=plan;rt.resource_sample=sample
        for field,value in [('workflowHash','0'*64),('productHash','0'*64),('sourceDigest','sha256:'+'0'*64),('ramPeakBytes',5*GIB),('measurementKind','tmpfs-only')]:
            c=contract(plan,self.root);path=Path(c['calibration']['evidenceRef']);data=json.loads(path.read_bytes());data[field]=value;path.write_bytes(canonical(data));c['calibration']['evidenceSha256']=hashlib.sha256(path.read_bytes()).hexdigest()
            with self.subTest(field=field),self.assertRaises(Blocked):SafetySupervisor(rt,j,c,digest(c)).preflight()

    def test_guard_writer_failure_latches_before_next_forward(self):
        from zap_assessment.egress import EgressGuard
        from types import SimpleNamespace
        guard=object.__new__(EgressGuard);guard.command='GET';guard.path='http://127.0.0.1/safe';guard.log_path=self.root/'missing'/'log';guard.server=SimpleNamespace()
        with self.assertRaises(OSError):guard.record('forwarded')
        self.assertTrue(guard.server.safety_halted)
        from zap_assessment.guard_server import BoundGuard
        bound=object.__new__(BoundGuard);bound.server=guard.server;bound.config={}
        from zap_assessment.egress import Denied
        with self.assertRaises(Denied):bound.authorize()

    def test_journal_middle_corruption_never_recovered_as_partial_tail(self):
        j=Journal(self.root/'corrupt','run','a'*64);j.append('intent',{'action':'provision'});j.append('ack',{})
        raw=j.path.read_bytes();j.path.write_bytes(b'{}\n'+raw.split(b'\n',1)[1])
        with self.assertRaises(Blocked):Journal(j.path,'run','a'*64,allow_partial_tail=True)

    def test_unconfirmed_watchdog_stop_quarantines_without_cleanup_retry(self):
        plan=make_plan(*fixture_inputs());scanner=FakeScanner();runtimes=[]
        class Unconfirmed:
            stop_confirmed=False;thread=None
            def preflight(self):pass
            def checkpoint(self):pass
            def start(self):raise Blocked('fixture unconfirmed stop')
            def close(self):pass
        def factory(*args):rt=FakeRuntime(*args);runtimes.append(rt);return rt
        result=Executor(self.root,factory,lambda rt:scanner,safety_factory=lambda rt,j:Unconfirmed()).run(plan,'unconfirmed')
        self.assertEqual('incomplete',result['cleanupStatus']);self.assertFalse(runtimes[0].stopped);self.assertEqual(0,scanner.starts)
        self.assertTrue(json.loads((self.root/'unconfirmed/ownership.lock').read_bytes())['quarantined'])
        self.assertTrue(ReservedStop.read(self.root/'unconfirmed/stop-reserve.bin')['data']['stopUnconfirmed'])

if __name__=='__main__':unittest.main()
