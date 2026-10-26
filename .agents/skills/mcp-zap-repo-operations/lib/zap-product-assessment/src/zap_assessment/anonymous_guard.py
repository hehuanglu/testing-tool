"""Stdlib-only exact anonymous workload guard; also runnable in pinned boundary image."""
import hashlib
import http.client
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import threading
import time
from urllib.parse import urlsplit,parse_qsl,urljoin


def blob(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def identity(v):
    if isinstance(v,dict):return any(k.lower() in ('authorization','token','accesstoken','cookie','proxy-authorization') or identity(x) for k,x in v.items())
    if isinstance(v,list):return any(identity(x) for x in v)
    return isinstance(v,str) and bool(re.search(r'(?i)Bearer\s+|eyJ[\w-]+\.eyJ[\w-]+\.',v))


def redirect_response_allowed(plan,case,status,headers):
    """Observe one declared redirect response; never follow it or expand the route set."""
    if case['category']!='protocol-control' or case['method']!='GET' or status not in case['expected']['statuses']:return False
    locations=[value for key,value in headers if key.lower()=='location']
    if len(locations)!=1:return False
    raw=locations[0]
    if any(ch in raw for ch in ('\r','\n','\\')):return False
    source=plan['origin']+case['path'];target=urlsplit(urljoin(source,raw));base=urlsplit(plan['origin'])
    if target.scheme!=base.scheme or target.netloc!=base.netloc or target.username or target.password or target.fragment:return False
    path=target.path+('?' +target.query if target.query else '')
    return any(c['id']!=case['id'] and c['method']=='GET' and c['path']==path and c['category']=='documentation' for c in plan['cases'])


def path_scope(template,baseline):
    names=re.findall(r'\{([^{}]+)\}',template)
    if len(names)!=1:raise ValueError('one discovered path selector required')
    prefix,suffix=template.split('{'+names[0]+'}')
    if not baseline.startswith(prefix) or suffix and not baseline.endswith(suffix):raise ValueError('path baseline mismatch')
    selector=baseline[len(prefix):len(baseline)-len(suffix) if suffix else None]
    if not re.fullmatch(r'[0-9]+',selector):raise ValueError('numeric selector capability only')
    return {'prefix':prefix,'suffix':suffix,'baseline':selector,'parameter':names[0]}


def scoped_path(scope,path):
    from urllib.parse import unquote
    prefix,suffix=scope['prefix'],scope['suffix']
    if not path.startswith(prefix) or suffix and not path.endswith(suffix):return False
    value=unquote(path[len(prefix):len(path)-len(suffix) if suffix else None])
    if not value or any(ord(ch)<32 or ord(ch)>126 for ch in value) or any(ch in value for ch in ('/','\\',';','%','\x00','\r','\n')) or value in ('.','..'):return False
    # A foreign numeric ID is not an injection payload. No numeric coercion may
    # dispatch to another real object; nonnumeric values reach parser validation.
    return value.strip()==scope['baseline'] or re.fullmatch(r'[+-]?\d+',value.strip()) is None


PATH_GUARD_JS=r'''
function scopedPath(scope,path){
 if(path.indexOf(scope.prefix)!==0||(scope.suffix&&path.slice(-scope.suffix.length)!==scope.suffix))return false;
 let value;try{value=decodeURIComponent(path.slice(scope.prefix.length,scope.suffix?path.length-scope.suffix.length:path.length));}catch(e){return false;}
 if(!value||/[^\x20-\x7e]/.test(value)||/[\/\\;%\x00\r\n]/.test(value)||value==='.'||value==='..')return false;
 return value.trim()===scope.baseline||!/^[-+]?\d+$/.test(value.trim());
}
'''


def authorize(p,mode,method,url,headers,body,now):
    u=urlsplit(url);base=urlsplit(p['origin']);hdr={k.lower():v for k,v in headers.items()}
    if now>=p['notAfter']:raise ValueError('deadline')
    if u.scheme!=base.scheme or u.netloc!=base.netloc or u.username or u.password or u.fragment or hdr.get('host')!=base.netloc:
        raise ValueError('origin-host')
    if any(k in hdr for k in ('authorization','proxy-authorization','transfer-encoding')):raise ValueError('identity-or-framing')
    if any(k.lower() in ('authorization','token','accesstoken','cookie','password') for k,v in parse_qsl(u.query)) or identity(u.query):raise ValueError('identity-query')
    if 'cookie' in hdr:
        jar=SimpleCookie();jar.load(hdr['cookie'])
        if not jar or any(k not in p['anonymousState']['cookies'] or identity(v.value) for k,v in jar.items()):raise ValueError('identity-cookie')
    if len(body)>p['limits']['requestBytes']:raise ValueError('request-size')
    case=next((c for c in p['cases'] if c['id']==mode.get('caseId')),None)
    if not case or case['method']!=method:raise ValueError('method-path-query')
    campaign=next((c for c in p['campaigns'] if c['id']==mode.get('campaignId') and c['caseId']==case['id']),None)
    if campaign and campaign['vectors']==['path']:
        operation=next(o for o in p['discovery']['operations'] if o['id']==case['operationId'])
        scope=path_scope(operation['pathTemplate'],urlsplit(case['path']).path)
        if not scoped_path(scope,u.path) or u.query!=urlsplit(case['path']).query or body:raise ValueError('path-selector-scope')
        return case,campaign
    if urlsplit(case['path']).path!=u.path:raise ValueError('method-path-query')
    if campaign and campaign['vectors']==['query']:
        expected=parse_qsl(urlsplit(case['path']).query,keep_blank_values=True);actual=parse_qsl(u.query,keep_blank_values=True)
        if method!='GET' or body or len(actual)!=len(dict(actual)) or set(dict(actual))!=set(dict(expected)):raise ValueError('query-shape')
        if any(k not in campaign['mutableKeys'] and dict(actual)[k]!=v for k,v in expected):raise ValueError('frozen-query-field')
        return case,campaign
    if case['path']!=u.path+('?' +u.query if u.query else ''):raise ValueError('method-path-query')
    value=None
    if body:
        if hdr.get('content-type','').split(';')[0].lower()!='application/json':raise ValueError('content-type')
        try:value=json.loads(body)
        except ValueError:raise ValueError('json-body') from None
        if identity(value):raise ValueError('identity-body')
    if mode.get('campaignId'):
        camp=next((c for c in p['campaigns'] if c['id']==mode['campaignId'] and c['caseId']==case['id']),None)
        if not camp or not isinstance(value,dict) or set(value)!=set(case['body']):raise ValueError('campaign-body-shape')
        for k,v in case['body'].items():
            if k not in camp['mutableKeys'] and value[k]!=v:raise ValueError('frozen-body-field')
        return case,camp
    if value!=case['body']:raise ValueError('exact-case-body')
    return case,None


def serve(plan_path,mode_path,evidence_path,host='127.0.0.1',port=18888):
    plan_bytes=Path(plan_path).read_bytes();p=json.loads(plan_bytes);limit=p['limits'];base=urlsplit(p['origin'])
    out=Path(evidence_path);out.mkdir(parents=True,exist_ok=True)
    lock=threading.Lock();state={'forwarded':0,'mutations':0,'last':0,'artifactBytes':0,'sequence':0,'campaigns':{},'inFlight':0,'peakInFlight':0,'cases':{}}
    class Guard(BaseHTTPRequestHandler):
        protocol_version='HTTP/1.0'
        def log_message(self,*a):pass
        def record(self,action,**kw):
            row={'at':time.time(),'method':self.command,'url':self.path,'action':action,**kw}
            with (out/'proxy.jsonl').open('ab') as f:f.write(blob(row)+b'\n');f.flush();os.fsync(f.fileno())
        def accounting(self,started):
            temporary=out/'accounting.pending'
            temporary.write_bytes(blob({**state,'observedAt':time.time(),'requestSeconds':time.monotonic()-started}))
            os.replace(temporary,out/'accounting.json')
        def respond(self,status,data=b'',headers=(),where='guard'):
            self.send_response_only(status)
            for k,v in headers:
                if k.lower() not in ('connection','transfer-encoding','content-length','x-zpa-response-origin'):self.send_header(k,v)
            self.send_header('X-Zpa-Response-Origin',where);self.send_header('Content-Length',str(len(data)));self.end_headers()
            if self.command!='HEAD':self.wfile.write(data)
        def deny(self,reason):
            self.record('denied',reason=reason,guardGenerated=True,requestHeaders=dict(self.headers),requestBody=getattr(self,'capturedBody',None));self.respond(403)
        def handle_work(self):
            self.connection.settimeout(limit['requestTimeoutSeconds'])
            with lock:
                conn=None;timer=None;started=time.monotonic();seq=None
                try:
                    if Path(mode_path).with_name('STOP').exists():raise ValueError('stopped')
                    if hashlib.sha256(Path(plan_path).read_bytes()).digest()!=hashlib.sha256(plan_bytes).digest():raise ValueError('guard-plan-drift')
                    mode=json.loads(Path(mode_path).read_bytes())
                    size=int(self.headers.get('Content-Length','0'))
                    if size<0 or size>limit['requestBytes'] or len(self.headers.get_all('Content-Length',[]))>1:raise ValueError('request-size-framing')
                    body=self.rfile.read(size);self.capturedBody=body.decode('utf-8',errors='replace')
                    if len(body)!=size:raise ValueError('short-body')
                    c,camp=authorize(p,mode,self.command,self.path,dict(self.headers),body,time.time())
                    if state['forwarded']>=limit['maxForwarded'] or state['artifactBytes']>=limit['artifactBytes']:raise ValueError('total-budget')
                    mutation=self.command not in ('GET','HEAD','OPTIONS')
                    if mutation and state['mutations']>=limit['maxMutations']:raise ValueError('mutation-budget')
                    cid=camp['id'] if camp else c['id']
                    counts=state['campaigns'] if camp else state['cases'];cap=camp['maxForwarded'] if camp else 1
                    if counts.get(cid,0)>=cap:raise ValueError('campaign-budget' if camp else 'case-already-dispatched')
                    delay=state['last']+1/limit['requestsPerSecond']-time.monotonic()
                    if delay>0:time.sleep(delay)
                    if Path(mode_path).with_name('STOP').exists() or time.time()>=p['notAfter']:raise ValueError('stopped-or-expired')
                    counts[cid]=counts.get(cid,0)+1;state['forwarded']+=1;state['mutations']+=int(mutation)
                    state['sequence']+=1;seq=state['sequence'];state['inFlight']+=1;state['peakInFlight']=max(state['inFlight'],state['peakInFlight'])
                    filename=f'{seq:05d}.json'
                    request={'method':self.command,'url':self.path,'headers':dict(self.headers),'body':body.decode('utf-8'),'caseId':c['id'],'campaignId':camp['id'] if camp else None,'producer':mode.get('producer'),'nativeOperationId':mode.get('nativeOperationId'),'ruleId':self.headers.get('x-zap-scan-id'),'ruleAttribution':'native injected x-zap-scan-id header when present; background/seed unavailable'}
                    self.accounting(started)
                    (out/(filename+'.intent')).write_bytes(blob(request));self.record('dispatch-intent',sequence=seq,caseId=c['id'],campaignId=request['campaignId'],nativeOperationId=request['nativeOperationId'])
                    conn=http.client.HTTPConnection(p['targetBinding']['address'],base.port or 80,timeout=limit['requestTimeoutSeconds'])
                    hdr={k:v for k,v in self.headers.items() if k.lower() not in ('host','connection','proxy-connection','content-length','x-zpa-response-origin')};hdr.update(Host=base.netloc,Connection='close')
                    network_deadline=time.monotonic()+limit['requestTimeoutSeconds']
                    conn.connect();sock=conn.sock
                    remaining=network_deadline-time.monotonic()
                    if remaining<=0:raise TimeoutError('absolute request deadline')
                    sock.settimeout(remaining)
                    def abort():
                        try:sock.shutdown(socket.SHUT_RDWR)
                        except OSError:pass
                    timer=threading.Timer(remaining,abort);timer.daemon=True;timer.start()
                    u=urlsplit(self.path);conn.request(self.command,u.path+('?' +u.query if u.query else ''),body=body or None,headers=hdr);state['last']=time.monotonic()
                    r=conn.getresponse();data=r.read(limit['responseBytes']+1);rh=r.getheaders()
                    record={**request,'status':r.status,'responseHeaders':rh,'responseBody':data.decode('utf-8',errors='replace'),'responseBodySha256':hashlib.sha256(data).hexdigest(),'responseBytes':len(data),'guardGenerated':False}
                    raw=blob(record);state['artifactBytes']+=len(raw);(out/filename).write_bytes(raw)
                    if len(data)>limit['responseBytes']:raise ValueError('response-size')
                    if 300<=r.status<400 and not redirect_response_allowed(p,c,r.status,rh):
                        self.record('app-response-blocked',sequence=seq,status=r.status,reason='redirect',guardGenerated=True,evidence=filename);self.respond(403);return
                    safe=[];dropped=[]
                    for k,v in rh:
                        if k.lower()=='set-cookie':
                            jar=SimpleCookie();jar.load(v)
                            if not jar or any(n not in p['anonymousState']['cookies'] or identity(m.value) for n,m in jar.items()):dropped.append(k);continue
                        safe.append((k,v))
                    self.record('forwarded',sequence=seq,status=r.status,evidence=filename,caseId=c['id'],campaignId=request['campaignId'],nativeOperationId=request['nativeOperationId'],guardGenerated=False,responseBodySha256=record['responseBodySha256'],droppedIdentityResponseHeaders=dropped)
                    self.respond(r.status,data,safe,'app')
                except ValueError as exc:
                    self.deny(str(exc))
                except Exception as exc:
                    self.record('failed',sequence=seq,errorType=type(exc).__name__,guardGenerated=True)
                    try:self.respond(502)
                    except OSError:pass
                finally:
                    if seq is not None:state['inFlight']-=1
                    if timer:timer.cancel()
                    if conn:conn.close()
                    self.accounting(started)
        do_GET=handle_work;do_POST=handle_work;do_PUT=handle_work;do_PATCH=handle_work;do_DELETE=handle_work;do_OPTIONS=handle_work;do_HEAD=handle_work;do_CONNECT=handle_work
    server=ThreadingHTTPServer((host,port),Guard);server.daemon_threads=True;return server

if __name__=='__main__':
    import sys
    serve(*sys.argv[1:4]).serve_forever()
