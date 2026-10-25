"""Versioned BOLA observation lane. Legacy research/v1.4 readers keep their meanings."""
import copy
import hashlib
import inspect
import json
from pathlib import Path
from .discovery import canonical_hash,verify_identity
from .bola_research import validate_request,DirectClient,save,project_response,render
from .journal import Journal
from .product_checks import check_case,pointer
from .product_workflow import validate_workflow
from .recipes import select


def compile_cases(p):
    r=select(p['recipe']);w=p['workload'];d=p['discovery'];actors=w['actors'];result=[]
    if not actors or 'anonymous' in actors:raise ValueError('dynamic authenticated actor refs required')
    for case in w['cases']:
        c=copy.deepcopy(case)
        actor={'role':'ANONYMOUS'} if c['actorRef']=='anonymous' else actors[c['actorRef']]
        for request in c.get('relatedRequests',[]):
            validate_request(d,request)
            if request['method']!='GET' or request['operationRef'] not in w['operationIds']:raise ValueError('related poststate outside frozen read scope')
        if any(index not in {str(i) for i in range(len(c.get('relatedRequests',[])))} or ref not in actors for index,ref in c.get('relatedObserverRefs',{}).items()):raise ValueError('related observer outside locked actors')
        for field in ('request','beforeRequest','afterRequest'):
            validate_request(d,c[field])
            if c[field]['operationRef'] not in w['operationIds']:raise ValueError('BOLA request outside authority subset')
        if c['beforeRequest']['method']!='GET' or c['afterRequest']['method']!='GET':raise ValueError('poststate must be read-only')
        action=c['action']
        if hasattr(r,'ACTION_OPERATIONS'):
            op=next(o for o in d['operations'] if o['id']==c['request']['operationRef'])
            if r.ACTION_OPERATIONS.get(action)!=(op['method'],op['pathTemplate']):raise ValueError('policy action/operation mismatch')
        resource=w['resources'][c['resourceRef']]
        if not resource.get('wireId') or not resource.get('creationEvidence') or not (resource.get('idPointer') or resource.get('implicitOwnerPointer') or resource.get('collection')):raise ValueError('resource binding/ownership provenance missing')
        if render({'request':c['requestTemplate'],'idLocations':c['idLocations']},resource)!=c['request']:raise ValueError('exact resource reference binding drift')
        if c['observerRef']!=resource['ownerRef']:raise ValueError('poststate observer not resource owner')
        relation='owner' if c['actorRef']==resource['ownerRef'] else 'shared-catalog' if resource.get('sharedCatalog') else 'shared-read' if c['actorRef'] in resource.get('sharedWith',[]) else 'nonowner'
        if resource.get('sharedWith') and (not resource.get('grantEvidenceRefs') or not set(resource['grantEvidenceRefs'])<={s['id'] for s in d['sources']}):raise ValueError('shared grant provenance missing')
        if c['relation']!=relation:raise ValueError('actor/resource relation drift')
        access=r.policy(actor['role'],c['relation'],action,c['state'])
        policy_detail=r.expected_case(actor['role'],c['relation'],action,c['state'],c['request'],resource) if hasattr(r,'expected_case') else None
        if policy_detail:access=policy_detail['access']
        required=getattr(r,'REQUIRED_READS',{}).get(action,[])
        observed_ops={c['beforeRequest']['operationRef'],*[request['operationRef'] for request in c.get('relatedRequests',[])]}
        if c.get('createdResourceRead'):observed_ops.add(c['createdResourceRead']['request']['operationRef'])
        if not set(required)<=observed_ops:raise ValueError('operation requires related stock/cart/resource poststate reads')
        statuses=r.SUCCESS.get(action) if hasattr(r,'SUCCESS') else r.success(d,c['request']['operationRef'])
        if not statuses:raise ValueError('success semantics undeclared')
        c['expected']={'access':access,'successStatuses':statuses,'denialStatuses':c.get('denialStatuses',[401,403,404,409]),
            'responseEquals':c.get('responseEquals',{}),'postEquals':c.get('postEquals',{}),'postUnchanged':c.get('postUnchanged',False),'relatedPostEquals':c.get('relatedPostEquals',{})}
        if policy_detail:
            if c.get('denialStatuses') and c['denialStatuses']!=policy_detail['denialStatuses']:raise ValueError('case denial status contradicts recipe policy')
            c['expected']['denialStatuses']=policy_detail['denialStatuses']
        if access=='allow' and c['request']['method']=='GET' and not resource.get('collection'):
            if resource.get('idPointer'):c['expected']['responseEquals'][resource['idPointer']]=resource['wireId']
        if c.get('pagination'):
            if c['request']['method']!='GET' or not resource.get('collection'):raise ValueError('pagination requires declared collection')
            c['expected']['pagination']=c['pagination']
            for request in c.get('pageRequests',[]):
                validate_request(d,request)
                if request['method']!='GET' or request['operationRef'] not in w['operationIds']:raise ValueError('pagination outside frozen read scope')
        if access=='deny' and c['request']['method']!='GET':
            positives=[row for row in result if row['id']==c.get('positiveControlRef') and row['expected']['access']=='allow' and row['action']==action]
            if len(positives)!=1 or positives[0]['resourceRef']==c['resourceRef'] or positives[0]['request']['body']!=c['request']['body']:raise ValueError('denied mutation needs dedicated valid earlier positive control')
        if not c.get('policyEvidenceRefs') or not set(c['policyEvidenceRefs'])<={s['id'] for s in d['sources']}:raise ValueError('policy provenance missing')
        if access=='allow' and c['request']['method']!='GET' and not(c['expected']['postEquals'] or c['expected']['postUnchanged']):raise ValueError('mutation poststate expectation required')
        if c.get('createdResourceRead'):
            read=c['createdResourceRead']
            operation=next((o for o in d['operations'] if o['id']==read['request']['operationRef']),None)
            if (access!='allow' or c['request']['method']!='POST' or not operation or operation['method']!='GET'
                    or operation['id'] not in w['operationIds'] or read['request']['method']!='GET'
                    or read['request']['path']!=operation['pathTemplate'] or read['request'].get('body') is not None
                    or read['request']['path'].count('{'+read['pathParameter']+'}')!=1
                    or not read.get('responseIdPointer') or not read.get('idPointer') or not read.get('ownerPointer')
                    or str(read.get('expectedOwner'))!=str(actors[c['observerRef']]['subject'])):
                raise ValueError('created-resource read outside frozen scope')
            c['expected']['createdResourceRead']=copy.deepcopy(read)
        if c.get('checkout'):
            if action not in getattr(r,'CHECKOUT_ACTIONS',()) or not c.get('createdResourceRead'):raise ValueError('checkout oracle requires recipe action and created-resource read')
            c['expected']['checkout']=copy.deepcopy(c['checkout'])
        result.append(c)
    if len({c['id'] for c in result})!=len(result) or not result:raise ValueError('duplicate/empty cases')
    checker=Path(inspect.getfile(check_case))
    return {'schemaVersion':'product-bola-observations/1.0','workflowSha256':canonical_hash(p),'actors':actors,
            'cases':result,'checkerSha256':hashlib.sha256(checker.read_bytes()).hexdigest(),'policyStatus':'accepted-for-test' if w.get('policyAcceptanceRefs') else 'source-hypothesis'}


