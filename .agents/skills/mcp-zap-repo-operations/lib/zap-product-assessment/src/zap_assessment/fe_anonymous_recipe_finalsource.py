"""Explicit finalsource FE source recipe. All product routes/selectors/state live here."""
from pathlib import Path
import re
from .fe_anonymous_contract import digest,validate_journeys

def discover(product):
    root=Path(product).resolve();names=['fe/src/router/AppRouter.tsx','fe/src/pages/HomePage.tsx','fe/src/pages/NotFoundPage.tsx','fe/src/components/auth/LoginForm.tsx','fe/src/components/auth/SignUpForm.tsx','fe/src/context/AuthContext.tsx','fe/src/api/auth.ts','fe/src/api/httpClient.ts','fe/nginx.conf','compose.yaml','be/src/modules/auth/dto/register.dto.ts','be/src/modules/auth/auth.service.ts','be/src/modules/auth/dto/login.dto.ts','be/src/modules/auth/login-attempt-tracker.service.ts']
    # Verify actual source-supported subset before issuing selectors/expected outcomes.
    sources=[{'id':'s'+str(i),'path':str(root/n),'sha256':digest(root/n)} for i,n in enumerate(names)]
    text={n:(root/n).read_text() for n in names}
    router=text[names[0]];login=text[names[3]];register=text[names[4]];auth=text[names[5]]
    if not all(x in router for x in ["path: '/login'","path: '/register'",'ProtectedAccountListPage',"path: '*'"]):raise ValueError('recipe router subset drift')
    if not all(x in login for x in ['login-email','login-password','Incorrect email or password.']) or not all(x in register for x in ['register-name','register-email','register-confirm-password','Passwords do not match.']):raise ValueError('recipe selector/oracle drift')
    token=re.search(r"const tokenKey = '([^']+)'",auth)
    if not token:raise ValueError('recipe identity boundary unresolved')
    js=[];responsibilities=[]
    def pred(kind,selector=None,value=None,**kw):return {k:v for k,v in dict(kind=kind,selector=selector,value=value,**kw).items() if v is not None}
    def nav(path,selector):return {'action':'navigate','path':path,'predicate':pred('exists',selector)}
    def fill(selector,value=None,fixture=None):return {'action':'fill','selector':selector,**({'fixtureField':fixture} if fixture else {'value':value})}
    def submit():return {'action':'submit','selector':'button[type="submit"]'}
    def add(id,steps,expected,network=(),transition=False,prerequisites=(),prov=('s0',)):
        js.append({'id':id,'branch':id,'steps':steps,'expected':expected,'network':list(network),'transition':transition,'prerequisites':list(prerequisites),'provenance':list(prov)})
        responsibilities.append({'id':'ui-'+id,'kind':'journey/input/branch','provenance':list(prov),'journeyIds':[id],'disposition':'planned'})
    add('home-navigation',[nav('/','#starter-heading'),{'action':'click','selector':'a[href="/register"]'}],[pred('exists','#register-name')],prov=('s0','s1'))
    for path,marker in [('/','#starter-heading'),('/login','#login-email'),('/register','#register-name')]:
        add('deep-reload-'+('home' if path=='/' else path[1:]),[nav(path,marker),{'action':'reload','predicate':pred('exists',marker)}],[pred('exists',marker),pred('urlPath',value=path)])
    add('not-found',[nav('/fe-owned-missing','#not-found-heading')],[pred('text','#not-found-heading','Không tìm thấy trang')],prov=('s0','s2'))
    add('query-hash-inert',[nav('/?feInput=%3Csvg%3E#fe-owned-nonce','#starter-heading')],[pred('text','#starter-heading','Application baseline is ready')],prov=('s0','s1'))
    # Every protected literal route plus dynamic template guest behavior; no fabricated IDs.
    paths=re.findall(r"path: '([^']+)'",router)
    for path in dict.fromkeys(paths):
        if not path.startswith('/') or ':' in path or path in ('/','/login','/register'):continue
        add('guest-'+path[1:].replace('/','-'),[nav(path,'#login-email')],[pred('urlPath',value='/login'),pred('exists','#login-email')])

    add('login-empty',[nav('/login','#login-email'),submit()],[pred('text','#login-email-error','Email is required.'),pred('text','#login-password-error','Password is required.')],[{'method':'POST','path':'/api/auth/login','absent':True}],prov=('s3',))
    add('login-invalid-email',[nav('/login','#login-email'),fill('#login-email','invalid'),fill('#login-password','Owned-invalid!123'),submit()],[pred('text','#login-email-error','Enter a valid email address.')],[{'method':'POST','path':'/api/auth/login','absent':True}],prov=('s3',))
    add('login-credential-failure',[nav('/login','#login-email'),fill('#login-email',fixture='unknownEmail'),fill('#login-password',fixture='password'),submit()],[pred('text','[role="alert"]','Incorrect email or password.')],[{'method':'POST','path':'/api/auth/login','statuses':[401]}],prov=('s3','s6'))
    add('register-empty',[nav('/register','#register-name'),submit()],[pred('text','#register-name-error','Full name is required.'),pred('text','#register-email-error','Email is required.'),pred('text','#register-password-error','Password is required.'),pred('text','#register-confirm-password-error','Confirm password is required.')],[{'method':'POST','path':'/api/auth/register','absent':True}],prov=('s4',))
    def fields(email='email',password='password',confirm='password'):
        return [fill('#register-name','FE owned fixture'),fill('#register-email',fixture=email),fill('#register-password',fixture=password),fill('#register-confirm-password',fixture=confirm)]
    add('register-mismatch',[nav('/register','#register-name'),*fields(confirm='differentPassword'),submit()],[pred('text','#register-confirm-password-error','Passwords do not match.')],[{'method':'POST','path':'/api/auth/register','absent':True}],prov=('s4',))
    add('register-server-validation',[nav('/register','#register-name'),*fields(email='serverInvalidEmail'),submit()],[pred('exists','[role="alert"]')],[{'method':'POST','path':'/api/auth/register','statuses':[400]}],prov=('s4','s10'))
    add('register-success-transition',[nav('/register','#register-name'),*fields(),submit()],[pred('storagePresent',key=token[1]),pred('urlPath',value='/')],[{'method':'POST','path':'/api/auth/register','statuses':[201,200]}],True,prov=('s4','s5','s6'))
    add('register-duplicate',[nav('/register','#register-name'),*fields(),submit()],[pred('text','#register-email-error','This email is already registered.')],[{'method':'POST','path':'/api/auth/register','statuses':[409]}],prerequisites=('register-success-transition',),prov=('s4','s6'))
    add('login-success-transition',[nav('/login','#login-email'),fill('#login-email',fixture='email'),fill('#login-password',fixture='password'),submit()],[pred('storagePresent',key=token[1]),pred('urlPath',value='/')],[{'method':'POST','path':'/api/auth/login','statuses':[200]}],True,prerequisites=('register-success-transition',),prov=('s3','s5','s6'))
    add('register-invalid-email',[nav('/register','#register-name'),fill('#register-name','FE owned fixture'),fill('#register-email','invalid'),fill('#register-password',fixture='password'),fill('#register-confirm-password',fixture='password'),submit()],[pred('text','#register-email-error','Enter a valid email address.')],[{'method':'POST','path':'/api/auth/register','absent':True}],prov=('s4',))
    add('password-visibility',[nav('/register','#register-name'),fill('#register-password',fixture='password'),{'action':'click','selector':'button[aria-label="Show password"]','predicate':pred('attribute','#register-password','text',attribute='type')},{'action':'click','selector':'button[aria-label="Hide password"]'}],[pred('attribute','#register-password','password',attribute='type')],prov=('s4',))
    add('login-session-transition',[nav('/login','#login-email'),fill('#login-email',fixture='email'),fill('#login-password',fixture='password'),{'action':'click','selector':'label:has(input[type="checkbox"])'},submit()],[pred('storagePresent',key=token[1],area='session'),pred('urlPath',value='/')],[{'method':'POST','path':'/api/auth/login','statuses':[200]}],True,prerequisites=('register-success-transition',),prov=('s3','s5'))
    add('guest-owned-account-detail',[nav('/accounts/{ownedAccountId}','#login-email')],[pred('urlPath',value='/login')],prerequisites=('register-success-transition',))
    add('guest-owned-goal-edit',[nav('/goals/{ownedGoalId}/edit','#login-email')],[pred('urlPath',value='/login')],prerequisites=('register-success-transition',))
    add('public-links',[nav('/register','#register-name'),{'action':'click','selector':'a[href="/login"]'}],[pred('exists','#login-email'),pred('attribute','button[aria-disabled="true"]','true',attribute='aria-disabled'),pred('attribute','span[aria-disabled="true"]','true',attribute='aria-disabled')],prov=('s3','s4'))
    add('guest-bills-new',[nav('/bills/new','#login-email')],[pred('urlPath',value='/login'),pred('exists','#login-email')])
    for rid,reason in [('social-login','Public social button aria-disabled with no handler; no provider access'),('reset','Forgot Password is aria-disabled span; no reset route/API'),('search','Router and public pages contain no search form or consumed query input'),('csrf','Public auth uses JSON response token; no ambient session cookie authority observed; verify runtime cookies'),('cors','Same-origin public UI calls; no credentialed cross-origin read dependency admitted')]:
        responsibilities.append({'id':rid,'kind':'applicability','provenance':['s0','s3','s4','s5','s6'],'journeyIds':['public-links'] if rid in ('social-login','reset') else ['query-hash-inert'],'disposition':'not-applicable','reason':reason})
    responsibilities.extend([{'id':'native-active-public-forms','kind':'active','provenance':['s3','s4','s6'],'journeyIds':['login-credential-failure','register-server-validation','register-input-syntax','syntax-login-readback','register-name-boundary','register-password-boundary','login-email-query-syntax'],'disposition':'planned'},
      {'id':'response-policy-groups','kind':'headers/cache/CSP/mixed-content/cookie/storage','provenance':['s8'],'journeyIds':['deep-reload-home','deep-reload-login','login-credential-failure'],'disposition':'planned'}])
    syntax='<img id=fe-owned-probe src=/fe-owned-probe>O\'Brien'
    add('register-input-syntax',[nav('/register','#register-name'),fill('#register-name',syntax),fill('#register-email',fixture='syntaxEmail'),fill('#register-password',fixture='password'),fill('#register-confirm-password',fixture='password'),submit()],
        [pred('storagePresent',key=token[1]),pred('text','section[aria-labelledby="starter-heading"] p',syntax),pred('absent','#fe-owned-probe')],[{'method':'POST','path':'/api/auth/register','statuses':[201]}],True,prov=('s1','s4','s10','s11'))
    add('syntax-login-readback',[nav('/login','#login-email'),fill('#login-email',fixture='syntaxEmail'),fill('#login-password',fixture='password'),submit()],
        [pred('storagePresent',key=token[1]),pred('text','section[aria-labelledby="starter-heading"] p',syntax),pred('absent','#fe-owned-probe')],[{'method':'POST','path':'/api/auth/login','statuses':[200]}],True,prerequisites=('register-input-syntax',),prov=('s1','s3','s11'))
    add('register-name-boundary',[nav('/register','#register-name'),fill('#register-name','n'*121)],[pred('attribute','#register-name','120',attribute='maxlength'),pred('valueLength','#register-name',120)],[{'method':'POST','path':'/api/auth/register','absent':True}],prov=('s4','s10'))
    add('register-password-boundary',[nav('/register','#register-name'),fill('#register-password',fixture='longPassword'),fill('#register-confirm-password',fixture='longPassword')],[pred('attribute','#register-password','72',attribute='maxlength'),pred('valueLength','#register-password',72),pred('valueLength','#register-confirm-password',72)],[{'method':'POST','path':'/api/auth/register','absent':True}],prov=('s4','s10'))
    add('login-email-query-syntax',[nav('/login','#login-email'),fill('#login-email',fixture='quotedEmail'),fill('#login-password',fixture='password'),submit()],[pred('text','[role="alert"]','Incorrect email or password.')],[{'method':'POST','path':'/api/auth/login','statuses':[401]}],prov=('s3','s11','s12'))
    responsibilities.extend([
        {'id':'password-sql-injection','kind':'applicability','provenance':['s11','s12'],'journeyIds':['login-credential-failure'],'disposition':'not-applicable','reason':'Password flows into bcrypt.compare/hash, never query text; historical native password probes are error controls only and are not repeated as SQLi; login credential failure and owned success UI cases remain.'},
        {'id':'register-sql-sink','kind':'applicability','provenance':['s10','s11'],'journeyIds':['register-input-syntax','syntax-login-readback'],'disposition':'not-applicable','reason':'Register uses typed scalar DTO plus ORM exists/save with bound values, no dynamic SQL string; quotes/markup exercised through successful persistence and login readback. No SQL sink exploit claim.'}])
    policies=[{'method':'GET','pathRegex':'/(?!api(?:/|$)).*','queryKeys':['feInput']},{'method':'POST','pathRegex':'/api/auth/login','effect':'public-read-like','effectProvenance':['s11','s12','s13'],'jsonFields':['email','password'],'transitionResponsePointers':['/data/accessToken']},{'method':'POST','pathRegex':'/api/auth/register','jsonFields':['fullName','email','password','confirm Password'],'transitionResponsePointers':['/data/token']}]
    campaigns=[{'id':'register-native-sqli','method':'POST','path':'/api/auth/register','ruleIds':[40018],'vectorFields':['fullName'],'fixtureBody':{'fullName':'marker','email':'serverInvalidEmail','password':'password','confirm Password':'password'},'maxDelivered':4,'maxAppRequests':7,'branch':'server email validation prevents creation; not SQL sink depth'}]
    campaigns.append({'id':'login-email-native-sqli','method':'POST','path':'/api/auth/login','ruleIds':[40018],'vectorFields':['email'],'fixtureBody':{'email':'queryEmail','password':'password'},'maxDelivered':2,'maxAppRequests':4,'branch':'email query input SQLi bounded probes, valid email baseline reaches parameterized query; rejected variants count validation depth only'})
    for j in js:
        if j['id'] in ('guest-owned-account-detail','guest-owned-goal-edit'):j['setupHook']='owned-guest-route-fixtures';j['fixtureRefs']=['ownedAccountId','ownedGoalId']
    return validate_journeys({'schemaVersion':'fe-anonymous-journeys/1.0','recipe':'finalsource-fe/1.0','sources':sources,'journeys':js,'responsibilities':responsibilities,'requestPolicies':policies,'campaigns':campaigns})


