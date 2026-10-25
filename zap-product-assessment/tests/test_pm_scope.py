"""PM audit O01–O07 and 16 acceptance scenarios. Offline, no target/Scanner access."""
import contextlib,copy,hashlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.product_scope import (reconcile,continue_work,apply_completion,compact_results,
    remaining_actions,select_techniques,inventory_from_operations,fe_readback)
from zap_assessment.product_workflow import coverage_gaps,reconcile_responsibilities
from zap_assessment.fe_authenticated_transport import AuthenticatedPolicy,path_matches,valid_payload,valid_owned_id
from zap_assessment.fe_authenticated_discovery import discover
from zap_assessment.fe_authenticated_contract import validate_journeys
from zap_assessment.executor_routing import classify_workload,choose_executor

WORKSPACE=Path(__file__).resolve().parents[2]

def case(cid='search',required=('active:query:q','result-read'),prerequisites=(),actions=()):
    return {'caseId':cid,'evidenceRefs':['product-source'],'requiredEvidence':list(required),
            'prerequisites':list(prerequisites),'actions':list(actions)}

def inventory(cases,**kw):
    return {'productLocation':'/owned/product','track':'fe-authenticated','complete':True,'cases':cases,**kw}

def observed(*units,outcome='matched'):
    return {'outcome':outcome,'resultRead':True,'evidenceUnits':list(units)}

def action(aid,kind='execute',effect='read',**kw):return {'id':aid,'kind':kind,'effect':effect,**kw}

class OfflineAuditTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_O01_empty_campaign_is_valid_ui_workload_but_not_active_task(self):
        d=discover(WORKSPACE/'finalsource','finalsource-fe-auth/1.0');j=copy.deepcopy(d['journeys']);j['campaigns']=[]
        validate_journeys(j)  # intentionally legal finite UI executor input
        p={'track':'fe-authenticated','discovery':{'responsibilityInventory':inventory([case()])}}
        self.assertEqual(fe_readback(p,{'journeys':[],'delivery':[]},[])['taskCompletion'],'partial')
        ui=inventory([case(required=('ui','result-read'))])
        self.assertEqual(reconcile(ui,{'search':observed('ui','result-read')},{})['taskCompletion'],'complete')
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_O02_deleted_journey_and_workload_duty_still_in_product_inventory(self):
        d=discover(WORKSPACE/'finalsource','finalsource-fe-auth/1.0');j=copy.deepcopy(d['journeys'])
        j['journeys']=[x for x in j['journeys'] if x['id']!='account-create'];j['responsibilities']=[x for x in j['responsibilities'] if x['id']!='account-create']
        validate_journeys(j)
        inv=d['responsibilityInventory'];self.assertIn('api-post-api-v1-accounts',{c['caseId'] for c in inv['cases']})
        inv['complete']=True
        obs={c['caseId']:{**observed(*c['requiredEvidence']),'role':c.get('role')} for c in inv['cases'] if c['caseId']!='api-post-api-v1-accounts'}
        result=reconcile(inv,obs,{},workload_cases=[])
        self.assertEqual([r['caseId'] for r in result['openResponsibilities']],['api-post-api-v1-accounts'])
    def test_O03_no_vacuous_completion_no_fixed_journey_count(self):
        result=reconcile(inventory([case()]),{'search':observed('ui','passive','baseline')},{})
        report=apply_completion({'executionStatus':'completed','journeys':[{}]*64,'taskCompletion':'completed'},result)
        self.assertEqual(report['taskCompletion'],'partial');self.assertTrue(report['notPerformed']);self.assertTrue(report['nextSteps'])
    def test_O04_empty_inventory_does_not_attest_scope(self):
        self.assertEqual(reconcile_responsibilities([],{}, {})['taskCompletion'],'partial')
        self.assertEqual(reconcile(inventory([]),{}, {})['taskCompletion'],'partial')
    def test_O05_protected_get_allocation_gap_survives_baseline(self):
        doc={'operations':[{'id':'owned','protected':True,'method':'GET','pathTemplate':'/owned'}]}
        self.assertTrue(coverage_gaps(doc,'be-authenticated',{'owned'},{'supportedOperationIds':['owned']},{'execution':{'attacks':[],'seeds':[{'method':'GET','path':'/owned'}]}}))
    def test_O07_uuid_mapping_still_exact_owned_and_local(self):
        uid='123e4567-e89b-12d3-a456-426614174000'
        self.assertTrue(path_matches({'path':'/api/items/{ownedId}'},'/api/items/'+uid))
        for value in ('../private','%2fadmin','x/y','//evil','%2e%2e'):
            self.assertFalse(path_matches({'path':'/api/items/{ownedId}'},'/api/items/'+value))
        self.assertTrue(valid_owned_id(uid,'uuid'));self.assertFalse(valid_owned_id(uid,'integer'))

