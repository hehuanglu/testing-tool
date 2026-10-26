"""Contract/transport variations; no target traffic or real Docker operations."""
import copy
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
from test_discovery import fixture,compiled
from test_research import BIND
from zap_assessment.discovery import validate_discovery,compile_plan,validate_plan,validate_transport
from zap_assessment import research_product as rp


def modern():
    d=fixture();d['schemaVersion']='product-discovery/1.1';d['product']['environmentEvidenceRefs']=['source'];d['product']['description']='Readable test deployment description'
    d['product']['origins'][0].update(accessFrom='scanner-network',confidence='high')
    d['product']['origins'].append({'url':'https://localhost:9443','role':'direct','accessFrom':'orchestrator-host','authorized':True,'bindingVerified':True,'evidenceRefs':['source'],'confidence':'medium'})
    for s in d['sources']+d['operations']+d['fixtures']+[d['auth']]:s['confidence']='high'
    return d


def proof(d=None):
    d=d or modern()
    return {'environment':d['product']['environment'],'targetBinding':BIND,'scannerOrigins':[d['product']['origins'][0]['url']],'directOrigins':['https://localhost:9443'],
            'observedAt':'2026-10-21T00:00:00Z','evidence':{'runtime':'fixture-independent-inspector'}}


def makeplan(d=None,p=None):
    d=d or modern();old=compiled()
    return compile_plan(d,live_binding=BIND,actor=old['actor'],requests=[{'method':'GET','path':'/v9/things'}],fixtures=[],authority=old['authority'],observed_transport=proof(d) if p is None else p)


