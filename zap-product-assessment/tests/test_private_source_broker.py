from dataclasses import asdict,replace
import json,os,socket,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.credential_broker import BrokerBinding,CredentialBroker
from zap_assessment.auth_lifecycle import ProducerStop
from zap_assessment.errors import Blocked
from zap_assessment.private_db import send,receive
from zap_assessment.private_source_broker import PrivateSourcePin,SourceGrant,PrivateSourceBroker,BrokeredReference

class PrivateSourceBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.source=self.root/'source.json'
        self.value={'runId':'source-original','origin':'http://127.0.0.1:18080','actors':{a:{'email':a+'@owned.invalid',
            'password':'private-source-'+a+'-123456789','fullName':'owned '+a,'userId':i,
            'registrationToken':'historical-private-token-'+a+'-123456789'} for a,i in [('A',11),('B',12)]}}
        self.source.write_text(json.dumps(self.value));self.source.chmod(0o600)
        self.binding=BrokerBinding('owned-run','a'*64,'A','11',None,'build','http://127.0.0.1:18080',200)
        self.grant=SourceGrant('b'*32,self.binding,'A',1003,1003);self.current=True;self.events=[]
        self.server=PrivateSourceBroker(run_id='owned-run',grants=[self.grant],source_pin=PrivateSourcePin.capture(self.source),
            source_run='source-original',source_origin=self.binding.origin,expected_subjects={'A':11,'B':12},
            check_current=lambda binding:self.current,record=self.events.append,forbidden_roots=[self.root/'repo'],clock=lambda:100)
    def tearDown(self):self.server.close();self.tmp.cleanup()
    def exchange(self,request=None,peer=None):
        client,server=socket.socketpair();errors=[]
        def handle():
            with server:
                try:
                    with patch('zap_assessment.private_source_broker.peer_identity',return_value=peer or {'uid':1003,'gid':1003}):
                        self.server.handle(server)
                except Exception as e:errors.append(type(e).__name__)
        t=threading.Thread(target=handle);t.start()
        with client:
            send(client,request or {'op':'resolve','referenceId':self.grant.reference_id,'binding':asdict(self.binding)})
            answer=receive(client)
        t.join(2);self.assertFalse(t.is_alive());self.assertFalse(errors)
        return answer
    def test_actor_projection_excludes_other_actor_and_historical_tokens(self):
        value=self.exchange();self.assertEqual({'status','referenceId','username','password'},set(value))
        self.assertEqual(self.value['actors']['A']['email'],value['username'])
        self.assertEqual(self.value['actors']['A']['password'],value['password'])
        self.assertNotIn(self.value['actors']['B']['password'],json.dumps(value))
        self.assertNotIn('registrationToken',json.dumps(value));self.assertEqual(1,self.server.source_reads)
        public=json.dumps(self.events)
        for actor in self.value['actors'].values():
            for key in ('email','password','registrationToken'):self.assertNotIn(actor[key],public)
        self.assertTrue(self.server.audit.matches(self.value['actors']['B']['registrationToken'].encode()))
    def test_wrong_peer_binding_and_replay_never_read_source(self):
        self.assertEqual('peer',self.exchange(peer={'uid':1000,'gid':1000})['reasonCode'])
        bad={'op':'resolve','referenceId':self.grant.reference_id,'binding':asdict(replace(self.binding,plan_hash='c'*64))}
        self.assertEqual('binding',self.exchange(bad)['reasonCode']);self.assertEqual(0,self.server.source_reads)
        self.exchange();self.assertEqual('no_replay',self.exchange()['reasonCode']);self.assertEqual(1,self.server.source_reads)
    def test_prerequisite_and_writer_failure_happen_before_source_read_and_consume_grant(self):
        self.current=False
        with patch.object(PrivateSourcePin,'read',side_effect=AssertionError('must not resolve')):
            self.assertEqual('prerequisite_or_source',self.exchange()['reasonCode'])
        self.assertEqual(0,self.server.source_reads);self.current=True
        self.assertEqual('no_replay',self.exchange()['reasonCode'])
    def test_writer_failure_prevents_file_read(self):
        self.server.record=lambda row:(_ for _ in ()).throw(OSError('ENOSPC'))
        self.assertEqual('prerequisite_or_source',self.exchange()['reasonCode']);self.assertEqual(0,self.server.source_reads)
    def test_source_swap_symlink_permissions_and_wrong_provenance_fail_closed(self):
        original=self.server.pin
        self.source.write_text(json.dumps({**self.value,'runId':'wrong'}))
        self.assertEqual('prerequisite_or_source',self.exchange()['reasonCode'])
        self.assertNotEqual(original,PrivateSourcePin.capture(self.source))
        self.source.chmod(0o644)
        with self.assertRaises(Blocked):PrivateSourcePin.capture(self.source)
        self.source.chmod(0o600);alias=self.root/'alias.json';alias.symlink_to(self.source)
        with self.assertRaises(Blocked):PrivateSourcePin.capture(alias)
    def test_in_place_source_reader_cannot_escape_forbidden_roots(self):
        self.server.forbidden_roots=(self.root,)
        self.assertEqual('prerequisite_or_source',self.exchange()['reasonCode'])
    def test_broker_rejects_grant_from_other_run_before_login(self):
        ref=BrokeredReference('b'*32,'A',replace(self.binding,run_id='other-run'),1005,1005)
        with self.assertRaisesRegex(Blocked,'grant_binding_mismatch'):
            CredentialBroker(binding=self.binding,source=ref,adapter=None,producer=ProducerStop(lambda:True,lambda:True),
                record=self.events.append,check_current=lambda binding:True,forbidden_roots=['/repo'],operations=[('GET','/accounts')])
    def test_deadline_loss_after_private_read_does_not_deliver_and_does_not_retry(self):
        count=[]
        def current(binding):count.append(1);return len(count)==1
        self.server.check_current=current
        self.assertEqual('prerequisite_or_source',self.exchange()['reasonCode']);self.assertEqual(1,self.server.source_reads)
        self.assertEqual('no_replay',self.exchange()['reasonCode'])

    def test_client_checks_server_peer_before_sending_grant(self):
        ref=BrokeredReference('b'*32,'A',self.binding,1005,1005)
        with patch('zap_assessment.private_source_broker.socket.socket') as sock, patch(
                'zap_assessment.private_source_broker.peer_identity',return_value={'uid':1000,'gid':1000}), patch(
                'zap_assessment.private_source_broker.send') as send_frame:
            with self.assertRaises(Blocked):ref.resolve(actor_ref='A',forbidden_roots=['/repo'])
            send_frame.assert_not_called()
        with self.assertRaises(Blocked):BrokeredReference('b'*32,'B',self.binding,1005,1005)

if __name__=='__main__':unittest.main()