class PMAcceptanceTests(unittest.TestCase):
    def test_01_new_api_02_removed_active_03_empty_campaign_04_removed_workload(self):
        inv=inventory([case('ui',('ui',)),case('api',('active:body:name',))])
        result=reconcile(inv,{'ui':observed('ui')},{},[case('ui',('ui',))])
        self.assertEqual([r['caseId'] for r in result['openResponsibilities']],['api'])
        self.assertEqual(result['nextActions'][0]['action'],'execute')
    def test_05_uuid_nested_cookie_classification_routes_to_actual_compatible_lane(self):
        request={'method':'PUT','path':'/items/123e4567-e89b-12d3-a456-426614174000','body':{'profile':{'name':'A'}}}
        decision=classify_workload(request,auth_kind='form',role='editor')
        self.assertTrue(decision['nestedJson']);self.assertFalse(decision['runtimeQualified']);self.assertTrue(decision['responsibilityRetained'])
        from test_executor_routing import candidate,ARGS
        lane=candidate('form-native');lane['configuredAuthKinds']=['form']
        chosen=choose_executor([candidate('bearer-only'),lane],'zap_attack_start',{**ARGS,'postData':json.dumps(request['body'])},auth_kind='form')
        self.assertEqual(chosen['selected'],'form-native');self.assertEqual(chosen['execution'],'not-operated')
        schema={'type':'object','properties':{'profile':{'type':'object','properties':{'name':{'type':'string'}},'required':['name'],'additionalProperties':False}},'required':['profile'],'additionalProperties':False}
        self.assertTrue(valid_payload({'jsonSchema':schema},request['body']))
        self.assertFalse(valid_payload({'jsonSchema':schema},{'profile':{'name':'A','owner':'other'}}))
    def test_06_missing_role_preserved_other_role_executes(self):
        inv=inventory([case('admin',prerequisites=('admin-session',)),case('user',actions=[action('user-read')])]);calls=[]
        result=continue_work(inv,{}, {},{'user-read':lambda a:(calls.append(a['id']) or {'observations':{'user':observed('active:query:q','result-read')}})},persist=lambda x:None)
        self.assertEqual(calls,['user-read']);self.assertEqual([r['caseId'] for r in result['openResponsibilities']],['admin'])
        bad=copy.deepcopy(inv);bad['cases'][0].update(disposition='not-applicable',reason='no admin',gapKind='role',applicability='missing')
        with self.assertRaises(ValueError):reconcile(bad,{}, {})
    def test_08_selector_repair_after_ack_12_pin_rollover_does_not_replay(self):
        events=[{'actionId':'create','caseId':'edit','state':'acknowledged','effect':'mutation'}]
        cs=[case('edit',('post-state',),actions=[action('create',effect='mutation'),action('repair','repair'),action('readback')])]
        fresh=remaining_actions(cs,events);self.assertEqual([a['id'] for a in fresh[0]['actions']],['repair','readback'])
        calls=[]
        def repair(a):calls.append('repair');return {'prerequisites':{'selector-repaired':True}}
        fresh[0]['actions'][1]['requires']=['selector-repaired']
        result=continue_work(inventory(fresh),{}, {},{'repair':repair,'readback':lambda a:{'observations':{'edit':observed('post-state')}}},attempts=events,persist=lambda x:calls.append(x['state']))
        self.assertEqual(result['taskCompletion'],'complete');self.assertNotIn('create',calls);self.assertEqual(events[0]['state'],'acknowledged')
    def test_09_unknown_mutation_only_blocks_dependencies_independent_work_executes(self):
        cs=[case('write',actions=[action('post',effect='mutation'),action('blind-retry',effect='mutation')]),
            case('other',actions=[action('read')])];calls=[];events=[]
        def fail(a):calls.append('post');raise TimeoutError()
        result=continue_work(inventory(cs),{}, {},{'post':fail,'blind-retry':lambda a:self.fail('replayed unknown mutation'),
            'read':lambda a:{'observations':{'other':observed('active:query:q','result-read')}}},persist=events.append)
        self.assertTrue(result['observations']['write']['outcomeUnknown']);self.assertEqual(result['observations']['other']['outcome'],'matched')
        self.assertEqual([e['state'] for e in events],['intent','unknown','intent','acknowledged'])
    def test_10_batch_cap_new_allocation_keeps_reserve_and_prior_observation(self):
        inv=inventory([case('first',actions=[action('batch-1')]),case('second',actions=[action('batch-2')])])
        first=continue_work(inv,{}, {},{'batch-1':lambda a:{'observations':{'first':observed('active:query:q','result-read')}}},persist=lambda x:None,max_actions=1)
        self.assertEqual(first['taskCompletion'],'partial')
        second=continue_work(inv,first['observations'],{}, {'batch-1':lambda a:self.fail('ACK replay'),'batch-2':lambda a:{'observations':{'second':observed('active:query:q','result-read')}}},attempts=first['actionsPerformed'],persist=lambda x:None)
        self.assertEqual(second['taskCompletion'],'complete')
    def test_11_fixture_preparation_then_real_case_callback_before_handoff(self):
        cs=[case(prerequisites=('fixture',),actions=[action('setup','prepare-fixture',effect='mutation'),action('check',requires=['fixture'])])];calls=[]
        def setup(a):calls.append('setup');return {'prerequisites':{'fixture':True}}
        def check(a):calls.append('check');return {'observations':{'search':observed('active:query:q','result-read',outcome='violated')}}
        result=continue_work(inventory(cs),{}, {},{'setup':setup,'check':check},persist=lambda x:None)
        self.assertEqual(calls,['setup','check']);self.assertEqual(result['taskCompletion'],'complete');self.assertEqual(result['observations']['search']['outcome'],'violated')
    def test_13_bola_source_hypothesis_never_creates_policy_approval(self):
        from zap_assessment.product_handoff import direct_dimensions
        run=dict(executionStatus='completed',evidenceStatus='complete',securityVerdict='inconclusive',cleanupStatus='retained',gateDecision='review_required')
        result=direct_dimensions({'cases':[{'id':'x','request':{'operationRef':'read'}}],'policyStatus':'source-hypothesis'},[{'caseId':'x','outcome':'matched'}],run,[])
        self.assertEqual(result['policy']['status'],'source-hypothesis');self.assertNotIn('reviewerApproval',result);self.assertEqual(result['rawStatuses']['securityVerdict'],'inconclusive')
    def test_14_report_samples_do_not_become_full_totals(self):
        from zap_assessment.report_reconciliation import reconcile_findings_report
        report={'site':[{'alerts':[{'pluginid':'7','name':'x','riskcode':'1','confidence':'2','count':'999','instances':[]}]}]}
        r=reconcile_findings_report({'session':'s','rows':[],'status':'partial','total':999},report)
        self.assertEqual(r['status'],'partial');self.assertFalse(r['nativeReportExhaustive']);self.assertEqual(r['findingsRowsRead'],0)
    def test_15_format_and_exit0_do_not_change_scope_or_attribution(self):
        scope=reconcile(inventory([case()]),{}, {});alerts={'alerts':[{'source':'ZAP','nativeRuleId':'7','severity':'High','instanceCount':3}],'summary':{'instances':3}}
        with tempfile.TemporaryDirectory() as td:
            compact_results(Path(td)/'out',{'executionStatus':'completed','exitCode':0},alerts,scope)
            saved=json.loads((Path(td)/'out/RUN.json').read_text());a=json.loads((Path(td)/'out/ALERTS.json').read_text())
            self.assertEqual(saved['notPerformed'],scope['openResponsibilities']);self.assertEqual(a['alerts'],alerts['alerts']);self.assertEqual(a['summary'],alerts['summary']);self.assertEqual(a['taskCompletion'],'partial')
            self.assertEqual({p.name for p in (Path(td)/'out').iterdir()},{'RUN.json','ALERTS.json'})
    def test_16_user_stop_and_phase_boundary(self):
        result=continue_work(inventory([case(actions=[action('never')])],phaseOnly=True),{}, {},{'never':lambda a:self.fail('continued after PM stop')},persist=lambda x:None,stop=True)
        self.assertEqual(result['taskCompletion'],'partial');self.assertFalse(result['wholeTrackComplete'])
    def test_technique_selection_adds_obligations_does_not_close_them(self):
        inv=select_techniques(inventory([case(required=('technique-decision','result-read'))]),'search',['active:body:profile.name'],'stored user input')
        self.assertEqual(reconcile(inv,{'search':observed('technique-decision','result-read')},{})['taskCompletion'],'partial')

