import copy,json,time,unittest
from zap_assessment.anonymous_guard import authorize,path_scope,scoped_path
from zap_assessment.anonymous import validate_plan
from test_anonymous import plan
from test_research import BIND

class PathContainmentTests(unittest.TestCase):
 def fixture(self):
  p=plan();o=p['discovery']['operations'][0];o['pathTemplate']='/objects/{id}/detail';c=p['cases'][0];c['path']='/objects/42/detail';p['cases']=[c];p['campaigns']=[{'id':'path-only','caseId':c['id'],'ruleIds':[40018],'vectors':['path'],'mutableKeys':['id'],'maxForwarded':20,'strength':'LOW','baselineSeed':True}]
  for row in p['dispositions']:
   if row['operationId']!='read':row.update(disposition='conditional',reason='not allocated')
  from zap_assessment.discovery import canonical_hash
  p['discoverySha256']=canonical_hash(p['discovery']);return p
 def test_one_numeric_selector_and_scanner_payload_reach_only_selected_segment(self):
  p=self.fixture();validate_plan(p,BIND,p['transportBinding']);headers={'Host':'127.0.0.1:9001'};mode={'caseId':'r','campaignId':'path-only'}
  for path in ['/objects/42/detail','/objects/42%27/detail','/objects/abc/detail']:
   authorize(p,mode,'GET',p['origin']+path,headers,b'',time.time())
  for path in ['/objects/43/detail','/objects/%2b43/detail','/objects/42;other/detail','/objects/%2e%2e/detail','/objects/a%2fb/detail','/else/42/detail','/objects/42/else','/objects/42/detail?token=secret']:
   with self.subTest(path=path),self.assertRaises(ValueError):authorize(p,mode,'GET',p['origin']+path,headers,b'',time.time())
 def test_no_implicit_wildcard_multi_selector_or_non_numeric_admission(self):
  for template,baseline in [('/objects/{owner}/{id}','/objects/1/42'),('/objects','/objects'),('/objects/{id}','/objects/string-key')]:
   with self.assertRaises(ValueError):path_scope(template,baseline)
  p=self.fixture();p['cases'][0]['method']='POST'
  with self.assertRaises(ValueError):validate_plan(p,BIND,p['transportBinding'])

if __name__=='__main__':unittest.main()
