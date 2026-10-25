from dataclasses import replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import time
import unittest

from zap_assessment.auth_lifecycle import AuthLost,ProducerStop
from zap_assessment.credential_broker import BrokerBinding,CredentialBroker,GeneratedReference
from zap_assessment.errors import Blocked
from zap_assessment.finalsource_delegated import TargetBinding,GetPolicy,FinalsourceAdapter,accounts_subject

class FinalsourceDelegatedTests(unittest.TestCase):
    def setUp(self):
        self.requests=[];self.subject=11;self.html=False;self.status=200;self.drift=False
        self.events=[];self.stops=[];self.brokers=[];outer=self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_POST(self):
                outer.requests.append((self.command,self.path))
                value=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if value!={'email':'owned@test.invalid','password':'owned-canary-password-12345'}:raise ValueError()
                self.reply(200,{'success':True,'data':{'accessToken':'owned-fixture-token-123456789','user':{'id':999}}})
            def do_GET(self):
                outer.requests.append((self.command,self.path))
                value={'success':True,'data':{'user_id':outer.subject,'accounts':[]}}
                self.reply(outer.status,value)
            def reply(self,status,value):
                raw=b'<html>login</html>' if outer.html else json.dumps(value).encode()
                self.send_response(status);self.send_header('Content-Type','text/html' if outer.html else 'application/json')
                self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        self.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.target=TargetBinding('a'*64,'sha256:'+'b'*64,'started','c'*64,'127.0.0.1',self.server.server_port)
        self.binding=BrokerBinding('owned-unit-run','a'*64,'A','11',None,'bound-build',f'http://127.0.0.1:{self.server.server_port}',time.time()+60)
        self.adapter=FinalsourceAdapter(binding=self.binding,target=self.target,
            policy=GetPolicy(['/api/v1/accounts','/api/v1/transactions']),
            require_current=lambda b,t:not self.drift,record=self.events.append)
    def tearDown(self):
        for b in self.brokers:b.destroy()
        self.server.shutdown();self.server.server_close();self.thread.join()
    def broker(self):
        source=GeneratedReference('owned-canary','A',lambda:{'username':'owned@test.invalid','password':'owned-canary-password-12345'})
        b=CredentialBroker(binding=self.binding,source=source,adapter=self.adapter,
            producer=ProducerStop(lambda:self.stops.append('stop') is None,lambda:True),
            record=self.events.append,check_current=lambda binding:not self.drift,
            forbidden_roots=['/non-secret-repo'],operations=[('GET','/api/v1/accounts'),('GET','/api/v1/transactions')])
        self.brokers.append(b);b.bootstrap(self.binding);return b
    def test_protected_principal_overrides_login_user_and_preserves_exact_query(self):
        b=self.broker();epoch=b.snapshot()['authEpoch']
        path='/api/v1/transactions?type=expense%27%20OR%201%3D1&limit=10&offset=0'
        b.protected(self.binding,'GET',path)
        self.assertEqual(path,self.requests[-1][1]);self.assertEqual(epoch,b.snapshot()['authEpoch'])
        proof=[r for r in self.events if r.get('event')=='identity_proof']
        self.assertTrue(proof);self.assertTrue(all(r['subjectRef']=='11' and r['roleRef'] is None for r in proof))
        public=json.dumps(self.events)
        self.assertNotIn('owned-fixture-token',public);self.assertNotIn('owned-canary-password',public)
    def test_wrong_actor_html_and_expired_session_latch_without_relogin(self):
        for fault in ('actor','html','401'):
            with self.subTest(fault=fault):
                self.subject=11;self.html=False;self.status=200
                self.adapter=FinalsourceAdapter(binding=self.binding,target=self.target,
                    policy=GetPolicy(['/api/v1/accounts']),require_current=lambda b,t:True,record=self.events.append)
                b=self.broker()
                if fault=='actor':self.subject=12
                if fault=='html':self.html=True
                if fault=='401':self.status=401
                with self.assertRaises(AuthLost):b.protected(self.binding,'GET','/api/v1/accounts')
                count=len(self.requests)
                with self.assertRaises(Blocked):b.protected(self.binding,'GET','/api/v1/accounts')
                with self.assertRaises(Blocked):b.bootstrap(self.binding)
                self.assertEqual(count,len(self.requests));b._session.await_stop()
                self.assertTrue(b.snapshot()['stop']['terminalConfirmed'])
    def test_drift_before_source_resolution_and_repeated_login_are_refused(self):
        self.drift=True
        with self.assertRaises(Blocked):self.adapter.login({'username':'owned@test.invalid','password':'canary'})
        self.assertFalse(self.requests)
        self.drift=False
        with self.assertRaisesRegex(Blocked,'no_replay'):self.adapter.login({})
    def test_query_policy_rejects_mutations_duplicates_unknown_names_and_aliases(self):
        policy=GetPolicy(['/api/v1/accounts','/api/v1/transactions'])
        bad=[('POST','/api/v1/accounts'),('GET','//127.0.0.1/api/v1/accounts'),('GET','/api/v1/%61ccounts'),
             ('GET','/api/v1/transactions?%74ype=expense'),('GET','/api/v1/transactions?type=a&type=b'),
             ('GET','/api/v1/transactions?type=%gg'),('GET','/api/v1/accounts?q=test'),
             ('GET','/api/v1/transactions?type=expense#frag')]
        for method,path in bad:
            with self.assertRaises(Blocked):policy.check(method,path)
        with self.assertRaises(Blocked):policy.check('GET','/api/v1/accounts',b'body')
    def test_oracle_rejects_boolean_subject_duplicate_json_membership_only_and_html(self):
        for body in ('{"success":true,"data":{"user_id":true,"accounts":[]}}',
                     '{"success":true,"data":{"accounts":[{"id":11}]}}',
                     '{"success":true,"data":{"user_id":11,"user_id":12,"accounts":[]}}',
                     '<html>login</html>'):
            with self.assertRaises(Blocked):accounts_subject({'status':200,'contentType':'application/json','body':body})
    def test_role_must_be_explicitly_absent_and_target_exact(self):
        with self.assertRaises(Blocked):FinalsourceAdapter(binding=replace(self.binding,role='invented'),target=self.target,
            policy=GetPolicy(['/api/v1/accounts']),require_current=lambda b,t:True,record=self.events.append)
        with self.assertRaises(Blocked):replace(self.target,address='127.00.0.1')

