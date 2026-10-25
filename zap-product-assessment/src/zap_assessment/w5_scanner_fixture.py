"""Owned W5 canary-only target + delegated boundary, controlled by private stdin.

No real product route, credentials, browser or arbitrary upstream is accepted.
Control is a UID-private Unix socket in tmpfs. Source canaries are generated in
this runtime; the host gets comparison hashes, never seed/password/token values.
ZAP receives only public fixture responses and nonsecret correlation metadata.
"""
import hashlib
import hmac
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import resource
import secrets
import html
import socket
import threading
import time
from urllib.parse import urlsplit,parse_qs

from .auth_lifecycle import ActorSession, AuthLost, ProducerStop
from .fixture import Fixture, Canary, ROOT
from .secret_audit import CanaryAuditor
from .traffic import CorrelatedGuard
from .opaque_canary import source_controls,PUBLIC_DB_CONTROL
from .credential_broker import BrokerBinding,GeneratedReference,CredentialBroker
from .errors import Blocked
from .private_source import TmpfsSourceZone
from .private_db import PrivateDbServer

BUILD = 'w5-delegated-synthetic/1.0'
LOCK = threading.RLock()
STATE = {'seed': None, 'actor': 'A', 'counter': 0, 'tokens': {}, 'roles': {'A':'member','B':'member'},
         'ttl': 600, 'rejectRefresh': False, 'session': None, 'case': 'uninitialized','source_zone':None,
         'private_db_server':None}
PRIVATE_SOURCE_ROOT=Path('/tmp/w5-private-source')


def source_status():
    """Metadata-only live tmpfs inventory; source values never enter control RPC."""
    config=json.loads((ROOT/'w5-binding.json').read_bytes())
    if config.get('sourceMode','generated')!='private-file':raise ValueError('private source mode required')
    names={p.name for p in PRIVATE_SOURCE_ROOT.parent.iterdir()}
    if not names<={'w5-control.sock',PRIVATE_SOURCE_ROOT.name}:raise ValueError('unproven private tmpfs path')
    zone=STATE['source_zone']
    return {'sourceMode':'private-file','sourceCreated':zone is not None,
            'sourceMetadata':zone.metadata() if zone is not None else None,
            'tmpfsPaths':sorted(names),'sourceValuesIncluded':False}


def derive(seed, label):
    return 'W5-canary-' + hmac.new(seed.encode(), label.encode(), hashlib.sha256).hexdigest()


def canaries():
    seed = STATE['seed']
    return ([seed]+[derive(seed, 'password-'+a) for a in ('A','B')] +
            [derive(seed, 'token-'+str(i)) for i in range(1, STATE['counter']+1)]) if seed else []


def record(name, value):
    from .safety_io import write_all
    data=(json.dumps({'caseId':STATE['case'],**value},separators=(',',':'))+'\n').encode()
    with LOCK:
        fd=os.open(ROOT/name,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
        try:write_all(fd,data);os.fsync(fd)
        finally:os.close(fd)


def issue(actor):
    if STATE['counter']>=64:raise ValueError('canary token inventory exhausted')
    STATE['counter'] += 1
    token=derive(STATE['seed'], 'token-'+str(STATE['counter']))
    STATE['tokens'][token]={'actor':actor,'expires':time.monotonic()+STATE['ttl'],'revoked':False}
    return token


class AuthTarget(Fixture):
    def reply(self,status,value):
        blob=json.dumps(value).encode();self.send_response_only(status)
        self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(blob)))
        self.end_headers();self.wfile.write(blob)

    def authenticated(self):
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        with LOCK:
            row=STATE['tokens'].get(token)
            valid=bool(row and not row['revoked'] and time.monotonic()<row['expires'])
            event='identity' if self.path=='/identity' else 'protected' if urlsplit(self.path).path=='/api/echo' else 'auth-control'
            record('auth-target.jsonl',{'event':event,'targetLogVersion':'1.1',
                                       'atMonotonic':time.monotonic(),'valid':valid,
                                       'subjectRef':row['actor'] if row else None,
                                       'requestId':self.headers.get('X-Zpa-Correlation'),
                                       'expiresAt':row['expires'] if row else None})
            return row if valid else None

    def do_GET(self):
        if self.path=='/identity':
            row=self.authenticated()
            return self.reply(200,{'subject':row['actor'],'role':STATE['roles'][row['actor']],
                                   'buildRef':BUILD}) if row else self.reply(401,{'authLost':True})
        if urlsplit(self.path).path=='/api/echo':
            row=self.authenticated()
            if not row:
                self.reply(401,{'authLost':True});return
        return super().do_GET()

    def do_POST(self):
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=4096:raise ValueError()
            value=json.loads(self.rfile.read(size)) if size else {}
            with LOCK:
                if self.path=='/login':
                    actor=value.get('actor')
                    valid=actor in ('A','B') and value.get('password')==derive(STATE['seed'],'password-'+str(actor))
                    record('auth-target.jsonl',{'event':'login','subjectRef':actor if actor in ('A','B') else None,
                                               'accepted':bool(valid),'atMonotonic':time.monotonic()})
                    return self.reply(200,{'accessToken':issue(actor)}) if valid else self.reply(401,{'error':'login'})
                row=self.authenticated()
                if not row:return self.reply(401,{'authLost':True})
                if self.path=='/refresh':
                    if STATE['rejectRefresh']:return self.reply(401,{'error':'refresh'})
                    row['revoked']=True;return self.reply(200,{'accessToken':issue(row['actor'])})
                if self.path=='/logout':
                    row['revoked']=True;return self.reply(200,{'loggedOut':True})
                return self.reply(404,{})
        except (ValueError,TypeError,KeyError):self.reply(400,{'error':'invalid'})


