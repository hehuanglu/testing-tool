#!/usr/bin/env python3
"""Create two dedicated users and one account through finalsource's test API.

Requires an explicit receipt authorizing fixture creation. It never changes the
borrowed target container, database, or existing users. No POST is retried.
Credentials are deliberately delivered in a separate private file for retesting.
"""
import argparse
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

WORKSPACE = Path('/Users/hahoangloc/Working/testing tool')
sys.path.insert(0, str(WORKSPACE/'zap-product-assessment/src'))
sys.dont_write_bytecode = True

WORKER = r'''
import http.client, ipaddress, json, sys, time
x=json.load(sys.stdin)
assert ipaddress.ip_address(x['address']).is_private
assert time.time()<x['notAfter']
assert (x['method'],x['path']) in [('GET','/api/health'),('POST','/api/auth/register'),('POST','/api/v1/accounts')]
assert x['method']=='POST' or not x.get('payload')
c=http.client.HTTPConnection(x['address'],3000,timeout=8)
headers={'Content-Type':'application/json','Connection':'close'}
if x.get('token'): headers['Authorization']='Bearer '+x['token']
body=json.dumps(x['payload']).encode() if x.get('payload') is not None else None
c.request(x['method'],x['path'],body=body,headers=headers)
r=c.getresponse();data=r.read(1048577)
assert len(data)<=1048576
assert not r.getheader('Location') and not r.getheader('Set-Cookie')
print(json.dumps({'status':r.status,'body':json.loads(data),'responseBytes':len(data)}))
c.close()
'''


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def write(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(canonical(value)+b'\n')


def docker(args, data=None, timeout=30):
    p = subprocess.run(['docker', *args], input=data, capture_output=True, timeout=timeout)
    if p.returncode:
        raise RuntimeError('Docker action failed; private diagnostic withheld')
    return p.stdout.decode().strip()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--run-bola', action='store_true')
    args = p.parse_args()
    receipt = json.loads(args.receipt.read_bytes())
    if receipt.get('environment') != 'finalsource-zap-test' or receipt.get('fixtureCreationAuthorized') is not True:
        raise ValueError('actual test fixture authorization required')
    if not receipt.get('userRequest') or not receipt.get('fixtureRequest') or not receipt.get('owner'):
        raise ValueError('authorization receipt needs the actual user requests and owner')
    out = args.output.resolve();out.mkdir(mode=0o700, parents=True, exist_ok=False)
    from zap_assessment.bola_borrowed import prepare_candidate, preflight
    from zap_assessment.bola import binding_readback, make_bola_plan, run_bola
    from zap_assessment.contracts import digest
    from zap_assessment.evidence import verify_bundle
    prepare_candidate('finalsource-zap-test-backend-1', 3000, out/'candidate')
    config = json.loads((out/'candidate/candidate.json').read_bytes())
    label = docker(['inspect', '--format', '{{index .Config.Labels "com.docker.compose.project"}}', config['binding']['containerId']])
    if label != 'finalsource-zap-test':
        raise ValueError('target is not the selected test project')
    binding_readback(config)
    run_id = 'pm-fixture-'+uuid.uuid4().hex[:16]
    expiry = time.time()+900
    name = 'zpa-'+run_id
    image = config['runtime']['imageId']
    intent = {'runId':run_id,'targetBinding':config['binding'],'receiptSha256':hashlib.sha256(args.receipt.read_bytes()).hexdigest(),
              'steps':['GET health','register A','register B','create one A-owned account'],
              'noAutomaticRetries':True,'noExistingDataModification':True,'retainedForRetesting':True}
    write(out/'intent.json',intent)
    credentials = {'runId':run_id,'origin':config['origin'],'actors':{}}
    for actor in ('A','B'):
        credentials['actors'][actor]={'email':run_id+'-'+actor.lower()+'@example.test',
            'password':'PmTest!'+secrets.token_urlsafe(24),'fullName':'PM Security Test '+actor+' '+run_id[-8:]}
    # Persist the generated inputs before any uncertain mutation ACK.
    write(out/'test-credentials-input.json',credentials)
    journal = []
    cid = None
    def event(kind, **data):
        row={'at':datetime.now(timezone.utc).isoformat(),'kind':kind,**data};journal.append(row)
        with (out/'fixture-journal.jsonl').open('ab') as f:f.write(canonical(row)+b'\n')
        (out/'fixture-journal.jsonl').chmod(0o600)
    def exchange(method,path,payload=None,token=None):
        binding_readback(config)
        if time.time()>=expiry:raise TimeoutError('fixture preparation expired')
        event('request-intent',method=method,path=path)
        job={'address':config['binding']['address'],'method':method,'path':path,'payload':payload,'token':token,'notAfter':expiry}
        result=json.loads(docker(['exec','-i','--user','1004:1004',name,'python','-c',WORKER],canonical(job),timeout=12))
        event('response',method=method,path=path,status=result['status'],responseBytes=result['responseBytes'])
        time.sleep(.55)
        return result
    result = {'executionStatus':'failed','fixtureCleanup':'retained-for-retest','clientCleanup':'pending'}
    try:
        event('client-create-intent',name=name,image=image)
        cid=docker(['create','--name',name,'--label','zpa.fixture.run='+run_id,'--network',config['binding']['networkId'],
            '--read-only','--cap-drop','ALL','--cap-add','NET_ADMIN','--security-opt','no-new-privileges',
            '--memory','128m','--cpus','1','--pids-limit','64',image,'sleep','1200'])
        docker(['start',name])
        event('client-created',containerId=cid)
        rules=[['iptables','-P','OUTPUT','DROP'],['iptables','-P','INPUT','DROP'],['iptables','-P','FORWARD','DROP'],
            ['iptables','-A','INPUT','-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','ACCEPT'],
            ['iptables','-A','OUTPUT','-p','tcp','-d',config['binding']['address'],'--dport','3000','-m','owner','--uid-owner','1004','-j','ACCEPT'],
            ['ip6tables','-P','OUTPUT','DROP'],['ip6tables','-P','INPUT','DROP'],['ip6tables','-P','FORWARD','DROP']]
        for rule in rules:docker(['exec',name,*rule])
        write(out/'client-boundary.json',{'containerId':cid,'image':image,'firewall':docker(['exec',name,'iptables-save']),
              'ipv6Firewall':docker(['exec',name,'ip6tables-save']),'workerSha256':hashlib.sha256(WORKER.encode()).hexdigest()})
        health=exchange('GET','/api/health')
        if health['status']!=200 or health['body'].get('data',{}).get('status')!='ok':raise ValueError('target health failed')
        for actor in ('A','B'):
            c=credentials['actors'][actor]
            response=exchange('POST','/api/auth/register',{'fullName':c['fullName'],'email':c['email'],'password':c['password'],'confirm Password':c['password']})
            data=response['body'].get('data',{});user=data.get('user',{})
            if response['status']!=201 or response['body'].get('success') is not True or user.get('email')!=c['email'] or type(user.get('id')) is not int or not data.get('token'):
                raise ValueError('registration did not confirm the dedicated actor; no replay')
            c.update(userId=user['id'],registrationToken=data['token'])
            write(out/('actor-'+actor+'-created.json'),{'actor':actor,'id':user['id'],'email':c['email'],'status':response['status']})
        if credentials['actors']['A']['userId']==credentials['actors']['B']['userId']:raise ValueError('actors not independent')
        account_input={'bank_name':'PM Security Fixture '+run_id[-8:],'account_type':'TEST',
            'branch_name':'Generated for authorized security retest','account_number_full':'9918'+''.join(str(secrets.randbelow(10)) for _ in range(12)),'balance':123.45}
        response=exchange('POST','/api/v1/accounts',account_input,credentials['actors']['A']['registrationToken'])
        account=response['body'].get('data',{}).get('account',{})
        if response['status']!=201 or type(account.get('id')) is not int or account.get('user_id')!=credentials['actors']['A']['userId']:
            raise ValueError('account creation/ownership unconfirmed; no replay')
        fixture={'createdByRun':run_id,'environment':'finalsource-zap-test','targetBinding':config['binding'],
            'accountId':account['id'],'ownerId':credentials['actors']['A']['userId'],'nonOwnerId':credentials['actors']['B']['userId'],
            'createdAccount':account,'creationStatus':201,'source':'actual register/create API responses',
            'retainedForRetesting':True,'cleanupActions':[],'userReceiptSha256':intent['receiptSha256']}
        write(out/'fixture-manifest.json',fixture)
        write(out/'test-credentials.json',credentials)
        config['environment']={'kind':'test','identity':'finalsource-zap-test','evidenceRef':str(args.receipt.resolve())}
        config['fixture']={k:fixture[k] for k in ('accountId','ownerId','nonOwnerId')}
        config['fixture']['provenanceRef']='sha256:'+digest(fixture)
        now=datetime.now(timezone.utc)
        authority=json.loads((out/'candidate/authority.template.json').read_bytes())
        authority.update(recordId=run_id+'-read',owner=receipt['owner'],issuer=receipt['owner'],
            approvalRef=str(args.receipt.resolve()),validFrom=(now-timedelta(seconds=5)).isoformat(),
            validUntil=(now+timedelta(hours=2)).isoformat(),configHash=digest(config),environmentIdentity='finalsource-zap-test')
        plan=make_bola_plan(config,authority)
        write(out/'bola-config.json',config);write(out/'bola-authority.json',authority)
        # Plan bytes use the upstream canonical serialization exactly.
        fd=os.open(out/'bola-plan.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,'wb') as f:f.write(plan.encoded)
        write(out/'bola-preflight.json',preflight(plan))
        result.update(executionStatus='completed',fixture=fixture,planHash=plan.hash)
        if args.run_bola:
            env={config['credentials'][a]['loginEnv']:json.dumps({k:credentials['actors'][a][k] for k in ('email','password')}) for a in ('A','B')}
            run=run_bola(plan,WORKSPACE/'zap-product-assessment/runs',plan.hash,environ=env)
            write(out/'bola-result.json',run)
            manifest=verify_bundle(run['bundle'])
            write(out/'bola-verification.json',{'verified':True,'bundle':run['bundle'],**{k:manifest[k] for k in ('executionStatus','evidenceStatus','securityVerdict','cleanupStatus','gateDecision')}})
            result['bola']=run
    except Exception as exc:
        result['errorType']=type(exc).__name__
        result['detail']='Preparation stopped. Inspect minimized journal and recorded created IDs; never retry an uncertain POST.'
        raise
    finally:
        matches=docker(['ps','-aq','--filter','label=zpa.fixture.run='+run_id])
        if matches:
            metadata=json.loads(docker(['inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"label":{{json (index .Config.Labels "zpa.fixture.run")}}}',name]))
            if metadata['label']==run_id and metadata['image']==image and (not cid or metadata['id']==cid):
                docker(['rm','-f',metadata['id']]);result['clientCleanup']='clean'
            else:result['clientCleanup']='ownership-mismatch'
        else:result['clientCleanup']='clean'
        result['targetAfter']=binding_readback(config)
        write(out/'result.json',result)
        print(json.dumps({'executionStatus':result['executionStatus'],'clientCleanup':result['clientCleanup'],'output':str(out),
                          'bola':result.get('bola',{}).get('securityVerdict')},ensure_ascii=False))


if __name__=='__main__':
    main()
