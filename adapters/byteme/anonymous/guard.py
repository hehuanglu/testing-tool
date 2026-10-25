"""ByteMe-only anonymous origin/method guard and fresh registration fixture adapter."""
import collections, http.client, json, os, re, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qsl, unquote
try:
    from result_readers import read_jsonl
except ImportError:
    from zap_assessment.result_readers import read_jsonl

def serve(root):
    root=Path(root); cfg=json.loads((root/'private.json').read_text()); origin=cfg['origin']; base=urlsplit(origin)
    previous=read_jsonl(root/'traffic.jsonl') if (root/'traffic.jsonl').exists() else []
    lock=threading.Lock(); seq=max((r.get('sequence',0) for r in previous),default=0)
    logins=[r['at'] for r in previous if r.get('path')=='/api/auth/token' and r.get('method')=='POST' and time.time()-r['at']<905]
    email_counts=collections.Counter()
    for row in previous:
        if row.get('path')!='/api/auth/token' or not row.get('actualBody'):continue
        try:value=json.loads(row['actualBody'])
        except ValueError:continue  # Malformed JSON is an intentional parser control.
        if isinstance(value,dict):email_counts[value.get('email')]+=1
    prior=next((r for r in reversed(previous) if r.get('kind')=='fixture-register' and r.get('status')==201),None)
    current={'email':prior['email'],'password':cfg['password']} if prior else None
    def record(row):
        with (root/'traffic.jsonl').open('a') as f: f.write(json.dumps(row,ensure_ascii=False)+'\n')
    def credentials(n):
        return {'fullName':'ByteMe clean assessment','email':f"zap{cfg['tag']}{n}@example.test",'phone':'09'+str(int(cfg['tag'],16)*10000+n)[-8:].zfill(8),'password':cfg['password'],'confirmPassword':cfg['password']}
    def forward(method,path,data,headers):
        c=http.client.HTTPConnection(cfg['address'],base.port,timeout=12)
        try:
            c.request(method,path,body=data,headers=headers);r=c.getresponse();body=r.read(4000001)
            if len(body)>4000000:raise ValueError('response-size')
            return r.status, r.getheaders(),body
        finally:c.close()
    class Guard(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def respond(self,status,headers,body):
            self.send_response_only(status)
            for k,v in headers:
                if k.lower() not in ('connection','transfer-encoding','content-length','set-cookie'):self.send_header(k,v)
            self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def work(self):
            nonlocal seq,current
            with lock:
                try:
                    if (root/'STOP').exists():raise ValueError('stopped')
                    mode=json.loads((root/'mode.json').read_text());u=urlsplit(self.path)
                    if u.scheme!='http' or u.netloc!=base.netloc or self.headers.get('Host')!=base.netloc:raise ValueError('origin')
                    if any(self.headers.get(k) for k in ('Authorization','Cookie','Proxy-Authorization','Transfer-Encoding')):raise ValueError('identity-framing')
                    if self.command!=mode['method']:raise ValueError('method')
                    if mode.get('vector')=='path':
                        value=unquote(u.path.removeprefix('/api/foods/'))
                        if not u.path.startswith('/api/foods/') or any(c in value for c in ('/','\\','\r','\n')):raise ValueError('path')
                    elif u.path!=mode['path']:raise ValueError('path')
                    if self.command=='GET' and any(k not in mode.get('queryKeys',[]) for k,v in parse_qsl(u.query)):raise ValueError('query')
                    size=int(self.headers.get('Content-Length','0'))
                    if not 0<=size<=32768:raise ValueError('request-size')
                    raw=self.rfile.read(size); original=raw.decode('utf-8');body=None
                    if raw:
                        try:body=json.loads(raw)
                        except ValueError:
                            if not mode.get('rawControl'):raise ValueError('json-shape')
                    if mode.get('field'):
                        if not isinstance(body,dict) or set(body)!={mode['field']}:raise ValueError('field-shape')
                    st=os.statvfs(root)
                    if st.f_bavail*st.f_frsize<2*1024**3:raise ValueError('disk-reserve')
                    seq+=1
                    if seq>5000:raise ValueError('request-budget')
                    headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','proxy-connection','host','content-length')}
                    headers.update({'Host':base.netloc,'Connection':'close'})
                    if u.path=='/api/auth/register' and self.command=='POST' and mode.get('adapt'):
                        fixture=credentials(seq)
                        if mode.get('field'):
                            field=mode['field']; fixture[field]=body[field]
                            if field in ('email','phone') and body[field]==mode['baseline']:fixture[field]=credentials(seq)[field]
                            if field=='password':fixture['confirmPassword']=body[field]
                            if field=='confirmPassword':fixture['password']=body[field]
                        else:fixture.update(body)
                        body=fixture;raw=json.dumps(body,ensure_ascii=False).encode()
                    if u.path=='/api/auth/token' and self.command=='POST':
                        now=time.time();logins[:]=[t for t in logins if now-t<905]
                        if len(logins)>=90:
                            record({'kind':'rate-wait','at':now,'seconds':max(1,906-(now-logins[0]))})
                            time.sleep(max(1,906-(now-logins[0])))
                        if mode.get('adapt'):
                            if current is None or email_counts[current['email']]>=7:
                                current=credentials(seq+5000)
                                code,_,rb=forward('POST','/api/auth/register',json.dumps(current).encode(),{'Host':base.netloc,'Content-Type':'application/json','Connection':'close'})
                                record({'kind':'fixture-register','at':time.time(),'status':code,'response':rb.decode(),'email':current['email']})
                                if code!=201:raise ValueError('login-fixture-create')
                            field=mode['field'];body={k:current[k] for k in ('email','password')};body[field]=json.loads(original)[field]
                            # Unchanged native baseline means the fresh positive control.
                            if body[field]==mode['baseline']:body[field]=current[field]
                            raw=json.dumps(body).encode()
                        email_counts[(body or {}).get('email','')]+=1;logins.append(time.time())
                    path=u.path+('?' + u.query if u.query else '')
                    time.sleep(.5)
                    status,rh,rb=forward(self.command,path,raw or None,headers)
                    record({'kind':'traffic','sequence':seq,'at':time.time(),'campaign':mode['id'],'technique':mode.get('technique','seed'),'field':mode.get('field'),'method':self.command,'path':path,'nativeBody':original,'actualBody':raw.decode() if raw else None,'status':status,'responseHeaders':rh,'response':rb.decode(errors='replace'),'ruleId':self.headers.get('X-ZAP-Scan-ID'),'userAgent':self.headers.get('User-Agent')})
                    self.respond(status,rh,rb)
                except Exception as e:
                    record({'kind':'guard-error','at':time.time(),'reason':str(e),'method':self.command,'url':self.path})
                    self.respond(403,[],b'')
        do_GET=work;do_POST=work;do_PUT=work;do_DELETE=work;do_HEAD=work;do_OPTIONS=work;do_PATCH=work
    return ThreadingHTTPServer(('127.0.0.1',18888),Guard)
if __name__=='__main__':
    import sys
    serve(sys.argv[1]).serve_forever()