class AuthDenialTests(unittest.TestCase):
    def setUp(self):
        from test_fe_authenticated_policy import AuthenticatedPolicyTests
        fixture=AuthenticatedPolicyTests();fixture.setUp();fixture.login();self.f=fixture;self.p=fixture.policy
        self.probe(200)
    def probe(self,status):
        f=self.f;return self.p.observe_response('GET',f.p['selection']['origin']+'/people/current',f.headers,b'',status,[],b'{"envelope":{"person":{"subject":"person-71","role":"researcher"}}}',f.mode)
    def test_O06_07_expected_403_rechecks_identity_without_global_auth_loss(self):
        f=self.f;r=self.p.observe_response('GET',f.p['selection']['origin']+'/records',f.headers,b'',403,[],b'{"denied":true}',f.mode)
        self.assertTrue(r['authorizationDenied']);self.assertNotIn('identityFailure',r);self.assertFalse(self.p.latched)
        self.assertEqual(f.admit('GET','/records?q=seed'),(False,'identity-probe-only'))
        self.probe(200);self.assertTrue(f.admit('GET','/records?q=seed')[0])
    def test_09_actual_loss_stops_producer_safely(self):
        r=self.probe(401);self.assertIn('identityFailure',r);self.assertTrue(self.p.latched);self.assertFalse(self.f.admit('GET','/records?q=seed')[0])

