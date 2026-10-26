import base64
from dataclasses import replace
import json
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import unittest

from zap_assessment.auth_lifecycle import AuthLost,ProducerStop
from zap_assessment.credential_broker import BrokerBinding,SourceReference,CredentialBroker
from zap_assessment.errors import Blocked


class Adapter:
    def __init__(self):
        self.token='arbitrary.jwt/value+not-a-W5-canary-987654321'
        self.identity_value={'subject':'subject-A','role':'member','buildRef':'build-A'}
        self.calls=[];self.response={'status':200,'body':'{"balance":100}',
                                   'headers':{},'contentType':'application/json'}
        self.login_error=None;self.refresh_error=False
    def login(self,credential):
        self.calls.append('login')
        if self.login_error:raise ValueError(self.login_error)
        if credential!={'username':'actor-A@example.test','password':'arbitrary-Passwörd-!-$-43'}:
            raise ValueError('bad-source')
        return self.token
    def identity(self,token):
        self.calls.append('identity')
        if token!=self.token:raise ValueError('bad-token')
        return self.identity_value
    def protected(self,token,method,path,body):
        self.calls.append((method,path));return self.response
    def refresh(self,token):
        if self.refresh_error:raise ValueError(self.token)
        self.token='next-arbitrary-token.-!345678910';return self.token
    def logout(self,token):return None


class CredentialBrokerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve()
        self.source=self.root/'private-source.json';self.repo=self.root/'repository';self.repo.mkdir()
        self.source.write_text(json.dumps({'actorRef':'A','username':'actor-A@example.test',
                                           'password':'arbitrary-Passwörd-!-$-43'}));self.source.chmod(0o600)
        self.binding=BrokerBinding('run-A','a'*64,'A','subject-A','member','build-A','http://127.0.0.1:1234',200)
        self.ref=SourceReference('private-ref-A',self.source,'A');self.events=[];self.adapter=Adapter()
        self.now=100;self.current=True;self.stop=[];self.brokers=[]
    def tearDown(self):
        for b in self.brokers:
            try:b.destroy()
            except Blocked:pass
        self.tmp.cleanup()
    def broker(self,**kwargs):
        b=CredentialBroker(binding=self.binding,source=kwargs.pop('source',self.ref),adapter=self.adapter,
            producer=ProducerStop(lambda:self.stop.append('request') is None,lambda:True),
            record=self.events.append,check_current=lambda b:self.current,
            forbidden_roots=[self.repo],operations=[('GET','/accounts')],clock=lambda:self.now,**kwargs)
        self.brokers.append(b);return b
    def boot(self,**kwargs):
        b=self.broker(**kwargs);b.bootstrap(self.binding);return b

    def test_arbitrary_secret_family_stays_inside_holder_and_public_results_are_safe(self):
        b=self.boot();response=b.protected(self.binding,'GET','/accounts')
        public=json.dumps([response,self.events,b._session.snapshot()])
        for secret in ('arbitrary-Passwörd-!-$-43',self.adapter.token):self.assertNotIn(secret,public)
        self.assertEqual(['login','identity','identity',('GET','/accounts')],self.adapter.calls)
        self.assertNotIn(str(self.source),repr(self.ref)+repr(b))
        with self.assertRaises(TypeError):pickle.dumps(b)

    def test_encoded_password_and_rotated_token_compared_without_hash_export(self):
        b=self.boot(allow_refresh=True);first=self.adapter.token;b.refresh(self.binding)
        for secret in ('arbitrary-Passwörd-!-$-43',first,self.adapter.token):
            for blob in (secret.encode(),base64.b64encode(secret.encode()),
                         ''.join('%%%02x'%v for v in secret.encode()).encode(),
                         ''.join('\\u%04x'%ord(c) for c in secret).encode()):
                with self.subTest(form=len(blob)):self.assertTrue(b.audit_bytes(self.binding,blob)['matched'])
        self.assertFalse(b.audit_bytes(self.binding,b'clean public data')['matched'])

    def test_source_actor_and_cross_run_binding_fail_before_resolve(self):
        b=self.broker();self.source.unlink()
        for binding in (replace(self.binding,run_id='run-B'),replace(self.binding,actor_ref='B'),
                        replace(self.binding,plan_hash='b'*64),replace(self.binding,build_ref='build-B')):
            with self.assertRaisesRegex(Blocked,'binding'):b.bootstrap(binding)
        self.assertEqual([],self.adapter.calls)
        with self.assertRaises(Blocked):self.broker(source=SourceReference('bad',self.source,'B'))

    def test_expiry_and_admission_loss_latch_no_forward_or_relogin(self):
        for fault in ('expiry','attestor'):
            with self.subTest(fault=fault):
                self.now=100;self.current=True;b=self.boot()
                if fault=='expiry':self.now=200
                else:self.current=False
                count=len(self.adapter.calls)
                with self.assertRaises(Blocked):b.protected(self.binding,'GET','/accounts')
                with self.assertRaises(Blocked):b.bootstrap(self.binding)
                self.assertEqual(count,len(self.adapter.calls))

    def test_file_source_rejects_modes_symlinks_hardlinks_duplicates_and_repo_copy(self):
        for fault in ('mode','symlink','parent-symlink','hardlink','duplicate','actor','repository','oversize'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(dir=self.root) as d:
                q=Path(d)/'source';q.write_bytes(self.source.read_bytes());q.chmod(0o600);path=q
                if fault=='mode':q.chmod(0o644)
                if fault=='symlink':path=q.with_name('alias');path.symlink_to(q)
                if fault=='parent-symlink':
                    alias=self.root/('alias-'+fault);alias.symlink_to(Path(d));path=alias/'source'
                if fault=='hardlink':os.link(q,q.with_name('linked'))
                if fault=='duplicate':q.write_text('{"actorRef":"A","actorRef":"A","username":"x","password":"y"}')
                if fault=='actor':q.write_text('{"actorRef":"B","username":"x","password":"y"}')
                if fault=='repository':path=self.repo/'copy';path.write_bytes(q.read_bytes());path.chmod(0o600)
                if fault=='oversize':q.write_bytes(b'x'*16385)
                with self.assertRaisesRegex(Blocked,'source_unavailable'):
                    SourceReference('ref',path,'A').resolve(actor_ref='A',forbidden_roots=[self.repo])

    def test_source_and_adapter_errors_have_no_secret_text_or_chained_output(self):
        self.adapter.login_error='arbitrary-Passwörd-!-$-43';b=self.broker()
        with self.assertRaises(AuthLost) as caught:b.bootstrap(self.binding)
        self.assertEqual('login_failed',str(caught.exception))
        self.assertTrue(caught.exception.__suppress_context__)
        with self.assertRaises(Blocked):b.bootstrap(self.binding)

    def test_identity_failure_cannot_forward_and_stop_is_requested(self):
        b=self.boot();self.adapter.identity_value={**self.adapter.identity_value,'subject':'B'}
        with self.assertRaisesRegex(AuthLost,'identity_binding_changed'):b.protected(self.binding,'GET','/accounts')
        b._session.await_stop();self.assertTrue(self.stop)
        self.assertFalse(any(isinstance(v,tuple) for v in self.adapter.calls))

    def test_secret_echo_and_target_login200_fail_closed(self):
        for response in ({'status':200,'body':self.adapter.token,'headers':{},'contentType':'application/json'},
                         {'status':200,'body':'login','headers':{},'contentType':'text/html'},
                         {'status':200,'body':'{}','headers':{'Set-Cookie':'private'},'contentType':'application/json'}):
            with self.subTest(response_type=response['contentType']):
                b=self.boot();self.adapter.response=response
                with self.assertRaises(AuthLost):b.protected(self.binding,'GET','/accounts')

    def test_paths_and_methods_never_escape_exact_operation_scope(self):
        b=self.boot();count=len(self.adapter.calls)
        for method,path in [('GET','http://outside/accounts'),('GET','//outside/accounts'),('GET','/accounts/../x'),
                            ('GET','/accounts%2f..'),('GET','/other'),('POST','/accounts'),('GET','/accounts#x')]:
            with self.assertRaises(Blocked):b.protected(self.binding,method,path)
        self.assertEqual(count,len(self.adapter.calls))
        with self.assertRaises(Blocked):b.protected(self.binding,'GET','/accounts',{'data':self.adapter.token})

    def test_close_preserves_cleanup_comparison_until_destroy_without_resolving_again(self):
        b=self.boot();self.source.unlink();b.close()
        self.assertTrue(b.audit_bytes(self.binding,self.adapter.token.encode())['matched'])
        with self.assertRaises(Blocked):b.protected(self.binding,'GET','/accounts')
        b.destroy()
        with self.assertRaises(Blocked):b.audit_bytes(self.binding,b'public')

    def test_refresh_rejected_and_source_reuse_do_not_resume_old_epoch(self):
        b=self.boot(allow_refresh=True);epoch=b._session.epoch
        with self.assertRaises(Blocked):b.bootstrap(self.binding)
        self.adapter.refresh_error=True
        with self.assertRaisesRegex(AuthLost,'refresh_rejected'):b.refresh(self.binding)
        self.assertEqual(epoch,b._session.epoch)
        with self.assertRaises(AuthLost):b.protected(self.binding,'GET','/accounts')

    def test_private_source_http_lifecycle_runs_in_child_with_no_secret_values_returned(self):
        script=Path(__file__).parent/'support/broker_reference_holder.py'
        r=subprocess.run([sys.executable,'-S',str(script)],capture_output=True,text=True,timeout=12,
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
        self.assertEqual(0,r.returncode,r.stdout+r.stderr)
        value=json.loads(r.stdout)
        self.assertEqual(8,len(value['cases']));self.assertTrue(all(c['status']=='pass' for c in value['cases']))
        self.assertEqual(0,value['productRequests']);self.assertFalse(value['sourceValuesIncluded'])
        self.assertFalse(value['operationalAdmission']);self.assertFalse(value['platformAcceptance'])

    def test_origin_normalization_and_query_vector_scope(self):
        for target in ('http://127.0.0.1:1234/','http://user:pass@127.0.0.1:1234',
                       'http://127.0.0.1:1234#frag','http://127.0.0.1:0','http://127.0.0.01'):
            with self.assertRaises(Blocked):replace(self.binding,origin=target)
        b=self.boot();b.protected(self.binding,'GET','/accounts?q=%27%20OR%201')
        self.assertEqual(('GET','/accounts?q=%27%20OR%201'),self.adapter.calls[-1])


if __name__=='__main__':unittest.main()