class Transport:
    def __init__(self, actor, bad_password=False):
        self.actor=actor;self.bad_password=bad_password;self.local=threading.local()

    def exchange(self,method,path,token=None,data=None,ident=None):
        c=http.client.HTTPConnection('127.0.0.1',18080,timeout=2)
        headers={'Host':'127.0.0.1:18080','Content-Type':'application/json','Connection':'close'}
        if token:headers['Authorization']='Bearer '+token
        if ident:headers['X-Zpa-Correlation']=ident
        try:
            c.request(method,path,None if data is None else json.dumps(data).encode(),headers)
            r=c.getresponse();body=r.read(1048577)
            if len(body)>1048576:raise ValueError('response budget')
            return {'status':r.status,'body':body.decode(),'headers':dict(r.getheaders()),
                    'contentType':r.getheader('Content-Type')}
        finally:c.close()

    def parsed(self,*args,**kwargs):
        r=self.exchange(*args,**kwargs)
        if r['status']!=200 or r['contentType']!='application/json':raise ValueError('auth contract')
        return json.loads(r['body'])

    def login(self):
        return self.parsed('POST','/login',data={'actor':self.actor,
            'password':'invalid-fixture-password' if self.bad_password else derive(STATE['seed'],'password-'+self.actor)})['accessToken']
    def identity(self,token):return self.parsed('GET','/identity',token)
    def refresh(self,token):return self.parsed('POST','/refresh',token)['accessToken']
    def logout(self,token):return self.parsed('POST','/logout',token)

    def protected(self,token,method,path,body):
        if method!='GET' or urlsplit(path).path!='/api/echo' or body is not None:raise ValueError('protected scope')
        handler,ident,req=self.local.boundary
        handler._record({'kind':'forward-intent','requestId':ident,'method':method,
                         'urlSha256':req['urlSha256'],'at':time.monotonic()})
        response=self.exchange(method,path,token,ident=ident)
        self.local.last=response
        return response


class Boundary(CorrelatedGuard):
    def forward(self,target,relative,ident,req):
        if urlsplit(relative).path!='/api/echo':return super().forward(target,relative,ident,req)
        candidate=STATE['session']
        if candidate is None:return 401,b'{"authLost":true}',[],False,'auth_not_ready'
        candidate.transport.local.boundary=(self,ident,req)
        try:
            response=candidate.protected('GET',relative)
            record('auth-wire.jsonl',{'requestId':ident,'actorRef':candidate.actor,'authEpoch':candidate.epoch,
                                     'atMonotonic':time.monotonic(),'credentialInjectedAtApprovedTarget':True})
            return response['status'],response['body'].encode(),list(response['headers'].items()),True,None
        except AuthLost:
            # An in-flight target401 is still target traffic. Preserve its
            # actual safe response rather than falsifying a guard-only denial.
            response=getattr(candidate.transport.local,'last',None)
            if response and response['status']==401 and CanaryAuditor(canaries()).response_safe(response):
                return response['status'],response['body'].encode(),list(response['headers'].items()),True,'target_auth_lost'
            return 401,b'{"authLost":true}',[],False,'auth_lost'
        finally:
            del candidate.transport.local.boundary
            if hasattr(candidate.transport.local,'last'):del candidate.transport.local.last