def prepare_guest_fixtures(messages,send,marker,record):
    """Separate setup lane, no authenticated UI coverage and no DB access."""
    import json,secrets
    import datetime as dt
    bodies=[]
    for m in messages:
        if 'POST ' in m.get('requestHeader','') and '/api/auth/register ' in m['requestHeader'] and ' 201 ' in m.get('responseHeader',''):
            try:
                body=json.loads(m['responseBody'])
                if marker in body['data']['user']['email']:bodies.append(body['data'])
            except (ValueError,KeyError):pass
    if len(bodies)!=1:raise ValueError('owned registration identity ambiguous/missing')
    actor=bodies[0];token=actor['token'];ledger={'actor':actor,'userId':actor['user']['id']};record(ledger)
    account=send('POST','/api/v1/accounts',{'bank_name':marker,'account_type':'Checking','branch_name':'fixture','account_number_full':str(secrets.randbelow(10**15)+10**15),'balance':0},token)
    ledger['accountId']=account['data']['account']['id'];record(ledger)
    if account['data']['account']['user_id']!=actor['user']['id']:raise ValueError('created account ownership mismatch')
    month=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
    goal=send('POST','/api/v1/goals',{'goal_type':'Saving','target_amount':'500','start_date':month+'-01','end_date':month+'-28'},token)
    ledger['goalId']=goal['data']['goal_id'];record(ledger)
    # Read only own collection before using IDs; exact schema must establish ownership independently.
    accounts=send('GET','/api/v1/accounts',None,token)
    if accounts['data']['user_id']!=actor['user']['id']:raise ValueError('fixture owner read mismatch')
    account_id=ledger['accountId'];goal_id=ledger['goalId']
    if not any(a['id']==account_id for a in accounts['data']['accounts']):raise ValueError('owned account ID absent')
    return {'ownedAccountId':str(account_id),'ownedGoalId':str(goal_id)},ledger

