"""Security boundary checks: prevent fixture drift, auth crossover and fallback."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('p0guard',Path(__file__).resolve().parents[1]/'scripts/finalsource_p0_guard.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();f=Path(self.tmp.name)/'creds.json'
        f.write_text(json.dumps({'actors':{'A':{'email':'a@example.test','password':'canary-A','userId':3},'B':{'email':'b@example.test','password':'canary-B','userId':4}}}))
        self.s=mod.State({'credentials':str(f),'mode':'delegated','actor':'A','notAfter':9999999999,'accounts':[1],'fixturePrefix':'run-owned'})
        self.events=[];self.calls=[];self.s.record=self.events.append
        self.s.tokens={'A':'secret-A','B':'secret-B'}
        def upstream(*args,**kwargs):self.calls.append((args,kwargs));return {'status':200,'body':'{}','headers':{}}
        self.s.upstream=upstream
    def tearDown(self):self.tmp.cleanup()
    def test_no_foreign_url_host_or_method(self):
        for method,path in [('GET','http://evil.test/'),('GET','//evil.test/'),('DELETE','/api/v1/accounts/1'),('POST','/api/auth/register'),('GET','/api/v1/accounts/99')]:
            self.assertIsNone(self.s.mirror(method,path,{},None))
        self.assertEqual([],self.calls)
    def test_actor_marker_cannot_cross_session(self):
        self.assertIsNone(self.s.mirror('GET','/api/v1/accounts',{'Authorization':'Bearer scan-marker-B'},None))
        self.assertIsNone(self.s.mirror('GET','/api/v1/accounts',{'Authorization':'Bearer arbitrary-jwt'},None))
        self.assertEqual([],self.calls)
        self.s.mirror('GET','/api/v1/accounts',{'Authorization':'Bearer scan-marker-A'},None)
        self.assertEqual('A',self.calls[-1][0][3]);self.assertEqual('secret-B',self.s.tokens['B'])
    def test_real_401_latches_no_relogin_or_anonymous_fallback(self):
        self.s.upstream=lambda *a,**k:{'status':401,'headers':{},'body':'{"statusCode":401}'}
        self.s.mirror('GET','/api/v1/accounts',{},None)
        self.assertTrue(self.s.lost);self.assertNotIn('A',self.s.tokens)
        self.s.upstream=lambda *a,**k:self.fail('forwarded after loss')
        self.assertEqual(401,self.s.mirror('GET','/api/v1/goals',{},None)['status'])
    def test_existing_fixture_cannot_be_updated_or_deleted(self):
        for m in ('PUT','DELETE'):
            with self.assertRaises(ValueError):self.s.control({'op':'request','method':m,'path':'/api/v1/accounts/1','actor':'A','body':{}})
        self.assertEqual([],self.calls)
    def test_create_requires_run_marker_and_goal_ownership_registry(self):
        with self.assertRaises(ValueError):self.s.control({'op':'request','method':'POST','path':'/api/v1/accounts','actor':'A','body':{'bank_name':'old data'}})
        with self.assertRaises(ValueError):self.s.control({'op':'request','method':'PUT','path':'/api/v1/goals/100','actor':'A','body':{'target_amount':1}})
        self.assertEqual([],self.calls)
    def test_native_login_matches_exact_fixture_only(self):
        self.s.mode='native'
        self.assertIsNone(self.s.mirror('POST','/api/auth/login',{},self.s.creds['B']))
        self.s.mirror('POST','/api/auth/login',{}, {'email':'a@example.test','password':'canary-A'})
        self.assertEqual(1,len(self.calls))
    def test_transaction_writes_require_new_account_pinned_category_and_marker(self):
        self.s.categories={'A':11,'B':22};self.s.accounts.add(2)
        body={'accountId':1,'category_id':11,'itemDescription':'run-owned-test'}
        for edit in [{},{'accountId':2,'category_id':99},{'accountId':2,'itemDescription':'old data'}]:
            with self.assertRaises(ValueError):self.s.control({'op':'request','method':'POST','path':'/api/v1/transactions','actor':'A','body':body|edit})
        self.assertEqual([],self.calls)
    def test_anonymous_transaction_control_still_reaches_real_target_oracle(self):
        self.s.categories={'A':11};self.s.accounts.add(2)
        self.s.control({'op':'request','method':'POST','path':'/api/v1/transactions','body':{'accountId':2,'category_id':11,'itemDescription':'run-owned-negative'}})
        self.assertIsNone(self.calls[-1][0][3])

if __name__=='__main__':unittest.main()
