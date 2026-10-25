import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from test_multi_product import workflow
from zap_assessment.product_workflow import validate_body_action,compile_workflow
from zap_assessment.product_native import check_transition
from zap_assessment.product_identity import strategy,check_identity
from zap_assessment.recipes import archive,spring_orders
from zap_assessment.research import ResearchRun
from test_research import BIND,FakeClient,FakeZap

class BodyTests(unittest.TestCase):
    def workload(self):
        p,i=workflow();w=copy.deepcopy(p['workload']);w['operationIds']+=['rename','read'];w['permissions']+=['mutation','poststate']
        w['nativeControl']=True;w['mutableBodyFields']={'rename':['title']}
        action={'method':'PATCH','path':'/documents/owned','body':{'title':'valid','reference':'owned'}};w['execution']['attacks']=[action]
        w['execution']['seeds'].append({**copy.deepcopy(action),'expected':[200]})
        w['nativeAssertions']={'attack-0':{'reads':[{'operationRef':'read','method':'GET','path':'/documents/owned','body':None}],
          'transition':{'field':'title','statePointer':'/read/entry/title','responsePointer':'/entry/title','fixedState':{'/read/entry/key':'owned'},'acceptedStatuses':[200],'rejectedStatuses':[422]}}}
        return p,i,w,action
    def test_rejected_trailing_seed_cannot_become_active_baseline(self):
        p,i,w,a=self.workload()
        w['execution']['seeds'].append({**copy.deepcopy(a),'body':{'title':None,'reference':'owned'},'expected':[422]})
        with self.assertRaisesRegex(ValueError,'valid accepted baseline'):validate_body_action(p['discovery'],archive,w,a)
        w['execution']['seeds'].append({**copy.deepcopy(a),'expected':[200]})
        self.assertEqual(validate_body_action(p['discovery'],archive,w,a)['id'],'rename')
        w['execution']['seeds'][1]['body']['reference']='other'
        with self.assertRaisesRegex(ValueError,'fixed reference drift'):validate_body_action(p['discovery'],archive,w,a)
    def test_flat_mapping_and_unknown_shapes_rejected_before_dispatch(self):
        p,i,w,a=self.workload();self.assertEqual(validate_body_action(p['discovery'],archive,w,a)['id'],'rename')
        for body in ([1],{'title':{'nested':'x'}},{'title':['x']},{}):
            changed=copy.deepcopy(a);changed['body']=body;w['execution']['attacks']=[changed]
            with self.assertRaisesRegex(ValueError,'shape'):validate_body_action(p['discovery'],archive,w,changed)
        w['execution']['attacks']=[a];w['mutableBodyFields']['rename']=['reference']
        with self.assertRaisesRegex(ValueError,'mapping'):validate_body_action(p['discovery'],archive,w,a)
    def test_control_owner_and_body_proof_cannot_be_self_granted(self):
        p,i,w,a=self.workload()
        with self.assertRaisesRegex(ValueError,'owned fixture'):compile_workflow(p['productLocation'],p['discovery'],p['recipe'],p['track'],p['authority'],w,i,'r')
        w.pop('nativeControl')
        with self.assertRaisesRegex(ValueError,'proof missing'):validate_body_action(p['discovery'],archive,w,a)
        w['nativeBodyProof']={'path':'absent','sha256':'0'*64}
        with self.assertRaises(OSError):validate_body_action(p['discovery'],archive,w,a)
    def test_response_rejection_and_last_accepted_state_oracle(self):
        p,i,w,a=self.workload();c=w['nativeAssertions']['attack-0']['transition'];before={'read':{'entry':{'key':'owned','title':'valid'}}};after={'read':{'entry':{'key':'owned','title':'mutated'}}}
        def message(mid,value,status):
            return {'id':mid,'requestHeader':'PATCH http://owned/documents/owned HTTP/1.1\r\nAuthorization: Bearer test\r\nX-ZAP-Scan-ID: 40012\r\n','requestBody':json.dumps({'title':value,'reference':'owned'}),'responseHeader':'HTTP/1.1 '+str(status)+'\r\n','responseBody':json.dumps({'entry':{'title':value}} if status==200 else {'problem':{'detail':'invalid'}})}
        messages=[message(1,'mutated',200),message(2,23,422)]
        r=check_transition(c,before,after,messages,a,'http://owned');self.assertEqual((r['acceptedResponses'],r['rejectedResponses'],r['deliveredBodyMessages']),(1,1,2))
        bad=copy.deepcopy(after);bad['read']['entry']['title']='unexpected'
        with self.assertRaisesRegex(ValueError,'final state'):check_transition(c,before,bad,messages,a,'http://owned')
        messages[0]['requestBody']=json.dumps({'title':'mutated','reference':'foreign'})
        with self.assertRaisesRegex(ValueError,'reference escaped'):check_transition(c,before,after,messages,a,'http://owned')

