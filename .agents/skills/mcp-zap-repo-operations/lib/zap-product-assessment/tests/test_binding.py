import copy,hashlib,http.client,json,tempfile,threading,unittest
from datetime import timedelta
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).parent/'support'))
from borrowed_target import IndependentTarget
from zap_assessment.contracts import *
from zap_assessment.executor import Executor
from zap_assessment.existing import ExistingDockerRuntime
from zap_assessment.guard_server import BoundGuard
from zap_assessment.journal import Journal

def inputs():
    t=IndependentTarget.__new__(IndependentTarget);t.name='independent-unit';t.network='unit-network'
    t.before={'containerId':'a'*64,'imageId':'sha256:'+'b'*64,'running':True,'startedAt':'2026-10-18T00:00:00Z','networks':{t.network:{'networkId':'c'*64,'address':'172.28.0.2'}}}
    t.cid=t.before['containerId'];return t.inputs()

class BindingContracts(unittest.TestCase):
    def test_immutable_valid_plan_and_registered_adapter(self):
        p=make_plan(*inputs());validate_locked_plan(p);d=p.data;d['guard']['address']='169.254.169.254'
        with self.assertRaises(Blocked):validate_locked_plan(Plan(canonical(d)))
    def test_unsupported_tls_dns_and_ipv6_fail_without_resources(self):
        for origin in ('https://172.28.0.2:3000','http://target.invalid:3000','http://[::1]:3000'):
            values=list(inputs());values[0]['attackOrigins']=[origin];values[2].records['binding-synthetic-authority']['attackOrigins']=[origin]
            schema=json.loads(values[3]);schema['servers']=[{'url':origin}];values[3]=canonical(schema);values[0]['schema']['sha256']=hashlib.sha256(values[3]).hexdigest()
            with patch('socket.getaddrinfo',side_effect=AssertionError('DNS forbidden')):
                with self.assertRaises(Blocked):make_plan(*values)
    def test_owner_authority_unresolved_and_build_unapproved_fail(self):
        for mode in ('owner','issuer','environmentEvidenceRef','bindingHash','allowedPaths'):
            v=list(inputs());a=v[2].records['binding-synthetic-authority']
            a[mode]=[] if mode=='allowedPaths' else '0'*64 if mode=='bindingHash' else 'UNRESOLVED'
            with self.assertRaises(Blocked):make_plan(*v)
    def test_bad_plan_has_no_side_effects(self):
        d=make_plan(*inputs()).data;d['guard']['allowedPaths'].append('/secret')
        with tempfile.TemporaryDirectory() as t:
            ex=Executor(Path(t)/'runs',lambda *args:self.fail('runtime created'),lambda *args:self.fail('scanner created'))
            with self.assertRaises(Blocked):ex.run(Plan(canonical(d)))
            self.assertFalse((Path(t)/'runs').exists())
    def test_runtime_build_or_restart_mismatch_refused(self):
        with tempfile.TemporaryDirectory() as t:
            rt=ExistingDockerRuntime('unit',t,Journal(Path(t)/'j','unit','a'*64));rt.plan=make_plan(*inputs())
            b=rt.plan.data['product']['binding'];obs={'containerId':b['containerId'],'imageId':b['imageId'],'startedAt':b['startedAt'],'running':True,'networks':{'n':{'networkId':b['networkId'],'address':b['address']}}}
            for key in ('imageId','startedAt','running'):
                wrong=copy.deepcopy(obs);wrong[key]=False if key=='running' else 'wrong'
                with patch('zap_assessment.existing.target_metadata',return_value=wrong):
                    with self.assertRaises(Blocked):rt.assert_binding()
            self.assertNotIn(b['containerId'],rt.names)
            self.assertNotIn(b['networkId'],rt.names)
    def test_content_import_warning_is_not_success(self):
        from zap_assessment.transport import Scanner
        m=type('M',(),{'call':lambda *args:'OpenAPI content import returned 1 ZAP warning/error message(s)'})()
        with self.assertRaises(Blocked):Scanner(m,None,None).import_content('{}','http://172.28.0.2:3000')

class PlanGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.received=[];received=self.received
        class App(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                received.append({'path':self.path,'credential':bool(self.headers.get('Cookie') or self.headers.get('Authorization'))})
                self.send_response(302 if self.path=='/redirect' else 200)
                if self.path=='/cookie':self.send_header('Set-Cookie','unit-canary=1')
                if self.path=='/redirect':self.send_header('Location','http://169.254.169.254/')
                self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'{}')
        self.app=ThreadingHTTPServer(('127.0.0.1',0),App);self.origin='http://127.0.0.1:'+str(self.app.server_port)
        config={'origin':self.origin,'address':'127.0.0.1','port':self.app.server_port,'allowedPaths':['/health','/cookie','/redirect'],'maxRate':2,'validUntil':(utcnow()+timedelta(minutes=1)).isoformat()}
        class Guard(BoundGuard):pass
        Guard.config=config;Guard.last_sent=0;Guard.log_path=Path(self.temp.name)/'egress.jsonl'
        self.Guard=Guard;self.guard=ThreadingHTTPServer(('127.0.0.1',0),Guard)
        for s in (self.app,self.guard):threading.Thread(target=s.serve_forever,daemon=True).start()
    def tearDown(self):
        for s in (self.guard,self.app):s.shutdown();s.server_close()
        self.temp.cleanup()
    def send(self,path='/health',extra=None):
        c=http.client.HTTPConnection('127.0.0.1',self.guard.server_port,timeout=3)
        c.request('GET',self.origin+path,headers={'Host':urlsplit(self.origin).netloc,**(extra or {})});r=c.getresponse();body=r.read();result=(r.status,dict(r.getheaders()),body);c.close();return result
    def test_bound_target_get_and_credential_forwarding(self):
        self.assertEqual(self.send()[0],200)
        for header in ('Authorization','Cookie','Proxy-Authorization'):
            self.assertEqual(self.send(extra={header:'unit-canary'})[0],403)
        self.assertEqual(len(self.received),1);self.assertFalse(self.received[0]['credential'])
    def test_credential_response_never_forwarded(self):
        status,headers,body=self.send('/cookie');self.assertEqual(status,403);self.assertNotIn('Set-Cookie',headers);self.assertNotIn(b'unit-canary',body)
        self.assertNotIn('unit-canary',(Path(self.temp.name)/'egress.jsonl').read_text())
    def test_path_query_encoding_and_expiry_block(self):
        for path in ('/secret','/health?q=secret','/%68ealth','/health/../secret'):
            self.assertEqual(self.send(path)[0],403)
        self.Guard.config['validUntil']=(utcnow()-timedelta(seconds=1)).isoformat();self.assertEqual(self.send()[0],403);self.assertEqual(self.received,[])
    def test_redirect_not_followed(self):
        self.assertEqual(self.send('/redirect')[0],302);self.assertEqual([x['path'] for x in self.received],['/redirect'])

class ProductCLIInputs(unittest.TestCase):
    def test_profile_cannot_open_schema_before_authority(self):
        from zap_assessment.cli import product_plan
        v=inputs();v[0]['schema']['path']='missing.json'
        with tempfile.TemporaryDirectory() as t:
            profile=Path(t)/'product.json';profile.write_bytes(canonical(v[0]))
            with self.assertRaises(Blocked):product_plan(profile)
    def test_adjacent_canonical_schema_and_separate_authority_plan_only(self):
        from zap_assessment.cli import product_plan
        v=inputs();record=v[2].records['binding-synthetic-authority']
        with tempfile.TemporaryDirectory() as t:
            profile=Path(t)/'product.json';auth=Path(t)/'authority.json';schema=Path(t)/v[0]['schema']['path']
            profile.write_bytes(canonical(v[0]));auth.write_bytes(canonical(record));schema.write_bytes(v[3])
            with patch('zap_assessment.runtime.docker',side_effect=AssertionError('no runtime planning effects')):
                plan=product_plan(profile,auth);validate_locked_plan(plan)
            self.assertEqual(plan.hash,make_plan(*v).hash)
            v[0]['schema']['path']='../credential.json';profile.write_bytes(canonical(v[0]))
            with self.assertRaises(Blocked):product_plan(profile,auth)
    def test_locked_schema_content_digest_is_checked(self):
        d=make_plan(*inputs()).data;d['schema']['info']['description']='malicious instruction'
        with self.assertRaises(Blocked):validate_locked_plan(Plan(canonical(d)))
    def test_example_candidate_and_template_remain_non_executable(self):
        from zap_assessment.cli import product_plan
        with self.assertRaises(Blocked):product_plan(ROOT/'profiles/example-existing.draft.json',ROOT/'profiles/example-existing.authority.template.json')

class CLIRecoveryStatus(unittest.TestCase):
    def test_failed_recovery_never_claims_cleanup_clean(self):
        import io
        from contextlib import redirect_stdout
        from zap_assessment.cli import main
        out=io.StringIO()
        with patch('sys.argv',['zap-assessment','recover','/nonexistent-zpa-test-run']),redirect_stdout(out):code=main()
        result=json.loads(out.getvalue());self.assertEqual(code,2);self.assertEqual(result['cleanupStatus'],'incomplete');self.assertEqual(result['gateDecision'],'block')
    def test_authority_without_explicit_product_is_refused(self):
        import io
        from contextlib import redirect_stdout
        from zap_assessment.cli import main
        out=io.StringIO()
        with patch('sys.argv',['zap-assessment','pilot','--authority','/nonexistent-authority.json']),redirect_stdout(out):code=main()
        result=json.loads(out.getvalue());self.assertEqual(code,2);self.assertEqual(result['executionStatus'],'not_started');self.assertEqual(result['cleanupStatus'],'clean')

class GuardResponseCoverage(unittest.TestCase):
    def test_guard_error_status_cannot_be_declared_as_target_success(self):
        from zap_assessment.pilot import fixture_inputs
        for status in (403,502):
            args=list(fixture_inputs());args[0]['expectedOperations'][0]['status']=status
            with patch('zap_assessment.runtime.docker',side_effect=AssertionError('invalid contract created runtime')):
                with self.assertRaises(Blocked):make_plan(*args)
    def test_guard_error_cannot_satisfy_valid_target_status(self):
        from test_assessment import FakeRuntime,FakeScanner,FakeClock
        from zap_assessment.pilot import fixture_inputs
        class GuardReply(FakeScanner):
            def seed(self,*args):return {'sendRequest':[{'responseHeader':'HTTP/1.1 403 Forbidden\r\n'}]}
        with tempfile.TemporaryDirectory() as t:
            clock=FakeClock();scanner=GuardReply();executor=Executor(t,FakeRuntime,lambda rt:scanner,clock,clock.sleep)
            result=executor.run(make_plan(*fixture_inputs()))
            self.assertEqual(result['gateDecision'],'block');self.assertEqual(result['evidenceStatus'],'incomplete')
