"""Narrow protected JSON subject/role strategy and private credential import, recipe mapped."""
import hashlib,json
from pathlib import Path
from .discovery import verify_identity,canonical_hash
from .product_checks import pointer
from .bola_research import DirectClient,save


def strategy(recipe,doc,role,*,imported=False):
    mapping=getattr(recipe,'IDENTITY_STRATEGIES',{}).get(role)
    if mapping is None:
        if imported or role!=getattr(recipe,'REGISTER_ROLE',None):raise ValueError('role-specific protected identity strategy unsupported; import not admitted')
        a=doc['auth']['identity'];return {'version':'protected-json-subject/1.0','operationId':a['operationId'],'subjectPointer':a['subjectPointer']}
    if mapping.get('version')=='signed-jwt-protected-probe/1.0':
        op=next((o for o in doc['operations'] if o['id']==mapping['operationId']),None)
        if not op or not op['protected'] or op['method']!='GET' or mapping.get('expectedStatus') not in (200,403) or not all(mapping.get(k) for k in ('issuer','audience','roleClaim','responsePointer','responseValue')):raise ValueError('signed protected identity mapping unsupported')
        if doc['auth']['headerName']!='Authorization' or doc['auth']['headerPrefix']!='Bearer ':raise ValueError('signed identity transport unsupported')
        return mapping
    if mapping.get('version')!='protected-json-subject-role/1.0' or not mapping.get('rolePointer'):raise ValueError('unknown identity strategy')
    op=next((o for o in doc['operations'] if o['id']==mapping['operationId']),None)
    if not op or not op['protected'] or op['method']!='GET' or mapping['subjectPointer']!=doc['auth']['identity']['subjectPointer'] or mapping['operationId']!=doc['auth']['identity']['operationId']:raise ValueError('protected identity mapping drift')
    return mapping


def check_identity(status,content_type,body,subject,role,mapping):
    verify_identity(status,content_type,body,subject,mapping['subjectPointer'])
    if mapping['version']=='protected-json-subject-role/1.0':
        if pointer(body,mapping['rolePointer'])!=role:raise ValueError('protected role mismatch')
    elif mapping['version']!='protected-json-subject/1.0':raise ValueError('unknown identity strategy')
    return True


def evidence_value(row,key):
    p=Path(row['path'])
    if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=row['sha256']:raise ValueError('actor source evidence drift')
    return pointer(json.loads(p.read_text()),row[key])


