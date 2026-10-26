"""Recipe-owned API setup, reused DirectClient and exact run ledger. No DB/role changes."""
import secrets
from pathlib import Path
from .bola_research import DirectClient,save,pointer
from .discovery import canonical_hash,verify_identity
from .product_workflow import validate_workflow,authority_check


def prepare(p,inspection,out):
    recipe=validate_workflow(p,inspection);w=p['workload'];d=p['discovery']
    if not hasattr(recipe,'registration'):raise ValueError('recipe actor setup unsupported; no side effect')
    refs=w['actorRefs']
    if not refs or any(role!=getattr(recipe,'REGISTER_ROLE',None) for role in refs.values()):raise ValueError('registration cannot provision requested role')
    a=d['auth'];ops={o['id']:o for o in d['operations']}
    needed=[a['identity']['actorSource']['operationId'],a['loginOperationId'],a['identity']['operationId']]
    if not set(needed)<=set(w['operationIds']):raise ValueError('setup operations outside frozen scope')
    authority_check(p['authority'],d,p['track'],needed,['network','setup','login','read'])
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False);ledger=[];actors={}
    def current():validate_workflow(p,inspection);return inspection()
    client=DirectClient(d,d['product']['binding'],current,out/'direct',{'permissions':p['permissions']},actor_refs=tuple(refs),allow_empty=True,not_after=p['notAfter'])
    def req(oid,body):
        o=ops[oid];return {'operationRef':oid,'method':o['method'],'path':o['pathTemplate'],'body':body}
    for ref,role in refs.items():
        password='Owned!'+secrets.token_urlsafe(24);marker='mp-'+secrets.token_hex(8)
        data=recipe.registration(marker,password,'09'+str(secrets.randbelow(10**8)).zfill(8))
        client.secret_values.extend([password,data[a['usernameField']]])
        status,body,evidence=client.request('register-'+ref,ref,req(needed[0],data),'setup',sensitive={'subjectPointer':a['identity']['actorSource']['subjectPointer']})
        if status!=201:raise ValueError('fresh registration not created; no replay')
        subject=str(pointer(body,a['identity']['actorSource']['subjectPointer']))
        ledger.append({'runId':p['runId'],'kind':'actor','actorRef':ref,'wireId':subject,'creationEvidence':evidence,'state':'retained','cleanupRequest':None})
        save(out,'ledger-revisions/'+str(len(ledger))+'.json',ledger)
        status,body,_=client.request('login-'+ref,ref,req(needed[1],{a['usernameField']:data[a['usernameField']],a['passwordField']:password}),'login',sensitive=True)
        if status!=200:raise ValueError('login failed; no replay')
        token=pointer(body,a['tokenPointer']);client.secret_values.append(token)
        identity=req(needed[2],None)
        status,body,_=client.request('protected-identity-'+ref,ref,identity,'read',token=token)
        from .product_identity import strategy,check_identity
        mapping=strategy(recipe,d,role)
        check_identity(status,'application/json',body,subject,role,mapping)
        actors[ref]={'username':data[a['usernameField']],'password':password,'token':token,'subject':subject,'role':role,
            'identityRequest':identity,'subjectPointer':a['identity']['subjectPointer'],'registrationSha256':__import__('hashlib').sha256((out/'direct'/evidence).read_bytes()).hexdigest(),
            'provenance':{'subject':subject,'runId':p['runId'],'credentialRef':'private:actors.json#'+ref,
                          'sourceOperationId':needed[0],'evidenceRefs':[str(out/'direct'/evidence)]}}
        save(out,'actor-revisions/'+ref+'.json',actors[ref])  # private, immutable per-actor recovery record
    save(out,'LEDGER.json',ledger)
    save(out,'actors.json',actors)
    save(out,'PREPARATION.json',{'setupRequests':client.count,'scanRequests':0,'coverage':'setup/identity only','cleanupStatus':'retained','ledgerSha256':canonical_hash(ledger)})
    return {'executionStatus':'prepared','actorRefs':list(actors),'cleanupStatus':'retained','scanRequests':0}

def verify_actor(actor):
    """Independent fresh registration evidence; never trust a JWT/login claim as actor source."""
    import hashlib,json
    from .bola_research import pointer
    provenance=actor['provenance']
    if provenance.get('provenanceKind')=='private-credential-import/1.0':
        from .product_identity import verify_import
        verify_import(actor);return True
    path=Path(provenance['evidenceRefs'][0])
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=actor['registrationSha256']:raise ValueError('registration evidence missing/drift')
    record=json.loads(path.read_text())
    if record['status']!=201 or str(record['body']['subject'])!=str(actor['subject']) or str(actor['subject'])!=provenance['subject']:raise ValueError('independent actor source mismatch')
    return True

def business(p,inspection,out,actors,catalog):
    recipe=validate_workflow(p,inspection)
    if not hasattr(recipe,'prepare_business'):raise ValueError('business fixture recipe unsupported before side effects')
    authority_check(p['authority'],p['discovery'],p['track'],recipe.BUSINESS_OPERATION_IDS,['network','read','mutation','poststate','dedicated-catalog'])
    if catalog.get('runId')!=p['runId'] or catalog.get('dedicated') is not True or not catalog.get('creationEvidence'):raise ValueError('catalog ownership absent')
    for actor in actors.values():verify_actor(actor)
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    def current():validate_workflow(p,inspection);return inspection()
    client=DirectClient(p['discovery'],p['discovery']['product']['binding'],current,out/'direct',{'permissions':p['permissions']},actor_refs=tuple(actors),allow_empty=True,not_after=p['notAfter'],capture_fields=recipe.CAPTURE_FIELDS)
    client.set_tokens(actors);revision=[0]
    def record(ledger):
        revision[0]+=1;save(out,'ledger-revisions/'+str(revision[0])+'.json',ledger)
    result=recipe.prepare_business(client,actors,catalog,p['runId'],record);save(out,'BUSINESS.json',result);return result