class ContinuationReaderTests(unittest.TestCase):
    def test_direct_or_ui_check_cannot_supply_active_unit(self):
        from zap_assessment.product_scope_cli import read_action_result
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'PLAN.json').write_text(json.dumps({'track':'bola-ownership'}));(p/'CHECKS.json').write_text(json.dumps([{'caseId':'ui','outcome':'matched'}]))
            with self.assertRaisesRegex(ValueError,'cannot satisfy'):read_action_result(p,{'resultBindings':[{'checkId':'ui','caseId':'search','evidenceUnits':['active:query:q']}]})
    def test_empty_cli_reconcile_exit0_means_command_success(self):
        from zap_assessment.product_cli import main
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            for name,data in [('inv',inventory([case()])),('obs',{}),('pre',{})]:(p/(name+'.json')).write_text(json.dumps(data))
            with contextlib.redirect_stdout(io.StringIO()):code=main(['scope','reconcile','--inventory',str(p/'inv.json'),'--observations',str(p/'obs.json'),'--prerequisites',str(p/'pre.json'),'--output',str(p/'out')])
            self.assertEqual(code,0);self.assertEqual(json.loads((p/'out/RUN.json').read_text())['taskCompletion'],'partial')


class FixtureDemandTests(unittest.TestCase):
    def test_setup_only_creates_requested_objects_and_never_replays_ack(self):
        from zap_assessment.fe_authenticated_fixture_finalsource import prepare_data
        actor={'subject':71,'setupToken':'unit-private','fixtures':{'marker':'owned-unit'}};calls=[];accounts=[]
        class Client:
            def __init__(self,*a,**k):pass
            def send(self,method,path,body=None,token=None):
                calls.append((method,path))
                if method=='POST':
                    account={'id':len(accounts)+1,'user_id':71,**body};accounts.append(account);return {'data':{'account':account}}
                return {'data':{'user_id':71,'accounts':accounts}}
        with tempfile.TemporaryDirectory() as td,patch('zap_assessment.fe_authenticated_fixture_finalsource.FixtureClient',Client):
            first=prepare_data({},actor,td,{'owned-account'})
            self.assertIn('ownedAccountId',first);self.assertNotIn('nativeAccountId',first)
            self.assertEqual(sum(m=='POST' for m,p in calls),1)
            prepare_data({},actor,td,{'owned-account'})
            self.assertEqual(sum(m=='POST' for m,p in calls),1)
            third=prepare_data({},actor,td,{'native-account'})
            self.assertIn('nativeAccountId',third);self.assertEqual(sum(m=='POST' for m,p in calls),2)
    def test_category_only_has_no_bill_insert_or_unneeded_accounts(self):
        from zap_assessment.fe_authenticated_fixture_finalsource import prepare_data
        actor={'subject':71,'setupToken':'unit-private','fixtures':{'marker':'owned-unit'}};asked=[]
        class Client:
            def __init__(self,*a,**k):pass
            def send(self,method,path,body=None,token=None):
                if method!='GET':raise AssertionError('unneeded mutation')
                return {'data':[{'category_id':8,'name':'owned-unit-category'}]} if 'categories' in path else {'data':{'user_id':71,'accounts':[]}}
        def db(bound,actor,selection,out,requested):asked.append(requested);return {'categoryId':8}
        with tempfile.TemporaryDirectory() as td,patch('zap_assessment.fe_authenticated_fixture_finalsource.FixtureClient',Client),patch('zap_assessment.fe_authenticated_fixture_finalsource.db_prerequisites',side_effect=db):
            values=prepare_data({},actor,td,{'category'},{'owned':True})
            self.assertEqual(asked,[{'category'}]);self.assertEqual(values,{'categoryId':8})
    def test_role_specific_actor_map_does_not_force_one_role(self):
        from zap_assessment.fe_authenticated_auth import validate_actor_roles
        validate_actor_roles({'identity':{'expectedRole':'reader','roleByActor':{'editor':'editor'}}},
            {'reader':{'role':'reader','subject':'one'},'editor':{'role':'editor','subject':'two'}})

