import http.client
import json
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from zap_assessment.egress import EgressGuard,Denied,request_target

class EgressTests(unittest.TestCase):
    def test_origin_alias_scheme_host_override_and_methods(self):
        good='http://127.0.0.1:18080/health'
        self.assertEqual(request_target('GET',good,{'Host':'127.0.0.1:18080'}),'/health')
        for method,url,headers in [('GET','http://localhost:18080/health',{'Host':'localhost:18080'}),('GET','https://127.0.0.1:18080/',{'Host':'127.0.0.1:18080'}),('GET',good,{'Host':'localhost:18080'}),('POST',good,{'Host':'127.0.0.1:18080'}),('GET',good,{'Host':'127.0.0.1:18080','Authorization':'Bearer egress-canary'}),('GET','http://127.0.0.1:18081/',{'Host':'127.0.0.1:18081'}),('GET','http://user@127.0.0.1:18080/',{'Host':'127.0.0.1:18080'}),('GET','http://169.254.169.254/',{'Host':'169.254.169.254'})]:
            with self.assertRaises(Denied):request_target(method,url,headers)
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.received=[];received=self.received
        class Target(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                received.append({'path':self.path,'host':self.headers.get('Host'),'at':time.monotonic()})
                self.send_response(302 if self.path=='/redirect' else 200)
                if self.path=='/redirect':self.send_header('Location','http://169.254.169.254/canary')
                self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
        self.target=ThreadingHTTPServer(('127.0.0.1',0),Target)
        self.origin='http://127.0.0.1:'+str(self.target.server_port);origin=self.origin;log=Path(self.temp.name)/'guard.jsonl'
        class Guard(EgressGuard):
            target_origin=origin;log_path=log;minimum_interval=.05;last_sent=0.0
        self.guard=ThreadingHTTPServer(('127.0.0.1',0),Guard)
        for server in (self.target,self.guard):threading.Thread(target=server.serve_forever,daemon=True).start()
    def tearDown(self):
        for server in (self.guard,self.target):server.shutdown();server.server_close()
        self.temp.cleanup()
    def send(self,url,method='GET',host=None):
        conn=http.client.HTTPConnection('127.0.0.1',self.guard.server_port,timeout=3)
        conn.request(method,url,headers={'Host':host or self.origin.removeprefix('http://'),'Connection':'close'});r=conn.getresponse();data=r.read();status=r.status;conn.close();return status,data
    def test_redirect_is_returned_without_following(self):
        status,_=self.send(self.origin+'/redirect');self.assertEqual(status,302)
        self.assertEqual([x['path'] for x in self.received],['/redirect'])
    def test_alias_and_tunnel_do_not_reach_target(self):
        alias=self.origin.replace('127.0.0.1','localhost')
        self.assertEqual(self.send(alias+'/alias',host=alias.removeprefix('http://'))[0],403)
        self.assertEqual(self.send(self.origin.removeprefix('http://'),method='CONNECT')[0],403)
        self.assertEqual(self.send(self.origin+'/mutate',method='POST')[0],403)
        self.assertEqual(self.received,[])
    def test_parallel_requests_are_rate_limited_at_send(self):
        with ThreadPoolExecutor(3) as pool:results=list(pool.map(lambda i:self.send(self.origin+'/x'),range(3)))
        self.assertTrue(all(status==200 for status,_ in results));times=sorted(x['at'] for x in self.received)
        self.assertTrue(all(b-a>=.04 for a,b in zip(times,times[1:])),times)
    def test_proxy_headers_cannot_change_target_host(self):
        self.assertEqual(self.send(self.origin+'/x',host='evil.invalid')[0],403);self.assertEqual(self.received,[])
    def test_scope_log_contains_hashes_without_raw_url(self):
        raw='http://evil.invalid/?private=fixture-only-canary';self.assertEqual(self.send(raw)[0],403)
        data=(Path(self.temp.name)/'guard.jsonl').read_text();self.assertNotIn('fixture-only-canary',data);self.assertNotIn('evil.invalid',data)
        self.assertEqual(json.loads(data)['action'],'denied')

if __name__=='__main__':unittest.main()
