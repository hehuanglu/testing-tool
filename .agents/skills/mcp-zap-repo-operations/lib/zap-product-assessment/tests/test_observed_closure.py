import copy,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.contracts import Blocked
from zap_assessment.observed import ObservedDockerRuntime

class ClosureTests(unittest.TestCase):
    def runtime(self):
        rt=object.__new__(ObservedDockerRuntime);rt.run_id='closure-fixture'
        rt.final_traffic={'events':[],'counts':{'senderRequests':0},'complete':True}
        return rt
    def test_readback_only_after_exact_owned_cleanup(self):
        rt=self.runtime();order=[]
        rt.policy_traffic=lambda:(order.append('readback') or copy.deepcopy(rt.final_traffic))
        with patch('zap_assessment.runtime.DockerRuntime.cleanup',side_effect=lambda:order.append('owned-stop')):rt.cleanup()
        self.assertEqual(['owned-stop','readback'],order);self.assertTrue(rt.closure_evidence['terminalCaptureUnchanged'])
    def test_late_background_traffic_blocks_publication(self):
        rt=self.runtime();rt.policy_traffic=lambda:{**rt.final_traffic,'counts':{'senderRequests':1}}
        with patch('zap_assessment.runtime.DockerRuntime.cleanup'),self.assertRaisesRegex(Blocked,'traffic changed'):rt.cleanup()
        self.assertFalse(hasattr(rt,'closure_evidence'))
    def test_unconfirmed_cleanup_cannot_create_closure(self):
        rt=self.runtime();rt.policy_traffic=lambda:self.fail('read before stop confirmation')
        with patch('zap_assessment.runtime.DockerRuntime.cleanup',side_effect=Blocked('ownership mismatch')),self.assertRaises(Blocked):rt.cleanup()
        self.assertFalse(hasattr(rt,'closure_evidence'))
