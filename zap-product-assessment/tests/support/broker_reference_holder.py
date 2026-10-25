"""Child-only private-file broker diagnostic. Accepts no target or credential.

All HTTP servers, private source material and auditor comparisons live in this
child. Stdout contains counts/booleans only; this is not platform/sink acceptance.
"""
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import resource
import secrets
import tempfile
import threading
import time

from zap_assessment.auth_lifecycle import AuthLost,ProducerStop
from zap_assessment.credential_broker import BrokerBinding,SourceReference,CredentialBroker,_PrivateAudit


def run():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    password=secrets.token_urlsafe(32);all_secrets=[password];tokens={};wire=[]
    class Target(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,value):
            data=json.dumps(value).encode();self.send_response(status)
            self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)))
            self.end_headers();self.wfile.write(data)
        def do_POST(self):
            if self.path not in ('/login','/refresh','/logout'):return self.reply(404,{})
            size=int(self.headers.get('Content-Length','0'))
            if not 0<=size<=16384:return self.reply(400,{})
            body=json.loads(self.rfile.read(size) or b'{}')
            if self.path=='/login':
                if body!={'username':'owned-A','password':password}:return self.reply(401,{})
                token=secrets.token_urlsafe(32);all_secrets.append(token)
                tokens[token]={'subject':'A','role':'member','expires':time.monotonic()+30,'revoked':False}
                wire.append({'event':'login','accepted':True});return self.reply(200,{'token':token})
            old=self.headers.get('Authorization','').removeprefix('Bearer ');row=tokens.get(old)
            if not row or row['revoked'] or time.monotonic()>=row['expires']:return self.reply(401,{})
            row['revoked']=True
            if self.path=='/logout':return self.reply(200,{'logout':True})
            new=secrets.token_urlsafe(32);all_secrets.append(new);tokens[new]={**row,'revoked':False}
            return self.reply(200,{'token':new})
        def do_GET(self):
            token=self.headers.get('Authorization','').removeprefix('Bearer ');row=tokens.get(token)
            valid=bool(row and not row['revoked'] and time.monotonic()<row['expires'])
            wire.append({'event':self.path,'accepted':valid})
            if not valid:return self.reply(401,{})
            if self.path=='/identity':return self.reply(200,{'subject':row['subject'],'role':row['role'],'buildRef':'child-build'})
            if self.path=='/read':return self.reply(200,{'amount':100})
            return self.reply(404,{})
    server=ThreadingHTTPServer(('127.0.0.1',0),Target);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    address='http://127.0.0.1:'+str(server.server_port)
    class Adapter:
        token=None
        def exchange(self,method,path,token=None,body=None):
            c=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=1)
            h={'Content-Type':'application/json'}
            if token:h['Authorization']='Bearer '+token
            try:
                c.request(method,path,None if body is None else json.dumps(body).encode(),h)
                r=c.getresponse();data=r.read(16385)
                if len(data)>16384:raise ValueError()
                return {'status':r.status,'body':data.decode(),'headers':dict(r.getheaders()),'contentType':r.getheader('Content-Type')}
            finally:c.close()
        def parsed(self,*args):
            r=self.exchange(*args)
            if r['status']!=200:raise ValueError()
            return json.loads(r['body'])
        def login(self,credential):self.token=self.parsed('POST','/login',None,credential)['token'];return self.token
        def identity(self,token):return self.parsed('GET','/identity',token)
        def protected(self,token,method,path,body):return self.exchange(method,path,token,body)
        def refresh(self,token):self.token=self.parsed('POST','/refresh',token)['token'];return self.token
        def logout(self,token):return self.parsed('POST','/logout',token)
    results=[];events=[];brokers=[]
    try:
        with tempfile.TemporaryDirectory(prefix='owned-broker-source-') as tmp:
            root=Path(tmp).resolve();source=root/'credential.json';source.write_text(json.dumps({'actorRef':'A','username':'owned-A','password':password}));source.chmod(0o600)
            for case in ('success','refresh','natural-expiry','revoke','role-change','logout','cancel','cleanup-audit'):
                adapter=Adapter();binding=BrokerBinding('child-'+case,'a'*64,'A','A','member','child-build',address,time.time()+60)
                b=CredentialBroker(binding=binding,source=SourceReference('private-file-A',source,'A'),adapter=adapter,
                    producer=ProducerStop(lambda:True,lambda:True),record=events.append,check_current=lambda _:True,
                    forbidden_roots=[root/'repository'],operations=[('GET','/read')],allow_refresh=True)
                brokers.append(b);b.bootstrap(binding);b.protected(binding,'GET','/read')
                row=tokens[adapter.token];count=sum(e['event']=='/read' for e in wire)
                if case=='refresh':
                    epoch=b.snapshot()['authEpoch'];b.refresh(binding)
                    if b.snapshot()['authEpoch']==epoch:raise AssertionError()
                    b.protected(binding,'GET','/read')
                elif case in ('natural-expiry','revoke','role-change','logout','cancel'):
                    if case=='natural-expiry':
                        row['expires']=time.monotonic()+.04;deadline=time.monotonic()+1
                        while time.monotonic()<row['expires']:
                            if time.monotonic()>deadline:raise AssertionError()
                            time.sleep(.005)
                    elif case=='revoke':row['revoked']=True
                    elif case=='role-change':row['role']='viewer'
                    elif case=='logout':b.logout(binding)
                    else:b.cancel()
                    try:b.protected(binding,'GET','/read')
                    except AuthLost:pass
                    else:raise AssertionError()
                    if count!=sum(e['event']=='/read' for e in wire):raise AssertionError()
                    b._session.await_stop()
                b.close()
                if not b.audit_bytes(binding,password.encode())['matched']:raise AssertionError()
                results.append({'caseId':case,'status':'pass'})
            public={'schemaVersion':'private-file-broker-child/1.0','cases':results,'wireEvents':wire,
                    'eventCount':len(events),'sourceValuesIncluded':False,'productRequests':0,
                    'platformAcceptance':False,'operationalAdmission':False}
            audit=_PrivateAudit()
            for value in all_secrets:audit.register(value)
            if audit.matches(json.dumps(public).encode()):raise AssertionError()
            for b in brokers:b.destroy()
            return public
    finally:
        for b in brokers:
            try:b.destroy()
            except Exception:pass
        server.shutdown();server.server_close();thread.join(2)


if __name__=='__main__':
    try:print(json.dumps(run()))
    except BaseException as exc:
        print(json.dumps({'status':'failed','reason':'holder_diagnostic_failed','errorType':type(exc).__name__}))
        raise SystemExit(2) from None
