"""Finalsource research deployment/fixture adapter; no scan engine implementation."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from .research import PROFILE, WORKSPACE, PACKAGE_ROOT, ResearchRun, ZapApi, gate, digest, manifest, write_json

from .discovery import validate_discovery, compile_plan, matches, verify_identity, canonical_hash, verify_local_sources, validate_transport, execution_origin

TARGET='finalsource-zap-test-backend-1'


def registration_input(prefix, actor):
    """Fresh API fixture input; no I/O, capture or persistence."""
    credentials = {'email': prefix+'-'+actor.lower()+'@example.test',
                   'password': 'Research!'+secrets.token_urlsafe(20),
                   'fullName': prefix+' '+actor}
    return credentials, {**credentials, 'confirm Password': credentials['password']}


def account_input(marker, balance=1000):
    """The existing account fixture recipe, independent of execution/capture."""
    return {'bank_name': marker, 'account_type': 'Checking', 'branch_name': 'fixture',
            'account_number_full': str(secrets.randbelow(10**17)+10**17), 'balance': balance}


def saving_goal_input(target='500'):
    month = dt.datetime.now(dt.timezone.utc).strftime('%Y-%m')
    return {'goal_type': 'Saving', 'target_amount': target,
            'start_date': month+'-01', 'end_date': month+'-28'}
SURFACE = {('PUT', '/api/v1/accounts/{id}'), ('POST', '/api/v1/accounts'), ('GET', '/api/v1/goals'), ('DELETE', '/api/v1/accounts/{id}'), ('GET', '/api/v1/transactions'), ('GET', '/api/v1/expenses/breakdown'), ('GET', '/api/v1/accounts/options'), ('PUT', '/api/v1/goals/{goalId}'), ('GET', '/api/v1/accounts'), ('GET', '/api/v1/accounts/{id}'), ('GET', '/api/v1/savings/summary'), ('GET', '/api/v1/expenses/summary'), ('GET', '/api/v1/categories/options'), ('GET', '/api/v1/bills'), ('GET', '/api/health'), ('POST', '/api/v1/goals'), ('POST', '/api/auth/login'), ('POST', '/api/auth/register'), ('POST', '/api/v1/transactions')}


def admit_adapter(doc, target, transport=None):
    """Explicit product recipe capability, never a source of discovery answers."""
    validate_discovery(doc, executable=True)
    verify_local_sources(doc)
    if doc['product']['environment']!='finalsource-zap-test' or doc['product']['binding']!=target:
        raise ValueError('finalsource adapter target mismatch')
    if doc['schemaVersion']!='product-discovery/1.1':raise ValueError('discovery 1.1 required for execution access-point semantics')
    validate_transport(doc,target,transport if transport is not None else observe_transport())
    # This adapter's recipes have a deliberately finite supported surface.
    expected=SURFACE
    actual={(o['method'],o['pathTemplate']) for o in doc['operations']}
    if actual!=expected:raise ValueError('unsupported finalsource recipe surface; extend adapter explicitly')
    a=doc['auth'];ops={o['id']:o for o in doc['operations']}
    if (a['kind']!='json-bearer' or ops[a['loginOperationId']]['pathTemplate']!='/api/auth/login'
        or a['usernameField']!='email' or a['passwordField']!='password'
        or a['tokenPointer']!='/data/accessToken' or a['headerName']!='Authorization' or a['headerPrefix']!='Bearer '
        or ops[a['identity']['operationId']]['pathTemplate']!='/api/v1/accounts'
        or a['identity']['subjectPointer']!='/data/user_id'
        or ops[a['identity']['actorSource']['operationId']]['pathTemplate']!='/api/auth/register'
        or a['identity']['actorSource']['subjectPointer']!='/data/user/id'):
        raise ValueError('unsupported finalsource auth recipe; no fallback')
    return doc


def discovered_plan(doc,target,actors,seeds,out,transport):
    actor={'subject':str(actors['A']['userId']),'runId':out.name,'credentialRef':'private:credentials.json#actors/A',
           'sourceOperationId':doc['auth']['identity']['actorSource']['operationId'],
           'evidenceRefs':['direct/0002-response.json','credentials.json#actors/A']}
    requests=[];fixtures=[]
    for seed in seeds:
        path=urllib.parse.urlsplit(seed['path']).path
        req={'method':seed['method'],'path':path,'fixtureOwned':True}
        if seed['method'] not in ('GET','HEAD','OPTIONS'):
            ref='owned-'+str(len(fixtures))
            fs=[f for f in doc['fixtures'] if any(o['id'] in f['operationIds'] and o['method']==seed['method'] and matches(o['pathTemplate'],path) for o in doc['operations'])]
            if not fs:raise ValueError('discovery lacks adapter mutation fixture semantics')
            fixtures.append({'id':ref,'runId':out.name,'actorSubject':actor['subject'],'paths':[path],
                             'preparationEvidence':['fixtures.json','BUSINESS_ASSERTIONS.json','category-fixture/result.json'],
                             'postconditions':[v for f in fs for v in f['postconditions']]})
            req['fixtureRefs']=[ref]
        requests.append(req)
    plan=compile_plan(doc,live_binding=target,actor=actor,requests=requests,fixtures=fixtures,
        authority={'fixtureActiveAuthorized':True,'source':'user instruction 2026-10-21; authority.json'},observed_transport=transport)
    plan['parameterScope']={'query':{o['pathTemplate']:o['input'].get('query',[]) for o in doc['operations'] if o['method']=='GET'},
                            'JSONBody':'explicit finalsource recipe, owned references fixed'}
    plan['excludedVectors']=['Authorization','cookie','path-ID fuzz']
    write_json(out/'PRODUCT_DISCOVERY.json',doc)
    write_json(out/'DISCOVERY_CONSUMPTION.json',{'discoverySha256':canonical_hash(doc),'adapter':'finalsource',
        'agentSupplied':['binding','origins','inventory','auth','fixture requirements','applicability/provenance'],
        'adapterSupplied':['credential values and fresh actor subject from register','fixture recipes and concrete IDs','bounded seed/input values'],
        'noAdapterFactsCountedAsDiscovery':True})
    return plan


def docker(*args, data=None, timeout=60):
    r=subprocess.run(['docker',*map(str,args)],input=data,capture_output=True,timeout=timeout)
    if r.returncode:raise RuntimeError('Docker operation failed: '+args[0]+'; diagnostic withheld')
    return r.stdout.decode().strip()

def binding():
    value=json.loads(docker('inspect','--format',
        '{"containerId":{{json .Id}},"imageId":{{json .Image}},"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"networks":{{json .NetworkSettings.Networks}}}',TARGET))
    if value.pop('project')!='finalsource-zap-test' or value.pop('running') is not True:raise ValueError('selected test deployment unavailable')
    nets=value.pop('networks')
    if len(nets)!=1:raise ValueError('ambiguous target network')
    net=next(iter(nets.values()));value.update(networkId=net['NetworkID'],address=net['IPAddress'])
    return value

def observe_transport():
    """Read current deployment aliases/ports and actual public proxy config, no env."""
    target=binding()
    def inspect(name):
        value=json.loads(docker('inspect','--format',
            '{"id":{{json .Id}},"image":{{json .Image}},"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"networks":{{json .NetworkSettings.Networks}},"ports":{{json .NetworkSettings.Ports}}}',name))
        if value['project']!='finalsource-zap-test' or not value['running']:raise ValueError('transport ownership mismatch')
        if not any(n['NetworkID']==target['networkId'] for n in value['networks'].values()):raise ValueError('transport network mismatch')
        return value
    back=inspect(TARGET);front=inspect('finalsource-zap-test-frontend-1')
    aliases={a for n in back['networks'].values() if n['NetworkID']==target['networkId'] for a in n.get('Aliases',[]) if re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_.-]*',a)}
    proxy=docker('exec','finalsource-zap-test-frontend-1','cat','/etc/nginx/conf.d/default.conf')
    source=(WORKSPACE/'finalsource/fe/nginx.conf').read_text().strip()
    if proxy.strip()!=source:raise ValueError('proxy config differs from discovered source')
    upstreams=re.findall(r'proxy_pass\s+http://([^/:;]+):(\d+)\s*;',proxy)
    if not upstreams or any(h not in aliases or int(p)!=3000 for h,p in upstreams):raise ValueError('proxy not bound to selected backend')
    direct=[]
    for row in front['ports'].get('8443/tcp',[]) or []:
        if row['HostIp']!='127.0.0.1':raise ValueError('proxy publishing outside selected local test')
        direct.extend(['https://'+host+':'+row['HostPort'] for host in ['localhost','127.0.0.1']])
    if not direct:raise ValueError('no local proxy publication')
    return {'environment':'finalsource-zap-test','targetBinding':target,
        'scannerOrigins':sorted('http://'+a+':3000' for a in aliases),'directOrigins':direct,
        'observedAt':dt.datetime.now(dt.timezone.utc).isoformat(),
        'evidence':{'backendContainerId':back['id'],'frontendContainerId':front['id'],'frontendImageId':front['image'],
                    'frontendStartedAt':front['startedAt'],'proxyConfigSha256':hashlib.sha256(proxy.strip().encode()).hexdigest()}}


def source_pin():
    rows=[]
    for p in sorted((WORKSPACE/'finalsource/be/src').rglob('*.ts')):
        rows.append({'path':str(p.relative_to(WORKSPACE)),'sha256':digest(p)})
    return {'files':rows,'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True).encode()).hexdigest()}

class Product:
    def __init__(self,out,discovery=None):
        self.out=Path(out);self.count=0;self.cases=[];self.discovery=discovery
        self.origin=execution_origin(discovery,'direct') if discovery else 'https://localhost:8080'
        self.ssl=ssl.create_default_context(cafile=str(WORKSPACE/'finalsource/.local-tls/localhost.crt'))
    def request(self,method,path,body=None,token=None,expected=None,label=None):
        if self.discovery and path!='/docs-json' and not any(o['method']==method and matches(o['pathTemplate'],urllib.parse.urlsplit(path).path) for o in self.discovery['operations']):
            raise ValueError('direct fixture request outside discovery')
        self.count+=1
        headers={'Accept':'application/json'}
        if token:headers['Authorization']='Bearer '+token
        data=json.dumps(body).encode() if body is not None else None
        if data is not None:headers['Content-Type']='application/json'
        request=urllib.request.Request(self.origin+path,data=data,method=method,headers=headers)
        intent={'method':method,'path':path,'body':body,'label':label,'at':time.time(),'attribution':'direct-api'}
        write_json(self.out/f'direct/{self.count:04d}-intent.json',intent)
        try:response=urllib.request.urlopen(request,context=self.ssl,timeout=10)
        except urllib.error.HTTPError as e:response=e
        with response:
            blob=response.read(2*1024*1024+1);status=response.status;response_headers=dict(response.headers)
        if len(blob)>2*1024*1024:raise ValueError('oversized product response')
        try:value=json.loads(blob)
        except ValueError:value={'raw':blob.decode()}
        row={**intent,'status':status,'headers':response_headers,'response':value,
             'expected':expected,'pass':None if expected is None else status in expected}
        write_json(self.out/f'direct/{self.count:04d}-response.json',row);self.cases.append(row)
        if expected is not None and status not in expected:raise ValueError(f'case failed: {label} status={status}')
        if self.discovery and label and (label.startswith('identity-') or label=='relogin-identity'):
            who=label.split('identity-',1)[-1] if label.startswith('identity-') else 'A'
            expected_subject=self.actor_subjects[who]
            verify_identity(status,response_headers.get('Content-Type',''),value,expected_subject,self.discovery['auth']['identity']['subjectPointer'])
        return value
    def create_actors(self):
        actors={};prefix='research-'+uuid.uuid4().hex[:14]
        for actor in ('A','B'):
            c, registration = registration_input(prefix, actor)
            write_json(self.out/'credentials-input.json',{**actors,actor:c})
            result=self.request('POST','/api/auth/register',registration,expected=[201],label='register-'+actor)
            actors[actor]={**c,'userId':result['data']['user']['id'],'token':result['data']['token']}
        write_json(self.out/'credentials.json',{'actors':actors})
        self.actor_subjects={k:v['userId'] for k,v in actors.items()}
        return actors
    def business(self,actors):
        a=actors['A'];token=a['token'];created=[];seeds=[]
        def call(method,path,body=None,expected=[200],label=None):
            result=self.request(method,path,body,token,expected,label)
            seeds.append({'method':method,'path':path,'body':body,'expected':expected,'label':label})
            return result
        # Independent actor provenance comes from fresh registration; oracle is protected response.
        for key,c in actors.items():
            result=self.request('GET','/api/v1/accounts',token=c['token'],expected=[200],label='identity-'+key)
            assert result['data']['user_id']==c['userId'] and isinstance(result['data']['accounts'],list)
        self.request('GET','/api/v1/accounts',expected=[401],label='anonymous-control')
        self.request('GET','/api/v1/accounts',token='invalid-research-token',expected=[401],label='invalid-token-control')
        self.request('POST','/api/auth/login',{'email':a['email'],'password':'wrong-research-password'},expected=[401],label='invalid-login')
        login=self.request('POST','/api/auth/login',{'email':a['email'],'password':a['password']},expected=[200],label='relogin')
        assert login['data']['user']['id']==a['userId']
        relogin_identity=self.request('GET','/api/v1/accounts',token=login['data']['accessToken'],expected=[200],label='relogin-identity')
        assert relogin_identity['data']['user_id']==a['userId']
        base=account_input('research-owned')
        for i in range(3):
            result=call('POST','/api/v1/accounts',{**base,'account_number_full':str(secrets.randbelow(10**17)+10**17),'bank_name':'research-owned-'+str(i)},[201],label='account-create')
            account=result['data']['account']['id'];assert isinstance(account,int);created.append(account)
        account=created[0];active=created[1]
        detail=call('GET',f'/api/v1/accounts/{account}',label='account-detail')
        call('GET','/api/v1/accounts',label='account-list')
        call('POST','/api/v1/accounts',{},[400],label='account-missing-fields')
        call('POST','/api/v1/accounts',{**base,'balance':-1},[400],label='account-negative-balance')
        call('POST','/api/v1/accounts',{**base,'account_number_full':'x'},[400],label='account-invalid-number')
        call('GET','/api/v1/accounts/not-an-id',expected=[400],label='malformed-id')
        updated={**base,'balance':1234,'bank_name':'research-updated'}
        call('PUT',f'/api/v1/accounts/{account}',updated,label='account-update')
        post=call('GET',f'/api/v1/accounts/{account}',label='account-update-poststate')
        assert post['data']['bank_name']=='research-updated' and float(post['data']['balance'])==1234
        before=post['data']
        call('PUT',f'/api/v1/accounts/{account}',{**updated,'balance':-1},[400],label='denied-update')
        after=call('GET',f'/api/v1/accounts/{account}',label='denied-update-poststate')['data'];assert before==after
        categories=call('GET','/api/v1/categories/options',label='category-options')['data']
        call('GET','/api/v1/accounts/options',label='account-options')
        transaction_ids=[]
        if categories:
            category=categories[0]['category_id']
            transaction={'accountId':account,'transactionDate':dt.datetime.now(dt.timezone.utc).isoformat(),
                         'type':'Expense','itemDescription':'research expense','category_id':category,'shopName':'owned fixture',
                         'amount':'25','paymentMethod':'Cash','status':'Complete'}
            for kind,amount,expected_balance in [('Expense','25',1209),('Revenue','40',1249)]:
                made=call('POST','/api/v1/transactions',{**transaction,'type':kind,'amount':amount},[201],label=kind.lower()+'-create')
                transaction_ids.append(made['data']['transactionId'])
                balance=call('GET',f'/api/v1/accounts/{account}',label=kind.lower()+'-balance-poststate')['data']['balance']
                assert float(balance)==expected_balance
            before=call('GET',f'/api/v1/accounts/{account}',label='overspend-prestate')['data']
            call('POST','/api/v1/transactions',{**transaction,'amount':'999999'},[400],label='overspend-denied')
            assert call('GET',f'/api/v1/accounts/{account}',label='overspend-poststate')['data']==before

        call('GET','/api/v1/transactions?type=Expense&limit=10&offset=0',label='transaction-list')
        call('GET','/api/v1/transactions?type=Expense&limit=-1',expected=[400],label='transaction-boundary')
        call('POST','/api/v1/transactions',{},[400],label='transaction-missing-fields')
        month=dt.datetime.now(dt.timezone.utc).strftime('%Y-%m');year=month[:4]
        call('GET','/api/v1/bills',label='bill-list')
        summary=call('GET','/api/v1/expenses/summary',label='expense-summary')
        if categories:assert sum(float(x['totalExpense']) for x in summary['data']['data'])==25
        call('GET','/api/v1/transactions?type=Revenue&limit=10&offset=0',label='revenue-list')
        call('GET','/api/v1/expenses/breakdown?month='+month,expected=[200,404],label='expense-breakdown')
        call('GET','/api/v1/expenses/breakdown?month=invalid',expected=[400],label='expense-invalid-month')
        savings=call('GET','/api/v1/savings/summary?year='+year,label='savings-summary')
        if categories:assert sum(float(x['amount']) for x in savings['data']['summary']['this_year'])==15
        call('GET','/api/v1/savings/summary?year=bad',expected=[400],label='savings-invalid-year')
        call('GET','/api/v1/goals',label='goal-list')
        goal=saving_goal_input()
        gid=call('POST','/api/v1/goals',goal,[201],label='saving-goal-create')['data']['goal_id']
        call('PUT',f'/api/v1/goals/{gid}',{'target_amount':'600'},label='saving-goal-update')
        goalpost=call('GET','/api/v1/goals',label='saving-goal-poststate')['data']
        assert goalpost['savingGoal']['goal_id']==gid and float(goalpost['savingGoal']['target_amount'])==600
        if categories:
            expense_goal={**goal,'goal_type':'Expense','category_id':categories[0]['category_id'],'target_amount':'100'}
            egid=call('POST','/api/v1/goals',expense_goal,[201],label='expense-goal-create')['data']['goal_id']
            call('PUT',f'/api/v1/goals/{egid}',{'target_amount':'120'},label='expense-goal-update')
            assert any(x['goal_id']==egid and float(x['target_amount'])==120
                       for x in call('GET','/api/v1/goals',label='expense-goal-poststate')['data']['expenseGoals'])
        call('POST','/api/v1/goals',{**goal,'target_amount':'0'},[400],label='goal-zero-boundary')
        call('POST','/api/v1/goals',{**goal,'end_date':goal['start_date']},[400],label='goal-date-order')
        call('PUT',f'/api/v1/goals/{gid}',{'target_amount':'-1'},[400],label='goal-denied-update')
        assert float(call('GET','/api/v1/goals',label='goal-denied-poststate')['data']['savingGoal']['target_amount'])==600
        # Active seeds use a separate disposable account. Deletes are explicit fixture cases, not payload fuzzing.
        call('DELETE',f'/api/v1/accounts/{account}',label='account-delete')
        call('GET',f'/api/v1/accounts/{account}',expected=[404],label='account-delete-poststate')
        # Account deletion must remove exactly this fixture's transactions.
        remaining=call('GET','/api/v1/transactions?type=Expense&limit=100&offset=0',label='delete-cascade-poststate')['data']['data']
        assert not any(x['transactionId'] in transaction_ids for x in remaining)
        pending=[]
        if not categories:pending.append('expense/revenue valid mutations and Expense goal: category fixture API absent; owned DB fixture setup required')
        write_json(self.out/'fixtures.json',{'actors':{k:v['userId'] for k,v in actors.items()},'accounts':created,'activeAccount':active,'nativeDeleteAccount':created[2],'goals':[gid],'pending':pending})
        return seeds,active,gid,pending


def provision(out,jar,target,actors,discovery=None,*,native_profile=None):
    # Docker bind mounts require absolute host paths even when the CLI output is relative.
    out=Path(out).resolve();name='be-research-'+uuid.uuid4().hex[:10];zapname=name+'-zap';mcpname=name+'-mcp'
    keys={'zap':secrets.token_urlsafe(30),'mcp':secrets.token_urlsafe(30)};write_json(out/'runtime-keys.json',keys)
    config=out/'runtime';config.mkdir();os.chmod(config,0o700)
    work=config/'zap-wrk';work.mkdir();os.chmod(work,0o777)
    (config/'zap.properties').write_text('api.key='+keys['zap']+'\napi.addrs.addr.name=.*\napi.addrs.addr.regex=true\n');os.chmod(config/'zap.properties',0o600)
    profile={'id':'finalsource-research-A','kind':'json-bearer','allowed-origin':'http://backend:3000',
        'credential-reference':'file:/research/password','login-url':'http://backend:3000/api/auth/login',
        'username':actors['A']['email'],'zap-user-name':'research-A','username-json-field':'email','password-json-field':'password',
        'token-json-pointer':'/data/accessToken','header-name':'Authorization','header-prefix':'Bearer ',
        'verification-url':'http://backend:3000/api/v1/accounts','logged-in-indicator-regex':'"user_id"\\s*:',
        'logged-out-indicator-regex':'"statusCode"\\s*:\\s*401','subject-json-pointer':'/data/user_id','expected-subject':str(actors['A']['userId'])}
    if native_profile is not None:
        if not discovery:raise ValueError('generic native profile requires discovery')
        profile=dict(native_profile)
    if discovery:
        a=discovery['auth'];ops={o['id']:o for o in discovery['operations']}
        scan_origin=execution_origin(discovery,'scanner')
        profile.update({'allowed-origin':scan_origin,'login-url':scan_origin+ops[a['loginOperationId']]['pathTemplate'],
            'username-json-field':a['usernameField'],'password-json-field':a['passwordField'],
            'token-json-pointer':a['tokenPointer'],'header-name':a['headerName'],'header-prefix':a['headerPrefix'],
            **({'verification-url':scan_origin+ops[a['identity']['operationId']]['pathTemplate'],'subject-json-pointer':a['identity']['subjectPointer']} if native_profile is None else {})})
    if profile.get('signed-jwt-identity'):
        import copy
        profile=copy.deepcopy(profile);identity=profile['signed-jwt-identity'];source=Path(identity['public-key-file']);blob=source.read_bytes()
        if source.is_symlink() or hashlib.sha256(blob).hexdigest()!=identity['public-key-sha256']:raise ValueError('native signing key source drift')
        (config/'public-key.pem').write_bytes(blob);os.chmod(config/'public-key.pem',0o644);identity['public-key-file']='/research/public-key.pem'
    write_json(config/'auth.yml' ,{'zap':{'auth':{'experimental-json-bearer-enabled':True}},'mcp':{'server':{'auth':{'bootstrap':{'profiles':[profile]}}}}})
    (config/'password').write_text(actors['A']['password']);os.chmod(config/'password',0o600)
    scan_origin=profile['allowed-origin']
    env={'ZAP_API_URL':zapname,'ZAP_API_PORT':'8090','ZAP_API_KEY':keys['zap'],'MCP_API_KEY':keys['mcp'],
         'MCP_CLIENT_ID':'research','MCP_SERVER_TOOLS_SURFACE':'guided','SPRING_CONFIG_ADDITIONAL_LOCATION':'file:/research/auth.yml',
         'ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory','ZAP_SCAN_QUEUE_COORDINATOR_BACKEND':'single-node',
         'ZAP_ALLOW_PRIVATE_NETWORKS':'true','ZAP_URL_WHITELIST':urllib.parse.urlsplit(scan_origin).hostname,'ZAP_URL_BLACKLIST':'localhost,127.0.0.1,169.254.0.0/16',
         'ZAP_THREAD_PER_HOST':'1','ZAP_HOST_PER_SCAN':'1','ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1','ZAP_SPIDER_THREAD_COUNT':'1',
         'ZAP_MAX_ACTIVE_SCAN_DURATION':'2','ZAP_MAX_SPIDER_SCAN_DURATION':'1','ZAP_SPIDER_MAX_DEPTH':'2',
         'ZAP_REPORT_DIR':'/zap/wrk','ZAP_API_READ_TIMEOUT_MS':'8000','MCP_PROTECTION_RATE_LIMIT_CAPACITY':'600','MCP_PROTECTION_RATE_LIMIT_REFILL_TOKENS':'600'}
    (config/'mcp.env').write_text(''.join(k+'='+v+'\n' for k,v in env.items()));os.chmod(config/'mcp.env',0o600)
    # Build a local research derivative of the installed JVM runtime, with the freshly built JAR.
    builddir=config/'image';builddir.mkdir()
    # Reuse the exact verified immutable input bytes on one filesystem. The image
    # still copies its own pinned JAR; cross-filesystem callers retain copy behavior.
    try:os.link(jar,builddir/'app.jar')
    except OSError:shutil.copy2(jar,builddir/'app.jar')
    base=docker('inspect','--format','{{.Image}}','mcp-zap-server-mcp-server-1')
    docker('image','tag',base,name+'-runtime-base')
    (builddir/'Dockerfile').write_text('FROM '+name+'-runtime-base\nCOPY --chmod=0444 app.jar /app/app.jar\n')
    result=subprocess.run(['docker','build','--pull=false','-t',name+'-image',str(builddir)],capture_output=True,timeout=120)
    (out/'image-build.log').write_bytes(result.stdout+result.stderr)
    if result.returncode:raise RuntimeError('research image build failed')
    resources={'zap':zapname,'mcp':mcpname,'runLabel':name,'image':name+'-image','mcpImageId':docker('image','inspect','--format','{{.Id}}',name+'-image'),
               'runtimeBaseImageId':base,'jarSha256':digest(jar),'targetBinding':target}
    write_json(out/'resources.json',resources)
    os.chmod(config,0o755)
    for p in (config/'zap.properties',config/'auth.yml',config/'password'):os.chmod(p,0o644)
    # Native ZAP isolated per run. API keys supplied in mounted configuration, never command values.
    zap_id=docker('run','-d','--name',zapname,'--label','zpa.research='+name,'--network',target['networkId'],
           '-p','127.0.0.1::8090','--memory','1400m','--cpus','2','-v',str(config/'zap.properties')+':/zap/research.properties:ro','-v',str(work)+':/zap/wrk',
           'zaproxy/zap-stable:2.17.0','zap.sh','-daemon','-host','0.0.0.0','-port','8090','-configfile','/zap/research.properties')
    resources['zapContainerId']=zap_id;write_json(out/'resources.json',resources)
    docker('exec',zapname,'mkdir','-p','/zap/wrk')
    port=json.loads(docker('inspect','--format','{{json .NetworkSettings.Ports}}',zapname))['8090/tcp'][0]['HostPort']
    zap=ZapApi('http://127.0.0.1:'+port,keys['zap'],out/'raw-zap')
    deadline=time.monotonic()+90
    while True:
        try:zap.call('core','view','version');break
        except Exception:
            if time.monotonic()>deadline:raise
            time.sleep(1)
    mcp_id=docker('run','-d','--name',mcpname,'--label','zpa.research='+name,'--network',target['networkId'],
           '-p','127.0.0.1::7456','--memory','768m','--cpus','1','--env-file',config/'mcp.env',
           '-v',str(config)+':/research:ro','-v',str(work)+':/zap/wrk',name+'-image')
    resources['mcpContainerId']=mcp_id;write_json(out/'resources.json',resources)
    port=json.loads(docker('inspect','--format','{{json .NetworkSettings.Ports}}',mcpname))['7456/tcp'][0]['HostPort']
    url='http://127.0.0.1:'+port+'/mcp';deadline=time.monotonic()+90
    while True:
        try:
            client=gate.McpHttpClient(url,keys['mcp'],timeout_seconds=8);tools=client.list_tools();break
        except Exception:
            if time.monotonic()>deadline:
                (out/'mcp-startup.log').write_text(docker('logs',mcpname));raise
            time.sleep(1)
    write_json(out/'mcp-tools.json',tools)
    # Preserve actual schemas, not a tool-name checklist.
    body,_=client._post_json({'jsonrpc':'2.0','id':client._next_id(),'method':'tools/list','params':{}})
    (out/'mcp-tool-schemas.txt').write_text(body)
    resources.update(zapImageId=docker('inspect','--format','{{.Image}}',zapname),mcpUrl=url,zapUrl=zap.url)
    write_json(out/'resources.json',resources)
    client.timeout_seconds=gate.mcp_client_timeout_seconds(60)
    return resources,zap,client,gate.McpHttpClient(url,keys['mcp'],timeout_seconds=8)


def seed_as_user(zap,zapname,session,seed,out,index,origin='http://backend:3000'):
    """Native user matching + HttpSender, same public APIs as scanner; no literal bearer scaffold."""
    sid='rs'+uuid.uuid4().hex[:10];path='/zap/wrk/'+sid+'.js'
    script='''const Control=Java.type("org.parosproxy.paros.control.Control");
const Users=Java.type("org.zaproxy.zap.extension.users.ExtensionUserManagement");
const HttpMessage=Java.type("org.parosproxy.paros.network.HttpMessage");
const HttpSender=Java.type("org.parosproxy.paros.network.HttpSender");
const History=Java.type("org.parosproxy.paros.model.HistoryReference");
const Model=Java.type("org.parosproxy.paros.model.Model");
const URI=Java.type("org.apache.commons.httpclient.URI");
const Vars=Java.type("org.zaproxy.zap.extension.script.ScriptVars");
const user=Control.getSingleton().getExtensionLoader().getExtension(Users).getContextUserAuthManager(CID).getUserById(UID);
const msg=new HttpMessage(new URI(URL,false));msg.getRequestHeader().setMethod(METHOD);
if(BODY!==null){msg.getRequestHeader().setHeader("Content-Type","application/json");msg.setRequestBody(BODY);msg.getRequestHeader().setContentLength(msg.getRequestBody().length());}
user.processMessageToMatchUser(msg);const sender=new HttpSender(HttpSender.MANUAL_REQUEST_INITIATOR);sender.setUser(user);sender.sendAndReceive(msg,false);
const history=new History(Model.getSingleton().getSession(),History.TYPE_MANUAL,msg);const node=Model.getSingleton().getSession().getSiteTree().addPath(history);node.setHistoryReference(history);
Vars.setGlobalVar(KEY,JSON.stringify({status:msg.getResponseHeader().getStatusCode(),historyId:history.getHistoryId()}));
'''
    values={'CID':int(session['contextId']),'UID':int(session['userId']),'URL':origin+seed['path'],
            'METHOD':seed['method'],'BODY':None if seed.get('body') is None else json.dumps(seed['body']),'KEY':sid}
    # Declarations avoid replacing identifiers inside Java names.
    script=''.join('const '+k+'='+json.dumps(v)+';\n' for k,v in values.items())+script
    local=Path(out)/'seeds'/f'{index:03d}.js';local.parent.mkdir(exist_ok=True);local.write_text(script)
    docker('cp',local,zapname+':'+path)
    zap.call('script','action','load',scriptName=sid,scriptType='standalone',scriptEngine='Graal.js',fileName=path)
    try:
        zap.call('script','action','runStandAloneScript',scriptName=sid)
        deadline=time.monotonic()+15
        while True:
            variables=zap.call('script','view','globalVars')
            raw=variables.get('globalVars',{}).get(sid) if isinstance(variables.get('globalVars'),dict) else None
            if raw is not None:break
            # individual view gives exact completion marker without global shape assumptions.
            try:raw=zap.call('script','view','globalVar',varKey=sid).get('globalVar')
            except Exception:raw=None
            if raw is not None:break
            if time.monotonic()>deadline:raise TimeoutError('native seed completion')
            time.sleep(.1)
        return raw if isinstance(raw,dict) else json.loads(raw)
    finally:zap.call('script','action','remove',scriptName=sid)


def install_scope_guard(zap,zapname,session,plan,account,category,out):
    allowed={(op['method'],op['path']) for op in plan['operations']}
    allowed.add(('POST','/api/auth/login'))
    # All business method/path pairs must already be in the immutable plan.
    u=urllib.parse.urlsplit(plan['origin'])
    script="""const URI=Java.type('org.apache.commons.httpclient.URI');
