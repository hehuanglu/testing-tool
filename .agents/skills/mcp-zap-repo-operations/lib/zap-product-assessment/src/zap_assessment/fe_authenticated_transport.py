"""Authenticated policy over the evidence2 TLS forwarding primitive. No identity injection."""
import hashlib,json,re,threading
from pathlib import Path
from urllib.parse import urlsplit,parse_qsl
from .fe_anonymous_transport import Broker,sha
from .fe_authenticated_auth import pointer

def path_matches(rule,path):
    template=rule['path']
    if '{' not in template:return template==path
    names=re.findall(r'\{([A-Za-z][A-Za-z0-9]*)\}',template)
    pattern=re.escape(template)
    formats=rule.get('pathParameters',{})
    for name in names:
        fmt=formats.get('format','segment') if formats.get('name')==name else 'segment'
        patterns={'integer':r'[1-9][0-9]{0,18}','uuid':r'[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}',
                  'slug':r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}','segment':r'[A-Za-z0-9][A-Za-z0-9_.~-]{0,127}'}
        if fmt not in patterns:return False
        pattern=pattern.replace(re.escape('{'+name+'}'),patterns[fmt])
    return re.fullmatch(pattern,path) is not None


def valid_owned_id(value,fmt='integer'):
    if fmt=='integer':return type(value) is int and 0<value<=9007199254740991
    return isinstance(value,str) and path_matches({'path':'/{id}','pathParameters':{'name':'id','format':fmt}},'/'+value)


def valid_payload(rule,payload):
    if 'jsonSchema' in rule:
        from jsonschema import Draft202012Validator
        return not list(Draft202012Validator(rule['jsonSchema']).iter_errors(payload))
    return isinstance(payload,dict) and set(payload)==set(rule.get('jsonFields',[])) and all(
        v is None or isinstance(v,(str,int,float,bool)) for v in payload.values())

