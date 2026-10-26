import copy
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from zap_assessment.research import ResearchRun, admit, manifest, verify_manifest

BIND={'containerId':'a'*64,'imageId':'sha256:'+'b'*64,'startedAt':'2026-10-21T00:00:00Z','networkId':'c'*64,'address':'172.19.0.2'}
def plan():
    return {'assuranceProfile':'be-authenticated-research/1.0','secretPersistenceAccepted':True,
            'environment':'finalsource-zap-test','authority':{'fixtureActiveAuthorized':True,'source':'test user'},
            'targetBinding':BIND,'jobStore':'in-memory','coordinator':'single-node','origin':'http://backend:3000',
            'actorSubject':'42','operations':[{'method':'POST','path':'/api/v1/accounts','fixtureOwned':True}],
            'ruleIds':[40012],'limits':{'monitorIntervalSeconds':2,'stopDeadlineSeconds':10,
                                       'hostReserveBytes':2147483648,'operationTimeoutSeconds':2}}
class FakeClient:
    def __init__(self):self.calls=[]
    def call_tool(self,name,args):
        self.calls.append((name,args))
        if name.endswith('_start'):raise TimeoutError('lost ACK')
        if name.endswith('_validate'):return 'Valid: false\nOutcome: authentication_failed'
        return 'stop acknowledged'
class FakeZap:
    def call(self,*args,**kwargs):return {'scans':[{'id':'17','progress':'50'}]}

class ResearchTests(unittest.TestCase):
    def setUp(self):
        # Unit tests use a synthetic filesystem sample, independent of host disk.
        sample=SimpleNamespace(f_bavail=8*1024**3,f_frsize=1)
        self.disk=patch('zap_assessment.research.os.statvfs',return_value=sample)
        self.disk.start();self.addCleanup(self.disk.stop)

    def test_resource_reserve_still_blocks_start_before_dispatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClient();r=ResearchRun(plan=plan(),binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            r.session='opaque-session'
            with patch('zap_assessment.research.os.statvfs',return_value=SimpleNamespace(f_bavail=1,f_frsize=1)):
                with self.assertRaisesRegex(RuntimeError,'reserve'):
                    r.start('attack','http://backend:3000/api/v1/accounts')
            self.assertEqual(c.calls,[])

    def test_explicit_contract_drift_topology_and_owned_write_admission(self):
        self.assertEqual(admit(plan(),BIND)['actorSubject'],'42')
        for key,value in [('assuranceProfile','strict'),('secretPersistenceAccepted',False),('jobStore','postgres'),('actorSubject','')]:
            p=plan();p[key]=value
            with self.assertRaises(ValueError):admit(p,BIND)
        p=plan();p['operations'][0]['fixtureOwned']=False
        with self.assertRaises(ValueError):admit(p,BIND)
        with self.assertRaises(ValueError):admit(plan(),{**BIND,'startedAt':'other'})
    def test_lost_ack_records_native_reconciliation_and_never_replays_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClient();r=ResearchRun(plan=plan(),binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            r.session='opaque-session'
            with self.assertRaises(TimeoutError):r.start('attack','http://backend:3000/api/v1/accounts',method='POST',postData='{}')
            with self.assertRaises(RuntimeError):r.start('attack','http://backend:3000/api/v1/accounts')
            self.assertEqual(len([n for n,a in c.calls if n.endswith('_start')]),1)
            self.assertEqual(c.calls[0][1]['authSessionId'],'opaque-session')
            self.assertTrue((Path(tmp)/'uncertain-scans.json').is_file())
    def test_auth_loss_latches_stops_only_owned_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClient();r=ResearchRun(plan=plan(),binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            r.session='opaque-session';r.operations=[{'kind':'attack','operationId':'owned','terminal':False}]
            self.assertFalse(r.validate(c));r.stop_all('auth-loss')
            self.assertEqual(c.calls[-1],('zap_attack_stop',{'operationId':'owned'}))
            with self.assertRaises(RuntimeError):r.current()
    def test_manifest_truncation_or_change_is_not_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'report.json';p.write_text('{"alerts":[]}');manifest(tmp)
            self.assertEqual(verify_manifest(tmp)['evidenceStatus'],'consistent')
            p.write_text('{"alerts":[')
            with self.assertRaises(ValueError):verify_manifest(tmp)
    def test_timeout_requests_owned_stop_and_keeps_partial_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            tick=[0]
            def clock():tick[0]+=1;return tick[0]
            c=FakeClient();r=ResearchRun(plan=plan(),binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp,clock=clock)
            op={'kind':'attack','operationId':'owned-timeout','terminal':False,'ackAt':0};r.operations=[op]
            with self.assertRaises(TimeoutError):r.wait(op)
            self.assertIn(('zap_attack_stop',{'operationId':'owned-timeout'}),c.calls)
            self.assertFalse(op['terminal'])

    def test_changed_locked_plan_refuses_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClient();r=ResearchRun(plan=plan(),binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            r.plan_path.write_text('{}')
            with self.assertRaises(RuntimeError):r.current()
if __name__=='__main__':unittest.main()