class _BrokerTransport(Transport):
    def login(self,credential):
        return self.parsed('POST','/login',data={'actor':credential['username'],
            'password':'invalid-fixture-password' if self.bad_password else credential['password']})['accessToken']


class _BrokerSession:
    """Holder-local compatibility seam; every protected call uses the broker."""
    def __init__(self,broker,binding,transport):
        self.broker=broker;self.binding=binding;self.transport=transport
    @property
    def actor(self):return self.binding.actor_ref
    @property
    def epoch(self):return self.snapshot()['authEpoch']
    def bootstrap(self):return self.broker.bootstrap(self.binding)
    def start_monitor(self):return self.broker.start_monitor(self.binding)
    def protected(self,method,path,body=None):
        try:return self.broker.protected(self.binding,method,path,body)
        except Blocked:
            raise AuthLost('broker_forwarding_refused') from None
    def refresh(self):return self.broker.refresh(self.binding)
    def logout(self):return self.broker.logout(self.binding)
    def cancel(self,reason):return self.broker.cancel(reason)
    def close(self):return self.broker.close()
    def snapshot(self):return self.broker.snapshot()


def make_session(actor,bad=False):
    def safe(response):return CanaryAuditor(canaries()).response_safe(response)
    # The boundary emits a durable stop intent. The host supervisor owns the
    # scanner operation IDs and must ACK terminal state separately.
    def stop():
        record('auth-stop.jsonl',{'event':'stop_requested','atMonotonic':time.monotonic()});return True
    def terminal():
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if (ROOT/('auth-stop-ack-'+STATE['case']+'.json')).exists():
                value=json.loads((ROOT/('auth-stop-ack-'+STATE['case']+'.json')).read_bytes())
                if value.get('caseId')==STATE['case'] and value.get('terminal') is True:return True
            time.sleep(.05)
        return False
    config=json.loads((ROOT/'w5-binding.json').read_bytes())
    def echo_oracle(response,method,path,body):
        query=parse_qs(urlsplit(path).query).get('q',[''])[0]
        return response['status']==200 and response['body']=='<html><body>'+html.escape(query)+'</body></html>'
    case=STATE['case']
    binding=BrokerBinding(config['runId'],config['planHash'],actor,actor,'member',BUILD,
                          'http://127.0.0.1:18080',time.time()+900)
    def current(bound):
        observed=json.loads((ROOT/'w5-binding.json').read_bytes())
        if config.get('sourceMode')=='private-file':source_status()
        return (observed==config and STATE['actor']==bound.actor_ref and STATE['case']==case)
    if config.get('sourceMode')=='private-file':
        source=STATE['source_zone'].reference(actor,lambda row:record('auth-reference.jsonl',row))
    else:
        source=GeneratedReference('w5-holder-generated:'+actor,actor,
            lambda:{'username':actor,'password':'invalid-fixture-password' if bad
                    else derive(STATE['seed'],'password-'+actor)})
    transport=_BrokerTransport(actor,bad)
    broker=CredentialBroker(binding=binding,source=source,adapter=transport,
        producer=ProducerStop(stop,terminal),record=lambda row:record('auth-journal.jsonl',row),
        check_current=current,forbidden_roots=[ROOT],operations=[('GET','/api/echo')],
        allow_refresh=True,poll_seconds=.5,response_safe=safe,response_content_type='text/html',
        response_oracle=echo_oracle)
    return _BrokerSession(broker,binding,transport)


