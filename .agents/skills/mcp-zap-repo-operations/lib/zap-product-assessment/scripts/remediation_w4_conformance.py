#!/usr/bin/env python3
"""Owned W4 anonymous fixture: locked normal runs and isolated negative cases.

Never registers a product/auth capability. Fault injection is explicit in the
locked case; actual daemon outages and host-disk exhaustion are not performed.
"""
import argparse,errno,hashlib,json,sys,time,uuid
from pathlib import Path
from unittest.mock import patch
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'src')]
from zap_assessment.contracts import Blocked,Plan,canonical,digest,make_plan
from zap_assessment.executor import Executor,InjectedCrash,implementation_digest
from zap_assessment.observed import ObservedDockerRuntime
from zap_assessment.w4_fixture import inputs as fixture_inputs,W4Scanner as LiveScanner
from zap_assessment.transport import MCP,LostAck
from zap_assessment.runtime import docker
from zap_assessment.runtime_safety import SafetySupervisor,GIB
from zap_assessment.evidence import write_file,verify_bundle
from zap_assessment.journal import Journal
from zap_assessment.traffic import capture_snapshot,correlate

CASES=('phase-deviation','addon-drift','normal','interrupt','disabled-rule','unknown-active','inventory-drift','journal-enospc','lost-start-ack')
FAULT_SCRIPT="""const V=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
const F=Java.type('java.nio.file.Files');const P=Java.type('java.nio.file.Path');
const cls=V.getGlobalCustomVar('w4.class');const fault=cls.getClassLoader().loadClass('PolicyFaultProbe');
const command=F.readString(P.of('/zap/wrk/fault-command.txt'));
if(command==='install') {
 V.setGlobalVar('w4.fixture.error','');
 try { fault.getMethod('install',Java.type('java.lang.String').class).invoke(null,''); } catch(e) { V.setGlobalVar('w4.fixture.error',String(e)); throw e; }
 cls.getMethod('bindRules',Java.type('java.lang.String').class).invoke(null,F.readString(P.of('/zap/wrk/observer-rule-ids.txt'))+',990001');
} else if(command!=='idle') fault.getMethod('emit',Java.type('java.lang.String').class).invoke(null,command);
"""

def active_proof(progress,traffic):
    terminal=[p for p in progress if p['terminal']]
    if len(terminal)!=1:return {'pass':False,'reason':'terminal scanProgress missing'}
    plugins=[]
    def walk(value):
        if isinstance(value,dict):
            for k,v in value.items():
                if k=='Plugin':plugins.append(v)
                else:walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(terminal[0]['progress'])
    if any(not isinstance(p,list) or len(p)!=7 or p[3]!='Complete' or not str(p[5]).isdecimal() for p in plugins):return {'pass':False,'reason':'scanProgress shape or terminal rule state'}
    counts={str(p[1]):int(p[5]) for p in plugins if int(p[5])>0}
    observed={}
    for e in traffic.get('events',[]):
        if e['producer']=='active':observed[e['ruleId']]=observed.get(e['ruleId'],0)+1
    return {'pass':counts==observed and set(counts)=={'40012'},'scanProgressRequestCounts':counts,'nativeRequestCounts':observed,'expectedRuleIds':['40012'],'vulnerabilityDetectionVerified':False}

