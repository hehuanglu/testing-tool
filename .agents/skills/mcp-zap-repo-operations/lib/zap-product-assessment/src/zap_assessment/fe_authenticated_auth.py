"""Independent actor/session records and native bootstrap configuration."""
import json,stat
from pathlib import Path

def pointer(value,path):
    for key in path.strip('/').split('/'):
        if key:value=value[int(key)] if isinstance(value,list) else value[key.replace('~1','/').replace('~0','~')]
    return value

def private_actors(path):
    p=Path(path)
    if p.is_symlink() or not stat.S_ISREG(p.stat().st_mode) or p.stat().st_mode&0o077:raise ValueError('actors must be a private regular file')
    rows=json.loads(p.read_bytes())
    for key,a in rows.items():
        if not {'username','password','subject','role','provenance'}<=a.keys() or not a['provenance']:raise ValueError('independent actor provenance absent')
        for ref in a['provenance']:
            from .fe_authenticated_contract import digest
            if digest(ref['path'])!=ref['sha256']:raise ValueError('actor provenance drift')
        if a.get('source')=='login-response-only':raise ValueError('login response cannot attest itself')
    return rows

def validate_actor_roles(auth,actors):
    if any(a['role']!=auth['identity'].get('roleByActor',{}).get(ref,auth['identity']['expectedRole']) for ref,a in actors.items()):raise ValueError('actor role differs from reviewed UI responsibility')
    principals=[str(a['subject']) for a in actors.values()]
    if len(principals)!=len(set(principals)):raise ValueError('separate actor refs must have independent principals')

def native_profile(auth,origin,actor,ref,credential_path):
    if auth['kind']!='json-bearer':raise ValueError('unqualified native adapter')
    return {'id':ref,'kind':'json-bearer','allowed-origin':origin,'credential-reference':'file:'+credential_path,'login-url':origin+auth['loginPath'],'username':actor['username'],'zap-user-name':ref,'username-json-field':auth['usernameField'],'password-json-field':auth['passwordField'],'token-json-pointer':auth['tokenPointer'],'header-name':'Authorization','header-prefix':'Bearer ','verification-url':origin+auth['identity']['path'],'subject-json-pointer':auth['identity']['subjectPointer'],'expected-subject':str(actor['subject']),'logged-in-indicator-regex':'.*','logged-out-indicator-regex':'"(?:status|statusCode)"\\s*:\\s*401'}
