"""Independent hash correlation of sender, boundary and fixture-arrival records.

Only the declared anonymous method/path/query route is supported. Header/body
fuzzing and active rule acceptance remain blocked for this integration.
"""
import hashlib,json,os,stat
import time
from pathlib import Path
class TrafficInvalid(ValueError):pass
Blocked=TrafficInvalid

def sha(b):return hashlib.sha256(b).hexdigest()
def read_rows(path):
    path=Path(path)
    if not path.exists():return []
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as f:
        s=os.fstat(f.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_nlink!=1 or s.st_size>16*1024*1024:raise Blocked('traffic log budget/type')
        raw=f.read(16*1024*1024+1)
    if not raw:return []
    if not raw.endswith(b'\n'):raise Blocked('traffic log partial record')
    def unique(pairs):
        value={}
        for k,v in pairs:
            if k in value:raise Blocked('duplicate traffic key')
            value[k]=v
        return value
    try:rows=[json.loads(line,object_pairs_hook=unique) for line in raw.split(b'\n')[:-1]]
    except (ValueError,UnicodeError) as e:raise Blocked('traffic log malformed') from e
    if any(not isinstance(r,dict) for r in rows):raise Blocked('traffic record object required')
    return rows

def correlate(sender,boundary,target,*,terminal=False):
    requests={};responses={};failures={};denials={};arrivals={};guards={};intents={};out=[];unsupported=[]
    for row in sender:
        if row.get('kind') not in ('request','response','transport-failure'):raise Blocked('sender event unknown')
        store={'request':requests,'response':responses,'transport-failure':failures}[row['kind']]
        ident=row.get('requestId')
        if not isinstance(ident,str) or not ident or ident in store:raise Blocked('sender duplicate or absent id')
        store[ident]=row
    for row in boundary:
        if row.get('kind')=='uncorrelated-denial':raise Blocked('boundary missing sender correlation')
        if row.get('kind')=='transport-denial':
            ident=row.get('requestId')
            if not isinstance(ident,str) or not ident or ident in denials:raise Blocked('transport denial missing/duplicate id')
            denials[ident]=row;continue
        if row.get('kind')=='forward-intent':
            ident=row.get('requestId')
            if not isinstance(ident,str) or not ident or ident in intents:raise Blocked('forward intent missing/duplicate id')
            intents[ident]=row
            continue
        if row.get('kind')!='boundary':continue
        ident=row.get('requestId')
        if not isinstance(ident,str) or not ident or ident in guards:raise Blocked('boundary id missing/duplicate')
        guards[ident]=row
    for row in target:
        if row.get('kind')!='arrival':continue
        ident=row.get('requestId')
        if not isinstance(ident,str) or ident in arrivals:raise Blocked('target id missing/duplicate')
        arrivals[ident]=row
    if (set(arrivals)|set(guards)|set(responses)|set(intents)|set(failures)|set(denials))-set(requests):raise Blocked('uncorrelated target/boundary/sender')
    if set(failures)&set(responses):raise Blocked('conflicting sender terminal results')
    if set(denials)&(set(guards)|set(intents)|set(arrivals)):raise Blocked('transport denial has HTTP forwarding evidence')
    # Target writes its arrival before the boundary can persist its response.
    # Such a prefix is pending only with a matching durable forwarding intent.
    for ident in set(arrivals)-set(guards):
        a=arrivals[ident];req=requests[ident];intent=intents.get(ident)
        if intent is None or any(intent.get(k)!=req.get(k) for k in ('method','urlSha256')) or any(a.get(k)!=req.get(k) for k in ('method','urlSha256','bodySha256')):raise Blocked('arrival without matching forward intent')
    pending=[]
    for ident,req in requests.items():
        if ident in denials or ident in failures:
            d=denials.get(ident);f=failures.get(ident)
            if d is None or f is None:pending.append(ident);continue
            if (req.get('scheme')!='https' or not isinstance(req.get('authoritySha256'),str) or len(req['authoritySha256'])!=64
                    or d.get('authoritySha256')!=req['authoritySha256'] or d.get('method')!='CONNECT'
                    or d.get('status')!=403 or d.get('forwarded') is not False or d.get('reasonCode')!='unsupported_https_connect'
                    or f.get('failureKind')!='io' or not isinstance(f.get('exceptionType'),str) or not f['exceptionType']):
                raise Blocked('transport denial correlation mismatch')
            unsupported.append({'requestId':ident,'disposition':'unsupported_https_connect','correlationScope':'CONNECT authority only; no TLS application response'})
            producer=('active-control' if req.get('initiator')==2 and req.get('activeControl') is True and req.get('ruleId') is None else {2:'active',3:'crawl',6:'manual',7:'background'}.get(req.get('initiator'),'unknown'))
            out.append({'requestId':ident,'producer':producer,'ruleId':req.get('ruleId') if producer=='active' else None,
                        'forwarded':False,'boundaryCorrelated':True,'targetAllowed':False,'credentialForwarded':False,
                        'unsupportedVectors':['https-transport']})
            continue
        g=guards.get(ident);response=responses.get(ident)
        if g is None or response is None:
            pending.append(ident);continue
        for key in ('method','urlSha256','bodySha256','initiator','ruleId'):
            if req.get(key)!=g.get(key):raise Blocked('boundary request correlation mismatch')
        if response.get('status')!=g.get('status') or response.get('bodySha256')!=g.get('responseBodySha256'):raise Blocked('boundary response mismatch')
        forwarded=g.get('forwarded')
        if type(forwarded) is not bool:raise Blocked('forward disposition missing')
        if forwarded:
            intent=intents.get(ident)
            if intent is None or any(intent.get(k)!=req.get(k) for k in ('method','urlSha256')):raise Blocked('forwarded request lacks durable intent')
            a=arrivals.get(ident)
            if a is None:raise Blocked('forwarded request missing independent arrival')
            for key in ('method','urlSha256','bodySha256','status','responseBodySha256'):
                if a.get(key)!=g.get(key):raise Blocked('target-arrival correlation mismatch')
        elif ident in arrivals:raise Blocked('denied request reached target')
        initiator=req.get('initiator')
        # These are engine-captured initiators, not controller phase guesses.
        producer=('active-control' if initiator==2 and req.get('activeControl') is True and req.get('ruleId') is None else {2:'active',3:'crawl',6:'manual',7:'background'}.get(initiator,'unknown'))
        rule=req.get('ruleId') if initiator==2 else None
        out.append({'requestId':ident,'producer':producer,'ruleId':rule,'forwarded':forwarded,
                    'boundaryCorrelated':True,'targetAllowed':g.get('targetAllowed') is True,
                    'credentialForwarded':g.get('credentialForwarded') is not False,
                    'unsupportedVectors':g.get('unsupportedVectors',[])})
    for event in out:
        req=requests[event['requestId']]
        if 'phase' in req:event['phase']=req['phase']
    if terminal and pending:raise Blocked('terminal traffic capture incomplete')
    if terminal and (set(guards)|set(denials))!=set(requests):raise Blocked('traffic lifecycle count mismatch')
    if terminal:
        if set(intents)-{ident for ident,g in guards.items() if g.get('forwarded') is True}:raise Blocked('forward intent outcome unconfirmed')
    return {'events':out,'complete':not pending,'pending':len(pending),'unsupportedTransports':unsupported,
            'counts':{'senderRequests':len(requests),'senderResponses':len(responses),'senderTransportFailures':len(failures),
                      'boundary':len(guards),'transportDenials':len(denials),'targetArrivals':len(arrivals)},
            'proof':'independent local observer correlation; not signed remote attestation'}

def capture_snapshot(paths):
    def stamps():
        rows=[]
        for p in paths:
            try:s=Path(p).lstat();rows.append((s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns))
            except FileNotFoundError:rows.append(None)
        return rows
    for _ in range(20):
        before=stamps();rows=[read_rows(p) for p in paths]
        if before==stamps():return rows
        time.sleep(.005)
    raise Blocked('traffic snapshot changed while reading')

# The guard reads a separate sender log on a read-only mount; request marker alone
# never supplies a producer identity or grants permission to forward.
import http.client,threading,time
from urllib.parse import urlsplit
from .egress import EgressGuard,Denied,policy_target,request_target

class CorrelatedGuard(EgressGuard):
    capture_config=Path('/fixture/traffic-config.json')
    boundary_path=Path('/fixture/boundary.jsonl')
    def forward(self, target, relative, ident, req):
        """Adapter hook after correlation/policy checks, before the actual socket.

        The default remains anonymous. A delegated adapter must record intent
        immediately before its last-hop request and refuse any scope widening.
        """
        self._record({'kind':'forward-intent','requestId':ident,'method':self.command,
                      'urlSha256':req['urlSha256'],'at':time.monotonic()})
        c=http.client.HTTPConnection(target.hostname,target.port,timeout=2)
        try:
            c.request('GET',relative,headers={'Host':target.netloc,'Connection':'close','X-Zpa-Correlation':ident})
            r=c.getresponse();body=r.read(1048577)
            if len(body)>1048576:raise ValueError('response budget')
            return r.status,body,r.getheaders(),True,None
        finally:c.close()
    def _record(self,row):
        data=(json.dumps(row,separators=(',',':'))+'\n').encode()
        with self.server.capture_lock:
            try:
                from .safety_io import write_all
                fd=os.open(self.boundary_path,os.O_WRONLY|os.O_CREAT|os.O_APPEND|os.O_NOFOLLOW,0o600)
                try:write_all(fd,data);os.fsync(fd)
                finally:os.close(fd)
            except OSError:self.server.safety_halted=True;raise
    def do_GET(self):
        if not self.capture_config.exists():return super().do_GET()
        if not hasattr(self.server,'capture_lock'):self.server.capture_lock=threading.RLock()
        config=json.loads(self.capture_config.read_bytes());ident=self.headers.get('X-Zpa-Correlation')
        status=403;body=b'';forwarded=False;allowed=False;req=None;reason='correlation_missing'
        try:
            if getattr(self.server,'safety_halted',False):raise Denied('capture_halted')
            matches=[r for r in read_rows(config['senderPath']) if r.get('kind')=='request' and r.get('requestId')==ident]
            if len(matches)!=1:raise Denied('correlation_missing')
            req=matches[0]
            if req['method']!=self.command or req['urlSha256']!=sha(self.path.encode()) or req['bodySha256']!=sha(b''):raise Denied('correlation_mismatch')
            if req['initiator']==2:
                control=req.get('activeControl') is True and req.get('ruleId') is None and bool(config.get('activeRules'))
                if not control and req.get('ruleId') not in config.get('activeRules',[]):raise Denied('unsupported_active_rule')
                if req.get('phase')!='active':raise Denied('active_phase')
            elif req['initiator'] not in (3,6,7):raise Denied('unsupported_producer')
            # Active rule-header attribution is retained as diagnostic only. All
            # active producers are refused until a rule-specific attestor exists.
            for key in ('Host','Authorization','Proxy-Authorization','Cookie','Transfer-Encoding','Content-Length','X-Zpa-Correlation'):
                if len(self.headers.get_all(key,[]))>1:raise Denied('duplicate_header')
            u=urlsplit(self.path)
            if config.get('activeRules') and u.path==config.get('queryPath'):
                relative=request_target(self.command,self.path,self.headers,config['origin'])
            else:relative=policy_target(self.command,self.path,self.headers,config['origin'],config['allowedPaths'])
            if self.headers.get('x-zap-scan-id') and (req['initiator']!=2 or self.headers.get('x-zap-scan-id')!=req.get('ruleId')):raise Denied('unexpected_rule_header')
            target=urlsplit(config['origin']);allowed=True
            with self.server.capture_lock:
                # Intent is durable before forwarding; a writer failure latches
                # the entire boundary and cannot be mistaken for no target work.
                with self.rate_lock:
                    time.sleep(max(0,type(self).last_sent+self.minimum_interval-time.monotonic()))
                    if getattr(self.server,'safety_halted',False):raise Denied('capture_halted')
                    status,body,headers,forwarded,reason=self.forward(target,relative,ident,req)
                    type(self).last_sent=time.monotonic()
        except (Denied,OSError,ValueError) as exc:
            reason=str(exc) if isinstance(exc,Denied) else type(exc).__name__
            if allowed: self.server.safety_halted=True
        if req is not None:
            self._record({'kind':'boundary','requestId':ident,'method':self.command,'urlSha256':sha(self.path.encode()),'bodySha256':sha(b''),
                          'initiator':req['initiator'],'ruleId':req.get('ruleId'),'status':status,'responseBodySha256':sha(body),
                          'forwarded':forwarded,'targetAllowed':allowed,'credentialForwarded':False,'unsupportedVectors':[],
                          'reasonCode':reason,'at':time.monotonic()})
        else:
            self._record({'kind':'uncorrelated-denial','requestId':ident,'reasonCode':reason,'at':time.monotonic()})
        self.send_response_only(status)
        if forwarded:
            for k,v in headers:
                if k.lower() not in ('connection','transfer-encoding','content-length','server','date'):self.send_header(k,v)
        self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
    def do_CONNECT(self):
        if not self.capture_config.exists():return super().do_CONNECT()
        if not hasattr(self.server,'capture_lock'):self.server.capture_lock=threading.RLock()
        with self.server.capture_lock:
            # CONNECT carries no request correlation header and no HTTPS path.
            # Bind only a unique pending native request for this exact authority.
            # Ambiguity is blocked; never guess using the most recent URL.
            config=json.loads(self.capture_config.read_bytes());rows=read_rows(config['senderPath'])
            closed={r.get('requestId') for r in rows if r.get('kind') in ('response','transport-failure')}
            closed.update(r.get('requestId') for r in read_rows(self.boundary_path) if r.get('kind')=='transport-denial')
            authority=sha(self.path.encode())
            matches=[r for r in rows if r.get('kind')=='request' and r.get('scheme')=='https' and r.get('authoritySha256')==authority and r.get('requestId') not in closed]
            if len(matches)==1:
                self._record({'kind':'transport-denial','requestId':matches[0]['requestId'],'method':'CONNECT',
                              'authoritySha256':authority,'status':403,'forwarded':False,
                              'reasonCode':'unsupported_https_connect','at':time.monotonic()})
            else:
                self._record({'kind':'uncorrelated-denial','requestId':None,'authoritySha256':authority,'reasonCode':'ambiguous_or_missing_connect','at':time.monotonic()})
                self.server.safety_halted=True
        self.send_response_only(403);self.send_header('Content-Length','0');self.end_headers()
    def do_POST(self):
        if self.capture_config.exists():return self.do_GET()
        return super().do_POST()
    do_PUT=do_POST;do_DELETE=do_POST;do_PATCH=do_POST;do_OPTIONS=do_POST;do_HEAD=do_POST
