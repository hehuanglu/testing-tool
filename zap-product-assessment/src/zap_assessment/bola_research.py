"""Policy-aware direct BOLA research. Legacy v1.4 and W6 are unchanged.

The core knows actors/resources/requests, never product routes or field names.
Saved observations are minimized client evidence, not wire/platform attestation.
"""
from __future__ import annotations
import copy
import hashlib
import http.client
import ipaddress
import json
import os
from pathlib import Path
import re
import signal
import ssl
import time
from types import MappingProxyType
from urllib.parse import urlsplit, parse_qsl, urlencode, unquote
from .discovery import (canonical_hash, validate_discovery, verify_local_sources,
    execution_origin, path_valid, matches, verify_identity, origin, secret_check)
from .bola_http import exchange, decode
from .journal import Journal
from .safety_io import atomic_bytes
from .discovery_handoff import clean

VERSION='bola-research/1.0'
LIMITS={'maxRequests':500,'requestsPerSecond':2,'executionSeconds':900,
        'requestTimeoutSeconds':5,'requestBytes':16384,'artifactBytes':33554432,
        'reserveBytes':2147483648}
PERMISSIONS=('setup','read','mutation','poststate','cleanup','login')


def save(root,name,value):
    root=Path(root);p=root/name
    if not p.resolve().is_relative_to(root.resolve()):raise ValueError('evidence path outside owned directory')
    if p.is_symlink() or any((root/q).is_symlink() for q in p.relative_to(root).parents):raise ValueError('symlink evidence path')
    p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    data=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n').encode()
    atomic_bytes(p,data)
    return p


def load(root,name):return decode((Path(root)/name).read_bytes())
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def implementation_pin():
    root=Path(__file__).parent
    files=[*root.glob('bola_research*.py'),root/'bola_http.py',root/'discovery.py',
           root/'journal.py',root/'safety_io.py',root/'discovery_handoff.py',root/'research_product.py',
           root/'anonymous_product.py',root/'business.py',root/'contracts.py']
    return {p.name:sha(p) for p in sorted(files)}


def pointer(value,path):
    for key in path.strip('/').split('/') if path else []:
        value=value[int(key)] if isinstance(value,list) else value[key.replace('~1','/').replace('~0','~')]
    return value


def sanitized(value,secrets=()):
    """Structural secret removal plus exact in-memory credential canaries everywhere."""
    if isinstance(value,dict):
        return {sanitized(k,secrets):('[private]' if re.search(r'(?i)password|token|cookie|authorization|secret|account_number_full|email',k)
                   else sanitized(v,secrets)) for k,v in value.items()}
    if isinstance(value,list):return [sanitized(v,secrets) for v in value]
    if isinstance(value,str):
        for s in sorted(set(secrets),key=len,reverse=True):
            if s:value=value.replace(s,'[private]')
        return clean(value)
    return value


def project_response(value,fields,secrets):
    """A closed adapter field set; unknown values never enter shared evidence.

    Omissions force an inconclusive control, so a new error/disclosure shape
    cannot silently turn into a clean denial after minimizing its content.
    """
    complete=True
    def project(v):
        nonlocal complete
        if isinstance(v,dict):
            result={}
            for key,item in v.items():
                if key not in fields:complete=False;continue
                result[key]=project(item)
            return result
        if isinstance(v,list):return [project(x) for x in v]
        return v
    return sanitized(project(value),secrets),complete


def check_path(path):
    u=urlsplit(path);path_valid(u.path)
    if u.scheme or u.netloc or u.fragment or re.search(r'%[0-9a-fA-F]{2}',u.path) or unquote(u.path)!=u.path:
        raise ValueError('encoded/foreign/unresolved path')
    if '{' in path or '}' in path or '\\' in path:raise ValueError('unresolved request')
    if len(parse_qsl(u.query,keep_blank_values=True))!=len({k for k,v in parse_qsl(u.query,keep_blank_values=True)}):raise ValueError('duplicate query')
    return u


def validate_request(doc,request):
    u=check_path(request['path'])
    candidates=[o for o in doc['operations'] if o['id']==request['operationRef'] and o['method']==request['method'] and matches(o['pathTemplate'],u.path)]
    if len(candidates)!=1:raise ValueError('request outside discovered operation')
    op=candidates[0]
    if any(k not in op['input'].get('query',[]) for k,v in parse_qsl(u.query,keep_blank_values=True)):raise ValueError('query outside inventory')
    if len(json.dumps(request.get('body'),allow_nan=False).encode())>LIMITS['requestBytes']:raise ValueError('request byte budget')
    if set(request)!={'operationRef','method','path','body'}:raise ValueError('request fields/headers forbidden')
    return op


def render(operation,resource):
    """Only declared ID slots may substitute; all other request bytes are frozen."""
    req=copy.deepcopy(operation['request']);wire=resource['wireId']
    for slot in operation['idLocations']:
        if slot['location']=='path':
            marker='{'+slot['name']+'}'
            if req['path'].count(marker)!=1:raise ValueError('missing reference slot')
            req['path']=req['path'].replace(marker,str(wire))
        elif slot['location']=='query':
            u=urlsplit(req['path']);q=dict(parse_qsl(u.query,keep_blank_values=True));q[slot['name']]=str(wire)
            req['path']=u.path+'?'+urlencode(q)
        elif slot['location']=='body':
            keys=slot['pointer'].strip('/').split('/');v=req['body']
            for key in keys[:-1]:v=v[key]
            if keys[-1] not in v:raise ValueError('missing body slot')
            v[keys[-1]]=wire
        else:raise ValueError('unsupported ID location')
    return req


def direct_binding(doc,binding,proof):
    if doc['product']['binding']!=binding or proof['targetBinding']!=binding or proof['environment']!=doc['product']['environment']:
        raise ValueError('target binding drift')
    selected=[o['url'] for o in doc['product']['origins'] if o['role']=='direct' and o['authorized'] and o['bindingVerified']]
    if not selected or any(o not in proof.get('directOrigins',[]) for o in selected):raise ValueError('direct origin not independently bound')
    for o in selected:
        u=urlsplit(origin(o))
        if u.hostname!='localhost' and not ipaddress.IPv4Address(u.hostname).is_loopback:raise ValueError('research direct transport supports verified local IPv4/localhost only')
    return execution_origin(doc,'direct')