def prepare(work,cal_report,case):
    r=json.loads(cal_report.read_bytes());f=Path(r['calibrationRef']);raw=f.read_bytes();c=json.loads(raw)
    if not r['calibrationComplete'] or not r['completeWorkflowMeasured'] or r['result']['cleanupStatus']!='clean':raise Blocked('completed clean calibration required')
    inputs=list(fixture_inputs(r.get('activeWorkflow',False)))
    if r['calibrationScope'].startswith('HTTP-only'):inputs[0]['crawlPath']='/health'
    plan=make_plan(*inputs)
    if r['sourceDigest']!=implementation_digest() or c['productHash']!=digest(plan.data['product']) or c['workflowHash']!=digest(plan.data['workflow']):raise Blocked('calibration workload/source drift')
    policy=json.loads(json.dumps(r['policy']['snapshots'][0]['inventory']))
    if case in ('disabled-rule','unknown-active'):
        policy['scripts'].append({'name':'w4-fault','type':'standalone','enabled':True,'sha256':hashlib.sha256(FAULT_SCRIPT.encode()).hexdigest()})
        policy['rules'].append({'id':'990001','enabled':False})
    contract={'schemaVersion':'runtime-safety/1.0','planHash':plan.hash,'sourceDigest':implementation_digest(),'runtimePins':plan.data['runtime'],'growth':c['growth'],'calibration':{'classification':'owned-synthetic','evidenceRef':str(f),'evidenceSha256':hashlib.sha256(raw).hexdigest()},'policy':policy,'sampleSeconds':5,'reserveBytes':2*GIB,'ramHeadroomBytes':4*GIB,'stopSeconds':120}
    work.mkdir(mode=0o700)
    lock={'case':case,'planHash':plan.hash,'safetyHash':digest(contract),'sourceDigest':implementation_digest(),'harnessSha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'faultFixtureSha256':hashlib.sha256((P/'tests/support/PolicyFaultProbe.java').read_bytes()).hexdigest(),'calibrationReportSha256':hashlib.sha256(cal_report.read_bytes()).hexdigest(),'independentReviewerApproval':False,'scope':r['calibrationScope'],'expected':'complete verified bundle; preserve security verdict and review gate' if case=='normal' else 'blocked/incomplete, exact owned stop, no false complete bundle','faultClassification':'none' if case=='normal' else 'owned runtime with explicit fault injection; not a real daemon outage'}
    for name,data in [('plan.json',plan.encoded),('safety-contract.json',canonical(contract)),('input-lock.json',canonical(lock))]:write_file(work,name,data)
    return lock

def run(work,output,expected):
    if output.exists():raise Blocked('fresh output required')
    plan=Plan((work/'plan.json').read_bytes());c=json.loads((work/'safety-contract.json').read_bytes());lock=json.loads((work/'input-lock.json').read_bytes());case=lock['case']
    if expected!=lock['safetyHash'] or expected!=digest(c) or plan.hash!=lock['planHash'] or implementation_digest()!=lock['sourceDigest'] or hashlib.sha256(Path(__file__).read_bytes()).hexdigest()!=lock['harnessSha256'] or hashlib.sha256((P/'tests/support/PolicyFaultProbe.java').read_bytes()).hexdigest()!=lock['faultFixtureSha256']:raise Blocked('locked conformance inputs drift')
    runtimes=[];supervisors=[];diagnostics=[];injected=[]
    class Runtime(ObservedDockerRuntime):
        def request(self,url,*args,**kwargs):
            result=super().request(url,*args,**kwargs)
            if result["status"]>=400 and "/JSON/script/" in url:
                diagnostics.append({"stage":"owned-script-api","status":result["status"],"detail":result["body"][:1600]})
            return result
        def install_capture(self):
            super().install_capture()
            if case not in ('disabled-rule','unknown-active'):return
            wrk=self.root/'zap-workspace';(wrk/'PolicyFaultProbe.java').write_bytes((P/'tests/support/PolicyFaultProbe.java').read_bytes())
            docker(['exec',self.names[2],'javac','-cp','/zap/wrk/probe-classes:/zap/*:/zap/lib/*','-d','/zap/wrk/probe-classes','/zap/wrk/PolicyFaultProbe.java'],timeout=30)
            (wrk/'w4-fault.js').write_text(FAULT_SCRIPT);(wrk/'fault-command.txt').write_text('install')
            self.engine('script','action','load',{'scriptName':'w4-fault','scriptType':'standalone','scriptEngine':'Graal.js','fileName':'/zap/wrk/w4-fault.js'})
            self.engine('script','action','runStandAloneScript',{'scriptName':'w4-fault'})
            error=self.engine('script','view','globalVar',{'varKey':'w4.fixture.error'}).get('globalVar')
            if error:raise Blocked('owned fault fixture install: '+error[:500])
            if self.engine('script','view','globalVar',{'varKey':'w4.fixture.enabled'}).get('globalVar')!='false':raise Blocked('native fault fixture not disabled')
        def policy_inventory(self):
            inv=super().policy_inventory()
            if case in ('disabled-rule','unknown-active'):
                flag=self.engine('script','view','globalVar',{'varKey':'w4.fixture.enabled'}).get('globalVar')
                if flag!='false':raise Blocked('native fault fixture changed')
                if not any(r['id']=='990001' for r in inv['rules']):inv['rules'].append({'id':'990001','enabled':False})
            return inv
        def inject(self):
            if injected:return
            injected.append({'case':case,'at':time.monotonic()});s=supervisors[0]
            if case in ('disabled-rule','unknown-active'):
                (self.root/'zap-workspace/fault-command.txt').write_text('disabled' if case=='disabled-rule' else 'unknown')
                self.engine('script','action','runStandAloneScript',{'scriptName':'w4-fault'})
            elif case=='addon-drift':self.engine('autoupdate','action','uninstallAddon',{'id':'soap'})
            elif case=='inventory-drift':self.engine('script','action','disable',{'scriptName':'SwaggerSecretDetector.js'})
            else:return
            deadline=time.monotonic()+15
            while not s.failure and time.monotonic()<deadline:time.sleep(.1)
            if not s.failure:raise Blocked('fault was not detected within test deadline')
            raise Blocked('expected owned policy latch')
    def factory(*args):
        rt=Runtime(*args);runtimes.append(rt)
        for name in ('resource_sample','install_capture','policy_inventory','policy_traffic','observations'):
            original=getattr(rt,name)
            def call(*a,_original=original,_name=name,**kw):
                try:return _original(*a,**kw)
                except Exception as exc:diagnostics.append({'stage':_name,'type':type(exc).__name__,'detail':str(exc)[:200]});raise
            setattr(rt,name,call)
        return rt
    def safety(rt,j):s=SafetySupervisor(rt,j,c,expected);supervisors.append(s);return s
    class Scanner(LiveScanner):
        def start(self,kind,target):
            op=super().start(kind,target)
            if case=='lost-start-ack':injected.append({'case':case,'at':time.monotonic(),'actualOperationId':op});raise LostAck('deliberately dropped actual start ACK')
            return op
        def status(self,kind,op):
            if case in ('disabled-rule','unknown-active','inventory-drift','addon-drift'):runtimes[0].inject()
            if case=='phase-deviation' and kind=='active' and not injected:
                # Trigger after the real selected rule starts, leaving its next
                # requests to encounter the boundary with the wrong phase.
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    rows=capture_snapshot([runtimes[0].root/'zap-workspace/sender-events.jsonl'])[0]
                    if any(r.get('kind')=='request' and r.get('ruleId')=='40012' for r in rows):break
                    time.sleep(.05)
                else:raise Blocked('real rule did not start before phase fault')
                runtimes[0].set_phase('settle');injected.append({'case':case,'at':time.monotonic()})
                deadline=time.monotonic()+15
                while not supervisors[0].failure and time.monotonic()<deadline:time.sleep(.1)
                if not supervisors[0].failure:raise Blocked('phase deviation was not latched')
                raise Blocked('expected phase policy latch')
            return super().status(kind,op)
    def scanner(rt):
        rt.w4_scanner=Scanner(MCP(rt.request),rt.engine,rt.request);return rt.w4_scanner
    ex=Executor(work/'runs',factory,scanner,safety_factory=safety);run_id='w4case-'+uuid.uuid4().hex[:16];recovery=None
    original_append=Journal.append
    def fault_append(j,kind,data):
        if case=='journal-enospc' and kind=='intent' and data.get('action')=='start-crawl':j.io_failed=True;injected.append({'case':case,'at':time.monotonic(),'faultKind':'injected-ENOSPC; real kernel storage fixture tested separately'})
        if case=='journal-enospc' and j.io_failed:raise OSError(errno.ENOSPC,'owned controller injection')
        return original_append(j,kind,data)
    started=time.monotonic()
    with patch.object(Journal,'append',fault_append):
        try:result=ex.run(plan,run_id,interrupt_after_start=case=='interrupt')
        except InjectedCrash:
            folder=work/'runs'/run_id;raw=(folder/'journal.jsonl').read_bytes();result=ex.recover(folder)
            recovery={'originalJournalUnchanged':(folder/'journal.jsonl').read_bytes()==raw,'originalJournalSha256':hashlib.sha256(raw).hexdigest(),'mode':'stop-only'}
    rt=runtimes[0];s=supervisors[0];folder=work/'runs'/run_id
    verification=None
    if result.get('bundle'):
        m=verify_bundle(result['bundle']);verification={k:m[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')}
    events=list(map(json.loads,(folder/'journal.jsonl').read_bytes().splitlines()))
    captures=capture_snapshot([folder/'zap-workspace/sender-events.jsonl',folder/'fixture/boundary.jsonl',folder/'fixture/arrivals.jsonl'])
    try:traffic=correlate(*captures,terminal=True)
    except Exception as exc:
        try:
            traffic=correlate(*captures,terminal=False);traffic['terminalComplete']=False;traffic['terminalReason']=type(exc).__name__+':'+str(exc)[:120]
        except Exception as inner:traffic={'complete':False,'reason':type(inner).__name__+':'+str(inner)[:120]}
    proof=active_proof(getattr(getattr(rt,'w4_scanner',None),'active_progress',[]),traffic) if plan.data['workflow']['active'] and case=='normal' else None
    no_resources=not docker(['ps','-aq','--filter','label=zpa.run='+run_id]).strip()
    passed=(verification is not None and result['executionStatus']=='completed' and result['evidenceStatus']=='complete' and result['cleanupStatus']=='clean') if case=='normal' else (result['gateDecision']=='block' and not (folder/'bundle').exists() and result['cleanupStatus']=='clean')
    if proof is not None:passed=passed and proof['pass']
    if case=='normal':passed=passed and s.result['resources']['monitoredThrough']=='all workloads stopped and removed' and s.result['resources']['maxObservedGapSeconds']<=5
    if case in ('disabled-rule','unknown-active'):passed=passed and s.policy.failure=='unexpected active rule traffic' and any(e['producer']=='active' and not e['forwarded'] and e['ruleId']==('990001' if case=='disabled-rule' else None) for e in traffic.get('events',[]))
    if case=='phase-deviation':passed=passed and s.policy.failure=='active producer outside phase policy' and any(e['producer']=='active' and e['phase']=='settle' and not e['forwarded'] and e['ruleId']=='40012' for e in traffic.get('events',[]))
    if case in ('inventory-drift','addon-drift'):passed=passed and s.policy.failure=='effective policy inventory drift'
    if case=='lost-start-ack':passed=passed and len(injected)==1 and sum(e['kind']=='intent' and e['data'].get('action')=='start-crawl' for e in events)==1
    if case=='interrupt':passed=passed and recovery['originalJournalUnchanged']
    if case=='journal-enospc':passed=passed and result['reason']=='journal-write-failure' and not any(e['kind']=='intent' and e['data'].get('action')=='start-crawl' for e in events)
    report={'schemaVersion':'w4-conformance/1.0','case':case,'sourceDigest':implementation_digest(),'planHash':plan.hash,'safetyHash':expected,'result':result,'activePolicyProof':proof,'activeProgress':getattr(getattr(rt,'w4_scanner',None),'active_progress',[]),'verification':verification,'recovery':recovery,'runRef':str(folder),'diagnostics':diagnostics,'injected':injected,'policyFailure':s.policy.failure,'resourceFailure':s.resource.failure,'safetyFailure':s.failure,'stopConfirmed':s.stop_confirmed,'safetyResult':s.result,'traffic':traffic,'noOwnedResources':no_resources,'elapsedSeconds':time.monotonic()-started,'expectedOutcomeObserved':bool(passed and no_resources),'productTargetRequests':0,'securityApproval':False,'limits':['Synthetic owned fixture only','CONNECT disposition has no TLS response/application proof','Fault injection does not prove a real built-in rule defect or shared daemon outage','No active technique,auth,browser or product acceptance']}
    write_file(output.parent,output.name,canonical(report));return report

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('mode',choices=['prepare','run']);ap.add_argument('--work-dir',required=True,type=Path);ap.add_argument('--calibration-report',type=Path);ap.add_argument('--case',choices=CASES,default='normal');ap.add_argument('--output',type=Path);ap.add_argument('--expect-safety-hash');a=ap.parse_args()
    if a.mode=='prepare':r=prepare(a.work_dir.absolute(),a.calibration_report.absolute(),a.case);print(json.dumps(r));return 0
    r=run(a.work_dir.absolute(),a.output.absolute(),a.expect_safety_hash);print(json.dumps({k:r[k] for k in ('case','result','policyFailure','expectedOutcomeObserved','noOwnedResources')}));return 0 if r['expectedOutcomeObserved'] else 2
if __name__=='__main__':sys.exit(main())