const Vars=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
function sendingRequest(msg,initiator,helper){
 const uri=msg.getRequestHeader().getURI();
 let ok=String(uri.getScheme())===SCHEME && String(uri.getHost())===HOST && (uri.getPort()===-1?DEFAULT_PORT:uri.getPort())===PORT;
 ok=ok && ALLOWED.indexOf(msg.getRequestHeader().getMethod()+' '+uri.getPath())>=0;
 const query=String(uri.getQuery()||'');
 if(query){const names=(QUERY[String(uri.getPath())]||[]);
   for(const pair of query.split('&')){if(names.indexOf(pair.split('=')[0])<0)ok=false;}
 }
 if(ok && String(uri.getPath())==='/api/v1/transactions' && String(msg.getRequestHeader().getMethod())==='POST'){
  try{const b=JSON.parse(String(msg.getRequestBody()));
      if(b.accountId!==undefined && b.accountId!==ACCOUNT)ok=false;
      if(b.category_id!==undefined && b.category_id!==CATEGORY)ok=false;
  }catch(e){} // malformed JSON reaches DTO validation, inside this exact owned operation.
 }
 if(!ok){
  Vars.setGlobalVar('research.denied',String(Number(Vars.getGlobalVar('research.denied')||0)+1));
  msg.getRequestHeader().setURI(new URI(ORIGIN+'/__research_scope_denied__',false));
  msg.getRequestHeader().setMethod('GET');msg.setRequestBody('');msg.getRequestHeader().setContentLength(0);
 }
 msg.getRequestHeader().setHeader('Host',AUTHORITY);
}
function responseReceived(msg,initiator,helper){}
"""
    script='const SCHEME='+json.dumps(u.scheme)+';const HOST='+json.dumps(u.hostname)+';const PORT='+str(u.port or (443 if u.scheme=='https' else 80))+';const DEFAULT_PORT='+str(443 if u.scheme=='https' else 80)+';const ORIGIN='+json.dumps(plan['origin'])+';const AUTHORITY='+json.dumps(u.netloc)+';\nconst QUERY='+json.dumps(plan['parameterScope']['query'])+';\nconst ALLOWED='+json.dumps(sorted(m+' '+p for m,p in allowed))+';\nconst ACCOUNT='+str(account)+';\nconst CATEGORY='+str(category)+';\n'+script
    local=Path(out)/'scope-guard.js';local.write_text(script);docker('cp',local,zapname+':/zap/wrk/research-scope.js')
    zap.call('script','action','load',scriptName='research-scope',scriptType='httpsender',scriptEngine='Graal.js',fileName='/zap/wrk/research-scope.js')
    zap.call('script','action','enable',scriptName='research-scope')
    write_json(Path(out)/'scope-locked.json',{'allowed':sorted(m+' '+p for m,p in allowed),'scriptSha256':digest(local),
               'blockedBehavior':'rewrite to exact non-business GET /__research_scope_denied__; excluded from app attack coverage',
               'foreignFixtureReferenceFuzzing':'excluded: accountId/category_id fixed to run-owned rows'})


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['run','verify','check-expiry']);parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--discovery',type=Path,help='Frozen PRODUCT_DISCOVERY.json; requires explicit adapter')
    parser.add_argument('--adapter',choices=['finalsource'],help='Explicit recipe selection; no auto fallback')
    parser.add_argument('--jar',type=Path);parser.add_argument('--kind',choices=['fresh','interrupted'],default='fresh')
    parser.add_argument('--credentials',type=Path,help='Existing private fixture credential file, for check-expiry only')
    args=parser.parse_args(argv)
    if args.command=='verify':
        from .research import verify_manifest
        print(json.dumps(verify_manifest(args.output)));return 0
    if args.command=='check-expiry':
        if not args.credentials:parser.error('--credentials required for check-expiry')
        args.output.mkdir(mode=0o700,parents=True,exist_ok=False)
        product=Product(args.output);actor=json.loads(args.credentials.read_text())['actors']['A']
        import base64
        payload=json.loads(base64.urlsafe_b64decode(actor['token'].split('.')[1]+'=='))
        expired=time.time()>payload['exp']+1
        result=product.request('GET','/api/v1/accounts',token=actor['token'],expected=[401] if expired else [200],label='natural-expiry-check')
        if not expired and result['data']['user_id']!=actor['userId']:raise ValueError('wrong protected subject')
        write_json(args.output/'EXPIRY.json',{'expiredAtObservation':expired,'expectedExpiryUtc':dt.datetime.fromtimestamp(payload['exp'],dt.timezone.utc).isoformat(),
                   'positiveProvenance':str(args.credentials.parent/'CASES.json'),'sameTokenSha256':hashlib.sha256(actor['token'].encode()).hexdigest(),
                   'disposition':'denied-after-expiry' if expired else 'still-valid-before-expiry'})
        manifest(args.output);print('expiry observation saved');return 0
    if args.jar is None or not args.jar.is_file():parser.error('--jar requires built source JAR')
    doc=json.loads(args.discovery.read_text()) if args.discovery else None
    transport=None
    if doc is not None:
        if args.adapter!='finalsource':parser.error('--discovery requires --adapter finalsource')
        transport=observe_transport()
        admit_adapter(doc,binding(),transport)
    elif args.adapter:parser.error('--adapter requires --discovery')
    out=args.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    product=Product(out,doc);resources=None;run=None;pending=[];result={'assuranceProfile':PROFILE,'secretPersistenceAccepted':True,
        'executionStatus':'failed','evidenceStatus':'partial','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'incomplete'}
    try:
        target=binding()
        if doc:write_json(out/'TRANSPORT_BINDING.json',transport)
        write_json(out/'target-source.json',source_pin());write_json(out/'target-binding.json',target)
        for source in [Path(__file__),Path(__file__).with_name('research.py')]:
            dest=out/'runner-source'/source.name;dest.parent.mkdir(exist_ok=True);shutil.copy2(source,dest)
        spec=product.request('GET','/docs-json',expected=[200],label='openapi')
        write_json(out/'openapi.json',spec)
        inventory=[{'method':method.upper(),'path':path,'operationId':details.get('operationId')} for path,methods in spec['paths'].items()
                   for method,details in methods.items() if method in ('get','post','put','patch','delete')]
        write_json(out/'OPERATIONS.json',inventory)
        if doc and {(o['method'],o['path']) for o in inventory}!={(o['method'],o['pathTemplate']) for o in doc['operations']}:
            raise ValueError('runtime API inventory drift before fixtures')
        actors=product.create_actors()
        receipt={'environment':'finalsource-zap-test','fixtureCreationAuthorized':True,
                 'owner':'user','userRequest':'Implement R00-R09 with owned fixtures on test; current request 2026-10-21',
                 'fixtureRequest':'Create A/B owned categories using existing fixture helper; no existing-row edits'}
        write_json(out/'authority.json',receipt)
        category=subprocess.run([sys.executable,str(PACKAGE_ROOT/'scripts/prepare_finalsource_category_fixture.py'),
                                '--receipt',str(out/'authority.json'),'--credentials',str(out/'credentials.json'),
                                '--output',str(out/'category-fixture')],capture_output=True,timeout=60)
        (out/'category-fixture.log').write_bytes(category.stdout+category.stderr)
        if category.returncode:raise RuntimeError('owned category fixture setup failed; do not retry writes')
        seeds,active,gid,pending=product.business(actors)
        import base64
        jwt_payload=json.loads(base64.urlsafe_b64decode(actors['A']['token'].split('.')[1]+'=='))
        lifecycle={'identityOracle':'protected JSON /data/user_id equals independently registered fixture actor',
                   'tokenTimingDiagnostic':{'iat':jwt_payload['iat'],'exp':jwt_payload['exp'],'ttlSeconds':jwt_payload['exp']-jwt_payload['iat'],
                                           'tokenSha256':hashlib.sha256(actors['A']['token'].encode()).hexdigest()},
                   'relogin':'observed: login plus protected subject assertion',
                   'naturalExpiry':{'status':'pending','earliestVerificationUtc':dt.datetime.fromtimestamp(jwt_payload['exp']+1,dt.timezone.utc).isoformat(),
                                    'reason':'product TTL is 3600 seconds; no product TTL change or fixture substitution'},
                   'refresh':{'status':'absent','basis':'full OpenAPI + auth.controller.ts/auth.service.ts; login/register only'},
                   'serverLogoutRevoke':{'status':'absent','basis':'full source routes and JWT strategy; no revoke/session store'},
                   'roleChange':{'status':'absent','basis':'JWT strategy exposes userId; no role claim or role API'},
                   'cookieVector':{'status':'not-applicable','basis':'JWT Authorization API, no cookie session observed'}}
        write_json(out/'LIFECYCLE.json',lifecycle)
        write_json(out/'BUSINESS_ASSERTIONS.json',{'allExpectedStatuses':all(c['pass'] is not False for c in product.cases),
            'assertions':'business() asserts account update/denial, balance deltas, summaries, goals, deletion/cascade from direct protected responses; CASES.json retains observations'})
        resources,zap,client,monitor=provision(out,args.jar.resolve(),target,actors,doc)
        operations=[{'method':s['method'],'path':urllib.parse.urlsplit(s['path']).path,'fixtureOwned':True} for s in seeds]
        native_delete=json.loads((out/'fixtures.json').read_text())['nativeDeleteAccount']
        operations.extend([{'method':'DELETE','path':f'/api/v1/accounts/{native_delete}','fixtureOwned':True},
                           {'method':'GET','path':f'/api/v1/accounts/{native_delete}','fixtureOwned':True},
                           {'method':'GET','path':f'/api/v1/accounts/{active}','fixtureOwned':True},
                           {'method':'PUT','path':f'/api/v1/accounts/{active}','fixtureOwned':True}])
        plan={'assuranceProfile':PROFILE,'secretPersistenceAccepted':True,'environment':'finalsource-zap-test',
              'authority':{'fixtureActiveAuthorized':True,'source':'user instruction 2026-10-21; prior finalsource test fixture receipt'},
              'targetBinding':target,'jobStore':'in-memory','coordinator':'single-node','origin':'http://backend:3000',
              'actorSubject':str(actors['A']['userId']),'operations':operations,'ruleIds':[40012,40018],
              'parameterScope':{'query':{'/api/v1/transactions':['type','limit','offset'], '/api/v1/expenses/breakdown':['month'],
                  '/api/v1/savings/summary':['year'],'/api/v1/expenses/summary':['userId']},
                  'JSONBody':'keys from immutable seed scripts; accountId/category_id fixed to owned fixtures'},
              'vectors':['query','JSON-body'],'excludedVectors':['Authorization','cookie (JWT API has no session cookie)','path-ID fuzz (owned exact IDs only)'],
              'limits':{'monitorIntervalSeconds':2,'stopDeadlineSeconds':10,'hostReserveBytes':2*1024**3,'operationTimeoutSeconds':180}}
        safe=[]
        deleted_account=json.loads((out/'fixtures.json').read_text())['accounts'][0]
        for s in seeds:
            if s['method']=='DELETE' or s['path']==f'/api/v1/accounts/{deleted_account}':continue
            if s['method']=='GET' or s['label'] in ('account-missing-fields','account-negative-balance','transaction-missing-fields','goal-zero-boundary','goal-date-order'):
                safe.append(s)
        safe.extend([{'method':'GET','path':f'/api/v1/accounts/{active}','expected':[200]},
                     {'method':'PUT','path':f'/api/v1/accounts/{active}','body':{'bank_name':'research-active','account_type':'Checking','balance':1000},'expected':[200]}])
        category_id=json.loads((out/'category-fixture/result.json').read_text())['created'][0]['id']
        mutation_seeds=[
            {'method':'POST','path':'/api/v1/accounts','body':{'bank_name':'active-owned','account_type':'Checking',
             'account_number_full':str(secrets.randbelow(10**17)+10**17),'balance':1000},'expected':[201]},
            {'method':'POST','path':'/api/v1/transactions','body':{'accountId':active,'category_id':category_id,
             'transactionDate':dt.datetime.now(dt.timezone.utc).isoformat(),'type':'Revenue','amount':'1',
             'itemDescription':'active owned seed','shopName':'research','paymentMethod':'Cash','status':'Complete'},'expected':[201]},
            {'method':'POST','path':'/api/v1/goals','body':{'goal_type':'Saving','target_amount':'500',
             'start_date':dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-01'),'end_date':dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-28')},'expected':[201]},
            {'method':'PUT','path':f'/api/v1/accounts/{active}','body':{'bank_name':'active-owned','account_type':'Checking','balance':1000},'expected':[200]},
            {'method':'PUT','path':f'/api/v1/goals/{gid}','body':{'target_amount':'600'},'expected':[200]}]
        safe.extend(mutation_seeds)
        safe.extend([{'method':'DELETE','path':f'/api/v1/accounts/{native_delete}','expected':[200],'label':'native-owned-delete'},
                     {'method':'GET','path':f'/api/v1/accounts/{native_delete}','expected':[404],'label':'native-delete-poststate'}])
        targets=[plan['origin']+'/api/v1/transactions?type=Expense&limit=10&offset=0',plan['origin']+'/api/v1/accounts',
                 plan['origin']+f'/api/v1/accounts/{active}',plan['origin']+'/api/v1/goals']
        if doc:
            plan=discovered_plan(doc,target,actors,[{'method':o['method'],'path':o['path']} for o in operations],out,transport)
            plan['execution']={'seeds':safe,'crawl':plan['identityPath'],
                'attacks':[{'method':'GET','path':urllib.parse.urlsplit(u).path+('?' + urllib.parse.urlsplit(u).query if urllib.parse.urlsplit(u).query else '')} for u in targets]+
                          [{'method':m['method'],'path':m['path'],'body':m['body']} for m in mutation_seeds]}
            from .discovery import validate_plan
            validate_plan(plan,target)
            safe=plan['execution']['seeds']
        run=ResearchRun(plan=plan,binding=binding,client=client,monitor_client=monitor,zap=zap,output=out/'mcp-run')
        prepared=run.prepare('finalsource-research-A')
        session={'contextId':next(x.split(': ',1)[1] for x in prepared.splitlines() if x.startswith('Context ID: ')),
                 'userId':next(x.split(': ',1)[1] for x in prepared.splitlines() if x.startswith('User ID: '))}
        write_json(out/'session-binding.json',{'authSessionId':run.session,**session})
        if doc:
            native_controls=[]
            for label,credential in [('anonymous',None),('invalid','invalid-research-token')]:
                request='GET '+plan['origin']+plan['identityPath']+' HTTP/1.1\r\nHost: '+urllib.parse.urlsplit(plan['origin']).netloc+'\r\nAccept: application/json\r\n'
                if credential:request+='Authorization: Bearer '+credential+'\r\n'
                response=zap.call('core','action','sendRequest',request=request+'\r\n',followRedirects='false')
                write_json(out/('native-'+label+'-control.json'),response)
                msgs=response.get('sendRequest',[])
                if isinstance(msgs,dict):msgs=[msgs]
                if not msgs or not all(re.match(r'HTTP/\S+ 401 ',m.get('responseHeader','')) for m in msgs):
                    raise ValueError('native anonymous/invalid control not denied')
                native_controls.append({'kind':label,'denied':True,'evidence':'native-'+label+'-control.json'})
            write_json(out/'NATIVE_CONTROLS.json',native_controls)
        # Pin native engine/add-ons/rules before attack.
        write_json(out/'addons.json',zap.call('autoupdate','view','installedAddons'))
        zap.call('ascan','action','addScanPolicy',scanPolicyName='research-selected',alertThreshold='MEDIUM',attackStrength='LOW')
        zap.call('ascan','action','disableAllScanners',scanPolicyName='research-selected')
        zap.call('ascan','action','enableScanners',ids='40012,40018',scanPolicyName='research-selected')
        write_json(out/'rules.json',zap.call('ascan','view','scanners',scanPolicyName='research-selected'))
        zap.call('ascan','action','setOptionPersistTemporaryMessages',Boolean='true')
        zap.call('ascan','action','setOptionTargetParamsInjectable',Integer=3)
        write_json(out/'vector-options.json',zap.call('ascan','view','optionTargetParamsEnabledRPC'))
        # Restrict context to declared paths; login and identity are explicit operational exceptions.
        paths=sorted({op['path'] for op in plan['operations']}|{'/api/auth/login',plan.get('identityPath','/api/v1/accounts')})
        regex='\\A'+re.escape(plan['origin'])+'(?:'+ '|'.join(re.escape(p) for p in paths)+')(?:\\?.*)?\\z'
        zap.call('context','action','setContextRegexs',contextName='finalsource-research-A-auth',incRegexs=json.dumps([regex]),excRegexs='[]')
        # Seed extant operations through the prepared native user. Destructive cases were asserted directly;
        # replay only fresh fixture-owned variants, never a deleted ID or ambiguous mutation.
        install_scope_guard(zap,resources['zap'],session,plan,active,category_id,out)
        for i,s in enumerate(safe):
            run.current();observed=seed_as_user(zap,resources['zap'],session,s,out,i,plan['origin'])
            write_json(out/'seeds'/f'{i:03d}-result.json',{'seed':s,'observed':observed})
            if observed['status'] not in s['expected']:raise ValueError('native seed did not exercise expected protected operation')
        crawl=run.start('crawl',plan['origin']+plan.get('identityPath','/api/v1/accounts'),strategy='http');run.wait(crawl)
        actions=plan['execution']['attacks'] if doc else ([{'method':'GET','path':urllib.parse.urlsplit(u).path+('?' + urllib.parse.urlsplit(u).query if urllib.parse.urlsplit(u).query else '')} for u in targets]+mutation_seeds)
        for action in actions:
            kwargs={'recurse':'false','policy':'research-selected'}
            if action['method']!='GET':kwargs.update(method=action['method'],postData=json.dumps(action.get('body')))
            attack=run.start('attack',plan['origin']+action['path'],**kwargs)
            run.wait(attack,interrupt_after=0 if args.kind=='interrupted' else None)
            if args.kind=='interrupted':break
        if not run.validate(client):raise RuntimeError('final protected identity lost')
        passive=run.tool('zap_passive_scan_wait',{'timeoutSeconds':60,'pollIntervalMs':1000})
        if 'timed out' in passive.lower():raise RuntimeError('passive backlog not settled')
        for fmt in ('html','json'):
            response=run.tool('zap_report_generate',{'baseUrl':plan['origin'],'format':fmt})
            path=next(line.split(': ',1)[1] for line in response.splitlines() if line.startswith('Path: '))
            dest=out/('report.'+fmt);docker('cp',resources['mcp']+':'+path,dest)
            if fmt=='json':json.loads(dest.read_bytes())
            elif '</html>' not in dest.read_text().lower():raise ValueError('truncated HTML report')
        write_json(out/'ALERTS.json',zap.call('core','view','alerts',baseurl=plan['origin'],start=0,count=10000))
        active_messages=[];active_index=[]
        for operation in run.operations:
            if operation['kind']!='attack':continue
            scan=operation['nativeScanId']
            ids_response=zap.call('ascan','view','messagesIds',scanId=scan)
            ids=ids_response.get('messagesIds',[])
            active_index.append({'scanId':scan,'messageIds':ids,'progress':zap.call('ascan','view','scanProgress',scanId=scan)})
            for chunk in range(0,len(ids),100):
                messages=zap.call('core','view','messagesById',ids=','.join(map(str,ids[chunk:chunk+100])))
                active_messages.extend(messages.get('messagesById',messages.get('messages',[])))
        write_json(out/'raw-active-messages.json',active_messages)
        write_json(out/'active-message-index.json',active_index)
        actual_rules=set()
        def collect_plugins(node):
            if isinstance(node,dict):
                if 'Plugin' in node and len(node['Plugin'])>1:actual_rules.add(int(node['Plugin'][1]))
                for child in node.values():collect_plugins(child)
            elif isinstance(node,list):
                for child in node:collect_plugins(child)
        collect_plugins(active_index)
        write_json(out/'actual-rule-disposition.json',{'planned':plan['ruleIds'],'observed':sorted(actual_rules),
                    'unexpected':sorted(actual_rules-set(plan['ruleIds']))})
        if doc and actual_rules!=set(plan['ruleIds']):raise ValueError('selected native rules not all observed')
        if actual_rules-set(plan['ruleIds']):raise ValueError('active scanner executed unexpected rule IDs')
        write_json(out/'active-message-index.json',active_index)
        write_json(out/'raw-active-messages.json',active_messages)

        history=[];offset=0
        while True:
            batch=zap.call('core','view','messages',baseurl=plan['origin'],start=offset,count=500)['messages'];history.extend(batch)
            if len(batch)<500:break
            offset+=len(batch)
        write_json(out/'raw-history.json',history)
        protected_active=[m for m in active_messages if 'Authorization: Bearer ' in m['requestHeader']
                          and re.match(r'HTTP/\S+ 2\d\d ',m['responseHeader'])]
        protected=[m for m in history if 'Authorization: Bearer ' in m['requestHeader'] and re.match(r'HTTP/\S+ 2\d\d ',m['responseHeader'])]
        write_json(out/'COVERAGE.json',{'protectedZapResponsesMeasured':len(protected),'totalZapHistoryRecords':len(history),
            'directApiRequests':product.count,'activeScanMessagesMeasured':len(active_messages),
            'activeProtected2xxMeasured':len(protected_active),'activeMethodCounts':{method:sum(m['requestHeader'].startswith(method+' ') for m in active_messages) for method in ['GET','POST','PUT','DELETE']},
            'basis':'full native history readback; 2xx+Authorization, identity sampled separately',
            'methods':{method:sum(m['requestHeader'].startswith(method+' ') for m in protected) for method in ['GET','POST','PUT','DELETE']},
            'pending':pending,'inFlightAccounting':'history timestamps, auth samples and stop ACKs retained; no zero-inflight assertion'})
        if not protected:raise ValueError('no protected native traffic')
        if args.kind!='interrupted' and not active_messages:raise ValueError('native active request attribution missing')
        if args.kind=='interrupted' and not run.stop_records:raise RuntimeError('interruption not observed before scan completed')
        if args.kind=='fresh' and doc is None:
            run.finish()
            docker('restart','--time','10',resources['mcp'])
            restarted_port=json.loads(docker('inspect','--format','{{json .NetworkSettings.Ports}}',resources['mcp']))['7456/tcp'][0]['HostPort']
            resources['mcpUrlAfterRestart']='http://127.0.0.1:'+restarted_port+'/mcp'
            write_json(out/'resources.json',resources)
            keys=json.loads((out/'runtime-keys.json').read_text())
            deadline=time.monotonic()+60
            while True:
                try:
                    restarted=gate.McpHttpClient(resources['mcpUrlAfterRestart'],keys['mcp'],timeout_seconds=8)
                    restarted.list_tools();break
                except Exception:
                    if time.monotonic()>deadline:raise
                    time.sleep(1)
            old_rejected=False
            try:old_validation=restarted.call_tool('zap_auth_session_validate',{'sessionId':run.session})
            except RuntimeError as e:
                old_rejected='Unknown auth session ID' in str(e);old_validation=str(e)
            if not old_rejected:raise ValueError('old auth handle was not rejected after restart')
            new_prepared=restarted.call_tool('zap_auth_session_prepare',{'profileId':'finalsource-research-A','targetUrl':plan['origin']+'/api/v1/accounts'})
            new_sid=next(line.split(': ',1)[1] for line in new_prepared.splitlines() if line.startswith('Session ID: '))
            new_validation=restarted.call_tool('zap_auth_session_validate',{'sessionId':new_sid})
            if new_sid==run.session or 'Valid: true' not in new_validation:raise ValueError('fresh post-restart validation failed')
            write_json(out/'restart-control.json',{'oldHandleRejected':old_rejected,'oldResult':old_validation,
                       'newHandleDifferent':True,'prepared':new_prepared,'validation':new_validation,'targetRestarted':False})

        result.update(executionStatus='interrupted' if args.kind=='interrupted' else 'completed',evidenceStatus='complete',
                      securityVerdict='requires-triage',gateDecision='partial-functional-coverage')
    except Exception as e:
        import traceback
        (out/'failure-trace.txt').write_text(traceback.format_exc())
        result.update(errorType=type(e).__name__,error=str(e));write_json(out/'failure.json',result)
    finally:
        if run:result['orchestration']=run.finish()
        write_json(out/'CASES.json',product.cases)
        if resources is None and (out/'resources.json').exists():resources=json.loads((out/'resources.json').read_text())
        if resources:
            cleanup=[]
            for name in [resources['mcp'],resources['zap']]:
                try:
                    (out/(name+'-logs.txt')).write_text(docker('logs',name))
                    label=docker('inspect','--format','{{index .Config.Labels "zpa.research"}}',name)
                    if label!=resources['runLabel']:raise ValueError('cleanup ownership mismatch')
                    docker('stop','--time','10',name);docker('rm',name);cleanup.append({'resource':name,'removed':True})
                except Exception as e:cleanup.append({'resource':name,'removed':False,'error':type(e).__name__})
            result['cleanupStatus']='runtime-removed-fixtures-retained' if all(r['removed'] for r in cleanup) else 'partial'
            write_json(out/'CLEANUP.json',{'resources':cleanup,'fixtures':'retained; no arbitrary user or database deletion'})
        write_json(out/'RUN.json',result);manifest(out)
    print(json.dumps({k:v for k,v in result.items() if k!='orchestration'},ensure_ascii=False))
    return 0 if result['executionStatus'] in ('completed','interrupted') else 1