def validate_inventory(doc,inv,*,source=True):
    validate_discovery(doc)
    if source:verify_local_sources(doc)
    if any(c['blocking'] for c in doc['conflicts']):raise ValueError('discovery conflict')
    if inv['discoverySha256']!=canonical_hash(doc):raise ValueError('inventory drift')
    refs={s['id'] for s in doc['sources']};known={o['id']:o for o in doc['operations']}
    ops={o['operationRef']:o for o in inv['operations']}
    if len(ops)!=len(inv['operations']) or set(ops)!=set(known):raise ValueError('every operation requires disposition')
    from .bola_research_branches import validate as validate_branches
    validate_branches(inv,refs)
    policies={p['id']:p for p in inv['policies']}
    for p in policies.values():
        if not p['evidenceRefs'] or not set(p['evidenceRefs'])<=refs or p['relation'] not in ('owner-only','shared-read'):raise ValueError('policy authority missing')
    for op in ops.values():
        if op['disposition'] not in ('candidate','blocked','unsupported','not-applicable','not-run') or not op['reason']:raise ValueError('disposition missing')
        if not op['evidenceRefs'] or not set(op['evidenceRefs'])<=refs:raise ValueError('operation provenance missing')
        if op['disposition']=='candidate':
            if op['policyRef'] not in policies or not op['objectType']:raise ValueError('ownership policy missing')
            req=op['request']
            if req['operationRef']!=op['operationRef'] or req['method']!=known[op['operationRef']]['method']:raise ValueError('operation mapping drift')
            path_valid(urlsplit(req['path']).path,True)
            if op['kind'] not in ('detail','collection','update','delete','reference'):raise ValueError('unsupported case kind')
            if op['kind'] in ('detail','update','delete','reference') and not op['idLocations']:raise ValueError('reference locations missing')
    return inv


def compile_plan(doc,inventory,actors,resources,authority,binding,proof,run_id,controls):
    validate_inventory(doc,inventory)
    p={'schemaVersion':VERSION,'runId':run_id,'lockedAt':time.time(),'notAfter':time.time()+LIMITS['executionSeconds'],
       'origin':direct_binding(doc,binding,proof),'targetBinding':copy.deepcopy(binding),'transportBinding':copy.deepcopy(proof),
       'discovery':copy.deepcopy(doc),'inventory':copy.deepcopy(inventory),'actors':copy.deepcopy(actors),
       'resources':copy.deepcopy(resources),'authority':copy.deepcopy(authority),'positiveControls':copy.deepcopy(controls),
       'implementationPins':implementation_pin(),'limits':dict(LIMITS),'cases':[]}
    identity_op=next(o for o in doc['operations'] if o['id']==doc['auth']['identity']['operationId'])
    p['identity']={'request':{'operationRef':identity_op['id'],'method':'GET','path':identity_op['pathTemplate'],'body':None},
                   'subjectPointer':doc['auth']['identity']['subjectPointer']}
    for op in inventory['operations']:
        if op['disposition']!='candidate':continue
        for r in resources:
            if r['objectType']!=op['objectType'] or r.get('role')!='target':continue
            for actor in ('A','B','anonymous'):
                if op['kind'] in ('update','delete','reference') and actor==r['owner']:continue # dedicated positives precede target creation
                relation='owner' if actor==r['owner'] else 'shared' if actor in r.get('sharedWith',[]) and op['kind'] in ('detail','collection') else 'nonowner'
                c={'id':op['operationRef']+'--'+r['id']+'--'+actor,'operationRef':op['operationRef'],
                   'actorRef':actor,'resourceRef':r['id'],'ownerRef':r['owner'],'relation':relation,
                   'expectedAccess':'allow' if relation in ('owner','shared') else 'deny',
                   'policyRef':op['policyRef'],'authorityRef':'authority','request':render(op,r),
                   'controlCaseRefs':['identity-before','owner-before','anonymous','owner-after','identity-after'],
                   'evidenceRequirements':['identity-before','owner-before','attempt','owner-after','identity-after'],
                   'budget':{'maxAttempt':1,'retry':False}}
                p['cases'].append(c)
    p['inventorySha256']=canonical_hash(inventory);p['discoverySha256']=canonical_hash(doc)
    validate_plan(p,binding,proof)
    return p


