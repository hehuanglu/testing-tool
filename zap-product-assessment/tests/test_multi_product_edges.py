import copy
import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_multi_product import workflow,authority,ROOT,actor
from test_discovery_transport import modern
from test_research import BIND,FakeClient,FakeZap
from zap_assessment import product_workflow as pw
from zap_assessment.recipes import spring_orders
from zap_assessment.product_cli import main
from zap_assessment.product_native import report_readback
from zap_assessment.product_bola import compile_cases
from zap_assessment.research import ResearchRun

class EdgeTests(unittest.TestCase):
    def test_source_status_and_templates_no_network_or_fe(self):
        candidate=spring_orders.discover(ROOT/'example')
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'candidate.json';path.write_text(json.dumps(candidate))
            for command in ('status','templates'):
                with patch('zap_assessment.product_cli.verify_binding',side_effect=AssertionError('network forbidden')),contextlib.redirect_stdout(io.StringIO()) as output:
                    code=main([command,'--product',str(ROOT/'example'),'--discovery',str(path),'--recipe','spring-orders/1.0','--track','be-anonymous'])
                self.assertEqual(code,0)
                if command=='status':self.assertEqual(json.loads(output.getvalue())['executionStatus'],'not-run')
                else:self.assertIn('fixtureDAG',json.loads(output.getvalue()))
    def test_common_anonymous_no_actor_token_propagation_and_identity_rejection(self):
        p,i=workflow();d=p['discovery'];cases=[{'id':'denial','operationId':'identity','method':'GET','path':'/principal','body':None,'fixtureRefs':[],'category':'protected-denial',
                                             'expected':{'statuses':[401],'contentType':'application/json','equals':{},'present':[]}}]
        w={'operationIds':['identity'],'permissions':['read'],'cases':cases,'campaigns':[],
           'dispositions':[{'operationId':o['id'],'disposition':'protected-denial' if o['id']=='identity' else 'conditional','reason':'bounded selected recipe'} for o in d['operations']]}
        a=authority(d,'be-anonymous');q=pw.compile_workflow(ROOT,d,p['recipe'],'be-anonymous',a,w,i,'anon-control');native=pw.compile_track(q)
        self.assertNotIn('actor',native);self.assertFalse(native['anonymousState']['propagateIdentity'])
        w['cases'][0]['headers']={'Authorization':'private'}
        with self.assertRaises(ValueError):pw.compile_workflow(ROOT,d,p['recipe'],'be-anonymous',a,w,i,'r')
    def test_auth_request_beyond_declared_subset_rejected_before_setup(self):
        p,i=workflow();w=copy.deepcopy(p['workload']);w['execution']['seeds'][0]['path']='/documents/new'
        with self.assertRaisesRegex(ValueError,'subset'):pw.compile_workflow(ROOT,p['discovery'],p['recipe'],p['track'],p['authority'],w,i,'r')
    def test_mutation_permission_cannot_be_omitted(self):
        p,i=workflow();w=copy.deepcopy(p['workload']);w['operationIds'].append('create');w['requests'].append({'method':'POST','path':'/documents'})
        with self.assertRaisesRegex(ValueError,'mutation authority'):pw.compile_workflow(ROOT,p['discovery'],p['recipe'],p['track'],p['authority'],w,i,'r')
    def test_common_finalsource_recipe_compiles_same_contract(self):
        from zap_assessment.research_product import SURFACE
        d=modern();d['sources'].append({'id':'runtime','kind':'runtime','location':'owned-fixture:deployment','sha256':None,'observedAt':'now','confidence':'high'});d['product']['environmentEvidenceRefs']=['runtime'];d['product']['location']=str(ROOT);d['operations']=[]
        for n,(method,path) in enumerate(sorted(SURFACE)):
            d['operations'].append({'id':'o'+str(n),'method':method,'pathTemplate':path,'protected':path.startswith('/api/v1/'),'semantics':'legacy compatibility fixture','input':{},'evidenceRefs':['source'],'confidence':'high'})
        lookup={(o['method'],o['pathTemplate']):o['id'] for o in d['operations']}
        d['auth'].update(loginOperationId=lookup['POST','/api/auth/login'],usernameField='email',passwordField='password',tokenPointer='/data/accessToken')
        d['auth']['identity'].update(operationId=lookup['GET','/api/v1/accounts'],subjectPointer='/data/user_id',actorSource={'operationId':lookup['POST','/api/auth/register'],'subjectPointer':'/data/user/id'})
        d['fixtures'][0]['operationIds']=[o['id'] for o in d['operations'] if o['protected'] and o['method']!='GET']
        proof={'environment':d['product']['environment'],'targetBinding':BIND,'scannerOrigins':[o['url'] for o in d['product']['origins'] if o['role']=='scanner'],
               'directOrigins':[o['url'] for o in d['product']['origins'] if o['role']=='direct'],'observedAt':'now','evidence':{'control':'independent fixture'}}
        w={'operationIds':[lookup['GET','/api/v1/accounts']],'permissions':['read','active'],'requests':[{'method':'GET','path':'/api/v1/accounts'}],
           'execution':{'crawl':'/api/v1/accounts','seeds':[{'method':'GET','path':'/api/v1/accounts','expected':[200]}],'attacks':[{'method':'GET','path':'/api/v1/accounts'}]}}
        p=pw.compile_workflow(ROOT,d,'finalsource-ledger/1.0','be-authenticated',authority(d,'be-authenticated'),w,lambda:(BIND,proof),'r')
        a=actor();a['sourceOperationId']=lookup['POST','/api/auth/register'];q=pw.compile_track(p,actor=a)
        self.assertEqual(q['identityPath'],'/api/v1/accounts');self.assertEqual(q['schemaVersion'],'research-plan/2.1')
    def test_report_readback_real_chunk_protocol_and_hash_rejection(self):
        class Run:
            plan={'origin':'http://owned'}
            def __init__(self,bad=False):self.bad=bad;self.calls=[]
            def tool(self,name,args):
                self.calls.append((name,args))
                fmt='json' if args.get('format')=='json' else 'html'
                if name=='zap_report_generate':return 'Path: /zap/wrk/report.'+fmt
                blob='{"alerts":[]}' if args['reportPath'].endswith('json') else '<html>control</html>'
                start=args['offset'];part=blob[start:start+4];end=start+len(part)==len(blob)
                return json.dumps({'reportPath':args['reportPath'],'offset':start,'nextOffset':None if end else start+len(part),'charactersReturned':len(part),'endOfFile':end,'totalCharacters':len(blob),
                   'offsetUnit':'unicodeCodePoints','artifactSha256':'bad' if self.bad else hashlib.sha256(blob.encode()).hexdigest(),'content':part})
        with tempfile.TemporaryDirectory() as tmp:
            r=Run();report_readback(r,tmp);self.assertEqual(json.loads((Path(tmp)/'report.json').read_text()),{'alerts':[]})
            self.assertTrue(any('expectedSha256' in args for n,args in r.calls))
        with tempfile.TemporaryDirectory() as tmp,self.assertRaises(Exception):report_readback(Run(True),tmp)
    def test_wrong_subject_and_auth_loss_existing_native_monitor(self):
        p,i=workflow();q=pw.compile_track(p,actor=actor())
        with tempfile.TemporaryDirectory() as tmp:
            client=FakeClient();r=ResearchRun(plan=q,binding=lambda:BIND,client=client,monitor_client=client,zap=FakeZap(),output=tmp);r.session='owned'
            self.assertFalse(r.validate(client))
            with self.assertRaises(RuntimeError):r.current()
    def test_unknown_projection_policy_not_pass_flags_or_executor_evaluate(self):
        from zap_assessment.product_checks import check_case
        e={'access':'deny','denialStatuses':[403]};o={'response':{'status':403,'body':{}},'before':{},'after':{},'disclosed':False,'captureComplete':False,'pass':True}
        with patch('zap_assessment.bola_research.evaluate',side_effect=AssertionError('forbidden oracle')):
            self.assertEqual(check_case(e,o)['outcome'],'inconclusive')
    def test_employee_cannot_use_customer_cart_identity(self):
        with self.assertRaisesRegex(ValueError,'CUSTOMER-only'):spring_orders.validate_actor({'role':'EMPLOYEE','identityRequest':{'operationRef':'cart.read'}})

