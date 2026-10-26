"""Actual TLS requests to owned local controls, including rejection before app arrival."""
import hashlib,http.client,json,ssl,socket,subprocess,tempfile,threading,unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from zap_assessment.fe_anonymous_transport import Broker

class TLSControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.root=Path(cls.tmp.name);cls.arrivals=[]
        for name,host in [('target','control.test'),('broker','control.test'),('wrong','wrong.test')]:
            subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','1','-subj','/CN='+host,'-addext','subjectAltName=DNS:'+host,'-keyout',str(cls.root/(name+'.key')),'-out',str(cls.root/(name+'.crt'))],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        class App(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_GET(self):
                cls.arrivals.append({'host':self.headers['Host'],'path':self.path});body=b'owned TLS app'
                self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        cls.target=ThreadingHTTPServer(('127.0.0.1',0),App);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(str(cls.root/'target.crt'),str(cls.root/'target.key'));cls.target.socket=ctx.wrap_socket(cls.target.socket,server_side=True)
        cls.thread=threading.Thread(target=cls.target.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.target.shutdown();cls.target.server_close();cls.tmp.cleanup()
    def probe(self,*,fingerprint=True,name='control.test',ca='target',headers=None):
        import shutil
        directory=self.root/('probe-'+str(len(list(self.root.glob('probe-*')))));directory.mkdir();(directory/'records').mkdir()
        for f in ('broker.crt','broker.key'):shutil.copyfile(self.root/f,directory/f)
        shutil.copyfile(self.root/(ca+'.crt'),directory/'upstream.crt');(directory/'mode.json').write_text('{}')
        cert=hashlib.sha256(ssl.PEM_cert_to_DER_cert((self.root/'target.crt').read_text())).hexdigest()
        p={'selection':{'origin':'https://'+name+':9443','binding':{'address':'127.0.0.1'},'targetPort':self.target.server_port,'certificate':{'derSha256':cert if fingerprint else '0'*64}},'limits':{'maxRequests':10,'requestsPerSecond':100,'maxBodyBytes':1024},'requestPolicies':[{'method':'GET','pathRegex':'/public'}]}
        broker=Broker(p,directory,directory/'records',('127.0.0.1',0));thread=threading.Thread(target=broker.serve_forever,daemon=True);thread.start();before=len(self.arrivals)
        try:
            c=http.client.HTTPConnection('127.0.0.1',broker.server_port);c.set_tunnel(name,9443);c.connect()
            # Broker certificate is control.test. Upstream name test still uses a verified broker connection.
            ctx=ssl.create_default_context(cafile=str(directory/'broker.crt'));c.sock=ctx.wrap_socket(c.sock,server_hostname='control.test')
            c.request('GET','/public',headers={'Host':name+':9443',**(headers or {})});r=c.getresponse();status=r.status;body=r.read();c.close()
            return status,body,len(self.arrivals)-before
        finally:broker.shutdown();broker.server_close()
    def test_verified_good_tls_and_host(self):
        self.assertEqual(self.probe(),(200,b'owned TLS app',1));self.assertEqual(self.arrivals[-1]['host'],'control.test:9443')
    def test_fingerprint_drift_before_app(self):self.assertEqual(self.probe(fingerprint=False)[::2],(502,0))
    def test_untrusted_ca_before_app(self):self.assertEqual(self.probe(ca='wrong')[::2],(502,0))
    def test_wrong_sni_name_before_app(self):self.assertEqual(self.probe(name='wrong.test')[::2],(502,0))
    def test_identity_not_stripped_or_forwarded(self):self.assertEqual(self.probe(headers={'Authorization':'Bearer owned-control'})[::2],(403,0))

if __name__=='__main__':unittest.main()
