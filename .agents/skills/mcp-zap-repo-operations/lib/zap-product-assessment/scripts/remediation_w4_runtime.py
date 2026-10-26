#!/usr/bin/env python3
"""Owned anonymous scanner calibration; never a product or authenticated scan.

Calibration always blocks bundle publication. Only measured complete workflow
phases can create reusable calibration metadata; threshold failures stay blocked.
"""
import argparse,hashlib,json,os,sys,time,threading,uuid
from pathlib import Path
from datetime import datetime,timezone
P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'src')]
from zap_assessment.contracts import Blocked,canonical,digest,make_plan
from zap_assessment.executor import Executor,implementation_digest
from zap_assessment.observed import ObservedDockerRuntime
from zap_assessment.w4_fixture import inputs as fixture_inputs,W4Scanner as LiveScanner
from zap_assessment.transport import MCP
from zap_assessment.runtime_safety import GIB,ResourceGate,EffectivePolicy,SafetySupervisor
from zap_assessment.evidence import write_file

class CalibrationSupervisor:
    """Bounded synthetic measurement with growth-based disk capacity.

    It cannot pass the normal external calibration gate and deliberately refuses
    publication. No fabrication of an already completed calibration file.
    """
    def __init__(self,rt,journal):
        self.rt=rt;self.journal=journal;self.failure=None;self.stop_confirmed=None;self.thread=None;self.stop=threading.Event();self.lock=threading.RLock();self.policy=None;self.ready=False;self.completed=False;self.expected_hash='calibration-only';self.result=None
        self.contract={'sampleSeconds':5,'reserveBytes':2*GIB,'ramHeadroomBytes':4*GIB,'stopSeconds':120,'growth':{'host':GIB,'docker':GIB},'calibration':{'classification':'owned-synthetic','evidenceSha256':'0'*64}}
        self.resource=ResourceGate(self.contract,rt.resource_sample)
    def preflight(self):
        if self.rt.plan.data['product']['adapter']!='synthetic-http-v1':raise Blocked('calibration only owned anonymous fixture')
        self.resource.preflight();self.thread=threading.Thread(target=self.watch,name='calibration-resources',daemon=True);self.thread.start()
    def watch(self):
        # Sampling itself takes time; start early enough that completed readings
        # still obey the unchanged five-second maximum interval.
        while not self.stop.wait(max(0,self.resource.last+1-time.monotonic())):
            try:
                if self.ready:self.audit('during')
                else:self.resource.check(force=True)
            except Exception as exc:
                self.failure=type(exc).__name__+':'+str(exc)[:100]
                try:self.stop_confirmed=self.rt.terminate() is True
                except Exception:self.stop_confirmed=False
                return
    def checkpoint(self):
        if self.failure:raise Blocked('calibration safety latch '+self.failure)
        self.resource.check()
    def start(self):
        self.checkpoint()
        with self.lock:
            initial=self.rt.policy_inventory()
            write_file(self.rt.root,'calibration-initial-inventory.json',canonical(initial))
            self.policy=EffectivePolicy(initial,active_execution_allowed=self.rt.plan.data['workflow']['active'],require_phase=True);self.policy.snapshot('before',self.rt.policy_inventory());self.ready=True
        self.audit('during')
    def audit(self,phase):
        with self.lock:
            self.resource.check(force=True)
            self.policy.snapshot(phase,self.rt.policy_inventory());data=self.rt.policy_traffic();self.policy.traffic(data['events'],complete=data['complete'])
    def close(self):
        self.stop.set()
        if self.thread:
            self.thread.join(130)
            if self.thread.is_alive():raise Blocked('calibration stop unconfirmed')
    def finish(self):
        self.close();self.checkpoint();self.audit('during');self.audit('after');self.policy_result=self.policy.finalize();self.result=self.policy_result
        self.result['resources']={'samples':self.resource.samples}
        self.rt.set_phase('cleanup');self.rt.resource_cleanup=True;self.ready=False
        self.rt.cleanup_measurement_helper=self.rt.probe_name;self.rt.cleanup_measurement_close=self.seal_cleanup
        self.rt.cleanup_resource_lock=self.resource.mutex
        self.rt.cleanup_resource_tick=lambda:self.resource.check(force=True) if not self.resource.failure else None
        self.stop.clear();self.thread=threading.Thread(target=self.watch,name='calibration-cleanup',daemon=True);self.thread.start()
        return self.result
    def seal_cleanup(self):
        self.close();self.resource.check(force=True);self.cleanup_sealed=time.monotonic()
        self.journal.append('resource-monitor-sealed',{'monotonicAt':self.cleanup_sealed,'allWorkloadsRemoved':True,'helper':self.rt.probe_name,'boundedRemovalSeconds':5})
    def cleanup_complete(self):
        SafetySupervisor.cleanup_complete(self)
        self.completed=True
        write_file(self.rt.root,'calibration-policy.json',canonical(self.policy_result))
        raise Blocked('calibration-only workflow measured; normal publication refused')
    clock=staticmethod(time.monotonic)

