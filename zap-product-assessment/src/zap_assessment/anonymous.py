"""Versioned anonymous research admission. Authenticated/strict contracts unchanged."""
from __future__ import annotations
import copy
import json
import re
import time
from urllib.parse import urlsplit, parse_qsl
from .discovery import (canonical_hash, validate_discovery, verify_local_sources,
                        execution_origin, path_valid, matches, origin, schema_check)

PROFILE='be-anonymous-research/1.0'
DEFAULT_LIMITS={'requestsPerSecond':2,'maxForwarded':600,'maxMutations':400,
 'requestBytes':16384,'responseBytes':1048576,'requestTimeoutSeconds':8,
 'executionSeconds':1200,'operationSeconds':180,'stopSeconds':10,
 'artifactBytes':134217728,'reserveBytes':2147483648,'concurrency':1}
DISPOSITIONS=('public-exercise','protected-denial','conditional','blocked','not-run','not-applicable')

def transport(doc,binding,proof):
    if proof['targetBinding']!=binding or proof['environment']!=doc['product']['environment']:
        raise ValueError('runtime binding/environment drift')
    # Backend-only products do not need a direct or UI origin.
    for role,key in [('scanner','scannerOrigins'),('direct','directOrigins')]:
        selected=[o['url'] for o in doc['product']['origins'] if o['role']==role and o['authorized'] and o['bindingVerified']]
        if role=='scanner' and not selected:raise ValueError('verified scanner origin missing')
        if any(o not in proof.get(key,[]) for o in selected):raise ValueError('origin not independently bound: '+role)


def compile_plan(doc, *, live_binding, observed_transport, run_id, cases, campaigns,
                 authority, fixtures=None, dispositions=None, limits=None, not_after=None,
                 cookie_policy=None, target_ownership='borrowed'):
    locked_at=time.time();effective_limits=copy.deepcopy(limits or DEFAULT_LIMITS)
    plan={'lockedAt':locked_at,'schemaVersion':'be-anonymous-research-plan/1.0','assuranceProfile':PROFILE,
      'runId':run_id,'environment':doc['product']['environment'],'targetBinding':copy.deepcopy(live_binding),
      'transportBinding':copy.deepcopy(observed_transport),'origin':execution_origin(doc,'scanner'),
      'discovery':copy.deepcopy(doc),'discoverySha256':canonical_hash(doc),'authority':copy.deepcopy(authority),
      'cases':copy.deepcopy(cases),'campaigns':copy.deepcopy(campaigns),'fixtures':copy.deepcopy(fixtures or []),
      'dispositions':copy.deepcopy(dispositions or []),'limits':effective_limits,
      'notAfter':not_after or locked_at+effective_limits['executionSeconds'],
      'anonymousState':{'propagateIdentity':False,'cookies':cookie_policy or {},'redirects':'deny'},
      'targetOwnership':target_ownership,'runtime':'dedicated-docker-http/1.0','jobStore':'in-memory','coordinator':'single-node'}
    validate_plan(plan,live_binding,observed_transport)
    return plan