if __name__=='__main__':unittest.main()

class AdditionalGuardTests(unittest.TestCase):
    def test_native_mutation_needs_real_oracle_before_side_effect(self):
        p,i=workflow();w=copy.deepcopy(p['workload']);w['operationIds'].append('create');w['permissions']+=['mutation','poststate'];w['requests'].append({'method':'POST','path':'/documents'})
        w['execution']['seeds'].append({'method':'POST','path':'/documents','body':{'title':'test'},'expected':[201]})
        with self.assertRaisesRegex(ValueError,'business oracle'):pw.compile_workflow(ROOT,p['discovery'],p['recipe'],p['track'],p['authority'],w,i,'native-control')
    def test_native_poststate_assertion_catches_effect(self):
        from zap_assessment.product_native import check_native_assertion
        check_native_assertion({'unchanged':True},{'stock':1},{'stock':1})
        with self.assertRaises(ValueError):check_native_assertion({'unchanged':True},{'stock':1},{'stock':0})
        with self.assertRaises(ValueError):check_native_assertion({'postEquals':{'/phase':'archived'}},{},{'phase':'live'})
    def test_collection_incomplete_stays_inconclusive_even_200(self):
        from zap_assessment.product_checks import check_case
        e={'access':'allow','successStatuses':[200],'pagination':{'rows':'/content','page':'/page','size':'/size','total':'/totalElements','identity':'/id','expected_ids':[1,2]}}
        o={'response':{'status':200,'body':{}},'captureComplete':True,'pages':[{'content':[{'id':1}],'page':0,'size':1,'totalElements':2}]}
        self.assertEqual(check_case(e,o)['outcome'],'inconclusive')
    def test_auth_map_drift_no_inspection_or_setup(self):
        p,i=workflow();d=copy.deepcopy(p['discovery']);d['auth']['usernameField']='changed';spy=[]
        with self.assertRaisesRegex(ValueError,'mapping'):pw.compile_workflow(ROOT,d,p['recipe'],p['track'],p['authority'],p['workload'],lambda:spy.append(1),'r')
        self.assertEqual(spy,[])
    def test_candidate_status_product_mismatch(self):
        c=spring_orders.discover(ROOT/'example')
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'c.json';path.write_text(json.dumps(c))
            with self.assertRaisesRegex(ValueError,'mismatch'):main(['status','--product',str(ROOT/'finalsource'),'--discovery',str(path),'--recipe','spring-orders/1.0','--track','be-anonymous'])