class ScopeContextTests(unittest.TestCase):
    def test_same_technique_wrong_role_or_state_cannot_close(self):
        c=case();c.update(role='editor',state='populated')
        self.assertEqual(reconcile(inventory([c]),{'search':{**observed('active:query:q','result-read'),'role':'reader','state':'populated'}},{})['taskCompletion'],'partial')
        self.assertEqual(reconcile(inventory([c]),{'search':{**observed('active:query:q','result-read'),'role':'editor','state':'populated'}},{})['taskCompletion'],'complete')
    def test_source_discovery_without_registry_retains_cookie_nested_facts(self):
        from zap_assessment.product_source import source_inventory
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'route.ts';p.write_text('owned source')
            facts={'sources':[{'id':'src','path':'route.ts','sha256':hashlib.sha256(p.read_bytes()).hexdigest()}],
                'operations':[{'id':'edit','method':'PUT','pathTemplate':'/items/{uuid}','protected':True,'semantics':'owned edit','input':{'body':{'profile':{'name':'text'}}},'evidenceRefs':['src'],'confidence':'medium'}],
                'auth':{'kind':'cookie','loginPath':'/signin','identityProbe':'/session'}}
            candidate=source_inventory(td,facts)
            self.assertEqual(candidate['authObservations']['kind'],'cookie');self.assertIsNone(candidate['binding'])
            inv=inventory_from_operations(candidate,'be-authenticated');self.assertEqual(inv['cases'][0]['input'],facts['operations'][0]['input'])
            self.assertFalse(inv['complete'])
    def test_ui_binding_cannot_claim_active_even_with_technique_label(self):
        inv=inventory([{**case(),'observationBindings':{'active:query:q':{'kind':'ui','ids':['ui']}}}])
        with self.assertRaisesRegex(ValueError,'UI cannot'):fe_readback({'track':'fe-authenticated','discovery':{'responsibilityInventory':inv}}, {'journeys':[{'id':'ui','completed':True}]},[])
    def test_pending_start_durable_restart_never_dispatches_again(self):
        events=[{'actionId':'start','caseId':'search','state':'intent','effect':'start'}]
        inv=inventory([case(actions=[action('start',effect='start'),action('again',effect='start')])])
        result=continue_work(inv,{}, {},{'start':lambda a:self.fail('replayed pending start'),'again':lambda a:self.fail('retry unknown')},attempts=events,persist=lambda x:None)
        self.assertTrue(result['observations']['search']['outcomeUnknown']);self.assertEqual(result['actionsPerformed'],[])