def import_actor(p,inspection,out,private_input):
    from .product_workflow import validate_workflow,authority_check
    recipe=validate_workflow(p,inspection);d=p['discovery'];role=private_input['role'];subject=str(private_input['subject'])
    mapping=strategy(recipe,d,role,imported=True)  # unsupported strategy rejects before login
    signed=mapping['version']=='signed-jwt-protected-probe/1.0'
    if signed and p['workload'].get('actorRole')!=role:raise ValueError('signed actor role must be frozen in workload')
    trust=private_input.get('jwtTrust')
    if signed:verify_trust(trust,d)
    sources=private_input['sourceEvidence']
    if not sources or not all(str(evidence_value(r,'subjectPointer'))==subject and evidence_value(r,'rolePointer')==role for r in sources):raise ValueError('independent imported subject/role source mismatch')
    ops={o['id']:o for o in d['operations']};login=d['auth']['loginOperationId'];oid=mapping['operationId']
    authority_check(p['authority'],d,p['track'],[login,oid],['network','login','read'])
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    client=DirectClient(d,d['product']['binding'],inspection,out/'direct',{'permissions':p['permissions']},actor_refs=('actor',),allow_empty=True,not_after=p['notAfter'])
    a=d['auth'];payload={a['usernameField']:private_input['username'],a['passwordField']:private_input['password']}
    client.secret_values.extend(payload.values())
    s,b,login_ref=client.request('import-login','actor',{'operationRef':login,'method':'POST','path':ops[login]['pathTemplate'],'body':payload},'login',sensitive=True)
    if s!=200:raise ValueError('import login failed; no replay')
    token=pointer(b,a['tokenPointer']);identity={'operationRef':oid,'method':'GET','path':ops[oid]['pathTemplate'],'body':None}
    s,b,ref=client.request('import-protected-identity','actor',identity,'read',token=token)
    if signed:
        from .signed_identity import check_probe
        check_probe(s,b,token,trust,mapping,subject,role)
    else:check_identity(s,'application/json',b,subject,role,mapping)
    controls=[]
    for label,control_token in [('anonymous',None),('invalid-session','owned-invalid-session')]:
        s,b,e=client.request('import-'+label,'anonymous' if control_token is None else 'actor',identity,'read',token=control_token)
        if s not in ((401,) if signed else (401,403)):raise ValueError('protected identity negative control failed')
        controls.append({'control':label,'status':s,'evidenceRef':str(out/'direct'/e)})
    receipt={'version':'private-credential-import/1.0','subject':subject,'role':role,'identityStrategy':mapping,'sourceEvidence':sources,
             'bindingSha256':canonical_hash(d['product']['binding']),'authoritySha256':p['authoritySha256'],'protectedEvidence':str(out/'direct'/ref),'protectedEvidenceSha256':hashlib.sha256((out/'direct'/ref).read_bytes()).hexdigest(),'controls':controls}
    if signed:receipt['jwtTrust']=trust
    save(out,'IMPORT.json',receipt);receipt_ref={'path':str(out/'IMPORT.json'),'sha256':hashlib.sha256((out/'IMPORT.json').read_bytes()).hexdigest()}
    actor={'username':private_input['username'],'password':private_input['password'],'token':token,'subject':subject,'role':role,'identityRequest':identity,'subjectPointer':mapping.get('subjectPointer'),'identityStrategy':mapping,
           'provenance':{'subject':subject,'runId':p['runId'],'credentialRef':'private:'+str(out/'actor.json'),'sourceOperationId':login,'evidenceRefs':[str(out/'IMPORT.json')],'provenanceKind':'private-credential-import/1.0','importReceipt':receipt_ref}}
    if signed:actor['jwtTrust']=trust
    save(out,'actor.json',actor);return {'executionStatus':'imported','subject':subject,'role':role,'identityStrategy':mapping['version'],'scanRequests':0}


def verify_import(actor):
    a=actor['provenance'];ref=a['importReceipt'];blob=Path(ref['path']).read_bytes()
    if hashlib.sha256(blob).hexdigest()!=ref['sha256']:raise ValueError('import receipt drift')
    receipt=json.loads(blob)
    if receipt['subject']!=str(actor['subject']) or receipt['role']!=actor['role'] or receipt['identityStrategy']!=actor['identityStrategy']:raise ValueError('import actor binding mismatch')
    if receipt.get('jwtTrust')!=actor.get('jwtTrust'):raise ValueError('import signing trust binding mismatch')
    if receipt.get('jwtTrust'):
        trust=receipt['jwtTrust'];p=Path(trust['publicKey']['path'])
        if hashlib.sha256(p.read_bytes()).hexdigest()!=trust['publicKey']['sha256']:raise ValueError('signing public key drift')
        for row in trust['sourceEvidence']:
            if hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()!=row['sha256']:raise ValueError('signing trust provenance drift')
    for r in receipt['sourceEvidence']:
        if str(evidence_value(r,'subjectPointer'))!=receipt['subject'] or evidence_value(r,'rolePointer')!=receipt['role']:raise ValueError('import source mismatch')
    if hashlib.sha256(Path(receipt['protectedEvidence']).read_bytes()).hexdigest()!=receipt['protectedEvidenceSha256']:raise ValueError('import protected evidence drift')
    return receipt


def verify_trust(trust,doc):
    if not isinstance(trust,dict) or trust.get('bindingSha256')!=canonical_hash(doc['product']['binding']) or not trust.get('sourceEvidence'):raise ValueError('signing trust needs independently bound deployment provenance')
    key=trust['publicKey'];path=Path(key['path'])
    if not path.is_absolute() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=key['sha256']:raise ValueError('signing public key pin mismatch')
    for row in trust['sourceEvidence']:
        p=Path(row['path']);blob=p.read_bytes()
        if hashlib.sha256(blob).hexdigest()!=row['sha256']:raise ValueError('signing trust source drift')
        source=json.loads(blob)
        if source.get('targetBinding')!=doc['product']['binding'] or source.get('publicKeySha256')!=key['sha256']:raise ValueError('signing key deployment binding mismatch')
    return True
