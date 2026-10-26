"""Boundary between W4 development conformance and product admission."""
import tempfile,unittest
from pathlib import Path
from unittest.mock import Mock
from zap_assessment.contracts import Blocked,make_plan
from zap_assessment.w4_fixture import inputs
from zap_assessment.adapters import registered_runtime
from zap_assessment.runtime_safety import EffectivePolicy,SafetySupervisor
from zap_assessment.observed import ObservedDockerRuntime
from zap_assessment.journal import Journal
from test_runtime_safety import INV,event
class W4CompletionTests(unittest.TestCase):
    def policy(self):
        p=EffectivePolicy(INV,require_phase=True);p.snapshot('before',INV);p.snapshot('during',INV);return p
    def receipt(self,phase='active'):return event('40012')|{'phase':phase}
    def test_contained_enabled_rule_outside_phase_still_latches(self):
        with self.assertRaisesRegex(Blocked,'outside phase'):self.policy().traffic([self.receipt('settle')|{'forwarded':False}],complete=True)
    def test_missing_native_phase_cannot_pass(self):
        with self.assertRaisesRegex(Blocked,'incomplete'):self.policy().traffic([event('40012')],complete=True)
    def test_inventory_enabled_does_not_prove_observed_active_set(self):
        p=self.policy();p.traffic([],complete=True);p.snapshot('after',INV)
        with self.assertRaisesRegex(Blocked,'observed active rule set'):p.finalize()
    def test_exact_set_and_phase_has_independent_security_verdict(self):
        p=self.policy();p.traffic([self.receipt()],complete=True);p.snapshot('after',INV)
        r=p.finalize();self.assertEqual(['40012'],r['observedActiveRules']);self.assertFalse(r['techniqueVerified']);self.assertFalse(r['securityApproval'])
    def test_active_fixture_not_available_through_product_registration(self):
        with self.assertRaisesRegex(Blocked,'explicit observed harness'):registered_runtime('r',Path('/unused'),None,make_plan(*inputs(True)))
    def test_regular_v1_cannot_enable_active_by_boolean(self):
        p,w,r,raw=inputs();w['active']=True;w['operations'].append('active')
        with self.assertRaisesRegex(Blocked,'active runtime unverified'):make_plan(p,w,r,raw)
    def test_development_workflow_cannot_switch_target_or_crawl_path(self):
        for key,value in [('crawlPath','/health'),('attackOrigins',['http://127.0.0.1:18081'])]:
            p,w,r,raw=inputs(True);p[key]=value
            with self.assertRaises(Blocked):make_plan(p,w,r,raw)
    def test_phase_atomic_replace_readable_to_native_uid(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'zap-workspace').mkdir();rt=ObservedDockerRuntime('r',root,Journal(root/'journal','r','a'*64));rt.capture_ready=True
            rt.set_phase('active');rt.set_phase('settle');f=root/'zap-workspace/observer-phase.txt'
            self.assertEqual('settle',f.read_text());self.assertTrue(f.stat().st_mode&0o004);self.assertEqual([],list(f.parent.glob('*.pending')))
    def test_final_helper_shutdown_over_five_seconds_blocks(self):
        s=object.__new__(SafetySupervisor);s.rt=Mock(phase_capture=True);s.cleanup_sealed=0;s.clock=lambda:5.001
        with self.assertRaisesRegex(Blocked,'helper shutdown'):s.cleanup_complete()
    def test_resource_latch_during_cleanup_cannot_be_ignored(self):
        s=object.__new__(SafetySupervisor);s.rt=Mock(phase_capture=True);s.cleanup_sealed=0;s.clock=lambda:1;s.resource=Mock(samples=[{'at':0},{'at':1}]);s.result={'resources':{}};s.failure='unavailable'
        with self.assertRaisesRegex(Blocked,'cleanup resource latch'):s.cleanup_complete()