def validate_plan(p,binding,proof, *, now=None):
    schema_check(p,'be-anonymous-research-plan-v1.schema.json')
    d=p['discovery'];validate_discovery(d)
    if d['schemaVersion']!='product-discovery/1.1':raise ValueError('discovery 1.1 required')
    if not d['operations']:raise ValueError('no operation inventory')
    if d['tracks']['be-anonymous']['status'] not in ('candidate','ready'):raise ValueError('anonymous prerequisites blocked')
    if any(x['blocking'] for x in d['conflicts']):raise ValueError('source/spec conflict unresolved')
    if canonical_hash(d)!=p['discoverySha256']:raise ValueError('inventory hash drift')
    if binding!=p['targetBinding'] or binding!=d['product']['binding']:raise ValueError('target binding drift')
    transport(d,binding,proof);transport(d,binding,p['transportBinding'])
    if p['origin']!=execution_origin(d,'scanner'):raise ValueError('origin selection drift')
    if p['environment']!=d['product']['environment']:raise ValueError('environment drift')
    u=urlsplit(origin(p['origin']))
    if u.scheme!='http':raise ValueError('unsupported dedicated HTTP adapter; HTTPS requires explicit adapter')
    if p['limits']['reserveBytes']!=DEFAULT_LIMITS['reserveBytes']:raise ValueError('research reserve must remain 2GiB')
    if p['notAfter']>p['lockedAt']+p['limits']['executionSeconds'] or p['lockedAt']>(time.time() if now is None else now)+1:raise ValueError('execution budget/deadline mismatch')
    if p['notAfter']<=(time.time() if now is None else now):raise ValueError('plan execution deadline')
    a=p['authority'];ops={x['id']:x for x in d['operations']}
    if a['environment']!=p['environment'] or not a['source'] or a['discoveryRead'] is not True:
        raise ValueError('explicit environment/read authority missing')
    disp={x['operationId']:x for x in p['dispositions']}
    if len(disp)!=len(p['dispositions']) or set(disp)!=set(ops):raise ValueError('every operation requires disposition')
    for oid,row in disp.items():
        if row['disposition'] not in DISPOSITIONS or not row['reason']:raise ValueError('invalid disposition')
        if row['disposition']=='protected-denial' and not ops[oid]['protected']:raise ValueError('denial mapping must be protected')
        if row['disposition']=='public-exercise' and ops[oid]['protected']:raise ValueError('public mapping must be unprotected')
    fids={f['id']:f for f in p['fixtures']}
    if len(fids)!=len(p['fixtures']):raise ValueError('duplicate fixture')
    for f in fids.values():
        if f['runId']!=p['runId'] or not f['ownership'] or not f['preparationEvidence'] or not f['cleanup']:
            raise ValueError('fixture ownership/preparation/cleanup unresolved')
    cases={}
    for c in p['cases']:
        if c['id'] in cases:raise ValueError('duplicate case')
        cases[c['id']]=c;known=ops.get(c['operationId']);v=urlsplit(c['path']);path_valid(v.path)
        if not known or c['method']!=known['method'] or not matches(known['pathTemplate'],v.path) or v.scheme or v.netloc or v.fragment:
            raise ValueError('case outside inventory or unresolved path')
        if any(k not in known['input'].get('query',[]) for k,val in parse_qsl(v.query,keep_blank_values=True)):
            raise ValueError('undiscovered query')
        if disp[known['id']]['disposition'] not in ('protected-denial','public-exercise'):raise ValueError('case operation not executable')
        if known['protected']!=(c['category']=='protected-denial'):raise ValueError('protected/public case category mismatch')
        if known['protected'] and not set(c['expected']['statuses'])<={401,403}:raise ValueError('denial expected outcome mismatch')
        if not known['protected'] and c['category'] not in ('public-success','public-validation','documentation','protocol-control'):
            raise ValueError('public category invalid')
        if any(k.lower() in ('authorization','proxy-authorization','cookie') for k in c.get('headers',{})):
            raise ValueError('identity header forbidden in workload')
        if c['method'] not in ('GET','HEAD','OPTIONS'):
            if not a['publicMutation' if not known['protected'] else 'deniedMutation']:raise ValueError('explicit mutation authority required')
            if not c['fixtureRefs']:raise ValueError('mutation fixture required')
        if '{' in c['path'] or '}' in c['path']:raise ValueError('unresolved ID')
        for fid in c['fixtureRefs']:
            if fid not in fids:raise ValueError('unresolved fixture')
        if c.get('privateBodyRef') is not None:
            from .anonymous_private_body import resolve_case
            resolved=resolve_case(p,c)
            # Keep the immutable public plan private-ref-only; validate campaigns
            # against the materialized body without storing credentials in it.
            cases[c['id']]=resolved
        if len(json.dumps(c.get('body')).encode())>p['limits']['requestBytes']:raise ValueError('case size limit')
        if not c['expected']['contentType'] or not c['expected']['statuses']:raise ValueError('expected oracle missing')
        if c['expected'].get('bodySha256'):
            if c['category']!='documentation' or c['method']!='GET' or c['expected'].get('equals') or c['expected'].get('present'):raise ValueError('document byte oracle requires documentation GET only')
    for oid,row in disp.items():
        if row['disposition'] in ('public-exercise','protected-denial') and not any(c['operationId']==oid for c in cases.values()):raise ValueError('executable disposition missing case')
    for camp in p['campaigns']:
        c=cases.get(camp['caseId'])
        if not a['active'] or not c:raise ValueError('explicit active authority/case required')
        if c['category']=='protected-denial':raise ValueError('protected active is outside anonymous public campaign')
        if not camp['ruleIds'] or any(r not in (40012,40018) for r in camp['ruleIds']):raise ValueError('unsupported selected technique')
        if camp['vectors']==['JSON-body']:
            if c['method']!='POST' or not isinstance(c['body'],dict):raise ValueError('unsupported vector/request capability')
            fields=set(c['body'])
        elif camp['vectors']==['query']:
            pairs=parse_qsl(urlsplit(c['path']).query,keep_blank_values=True)
            if c['method']!='GET' or c['body'] is not None or len(pairs)!=len(dict(pairs)):raise ValueError('unsupported query baseline')
            fields=set(dict(pairs))
            if {k.lower() for k in fields} & {'authorization','token','accesstoken','cookie','password'}:raise ValueError('identity query forbidden')
        elif camp['vectors']==['path']:
            from .anonymous_guard import path_scope
            if c['method']!='GET' or c['body'] is not None:raise ValueError('anonymous path capability is GET only')
            scope=path_scope(ops[c['operationId']]['pathTemplate'],urlsplit(c['path']).path)
            fields={scope['parameter']}
        else:raise ValueError('unsupported vector/request capability')
        if not set(camp['mutableKeys'])<=fields or not camp['mutableKeys']:raise ValueError('unknown vector fields')
        if not 1<=camp['maxForwarded']<=p['limits']['maxForwarded']:raise ValueError('campaign budget')
    # Every finite allocation is bounded before provisioning. No fake auth actor.
    for k,cap in DEFAULT_LIMITS.items():
        if not 0<p['limits'][k]<=cap:raise ValueError('limit outside research cap: '+k)
    for name,contract in p['anonymousState']['cookies'].items():
        if not re.fullmatch(r'[A-Za-z0-9_-]+',name) or contract.get('identity') is not False or not contract.get('evidenceRefs'):
            raise ValueError('anonymous cookie contract required')
    return p