def validate_plan(p,binding,proof,*,now=None,source=True):
    if p['schemaVersion']!=VERSION:raise ValueError('BOLA plan version')
    validate_inventory(p['discovery'],p['inventory'],source=source)
    if canonical_hash(p['discovery'])!=p['discoverySha256'] or canonical_hash(p['inventory'])!=p['inventorySha256']:raise ValueError('freeze drift')
    if direct_binding(p['discovery'],binding,proof)!=p['origin'] or p['targetBinding']!=binding:raise ValueError('origin selection drift')
    if p['limits']!=LIMITS:raise ValueError('finite research limits changed')
    now=time.time() if now is None else now
    if not p['lockedAt']<=now+1 or p['notAfter']<=now or p['notAfter']>p['lockedAt']+LIMITS['executionSeconds']+1:raise ValueError('execution deadline')
    if set(p['authority'].get('permissions',[]))!=set(PERMISSIONS) or not p['authority']['source'] or p['authority']['environment']!=p['discovery']['product']['environment']:raise ValueError('explicit permission receipt required')
    actors=p['actors'];resources={r['id']:r for r in p['resources']};ops={o['operationRef']:o for o in p['inventory']['operations']}
    identity=p['discovery']['auth']['identity'];identity_op=next(o for o in p['discovery']['operations'] if o['id']==identity['operationId'])
    if p['identity']!={'request':{'operationRef':identity_op['id'],'method':'GET','path':identity_op['pathTemplate'],'body':None},'subjectPointer':identity['subjectPointer']} or not identity_op['protected']:raise ValueError('protected identity mapping drift')
    if set(actors)!= {'A','B'} or str(actors['A']['subject'])==str(actors['B']['subject']):raise ValueError('independent actors required')
    if actors['A']['credentialRef']==actors['B']['credentialRef']:raise ValueError('separate credential slots required')
    if len(resources)!=len(p['resources']):raise ValueError('duplicate fixture')
    for r in resources.values():
        if r['runId']!=p['runId'] or r['owner'] not in actors or not r['preparationEvidence'] or r['createdByRun'] is not True or not r['cleanup']:
            raise ValueError('fixture ownership/provenance missing')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',str(r['wireId'])):raise ValueError('invalid fixture ID')
        validate_request(p['discovery'],r['readRequest'])
        for req in r.get('relatedRequests',[]):validate_request(p['discovery'],req)
    ids=set()
    for c in p['cases']:
        if c['id'] in ids:raise ValueError('duplicate case')
        ids.add(c['id']);r=resources[c['resourceRef']];op=ops[c['operationRef']]
        if op['disposition']!='candidate' or op['objectType']!=r['objectType'] or c['request']!=render(op,r):raise ValueError('exact reference binding drift')
        validate_request(p['discovery'],c['request'])
        for page in op.get('pageRequests',[]):validate_request(p['discovery'],page)
        relation='owner' if c['actorRef']==r['owner'] else 'shared' if c['actorRef'] in r.get('sharedWith',[]) and op['kind'] in ('detail','collection') else 'nonowner'
        if r.get('sharedWith'):
            policy=next(x for x in p['inventory']['policies'] if x['id']==op['policyRef'])
            if policy['relation']!='shared-read' or not r.get('grantEvidenceRefs') or not set(r['grantEvidenceRefs'])<={s['id'] for s in p['discovery']['sources']}:raise ValueError('shared grant provenance missing')
        if c['relation']!=relation or c['ownerRef']!=r['owner'] or c['policyRef']!=op['policyRef'] or c['expectedAccess']!=('allow' if relation in ('owner','shared') else 'deny'):raise ValueError('policy drift')
        if c['actorRef'] not in (*actors,'anonymous') or c['budget']!={'maxAttempt':1,'retry':False}:raise ValueError('actor/budget mismatch')
        if op['kind'] in ('update','delete','reference') and not any(x['operationRef']==c['operationRef'] and x['owner']==r['owner'] for x in p['positiveControls']):raise ValueError('dedicated owner positive missing')
    if not ids:raise ValueError('empty BOLA cases')
    if source and p['implementationPins']!=implementation_pin():raise ValueError('implementation pin drift')
    expected_ids={op['operationRef']+'--'+r['id']+'--'+a for op in ops.values() if op['disposition']=='candidate'
        for r in resources.values() if r['role']=='target' and r['objectType']==op['objectType']
        for a in ('A','B','anonymous') if not(op['kind'] in ('update','delete','reference') and a==r['owner'])}
    if ids!=expected_ids:raise ValueError('case coverage missing from inventory')
    secret_check(p)
    return p


