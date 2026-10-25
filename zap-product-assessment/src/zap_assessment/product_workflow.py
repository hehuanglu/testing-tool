"""Common entry contract for finite code-owned recipes. No product-name dispatch/defaults."""
import copy
import hashlib
import inspect
import time
from pathlib import Path
from urllib.parse import urlsplit
from .discovery import canonical_hash, validate_discovery, verify_local_sources, secret_check
from .recipes import select

TRACKS=('be-anonymous','be-authenticated','bola-ownership')
FE_TRACKS=('fe-anonymous','fe-authenticated')  # separate research contract; common CLI dispatches before backend admission

def implementation_pins():
    root=Path(__file__).parent
    files=[*root.glob('product_*.py'),*root.joinpath('recipes').glob('*.py'),*root.joinpath('recipes').glob('*.json'),*root.parent.parent.joinpath('schemas').glob('*.json'),root/'signed_identity.py',root/'recipe_mapping.py',root/'bola_research.py',root/'bola_http.py',root/'discovery.py',root/'research.py',root/'research_product.py',root/'anonymous.py',root/'anonymous_runner.py']
    files.append(root/'archive_control.py')
    return {str(f):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(set(files))}

def recipe_pin(recipe):
    return hashlib.sha256(Path(inspect.getfile(recipe)).read_bytes()).hexdigest()

def admission(product, doc, recipe_id, track):
    recipe=select(recipe_id)  # Always before any setup/login/transport/provision.
    if track not in TRACKS:raise ValueError('unsupported track')
    validate_discovery(doc);verify_local_sources(doc)
    if Path(product).resolve()!=Path(doc['product']['location']).resolve():raise ValueError('discovery requested product mismatch')
    if doc['schemaVersion']!='product-discovery/1.1':raise ValueError('common entry requires transport-aware discovery 1.1; legacy readers preserved')
    if not doc['product']['binding']:raise ValueError('runtime binding unresolved')
    sources={s['id']:s for s in doc['sources']}
    if not any(sources[ref]['kind'] in ('deployment','runtime') for ref in doc['product']['environmentEvidenceRefs']):raise ValueError('environment needs deployment/runtime provenance; source location is not an environment')
    if any(c['blocking'] for c in doc['conflicts']):raise ValueError('source/spec conflict')
    if doc['tracks'][track]['status'] not in ('candidate','ready'):raise ValueError('track prerequisites unresolved')
    supported=recipe.admit(doc,track=track)
    if not supported:raise ValueError('recipe has no compatible operations')
    return recipe,{'recipe':recipe_id,'recipeSha256':recipe_pin(recipe),'track':track,'status':'partial' if len(supported)<len(doc['operations']) else 'compatible',
        'nativeActiveVectors':['query'] if track=='be-authenticated' else (['query','JSON-body'] if track=='be-anonymous' else []),'nativeActiveMethods':['GET'] if track=='be-authenticated' else (['GET','POST'] if track=='be-anonymous' else []),
        'conditionalNativeBody':{'capability':'native-flat-json-update/1.0','methods':['PUT','PATCH'],'shape':'flat JSON object; one recipe-mapped mutable scalar; references fixed','requires':'current controlled native delivery proof, exact owned fixture and transition oracle'} if track=='be-authenticated' else None,
        'conditionalNativePath':{'capability':'native-numeric-path/1.0','methods':['GET','DELETE','POST'],'shape':'single numeric selector; fixed route, no query/body; mutation fixture/oracle required; each method needs separate proof','requires':'current owned authenticated native control proof for selected methods'} if track=='be-authenticated' else None,
        'proofStage':'compiler capability; runtime qualification separate','supportedOperationIds':supported,'gaps':[{'operationId':o['id'],'reason':'no recipe; inventory retained'} for o in doc['operations'] if o['id'] not in supported]}

