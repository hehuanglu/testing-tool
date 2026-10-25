import copy,hashlib,unittest
from test_anonymous import plan
from test_research import BIND
from zap_assessment.anonymous import expected_response,validate_plan
from zap_assessment.recipes import spring_orders

class FrameworkOracleTests(unittest.TestCase):
 def test_document_hash_detects_changed_or_guard_content(self):
  body='openapi: 3.0.3\ninfo:\n  title: ByteMe API\n';c=copy.deepcopy(plan()['cases'][0]);c['category']='documentation';c['expected']={'statuses':[200],'contentType':'application/yaml','equals':{},'present':[],'bodySha256':hashlib.sha256(body.encode()).hexdigest()}
  m={'responseHeader':'HTTP/1.1 200 OK\r\nContent-Type: application/yaml\r\nX-Zpa-Response-Origin: app\r\n','responseBody':body}
  self.assertTrue(expected_response(c,m)['matched'])
  for bad in [{**m,'responseBody':body+'changed'},{**m,'responseHeader':m['responseHeader'].replace('application/yaml','text/html')},{**m,'responseHeader':m['responseHeader'].replace('X-Zpa-Response-Origin: app','X-Zpa-Response-Origin: guard')}]:self.assertFalse(expected_response(c,bad)['matched'])
 def test_hash_oracle_does_not_replace_business_json_semantics(self):
  p=plan();c=p['cases'][0];c['expected']['bodySha256']='a'*64
  with self.assertRaises(ValueError):validate_plan(p,BIND,p['transportBinding'])
  c['category']='documentation';self.assertTrue(validate_plan(p,BIND,p['transportBinding']))
  c['expected']['present']=['/required']
  with self.assertRaises(ValueError):validate_plan(p,BIND,p['transportBinding'])
 def test_framework_only_anonymous_exact_get_and_protection(self):
  # Framework additions do not change controller extraction or protected/native roles.
  row={'id':'framework.test','method':'GET','pathTemplate':'/openapi.yaml','protected':False}
  d={'operations':[row],'auth':None};self.assertEqual(spring_orders.admit(d,track='be-anonymous'),['framework.test'])
  self.assertEqual(spring_orders.admit({'operations':[{**row,'pathTemplate':'/not-framework'}],'auth':None},track='be-anonymous'),[])
  for bad in [{**row,'method':'POST'},{**row,'protected':True}]:
   with self.assertRaises(ValueError):spring_orders.admit({'operations':[bad]},track='be-anonymous')
  with self.assertRaises(ValueError):spring_orders.admit(d,track='be-authenticated')

if __name__=='__main__':unittest.main()
