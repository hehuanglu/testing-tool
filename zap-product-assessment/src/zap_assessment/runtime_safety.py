"""W4 policy/resource containment. No authority, auth mode or security-pass grant."""
import copy
import hashlib
import json
import math
import os
import stat
from pathlib import Path
import threading
import time
from .contracts import Blocked,canonical,digest

GIB=1024**3

def _integer(v):return type(v) is int and v>=0

def _calibration(contract,plan):
    """Read pinned metadata, never a credential source or an inline growth claim."""
    from .capabilities import _json
    path=Path(contract['calibration']['evidenceRef'])
    if not path.is_absolute() or any(p in ('.','..') for p in path.parts):raise Blocked('calibration reference must be absolute')
    fd=os.open('/',os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
    try:
        for part in path.parts[1:-1]:
            next_fd=os.open(part,os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW,dir_fd=fd);os.close(fd);fd=next_fd
        data_fd=os.open(path.name,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK,dir_fd=fd)
        with os.fdopen(data_fd,'rb') as f:
            before=os.fstat(f.fileno())
            if not stat.S_ISREG(before.st_mode) or before.st_nlink!=1 or before.st_size>1048576:raise Blocked('calibration evidence unreadable')
            raw=f.read(1048577);after=os.fstat(f.fileno())
            if len(raw)!=before.st_size or (before.st_ino,before.st_mtime_ns,before.st_ctime_ns)!=(after.st_ino,after.st_mtime_ns,after.st_ctime_ns):raise Blocked('calibration evidence changed')
    except OSError as exc:raise Blocked('calibration evidence unreadable') from exc
    finally:os.close(fd)
    if hashlib.sha256(raw).hexdigest()!=contract['calibration']['evidenceSha256']:raise Blocked('calibration checksum mismatch')
    c=_json(raw)
    fields={'schemaVersion','measurementKind','sourceDigest','runtimePins','workflowHash','productHash','growth','ramPeakBytes','completedPhases','observations'}
    if not isinstance(c,dict) or set(c)!=fields or c['schemaVersion']!=('runtime-calibration/1.2' if plan.data['workflow']['active'] else 'runtime-calibration/1.1') or c['measurementKind']!='scanner-topology':raise Blocked('scanner growth calibration missing')
    if any(c[k]!=contract[k] for k in ('sourceDigest','runtimePins','growth')) or c['workflowHash']!=digest(plan.data['workflow']) or c['productHash']!=digest(plan.data['product']):raise Blocked('calibration topology/source/workload drift')
    if c['completedPhases']!=['startup','crawl']+(['active'] if plan.data['workflow']['active'] else [])+['settle','report','cleanup'] or not _integer(c['ramPeakBytes']) or not 0<c['ramPeakBytes']<=contract['ramHeadroomBytes']:raise Blocked('RAM candidate calibration unproven')
    rows=c['observations']
    if not isinstance(rows,list) or len(rows)<2:raise Blocked('growth timeline missing')
    previous=-1
    for r in rows:
        if not isinstance(r,dict) or set(r)!={'at','hostGrowth','dockerGrowth'}:raise Blocked('growth observation invalid')
        if type(r['at']) not in (int,float) or not math.isfinite(r['at']) or r['at']<=previous:raise Blocked('growth timeline invalid')
        if any(not _integer(r[k]) for k in ('hostGrowth','dockerGrowth')) or r['hostGrowth']>c['growth']['host'] or r['dockerGrowth']>c['growth']['docker']:raise Blocked('growth estimate below observed usage')
        previous=r['at']
    return c

class ResourceGate:
    def __init__(self,contract,sampler,clock=time.monotonic):
        self.contract=copy.deepcopy(contract);self.sampler=sampler;self.clock=clock;self.last=None;self.failure=None;self.samples=[];self.mutex=threading.RLock()
    def _fail(self,reason):self.failure=reason;raise Blocked(reason)
    def required_ram(self,preflight):return 4*GIB
    def preflight(self):
        with self.mutex:return self._preflight()
    def _preflight(self):
        c=self.contract
        if (c.get('sampleSeconds')!=5 or c.get('reserveBytes')!=2*GIB or c.get('ramHeadroomBytes')!=4*GIB
                or type(c.get('stopSeconds')) is not int or not 0<c['stopSeconds']<=120):self._fail('resource contract thresholds invalid')
        growth=c.get('growth',{})
        if set(growth)!={'host','docker'} or not all(_integer(x) and x>0 for x in growth.values()):self._fail('growth calibration missing')
        if c.get('calibration',{}).get('classification')!='owned-synthetic' or len(c.get('calibration',{}).get('evidenceSha256',''))!=64:self._fail('calibration evidence missing')
        return self._sample(True)
    def _sample(self,preflight=False):
        if self.failure:raise Blocked(self.failure)
        try:s=self.sampler()
        except Exception:self._fail('resource sample unavailable')
        if not isinstance(s,dict) or s.get('dockerAvailable') is not True:self._fail('docker unavailable')
        if any(not _integer(s.get(k)) for k in ('hostFree','dockerFree','ramAvailable')):self._fail('resource measurement unknown')
        observed=self.clock()
        if self.last is not None and observed-self.last>5:self._fail('resource sampling gap exceeds contract')
        self.last=observed;self.samples.append({'at':self.last,**{k:s[k] for k in ('hostFree','dockerFree','ramAvailable','dockerAvailable')}})
        for field,place in [('hostFree','host'),('dockerFree','docker')]:
            # User revised G6 on 2026-10-19: remove the fixed 8GiB floor.
            # Keep growth-based capacity and the reserved emergency channel.
            required=2*self.contract['growth'][place]+self.contract['reserveBytes'] if preflight else self.contract['reserveBytes']
            if s[field]<required if preflight else s[field]<=required:self._fail(place+' disk reserve reached')
        if s['ramAvailable']<self.required_ram(preflight):self._fail('RAM candidate headroom reached')
        return s
    def check(self,force=False):
        with self.mutex:
            if self.failure:raise Blocked(self.failure)
            if force or self.last is None or self.clock()-self.last>=4:return self._sample()


def _inventory(value):
    if not isinstance(value,dict) or set(value)!={'addons','scripts','rules','inputVectors'}:raise Blocked('policy inventory incomplete')
    result={}
    for group,key in [('addons','id'),('scripts','name'),('rules','id')]:
        rows=value[group]
        if not isinstance(rows,list) or any(not isinstance(r,dict) or not isinstance(r.get(key),str) for r in rows):raise Blocked('policy inventory shape')
        if len({r[key] for r in rows})!=len(rows):raise Blocked('duplicate policy inventory identity')
        for r in rows:
            if group=='addons' and (set(r)!={'id','version'} or not isinstance(r['version'],str)):raise Blocked('addon pin missing')
            if group=='rules' and (set(r)!={'id','enabled'} or type(r['enabled']) is not bool):raise Blocked('rule state missing')
            if group=='scripts' and (set(r)!={'name','type','enabled','sha256'} or type(r['enabled']) is not bool or not isinstance(r['type'],str) or not isinstance(r['sha256'],str) or len(r['sha256'])!=64):raise Blocked('script content pin missing')
        result[group]=sorted(copy.deepcopy(rows),key=lambda r:r[key])
    vectors=value['inputVectors']
    if not isinstance(vectors,list) or not vectors or any(not isinstance(v,str) or not v for v in vectors) or len(set(vectors))!=len(vectors):raise Blocked('input vector pin missing')
    result['inputVectors']=sorted(vectors);return result


class EffectivePolicy:
    def __init__(self,expected,*,active_execution_allowed=True,require_phase=False):
        if type(active_execution_allowed) is not bool:raise Blocked('active execution policy unknown')
        self.active_execution_allowed=active_execution_allowed;self.require_phase=require_phase
        self.expected=_inventory(expected);self.hash=digest(self.expected);self.snapshots=[];self.failure=None;self.events={};self.complete=False
    def _fail(self,reason):self.failure=reason;raise Blocked(reason)
    def snapshot(self,phase,observed):
        if self.failure:raise Blocked(self.failure)
        if phase not in ('before','during','after'):self._fail('policy phase unknown')
        if _inventory(observed)!=self.expected:self._fail('effective policy inventory drift')
        self.snapshots.append({'phase':phase,'inventoryHash':self.hash,'inventory':copy.deepcopy(self.expected)})
    def traffic(self,events,*,complete):
        if self.failure:raise Blocked(self.failure)
        if type(complete) is not bool or not isinstance(events,list):self._fail('egress capture missing')
        active={r['id'] for r in self.expected['rules'] if r['enabled']}
        for e in events:
            required={'requestId','producer','ruleId','forwarded','boundaryCorrelated','targetAllowed','credentialForwarded','unsupportedVectors'}
            if self.require_phase:required.add('phase')
            elif isinstance(e,dict) and 'phase' in e:required.add('phase')
            if (not isinstance(e,dict) or set(e)!=required or not isinstance(e.get('requestId'),str) or not e['requestId']
                    or type(e['forwarded']) is not bool or type(e['boundaryCorrelated']) is not bool
                    or type(e['targetAllowed']) is not bool or type(e['credentialForwarded']) is not bool
                    or not isinstance(e['unsupportedVectors'],list)):
                self._fail('egress record incomplete')
            identity=e['requestId']
            if identity in self.events and self.events[identity]!=e:self._fail('egress correlation changed')
            if not e['boundaryCorrelated']:self._fail('unknown request attribution')
            # An attempted producer outside the expected policy is a deviation
            # even when the boundary successfully contains it before the target.
            if e['producer'] not in ('active','active-control','crawl','manual','import','seed','control','passive','background'):self._fail('unknown request attribution')
            if e['producer']=='active' and e['ruleId'] not in active:self._fail('unexpected active rule traffic')
            if e['producer'] in ('active','active-control') and not self.active_execution_allowed:self._fail('active producer outside workflow policy')
            if e['producer'] in ('active','active-control') and self.require_phase and e.get('phase')!='active':self._fail('active producer outside phase policy')
            if e['producer']!='active' and e['ruleId'] is not None:self._fail('ambiguous rule attribution')
            if e['forwarded']:
                if not e['targetAllowed'] or e['credentialForwarded']:self._fail('forbidden forwarding')
                if e['unsupportedVectors']:self._fail('input vector fidelity unproven')
            self.events[identity]=copy.deepcopy(e)
        self.complete=complete
    def finalize(self):
        if self.failure:raise Blocked(self.failure)
        phases=[s['phase'] for s in self.snapshots]
        if not phases or phases[0]!='before' or phases[-1]!='after' or 'during' not in phases or not self.complete:self._fail('policy lifecycle or egress proof missing')
        expected={r['id'] for r in self.expected['rules'] if r['enabled']}
        observed={e['ruleId'] for e in self.events.values() if e['producer']=='active' and e['forwarded']}
        if self.require_phase and self.active_execution_allowed and observed!=expected:self._fail('observed active rule set mismatch')
        counts={k:sum(e['forwarded'] and e['producer']==k for e in self.events.values()) for k in ('active','active-control','crawl','manual','import','seed','control','passive','background')}
        return {'policyHash':self.hash,'activeExecutionAllowed':self.active_execution_allowed,'expectedActiveRules':sorted(expected) if self.active_execution_allowed else [],'observedActiveRules':sorted(observed),'inventoryStatus':'pass','egressStatus':'pass','trafficByProducer':counts,'snapshots':self.snapshots,'eventCount':len(self.events),'securityApproval':False,'techniqueVerified':False}


class SafetySupervisor:
    def __init__(self,runtime,journal,contract,expected_hash,clock=time.monotonic):
        self.rt=runtime;self.journal=journal;self.contract=copy.deepcopy(contract);self.expected_hash=expected_hash;self.clock=clock
        self.resource=ResourceGate(contract,runtime.resource_sample,clock);self.policy=EffectivePolicy(contract.get('policy',{}),active_execution_allowed=runtime.plan.data['workflow']['active'],require_phase=getattr(runtime,'phase_capture',False))
        self.failure=None;self.cancel=threading.Event();self.thread=None;self.lock=threading.RLock();self.stop_confirmed=None;self.result=None;self.ready=False
    def preflight(self):
        from .executor import implementation_digest
        from .contracts import ROOT
        from jsonschema import Draft202012Validator
        c=self.contract
        schema=json.loads((ROOT/'schemas/remediation/runtime-safety.schema.json').read_text())
        if list(Draft202012Validator(schema).iter_errors(c)):raise Blocked('runtime safety schema invalid')
        fields={'schemaVersion','planHash','growth','calibration','policy','sampleSeconds','reserveBytes','ramHeadroomBytes','stopSeconds','runtimePins','sourceDigest'}
        if set(c)!=fields or c['schemaVersion']!='runtime-safety/1.0' or not self.expected_hash or digest(c)!=self.expected_hash:raise Blocked('runtime safety external contract pin missing or drifted')
        if c['planHash']!=self.rt.plan.hash or c['sourceDigest']!=implementation_digest() or c['runtimePins']!=self.rt.plan.data['runtime']:raise Blocked('runtime safety plan/source/image binding mismatch')
        self.calibration=_calibration(c,self.rt.plan)
        self.resource.preflight()
        self.journal.append('safety-preflight',{'contractHash':self.expected_hash,'planHash':c['planHash'],'resourceSample':self.resource.samples[-1]})
        # Startup/health can take longer than five seconds. Watch resources from
        # preflight; policy audits begin only after capture has been installed.
        self.thread=threading.Thread(target=self._watch,daemon=True,name='assessment-safety-monitor');self.thread.start()
    def audit(self,phase):
        with self.lock:
            if self.failure:raise Blocked(self.failure)
            self.resource.check(force=True)
            self.policy.snapshot(phase,self.rt.policy_inventory())
            data=self.rt.policy_traffic()
            if data.get('complete') is not True:raise Blocked('egress monitor coverage unproven')
            self.policy.traffic(data['events'],complete=data['complete'])
            self.journal.append('safety-sample',{'phase':phase,'monotonicAt':self.clock(),'resourceSample':self.resource.samples[-1],'policyHash':self.policy.hash,'egressRecords':len(self.policy.events)})
    def start(self):
        self.audit('before')
        self.ready=True
    def _watch(self):
        # Start one second early to leave room for a bounded measurement. A
        # completed sample gap over5s is itself a blocking observation gap.
        # Leave time for the sampler itself; the contract bounds completed reads.
        while not self.cancel.wait(max(0,self.resource.last+1-self.clock())):
            try:
                if self.ready:self.audit('during')
                else:self.resource.check(force=True)
            except Exception as exc:
                self.failure=type(exc).__name__
                reason=self.resource.failure or self.policy.failure or 'capture_or_writer_failure'
                try:self.journal.append('safety-latch',{'reasonCode':reason,'monotonicAt':self.clock(),'stopBudgetSeconds':self.contract['stopSeconds']})
                except Exception:pass
                # One bounded stop of this runtime only; never restart a daemon.
                try:self.stop_confirmed=self.rt.terminate() is True
                except Exception:self.stop_confirmed=False
                try:
                    self.journal.append('safety-stop',{'confirmed':self.stop_confirmed,'monotonicAt':self.clock()})
                    if hasattr(self.rt,'stop_reserve'):self.rt.stop_reserve.record({'state':'safety-stop','stopUnconfirmed':not self.stop_confirmed,'cleanupStatus':'pending','reasonCode':reason})
                except Exception:pass
                return
    def checkpoint(self):
        if self.failure:raise Blocked('runtime safety latch: '+self.failure)
        try:self.resource.check()
        except Exception as exc:self.failure=type(exc).__name__;raise
    def finish(self):
        self.close();self.audit('during');self.audit('after');self.result=self.policy.finalize()
        if getattr(self.rt,'phase_capture',False):
            self.rt.set_phase('cleanup');self.rt.resource_cleanup=True;self.ready=False
            self.rt.cleanup_measurement_helper=self.rt.probe_name
            self.rt.cleanup_measurement_close=self.seal_cleanup
            self.rt.cleanup_resource_lock=self.resource.mutex
            self.rt.cleanup_resource_tick=lambda:self.resource.check(force=True) if not self.resource.failure else None
            self.cancel.clear();self.thread=threading.Thread(target=self._watch,daemon=True,name='cleanup-resources');self.thread.start()
        samples=self.resource.samples
        self.result['resources']={'samples':samples,'maxObservedGapSeconds':max((b['at']-a['at'] for a,b in zip(samples,samples[1:])),default=0),'samplePeriodSeconds':5,'candidateRamHeadroomBytes':4*GIB}
        return self.result
    def seal_cleanup(self):
        self.close();self.resource.check(force=True)
        self.cleanup_sealed=self.clock()
        self.journal.append('resource-monitor-sealed',{'monotonicAt':self.cleanup_sealed,'allWorkloadsRemoved':True,'helper':self.rt.probe_name,'boundedRemovalSeconds':5})
    def cleanup_complete(self):
        if not getattr(self.rt,'phase_capture',False):return
        if not hasattr(self,'cleanup_sealed'):raise Blocked('cleanup resource seal missing')
        elapsed=self.clock()-self.cleanup_sealed
        if elapsed>5:raise Blocked('measurement helper shutdown exceeded sampling contract')
        self.checkpoint_after_cleanup=True
        samples=self.resource.samples
        self.result['resources'].update({'samples':samples,'maxObservedGapSeconds':max((b['at']-a['at'] for a,b in zip(samples,samples[1:])),default=0),'monitoredThrough':'all workloads stopped and removed','measurementHelperShutdownSeconds':elapsed,'sealedAtMonotonic':self.cleanup_sealed})
        if self.failure:raise Blocked('cleanup resource latch')
    def close(self):
        self.cancel.set()
        if self.thread is not None:
            self.thread.join(timeout=self.contract['stopSeconds']+15)
            if self.thread.is_alive():self.failure='monitor stop unconfirmed';raise Blocked(self.failure)
