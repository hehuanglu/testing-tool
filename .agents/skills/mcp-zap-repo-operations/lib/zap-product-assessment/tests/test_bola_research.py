"""BOLA research risks: independent HTTP fixture, not product proof."""
import copy
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
from zap_assessment import bola_research as br
from zap_assessment.bola_research_fixture import fixture as server
from zap_assessment.bola_http import exchange
from test_discovery import fixture as discovery_fixture


def request(oid,method,path,body=None):return {'operationRef':oid,'method':method,'path':path,'body':body}


def model(f,out):
    d=discovery_fixture(('source',));d['product']['location']='owned:independent-cargo';d['product']['environment']='owned-cargo'
    d['sources'][0].update(location=str(Path(__file__).resolve().parents[1]/'src/zap_assessment/bola_research_fixture.py'),sha256=br.sha(Path(__file__).resolve().parents[1]/'src/zap_assessment/bola_research_fixture.py'))
    d['product']['origins']=[{'url':f['origin'],'role':'direct','authorized':True,'bindingVerified':True,'evidenceRefs':['source']}]
    rows=[('login','POST','/session',False),('identity','GET','/me',True),('detail','GET','/cargo/{key}',True),('list','GET','/cargo',True),('update','PATCH','/cargo/{key}',True),('delete','DELETE','/cargo/{key}',True),('lookup','GET','/lookup',True),('move','POST','/move',True)]
    d['operations']=[{'id':i,'method':m,'pathTemplate':p,'protected':prot,'semantics':'Owned independent fixture contract','input':{'query':['page'] if i=='list' else ['key'] if i=='lookup' else []},'evidenceRefs':['source']} for i,m,p,prot in rows]
    d['auth'].update(loginOperationId='login',usernameField='name',passwordField='unused',tokenPointer='/credential')
    d['auth']['identity'].update(operationId='identity',subjectPointer='/principal',actorSource={'operationId':'login','subjectPointer':'/principal'})
    d['fixtures']=[];proof={'targetBinding':d['product']['binding'],'environment':'owned-cargo','directOrigins':[f['origin']]}
    policies=[{'id':'cargo-policy','relation':'shared-read','semantics':'custodian full access, members GET only; all others denied','evidenceRefs':['source']}]
    operations=[]
    for o in d['operations']:
        kind={'detail':'detail','list':'collection','update':'update','delete':'delete','lookup':'detail','move':'reference'}.get(o['id'])
        slots=[{'location':'path','name':'key'}] if o['id'] in ('detail','update','delete') else [{'location':'query','name':'key'}] if o['id']=='lookup' else [{'location':'body','pointer':'/reference/cargoKey'}] if o['id']=='move' else []
        body={'units':765} if o['id']=='update' else {'reference':{'cargoKey':None},'units':765} if o['id']=='move' else None
        operations.append({'operationRef':o['id'],'disposition':'candidate' if kind else 'not-applicable','reason':'Fixture policy cases' if kind else 'Auth/identity control',
          'evidenceRefs':['source'],'objectType':'cargo' if kind else None,'policyRef':'cargo-policy' if kind else None,'kind':kind,'idLocations':slots,
          'request':request(o['id'],o['method'],o['pathTemplate']+'?page=0' if o['id']=='list' else o['pathTemplate'],body),
          **({'collectionPointers':['/items'],'collectionIdField':'key','hasMorePointer':'/more','pageRequests':[request('list','GET','/cargo?page=1'),request('list','GET','/cargo?page=2')]} if o['id']=='list' else {})})
    inv={'discoverySha256':br.canonical_hash(d),'policies':policies,'operations':operations}
    actors={a:{'subject':a,'credentialRef':'memory:'+a,'evidenceRefs':[],'runId':out.name} for a in ('A','B')}
    resources=[]
    for key in ('a','b','shared'):
        value=f['state']['records'][f['keys'][key]]
        resources.append({'id':key,'wireId':value['key'],'objectType':'cargo','owner':value['custodian'],'sharedWith':value['members'],
          'role':'target','runId':out.name,'createdByRun':True,'preparationEvidence':['seed.json'],'grantEvidenceRefs':['source'] if value['members'] else [],'cleanup':'owned in-memory fixture removed on context exit',
          'readRequest':request('detail','GET','/cargo/'+value['key']),'relatedRequests':[],'statePointer':'/payload','idField':'key',
          'expectedFields':{'/caption':value['caption'],'/units':100},'markers':[value['caption']]})
    authority={'environment':'owned-cargo','source':'user authorized owned synthetic controls 2026-10-21; CONTRACT.md','permissions':list(br.PERMISSIONS)}
    return d,inv,actors,resources,authority,proof


