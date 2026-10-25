import copy,json,unittest
from pathlib import Path
from zap_assessment.fe_authenticated_controls import observations
from zap_assessment.fe_authenticated_transport import AuthenticatedPolicy
from zap_assessment.fe_anonymous_transport import Policy
from zap_assessment.fe_authenticated_contract import validate_journeys,admission

class AuthenticatedPolicyTests(unittest.TestCase):
    def setUp(self):
        self.j=observations(Path(__file__).resolve().parents[1]/'src/zap_assessment/fe_authenticated_control_fixture.py')
        self.p={'selection':{'origin':'https://cardinal.test:9543'},'journeys':self.j,'requestPolicies':self.j['requestPolicies'],'campaigns':self.j['campaigns'],'actorBindings':{'actor-a':{'username':'owned-a','subject':'person-71','role':'researcher'}},'authority':{'permissions':['network','browser','private-research-retention','owned-mutation','active']},'limits':{'maxRequests':100,'maxBodyBytes':4096,'maxLoginsPerActor':3,'identityMaxGapSeconds':30}}
        self.policy=AuthenticatedPolicy(self.p);self.mode={'actorRef':'actor-a','sessionGroup':'group-a','phase':'login-pending','slot':'browser'};self.headers={'Host':'cardinal.test:9543','Content-Type':'application/json'}
    def admit(self,method,path,body=b'',headers=None):return self.policy.admit(method,self.p['selection']['origin']+path,headers or self.headers,body,self.mode)
    def login(self):
        b=b'{"handle":"owned-a","phrase":"private"}';self.assertTrue(self.admit('POST','/session/open',b)[0]);self.policy.observe_response('POST',self.p['selection']['origin']+'/session/open',self.headers,b,200,[],b'{"payload":{"credential":"private-token"}}',self.mode);self.headers['Authorization']='Bearer private-token';self.mode['phase']='authenticated'
    def test_no_token_or_200_shortcut(self):
        self.login();self.assertEqual(self.admit('GET','/records?q=seed'),(False,'identity-probe-only'))
        self.assertTrue(self.admit('GET','/people/current')[0]);self.policy.observe_response('GET',self.p['selection']['origin']+'/people/current',self.headers,b'',200,[],b'{"envelope":{"person":{"subject":"person-71","role":"researcher"}}}',self.mode);self.assertTrue(self.admit('GET','/records?q=seed')[0])
    def test_wrong_actor_latches(self):
        self.login();self.policy.observe_response('GET',self.p['selection']['origin']+'/people/current',self.headers,b'',200,[],b'{"envelope":{"person":{"subject":"person-92","role":"researcher"}}}',self.mode);self.assertTrue(self.policy.latched);self.assertFalse(self.admit('GET','/records?q=seed')[0])
    def test_unregistered_token_rejected_before_send(self):
        self.login();self.headers['Authorization']='Bearer different-valid-token';self.assertEqual(self.admit('GET','/people/current'),(False,'unregistered-or-stale-credential'))
    def test_native_missing_header_control_denied_without_faking_session_loss(self):
        self.mode['slot']='native';self.login();self.headers.pop('Authorization')
        self.assertEqual(self.admit('GET','/people/current'),(False,'native-unauthenticated-control-denied'));self.assertFalse(self.policy.latched)
        self.headers['Authorization']='Bearer private-token'
        self.policy.observe_response('GET',self.p['selection']['origin']+'/people/current',self.headers,b'',401,[],b'{"error":"expired"}',self.mode)
        self.assertTrue(self.policy.latched)
    def test_browser_missing_header_still_latches(self):
        self.login();self.headers.pop('Authorization');self.assertEqual(self.admit('GET','/people/current'),(False,'browser-credential-missing'));self.assertTrue(self.policy.latched)
    def test_origin_cookie_and_public_identity_rejected(self):
        self.assertFalse(self.policy.admit('GET','https://other.test/people/current',self.headers,b'',self.mode)[0]);self.headers['Cookie']='session=unknown';self.assertFalse(self.admit('GET','/signin')[0])
        self.headers.pop('Cookie');self.headers['Authorization']='Bearer arbitrary';self.assertEqual(self.admit('GET','/signin'),(False,'credential-public-path'))
    def test_missing_permissions_only_blocks_dependent_branches(self):
        self.p['authority']['permissions']=['network','browser','private-research-retention'];rows=admission(self.p)
        self.assertTrue(next(r for r in rows if r['id']=='ui-login')['admitted']);self.assertFalse(next(r for r in rows if r['id']=='ui-mutation')['admitted']);self.assertFalse(next(r for r in rows if r['id']=='native-query')['admitted'])
    def test_unsafe_or_arbitrary_recipe_rejected(self):
        for change in ('script','external','predicate'):
            j=copy.deepcopy(self.j)
            if change=='script':j['journeys'][0]['steps'][0]['script']='arbitrary code'
            elif change=='external':j['journeys'][0]['steps'][0]['path']='//outside.test'
            else:j['journeys'][0]['expectedUi'][0]['kind']='javascript'
            with self.assertRaises(Exception):validate_journeys(j)
    def test_owned_alias_candidates_are_all_considered_without_widening(self):
        self.p['requestPolicies'] += [{'method':'GET','path':'/records/{firstId}','phase':'protected','effect':'read'}, {'method':'GET','path':'/records/{secondId}','phase':'protected','effect':'read'}]
        self.p['actorBindings']['actor-a']['ownedIds']={'firstId':8,'secondId':9}
        self.login();self.policy.observe_response('GET',self.p['selection']['origin']+'/people/current',self.headers,b'',200,[],b'{"envelope":{"person":{"subject":"person-71","role":"researcher"}}}',self.mode)
        self.assertTrue(self.admit('GET','/records/9')[0]);self.assertFalse(self.admit('GET','/records/10')[0])
    def test_duplicate_scalar_query_is_denied(self):
        self.assertEqual(self.admit('GET','/records?q=one&q=two'),(False,'duplicate-query-key'))
    def test_role_and_distinct_actor_identity_before_dispatch(self):
        from zap_assessment.fe_authenticated_auth import validate_actor_roles
        with self.assertRaisesRegex(ValueError,'role'):validate_actor_roles(self.j['auth'],{'actor-a':{'role':'admin','subject':'one'}})
        with self.assertRaisesRegex(ValueError,'independent'):validate_actor_roles(self.j['auth'],{'actor-a':{'role':'researcher','subject':'one'},'actor-b':{'role':'researcher','subject':'one'}})
    def test_anonymous_policy_still_rejects_identity(self):
        p={'selection':self.p['selection'],'requestPolicies':[{'method':'GET','pathRegex':'/records'}],'limits':self.p['limits']};policy=Policy(p)
        self.assertFalse(policy.admit('GET',self.p['selection']['origin']+'/records',{'Host':'cardinal.test:9543','Authorization':'Bearer private-token'},b'',{})[0]);self.assertTrue(policy.latched)

if __name__=='__main__':unittest.main()
