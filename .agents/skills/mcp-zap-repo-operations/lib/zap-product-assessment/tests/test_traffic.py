import copy,hashlib,json,os,tempfile,unittest
from pathlib import Path
from zap_assessment.traffic import correlate,read_rows,TrafficInvalid

def evidence():
    h=hashlib.sha256(b'').hexdigest();url=hashlib.sha256(b'http://127.0.0.1:18080/health').hexdigest()
    req={'kind':'request','requestId':'run-1','initiator':3,'method':'GET','urlSha256':url,'bodySha256':h,'ruleId':None}
    resp={'kind':'response','requestId':'run-1','status':200,'bodySha256':h}
    guard={'kind':'boundary','requestId':'run-1','initiator':3,'ruleId':None,'method':'GET','urlSha256':url,'bodySha256':h,'status':200,'responseBodySha256':h,'forwarded':True,'targetAllowed':True,'credentialForwarded':False,'unsupportedVectors':[]}
    arrival={'kind':'arrival','requestId':'run-1','method':'GET','urlSha256':url,'bodySha256':h,'status':200,'responseBodySha256':h}
    intent={'kind':'forward-intent','requestId':'run-1','method':req['method'],'urlSha256':req['urlSha256']}
    return [req,resp],[guard,intent],[arrival]

class TrafficTests(unittest.TestCase):
    def transport_evidence(self):
        s,g,t=evidence();s[0].update(scheme='https',authoritySha256=sha(b'127.0.0.1:18080'))
        return [s[0],{'kind':'transport-failure','requestId':'run-1','failureKind':'io','exceptionType':'java.io.IOException'}],[{'kind':'transport-denial','requestId':'run-1','method':'CONNECT','authoritySha256':s[0]['authoritySha256'],'status':403,'forwarded':False,'reasonCode':'unsupported_https_connect'}],[]
    def test_transport_denial_has_no_fabricated_application_response(self):
        r=correlate(*self.transport_evidence(),terminal=True)
        self.assertTrue(r['complete']);self.assertEqual(0,r['counts']['senderResponses']);self.assertEqual(1,r['counts']['senderTransportFailures'])
        self.assertFalse(r['events'][0]['forwarded']);self.assertEqual(['https-transport'],r['events'][0]['unsupportedVectors'])
        self.assertEqual('unsupported_https_connect',r['unsupportedTransports'][0]['disposition'])
    def test_transport_denial_requires_native_failure_and_exact_authority(self):
        s,g,t=self.transport_evidence()
        for args in ((s[:1],g,t),(s,[],t),(s,g+[g[0]],t),(s+[{'kind':'response','requestId':'run-1','status':403,'bodySha256':sha(b'')}],g,t)):
            with self.subTest(args=args),self.assertRaises(TrafficInvalid):correlate(*args,terminal=True)
        for group,key,val in ((0,'scheme','http'),(1,'authoritySha256','0'*64),(1,'forwarded',True),(1,'status',200)):
            rows=copy.deepcopy((s,g,t));rows[group][0][key]=val
            with self.subTest(key=key),self.assertRaises(TrafficInvalid):correlate(*rows,terminal=True)
        s[1]['failureKind']='exception'
        with self.assertRaises(TrafficInvalid):correlate(s,g,t,terminal=True)
    def test_matches_three_independent_records(self):
        result=correlate(*evidence(),terminal=True);self.assertTrue(result['complete']);self.assertEqual('crawl',result['events'][0]['producer']);self.assertTrue(result['events'][0]['boundaryCorrelated'])
    def test_no_marker_only_proof_or_backfill(self):
        s,g,t=evidence()
        for args in (([],g,t),(s,[],t),(s,g,[]),(s[:1],g,t)):
            with self.subTest(args=args),self.assertRaises(TrafficInvalid):correlate(*args,terminal=True)
    def test_tamper_all_internal_hashes_does_not_override_independent_target(self):
        s,g,t=evidence()
        for key in ('method','urlSha256','bodySha256','status','responseBodySha256'):
            rows=copy.deepcopy((s,g,t));rows[1][0][key]='changed'
            if key in rows[0][0]:rows[0][0][key]='changed'
            if key in rows[1][1]:rows[1][1][key]='changed'
            if key=='status':rows[0][1]['status']='changed'
            if key=='responseBodySha256':rows[0][1]['bodySha256']='changed'
            with self.subTest(key=key),self.assertRaises(TrafficInvalid):correlate(*rows,terminal=True)
    def test_denied_cannot_have_target_arrival(self):
        s,g,t=evidence();g[0]['forwarded']=False
        with self.assertRaises(TrafficInvalid):correlate(s,g,t,terminal=True)
    def test_arrival_between_forward_intent_and_receipt_remains_pending(self):
        s,g,t=evidence();intent={'kind':'forward-intent','requestId':'run-1','method':g[0]['method'],'urlSha256':g[0]['urlSha256']}
        result=correlate(s[:1],[intent],t,terminal=False)
        self.assertFalse(result['complete']);self.assertEqual(1,result['pending'])
        with self.assertRaises(TrafficInvalid):correlate(s[:1],[intent],t,terminal=True)
    def test_duplicate_missing_unknown_and_partial_events(self):
        s,g,t=evidence()
        for args in ((s+[s[0]],g,t),(s,g+[g[0]],t),(s,g,t+[t[0]])):
            with self.assertRaises(TrafficInvalid):correlate(*args,terminal=True)
        s[0]['initiator']=999;g[0]['initiator']=999
        self.assertEqual('unknown',correlate(s,g,t,terminal=True)['events'][0]['producer'])
        self.assertFalse(correlate(s[:1],g,t)['complete'])
    def test_jsonl_special_files_and_duplicates_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'log';p.write_bytes(b'{"kind":"request","kind":"response"}\n')
            with self.assertRaises(TrafficInvalid):read_rows(p)
            p.write_bytes(b'{"kind":"request"}')
            with self.assertRaises(TrafficInvalid):read_rows(p)
            p.unlink();os.mkfifo(p)
            with self.assertRaises(TrafficInvalid):read_rows(p)
