"""Source-assisted inventory. Candidates deliberately are NOT executable discovery 1.1."""
import copy
import datetime as dt
import hashlib
from pathlib import Path
from .discovery import canonical_hash, secret_check, validate_discovery, verify_local_sources

VERSION='product-source-candidate/1.0'

def source_inventory(product, observations):
    root=Path(product).resolve(strict=True)
    if not root.is_dir():raise ValueError('product directory required')
    secret_check(observations)
    sources=[]
    for row in observations['sources']:
        path=(root/row['path']).resolve(strict=True)
        if not path.is_relative_to(root) or not path.is_file():raise ValueError('source outside requested product')
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=row['sha256']:raise ValueError('source observation drift; reread source')
        sources.append({'id':row['id'],'kind':'source','location':str(path),'sha256':digest,
                        'observedAt':dt.datetime.now(dt.timezone.utc).isoformat(),'confidence':'medium'})
    refs={s['id'] for s in sources}
    for row in observations['operations']:
        if not row['evidenceRefs'] or not set(row['evidenceRefs'])<=refs:raise ValueError('operation provenance missing')
    # Validate the *source facts* with the existing reader, without invented environment.
    candidate={'schemaVersion':VERSION,'stage':'source-only','productLocation':str(root),
        'sources':sources,'operations':copy.deepcopy(observations['operations']),
        'auth':copy.deepcopy(observations.get('auth')),'fixtures':copy.deepcopy(observations.get('fixtures',[])),
        'policies':copy.deepcopy(observations.get('policies',[])),
        'backendOnly':observations.get('backendOnly',False),'conflicts':copy.deepcopy(observations.get('conflicts',[])),
        'gaps':copy.deepcopy(observations.get('gaps',[])),
        'environment':None,'binding':None,'origins':[]}
    # Discovery retains auth facts even when no finite executor can compile them.
    auth=candidate['auth']
    if auth and not {'loginOperationId','usernameField','passwordField','tokenPointer','headerName','headerPrefix','identity','credentialRef'}<=auth.keys():
        candidate['authObservations']=auth;candidate['auth']=None
    validate_candidate(candidate)
    return candidate

def validate_candidate(c):
    if c.get('schemaVersion')!=VERSION or c.get('stage')!='source-only':raise ValueError('source candidate version/stage')
    if c['environment'] is not None or c['binding'] is not None or c['origins']:raise ValueError('source candidate cannot claim deployment')
    verify_local_sources(c)
    from .discovery import schema_check,path_valid
    schema_check(c,'product-source-candidate-v1.schema.json')
    refs={s['id'] for s in c['sources']}
    seen=set()
    if len(refs)!=len(c['sources']) or not refs:raise ValueError('duplicate/missing source')
    for op in c['operations']:
        path_valid(op['pathTemplate'],True)
        identity=(op['method'],op['pathTemplate'])
        if identity in seen or not set(op['evidenceRefs'])<=refs:raise ValueError('duplicate/unproven source operation')
        seen.add(identity)
    ids={o['id']:o for o in c['operations']}
    if len(ids)!=len(c['operations']):raise ValueError('duplicate operation ID')
    for row in c['fixtures']+c['gaps']+c['conflicts']+c['policies']:
        if not set(row['evidenceRefs'])<=refs:raise ValueError('candidate provenance missing')
    for f in c['fixtures']:
        if not set(f['operationIds'])<=ids.keys():raise ValueError('candidate fixture operation unknown')
    if c['auth']:
        a=c['auth'];identity=a['identity']
        for oid in (a['loginOperationId'],identity['operationId'],identity['actorSource']['operationId']):
            if oid not in ids:raise ValueError('candidate auth operation absent')
        if not ids[identity['operationId']]['protected']:raise ValueError('candidate identity must be protected')
    secret_check(c)
    return c

def _document(c, environment, binding, origins, env_ref):
    refs=[s['id'] for s in c['sources']]
    return {'schemaVersion':'product-discovery/1.1',
        'product':{'location':c['productLocation'],'environment':environment,'description':'Source-assisted backend inventory; runtime completeness unproven',
                   'environmentEvidenceRefs':[env_ref],'binding':binding,'origins':origins},
        'sources':copy.deepcopy(c['sources']),'operations':copy.deepcopy(c['operations']),
        'auth':copy.deepcopy(c['auth']),'fixtures':copy.deepcopy(c['fixtures']),
        'tracks':{t:{'status':'not-applicable' if c['backendOnly'] and t.startswith('fe-') else 'candidate',
                     'reason':'Backend-only source' if c['backendOnly'] and t.startswith('fe-') else 'Runtime/authority/recipe gates required',
                     'evidenceRefs':refs} for t in ('fe-anonymous','be-anonymous','fe-authenticated','be-authenticated','bola-ownership')},
        'ui':[],'authObservations':copy.deepcopy(c.get('authObservations')),'conflicts':copy.deepcopy(c['conflicts']),'gaps':copy.deepcopy(c['gaps'])}

def materialize(c, deployment_source, environment, binding, origins):
    validate_candidate(c)
    if not binding or not environment or not origins:raise ValueError('runtime binding/environment/origins unresolved')
    if deployment_source['kind'] not in ('deployment','runtime'):raise ValueError('environment needs deployment provenance')
    d=_document(c,environment,binding,origins,deployment_source['id'])
    d['sources'].append(copy.deepcopy(deployment_source));validate_discovery(d);verify_local_sources(d)
    return d