def authority_check(a, doc, track, operation_ids, permissions, *, now=None):
    import math
    now=time.time() if now is None else now
    if any(type(a.get(k)) not in (int,float) or not math.isfinite(a[k]) for k in ('notBefore','notAfter')):raise ValueError('authority validity window invalid')
    if not a.get('authorizationRef') or not a.get('issuer') or a.get('scopeOrigin')!='explicit-user-authorization':raise ValueError('authority source absent; historical receipt is not a grant')
    if not a.get('notBefore',now+1)<=now<a.get('notAfter',0):raise ValueError('authority absent/expired/not yet valid')
    if a.get('productLocation')!=str(Path(doc['product']['location']).resolve()) or a.get('environment')!=doc['product']['environment'] or a.get('bindingSha256')!=canonical_hash(doc['product']['binding']):raise ValueError('authority product/binding mismatch')
    if track not in a.get('tracks',[]) or not set(operation_ids)<=set(a.get('operationIds',[])) or not set(permissions)<=set(a.get('permissions',[])):raise ValueError('authority operation/permission scope missing')
    return a

def compile_workflow(product,doc,recipe_id,track,authority,workload,inspection,run_id):
    recipe,cap=admission(product,doc,recipe_id,track)
    from .anonymous import transport
    from .discovery import validate_transport
    b,proof=inspection()
    if b!=doc['product']['binding']:raise ValueError('binding drift')
    (transport if track=='be-anonymous' else validate_transport)(doc,b,proof)
    ids=set(workload.get('operationIds',[]))
    if not ids or not ids<=set(cap['supportedOperationIds']):raise ValueError('workload recipe capability missing')
    permissions=['network']+list(workload.get('permissions',[]))
    if any(p not in ('network','login','setup','mutation','read','poststate','cleanup','active','dedicated-catalog') for p in permissions):raise ValueError('unknown permission')
    operational=[]
    if track=='be-authenticated' and 'actorRefs' not in workload and not workload.get('fixtureKind'):
        operational=[doc['auth']['loginOperationId'],workload_identity(recipe,doc,workload)['operationId']]
        permissions=list(dict.fromkeys(permissions+['login','read']))
    authority_check(authority,doc,track,ids|set(operational),permissions)
    if track=='be-authenticated' and authority.get('secretPersistenceAccepted') is not True:raise ValueError('explicit research native secret retention acceptance required')
    if track=='be-authenticated' and workload.get('nativeControl'):
        if authority.get('controlledFixtureOwner') is None or proof.get('evidence',{}).get('controlOwner')!=authority['controlledFixtureOwner']:raise ValueError('native control requires independently inspected owned fixture binding')
    secret_check(workload)
    validate_workload(doc,recipe,track,workload,permissions)
    p={'schemaVersion':'product-workflow/1.0','runId':run_id,'productLocation':str(Path(product).resolve()),'recipe':recipe_id,'recipeSha256':recipe_pin(recipe),
       'track':track,'discovery':copy.deepcopy(doc),'discoverySha256':canonical_hash(doc),'transportBinding':proof,
       'authority':copy.deepcopy(authority),'authoritySha256':canonical_hash(authority),'workload':copy.deepcopy(workload),'capability':cap,
       'coverageGaps':coverage_gaps(doc,track,ids,cap,workload),'implementationPins':implementation_pins(),'operationalOperationIds':operational,'permissions':permissions,'limits':{'maxRequests':500,'requestsPerSecond':2,'executionSeconds':900,'reserveBytes':2147483648},
       'notAfter':min(authority['notAfter'],time.time()+900)}
    from .product_scope import inventory_from_operations
    p['responsibilityInventory']=inventory_from_operations(doc,track)
    validate_workflow(p,inspection)
    return p