if __name__=='__main__':unittest.main()

import http.client,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from zap_assessment.traffic import CorrelatedGuard,sha

class GuardCorrelationTests(unittest.TestCase):
    def test_connect_unique_native_pending_is_denied_without_forward(self):
        req={'kind':'request','requestId':'tls-1','initiator':3,'ruleId':None,'method':'GET','scheme':'https','authoritySha256':sha(b'127.0.0.1:18080'),'urlSha256':sha(b'https://127.0.0.1:18080/scheme-canary'),'bodySha256':sha(b'')}
        (self.root/'sender').write_text(json.dumps(req)+'\n')
        c=http.client.HTTPConnection('127.0.0.1',self.guard.server_port,timeout=2);c.request('CONNECT','127.0.0.1:18080');r=c.getresponse();r.read();self.assertEqual(403,r.status);c.close()
        self.assertEqual([],self.arrivals)
        with (self.root/'sender').open('a') as f:f.write(json.dumps({'kind':'transport-failure','requestId':'tls-1','failureKind':'io','exceptionType':'java.io.IOException'})+'\n')
        self.assertTrue(correlate(read_rows(self.root/'sender'),read_rows(self.root/'boundary'),self.arrivals,terminal=True)['complete'])
    def test_connect_ambiguity_latches_instead_of_guessing(self):
        for ident in ('a','b'):
            with (self.root/'sender').open('a') as f:f.write(json.dumps({'kind':'request','requestId':ident,'scheme':'https','authoritySha256':sha(b'127.0.0.1:18080')})+'\n')
        c=http.client.HTTPConnection('127.0.0.1',self.guard.server_port,timeout=2);c.request('CONNECT','127.0.0.1:18080');r=c.getresponse();r.read();self.assertEqual(403,r.status);c.close()
        self.assertTrue(self.guard.safety_halted);self.assertEqual([],self.arrivals)
        with self.assertRaises(TrafficInvalid):correlate(read_rows(self.root/'sender'),read_rows(self.root/'boundary'),[],terminal=True)
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.arrivals=[];owner=self
        class Target(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                b=b'{}';owner.arrivals.append({'kind':'arrival','requestId':self.headers.get('X-Zpa-Correlation'),'method':'GET','urlSha256':sha(('http://'+self.headers['Host']+self.path).encode()),'bodySha256':sha(b''),'status':200,'responseBodySha256':sha(b)})
                self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b)
        self.target=ThreadingHTTPServer(('127.0.0.1',0),Target);self.origin='http://127.0.0.1:'+str(self.target.server_port)
        (self.root/'sender').write_bytes(b'');config=self.root/'config';config.write_text(json.dumps({'senderPath':str(self.root/'sender'),'origin':self.origin,'allowedPaths':['/safe']}))
        class Guard(CorrelatedGuard):
            target_origin=owner.origin;capture_config=config;boundary_path=owner.root/'boundary';log_path=owner.root/'legacy';minimum_interval=0;last_sent=0
        self.guard=ThreadingHTTPServer(('127.0.0.1',0),Guard)
        self.guard.capture_lock=threading.RLock()
        for s in (self.target,self.guard):threading.Thread(target=s.serve_forever,daemon=True).start()
    def tearDown(self):
        for s in (self.guard,self.target):s.shutdown();s.server_close()
        self.tmp.cleanup()
    def request(self,initiator=3,path='/safe',rule=None,marker=True,extra=None):
        ident='fixture-'+str(time.monotonic_ns());url=self.origin+path
        row={'kind':'request','requestId':ident,'initiator':initiator,'ruleId':rule,'method':'GET','urlSha256':sha(url.encode()),'bodySha256':sha(b'')}
        if marker:
            with (self.root/'sender').open('a') as f:f.write(json.dumps(row)+'\n')
        c=http.client.HTTPConnection('127.0.0.1',self.guard.server_port,timeout=3)
        c.request('GET',url,headers={'Host':self.origin[7:],'X-Zpa-Correlation':ident,**(extra or {})});r=c.getresponse();body=r.read();status=r.status;c.close()
        response={'kind':'response','requestId':ident,'status':status,'bodySha256':sha(body)}
        with (self.root/'sender').open('a') as f:f.write(json.dumps(response)+'\n')
        return status
    def test_loopback_forward_correlates_three_observers(self):
        self.assertEqual(200,self.request());r=correlate(read_rows(self.root/'sender'),read_rows(self.root/'boundary'),self.arrivals,terminal=True)
        self.assertTrue(r['complete']);self.assertEqual(1,r['counts']['targetArrivals'])
    def test_active_disabled_rule_unknown_path_credential_block_before_target(self):
        for kwargs in ({'initiator':2,'rule':'100043'},{'initiator':999},{'path':'/outside'},{'extra':{'Authorization':'Bearer test-canary'}}):
            with self.subTest(kwargs=kwargs):self.assertEqual(403,self.request(**kwargs))
        self.assertEqual([],self.arrivals)
        r=correlate(read_rows(self.root/'sender'),read_rows(self.root/'boundary'),self.arrivals,terminal=True);self.assertTrue(all(not e['forwarded'] for e in r['events']))
    def test_marker_without_sender_is_denied_and_cannot_be_complete_proof(self):
        self.assertEqual(403,self.request(marker=False));self.assertEqual([],self.arrivals)
        with self.assertRaises(TrafficInvalid):correlate(read_rows(self.root/'sender'),read_rows(self.root/'boundary'),self.arrivals,terminal=True)
