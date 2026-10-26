"""Cgroup measurement must work without tools inside distroless workloads."""
import json,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zap_assessment.observed import ObservedDockerRuntime
from zap_assessment.contracts import Blocked
from zap_assessment.journal import Journal

class ObservedResourceTests(unittest.TestCase):
    def test_fresh_recovery_reconciles_only_recorded_measurement_helper(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);j=Journal(root/'journal','run','a'*64)
            rt=ObservedDockerRuntime('run',root,j)
            self.assertNotIn('zpa-run-measurement',rt.owned_names())
            j.append('intent',{'action':'container-create','resource':'zpa-run-measurement','createdByRun':'foreign'})
            self.assertNotIn('zpa-run-measurement',rt.owned_names())
            j.append('intent',{'action':'container-create','resource':'zpa-run-measurement','createdByRun':'run','expectedImageId':'sha256:pinned'})
            self.assertIn('zpa-run-measurement',rt.owned_names())
    def test_distroless_uses_owned_helper_and_refuses_pid_drift(self):
        for drift,cleanup in ((False,False),(True,False),(True,True)):
            with self.subTest(drift=drift,cleanup=cleanup),tempfile.TemporaryDirectory() as d:
                root=Path(d);rt=ObservedDockerRuntime('run',root,Journal(root/'journal','run','a'*64))
                rt.plan=SimpleNamespace(data={'product':{'adapter':'synthetic-http-v1'}})
                rt.resource_cleanup=cleanup
                rt.probe_name='measurement';rt.created=[rt.names[3]];calls=[];owner_reads=[]
                def owner(name,**kwargs):
                    owner_reads.append(name)
                    return {'Id':'a'*64,'State':{'Pid':124 if drift and len(owner_reads)>1 else 123,'Running':True}}
                rt.check_owner=owner
                def docker(args,**kwargs):
                    calls.append(args)
                    if args[0]=='inspect':return '7'
                    self.assertEqual(['exec','measurement','python','-c'],args[:4])
                    if '/proc/meminfo' in args[4]:return json.dumps({'dockerFree':20*1024**3,'ramAvailable':8*1024**3})
                    self.assertEqual(['123','a'*64],args[-2:]);return '42'
                with patch('zap_assessment.observed.docker',side_effect=docker):
                    if drift:
                        with self.assertRaises(Blocked):rt.resource_sample()
                        self.assertEqual([],rt.metrics)
                    else:
                        rt.resource_sample();self.assertEqual({rt.names[3]:42},rt.metrics[0]['containerMemoryPeakBytes'])
                        self.assertEqual({rt.names[3]:7},rt.metrics[0]['containerWritableBytes'])
                self.assertFalse(any(a[:2]==['exec',rt.names[3]] for a in calls))
