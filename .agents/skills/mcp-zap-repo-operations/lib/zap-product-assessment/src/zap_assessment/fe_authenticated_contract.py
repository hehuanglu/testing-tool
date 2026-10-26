"""Finite authenticated research contract; no product-specific routes or selectors."""
import copy,re,time
from pathlib import Path
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator
from .fe_anonymous_contract import digest,canonical,load,save,sources,ROOT
PROFILE='fe-authenticated-research/1.0'
PLAN='fe-authenticated-research-plan/1.0'
JOURNEYS='fe-authenticated-journeys/1.0'
ACTIONS=('navigate','fill','click','submit','wait','reload','select','check','uncheck','back','forward','new-tab','identity-probe','logout-boundary','reopen','readback','post-state')
PREDICATES=('exists','absent','text','urlPath','invalid','disabled','attribute','storagePresent','storageAbsent','valueLength','ready','checked','count','textAbsent','imageLoaded')

def pins():
    paths=list(Path(__file__).parent.glob('fe_authenticated_*.py'))+list(Path(__file__).parent.glob('fe_anonymous_*.py'))
    paths += [Path(__file__).with_name(n) for n in ('ui_webdriver.py','runtime.py','transport.py','journal.py','evidence.py','anonymous_runner.py','product_cli.py','product_workflow.py','product_handoff.py','discovery_handoff.py','product_scope.py','product_scope_cli.py','executor_routing.py')]
    paths += list((ROOT/'schemas').glob('fe-authenticated-*.json'))+[ROOT/'scripts/fe_authenticated_research.py',ROOT/'profiles/runtime-baseline.json']
    return {str(p):digest(p) for p in sorted(paths) if p.exists()}

def identifier(value):
    if not isinstance(value,str) or not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',value):raise ValueError('unsafe identifier')

def local_path(value):
    if not isinstance(value,str) or not value.startswith('/') or value.startswith('//') or any(c in value for c in ('\\','\r','\n','#')):raise ValueError('nonlocal path')
    if len(value)>2048:raise ValueError('path budget')

def predicate(p):
    if p.get('kind') not in PREDICATES or set(p)-{'kind','selector','value','attribute','key','area','seconds','fixtureField'}:raise ValueError('unsupported finite predicate')
    if p.get('selector') and (len(p['selector'])>512 or '\x00' in p['selector']):raise ValueError('selector budget')
    if p.get('seconds',6)>12:raise ValueError('predicate deadline')

