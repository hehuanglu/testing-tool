import copy
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from zap_assessment import archive_control as ac
from zap_assessment import product_workflow as pw
from zap_assessment.product_source import validate_candidate,materialize
from zap_assessment.product_binding import inspect_backend,verify_binding
from zap_assessment.product_checks import check_case,check_pages,check_checkout,check_cancel
from zap_assessment.product_bola import compile_cases,execute,cleanup_owned
from zap_assessment.product_prepare import prepare
from zap_assessment.product_native import profile,report_readback,protected_success
from zap_assessment.recipes import spring_orders
from zap_assessment.bola_research import DirectClient
from zap_assessment.bola_http import exchange
from test_research import BIND
from test_discovery_transport import modern,proof

ROOT=Path(__file__).resolve().parents[2]

def authority(d,track):
    return {'issuer':'owned control runner','scopeOrigin':'explicit-user-authorization','authorizationRef':'user prompt: owned synthetic HTTP/JSON-bearer/control fixtures',
        'notBefore':time.time()-1,'notAfter':time.time()+600,'productLocation':d['product']['location'],'environment':d['product']['environment'],
        'bindingSha256':pw.canonical_hash(d['product']['binding']),'tracks':[track],
        'operationIds':[o['id'] for o in d['operations']],'permissions':['network','read','poststate','setup','login','mutation','cleanup','active'],'secretPersistenceAccepted':True}

def workflow(d=None,track='be-authenticated',w=None,inspection=None):
    d=d or ac.discovery(ROOT,BIND,['http://owned-alias:18080'],['http://127.0.0.1:18080'])
    observed={'environment':d['product']['environment'],'targetBinding':BIND,'scannerOrigins':[o['url'] for o in d['product']['origins'] if o['role']=='scanner'],
        'directOrigins':[o['url'] for o in d['product']['origins'] if o['role']=='direct'],'observedAt':'2026-10-21T00:00:00Z','evidence':{'independentInspector':'owned control'}}
    inspection=inspection or (lambda:(BIND,observed))
    w=w or {'operationIds':['identity','list'],'permissions':['read','active'],'requests':[{'method':'GET','path':'/principal'},{'method':'GET','path':'/documents'}],
        'execution':{'crawl':'/principal','seeds':[{'method':'GET','path':'/principal','expected':[200]}], 'attacks':[{'method':'GET','path':'/documents?index=0&limit=2'}]}}
    return pw.compile_workflow(d['product']['location'],d,'archive-control/1.0',track,authority(d,track),w,inspection,'control-run'),inspection


def actor(subject='reader-owned'):
    return {'subject':subject,'runId':'control-run','credentialRef':'private:actor','sourceOperationId':'join','evidenceRefs':['register.json']}

