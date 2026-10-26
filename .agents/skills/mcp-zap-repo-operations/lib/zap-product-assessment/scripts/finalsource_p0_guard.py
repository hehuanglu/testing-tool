"""Run-local finalsource mirror and private API client. No Docker socket or DB access.

Only this UID may reach the borrowed frontend. The scanner reaches the mirror.
Native mode forwards exact fixture login; delegated mode holds real JWTs here,
accepts an actor-specific non-secret browser marker and injects at the last hop.
No automatic reauthentication: a real 401 latches authLost and removes the token.
"""
import http.client
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import re
import ssl
import sys
import threading
import time
from urllib.parse import urlsplit

READS = {'/api/health', '/docs-json', '/api/v1/accounts', '/api/v1/accounts/options',
         '/api/v1/categories/options', '/api/v1/transactions', '/api/v1/goals',
         '/api/v1/expenses/summary', '/api/v1/expenses/breakdown', '/api/v1/bills', '/api/v1/savings/summary'}
UI = {'/', '/login', '/register', '/accounts', '/accounts/new', '/transactions',
      '/transactions/new', '/expenses', '/bills', '/bills/new', '/goals', '/goals/new'}


class State:
    def __init__(self, config, *, lifecycle=None):
        self.c = config
        # W5 injection is an in-memory development seam, not a listener/mode
        # admission switch. It never opens the historical credential-copy file.
        if lifecycle is not None and (config['mode'] != 'delegated' or lifecycle.actor != config['actor']):
            raise ValueError('lifecycle actor/mode mismatch')
        self.lifecycle = lifecycle
        self.creds = {} if lifecycle is not None else json.loads(Path(config['credentials']).read_text())['actors']
        self.tokens = {}
        self.lost = False
        self.mode = config['mode']
        self.actor = config['actor']
        self.accounts = set(config.get('accounts', []))
        self.categories = config.get('categories', {})
        self.transactions = set()
        self.goals = set()
        self.mutations = []
        self.lock = threading.RLock()
        self.last = 0

    def record(self, row):
        with self.lock:
            with open('/evidence/guard.jsonl', 'a') as f:
                f.write(json.dumps({'at':time.time(), **row}, ensure_ascii=False)+'\n')

    def upstream(self, method, path, body=None, actor=None, token_override=None, headers=None):
        if time.time() > self.c['notAfter']:
            raise TimeoutError('authorization deadline')
        if not path.startswith('/') or path.startswith('//') or urlsplit(path).netloc:
            raise ValueError('relative path required')
        with self.lock:
            time.sleep(max(0, self.last + .5 - time.monotonic()))
            self.last = time.monotonic()
        h = {'Accept':'application/json', 'Connection':'close'}
        for k,v in (headers or {}).items():
            if k.lower() in {'accept','content-type','user-agent','origin','referer'}:
                h[k] = v
        token = token_override if token_override is not None else self.tokens.get(actor)
        if token:
            h['Authorization'] = 'Bearer ' + token
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            h['Content-Type'] = 'application/json'
        # Self-signed local test endpoint only; no host/system trust is modified.
        conn = http.client.HTTPSConnection(self.c['frontendAddress'], 8443, timeout=8,
                                           context=ssl._create_unverified_context())
        try:
            conn.request(method, path, data, h)
            r = conn.getresponse(); b = r.read(2_000_001)
            if len(b)>2_000_000:
                raise ValueError('response limit')
            try: text=b.decode();encoding='utf-8'
            except UnicodeDecodeError: text=base64.b64encode(b).decode();encoding='base64'
            result = {'status':r.status, 'headers':dict(r.getheaders()), 'body':text,'bodyEncoding':encoding}
            self.record({'source':'upstream','method':method,'path':path,'actor':actor or 'anonymous',
                         'status':r.status,'bytes':len(b),'credentialInjected':bool(token)})
            return result
        finally:
            conn.close()

    def login(self, actor):
        if self.lifecycle is not None:
            if actor != self.actor: raise ValueError('lifecycle actor mismatch')
            self.lifecycle.bootstrap()
            return self.lifecycle.snapshot()
        a = self.creds[actor]
        r = self.upstream('POST','/api/auth/login',{'email':a['email'],'password':a['password']})
        if r['status']!=200:
            raise ValueError('fixture login failed')
        d = json.loads(r['body'])['data']
        if d['user']['id'] != a['userId']:
            raise ValueError('login identity mismatch')
        self.tokens[actor] = d['accessToken']
        self.record({'source':'identity','actor':actor,'expectedId':a['userId'],
                     'observedId':d['user']['id'],'status':200})
        return {'actor':actor,'user':d['user'],'status':200}

    def control(self, x):
        op = x['op']
        if op=='login': return self.login(x['actor'])
        if self.lifecycle is not None:
            if op=='state': return self.lifecycle.snapshot()
            # Bypass/invalid-token/business controls require a separate adapter
            # contract; the candidate only exercises the existing mirror reads.
            raise ValueError('lifecycle control unsupported')
        if op=='state': return {'authLost':self.lost,'accounts':sorted(self.accounts),
                                'goals':sorted(self.goals),'transactions':sorted(self.transactions),'mutations':self.mutations}
        if op=='invalidate':
            self.tokens[self.actor]='intentionally-invalid-local-test-token'; return {'invalidated':True}
        if op!='request': raise ValueError('unknown control')
        method=x.get('method','GET');path=x['path'];p=urlsplit(path).path
        actor=x.get('actor');body=x.get('body')
        allowed = method=='GET' and (p in READS or re.fullmatch(r'/api/v1/accounts/\d+',p))
        if method=='POST' and p=='/api/v1/accounts':
            allowed = actor in ('A','B') and body.get('bank_name','').startswith(self.c['fixturePrefix'])
        if method=='POST' and p=='/api/v1/goals':
            allowed = actor in ('A','B') and body.get('goal_type')=='Saving' and body.get('category_id') is None
        if method=='POST' and p=='/api/v1/transactions':
            allowed=(body.get('accountId') in self.accounts and body.get('accountId') not in self.c.get('accounts',[])
                     and body.get('category_id') in self.categories.values()
                     and body.get('itemDescription','').startswith(self.c['fixturePrefix']))
        if method in ('PUT','DELETE') and re.fullmatch(r'/api/v1/accounts/\d+',p):
            allowed=int(p.rsplit('/',1)[1]) in self.accounts and int(p.rsplit('/',1)[1]) not in self.c.get('accounts',[])
        if method=='PUT' and re.fullmatch(r'/api/v1/goals/\d+',p):
            allowed=int(p.rsplit('/',1)[1]) in self.goals
        if not allowed: raise ValueError('control scope violation')
        r=self.upstream(method,path,body,actor,token_override=x.get('tokenOverride'))
        if method!='GET':
            row={'actor':actor,'method':method,'path':path,'status':r['status'],'body':body}
            self.mutations.append(row);self.record({'source':'mutation',**row})
            if method=='POST' and r['status']==201:
                d=json.loads(r['body'])['data']
                if p.endswith('/accounts'): self.accounts.add(d['account']['id'])
                elif p.endswith('/transactions'): self.transactions.add(d['transactionId'])
                else: self.goals.add(d['goal_id'])
        return r

    def mirror(self, method, path, headers, body):
        u=urlsplit(path);p=u.path
        if u.scheme or u.netloc or not p.startswith('/') or p.startswith('//'):
            return None
        isapi=p.startswith('/api/')
        if self.lifecycle is not None and not isapi:
            return None  # W5 candidate has no admitted UI/static transport.
        allowed=(method=='GET' and (p in READS or p in UI or re.fullmatch(r'/assets/[A-Za-z0-9_.-]+',p)
                  or re.fullmatch(r'/accounts/\d+',p) or re.fullmatch(r'/goals/\d+/edit',p)
                  or (re.fullmatch(r'/api/v1/accounts/\d+',p) and int(p.rsplit('/',1)[1]) in self.accounts)))
        actor=None;override=None
        if method=='POST' and p=='/api/auth/login' and self.mode=='native':
            a=self.creds[self.actor]
            allowed=body=={'email':a['email'],'password':a['password']}
        if not allowed: return None
        auth=headers.get('Authorization','')
        if self.mode=='delegated' and isapi:
            # Browser marker is a run-local capability, never a target credential.
            if auth and auth!='Bearer scan-marker-'+self.actor: return None
            actor=self.actor
            if self.lifecycle is not None:
                from zap_assessment.auth_lifecycle import AuthLost
                try:
                    response = self.lifecycle.protected(method, path, body)
                    return {'status':response['status'], 'headers':response.get('headers', {}),
                            'body':response['body']}
                except AuthLost:
                    self.lost = True
                    return {'status':401, 'headers':{'Content-Type':'application/json'},
                            'body':'{"authLost":true}'}
            if self.lost: return {'status':401,'headers':{'Content-Type':'application/json'},'body':'{"authLost":true}'}
        elif auth.startswith('Bearer ') and self.mode=='native':
            override=auth[7:]
        r=self.upstream(method,path,body,actor,override,headers)
        if self.mode=='delegated' and isapi and r['status']==401:
            self.lost=True;self.tokens.pop(self.actor,None)
            self.record({'source':'auth-loss','actor':self.actor,'path':path,'status':401,'latched':True})
        return r


