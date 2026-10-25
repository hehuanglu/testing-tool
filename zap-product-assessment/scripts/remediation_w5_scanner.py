#!/usr/bin/env python3
"""Locked canary-only W5 integration on owned Docker ZAP/MCP, never finalsource.

The legacy anonymous plan is used only to provision the fixed synthetic network
primitives. No anonymous assessment manifest is published for protected traffic.
"""
import argparse
import base64
from datetime import datetime,timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import resource
import sys
import threading
import time
from types import SimpleNamespace
import uuid

P=Path(__file__).resolve().parents[1];sys.path[:0]=[str(P/'src')]
from zap_assessment.contracts import canonical,digest,make_plan,Blocked
from zap_assessment.errors import SecretLeak
from zap_assessment.executor import implementation_digest
from zap_assessment.journal import Journal
from zap_assessment.observed import ObservedDockerRuntime
from zap_assessment.runtime import docker
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.secret_audit import CanaryAuditor
from zap_assessment.transport import MCP
from zap_assessment.w4_fixture import inputs,W4Scanner
from zap_assessment.w5_scanner_fixture import CONTROL_CLIENT
from zap_assessment.opaque_canary import OpaqueCanaryAuditor,PUBLIC_DB_CONTROL,validate_source_boundary
from zap_assessment.traffic import capture_snapshot,correlate,read_rows
from zap_assessment.scanner_secret_audit import container_sinks,audit_database,artifact_digest
from zap_assessment.w5_resources import bounded_profile,validate_profile,verify_measurements,seed_image_cache,W5ResourceGate
from zap_assessment.private_db import CONTRACT as PRIVATE_DB_CONTRACT,CONTROL_ZONE,validate_public_receipt

spec=importlib.util.spec_from_file_location('w4_calibration',P/'scripts/remediation_w4_runtime.py')
calmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(calmod)
spec=importlib.util.spec_from_file_location('w4_conformance',P/'scripts/remediation_w4_conformance.py')
conmod=importlib.util.module_from_spec(spec);spec.loader.exec_module(conmod)
CASES=('success','crawl','active','refresh-success','expiry','refresh-failure','logout','revoke',
       'role-change','exception','cancel','restart','login-failure','cleanup','crash')
PRIVATE_SECRET_SOURCE='owned-private-file-reference-in-holder-tmpfs; host comparison hashes only'
MONITOR_CONTRACT='w5-independent-monitors/1.0'


class W5Supervisor(calmod.CalibrationSupervisor):
    """Independent completed resource/policy reads, each still bounded by 5s.

    The old single worker performed policy HTTP reads between resource samples.
    Separate workers remove that serialization, not the freshness requirement.
    Either monitor latches one owned stop; cleanup keeps resource monitoring.
    """
    def __init__(self,rt,journal):
        super().__init__(rt,journal)
        self.policy_stop=threading.Event();self.policy_thread=None
        self.failure_lock=threading.Lock();self.last_policy_at=None;self.policy_samples=[]

    def latch(self,exc):
        with self.failure_lock:
            if self.failure:return
            self.failure=type(exc).__name__+':'+str(exc)[:100]
        try:self.stop_confirmed=self.rt.terminate() is True
        except Exception:self.stop_confirmed=False

    def watch(self):
        # A completed read is the bound. Leave more headroom for CLI/VM jitter;
        # do not move timestamps or extend the unchanged five-second deadline.
        while not self.stop.wait(max(0,self.resource.last+.25-time.monotonic())):
            try:
                self.resource.check(force=True)
                if self.ready and (self.last_policy_at is None or time.monotonic()-self.last_policy_at>5):
                    raise Blocked('policy sampling gap exceeds contract')
            except Exception as exc:self.latch(exc);return

    def audit(self,phase):
        with self.lock:
            if self.failure:raise Blocked(self.failure)
            began=time.monotonic()
            inventory=self.rt.policy_inventory();data=self.rt.policy_traffic();now=time.monotonic()
            if now-began>5 or (self.last_policy_at is not None and now-self.last_policy_at>5):
                raise Blocked('policy sampling gap exceeds contract')
            self.policy.snapshot(phase,inventory);self.policy.traffic(data['events'],complete=data['complete'])
            self.policy_samples.append({'phase':phase,'startedAt':began,'completedAt':now,
                'inventoryHash':self.policy.hash,'egressRecords':len(self.policy.events)})
            self.last_policy_at=now

    def policy_watch(self):
        while not self.policy_stop.wait(1):
            try:self.audit('during')
            except Exception as exc:self.latch(exc);return

    def start(self):
        self.checkpoint()
        initial=self.rt.policy_inventory()
        save(self.rt.root/'calibration-initial-inventory.json',initial)
        self.policy=calmod.EffectivePolicy(initial,active_execution_allowed=self.rt.plan.data['workflow']['active'],require_phase=True)
        self.audit('before');self.audit('during');self.ready=True
        self.policy_thread=threading.Thread(target=self.policy_watch,name='w5-policy',daemon=True)
        self.policy_thread.start()

    def close_policy(self):
        self.policy_stop.set()
        if self.policy_thread:
            self.policy_thread.join(130)
            if self.policy_thread.is_alive():raise Blocked('policy monitor stop unconfirmed')

    def finish(self):
        # Keep the independent resource worker alive through final policy reads.
        self.close_policy();self.checkpoint();self.audit('during');self.audit('after')
        self.policy_result=self.policy.finalize();self.result=self.policy_result
        self.result['resources']={'samples':self.resource.samples}
        self.rt.set_phase('cleanup');self.rt.resource_cleanup=True;self.ready=False
        self.rt.cleanup_measurement_helper=self.rt.probe_name;self.rt.cleanup_measurement_close=self.seal_cleanup
        self.rt.cleanup_resource_lock=self.resource.mutex
        self.rt.cleanup_resource_tick=lambda:self.resource.check(force=True) if not self.resource.failure else None
        return self.result

    def close(self):
        self.close_policy();super().close()


def verify_policy_monitor(result):
    rows=result.get('policyMonitorSamples');snapshots=(result.get('policy') or {}).get('snapshots',[])
    if (result.get('monitorContract')!=MONITOR_CONTRACT or not isinstance(rows,list) or len(rows)<3
            or len(rows)!=len(snapshots)):
        raise Blocked('independent policy monitor receipts incomplete')
    previous=None
    for row,snapshot in zip(rows,snapshots):
        began=row.get('startedAt');end=row.get('completedAt');count=row.get('egressRecords')
        if (any(type(t) not in (int,float) or not math.isfinite(t) for t in (began,end))
                or not 0<=end-began<=5 or (previous is not None and not 0<end-previous<=5)
                or row.get('phase')!=snapshot.get('phase') or row.get('inventoryHash')!=snapshot.get('inventoryHash')
                or type(count) is not int or count<0):raise Blocked('policy freshness or snapshot receipt contradicted')
        previous=end


def source_mode(plan):
    if plan.get('schemaVersion')=='w5-scanner-plan/1.0' and plan.get('sourceMode','generated')=='generated':
        return 'generated'
    if (plan.get('schemaVersion') in ('w5-scanner-plan/1.1','w5-scanner-plan/1.2') and plan.get('sourceMode')=='private-file'
            and plan.get('sourceContract')=='owned-private-source/1.0'
            and plan.get('allowedSourceZone')=='/tmp/w5-private-source'
            and plan.get('secretSource')==PRIVATE_SECRET_SOURCE):return 'private-file'
    raise Blocked('W5 source contract invalid')


def private_db_mode(plan):
    if plan.get('schemaVersion')=='w5-scanner-plan/1.2':
        if (source_mode(plan)!='private-file' or plan.get('privateDbControls') is not True
                or plan.get('privateDbContract')!=PRIVATE_DB_CONTRACT
                or plan.get('allowedPrivateControlZone')!=CONTROL_ZONE
                or not isinstance(plan.get('privateDbReaderSourceSha256'),str)
                or len(plan['privateDbReaderSourceSha256'])!=64
                or any(c not in '0123456789abcdef' for c in plan['privateDbReaderSourceSha256'])):raise Blocked('private database contract invalid')
        return True
    if any(k in plan for k in ('privateDbControls','privateDbContract','allowedPrivateControlZone','privateDbReaderSourceSha256')):
        raise Blocked('private database controls require explicit plan1.2')
    return False


def validate_source_metadata(value,run_id,plan_hash):
    if (not isinstance(value,dict) or value.get('schemaVersion')!='owned-private-source/1.0'
            or value.get('runId')!=run_id or value.get('planHash')!=plan_hash
            or value.get('sourceKind')!='owned-guard-private-file-reference' or value.get('filesystem')!='tmpfs'
            or value.get('zonePath')!='/tmp/w5-private-source'
            or value.get('sourceValuesIncluded') is not False or value.get('contentHashesIncluded') is not False):
        raise Blocked('private source metadata binding invalid')
    fields={'inode','device','bytes','uid','gid','links','mode','mtimeNs','ctimeNs'}
    zone=value.get('zone',{})
    rows=value.get('files')
    if (not isinstance(rows,list) or any(not isinstance(r,dict) for r in rows)
            or [r.get('actorRef') for r in rows]!=['A','B']
            or not isinstance(zone,dict) or set(zone)!=fields):raise Blocked('private source inventory incomplete')
    for row,is_file in [(zone,False),*[(r,True) for r in rows]]:
        if (not isinstance(row,dict) or any(type(row.get(k)) is not int or row[k]<0 for k in fields)
                or row['uid']!=1003 or row['gid']!=1003 or row['mode']!=(0o600 if is_file else 0o700)
                or row['inode']<=0 or row['mtimeNs']<=0 or row['ctimeNs']<=0):
            raise Blocked('private source permissions or identity unproven')
        if is_file and (row['links']!=1 or not 1<=row['bytes']<=16384
                or set(row)!=fields|{'actorRef','referenceId','relativePath'}
                or row['referenceId']!='owned-private-file:'+row['actorRef']
                or row['relativePath']!=row['actorRef']+'.json'):
            raise Blocked('private source file contract invalid')
    return value


