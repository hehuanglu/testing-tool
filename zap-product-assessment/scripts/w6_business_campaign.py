#!/usr/bin/env python3
"""Owned synthetic W6 HTTP campaign. Never accepts a product URL or credentials."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from zap_assessment.business import digest, validate_manifest, VERSION
from zap_assessment.business_fixture import generate_manifest
from zap_assessment.business_verification import audit_business, verify_business_bundle
from zap_assessment.product_adapter import prepare_jobs
from zap_assessment.contracts import canonical
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.unified_binding import validate_context, bind_fixture, docker_labels


def docker(args,timeout=30,payload=None):
    result=subprocess.run(['docker',*args],capture_output=True,text=True,timeout=timeout,input=payload)
    if result.returncode:raise RuntimeError('docker command failed: '+args[0])
    return result.stdout


def write(path, value):atomic_bytes(path,canonical(value))


def seal(bundle):
    rows=[]
    for p in sorted(bundle.iterdir()):
        if p.name in ('manifest.json','manifest.sha256'):continue
        raw=p.read_bytes();rows.append({'path':p.name,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
    raw=canonical({'contractVersion':VERSION,'artifacts':rows});atomic_bytes(bundle/'manifest.json',raw)
    atomic_bytes(bundle/'manifest.sha256',(hashlib.sha256(raw).hexdigest()+'\n').encode())


def source_pins():
    paths=[*sorted((ROOT/'src/zap_assessment').glob('business*.py')),ROOT/'src/zap_assessment/product_adapter.py',
           ROOT/'src/zap_assessment/bola_http.py',ROOT/'src/zap_assessment/verification.py',ROOT/'src/zap_assessment/safety_io.py',
           ROOT/'schemas/remediation/business-fixture.schema.json',ROOT/'src/zap_assessment/unified_binding.py',Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run(output,seed,adapter,reverse,fault,context=None):
    context=validate_context(context,{"api"})
    output=Path(output).resolve();output.mkdir(mode=0o700,parents=True,exist_ok=False)
    run_id=context['childRunId'] if context else 'w6-'+uuid.uuid4().hex;name=run_id+'-fixture'
    fixture=validate_manifest(generate_manifest(run_id,seed,adapter,reverse))
    bind_fixture(context,digest(fixture))
    jobs=prepare_jobs(fixture)
    free=os.statvfs(output).f_bavail*os.statvfs(output).f_frsize
    resource={'hostFreeBytes':free,'estimatedGrowthBytes':32*1024**2,'reserveBytes':2*1024**3,'fixtureMemoryLimitBytes':128*1024**2}
    write(output/'resource-preflight.json',resource)
    if free < 2*resource['estimatedGrowthBytes']+resource['reserveBytes']:raise RuntimeError('owned fixture disk preflight blocked')
    image=json.loads((ROOT/'profiles/runtime-baseline.json').read_text())['boundary']
    image_id=docker(['image','inspect',image,'--format','{{.Id}}']).strip()
    plan={'contractVersion':VERSION,'mode':'owned-synthetic-business','runId':run_id,'fixtureHash':digest(fixture),
          'containerName':name,'image':image_id,'sourcePins':source_pins(),'securityApproval':False,
          'contractScope':'API business/BOLA on owned fixture; bills/product runtime excluded as explicit gaps',
          'fault':fault,'borrowedBolaContract':'v1.4 read-only unchanged'}
    if context:plan['unifiedBinding']=context
    write(output/'fixture-input.json',fixture);(output/'fixture-input.json').chmod(0o444);write(output/'locked-plan.json',plan)
    cid=None;runtime=None;cleanup=None
    started=time.time()
    try:
        cid=docker(['run','-d','--name',name,'--label','zpa.run='+run_id,'--label','zpa.mode=w6-owned-business',
                    *docker_labels(context),'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
                    '--memory','128m','--memory-swap','128m','--cpus','0.5','--pids-limit','48','--user','1000:1000',
                    '--tmpfs','/state:rw,nosuid,noexec,size=16m,uid=1000,gid=1000,mode=0700',
                    '--mount','type=bind,src='+str(ROOT/'src')+',dst=/source,readonly',
                    '--mount','type=bind,src='+str(output/'fixture-input.json')+',dst=/manifest.json,readonly',
                    '--env','PYTHONPATH=/source','--env','PYTHONDONTWRITEBYTECODE=1',image_id,
                    'python','-m','zap_assessment.business_fixture','/manifest.json','/state',fault]).strip()
        j=json.loads(docker(['inspect',name]))[0]
        if j['Id']!=cid or j['Config']['Labels'].get('zpa.run')!=run_id:raise RuntimeError('create ownership mismatch')
        runtime={'id':cid,'name':name,'image':j['Image'],'runId':run_id,'networkMode':j['HostConfig']['NetworkMode'],'readOnlyRoot':j['HostConfig']['ReadonlyRootfs']}
        for attempt in range(40):
            ready=subprocess.run(['docker','exec',name,'test','-f','/state/state.json'],capture_output=True,timeout=5)
            if ready.returncode==0:break
            time.sleep(.1)
        else:raise RuntimeError('fixture readiness deadline')
        observations=json.loads(docker(['exec','-i',name,'python','-m','zap_assessment.business_worker'],120,json.dumps({'jobs':jobs,'runId':run_id,'unifiedBinding':context})))
        observations['runtime']=runtime
        arrivals=[json.loads(line) for line in docker(['exec',name,'cat','/state/arrivals.jsonl']).splitlines()]
        write(output/'raw-observations.json',observations);write(output/'raw-arrivals.json',arrivals)
    finally:
        if cid:
            j=json.loads(docker(['inspect',name]))[0]
            if j['Id']!=cid or j['Config']['Labels'].get('zpa.run')!=run_id or j['Image']!=image_id:raise RuntimeError('cleanup ownership mismatch')
            docker(['stop','--time','2',cid]);docker(['rm',cid])
            remains=subprocess.run(['docker','inspect',cid],capture_output=True,timeout=10)
            cleanup={'cleanupStatus':'clean' if remains.returncode else 'failed','runtime':runtime,'removed':bool(remains.returncode)}
            write(output/'cleanup-receipt.json',cleanup)
        write(output/'execution-receipt.json',{'runId':run_id,'elapsedSeconds':time.time()-started,'ownedContainerId':cid,
              'productRequests':0,'realCredentialsResolved':0,'fault':fault})
    bundle=output/'bundle';bundle.mkdir(mode=0o700)
    result=audit_business(plan,fixture,observations,arrivals,cleanup)
    for name,value in [('plan.json',plan),('fixture.json',fixture),('observations.json',observations),
                       ('arrivals.json',arrivals),('cleanup.json',cleanup),('result.json',result)]:write(bundle/name,value)
    seal(bundle);pin=digest(plan);verified=verify_business_bundle(bundle,pin)
    write(output/'verification.json',verified);write(output/'plan-pin.json',{'planHash':pin})
    expected='pass' if fault=='fixed' else 'fail'
    passed=verified['syntheticContractStatus']==expected
    write(output/'campaign-result.json',{'developmentExpectation':expected,'developmentPassed':passed,
        'planHash':pin,'applicationOracleCounts':verified['applicationOracleCounts'],
        'executionStatus':verified['executionStatus'],'evidenceStatus':verified['evidenceStatus'],
        'securityVerdict':verified['securityVerdict'],'cleanupStatus':verified['cleanupStatus'],'gateDecision':'block'})
    return passed


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seed',type=int,required=True);p.add_argument('--adapter',choices=['finalsource-shaped','alternate-ledger'],default='finalsource-shaped')
    p.add_argument('--reverse',action='store_true');p.add_argument('--fault',choices=['fixed','denied-mutated','denied-disclosure','list-leak'],default='fixed')
    args=p.parse_args();passed=run(args.output,args.seed,args.adapter,args.reverse,args.fault)
    print(json.dumps({'developmentPassed':passed,'output':str(args.output),'productRuntimeVerified':False,'gateDecision':'block'}));return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
