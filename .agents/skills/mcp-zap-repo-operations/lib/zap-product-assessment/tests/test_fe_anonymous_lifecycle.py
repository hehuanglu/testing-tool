import json,tempfile,threading,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from zap_assessment.fe_anonymous_contract import load
from zap_assessment.fe_anonymous_controls import browser_case
from zap_assessment.fe_anonymous_runner import FERun
from zap_assessment.fe_anonymous_transport import Policy

class LifecycleTests(unittest.TestCase):
    def test_sequential_jobs_replace_read_only_job_atomically(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'browser').mkdir()
            rt=SimpleNamespace(root=root,p={'selection':{'origin':'https://site.test:9443'}},names=['net','broker','zap','mcp','browser'],mode=lambda *a,**k:None)
            def worker(*a,**k):
                job=load(root/'browser/job.json');out=root/'browser'/job['journey']['id'];out.mkdir()
                (out/'RESULT.json').write_text(json.dumps({'journeyId':job['journey']['id'],'outcome':'observed'}))
                return SimpleNamespace(stdout=b'',stderr=b'')
            with patch('zap_assessment.fe_anonymous_controls.subprocess.run',side_effect=worker):
                self.assertEqual(browser_case(rt,{'id':'first'})['journeyId'],'first')
                self.assertEqual(browser_case(rt,{'id':'second'})['journeyId'],'second')
            self.assertEqual((root/'browser/job.json').stat().st_mode&0o777,0o444)
    def test_low_disk_sensor_latches_without_touching_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            r=FERun.__new__(FERun);r.out=Path(tmp);r.p={'limits':{'reserveBytes':2*1024**3,'artifactBytes':128*1024**2}}
            r.rt=SimpleNamespace(names=['net','broker','zap','mcp','browser'],created=[],config=r.out)
            r.done=SimpleNamespace(wait=lambda *a:False);r.cancel=threading.Event();r.errors=[];r.samples=[]
            with patch('zap_assessment.fe_anonymous_runner.os.statvfs',return_value=SimpleNamespace(f_bavail=1024**3,f_frsize=1)):
                r.monitor()
            self.assertTrue(r.cancel.is_set());self.assertTrue((r.out/'STOP').exists());self.assertEqual(r.errors[0]['kind'],'resource')
    def test_native_budget_is_enforced_before_delivery(self):
        plan={'selection':{'origin':'https://site.test:9443'},'limits':{'maxRequests':50,'maxBodyBytes':4096},'requestPolicies':[{'method':'POST','pathRegex':'/session','jsonFields':['email','password']}],'campaigns':[{'id':'password-vector','maxDelivered':2}]}
        p=Policy(plan);h={'Host':'site.test:9443','Content-Type':'application/json','X-ZAP-Scan-ID':'40018'};mode={'campaignId':'password-vector','fixedFields':{'email':'owned@example.test'}}
        body=b'{"email":"owned@example.test","password":"owned-control"}'
        for _ in range(2):self.assertEqual(p.admit('POST','https://site.test:9443/session',h,body,mode),(True,'admitted'))
        self.assertEqual(p.admit('POST','https://site.test:9443/session',h,body,mode),(False,'campaign-budget'))
        self.assertFalse(p.admit('POST','https://site.test:9443/session',h,b'{"email":"different@example.test","password":"x"}',mode)[0])

if __name__=='__main__':unittest.main()
