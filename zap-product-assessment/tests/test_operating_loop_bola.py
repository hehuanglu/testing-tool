import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.recipes import spring_orders
from zap_assessment.product_checks import check_case
from zap_assessment.product_bola import compile_cases
from test_multi_product import workflow

class StatePolicyTests(unittest.TestCase):
 def decision(self,role,action,state,next_state=None,kind='DELIVERY',relation='nonowner'):
  return spring_orders.expected_case(role,relation,action,state,{'body':{'status':next_state}},{'typeValue':kind,'typePointer':'/orderType'})
 def test_granted_role_does_not_allow_invalid_transition_or_inherit_other_roles(self):
  self.assertEqual(self.decision('EMPLOYEE','order.confirm','PENDING')['access'],'allow')
  self.assertEqual(self.decision('EMPLOYEE','order.confirm','CONFIRMED')['denialStatuses'],[409])
  self.assertEqual(self.decision('EMPLOYEE','order.status','SHIPPING','CANCELLED')['denialStatuses'],[409])
  self.assertEqual(self.decision('EMPLOYEE','order.status','PROCESSING','SHIPPING',kind='DINE_IN')['denialStatuses'],[409])
  self.assertEqual(self.decision('EMPLOYEE','order.status','PROCESSING','SHIPPING')['access'],'allow')
  self.assertEqual(self.decision('EMPLOYEE','order.status','COMPLETED','PROCESSING')['denialStatuses'],[409])
  self.assertEqual(self.decision('ADMIN','order.status','PENDING','CONFIRMED')['denialStatuses'],[403])
  self.assertEqual(self.decision('ANONYMOUS','order.read','PENDING')['denialStatuses'],[401])
  self.assertEqual(self.decision('CUSTOMER','cart.update','PENDING')['denialStatuses'],[404])
 def test_missing_type_and_bad_next_state_are_not_silent_allow(self):
  with self.assertRaisesRegex(ValueError,'type provenance'):spring_orders.expected_case('EMPLOYEE','nonowner','order.status','PROCESSING',{'body':{'status':'SHIPPING'}},{})
  self.assertEqual(self.decision('EMPLOYEE','order.status','PENDING','PENDING')['denialStatuses'],[400])

class CreatedResourceOracleTests(unittest.TestCase):
 def test_created_key_is_bound_from_ack_then_read_through_frozen_route(self):
  from zap_assessment.archive_control import ArchiveControl,discovery
  from zap_assessment.product_prepare import prepare
  from zap_assessment.product_bola import execute
  from test_multi_product import ROOT
  from test_research import BIND
  server=ArchiveControl().start()
  try:
   with tempfile.TemporaryDirectory() as temp:
    root=Path(temp);d=discovery(ROOT,BIND,['http://owned:18080'],[server.origin]);setup={'operationIds':['join','login','identity'],'permissions':['setup','login','read'],'actorRefs':{'reader':'READER'}}
    p,i=workflow(d,w=setup);prepare(p,i,root/'actors');actors=json.loads((root/'actors/actors.json').read_text());actor=actors['reader']
    identity=actor['identityRequest'];request={'operationRef':'create','method':'POST','path':'/documents','body':{'title':'fresh'}}
    case={'id':'create-then-read','actorRef':'reader','observerRef':'reader','resourceRef':'principal','state':'live','relation':'owner','action':'create','request':request,'requestTemplate':request,'idLocations':[],'beforeRequest':identity,'afterRequest':identity,'postUnchanged':True,'policyEvidenceRefs':['archive-source'],'responseEquals':{'/entry/owner':actor['subject']},'createdResourceRead':{'request':{'operationRef':'read','method':'GET','path':'/documents/{key}','body':None},'responseIdPointer':'/entry/key','pathParameter':'key','idPointer':'/entry/key','ownerPointer':'/entry/owner','expectedOwner':actor['subject']}}
    w={'operationIds':['identity','create','read'],'permissions':['read','mutation','poststate'],'actors':{'reader':{k:actor[k] for k in ('subject','role','identityRequest','subjectPointer')}},'resources':{'principal':{'ownerRef':'reader','wireId':actor['subject'],'creationEvidence':actor['provenance']['evidenceRefs'],'implicitOwnerPointer':'/principal/key'}},'cases':[case]}
    p,i=workflow(d,track='bola-ownership',w=w);result=execute(p,i,root/'bola',actors);self.assertEqual(result['executionStatus'],'completed')
    checks=json.loads((root/'bola/CHECKS.json').read_text());self.assertEqual(checks[0]['outcome'],'matched')
    observations=json.loads((root/'bola/OBSERVATIONS.json').read_text());self.assertEqual(observations[0]['createdRead']['body']['entry']['title'],'fresh')
    self.assertEqual(sum(r['method']=='POST' and r['path']=='/documents' for r in server.requests),1)
    bad=copy.deepcopy(p);bad['workload']['cases'][0]['createdResourceRead']['request']['path']='/foreign/{key}'
    with self.assertRaises(ValueError):compile_cases(bad)
  finally:server.close()

 def test_readback_owner_identity_and_checkout_stock_are_independent_of_success_status(self):
  order={'id':91,'userId':7,'status':'PENDING','items':[{'foodId':13,'quantity':2,'foodName':'dedicated','unitPrice':'2.50','lineTotal':'5.00'}],'totalAmount':'5.00'}
  e={'access':'allow','successStatuses':[201],'postEquals':{'/items':[]},'createdResourceRead':{'idPointer':'/id','ownerPointer':'/userId','responseIdPointer':'/id','expectedOwner':7},'checkout':{'food_id':13,'quantity':2,'owner':7,'food_name':'dedicated','unit_price':'2.50','stockPointer':'/stock/stockQuantity'}}
  o={'response':{'status':201,'body':copy.deepcopy(order)},'before':{'items':[{'id':1}]},'after':{'items':[]},'createdRead':{'status':200,'body':copy.deepcopy(order)},'relatedBefore':{'stock':{'stockQuantity':10}},'relatedAfter':{'stock':{'stockQuantity':8}},'captureComplete':True}
  self.assertEqual(check_case(e,o)['outcome'],'matched')
  for field,value in [('id',92),('userId',8)]:
   bad=copy.deepcopy(o);bad['createdRead']['body'][field]=value;self.assertEqual(check_case(e,bad)['outcome'],'violated')
  bad=copy.deepcopy(o);bad['relatedAfter']['stock']['stockQuantity']=9;self.assertIn('checkout-state',check_case(e,bad)['reasons'])
  bad=copy.deepcopy(o);bad.pop('createdRead');self.assertEqual(check_case(e,bad)['outcome'],'inconclusive')