def validate_workflow(p,inspection):
    if p.get('schemaVersion')!='product-workflow/1.0':raise ValueError('workflow version')
    if p.get('implementationPins')!=implementation_pins():raise ValueError('implementation drift')
    recipe,cap=admission(p['productLocation'],p['discovery'],p['recipe'],p['track'])
    if recipe_pin(recipe)!=p['recipeSha256'] or cap!=p['capability']:raise ValueError('recipe capability drift')
    if canonical_hash(p['discovery'])!=p['discoverySha256'] or canonical_hash(p['authority'])!=p['authoritySha256']:raise ValueError('source/authority drift')
    if time.time()>=p['notAfter']:raise ValueError('workflow deadline')
    authority_check(p['authority'],p['discovery'],p['track'],set(p['workload']['operationIds'])|set(p.get('operationalOperationIds',[])),p['permissions'])
    validate_workload(p['discovery'],recipe,p['track'],p['workload'],p['permissions'])
    if p['workload'].get('nativeControl') and (p['authority'].get('controlledFixtureOwner') is None or p['transportBinding'].get('evidence',{}).get('controlOwner')!=p['authority']['controlledFixtureOwner']):raise ValueError('native control ownership missing')
    if not set(p['workload']['operationIds'])<=set(cap['supportedOperationIds']):raise ValueError('operation capability drift')
    if p.get('coverageGaps')!=coverage_gaps(p['discovery'],p['track'],set(p['workload']['operationIds']),cap,p['workload']):raise ValueError('coverage gap inventory drift')
    b,proof=inspection()
    if b!=p['discovery']['product']['binding']:raise ValueError('binding drift')
    from .anonymous import transport
    from .discovery import validate_transport,execution_origin
    (transport if p['track']=='be-anonymous' else validate_transport)(p['discovery'],b,proof)
    # Preserve all aliases while locking their order and the independent origin set.
    for role,key in [('scanner','scannerOrigins'),('direct','directOrigins')]:
        if p['transportBinding'].get(key)!=proof.get(key):raise ValueError('transport origin/alias drift')
    if p['workload'].get('nativeControl') and proof.get('evidence',{}).get('controlOwner')!=p['authority']['controlledFixtureOwner']:raise ValueError('native control ownership drift')
    return recipe

def compile_track(p, *, actor=None, fixtures=None, identity_strategy=None):
    """Translate a locked recipe workload to existing native contracts, never a new scan engine."""
    if p.get('track')=='fe-authenticated':
        from .fe_authenticated_contract import validate_plan
        return validate_plan(p,live=True)
    if p.get('track')=='fe-anonymous':
        from .fe_anonymous_contract import validate_plan
        return validate_plan(p,live=True)
    d=p['discovery'];b=d['product']['binding'];w=p['workload'];a=p['authority'];track=p['track']
    if 'actorRefs' in w or w.get('fixtureKind'):raise ValueError('preparation-only workflow; use prepare/business-fixtures')
    if track=='be-anonymous':
        from .anonymous import compile_plan
        aa={'environment':d['product']['environment'],'source':a['authorizationRef'],'discoveryRead':True,
            'publicMutation':'mutation' in p['permissions'],'deniedMutation':'mutation' in p['permissions'],
            'active':'active' in p['permissions'],'fixtureSetup':'setup' in p['permissions'],
            'secretPersistenceAccepted':a.get('secretPersistenceAccepted',False)}
        return compile_plan(d,live_binding=b,observed_transport=p['transportBinding'],run_id=p['runId'],
            cases=w['cases'],campaigns=w.get('campaigns',[]),authority=aa,fixtures=fixtures if fixtures is not None else w.get('fixtures',[]),dispositions=w['dispositions'],not_after=p['notAfter'])
    if track=='be-authenticated':
        from .discovery import compile_plan,validate_plan
        if actor is None:raise ValueError('independently established actor required')
        q=compile_plan(d,live_binding=b,observed_transport=p['transportBinding'],actor=actor,
            requests=w['requests'],fixtures=fixtures or [],authority={'fixtureActiveAuthorized':'active' in p['permissions'],'source':a['authorizationRef']},identity_strategy=identity_strategy)
        q['secretPersistenceAccepted']=a['secretPersistenceAccepted'];q['execution']=copy.deepcopy(w['execution'])
        q['ruleIds']=copy.deepcopy(w.get('ruleIds',q['ruleIds']))
        if w.get('pathAttackIndices'):q['vectors']=['path']
        q['parameterScope']={'query':{o['pathTemplate']:o['input'].get('query',[]) for o in d['operations']}}
        validate_plan(q,b);return q
    from .product_bola import compile_cases
    return compile_cases(p)


