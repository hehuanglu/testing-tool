"""Owned TLS-intercepting upstream broker. Only broker UID can reach the pinned FE.

ZAP -> CONNECT broker -> decrypt/policy -> verified TLS with canonical Host/SNI.
No product private key, system trust change, insecure TLS or credential stripping.
"""
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import socket
import ssl
import threading
import time
from urllib.parse import urlsplit,parse_qsl


def sha(b):return hashlib.sha256(b).hexdigest()

class Policy:
    def __init__(self,plan):
        self.plan=plan;self.origin=plan['selection']['origin'];self.count=0;self.latched=False
        self.lock=threading.Lock();self.last=0;self.terminal_case=None;self.campaign_counts={};self.campaign_app_counts={}
    def admit(self,method,url,headers,body,mode):
        with self.lock:
            self.count+=1
            if self.latched:return False,'identity-latched'
            if self.terminal_case is not None and self.terminal_case==mode.get('caseId'):return False,'after-identity-transition'
            if self.count>self.plan['limits']['maxRequests']:return False,'request-budget'
            u=urlsplit(url);base=urlsplit(self.origin)
            if (u.scheme,u.netloc)!=(base.scheme,base.netloc) or u.username or u.password or u.fragment:return False,'origin'
            h={k.lower():v for k,v in headers.items()}
            if h.get('host')!=base.netloc or 'upgrade' in h or 'transfer-encoding' in h:return False,'host-or-protocol'
            identity=any(h.get(k) for k in ('authorization','proxy-authorization','x-api-key','x-auth-token','x-access-token'))
            candidates=[r for r in self.plan['requestPolicies'] if method==r['method'] and re.fullmatch(r['pathRegex'],u.path)]
            if identity:
                if not mode.get('transition'):self.latched=True
                return False,'identity-transition' if mode.get('transition') else 'identity-outside-phase'
            if not candidates:return False,'path-method'
            for r in candidates:
                permissions=set(self.plan.get('authority',{}).get('permissions',[]))
                if 'authority' in self.plan:
                    if mode.get('campaignId') and 'active' not in permissions:return False,'active-permission'
                    if method not in ('GET','HEAD','OPTIONS') and not (r.get('effect')=='public-read-like' and r.get('effectProvenance')) and 'public-mutation' not in permissions:return False,'mutation-permission'
                if any(k not in r.get('queryKeys',[]) for k,v in parse_qsl(u.query,keep_blank_values=True)):continue
                if any(k.lower() in ('token','accesstoken','authorization','password') for k,v in parse_qsl(u.query,keep_blank_values=True)):continue
                cookies=h.get('cookie','')
                if cookies and any(part.split('=',1)[0].strip() not in r.get('anonymousCookies',[]) for part in cookies.split(';')):
                    if not mode.get('transition'):self.latched=True
                    return False,'cookie-identity'
                if len(body)>self.plan['limits']['maxBodyBytes']:return False,'request-body-budget'
                if body:
                    if not r.get('jsonFields') or 'application/json' not in h.get('content-type',''):continue
                    try:b=json.loads(body)
                    except ValueError:continue
                    if not isinstance(b,dict) or set(b)!=set(r['jsonFields']):continue
                    if any(v is not None and not isinstance(v,(str,int,float,bool)) for v in b.values()):continue
                    if any(k.lower() in ('token','accesstoken','authorization') for k in b):return False,'body-identity'
                    fixed=mode.get('fixedFields',{})
                    if any(b.get(k)!=v for k,v in fixed.items()):continue
                elif r.get('jsonFields'):continue
                if mode.get('campaignId'):
                    campaign=next((c for c in self.plan.get('campaigns',[]) if c['id']==mode['campaignId']),None)
                    if campaign and campaign.get('maxAppRequests') is not None:
                        count=self.campaign_app_counts.get(campaign['id'],0)
                        if count>=campaign['maxAppRequests']:return False,'campaign-app-budget'
                        self.campaign_app_counts[campaign['id']]=count+1
                if mode.get('campaignId') and h.get('x-zap-scan-id') and sha(body)!=mode.get('baselineHash'):
                    campaign=next((c for c in self.plan.get('campaigns',[]) if c['id']==mode['campaignId']),None)
                    if campaign:
                        count=self.campaign_counts.get(campaign['id'],0)
                        if count>=campaign['maxDelivered']:return False,'campaign-budget'
                        self.campaign_counts[campaign['id']]=count+1
                return True,'admitted'
            return False,'input-policy'

