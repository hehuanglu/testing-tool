#!/usr/bin/env python3
"""Owned synthetic browser diagnostic. No product URL, credential input or ZAP."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from zap_assessment.business import digest,validate_manifest
from zap_assessment.business_fixture import generate_manifest
from zap_assessment.contracts import canonical
from zap_assessment.journal import Journal
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.ui_contract import VERSION,ui_steps,public_config,audit_ui
from zap_assessment.ui_verification import verify_ui_bundle
from zap_assessment.unified_binding import validate_context,bind_fixture,docker_labels

IMAGE='sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6'


def docker(args,timeout=30):
    r=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout)
    if r.returncode:raise RuntimeError('owned_ui_docker_'+args[0]+'_failed')
    return r.stdout


def write(path,value):atomic_bytes(path,canonical(value))
def inspect(name):return json.loads(docker(['inspect',name]))[0]


def owned_work_file(cid,path,budget):
    # Docker archive/cp does not expose this runtime's tmpfs mount. Read only
    # fixed minimized export paths, with a bound enforced before stdout export.
    if path!='/work/result.json' and path!='/work/screens/balance-after-reload.png':
        raise ValueError('unregistered_ui_export_path')
    script='import pathlib,sys; b=pathlib.Path(sys.argv[1]).open("rb").read(int(sys.argv[2])+1); assert len(b)<=int(sys.argv[2]); sys.stdout.buffer.write(b)'
    r=subprocess.run(['docker','exec',cid,'python','-c',script,path,str(budget)],capture_output=True,timeout=15)
    if r.returncode or len(r.stdout)>budget:raise RuntimeError('owned_ui_bounded_export_failed')
    return r.stdout


def source_pins():
    names=[*sorted((ROOT/'src/zap_assessment').glob('ui_*.py')),ROOT/'src/zap_assessment/business.py',ROOT/'src/zap_assessment/business_fixture.py',
           ROOT/'src/zap_assessment/product_adapter.py',ROOT/'src/zap_assessment/ui_verification.py',ROOT/'src/zap_assessment/opaque_canary.py',
           ROOT/'src/zap_assessment/secret_audit.py',ROOT/'src/zap_assessment/verification.py',ROOT/'src/zap_assessment/safety_io.py',ROOT/'schemas/remediation/ui-plan.schema.json',ROOT/'src/zap_assessment/unified_binding.py',Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in names}


def seal(root):
    rows=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name not in ('manifest.json','manifest.sha256'):
            blob=p.read_bytes();rows.append({'path':str(p.relative_to(root)),'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest()})
    raw=canonical({'contractVersion':VERSION,'artifacts':rows});atomic_bytes(root/'manifest.json',raw);atomic_bytes(root/'manifest.sha256',(hashlib.sha256(raw).hexdigest()+'\n').encode())


def run(args,context=None):
    context=validate_context(context,{"session","ui"})
    if not args.spike_only:
        if not args.session_spike or not args.expect_spike_plan_sha:raise ValueError('session_spike_with_external_pin_required_before_full_diagnostic')
        spike=verify_ui_bundle(args.session_spike,args.expect_spike_plan_sha)
        if (spike['scope']!='session-spike' or spike['executionStatus']!='completed' or spike['evidenceKind']!='actual-webdriver'
                or spike['image']!=IMAGE):raise ValueError('session_spike_not_completed')
        current=source_pins()
        for key in ('src/zap_assessment/ui_fixture.py','src/zap_assessment/ui_webdriver.py','src/zap_assessment/ui_browser_worker.py'):
            if spike['sourcePins'].get(key)!=current[key]:raise ValueError('session_spike_source_drift')
    output=args.output.resolve();output.mkdir(mode=0o700,parents=True,exist_ok=False)
    ident=uuid.uuid4().hex;run_id=context['childRunId'] if context else 'w6-w7-'+ident;name='w7-ui-'+run_id.removeprefix('w6-w7-');volume=name+'-profile'
    fixture=validate_manifest(generate_manifest(run_id,args.seed,args.adapter,args.reverse))
    bind_fixture(context,digest(fixture))
    plan={'contractVersion':VERSION,'mode':'owned-synthetic-ui-diagnostic','scope':'session-spike' if args.spike_only else 'ui-business-flow',
          'runId':run_id,'fixtureHash':digest(fixture),'containerName':name,'profileVolume':volume,'image':IMAGE,
          'fidelity':'owned-synthetic-source-derived-ui','fault':args.fault,'steps':ui_steps(fixture,args.spike_only),
          'evidenceKind':'actual-webdriver','sourcePins':source_pins(),'securityApproval':False,'productRequestsPermitted':False,
          'spikePlanHash':None if args.spike_only else args.expect_spike_plan_sha}
    if context:plan['unifiedBinding']=context
    config=public_config(fixture);write(output/'locked-plan.json',plan)
    write(output/'job.json',{'plan':plan,'fixture':fixture,'config':config});(output/'job.json').chmod(0o444)
    fs=os.statvfs(output);free=fs.f_bavail*fs.f_frsize
    write(output/'resource-preflight.json',{'hostFreeBytes':free,'estimatedGrowthBytes':32*1024**2,'reserveBytes':2*1024**3,'memoryBytes':768*1024**2})
    if free<2*32*1024**2+2*1024**3:raise RuntimeError('ui_disk_preflight_blocked')
    journal=Journal(output/'journal.jsonl',run_id,digest(plan));journal.append('plan_locked',{'planHash':digest(plan),'sourcePins':plan['sourcePins']})
    cid=None;runtime=None;made_volume=False;result=None;private=None
    try:
        journal.append('volume_create_intent',{'name':volume,'image':IMAGE})
        docker(['volume','create','--label','zpa.run='+run_id,'--label','zpa.mode=w7-ui-diagnostic',*docker_labels(context),volume]);made_volume=True
        v=json.loads(docker(['volume','inspect',volume]))[0]
        if v['Labels'].get('zpa.run')!=run_id:raise RuntimeError('profile_volume_ownership')
        journal.append('container_create_intent',{'name':name,'image':IMAGE,'volume':volume})
        cid=docker(['run','-d','--name',name,'--label','zpa.run='+run_id,'--label','zpa.mode=w7-ui-diagnostic',
                    *docker_labels(context),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1000:1000',
                    '--memory','768m','--memory-swap','768m','--cpus','1','--pids-limit','256','--ulimit','core=0','--shm-size','128m',
                    '--tmpfs','/work:rw,exec,nosuid,size=256m,uid=1000,gid=1000,mode=0700',
                    '--tmpfs','/tmp:rw,nosuid,size=128m,uid=1000,gid=1000,mode=1777',
                    '--mount','type=volume,src='+volume+',dst=/home/zap',
                    '--mount','type=bind,src='+str(ROOT/'src')+',dst=/source,readonly',
                    '--mount','type=bind,src='+str(output/'job.json')+',dst=/job.json,readonly',
                    '--env','PYTHONPATH=/source','--env','PYTHONDONTWRITEBYTECODE=1','--env','HOME=/home/zap','--env','MOZ_CRASHREPORTER_DISABLE=1',
                    '--entrypoint','python',IMAGE,'-m','zap_assessment.ui_browser_worker']).strip()
        j=inspect(cid)
        if j['Config']['Labels'].get('zpa.run')!=run_id or j['Image']!=IMAGE:raise RuntimeError('ui_container_ownership')
        runtime={'id':cid,'name':name,'image':j['Image'],'runId':run_id,'networkMode':j['HostConfig']['NetworkMode'],
                 'readOnlyRoot':j['HostConfig']['ReadonlyRootfs'],'profileVolume':volume,'memoryBytes':j['HostConfig']['Memory'],
                 'memorySwapBytes':j['HostConfig']['MemorySwap'],'capDrop':j['HostConfig']['CapDrop'],'pidsLimit':j['HostConfig']['PidsLimit']}
        journal.append('container_created',runtime)
        deadline=time.monotonic()+150
        while True:
            ready=subprocess.run(['docker','exec',cid,'test','-f','/work/result.json'],capture_output=True,timeout=8)
            if ready.returncode==0:break
            j=inspect(cid)
            if not j['State']['Running'] or time.monotonic()>=deadline:break
            time.sleep(.2)
        j=inspect(cid)
        if ready.returncode!=0:
            write(output/'worker-failure.json',{'exitCode':j['State']['ExitCode'],'oomKilled':j['State']['OOMKilled'],'safeLog':docker(['logs',cid])})
            raise RuntimeError('ui_worker_failed')
        atomic_bytes(output/'worker-result.json',owned_work_file(cid,'/work/result.json',4*1024**2))
        result=json.loads((output/'worker-result.json').read_text())
        if result['screenshots']:
            (output/'screenshots').mkdir()
            for screen in result['screenshots']:
                if screen['path']!='balance-after-reload.png':raise ValueError('unregistered_ui_screenshot')
                atomic_bytes(output/'screenshots'/screen['path'],owned_work_file(cid,'/work/screens/'+screen['path'],256*1024))
    finally:
        if cid is None:
            candidate=subprocess.run(['docker','inspect',name],capture_output=True,text=True,timeout=10)
            if candidate.returncode==0:
                j=json.loads(candidate.stdout)[0]
                if j['Config']['Labels'].get('zpa.run')==run_id and j['Image']==IMAGE:cid=j['Id']
        if cid:
            j=inspect(cid)
            if j['Id']!=cid or j['Config']['Labels'].get('zpa.run')!=run_id or j['Image']!=IMAGE:raise RuntimeError('ui_cleanup_ownership')
            if j['State']['Running']:docker(['stop','--time','5',cid])
            private=Path.home()/'.codex/private-evidence/mcp-zap'/run_id;private.mkdir(mode=0o700,parents=True,exist_ok=False)
            docker(['cp',cid+':/home/zap/.',str(private)])
            index=[]
            for p in sorted(private.rglob('*')):
                if p.is_file() and not p.is_symlink():p.chmod(0o600);index.append({'path':str(p.relative_to(private)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
                elif p.is_dir():p.chmod(0o700)
            raw=canonical({'files':index});(private/'private-index.json').write_bytes(raw);(private/'private-index.json').chmod(0o600)
            write(output/'private-profile-retention.json',{'path':str(private),'indexSha256':hashlib.sha256(raw).hexdigest(),'files':len(index),'sourceValuesIncluded':False})
            journal.append('cleanup_intent',{'containerId':cid,'volume':volume,'rawProfileRetention':'private-outside-workspace'})
            docker(['rm',cid])
        if not made_volume:
            candidate=subprocess.run(['docker','volume','inspect',volume],capture_output=True,text=True,timeout=10)
            if candidate.returncode==0:
                v=json.loads(candidate.stdout)[0]
                if v.get('Labels',{}).get('zpa.run')==run_id:made_volume=True
        if made_volume:
            v=json.loads(docker(['volume','inspect',volume]))[0]
            if v['Labels'].get('zpa.run')!=run_id:raise RuntimeError('ui_volume_cleanup_ownership')
            docker(['volume','rm',volume])
        if cid and runtime and private:
            c=subprocess.run(['docker','inspect',cid],capture_output=True,timeout=10);v=subprocess.run(['docker','volume','inspect',volume],capture_output=True,timeout=10)
            cleanup={'runtime':runtime,'containerRemoved':c.returncode!=0,'volumeRemoved':v.returncode!=0,
                     'rawProfileRetention':'private-outside-workspace','privateProfileIndexSha256':hashlib.sha256((private/'private-index.json').read_bytes()).hexdigest()}
            write(output/'cleanup.json',cleanup);journal.append('cleanup_confirmed',cleanup)
    if result is None:raise RuntimeError('ui_no_result')
    observations={k:result[k] for k in ('steps','browser','screenshots','driverPin','browserCleanupError')};observations['runtime']=runtime;observations['evidenceKind']='actual-webdriver'
    if context:observations['unifiedBinding']=result['unifiedBinding']
    verdict=audit_ui(plan,fixture,observations,result['arrivals'],result['secretAudit'],cleanup)
    bundle=output/'bundle';bundle.mkdir(mode=0o700)
    for filename,value in [('plan.json',plan),('fixture.json',fixture),('observations.json',observations),('arrivals.json',result['arrivals']),
                           ('secret-audit.json',result['secretAudit']),('cleanup.json',cleanup),('result.json',verdict)]:write(bundle/filename,value)
    if result['screenshots']:
        (bundle/'screenshots').mkdir()
        for s in result['screenshots']:atomic_bytes(bundle/'screenshots'/s['path'],(output/'screenshots'/s['path']).read_bytes())
    seal(bundle);verified=verify_ui_bundle(bundle,digest(plan));write(output/'verification.json',verified)
    expected='not_run' if args.spike_only else 'inconclusive' if args.fault=='no-submit' else 'pass' if args.fault=='fixed' else 'fail'
    passed=verified['functionalVerdict']==expected and verified['secretVerdict']=='fail'
    write(output/'gate-results.json',{'developmentPassed':passed,'expectedFunctionalVerdict':expected,'planHash':digest(plan),
          **{k:verified[k] for k in ('scope','executionStatus','evidenceStatus','functionalVerdict','applicationVerdict','secretVerdict','securityVerdict','cleanupStatus','gateDecision','G8Operational','stepCounts')},
          'privateProfileRetained':True,'securityApproval':False,'productRequests':0})
    return passed


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--seed',type=int,required=True)
    p.add_argument('--adapter',choices=['finalsource-shaped','alternate-ledger'],default='finalsource-shaped');p.add_argument('--reverse',action='store_true')
    p.add_argument('--fault',choices=['fixed','wrong-balance','error-page','denied-mutated','denied-disclosure','no-submit'],default='fixed')
    p.add_argument('--spike-only',action='store_true');p.add_argument('--session-spike',type=Path);p.add_argument('--expect-spike-plan-sha');a=p.parse_args()
    try:passed=run(a);print(json.dumps({'developmentPassed':passed,'gateDecision':'block','productRuntimeVerified':False}));return 0 if passed else 1
    except Exception as exc:print(json.dumps({'developmentPassed':False,'errorType':type(exc).__name__,'reasonCode':str(exc) if isinstance(exc,RuntimeError) else 'invalid_or_incomplete_ui_diagnostic'}));return 2


if __name__=='__main__':raise SystemExit(main())