class TransportTests(unittest.TestCase):
    def test_stable_environment_access_point_confidence_required(self):
        validate_discovery(modern(),executable=True)
        for mutate in [lambda d:d['product'].update(environment='environment prose with spaces'),lambda d:d['product']['origins'][1].update(accessFrom='scanner-network'),lambda d:d['auth'].pop('confidence')]:
            d=modern();mutate(d)
            with self.assertRaises(ValueError):validate_discovery(d,executable=True)
    def test_plan_accepts_verified_alias_and_binds_changed_metadata(self):
        d=modern();d['product']['origins'][0]['url']='http://named-container:9001'
        p=makeplan(d);self.assertEqual(p['schemaVersion'],'research-plan/2.1');self.assertEqual(p['origin'],'http://named-container:9001')
        validate_plan(p,BIND)
        p['origin']='http://not-observed:9001'
        with self.assertRaises(ValueError):validate_plan(p,BIND)
    def test_self_claimed_origin_not_external_authority(self):
        d=modern();p=proof(d);d['product']['origins'][0]['url']='https://outside.test'
        with self.assertRaisesRegex(ValueError,'independently bound'):makeplan(d,p)
        p=proof();p['environment']='other-test'
        with self.assertRaisesRegex(ValueError,'environment'):makeplan(modern(),p)
        p=proof();p['directOrigins']=['http://docker-only:3000']
        with self.assertRaisesRegex(ValueError,'direct'):makeplan(modern(),p)
    def test_legacy_meaning_preserved_and_new_missing_inspection_rejected(self):
        self.assertEqual(compiled()['schemaVersion'],'research-plan/2.0')
        d=modern();old=compiled()
        with self.assertRaisesRegex(ValueError,'observation required'):
            compile_plan(d,live_binding=BIND,actor=old['actor'],requests=[{'method':'GET','path':'/v9/things'}],fixtures=[],authority=old['authority'])
    def test_adapter_admits_only_independently_observed_alias(self):
        d=modern();d['product']['environment']='finalsource-zap-test'
        mapping={};ops=[]
        for n,(method,path) in enumerate(sorted(rp.SURFACE)):
            oid='o'+str(n);mapping[(method,path)]=oid
            ops.append({'id':oid,'method':method,'pathTemplate':path,'protected':path.startswith('/api/v1/'),'semantics':'synthetic adapter compatibility','input':{},'evidenceRefs':['source'],'confidence':'high'})
        d['operations']=ops
        d['auth'].update(loginOperationId=mapping[('POST','/api/auth/login')],tokenPointer='/data/accessToken',usernameField='email',passwordField='password')
        d['auth']['identity'].update(operationId=mapping[('GET','/api/v1/accounts')],subjectPointer='/data/user_id',actorSource={'operationId':mapping[('POST','/api/auth/register')],'subjectPointer':'/data/user/id'})
        d['fixtures'][0]['operationIds']=[x['id'] for x in ops if x['protected'] and x['method']!='GET']
        d['product']['origins'][0]['url']='http://verified-alias:3000';p=proof(d)
        with patch.object(rp,'verify_local_sources',return_value=True):
            self.assertIs(rp.admit_adapter(d,BIND,p),d)
            d['product']['origins'][0]['url']='http://unobserved-alias:3000'
            with self.assertRaisesRegex(ValueError,'independently bound'):rp.admit_adapter(d,BIND,p)
    def test_multiple_verified_aliases_preserved_with_deterministic_selection(self):
        d=modern();second={**d['product']['origins'][0],'url':'http://second-alias:8443'};d['product']['origins'].insert(1,second)
        p=proof(d);p['scannerOrigins'].append(second['url']);before=copy.deepcopy(d)
        plan=makeplan(d,p);self.assertEqual(plan['origin'],d['product']['origins'][0]['url']);self.assertEqual(d,before)
        self.assertEqual(plan['discovery'],d)
        plan['origin']=second['url']
        with self.assertRaisesRegex(ValueError,'selection drift'):validate_plan(plan,BIND)
        d['product']['origins'][0],d['product']['origins'][1]=d['product']['origins'][1],d['product']['origins'][0]
        reversed_plan=makeplan(d,p);self.assertEqual(reversed_plan['origin'],second['url']);self.assertNotEqual(reversed_plan['discoverySha256'],makeplan(before,p)['discoverySha256'])
        d['product']['origins'].append({**second,'url':'http://foreign-alias:8443'})
        with self.assertRaisesRegex(ValueError,'independently bound'):makeplan(d,p)
    def test_direct_client_uses_same_verified_candidate_order(self):
        from zap_assessment.discovery import execution_origin
        d=modern();direct=next(o for o in d['product']['origins'] if o['role']=='direct')
        d['product']['origins'].insert(0,{**direct,'url':'https://unselected.test','authorized':False})
        d['product']['origins'].append({**direct,'url':'https://127.0.0.1:9443'})
        p=proof(d);p['scannerOrigins']=[o['url'] for o in d['product']['origins'] if o['role']=='scanner'];p['directOrigins'].append('https://127.0.0.1:9443')
        validate_transport(d,BIND,p)
        with patch.object(rp.ssl,'create_default_context',return_value=None):client=rp.Product('/unused',d)
        self.assertEqual(client.origin,'https://localhost:9443');self.assertEqual(client.origin,execution_origin(d,'direct'))
    def test_legacy_multiple_origins_still_rejected(self):
        d=fixture();d['product']['origins'].append({**d['product']['origins'][0],'url':'http://second-alias:9001'})
        with self.assertRaisesRegex(ValueError,'ambiguous scanner'):compiled(d)
    def test_cleanup_consumes_same_discovery_transport(self):
        import runpy,sys,contextlib,io
        from zap_assessment import research
        d=modern()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);run=root/'evidence'/'run-1';run.mkdir(parents=True);(run/'direct').mkdir()
            (run/'PRODUCT_DISCOVERY.json').write_text(json.dumps(d))
            (run/'target-binding.json').write_text(json.dumps(BIND))
            (run/'credentials.json').write_text(json.dumps({'actors':{'A':{'email':'research-test@example.test','password':'private-unit-fixture','userId':12}}}))
            (run/'direct/registration-response.json').write_text(json.dumps({'label':'register-A','status':201,'response':{'data':{'user':{'id':12,'email':'research-test@example.test'}}}}))
            class Product:
                def request(self,method,*a,**kw):
                    return {'data':{'accessToken':'synthetic-unit-fixture'}} if method=='POST' else {'data':{'user_id':12,'accounts':[]}}
            argv=['cleanup','--evidence-root',str(root/'evidence'),'--output',str(root/'cleanup')]
            with patch.object(sys,'argv',argv),patch.object(rp,'binding',return_value=BIND),patch.object(rp,'admit_adapter') as admit,patch.object(rp,'observe_transport',return_value=proof(d)),patch.object(rp,'Product',return_value=Product()) as factory,patch.object(research,'verify_manifest'),patch.object(research,'manifest'),contextlib.redirect_stdout(io.StringIO()):
                runpy.run_path(str(rp.WORKSPACE/'zap-product-assessment/scripts/cleanup_research_accounts.py'),run_name='__main__')
            self.assertEqual(factory.call_args.kwargs['discovery'],d);admit.assert_called_once()
    def test_scope_guard_executes_alias_and_rejects_wrong_host_or_method(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=makeplan();p['origin']='http://named-container:9001';p['parameterScope']={'query':{'/v9/things':['page']}}
            with patch.object(rp,'docker',return_value=''):
                rp.install_scope_guard(SimpleNamespace(call=lambda *a,**k:None),'fake-zap',{},p,12,34,tmp)
            script=(Path(tmp)/'scope-guard.js').read_text()
            harness=r'''
const outcomes=[];
class TestURI {constructor(s){this.url=new URL(s);}getScheme(){return this.url.protocol.slice(0,-1)}getHost(){return this.url.hostname}getPort(){return this.url.port?Number(this.url.port):-1}getPath(){return this.url.pathname}getQuery(){return this.url.search.slice(1)}}
const vars={getGlobalVar:()=>0,setGlobalVar:()=>{}};const Java={type:n=>n.includes('ScriptVars')?vars:TestURI};
SCRIPT
for(const [url,method] of [['http://named-container:9001/v9/things?page=1','GET'],['http://wrong:9001/v9/things','GET'],['http://named-container:9001/v9/things','DELETE'],['http://named-container:9001/v9/things?foreign=1','GET']]){
 let uri=new URI(url),m=method;const h={getURI:()=>uri,getMethod:()=>m,setURI:x=>uri=x,setMethod:x=>m=x,setContentLength:()=>{},setHeader:()=>{}};
 const msg={getRequestHeader:()=>h,setRequestBody:()=>{}};sendingRequest(msg,0,{});outcomes.push([uri.getHost(),uri.getPath(),m]);}
console.log(JSON.stringify(outcomes));
'''.replace('SCRIPT',script)
            result=subprocess.run(['node','-e',harness],capture_output=True,text=True,check=True)
            rows=json.loads(result.stdout);self.assertEqual(rows[0],['named-container','/v9/things','GET'])
            self.assertTrue(all(x==['named-container','/__research_scope_denied__','GET'] for x in rows[1:]))
    def test_provision_uses_selected_alias_in_profile_and_whitelist(self):
        d=modern();d['product']['origins'][0]['url']='http://named-container:9001'
        d['product']['origins'].insert(1,{**d['product']['origins'][0],'url':'http://other-verified-alias:9001'})
        actors={'A':{'email':'fixture@example.test','password':'private-test-value','userId':99}}
        class Client:
            def __init__(self,*a,**k):pass
            def list_tools(self):return []
            def _next_id(self):return 1
            def _post_json(self,*a):return ('{}',None)
        class Zap:
            def __init__(self,*a):self.url=a[0]
            def call(self,*a,**k):return {}
        def docker(*args,**kwargs):
            if args[0]=='inspect' and 'Ports' in args[2]:return json.dumps({'8090/tcp':[{'HostPort':'13000'}],'7456/tcp':[{'HostPort':'13001'}]})
            if args[0]=='inspect':return 'sha256:fixture-runtime'
            if args[:2]==('image','inspect'):return 'sha256:fixture-image'
            return ''
        with tempfile.TemporaryDirectory() as tmp:
            jar=Path(tmp)/'test.jar';jar.write_bytes(b'fixture-jar')
            with patch.object(rp,'docker',side_effect=docker),patch.object(rp.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=b'',stderr=b'')),patch.object(rp,'ZapApi',Zap),patch.object(rp.gate,'McpHttpClient',Client):
                rp.provision(Path(tmp),jar,BIND,actors,d)
            profile=json.loads((Path(tmp)/'runtime/auth.yml').read_text())['mcp']['server']['auth']['bootstrap']['profiles'][0]
            self.assertEqual(profile['allowed-origin'],'http://named-container:9001')
            self.assertEqual(profile['login-url'],'http://named-container:9001/v9/session')
            self.assertEqual(profile['verification-url'],'http://named-container:9001/v9/me')
            env=dict(s.split('=',1) for s in (Path(tmp)/'runtime/mcp.env').read_text().splitlines())
            self.assertEqual(env['ZAP_URL_WHITELIST'],'named-container');self.assertEqual(env['ZAP_SCAN_JOBS_STORE_BACKEND'],'in-memory')

if __name__=='__main__':unittest.main()