def serve(config):
    # Standalone guard launch is also an admission boundary. In-memory State
    # fixtures remain available to unit tests; no listener or secret is opened.
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
    from zap_assessment.capabilities import require_p0_mode
    require_p0_mode(config.get('mode'))
    state=State(config)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def handle_one(self):
            try:
                n=int(self.headers.get('Content-Length','0'))
                if n>10000 or self.headers.get('Transfer-Encoding'): raise ValueError('body limit')
                b=self.rfile.read(n);body=json.loads(b) if b else None
                if self.server.server_port==18081:
                    if self.command!='POST' or self.path!='/control': raise ValueError('control endpoint')
                    result=state.control(body);r={'status':200,'body':json.dumps(result),'headers':{'Content-Type':'application/json'}}
                else:
                    if self.headers.get('Host')!='127.0.0.1:18080': raise ValueError('host override')
                    r=state.mirror(self.command,self.path,self.headers,body)
                    if r is None: raise ValueError('mirror scope')
                content=base64.b64decode(r['body']) if r.get('bodyEncoding')=='base64' else r['body'].encode()
                self.send_response_only(r['status'])
                for k,v in r['headers'].items():
                    if k.lower() not in {'connection','transfer-encoding','content-length','set-cookie'}: self.send_header(k,v)
                self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
            except Exception as e:
                state.record({'source':'denied','method':self.command,'path':self.path,'reason':str(e)})
                content=b'{"guardGenerated":true}'
                self.send_response_only(403);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content)
        do_GET=handle_one;do_POST=handle_one;do_PUT=handle_one;do_DELETE=handle_one;do_PATCH=handle_one
        do_HEAD=handle_one;do_OPTIONS=handle_one;do_CONNECT=handle_one
    threading.Thread(target=ThreadingHTTPServer(('127.0.0.1',18081),Handler).serve_forever,daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',18080),Handler).serve_forever()

if __name__=='__main__': serve(json.loads(Path(sys.argv[1]).read_text()))
