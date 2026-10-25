from __future__ import annotations
import copy
import hashlib
import ipaddress
import json
import socket
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
from .errors import Blocked

def canonical(value): return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
def digest(value): return hashlib.sha256(canonical(value)).hexdigest()
def utcnow(): return datetime.now(timezone.utc)
def validate(kind,value,*,schema_version=None):
    version=schema_version if schema_version is not None else value.get('schemaVersion','1.0') if isinstance(value,dict) else '1.0'
    directories={'1.0':'','1.1':'v1.1','1.2':'v1.2','1.3':'v1.3','1.4':'v1.4','2.0':'v2.0'}
    if not isinstance(version,str) or version not in directories: raise Blocked('unsupported schema version')
    base=ROOT/'schemas'/directories[version]
    if version=='2.0':
        definitions=json.loads((base/'bundle.schema.json').read_text())['$defs']
        if kind not in definitions: raise Blocked('unsupported v2 contract kind')
        schema={'$defs':definitions,'$ref':'#/$defs/'+kind}
    else:
        path=base/f'{kind}.schema.json'
        if not path.is_file(): raise Blocked('unsupported contract kind for version')
        schema=json.loads(path.read_text())
    errors=list(Draft202012Validator(schema,format_checker=FormatChecker()).iter_errors(value))
    if errors: raise Blocked(f'{kind}: invalid field at '+'.'.join(map(str,errors[0].absolute_path)))

def origin(url,exact=False):
    if not isinstance(url,str) or any(c.isspace() or ord(c)<32 for c in url) or '\\' in url: raise Blocked('ambiguous URL')
    try:
        u=urlsplit(url)
        if u.scheme not in ('http','https') or not u.hostname or u.username or u.password or u.fragment: raise Blocked('invalid URL')
        host=u.hostname
        if '%' in host or host.endswith('.') or host!=host.lower() or host.encode('idna').decode()!=host: raise Blocked('ambiguous host')
        try: ip=ipaddress.ip_address(host); host=f'[{ip.compressed}]' if ip.version==6 else str(ip)
        except ValueError:
            if all(c.isdigit() or c=='.' for c in host) or host.startswith('0x'): raise Blocked('ambiguous IP')
        port=u.port or (443 if u.scheme=='https' else 80)
        o=f'{u.scheme}://{host}'+(f':{port}' if port!=(443 if u.scheme=='https' else 80) else '')
        if exact and url!=o: raise Blocked('origin must be canonical, without path')
        return o
    except (ValueError,UnicodeError) as e: raise Blocked('invalid URL') from e

class Scope:
    def __init__(self,origins,addresses,resolver=None):
        self.origins=frozenset(origin(x,True) for x in origins)
        self.addresses=frozenset(str(ipaddress.ip_address(x)) for x in addresses)
        self.resolver=resolver or (lambda host: {r[4][0] for r in socket.getaddrinfo(host,None,type=socket.SOCK_STREAM)})
    def check(self,url):
        if origin(url) not in self.origins: raise Blocked('outside attack scope')
        host=urlsplit(url).hostname
        try: found={str(ipaddress.ip_address(host))}
        except ValueError: found={str(ipaddress.ip_address(x)) for x in self.resolver(host)}
        if not found or not found<=self.addresses: raise Blocked('DNS outside pinned address set')
        return found

@dataclass(frozen=True)
class Plan:
    encoded: bytes
    @property
    def data(self): return json.loads(self.encoded)
    @property
    def hash(self): return hashlib.sha256(self.encoded).hexdigest()

class AuthorityRegistry:
    """Operator-provided records; product profiles cannot create their own authority."""
    def __init__(self,records): self.records=copy.deepcopy(records)
    def get(self,ref):
        if ref not in self.records: raise Blocked('missing authorization record')
        record=self.records[ref]; validate('authorization',record); return copy.deepcopy(record)