def sample(f,case_kind='detail',actor='B',key='a'):
    with tempfile.TemporaryDirectory() as td:
        d,inv,actors,resources,a,proof=model(f,Path(td))
        controls=[{'operationRef':oid,'owner':who,'verified':True} for oid in ('update','delete','move') for who in ('A','B')]
        # Oracle fixture input uses the real compiler with consistent run IDs.
        p=br.compile_plan(d,inv,actors,resources,a,d['product']['binding'],proof,Path(td).name,controls)
        c=next(c for c in p['cases'] if c['operationRef']==case_kind and c['actorRef']==actor and c['resourceRef']==key)
        r=next(r for r in resources if r['id']==key)
        def http(who,req):
            headers={'Content-Type':'application/json'}
            if who!='anonymous':headers['Authorization']='Bearer '+f['tokens'][who]
            s,b,n=exchange(f['origin'],req['method'],req['path'],headers,json.dumps(req['body']).encode() if req['body'] is not None else None,1)
            return {'status':s,'body':b}
        obs={}
        for phase in ('before','after'):
            if phase=='after':
                try:obs['attempt']=http(actor,c['request'])
                except (OSError,ValueError):obs['attempt']={'error':'unknown-outcome','retry':False}
            for who in set([actor,r['owner']])-{'anonymous'}:obs['identity-'+phase+'-'+who]=http(who,p['identity']['request'])
            obs['owner-'+phase]=http(r['owner'],r['readRequest']);obs['related-'+phase]=[]
        return p,c,obs,br.evaluate(p,c,obs),f['state']['records'].copy()


def captured_run(out,mode='secure',interrupt_after=None):
    """Integration harness. Only pacing waits are mocked; real independent HTTP.

    The server never imports the compiler or oracle. Its arrived actors and actual
    stored values are saved separately from decisions for independent checks.
    """
    out=Path(out);out.mkdir(mode=0o700,parents=True)
    with server(mode) as f,patch.object(br.time,'sleep'):
        d,inv,actors,resources,a,proof=model(f,out)
        client=br.DirectClient(d,d['product']['binding'],lambda:(d['product']['binding'],proof),out,a,capture_fields={'principal','payload','key','custodian','caption','units','members','items','more','error','code','fieldName','changed'})
        client.set_tokens({who:{'token':t} for who,t in f['tokens'].items()})
        br.save(out,'seed.json',{'resources':resources,'fixtureSource':br.sha(Path(__file__).resolve().parents[1]/'src/zap_assessment/bola_research_fixture.py')})
        for who in ('A','B'):
            _,_,ref=client.request('initial-subject-'+who,who,request('identity','GET','/me'),'read')
            actors[who]['evidenceRefs']=[ref]
        controls=[]
        for who,key in [('A','pa'),('B','pb')]:
            for oid,method,path,body in [('update','PATCH','/cargo/'+f['keys'][key],{'units':765}),('move','POST','/move',{'reference':{'cargoKey':f['keys'][key]},'units':766}),('delete','DELETE','/cargo/'+f['keys']['da' if who=='A' else 'db'],None)]:
                wire=f['keys']['da' if who=='A' else 'db'] if oid=='delete' else f['keys'][key]
                r=copy.deepcopy(next(r for r in resources if r['owner']==who));r.update(id='positive-'+who+'-'+oid,wireId=wire,readRequest=request('detail','GET','/cargo/'+wire))
                value=f['state']['records'][wire];r['expectedFields']={'/caption':value['caption'],'/units':value['units']}
                _,_,before=client.request('positive-before-'+who+'-'+oid,who,r['readRequest'],'read')
                req=request(oid,method,path,body);_,_,attempt=client.request('positive-attempt-'+who+'-'+oid,who,req,'setup')
                _,_,after=client.request('positive-after-'+who+'-'+oid,who,r['readRequest'],'poststate')
                controls.append({'operationRef':oid,'owner':who,'resource':r,'beforeRef':before,'attemptRef':attempt,'afterRef':after,'request':req,'expectedPost':None if oid=='delete' else {'/units':body['units']},'verified':True})
        if mode=='expire-mid':
            send=client.request
            def expire_during_cases(*args,**kwargs):
                result=send(*args,**kwargs)
                if client.count>=30:f['state']['expired']=True
                return result
            client.request=expire_during_cases
        plan=br.compile_plan(d,inv,actors,resources,a,d['product']['binding'],proof,out.name,controls)
        runner=br.BolaRun(plan,client,out);result=runner.run(interrupt_after)
        br.save(out,'INDEPENDENT_SERVER.json',{'arrivals':f['state']['arrivals'],'records':f['state']['records'],'attempts':f['state']['attempts'],'mode':mode,'pacingWaitMocked':True})
        if any(secret.encode() in p.read_bytes() for p in out.rglob('*') if p.is_file() for secret in client.secret_values if secret):raise AssertionError('credential canary persisted')
    result['cleanupStatus']='clean';result['gateDecision']='allow' if result['executionStatus']=='completed' and result['securityVerdict']=='pass' else 'block'
    br.save(out,'RUN.json',result);br.save(out,'ALERTS.json',br.alerts(plan,runner.rows));br.seal(out)
    br.save(out,'VERIFICATION.json',br.verify(out))
    return result