def expected_response(case,message):
    """App attribution, JSON shape and semantic checks; HTTP 200 alone is insufficient."""
    h=message.get('responseHeader','');status=re.match(r'HTTP/\S+ (\d+)',h)
    headers={k.strip().lower():v.strip() for k,sep,v in (x.partition(':') for x in h.split('\r\n')[1:]) if sep}
    if headers.get('x-zpa-response-origin')!='app':return {'matched':False,'reason':'guard-or-unattributed'}
    if not status or int(status[1]) not in case['expected']['statuses']:return {'matched':False,'reason':'status'}
    if case['expected']['contentType'].lower() not in headers.get('content-type','').lower():return {'matched':False,'reason':'content-type'}
    if case['expected'].get('bodySha256'):
        import hashlib
        matched=hashlib.sha256(message.get('responseBody','').encode()).hexdigest()==case['expected']['bodySha256']
        return {'matched':matched,'status':int(status[1]),'responseOrigin':'app','category':case['category'],'oracle':'pinned document bytes'}
    try:value=json.loads(message['responseBody'])
    except (ValueError,KeyError):return {'matched':False,'reason':'json'}
    for pointer,expected in case['expected'].get('equals',{}).items():
        got=value
        try:
            for part in pointer.strip('/').split('/'):
                key=part.replace('~1','/').replace('~0','~');got=got[int(key)] if isinstance(got,list) else got[key]
        except (TypeError,KeyError,IndexError,ValueError):return {'matched':False,'reason':'schema-pointer'}
        if got!=expected:return {'matched':False,'reason':'semantic'}
    for pointer in case['expected'].get('present',[]):
        got=value
        try:
            for part in pointer.strip('/').split('/'):
                key=part.replace('~1','/').replace('~0','~');got=got[int(key)] if isinstance(got,list) else got[key]
        except (TypeError,KeyError,IndexError,ValueError):return {'matched':False,'reason':'schema-pointer'}
        if got is None:return {'matched':False,'reason':'schema-null'}
    return {'matched':True,'status':int(status[1]),'responseOrigin':'app','category':case['category']}


def validate_exports(messages,alerts,message_count,alert_count):
    if len(messages)!=message_count or len({str(m['id']) for m in messages})!=message_count:raise ValueError('missing/duplicate message page')
    if len(alerts)!=alert_count or len({str(a['id']) for a in alerts})!=alert_count:raise ValueError('missing/duplicate alert page')
    mids={str(m['id']) for m in messages}
    if any(str(a.get('messageId')) not in mids for a in alerts):raise ValueError('missing alert message refs')
    return True
