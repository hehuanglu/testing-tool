import copy,unittest
from zap_assessment.fe_anonymous_contract import admission
from zap_assessment.fe_anonymous_transport import Policy

class BranchAdmission(unittest.TestCase):
 def plan(self):
  return {'authority':{'permissions':['network','browser','private-research-retention']},'journeyIds':['home','validation','register','login','fixture'],'journeys':{'journeys':[
   {'id':'home','network':[]},{'id':'validation','network':[{'method':'POST','path':'/register','absent':True}]},
   {'id':'register','network':[{'method':'POST','path':'/register'}]}, {'id':'login','network':[{'method':'POST','path':'/login'}]},
   {'id':'fixture','network':[],'setupHook':'owned-guest-route-fixtures'}]},'campaigns':[{'id':'active','method':'POST','path':'/login'}],
   'requestPolicies':[{'method':'POST','pathRegex':'/login','effect':'public-read-like','effectProvenance':['reviewed-auth-service']}]}
 def test_read_validation_continue_mutation_and_fixture_blocked(self):
  rows={r['id']:r for r in admission(self.plan())}
  for key in ('home','validation','login'):self.assertTrue(rows[key]['admitted'])
  for key in ('register','fixture'):self.assertEqual(rows[key]['missingPermissions'],['public-mutation'])
  self.assertEqual(rows['active']['missingPermissions'],['active'])
 def test_active_permission_does_not_authorize_mutation(self):
  p=self.plan();p['authority']['permissions'].append('active');p['campaigns'][0]['path']='/register'
  self.assertEqual(admission(p)[-1]['missingPermissions'],['public-mutation'])
 def test_read_like_requires_provenance(self):
  p=self.plan();p['requestPolicies'][0].pop('effectProvenance')
  rows={r['id']:r for r in admission(p)};self.assertEqual(rows['login']['missingPermissions'],['public-mutation'])
 def test_broker_keeps_real_mutation_gate(self):
  p=self.plan();p.update(selection={'origin':'https://site.test'},limits={'maxRequests':5,'maxBodyBytes':1024});p['requestPolicies'].append({'method':'POST','pathRegex':'/register','jsonFields':['x']})
  self.assertEqual(Policy(p).admit('POST','https://site.test/register',{'Host':'site.test','Content-Type':'application/json'},b'{"x":"owned"}',{}),(False,'mutation-permission'))

class MissingFixtureContinuation(unittest.TestCase):
 def test_only_fixture_and_its_dependents_stop(self):
  import tempfile,threading,time
  from pathlib import Path
  from types import SimpleNamespace
  from unittest.mock import patch
  from zap_assessment.fe_anonymous_runner import FERun
  from zap_assessment.fe_anonymous_contract import save,load
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);x=FERun.__new__(FERun);x.out=root;x.hash='owned-test';x.j=SimpleNamespace(append=lambda *a:None)
   x.p={'runId':'owned-fixture-control','authority':{'permissions':['network','browser','private-research-retention','public-mutation']},'requestPolicies':[], 'journeyIds':['fixture','dependent','validation'], 'campaigns':[],
    'journeys':{'recipe':'finalsource-fe/1.0','responsibilities':[],'journeys':[{'id':'fixture','setupHook':'owned-guest-route-fixtures','fixtureRefs':['missing'],'network':[]},{'id':'dependent','prerequisites':['fixture'],'network':[]},{'id':'validation','network':[]}]},
    'limits':{'reserveBytes':2*1024**3},'selection':{'resourceCalibration':{'observedGrowthBytes':1,'requiredRamBytes':4*1024**3}}}
   x.rt=SimpleNamespace(names=[],config=root,resource_sample=lambda:{'hostFree':16*1024**3,'dockerFree':16*1024**3,'ramAvailable':8*1024**3},provision=lambda:None,boundary=lambda:None,cleanup=lambda:None)
   x.monitor=lambda:None;x.configure=lambda:None;x.fixture_values=lambda:{'marker':'owned-fixture'};x.crawl=lambda:None;x.stop=lambda:None
   x.export=lambda:save(root,'UNKNOWN_MUTATIONS.json',{'obligations':[]})
   x.journey=lambda j,f:x.checks.append({'journeyId':j['id'],'outcome':'pass'})
   x.cancel=threading.Event();x.done=threading.Event();x.checks=[];x.ops=[];x.errors=[];x.samples=[];x.mcp=None;x.fixture_ledger=None;x.fixture_client=None;x.fixture_setup_attempted=False;x.fixture_cleanup={};x.fixture_recipe=None
   x.result={'executionStatus':'running','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block','taskCompletion':'partial'}
   with patch('zap_assessment.fe_anonymous_runner.RecordedMCP',return_value=SimpleNamespace(initialize=lambda:{})),patch('zap_assessment.fe_anonymous_runner.inspect',return_value={}),patch('zap_assessment.fe_anonymous_fixtures.DirectFixtures',side_effect=ValueError('owned fixture unavailable')):
    x.execute()
   outcomes={c['journeyId']:c['outcome'] for c in load(root/'CHECKS.json')}
   self.assertEqual(outcomes,{'fixture':'not-run','dependent':'not-run','validation':'pass'});self.assertEqual(x.result['taskCompletion'],'partial')