def validate_journeys(d):
    Draft202012Validator(load(ROOT/'schemas/fe-authenticated-journeys-v1.schema.json')).validate(d);sources(d)
    from .fe_authenticated_recipes import select
    select(d['recipe'])
    js=d['journeys'];ids=[j['id'] for j in js];rs=d['responsibilities'];rids=[r['id'] for r in rs];ss={s['id'] for s in d['sources']}
    if not ids or len(set(ids))!=len(ids) or len(set(rids))!=len(rids) or len(ss)!=len(d['sources']):raise ValueError('duplicate/empty inventory')
    for r in rs:
        identifier(r['id'])
        if not r['provenance'] or not set(r['provenance'])<=ss:raise ValueError('responsibility provenance')
        if not set(r['journeyIds'])<=set(ids):raise ValueError('unknown responsibility journey')
        if r['disposition'] in ('not-applicable','gap') and not r.get('reason'):raise ValueError('disposition reason absent')
    groups={g['id']:g for g in d['sessionGroups']}
    if len(groups)!=len(d['sessionGroups']):raise ValueError('duplicate session group')
    for g in groups.values():
        identifier(g['id']);identifier(g['actorRef'])
    for i,j in enumerate(js):
        identifier(j['id'])
        if j['sessionGroup'] not in groups or j['actorRef'] not in groups[j['sessionGroup']].get('actorRefs',[groups[j['sessionGroup']]['actorRef']]):raise ValueError('session actor mismatch')
        if not j['provenance'] or not set(j['provenance'])<=ss or not set(j['responsibilityIds'])<=set(rids):raise ValueError('journey provenance/responsibility')
        if not set(j['prerequisites'])<=set(ids[:i]):raise ValueError('prerequisite order')
        if not j['steps'] or not j['expectedUi']:raise ValueError('UI evidence obligation absent')
        for s in j['steps']:
            if s['action'] not in ACTIONS:raise ValueError('unsupported action')
            if s['action'] in ('navigate','new-tab','reopen','readback','post-state'):local_path(s['path'])
            if s['action'] in ('fill','click','submit','select','check','uncheck') and not s.get('selector'):raise ValueError('selector absent')
            if s['action']=='post-state' and (not s.get('pointer') or ('expectedValue' in s)==bool(s.get('expectedFixture'))):raise ValueError('finite post-state oracle absent/ambiguous')
            if s['action']=='readback':
                if not {'pointer','valuePointer','fixtureField'}<=s.keys() or s['fixtureField'] in ('username','password'):raise ValueError('bounded readback binding absent/unsafe')
                if bool(s.get('matchPointer'))!=bool(s.get('matchFixture')):raise ValueError('readback match pair incomplete')
            if s.get('predicate'):predicate(s['predicate'])
        for p in j['expectedUi']:predicate(p)
        for n in j['expectedNetwork']:local_path(n['path'])
        if j['effect']=='mutation' and not j['postState']:raise ValueError('mutation post-state absent')
    for c in d['campaigns']:
        identifier(c['id']);local_path(c['path'])
        if c['authKind'] not in ('json-bearer','form'):raise ValueError('browser handle cannot active scan')
        if not set(c['journeyIds'])<=set(ids) or not c['journeyIds']:raise ValueError('campaign UI provenance absent')
        if c['vector'] not in ('query','json-body') or not c['vectorFields'] or c['maxDelivered']<1 or c['maxAppRequests']<c['maxDelivered']:raise ValueError('campaign budget/vector')
    for r in d['requestPolicies']:
        if r['method'] not in ('GET','HEAD','OPTIONS','POST','PUT','PATCH','DELETE'):raise ValueError('method unsupported')
        local_path(r['path'])
        if r.get('jsonSchema'):
            from .executor_routing import contract
            contract(r['jsonSchema'])  # no network/external schema resolution
            Draft202012Validator.check_schema(r['jsonSchema'])
            if r.get('jsonFields'):raise ValueError('ambiguous JSON shape contract')
        if any(x in r for x in ('pathRegex','script','javascript')):raise ValueError('exact path or finite segments required')
    a=d['auth'];local_path(a['loginPath']);local_path(a['identity']['path'])
    if a['kind']!='json-bearer':raise ValueError('auth kind not qualified by this adapter; retain dependency')
    if not a['identity'].get('subjectPointer') or not a['identity'].get('roleProvenance'):raise ValueError('independent identity contract absent')
    return d

def admission(p):
    permissions=set(p['authority']['permissions']);rows=[]
    for kind,items in [('journey',p['journeys']['journeys']),('campaign',p['campaigns'])]:
        for j in items:
            required={'network','browser','private-research-retention'}
            if kind=='campaign':required|={'active'}
            if j.get('effect')=='mutation' or kind=='campaign' and j['method'] not in ('GET','HEAD','OPTIONS'):required.add('owned-mutation')
            if j.get('setupRefs'):required.add('fixture-setup')
            required.update(j.get('setupPermissions',[]))
            missing=sorted(required-permissions);rows.append({'kind':kind,'id':j['id'],'admitted':not missing,'missingPermissions':missing,'dependencies':j.get('prerequisites',[])})
    return rows

