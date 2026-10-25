import copy
import json
from pathlib import Path
import tempfile
import unittest
from zap_assessment.discovery import validate_discovery,compile_plan,validate_plan,verify_identity,canonical_hash
from zap_assessment.research import admit,ResearchRun
from zap_assessment.research_product import admit_adapter
from zap_assessment.discovery_handoff import normalize
from test_research import FakeClient,FakeZap,plan as legacy_plan,BIND


def fixture(kinds=('source','openapi')):
    sources=[{'id':k,'kind':k,'location':'fixture:'+k,'sha256':None,'observedAt':'2026-10-21T00:00:00Z'} for k in kinds]
    refs=[s['id'] for s in sources]
    def op(oid,m,p,protected=True):return {'id':oid,'method':m,'pathTemplate':p,'protected':protected,'semantics':'fixture behavior','input':{'query':['page']},'evidenceRefs':refs}
    d={'schemaVersion':'product-discovery/1.0','product':{'location':'fixture:other-product','environment':'research-test',
       'binding':dict(BIND),'origins':[{'url':'https://api.test:8443','role':'scanner','authorized':True,'bindingVerified':True,'evidenceRefs':refs}]},
       'sources':sources,'operations':[op('login','POST','/v9/session',False),op('register','POST','/v9/people',False),op('identity','GET','/v9/me'),op('list','GET','/v9/things'),op('create','POST','/v9/things'),op('update','PATCH','/v9/things/{objectId}')],
       'auth':{'kind':'json-bearer','loginOperationId':'login','usernameField':'username','passwordField':'passphrase','tokenPointer':'/session/token','headerName':'Authorization','headerPrefix':'Bearer ',
          'identity':{'operationId':'identity','subjectPointer':'/person/uuid','actorSource':{'operationId':'register','subjectPointer':'/person/uuid'},'expectedStatus':200,'contentType':'application/json'},'credentialRef':'private:future-run-actor','evidenceRefs':refs},
       'fixtures':[{'id':'owned','operationIds':['create','update'],'preparation':'create fresh person and owned thing','ownership':'person UUID from independent creation response','postconditions':['read owned thing; denied update unchanged'],'evidenceRefs':refs}],
       'tracks':{t:{'status':'candidate','reason':'prerequisites unresolved until fixture stage','evidenceRefs':refs} for t in ['fe-anonymous','be-anonymous','fe-authenticated','be-authenticated','bola-ownership']},'ui':[],'conflicts':[],'gaps':[]}
    return d


def compiled(d=None):
    return compile_plan(d or fixture(),live_binding=BIND,
        actor={'subject':'person-uuid','runId':'run-1','credentialRef':'private:actor','sourceOperationId':'register','evidenceRefs':['registration.json']},
        requests=[{'method':'GET','path':'/v9/things'},{'method':'PATCH','path':'/v9/things/thing-uuid','fixtureOwned':True,'fixtureRefs':['f']}],
        fixtures=[{'id':'f','runId':'run-1','actorSubject':'person-uuid','paths':['/v9/things/thing-uuid'],'preparationEvidence':['owned.json'],'postconditions':['read back fields']}],
        authority={'fixtureActiveAuthorized':True,'source':'fixture authority'})


