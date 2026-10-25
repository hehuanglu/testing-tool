"""No-product owned Linux peer/source control. Values never cross Docker I/O."""
import argparse
from dataclasses import asdict
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json,os,secrets,socket,sys,threading,time
from pathlib import Path
from .auth_lifecycle import ProducerStop
from .credential_broker import BrokerBinding,CredentialBroker
from .errors import Blocked
from .private_db import strict_json,send
from .private_source_broker import (PrivateSourcePin,SourceGrant,PrivateSourceBroker,
                                    BrokeredReference,source_socket)

STATUS=Path('/tmp/source-broker-status.json')
BUILD='owned-source-broker/1.0'


def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()


def validate(config):
    if (not isinstance(config,dict) or set(config)!={'contract','runId','productInputAccepted','grants'}
            or config.get('contract')!='owned-source-control/1.0'
            or not str(config.get('runId','')).startswith('source-control-')
            or config.get('productInputAccepted') is not False or not isinstance(config.get('grants'),dict)
            or set(config['grants'])!={'A','B','lost','gated'}):
        raise Blocked('source_control_contract')
    for key,row in config['grants'].items():
        if not isinstance(row,dict) or set(row)!={'referenceId','binding','uid'}:
            raise Blocked('source_control_contract')
        binding=BrokerBinding(**row['binding'])
        actor='B' if key=='B' else 'A'
        if (binding.run_id!=config['runId'] or binding.origin!='http://127.0.0.1:18080'
                or binding.actor_ref!=actor or binding.subject!=('12' if actor=='B' else '11')
                or row['uid']!=(1004 if actor=='B' else 1003)):
            raise Blocked('source_control_scope')
    return config


def serve(config):
    private=Path('/tmp/source-private');private.mkdir(mode=0o700)
    source=private/'source.json';actors={a:{'email':a+'@owned-source.invalid','password':secrets.token_urlsafe(36),
        'registrationToken':secrets.token_urlsafe(48),'fullName':'Owned '+a,'userId':i} for a,i in [('A',11),('B',12)]}
    raw=canonical({'runId':'owned-origin-'+config['runId'],'origin':'http://127.0.0.1:18080','actors':actors})
    fd=os.open(source,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(raw)
    grants=[SourceGrant(r['referenceId'],BrokerBinding(**r['binding']),r['binding']['actor_ref'],r['uid'],r['uid'])
            for r in config['grants'].values()]
    events=[];tokens={};auth=[]
    broker=PrivateSourceBroker(run_id=config['runId'],grants=grants,source_pin=PrivateSourcePin.capture(source),
        source_run='owned-origin-'+config['runId'],source_origin='http://127.0.0.1:18080',
        expected_subjects={'A':11,'B':12},check_current=lambda b:b.build_ref==BUILD and b.expires_at>time.time(),
        record=events.append,forbidden_roots=['/package','/evidence'])
    def status():
        value={'contract':'owned-source-control/1.0','ready':True,'runId':config['runId'],'uid':os.getuid(),
            'sourceReads':broker.source_reads,'usedReferences':sorted(broker.used),'sourceMetadata':list(broker.pin.identity),
            'events':events,'authRequests':auth,'sourceValuesIncluded':False,'productRequests':0}
        raw=canonical(value)
        if broker.audit.matches(raw):raise Blocked('source_control_publication_failed')
        temp=STATUS.with_suffix('.pending');temp.write_bytes(raw);temp.chmod(0o600);temp.replace(STATUS)
    class Target(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,code,value):
            blob=canonical(value);self.send_response(code);self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(blob)));self.end_headers();self.wfile.write(blob)
        def do_POST(self):
            data=strict_json(self.rfile.read(min(16384,int(self.headers.get('Content-Length','0')))))
            actor=next((a for a,r in actors.items() if data=={'username':r['email'],'password':r['password']}),None)
            auth.append({'method':'POST','operation':'login','accepted':actor is not None,'actorRef':actor})
            if not actor:return self.reply(401,{'error':'denied'})
            token=secrets.token_urlsafe(48);tokens[token]=actor;broker.audit.register(token)
            self.reply(200,{'token':token})
        def do_GET(self):
            actor=tokens.get(self.headers.get('Authorization','').removeprefix('Bearer '))
            auth.append({'method':'GET','operation':'identity' if self.path=='/identity' else 'protected',
                         'accepted':actor is not None,'actorRef':actor})
            if not actor:return self.reply(401,{'error':'denied'})
            if self.path=='/identity':return self.reply(200,{'subject':str(actors[actor]['userId']),'role':None,'buildRef':BUILD})
            if self.path=='/protected':return self.reply(200,{'subject':str(actors[actor]['userId']),'owned':True})
            self.reply(404,{'error':'not-found'})
    target=ThreadingHTTPServer(('127.0.0.1',18080),Target)
    threading.Thread(target=target.serve_forever,daemon=True).start();broker.start()
    try:
        while True:status();time.sleep(.1)
    finally:broker.close();target.shutdown()


