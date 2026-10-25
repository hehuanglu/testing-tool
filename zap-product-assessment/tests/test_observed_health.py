"""Health checks must traverse the engine sender after capture activation."""
import unittest
from types import SimpleNamespace
from zap_assessment.contracts import Blocked
from zap_assessment.egress import Denied
from zap_assessment.observed import ObservedDockerRuntime

class ObservedHealthTests(unittest.TestCase):
    def runtime(self):
        rt=ObservedDockerRuntime.__new__(ObservedDockerRuntime)
        rt.plan=SimpleNamespace(data={'product':{'attackOrigins':['http://127.0.0.1:18080']}})
        rt.calls=[]
        def engine(*args):
            rt.calls.append(args)
            return {'sendRequest':[{'responseHeader':'HTTP/1.1 200 OK\r\n','responseBody':'{"productId":"fixture"}'}]}
        rt.engine=engine
        def bypass(*args,**kwargs):raise AssertionError('controller target bypass')
        rt.request=bypass
        return rt
    def test_health_uses_engine_sender_and_retains_real_response(self):
        rt=self.runtime();r=rt.target_request('http://127.0.0.1:18080/health')
        self.assertEqual({'status':200,'body':'{"productId":"fixture"}'},r)
        self.assertEqual(('core','action','sendRequest'),rt.calls[0][:3])
        self.assertEqual('false',rt.calls[0][3]['followRedirects'])
    def test_outside_origin_or_path_never_reaches_engine(self):
        for url in ('http://127.0.0.1:18081/health','http://127.0.0.1:18080/not-health','http://user:pass@127.0.0.1:18080/health'):
            rt=self.runtime()
            with self.subTest(url=url),self.assertRaises(Denied):rt.target_request(url)
            self.assertEqual([],rt.calls)
    def test_missing_or_multiple_receipts_cannot_become_success(self):
        for data in ({},{'sendRequest':[]},{'sendRequest':[{},{}]},{'sendRequest':[{'responseHeader':'invalid'}]}):
            rt=self.runtime();rt.engine=lambda *a:data
            with self.subTest(data=data),self.assertRaises(Blocked):rt.target_request('http://127.0.0.1:18080/health')