def cleanup_guest_fixtures(ledger,send):
    token=ledger['actor']['token']
    if not ledger.get('accountId'):return {'retainedUserId':ledger['userId'],'retainedGoalId':ledger.get('goalId'),'noAccountAcknowledged':True}
    rows=send('GET','/api/v1/accounts',None,token)
    if rows['data']['user_id']!=ledger['userId'] or not any(a['id']==ledger['accountId'] for a in rows['data']['accounts']):raise ValueError('cleanup ownership unavailable')
    send('DELETE','/api/v1/accounts/'+str(ledger['accountId']),None,token)
    rows=send('GET','/api/v1/accounts',None,token)
    if any(a['id']==ledger['accountId'] for a in rows['data']['accounts']):raise ValueError('account cleanup absence failed')
    return {'accountDeleted':ledger['accountId'],'retainedUserId':ledger['userId'],'retainedGoalId':ledger.get('goalId'),'reason':'No supported user/goal DELETE API; no DB deletion'}


def prepare_fixtures(hook,messages,send,marker,record):
    if hook!='owned-guest-route-fixtures':raise ValueError('unknown recipe setup hook')
    return prepare_guest_fixtures(messages,send,marker,record)

def fixture_evidence_paths(hook):
    if hook!='owned-guest-route-fixtures':raise ValueError('unknown recipe setup hook')
    return ['/api/auth/register']

def cleanup_fixtures(ledger,send):return cleanup_guest_fixtures(ledger,send)


def public_retention(messages,marker):
    """Read acknowledged owned identities from native responses; never resubmit to reconcile."""
    import json
    rows={}
    for message in messages:
        if not message.get('requestHeader','').startswith(('POST ',)):continue
        try:
            response=json.loads(message.get('responseBody','{}'))
            user=response.get('data',{}).get('user',{})
            if marker in user.get('email','') and user.get('id'):
                key=str(user['id']);row=rows.setdefault(key,{'userId':user['id'],'email':user['email'],'nativeMessageIds':[],'retention':'retained owned test identity; no public user DELETE; no DB deletion','readback':False})
                row['nativeMessageIds'].append(str(message['id']))
                if '/api/auth/login ' in message['requestHeader'] and ' 200 ' in message['responseHeader']:row['readback']=True
        except (ValueError,TypeError,AttributeError):continue
    return list(rows.values())