class BolaResearchTests(unittest.TestCase):
    def test_secure_and_vulnerable_and_leaking_errors_independent_http(self):
        for mode,expected in [('secure','pass'),('vulnerable','fail'),('leak403','fail'),('leak404','fail')]:
            with self.subTest(mode=mode),server(mode) as f:
                p,c,obs,result,state=sample(f)
                self.assertEqual(result['verdict'],expected)
                self.assertEqual(obs['attempt']['status'],{'secure':403,'vulnerable':200,'leak403':403,'leak404':404}[mode])
                self.assertTrue(any(x['actor']=='B' and x['path'].startswith('/cargo/') for x in f['state']['arrivals']))
    def test_shared_read_is_allowed_and_field_name_collision_not_disclosure(self):
        with server() as f:
            p,c,o,result,state=sample(f,key='shared');self.assertEqual(c['expectedAccess'],'allow');self.assertEqual(result['verdict'],'pass')
            p,c,o,result,state=sample(f);self.assertFalse(result['disclosure']);self.assertEqual(result['verdict'],'pass')
    def test_missing_fixture_and_failed_subject_never_pass(self):
        with server('missing') as f:self.assertEqual(sample(f)[3]['verdict'],'inconclusive')
        with server('vulnerable') as f:
            p,c,o,result,state=sample(f);o['identity-after-B']['body']['principal']='A'
            r=br.evaluate(p,c,o);self.assertEqual(r['verdict'],'inconclusive');self.assertTrue(r['candidateFinding']);self.assertTrue(r['disclosure'])
    def test_denied_mutation_with_effect_and_lost_ack_no_repeat(self):
        for mode in ('secure','denied-sideeffect','lost-ack'):
            with self.subTest(mode=mode),server(mode) as f:
                p,c,o,result,state=sample(f,'update')
                self.assertEqual(result['verdict'],'pass' if mode=='secure' else 'fail')
                key=f['keys']['a'];self.assertEqual(f['state']['attempts'].get(key,0),0 if mode=='secure' else 1)
                self.assertEqual(f['state']['records'][key]['units'],100 if mode=='secure' else 765)
    def test_nested_body_and_query_substitutions_arrive_exactly(self):
        for operation in ('lookup','move'):
            with server() as f:
                p,c,o,result,state=sample(f,operation)
                self.assertEqual(result['verdict'],'pass')
                arrived=next(x for x in f['state']['arrivals'] if x['actor']=='B' and x['path'].startswith('/lookup' if operation=='lookup' else '/move'))
                self.assertTrue(f['keys']['a'] in arrived['path'] if operation=='lookup' else arrived['body']['reference']['cargoKey']==f['keys']['a'])
    def test_expired_auth_inconclusive_and_swapped_slot_pre_send(self):
        with server() as f,tempfile.TemporaryDirectory() as td:
            d,inv,actors,res,a,proof=model(f,Path(td));client=br.DirectClient(d,d['product']['binding'],lambda:(d['product']['binding'],proof),td,a)
            client.set_tokens({who:{'token':t} for who,t in f['tokens'].items()})
            with self.assertRaisesRegex(ValueError,'swapped'):client.request('swapped','B',request('identity','GET','/me'),'read',token=f['tokens']['A'])
            self.assertEqual(f['state']['arrivals'],[])
            f['state']['expired']=True
            self.assertEqual(sample(f)[3]['verdict'],'inconclusive')
    def test_plan_mutants_fail_before_traffic(self):
        with server() as f,tempfile.TemporaryDirectory() as td:
            d,inv,actors,res,a,proof=model(f,Path(td));controls=[{'operationRef':oid,'owner':who,'verified':True} for oid in ('update','delete','move') for who in ('A','B')]
            p=br.compile_plan(d,inv,actors,res,a,d['product']['binding'],proof,Path(td).name,controls)
            mutations=[lambda p:p.update(origin='http://127.0.0.1:1'),lambda p:p['cases'][0]['request'].update(path='/cargo/%2e%2e'),
              lambda p:p['cases'][0].update(actorRef='C'),lambda p:p['cases'][0]['request'].update(body={'reference':{'cargoKey':'invented'}}),
              lambda p:p['resources'][0].update(runId='old'),lambda p:p['actors']['B'].update(subject='A'),lambda p:p['inventory']['policies'][0].update(evidenceRefs=[]),
              lambda p:p['cases'].pop(),lambda p:p.update(notAfter=1),lambda p:p['limits'].update(maxRequests=999),lambda p:p['cases'][0].update(expectedAccess='deny')]
            for mutate in mutations:
                q=copy.deepcopy(p);mutate(q)
                with self.assertRaises((ValueError,KeyError)):br.validate_plan(q,d['product']['binding'],proof)
            self.assertEqual(f['state']['arrivals'],[])
    def test_pagination_later_page_leak_and_truncation(self):
        with server('list-leak') as f:
            p,c,o,r,state=sample(f,'list');op=next(x for x in p['inventory']['operations'] if x['operationRef']=='list')
            for i,req in enumerate(op['pageRequests']):
                s,b,n=exchange(f['origin'],'GET',req['path'],{'Authorization':'Bearer '+f['tokens']['B']},None,1);o['page-'+str(i)]={'status':s,'body':b}
            self.assertEqual(br.evaluate(p,c,o)['verdict'],'fail')
            del o['page-1'];self.assertEqual(br.evaluate(p,c,o)['verdict'],'inconclusive')
    def test_redaction_nested_canaries(self):
        token='opaque-secret-CANARY-123456789';v={'unknown':[token,{'password':'p','accessToken':token,'note':'value='+token}],'email':'test@example.test'}
        red=br.sanitized(v,[token]);s=json.dumps(red)
        self.assertNotIn(token,s);self.assertNotIn('test@example.test',s);self.assertNotIn('"p"',s)
        self.assertNotIn(token,json.dumps(br.sanitized({token:'echo'},[token])))

    def test_delete_unknown_poststate_cannot_be_mutation_finding(self):
        with server() as f:
            p,c,o,r,state=sample(f,'delete');o['owner-after']={'error':'timeout'}
            result=br.evaluate(p,c,o)
            self.assertEqual(result['verdict'],'inconclusive');self.assertFalse(result['stateChanged'])

    def test_captured_executor_secure_vulnerable_interrupted_and_tampering(self):
        with tempfile.TemporaryDirectory() as td:
            for mode,interrupted,expected in [('secure',None,'pass'),('vulnerable',None,'fail'),('expire-mid',None,'inconclusive'),('secure',2,'inconclusive')]:
                root=Path(td)/(mode+str(interrupted))
                result=captured_run(root,mode,interrupted)
                self.assertEqual(result['securityVerdict'],expected)
                proof=br.load(root,'INDEPENDENT_SERVER.json')
                self.assertFalse(any(x['cookie'] for x in proof['arrivals']))
                self.assertEqual(br.verify(root)['evidenceStatus'],'consistent')
            original=Path(td)/'secureNone'
            portable=Path(td)/'portable';shutil.copytree(original,portable);self.assertEqual(br.verify(portable)['evidenceStatus'],'consistent')
            mutants=[('row-actor',lambda r: _edit(r,'RESULTS.json',lambda v:v[0].update(actorRef='B'))),
                ('poststate',lambda r:_edit(r,'RESULTS.json',lambda v:v[0]['observations'].update(**{'owner-after':{'status':200,'body':{}}}))),
                ('coverage',lambda r:_edit(r,'COVERAGE.json',lambda v:v.update(operationDispositions=[]))),
                ('cleanup',lambda r:_edit(r,'RUN.json',lambda v:v.update(gateDecision='block'))),
                ('missing-control',lambda r:(r/br.load(r,'PLAN.json')['positiveControls'][0]['afterRef']).unlink()),
                ('rehash-decision',lambda r:_edit_rows(r,lambda v:v[0]['decision'].update(verdict='fail'))),
                ('rehash-control-order',lambda r:_edit_rows(r,_swap_owner_controls))]
            for name,mutate in mutants:
                dest=Path(td)/name;shutil.copytree(original,dest);mutate(dest)
                # Rehash index too: semantic checks must reject self-consistent hashes.
                (dest/'EVIDENCE_INDEX.json').unlink();br.seal(dest)
                with self.subTest(name=name),self.assertRaises(Exception):br.verify(dest)

    def test_scope_and_credential_guards_send_nothing(self):
        with server() as f,tempfile.TemporaryDirectory() as td:
            d,inv,actors,res,a,proof=model(f,Path(td));client=br.DirectClient(d,d['product']['binding'],lambda:(d['product']['binding'],proof),td,a)
            client.set_tokens({who:{'token':t} for who,t in f['tokens'].items()})
            invalid=[request('detail','GET','http://elsewhere/cargo/a'),request('detail','GET','/cargo/%2e%2e'),request('detail','GET','/cargo/unknown?outside=1')]
            for req in invalid:
                with self.assertRaises(ValueError):client.request('invalid','B',req,'read')
            with self.assertRaises(ValueError):client.request('invalid-read','B',request('move','POST','/move',{}),'read')
            with self.assertRaises(ValueError):client.request('anonymous-token','anonymous',request('identity','GET','/me'),'read',token=f['tokens']['A'])
            with self.assertRaises(ValueError):br.save(td,'../escape.json',{})
            client.deadline=0
            with self.assertRaises(TimeoutError):client.request('expired','B',request('identity','GET','/me'),'read')
            self.assertEqual(f['state']['arrivals'],[])

    def test_allowlist_omission_preserves_uncertainty_without_secret_persistence(self):
        secret='unknown-field-private-canary-12345'
        body,complete=br.project_response({'error':{'code':'DENIED'},'newUnknownField':secret},{'error','code'},[])
        self.assertFalse(complete);self.assertNotIn(secret,json.dumps(body))
        with server() as f:
            p,c,o,r,state=sample(f);o['attempt']['captureComplete']=False
            self.assertEqual(br.evaluate(p,c,o)['verdict'],'inconclusive')


def _edit(root,name,change):
    value=br.load(root,name);change(value);(Path(root)/name).write_text(json.dumps(value))


def _edit_rows(root,change):
    rows=br.load(root,'RESULTS.json');change(rows)
    (Path(root)/'RESULTS.json').write_text(json.dumps(rows))
    for row in rows:(Path(root)/'cases'/str(row['caseId']+'.json')).write_text(json.dumps(row))


def _swap_owner_controls(rows):
    row=rows[0]
    for key in ('observations','evidenceRefs'):
        row[key]['owner-before'],row[key]['owner-after']=row[key]['owner-after'],row[key]['owner-before']


if __name__=='__main__':unittest.main()
