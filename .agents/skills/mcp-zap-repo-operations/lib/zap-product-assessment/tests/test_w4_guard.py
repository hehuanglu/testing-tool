"""HTTP boundary integration with simulated native receipts (not live ZAP proof)."""
import hashlib,http.client,json,tempfile,threading,unittest
from pathlib import Path
from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
from zap_assessment.traffic import CorrelatedGuard
class GuardTests(unittest.TestCase):
 def test_query_bytes_preserved_and_unsupported_attempts_never_arrive(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);arrivals=[]
   class Target(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
     arrivals.append(self.path);self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
   upstream=ThreadingHTTPServer(('127.0.0.1',0),Target);origin='http://127.0.0.1:'+str(upstream.server_port)
   class Guard(CorrelatedGuard):
    capture_config=root/'config';boundary_path=root/'boundary';minimum_interval=0
   sender=root/'sender';sender.write_text('');Guard.capture_config.write_text(json.dumps({'origin':origin,'senderPath':str(sender),'allowedPaths':['/health'],'activeRules':['40012'],'queryPath':'/api/echo','requirePhase':True}))
   boundary=ThreadingHTTPServer(('127.0.0.1',0),Guard)
   for server in (upstream,boundary):threading.Thread(target=server.serve_forever,daemon=True).start()
   try:
    cases=[('GET','/api/echo?q=%3Cscript%3E%2B%26%22','active',{},200),('GET','/api/echo?q=test','settle',{},403),('POST','/api/echo?q=test','active',{},403),('GET','/private','active',{},403),('GET','/api/echo?q=test','active',{'Authorization':'Bearer synthetic-canary'},403),('GET','/api/echo?q=test','active',{'Cookie':'synthetic=canary'},403),('GET','/api/echo?q=test','active',{'Host':'elsewhere.invalid'},403)]
    for n,(method,path,phase,headers,expected) in enumerate(cases):
     ident=str(n);url=origin+path;req={'kind':'request','requestId':ident,'initiator':2,'ruleId':'40012','phase':phase,'method':method,'urlSha256':hashlib.sha256(url.encode()).hexdigest(),'bodySha256':hashlib.sha256(b'').hexdigest()}
     with sender.open('a') as f:f.write(json.dumps(req)+'\n')
     c=http.client.HTTPConnection('127.0.0.1',boundary.server_port,timeout=3);c.request(method,url,headers={'Host':origin.split('//')[1],'X-Zpa-Correlation':ident,**headers});r=c.getresponse();self.assertEqual(expected,r.status);r.read();c.close()
    self.assertEqual([cases[0][1]],arrivals)
   finally:
    for server in (boundary,upstream):server.shutdown();server.server_close()