class ContinuationControlTests(unittest.TestCase):
    def test_owned_loopback_setup_ack_rollover_reads_without_recreating(self):
        # Owned only for this test; no Docker/product/shared scanner is used.
        from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
        import http.client,threading,secrets
        marker=secrets.token_hex(12);state={'creates':0,'object':None}
        class App(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def send(self,status,value):
                blob=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(blob)));self.end_headers();self.wfile.write(blob)
            def do_POST(self):
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                if self.path!='/objects' or data.get('owner')!=marker:return self.send(403,{})
                state['creates']+=1;state['object']={'id':'123e4567-e89b-12d3-a456-426614174000','owner':marker}
                self.send(201,state['object'])
            def do_GET(self):
                if self.path=='/owner':return self.send(200,{'owner':marker})
                if state['object'] and self.path=='/objects/'+state['object']['id']:return self.send(200,state['object'])
                self.send(404,{})
        app=ThreadingHTTPServer(('127.0.0.1',0),App);thread=threading.Thread(target=app.serve_forever,daemon=True);thread.start()
        self.assertEqual(app.server_address[0],'127.0.0.1');port=app.server_address[1]
        def send(method,path,body=None):
            connection=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
            try:
                connection.request(method,path,json.dumps(body) if body is not None else None,{'Content-Type':'application/json'})
                response=connection.getresponse();return response.status,json.loads(response.read())
            finally:connection.close()
        try:
            self.assertEqual(send('GET','/owner'),(200,{'owner':marker})) # ownership before effects
            cs=[case('populated',('owned-readback',),('object-ready',),[
                action('create-owned','prepare-fixture',effect='mutation'),action('read-owned',requires=['object-ready'])])]
            inv=inventory(cs,track='bola-ownership');events=[]
            def create(a):
                status,value=send('POST','/objects',{'owner':marker});self.assertEqual(status,201);self.assertEqual(value['owner'],marker)
                return {'prerequisites':{'object-ready':True}}
            first=continue_work(inv,{}, {},{'create-owned':create},persist=events.append,max_actions=1)
            self.assertEqual(first['taskCompletion'],'partial');self.assertEqual(state['creates'],1)
            def read(a):
                status,value=send('GET','/objects/'+state['object']['id']);self.assertEqual(status,200);self.assertEqual(value['owner'],marker)
                return {'observations':{'populated':observed('owned-readback')}}
            inv['cases']=remaining_actions(cs,first['actionHistory'])
            second=continue_work(inv,first['observations'],first['prerequisites'],{'create-owned':lambda a:self.fail('ACK replay'),'read-owned':read},attempts=first['actionHistory'],persist=events.append)
            self.assertEqual(second['taskCompletion'],'complete');self.assertEqual(state['creates'],1)
        finally:app.shutdown();app.server_close();thread.join(timeout=2)
    def test_native_reader_requires_changed_payload_and_native_terminal(self):
        from zap_assessment.product_scope_cli import native_readback
        from zap_assessment.research import manifest
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);plan={'origin':'http://unit.test','ruleIds':[40018],'execution':{'attacks':[{'method':'GET','path':'/search?q=plain'}]}}
            files={'PLAN.json':plan,'operations.json':[{'nativeScanId':'1','terminal':True}],
                'IDENTITY_STRATEGY.json':{'nativeValidated':True},'active-attribution-0.json':{'nativeScanId':'1','messageIds':{'messagesIds':['7']}}}
            raw={'id':'7','requestHeader':(chr(13)+chr(10)).join(['GET http://unit.test/search?q=plain HTTP/1.1', 'Authorization: Bearer synthetic-unit', 'X-ZAP-Scan-ID: 40018', '']),'responseHeader':'HTTP/1.1 200 OK'+chr(13)+chr(10),'requestBody':''}
            for name,value in {**files,'raw-history.json':[raw]}.items():(root/name).write_text(json.dumps(value))
            mapping={'resultBindings':[{'kind':'active','attackIndex':0,'caseId':'search','evidenceUnits':['active:query:q']}]}
            manifest(root)
            self.assertEqual(native_readback(root,{'workload':{}},mapping)['observations'],{})
            raw['requestHeader']=raw['requestHeader'].replace('q=plain','q=changed')
            (root/'raw-history.json').write_text(json.dumps([raw]));manifest(root)
            self.assertIn('search',native_readback(root,{'workload':{}},mapping)['observations'])
            wrong=copy.deepcopy(mapping);wrong['resultBindings'][0]['evidenceUnits']=['active:query:other']
            self.assertEqual(native_readback(root,{'workload':{}},wrong)['observations'],{})
            (root/'operations.json').write_text(json.dumps([{'nativeScanId':'1','terminal':False}]))
            manifest(root)
            self.assertEqual(native_readback(root,{'workload':{}},mapping)['observations'],{})
    def test_preparation_reader_verifies_actor_before_fulfilling_prerequisite(self):
        from zap_assessment.product_scope_cli import read_action_result
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);proof=root/'register.json';proof.write_text(json.dumps({'status':201,'body':{'subject':'unit-actor'}}))
            actor={'subject':'unit-actor','provenance':{'subject':'unit-actor','evidenceRefs':[str(proof)]},'registrationSha256':hashlib.sha256(proof.read_bytes()).hexdigest()}
            (root/'actors.json').write_text(json.dumps({'actor-a':actor}))
            d={'prerequisiteBindings':{'session-a':'actor-a','session-b':'missing'}}
            result=read_action_result(root,d,plan={'track':'be-authenticated'},command='prepare')
            self.assertEqual(result,{'prerequisites':{'session-a':True}})
            proof.write_text('{}')
            with self.assertRaisesRegex(ValueError,'evidence'):read_action_result(root,d,plan={'track':'be-authenticated'},command='prepare')