def check_authority(a,p,w,now=None):
    now=now or utcnow()
    if not datetime.fromisoformat(a['validFrom'].replace('Z','+00:00'))<=now<datetime.fromisoformat(a['validUntil'].replace('Z','+00:00')): raise Blocked('authority expired or not yet valid')
    if a['recordId']!=p['authorizationRef']: raise Blocked('authority reference mismatch')
    if (a['productId'],a['environmentIdentity'])!=(p['productId'],p['environment']['identity']): raise Blocked('environment identity mismatch')
    if p['environment']['kind']=='production': raise Blocked('production refused')
    if not set(p['attackOrigins'])<=set(a['attackOrigins']): raise Blocked('authority scope mismatch')
    if not set(w['operations'])<=set(a['operations']): raise Blocked('operations not authorized')
    if w['destructiveLevel']!=a['destructiveLevel']: raise Blocked('destructive level mismatch')
    if w['budgets']['total']>a['maxRuntimeSeconds'] or w['maxRate']>a['maxRate']: raise Blocked('authority budget exceeded')
    # V1 ships only the namespace-contained fixture adapter. A staging label never enables it.
    if p['schemaVersion']=='1.0' and (p['environment']['kind']!='synthetic' or a['issuer']!='isolated-fixture-harness' or not a['approvalRef'].startswith('user-authorized-synthetic:')): raise Blocked('product runtime not verified; fixture authority required')

def openapi_validate(doc,p):
    if not isinstance(doc,dict) or not str(doc.get('openapi','')).startswith('3.0.'): raise Blocked('only self-contained OpenAPI 3.0 JSON')
    def walk(v):
        if isinstance(v,dict):
            for k,x in v.items():
                if k in ('callbacks','webhooks','links'): raise Blocked('unsupported schema operation extension')
                if k=='$ref' and (not isinstance(x,str) or not x.startswith('#/')): raise Blocked('external schema reference')
                if k=='servers':
                    if not isinstance(x,list) or any(not isinstance(t,dict) or origin(t.get('url',''),True) not in p['attackOrigins'] for t in x): raise Blocked('schema server outside scope')
                walk(x)
        elif isinstance(v,list):
            for x in v: walk(x)
    walk(doc)
    paths=doc.get('paths',{})
    expected={(x['method'].lower(),x['path']) for x in p['expectedOperations']}
    observed=set()
    for path,definition in paths.items():
        if not isinstance(definition,dict): raise Blocked('invalid OpenAPI path')
        for method in definition:
            if method in ('get','post','put','delete','patch','head','options','trace'):
                if (method,path) not in expected: raise Blocked('unapproved schema operation')
                observed.add((method,path))
    if observed!=expected: raise Blocked('schema coverage contract mismatch')

def w4_active_fixture(p,w):
    # Development-only admission. Registered product adapters still reject it.
    return (w.get('active') is True and w.get('workflowId')=='w4-owned-active-conformance' and p.get('schemaVersion')=='1.0'
            and p.get('adapter')=='synthetic-http-v1' and p.get('environment',{}).get('kind')=='synthetic'
            and p.get('attackOrigins')==['http://127.0.0.1:18080'] and not p.get('dependencyOrigins')
            and p.get('crawlPath')=='/api/echo?q=baseline' and w.get('authMode')=='none')