class DirectClient:
    """No proxy/env, redirects, cookie jar, retries or raw credential capture."""
    def __init__(self,doc,binding,inspection,out,authority,ssl_context=None,capture_fields=None,actor_refs=None,allow_empty=False,not_after=None):
        self.actor_refs=tuple(actor_refs or ('A','B'));self.allow_empty=allow_empty
        if not self.actor_refs or len(set(self.actor_refs))!=len(self.actor_refs) or 'anonymous' in self.actor_refs:raise ValueError('invalid actor refs')
        self.doc=copy.deepcopy(doc);self.binding=copy.deepcopy(binding);self.inspect=inspection
        b,proof=inspection();self.origin=direct_binding(doc,b,proof);self.out=Path(out);self.authority=copy.deepcopy(authority)
        self.out.mkdir(parents=True,mode=0o700,exist_ok=True);self.deadline=min(time.time()+LIMITS['executionSeconds'],not_after) if not_after is not None else time.time()+LIMITS['executionSeconds']
        self.ssl=ssl_context;self.tokens=MappingProxyType({});self.secret_values=[];self.count=0;self.last=0;self.stopped=False
        self.capture_fields=frozenset(capture_fields) if capture_fields is not None else None
        self.seen=set();self.pins=implementation_pin();self.j=Journal(self.out/'journal.jsonl',self.out.name,canonical_hash({'discovery':doc,'authority':authority,'binding':binding}))
    def set_tokens(self,actors):
        if self.tokens:raise ValueError('immutable actor dispatch slots')
        if set(actors)!=set(self.actor_refs) or any(not a['token'] for a in actors.values()) or len({a['token'] for a in actors.values()})!=len(actors):raise ValueError('independent token slots')
        self.tokens=MappingProxyType({k:v['token'] for k,v in actors.items()})
        self.secret_values.extend(v for a in actors.values() for k,v in a.items() if k in ('password','token','email'))
    def current(self,permission):
        if permission not in self.authority['permissions']:raise ValueError('permission absent')
        if permission not in ('cleanup','poststate') and self.stopped:raise InterruptedError('stop latch')
        if time.time()>=self.deadline:raise TimeoutError('execution deadline')
        if implementation_pin()!=self.pins:raise ValueError('implementation drift')
        verify_local_sources(self.doc);b,proof=self.inspect()
        if b!=self.binding or direct_binding(self.doc,b,proof)!=self.origin:raise ValueError('binding drift')
        s=os.statvfs(self.out)
        if s.f_bavail*s.f_frsize<LIMITS['reserveBytes']:raise OSError('host reserve reached')
        if sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())>LIMITS['artifactBytes']:raise OSError('artifact budget')
    def request(self,label,actor,request,permission,*,token=None,sensitive=False):
        self.current(permission);validate_request(self.doc,request)
        if label in self.seen or self.count>=LIMITS['maxRequests']:raise ValueError('dispatch allocation exhausted')
        if actor not in (*self.actor_refs,'anonymous'):raise ValueError('invalid actor slot')
        if token is not None and actor in self.tokens and token!=self.tokens[actor]:raise ValueError('swapped actor token')
        token=self.tokens.get(actor) if token is None else token
        if actor=='anonymous' and token:raise ValueError('anonymous credential forbidden')
        if request['method']!='GET' and permission in ('read','poststate'):raise ValueError('read permission cannot mutate')
        self.count+=1;self.seen.add(label)
        action={'id':label,'actorRef':actor,'request':sanitized(request,self.secret_values),'permission':permission,'maxDispatch':1}
        # Each dynamic setup/cleanup allocation is durably frozen before its first send.
        save(self.out,'actions/'+label+'.json',action)
        delay=max(0,self.last+1/LIMITS['requestsPerSecond']-time.monotonic())
        if delay:time.sleep(delay)
        self.current(permission);self.last=time.monotonic()
        self.j.append('intent',{'actionRef':'actions/'+label+'.json','actionSha256':canonical_hash(action),'actorRef':actor})
        headers={'Accept':'application/json','Content-Type':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        payload=json.dumps(request['body'],allow_nan=False).encode() if request['body'] is not None else None
        started=time.time()
        try:
            status,body,size=exchange(self.origin,request['method'],request['path'],headers,payload,LIMITS['requestTimeoutSeconds'],self.deadline,ssl_context=self.ssl,allow_empty=self.allow_empty)
        except (OSError,ValueError,TimeoutError,http.client.HTTPException) as error:
            save(self.out,'http/'+label+'.json',{'actionRef':'actions/'+label+'.json','startedAt':started,'endedAt':time.time(),'attribution':'client-transport-unknown','error':type(error).__name__,'retry':False})
            self.j.append('unknown-outcome',{'actionRef':'actions/'+label+'.json','retry':False})
            raise
        projected,complete=project_response(body,self.capture_fields,self.secret_values) if self.capture_fields is not None else (sanitized(body,self.secret_values),True)
        captured={'actionRef':'actions/'+label+'.json','startedAt':started,'endedAt':time.time(),'attribution':'direct-app-response-unattested','captureComplete':True if sensitive else complete,
                  'status':status,'bytes':size,'body':({'credentialResponseOmitted':True,'subject':pointer(body,sensitive['subjectPointer'])}
                     if isinstance(sensitive,dict) and status in (200,201) else {'credentialResponseOmitted':True}) if sensitive else projected}
        save(self.out,'http/'+label+'.json',captured);self.j.append('ack',{'actionRef':'actions/'+label+'.json','responseRef':'http/'+label+'.json','status':status})
        return status,body,'http/'+label+'.json'


def extract_snapshot(resource,body,status,require_expected=True):
    if status!=200:return None
    try:
        result=pointer(body,resource['statePointer'])
        if not isinstance(result,dict) or str(result[resource['idField']])!=str(resource['wireId']):return None
        if require_expected and any(pointer(result,p)!=v for p,v in resource['expectedFields'].items()):return None
        return result
    except (KeyError,TypeError,IndexError):return None


def contains_disclosure(resource,body):
    """Markers are unique fixture values; ID+schema/value pairs are structural."""
    markers=resource.get('markers',[])
    if isinstance(body,str):return any(m in body for m in markers if len(m)>=12)
    if isinstance(body,list):return any(contains_disclosure(resource,v) for v in body)
    if isinstance(body,dict):
        if str(body.get(resource['idField']))==str(resource['wireId']):
            if any(pointer_present_equal(body,p,v) for p,v in resource['expectedFields'].items()):return True
        return any(contains_disclosure(resource,v) for v in body.values())
    return False


def pointer_present_equal(body,p,v):
    try:return pointer(body,p)==v
    except (KeyError,TypeError,IndexError):return False


def evaluate(plan,case,observations):
    """Replay exclusively from saved minimized HTTP and declared policy."""
    r=next(r for r in plan['resources'] if r['id']==case['resourceRef']);op=next(o for o in plan['inventory']['operations'] if o['operationRef']==case['operationRef'])
    def response(key):return observations.get(key,{})
    before=response('owner-before');after=response('owner-after');attempt=response('attempt')
    old=extract_snapshot(r,before.get('body'),before.get('status'));new=extract_snapshot(r,after.get('body'),after.get('status'),False)
    identities=True
    for phase in ('identity-before','identity-after'):
        for actor in set([case['ownerRef'],case['actorRef']])-{'anonymous'}:
            identity=response(phase+'-'+actor)
            try:verify_identity(identity['status'],'application/json',identity['body'],plan['actors'][actor]['subject'],plan['identity']['subjectPointer'])
            except (ValueError,KeyError,TypeError):identities=False
    # Captures keep error/disclosure even when the surrounding controls fail.
    leak=contains_disclosure(r,attempt.get('body'))
    collection_valid=True
    if op['kind']=='collection' and attempt.get('status')==200:
        try:
            items=[]
            pages=[attempt]+[response('page-'+str(i)) for i in range(len(op.get('pageRequests',[]))) if 'page-'+str(i) in observations]
            complete=True
            for pi,page in enumerate(pages):
                if page.get('status')!=200:raise ValueError('page response failed')
                for projection in op['collectionPointers']:
                    value=pointer(page['body'],projection)
                    if value is not None:items.extend(value if isinstance(value,list) else [value])
                if op.get('hasMorePointer'):
                    more=pointer(page['body'],op['hasMorePointer'])
                    if type(more) is not bool:raise ValueError('pagination shape')
                    if more!=(pi<len(pages)-1):complete=False
            ids=[str(x[op['collectionIdField']]) for x in items]
            expected=[str(x['wireId']) for x in plan['resources'] if x['objectType']==r['objectType'] and x['role']=='target' and (x['owner']==case['actorRef'] or case['actorRef'] in x.get('sharedWith',[]))]
            foreign={str(x['wireId']) for x in plan['resources'] if x['objectType']==r['objectType'] and x['role']=='target' and x['owner']!=case['actorRef'] and case['actorRef'] not in x.get('sharedWith',[])}
            leak=bool(set(ids)&foreign) if case['expectedAccess']=='deny' else str(r['wireId']) in ids
            collection_valid=complete and len(set(ids))==len(ids) and set(expected)<=set(ids) and set(ids)<=set(expected)|foreign
        except (KeyError,TypeError,IndexError,ValueError):collection_valid=False
    absent=(after.get('status')==404 and isinstance(after.get('body'),dict) and not contains_disclosure(r,after['body']))
    state_known=new is not None or absent
    changed=old is not None and state_known and (new!=old or response('related-before')!=response('related-after'))
    controls=identities and old is not None and state_known and collection_valid
    if any(isinstance(value,dict) and value.get('captureComplete') is False for value in observations.values()):controls=False
    if any(len(response('related-'+phase))!=len(r.get('relatedRequests',[])) for phase in ('before','after')):controls=False
    if any(x.get('status')!=200 for phase in ('related-before','related-after') for x in response(phase)):controls=False
    if op['kind'] in ('update','delete','reference'):
        controls=controls and any(x['operationRef']==case['operationRef'] and x['owner']==r['owner'] and x['verified'] for x in plan['positiveControls'])
    if case['expectedAccess']=='allow':
        ok=attempt.get('status')==200 and leak and controls
        return {'verdict':'pass' if ok else 'inconclusive','controlsValid':controls,'disclosure':leak,'stateChanged':changed,'observation':'authorized-access' if ok else 'allow-control-failed'}
    violation=leak if op['kind'] in ('detail','collection') else changed
    # Mutation replies can contain owned data even if no state changed: retain disclosure.
    violation=violation or leak
    denial=(attempt.get('status') in (401,403,404) or op['kind']=='collection' and attempt.get('status')==200 and collection_valid) and isinstance(attempt.get('body'),dict) and not violation
    auth_lost=case['actorRef']!='anonymous' and attempt.get('status')==401
    controls=controls and not auth_lost
    verdict='fail' if violation and controls else 'inconclusive' if violation or not controls or not denial else 'pass'
    return {'verdict':verdict,'controlsValid':controls,'disclosure':leak,'stateChanged':changed,
            'observation':'policy-violation' if violation else 'denied' if denial else 'ambiguous',
            'candidateFinding':violation and not controls,'authLost':auth_lost}


class BolaRun:
    def __init__(self,plan,client,out):
        self.p=copy.deepcopy(plan);self.client=client;self.out=Path(out);self.rows=[];self.stop_reason=None
        b,proof=client.inspect();validate_plan(self.p,b,proof)
        self.hash=canonical_hash(self.p);save(out,'PLAN.json',self.p);save(out,'PLAN.sha256',(self.hash+'\n').encode())
    def request(self,label,actor,req,permission):
        if canonical_hash(self.p)!=self.hash or canonical_hash(load(self.out,'PLAN.json'))!=self.hash:raise ValueError('plan drift')
        c=next((c for c in self.p['cases'] if label.startswith(c['id']+'--')),None)
        if c is None:raise ValueError('unallocated case action')
        key=label[len(c['id'])+2:];r=next(r for r in self.p['resources'] if r['id']==c['resourceRef'])
        op=next(o for o in self.p['inventory']['operations'] if o['operationRef']==c['operationRef'])
        if key=='attempt':expected,who=c['request'],c['actorRef']
        elif key.startswith('identity-'):expected,who=self.p['identity']['request'],key.rsplit('-',1)[-1]
        elif key.startswith('related-'):expected,who=r['relatedRequests'][int(key.rsplit('-',1)[-1])],c['ownerRef']
        elif key.startswith('page-'):expected,who=op['pageRequests'][int(key.split('-')[1])],c['actorRef']
        elif key in ('owner-before','owner-after'):expected,who=r['readRequest'],c['ownerRef']
        else:raise ValueError('unallocated case control')
        if req!=expected or actor!=who:raise ValueError('exact case action mismatch')
        status,body,ref=self.client.request(label,actor,req,permission)
        return load(self.client.out,ref),ref
    def case(self,c):
        r=next(x for x in self.p['resources'] if x['id']==c['resourceRef']);obs={};refs={}
        def get(key,actor,req,permission='read'):
            try:o,ref=self.request(c['id']+'--'+key,actor,req,permission)
            except (InterruptedError,TimeoutError,OSError,ValueError,http.client.HTTPException):
                ref='http/'+c['id']+'--'+key+'.json'
                o=load(self.client.out,ref) if (self.client.out/ref).exists() else {'error':'local-guard-rejection','attribution':'local-guard'}
            obs[key]=o;refs[key]=ref if (self.client.out/ref).exists() else None
            return o
        def identities(phase):
            failed=False
            for actor in sorted(set([c['ownerRef'],c['actorRef']])-{'anonymous'}):
                o=get(phase+'-'+actor,actor,self.p['identity']['request'],'poststate' if phase=='identity-after' else 'read')
                try:verify_identity(o['status'],'application/json',o['body'],self.p['actors'][actor]['subject'],self.p['identity']['subjectPointer'])
                except (ValueError,KeyError,TypeError):failed=True
            if failed:raise PermissionError('identity lost')
        identities('identity-before')
        get('owner-before',r['owner'],r['readRequest'])
        related=[]
        for i,req in enumerate(r.get('relatedRequests',[])):
            v=get('related-before-'+str(i),r['owner'],req)
            try:related.append({'status':v['status'],'state':pointer(v['body'],r.get('relatedPointers',['']*len(r['relatedRequests']))[i])})
            except (KeyError,TypeError):related.append({'error':'related-state-unavailable'})
        obs['related-before']=related
        attempt=get('attempt',c['actorRef'],c['request'],'read' if c['request']['method']=='GET' else 'mutation')
        op=next(o for o in self.p['inventory']['operations'] if o['operationRef']==c['operationRef'])
        for i,page in enumerate(op.get('pageRequests',[])):
            try:more=pointer(attempt['body'],op['hasMorePointer'])
            except (KeyError,TypeError):break
            if attempt.get('status')!=200 or more is not True:break
            attempt=get('page-'+str(i),c['actorRef'],page)
        # Readback always follows unknown ACK; the attempt is never replayed.
        get('owner-after',r['owner'],r['readRequest'],'poststate')
        related=[]
        for i,req in enumerate(r.get('relatedRequests',[])):
            v=get('related-after-'+str(i),r['owner'],req,'poststate')
            try:related.append({'status':v['status'],'state':pointer(v['body'],r.get('relatedPointers',['']*len(r['relatedRequests']))[i])})
            except (KeyError,TypeError):related.append({'error':'related-state-unavailable'})
        obs['related-after']=related
        try:identities('identity-after')
        except PermissionError:self.stop_reason='identity-lost';self.client.stopped=True
        decision=evaluate(self.p,c,obs)
        if decision.get('authLost'):self.stop_reason='authentication-lost';self.client.stopped=True
        row={'caseId':c['id'],'operationRef':c['operationRef'],'actorRef':c['actorRef'],'resourceRef':c['resourceRef'],
             'expectedAccess':c['expectedAccess'],'observations':obs,'evidenceRefs':refs,'decision':decision}
        self.rows.append(row);save(self.out,'cases/'+c['id']+'.json',row)
    def run(self,interrupt_after=None):
        old={}
        def stop(signum,frame):self.stop_reason='signal-'+str(signum);self.client.stopped=True
        if __import__('threading').current_thread() is __import__('threading').main_thread():
            for s in (signal.SIGINT,signal.SIGTERM):old[s]=signal.signal(s,stop)
        try:
            for c in self.p['cases']:
                if self.stop_reason:break
                if interrupt_after is not None and len(self.rows)>=interrupt_after:
                    self.stop_reason='controlled-interruption';self.client.stopped=True;break
                try:self.case(c)
                except (PermissionError,InterruptedError,ValueError,OSError,TimeoutError) as error:
                    self.stop_reason=type(error).__name__;self.client.stopped=True;break
        finally:
            for s,handler in old.items():signal.signal(s,handler)
        save(self.out,'RESULTS.json',self.rows)
        executed={x['caseId'] for x in self.rows}
        coverage={'inventoryOperations':len(self.p['inventory']['operations']),'operationDispositions':self.p['inventory']['operations'],
                  'plannedCases':len(self.p['cases']),'executedCases':len(self.rows),
                  'cases':[{'caseId':c['id'],'status':next((x['decision']['verdict'] for x in self.rows if x['caseId']==c['id']),'not-run'),
                    'reason':None if c['id'] in executed else self.stop_reason or 'not executed'} for c in self.p['cases']]}
        save(self.out,'COVERAGE.json',coverage)
        complete=len(self.rows)==len(self.p['cases']) and not self.stop_reason
        verdict='fail' if any(x['decision']['verdict']=='fail' for x in self.rows) else 'pass' if complete and all(x['decision']['verdict']=='pass' for x in self.rows) else 'inconclusive'
        result={'executionStatus':'completed' if complete else 'interrupted' if self.stop_reason in ('controlled-interruption','signal-2','signal-15') else 'stopped',
                'evidenceStatus':'complete' if complete else 'partial','securityVerdict':verdict,'cleanupStatus':'pending','gateDecision':'block',
                'stopReason':self.stop_reason,'requests':self.client.count,'proof':'client dispatch and sampled protected subject, not continuous wire attestation'}
        return result


def alerts(plan,rows):
    findings={}
    for row in rows:
        d=row['decision']
        if d['verdict']!='fail' and not d.get('candidateFinding'):continue
        c=next(c for c in plan['cases'] if c['id']==row['caseId'])
        op=next(o for o in plan['inventory']['operations'] if o['operationRef']==c['operationRef'])
        key=op['objectType']+'-'+('write' if c['request']['method']!='GET' else 'read')
        finding=findings.setdefault(key,{'id':'BOLA-'+key,'source':'BOLA/direct-client','nativeZapId':None,'ruleId':'object-authorization',
          'name':'Truy cập object ngoài policy: '+key,'severity':'High','confidence':'High' if d['controlsValid'] else 'Low',
          'classificationAuthority':'agent evaluation from explicit source/fixture policy and client evidence; no reviewer approval',
          'description':'Actor không có quyền theo policy đã đọc dữ liệu fixture hoặc thay đổi trạng thái của owner khác.',
          'impact':'Disclosure hoặc integrity impact chỉ trên object và related state có evidence.',
          'remediation':'Kiểm quyền với subject đã xác thực trên mỗi object/reference trước đọc hoặc ghi; giữ post-state controls.',
          'retest':'Chạy lại cùng logical cases với fixtures mới trên selected fixed build.',
          'instances':[]})
        finding['instances'].append({'caseId':c['id'],'operationRef':c['operationRef'],'actor':c['actorRef'],'resource':c['resourceRef'],
            'method':c['request']['method'],'path':c['request']['path'],'expected':c['expectedAccess'],'observed':d,
            'evidenceRefs':['cases/'+c['id']+'.json',*filter(None,row['evidenceRefs'].values())]})
    return {'schemaVersion':'product-assessment-handoff/bola-1.0','source':'BOLA/direct-client','nativeZap':False,
            'findings':list(findings.values()),'count':len(findings),'securitySignOff':False}


def seal(root):
    root=Path(root)
    rows=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(root.rglob('*'))
          if p.is_file() and p.name not in ('EVIDENCE_INDEX.json','VERIFICATION.json')]
    save(root,'EVIDENCE_INDEX.json',{'family':VERSION,'files':rows,'limitations':'Client captures; no signature/wire/source-to-image attestation. Hash index is local integrity, not an external trust anchor.'})