def validate_workload(doc,recipe,track,w,permissions):
    from .bola_research import validate_request
    from .discovery import matches,path_valid
    ids=set(w['operationIds']);ops={o['id']:o for o in doc['operations']}
    if w.get('fixtureKind')=='owned-business':
        if not hasattr(recipe,'prepare_business') or not set(recipe.BUSINESS_OPERATION_IDS)<=ids:raise ValueError('business fixture capability missing')
        if not {'mutation','read','poststate','dedicated-catalog'}<=set(permissions):raise ValueError('business fixture authority missing')
        return
    if 'actorRefs' in w:
        if not hasattr(recipe,'registration') or any(role!=getattr(recipe,'REGISTER_ROLE',None) for role in w['actorRefs'].values()):raise ValueError('setup role unsupported')
        if not {'setup','login','read'}<=set(permissions):raise ValueError('setup authority missing')
        return
    requests=[]
    if track=='be-anonymous':
        requests=w['cases']
        for c in requests:
            if any(k.lower() in ('authorization','cookie','proxy-authorization') for k in c.get('headers',{})):raise ValueError('anonymous identity header forbidden')
        if w.get('campaigns') and 'active' not in permissions:raise ValueError('active authority missing')
    elif track=='be-authenticated':
        if 'ruleIds' in w:
            selected=w['ruleIds']
            if (not isinstance(selected,list) or not selected or any(type(rule)!=int or rule not in (40012,40018) for rule in selected)
                    or len(selected)!=len(set(selected))):raise ValueError('unsupported/duplicate selected native rule set')
        requests=w['requests']+w['execution']['seeds']+w['execution']['attacks']
        if w['execution']['attacks'] and 'active' not in permissions:raise ValueError('active authority missing')
        if 'pathAttackIndices' in w:validate_path_actions(doc,w)
        for index,action in enumerate(w['execution']['attacks']):
            if index not in w.get('pathAttackIndices',[]) and (action['method']!='GET' or action.get('body') is not None):validate_body_action(doc,recipe,w,action)
        if w['execution']['crawl']!=ops[workload_identity(recipe,doc,w)['operationId']]['pathTemplate']:raise ValueError('identity crawl drift')
        for oid,fields in w.get('mutableBodyFields',{}).items():
            if oid not in ids:raise ValueError('mutable field operation outside subset')
            allowed=recipe.mutable_fields(ops[oid]) if hasattr(recipe,'mutable_fields') else recipe.MUTABLE_FIELDS.get(oid,[])
            if not set(fields)<=set(allowed):raise ValueError('mutable body fields outside recipe; references/identity fixed')
        for group,allocations in [('seed',w['execution']['seeds']),('attack',w['execution']['attacks'])]:
            for index,action in enumerate(allocations):
                if action['method'] in ('GET','HEAD','OPTIONS'):continue
                assertion=w.get('nativeAssertions',{}).get(group+'-'+str(index))
                if not assertion or not assertion.get('reads') or not (assertion.get('unchanged') is True or assertion.get('postEquals') or assertion.get('transition')):raise ValueError('native mutation business oracle missing')
                if not {'read','poststate'}<=set(permissions):raise ValueError('native oracle authority missing')
                for read in assertion['reads']:
                    validate_request(doc,read)
                    if read['method']!='GET' or read['operationRef'] not in ids:raise ValueError('native oracle outside frozen scope')
    else:
        requests=[c[k] for c in w['cases'] for k in ('request','beforeRequest','afterRequest')]+[request for c in w['cases'] for request in c.get('pageRequests',[])]+[request for c in w['cases'] for request in c.get('relatedRequests',[])]
        for actor in w['actors'].values():
            if hasattr(recipe,'validate_actor'):recipe.validate_actor(actor)
            requests.append(actor['identityRequest'])
            if not actor.get('subject') or not actor.get('role'):raise ValueError('actor role/subject missing')
    for request in requests:
        u=urlsplit(request['path']);path_valid(u.path)
        if u.scheme or u.netloc or u.fragment:raise ValueError('foreign workload request')
        found=[o for o in doc['operations'] if o['method']==request['method'] and matches(o['pathTemplate'],u.path)]
        literal=[o for o in found if o['pathTemplate']==u.path]
        if literal:found=literal
        if len(found)!=1 or found[0]['id'] not in ids:raise ValueError('workload operation outside authority subset')
        if request['method'] not in ('GET','HEAD','OPTIONS') and 'mutation' not in permissions:raise ValueError('mutation authority missing')
        if track=='be-authenticated' and not found[0]['protected']:raise ValueError('authenticated workload must be protected')
    return True


