"""Owned third-domain HTTP control, never an example/finalsource deployment substitute."""
import hashlib
import json
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
import secrets
import base64,time
import threading
from urllib.parse import urlsplit,parse_qs

class ArchiveControl:
    def __init__(self,host='127.0.0.1',port=0,seed=None,faults=None):
        self.members={};self.sessions={};self.documents={};self.requests=[];self.lock=threading.RLock()
        self.faults=faults or (seed or {}).get('faults',{});self.seed=seed;self.identity_probes=0
        if seed:
            self.members.update(seed.get('members',{}))
            self.documents.update(seed.get('documents',{}))
        control=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):self.dispatch()
            def do_POST(self):self.dispatch()
            def do_PATCH(self):self.dispatch()
            def do_DELETE(self):self.dispatch()
            def dispatch(self):
                path=urlsplit(self.path).path;query=parse_qs(urlsplit(self.path).query)
                with control.lock:
                    control.requests.append({'method':self.command,'path':path,'authenticated':bool(self.headers.get('Authorization'))})
                    actor=control.sessions.get(self.headers.get('Authorization','').removeprefix('Bearer '))
                    try:
                        raw=self.rfile.read(min(int(self.headers.get('Content-Length','0')),16384));body=json.loads(raw) if raw else None
                    except (ValueError,TypeError):return self.send(400,{'fault':'invalid-json'})
                    if path=='/members' and self.command=='POST':
                        if not isinstance(body,dict) or not body.get('handle') or not body.get('passphrase'):return self.send(422,{'fault':'required'})
                        key='reader-'+secrets.token_hex(6);control.members[body['handle']]={'key':key,'password':body['passphrase'],'role':'READER'}
                        return self.send(201,{'member':{'key':key}})
                    if path=='/sessions' and self.command=='POST':
                        m=control.members.get((body or {}).get('handle'))
                        if not m or m['password']!=(body or {}).get('passphrase'):return self.send(401,{'fault':'denied'})
                        token=control.issue_token(m) if (control.seed or {}).get('jwt') else secrets.token_urlsafe(24);control.sessions[token]=m['key'];return self.send(200,{'session':{'bearer':token}})
                    if path=='/echo' and self.command=='POST':return self.send(201,{'accepted':(body or {}).get('label')})
                    if not actor:return self.send(401,{'fault':'denied'})
                    member=next(m for m in control.members.values() if m['key']==actor)
                    if path=='/access':
                        control.identity_probes+=1
                        if control.faults.get('authLossAfter') and control.identity_probes>control.faults['authLossAfter']:return self.send(401,{'problem':{'key':'session-lost'}})
                        if member['role']!='CURATOR':return self.send(403,{'problem':{'key':'role-denied'}})
                        return self.send(200,{'gate':{'state':'present'}})
                    if path=='/principal':
                        if control.faults.get('authLoss'):return self.send(401,{'problem':{'detail':'expired'}})
                        return self.send(200,{'principal':{'key':control.faults.get('subject',actor),'tier':control.faults.get('role',member['role'])}})
                    if path=='/documents' and self.command=='POST':
                        key='doc-'+secrets.token_hex(6);doc={'key':key,'owner':actor,'title':(body or {}).get('title'),'phase':'live'};control.documents[key]=doc
                        return self.send(201,{'entry':doc.copy()})
                    if path=='/documents' and self.command=='GET':
                        try:index=int(query.get('index',['0'])[0]);limit=int(query.get('limit',['2'])[0])
                        except ValueError:return self.send(400,{'fault':'pagination'})
                        if index<0 or not 1<=limit<=100:return self.send(400,{'fault':'pagination'})
                        rows=[v.copy() for v in control.documents.values() if v['owner']==actor]
                        return self.send(200,{'entries':rows[index*limit:(index+1)*limit],'meta':{'index':index,'limit':limit,'count':len(rows)}})
                    sealing=self.command=='POST' and path.endswith('/seal')
                    key=(path[:-5] if sealing else path).removeprefix('/documents/');doc=control.documents.get(key)
                    if not doc:return self.send(404,{'fault':'missing'})
                    if doc['owner']!=actor:return self.send(403,{'fault':'denied'})
                    if sealing:
                        if body is not None:return self.send(422,{'fault':'no-body'})
                        if doc['phase']!='live':return self.send(409,{'fault':'invalid-phase'})
                        doc['phase']='sealed';return self.send(200,{'entry':doc.copy()})
                    if self.command=='GET':return self.send(200,{'entry':doc.copy()})
                    if self.command=='PATCH':
                        if not isinstance(body,dict) or set(body) not in ({'title'},{'title','reference'}) or body.get('reference',key)!=key or not isinstance(body['title'],str) or not 1<=len(body['title'])<=80:return self.send(422,{'problem':{'detail':'invalid title/reference'}})
                        doc['title']=body['title'];return self.send(200,{'entry':doc.copy()})
                    if self.command=='DELETE':doc['phase']='archived';return self.send(204,None)
                    return self.send(405,{'fault':'method'})
            def send(self,status,body):
                data=b'' if body is None else json.dumps(body).encode();self.send_response(status)
                if body is not None:self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        self.server=ThreadingHTTPServer((host,port),Handler);self.thread=None
    def issue_token(self,member):
        # Owned fixture issuer only. Production identity verification uses OpenSSL/Nimbus.
        config=self.seed['jwt'];now=int(time.time());encode=lambda b:base64.urlsafe_b64encode(b).decode().rstrip('=')
        payload={'iss':config['issuer'],'aud':[config['audience']],'sub':member['key'],'clearance':member['role'],'iat':now,'exp':now+600}
        wire=encode(b'{"alg":"RS256"}')+'.'+encode(json.dumps(payload,separators=(',',':')).encode())
        digest=bytes.fromhex('3031300d060960864801650304020105000420')+hashlib.sha256(wire.encode()).digest()
        n=int(config['n'],16);d=int(config['d'],16);size=(n.bit_length()+7)//8;encoded=b'\x00\x01'+b'\xff'*(size-len(digest)-3)+b'\x00'+digest
        signature=pow(int.from_bytes(encoded,'big'),d,n).to_bytes(size,'big');return wire+'.'+encode(signature)
    @property
    def origin(self):return 'http://127.0.0.1:'+str(self.server.server_port)
    def start(self):self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start();return self
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join(timeout=5)