class RelatedPostStateTests(unittest.TestCase):
    def test_denial_order_unchanged_but_stock_changed_is_detected(self):
        from zap_assessment.product_checks import check_case
        e={'access':'deny','denialStatuses':[403]};o={'response':{'status':403,'body':{}},'before':{'status':'PENDING'},'after':{'status':'PENDING'},'relatedBefore':{'stock':10},'relatedAfter':{'stock':9},'disclosed':False,'captureComplete':True}
        self.assertIn('side-effect-after-denial',check_case(e,o)['reasons'])
    def test_unknown_auth_only_blocks_dependent_track(self):
        p,_=workflow();d=p['discovery'];d['auth']=None
        self.assertTrue(pw.admission(ROOT,d,p['recipe'],'be-anonymous')[1]['supportedOperationIds'])
        with self.assertRaisesRegex(ValueError,'auth'):pw.admission(ROOT,d,p['recipe'],'be-authenticated')

class NativeCapabilityProofTests(unittest.TestCase):
    def test_unproved_native_body_attack_rejected_before_setup(self):
        p,i=workflow();w=copy.deepcopy(p['workload']);w['operationIds'].append('create');w['permissions']+=['mutation','poststate']
        w['execution']['attacks'].append({'method':'POST','path':'/documents','body':{'title':'owned'}})
        with self.assertRaisesRegex(ValueError,'guard delivery proof missing'):pw.compile_workflow(ROOT,p['discovery'],p['recipe'],p['track'],p['authority'],w,i,'native-body-blocked')
        self.assertEqual(p['capability']['nativeActiveVectors'],['query']);self.assertTrue(all(a['method']=='GET' for a in pw.compile_track(p,actor=actor())['execution']['attacks']))
