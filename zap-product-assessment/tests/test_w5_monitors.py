import copy
import importlib.util
from pathlib import Path
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from zap_assessment.errors import Blocked
from zap_assessment.runtime_safety import GIB

SPEC=importlib.util.spec_from_file_location('w5_monitor_contract',Path(__file__).resolve().parents[1]/'scripts/remediation_w5_scanner.py')
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)


class Runtime:
    def __init__(self,root):
        self.root=root;self.plan=SimpleNamespace(data={'product':{'adapter':'synthetic-http-v1'},'workflow':{'active':True}})
        self.probe_name='owned-probe';self.block=False;self.entered=threading.Event();self.release=threading.Event()
        self.stopped=threading.Event();self.stops=0;self.phase=None
        self.inventory={'addons':[{'id':'ascanrules','version':'pinned'}],'scripts':[],
                        'rules':[{'id':'40012','enabled':True}],'inputVectors':['query']}
    def resource_sample(self):
        return {'dockerAvailable':True,'hostFree':5*GIB,'dockerFree':5*GIB,'ramAvailable':5*GIB}
    def policy_inventory(self):
        if self.block and threading.current_thread().name=='w5-policy':
            self.entered.set();self.release.wait(4)
        return copy.deepcopy(self.inventory)
    def policy_traffic(self):return {'events':[],'complete':True}
    def set_phase(self,phase):self.phase=phase
    def terminate(self):self.stops+=1;self.stopped.set();return True


class IndependentMonitorTests(unittest.TestCase):
    def test_resource_reads_continue_while_policy_read_waits_and_cleanup_remains_monitored(self):
        with tempfile.TemporaryDirectory() as t:
            rt=Runtime(Path(t));s=C.W5Supervisor(rt,None)
            try:
                s.preflight();s.start();rt.block=True
                self.assertTrue(rt.entered.wait(2))
                before=len(s.resource.samples);time.sleep(2.1)
                self.assertGreater(len(s.resource.samples),before)
                rt.release.set();rt.block=False
                # Do not require an active exercise for this monitor-only test.
                s.policy.active_execution_allowed=False
                s.finish();self.assertFalse(s.ready);self.assertTrue(s.thread.is_alive())
                self.assertEqual('cleanup',rt.phase);self.assertIsNone(s.failure)
                result={'monitorContract':C.MONITOR_CONTRACT,'policyMonitorSamples':s.policy_samples,'policy':s.result}
                C.verify_policy_monitor(result)
            finally:rt.release.set();s.close()
            self.assertFalse(s.thread.is_alive());self.assertFalse(s.policy_thread.is_alive())

    def test_stale_policy_latches_owned_stop_even_when_resource_reads_are_fresh(self):
        with tempfile.TemporaryDirectory() as t:
            rt=Runtime(Path(t));s=C.W5Supervisor(rt,None)
            try:
                s.resource.preflight();s.ready=True;s.last_policy_at=time.monotonic()-6
                s.thread=threading.Thread(target=s.watch);s.thread.start()
                self.assertTrue(rt.stopped.wait(2));self.assertIn('policy sampling gap',s.failure)
                self.assertIsNone(s.resource.failure)
                s.latch(Blocked('second failure'));self.assertEqual(1,rt.stops)
            finally:s.close()

    def test_audit_cannot_refresh_stale_policy_by_just_resetting_timestamp(self):
        with tempfile.TemporaryDirectory() as t:
            rt=Runtime(Path(t));s=C.W5Supervisor(rt,None)
            s.policy=C.calmod.EffectivePolicy(rt.inventory,active_execution_allowed=False,require_phase=True)
            s.last_policy_at=1
            with patch.object(C.time,'monotonic',return_value=8),self.assertRaisesRegex(Blocked,'policy sampling gap'):
                s.audit('during')
            self.assertEqual([],s.policy_samples);self.assertEqual(1,s.last_policy_at)

    def test_rehashed_policy_receipts_cannot_hide_gap_duration_or_wrong_snapshot(self):
        rows=[{'phase':phase,'startedAt':at-.1,'completedAt':at,'inventoryHash':'a'*64,'egressRecords':0}
              for phase,at in zip(('before','during','after'),(1,3,5))]
        value={'monitorContract':C.MONITOR_CONTRACT,'policyMonitorSamples':rows,
               'policy':{'snapshots':[{'phase':r['phase'],'inventoryHash':r['inventoryHash']} for r in rows]}}
        C.verify_policy_monitor(value)
        for fault in ('gap','duration','snapshot','missing','nan'):
            r=copy.deepcopy(value)
            if fault=='gap':r['policyMonitorSamples'][-1].update(startedAt=10,completedAt=11)
            elif fault=='duration':r['policyMonitorSamples'][-1]['startedAt']=-1
            elif fault=='snapshot':r['policyMonitorSamples'][-1]['inventoryHash']='b'*64
            elif fault=='missing':r['policyMonitorSamples'].pop()
            else:r['policyMonitorSamples'][-1]['completedAt']=float('nan')
            with self.subTest(fault=fault),self.assertRaises(Blocked):C.verify_policy_monitor(r)


if __name__=='__main__':unittest.main()