class Adapter:
    def __init__(self):self.last=0
    def exchange(self,method,path,body=None,token=None):
        time.sleep(max(0,.5-(time.monotonic()-self.last)));self.last=time.monotonic()
        conn=http.client.HTTPConnection('127.0.0.1',18080,timeout=3)
        try:
            headers={'Content-Type':'application/json'}
            if token:headers['Authorization']='Bearer '+token
            conn.request(method,path,canonical(body) if body is not None else None,headers)
            response=conn.getresponse();blob=response.read(65537)
            if len(blob)>65536:raise Blocked('source_control_response_budget')
            return {'status':response.status,'headers':{},'contentType':'application/json','body':blob.decode()}
        finally:conn.close()
    def login(self,credential):
        response=self.exchange('POST','/login',credential)
        if response['status']!=200:raise Blocked('source_control_login')
        return strict_json(response['body'])['token']
    def identity(self,token):return strict_json(self.exchange('GET','/identity',token=token)['body'])
    def protected(self,token,method,path,body):return self.exchange(method,path,body,token)


def client(config,key,mode):
    grant=config['grants'][key];binding=BrokerBinding(**grant['binding'])
    ref=BrokeredReference(grant['referenceId'],binding.actor_ref,binding,1006 if mode=='wrong-server' else 1005,1005)
    if mode=='lost-ack':
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as channel:
            channel.settimeout(3);channel.connect(source_socket(binding.run_id))
            send(channel,{'op':'resolve','referenceId':ref.reference_id,'binding':asdict(binding)})
        return {'status':'sent_without_readback','loginAttempted':False,'sourceValuesIncluded':False}
    if mode in ('resolve','wrong-server'):
        try:ref.resolve(actor_ref=binding.actor_ref,forbidden_roots=['/package'])
        except Blocked:return {'status':'denied','sourceValuesIncluded':False}
        return {'status':'resolved','sourceValuesIncluded':False}
    events=[];broker=CredentialBroker(binding=binding,source=ref,adapter=Adapter(),
        producer=ProducerStop(lambda:True,lambda:True),record=events.append,
        check_current=lambda b:b==binding and b.expires_at>time.time(),forbidden_roots=['/package'],
        operations=[('GET','/protected')])
    try:
        broker.bootstrap(binding);response=broker.protected(binding,'GET','/protected')
        accepted=response['status']==200 and strict_json(response['body'])=={'subject':binding.subject,'owned':True}
        broker.close();counts={}
        for event in events:counts[event['event']]=counts.get(event['event'],0)+1
        value={'status':'pass' if accepted else 'fail','actorRef':binding.actor_ref,
            'session':broker.snapshot(),'eventCounts':counts,'sourceValuesIncluded':False}
        if broker.audit_bytes(binding,canonical(value))['matched']:raise Blocked('source_control_publication_failed')
        return value
    finally:broker.destroy()


def main():
    os.umask(0o077);ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['server','client'])
    ap.add_argument('--grant',choices=['A','B','lost','gated'],default='A')
    ap.add_argument('--action',choices=['session','resolve','lost-ack','wrong-server'],default='session');args=ap.parse_args()
    try:
        raw=Path('/tmp/source-control-config.json').read_bytes() if args.mode=='server' else sys.stdin.buffer.read(16385)
        if len(raw)>16384:raise Blocked('source_control_input_budget')
        config=validate(strict_json(raw))
        if args.mode=='server':serve(config);return 0
        value=client(config,args.grant,args.action)
    except BaseException:
        value={'status':'blocked','reasonCode':'owned_source_control_failed','sourceValuesIncluded':False}
    print(json.dumps(value,separators=(',',':')))
    return 0 if value['status'] in ('pass','denied','sent_without_readback','resolved') else 2


if __name__=='__main__':raise SystemExit(main())