def execute(p,inspection,out,actors,*,interrupt_after=None):
    from .product_prepare import verify_actor
    validate_workflow(p,inspection)
    for actor in actors.values():verify_actor(actor)
    locked=compile_cases(p);out=Path(out);out.mkdir(mode=0o700,parents=True,exist_ok=False)
    from .product_workflow import archive_sources
    archive_sources(p,out)
    save(out,'PLAN.json',locked);j=Journal(out/'journal.jsonl',p['runId'],canonical_hash(locked))
    def current():
        validate_workflow(p,inspection)
        if json.loads((out/'PLAN.json').read_text())!=locked:raise ValueError('BOLA locked policy drift')
        return inspection()
    client=DirectClient(p['discovery'],p['discovery']['product']['binding'],current,out/'direct',{'permissions':p['permissions']},
        actor_refs=tuple(locked['actors']),allow_empty=True,not_after=p['notAfter'],capture_fields=select(p['recipe']).CAPTURE_FIELDS)
    client.set_tokens(actors);observations=[]
    error=None
    try:
        from .product_identity import strategy,check_identity,verify_trust
        from .signed_identity import check_probe
        recipe=select(p['recipe'])
        def identity(ref,label):
            actor=locked['actors'][ref];private=actors[ref]
            if str(private['subject'])!=str(actor['subject']) or private['role']!=actor['role']:raise ValueError('independent subject/role binding mismatch')
            mapping=strategy(recipe,p['discovery'],actor['role'])
            expected=next(o for o in p['discovery']['operations'] if o['id']==mapping['operationId'])
            if actor['identityRequest']!={'operationRef':expected['id'],'method':'GET','path':expected['pathTemplate'],'body':None}:raise ValueError('role-specific identity request drift')
            s,body,e=client.request('identity-'+label+'-'+ref,ref,actor['identityRequest'],'read')
            if mapping['version']=='signed-jwt-protected-probe/1.0':
                if private.get('identityStrategy')!=mapping:raise ValueError('signed private actor strategy mismatch')
                verify_trust(private['jwtTrust'],p['discovery']);check_probe(s,body,private['token'],private['jwtTrust'],mapping,actor['subject'],actor['role'])
            else:check_identity(s,'application/json',body,actor['subject'],actor['role'],mapping)
            return e
        controls=DirectClient(p['discovery'],p['discovery']['product']['binding'],current,out/'identity-controls',{'permissions':p['permissions']},actor_refs=tuple(locked['actors']),allow_empty=True,not_after=p['notAfter'],capture_fields=recipe.CAPTURE_FIELDS)
        for ref,actor in locked['actors'].items():
            identity(ref,'before')
            for label,slot,token in [('anonymous','anonymous',None),('invalid',ref,'owned-invalid-session')]:
                status,_,_=controls.request(label+'-'+ref,slot,actor['identityRequest'],'read',token=token)
                if status!=401:raise ValueError('protected identity negative control failed')
        for i,c in enumerate(locked['cases']):
            if interrupt_after is not None and i>=interrupt_after:break
            validate_workflow(p,inspection)
            if canonical_hash(locked)!=canonical_hash(json.loads((out/'PLAN.json').read_text())):raise ValueError('locked expectations drift')
            for ref in dict.fromkeys([c['observerRef'],c['actorRef'],*c.get('relatedObserverRefs',{}).values()]):
                if ref!='anonymous':identity(ref,c['id']+'-before')
            if c.get('positiveControlRef'):
                positive=next((o for o in observations if o['caseId']==c['positiveControlRef']),None)
                expected=next(row['expected'] for row in locked['cases'] if row['id']==c['positiveControlRef'])
                if positive is None or check_case(expected,positive)['outcome']!='matched':raise ValueError('valid positive control unproven')
            owner=c['observerRef'];before=client.request(c['id']+'-before',owner,c['beforeRequest'],'poststate')[1]
            resource=p['workload']['resources'][c['resourceRef']]
            if resource.get('idPointer') and str(pointer(before,resource['idPointer']))!=str(resource['wireId']):raise ValueError('prestate resource binding drift')
            owner_pointer=resource.get('ownerPointer') or resource.get('implicitOwnerPointer')
            if owner_pointer and str(pointer(before,owner_pointer))!=str(locked['actors'][owner]['subject']):raise ValueError('prestate resource owner mismatch')
            if resource.get('statePointer') and pointer(before,resource['statePointer'])!=c['state']:raise ValueError('locked action state drift')
            if resource.get('typePointer') and pointer(before,resource['typePointer'])!=resource.get('typeValue'):raise ValueError('locked resource type drift')
            related_before={}
            for number,request in enumerate(c.get('relatedRequests',[])):
                related_owner=c.get('relatedObserverRefs',{}).get(str(number),owner)
                status,value,_=client.request(c['id']+'-related-before-'+str(number),related_owner,request,'poststate')
                if status!=200:raise ValueError('related prestate incomplete')
                related_before[request['operationRef']+'-'+str(number)]=value
            j.append('pending-start',{'caseId':c['id'],'retry':False})
            try:s,body,ref=client.request(c['id'],c['actorRef'],c['request'],'read' if c['request']['method']=='GET' else 'mutation')
            except Exception:
                # Never resend mutation; read-only reconcile is attempted and preserved.
                try:after=client.request(c['id']+'-reconcile',owner,c['afterRequest'],'poststate')[1]
                except Exception:after=None
                save(out,c['id']+'-unknown.json',{'caseId':c['id'],'after':after,'retry':False});raise
            after=client.request(c['id']+'-after',owner,c['afterRequest'],'poststate')[1]
            created=None
            if c.get('createdResourceRead'):
                spec=c['createdResourceRead'];wire_id=pointer(body,spec['responseIdPointer'])
                if isinstance(wire_id,bool) or not isinstance(wire_id,(str,int)) or not __import__('re').fullmatch(r'[A-Za-z0-9_-]+',str(wire_id)):raise ValueError('created-resource selector invalid; no mutation replay')
                read=render({'request':spec['request'],'idLocations':[{'location':'path','name':spec['pathParameter']}]},{'wireId':wire_id})
                validate_request(p['discovery'],read)
                j.append('created-resource-read-intent',{'caseId':c['id'],'wireId':wire_id,'request':read,'sourceResponseRef':ref,'retryMutation':False})
                status,value,e=client.request(c['id']+'-created-read',owner,read,'poststate')
                created={'status':status,'body':value,'evidenceRef':e,'wireId':wire_id}
            for actor_ref in dict.fromkeys([owner,c['actorRef'],*c.get('relatedObserverRefs',{}).values()]):
                if actor_ref!='anonymous':identity(actor_ref,c['id']+'-after')
            # Projection is an explicit recipe/workload contract. Unknown fields are inconclusive.
            fields=select(p['recipe']).CAPTURE_FIELDS
            disclosed=(c.get('disclosurePointer') is None)
            if c.get('disclosurePointer'):
                try:disclosed=pointer(body,c['disclosurePointer'])==c['disclosureValue']
                except (KeyError,TypeError,IndexError):disclosed=False
            related_after={}
            for number,request in enumerate(c.get('relatedRequests',[])):
                related_owner=c.get('relatedObserverRefs',{}).get(str(number),owner)
                status,value,_=client.request(c['id']+'-related-after-'+str(number),related_owner,request,'poststate')
                if status!=200:raise ValueError('related poststate incomplete')
                related_after[request['operationRef']+'-'+str(number)]=value
            pages=[body];page_evidence=[ref]
            if c.get('pagination') and c['expected']['access']=='allow':
                for number,request in enumerate(c.get('pageRequests',[])):
                    status,page,page_ref=client.request(c['id']+'-page-'+str(number),c['actorRef'],request,'read')
                    if status!=200:raise ValueError('collection page read failed')
                    pages.append(page);page_evidence.append(page_ref)
            complete=all(project_response(v,fields,[])[1] for v in (before,after,body,*related_before.values(),*related_after.values(),*pages,*([created['body']] if created else [])))
            o={'relatedBefore':related_before,'relatedAfter':related_after,'pages':pages,'pageEvidence':page_evidence,'caseId':c['id'],'before':before,'after':after,'response':{'status':s,'body':body},'captureComplete':complete,'disclosed':disclosed,'httpEvidence':ref}
            if created:o['createdRead']=created
            observations.append(o);save(out,'observations/'+c['id']+'.json',o);j.append('ack',{'caseId':c['id'],'responseRef':ref})
    except Exception as exc:
        error=type(exc).__name__
        detail=str(exc)
        for value in client.secret_values:
            if value:detail=detail.replace(value,'[private]')
        save(out,'ERROR.json',{'type':error,'detail':detail[:300],'replay':False})
    save(out,'OBSERVATIONS.json',observations)
    checks=[{'caseId':c['id'],**check_case(c['expected'],o)} for c,o in zip(locked['cases'],observations)]
    save(out,'CHECKS.json',checks)
    result={'executionStatus':'failed' if error else 'completed' if len(checks)==len(locked['cases']) else 'interrupted','evidenceStatus':'complete' if len(checks)==len(locked['cases']) and not error else 'partial',
            'securityVerdict':'inconclusive' if error or len(checks)!=len(locked['cases']) or locked['policyStatus']=='source-hypothesis' or any(x['outcome']=='inconclusive' for x in checks) else 'fail' if any(x['outcome']=='violated' for x in checks) else 'no-violation-in-tested-cases',
            'cleanupStatus':'retained','gateDecision':'review_required','source':'direct','notZapAlerts':True}
    from .product_scope import task_readback,apply_completion
    result=apply_completion(result,task_readback(p))
    save(out,'RUN.json',result)
    from .research import manifest
    manifest(out)
    from .product_handoff import direct_handoff
    direct_handoff(p,out)
    return result


