#!/usr/bin/env python3
"""Bounded auth controls plus one explicitly authorized weak-password test user."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import uuid

sys.path.insert(0,str(Path(__file__).parent))
from prepare_finalsource_fixture import docker,write,canonical,WORKSPACE
sys.path.insert(0,str(WORKSPACE/'zap-product-assessment/src'))
from zap_assessment.bola import binding_readback

WORKER=r'''
import http.client,json,sys,time
x=json.load(sys.stdin)
assert time.time()<x['notAfter']
assert x['method'] in ('GET','POST')
assert (x['method']=='POST' and x['path'] in ('/api/auth/register','/api/auth/login')) or (x['method']=='GET' and x['path'] in x['allowedGet'])
assert not x.get('headers',{}).get('Cookie')
c=http.client.HTTPConnection(x['address'],3000,timeout=6)
h={'Content-Type':'application/json','Connection':'close',**x.get('headers',{})}
b=json.dumps(x['payload']).encode() if x.get('payload') is not None else None
c.request(x['method'],x['path'],body=b,headers=h);r=c.getresponse();data=r.read(131073)
assert len(data)<=131072 and not r.getheader('Location')
print(json.dumps({'status':r.status,'body':json.loads(data),'headers':dict(r.getheaders()),'bytes':len(data)}));c.close()
'''


def sanitized(value):
    if isinstance(value,dict):return {k:('<redacted>' if k.lower() in ('password','confirm password','accesstoken','token','authorization') else sanitized(v)) for k,v in value.items()}
    if isinstance(value,list):return [sanitized(v) for v in value]
    return value


def login_failure_fingerprint(response):
    """Compare semantics, not the intentionally different response timestamps."""
    body=response['body']
    return {'status':response['status'],**{k:body.get(k) for k in ('success','statusCode','message','path')}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fixture',type=Path,required=True);p.add_argument('--receipt',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=json.loads(a.receipt.read_bytes())
    if r.get('environment')!='finalsource-zap-test' or r.get('fixtureCreationAuthorized') is not True:raise ValueError('test user creation authority missing')
    c=json.loads((a.fixture/'bola-config.json').read_bytes());binding_readback(c)
    creds=json.loads((a.fixture/'test-credentials.json').read_bytes())
    out=a.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    rid='auth-probe-'+uuid.uuid4().hex[:16];name='zpa-'+rid;cid=None;events=[];expires=time.time()+180
    actor=creds['actors']['A'];obj='/api/v1/accounts/'+str(c['fixture']['accountId'])
    weak={'email':rid+'@example.test','password':'a','fullName':'PM Weak Password Probe'}
    write(out/'test-credentials-input.json',weak)
    def exchange(label,method,path,payload=None,token=None):
        binding_readback(c)
        intent={'at':datetime.now(timezone.utc).isoformat(),'label':label,'method':method,'path':path,'payload':sanitized(payload),'authenticated':bool(token)}
        write(out/(label+'-request.json'),intent)
        job={'address':c['binding']['address'],'method':method,'path':path,'payload':payload,'headers':{'Authorization':'Bearer '+token} if token else {},'notAfter':expires,'allowedGet':[obj,'/api/v1/accounts/not-an-integer']}
        response=json.loads(docker(['exec','-i','--user','1004:1004',name,'python','-c',WORKER],canonical(job),timeout=10))
        write(out/(label+'-response.json'),sanitized(response))
        events.append({'label':label,'method':method,'path':path,'status':response['status']});time.sleep(.55);return response
    result={'executionStatus':'failed','createdTestUserRetained':False,'cleanupStatus':'pending'}
    try:
        write(out/'intent.json',{'runId':rid,'binding':c['binding'],'operations':['anonymous object GET','tampered JWT GET','invalid id GET','one weak test registration','weak test login','known/unknown wrong login controls'],'receiptSha256':hashlib.sha256(a.receipt.read_bytes()).hexdigest(),'noRetries':True})
        cid=docker(['create','--name',name,'--label','zpa.authprobe.run='+rid,'--network',c['binding']['networkId'],'--read-only','--cap-drop','ALL','--cap-add','NET_ADMIN','--security-opt','no-new-privileges','--memory','128m','--cpus','1',c['runtime']['imageId'],'sleep','300']);docker(['start',name])
        for rule in [['iptables','-P','OUTPUT','DROP'],['iptables','-P','INPUT','DROP'],['iptables','-P','FORWARD','DROP'],['iptables','-A','INPUT','-m','conntrack','--ctstate','ESTABLISHED,RELATED','-j','ACCEPT'],['iptables','-A','OUTPUT','-p','tcp','-d',c['binding']['address'],'--dport','3000','-m','owner','--uid-owner','1004','-j','ACCEPT'],['ip6tables','-P','OUTPUT','DROP'],['ip6tables','-P','INPUT','DROP']]:docker(['exec',name,*rule])
        write(out/'boundary.json',{'containerId':cid,'imageId':c['runtime']['imageId'],'workerSha256':hashlib.sha256(WORKER.encode()).hexdigest(),'firewall':docker(['exec',name,'iptables-save']),'ipv6Firewall':docker(['exec',name,'ip6tables-save'])})
        anon=exchange('01-anonymous','GET',obj)
        token=actor['registrationToken'];parts=token.split('.');parts[2]=('A' if parts[2][0]!='A' else 'B')+parts[2][1:]
        forged=exchange('02-tampered-jwt','GET',obj,token='.'.join(parts))
        badid=exchange('03-invalid-id','GET','/api/v1/accounts/not-an-integer',token=token)
        reg=exchange('04-weak-register','POST','/api/auth/register',{'fullName':weak['fullName'],'email':weak['email'],'password':'a','confirm Password':'a'})
        accepted=reg['status']==201 and reg['body'].get('success') is True
        login=None
        if accepted:
            weak.update(userId=reg['body']['data']['user']['id'],registrationToken=reg['body']['data']['token']);result['createdTestUserRetained']=True
            write(out/'test-credentials.json',weak)
            login=exchange('05-weak-login','POST','/api/auth/login',{'email':weak['email'],'password':'a'})
        known=exchange('06-known-wrong-login','POST','/api/auth/login',{'email':weak['email'],'password':'incorrect-probe-password'})
        unknown=exchange('07-unknown-wrong-login','POST','/api/auth/login',{'email':rid+'-absent@example.test','password':'incorrect-probe-password'})
        result.update(executionStatus='completed',observations=events,controls={'anonymousDenied':anon['status']==401,'tamperedSignatureDenied':forged['status']==401,
            'invalidIdRejected':badid['status']==400,'loginFailureMessagesEqual':known['status']==unknown['status']==401 and login_failure_fingerprint(known)==login_failure_fingerprint(unknown)},
            weakPassword={'passwordLength':1,'registrationAccepted':accepted,'loginAccepted':bool(login and login['status']==200),'createdUserId':weak.get('userId'),'classification':'confirmed acceptance behavior; security policy finding requires PM triage'})
    finally:
        exists=docker(['ps','-aq','--filter','label=zpa.authprobe.run='+rid])
        if exists:
            m=json.loads(docker(['inspect','--format','{"id":{{json .Id}},"label":{{json (index .Config.Labels "zpa.authprobe.run")}},"image":{{json .Image}}}',name]))
            if m['label']!=rid or m['image']!=c['runtime']['imageId'] or cid and m['id']!=cid:raise ValueError('auth probe cleanup ownership mismatch')
            docker(['rm','-f',m['id']])
        result['cleanupStatus']='clean';result['targetAfter']=binding_readback(c)
        write(out/'result.json',result)
        print(json.dumps({'output':str(out),'executionStatus':result['executionStatus'],'weakPassword':result.get('weakPassword'),'controls':result.get('controls'),'cleanupStatus':result['cleanupStatus']},ensure_ascii=False))


if __name__=='__main__':main()