def archive_sources(p,out):
    """Retain exact assessment/checker/recipe/schema bytes for offline replay after source changes."""
    from .bola_research import save
    out=Path(out);index=[]
    for number,(name,expected) in enumerate(p['implementationPins'].items()):
        source=Path(name);blob=source.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=expected:raise ValueError('implementation changed before source archive')
        target='source/'+str(number).zfill(3)+'-'+source.name;save(out,target,blob)
        index.append({'original':name,'path':target,'sha256':expected})
    save(out,'WORKFLOW.json',p);save(out,'SOURCE_ARCHIVE.json',index)


def workload_identity(recipe,doc,workload):
    if workload.get('actorRole'):
        from .product_identity import strategy
        return strategy(recipe,doc,workload['actorRole'],imported=True)
    return doc['auth']['identity']


def coverage_gaps(doc,track,selected,cap,workload=None):
    gaps=[{'operationId':o['id'],'reason':'no compatible recipe' if o['id'] not in cap['supportedOperationIds'] else 'outside selected workload; prerequisites/authority/recipe allocation required'} for o in doc['operations'] if o['id'] not in selected]
    if track=='be-authenticated':
        from .discovery import matches
        w=workload or {};attacks=w.get('execution',{}).get('attacks',[])
        for o in doc['operations']:
            if not o['protected'] or o['method'] in ('HEAD','OPTIONS'):continue
            allocated=any(a['method']==o['method'] and (o['method']=='GET' or a.get('body') is not None or bool(w.get('pathAttackIndices'))) and matches(o['pathTemplate'],urlsplit(a['path']).path) for a in attacks)
            if allocated:continue  # Admission checked this exact allocation; execution proof still separate.
            gaps.append({'operationId':o['id'],'vector':'native active query/path' if o['method']=='GET' else 'native active body','reason':'not allocated; requires supported flat update shape, current controlled proof, owned fixture and transition oracle' if o['method'] in ('PUT','PATCH') else 'native active method unsupported; seed is not active body coverage'})
    return gaps


