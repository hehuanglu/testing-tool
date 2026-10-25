import copy,json,unittest
from zap_assessment.executor_routing import assess_executor,choose_executor,compare_contracts

def candidate(name='shared'):
 return {'id':name,'tools':{'tools':[{'name':'zap_attack_start','inputSchema':{'type':'object','properties':{'targetUrl':{'type':'string'},'method':{'type':'string'},'postData':{'type':'string','maxLength':65536},'authSessionId':{'type':'string'},'recurse':{'type':'string','enum':['true','false']}},'required':['targetUrl'],'additionalProperties':False}}]},
  'semantics':{'zap_attack_start':{'exactBodyRequiresPreparedAuth':True,'executionMode':'direct','activeAuthKinds':['form','json-bearer']}},'configuredAuthKinds':['json-bearer'],'sessionValidated':True}
ARGS={'targetUrl':'http://owned/api/object/7','method':'PUT','postData':'{"name":"a"}','authSessionId':'prepared','recurse':'false'}

class RoutingTests(unittest.TestCase):
 def test_missing_field_routes_candidate_without_call(self):
  a=candidate();b=candidate('isolated');del a['tools']['tools'][0]['inputSchema']['properties']['postData']
  d=choose_executor([a,b],'zap_attack_start',ARGS,auth_kind='json-bearer')
  self.assertEqual(d['selected'],'isolated');self.assertEqual(d['decisions'][0]['reason'],'schema-field-missing')
  self.assertEqual(d['decisions'][0]['status'],'not-operated');self.assertEqual(d['execution'],'not-operated')
 def test_supported_shared_is_preferred(self):
  self.assertEqual(choose_executor([candidate(),candidate('isolated')],'zap_attack_start',ARGS,auth_kind='json-bearer')['selected'],'shared')
 def test_tool_unexposed_not_confused_with_missing_field(self):
  a=candidate();a['tools']['tools']=[]
  self.assertEqual(assess_executor(a,'zap_attack_start',ARGS)['status'],'not-exposed')
 def test_required_type_enum_and_constraint_errors(self):
  for change in ({'targetUrl':None},{'recurse':False},{'recurse':'maybe'},{'postData':'a'*65537}):
   self.assertEqual(assess_executor(candidate(),'zap_attack_start',{**ARGS,**change},auth_kind='json-bearer')['status'],'input-error')
  a=copy.deepcopy(ARGS);del a['targetUrl']
  self.assertEqual(assess_executor(candidate(),'zap_attack_start',a,auth_kind='json-bearer')['status'],'input-error')
 def test_auth_kind_and_validation_separate(self):
  self.assertEqual(assess_executor(candidate(),'zap_attack_start',ARGS,auth_kind='browser-cookie')['reason'],'auth-kind-incompatible')
  a=candidate();a['sessionValidated']=False
  self.assertEqual(assess_executor(a,'zap_attack_start',ARGS,auth_kind='json-bearer')['reason'],'session-not-validated')
 def test_exact_body_needs_direct_auth_even_with_fields(self):
  a=candidate();a['semantics']['zap_attack_start']['executionMode']='queue'
  self.assertFalse(assess_executor(a,'zap_attack_start',ARGS,auth_kind='json-bearer')['compatible'])
  self.assertFalse(assess_executor(candidate(),'zap_attack_start',ARGS)['compatible'])
 def test_permissive_unknown_fields_not_capability(self):
  a=candidate();s=a['tools']['tools'][0]['inputSchema'];del s['properties']['postData'];s['additionalProperties']=True
  self.assertEqual(assess_executor(a,'zap_attack_start',ARGS,auth_kind='json-bearer')['reason'],'schema-field-missing')
 def test_schema_drift_beyond_names(self):
  a=candidate()['tools'];b=copy.deepcopy(a);s=b['tools'][0]['inputSchema'];s['required'].append('method');s['properties']['recurse']['type']='boolean';s['properties']['postData']['maxLength']=10
  row=compare_contracts(a,b)['tools'][0]
  self.assertFalse(row['sameSchemaContract']);self.assertEqual(row['fieldsOnlyRight'],[])
  self.assertEqual({r['field'] for r in row['changedFieldContracts']},{'recurse','postData'})
 def test_no_external_schema_resolution_or_pagination(self):
  a=candidate();a['tools']['nextCursor']='next';self.assertFalse(assess_executor(a,'zap_attack_start',ARGS)['compatible'])
  a=candidate();a['tools']['tools'][0]['inputSchema']['properties']['targetUrl']={'$ref':'https://example.invalid/schema'}
  self.assertEqual(assess_executor(a,'zap_attack_start',ARGS)['reason'],'schema-not-comparable')
 def test_undeclared_auth_kind_not_anonymous_compatibility(self):
  a={k:v for k,v in ARGS.items() if k not in ('method','postData')}
  self.assertEqual(assess_executor(candidate(),'zap_attack_start',a)['reason'],'auth-kind-not-declared')

class BodyTransitionTests(unittest.TestCase):
 def messages(self):
  def message(i,name):return {'id':str(i),'requestHeader':'PUT http://owned/account/7 HTTP/1.1\r\nAuthorization: Bearer local-test-only\r\nX-ZAP-Scan-ID: 40018\r\n',
    'requestBody':json.dumps({'bank_name':name,'balance':10}),'responseHeader':'HTTP/1.1 200 OK\r\n',
    'responseBody':json.dumps({'account':{'name':name,'id':7}})}
  return [message(1,'changed'),message(2,'baseline')]
 def check(self,messages,after):
  from zap_assessment.product_native import check_transition
  return check_transition({'field':'bank_name','statePointer':'/name','responsePointer':'/account/name',
    'acceptedStatuses':[200],'rejectedStatuses':[400],'fixedState':{'/id':7},'responseEquals':{'/account/id':7}},
    {'name':'baseline','id':7},after,messages,{'method':'PUT','path':'/account/7','body':{'bank_name':'baseline','balance':10}},'http://owned')
 def test_baseline_restore_is_real_last_accepted_state(self):
  r=self.check(self.messages(),{'name':'baseline','id':7});self.assertTrue(r['finalStateMatched']);self.assertEqual(r['deliveredBodyMessages'],1)
 def test_unacknowledged_final_state_rejected(self):
  with self.assertRaisesRegex(ValueError,'final state'):self.check(self.messages(),{'name':'changed','id':7})
 def test_only_baseline_or_guard_never_body_delivery(self):
  with self.assertRaisesRegex(ValueError,'payload absent'):self.check(self.messages()[1:],{'name':'baseline','id':7})

if __name__=='__main__':unittest.main()
