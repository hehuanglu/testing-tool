import copy,json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import Mock
from test_anonymous import plan
from test_research import BIND
from zap_assessment.anonymous import validate_plan,expected_response
from zap_assessment.anonymous_guard import authorize
from zap_assessment.anonymous_runner import AnonymousRun


def query_plan():
 p=plan();case=p['cases'][0];case['path']='/data?q=baseline&categoryId=1';case['expected']['equals']={'/0/name':'baseline'}
 p['discovery']['operations'][0]['input']['query']=['q','categoryId']
 from zap_assessment.discovery import canonical_hash
 p['discoverySha256']=canonical_hash(p['discovery']);p['campaigns']=[{**p['campaigns'][0],'caseId':'r','vectors':['query'],'mutableKeys':['q']}]
 return p


class AnonymousQueryTests(unittest.TestCase):
 def test_admission_rejects_unknown_duplicate_and_wrong_method(self):
  p=query_plan();self.assertTrue(validate_plan(p,BIND,p['transportBinding']))
  for path,method,keys in [('/data?q=x&q=y','GET',['q']),('/data?q=x','POST',['q']),('/data?q=x','GET',['foreign']),('/data?password=x','GET',['password'])]:
   bad=copy.deepcopy(p);bad['cases'][0]['path']=path;bad['cases'][0]['method']=method;bad['campaigns'][0]['mutableKeys']=keys
   with self.subTest(path=path,method=method,keys=keys),self.assertRaises(ValueError):validate_plan(bad,BIND,bad['transportBinding'])

 def test_guard_accepts_only_selected_scalar_query_and_keeps_baseline_exact(self):
  p=query_plan();mode={'caseId':'r','campaignId':'active'};origin=p['origin'];headers={'Host':'127.0.0.1:9001'}
  case,camp=authorize(p,mode,'GET',origin+'/data?q=%27OR%201%3D1&categoryId=1',headers,b'',p['lockedAt']);self.assertEqual(camp['id'],'active')
  bad=[('GET','/data?q=x&categoryId=2',headers,b''),('GET','/data?q=x&categoryId=1&extra=1',headers,b''),('GET','/data?q=x&q=y&categoryId=1',headers,b''),('GET','/other?q=x&categoryId=1',headers,b''),('POST','/data?q=x&categoryId=1',headers,b''),('GET','/data?q=x&categoryId=1',headers,b'{}'),('GET','/data?q=x&categoryId=1',{**headers,'Authorization':'Bearer owned'},b''),('GET','/data?q=x&categoryId=1&password=secret',headers,b'')]
  for method,path,h,body in bad:
   with self.subTest(method=method,path=path),self.assertRaises(ValueError):authorize(p,mode,method,origin+path,h,body,p['lockedAt'])
  with self.assertRaises(ValueError):authorize(p,{'caseId':'r'},'GET',origin+'/data?q=changed&categoryId=1',headers,b'',p['lockedAt'])
  with self.assertRaises(ValueError):authorize(p,mode,'GET','http://example.test/data?q=x&categoryId=1',headers,b'',p['lockedAt'])

 def test_array_baseline_oracle_detects_missing_or_changed_rows(self):
  case=query_plan()['cases'][0];base={'responseHeader':'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Zpa-Response-Origin: app\r\n','responseBody':'[{"name":"baseline"}]'}
  self.assertTrue(expected_response(case,base)['matched'])
  for body in ['[]','[{"name":"other"}]','{}','null']:
   with self.subTest(body=body):self.assertFalse(expected_response(case,{**base,'responseBody':body})['matched'])

 def test_runner_selects_query_vector_and_never_posts_baseline(self):
  with tempfile.TemporaryDirectory() as t:
   r=AnonymousRun.__new__(AnonymousRun);r.p=query_plan();r.out=Path(t);r.ops=[];r.current=Mock();r.mode=Mock();r.j=Mock();r.bind_baseline=Mock();r.rt=Mock();r.rt.capture.glob.return_value=[];r.cancelled=threading.Event();calls=[]
   def engine(comp,kind,name,args=None):
    calls.append((name,args))
    if name=='scanners':return {'scanners':[{'id':40012,'enabled':'true'},{'id':40018,'enabled':'true'}]}
    if name=='sendRequest':return {'sendRequest':[{'requestBody':'','responseHeader':'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nX-Zpa-Response-Origin: app\r\n','responseBody':'[{"name":"baseline"}]'}]}
    if name=='scans':return {'scans':[]}
    if name=='scan':return {'scan':'4'}
    if name=='status':return {'status':'100'}
    return {}
   r.engine=engine;r.attack(r.p['campaigns'][0])
   scan=next(args for name,args in calls if name=='scan');self.assertEqual(scan['method'],'GET');self.assertNotIn('postData',scan)
   request=next(args['request'] for name,args in calls if name=='sendRequest');self.assertTrue(request.startswith('GET '));self.assertTrue(request.endswith('\r\n\r\n'));self.assertNotIn('Content-Type:',request)
   self.assertIn(('setOptionTargetParamsInjectable',{'Integer':1}),calls);self.assertIn(('setOptionTargetParamsEnabledRPC',{'Integer':0}),calls)
   r.bind_baseline.assert_called_once();self.assertEqual(r.bind_baseline.call_args.kwargs['expected_method'],'GET')

if __name__=='__main__':unittest.main()
