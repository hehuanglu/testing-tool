import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from test_anonymous import plan
from zap_assessment.anonymous_private_body import resolve_case,materialize_guard_plan
from zap_assessment.anonymous import validate_plan
from zap_assessment.anonymous_guard import authorize
from test_research import BIND

class PrivateAuthBodyTests(unittest.TestCase):
 def fixture(self,root):
  p=plan();p['campaigns']=[];p['authority']['secretPersistenceAccepted']=True
  from test_discovery_transport import modern
  auth=copy.deepcopy(modern()['auth']);auth['loginOperationId']='write';auth['usernameField']='email';auth['passwordField']='password';auth['identity']['actorSource']['operationId']='write';auth['identity']['operationId']='deny';p['discovery']['auth']=auth
  from zap_assessment.discovery import canonical_hash
  p['discoverySha256']=canonical_hash(p['discovery']);c=p['cases'][1];c['category']='public-success';c['body']=None
  f=root/'body.json';f.write_text(json.dumps({'email':'owned@example.test','password':'Synthetic-owned!123'}));f.chmod(0o600);c['privateBodyRef']={'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()};return p,c,f
 def test_body_is_resolved_only_at_private_boundary_and_never_propagates_token(self):
  with tempfile.TemporaryDirectory() as t:
   p,c,f=self.fixture(Path(t));self.assertTrue(validate_plan(p,BIND,p['transportBinding']));resolved=resolve_case(p,c);self.assertIsNone(c['body']);self.assertNotIn('Synthetic-owned',json.dumps(p));self.assertEqual(resolved['body']['password'],'Synthetic-owned!123')
   guard=materialize_guard_plan(p);authorize(guard,{'caseId':c['id']},'POST',p['origin']+c['path'],{'Host':'127.0.0.1:9001','Content-Type':'application/json'},json.dumps(resolved['body']).encode(),p['lockedAt'])
   with self.assertRaises(ValueError):authorize(guard,{'caseId':c['id']},'POST',p['origin']+c['path'],{'Host':'127.0.0.1:9001','Content-Type':'application/json','Authorization':'Bearer fabricated'},json.dumps(resolved['body']).encode(),p['lockedAt'])
 def test_retention_scope_campaign_permissions_and_drift_fail_closed(self):
  with tempfile.TemporaryDirectory() as t:
   p,c,f=self.fixture(Path(t))
   for mutate in [lambda p,c:p['authority'].update(secretPersistenceAccepted=False),lambda p,c:c.update(method='GET'),lambda p,c:c.update(operationId='read'),lambda p,c:p['campaigns'].append({'caseId':c['id']})]:
    bad=copy.deepcopy(p);bc=bad['cases'][1];mutate(bad,bc)
    with self.assertRaises(ValueError):resolve_case(bad,bc)
   f.chmod(0o644)
   with self.assertRaises(ValueError):resolve_case(p,c)
   f.chmod(0o600);f.write_text('{"password":"changed"}')
   with self.assertRaises(ValueError):resolve_case(p,c)
 def test_symlink_token_body_and_missing_credentials_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);p,c,f=self.fixture(root);link=root/'link.json';link.symlink_to(f);c['privateBodyRef']['path']=str(link)
   with self.assertRaises(ValueError):resolve_case(p,c)
   c['privateBodyRef']['path']=str(f)
   for body in [{'email':'owned@example.test','password':'fixed','accessToken':'value'},{'email':'owned@example.test','password':None},{'email':'owned@example.test','password':'Bearer value'}]:
    f.write_text(json.dumps(body));c['privateBodyRef']['sha256']=hashlib.sha256(f.read_bytes()).hexdigest()
    with self.assertRaises(ValueError):resolve_case(p,c)

if __name__=='__main__':unittest.main()