def reconcile_responsibilities(cases,observations,prerequisites):
    """Finite continuation selection; case dependencies never become an operation-wide gate.

    The caller supplies reviewed cases/allocations, not a Cartesian product. Observations
    are selected lineage evidence units, not retry counts. Unknown outcomes require readback.
    """
    if len({c['caseId'] for c in cases})!=len(cases):raise ValueError('duplicate responsibility')
    rows=[];eligible=[];allocations={}
    for c in cases:
        cid=c['caseId'];refs=c.get('evidenceRefs',[])
        if not refs:raise ValueError('responsibility provenance missing')
        if c.get('disposition') in ('user-excluded','not-applicable'):
            if not c.get('reason'):raise ValueError('exclusion needs reason and provenance')
            if c.get('disposition')=='not-applicable' and c.get('gapKind') in ('role','auth','fixture','capability','configuration'):raise ValueError('prerequisite is not inapplicability')
            rows.append({'caseId':cid,'status':c['disposition'],'reason':c['reason']});continue
        seen=observations.get(cid,{})
        if seen.get('outcomeUnknown'):
            rows.append({'caseId':cid,'status':'blocked','dependencies':['reconcile allocation/state before retry'],'outcomeUnknown':True});continue
        required=set(c.get('requiredEvidence',[]));proved=set(seen.get('evidenceUnits',[]))
        if required and seen.get('outcome') in ('matched','violated') and required<=proved and (not c.get('requireResultRead') or seen.get('resultRead') is True):
            rows.append({'caseId':cid,'status':'observed','outcome':seen['outcome']});continue
        missing=[key for key in c.get('prerequisites',[]) if prerequisites.get(key) is not True]
        if missing:rows.append({'caseId':cid,'status':'blocked','dependencies':missing});continue
        row={'caseId':cid,'status':'eligible','missingEvidence':sorted(required-proved)};rows.append(row);eligible.append(cid)
        if c.get('allocation'):
            a=c['allocation'];key=a['id']
            if key in allocations and allocations[key]!=a:raise ValueError('continuation allocation conflict')
            allocations[key]=a
    return {'taskCompletion':'partial' if not rows or any(r['status'] in ('eligible','blocked') for r in rows) else 'observations-complete-policy-separate',
            'cases':rows,'nextEligibleCaseIds':eligible,'nextAllocations':list(allocations.values()),'handoffClosesTask':False}


def validate_body_action(doc,recipe,w,action):
    from .discovery import matches
    body=action.get('body')
    if not w.get('nativeControl') and not w.get('nativeBodyProof'):raise ValueError('guard delivery proof missing for native body')
    if action['method'] not in ('PUT','PATCH') or not isinstance(body,dict) or not body or any(type(v) not in (str,int,float,bool,type(None)) for v in body.values()):raise ValueError('unsupported native body shape/method; flat JSON update only')
    op=next((o for o in doc['operations'] if o['method']==action['method'] and matches(o['pathTemplate'],urlsplit(action['path']).path)),None)
    if op is None:raise ValueError('native body operation unknown')
    fields=w.get('mutableBodyFields',{}).get(op['id'],[])
    allowed=recipe.mutable_fields(op) if hasattr(recipe,'mutable_fields') else recipe.MUTABLE_FIELDS.get(op['id'],[])
    if len(fields)!=1 or not set(fields)<=set(allowed)&set(body):raise ValueError('native mutable mapping absent/unsupported; references remain fixed')
    if not w.get('nativeControl'):verify_body_proof(w['nativeBodyProof'])
    index=w['execution']['attacks'].index(action);oracle=w.get('nativeAssertions',{}).get('attack-'+str(index),{}).get('transition')
    if not oracle or oracle.get('field') not in fields or not oracle.get('fixedState') or not oracle.get('acceptedStatuses') or not oracle.get('rejectedStatuses'):raise ValueError('native body transition oracle missing')
    seeds=[s for s in w['execution']['seeds'] if s['method']==action['method'] and s['path']==action['path']]
    # ZAP selects the latest recorded request/response for this method/path. An
    # invalid trailing control would otherwise become the active campaign baseline.
    if not seeds or seeds[-1].get('body')!=body or not seeds[-1].get('expected') or not set(seeds[-1]['expected'])<=set(oracle['acceptedStatuses']):raise ValueError('native body requires last matching seed to be its valid accepted baseline')
    fixed={k:v for k,v in body.items() if k not in fields}
    if any(not isinstance(s.get('body'),dict) or set(s['body'])!=set(body) or any(s['body'][k]!=v for k,v in fixed.items()) for s in seeds):raise ValueError('native body seed fixed reference drift')
    return op