class RolloverAndReportingTests(unittest.TestCase):
    def test_reconciled_unknown_does_not_resurrect_after_another_allocation(self):
        events=[{'actionId':'old-post','caseId':'search','state':'unknown','effect':'mutation'}]
        inv=inventory([case(actions=[action('read-state','reconcile-state')])])
        result=continue_work(inv,{'search':{'outcomeUnknown':True}}, {},{'read-state':lambda a:{'observations':{'search':{**observed('active:query:q','result-read'),'stateReconciled':True}}}},attempts=events,persist=lambda x:None)
        self.assertEqual(result['taskCompletion'],'complete')
        again=continue_work(inv,result['observations'],{}, {},attempts=result['actionHistory'],persist=lambda x:None)
        self.assertEqual(again['taskCompletion'],'complete');self.assertFalse(again['observations']['search']['outcomeUnknown'])
    def test_cli_previous_automatically_preserves_unknown_and_inventory(self):
        from zap_assessment.product_cli import main
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)
            data={'inv':inventory([case()]),'obs':{'search':{'outcomeUnknown':True}},'pre':{},'actions':{}}
            for k,v in data.items():(p/(k+'.json')).write_text(json.dumps(v))
            def command(output,extra=()):return ['scope','continue','--inventory',str(p/'inv.json'),'--observations',str(p/'obs.json'),'--prerequisites',str(p/'pre.json'),'--actions',str(p/'actions.json'),'--output',str(p/output),*extra]
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(command('first')),0)
            (p/'obs.json').write_text('{}')
            with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(command('second',['--previous',str(p/'first')])),0)
            result=json.loads((p/'second/RUN.json').read_text());self.assertTrue(result['observations']['search']['outcomeUnknown']);self.assertEqual(result['taskCompletion'],'partial')
    def test_compact_handoff_keeps_discovery_gap_and_redacts_credentials(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'handoff';rec=reconcile(inventory([],complete=False),{}, {})
            compact_results(p,{'password':'short-secret','executionStatus':'completed'},{'taskCompletion':'complete','scope':{'taskCompletion':'complete'},'alerts':[]},rec)
            r=json.loads((p/'RUN.json').read_text());a=json.loads((p/'ALERTS.json').read_text())
            self.assertTrue(r['notPerformed']);self.assertTrue(r['nextSteps']);self.assertNotIn('short-secret',(p/'RUN.json').read_text())
            self.assertEqual(a['taskCompletion'],'partial');self.assertEqual(a['scope']['taskCompletion'],'partial')


class ExistingEntryDispatchTests(unittest.TestCase):
    def test_cli_dispatch_reads_checker_not_exit0_and_rejects_foreign_task(self):
        from zap_assessment.product_scope_cli import main
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);run=p/'executor'
            inv=inventory([case(required=('direct-read',),actions=[action('run')])],track='bola-ownership')
            plan={'track':'bola-ownership','discovery':{'product':{'location':'/owned/product'}},'workload':{'cases':[{'id':'checked','request':{'method':'GET'}}]}}
            documents={'inv':inv,'obs':{},'pre':{},'plan':plan,'actions':{'run':{'arguments':['run','--plan',str(p/'plan.json'),'--selection',str(p/'plan.json'),'--output',str(run)],'resultBindings':[{'caseId':'search','checkId':'checked','evidenceUnits':['direct-read']}]}}}
            for name,value in documents.items():(p/(name+'.json')).write_text(json.dumps(value))
            def argv(out):return ['continue','--inventory',str(p/'inv.json'),'--observations',str(p/'obs.json'),'--prerequisites',str(p/'pre.json'),'--actions',str(p/'actions.json'),'--output',str(p/out)]
            def executor(args):
                run.mkdir();(run/'CHECKS.json').write_text(json.dumps([{'caseId':'checked','outcome':'violated'}]));return 0
            # Unit seam at executor transport; independent reader invocation remains mandatory.
            with patch('zap_assessment.product_cli.main',side_effect=executor) as dispatch,patch('zap_assessment.product_bola.verify',return_value={'integrityVerified':True}) as reader,contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv('out')),0);self.assertEqual(dispatch.call_count,1);self.assertEqual(reader.call_count,1)
            result=json.loads((p/'out/RUN.json').read_text());self.assertEqual(result['taskCompletion'],'complete');self.assertEqual(result['observations']['search']['outcome'],'violated')
            plan['discovery']['product']['location']='/foreign';(p/'plan.json').write_text(json.dumps(plan))
            with patch('zap_assessment.product_cli.main',side_effect=AssertionError('foreign task dispatched')) as dispatch,contextlib.redirect_stdout(io.StringIO()):main(argv('foreign-out'))
            self.assertFalse(dispatch.called);self.assertEqual(json.loads((p/'foreign-out/RUN.json').read_text())['taskCompletion'],'partial')