def capture_source(rt,stage,plan):
    info=rt.check_owner(rt.names[1]);host=info['HostConfig'];options=set((host.get('Tmpfs') or {}).get('/tmp','').split(','))
    if (info['Config'].get('User')!='1003:1003' or host.get('ReadonlyRootfs') is not True
            or not {'rw','size=16m','uid=1003','gid=1003','mode=0700'}<=options):
        raise Blocked('private source holder mount/UID unproven')
    value=rt.control({'op':'source-status'})
    if value.get('sourceMode')!='private-file' or value.get('sourceValuesIncluded') is not False:
        raise Blocked('private source status invalid')
    if value.get('sourceCreated') is True:
        validate_source_metadata(value.get('sourceMetadata'),plan['runId'],digest(plan))
        rt.source_zone_verified=True
    receipt={'stage':stage,'containerId':info['Id'],'imageId':info['Image'],
            'holderUser':info['Config']['User'],'readonlyRoot':host['ReadonlyRootfs'],
            'tmpfsOptions':sorted(options),'sourceStatus':value}
    save(rt.root/('source-'+stage+'.json'),receipt)
    return receipt


def verify_source_receipts(result,plan,records,target,journal):
    expected=['before-source','after-source']+['case-'+c for c in plan['cases'] if c!='crash']
    receipts=result.get('privateSourceReceipts')
    if not isinstance(receipts,list) or [r.get('stage') for r in receipts]!=expected:
        raise Blocked('private source lifecycle receipts incomplete')
    identity=None;metadata=None
    for index,row in enumerate(receipts):
        current=(row.get('containerId'),row.get('imageId'))
        if identity is None:identity=current
        elif identity!=current:raise Blocked('private source holder identity drift')
        opts=row.get('tmpfsOptions',[])
        if (row.get('holderUser')!='1003:1003' or row.get('readonlyRoot') is not True
                or not isinstance(opts,list) or not {'rw','size=16m','uid=1003','gid=1003','mode=0700'}<=set(opts)):
            raise Blocked('private source mount receipt invalid')
        status=row.get('sourceStatus',{})
        if status.get('sourceMode')!='private-file' or status.get('sourceValuesIncluded') is not False:
            raise Blocked('private source status receipt invalid')
        if index==0:
            if (status.get('sourceCreated') is not False or status.get('sourceMetadata') is not None
                    or status.get('tmpfsPaths')!=['w5-control.sock']):
                raise Blocked('private source existed before locked source binding')
        else:
            value=validate_source_metadata(status.get('sourceMetadata'),plan['runId'],digest(plan))
            if (status.get('sourceCreated') is not True
                    or status.get('tmpfsPaths')!=['w5-control.sock','w5-private-source']):
                raise Blocked('private source tmpfs inventory contradicted')
            if metadata is None:metadata=value
            elif value!=metadata:raise Blocked('private source file identity changed across lifecycle')
    created={e['data'].get('containerId'):e['data'] for e in journal.events
             if e['kind']=='ack' and e['data'].get('action')=='container-create'}
    if (identity[0] not in created or created[identity[0]].get('resource')!='zpa-'+plan['runId']+'-fixture'
            or identity[1]!=plan['runtimePins']['python'].split('@')[-1]):
        raise Blocked('private source not bound to holder creation ACK/image')
    cases=[c for c in plan['cases'] if c!='crash']
    if len(records)!=len(cases) or sorted(r.get('caseId') for r in records)!=sorted(cases):
        raise Blocked('private source reference resolutions incomplete')
    source=next(r for r in metadata['files'] if r['actorRef']==plan['actorRef'])
    for row in records:
        at=row.get('atMonotonic');logins=[t for t in target if t.get('caseId')==row.get('caseId') and t.get('event')=='login']
        if (row.get('event')!='private_source_resolved' or row.get('runId')!=plan['runId']
                or row.get('planHash')!=digest(plan) or row.get('sourceKind')!='owned-guard-private-file-reference'
                or row.get('sourceValuesIncluded') is not False or row.get('contentHashesIncluded') is not False
                or row.get('source')!=source or type(at) not in (int,float) or not math.isfinite(at)
                or len(logins)!=1 or not 0<=logins[0]['atMonotonic']-at<=8):
            raise Blocked('private source resolution/target login binding contradicted')
    return {'sourceContractStatus':'private-file-diagnostic-pass','resolutions':len(records),
            'privateFileMcpScannerProof':True,'operationalAdmission':False}


def save(path,value):atomic_bytes(path,canonical(value))


def source_pin():
    return {'implementation':implementation_digest(),
            'harness':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'calibrationHarness':hashlib.sha256((P/'scripts/remediation_w4_runtime.py').read_bytes()).hexdigest(),
            'conformanceHarness':hashlib.sha256((P/'scripts/remediation_w4_conformance.py').read_bytes()).hexdigest()}


def prepare(work,actor,resource_profile='legacy',source='generated',private_db=False):
    if actor not in ('A','B'):raise Blocked('unknown W5 actor')
    if source not in ('generated','private-file'):raise Blocked('unknown W5 source mode')
    if type(private_db) is not bool or (private_db and source!='private-file'):
        raise Blocked('private database control requires private-file source')
    work=Path(work).absolute();work.mkdir(mode=0o700)
    plan={'schemaVersion':'w5-scanner-plan/1.0','runId':'w5live-'+uuid.uuid4().hex[:14],
          'actorRef':actor,'scope':'owned-synthetic-delegated-canary','cases':list(CASES),
          'sourcePins':source_pin(),'runtimePins':json.loads((P/'profiles/runtime-baseline.json').read_bytes()),
          'budgets':{'identityPollSeconds':.5,'requestTimeoutSeconds':2,'stopRequestSeconds':10,'terminalSeconds':120},
          'secretSource':'owned-guard-memory-generated; host comparison hashes only',
          'expected':'all lifecycle outcomes + actual sink audit; missing decoder/access blocks G3',
          'operationalAdmission':False,'productRequests':0,'browserAdmission':False}
    plan['monitorContract']=MONITOR_CONTRACT
    if source=='private-file':
        plan.update(schemaVersion='w5-scanner-plan/1.1',sourceMode='private-file',
                    sourceContract='owned-private-source/1.0',allowedSourceZone='/tmp/w5-private-source',
                    secretSource=PRIVATE_SECRET_SOURCE)
    if private_db:
        plan.update(schemaVersion='w5-scanner-plan/1.2',privateDbControls=True,
                    privateDbContract=PRIVATE_DB_CONTRACT,allowedPrivateControlZone=CONTROL_ZONE,
                    privateDbReaderSourceSha256=hashlib.sha256((P/'src/zap_assessment/probes/SessionDbReadback.java').read_bytes()).hexdigest())
    if resource_profile=='bounded-fixture':plan['resourceProfile']=bounded_profile(P.parent)
    elif resource_profile!='legacy':raise Blocked('unknown W5 resource profile')
    save(work/'w5-plan.json',plan)
    return {'planHash':digest(plan),'runId':plan['runId'],'workDir':str(work)}