def body_proof_pins():
    root=Path(__file__).parent
    return {str(root/name):hashlib.sha256((root/name).read_bytes()).hexdigest() for name in ('product_native.py','product_workflow.py','product_prepare.py','product_identity.py','signed_identity.py','discovery.py','research.py','research_product.py')}


def validate_path_actions(doc,w):
    """Proof-gated selectors; write methods also require owned fixtures and state oracles."""
    from .anonymous_guard import path_scope
    from .discovery import matches
    indices=w['pathAttackIndices'];attacks=w['execution']['attacks']
    if (not isinstance(indices,list) or not indices or any(type(i)!=int or i<0 or i>=len(attacks) for i in indices)
            or len(set(indices))!=len(indices) or set(indices)!=set(range(len(attacks)))):
        raise ValueError('path allocation must be a nonempty exclusive path batch')
    for i in indices:
        a=attacks[i];u=urlsplit(a['path'])
        if a['method'] not in ('GET','DELETE','POST') or a.get('body') is not None or u.query:raise ValueError('path capability has no body/query')
        found=[o for o in doc['operations'] if o['method']==a['method'] and matches(o['pathTemplate'],u.path)]
        if len(found)!=1:raise ValueError('path operation ambiguous')
        path_scope(found[0]['pathTemplate'],u.path)
        seeds=[s for s in w['execution']['seeds'] if s['method']==a['method'] and s['path']==a['path']]
        if not seeds or not seeds[-1].get('expected') or any(status<200 or status>=300 for status in seeds[-1]['expected']):raise ValueError('path capability requires successful exact baseline')
        if a['method']!='GET':
            requests=[r for r in w['requests'] if r['method']==a['method'] and r['path']==u.path]
            oracle=w.get('nativeAssertions',{}).get('attack-'+str(i),{})
            if not requests or not all(r.get('fixtureOwned') is True and r.get('fixtureRefs') for r in requests) or not oracle.get('reads') or not (oracle.get('unchanged') is True or oracle.get('postEquals')):raise ValueError('path mutation requires owned fixture and exact state oracle')
    if not w.get('nativeControl'):verify_path_proof(w.get('nativePathProof'),{attacks[i]['method'] for i in indices})


def path_proof_pins():
    root=Path(__file__).parent
    return {**body_proof_pins(),str(root/'anonymous_guard.py'):hashlib.sha256((root/'anonymous_guard.py').read_bytes()).hexdigest()}


def verify_path_proof(ref,methods=None):
    import json
    if not isinstance(ref,dict):raise ValueError('native path control proof required')
    path=Path(ref['path']);blob=path.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=ref['sha256']:raise ValueError('native path proof drift')
    proof=json.loads(blob)
    if (proof.get('capability')!='native-numeric-path/1.0' or proof.get('implementationPins')!=path_proof_pins()
            or not proof.get('controlledFixtureOwner') or not proof.get('guardControls') or not proof.get('deliveredPathMessages')
            or not proof.get('allTerminal') or not proof.get('reportReadback')):raise ValueError('native path proof incomplete or implementation mismatch')
    if not set(methods or [])<=set(proof.get('provenMethods',[])):raise ValueError('native path method lacks controlled proof')
    for row in proof['evidence']:
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('native path evidence drift')
    return proof


def verify_body_proof(ref):
    import json
    path=Path(ref['path']);blob=path.read_bytes()
    if hashlib.sha256(blob).hexdigest()!=ref['sha256']:raise ValueError('native body proof drift')
    proof=json.loads(blob)
    if proof.get('capability')!='native-flat-json-update/1.0' or proof.get('implementationPins')!=body_proof_pins():raise ValueError('native body proof implementation mismatch')
    if not proof.get('controlledFixtureOwner') or not proof.get('guardControls') or not proof.get('deliveredBodyMessages') or not proof.get('allTerminal') or not proof.get('reportReadback'):raise ValueError('native body proof incomplete')
    for row in proof['evidence']:
        if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('native body proof evidence drift')
    return proof
