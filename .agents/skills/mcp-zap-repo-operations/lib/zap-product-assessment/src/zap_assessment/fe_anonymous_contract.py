"""Finite FE research contract. No product literals, executable document JS or identity reuse."""
import copy
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator

ROOT=Path(__file__).resolve().parents[2]
PROFILE='fe-anonymous-research/1.0'
PLAN='fe-anonymous-research-plan/1.0'
JOURNEYS='fe-anonymous-journeys/1.0'

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def canonical(value):return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def save(root,name,value):
    path=Path(root)/name;path.parent.mkdir(parents=True,exist_ok=True)
    data=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    with path.open('wb') as f:f.write(data)
    path.chmod(0o600)
    return path

def pins():
    files=[*Path(__file__).parent.glob('fe_anonymous_*.py'),*ROOT.joinpath('schemas').glob('fe-anonymous-*.json'),ROOT/'scripts/fe_anonymous_research.py']
    files += [Path(__file__).with_name(n) for n in ('ui_webdriver.py','runtime.py','transport.py','journal.py','evidence.py','anonymous_runner.py','discovery_handoff.py','product_cli.py','product_workflow.py','product_handoff.py','product_scope.py','product_scope_cli.py')]
    files += [ROOT/'profiles/runtime-baseline.json']
    return {str(p):digest(p) for p in sorted(files)}

def sources(doc):
    if not doc.get('sources'):raise ValueError('source provenance absent')
    for s in doc['sources']:
        if digest(s['path'])!=s['sha256']:raise ValueError('source drift: '+s['path'])

def schema(value,name):Draft202012Validator(load(ROOT/'schemas'/name)).validate(value)

def validate_journeys(doc):
    schema(doc,'fe-anonymous-journeys-v1.schema.json');sources(doc)
    ids=[j['id'] for j in doc['journeys']]
    if len(ids)!=len(set(ids)) or not ids:raise ValueError('journey IDs not unique/nonempty')
    obligations=doc['responsibilities'];oids=[o['id'] for o in obligations]
    if len(oids)!=len(set(oids)):raise ValueError('duplicate responsibility')
    known={s['id'] for s in doc['sources']}
    if len(known)!=len(doc['sources']):raise ValueError('duplicate source provenance')
    for o in obligations:
        if not o['provenance'] or not set(o['provenance'])<=known:raise ValueError('responsibility provenance')
        if not set(o['journeyIds'])<=set(ids):raise ValueError('unknown responsibility journey')
        if o['disposition']=='not-applicable' and not o.get('reason'):raise ValueError('N/A reason absent')
    for j in doc['journeys']:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',j['id']):raise ValueError('unsafe journey identifier')
        if not set(j.get('prerequisites',[]))<=set(ids[:ids.index(j['id'])]):raise ValueError('journey prerequisite must precede dependent')
        if not j['provenance'] or not set(j['provenance'])<=known:raise ValueError('journey provenance')
        if not j['steps'] or not j['expected']:raise ValueError('UI oracle absent')
        for step in j['steps']:
            if step['action'] in ('navigate',) and (not step['path'].startswith('/') or step['path'].startswith('//') or '\\' in step['path']):raise ValueError('nonlocal navigation')
            if step['action'] in ('click','fill','submit') and not step.get('selector'):raise ValueError('selector absent')
            if any(k in step for k in ('script','javascript')):raise ValueError('arbitrary JS forbidden')
    for campaign in doc['campaigns']:
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,63}',campaign['id']):raise ValueError('unsafe campaign identifier')
    return doc

def branch_permissions(p,journey=None,campaign=None):
    required={'network','browser','private-research-retention'}
    branch=journey or campaign
    if campaign:required.add('active')
    if branch.get('setupHook'):required.add('public-mutation')
    requests=([{'method':campaign['method'],'path':campaign['path']}] if campaign else [n for n in journey['network'] if not n.get('absent')])
    for request in requests:
        if request['method'] in ('GET','HEAD','OPTIONS'):continue
        policies=[r for r in p['requestPolicies'] if r['method']==request['method'] and re.fullmatch(r['pathRegex'],request['path'])]
        if not policies or not all(r.get('effect')=='public-read-like' and r.get('effectProvenance') for r in policies):required.add('public-mutation')
    return required

def admission(p):
    permissions=set(p['authority'].get('permissions',[]));rows=[]
    for j in p['journeys']['journeys']:
        if j['id'] in p['journeyIds']:
            missing=branch_permissions(p,journey=j)-permissions
            rows.append({'kind':'journey','id':j['id'],'missingPermissions':sorted(missing),'admitted':not missing})
    for c in p['campaigns']:
        missing=branch_permissions(p,campaign=c)-permissions
        rows.append({'kind':'campaign','id':c['id'],'missingPermissions':sorted(missing),'admitted':not missing})
    return rows