if __name__=='__main__':unittest.main()

class DelegatedHolderWiringTests(unittest.TestCase):
    # Reuse only the owned fixture setup; do not duplicate the adapter tests.
    setUp = FinalsourceDelegatedTests.setUp
    tearDown = FinalsourceDelegatedTests.tearDown
    def test_holder_wires_replay_before_source_epoch_and_every_final_hop(self):
        import hashlib
        from pathlib import Path
        import tempfile
        from zap_assessment.delegated_attestation import RuntimeAttestor,RuntimeSnapshot,GATES,ProofReplay
        from zap_assessment.delegated_holder import DelegatedHolder
        class Replay(ProofReplay):
            failure=None
            def verify(replay,gate,evidence,**kwargs):
                if gate==replay.failure:raise Blocked('unit-proof-failure')
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'proof';p.write_bytes(b'owned-unit-evidence-not-runtime-acceptance')
            checksum=hashlib.sha256(p.read_bytes()).hexdigest();replay=Replay();resolutions=[]
            attestor=RuntimeAttestor(binding=self.binding,target=self.target,scanner_id='d'*64,
                scanner_image='sha256:'+'e'*64,holder_id='f'*64,holder_image='sha256:'+'1'*64,
                source_root=folder,source_pins={'proof':checksum},evidence_root=folder,
                evidence_pins={g:[('proof',checksum)] for g in GATES},replay=replay,
                observe=lambda:RuntimeSnapshot(self.target,'d'*64,'sha256:'+'e'*64,'f'*64,'sha256:'+'1'*64,time.monotonic()),
                stop=lambda:self.stops.append('attestor-stop'))
            def resolve():
                resolutions.append('source')
                return {'username':'owned@test.invalid','password':'owned-canary-password-12345'}
            holder=DelegatedHolder(attestor=attestor,source=GeneratedReference('unit-owned','A',resolve),
                producer=ProducerStop(lambda:True,lambda:True),record=self.events.append,
                forbidden_roots=['/non-secret-repo'],operations=['/api/v1/accounts','/api/v1/transactions'])
            try:
                holder.bootstrap();self.assertEqual(['source'],resolutions)
                self.assertEqual(attestor.epoch,holder.broker.snapshot()['authEpoch'])
                self.assertEqual(200,holder.dispatch('GET','/api/v1/accounts')['status'])
                count=len(self.requests);replay.failure='G5'
                with self.assertRaises(Blocked):holder.dispatch('GET','/api/v1/accounts')
                with self.assertRaises(Blocked):holder.bootstrap()
                self.assertEqual(count,len(self.requests));self.assertEqual(['source'],resolutions)
            finally:holder.destroy()
