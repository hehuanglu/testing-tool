import hashlib,unittest
from zap_assessment.fe_anonymous_analysis import correlate,response_policies,evaluate_predicate

class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.plan={'selection':{'origin':'https://site.test:9443','certificate':{'derSha256':'c'*64}}}
        self.message={'id':'7','requestHeader':'POST https://site.test:9443/input HTTP/1.1\r\nHost: site.test:9443\r\n','requestBody':'{"input":"owned"}','responseHeader':'HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nCache-Control: no-store\r\n\r\n','responseBody':'{"status":"observed"}'}
        self.row={'sequence':1,'caseId':'public-input','campaignId':None,'forwarded':True,'reason':'app','method':'POST','url':'https://site.test:9443/input','requestBodySha256':hashlib.sha256(self.message['requestBody'].encode()).hexdigest(),'responseBodySha256':hashlib.sha256(self.message['responseBody'].encode()).hexdigest(),'status':200,'upstreamCertificateSha256':'c'*64,'upstreamSNI':'site.test'}
    def test_exact_native_link_and_synthetic_copy_are_explicit(self):
        result=correlate(self.plan,[self.row],[self.message,{**self.message,'id':'8'}])
        self.assertEqual(result['forwarded'],1);self.assertEqual(result['exchanges'][0]['nativeMessageIds'],['7','8']);self.assertEqual(result['exchanges'][0]['equivalentNativeCopies'],2)
    def test_different_body_or_missing_capture_fails(self):
        with self.assertRaisesRegex(ValueError,'missing from native'):correlate(self.plan,[self.row],[{**self.message,'requestBody':'{"input":"different"}'}])
        with self.assertRaisesRegex(ValueError,'unverified'):correlate(self.plan,[{**self.row,'upstreamSNI':'wrong'}],[self.message])
    def test_guard_is_excluded_from_target_policy_observations(self):
        guard={**self.message,'id':'9','responseHeader':'HTTP/1.1 403 Forbidden\r\nX-ZPA-Guard: blocked\r\n\r\n'}
        result=response_policies([self.message,guard]);self.assertEqual(len(result['groups']),1);self.assertEqual(result['groups'][0]['category'],'api-json');self.assertEqual(result['groups'][0]['nativeMessageIds'],['7'])
    def test_captured_dom_independent_of_pass_flag(self):
        p={'kind':'text','selector':'#result','value':'Loaded'}
        self.assertFalse(evaluate_predicate({'elements':[{'selector':'#result','exists':True,'text':'Loading'}]},p))
        self.assertTrue(evaluate_predicate({'elements':[{'selector':'#result','exists':True,'text':'Loaded'}]},p))
