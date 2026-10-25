import unittest
from zap_assessment.fe_anonymous_transport import Policy

class BoundaryTests(unittest.TestCase):
    def setUp(self):
        self.p={'selection':{'origin':'https://site.test:9443'},'limits':{'maxRequests':20,'maxBodyBytes':4096},'requestPolicies':[{'method':'GET','pathRegex':'/public','queryKeys':['q']},{'method':'POST','pathRegex':'/session','jsonFields':['email','password']}]}
        self.h={'Host':'site.test:9443'}
    def admit(self,method='GET',url='https://site.test:9443/public',headers=None,body=b'',mode=None):return Policy(self.p).admit(method,url,headers or self.h,body,mode or {})
    def test_canonical_identity_and_downgrade(self):
        self.assertTrue(self.admit()[0]);self.assertFalse(self.admit(url='http://site.test:9443/public')[0]);self.assertFalse(self.admit(headers={**self.h,'Host':'wrong'})[0])
        for key in ('Authorization','Proxy-Authorization','Cookie'):
            self.assertFalse(self.admit(headers={**self.h,key:'secret'})[0])
    def test_latch_and_terminal_transition_no_stripping(self):
        policy=Policy(self.p)
        self.assertEqual(policy.admit('GET','https://site.test:9443/public',{**self.h,'Authorization':'Bearer private'},b'',{})[1],'identity-outside-phase')
        self.assertEqual(policy.admit('GET','https://site.test:9443/public',self.h,b'',{})[1],'identity-latched')
        policy=Policy(self.p)
        self.assertEqual(policy.admit('GET','https://site.test:9443/public',{**self.h,'Authorization':'Bearer private'},b'',{'transition':True})[1],'identity-transition')
    def test_public_auth_body_is_not_authority(self):
        h={**self.h,'Content-Type':'application/json'}
        self.assertTrue(self.admit('POST','https://site.test:9443/session',h,b'{"email":"owned@test","password":"private"}')[0])
        self.assertFalse(self.admit('POST','https://site.test:9443/session',h,b'{"email":{},"password":"private"}')[0])
        self.assertFalse(self.admit('POST','https://site.test:9443/session',h,b'{"email":"x","password":"p","token":"t"}')[0])
    def test_query_cookie_protocol_scope(self):
        self.assertFalse(self.admit(url='https://site.test:9443/public?token=private')[0]);self.assertFalse(self.admit(url='https://site.test:9443/private')[0])
        self.assertFalse(self.admit(headers={**self.h,'Upgrade':'websocket'})[0])
        self.p['requestPolicies'][0].update(anonymousCookies=['consent'],cookieProvenance=['source-ref'])
        self.assertTrue(self.admit(headers={**self.h,'Cookie':'consent=yes'})[0]);self.assertFalse(self.admit(headers={**self.h,'Cookie':'session=x'})[0])

if __name__=='__main__':unittest.main()