def verify(root):
    if load(root,'PLAN.json').get('schemaVersion')=='bola-continuation-plan/1.0':
        from .bola_research_expanded import verify as verify_expanded
        return verify_expanded(root)
    root=Path(root);idx=load(root,'EVIDENCE_INDEX.json');listed={x['path'] for x in idx['files']}
    if len(listed)!=len(idx['files']):raise ValueError('duplicate evidence index')
    actual={str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and p.name not in ('EVIDENCE_INDEX.json','VERIFICATION.json')}
    if listed!=actual:raise ValueError('missing/unindexed evidence')
    for row in idx['files']:
        p=(root/row['path'])
        if p.is_symlink() or not p.resolve().is_relative_to(root.resolve()) or not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise ValueError('evidence hash/reference mismatch')
    plan=load(root,'PLAN.json');h=canonical_hash(plan)
    if (root/'PLAN.sha256').read_text().strip()!=h:raise ValueError('plan hash mismatch')
    # Saved readback must not depend on present deployment, expiry or edited sources.
    validate_plan(plan,plan['targetBinding'],plan['transportBinding'],now=plan['lockedAt'],source=False)
    journal=Journal(root/'journal.jsonl',plan['runId'],canonical_hash({'discovery':plan['discovery'],'authority':plan['authority'],'binding':plan['targetBinding']})).events
    acks={e['data']['responseRef']:e for e in journal if e['kind']=='ack'}
    intents={e['data']['actionRef']:e for e in journal if e['kind']=='intent'}
    if len(acks)!=sum(e['kind']=='ack' for e in journal) or len(intents)!=sum(e['kind']=='intent' for e in journal):raise ValueError('duplicate dispatch/ack')
    for ref,event in intents.items():
        action=load(root,ref)
        if canonical_hash(action)!=event['data']['actionSha256'] or action['actorRef']!=event['data']['actorRef'] or action['maxDispatch']!=1:raise ValueError('action intent mismatch')
    for path in sorted((root/'http').glob('*.json')):
        ref=str(path.relative_to(root));captured=decode(path.read_bytes());action_ref=captured['actionRef']
        if action_ref not in intents:raise ValueError('HTTP without intent')
        if 'status' in captured:
            ack=acks.get(ref)
            if not ack or ack['data']['actionRef']!=action_ref or ack['seq']<=intents[action_ref]['seq'] or ack['data']['status']!=captured['status']:raise ValueError('HTTP ACK mismatch')
        elif not any(e['kind']=='unknown-outcome' and e['data']['actionRef']==action_ref and e['seq']>intents[action_ref]['seq'] for e in journal):raise ValueError('unknown outcome unaccounted')
    for r in plan['resources']:
        for ref in r['preparationEvidence']:
            if ref not in listed:raise ValueError('fixture preparation missing')
            preparation=load(root,ref)
            if ref.startswith('http/'):
                action=load(root,preparation['actionRef'])
                if action['actorRef']!=r['owner'] or action['permission']!='setup' or preparation.get('status')!=201:raise ValueError('fixture creation ownership mismatch')
    for actor,record in plan['actors'].items():
        for ref in record['evidenceRefs']:
            response=load(root,ref)
            if response.get('body',{}).get('credentialResponseOmitted') and str(response['body'].get('subject'))!=str(record['subject']):raise ValueError('actor registration/login subject mismatch')
    # Dedicated positives are actual HTTP/state evidence, not trusted booleans.
    target_ids={(r['objectType'],str(r['wireId'])) for r in plan['resources']}
    for control in plan['positiveControls']:
        resource=control['resource']
        if (resource['objectType'],str(resource['wireId'])) in target_ids or resource['runId']!=plan['runId'] or resource['owner']!=control['owner']:
            raise ValueError('positive fixture ownership/separation mismatch')
        before=load(root,control['beforeRef']);attempt=load(root,control['attemptRef']);after=load(root,control['afterRef'])
        for ref,row in ((control['beforeRef'],before),(control['attemptRef'],attempt),(control['afterRef'],after)):
            action=load(root,row['actionRef'])
            if action['actorRef']!=control['owner'] or ref not in acks or row['actionRef'] not in intents:raise ValueError('positive control evidence missing')
        if load(root,attempt['actionRef'])['request']!=control['request']:raise ValueError('positive request mismatch')
        initial=extract_snapshot(resource,before['body'],before['status'])
        post=extract_snapshot(resource,after['body'],after['status'],False)
        actual=(initial is not None and attempt['status']==200 and
            (after['status']==404 if control['request']['method']=='DELETE' else post is not None and post!=initial and bool(control['expectedPost']) and all(pointer_present_equal(post,p,v) for p,v in control['expectedPost'].items())))
        if not actual or control['verified'] is not True:raise ValueError('positive poststate control mismatch')
        if not acks[control['beforeRef']]['seq']<intents[attempt['actionRef']]['seq']<acks[control['afterRef']]['seq']:raise ValueError('positive control chronology mismatch')
    seen=set();rows=load(root,'RESULTS.json');bycase={c['id']:c for c in plan['cases']}
    for row in rows:
        cid=row['caseId']
        if cid in seen or cid not in bycase:raise ValueError('case sequence mismatch')
        if cid!=plan['cases'][len(seen)]['id']:raise ValueError('case order mismatch')
        seen.add(cid);c=bycase[cid]
        if load(root,'cases/'+cid+'.json')!=row:raise ValueError('case record mismatch')
        if any(row[k]!=c[k] for k in ('operationRef','actorRef','resourceRef','expectedAccess')):raise ValueError('case binding mismatch')
        if set(row['evidenceRefs'])!={k for k in row['observations'] if k not in ('related-before','related-after')}:raise ValueError('HTTP reference accounting mismatch')
        for key,ref in row['evidenceRefs'].items():
            if ref is None:
                if row['observations'][key].get('attribution')!='local-guard':raise ValueError('missing HTTP proof')
                continue
            captured=load(root,ref)
            if captured!=row['observations'][key]:raise ValueError('HTTP observation mismatch')
            action=load(root,captured['actionRef']);intent=intents.get(captured['actionRef'])
            if not intent or intent['data']['actionSha256']!=canonical_hash(action):raise ValueError('missing exact intent')
            expected_actor=c['actorRef'] if key=='attempt' or key.startswith('page-') else key.rsplit('-',1)[-1] if key.startswith('identity-') else c['ownerRef']
            if action['actorRef']!=expected_actor:raise ValueError('HTTP actor drift')
            r=next(r for r in plan['resources'] if r['id']==c['resourceRef'])
            op=next(o for o in plan['inventory']['operations'] if o['operationRef']==c['operationRef'])
            expected_req=c['request'] if key=='attempt' else op['pageRequests'][int(key.split('-')[1])] if key.startswith('page-') else plan['identity']['request'] if key.startswith('identity-') else r['relatedRequests'][int(key.rsplit('-',1)[-1])] if key.startswith('related-') else r['readRequest']
            if action['request']!=expected_req:raise ValueError('HTTP request drift')
            if 'status' in captured:
                ack=acks.get(ref)
                if not ack or ack['seq']<=intent['seq'] or ack['data']['status']!=captured['status']:raise ValueError('HTTP ACK sequence missing')
        required=set(c['evidenceRequirements'])-{'identity-before','identity-after'}
        required.update(phase+'-'+a for phase in ('identity-before','identity-after') for a in set([c['ownerRef'],c['actorRef']])-{'anonymous'})
        if not required<=row['observations'].keys():raise ValueError('required controls missing')
        attempt_ref=row['observations']['attempt'].get('actionRef')
        if attempt_ref in intents:
            attempt_seq=intents[attempt_ref]['seq']
            for key,ref in row['evidenceRefs'].items():
                if ref is None or key=='attempt' or key.startswith('page-'):continue
                captured=load(root,ref);control_intent=intents[captured['actionRef']]['seq']
                if 'before' in key and control_intent>=attempt_seq or 'after' in key and control_intent<=attempt_seq:raise ValueError('case control chronology mismatch')
        if evaluate(plan,c,row['observations'])!=row['decision']:raise ValueError('oracle decision mismatch')
        for phase in ('before','after'):
            related=[]
            for i,_ in enumerate(r.get('relatedRequests',[])):
                v=row['observations']['related-'+phase+'-'+str(i)]
                try:related.append({'status':v['status'],'state':pointer(v['body'],r.get('relatedPointers',['']*len(r['relatedRequests']))[i])})
                except (KeyError,TypeError):related.append({'error':'related-state-unavailable'})
            if related!=row['observations']['related-'+phase]:raise ValueError('related state missing')
    cov=load(root,'COVERAGE.json')
    if cov['inventoryOperations']!=len(plan['inventory']['operations']) or cov['operationDispositions']!=plan['inventory']['operations']:raise ValueError('operation disposition mismatch')
    if cov['plannedCases']!=len(plan['cases']) or cov['executedCases']!=len(rows) or {x['caseId'] for x in cov['cases']}!=set(bycase):raise ValueError('coverage denominator mismatch')
    for x in cov['cases']:
        expected=next((r['decision']['verdict'] for r in rows if r['caseId']==x['caseId']),'not-run')
        if x['status']!=expected:raise ValueError('coverage verdict mismatch')
    if load(root,'ALERTS.json')!=alerts(plan,rows):raise ValueError('findings mismatch')
    run=load(root,'RUN.json')
    complete=len(rows)==len(plan['cases']) and not run.get('stopReason')
    verdict='fail' if any(r['decision']['verdict']=='fail' for r in rows) else 'pass' if complete and all(r['decision']['verdict']=='pass' for r in rows) else 'inconclusive'
    if run['securityVerdict']!=verdict or (run['executionStatus']=='completed')!=complete:raise ValueError('run verdict mismatch')
    if run['requests']!=len(intents) or run['evidenceStatus']!=('complete' if complete else 'partial'):raise ValueError('run accounting mismatch')
    if (root/'CLEANUP_RETENTION.json').exists():
        cleanup=load(root,'CLEANUP_RETENTION.json')
        ledger={r['id']:r for r in load(root,'FIXTURES.json')['ledger'] if r.get('objectType')=='account'}
        if len(cleanup['accounts'])!=len(ledger) or {x['resource'] for x in cleanup['accounts']}!=set(ledger):raise ValueError('cleanup denominator mismatch')
        for entry in cleanup['accounts']:
            resource=ledger[entry['resource']]
            if any(entry[k]!=resource[k] for k in ('wireId','owner','runId')):raise ValueError('cleanup ownership mismatch')
            if entry['status'] in ('deleted','already-absent'):
                captures=[load(root,ref) for ref in entry['evidenceRefs']]
                identity=captures[0]
                verify_identity(identity['status'],'application/json',identity['body'],plan['actors'][entry['owner']]['subject'],plan['identity']['subjectPointer'])
                if captures[-1].get('status')!=404:raise ValueError('cleanup absence unproven')
                for capture in captures:
                    if load(root,capture['actionRef'])['actorRef']!=entry['owner']:raise ValueError('cleanup actor mismatch')
        status='retained-documented' if all(x['status'] in ('deleted','already-absent') for x in cleanup['accounts']) else 'incomplete'
        if run['cleanupStatus']!=status:raise ValueError('cleanup claim mismatch')
    expected_gate='allow' if run['executionStatus']=='completed' and verdict=='pass' and run['cleanupStatus'] in ('clean','retained-documented') else 'block'
    if run['gateDecision']!=expected_gate:raise ValueError('gate claim mismatch')
    return {'evidenceStatus':'consistent','files':len(listed),'replayedCases':len(rows),'securitySignOff':False,'independentLimits':idx['limitations']}


