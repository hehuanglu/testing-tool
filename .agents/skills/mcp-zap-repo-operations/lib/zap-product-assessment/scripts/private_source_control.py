#!/usr/bin/env python3
"""Locked Linux peer/source controls; no product reference, URL or secret input."""
import argparse
from dataclasses import asdict
import hashlib,importlib.util,json,os,re,subprocess,sys,time,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'src'))
from zap_assessment.contracts import canonical,digest
from zap_assessment.credential_broker import BrokerBinding
from zap_assessment.errors import Blocked
from zap_assessment.private_db import strict_json
from zap_assessment.runtime import PYTHON
from zap_assessment.safety_io import atomic_bytes
spec=importlib.util.spec_from_file_location('native_sink_control',ROOT/'scripts/actual_zap_sink_control.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)


def pins():
    return {**native.source_pin(),str(Path(__file__).relative_to(ROOT)):hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def prepare(work):
    if not work.is_absolute() or work.exists() or work.is_symlink():raise Blocked('source_control_work_not_fresh')
    run='source-control-'+uuid.uuid4().hex
    plan={'contract':'owned-source-control/1.0','runId':run,'image':PYTHON,
        'imageId':native.call(['image','inspect','--format','{{.Id}}',PYTHON]).decode().strip(),
        'sourcePins':pins(),'expiresAt':time.time()+900,'productInputAccepted':False,'operationalAdmission':False,
        'grants':{k:{'referenceId':uuid.uuid4().hex,'actor':a,'subject':s,'uid':u,
            'build':'source-prerequisite-blocked' if k=='gated' else 'owned-source-broker/1.0'}
            for k,a,s,u in [('A','A','11',1003),('B','B','12',1004),('lost','A','11',1003),('gated','A','11',1003)]},
        'resources':{'hostReserveBytes':2*1024**3,'estimatedHostGrowthBytes':32*1024**2,
            'dockerReserveBytes':2*1024**3,'ramReserveBytes':512*1024**2,'containerLimitBytes':128*1024**2,
            'sampleSeconds':5,'deadlineSeconds':90,'productCalibration':False}}
    work.mkdir(mode=0o700)
    for rel,h in plan['sourcePins'].items():
        raw=(ROOT/rel).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=h:raise Blocked('source_control_prepare_drift')
        p=work/'source'/rel;p.parent.mkdir(parents=True,exist_ok=True);atomic_bytes(p,raw);p.chmod(0o444)
    atomic_bytes(work/'plan.json',canonical(plan))
    return {'planHash':digest(plan),'workDir':str(work),'productRequests':0}


def validate_status(value,config):
    if (not isinstance(value,dict) or set(value)!={'contract','ready','runId','uid','sourceReads','usedReferences',
          'sourceMetadata','events','authRequests','sourceValuesIncluded','productRequests'}
            or value['contract']!='owned-source-control/1.0' or value['ready'] is not True
            or value['runId']!=config['runId'] or value['uid']!=1005 or value['sourceValuesIncluded'] is not False
            or value['productRequests']!=0 or type(value['sourceReads']) is not int or not 0<=value['sourceReads']<=3):
        raise Blocked('source_control_status_contract')
    refs={r['referenceId'] for r in config['grants'].values()}
    actors={r['referenceId']:r['binding']['actor_ref'] for r in config['grants'].values()}
    if (not isinstance(value['usedReferences'],list) or not set(value['usedReferences'])<=refs
            or len(value['usedReferences'])!=len(set(value['usedReferences']))
            or not isinstance(value['sourceMetadata'],list) or len(value['sourceMetadata'])!=9
            or any(type(n) is not int or n<0 for n in value['sourceMetadata'])
            or value['sourceMetadata'][2:6]!=[1005,1005,1,0o600]):
        raise Blocked('source_control_status_contract')
    for row in value['events']:
        if (not isinstance(row,dict) or row.get('referenceId') not in refs
                or row.get('actorRef')!=actors[row['referenceId']]):
            raise Blocked('source_control_status_contract')
        if row.get('event')=='source_grant_reserved':
            if set(row)!={'event','referenceId','runId','planHash','actorRef'} or row['runId']!=config['runId']:
                raise Blocked('source_control_status_contract')
            if row['planHash'] not in {r['binding']['plan_hash'] for r in config['grants'].values()}:
                raise Blocked('source_control_status_contract')
        elif row.get('event')=='source_grant_delivery_attempt':
            if set(row)!={'event','referenceId','actorRef','sourceValuesIncluded'} or row['sourceValuesIncluded'] is not False:
                raise Blocked('source_control_status_contract')
        else:raise Blocked('source_control_status_contract')
    for row in value['authRequests']:
        if (not isinstance(row,dict) or set(row)!={'method','operation','accepted','actorRef'}
                or row['method'] not in ('GET','POST') or row['operation'] not in ('login','identity','protected')
                or type(row['accepted']) is not bool or row['actorRef'] not in (None,'A','B')):
            raise Blocked('source_control_status_contract')
    return value


def run(work,expected):
    plan=strict_json((work/'plan.json').read_bytes())
    if digest(plan)!=expected or plan['sourcePins']!=pins() or time.time()>=plan['expiresAt']:
        raise Blocked('source_control_entry_drift')
    for rel,h in plan['sourcePins'].items():
        if hashlib.sha256((work/'source'/rel).read_bytes()).hexdigest()!=h:raise Blocked('source_control_snapshot_drift')
    fd=os.open(work/'attempt.lock',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600);os.close(fd)
    limit=plan['resources'];fs=os.statvfs(work)
    if fs.f_bavail*fs.f_frsize<limit['hostReserveBytes']+2*limit['estimatedHostGrowthBytes']:
        raise Blocked('source_control_host_headroom')
    name='zpa-'+plan['runId'];cid=None;samples=[];receipts=[];deadline=time.monotonic()+limit['deadlineSeconds']
    config={'contract':plan['contract'],'runId':plan['runId'],'productInputAccepted':False,'grants':{}}
    for key,row in plan['grants'].items():
        b=BrokerBinding(plan['runId'],expected,row['actor'],row['subject'],None,row['build'],
                        'http://127.0.0.1:18080',plan['expiresAt'])
        config['grants'][key]={'referenceId':row['referenceId'],'binding':asdict(b),'uid':row['uid']}
    status={'executionStatus':'partial','evidenceStatus':'incomplete','securityVerdict':'inconclusive',
            'cleanupStatus':'pending','gateDecision':'block','productRequests':0}
    atomic_bytes(work/'create-intent.json',canonical({'name':name,'planHash':expected,'imageId':plan['imageId']}))
    def exchange(args,payload=None):
        if time.monotonic()>=deadline:raise Blocked('source_control_deadline')
        r=subprocess.run(['docker',*args],input=payload,capture_output=True,timeout=min(8,max(.1,deadline-time.monotonic())))
        if r.returncode or len(r.stdout)>65536 or r.stderr:raise Blocked('source_control_private_exchange_failed')
        return r.stdout
    try:
        status['phase']='create'
        cid=native.call(['create','--name',name,'--label','zpa.run='+plan['runId'],'--network','none',
            '--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--user','1005:1005',
            '--memory','128m','--memory-swap','128m','--pids-limit','64','--cpus','1','--ulimit','core=0:0',
            '--log-driver','none','--tmpfs','/tmp:rw,size=16m,uid=1005,gid=1005,mode=0700',
            '-v',str(work/'source/src')+':/package/src:ro','-e','PYTHONPATH=/package/src',
            '--entrypoint','sleep',plan['imageId'],'120']).decode().strip()
        atomic_bytes(work/'create-ack.json',canonical({'name':name,'id':cid,'planHash':expected}))
        native.owner(name,plan,cid);native.call(['start',cid])
        def sample():
            began=time.monotonic();info=native.owner(name,plan,cid)
            raw=exchange(['exec',cid,'python3','-c',"import json,os,pathlib; f=os.statvfs('/'); m=dict(x.split(':',1) for x in open('/proc/meminfo')); p=pathlib.Path('/sys/fs/cgroup'); print(json.dumps({'dockerFree':f.f_bavail*f.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024,'memoryPeak':int((p/'memory.peak').read_text()),'memoryEvents':(p/'memory.events').read_text()}))"])
            row=strict_json(raw);row.update(startedAt=began,completedAt=time.monotonic(),containerId=cid,
                hostFree=os.statvfs(work).f_bavail*os.statvfs(work).f_frsize);samples.append(row)
            events=dict(line.split() for line in row['memoryEvents'].splitlines())
            if (row['completedAt']-began>5 or (len(samples)>1 and row['completedAt']-samples[-2]['completedAt']>5)
                    or row['hostFree']<limit['hostReserveBytes'] or row['dockerFree']<limit['dockerReserveBytes']
                    or row['ramAvailable']<limit['ramReserveBytes'] or row['memoryPeak']>limit['containerLimitBytes']
                    or any(int(events.get(k,0)) for k in ('oom','oom_kill','oom_group_kill')) or info['State']['OOMKilled']):
                raise Blocked('source_control_resource_bound')
        sample();status['phase']='server-startup'
        # Detached exec does not carry an attached stdin. Stage only this public
        # binding/grant metadata, never source values, before starting the server.
        exchange(['exec','-i',cid,'python3','-c',"import os,sys; from pathlib import Path; os.umask(0o077); Path('/tmp/source-control-config.json').write_bytes(sys.stdin.buffer.read(16385))"],canonical(config))
        exchange(['exec','-d',cid,'python3','-m','zap_assessment.source_broker_fixture','server'])
        def state():
            return validate_status(strict_json(exchange(['exec',cid,'python3','-c',"from pathlib import Path; print(Path('/tmp/source-broker-status.json').read_text())"])),config)
        ready_end=time.monotonic()+8
        while True:
            try:initial=state();break
            except Blocked:
                if time.monotonic()>=ready_end:raise
                sample();time.sleep(.1)
        atomic_bytes(work/'source-before.json',canonical(initial));sample()
        def client(label,key,uid,action,expected_status,cfg=None):
            status['phase']=label
            raw=exchange(['exec','-i','--user',str(uid)+':'+str(uid),cid,'python3','-m',
                'zap_assessment.source_broker_fixture','client','--grant',key,'--action',action],canonical(cfg or config))
            value=strict_json(raw)
            if value.get('status')!=expected_status or value.get('sourceValuesIncluded') is not False:
                raise Blocked('source_control_client_assertion')
            if expected_status=='pass':
                if set(value)!={'status','actorRef','session','eventCounts','sourceValuesIncluded'}:
                    raise Blocked('source_control_client_contract')
                session=value['session']
                if (value['actorRef']!=config['grants'][key]['binding']['actor_ref'] or session.get('state')!='closed'
                        or session.get('writerFailed') is not False or not session.get('stop',{}).get('terminalConfirmed')):
                    raise Blocked('source_control_client_contract')
                counts=value['eventCounts'];allowed={'identity_proof','epoch_started','protected_start',
                    'protected_response_received','protected_finish','auth_lost','producer_stop'}
                if (not isinstance(session.get('authEpoch'),str) or not re.fullmatch('[0-9a-f]{32}',session['authEpoch'])
                        or not isinstance(counts,dict) or not set(counts)<=allowed
                        or any(type(n) is not int or not 1<=n<=10 for n in counts.values())):
                    raise Blocked('source_control_client_contract')
                # Keep only allowlisted derived metadata; no private response or token.
                value={'status':'pass','actorRef':value['actorRef'],'authEpoch':session['authEpoch'],
                       'terminalConfirmed':True,'eventCounts':value['eventCounts'],'sourceValuesIncluded':False}
            elif set(value)!={'status','sourceValuesIncluded'}|({'loginAttempted'} if action=='lost-ack' else set()):
                raise Blocked('source_control_client_contract')
            if action=='lost-ack' and value['loginAttempted'] is not False:
                raise Blocked('source_control_client_contract')
            receipts.append({'case':label,'uid':uid,'result':value});sample()
        client('wrong-peer','A',1000,'resolve','denied')
        client('wrong-server','A',1003,'wrong-server','denied')
        bad=strict_json(canonical(config));bad['grants']['A']['binding']['plan_hash']='0'*64
        client('wrong-plan','A',1003,'resolve','denied',bad)
        client('cross-actor-peer','B',1003,'resolve','denied')
        client('prerequisite-denied','gated',1003,'resolve','denied')
        client('actor-A','A',1003,'session','pass')
        client('actor-A-replay','A',1003,'resolve','denied')
        client('actor-B','B',1004,'session','pass')
        client('lost-ack','lost',1003,'lost-ack','sent_without_readback')
        client('lost-ack-replay','lost',1003,'resolve','denied')
        time.sleep(.2);final=state();sample()
        if (final['sourceReads']!=3 or len(final['usedReferences'])!=4 or len(final['authRequests'])!=8
                or any(r['accepted'] is not True for r in final['authRequests'])):
            raise Blocked('source_control_independent_counts')
        atomic_bytes(work/'source-after.json',canonical(final));atomic_bytes(work/'cases.json',canonical(receipts))
        status.update(executionStatus='completed',evidenceStatus='complete',phase='completed')
    except Exception as exc:status['reasonCode']=str(exc) if isinstance(exc,Blocked) else 'source_control_failed'
    finally:
        try:
            if cid is None:
                found=native.call(['ps','-aq','--filter','name=^/'+name+'$']).decode().strip()
                if found:cid=native.owner(name,plan,None)['Id']
            if cid:
                native.owner(name,plan,cid);native.call(['stop','--time','5',cid]);info=native.owner(name,plan,cid)
                if info['State']['Running']:raise Blocked('source_control_stop_unconfirmed')
                atomic_bytes(work/'stop.json',canonical({'containerId':cid,'terminal':True,'oomKilled':info['State']['OOMKilled']}))
                native.call(['rm',cid])
            status['cleanupStatus']='clean'
        except Exception:status['cleanupStatus']='quarantine'
        atomic_bytes(work/'resource-samples.json',canonical(samples))
        atomic_bytes(work/'status.json',canonical({**status,'planHash':expected,'operationalAdmission':False,
            'limitation':'Owned canary source/peer protocol only; no product/host-VM platform acceptance.'}))
    return status


def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('command',choices=['prepare','run','recover'])
    ap.add_argument('--work-dir',type=Path,required=True);ap.add_argument('--expect-plan-hash');a=ap.parse_args()
    try:
        if a.command=='prepare':value=prepare(a.work_dir)
        elif not a.expect_plan_hash:raise Blocked('source_control_external_pin_required')
        elif a.command=='recover':value=native.recover(a.work_dir,a.expect_plan_hash)
        else:value=run(a.work_dir,a.expect_plan_hash)
        print(json.dumps(value));return 0 if value.get('executionStatus','completed')=='completed' else 2
    except Exception:
        print(json.dumps({'gateDecision':'block','reasonCode':'source_control_entry_refused','productRequests':0}));return 2


if __name__=='__main__':raise SystemExit(main())