class DiscoveryTests(unittest.TestCase):
    def test_independent_source_availability(self):
        for kinds in [('source','openapi'),('source',),('openapi',),('traffic',)]:
            with self.subTest(kinds=kinds):self.assertEqual(compiled(fixture(kinds))['actorSubject'],'person-uuid')
    def test_no_source_spec_or_observation_stays_incomplete(self):
        d=fixture(('deployment',));d['operations']=[];d['auth']=None;d['fixtures']=[]
        d['tracks']['be-authenticated']['status']='blocked'
        validate_discovery(d)
        with self.assertRaisesRegex(ValueError,'no inventory'):validate_discovery(d,executable=True)
    def test_conflict_and_out_of_scope_spec_origin(self):
        d=fixture();d['conflicts']=[{'description':'old spec disagrees with source method','blocking':True,'evidenceRefs':['source','openapi']}]
        with self.assertRaisesRegex(ValueError,'conflict'):compiled(d)
        d=fixture();d['product']['origins'][0].update(authorized=False,bindingVerified=False)
        with self.assertRaisesRegex(ValueError,'origin'):compiled(d)
    def test_method_and_template_vs_concrete_identity(self):
        p=compiled();self.assertEqual(p['operations'][0]['operationId'],'list')
        self.assertEqual(p['operations'][1]['operationId'],'update')
        p['operations'][1]['path']='/v9/things/{objectId}'
        with self.assertRaises(ValueError):validate_plan(p,BIND)
    def test_metadata_fact_changes_reach_plan(self):
        d=fixture();d['product']['origins'][0]['url']='http://internal-service:9010'
        p=compiled(d);self.assertEqual(p['origin'],'http://internal-service:9010')
        d['operations'][2]['pathTemplate']='/v9/whoami'
        q=compiled(d);self.assertEqual(q['identityPath'],'/v9/whoami');self.assertNotEqual(p['discoverySha256'],q['discoverySha256'])
        with self.assertRaisesRegex(ValueError,'adapter target'):admit_adapter(d,BIND)
    def test_required_auth_and_fixture_facts_fail_closed(self):
        for mutation in [lambda d:d.update(auth=None),lambda d:d['auth']['identity'].update(subjectPointer=''),lambda d:d['fixtures'][0].update(preparation=''),lambda d:d['fixtures'][0].update(ownership=''),lambda d:d['fixtures'][0].update(postconditions=[])]:
            d=fixture();mutation(d)
            with self.subTest(d=d):
                with self.assertRaises(ValueError):compiled(d)
    def test_identity_is_json_and_correct_actor(self):
        self.assertTrue(verify_identity(200,'application/json',{'person':{'uuid':'person-uuid'}},'person-uuid','/person/uuid'))
        for status,ct,body in [(200,'text/html','login'),(200,'application/json',{'person':{'uuid':'other'}}),(401,'application/json',{}),(200,'application/json',{})]:
            with self.subTest(status=status,ct=ct,body=body):
                with self.assertRaises(ValueError):verify_identity(status,ct,body,'person-uuid','/person/uuid')
    def test_missing_invalid_or_unknown_provenance(self):
        for refs in [[],['missing']]:
            d=fixture();d['operations'][0]['evidenceRefs']=refs
            with self.assertRaises(ValueError):compiled(d)
    def test_inline_secrets_refused_not_echoed(self):
        for value in [{'password':'private-value'}, {'note':'Bearer abcdefghijklmnop'}, {'token':'private-value'}]:
            d=fixture();d['operations'][0]['input']=value
            with self.assertRaises(ValueError) as cm:compiled(d)
            self.assertNotIn('private-value',str(cm.exception))
    def test_binding_plan_inventory_actor_fixture_drift(self):
        changes=[lambda p:p.update(origin='https://outside.test'),lambda p:p.update(actorSubject='other'),lambda p:p['fixtures'][0].update(actorSubject='other'),lambda p:p['fixtures'][0].update(runId='other'),lambda p:p['fixtures'][0].update(preparationEvidence=[]),lambda p:p['operations'][1].update(fixtureRefs=[]),lambda p:p['operations'][0].update(path='/outside'),lambda p:p['discovery']['operations'][0].update(pathTemplate='/changed'),lambda p:p.update(jobStore='queue'),lambda p:p.update(ruleIds=[]),lambda p:p.update(ruleIds=[999999])]
        for change in changes:
            p=compiled();change(p)
            with self.subTest(change=change):
                with self.assertRaises(ValueError):admit(p,BIND)
        with self.assertRaisesRegex(ValueError,'binding drift'):admit(compiled(),{**BIND,'startedAt':'other'})
        # Admission allows a meaningful rule subset before ResearchRun locks it.
        # Post-lock edits are covered by test_in_memory_plan_drift_rejected;
        # missing selected-technique duties are covered by question reconciliation.
        single=compiled();single['ruleIds']=[40012]
        self.assertEqual(admit(single,BIND)['ruleIds'],[40012])
    def test_executor_consumes_received_plan_hash_and_identity_target(self):
        class Client(FakeClient):
            def call_tool(self,name,args):
                self.calls.append((name,args))
                if name.endswith('prepare'):return 'Session ID: opaque'
                if name.endswith('validate'):return 'Valid: true'
                return ''
        with tempfile.TemporaryDirectory() as tmp:
            p=compiled();c=Client();r=ResearchRun(plan=p,binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            r.prepare('test');r.finish()
            self.assertEqual(c.calls[0][1]['targetUrl'],'https://api.test:8443/v9/me')
            self.assertEqual(json.loads((Path(tmp)/'plan.json').read_text()),p)
            self.assertIn(r.plan_digest,(Path(tmp)/'journal.jsonl').read_text())
            with self.assertRaisesRegex(ValueError,'outside locked'):r.start('attack','https://outside.test/v9/things')
    def test_legacy_schema_admission_preserved(self):
        self.assertEqual(admit(legacy_plan(),BIND)['actorSubject'],'42')
        p=legacy_plan();p['origin']='https://api.test'
        with self.assertRaises(ValueError):admit(p,BIND)
        p=legacy_plan();p['assuranceProfile']='strict'
        with self.assertRaises(ValueError):admit(p,BIND)
    def test_deployment_metadata_cannot_invent_operations(self):
        with self.assertRaisesRegex(ValueError,'observation source'):compiled(fixture(('deployment',)))
    def test_in_memory_plan_drift_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClient();r=ResearchRun(plan=compiled(),binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            r.plan['origin']='https://outside.test'
            with self.assertRaisesRegex(RuntimeError,'in-memory'):r.current()
    def test_action_query_body_and_method_are_frozen(self):
        p=compiled();p['execution']={'seeds':[],'crawl':'/v9/me','attacks':[{'method':'GET','path':'/v9/things?page=1'}]}
        validate_plan(p,BIND)
        q=copy.deepcopy(p);q['execution']['attacks'][0]['path']='/v9/things?undiscovered=1'
        with self.assertRaisesRegex(ValueError,'query parameter'):validate_plan(q,BIND)
        q=copy.deepcopy(p);q['execution']['attacks'][0]['method']='DELETE'
        with self.assertRaisesRegex(ValueError,'action outside'):validate_plan(q,BIND)
        with tempfile.TemporaryDirectory() as tmp:
            c=FakeClient();r=ResearchRun(plan=p,binding=lambda:BIND,client=c,monitor_client=c,zap=FakeZap(),output=tmp)
            with self.assertRaisesRegex(ValueError,'input outside'):r.start('attack',p['origin']+'/v9/things?page=2')
            self.assertFalse(c.calls)
    def test_local_source_drift_requires_rediscovery(self):
        import hashlib
        from zap_assessment.discovery import verify_local_sources
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'routes.ts';f.write_text('route')
            d=fixture(('source',));d['sources'][0].update(location=str(f)+':1',sha256=hashlib.sha256(f.read_bytes()).hexdigest())
            self.assertTrue(verify_local_sources(d));f.write_text('changed')
            with self.assertRaisesRegex(ValueError,'source changed'):verify_local_sources(d)
    def test_output_details_refs_guard_separation_and_raw_unchanged(self):
        raw=[{'pluginId':'100','name':'Finding','risk':'Low','confidence':'Medium','url':'https://api.test/v9/things','description':'Native desc','solution':'Native fix','evidence':'marker','id':'1','method':'GET','param':'x'},
             {'pluginId':'100','name':'Finding','risk':'Low','confidence':'Medium','url':'http://api.test/__research_scope_denied__','id':'2'}]
        before=copy.deepcopy(raw);groups,excluded=normalize(raw,raw_ref='/private/raw.json',raw_sha='a'*64)
        self.assertEqual(raw,before);self.assertEqual(len(groups),1);self.assertEqual(len(excluded),1)
        self.assertEqual(groups[0]['description'],'Native desc');self.assertEqual(groups[0]['instances'][0]['evidence'],'marker')
        self.assertEqual(groups[0]['evidenceRefs'][0]['jsonPointer'],'/alerts/0');self.assertEqual(groups[0]['source'],'ZAP')

if __name__=='__main__':unittest.main()