def cleanup_owned(p,inspection,ledger,client,run_id,journal=None):
    """Exact IDs only; never replay an uncertain cleanup allocation."""
    validate_workflow(p,inspection)
    for row in ledger:
        if row['runId']!=run_id or not row.get('creationEvidence') or not row.get('wireId'):raise ValueError('cleanup ownership absent')
        if row.get('state') in ('pending','unknown'):raise ValueError('cleanup needs reconciliation; no replay')
    for row in reversed(ledger):
        if row['state']=='clean':continue
        req=row.get('cleanupRequest')
        if req is None:row['state']='retained';continue
        if str(row['wireId']) not in req['path'].split('/'):raise ValueError('cleanup exact ID binding absent')
        from .product_workflow import authority_check
        authority_check(p['authority'],p['discovery'],p['track'],[req['operationRef']],['cleanup'])
        if req['operationRef'] not in p['workload']['operationIds']:raise ValueError('cleanup outside frozen subset')
        if journal is None:raise ValueError('durable cleanup journal required before mutation')
        if any(e['kind'].startswith('cleanup-') and e['data'].get('wireId')==row['wireId'] for e in journal.events):raise ValueError('cleanup allocation exists; reconcile, never replay')
        journal.append('cleanup-pending',{'runId':run_id,'wireId':row['wireId'],'request':req,'retry':False})
        row['state']='pending'
        try:client.request('cleanup-'+row['wireId'],row['actorRef'],req,'cleanup');row['state']='clean'
        except Exception:
            row['state']='unknown';journal.append('cleanup-unknown',{'wireId':row['wireId'],'retry':False});raise
        journal.append('cleanup-ack',{'wireId':row['wireId']})
    return ledger


def verify(root):
    from .research import verify_manifest
    root=Path(root);readback=verify_manifest(root)
    plan=json.loads((root/'PLAN.json').read_text());observations=json.loads((root/'OBSERVATIONS.json').read_text());saved=json.loads((root/'CHECKS.json').read_text())
    if hashlib.sha256(Path(inspect.getfile(check_case)).read_bytes()).hexdigest()!=plan['checkerSha256']:raise ValueError('checker version/source drift; retain original checker')
    replay=[{'caseId':c['id'],**check_case(c['expected'],o)} for c,o in zip(plan['cases'],observations)]
    if replay!=saved:raise ValueError('independent checker readback mismatch')
    return {**readback,'caseCount':len(replay),'securityApproval':False,'schemaVersion':plan['schemaVersion']}
