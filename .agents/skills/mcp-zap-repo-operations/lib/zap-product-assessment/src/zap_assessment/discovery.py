"""Product-neutral discovery contract and bounded research plan compiler.

Agent interprets evidence; this layer validates references and binds requests.
It does not discover routes by guessing, execute product code or select adapters.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, unquote, parse_qsl
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
TRACKS = ('fe-anonymous','be-anonymous','fe-authenticated','be-authenticated','bola-ownership')
METHODS = ('GET','HEAD','OPTIONS','POST','PUT','PATCH','DELETE')
LIMITS = {'monitorIntervalSeconds':2,'stopDeadlineSeconds':10,'hostReserveBytes':2147483648,'operationTimeoutSeconds':180}


def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def schema_check(value, name):
    schema=json.loads((ROOT/'schemas'/name).read_text())
    errors=list(Draft202012Validator(schema).iter_errors(value))
    if errors:
        # Do not echo values (which may be a rejected credential).
        raise ValueError('invalid '+name+' at '+'.'.join(map(str,errors[0].absolute_path)))


def origin(value):
    u=urlsplit(value)
    if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.query or u.fragment or u.path not in ('','/'):
        raise ValueError('exact HTTP origin required')
    return value.rstrip('/')


def path_valid(path, template=False):
    u=urlsplit(path)
    decoded=unquote(u.path)
    if not path.startswith('/') or path.startswith('//') or u.scheme or u.netloc or u.query or u.fragment or '\\' in decoded or any(x in ('.','..') for x in decoded.split('/')) or any(ord(c)<32 for c in decoded):
        raise ValueError('invalid operation path')
    if not template and re.search(r'[{}]',path):raise ValueError('unresolved path template')
    return path


def matches(template,path):
    # Escape all literals; only full template segments can bind fixture IDs.
    parts=template.split('/')
    pattern='/'.join('[^/]+' if re.fullmatch(r'\{[A-Za-z_][\w-]*\}',p) else re.escape(p) for p in parts)
    return re.fullmatch(pattern,path) is not None


def secret_check(value):
    """References/field names are allowed, inline credential material is not."""
    if isinstance(value,dict):
        for k,v in value.items():
            if k.lower() in ('password','token','accesstoken','authorization','cookie','secret','apikey','rawhttp','requestheader','responseheader') and v:
                raise ValueError('inline credential/raw HTTP forbidden')
            secret_check(v)
    elif isinstance(value,list):
        for v in value:secret_check(v)
    elif isinstance(value,str) and (re.search(r'Bearer\s+[A-Za-z0-9._~-]{12,}',value) or re.search(r'eyJ[\w-]+\.eyJ[\w-]+\.[\w-]+',value)):
        raise ValueError('inline bearer forbidden')


def validate_discovery(doc, *, executable=False):
    schema_check(doc,'product-discovery-v1.1.schema.json' if doc.get('schemaVersion')=='product-discovery/1.1' else 'product-discovery-v1.schema.json');secret_check(doc)
    sources={s['id']:s for s in doc['sources']}
    if len(sources)!=len(doc['sources']):raise ValueError('duplicate source ID')
    def refs(row):
        if not row.get('evidenceRefs') or any(r not in sources for r in row['evidenceRefs']):raise ValueError('missing provenance')
    if doc['schemaVersion']=='product-discovery/1.1':
        if any(v not in sources for v in doc['product']['environmentEvidenceRefs']):raise ValueError('environment provenance missing')
    origins=set()
    for o in doc['product']['origins']:
        refs(o);origins.add(origin(o['url']))
        if doc['schemaVersion']=='product-discovery/1.1':
            required={'scanner':'scanner-network','direct':'orchestrator-host','ui':'browser'}.get(o['role'])
            if required and o['accessFrom']!=required:raise ValueError('origin execution access point mismatch')
    seen=set();ids={}
    for op in doc['operations']:
        refs(op)
        if not any(sources[r]['kind'] in ('source','openapi','runtime','traffic','ui') for r in op['evidenceRefs']):raise ValueError('operation lacks discovery observation source')
        if 'query' in op['input'] and (not isinstance(op['input']['query'],list) or not all(isinstance(q,str) for q in op['input']['query'])):raise ValueError('query names must be a list')
        path_valid(op['pathTemplate'],True);key=(op['method'],op['pathTemplate'])
        if key in seen or op['id'] in ids:raise ValueError('duplicate operation')
        seen.add(key);ids[op['id']]=op
    for f in doc['fixtures']:
        refs(f)
        if not set(f['operationIds'])<=ids.keys():raise ValueError('fixture refers to unknown operation')
    for t in doc['tracks'].values():refs(t)
    if doc.get('auth'):
        a=doc['auth'];refs(a)
        for oid in [a['loginOperationId'],a['identity']['operationId'],a['identity']['actorSource']['operationId']]:
            if oid not in ids:raise ValueError('auth operation missing')
        if ids[a['identity']['operationId']]['protected'] is not True:raise ValueError('identity must use protected operation')
        if ids[a['loginOperationId']]['method']!='POST':raise ValueError('unsupported login method for json bearer executor')
    if executable:
        if not doc['operations']:raise ValueError('no inventory; observe UI/traffic or provide source/spec')
        if not doc.get('auth'):raise ValueError('login details/identity oracle missing')
        if doc['auth']['kind']!='json-bearer':raise ValueError('unsupported auth extension; no fallback')
        if any(c['blocking'] for c in doc['conflicts']):raise ValueError('unresolved source/runtime conflict')
        if doc['tracks']['be-authenticated']['status'] not in ('candidate','ready'):raise ValueError('be-auth prerequisites blocked')
        if not doc['product']['binding']:raise ValueError('deployment binding missing')
        if not any(o['role']=='scanner' and o['authorized'] and o['bindingVerified'] for o in doc['product']['origins']):raise ValueError('no authorized verified scanner origin')
        for op in doc['operations']:
            if op['protected'] and op['method'] not in ('GET','HEAD','OPTIONS'):
                if not any(op['id'] in f['operationIds'] and f['preparation'] and f['ownership'] and f['postconditions'] for f in doc['fixtures']):
                    raise ValueError('mutation fixture preparation/ownership/poststate missing')
    return doc


def compile_plan(doc, *, live_binding, actor, requests, fixtures, authority, limits=None, observed_transport=None, identity_strategy=None):
    validate_discovery(doc,executable=True)
    if doc['product']['binding']!=live_binding:raise ValueError('discovery target binding drift')
    scanner=[o['url'] for o in doc['product']['origins'] if o['role']=='scanner' and o['authorized'] and o['bindingVerified']]
    if not scanner or (doc['schemaVersion']=='product-discovery/1.0' and len(scanner)!=1):raise ValueError('ambiguous scanner origin')
    if doc['schemaVersion']=='product-discovery/1.1':
        if observed_transport is None:raise ValueError('independent runtime transport observation required')
        validate_transport(doc,live_binding,observed_transport)
    ops={o['id']:o for o in doc['operations']};resolved=[]
    for req in requests:
        path_valid(req['path'])
        candidates=[o for o in ops.values() if o['method']==req['method'] and matches(o['pathTemplate'],req['path'])]
        # Literal routes take precedence over a parameter route (e.g. /things/options).
        literal=[o for o in candidates if o['pathTemplate']==req['path']]
        if literal:candidates=literal
        if len(candidates)!=1:raise ValueError('request outside discovered inventory or ambiguous')
        op=candidates[0]
        if not op['protected']:raise ValueError('be-auth execution request must be protected')
        row={**copy.deepcopy(req),'operationId':op['id'],'evidenceRefs':op['evidenceRefs']}
        if row not in resolved:resolved.append(row)
    if not resolved:raise ValueError('empty execution subset')
    a=doc['auth'];identity=ops[(identity_strategy or a['identity'])['operationId']]
    p={'schemaVersion':'research-plan/2.0','assuranceProfile':'be-authenticated-research/1.0','secretPersistenceAccepted':True,
       'environment':doc['product']['environment'],'authority':authority,'targetBinding':live_binding,
       'jobStore':'in-memory','coordinator':'single-node','origin':execution_origin(doc,'scanner'),'actorSubject':actor['subject'],
       'actor':copy.deepcopy(actor),'discovery':copy.deepcopy(doc),'discoverySha256':canonical_hash(doc),
       'operations':resolved,'fixtures':copy.deepcopy(fixtures),'ruleIds':[40012,40018],
       'vectors':['query','JSON-body'],'identityPath':identity['pathTemplate'],
       'limits':limits or dict(LIMITS)}
    if identity_strategy and identity_strategy.get('version')=='signed-jwt-protected-probe/1.0':p['identityStrategy']=copy.deepcopy(identity_strategy)
    if doc['schemaVersion']=='product-discovery/1.1':
        if observed_transport is None:raise ValueError('independent runtime transport observation required')
        p['schemaVersion']='research-plan/2.1';p['transportBinding']=copy.deepcopy(observed_transport)
    validate_plan(p,live_binding)
    return p


def validate_plan(plan,live_binding):
    schema_check(plan,'be-authenticated-research-plan-v2.1.schema.json' if plan.get('schemaVersion')=='research-plan/2.1' else 'be-authenticated-research-plan-v2.schema.json');secret_check(plan)
    doc=plan['discovery'];validate_discovery(doc,executable=True)
    if plan['schemaVersion']=='research-plan/2.1':
        if doc['schemaVersion']!='product-discovery/1.1':raise ValueError('discovery version mismatch')
        validate_transport(doc, live_binding, plan['transportBinding'])
        if plan['origin']!=execution_origin(doc,'scanner'):raise ValueError('origin selection drift')
    elif doc['schemaVersion']=='product-discovery/1.1':raise ValueError('discovery requires transport-bound plan')
    if canonical_hash(doc)!=plan['discoverySha256']:raise ValueError('discovery hash drift')
    if plan['targetBinding']!=live_binding or doc['product']['binding']!=live_binding:raise ValueError('target binding drift')
    if plan['environment']!=doc['product']['environment']:raise ValueError('environment drift')
    if not any(o['url']==plan['origin'] and o['role']=='scanner' and o['authorized'] and o['bindingVerified'] for o in doc['product']['origins']):raise ValueError('origin outside verified authority')
    origin(plan['origin']);path_valid(plan['identityPath'])
    a=plan['actor']
    if a['subject']!=plan['actorSubject'] or not a['evidenceRefs']:raise ValueError('actor provenance mismatch')
    if a.get('provenanceKind')=='private-credential-import/1.0':
        ref=a['importReceipt'];blob=Path(ref['path']).read_bytes()
        if hashlib.sha256(blob).hexdigest()!=ref['sha256']:raise ValueError('import receipt drift')
        receipt=json.loads(blob)
        if receipt['subject']!=a['subject'] or receipt['bindingSha256']!=canonical_hash(live_binding) or a['sourceOperationId']!=doc['auth']['loginOperationId']:raise ValueError('import provenance binding mismatch')
    elif a['sourceOperationId']!=doc['auth']['identity']['actorSource']['operationId']:raise ValueError('actor provenance mismatch')
    ids={o['id']:o for o in doc['operations']};fids={f['id']:f for f in plan['fixtures']}
    if len(fids)!=len(plan['fixtures']):raise ValueError('duplicate resolved fixture')
    for op in plan['operations']:
        path_valid(op['path']);known=ids.get(op['operationId'])
        if not known or not known['protected'] or known['method']!=op['method'] or not matches(known['pathTemplate'],op['path']):raise ValueError('operation outside discovered scope')
        if op['evidenceRefs']!=known['evidenceRefs']:raise ValueError('operation provenance drift')
        if op['method'] not in ('GET','HEAD','OPTIONS'):
            refs=op.get('fixtureRefs',[])
            if not refs or op.get('fixtureOwned') is not True:raise ValueError('mutation missing fixture')
            for ref in refs:
                f=fids.get(ref)
                if not f or f['runId']!=a['runId'] or f['actorSubject']!=a['subject'] or op['path'] not in f['paths'] or not f['preparationEvidence'] or not f['postconditions']:
                    raise ValueError('mutation fixture ownership/preparation/poststate mismatch')
    oracle=plan.get('identityStrategy',doc['auth']['identity'])
    if 'identityStrategy' in plan:
        if a.get('provenanceKind')!='private-credential-import/1.0' or receipt.get('identityStrategy')!=oracle or oracle.get('version')!='signed-jwt-protected-probe/1.0' or not receipt.get('jwtTrust'):raise ValueError('signed identity strategy needs bound imported provenance')
        op=ids.get(oracle['operationId'])
        if not op or not op['protected'] or op['method']!='GET':raise ValueError('signed identity probe must be protected GET')
    if plan['identityPath']!=ids[oracle['operationId']]['pathTemplate']:raise ValueError('identity path drift')
    if 'execution' in plan:
        actions=plan['execution']
        if actions['crawl']!=plan['identityPath']:raise ValueError('crawl target drift')
        for action in actions['seeds']+actions['attacks']:
            u=urlsplit(action['path']);path_valid(u.path)
            known=[o for o in plan['operations'] if o['method']==action['method'] and o['path']==u.path]
            if not known or u.netloc or u.scheme or u.fragment:raise ValueError('execution action outside plan')
            inventory=ids[known[0]['operationId']]
            allowed=inventory['input'].get('query',[])
            if any(k not in allowed for k,v in parse_qsl(u.query,keep_blank_values=True)):raise ValueError('undiscovered query parameter')
    return plan


def verify_identity(status,content_type,body,expected_subject,pointer):
    """Used before native prepare; 200 alone cannot establish authentication."""
    if status!=200 or 'application/json' not in content_type.lower():raise ValueError('protected identity response not JSON 200')
    value=body
    try:
        for part in pointer.lstrip('/').split('/'):value=value[part.replace('~1','/').replace('~0','~')]
    except (KeyError,TypeError):raise ValueError('protected identity subject absent') from None
    if str(value)!=str(expected_subject):raise ValueError('wrong protected actor')
    return True


def verify_local_sources(doc):
    """Check pinned local source files before writes; observation artifacts may use URI refs."""
    for source in doc['sources']:
        if source['kind'] not in ('source','deployment'):continue
        location=re.sub(r':\d+(?:-\d+)?$','',source['location'])
        p=Path(location)
        if p.is_absolute() and source['sha256']:
            if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('discovery source changed; rediscovery required')
    return True


def validate_transport(doc,live_binding,proof):
    """proof comes from the caller's independent runtime inspector, not the agent."""
    if proof['targetBinding']!=live_binding or proof['environment']!=doc['product']['environment']:
        raise ValueError('runtime environment/binding mismatch')
    for role,key in [('scanner','scannerOrigins'),('direct','directOrigins')]:
        selected=[o for o in doc['product']['origins'] if o['role']==role and o['authorized'] and o['bindingVerified']]
        if not selected or any(o['url'] not in proof[key] for o in selected):
            raise ValueError('origin not independently bound to selected deployment: '+role)
    return True


def execution_origin(doc,role):
    """Select the first authorized, verified candidate in immutable inventory order.

    The caller must independently validate all candidates before target traffic.
    This keeps alias discovery intact and gives compiler/profile/cleanup one rule.
    """
    candidates=[o['url'] for o in doc['product']['origins'] if o['role']==role and o['authorized'] and o['bindingVerified']]
    if not candidates:raise ValueError('no verified execution origin: '+role)
    return candidates[0]
