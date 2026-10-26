"""Finalsource qualification recipe. Facts come from current source/deployment/spec."""
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import ssl
import time
import urllib.error
import urllib.request
import uuid
from .discovery import canonical_hash,validate_discovery,verify_local_sources
from .anonymous import compile_plan
from .research_product import binding,observe_transport,Product,TARGET,WORKSPACE,SURFACE
from .runtime import docker


def save(root,name,value):
    p=Path(root)/name;p.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    b=value if isinstance(value,bytes) else (json.dumps(value,ensure_ascii=False,indent=2)+'\n').encode()
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(b);f.flush();os.fsync(f.fileno())
    return p


def discover(output):
    out=Path(output);out.mkdir(mode=0o700,parents=True,exist_ok=False)
    b=binding();proof=observe_transport();proof['scannerOrigins'].insert(0,'http://'+b['address']+':3000')
    save(out,'transport.json',proof)
    fmt='{"id":{{json .Id}},"image":{{json .Image}},"startedAt":{{json .State.StartedAt}},"labels":{{json .Config.Labels}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}},"mounts":{{json .Mounts}}}'
    for n in (TARGET,'finalsource-zap-test-frontend-1','finalsource-zap-test-database-1'):
        save(out,'deployment/'+n+'.json',json.loads(docker(['inspect','--format',fmt,n])))
    now=dt.datetime.now(dt.timezone.utc).isoformat();sources=[]
    def source(kind,p):
        sid='s'+str(len(sources));sources.append({'id':sid,'kind':kind,'location':str(p),'sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest(),'observedAt':now,'confidence':'high'});return sid
    deployment=source('runtime',out/'transport.json')
    for p in sorted((WORKSPACE/'finalsource').glob('*compose*')):
        if p.is_file():source('deployment',p)
    main=source('source',WORKSPACE/'finalsource/be/src/main.ts')
    proxy=source('source',WORKSPACE/'finalsource/fe/nginx.conf')
    # Direct read with the existing local certificate and hostname verification.
    ctx=ssl.create_default_context(cafile=str(WORKSPACE/'finalsource/.local-tls/localhost.crt'))
    origin=proof['directOrigins'][0]
    with urllib.request.urlopen(origin+'/docs-json',context=ctx,timeout=8) as response:
        data=response.read(1048577)
        if response.status!=200 or 'application/json' not in response.headers.get('Content-Type','') or len(data)>1048576:raise ValueError('live OpenAPI response invalid')
    spec=json.loads(data);save(out,'openapi.json',data);spec_ref=source('openapi',out/'openapi.json')
    actual={}
    # Parse literal Nest controller/method decorators only; reject unrecognized route conflicts.
    for p in sorted((WORKSPACE/'finalsource/be/src').rglob('*.controller.ts')):
        text=p.read_text();ref=source('source',p)
        controllers=list(re.finditer(r"@Controller\('([^']+)'\)",text))
        for ci,controller in enumerate(controllers):
            block=text[controller.start():controllers[ci+1].start() if ci+1<len(controllers) else len(text)]
            pre=text[text.rfind('\n}',0,controller.start())+2:controller.start()]
            base=re.match(r"@Controller\('([^']+)'\)",block)
            if not base:raise ValueError('unsupported controller prefix')
            for m in re.finditer(r"@(Get|Post|Put|Patch|Delete|Options|Head)\((?:'([^']*)')?\)",block):
                path='/api/'+base[1]+('/'+m[2] if m[2] else '')
                path=re.sub(r':([A-Za-z]\w*)',r'{\1}',path)
                actual[(m[1].upper(),path)]={'ref':ref,'protected':'@UseGuards(JwtAuthGuard)' in (pre+block)}
    ops=[];conflicts=[];fromspec=set()
    for path,verbs in spec['paths'].items():
        for verb,v in verbs.items():
            if verb.upper() not in ('GET','POST','PUT','PATCH','DELETE','HEAD','OPTIONS'):continue
            key=(verb.upper(),path);fromspec.add(key);src=actual.get(key)
            protected=bool(v.get('security',spec.get('security',[])))
            if src is None or src['protected']!=protected:conflicts.append({'description':'Source/spec route or protection disagreement: '+str(key),'blocking':True,'evidenceRefs':[spec_ref]})
            refs=[spec_ref]+([src['ref']] if src else [])
            ops.append({'id':v.get('operationId',verb+path),'method':verb.upper(),'pathTemplate':path,'protected':protected,
             'semantics':v.get('summary',str(key)),'input':{'query':[p['name'] for p in v.get('parameters',[]) if p['in']=='query'],
             'requestBody':v.get('requestBody'),'responses':v.get('responses',{}),'surface':'business'},'evidenceRefs':refs,'confidence':'high'})
    for key,v in actual.items():
        if key not in fromspec:conflicts.append({'description':'Source operation absent from live spec: '+str(key),'blocking':True,'evidenceRefs':[v['ref'],spec_ref]})
    ops += [dict(id='documentation-openapi',method='GET',pathTemplate='/docs-json',protected=False,semantics='Development OpenAPI document; documentation separate from business APIs',input={'query':[],'surface':'documentation'},evidenceRefs=[main,spec_ref],confidence='high'),
            dict(id='protocol-head-health',method='HEAD',pathTemplate='/api/health',protected=False,semantics='Express HEAD fallback for GET; probe protocol only',input={'query':[],'surface':'protocol'},evidenceRefs=[main],confidence='medium'),
            dict(id='protocol-cors-login',method='OPTIONS',pathTemplate='/api/auth/login',protected=False,semantics='Configured CORS preflight, no business execution',input={'query':[],'surface':'protocol'},evidenceRefs=[main],confidence='high')]
    # Supplement DTO/services semantics; retain pins for source drift checks.
    for p in sorted((WORKSPACE/'finalsource/be/src/modules').rglob('*.ts')):
        if p.name.endswith(('.service.ts','.dto.ts')):source('source',p)
    doc={'schemaVersion':'product-discovery/1.1','product':{'location':str(WORKSPACE/'finalsource'),'environment':'finalsource-zap-test','environmentEvidenceRefs':[deployment],
       'binding':b,'origins':[{'url':proof['scannerOrigins'][0],'role':'scanner','accessFrom':'scanner-network','authorized':True,'bindingVerified':True,'confidence':'high','evidenceRefs':[deployment]},
       {'url':origin,'role':'direct','accessFrom':'orchestrator-host','authorized':True,'bindingVerified':True,'confidence':'high','evidenceRefs':[deployment,proxy]}]},
       'sources':sources,'operations':ops,'auth':None,'fixtures':[],
       'tracks':{t:{'status':'candidate' if t=='be-anonymous' else 'not-observed','reason':'Anonymous research scope; other executors not selected','evidenceRefs':[spec_ref]} for t in ('fe-anonymous','be-anonymous','fe-authenticated','be-authenticated','bola-ownership')},
       'ui':[],'conflicts':conflicts,'gaps':[{'status':'unknown','description':'Current source pins are not source-to-running-image attestation. Live spec and traffic determine runtime claims. GraphQL/SOAP not observed.','evidenceRefs':[deployment,spec_ref]}]}
    validate_discovery(doc);save(out,'PRODUCT_DISCOVERY.json',doc)
    return doc


def authority():
    return {'environment':'finalsource-zap-test','source':'Human user instruction in chat 2026-10-21, scope section1; CONTRACT.md (record, not approval)',
      'discoveryRead':True,'active':True,'publicMutation':True,'deniedMutation':True,'fixtureSetup':True}


def admit_recipe(doc):
    """Reject recipe extensions before creating fixtures, even if setup routes exist."""
    extra={('GET','/docs-json'),('HEAD','/api/health'),('OPTIONS','/api/auth/login')}
    actual={(o['method'],o['pathTemplate']) for o in doc['operations']}
    if doc['product']['environment']!='finalsource-zap-test' or actual!=SURFACE|extra:
        raise ValueError('unsupported anonymous finalsource recipe; no mutation permitted')
    public={('GET','/api/health'),('POST','/api/auth/login'),('POST','/api/auth/register')}|extra
    if any(o['protected']!=((o['method'],o['pathTemplate']) not in public) for o in doc['operations']):
        raise ValueError('unsupported anonymous protection semantics; no mutation permitted')


def observe_login_policy():
    """Read only the three nonsecret policy settings from the selected test container."""
    code="const names=['LOGIN_MAX_ATTEMPTS','LOGIN_ATTEMPT_WINDOW_SECONDS','LOGIN_LOCKOUT_SECONDS']; process.stdout.write(JSON.stringify(Object.fromEntries(names.map(k=>[k,process.env[k]??null]))))"
    env=json.loads(docker(['exec',TARGET,'node','-e',code]))
    values={key:int(env[name] if env[name] is not None else default) for key,name,default in
            [('maxAttempts','LOGIN_MAX_ATTEMPTS',5),('attemptWindowSeconds','LOGIN_ATTEMPT_WINDOW_SECONDS',900),('lockoutSeconds','LOGIN_LOCKOUT_SECONDS',900)]}
    if not 1<=values['maxAttempts']<=20 or not all(60<=values[k]<=86400 for k in ('attemptWindowSeconds','lockoutSeconds')):
        raise ValueError('unsupported finite login policy budget')
    return {**values,'binding':binding(),'source':'selected test container: three allowlisted nonsecret settings; defaults from app.config.ts'}


def login_policy_cases(doc,email,password,policy,fixture_ref='run-data'):
    """After a successful baseline login, check finite failures then correct-password denial."""
    op=next(o for o in doc['operations'] if o['method']=='POST' and o['pathTemplate']=='/api/auth/login' and not o['protected'])
    count=policy['maxAttempts']
    if not isinstance(count,int) or not 1<=count<=20:raise ValueError('login policy count outside budget')
    expected={'statuses':[401],'contentType':'application/json','equals':{'/success':False,'/statusCode':401,'/message':'Incorrect email or password.'},'present':['/path']}
    def case(cid,pw):
        return {'id':cid,'operationId':op['id'],'method':'POST','path':'/api/auth/login','body':{'email':email,'password':pw},'category':'public-validation','fixtureRefs':[fixture_ref],'expected':expected.copy()}
    return [case('login-policy-failure-'+str(i+1),'wrong-run-policy-password') for i in range(count)]+[case('login-policy-correct-blocked',password)]


def setup(doc,out,run_id):
    """Explicit finite direct lane. No credentials/identity sent by this client to ZAP."""
    validate_discovery(doc);admit_recipe(doc);verify_local_sources(doc)
    required={('POST','/api/auth/register'),('POST','/api/auth/login'),('GET','/api/v1/accounts'),('POST','/api/v1/accounts'),('GET','/api/v1/accounts/{id}'),('DELETE','/api/v1/accounts/{id}'),('GET','/api/v1/goals'),('POST','/api/v1/goals'),('GET','/api/v1/transactions')}
    if not required<={(o['method'],o['pathTemplate']) for o in doc['operations']}:raise ValueError('unsupported fixture/oracle recipe; no mutation permitted')
    if binding()!=doc['product']['binding']:raise ValueError('binding drift before fixture setup')
    from .anonymous import transport
    proof=observe_transport();proof['scannerOrigins'].append('http://'+binding()['address']+':3000');transport(doc,binding(),proof)
    if doc['conflicts']:raise ValueError('source/spec conflicts before setup')
    if not authority()['fixtureSetup']:raise ValueError('fixture setup authority missing')
    policy=observe_login_policy()
    if policy['binding']!=doc['product']['binding']:raise ValueError('login policy binding drift before setup')
    save(out,'LOGIN_POLICY.json',policy)
    prefix=run_id+'-'+uuid.uuid4().hex[:8]
    creds={'email':prefix+'@example.test','password':'Anonymous!'+secrets.token_urlsafe(16),'fullName':prefix}
    account={'bank_name':prefix,'account_type':'Checking','branch_name':'research','account_number_full':str(secrets.randbelow(10**17)+10**17),'balance':1000}
    goal={'goal_type':'Saving','target_amount':1000,'start_date':dt.date.today().replace(day=1).isoformat(),'end_date':'2027-12-31'}
    setup_plan={'runId':run_id,'binding':doc['product']['binding'],'discoverySha256':canonical_hash(doc),'authority':authority(),'requests':[
      {'method':'POST','path':'/api/auth/register','body':{**creds,'confirm Password':creds['password']},'maxDispatch':1},
      {'method':'POST','path':'/api/v1/accounts','body':account,'maxDispatch':1},
      {'method':'POST','path':'/api/v1/goals','body':goal,'maxDispatch':1}],
      'oracleReadPaths':['/api/v1/accounts','/api/v1/accounts/{ownedId}','/api/v1/goals','/api/v1/transactions'],
      'cleanup':'DELETE own account after owner read; retain run user and goal, no API delete', 'notAfter':time.time()+1200,'retry':'no mutation retry on ambiguous ACK'}
    save(out,'SETUP_PLAN.json',setup_plan);save(out,'private/credentials-input.json',creds)
    product=Product(out,doc)
    result=product.request('POST','/api/auth/register',setup_plan['requests'][0]['body'],expected=[201],label='setup-register')
    actor={**creds,'userId':result['data']['user']['id'],'token':result['data']['token']}
    save(out,'private/actor.json',actor)
    a=product.request('POST','/api/v1/accounts',account,actor['token'],[201],'setup-account')['data']['account']
    if a['user_id']!=actor['userId']:raise ValueError('new account owner mismatch')
    g=product.request('POST','/api/v1/goals',goal,actor['token'],[201],'setup-goal')['data']['goal_id']
    fixtures={'runId':run_id,'actorId':actor['userId'],'accountId':a['id'],'goalId':g,'accountBody':account,'goalBody':goal,'lane':'direct-setup-oracle','createdByRun':True}
    save(out,'fixtures.json',fixtures)
    before=oracle(product,actor,fixtures);save(out,'poststate-before.json',before)
    return actor,fixtures,product


def oracle(product,actor,fixtures):
    result={}
    for key,path in [('accounts','/api/v1/accounts'),('account','/api/v1/accounts/'+str(fixtures['accountId'])),('goals','/api/v1/goals'),('transactions','/api/v1/transactions?type=All')]:
        result[key]=product.request('GET',path,token=actor['token'],expected=[200],label='oracle-'+key)['data']
    if result['accounts']['user_id']!=actor['userId']:raise ValueError('poststate identity mismatch')
    return result


def plan(doc,out,run_id,actor,f):
    cases=[];ops={(o['method'],o['pathTemplate']):o for o in doc['operations']}
    def case(cid,method,path,body,status,category,eq=None,present=None,template=None,headers=None):
        if category in ('public-validation','protected-denial'):
            eq={'/success':False,'/statusCode':status[0],**(eq or {})};present=['/message',*(present or [])]
        op=ops[(method,template or path)];cases.append({'id':cid,'operationId':op['id'],'method':method,'path':path,'body':body,'category':category,'fixtureRefs':['run-data'] if method not in ('GET','HEAD','OPTIONS') or '{' in op['pathTemplate'] else [],'expected':{'statuses':status,'contentType':'application/json','equals':eq or {},'present':present or []},**({'headers':headers} if headers else {})})
    case('health','GET','/api/health',None,[200],'public-success',{'/data/status':'ok'})
    case('docs','GET','/docs-json',None,[200],'documentation',present=['/paths'])
    # No HTML/JSON oracle for HEAD/OPTIONS, these are explicit protocol controls in runner.
    case('head-health','HEAD','/api/health',None,[200],'protocol-control')
    case('cors-login','OPTIONS','/api/auth/login',None,[204],'protocol-control',headers={'Origin':doc['product']['origins'][1]['url'],'Access-Control-Request-Method':'POST','Access-Control-Request-Headers':'content-type'})
    login={'email':actor['email'],'password':actor['password']}
    case('login-success','POST','/api/auth/login',login,[200],'public-success',{'/data/user/id':actor['userId']},['/data/accessToken'])
    case('login-missing','POST','/api/auth/login',{},[400],'public-validation')
    case('login-email','POST','/api/auth/login',{'email':'invalid','password':'x'},[400],'public-validation')
    case('login-boundary','POST','/api/auth/login',{'email':actor['email'],'password':'x'*73},[400],'public-validation')
    case('login-known-wrong','POST','/api/auth/login',{**login,'password':'wrong-run-password'},[401],'public-validation',{'/message':'Incorrect email or password.'})
    case('login-unknown-wrong','POST','/api/auth/login',{'email':run_id+'-absent@example.test','password':'wrong-run-password'},[401],'public-validation',{'/message':'Incorrect email or password.'})
    reg={'email':actor['email'],'fullName':actor['fullName'],'password':actor['password'],'confirm Password':actor['password']}
    case('register-duplicate','POST','/api/auth/register',reg,[409],'public-validation')
    case('register-missing','POST','/api/auth/register',{},[400],'public-validation')
    case('register-mismatch','POST','/api/auth/register',{**reg,'confirm Password':'mismatch'},[400],'public-validation')
    case('register-name-boundary','POST','/api/auth/register',{**reg,'fullName':'x'*121},[400],'public-validation')
    # Feature currently permits length1. Record observed acceptance, not a fictitious >=8 assertion.
    weak={**reg,'email':run_id+'-weak@example.test','password':'x','confirm Password':'x'}
    case('register-minimum','POST','/api/auth/register',weak,[201],'public-success',present=['/data/token','/data/user/id'])
    case('login-minimum','POST','/api/auth/login',{'email':weak['email'],'password':'x'},[200],'public-success',present=['/data/accessToken','/data/user/id'])
    cases.extend(login_policy_cases(doc,weak['email'],'x',json.loads((Path(out)/'LOGIN_POLICY.json').read_bytes())))
    for (method,path),op in ops.items():
        if not op['protected']:continue
        concrete=path.replace('{id}',str(f['accountId'])).replace('{goalId}',str(f['goalId']))
        body=None
        if method in ('POST','PUT'):
            if '/accounts' in path:body=f['accountBody']
            elif '/goals' in path:body=f['goalBody'] if method=='POST' else {'target_amount':2000}
            elif '/transactions' in path:body={'accountId':f['accountId'],'transactionDate':'2026-10-21T00:00:00Z','type':'Expense','itemDescription':run_id,'shopName':'run','amount':1,'paymentMethod':'Cash','status':'Complete'}
        case('denial-'+op['id'].lower().replace('_','-'),method,concrete,body,[401],'protected-denial',template=path)
    # Public JSON POST active tests use one synthetic absent email; no credential guessing/list.
    case('login-active-seed','POST','/api/auth/login',{'email':run_id+'-dast@example.test','password':'research-marker'},[401],'public-validation')
    activecase=next(c for c in cases if c['id']=='login-active-seed');cases.remove(activecase);cases.insert(4,activecase) # First POST node supplies baseline.
    campaigns=[{'id':'login-json','caseId':'login-active-seed','ruleIds':[40012,40018],'vectors':['JSON-body'],'mutableKeys':['password'],'maxForwarded':120,'strength':'LOW','baselineSeed':True},
               {'id':'register-json','caseId':'register-duplicate','ruleIds':[40012,40018],'vectors':['JSON-body'],'mutableKeys':['fullName'],'maxForwarded':120,'strength':'LOW','baselineSeed':True}]
    dispositions=[{'operationId':o['id'],'disposition':'protected-denial' if o['protected'] else 'public-exercise','reason':'Exact anonymous denial; business success not exercised' if o['protected'] else 'Public success/validation or explicitly separate docs/protocol control'} for o in doc['operations']]
    proof=observe_transport();proof['scannerOrigins'].append('http://'+binding()['address']+':3000')
    p=compile_plan(doc,live_binding=binding(),observed_transport=proof,run_id=run_id,cases=cases,campaigns=campaigns,authority=authority(),fixtures=[{'id':'run-data','runId':run_id,'ownership':'Fresh user subject from registration, owned account user_id verified; goal created as same actor','preparationEvidence':['fixtures.json','SETUP_PLAN.json','poststate-before.json'],'cleanup':'API DELETE owned account; retain user/goal with no delete API'}],dispositions=dispositions)
    save(out,'PLAN.json',p);save(out,'PLAN.sha256',canonical_hash(p).encode()+b'\n');return p