class FixtureDepthTests(unittest.TestCase):
    def test_expense_fixture_does_not_create_pagination_batch(self):
        from zap_assessment.fe_authenticated_fixture_finalsource import prepare_data
        actor={'subject':71,'setupToken':'unit-private','fixtures':{'marker':'owned-unit','today':'2026-10-25'}};accounts=[];transactions=[]
        class Client:
            def __init__(self,*a,**k):pass
            def send(self,method,path,body=None,token=None):
                if path=='/api/v1/accounts' and method=='POST':
                    value={**body,'id':5,'user_id':71};accounts.append(value);return {'data':{'account':value}}
                if path=='/api/v1/accounts':return {'data':{'user_id':71,'accounts':accounts}}
                if path=='/api/v1/categories/options':return {'data':[{'category_id':9,'name':'owned-unit-category'}]}
                if method=='POST':transactions.append(body);return {'data':{'id':len(transactions)}}
                return {'data':{'total':len(transactions),'hasMore':False,'data':transactions}}
        with tempfile.TemporaryDirectory() as td,patch('zap_assessment.fe_authenticated_fixture_finalsource.FixtureClient',Client),patch('zap_assessment.fe_authenticated_fixture_finalsource.db_prerequisites',return_value={'categoryId':9}):
            prepare_data({},actor,td,{'expense-transaction'},{'owned':True})
            self.assertEqual(len(transactions),1);self.assertEqual(transactions[0]['type'],'Expense')
            ledger=json.loads((Path(td)/'FIXTURE_DAG.json').read_text());self.assertEqual(ledger['transactionTargetCount'],1)
            self.assertEqual(ledger['fixtures']['expectedBalanceAfterExpense'],999.0)
    def test_cleanup_reader_accepts_one_owned_account_and_exact_retention(self):
        from zap_assessment.fe_authenticated_evidence_finalsource import cleanup_readback
        with tempfile.TemporaryDirectory() as td:
            root=Path(td)
            docs={'private/ACTORS_INITIAL.json':{'a':{'subject':71}},'private/fixtures/a/FIXTURE_DAG.json':{'subject':71,'accounts':[{'id':5}],'maxNewAccounts':1},
                'FIXTURE_CLEANUP.json':{'replay':False,'accounts':{'a':[5]},'retained':[{'actorRef':'a','kind':'principal','ids':[71],'reason':'no API delete'}]},
                'private/cleanup/a/CLEANUP_INTENT.json':{'subject':71,'exactAccountIds':[5],'state':'acknowledged'},
                'private/cleanup/a/setup/001-response.json':{'body':{'data':{'user_id':71,'accounts':[{'id':5}]}}},
                'private/cleanup/a/setup/002-request.json':{'method':'DELETE','path':'/api/v1/accounts/5','state':'response-observed'},
                'private/cleanup/a/setup/002-response.json':{'body':{'data':{'deleted_account_id':5}}},
                'private/cleanup/a/setup/003-response.json':{'body':{'data':{'user_id':71,'accounts':[]}}}}
            for name,value in docs.items():
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
            self.assertEqual(cleanup_readback(root)['accounts'],{'a':[5]})

class FixtureReadinessTests(unittest.TestCase):
    def test_empty_business_checks_do_not_fulfill_fixture(self):
        from zap_assessment.product_scope_cli import read_action_result
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'BUSINESS.json').write_text(json.dumps({'ledger':[{'kind':'order','wireId':'7','creationEvidence':'ack'}],'checks':[]}))
            with self.assertRaisesRegex(ValueError,'readback incomplete'):read_action_result(p,{'prerequisiteBindings':{'order':'order'}},plan={'track':'bola-ownership'},command='business-fixtures')

class AnonymousScopeReadbackTests(unittest.TestCase):
    def test_ui_only_anonymous_task_can_close_from_independent_ui_readback(self):
        inv=inventory([{**case(required=('ui','result-read')),'role':'anonymous','observationBindings':{'ui':{'kind':'ui','ids':['public-ui']},'result-read':{'kind':'ui','ids':['public-ui']}}}],track='fe-anonymous')
        p={'track':'fe-anonymous','discovery':{'responsibilityInventory':inv},'journeys':{'journeys':[{'id':'public-ui'}]}}
        self.assertEqual(fe_readback(p,{'journeys':[{'id':'public-ui','completed':True}]},[])['taskCompletion'],'complete')

if __name__=='__main__':unittest.main()







