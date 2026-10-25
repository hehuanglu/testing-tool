"""Real owned TLS mutation faults; POST is never replayed."""
import hashlib,http.client,json,ssl,socket,subprocess,tempfile,threading,time,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from zap_assessment.fe_anonymous_transport import Broker

class UnknownControls(unittest.TestCase):
 def control(self,mode):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);arrivals=[]
   subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN=control.test','-addext','subjectAltName=DNS:control.test','-keyout',str(root/'broker.key'),'-out',str(root/'broker.crt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
   (root/'upstream.crt').write_bytes((root/'broker.crt').read_bytes());(root/'mode.json').write_text(json.dumps({'caseId':'owned-submit','campaignId':'owned-campaign'}));(root/'records').mkdir()
   class App(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):
     arrivals.append(hashlib.sha256(self.rfile.read(int(self.headers['Content-Length']))).hexdigest())
     if mode=='drop':self.connection.shutdown(socket.SHUT_RDWR);return
     if mode=='timeout':time.sleep(.5);return
     body=b'x'*2048;self.send_response(201);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
   target=ThreadingHTTPServer(('127.0.0.1',0),App);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(root/'broker.crt',root/'broker.key');target.socket=ctx.wrap_socket(target.socket,server_side=True);threading.Thread(target=target.serve_forever,daemon=True).start()
   p={'runId':'owned-allocation','selection':{'origin':'https://control.test:9443','binding':{'address':'127.0.0.1'},'targetPort':target.server_port,'certificate':{'derSha256':hashlib.sha256(ssl.PEM_cert_to_DER_cert((root/'broker.crt').read_text())).hexdigest()}},'limits':{'maxRequests':10,'requestsPerSecond':100,'maxBodyBytes':1024},'requestPolicies':[{'method':'POST','pathRegex':'/submit','jsonFields':['input']}]}
   broker=Broker(p,root,root/'records',('127.0.0.1',0));threading.Thread(target=broker.serve_forever,daemon=True).start()
   try:
    c=http.client.HTTPConnection('127.0.0.1',broker.server_port);c.set_tunnel('control.test',9443);c.connect();c.sock=ssl.create_default_context(cafile=str(root/'broker.crt')).wrap_socket(c.sock,server_hostname='control.test')
    if mode=='before-send':broker.upstream.wrap_socket=lambda *a,**k: (_ for _ in ()).throw(OSError('owned before-send fault'))
    original=http.client.HTTPConnection.getresponse
    def short(connection):
     if connection.host=='control.test' and mode=='timeout':connection.sock.settimeout(.1)
     return original(connection)
    with patch.object(http.client.HTTPConnection,'getresponse',short):
     c.request('POST','/submit',b'{"input":"owned"}',headers={'Host':'control.test:9443','Content-Type':'application/json'});response=c.getresponse();response.read();c.close()
    records=[json.loads(f.read_text()) for f in (root/'records').glob('*.json')];events=[json.loads(s) for s in (root/'records/request-events.jsonl').read_text().splitlines()]
    row=records[0];self.assertEqual(len(records),1);self.assertEqual(row['caseId'],'owned-submit');self.assertEqual(row['campaignId'],'owned-campaign');self.assertEqual(row['allocationId'],'owned-allocation');self.assertEqual(row['requestBodySha256'],hashlib.sha256(b'{"input":"owned"}').hexdigest())
    if mode=='before-send':self.assertEqual(arrivals,[]);self.assertEqual(row['transportState'],'not-sent');self.assertIs(row['forwarded'],False)
    else:
     self.assertEqual(len(arrivals),1);self.assertEqual(row['transportState'],'unknown');self.assertIsNone(row['forwarded']);self.assertTrue(row['reconciliationRequired']);self.assertTrue(row['retentionRequired']);self.assertIs(row['mutationReplay'],False);self.assertIn('sent',[r['transportState'] for r in events])
    return {'mode':mode,'ownedMutationCount':len(arrivals),'row':row,'events':events}
   finally:broker.shutdown();broker.server_close();target.shutdown();target.server_close()
 def test_large_response(self):self.control('large')
 def test_commit_then_drop(self):self.control('drop')
 def test_timeout_after_commit(self):self.control('timeout')
 def test_before_send(self):self.control('before-send')

if __name__=='__main__':unittest.main()