def compare_runs(before,after):
    reasons=[];roots=[Path(before),Path(after)]
    for r in roots:verify(r)
    plans=[load(r,'PLAN.json') for r in roots];runs=[load(r,'RUN.json') for r in roots]
    for key in ('implementationPins','inventorySha256','discoverySha256'):
        if plans[0][key]!=plans[1][key]:reasons.append('drift: '+key)
    if plans[0]['targetBinding']!=plans[1]['targetBinding']:reasons.append('target build/binding drift')
    logical=lambda p:[(c['id'],c['operationRef'],c['actorRef'],c['resourceRef'],c['expectedAccess']) for c in p['cases']]
    if logical(plans[0])!=logical(plans[1]):reasons.append('logical case drift')
    if any(r['executionStatus']!='completed' for r in runs):reasons.append('incomplete execution')
    if [r['wireId'] for r in plans[0]['resources']]==[r['wireId'] for r in plans[1]['resources']]:reasons.append('fresh fixture IDs not established')
    if [(r['caseId'],r['decision']) for r in load(roots[0],'RESULTS.json')]!=[(r['caseId'],r['decision']) for r in load(roots[1],'RESULTS.json')]:reasons.append('logical outcome drift')
    return {'decision':'repeatability-compatible' if not reasons else 'inconclusive','reasons':reasons,
            'comparisonKind':'same-build-BOLA-repeatability','findingsCountedFrom':'primary run only','fixedBuildRegression':'pending-selected-build-B'}