class Broker(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,plan,config,evidence,address=('127.0.0.1',18888),policy_factory=Policy):
        super().__init__(address,Handler)
        self.plan=plan;self.policy=policy_factory(plan);self.config=Path(config);self.evidence=Path(evidence);self.lock=threading.Lock();self.seq=0
        self.tls=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);self.tls.minimum_version=ssl.TLSVersion.TLSv1_2
        self.tls.load_cert_chain(str(self.config/'broker.crt'),str(self.config/'broker.key'))
        self.upstream=ssl.create_default_context(cafile=str(self.config/'upstream.crt'));self.upstream.minimum_version=ssl.TLSVersion.TLSv1_2
    def record(self,row):
        with self.lock:
            if 'sequence' not in row:
                self.seq+=1;row.update(sequence=self.seq,requestId=str(self.seq).zfill(6))
            row.update(at=time.time(),recordVersion='fe-broker/2.0')
            f=self.evidence/(str(row['sequence']).zfill(6)+'.json');pending=f.with_suffix('.pending')
            with pending.open('w') as stream:
                pending.chmod(0o600);stream.write(json.dumps(row)+'\n');stream.flush();os.fsync(stream.fileno())
            os.replace(pending,f)
            directory=os.open(self.evidence,os.O_RDONLY)
            try:os.fsync(directory)
            finally:os.close(directory)
            # Append-only lifecycle survives a controller crash as well as final-row updates.
            with (self.evidence/'request-events.jsonl').open('a') as stream:
                os.chmod(stream.name,0o600);stream.write(json.dumps(row)+'\n');stream.flush();os.fsync(stream.fileno())

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*args):pass
    def handle(self):
        try:super().handle()
        except (ConnectionResetError,BrokenPipeError,TimeoutError):pass
    def setup(self):
        super().setup();self.connection.settimeout(12)
    def finish(self):
        try:super().finish()
        finally:self.connection.close()
    def do_CONNECT(self):
        base=urlsplit(self.server.plan['selection']['origin'])
        if self.path!=base.netloc:
            mode=json.loads((self.server.config/'mode.json').read_bytes())
            self.server.record({'method':'CONNECT','url':self.path,'caseId':mode.get('caseId'),'forwarded':False,'reason':'connect-origin'});self.send_error(403);return
        self.send_response(200,'Connection Established');self.end_headers()
        try:
            self.connection=self.server.tls.wrap_socket(self.connection,server_side=True)
            self.rfile=self.connection.makefile('rb');self.wfile=self.connection.makefile('wb')
            self.close_connection=False
            while not self.close_connection:self.handle_one_request()
        except (OSError,ssl.SSLError):self.close_connection=True
    def process(self):
        s=self.server;p=s.plan;sel=p['selection'];base=urlsplit(sel['origin'])
        url=self.path if self.path.startswith(('https://','http://')) else sel['origin']+self.path
        row={'method':self.command,'url':url,'forwarded':False,'transportState':'not-sent','reason':'before-request-capture'}
        try:
            mode=json.loads((s.config/'mode.json').read_bytes())
            row.update(caseId=mode.get('caseId'),campaignId=mode.get('campaignId'),allocationId=p.get('runId'),ruleId=self.headers.get('X-ZAP-Scan-ID'))
            n=int(self.headers.get('Content-Length','0'))
            if n<0 or n>p['limits']['maxBodyBytes']:raise ValueError('body-budget')
            body=self.rfile.read(n)
            if len(body)!=n:raise ValueError('body-incomplete')
            mode=json.loads((s.config/'mode.json').read_bytes())
            ok,reason=s.policy.admit(self.command,url,self.headers,body,mode)
            if hasattr(s.policy,'request_facts'):row.update(s.policy.request_facts(self.command,url,self.headers,mode))
            if (s.config/'STOP').exists():ok=False;reason='stopped'
            row.update(requestBodySha256=sha(body),payloadChanged=bool(mode.get('baselineHash') and sha(body)!=mode['baselineHash']),reason=reason,identityPhase='transition' if mode.get('transition') else 'anonymous')
            if hasattr(s.policy,'request_facts'):row.update(s.policy.request_facts(self.command,url,self.headers,mode))
            if not ok:
                s.record(row);self.send_response(403);self.send_header('X-ZPA-Guard','blocked');self.send_header('Content-Length','0');self.send_header('Connection','close');self.end_headers();self.close_connection=True;return
            row.update(transportState='intent',reason='durable-intent');s.record(row)
            # Exact address/port inspected from pinned deployment; TLS verifies canonical DNS name and CA.
            sock=socket.create_connection((sel['binding']['address'],sel['targetPort']),timeout=10)
            try:
                tls=s.upstream.wrap_socket(sock,server_hostname=base.hostname)
                peer_sha=sha(tls.getpeercert(binary_form=True))
                if peer_sha!=sel['certificate']['derSha256']:raise ValueError('upstream-certificate-drift')
                with s.policy.lock:
                    pause=max(0,1/p['limits']['requestsPerSecond']-(time.monotonic()-s.policy.last))
                    if pause:threading.Event().wait(pause)
                    s.policy.last=time.monotonic()
                c=http.client.HTTPConnection(base.hostname,timeout=10);c.sock=tls
                headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','proxy-connection','host')};headers['Host']=base.netloc;headers['Connection']='close'
                # Persist BEFORE entering code that can send any upstream bytes. A crash here is uncertain, never replayable.
                row.update(transportState='sent',forwarded=None,reason='send-may-have-started',mutationReplay=False);s.record(row)
                c.request(self.command,urlsplit(url).path+('?' + urlsplit(url).query if urlsplit(url).query else ''),body or None,headers)
                r=c.getresponse()
                row.update(transportState='response-headers',status=r.status,responseHeaders=[(k,v) for k,v in r.getheaders() if k.lower() not in ('set-cookie','authorization')]);s.record(row)
                blob=r.read(p['limits']['maxBodyBytes']+1)
                if len(blob)>p['limits']['maxBodyBytes']:raise ValueError('response-budget')
                row.update(transportState='response-observed',forwarded=True,reason='app',status=r.status,responseBodySha256=sha(blob),upstreamSNI=base.hostname,upstreamHost=headers['Host'],upstreamCertificateSha256=peer_sha)
                if hasattr(s.policy,'observe_response'):
                    row.update(s.policy.observe_response(self.command,url,self.headers,body,r.status,r.getheaders(),blob,mode))
                elif r.status<300:
                    for pointer in next((rule.get('transitionResponsePointers',[]) for rule in p['requestPolicies'] if rule['method']==self.command and re.fullmatch(rule['pathRegex'],urlsplit(url).path)),[]):
                        try:
                            value=json.loads(blob)
                            for segment in pointer.strip('/').split('/'):value=value[segment]
                            if isinstance(value,str) and value:
                                row['identityTransitionResponse']=True
                                with s.policy.lock:
                                    if mode.get('transition'):s.policy.terminal_case=mode.get('caseId')
                                    else:s.policy.latched=True;row['unexpectedIdentityTransition']=True
                        except (ValueError,KeyError,TypeError):pass
                cookie_names=[v.split('=',1)[0] for k,v in r.getheaders() if k.lower()=='set-cookie']
                allowed={name for rule in p['requestPolicies'] if rule['method']==self.command and 'pathRegex' in rule and re.fullmatch(rule['pathRegex'],urlsplit(url).path) for name in rule.get('anonymousCookies',[])}
                if not hasattr(s.policy,'observe_response') and set(cookie_names)-allowed:
                    row['identityTransitionResponse']=True
                    with s.policy.lock:
                        if mode.get('transition'):s.policy.terminal_case=mode.get('caseId')
                        else:s.policy.latched=True;row['unexpectedIdentityTransition']=True
                s.record(row);self.send_response_only(r.status,r.reason)
                for k,v in r.getheaders():
                    if k.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(k,v)
                self.send_header('Content-Length',str(len(blob)));self.send_header('Connection','close');self.end_headers()
                if self.command!='HEAD':self.wfile.write(blob)
                c.close()
            finally:
                if 'tls' in locals():tls.close()
                sock.close()
        except Exception as e:
            if row.get('transportState')!='response-observed':
                uncertain=row.get('transportState') in ('sent','response-headers','unknown')
                row.update(transportState='unknown' if uncertain else 'not-sent',forwarded=None if uncertain else False,reason='transport-error',errorType=type(e).__name__)
                if uncertain and self.command not in ('GET','HEAD','OPTIONS'):
                    row.update(reconciliationRequired=True,retentionRequired=True,mutationReplay=False)
                    with s.policy.lock:s.policy.latched=True
                s.record(row)
            try:self.send_error(502)
            except OSError:pass
        self.close_connection=True
    do_GET=do_HEAD=do_POST=do_OPTIONS=do_PUT=do_PATCH=do_DELETE=process

if __name__=='__main__':
    import sys
    Broker(json.loads(Path(sys.argv[1]).read_bytes()),sys.argv[2],sys.argv[3]).serve_forever()