def control(value):
    op=value.get('op');candidate=STATE['session']
    if op=='readiness':return {'credentialDelivered':STATE['seed'] is not None,'sessionCreated':candidate is not None}
    if op=='source-status':return source_status()
    if op=='auditor-bind':
        if STATE['seed'] is not None or candidate is not None:raise ValueError('source already bound')
        STATE['seed']=secrets.token_hex(32)
        private=[STATE['seed']]+[derive(STATE['seed'],'password-'+actor) for actor in ('A','B')]
        private += [derive(STATE['seed'],'token-'+str(i)) for i in range(1,65)]
        result=source_controls([*private,PUBLIC_DB_CONTROL])
        config=json.loads((ROOT/'w5-binding.json').read_bytes())
        if config.get('sourceMode')=='private-file':
            zone=TmpfsSourceZone(PRIVATE_SOURCE_ROOT,run_id=config['runId'],plan_hash=config['planHash'])
            zone.create({actor:{'username':actor,'password':derive(STATE['seed'],'password-'+actor)}
                         for actor in ('A','B')})
            STATE['source_zone']=zone
            result['sourceKind']='owned-guard-private-file-reference'
            if config.get('privateDbControls') is True:
                if config.get('actorRef') not in ('A','B'):raise ValueError('private database actor binding invalid')
                server=PrivateDbServer(run_id=config['runId'],plan_hash=config['planHash'],actor=config['actorRef'],
                    zone=zone,current_case=lambda:STATE['case'],
                    canaries=lambda:([STATE['seed']]+[derive(STATE['seed'],'password-'+a) for a in ('A','B')]
                        +[derive(STATE['seed'],'token-'+str(i)) for i in range(1,65)]+[PUBLIC_DB_CONTROL]),
                    record=lambda row:record('private-db-audit.jsonl',row))
                server.start();STATE['private_db_server']=server
        record('auth-source.jsonl',{'event':'source_bound','sourceKind':result['sourceKind'],
            'sourceValuesIncluded':False,'controls':result['controls'],
            'fingerprintsSha256':hashlib.sha256(json.dumps(result['fingerprints'],sort_keys=True,separators=(',',':')).encode()).hexdigest(),
            'runId':config['runId'],'planHash':config['planHash'],'atMonotonic':time.monotonic()})
        return result
    if op=='boot':
        if STATE['seed'] is None or 'seed' in value:raise ValueError('private source binding required')
        if candidate is not None:candidate.close()
        if value.get('actor') not in ('A','B'):raise ValueError('actor')
        STATE.update(actor=value['actor'],case=value['caseId'],ttl=value.get('ttl',600),rejectRefresh=False)
        STATE['roles']={'A':'member','B':'member'}
        candidate=make_session(value['actor'],value.get('badPassword',False));STATE['session']=candidate
        try:candidate.bootstrap();candidate.start_monitor()
        except AuthLost:pass
    elif op=='refresh':
        STATE['rejectRefresh']=value.get('reject',False)
        try:candidate.refresh()
        except AuthLost:pass
    elif op in ('revoke','role-change'):
        with LOCK:
            for row in STATE['tokens'].values():
                if row['actor']==STATE['actor']:
                    if op=='revoke':row['revoked']=True
                    else:STATE['roles'][STATE['actor']]='viewer'
            record('auth-target.jsonl',{'event':op,'atMonotonic':time.monotonic(),'actorRef':STATE['actor']})
    elif op=='logout':
        try:candidate.logout()
        except AuthLost:pass
    elif op in ('cancel','exception','restart','cleanup'):
        candidate.cancel(op)
    elif op=='state':pass
    else:raise ValueError('control scope')
    return {'session':STATE['session'].snapshot(),'mintedTokens':STATE['counter'],
            'coreLimit':list(resource.getrlimit(resource.RLIMIT_CORE)),
            'clockMonotonic':time.monotonic(),'clockId':'owned-linux-namespace'}


CONTROL_CLIENT = """import socket,json,sys
x=json.load(sys.stdin);s=socket.socket(socket.AF_UNIX);s.settimeout(8);s.connect('/tmp/w5-control.sock');s.sendall(json.dumps(x).encode());s.shutdown(socket.SHUT_WR);data=b''
while True:
 b=s.recv(65536)
 if not b:break
 data+=b
 if len(data)>65536:raise ValueError('control budget')
print(data.decode())
"""


def main():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    Boundary.minimum_interval=1/int((ROOT/'rate.txt').read_text())
    for port,handler in ((18080,AuthTarget),(18081,Canary),(18888,Boundary)):
        server=ThreadingHTTPServer(('127.0.0.1',port),handler)
        threading.Thread(target=server.serve_forever,daemon=True).start()
    listener=socket.socket(socket.AF_UNIX);listener.bind('/tmp/w5-control.sock');os.chmod('/tmp/w5-control.sock',0o600);listener.listen()
    while True:
        connection,_=listener.accept()
        with connection:
            try:
                data=b''
                while True:
                    chunk=connection.recv(65536)
                    if not chunk:break
                    data+=chunk
                    if len(data)>65536:raise ValueError()
                response=control(json.loads(data))
            except Exception:response={'blocked':True,'reason':'control_failed'}
            connection.sendall(json.dumps(response).encode())


if __name__=='__main__':main()
