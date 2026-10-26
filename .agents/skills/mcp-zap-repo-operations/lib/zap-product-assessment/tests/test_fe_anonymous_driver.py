import copy,json,tempfile,threading,unittest,http.client
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from zap_assessment.fe_anonymous_geckodriver import harden,Relay

class DriverTests(unittest.TestCase):
    def test_capability_is_hardened_in_all_matches(self):
        original={'capabilities':{'alwaysMatch':{'acceptInsecureCerts':True},'firstMatch':[{'acceptInsecureCerts':True}]},'desiredCapabilities':{'acceptInsecureCerts':True}}
        result,requested=harden(copy.deepcopy(original));self.assertTrue(requested);self.assertFalse(result['capabilities']['alwaysMatch']['acceptInsecureCerts']);self.assertNotIn('acceptInsecureCerts',result['capabilities']['firstMatch'][0]);self.assertNotIn('desiredCapabilities',result)
    def test_selenium_first_match_does_not_create_conflicting_options(self):
        value={'capabilities':{'firstMatch':[{'browserName':'firefox','acceptInsecureCerts':True,'moz:firefoxOptions':{'prefs':{'existing':True}}}]}}
        result,requested=harden(value);caps=result['capabilities']
        self.assertTrue(requested);self.assertNotIn('moz:firefoxOptions',caps['alwaysMatch'])
        self.assertTrue(caps['firstMatch'][0]['moz:firefoxOptions']['prefs']['existing'])
        self.assertFalse(caps['alwaysMatch']['acceptInsecureCerts']);self.assertNotIn('acceptInsecureCerts',caps['firstMatch'][0])
    def relay(self,actual):
        received=[]
        class Backend(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                received.append(json.loads(self.rfile.read(int(self.headers['Content-Length']))));blob=json.dumps({'value':{'sessionId':'owned','capabilities':{'acceptInsecureCerts':actual,'browserName':'firefox'}}}).encode();self.send_response(200);self.send_header('Content-Length',str(len(blob)));self.end_headers();self.wfile.write(blob)
            def do_DELETE(self):
                self.send_response(200);self.send_header('Content-Length','0');self.end_headers()
        with tempfile.TemporaryDirectory() as tmp:
            back=ThreadingHTTPServer(('127.0.0.1',0),Backend);relay=ThreadingHTTPServer(('127.0.0.1',0),Relay);relay.backend=back.server_port;relay.evidence=Path(tmp);relay.driver_sha='a'*64;relay.addon_sha='b'*64
            threads=[threading.Thread(target=s.serve_forever,daemon=True) for s in (back,relay)]
            for t in threads:t.start()
            try:
                c=http.client.HTTPConnection('127.0.0.1',relay.server_port,timeout=3);c.request('POST','/session',json.dumps({'capabilities':{'alwaysMatch':{'acceptInsecureCerts':True}}}),{'Content-Type':'application/json'});r=c.getresponse();r.read();status=r.status;c.close();record=json.loads(next(Path(tmp).glob('session-*.json')).read_text())
            finally:
                for s in (relay,back):s.shutdown();s.server_close()
                for t in threads:t.join()
        self.assertFalse(received[0]['capabilities']['alwaysMatch']['acceptInsecureCerts']);return status,record
    def test_verified_effective_capability_is_recorded(self):
        status,row=self.relay(False);self.assertEqual(status,200);self.assertIs(row['effectiveAcceptInsecureCerts'],False);self.assertIs(row['requestedAcceptInsecureCerts'],True)
    def test_noncompliant_driver_is_not_returned_to_crawler(self):
        status,row=self.relay(True);self.assertEqual(status,502);self.assertIs(row['effectiveAcceptInsecureCerts'],True)

if __name__=='__main__':unittest.main()