class AuthenticatedPolicy:
    def __init__(self,plan):
        self.plan=plan;self.origin=plan['selection']['origin'];self.lock=threading.RLock();self.last=0;self.count=0;self.latched=False;self.terminal_case=None
        self.actors=plan.get('actorBindings',{});self.bindings_path=plan.get('actorBindingsPath');self.sessions={};self.epochs={};self.logins={};self.campaign_app_counts={};self.campaign_counts={}
    def state(self,mode):
        return self.sessions.get((mode.get('sessionGroup'),mode.get('slot','browser')))
    def request_facts(self,method,url,headers,mode):
        with self.lock:
            s=self.state(mode) or {}
            return {'actorRef':mode.get('actorRef'),'sessionGroup':mode.get('sessionGroup'),'authSlot':mode.get('slot','browser'),'identityPhase':s.get('phase','fresh'),'authEpoch':s.get('epoch'),'identityVerifiedAt':s.get('verifiedAt'),'policyLatched':self.latched,'credentialFingerprint':sha(headers.get('Authorization','').encode()) if headers.get('Authorization') else None}
    def admit(self,method,url,headers,body,mode):
        with self.lock:
            if self.bindings_path:
                current=json.loads(Path(self.bindings_path).read_bytes())
                if any(k not in current or any(current[k][f]!=a[f] for f in ('username','subject','role','provenance')) for k,a in self.actors.items()):self.latched=True;return False,'actor-binding-drift'
                self.actors=current
            self.count+=1
            if self.latched:return False,'identity-latched'
            if self.count>self.plan['limits']['maxRequests']:return False,'request-budget'
            u=urlsplit(url);base=urlsplit(self.origin);h={k.lower():v for k,v in headers.items()}
            if (u.scheme,u.netloc)!=(base.scheme,base.netloc) or u.username or u.password or u.fragment:return False,'origin'
            if h.get('host')!=base.netloc or any(h.get(k) for k in ('upgrade','transfer-encoding','proxy-authorization','x-api-key','x-auth-token','x-access-token')):return False,'host-or-protocol'
            if h.get('cookie'):return False,'cookie-auth-unqualified'
            query=parse_qsl(u.query,keep_blank_values=True)
            if len(query)!=len({k for k,v in query}):return False,'duplicate-query-key'
            candidates=[r for r in self.plan['requestPolicies'] if method==r['method'] and path_matches(r,u.path)]
            if not candidates:return False,'path-method'
            if len(body)>self.plan['limits']['maxBodyBytes']:return False,'body-budget'
            auth=self.plan['journeys']['auth'];actor=self.actors.get(mode.get('actorRef'));slot=mode.get('slot','browser');key=(mode.get('sessionGroup'),slot)
            for rule in candidates:
                names=re.findall(r'\{([A-Za-z][A-Za-z0-9]*)\}',rule['path'])
                if names:
                    owned=(actor or {}).get('ownedIds',{})
                    if any(name not in owned for name in names) or rule['path'].format_map(owned)!=u.path:continue
                if any(k not in rule.get('queryKeys',[]) or k.lower() in ('token','password','authorization','accesstoken') for k,v in parse_qsl(u.query,keep_blank_values=True)):continue
                payload=None
                if body:
                    try:payload=json.loads(body)
                    except ValueError:continue
                    if 'application/json' not in h.get('content-type','') or not valid_payload(rule,payload):continue
                elif rule.get('jsonFields') or rule.get('jsonSchema'):continue
                permissions=set(self.plan.get('authority',{}).get('permissions',[]))
                if rule['effect']=='mutation' and 'owned-mutation' not in permissions:return False,'mutation-permission'
                if mode.get('campaignId') and 'active' not in permissions:return False,'active-permission'
                if rule['phase']=='bootstrap':
                    if h.get('authorization') or not actor or mode.get('phase')!='login-pending' or not payload or payload.get(auth['usernameField'])!=actor['username']:return False,'bootstrap-binding'
                    n=self.logins.get(mode['actorRef'],0)+1
                    if n>self.plan['limits']['maxLoginsPerActor']:return False,'login-budget'
                    self.logins[mode['actorRef']]=n;epoch=self.epochs.get(key,0)+1;self.epochs[key]=epoch
                    self.sessions[key]={'phase':'login-pending','actorRef':mode['actorRef'],'epoch':epoch};return True,'admitted-bootstrap'
                if rule['phase']=='public':
                    if h.get('authorization'):return False,'credential-public-path'
                    return True,'admitted-public'
                s=self.state(mode)
                if not actor or not s or s.get('actorRef')!=mode.get('actorRef') or s['phase'] not in ('identity-verifying','authenticated'):return False,'unverified-session'
                if not h.get('authorization'):
                    if slot=='native':return False,'native-unauthenticated-control-denied'
                    self.latched=True;return False,'browser-credential-missing'
                if sha(h['authorization'].encode())!=s.get('fingerprint'):self.latched=True;return False,'unregistered-or-stale-credential'
                if s['phase']!='authenticated' and (method!='GET' or u.path!=auth['identity']['path']):return False,'identity-probe-only'
                if s['phase']=='authenticated' and __import__('time').time()-s['verifiedAt']>self.plan['limits']['identityMaxGapSeconds'] and u.path!=auth['identity']['path']:return False,'identity-monitor-gap'
                if mode.get('phase') in ('logout','lost','terminal'):return False,'terminal-session'
                if method=='GET' and u.path==auth['identity']['path']:return True,'admitted-identity-monitor'
                if mode.get('campaignId'):
                    c=next((x for x in self.plan['campaigns'] if x['id']==mode['campaignId']),None)
                    if c:
                        from .fe_authenticated_campaigns import materialize
                        try:c=materialize(c,actor.get('fixtures',actor.get('ownedIds',{})))
                        except (ValueError,KeyError):return False,'campaign-fixture-binding'
                    if not c or method!=c['method'] or not path_matches(c,u.path) or c['actorRef']!=mode['actorRef']:return False,'campaign-binding'
                    if payload is not None and any(payload.get(k)!=v for k,v in mode.get('fixedFields',{}).items()):return False,'campaign-fixed-sibling'
                    if any(dict(parse_qsl(u.query)).get(k)!=str(v) for k,v in mode.get('fixedQuery',{}).items()):return False,'campaign-fixed-query'
                    baseline=c.get('query',{}) if c['vector']=='query' else c.get('body',{})
                    candidate=dict(parse_qsl(u.query,keep_blank_values=True)) if c['vector']=='query' else payload
                    if not isinstance(candidate,dict) or set(candidate)!=set(baseline):return False,'campaign-vector-shape'
                    changed={k for k in baseline if str(candidate[k])!=str(baseline[k])}
                    if not changed<=set(c['vectorFields']):return False,'campaign-nonvector-change'
                    if h.get('x-zap-scan-id'):
                        if h['x-zap-scan-id'] not in {str(x) for x in c['ruleIds']}:return False,'campaign-rule'
                        if changed:
                            count=self.campaign_counts.get(c['id'],0)
                            if count>=c['maxDelivered']:return False,'campaign-changed-budget'
                            self.campaign_counts[c['id']]=count+1
                    n=self.campaign_app_counts.get(c['id'],0)
                    if n>=c['maxAppRequests']:return False,'campaign-app-budget'
                    self.campaign_app_counts[c['id']]=n+1
                return True,'admitted-protected'
            return False,'input-policy'
    def observe_response(self,method,url,headers,body,status,response_headers,blob,mode):
        import time
        with self.lock:
            auth=self.plan['journeys']['auth'];path=urlsplit(url).path;s=self.state(mode);facts={}
            if method=='POST' and path==auth['loginPath']:
                if status in (200,201):
                    try:token=pointer(json.loads(blob),auth['tokenPointer'])
                    except (ValueError,KeyError,IndexError,TypeError):token=None
                    if not isinstance(token,str) or not token:s['phase']='lost';self.latched=True;return {'identityFailure':'bootstrap-token-absent'}
                    s.update(phase='identity-verifying',fingerprint=sha(('Bearer '+token).encode()));facts['credentialFingerprint']=s['fingerprint']
                else:s['phase']='lost'
            elif s and path==auth['identity']['path'] and method=='GET':
                expected=self.actors[s['actorRef']]
                try:
                    value=json.loads(blob);principal=str(pointer(value,auth['identity']['subjectPointer']));role=str(pointer(value,auth['identity']['rolePointer'])) if auth['identity'].get('rolePointer') else expected['role']
                except (ValueError,KeyError,IndexError,TypeError):principal=None;role=None
                if status==200 and principal==str(expected['subject']) and role==expected['role']:
                    s.update(phase='authenticated',verifiedAt=time.time());facts.update(observedPrincipal=principal,observedRole=role,identityEvidence='protected-response',roleEvidence='protected-response' if auth['identity'].get('rolePointer') else 'independent-actor-provenance')
                else:s['phase']='lost';self.latched=True;facts.update(identityFailure='wrong-or-lost-principal',observedPrincipal=principal)
            elif s and status==401:s['phase']='lost';self.latched=True;facts['identityFailure']='protected-auth-loss'
            elif s and status==403:
                # Authorization is a product observation. Re-probe this session
                # before further business traffic; other identities are unchanged.
                s['phase']='identity-verifying'
                facts.update(authorizationDenied=True,identityRecheckRequired=True)
            if s:facts.update(identityPhaseAfter=s['phase'],authEpoch=s['epoch'])
            if any(k.lower()=='set-cookie' for k,v in response_headers):self.latched=True;facts['identityFailure']='unexpected-cookie-authority'
            return facts

if __name__=='__main__':
    import sys
    p=json.loads(Path(sys.argv[1]).read_bytes());p['actorBindingsPath']=str(Path(sys.argv[2])/'actor-bindings.json');p['actorBindings']=json.loads(Path(p['actorBindingsPath']).read_bytes())
    server=Broker(p,sys.argv[2],sys.argv[3],policy_factory=AuthenticatedPolicy)
    # Qualification-only negative TLS controls cannot enter a compiled product plan.
    if p.get('ownedControlFault'):
        if not p['selection']['environment'].startswith('fa-control-') or p['journeys']['recipe']!='reviewed-fe-auth/1.0':raise ValueError('TLS fault outside owned control')
        if p['ownedControlFault']=='tls-ca':server.upstream=__import__('ssl').create_default_context()
        elif p['ownedControlFault']=='tls-pin':server.plan['selection']['certificate']['derSha256']='0'*64
        elif p['ownedControlFault']!='tls-hostname':raise ValueError('unknown owned TLS fault')
    server.serve_forever()
