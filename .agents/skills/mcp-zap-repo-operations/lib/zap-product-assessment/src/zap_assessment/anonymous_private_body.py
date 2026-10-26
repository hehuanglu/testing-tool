"""Private, pinned seed bodies for discovered public auth; never session propagation."""
import copy,hashlib,json,stat
from pathlib import Path
from .anonymous_guard import identity


def resolve_case(plan,case):
    ref=case.get('privateBodyRef')
    if ref is None:return copy.deepcopy(case)
    auth=plan['discovery'].get('auth') or {};ids={auth.get('loginOperationId'),auth.get('identity',{}).get('actorSource',{}).get('operationId')}
    if plan['authority'].get('secretPersistenceAccepted') is not True:raise ValueError('private public-auth retention acceptance required')
    if case['operationId'] not in ids or case['method']!='POST' or case.get('body') is not None or case['category'] not in ('public-success','public-validation'):raise ValueError('private body restricted to discovered public auth seeds')
    operation=next((o for o in plan['discovery']['operations'] if o['id']==case['operationId']),None)
    if not operation or operation['protected'] or operation['method']!='POST' or case['path']!=operation['pathTemplate']:raise ValueError('private body operation mismatch')
    campaigns=[c for c in plan['campaigns'] if c['caseId']==case['id']]
    # Private auth campaigns use the existing exact-body guard, with a small explicit
    # allocation. Registration keeps the unique credential fixed at a duplicate
    # baseline; it cannot create arbitrary accounts from scanner payloads.
    for campaign in campaigns:
        keys=campaign.get('mutableKeys',[])
        login=case['operationId']==auth.get('loginOperationId')
        if (campaign.get('vectors')!=['JSON-body'] or campaign.get('baselineSeed') is not True
                or type(campaign.get('maxForwarded'))!=int or not 1<=campaign['maxForwarded']<=20
                or not keys or len(keys)!=len(set(keys))
                or case.get('expected',{}).get('statuses')!=([200] if login else [409])
                or (login and keys!=[auth.get('usernameField')])
                or (not login and any(k in (auth.get('usernameField'),auth.get('passwordField')) or 'password' in k.lower() for k in keys))):
            raise ValueError('private credential active campaigns not admitted: exact bounded auth baseline required')
    path=Path(ref['path'])
    if not path.is_absolute() or path.is_symlink() or not path.is_file() or not stat.S_ISREG(path.stat().st_mode) or path.stat().st_mode & 0o077:raise ValueError('private auth body must be regular mode0600')
    data=path.read_bytes()
    if len(data)>plan['limits']['requestBytes'] or hashlib.sha256(data).hexdigest()!=ref['sha256']:raise ValueError('private auth body size/hash drift')
    try:body=json.loads(data)
    except (ValueError,UnicodeError):raise ValueError('private auth body invalid JSON') from None
    if not isinstance(body,dict) or not body or any(not isinstance(v,str) for v in body.values()) or identity(body):raise ValueError('private auth body shape/identity forbidden')
    if not body.get(auth.get('usernameField')) or not body.get(auth.get('passwordField')):raise ValueError('private auth credential fields missing')
    if any(not set(c['mutableKeys'])<=set(body) for c in campaigns):raise ValueError('private active field absent')
    result=copy.deepcopy(case);result.pop('privateBodyRef');result['body']=body;return result


def materialize_guard_plan(plan):
    result=copy.deepcopy(plan);result['cases']=[resolve_case(plan,c) for c in plan['cases']];return result