def make_plan(product,workflow,registry,schema_bytes,now=None):
    validate('product',product); validate('workflow',workflow)
    p=copy.deepcopy(product); w=copy.deepcopy(workflow)
    for o in p['attackOrigins']+p['dependencyOrigins']: origin(o,True)
    if len(p['attackOrigins'])!=1 or p['dependencyOrigins']: raise Blocked('V1 one origin; browser dependencies unsupported')
    if set(w['operations'])!=({'health','seed','crawl','import'}|({'active'} if w['active'] else set())): raise Blocked('inconsistent operations')
    if w['active'] and not w4_active_fixture(p,w): raise Blocked('active runtime unverified; required V1 is exploratory only')
    if (w.get('workflowId')=='w4-owned-active-conformance' or p.get('crawlPath')=='/api/echo?q=baseline') and not w4_active_fixture(p,w):raise Blocked('W4 development fixture scope mismatch')
    if len(schema_bytes)>1048576 or hashlib.sha256(schema_bytes).hexdigest()!=p['schema']['sha256']: raise Blocked('schema size/hash mismatch')
    try: schema=json.loads(schema_bytes)
    except (ValueError,UnicodeError) as e: raise Blocked('invalid schema JSON') from e
    openapi_validate(schema,p)
    a=registry.get(p['authorizationRef']); check_authority(a,p,w,now)
    # Planning performs no DNS/network; actual send paths and kernel boundary enforce egress.
    if p['schemaVersion']=='1.1':
        from .binding import validate_binding,guard_values
        validate_binding(p,w,a)
        if canonical(schema)!=schema_bytes: raise Blocked('content schema must use canonical JSON encoding')
        payload={'runtime':json.loads((ROOT/'profiles/runtime-baseline.json').read_text()),'schemaVersion':'1.1','product':p,'workflow':w,'authority':a,'authorizationHash':digest(a),'profileHash':digest(p),'workflowHash':digest(w),'schema':schema,'schemaHash':p['schema']['sha256'],'effectiveEgress':p['attackOrigins'],'capabilities':['http-crawl','openapi-json','report-chunks'],'limitations':['anonymous public/API only','seed coverage is not active-rule coverage','session exclusive until report export','MCP summary scoped to crawlPath; full findings source is report.json','HTTP image/container metadata identity; no TLS or cryptographic application build attestation'],'guard':guard_values(p,w,a)}
        return Plan(canonical(payload))
    for o in p['attackOrigins']:
        try: ip=ipaddress.ip_address(urlsplit(o).hostname)
        except ValueError as e: raise Blocked('V1 runtime requires pinned literal IP') from e
        if str(ip) not in a['resolvedAddresses'] or not ip.is_loopback: raise Blocked('V1 requires isolated loopback target')
        if urlsplit(o).port!=18080: raise Blocked('fixture namespace target port required')
    for seed in p['publicSeeds']:
        if seed not in {x['path'] for x in p['expectedOperations']}: raise Blocked('seed outside approved operations')
    payload={'runtime':json.loads((ROOT/'profiles'/'runtime-baseline.json').read_text()),'schemaVersion':'1.0','product':p,'workflow':w,'authority':a,'authorizationHash':digest(a),'profileHash':digest(p),'workflowHash':digest(w),'schema':schema,'schemaHash':p['schema']['sha256'],'effectiveEgress':p['attackOrigins'],'capabilities':['http-crawl','openapi-json','report-chunks'],'limitations':['anonymous public/API only','seed coverage is not active-rule coverage','session exclusive until report export']}
    return Plan(canonical(payload))


def validate_locked_plan(plan):
    d=plan.data; validate('normalized-plan',d)
    if d['runtime']!=json.loads((ROOT/'profiles'/'runtime-baseline.json').read_text()): raise Blocked('runtime registry drift')
    if canonical(d)!=plan.encoded: raise Blocked('plan must use canonical encoding')
    p=d['product']; w=d['workflow']; a=d['authority']
    check_authority(a,p,w)
    if digest(p)!=d['profileHash'] or digest(w)!=d['workflowHash'] or digest(a)!=d['authorizationHash'] or p['schema']['sha256']!=d['schemaHash']: raise Blocked('locked plan reference/hash mismatch')
    if d['effectiveEgress']!=p['attackOrigins']: raise Blocked('locked plan scope mismatch')
    openapi_validate(d['schema'],p)
    if set(w['operations'])!=({'health','seed','crawl','import'}|({'active'} if w['active'] else set())): raise Blocked('locked plan operations mismatch')
    if w['active'] and not w4_active_fixture(p,w): raise Blocked('active runtime unverified; required V1 is exploratory only')
    if (w.get('workflowId')=='w4-owned-active-conformance' or p.get('crawlPath')=='/api/echo?q=baseline') and not w4_active_fixture(p,w):raise Blocked('W4 development fixture scope mismatch')
    if p['schemaVersion']=='1.1':
        from .binding import validate_binding,guard_values
        validate_binding(p,w,a)
        if digest(d['schema'])!=d['schemaHash']: raise Blocked('content schema digest mismatch')
        if d['guard']!=guard_values(p,w,a): raise Blocked('guard differs from immutable plan')
    elif p['attackOrigins']!=['http://127.0.0.1:18080'] or p['dependencyOrigins'] or a['resolvedAddresses']!=['127.0.0.1']: raise Blocked('fixture runtime scope mismatch')
    for seed in p['publicSeeds']:
        if seed not in {x['path'] for x in p['expectedOperations']}: raise Blocked('unapproved seed')