def validate_plan(p,live=False):
    Draft202012Validator(load(ROOT/'schemas/fe-authenticated-plan-v1.schema.json')).validate(p)
    if (p['schemaVersion'],p['profile'],p['track'])!=(PLAN,PROFILE,'fe-authenticated'):raise ValueError('track/profile mismatch')
    validate_journeys(p['journeys']);sources(p['discovery'])
    if p['implementationPins']!=pins():raise ValueError('implementation drift')
    if canonical(p['discovery'])!=p['discoverySha256'] or canonical(p['journeys'])!=p['journeysSha256']:raise ValueError('inventory drift')
    from .fe_authenticated_recipes import materialize
    if p['discovery']['recipe']!=p['journeys']['recipe'] or materialize(p['discovery']['journeys'],p['selection'])!=p['journeys']:raise ValueError('recipe/workload differs from reviewed discovery')
    s=p['selection'];u=urlsplit(s['origin']);a=p['authority']
    if p.get('ownedControlFault') and (a.get('controlScope')!='owned-fe-auth-control' or not s['environment'].startswith('fa-control-') or p['journeys']['recipe']!='reviewed-fe-auth/1.0'):raise ValueError('qualification fault outside owned control')
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment:raise ValueError('canonical HTTPS origin required')
    if s!=p['discovery']['selection'] or a['selectionSha256']!=canonical(s) or a['productLocation']!=p['discovery']['productLocation']:raise ValueError('product/deployment authority mismatch')
    if a['scopeOrigin']!='explicit-user-authorization' or not a['authorizationRef'] or a['profile']!=PROFILE or 'fe-authenticated' not in a['tracks']:raise ValueError('authority/profile source absent')
    if a['rawRetention']!='local-private' or not {'network','browser','private-research-retention'}<=set(a['permissions']):raise ValueError('research retention/base permission absent')
    identifier(p['runId'])
    if live and not a['notBefore']<=time.time()<min(a['notAfter'],p['notAfter']):raise ValueError('authority expired')
    if p['requestPolicies']!=p['journeys']['requestPolicies'] or p['campaigns']!=p['journeys']['campaigns']:raise ValueError('policy/campaign drift')
    if p['journeyIds']!=[j['id'] for j in p['journeys']['journeys']]:raise ValueError('inventory omission')
    for f in ('certificate','jar'):
        if digest(s[f]['path'])!=s[f]['sha256']:raise ValueError('artifact pin drift')
    for row in s['scannerSourcePins']:
        if digest(row['path'])!=row['sha256']:raise ValueError('scanner source drift')
    if not s['scannerSourcePins']:raise ValueError('scanner source absent')
    if p['limits']['reserveBytes']<2*1024**3:raise ValueError('reserve weakened')
    c=s['resourceCalibration']
    if c['observedGrowthBytes']<=0 or c['requiredRamBytes']<4*1024**3 or not c['evidence']:raise ValueError('browser TLS auth calibration absent')
    for row in c['evidence']:
        if digest(row['path'])!=row['sha256']:raise ValueError('calibration drift')
    if any(not re.fullmatch(r'sha256:[a-f0-9]{64}|.+@sha256:[a-f0-9]{64}',v) for v in s['images'].values()):raise ValueError('immutable image pin required')
    return p

def compile_plan(d,j,s,a,run_id):
    validate_journeys(j);sources(d)
    if j!=d['journeys']:raise ValueError('workload must preserve reviewed source inventory')
    from .fe_authenticated_recipes import materialize
    j=materialize(j,s)
    p={'schemaVersion':PLAN,'profile':PROFILE,'track':'fe-authenticated','runId':run_id,'discovery':copy.deepcopy(d),'discoverySha256':canonical(d),'journeys':copy.deepcopy(j),'journeysSha256':canonical(j),'selection':copy.deepcopy(s),'authority':copy.deepcopy(a),'journeyIds':[x['id'] for x in j['journeys']],'requestPolicies':j['requestPolicies'],'campaigns':j['campaigns'],'implementationPins':pins(),'notAfter':min(a['notAfter'],time.time()+7200),'limits':{'reserveBytes':2*1024**3,'artifactBytes':256*1024**2,'maxRequests':1200,'requestsPerSecond':3,'executionSeconds':2400,'stopSeconds':60,'maxBodyBytes':2*1024**2,'maxLoginsPerActor':j['auth']['maxLoginsPerActor'],'identityMaxGapSeconds':30},'retention':{'raw':'local-private','fixtures':'exact owned ledger; retention where cleanup unsupported'},'stopPolicy':'latch dependent producer; stop/export/reconcile only; never replay unknown mutation/start'}
    return validate_plan(p,live=True)