def validate_plan(p,*,live=False):
    schema(p,'fe-anonymous-plan-v1.schema.json');validate_journeys(p['journeys']);sources(p['discovery'])
    if p['profile']!=PROFILE or p['track']!='fe-anonymous':raise ValueError('FE profile/track')
    if p['implementationPins']!=pins():raise ValueError('implementation drift')
    if p['discoverySha256']!=canonical(p['discovery']) or p['journeysSha256']!=canonical(p['journeys']):raise ValueError('inventory drift')
    if p['requestPolicies']!=p['journeys']['requestPolicies']:raise ValueError('request policy differs from inventory')
    campaigns={c['id']:c for c in p['journeys']['campaigns']}
    if len(campaigns)!=len(p['journeys']['campaigns']) or len({c['id'] for c in p['campaigns']})!=len(p['campaigns']):raise ValueError('duplicate campaign')
    if any(campaigns.get(c['id'])!=c for c in p['campaigns']):raise ValueError('unreviewed active campaign')
    a=p['authority'];s=p['selection'];u=urlsplit(s['origin'])
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.path or u.query or u.fragment:raise ValueError('canonical HTTPS origin required')
    if s!=p['discovery']['selection']:raise ValueError('selection drift')
    if a.get('scopeOrigin')!='explicit-user-authorization' or not a.get('authorizationRef'):raise ValueError('authority source absent')
    if a.get('productLocation')!=p['discovery']['productLocation'] or a.get('selectionSha256')!=canonical(s) or 'fe-anonymous' not in a.get('tracks',[]):raise ValueError('authority binding mismatch')
    if not {'network','browser','private-research-retention'}<=set(a.get('permissions',[])):raise ValueError('FE base authority permissions absent')
    if not p['journeyIds'] or len(set(p['journeyIds']))!=len(p['journeyIds']) or not set(p['journeyIds'])<=set(j['id'] for j in p['journeys']['journeys']):raise ValueError('unknown/duplicate/empty journey')
    if live and not a['notBefore']<=time.time()<min(a['notAfter'],p['notAfter']):raise ValueError('authority expired')
    for f in ('certificate','jar'):
        if digest(s[f]['path'])!=s[f]['sha256']:raise ValueError(f+' pin drift')
    for row in s['scannerSourcePins']:
        if digest(row['path'])!=row['sha256']:raise ValueError('scanner source drift')
    if not s['scannerSourcePins']:raise ValueError('runtime source pin absent')
    if p['limits']['reserveBytes']<2*1024**3:raise ValueError('reserve weakened')
    calibration=s['resourceCalibration']
    if calibration['observedGrowthBytes']<=0 or calibration['requiredRamBytes']<4*1024**3 or not calibration.get('evidence'):raise ValueError('browser/TLS calibration absent')
    for row in calibration['evidence']:
        if digest(row['path'])!=row['sha256']:raise ValueError('resource calibration drift')
    if any(not re.fullmatch(r'sha256:[a-f0-9]{64}|.+@sha256:[a-f0-9]{64}',v) for v in s['images'].values()):raise ValueError('immutable image pins required')
    for rule in p['requestPolicies']:
        if rule['method'] not in ('GET','HEAD','POST','OPTIONS'):raise ValueError('method unsupported')
        re.compile(rule['pathRegex'])
        if rule.get('anonymousCookies') and not rule.get('cookieProvenance'):raise ValueError('cookie provenance absent')
    return p

def compile_plan(discovery,journeys,selection,authority,run_id):
    validate_journeys(journeys);sources(discovery)
    if discovery['selection']!=selection:raise ValueError('discovery selection mismatch')
    p={'schemaVersion':PLAN,'profile':PROFILE,'track':'fe-anonymous','runId':run_id,'discovery':copy.deepcopy(discovery),'discoverySha256':canonical(discovery),
       'journeys':copy.deepcopy(journeys),'journeysSha256':canonical(journeys),'selection':copy.deepcopy(selection),'authority':copy.deepcopy(authority),
       'journeyIds':[j['id'] for j in journeys['journeys']],'requestPolicies':journeys['requestPolicies'],'campaigns':journeys['campaigns'],
       'implementationPins':pins(),'notAfter':min(authority['notAfter'],time.time()+7200),
       'limits':{'reserveBytes':2*1024**3,'artifactBytes':128*1024**2,'executionSeconds':1800,'maxRequests':600,'requestsPerSecond':2,'stopSeconds':60,'maxBodyBytes':2*1024**2},
       'retention':{'raw':'private-local; retain evidence; exact owned containers/profiles disposable after capture','fixtures':'retain acknowledged public registrations where no API delete exists'},
       'stopPolicy':'latch on identity outside transition, binding/source/resource breach; pending starts reconcile only, never replay'}
    return validate_plan(p,live=True)