def discovery(product,binding,scanner,direct):
    from .discovery import TRACKS
    source=Path(__file__).resolve();refs=['archive-source'];ops=[]
    rows=[('join','POST','/members',False),('login','POST','/sessions',False),('echo','POST','/echo',False),('identity','GET','/principal',True),
          ('list','GET','/documents',True),('create','POST','/documents',True),('read','GET','/documents/{key}',True),('rename','PATCH','/documents/{key}',True),('remove','DELETE','/documents/{key}',True),('seal','POST','/documents/{key}/seal',True),('access','GET','/access',True)]
    for oid,method,path,protected in rows:ops.append({'id':oid,'method':method,'pathTemplate':path,'protected':protected,'semantics':'owned archive control '+oid,
        'input':{'query':['index','limit'] if oid=='list' else []},'evidenceRefs':refs,'confidence':'high'})
    return {'schemaVersion':'product-discovery/1.1','product':{'location':str(Path(product).resolve()),'environment':'owned-archive-control','binding':binding,
        'environmentEvidenceRefs':['archive-runtime'],'origins':[{'url':url,'role':role,'authorized':True,'bindingVerified':True,'evidenceRefs':refs,
            'accessFrom':'scanner-network' if role=='scanner' else 'orchestrator-host','confidence':'high'} for role,urls in [('scanner',scanner),('direct',direct)] for url in urls]},
        'sources':[{'id':refs[0],'kind':'source','location':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'observedAt':'2026-10-21T00:00:00Z','confidence':'high'},{'id':'archive-runtime','kind':'runtime','location':'owned-runtime:'+str(binding['containerId']),'sha256':None,'observedAt':'2026-10-21T00:00:00Z','confidence':'high'}],
        'operations':ops,'auth':{'kind':'json-bearer','loginOperationId':'login','usernameField':'handle','passwordField':'passphrase','tokenPointer':'/session/bearer','headerName':'Authorization','headerPrefix':'Bearer ',
          'identity':{'operationId':'identity','subjectPointer':'/principal/key','actorSource':{'operationId':'join','subjectPointer':'/member/key'},'expectedStatus':200,'contentType':'application/json'},'credentialRef':'private:owned-control','evidenceRefs':refs,'confidence':'high'},
        'fixtures':[{'id':'owned-doc','operationIds':['create','rename','remove','seal'],'preparation':'fresh reader and document','ownership':'independent /member/key','postconditions':['exact title transition','archived record retained after 204','seal changes only live to sealed and rejects repeats'], 'evidenceRefs':refs,'confidence':'high'}],
        'tracks':{t:{'status':'not-applicable' if t.startswith('fe-') else 'candidate','reason':'owned backend control only','evidenceRefs':refs} for t in TRACKS},'ui':[],'conflicts':[],'gaps':[]}

def fixture_signing_key(directory):
    """Generate an isolated control issuer; never log the private numeric seed."""
    import subprocess,re
    root=Path(directory);root.mkdir(parents=True,mode=0o700,exist_ok=True);private=root/'issuer-private.pem';public=root/'issuer-public.pem'
    subprocess.run(['/usr/bin/openssl','genrsa','-out',str(private),'2048'],capture_output=True,check=True);private.chmod(0o600)
    subprocess.run(['/usr/bin/openssl','rsa','-in',str(private),'-pubout','-out',str(public)],capture_output=True,check=True);public.chmod(0o600)
    description=subprocess.run(['/usr/bin/openssl','rsa','-in',str(private),'-text','-noout'],capture_output=True,check=True).stdout.decode()
    def number(name):
        section=re.search(r'(?m)^'+name+r':\s*\n((?:\s+[0-9a-f:]+\n)+)',description)
        if not section:raise ValueError('fixture RSA generator format unsupported')
        return re.sub('[^0-9a-f]','',section[1])
    return {'issuer':'archive-controlled','audience':'archive-native','n':number('modulus'),'d':number('privateExponent')},public


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--host',default='127.0.0.1');p.add_argument('--port',type=int,default=18080);p.add_argument('--seed',type=Path);a=p.parse_args()
    ArchiveControl(a.host,a.port,json.loads(a.seed.read_text()) if a.seed else None).server.serve_forever()