class IdentityTests(unittest.TestCase):
    def test_recipe_mapping_different_role_subject_wrong_and_loss(self):
        p,_=workflow();m=strategy(archive,p['discovery'],'LIBRARIAN',imported=True)
        check_identity(200,'application/json',{'principal':{'key':'staff-owned','tier':'LIBRARIAN'}},'staff-owned','LIBRARIAN',m)
        for status,body in [(200,{'principal':{'key':'other','tier':'LIBRARIAN'}}),(200,{'principal':{'key':'staff-owned','tier':'READER'}}),(401,{}),(200,{})]:
            with self.assertRaises((ValueError,KeyError)):check_identity(status,'application/json',body,'staff-owned','LIBRARIAN',m)
        with self.assertRaisesRegex(ValueError,'unsupported'):strategy(spring_orders,p['discovery'],'EMPLOYEE',imported=True)
        with self.assertRaisesRegex(ValueError,'unsupported'):strategy(archive,p['discovery'],'UNREVIEWED',imported=True)
    def test_native_callback_failure_latches_and_prevents_next_start(self):
        p,i=workflow();from test_multi_product import actor
        from zap_assessment.product_workflow import compile_track
        q=compile_track(p,actor=actor());client=FakeClient()
        class Positive:
            def call_tool(self,*args):return 'Valid: true'
        with tempfile.TemporaryDirectory() as tmp:
            run=ResearchRun(plan=q,binding=lambda:BIND,client=Positive(),monitor_client=client,zap=FakeZap(),output=tmp,identity_validator=lambda r:False)
            run.session='owned';self.assertFalse(run.validate(run.client));self.assertTrue(run.lost.is_set())
            with self.assertRaises(RuntimeError):run.current()

class ImportTests(unittest.TestCase):
    def test_private_import_controls_and_swapped_credential(self):
        import hashlib
        from zap_assessment.archive_control import ArchiveControl,discovery
        from zap_assessment.product_identity import import_actor,verify_import
        from test_multi_product import ROOT
        from zap_assessment.product_prepare import verify_actor
        seed={'members':{'keeper':{'key':'staff-owned','role':'LIBRARIAN','password':'private-owned'},'reader':{'key':'reader-owned','role':'READER','password':'private-reader'}}}
        server=ArchiveControl(seed=seed).start()
        try:
            d=discovery(ROOT,BIND,['http://owned-control:18080'],[server.origin]);p,i=workflow(d)
            with tempfile.TemporaryDirectory() as tmp:
                root=Path(tmp);source=root/'seed.json';source.write_text(json.dumps(seed))
                credential={'username':'keeper','password':'private-owned','subject':'staff-owned','role':'LIBRARIAN','sourceEvidence':[{'path':str(source),'sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'subjectPointer':'/members/keeper/key','rolePointer':'/members/keeper/role'}]}
                result=import_actor(p,i,root/'valid',credential);self.assertEqual(result['executionStatus'],'imported')
                actor=json.loads((root/'valid/actor.json').read_text());verify_actor(actor);verify_import(actor)
                # A valid other credential cannot satisfy the independently pinned subject.
                swapped={**credential,'username':'reader','password':'private-reader'}
                with self.assertRaisesRegex(ValueError,'wrong protected actor'):import_actor(p,i,root/'swapped',swapped)
                wrong=copy.deepcopy(actor);wrong['role']='READER'
                with self.assertRaisesRegex(ValueError,'binding'):verify_actor(wrong)
                for path in (root/'valid/direct').rglob('*.json'):
                    content=path.read_text();self.assertNotIn('private-owned',content);self.assertNotIn(actor['token'],content)
        finally:server.close()
