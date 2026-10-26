import copy,unittest
from test_multi_product import workflow
from zap_assessment.product_workflow import validate_path_actions,compile_workflow
from zap_assessment.product_native import check_path_delivery

class AuthenticatedPathTests(unittest.TestCase):
    def fixture(self):
        p,i=workflow();w=copy.deepcopy(p['workload'])
        w.update(operationIds=['identity','read'],nativeControl=True,pathAttackIndices=[0])
        w['execution']={'crawl':'/principal','seeds':[{'method':'GET','path':'/documents/42','expected':[200]}],'attacks':[{'method':'GET','path':'/documents/42'}]}
        return p,i,w
    def test_write_query_multiselector_and_unproved_path_stay_denied(self):
        p,i,w=self.fixture();validate_path_actions(p['discovery'],w)
        for delta in ({'method':'DELETE'},{'path':'/documents/key'},{'path':'/documents/42?index=0'},{'body':{} }):
            bad=copy.deepcopy(w);bad['execution']['attacks'][0].update(delta)
            with self.subTest(delta=delta),self.assertRaises(ValueError):validate_path_actions(p['discovery'],bad)
        for indices in ([],[True],[0,0],[1],[-1],None):
            bad=copy.deepcopy(w);bad['pathAttackIndices']=indices
            with self.subTest(indices=indices),self.assertRaises(ValueError):validate_path_actions(p['discovery'],bad)
        bad=copy.deepcopy(w);bad.pop('nativeControl')
        with self.assertRaisesRegex(ValueError,'proof required'):validate_path_actions(p['discovery'],bad)
        with self.assertRaisesRegex(ValueError,'owned fixture'):compile_workflow(p['productLocation'],p['discovery'],p['recipe'],p['track'],p['authority'],w,i,'control')
    def test_wire_oracle_requires_real_changed_scoped_attributed_authenticated_messages(self):
        action={'method':'GET','path':'/documents/42'}
        def message(path='/documents/42%27',rule=40018,status=400):
            return {'id':'1','requestHeader':f'GET http://owned{path} HTTP/1.1\r\nAuthorization: Bearer owned\r\nX-ZAP-Scan-ID: {rule}\r\n','requestBody':'','responseHeader':f'HTTP/1.1 {status}\r\n'}
        result=check_path_delivery('/documents/{key}',action,[message()],'http://owned',[40018]);self.assertEqual(result['deliveredPathMessages'],1)
        for m in (message('/documents/43'),message('/foreign/42%27'),message('/documents/42%27?secret=x'),message(rule=40012),message(status=401),message('/documents/42')):
            with self.subTest(m=m),self.assertRaises(ValueError):check_path_delivery('/documents/{key}',action,[m],'http://owned',[40018])
        bad=message();bad['requestHeader']=bad['requestHeader'].replace('Authorization: Bearer owned\r\n','')
        with self.assertRaises(ValueError):check_path_delivery('/documents/{key}',action,[bad],'http://owned',[40018])

    def test_write_selector_needs_method_baseline_ownership_and_oracle_before_proof(self):
        p,i,w=self.fixture();a={'method':'DELETE','path':'/documents/42'}
        w['execution']['attacks']=[a];w['execution']['seeds']=[{**a,'expected':[204]}]
        w['requests']=[{'method':'GET','path':'/principal'},{**a,'fixtureOwned':True,'fixtureRefs':['owned']}]
        w['nativeAssertions']={'attack-0':{'reads':[{'operationRef':'read','method':'GET','path':'/documents/42','body':None}],'unchanged':True}}
        validate_path_actions(p['discovery'],w)
        for field in ('nativeAssertions','requests'):
            bad=copy.deepcopy(w);bad[field]={} if field=='nativeAssertions' else []
            with self.assertRaisesRegex(ValueError,'owned fixture'):validate_path_actions(p['discovery'],bad)
        bad=copy.deepcopy(w);bad.pop('nativeControl')
        with self.assertRaisesRegex(ValueError,'proof required'):validate_path_actions(p['discovery'],bad)