class Runtime(ObservedDockerRuntime):
    def resource_sample(self):
        try:return self._resource_sample()
        except Exception as exc:
            if not hasattr(self,'resource_diagnostics'):self.resource_diagnostics=[]
            self.resource_diagnostics.append({'stage':getattr(self,'resource_stage','initial'),
                                              'type':type(exc).__name__})
            raise
    def artifact_bytes(self):
        # Phase and other atomic writers can rename a pending file between
        # directory enumeration and stat. Retry the bounded snapshot; unreadable
        # or persistently changing storage still fails the resource sample.
        for _ in range(5):
            try:return sum(f.stat().st_size for f in self.root.rglob('*') if f.is_file() and not f.is_symlink())
            except FileNotFoundError:continue
        raise Blocked('artifact size snapshot unstable')
    def _resource_sample(self):
        timing_start=time.monotonic();timings={}
        self.resource_stage='initial'
        if self.probe_name is None:return super().resource_sample()
        removed={e['data']['resource'] for e in self.journal.events if e['kind']=='ack' and e['data'].get('action')=='container-removed'}
        names=[n for n in self.names if n!=self.probe_name and n in self.created and n not in removed]
        self.resource_stage='inspect-before'
        infos=json.loads(docker(['inspect',*names],timeout=3)) if names else []
        timings['inspectBeforeSeconds']=time.monotonic()-timing_start
        by_name={r['Name'].lstrip('/'):r for r in infos}
        if set(by_name)!=set(names):raise Blocked('batched owned measurement incomplete')
        targets=[];peaks={n:self.peak_cache.get(n,0) for n in removed};writable={}
        memory={n:{**row,'currentBytes':0,'running':False} for n,row in getattr(self,'memory_cache',{}).items() if n in removed}
        storage_bound=0
        for name in names:
            info=self.verify_owner(name,by_name[name]);host=info['HostConfig']
            if info['State'].get('OOMKilled'):raise Blocked('owned container OOM kill observed')
            if not host.get('ReadonlyRootfs') or host['MemorySwap']!=host['Memory']:
                raise Blocked('owned readonly/no-swap storage bound unproven')
            capacity=0
            for options in (host.get('Tmpfs') or {}).values():
                sizes=[x[5:] for x in options.split(',') if x.startswith('size=')]
                if len(sizes)!=1:raise Blocked('tmpfs capacity not pinned')
                value=sizes[0].lower();scale={'k':1024,'m':1024**2,'g':1024**3}
                capacity+=int(value[:-1])*scale[value[-1]] if value[-1] in scale else int(value)
            log=host['LogConfig']
            if log['Type']!='json-file' or log['Config'].get('max-size')!='1m' or log['Config'].get('max-file')!='2':
                raise Blocked('owned log storage cap unproven')
            writable[name]=capacity+2*1024**2+8*1024**2
            storage_bound+=writable[name]
            if info['State']['Running']:
                targets.append({'name':name,'pid':info['State']['Pid'],'id':info['Id']})
            elif self.resource_cleanup:peaks[name]=self.peak_cache.get(name,0)
            else:raise Blocked('workload stopped outside cleanup measurement')
        code="""import json,os,pathlib,sys
x=json.load(sys.stdin);s=os.statvfs('/');m=dict(r.split(':',1) for r in open('/proc/meminfo'));stats={}
for t in x:
 try:
  lines=pathlib.Path('/proc/'+str(t['pid'])+'/cgroup').read_text().splitlines();paths=[r.split(':',2)[2] for r in lines if r.startswith('0::')];assert len(paths)==1
  p=pathlib.PurePosixPath(paths[0]);assert '..' not in p.parts and (t['id'] in p.parts or p.name=='docker-'+t['id']+'.scope')
  root=pathlib.Path('/sys/fs/cgroup')/str(p).lstrip('/')
  stats[t['name']]={'currentBytes':int((root/'memory.current').read_text()),'peakBytes':int((root/'memory.peak').read_text()),'events':dict((k,int(v)) for k,v in (r.split() for r in (root/'memory.events').read_text().splitlines()))}
 except FileNotFoundError:stats[t['name']]=None
print(json.dumps({'dockerFree':s.f_bavail*s.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024,'stats':stats}))
"""
        self.resource_stage='cgroups'
        stage_start=time.monotonic()
        data=json.loads(docker(['exec','-i',self.probe_name,'python','-c',code],canonical(targets),timeout=3))
        timings['cgroupSeconds']=time.monotonic()-stage_start
        self.resource_stage='inspect-after'
        stage_start=time.monotonic()
        after=json.loads(docker(['inspect',*names],timeout=3)) if names else []
        timings['inspectAfterSeconds']=time.monotonic()-stage_start
        after={r['Name'].lstrip('/'):r for r in after}
        for target in targets:
            name=target['name'];info=self.verify_owner(name,after[name]);stats=data['stats'][name]
            if stats is None:
                if not self.resource_cleanup or info['State']['Running']:raise Blocked('owned cgroup disappeared')
                value=self.peak_cache.get(name,0)
                memory[name]={**getattr(self,'memory_cache',{}).get(name,{}),'currentBytes':0,'running':False}
            elif info['State']['Running'] and info['State']['Pid']!=target['pid']:
                raise Blocked('owned cgroup PID changed')
            else:
                value=stats['peakBytes']
                memory[name]={**stats,'running':info['State']['Running'],'limitBytes':info['HostConfig']['Memory'],
                              'oomKilled':info['State'].get('OOMKilled',False),'containerId':info['Id']}
                if (memory[name]['oomKilled'] or any(stats['events'].get(k,0)>0 for k in ('oom','oom_kill','oom_group_kill'))):
                    self.memory_failure=memory[name];raise Blocked('owned cgroup OOM observed')
            peaks[name]=value;self.peak_cache[name]=max(value,self.peak_cache.get(name,0))
        for name in names:
            if name not in memory and name in getattr(self,'memory_cache',{}):
                memory[name]={**self.memory_cache[name],'currentBytes':0,'running':False}
        self.memory_cache=memory
        fs=os.statvfs(self.root);host=fs.f_bavail*fs.f_frsize
        self.resource_stage='artifact-walk'
        stage_start=time.monotonic()
        usage=self.artifact_bytes()
        timings['artifactWalkSeconds']=time.monotonic()-stage_start
        timings['totalSeconds']=time.monotonic()-timing_start
        if getattr(self,'artifact_cap',None) is not None and usage>self.artifact_cap:
            raise Blocked('owned artifact growth exceeded locked calibration budget')
        self.metrics.append({'at':time.monotonic(),'phase':self.phase,'hostGrowth':usage,'dockerGrowth':sum(writable.values()),
                             'containerMemoryPeakBytes':peaks,'containerWritableBytes':writable,
                             'containerMemory':memory,
                             'samplerTimings':timings,
                             'dockerGrowthMeasurement':'upper bound from readonly roots, bounded tmpfs/logs and 8MiB metadata reserve per container; not SizeRw',
                             'ramAvailable':data['ramAvailable'],'hostFree':host,'dockerFree':data['dockerFree']})
        return {'hostFree':host,'dockerFree':data['dockerFree'],'ramAvailable':data['ramAvailable'],'dockerAvailable':True}

    def engine(self,component,kind,name,args):
        try:return super().engine(component,kind,name,args)
        except Exception:
            if not hasattr(self,'api_failures'):self.api_failures=[]
            self.api_failures.append({'component':component,'kind':kind,'name':name})
            raise
    def create(self,name,image,args):
        args=[*args,'--log-driver','json-file','--log-opt','max-size=1m','--log-opt','max-file=2']
        if name==self.anchor:
            args=[*args,'--read-only','--memory','64m','--memory-swap','64m','--tmpfs','/run:rw,size=1m']
        if name==self.names[1]:
            self.commands[name]=['python','-m','zap_assessment.w5_scanner_fixture']
            args=[str(P/'src')+':/package/src:ro' if v==str(P)+':/package:ro' else v for v in args]
            args=[*args,'--read-only','--memory-swap','128m','--ulimit','core=0','--tmpfs','/tmp:rw,size=16m,uid=1003,gid=1003,mode=0700']
        elif name==self.names[2]:
            args=['ZAP_MEMORY=512m' if v=='ZAP_MEMORY=768m' else v for v in args]
            home=self.root/'zap-home';temporary=self.root/'zap-tmp'
            for path in (home,temporary):path.mkdir(mode=0o777,exist_ok=True);path.chmod(0o777)
            if getattr(self,'resource_profile',{}).get('seedPinnedImageCache'):
                self.cache_seed=seed_image_cache(P.parent,home)
                save(self.root/'cache-seed.json',self.cache_seed)
            args=[*args,'--read-only','--memory-swap','1024m','--ulimit','core=0',
                  '-v',str(temporary)+':/tmp','-v',str(home)+':/home/zap']
        elif name==self.names[3]:
            temporary=self.root/'mcp-tmp';temporary.mkdir(mode=0o777,exist_ok=True);temporary.chmod(0o777)
            args=[*args,'--read-only','--memory-swap','512m','--ulimit','core=0',
                  '-v',str(temporary)+':/tmp']
        return super().create(name,image,args)

    def control(self,value):
        self.check_owner(self.names[1])
        raw=docker(['exec','-i','--user','1003:1003',self.names[1],'python','-c',CONTROL_CLIENT],canonical(value),timeout=10)
        response=json.loads(raw)
        if response.get('blocked'):raise Blocked('owned auth control rejected')
        self.audit_blob('control-tool-output',raw.encode())
        return response

    def audit_blob(self,sink,blob):
        if self.auditor.matches(blob):
            self.leak=True;raise SecretLeak('canary detected at '+sink)
        return {'sink':sink,'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'matches':0}

    def request(self,*args,**kwargs):
        value=super().request(*args,**kwargs)
        if hasattr(self,'auditor'):self.audit_receipts.append(self.audit_blob('MCP-and-engine-envelope',canonical(value)))
        return value


def create_db_reader(rt,plan,private=False):
    if hasattr(rt,'db_reader'):raise Blocked('database reader creation replay refused')
    name='zpa-'+plan['runId']+'-db-reader';rt.db_reader=name;rt.names.append(name)
    uid='1003' if private else '1000'
    java_source=P/'src/zap_assessment/probes/SessionDbReadback.java'
    if private:
        raw=java_source.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=plan['privateDbReaderSourceSha256']:raise Blocked('private JDBC source drift')
        java_source=rt.root/'private-db-reader-source.java';atomic_bytes(java_source,raw);java_source.chmod(0o444)
    rt.commands[name]=['sleep','900' if private else '300']
    args=['--network','container:'+rt.anchor if private else 'none','--read-only','--cap-drop','ALL',
          '--security-opt','no-new-privileges','--ulimit','core=0','--memory','256m','--pids-limit','64',
          '--user',uid+':'+uid,'--memory-swap','256m','--tmpfs','/tmp:rw,size=32m,uid='+uid+',gid='+uid,
          '-v',str(java_source)+':/source/SessionDbReadback.java:ro',
          '-v',str(rt.root/'zap-workspace')+':/session:ro']
    if private:
        args += ['-v',str(P/'src')+':/package/src:ro','-v',str(rt.root/'fixture/w5-binding.json')+':/binding/w5-binding.json:ro',
                 '-e','PYTHONPATH=/package/src','-e','PYTHONDONTWRITEBYTECODE=1']
    rt.create(name,rt.plan.data['runtime']['zap'],args)
    docker(['exec',name,'javac','-cp','/zap/lib/hsqldb-2.7.4.jar','-d','/tmp','/source/SessionDbReadback.java'],timeout=30)
    if not private:return None
    info=rt.check_owner(name);anchor=rt.check_owner(rt.anchor);host=info['HostConfig']
    if (info['Config'].get('User')!='1003:1003' or host.get('NetworkMode')!='container:'+anchor['Id']
            or host.get('ReadonlyRootfs') is not True or host.get('Memory')!=256*1024**2
            or host.get('MemorySwap')!=host.get('Memory')):raise Blocked('private database reader ownership/mount invalid')
    probe="""import os,sys,json,hashlib
from pathlib import Path
from zap_assessment.private_source import mount_type
print(json.dumps({'pythonVersion':list(sys.version_info[:3]),'uid':os.geteuid(),'gid':os.getegid(),
'tmpFilesystem':mount_type(Path('/tmp')),'hsqldbJarSha256':hashlib.sha256(Path('/zap/lib/hsqldb-2.7.4.jar').read_bytes()).hexdigest(),
'readerClassSha256':hashlib.sha256(Path('/tmp/SessionDbReadback.class').read_bytes()).hexdigest(),
'readerSourceSha256':hashlib.sha256(Path('/source/SessionDbReadback.java').read_bytes()).hexdigest()}))
"""
    observed=json.loads(docker(['exec',name,'python3','-c',probe],timeout=10))
    if (observed['pythonVersion'][:2]<[3,10] or observed['uid']!=1003 or observed['gid']!=1003
            or observed['tmpFilesystem']!='tmpfs'
            or observed['readerSourceSha256']!=hashlib.sha256((P/'src/zap_assessment/probes/SessionDbReadback.java').read_bytes()).hexdigest()):
        raise Blocked('private database reader environment unproven')
    result={'contract':PRIVATE_DB_CONTRACT,'containerId':info['Id'],'imageId':info['Image'],
            'networkAnchorId':anchor['Id'],'networkMode':host['NetworkMode'],'readerUser':'1003:1003',
            'readonlyRoot':True,'memoryBytes':host['Memory'],'swapBytes':host['MemorySwap'],
            'tmpfsOptions':sorted(host['Tmpfs']['/tmp'].split(',')),'observed':observed,
            'sourceValuesIncluded':False,'rawCellsExportedToController':False}
    save(rt.root/'private-db-reader.json',result);return result


def private_db_call(rt,plan,case,mode='control',probe='valid'):
    rt.check_owner(rt.db_reader);rt.check_owner(rt.names[1])
    intent={'action':'private-db-call','caseId':case,'mode':mode,'probe':probe,'reader':rt.db_reader}
    if mode=='session':
        writer=rt.check_owner(rt.names[2])
        if writer['State']['Running']:raise Blocked('private saved-session writer not stopped')
        intent.update(writerContainerId=writer['Id'],writerNotRunning=True)
    rt.journal.append('intent',intent)
    uid='1000:1000' if probe=='wrong-uid' else '1003:1003'
    args=['exec','--user',uid,rt.db_reader,'python3','-m','zap_assessment.private_db_bridge',
          '--actor',plan['actorRef'],'--case',case,'--mode',mode,'--probe',probe]
    raw=docker(args,timeout=30)
    rt.audit_blob('private-db-metadata-output',raw.encode())
    value=json.loads(raw)
    if probe!='valid':
        reason='peer_uid' if probe=='wrong-uid' else 'no_replay' if probe=='replay' else 'binding'
        expected={'probe':probe,'status':'denied','reasonCode':reason,
            'peer':{'uid':1000,'gid':1000} if probe=='wrong-uid' else {'uid':1003,'gid':1003},
            'sourceRead':False,'privateValueDelivered':False,'sourceValuesIncluded':False,
            'requestedActorMatches':probe!='wrong-actor','requestedPlanMatches':probe!='wrong-plan',
            'requestedRunMatches':True,'requestedCaseMatches':True}
        if value!=expected:raise Blocked('private database negative control failed')
        result={'caseId':case,**value};save(rt.root/('private-db-probe-'+probe+'.json'),result)
        rt.journal.append('ack',{**intent,'metadataSha256':digest(result)});return result
    validate_public_receipt(value,run_id=plan['runId'],plan_hash=digest(plan),actor=plan['actorRef'],case_id=case,mode=mode)
    if value['leakDetected']:
        rt.leak=True;raise SecretLeak('canary detected in private saved-session audit')
    save(rt.root/('private-db-'+(case if mode=='control' else 'saved-session')+'.json'),value)
    rt.journal.append('ack',{**intent,'metadataSha256':digest(value),'nonce':value['nonce']})
    return value


def wait_terminal(scanner,kind,op,timeout=120):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        if scanner.status(kind,op):return True
        time.sleep(.2)
    return False


def inspect_history(rt):
    total=int(rt.engine('core','view','numberOfMessages',{})['numberOfMessages'])
    receipts=[];count=0
    for start in range(0,total,50):
        value=rt.engine('core','view','messages',{'start':start,'count':min(50,total-start)})
        rows=value.get('messages')
        if not isinstance(rows,list):raise Blocked('history reader contract')
        receipts.append(rt.audit_blob('zap-history-decoded-messages',canonical(rows)));count+=len(rows)
    if count!=total:raise Blocked('history count changed during snapshot')
    return {'messageCount':total,'readbackCount':count,'chunks':receipts}


def audit_host(rt):
    receipts=[]
    for path in sorted(rt.root.rglob('*')):
        if path.is_symlink():raise Blocked('unreadable audit symlink')
        if not path.is_file():continue
        previous=getattr(rt,'host_audited',{}).get(str(path))
        if previous:
            h=hashlib.sha256()
            with path.open('rb') as stream:
                while chunk:=stream.read(65536):h.update(chunk)
            if h.hexdigest()!=previous['sha256']:raise Blocked('host file changed after decoded container snapshot')
            receipts.append({'sink':'owned-artifact:'+str(path.relative_to(rt.root)),
                             'bytes':path.stat().st_size,'sha256':h.hexdigest(),'matches':0,
                             'decoderProof':'same bytes as final owned-container readback'})
            continue
        if path.stat().st_size>8*1024*1024:raise Blocked('audit artifact exceeds decoder bound')
        data=path.read_bytes()
        # Binary files still have a raw-canary audit, explicitly not DB decoding.
        receipts.append(rt.audit_blob('owned-artifact:'+str(path.relative_to(rt.root)),data))
    return receipts


def recover(work,external):
    work=Path(work).absolute();p=json.loads((work/'w5-plan.json').read_bytes())
    if digest(p)!=external:raise Blocked('recovery external lock mismatch')
    root=work/'runtime';original=Journal(root/'journal.jsonl',p['runId'],external)
    before=hashlib.sha256(original.path.read_bytes()).hexdigest()
    folder=work/('recovery-'+uuid.uuid4().hex);folder.mkdir(mode=0o700)
    current=Journal(folder/'journal.jsonl',p['runId'],external)
    current.append('recovery-source',{'originalJournalSha256':before,'mode':'stop-only-no-replay'})
    class RecoveryJournal:
        @property
        def events(self):return original.events+current.events
        def append(self,*args,**kwargs):return current.append(*args,**kwargs)
    rt=Runtime(p['runId'],root,RecoveryJournal());rt.plan=make_plan(*inputs(True));rt.stop_timeout=120
    for e in original.events:
        name=e['data'].get('resource')
        if e['kind']=='intent' and e['data'].get('action')=='container-create' and name not in rt.names:rt.names.append(name)
    rt.cleanup()
    after=hashlib.sha256(original.path.read_bytes()).hexdigest()
    if before!=after:raise Blocked('recovery altered original journal')
    result={'stopOnly':True,'noReplay':True,'originalJournalUnchanged':True,'originalJournalSha256':before}
    save(folder/'result.json',result);return result


def verify_runtime_receipts(r,traffic,profile=None,private_db=False):
    """Replay recorded safety observations; checksums alone cannot validate them.

    This validates development receipts, not the missing operational sink proof.
    No Docker calls, credentials, database writer or live target are involved.
    """
    if (r.get('canaryLeakDetected') is not False or r.get('securityApproval') is not False
            or r.get('securityVerdict')!='inconclusive' or r.get('cleanupStatus')!='clean'
            or r.get('executionStatus')!='completed' or r.get('evidenceStatus')!='complete-development-only'
            or any(r.get(k) is not None for k in ('error','safetyFailure','resourceFailure'))):
        raise Blocked('scanner development safety receipt contradicted')
    samples=r.get('resourceSamples')
    if not isinstance(samples,list) or len(samples)<2:raise Blocked('resource timeline missing')
    # Use the actual calibration gate and its unchanged synthetic growth budget.
    tick=[0];current=[None]
    gate=calmod.CalibrationSupervisor(SimpleNamespace(resource_sample=lambda:current[0]),None).resource
    if profile is not None:gate=W5ResourceGate(gate.contract,lambda:current[0],profile)
    gate.clock=lambda:tick[0]
    for i,sample in enumerate(samples):
        at=sample.get('at')
        if (type(at) not in (int,float) or not math.isfinite(at)
                or (i and at<=samples[i-1]['at'])):raise Blocked('resource timeline order invalid')
        tick[0]=at;current[0]=sample
        if i==0:gate.preflight()
        else:gate.check(force=True)
    if profile is not None:
        if r.get('resourceProfile')!=profile or r.get('memoryFailure') is not None:raise Blocked('W5 resource profile receipt contradicted')
        verify_measurements(profile,r.get('resourceMetrics'),samples)
    gap=max(b['at']-a['at'] for a,b in zip(samples,samples[1:]))
    resources=r.get('policy',{}).get('resources',{})
    helper=resources.get('measurementHelperShutdownSeconds')
    if (r.get('maxObservedResourceGapSeconds')!=gap or resources.get('maxObservedGapSeconds')!=gap
            or resources.get('samples')!=samples or resources.get('monitoredThrough')!='all workloads stopped and removed'
            or type(helper) not in (int,float) or not math.isfinite(helper) or not 0<=helper<=5):
        raise Blocked('resource cleanup receipt contradicted')
    policy=r['policy'];snapshots=policy.get('snapshots',[])
    if not snapshots:raise Blocked('policy snapshots missing')
    replay=calmod.EffectivePolicy(snapshots[0]['inventory'],active_execution_allowed=True,require_phase=True)
    for snapshot in snapshots:replay.snapshot(snapshot['phase'],snapshot['inventory'])
    replay.traffic(traffic['events'],complete=traffic['complete']);expected=replay.finalize()
    if expected['expectedActiveRules']!=['40012'] or any(policy.get(k)!=v for k,v in expected.items()):
        raise Blocked('policy receipt disagrees with independent traffic')
    counts={}
    for event in traffic['events']:
        if event['producer']=='active':counts[event['ruleId']]=counts.get(event['ruleId'],0)+1
    proof=r.get('activePolicyProof') or {}
    if (set(counts)!={'40012'} or proof.get('pass') is not True
            or proof.get('expectedRuleIds')!=['40012'] or proof.get('nativeRequestCounts')!=counts
            or proof.get('scanProgressRequestCounts')!=counts or proof.get('vulnerabilityDetectionVerified') is not False):
        raise Blocked('active request receipt disagrees with independent traffic')
    database=r.get('databaseReadback') or {}
    control=database.get('positiveControl') or {};saved=database.get('savedSession') or {}
    for result in (control,saved):
        if (result.get('decoder')!='HSQL JDBC all PUBLIC table typed cells'
                or any(type(result.get(k)) is not int or result[k]<=0 for k in ('rows','decodedCells','decodedBytes'))
                or not isinstance(result.get('tables'),list) or not result['tables']
                or len(result['tables'])!=len(set(result['tables']))):
            raise Blocked('saved-session decoder receipt incomplete')
    expected_matches,expected_cells,expected_table=(10,15,'PRIVATE_SOURCE_CONTROL') if private_db else (2,2,'CANARY_CONTROL')
    if (control.get('seededControl') is not True or control.get('canaryMatches')!=expected_matches
            or control.get('decodedCells')!=expected_cells or control.get('tables')!=[expected_table]
            or saved.get('seededControl') is not False or saved.get('canaryMatches')!=0
            or 'HISTORY' not in saved['tables']):raise Blocked('saved-session canary control contradicted')


def verify_private_db_receipts(work,plan,result,journal):
    if result.get('privateDbContract')!=PRIVATE_DB_CONTRACT:raise Blocked('private DB contract receipt missing')
    reader=result.get('privateDbReader') or {};observed=reader.get('observed') or {}
    created={e['data'].get('resource'):e['data'].get('containerId') for e in journal.events
             if e['kind']=='ack' and e['data'].get('action')=='container-create'}
    name='zpa-'+plan['runId']+'-db-reader';anchor=created.get('zpa-'+plan['runId']+'-net')
    if (reader.get('contract')!=PRIVATE_DB_CONTRACT or not anchor
            or reader.get('containerId')!=created.get(name)
            or reader.get('imageId')!=plan['runtimePins']['zap'].split('@')[-1]
            or reader.get('networkAnchorId')!=anchor or reader.get('networkMode')!='container:'+anchor
            or reader.get('readerUser')!='1003:1003' or reader.get('readonlyRoot') is not True
            or reader.get('memoryBytes')!=256*1024**2 or reader.get('swapBytes')!=reader['memoryBytes']
            or not {'rw','size=32m','uid=1003','gid=1003'}<=set(reader.get('tmpfsOptions',[]))
            or reader.get('sourceValuesIncluded') is not False or reader.get('rawCellsExportedToController') is not False):
        raise Blocked('private DB reader ownership/configuration contradicted')
    version=observed.get('pythonVersion')
    if (not isinstance(version,list) or len(version)!=3 or any(type(v) is not int for v in version)
            or version[:2]<[3,10] or observed.get('uid')!=1003 or observed.get('gid')!=1003
            or observed.get('tmpFilesystem')!='tmpfs' or observed.get('readerSourceSha256')!=plan['privateDbReaderSourceSha256']):
        raise Blocked('private DB reader observation invalid')
    for field in ('readerClassSha256','hsqldbJarSha256'):
        value=observed.get(field)
        if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
            raise Blocked('private DB code/library pin missing')
    if (json.loads((work/'runtime/private-db-reader.json').read_bytes())!=reader
            or hashlib.sha256((work/'runtime/private-db-reader-source.java').read_bytes()).hexdigest()!=plan['privateDbReaderSourceSha256']
            or json.loads((work/'runtime/fixture/w5-binding.json').read_bytes())!=
              {'runId':plan['runId'],'planHash':digest(plan),'sourceMode':'private-file','actorRef':plan['actorRef'],'privateDbControls':True}):
        raise Blocked('private DB captured source/binding drift')
    cases=[c for c in plan['cases'] if c!='crash'];controls=result.get('privateDbAudits')
    if not isinstance(controls,list) or [r.get('caseId') for r in controls]!=cases:
        raise Blocked('private DB lifecycle controls incomplete')
    session=result.get('privateDbSessionAudit');all_receipts=[*controls,session]
    source=result['privateSourceReceipts'][1]['sourceStatus']['sourceMetadata']
    expected_source=next(r for r in source['files'] if r['actorRef']==plan['actorRef'])
    log=read_rows(work/'runtime/fixture/private-db-audit.jsonl')
    audits=[e for e in log if e.get('event')=='private_db_audited']
    resolutions=[e for e in log if e.get('event')=='private_db_source_resolved']
    denials=[e for e in log if e.get('event')=='private_db_channel_denied']
    if len(audits)!=len(all_receipts) or len(resolutions)!=len(all_receipts) or len(denials)!=4:
        raise Blocked('private DB holder journal incomplete')
    nonces=set();expected_calls={}
    for i,(value,event,resolved) in enumerate(zip(all_receipts,audits,resolutions)):
        mode='control' if i<len(cases) else 'session';case=cases[i] if i<len(cases) else 'cleanup'
        validate_public_receipt(value,run_id=plan['runId'],plan_hash=digest(plan),actor=plan['actorRef'],case_id=case,mode=mode)
        if value['status']!='pass' or value['nonce'] in nonces or value['sourceMetadata']!=source:
            raise Blocked('private DB source identity, nonce or outcome contradicted')
        nonces.add(value['nonce'])
        if {k:v for k,v in event.items() if k!='event'}!=value:
            raise Blocked('private DB holder receipt differs from reader output')
        at=resolved.get('atMonotonic')
        if (resolved.get('runId')!=plan['runId'] or resolved.get('planHash')!=digest(plan)
                or resolved.get('source')!=expected_source or resolved.get('caseId')!=case or resolved.get('mode')!=mode
                or resolved.get('sourceValuesIncluded') is not False or resolved.get('contentHashesIncluded') is not False
                or type(at) not in (int,float) or not math.isfinite(at)
                or not 0<=value['startedAtMonotonic']-at<=1):raise Blocked('private DB audit source resolution binding invalid')
        file=work/('runtime/private-db-'+(case if mode=='control' else 'saved-session')+'.json')
        if json.loads(file.read_bytes())!=value:raise Blocked('private DB metadata capture mismatch')
        expected_calls[(mode,case,'valid')]=value
    negatives=result.get('privateDbChannelControls')
    probes=('wrong-uid','wrong-actor','wrong-plan','replay')
    if not isinstance(negatives,list) or [r.get('probe') for r in negatives]!=list(probes):
        raise Blocked('private DB negative channel controls incomplete')
    for value,event,probe in zip(negatives,denials,probes):
        expected={'caseId':'success' if probe=='replay' else 'uninitialized','probe':probe,'status':'denied',
            'reasonCode':'peer_uid' if probe=='wrong-uid' else 'no_replay' if probe=='replay' else 'binding',
            'peer':{'uid':1000,'gid':1000} if probe=='wrong-uid' else {'uid':1003,'gid':1003},
            'sourceRead':False,'privateValueDelivered':False,'sourceValuesIncluded':False,
            'requestedActorMatches':probe!='wrong-actor','requestedPlanMatches':probe!='wrong-plan',
            'requestedRunMatches':True,'requestedCaseMatches':True}
        if (value!=expected or {k:v for k,v in event.items() if k not in ('event','atMonotonic')}!=
                {k:v for k,v in value.items() if k!='probe'}
                or json.loads((work/('runtime/private-db-probe-'+probe+'.json')).read_bytes())!=value):
            raise Blocked('private DB denial proof contradicted')
        expected_calls[('control',value['caseId'],probe)]=value
    intents={};acks={}
    for index,event in enumerate(journal.events):
        data=event['data']
        if data.get('action')!='private-db-call':continue
        key=(data.get('mode'),data.get('caseId'),data.get('probe'));store=intents if event['kind']=='intent' else acks if event['kind']=='ack' else None
        if store is None or key in store:raise Blocked('private DB duplicate/unknown call journal event')
        store[key]=(index,data)
    if set(intents)!=set(expected_calls) or set(acks)!=set(expected_calls):raise Blocked('private DB call ACK inventory incomplete')
    for key,value in expected_calls.items():
        before,intent=intents[key];after,ack=acks[key]
        expected={**intent,'metadataSha256':digest(value)}
        if key[-1]=='valid':expected['nonce']=value['nonce']
        if before>=after or intent.get('reader')!=name or ack!=expected:
            raise Blocked('private DB ACK/readback binding mismatch')
    session_key=('session','cleanup','valid');before,intent=intents[session_key];after,_=acks[session_key]
    stopped=[i for i,e in enumerate(journal.events) if e['kind']=='ack' and e['data'].get('action')=='w5-zap-graceful-shutdown']
    killed=[i for i,e in enumerate(journal.events) if e['kind']=='intent' and e['data'].get('action')=='w5-owned-guard-sigkill']
    if (len(stopped)!=1 or len(killed)!=1 or not stopped[0]<before<after<killed[0]
            or intent.get('writerNotRunning') is not True
            or intent.get('writerContainerId')!=created.get('zpa-'+plan['runId']+'-zap')):
        raise Blocked('private DB writer-stop/audit/holder-stop ordering contradicted')
    db=result['databaseReadback']
    if db.get('privateChannel') is not True or db.get('savedSession')!=session['audit'] or db.get('positiveControl')!=controls[-1]['audit']:
        raise Blocked('private DB database summary differs from holder audit')
    return {'contract':PRIVATE_DB_CONTRACT,'controlLifecycleCases':len(controls),
        'sourceEncodingTextBinaryDetections':len(controls)*10,'savedSessionAuditedInHolder':True,
        'channelNegativeControls':4,'rawCellsExportedToController':False,'operationalG3':'blocked'}


def verify(work,external):
    work=Path(work).absolute();p=json.loads((work/'w5-plan.json').read_bytes())
    mode=source_mode(p)
    private_db=private_db_mode(p)
    if digest(p)!=external:raise Blocked('readback external plan mismatch')
    index=json.loads((work/'readback-index.json').read_bytes())
    required={'w5-plan.json','attempt.json','gate-results.json','runtime/report.json',
              'runtime/fixture/auth-journal.jsonl','runtime/fixture/auth-target.jsonl',
              'runtime/zap-workspace/sender-events.jsonl','runtime/fixture/boundary.jsonl',
              'runtime/fixture/arrivals.jsonl','runtime/journal.jsonl',
              'runtime/calibration-initial-inventory.json','runtime/calibration-policy.json',
              'runtime/zap-workspace/w5-saved-session.session',
              'runtime/zap-workspace/w5-saved-session.session.data',
              'runtime/zap-workspace/w5-saved-session.session.properties',
              'runtime/zap-workspace/w5-saved-session.session.script'}
    required.update('runtime/case-'+case+'.json' for case in p['cases'] if case!='crash')
    private_source=p.get('secretSource')=='owned-guard-memory-generated; host comparison hashes only'
    private_source=private_source or mode=='private-file'
    if private_source:required.add('runtime/fixture/auth-source.jsonl')
    if mode=='private-file':
        required.add('runtime/fixture/auth-reference.jsonl')
        required.update('runtime/source-'+stage+'.json' for stage in
                        ['before-source','after-source']+['case-'+c for c in p['cases'] if c!='crash'])
    if private_db:
        required.update({'runtime/private-db-reader.json','runtime/private-db-reader-source.java',
                         'runtime/private-db-saved-session.json','runtime/fixture/private-db-audit.jsonl'})
        required.update('runtime/private-db-'+c+'.json' for c in p['cases'] if c!='crash')
        required.update('runtime/private-db-probe-'+c+'.json' for c in ('wrong-uid','wrong-actor','wrong-plan','replay'))
    if not required<=set(index):raise Blocked('scanner required artifact index incomplete')
    for name,checksum in index.items():
        if artifact_digest(work,name)!=checksum:raise Blocked('scanner artifact checksum mismatch')
    r=json.loads((work/'gate-results.json').read_bytes())
    if p.get('monitorContract') is not None:
        if p['monitorContract']!=MONITOR_CONTRACT:raise Blocked('unknown W5 monitor contract')
        verify_policy_monitor(r)
    if private_source:
        validate_source_boundary(r.get('sourceBoundary'),source_kind=(
            'owned-guard-private-file-reference' if mode=='private-file' else 'owned-guard-memory-generated'))
        binding=read_rows(work/'runtime/fixture/auth-source.jsonl')
        if (len(binding)!=1 or binding[0].get('runId')!=p['runId'] or binding[0].get('planHash')!=external
                or binding[0].get('event')!='source_bound' or binding[0].get('sourceValuesIncluded') is not False
                or binding[0].get('fingerprintsSha256')!=digest(r['sourceBoundary']['fingerprints'])
                or binding[0].get('controls')!=r['sourceBoundary']['controls']):raise Blocked('private source binding contradicted')
        if binding[0].get('sourceKind')!=r['sourceBoundary']['sourceKind']:
            raise Blocked('private source kind contradicted')
    if (r['planHash']!=external or r['status']!='development_pass_operational_blocked'
            or not r['cleanupConfirmed'] or not r['noOwnedResources']
            or r['operationalG3']!='blocked' or r['productG4']!='blocked' or r['gateDecision']!='block'
            or sorted(c['caseId'] for c in r['cases'])!=sorted(p['cases'])
            or any(c['status']!='pass' for c in r['cases'])):raise Blocked('scanner development result contradicted')
    events=read_rows(work/'runtime/fixture/auth-journal.jsonl')
    target=read_rows(work/'runtime/fixture/auth-target.jsonl')
    traffic=correlate(read_rows(work/'runtime/zap-workspace/sender-events.jsonl'),
                      read_rows(work/'runtime/fixture/boundary.jsonl'),
                      read_rows(work/'runtime/fixture/arrivals.jsonl'),terminal=True)
    if not traffic['complete']:raise Blocked('terminal wire evidence incomplete')
    verify_runtime_receipts(r,traffic,p.get('resourceProfile'),private_db)
    journal=Journal(work/'runtime/journal.jsonl',p['runId'],external)  # Read/validate only.
    source_proof=None
    if mode=='private-file':
        source_proof=verify_source_receipts(r,p,read_rows(work/'runtime/fixture/auth-reference.jsonl'),target,journal)
        for row in r['privateSourceReceipts']:
            if json.loads((work/('runtime/source-'+row['stage']+'.json')).read_bytes())!=row:
                raise Blocked('private source capture and summary disagree')
    db_proof=verify_private_db_receipts(work,p,r,journal) if private_db else None
    if p.get('resourceProfile'):
        created={e['data']['resource']:e['data']['containerId'] for e in journal.events
                 if e['kind']=='ack' and e['data'].get('action')=='container-create'}
        for metric in r['resourceMetrics']:
            for name,reading in metric.get('containerMemory',{}).items():
                if created.get(name)!=reading['containerId']:raise Blocked('W5 memory receipt not bound to creation ACK')
    initial=json.loads((work/'runtime/calibration-initial-inventory.json').read_bytes())
    if (calmod.EffectivePolicy(initial).expected!=r['policy']['snapshots'][0]['inventory']
            or json.loads((work/'runtime/calibration-policy.json').read_bytes())!=r['policy']):
        raise Blocked('policy observation and summary disagree')
    for case in r['cases']:
        if case['caseId']!='crash' and json.loads((work/('runtime/case-'+case['caseId']+'.json')).read_bytes())!=case:
            raise Blocked('auth case observation and summary disagree')
    native_ids={e['requestId'] for e in traffic['events']}
    def protected_arrival(a):
        # Legacy target logs also called refresh/logout authentication controls
        # 'protected'. Only native-correlated application arrivals establish
        # forwarding; those controls have no scanner request ID.
        if a.get('event')!='protected':return False
        if a.get('targetLogVersion')=='1.1' and a.get('requestId') not in native_ids:
            raise Blocked('application arrival missing native correlation')
        return a.get('requestId') in native_ids
    for case in p['cases']:
        if case=='crash':continue
        observations=[a for a in target if a.get('caseId')==case]
        rows=[e for e in events if e.get('caseId')==case]
        if case=='login-failure':
            if not any(a.get('event')=='login' and a.get('accepted') is False for a in observations):raise Blocked('login negative proof missing')
        elif not any(protected_arrival(a) and a.get('valid') is True for a in observations):
            raise Blocked('protected positive target proof missing')
        for event in rows:
            if event['event']=='protected_start':
                if not any(e['event']=='identity_proof' and e['authEpoch']==event['authEpoch']
                           and 0<=event['atMonotonic']-e['atMonotonic']<=5 for e in rows):
                    raise Blocked('protected identity epoch/freshness missing')
    for case in r['cases']:
        if case.get('expectedAuthLoss') and (case.get('afterLatchProtectedForwards')!=0
                or not 0<=case.get('stopDispatchUpperBoundSeconds',float('inf'))<=10):
            raise Blocked('auth stop/latch development budget contradicted')
    for e in events:
        if e['runId']!=p['runId'] or e['planHash']!=external or e['actorRef']!=p['actorRef']:
            raise Blocked('auth event binding mismatch')
        if e['event']=='auth_lost' and any(a.get('caseId')==e['caseId'] and protected_arrival(a)
                                          and a['atMonotonic']>e['atMonotonic'] for a in target):
            raise Blocked('independent protected arrival after latch')
    if any(a.get('valid') is True and a.get('subjectRef')!=p['actorRef'] for a in target):raise Blocked('actor crossed in actual target')
    if not r.get('databaseReadback') or r['databaseReadback']['savedSession']['decodedCells']<=0:
        raise Blocked('saved-session decoder proof missing')
    result={'readbackStatus':'pass','cases':len(r['cases']),'operationalG3':'blocked','productG4':'blocked','securityApproval':False}
    if source_proof:result['privateSourceProof']=source_proof
    if db_proof:result['privateDbProof']=db_proof
    return result


def run(work,external):
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    work=Path(work).absolute();plan=json.loads((work/'w5-plan.json').read_bytes())
    mode=source_mode(plan)
    private_db=private_db_mode(plan)
    if digest(plan)!=external or plan['sourcePins']!=source_pin():raise Blocked('locked source/plan drift')
    save(work/'attempt.json',{'at':datetime.now(timezone.utc).isoformat(),'planHash':external})
    run=plan['runId'];root=work/'runtime';root.mkdir(mode=0o700)
    j=Journal(root/'journal.jsonl',run,external);rt=Runtime(run,root,j);rt.plan=make_plan(*inputs(True));rt.stop_timeout=120
    rt.private_source_mode=mode=='private-file'
    # Before source binding there are no private canaries. Only the public JDBC
    # fixture control exists on the host. The allowed guard creates the source.
    rt.auditor=CanaryAuditor([PUBLIC_DB_CONTROL]);source_boundary=None
    rt.audit_receipts=[];rt.leak=False;supervisor=W5Supervisor(rt,j)
    if plan.get('resourceProfile'):
        validate_profile(plan['resourceProfile'])
        if plan['resourceProfile']!=bounded_profile(P.parent):raise Blocked('locked W5 resource baseline drift')
        rt.artifact_cap=plan['resourceProfile']['artifactCapBytes']
        rt.resource_profile=plan['resourceProfile']
        supervisor.resource=W5ResourceGate(supervisor.contract,rt.resource_sample,plan['resourceProfile'])
    rows=[];status='blocked';error=None;scanner=None;closed=False;history=[];sink_audits=[];database=None;active_proof=None;source_receipts=[]
    db_controls=[];db_negatives=[];db_reader=None;db_session=None
    try:
        supervisor.preflight();rt.provision()
        binding={'runId':run,'planHash':external}
        if mode=='private-file':binding['sourceMode']='private-file'
        if private_db:binding.update(actorRef=plan['actorRef'],privateDbControls=True)
        save(root/'fixture/w5-binding.json',binding);os.chmod(root/'fixture/w5-binding.json',0o644)
        rt.wait_health()
        # Choose the persistent session before policy/observer installation. A
        # late saveSession can restart add-on state and invalidate that policy.
        j.append('intent',{'action':'w5-session-save','path':'/zap/wrk/w5-saved-session'})
        rt.engine('core','action','saveSession',{'name':'/zap/wrk/w5-saved-session','overwrite':'false'})
        j.append('ack',{'action':'w5-session-save'})
        scanner=W4Scanner(MCP(rt.request),rt.engine,rt.request);scanner.initialize();scanner.health()
        rt.configure_rate(2);supervisor.start()
        readiness=rt.control({'op':'readiness'})
        if readiness!={'credentialDelivered':False,'sessionCreated':False}:raise Blocked('precredential snapshot taken too late')
        if private_db:db_reader=create_db_reader(rt,plan,True)
        if mode=='private-file':source_receipts.append(capture_source(rt,'before-source',plan))
        sink_audits=[{'stage':'before-credential-delivery',**container_sinks(rt,n,precredential=True)}
                     for n in rt.names[:4] if n!=rt.anchor]
        source_boundary=rt.control({'op':'auditor-bind'})
        validate_source_boundary(source_boundary,source_kind=(
            'owned-guard-private-file-reference' if mode=='private-file' else 'owned-guard-memory-generated'))
        rt.auditor=OpaqueCanaryAuditor(source_boundary['fingerprints'])
        if mode=='private-file':source_receipts.append(capture_source(rt,'after-source',plan))
        if private_db:
            for probe in ('wrong-uid','wrong-actor','wrong-plan'):
                db_negatives.append(private_db_call(rt,plan,'uninitialized',probe=probe))
        url='http://127.0.0.1:18080/api/echo?q=baseline'
        for case in CASES:
            if case=='crash':break
            rt.set_phase('crawl');before=len(read_rows(root/'fixture/auth-target.jsonl'))
            response=rt.control({'op':'boot','actor':plan['actorRef'],'caseId':case,
                                 'ttl':3 if case=='expiry' else 600,'badPassword':case=='login-failure'})
            start_epoch=response['session']['authEpoch'];operations=[];began=time.monotonic()
            if case!='login-failure':
                scanner.seed(url)
                if case in ('crawl','expiry','revoke','role-change','cancel','exception','restart','cleanup','logout','refresh-failure'):
                    op=scanner.start('crawl',url);operations.append(('crawl',op))
                if case=='active':
                    rt.set_phase('active');op=scanner.start('active',url);operations.append(('active',op))
                if case.startswith('refresh-'):
                    response=rt.control({'op':'refresh','reject':case=='refresh-failure'})
                    if case=='refresh-success':
                        if response['session']['authEpoch']==start_epoch:raise Blocked('refresh epoch not advanced')
                        scanner.seed(url)
                if case in ('revoke','role-change','exception','cancel','restart','cleanup','logout'):
                    rt.control({'op':case})
            loss_expected=case not in ('success','crawl','active','refresh-success')
            if loss_expected:
                deadline=time.monotonic()+8
                while time.monotonic()<deadline:
                    response=rt.control({'op':'state'})
                    if response['session']['state']=='lost':break
                    time.sleep(.1)
                else:raise Blocked('auth loss not detected within budget')
                stop_at=time.monotonic()
                for kind,op in operations:scanner.stop(kind,op)
                losses=[r for r in read_rows(root/'fixture/auth-journal.jsonl') if r.get('caseId')==case and r.get('event')=='auth_lost']
                after_dispatch=rt.control({'op':'state'})
                # The macOS host and Linux VM have different monotonic origins.
                # An observation after the stop call bounds dispatch in the
                # guard's own clock without pretending these clocks are equal.
                dispatch_bound=after_dispatch['clockMonotonic']-losses[-1]['atMonotonic'] if losses else float('inf')
                if dispatch_bound>10:raise Blocked('stop dispatch budget exceeded')
                if not all(wait_terminal(scanner,k,o) for k,o in operations):raise Blocked('operation stop unconfirmed')
                arrivals=len(read_rows(root/'fixture/auth-target.jsonl'))
                scanner.seed(url);scanner.seed(url)
                protected=[r for r in read_rows(root/'fixture/auth-target.jsonl')[arrivals:] if r.get('event')=='protected']
                if protected:raise Blocked('protected request reached target after latch')
            else:
                if not all(wait_terminal(scanner,k,o) for k,o in operations):raise Blocked('operation terminal unconfirmed')
            save(root/f'fixture/auth-stop-ack-{case}.json',{'caseId':case,'terminal':True})
            os.chmod(root/f'fixture/auth-stop-ack-{case}.json',0o644)
            time.sleep(.1)
            snapshot=rt.control({'op':'state'})
            events=read_rows(root/'fixture/auth-target.jsonl')[before:]
            if case=='expiry' and not any(e.get('valid') is False and e.get('expiresAt') is not None and e['atMonotonic']>=e['expiresAt'] for e in events):raise Blocked('server TTL expiry not observed')
            if case!='login-failure' and not any(e.get('event')=='protected' and e.get('valid') is True for e in events):raise Blocked('protected positive missing')
            rt.set_phase('settle')
            deadline=time.monotonic()+30
            while not scanner.passive():
                if time.monotonic()>deadline:raise Blocked('passive did not settle')
                time.sleep(.2)
            history.append({'caseId':case,**inspect_history(rt)})
            if mode=='private-file':source_receipts.append(capture_source(rt,'case-'+case,plan))
            if private_db:
                db_controls.append(private_db_call(rt,plan,case))
                if case=='success':db_negatives.append(private_db_call(rt,plan,case,probe='replay'))
            rows.append({'caseId':case,'expectedAuthLoss':loss_expected,'observed':snapshot,
                         'ownedOperations':[{'kind':k,'operationId':o} for k,o in operations],
                         'serverEvents':len(events),'afterLatchProtectedForwards':0 if loss_expected else None,
                         'stopDispatchUpperBoundSeconds':dispatch_bound if loss_expected else None,
                         'elapsedSeconds':time.monotonic()-began,'status':'pass'})
            save(root/f'case-{case}.json',rows[-1])
        # Actual report tool/chunks, then persistent HSQL session creation.
        rt.set_phase('report');report_path=scanner.report('http://127.0.0.1:18080')
        from zap_assessment.evidence import read_report
        report=read_report(scanner.chunk,report_path,8*1024*1024);rt.audit_blob('report-readback',report)
        atomic_bytes(root/'report.json',report)
        history.append({'caseId':'session-save',**inspect_history(rt)})
        rt.capture_terminal=True;rt.observations();supervisor.finish()
        active_proof=conmod.active_proof(getattr(scanner,'active_progress',[]),rt.final_traffic)
        if not active_proof['pass']:raise Blocked('native active request count mismatched scanProgress')
        sink_audits += [{'stage':'before-stop',**container_sinks(rt,n)} for n in rt.names[:4] if n!=rt.anchor]
        # Keep the network boundary alive while the JVM stops: shutdown add-ons
        # can emit background HTTPS attempts that still require denial receipts.
        rt.resource_cleanup=True
        # Sampling continues through this declared exit; stopped cgroup peaks
        # are retained by the existing W4 cleanup sampler.
        # A single shutdown intent, then reconcile container state even if its
        # HTTP ACK is lost. Do not retry a shutdown/mutation blindly.
        j.append('intent',{'action':'w5-zap-graceful-shutdown','resource':rt.names[2]})
        try:rt.engine('core','action','shutdown',{})
        except Exception:pass
        deadline=time.monotonic()+20
        while rt.check_owner(rt.names[2])['State']['Running'] and time.monotonic()<deadline:time.sleep(.2)
        if rt.check_owner(rt.names[2])['State']['Running']:raise Blocked('saved-session writer shutdown unconfirmed')
        j.append('ack',{'action':'w5-zap-graceful-shutdown','resource':rt.names[2]})
        closed_traffic=rt.policy_traffic()
        supervisor.policy.traffic(closed_traffic['events'],complete=closed_traffic['complete'])
        supervisor.result.update(supervisor.policy.finalize())
        # Retain the earlier snapshot and seal only at the actual producer stop
        # barrier. New active/out-of-scope traffic would still fail policy above.
        save(root/'traffic-before-shutdown.json',rt.final_traffic)
        rt.final_traffic=closed_traffic
        if private_db:
            # The holder remains alive until the private JDBC audit completes.
            # No decoded session cells cross the controller/Docker output pipe.
            db_session=private_db_call(rt,plan,'cleanup',mode='session')
            database={'positiveControl':db_controls[-1]['audit'],'savedSession':db_session['audit'],'privateChannel':True}
        rt.check_owner(rt.names[1]);j.append('intent',{'action':'w5-owned-guard-sigkill','resource':rt.names[1]})
        docker(['kill','--signal','KILL',rt.names[1]])
        if rt.check_owner(rt.names[1])['State']['Running']:raise Blocked('guard crash not observed')
        rows.append({'caseId':'crash','status':'pass','guardProcessKilled':True,'restartPolicy':'fail-stop-no-token-resume',
                     'scope':'credential-holding process killed after producers terminal; mid-scan kill not claimed'})
        rt.terminate()
        sink_audits += [{'stage':'after-stop',**container_sinks(rt,n)} for n in rt.names[:4] if n!=rt.anchor]
        # Read the saved HSQL database only after its writer has stopped.
        if not private_db:
            create_db_reader(rt,plan)
            cmd=['exec','-i',rt.db_reader,'java','-cp','/tmp:/zap/lib/hsqldb-2.7.4.jar','SessionDbReadback']
            seeded=docker([*cmd,'selftest'],(PUBLIC_DB_CONTROL+'\n').encode(),timeout=30)
            control=audit_database(rt.auditor,seeded.encode(),expect_canary=True)
            decoded=docker([*cmd,'session'],timeout=30)
            database={'positiveControl':control,'savedSession':audit_database(rt.auditor,decoded.encode())}
        supervisor.resource.check(force=True)
        audit=audit_host(rt)
        if source_pin()!=plan['sourcePins']:raise Blocked('source drift during owned scanner campaign')
        status='development_pass_operational_blocked'
    except BaseException as exc:
        if isinstance(exc,SecretLeak):rt.leak=True
        error={'type':type(exc).__name__,'reason':str(exc)[:160] if isinstance(exc,Blocked) else 'owned campaign failed'}
        audit=[]
    finally:
        try:
            if not hasattr(rt,'cleanup_resource_tick'):supervisor.close()
            if rt.leak:
                supervisor.close()
                rt.cleanup_measurement_helper=None
                rt.terminate()  # Preserve stopped run-owned filesystems on leak.
                raise Blocked('canary sink quarantined; removal forbidden')
            rt.cleanup()
            if hasattr(supervisor,'cleanup_sealed'):
                try:supervisor.cleanup_complete()
                except Blocked as exc:
                    if str(exc)!='calibration-only workflow measured; normal publication refused':raise
            closed=True
        except Exception as exc:
            try:supervisor.close()
            except Exception:pass
            error=error or {'type':type(exc).__name__,'reason':'owned cleanup unconfirmed'}
            status='blocked'
    no_resources=not docker(['ps','-aq','--filter','label=zpa.run='+run]).strip()
    result={'schemaVersion':'w5-scanner-campaign/1.0','planHash':external,'runId':run,
            'status':status if closed and no_resources else 'blocked','error':error,'cases':rows,
            'actualHistoryAudits':history,'envelopeAudits':rt.audit_receipts,'artifactAudit':audit,
            'containerSinkAudits':sink_audits,'databaseReadback':database,
            'activePolicyProof':active_proof,
            'safetyFailure':supervisor.failure,'resourceFailure':supervisor.resource.failure,
            'apiFailures':getattr(rt,'api_failures',[]),
            'sinkReadStages':getattr(rt,'sink_stages',[]),
            'resourceDiagnostics':getattr(rt,'resource_diagnostics',[]),
            'resourceSamples':supervisor.resource.samples,'policy':getattr(supervisor,'policy_result',None),
            'monitorContract':MONITOR_CONTRACT,'policyMonitorSamples':supervisor.policy_samples,
            'resourceMetrics':rt.metrics,'memoryFailure':getattr(rt,'memory_failure',None),
            'resourceProfile':plan.get('resourceProfile'),
            'sourceBoundary':source_boundary,
            'privateSourceReceipts':source_receipts,
            'privateDbReader':db_reader,'privateDbAudits':db_controls,'privateDbChannelControls':db_negatives,
            'privateDbSessionAudit':db_session,'privateDbContract':PRIVATE_DB_CONTRACT if private_db else None,
            'cacheSeed':getattr(rt,'cache_seed',None),
            'maxObservedResourceGapSeconds':max((b['at']-a['at'] for a,b in zip(supervisor.resource.samples,supervisor.resource.samples[1:])),default=None),
            'noOwnedResources':no_resources,'cleanupConfirmed':closed,'canaryLeakDetected':rt.leak,
            'executionStatus':'completed' if status=='development_pass_operational_blocked' and closed else 'failed',
            'evidenceStatus':'complete-development-only' if status=='development_pass_operational_blocked' and closed else 'partial',
            'securityVerdict':'fail' if rt.leak else 'inconclusive',
            'cleanupStatus':'quarantine' if rt.leak or not closed or not no_resources else 'clean',
            'operationalG3':'blocked','productG4':'blocked','gateDecision':'block','securityApproval':False,
            'missingProof':['Production/delegated admission needs per-sink seeded controls beyond the fixture readers, independent review and transport/dump boundary acceptance',
                            'Product subject/epoch adapter not runtime verified; role/refresh/revoke unobserved in bounded discovery'],
            'limits':['Owned canary diagnostic, no real credential/product traffic','G5/G6 calibration-only; no protected operational admission','Browser/native/canonical/shared unadmitted']}
    save(work/'gate-results.json',result)
    index={str(f.relative_to(work)):hashlib.sha256(f.read_bytes()).hexdigest()
           for f in work.rglob('*') if f.is_file() and not f.is_symlink()}
    save(work/'readback-index.json',index)
    return result


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['prepare','run','recover','verify']);ap.add_argument('--work-dir',required=True,type=Path);ap.add_argument('--actor',choices=['A','B'],default='A');ap.add_argument('--expect-plan-hash');ap.add_argument('--resource-profile',choices=['legacy','bounded-fixture'],default='legacy');ap.add_argument('--source-mode',choices=['generated','private-file'],default='generated')
    ap.add_argument('--private-db-controls',action='store_true');a=ap.parse_args()
    if a.command!='prepare' and (a.source_mode!='generated' or a.private_db_controls):ap.error('source/control options belong to prepare; execution uses the locked plan')
    if a.command=='prepare':r=prepare(a.work_dir,a.actor,a.resource_profile,a.source_mode,a.private_db_controls)
    elif a.command=='run':r=run(a.work_dir,a.expect_plan_hash)
    elif a.command=='recover':r=recover(a.work_dir,a.expect_plan_hash)
    else:r=verify(a.work_dir,a.expect_plan_hash)
    summary={k:v for k,v in r.items() if k in ('planHash','runId','workDir','status','error','cleanupConfirmed','noOwnedResources','stopOnly','noReplay','readbackStatus')}
    if isinstance(r.get('cases'),list):summary['caseCount']=len(r['cases'])
    print(json.dumps(summary))
    return 0 if r.get('status','development_pass_operational_blocked')=='development_pass_operational_blocked' else 2
if __name__=='__main__':sys.exit(main())
