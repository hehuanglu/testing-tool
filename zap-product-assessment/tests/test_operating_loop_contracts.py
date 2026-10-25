import copy,unittest
from test_multi_product import workflow,actor
from zap_assessment.product_workflow import compile_track,validate_workload
from zap_assessment.recipes import archive
from zap_assessment.anonymous_guard import redirect_response_allowed

class NativeRuleSelectionTests(unittest.TestCase):
 def test_selected_subset_reaches_native_plan_without_changing_legacy_default(self):
  p,_=workflow();self.assertEqual(compile_track(p,actor=actor())['ruleIds'],[40012,40018])
  p['workload']['ruleIds']=[40018]
  validate_workload(p['discovery'],archive,p['track'],p['workload'],p['permissions'])
  self.assertEqual(compile_track(p,actor=actor())['ruleIds'],[40018])
 def test_invalid_rule_set_is_rejected_before_dispatch(self):
  p,_=workflow()
  for rules in ([],[40018,40018],[40003],[True],['40018'],None):
   w=copy.deepcopy(p['workload']);w['ruleIds']=rules
   with self.subTest(rules=rules),self.assertRaisesRegex(ValueError,'selected native rule'):
    validate_workload(p['discovery'],archive,p['track'],w,p['permissions'])

class RedirectObservationTests(unittest.TestCase):
 def setUp(self):
  self.case={'id':'redirect','method':'GET','path':'/docs','category':'protocol-control','expected':{'statuses':[302]}}
  self.plan={'origin':'http://local.test:8080','cases':[self.case,{'id':'index','method':'GET','path':'/docs/index.html','category':'documentation'}]}
 def test_only_declared_same_origin_document_redirect_is_observable(self):
  for location in ('/docs/index.html','http://local.test:8080/docs/index.html'):
   self.assertTrue(redirect_response_allowed(self.plan,self.case,302,[('Location',location)]))
 def test_foreign_undeclared_credentials_fragment_and_legacy_redirects_stay_denied(self):
  for location in ('http://evil.test/docs/index.html','//evil.test/docs/index.html','/other','/docs/index.html?token=x','http://user:pass@local.test:8080/docs/index.html','/docs/index.html#secret','/docs/index.html\r\nInjected:x','\\evil.test/x'):
   with self.subTest(location=location):self.assertFalse(redirect_response_allowed(self.plan,self.case,302,[('Location',location)]))
  self.assertFalse(redirect_response_allowed(self.plan,self.case,302,[('Location','/docs/index.html'),('location','/docs/index.html')]))
  self.assertFalse(redirect_response_allowed(self.plan,{**self.case,'category':'public-success'},302,[('Location','/docs/index.html')]))
  self.assertFalse(redirect_response_allowed(self.plan,self.case,307,[('Location','/docs/index.html')]))

class PrivateActiveAuthTests(unittest.TestCase):
 def test_bounded_login_campaign_freezes_password_and_blocks_identity_propagation(self):
  import tempfile,json
  from pathlib import Path
  from test_anonymous_private_body import PrivateAuthBodyTests
  from zap_assessment.anonymous_private_body import resolve_case,materialize_guard_plan
  from zap_assessment.anonymous import validate_plan
  from zap_assessment.anonymous_guard import authorize
  from test_research import BIND
  with tempfile.TemporaryDirectory() as temp:
   p,c,_=PrivateAuthBodyTests().fixture(Path(temp));c['expected']['statuses']=[200]
   camp={'id':'private-login','caseId':c['id'],'vectors':['JSON-body'],'mutableKeys':['email'],'ruleIds':[40018],'strength':'LOW','maxForwarded':12,'baselineSeed':True};p['campaigns']=[camp]
   validate_plan(p,BIND,p['transportBinding']);guard=materialize_guard_plan(p);resolved=resolve_case(p,c)
   body={**resolved['body'],'email':"owned'@example.test"};headers={'Host':'127.0.0.1:9001','Content-Type':'application/json'};mode={'caseId':c['id'],'campaignId':camp['id']}
   authorize(guard,mode,'POST',p['origin']+c['path'],headers,json.dumps(body).encode(),p['lockedAt'])
   for bad in ({**body,'password':'changed'},{**body,'accessToken':'forged'}):
    with self.assertRaises(ValueError):authorize(guard,mode,'POST',p['origin']+c['path'],headers,json.dumps(bad).encode(),p['lockedAt'])
   self.assertIsNone(c['body']);self.assertNotIn('Synthetic-owned',json.dumps(p))
   for delta in ({'maxForwarded':21},{'mutableKeys':['password']},{'baselineSeed':False},{'vectors':['query']}):
    altered=copy.deepcopy(p);altered['campaigns'][0].update(delta)
    with self.assertRaises(ValueError):resolve_case(altered,altered['cases'][1])
