import copy,json,hashlib,unittest
from zap_assessment.fe_anonymous_analysis import active_delivery,mutation_obligations

class IndependentDelivery(unittest.TestCase):
 def fixture(self):
  body=json.dumps({'email':'owned@example.test','password':'owned'});payload=json.dumps({'email':"o'brien@example.test",'password':'owned'})
  p={'selection':{'origin':'https://site.test','certificate':{'derSha256':'a'*64}},'campaigns':[{'id':'query','method':'POST','path':'/login','ruleIds':[40018],'vectorFields':['email'],'fixtureBody':{'email':'email','password':'password'},'maxDelivered':2}]}
  m={'id':'1','requestHeader':'POST https://site.test/login HTTP/1.1\r\nX-ZAP-Scan-ID: 40018\r\n','requestBody':payload,'responseHeader':'HTTP/1.1 401 Unauthorized\r\n','responseBody':'denied'}
  r={'sequence':1,'campaignId':'query','ruleId':'40018','forwarded':True,'method':'POST','url':'https://site.test/login','requestBodySha256':hashlib.sha256(payload.encode()).hexdigest(),'status':401,'responseBodySha256':hashlib.sha256(b'denied').hexdigest(),'reason':'app','upstreamSNI':'site.test','upstreamCertificateSha256':'a'*64}
  b=dict(m,requestBody=body)
  return p,[r],[m],{'query':b}
 def test_valid_rule_vector_delivery(self):
  d=active_delivery(*self.fixture());self.assertEqual(d['query']['deliveredByVector'],{'email':1});self.assertTrue(d['query']['deliveryProven'])
 def test_unchanged_rule_control_is_not_payload(self):
  p,r,m,b=self.fixture();m[0]['requestBody']=b['query']['requestBody'];r[0]['requestBodySha256']=hashlib.sha256(m[0]['requestBody'].encode()).hexdigest()
  self.assertFalse(active_delivery(p,r,m,b)['query']['deliveryProven'])
 def test_missing_forward_proof_cannot_pass(self):
  p,r,m,b=self.fixture();r[0]['forwarded']=False
  self.assertFalse(active_delivery(p,r,m,b)['query']['deliveryProven'])
 def test_wrong_sibling_and_rule_header_rejected(self):
  p,r,m,b=self.fixture();p['campaigns'][0]['vectorFields']=['password']
  with self.assertRaises(ValueError):active_delivery(p,r,m,b)
  p,r,m,b=self.fixture();m[0]['requestHeader']=m[0]['requestHeader'].replace('40018','40012')
  with self.assertRaises(ValueError):active_delivery(p,r,m,b)
 def test_sent_without_response_remains_obligation_after_crash(self):
  p,r,m,b=self.fixture();r[0].update(transportState='sent',forwarded=None)
  obligations=mutation_obligations(r);self.assertEqual(len(obligations),1);self.assertIs(obligations[0]['mutationReplay'],False)

class AccountingTests(unittest.TestCase):
 def test_unknown_is_sent_and_never_blocked(self):
  from zap_assessment.fe_anonymous_analysis import transport_accounting
  rows=[{'forwarded':None,'transportState':'unknown','reason':'transport-error'},
        {'forwarded':False,'transportState':'not-sent','reason':'transport-error'},
        {'forwarded':False,'reason':'input-policy'},
        {'forwarded':True,'transportState':'response-observed','reason':'app'}]
  self.assertEqual(transport_accounting(rows),{'attempted':4,'forwarded':1,'blocked':1,'notSent':2,'sent':2,'unknown':1})

class AppCapTests(unittest.TestCase):
 def test_all_app_attempts_are_capped_including_unchanged_native_controls(self):
  from zap_assessment.fe_anonymous_transport import Policy,sha
  body=b'{"input":"owned"}'
  p={'selection':{'origin':'https://site.test'},'limits':{'maxRequests':50,'maxBodyBytes':4096},'requestPolicies':[{'method':'POST','pathRegex':'/login','jsonFields':['input']}],'campaigns':[{'id':'query','maxDelivered':2,'maxAppRequests':3}]}
  policy=Policy(p);mode={'campaignId':'query','baselineHash':sha(body)};headers={'Host':'site.test','Content-Type':'application/json'}
  self.assertTrue(policy.admit('POST','https://site.test/login',headers,body,mode)[0])
  headers['X-ZAP-Scan-ID']='40018'
  for _ in range(2):self.assertTrue(policy.admit('POST','https://site.test/login',headers,body,mode)[0])
  self.assertEqual(policy.admit('POST','https://site.test/login',headers,body,mode),(False,'campaign-app-budget'))

class FinalAccountingTests(unittest.TestCase):
 def test_late_denied_connect_is_in_final_counters(self):
  from zap_assessment.fe_anonymous_analysis import transport_accounting
  early=[{'forwarded':True,'reason':'app'}]
  final=early+[{'forwarded':False,'reason':'connect-origin','method':'CONNECT'}]
  self.assertEqual(transport_accounting(early)['attempted'],1)
  self.assertEqual(transport_accounting(final)['attempted'],2)
  self.assertEqual(transport_accounting(final)['forwarded'],1)
  self.assertEqual(transport_accounting(final)['blocked'],1)