class SignedBolaPipelineTests(unittest.TestCase):
 def test_real_signed_actor_and_anonymous_controls_use_common_pipeline(self):
  import hashlib
  from zap_assessment.archive_control import ArchiveControl,discovery,fixture_signing_key
  from zap_assessment.product_identity import import_actor
  from zap_assessment.product_bola import execute
  from zap_assessment.product_workflow import canonical_hash
  from zap_assessment.bola_http import exchange
  from test_multi_product import ROOT
  from test_research import BIND
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);jwt,pub=fixture_signing_key(root/'keys')
   seed={'jwt':jwt,'members':{'reader':{'key':'reader-control','role':'READER','password':'control-reader'},'curator':{'key':'curator-control','role':'CURATOR','password':'control-curator'}}}
   server=ArchiveControl(seed=seed).start()
   try:
    d=discovery(ROOT,BIND,['http://owned-alias:18080'],[server.origin]);source=root/'subjects.json';source.write_text(json.dumps({'members':seed['members']}));trustsource=root/'trust.json';trustsource.write_text(json.dumps({'targetBinding':BIND,'publicKeySha256':hashlib.sha256(pub.read_bytes()).hexdigest()}))
    ref=lambda p:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
    trust={'publicKey':ref(pub),'bindingSha256':canonical_hash(BIND),'sourceEvidence':[ref(trustsource)]};actors={}
    for name,role,probe in [('reader','READER','identity'),('curator','CURATOR','access')]:
     w={'actorRole':role,'operationIds':[probe],'permissions':['read','login'],'requests':[{'method':'GET','path':'/principal' if probe=='identity' else '/access'}],'execution':{'crawl':'/principal' if probe=='identity' else '/access','seeds':[],'attacks':[]}}
     p,i=workflow(d,w=w);private={'username':name,'password':seed['members'][name]['password'],'subject':seed['members'][name]['key'],'role':role,'sourceEvidence':[{**ref(source),'subjectPointer':'/members/'+name+'/key','rolePointer':'/members/'+name+'/role'}]}
     if name=='curator':private['jwtTrust']=trust
     import_actor(p,i,root/name,private);actors[name]=json.loads((root/name/'actor.json').read_text())
    status,body,_=exchange(server.origin,'POST','/documents',{'Authorization':'Bearer '+actors['reader']['token'],'Content-Type':'application/json'},b'{"title":"owned"}',5);self.assertEqual(status,201);key=body['entry']['key']
    request={'operationRef':'read','method':'GET','path':'/documents/'+key,'body':None}
    cases=[]
    for name,status in [('curator',403),('anonymous',401)]:
     cases.append({'id':name+'-cross-read','actorRef':name,'observerRef':'reader','resourceRef':'doc','state':'live','relation':'nonowner','action':'read','request':request,'requestTemplate':{**request,'path':'/documents/{key}'},'idLocations':[{'location':'path','name':'key'}],'beforeRequest':request,'afterRequest':request,'policyEvidenceRefs':['archive-source'],'denialStatuses':[status],'disclosurePointer':'/entry/key','disclosureValue':key})
    locked={k:{n:v[n] for n in ('subject','role','identityRequest','subjectPointer')} for k,v in actors.items()}
    w={'operationIds':['read','identity','access'],'permissions':['read','poststate'],'actors':locked,'resources':{'doc':{'ownerRef':'reader','wireId':key,'creationEvidence':'owned fixture create','idPointer':'/entry/key','ownerPointer':'/entry/owner','statePointer':'/entry/phase'}},'cases':cases}
    p,i=workflow(d,track='bola-ownership',w=w);result=execute(p,i,root/'bola',actors)
    self.assertEqual(result['executionStatus'],'completed');self.assertEqual(result['securityVerdict'],'inconclusive')
    self.assertEqual([x['outcome'] for x in json.loads((root/'bola/CHECKS.json').read_text())],['matched','matched'])
    self.assertTrue(list((root/'bola/identity-controls').rglob('*.json')))
   finally:server.close()

if __name__=='__main__':unittest.main()