class SourceTests(unittest.TestCase):
    def test_source_discovery_no_environment_fe_or_runtime_claim(self):
        c=spring_orders.discover(ROOT/'example');validate_candidate(c)
        self.assertEqual(len(c['operations']),18);self.assertEqual(sum(not o['protected'] for o in c['operations']),5)
        self.assertIsNone(c['environment']);self.assertIsNone(c['binding']);self.assertEqual(c['origins'],[])
        self.assertEqual(c['auth']['tokenPointer'],'/accessToken');self.assertEqual(c['auth']['identity']['subjectPointer'],'/userId')
        self.assertFalse(any('finalsource' in json.dumps(v) for v in c['operations']))
    def test_candidate_rejects_fake_environment_and_source_drift(self):
        c=spring_orders.discover(ROOT/'example');c['environment']='fake'
        with self.assertRaisesRegex(ValueError,'deployment'):validate_candidate(c)
        c=spring_orders.discover(ROOT/'example');c['sources'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'source changed'):validate_candidate(c)
    def test_materialize_requires_real_deployment(self):
        c=spring_orders.discover(ROOT/'example')
        with self.assertRaisesRegex(ValueError,'unresolved'):materialize(c,{},'',None,[])
    def test_renamed_source_folder_and_method_inventory_drift(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'renamed';shutil.copytree(ROOT/'example',dest)
            self.assertEqual(len(spring_orders.discover(dest)['operations']),18)
            p=dest/'cart/controller/CartController.java';p.write_text(p.read_text().replace('@PostMapping("/items")','@PatchMapping("/items")'))
            with self.assertRaisesRegex(ValueError,'conflict'):spring_orders.discover(dest)

    def test_spring_project_source_layout_keeps_checkout_provenance(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            dest=Path(temp)/'byteme'
            source=dest/'src/main/java/org/example'
            source.parent.mkdir(parents=True)
            shutil.copytree(ROOT/'example',source)
            candidate=spring_orders.discover(dest)
            validate_candidate(candidate)
            self.assertEqual(candidate['productLocation'],str(dest.resolve()))
            self.assertEqual(len(candidate['operations']),18)
            self.assertTrue(all(s['id'].startswith('src/main/java/org/example/') for s in candidate['sources']))
            self.assertEqual(len(spring_orders.admit(candidate,'be-authenticated')),18)

class BindingTests(unittest.TestCase):
    def fixture(self):
        selection={'transport':'docker-http/1.0','container':'chosen-backend','environment':'owned-control','network':'test-net','port':8123,'expectedBinding':BIND}
        v={'id':BIND['containerId'],'image':BIND['imageId'],'started':BIND['startedAt'],'running':True,'project':'owned-control',
            'networks':{'test-net':{'NetworkID':BIND['networkId'],'IPAddress':BIND['address'],'Aliases':['api','chosen-backend']}},
            'exposed':{'8123/tcp':{}},'ports':{'8123/tcp':[{'HostIp':'127.0.0.1','HostPort':'38477'}]}}
        return selection,v
    def test_backend_only_alias_port_no_fe(self):
        s,v=self.fixture();b,p=inspect_backend(s,lambda _:v)
        self.assertEqual(b,BIND);self.assertEqual(p['directOrigins'],['http://127.0.0.1:38477']);self.assertIn('http://api:8123',p['scannerOrigins'])
    def test_null_aliases_are_empty_not_an_unverified_alias(self):
        s,v=self.fixture();v['networks']['test-net']['Aliases']=None
        b,p=inspect_backend(s,lambda _:v);self.assertEqual(p['scannerOrigins'],['http://'+BIND['address']+':8123'])

    def test_rebound_started_image_network_port_ownership(self):
        for field in ('id','image','started','project','running','exposed','networks'):
            s,v=self.fixture();v[field]=False if field=='running' else {} if field in ('exposed','networks') else 'foreign'
            with self.subTest(field=field),self.assertRaises(ValueError):inspect_backend(s,lambda _:v)
    def test_unsupported_tls_no_fallback(self):
        s,v=self.fixture();s['transport']='docker-https'
        with self.assertRaisesRegex(ValueError,'unsupported transport'):inspect_backend(s,lambda _:v)
    def test_no_direct_lane_for_anonymous(self):
        s,v=self.fixture();v['ports']={};b,p=inspect_backend(s,lambda _:v)
        d=ac.discovery(ROOT,b,['http://api:8123'],[]);d['product']['environment']='owned-control'
        verify_binding(d,s,require_direct=False,read=lambda _:v)
        with self.assertRaises(ValueError):verify_binding(d,s,require_direct=True,read=lambda _:v)
    def test_foreign_alias_rejected(self):
        s,v=self.fixture();d=ac.discovery(ROOT,BIND,['http://foreign:8123'],[]);d['product']['environment']='owned-control'
        with self.assertRaisesRegex(ValueError,'independently bound'):verify_binding(d,s,require_direct=False,read=lambda _:v)

class AdmissionTests(unittest.TestCase):
    def test_native_protected_response_optional_reason_phrase(self):
        request = 'GET /api/cart HTTP/1.1\r\nAuthorization: Bearer owned-fixture\r\n'
        for status in ('200 OK', '200', '204 No Content', '204'):
            with self.subTest(status=status):
                self.assertTrue(protected_success({'requestHeader':request,'responseHeader':'HTTP/1.1 '+status+'\r\nContent-Type: application/json\r\n'}))
        for status in ('401', '403 Forbidden', '2000', '200garbage'):
            with self.subTest(status=status):
                self.assertFalse(protected_success({'requestHeader':request,'responseHeader':'HTTP/1.1 '+status+'\r\nContent-Type: application/json\r\n'}))
        self.assertFalse(protected_success({'requestHeader':'GET /api/cart HTTP/1.1\r\n','responseHeader':'HTTP/1.1 200\r\n'}))

    def test_unknown_recipe_before_independent_inspection_or_side_effect(self):
        spy=[];d=ac.discovery(ROOT,BIND,[],[])
        with self.assertRaisesRegex(ValueError,'unknown recipe'):pw.compile_workflow(ROOT,d,'unknown','be-authenticated',{}, {},lambda:spy.append('inspect'),'r')
        self.assertEqual(spy,[])
    def test_product_mismatch(self):
        p,i=workflow()
        with self.assertRaisesRegex(ValueError,'product mismatch'):pw.admission(ROOT/'example',p['discovery'],p['recipe'],p['track'])
    def test_authority_empty_expired_binding_source_and_operations(self):
        p,i=workflow();d=p['discovery']
        for mutate in [lambda a:a.clear(),lambda a:a.update(notAfter=0),lambda a:a.update(bindingSha256='other'),lambda a:a.update(scopeOrigin='historical-report'),lambda a:a.update(operationIds=[]),lambda a:a.update(permissions=[])]:
            a=authority(d,p['track']);mutate(a)
            with self.assertRaises(ValueError):pw.compile_workflow(ROOT,d,p['recipe'],p['track'],a,p['workload'],i,'r')
    def test_retention_not_defaulted(self):
        p,i=workflow();a=authority(p['discovery'],p['track']);a.pop('secretPersistenceAccepted')
        with self.assertRaisesRegex(ValueError,'retention'):pw.compile_workflow(ROOT,p['discovery'],p['recipe'],p['track'],a,p['workload'],i,'r')
    def test_recipe_source_authority_origin_plan_drift(self):
        p,i=workflow()
        for mutate in [lambda q:q.update(recipeSha256='bad'),lambda q:q['authority'].update(notAfter=0),lambda q:q['discovery']['operations'][0].update(method='GET')]:
            q=copy.deepcopy(p);mutate(q)
            with self.assertRaises(ValueError):pw.validate_workflow(q,i)
        with self.assertRaisesRegex(ValueError,'binding drift'):pw.validate_workflow(p,lambda:({**BIND,'startedAt':'changed'},i()[1]))
        proof=copy.deepcopy(i()[1]);proof['scannerOrigins'].append('http://foreign:99')
        with self.assertRaisesRegex(ValueError,'alias drift'):pw.validate_workflow(p,lambda:(BIND,proof))
    def test_unknown_operations_retained_as_gaps(self):
        p,i=workflow();d=p['discovery'];d['operations'].append({**d['operations'][-1],'id':'extra','pathTemplate':'/new/{id}'})
        _,cap=pw.admission(ROOT,d,p['recipe'],p['track']);self.assertEqual(cap['status'],'partial');self.assertEqual(cap['gaps'][0]['operationId'],'extra')
    def test_native_contract_and_profile_mapping(self):
        p,i=workflow();q=pw.compile_track(p,actor=actor());self.assertEqual(q['schemaVersion'],'research-plan/2.1')
        n=profile(p['discovery'],{'subject':'reader','username':'owned'},'run')
        self.assertEqual(n['token-json-pointer'],'/session/bearer');self.assertTrue(n['login-url'].endswith('/sessions'))
        self.assertEqual(n['subject-json-pointer'],'/principal/key')

class SemanticTests(unittest.TestCase):
    def test_roles_no_admin_inheritance_and_shared_catalog(self):
        policy=spring_orders.policy
        for role,relation,action,state,want in [('EMPLOYEE','nonowner','order.read','PENDING','allow'),('CUSTOMER','nonowner','order.read','PENDING','deny'),
            ('ADMIN','owner','order.read','PENDING','deny'),('CUSTOMER','shared-catalog','cart.add','PENDING','allow'),('CUSTOMER','nonowner','cart.update','PENDING','deny'),
            ('CUSTOMER','owner','order.cancel','CANCELLED','deny'),('CUSTOMER','owner','order.cancel','PENDING','allow')]:
            self.assertEqual(policy(role,relation,action,state),want)
    def test_declared_201_204_and_cancel_not_404(self):
        for status,post in [(201,{'phase':'live'}),(204,{'phase':'archived'}),(200,{'status':'CANCELLED'})]:
            e={'access':'allow','successStatuses':[status],'postEquals':{'/'+k:v for k,v in post.items()}}
            o={'response':{'status':status,'body':None},'after':post,'captureComplete':True}
            self.assertEqual(check_case(e,o)['outcome'],'matched')
            o['response']['status']=202;self.assertEqual(check_case(e,o)['outcome'],'violated')
    def test_denial_side_effect_and_unknown_projection(self):
        e={'access':'deny','denialStatuses':[403]};o={'response':{'status':403,'body':{'fault':'denied'}},'before':{'stock':10},'after':{'stock':9},'disclosed':False,'captureComplete':True}
        self.assertIn('side-effect-after-denial',check_case(e,o)['reasons'])
        o['after']=o['before'];o['captureComplete']=False;self.assertEqual(check_case(e,o)['outcome'],'inconclusive')
        e['access']='unknown';self.assertEqual(check_case(e,o)['outcome'],'inconclusive')
    def test_missing_pagination_duplicate_and_complete(self):
        pages=[{'content':[{'id':1},{'id':2}],'page':0,'size':2,'totalElements':3},{'content':[{'id':3}],'page':1,'size':2,'totalElements':3}]
        def check(p):return check_pages(p,rows='/content',page='/page',size='/size',total='/totalElements',identity='/id',expected_ids=[1,2,3])
        self.assertTrue(check(pages));self.assertFalse(check(pages[:1]));pages[1]['content'][0]['id']=1;self.assertFalse(check(pages))
    def test_checkout_stock_snapshot_cart_and_cancel_repeat(self):
        before={'stock':10};after={'stock':8,'cart':{'items':[]},'order':{'id':42,'userId':7,'status':'PENDING','items':[{'foodId':3,'quantity':2,'foodName':'meal','unitPrice':'2.50','lineTotal':'5.00'}],'totalAmount':'5.00'}}
        kw={'food_id':3,'quantity':2,'owner':7,'food_name':'meal','unit_price':'2.50'}
        self.assertTrue(check_checkout(before,after,**kw));after['cart']['items']=[1];self.assertFalse(check_checkout(before,after,**kw))
        b={'order':{'id':42,'status':'PENDING'},'stock':8};a={'order':{'id':42,'status':'CANCELLED'},'stock':10}
        self.assertTrue(check_cancel(b,a,2,copy.deepcopy(a)));again=copy.deepcopy(a);again['stock']=12;self.assertFalse(check_cancel(b,a,2,again))
    def test_delivery_dine_in_and_registration_fields(self):
        self.assertIn('tableNumber',spring_orders.checkout('DINE_IN'));self.assertNotIn('tableNumber',spring_orders.checkout('DELIVERY'))
        self.assertIn('shippingAddress',spring_orders.checkout('DELIVERY'));r=spring_orders.registration('marker','private','0901234567');self.assertIn('phone',r);self.assertIn('confirmPassword',r)

class OwnedHTTPTests(unittest.TestCase):
    def setUp(self):
        self.server=ac.ArchiveControl().start();self.temp=tempfile.TemporaryDirectory();self.out=Path(self.temp.name)
        d=ac.discovery(ROOT,BIND,['http://owned-archive:18080'],[self.server.origin]);self.p,self.inspection=workflow(d)
    def tearDown(self):self.server.close();self.temp.cleanup()
    def setup_actors(self):
        w={'operationIds':['join','login','identity'],'permissions':['setup','login','read'],'actorRefs':{'reader-one':'READER','reader-two':'READER'}}
        p,i=workflow(self.p['discovery'],w=w);prepare(p,i,self.out/'setup');return json.loads((self.out/'setup/actors.json').read_text())
    def test_common_prepare_dynamic_subject_and_no_secret_capture(self):
        actors=self.setup_actors();self.assertNotEqual(actors['reader-one']['subject'],actors['reader-two']['subject'])
        for path in (self.out/'setup/direct').rglob('*.json'):
            content=path.read_text()
            for a in actors.values():self.assertNotIn(a['password'],content);self.assertNotIn(a['token'],content)
    def test_wrong_setup_role_rejected_before_traffic(self):
        w={'operationIds':['join','login','identity'],'permissions':['setup','login','read'],'actorRefs':{'admin':'ADMIN'}}
        with self.assertRaisesRegex(ValueError,'role'):
            p,i=workflow(self.p['discovery'],w=w);prepare(p,i,self.out/'no-setup')
        self.assertEqual(self.server.requests,[])
    def test_direct_204_and_dynamic_slots(self):
        actors=self.setup_actors();client=DirectClient(self.p['discovery'],BIND,self.inspection,self.out/'direct',{'permissions':['setup','mutation','read']},actor_refs=tuple(actors),allow_empty=True);client.set_tokens(actors)
        req=lambda oid,m,path,b=None:{'operationRef':oid,'method':m,'path':path,'body':b}
        s,b,_=client.request('create','reader-one',req('create','POST','/documents',{'title':'owned'}),'setup');self.assertEqual(s,201);key=b['entry']['key']
        s,b,_=client.request('remove','reader-one',req('remove','DELETE','/documents/'+key),'mutation');self.assertEqual((s,b),(204,None))
        self.assertEqual(client.request('read','reader-one',req('read','GET','/documents/'+key),'read')[1]['entry']['phase'],'archived')
    def test_unknown_outcome_not_replayed(self):
        actors=self.setup_actors();client=DirectClient(self.p['discovery'],BIND,self.inspection,self.out/'direct',{'permissions':['mutation']},actor_refs=tuple(actors));client.set_tokens(actors)
        request={'operationRef':'create','method':'POST','path':'/documents','body':{'title':'owned'}}
        with patch('zap_assessment.bola_research.exchange',side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):client.request('same','reader-one',request,'mutation')
        with self.assertRaisesRegex(ValueError,'allocation'):client.request('same','reader-one',request,'mutation')
        self.assertTrue(any('unknown-outcome'==json.loads(line)['kind'] for line in (self.out/'direct/journal.jsonl').read_text().splitlines()))
    def test_common_bola_role_policy_and_soft_delete(self):
        actors=self.setup_actors();one=actors['reader-one'];two=actors['reader-two'];headers={'Authorization':'Bearer '+one['token'],'Content-Type':'application/json'}
        s,b,_=exchange(self.server.origin,'POST','/documents',headers,json.dumps({'title':'original'}).encode(),5)
        key=b['entry']['key'];request=lambda oid,m,body=None:{'operationRef':oid,'method':m,'path':'/documents/'+key,'body':body}
        ad={k:{'subject':v['subject'],'role':v['role'],'identityRequest':v['identityRequest'],'subjectPointer':v['subjectPointer']} for k,v in actors.items()}
        base={'observerRef':'reader-one','resourceRef':'document','state':'live','policyEvidenceRefs':['archive-source'],
              'beforeRequest':request('read','GET'),'afterRequest':request('read','GET'),'projectionFields':['entry','fault'], 'disclosurePointer':'/entry/key','disclosureValue':key}
        cases=[{**base,'id':'cross-read','actorRef':'reader-two','relation':'nonowner','action':'read','request':request('read','GET')},
               {**base,'id':'rename','actorRef':'reader-one','relation':'owner','action':'rename','request':request('rename','PATCH',{'title':'renamed'}),'postEquals':{'/entry/title':'renamed'}},
               {**base,'id':'archive','actorRef':'reader-one','relation':'owner','action':'remove','request':request('remove','DELETE'),'postEquals':{'/entry/phase':'archived'}}]
        w={'operationIds':['identity','read','rename','remove'],'permissions':['read','poststate','mutation'],'actors':ad,'resources':{'document':{'ownerRef':'reader-one','wireId':key,'creationEvidence':'owned create receipt','idPointer':'/entry/key','ownerPointer':'/entry/owner','statePointer':'/entry/phase'}},'cases':cases,'policyAcceptanceRefs':['owned control fixed policy']}
        for case in cases:
            case['requestTemplate']={**case['request'],'path':'/documents/{key}'};case['idLocations']=[{'location':'path','name':'key'}]
        p,i=workflow(self.p['discovery'],track='bola-ownership',w=w);result=execute(p,i,self.out/'bola',actors)
        self.assertEqual(result['securityVerdict'],'no-violation-in-tested-cases');self.assertTrue(result['notZapAlerts']);self.assertEqual(result['source'],'direct')
        checks=json.loads((self.out/'bola/CHECKS.json').read_text());self.assertEqual([x['outcome'] for x in checks],['matched']*3)
    def test_cleanup_ownership_and_unknown_no_replay(self):
        calls=[]
        class Client:
            def request(self,*args):calls.append(args)
        for row in [{'runId':'foreign','creationEvidence':'created','wireId':'doc1','state':'retained'}, {'runId':'control-run','creationEvidence':'created','wireId':'doc1','state':'unknown'}]:
            with self.assertRaises(ValueError):cleanup_owned(self.p,self.inspection,[row],Client(),'control-run')
        self.assertEqual(calls,[])

if __name__=='__main__':unittest.main()