def run(output,work,http_only=False,active=False):
    output=Path(output).absolute();work=Path(work).absolute()
    if output.exists() or work.exists() or output.is_symlink() or work.is_symlink():raise ValueError('fresh paths required')
    work.mkdir(mode=0o700);inputs=list(fixture_inputs(active))
    if http_only:inputs[0]['crawlPath']='/health'
    plan=make_plan(*inputs);runtimes=[];supervisors=[]
    write_file(work,'expected.json',canonical({'mode':'owned anonymous HTTP fixture; no product traffic','expected':'calibration-only block with completed startup/crawl/settle/report/cleanup; fixed8GiB floor removed by user; growth/reserve/RAM/sampling retained','noExistingCalibrationFabricated':True}))
    def factory(*a):
        rt=ObservedDockerRuntime(*a);runtimes.append(rt);rt.calibration_diagnostics=[]
        # Synthetic-only private diagnostics; Executor's public journal continues
        # to retain error types only. No credentials enter this calibration mode.
        def wrap(name):
            original=getattr(rt,name)
            def call(*args,**kwargs):
                try:return original(*args,**kwargs)
                except Exception as exc:
                    rt.calibration_diagnostics.append({'stage':name,'type':type(exc).__name__,'detail':str(exc)[:300]})
                    raise
            setattr(rt,name,call)
        for name in ('resource_sample','install_capture','policy_inventory','policy_traffic','target_request','observations'):wrap(name)
        return rt
    def safety(rt,j):
        s=CalibrationSupervisor(rt,j);supervisors.append(s)
        for name in ('preflight','start','finish'):
            original=getattr(s,name)
            def call(*args,_original=original,_name=name,**kwargs):
                try:return _original(*args,**kwargs)
                except Exception as exc:
                    rt.calibration_diagnostics.append({'stage':'safety.'+_name,'type':type(exc).__name__,'detail':str(exc)[:300]})
                    raise
            setattr(s,name,call)
        return s
    run_id='w4cal-'+uuid.uuid4().hex[:16];started=datetime.now(timezone.utc).isoformat()
    def scanner(rt):
        rt.w4_scanner=LiveScanner(MCP(rt.request),rt.engine,rt.request);return rt.w4_scanner
    result=Executor(work,factory,scanner,safety_factory=safety).run(plan,run_id)
    rt=runtimes[0];s=supervisors[0];metrics=rt.metrics
    calibration=None
    if s.completed and result['cleanupStatus']=='clean':
        peak=max((sum(r['containerMemoryPeakBytes'].values()) for r in metrics),default=0)
        if peak<=0:raise Blocked('per-container cgroup memory peak unproven')
        growth={'host':max(GIB,max(r['hostGrowth'] for r in metrics)*2),'docker':max(GIB,max(r['dockerGrowth'] for r in metrics)*2)}
        calibration={'schemaVersion':'runtime-calibration/1.2' if active else 'runtime-calibration/1.1','measurementKind':'scanner-topology','sourceDigest':implementation_digest(),'runtimePins':plan.data['runtime'],'workflowHash':digest(plan.data['workflow']),'productHash':digest(plan.data['product']),'growth':growth,'ramPeakBytes':max(1,peak),'completedPhases':['startup','crawl']+(['active'] if active else [])+['settle','report','cleanup'],'observations':[{'at':r['at'],'hostGrowth':r['hostGrowth'],'dockerGrowth':r['dockerGrowth']} for r in metrics]}
        write_file(work,'calibration.json',canonical(calibration))
    report={'schemaVersion':'w4-runtime-measurement/1.0','startedAt':started,'finishedAt':datetime.now(timezone.utc).isoformat(),'planHash':plan.hash,'result':result,'calibrationComplete':calibration is not None,'calibrationRef':str(work/'calibration.json') if calibration else None,'sourceDigest':implementation_digest(),'resourceSamples':s.resource.samples,'workloadMetrics':metrics,'policy':getattr(s,'policy_result',None),'safetyFailure':s.failure,'completeWorkflowMeasured':s.completed,'runRef':str(rt.root),'targetProductRequests':0,'securityApproval':False,'limits':['Calibration-only publication refused','Anonymous synthetic workload only; no auth/browser/vulnerability-detection acceptance','Per-owned-container cgroup memory.peak and SizeRw required; free/RAM gauges also include shared-host activity; no source-to-image attestation','Native rule identity and phase are observed; this does not prove vulnerability detection or sink coverage']}
    report['activeProgress']=getattr(getattr(rt,'w4_scanner',None),'active_progress',[])
    report['activeWorkflow']=active
    report['trafficClosure']=getattr(rt,'closure_evidence',None)
    report['diagnostics']=rt.calibration_diagnostics
    report['captureInstallReadback']=getattr(rt,'capture_install_readback',None)
    report['calibrationScope']='HTTP-only /health crawl + /health,/api/items import/seeds; excludes redirect-negative workload' if http_only else 'full redirect fixture; CONNECT refusal has an explicit unsupported disposition, no TLS application proof'
    write_file(output.parent,output.name,canonical(report));return report

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--work-dir',required=True,type=Path);ap.add_argument('--http-only',action='store_true',help='bounded resource measurement; never grants redirect/HTTPS acceptance');ap.add_argument('--active',action='store_true');a=ap.parse_args();r=run(a.output,a.work_dir,a.http_only,a.active)
    print(json.dumps({k:r[k] for k in ('calibrationComplete','completeWorkflowMeasured','safetyFailure','result','calibrationRef')}));return 0 if r['calibrationComplete'] else 2
if __name__=='__main__':sys.exit(main())
