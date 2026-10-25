#!/usr/bin/env python3
"""Explicitly authorized local finalsource P0 pilot; separate from v1.4 read-only BOLA.

Creates only run-prefixed fixture accounts and saving goals through application
APIs. All scanner traffic crosses a method/path guard. Borrowed app containers
are inspected only, never exec'd, restarted or removed. Output must be new.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time
import uuid
from urllib.parse import urlencode

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from zap_assessment.runtime import DockerRuntime, docker, ZAP, MCP_IMAGE
from zap_assessment.journal import Journal
from zap_assessment.transport import MCP, field
from zap_assessment.contracts import Blocked
from zap_assessment.capabilities import require_p0_mode

ORIGIN='http://127.0.0.1:18080'

def sha(b): return hashlib.sha256(b).hexdigest()
def raw(j): return json.dumps(j,ensure_ascii=False,indent=2).encode()+b'\n'
def write(p,j):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('xb') as f:f.write(j if isinstance(j,bytes) else raw(j))
    p.chmod(0o600)

def metadata(name):
    fmt='{"id":{{json .Id}},"image":{{json .Image}},"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},"networks":{{json .NetworkSettings.Networks}},"project":{{json (index .Config.Labels "com.docker.compose.project")}}}'
    d=json.loads(docker(['inspect','--format',fmt,name]));ns=list(d.pop('networks').values())
    if len(ns)!=1 or not d['running'] or d['project']!='finalsource-zap-test':raise ValueError('borrowed binding')
    return d|{'networkId':ns[0]['NetworkID'],'address':ns[0]['IPAddress']}

class Pilot(DockerRuntime):
    def __init__(self,out,actor,mode,credentials,accounts,business=False,category_fixture=None):
        require_p0_mode(mode)
        out.mkdir(mode=0o700)
        self.actor=actor;self.mode=mode;self.business=business;self.front=metadata('finalsource-zap-test-frontend-1');self.back=metadata('finalsource-zap-test-backend-1')
        run='p0-'+uuid.uuid4().hex[:12]
        self.plan={'runId':run,'actor':actor,'mode':mode,'front':self.front,'back':self.back,
                   'mirror':ORIGIN,'canonicalFrontend':'https://'+self.front['address']+':8443',
                   'notAfter':time.time()+2400,'fixturePrefix':run,'retention':'30 days; no automatic deletion',
                   'limits':{'rps':2,'clientMinutes':1,'activeMinutes':1,'activeRules':['40012','40018']},
                   'sourceSha256':sha(Path(__file__).read_bytes()),'guardSha256':sha((ROOT/'scripts/finalsource_p0_guard.py').read_bytes()),
                   'images':{'zap':ZAP,'mcp':MCP_IMAGE}}
        write(out/'plan.json',self.plan)
        write(out/'source/runner.py',Path(__file__).read_bytes())
        write(out/'source/guard.py',(ROOT/'scripts/finalsource_p0_guard.py').read_bytes())
        journal=Journal(out/'journal.jsonl',run,sha(raw(self.plan)))
        super().__init__(run,out,journal)
        self.names=[f'zpa-{run}-{x}' for x in ('net','guard','zap','mcp')];self.anchor=self.names[0]
        self.calls=0;self.tools=0;self.credentials=credentials;self.initial_accounts=accounts
        self.category_fixture=category_fixture
        self.completed=[]

    def binding(self):
        if metadata('finalsource-zap-test-frontend-1')!=self.front or metadata('finalsource-zap-test-backend-1')!=self.back:
            raise ValueError('borrowed target drift')

    def provision(self):
        require_p0_mode(self.mode)
        b=json.loads((ROOT/'profiles/runtime-baseline.json').read_text())
        wrk=self.root/'workspace';wrk.mkdir(mode=0o777);wrk.chmod(0o777)
        ev=self.root/'guard';ev.mkdir(mode=0o777);ev.chmod(0o777)
        cfg=self.root/'private';cfg.mkdir(mode=0o700);cfg.chmod(0o755)
        credentials=json.loads(self.credentials.read_text())
        actors={'A','B'} if self.business else {self.actor}
        if self.mode=='native' and self.actor=='A' and 'W' in credentials['actors']:actors.add('W')
        credentials['actors']={k:v for k,v in credentials['actors'].items() if k in actors}
        write(cfg/'credentials.json',credentials);(cfg/'credentials.json').chmod(0o444)
        write(self.root/'credential-isolation.json',{'resolvedActors':sorted(actors),'scannerCredentialMount':False,
              'guardCredentialMount':'private/credentials.json','scannerActor':self.actor,'mode':self.mode})
        conf={'frontendAddress':self.front['address'],'credentials':'/config/credentials.json','mode':self.mode,
              'actor':self.actor,'notAfter':self.plan['notAfter'],'accounts':self.initial_accounts,'fixturePrefix':self.run_id}
        if self.category_fixture:
            categories=json.loads(self.category_fixture.read_text())['created']
            for row in categories:
                if row['user_id']!=credentials['actors'][row['actor']]['userId']:raise ValueError('category ownership manifest')
            conf['categories']={r['actor']:r['id'] for r in categories}
            write(self.root/'category-fixture.json',{'categories':categories,'sourceSha256':sha(self.category_fixture.read_bytes())})
        write(cfg/'guard.json',conf);(cfg/'guard.json').chmod(0o444)
        self.commands={self.anchor:['sleep','3000'],self.names[1]:['python','/guard.py','/config/guard.json'],
            self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=true',
                '-config','autoupdate.checkOnStart=false','-config','spider.processForm=false','-config','spider.postForm=false',
                '-config','connection.timeoutInSecs=8'],self.names[3]:[]}
        self.create(self.anchor,b['boundary'],['--no-healthcheck','--network',self.front['networkId'],'--cap-add','NET_ADMIN'])
        rules=['iptables -P OUTPUT DROP','iptables -P INPUT DROP','iptables -P FORWARD DROP',
            'ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP','iptables -A INPUT -i lo -j ACCEPT',
            'iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
            'iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
            'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 18081,7456 -m owner --uid-owner 1000 -j REJECT',
            'iptables -A OUTPUT -o lo -m owner --uid-owner 1000 -j ACCEPT',
            'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT',
            'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090,18080,18081 -m owner --uid-owner 1002 -j ACCEPT',
            f'iptables -A OUTPUT -p tcp -d {self.front["address"]} --dport 8443 -m owner --uid-owner 1003 -j ACCEPT']
        for rule in rules:docker(['exec',self.anchor,*rule.split()])
        write(self.root/'firewall.json',{'ipv4':docker(['exec',self.anchor,'iptables-save']),'ipv6':docker(['exec',self.anchor,'ip6tables-save'])})
        shared=['--no-healthcheck','--network','container:'+self.anchor,'--cap-drop','ALL','--security-opt','no-new-privileges']
        self.create(self.names[1],b['boundary'],[*shared,'--user','1003:1003','--memory','192m',
            '-v',str(ROOT/'scripts/finalsource_p0_guard.py')+':/guard.py:ro','-v',str(cfg)+':/config:ro','-v',str(ev)+':/evidence'])
        self.create(self.names[2],ZAP,[*shared,'--user','1000:1000','--memory','2048m','--shm-size','512m','--cpus','2',
            '-e','ZAP_MEMORY=1024m','-v',str(wrk)+':/zap/wrk'])
        env={'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'none','MCP_SECURITY_ENABLED':'false',
            'ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':'','ZAP_REPORT_DIRECTORY':'/zap/wrk',
            'ZAP_ALLOW_LOCALHOST':'true','ZAP_ALLOW_PRIVATE_NETWORKS':'true','MCP_SERVER_TOOLS_SURFACE':'expert',
            'ZAP_SPIDER_THREAD_COUNT':'1','ZAP_MAX_SPIDER_SCAN_DURATION':'1','ZAP_SPIDER_MAX_DEPTH':'2',
            'ZAP_MAX_ACTIVE_SCAN_DURATION':'1','ZAP_THREAD_PER_HOST':'1','ZAP_HOST_PER_SCAN':'1',
            'JAVA_TOOL_OPTIONS':'-Xmx384m','ZAP_INIT_CONNECTION_TIMEOUT':'90'}
        opts=[*shared,'--user','1001:1000','--memory','512m','-v',str(wrk)+':/zap/wrk']
        for k,v in env.items():opts+=['-e',k+'='+v]
        self.create(self.names[3],MCP_IMAGE,opts)
        write(self.root/'runtime.json',[{'name':n,'id':self.check_owner(n)['Id'],'image':self.check_owner(n)['Image']} for n in self.names])

    def engine(self,component,kind,name,args=None):
        self.binding();self.calls+=1
        args=args or {};label=f'{self.calls:04d}-{component}-{name}'
        write(self.root/'engine'/f'{label}-request.json',{'component':component,'kind':kind,'name':name,'arguments':args,'at':time.time()})
        # Standalone UI journey is synchronous and has eight deliberate page waits.
        r=self.request(f'http://127.0.0.1:8090/JSON/{component}/{kind}/{name}/?'+urlencode(args),timeout=180 if name=='runStandAloneScript' else 90 if name=='authenticateAsUser' else 20)
        write(self.root/'engine'/f'{label}-response.json',r)
        j=json.loads(r['body'])
        if r['status']!=200 or 'code' in j:raise ValueError('engine rejected '+name+': '+str(j)[:300])
        return j

    def control(self,x,label):
        r=self.request('http://127.0.0.1:18081/control','POST',{'Content-Type':'application/json'},raw(x),timeout=15)
        j=json.loads(r['body']);write(self.root/'controls'/f'{label}.json',{'request':x,'response':j,'transportStatus':r['status'],'at':time.time()})
        if r['status']!=200:raise ValueError('control rejected '+label)
        return j

    def tool(self,name,args):
        from jsonschema import Draft202012Validator
        Draft202012Validator(self.mcp.contracts[name]).validate(args)
        self.tools+=1;label=f'{self.tools:04d}-{name}'
        write(self.root/'tools'/f'{label}-request.json',{'name':name,'arguments':args,'at':time.time()})
        r=self.mcp.rpc('tools/call',{'name':name,'arguments':args});write(self.root/'tools'/f'{label}-response.json',r)
        if r.get('isError'):raise ValueError('tool error '+name)
        s='\n'.join(v['text'] for v in r.get('content',[]) if v.get('type')=='text')
        return json.loads(s) if s.startswith('"') else s

    def script(self,name,source):
        write(self.root/'workspace'/f'{name}.js',source.encode());os.chmod(self.root/'workspace'/f'{name}.js',0o644)
        self.engine('script','action','load',{'scriptName':name,'scriptType':'standalone','scriptEngine':'Graal.js','fileName':'/zap/wrk/'+name+'.js'})
        self.engine('script','action','runStandAloneScript',{'scriptName':name})
        deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            v=self.engine('script','view','globalVars')
            if 'p0.result' in v.get('globalVars',{}):
                result=v['globalVars']['p0.result']
                return json.loads(result) if isinstance(result,str) else result
            time.sleep(2)
        write(self.root/'script-diagnostics.json',self.engine('script','view','listScripts'));raise TimeoutError('browser journey')

    def seed(self,path,label):
        j=self.engine('core','action','sendRequest',{'request':f'GET {ORIGIN}{path} HTTP/1.1\r\nHost: 127.0.0.1:18080\r\nConnection: close\r\n\r\n','followRedirects':'false'})
        write(self.root/'http'/f'{label}.json',j);return j

    def settle(self):
        observations=[];deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            j=self.engine('pscan','view','recordsToScan');observations.append({'at':time.time(),**j})
            if len(observations)>1 and all(str(o['recordsToScan'])=='0' for o in observations[-2:]):
                write(self.root/'passive-settle.json',observations);return
            time.sleep(2)
        write(self.root/'passive-settle.json',observations);raise TimeoutError('passive settle')

    def reports(self):
        for fmt in ('json','html'):
            s=self.tool('zap_report_generate',{'baseUrl':ORIGIN,'format':fmt});path=field(s,'Path')
            chunks=[];pages=[];offset=0;expected=None
            for _ in range(300):
                a={'reportPath':path,'offset':offset,'maxChars':120000}
                if expected:a['expectedSha256']=expected
                j=json.loads(self.tool('zap_report_read_chunk',a));expected=expected or j['artifactSha256']
                if j['artifactSha256']!=expected:raise ValueError('report changed')
                chunks.append(j['content']);pages.append({k:v for k,v in j.items() if k!='content'})
                if j['endOfFile']:break
                if j['nextOffset']<=offset:raise ValueError('offset')
                offset=j['nextOffset']
            else:raise ValueError('report page budget')
            content=''.join(chunks).encode()
            if sha(content)!=expected:raise ValueError('report readback')
            write(self.root/'reports'/('report.'+fmt),content);write(self.root/'reports'/(fmt+'-readback.json'),{'sha256':expected,'bytes':len(content),'pages':pages})

    def execute(self,business=False):
        require_p0_mode(self.mode)
        outcome={'executionStatus':'running','evidenceStatus':'incomplete','cleanupStatus':'pending','mode':self.mode}
        try:
            self.provision();self.wait_health(180);self.mcp=MCP(self.request);write(self.root/'mcp-discovery.json',self.mcp.initialize())
            write(self.root/'scanner.json',{'version':self.engine('core','view','version'),'addons':self.engine('autoupdate','view','installedAddons')})
            #10116 checks the scanner's online update service, not the application.
            # In a deny-egress pinned runner it waited60s per response (retained a4 log).
            # Disable only that self-update check; retain all application passive rules.
            passive=self.engine('pscan','view','scanners')
            update=[r for r in passive['scanners'] if r['id']=='10116']
            if len(update)!=1 or update[0]['name']!='ZAP is Out of Date':raise ValueError('passive rule identity drift')
            self.engine('pscan','action','disableScanners',{'ids':'10116'})
            self.engine('network','action','setConnectionTimeout',{'timeout':8})
            write(self.root/'passive-policy.json',{'disabled':update,'reason':'scanner self-update requires forbidden internet; version/addons pinned separately',
                  'readback':self.engine('pscan','view','scanners'),'targetConnectionTimeoutSeconds':8})
            code="""import socket,json
checks={}
for name,host,port in json.loads(__import__('sys').stdin.read()):
 s=socket.socket();s.settimeout(.3)
 try:checks[name]=s.connect_ex((host,port))
 except OSError:checks[name]=-1
 finally:s.close()
print(json.dumps(checks))
"""
            probes=[['mirror','127.0.0.1',18080],['privateControl','127.0.0.1',18081],
                    ['targetFrontendBypass',self.front['address'],8443],['targetBackendBypass',self.back['address'],3000],
                    ['reservedOutsideCanary','192.0.2.1',80],['metadata','169.254.169.254',80]]
            checks=json.loads(docker(['exec','-i','--user','1000:1000',self.anchor,'python','-c',code],raw(probes)))
            write(self.root/'egress-proof.json',checks)
            if checks['mirror']!=0 or any(v==0 for k,v in checks.items() if k!='mirror'):raise ValueError('egress boundary failed')
            denied=self.request(ORIGIN+'/api/auth/register','POST',{'Content-Type':'application/json'},b'{}')
            write(self.root/'guard-write-denial.json',denied)
            if denied['status']!=403 or not json.loads(denied['body']).get('guardGenerated'):raise ValueError('guard write bypass')
            for actor in (['A','B'] if self.business else [self.actor]):self.control({'op':'login','actor':actor},'login-'+actor)
            if self.mode=='native' and self.actor=='A' and 'W' in json.loads(self.credentials.read_text())['actors']:
                write(self.root/'weak-password-retest.json',self.control({'op':'login','actor':'W'},'weak-password-login-retest'))
            self.control({'op':'request','path':'/docs-json'},'current-openapi')
            if business:business_controls(self)
            if self.mode=='native':native_browser(self)
            elif self.mode=='business':
                transaction_controls(self)
                write(self.root/'operations.json',[])
                outcome.update(executionStatus='completed',evidenceStatus='complete',technique='direct API business controls; no ZAP producer')
                return outcome
            else:delegated_scan(self)
            self.settle();write(self.root/'urls.json',self.engine('core','view','urls',{'baseurl':ORIGIN}))
            messages=self.engine('core','view','messages',{'baseurl':ORIGIN,'start':0,'count':10000});write(self.root/'messages.json',messages)
            self.reports();write(self.root/'operations.json',self.completed)
            secret=json.loads(self.credentials.read_text())['actors'][self.actor]['password'].encode()
            jwt=re.compile(rb'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+')
            occurrences=[]
            for f in self.root.rglob('*'):
                rel=f.relative_to(self.root)
                if not f.is_file() or rel.parts[0] in {'private','source','controls','guard'}:continue
                b=f.read_bytes();pw=secret in b;tokens=len(jwt.findall(b))
                if pw or tokens:occurrences.append({'path':str(rel),'targetPasswordPresent':pw,'jwtOccurrences':tokens})
            audit={'scannerArtifactsAudited':True,'occurrences':occurrences,
                   'secretGate':'failed' if occurrences else 'passed','actualSecretValuesPrinted':False,
                   'privateCredentialRetention':'explicitly authorized synthetic fixtures;0600 under0700',
                   'note':'Native findings remain restricted even when functional crawl completes'}
            write(self.root/'credential-audit.json',audit)
            if self.mode=='delegated' and occurrences:raise ValueError('delegated credential gate failed')
            outcome.update(executionStatus='completed',evidenceStatus='complete')
        except Exception as e:
            outcome.update(executionStatus='failed',errorType=type(e).__name__,error=str(e)[:600])
        finally:
            try:
                if len(self.created)>=3:write(self.root/'zap.log',docker(['logs',self.names[2]]).encode())
                if len(self.created)>=2:write(self.root/'guard-state.json',self.control({'op':'state'},'final-state'))
            except Exception as e:outcome['finalObservationError']=str(e)[:300]
            try:self.cleanup();outcome['cleanupStatus']='clean'
            except Exception as e:outcome.update(cleanupStatus='incomplete',cleanupError=str(e)[:300])
            try:self.binding();outcome['targetBindingAfter']='unchanged'
            except Exception as e:outcome.update(targetBindingAfter='unconfirmed',bindingError=str(e)[:300])
            # Private mount was temporarily readable by the container UID; restore host retention modes.
            for p in (self.root/'private').rglob('*'):
                if p.is_file():p.chmod(0o600)
            if (self.root/'private').exists():(self.root/'private').chmod(0o700)
            if (self.root/'workspace').exists():(self.root/'workspace').chmod(0o700)
            write(self.root/'outcome.json',outcome)
        return outcome

def business_controls(p):
    rows=[]
    def req(label,actor,path,method='GET',body=None):
        x={'op':'request','actor':actor,'path':path,'method':method}
        if body is not None:x['body']=body
        r=p.control(x,label);rows.append({'label':label,'actor':actor,'method':method,'path':path,'status':r['status'],'evidence':'controls/'+label+'.json'})
        return r
    def data(r):return json.loads(r['body'])['data']
    for a in ('A','B'):
        for path in ['/api/v1/accounts','/api/v1/transactions?type=All&limit=20&offset=0','/api/v1/categories/options','/api/v1/goals','/api/v1/bills','/api/v1/savings/summary','/api/v1/expenses/summary','/api/v1/expenses/breakdown?month=2026-10']:
            req('baseline-'+a+'-'+re.sub(r'[^a-zA-Z0-9]','-',path),a,path)
    ids={}
    for a in ('A','B'):
        body={'bank_name':p.run_id+'-'+a,'account_type':'Checking','branch_name':'Security fixture',
              'account_number_full':str(int(uuid.uuid4().hex[:12],16)),'balance':123.45}
        r=req('create-account-'+a,a,'/api/v1/accounts','POST',body)
        if r['status']!=201:raise ValueError('owner create account failed')
        obj=data(r)['account'];ids[a]=obj['id']
        if obj['user_id']!=p.control({'op':'login','actor':a},'identity-recheck-'+a)['user']['id']:raise ValueError('ownership')
    aid=ids['A'];path=f'/api/v1/accounts/{aid}'
    before=data(req('owner-before','A',path));update={'bank_name':p.run_id+'-updated','account_type':'Checking','branch_name':'Security fixture','balance':234.56}
    deny=req('cross-update','B',path,'PUT',update);after=data(req('owner-after-cross-update','A',path))
    anon=req('anonymous-update',None,path,'PUT',update);afteranon=data(req('owner-after-anonymous-update','A',path))
    own=req('owner-update','A',path,'PUT',update);updated=data(req('owner-after-update','A',path))
    crossread=req('cross-read','B',path);anread=req('anonymous-read',None,path)
    crossdel=req('cross-delete','B',path,'DELETE');afterdel=data(req('owner-after-cross-delete','A',path))
    andel=req('anonymous-delete',None,path,'DELETE');afterandel=data(req('owner-after-anonymous-delete','A',path))
    removed=req('owner-delete','A',path,'DELETE');missing=req('owner-after-delete','A',path)
    checks={'crossUpdateDeniedUnchanged':deny['status']==403 and before==after,
            'anonymousUpdateDeniedUnchanged':anon['status']==401 and before==afteranon,
            'ownerUpdateEffective':own['status']==200 and updated['balance']==234.56,
            'crossReadDenied':crossread['status']==403,'anonymousReadDenied':anread['status']==401,
            'crossDeleteDeniedUnchanged':crossdel['status']==403 and updated==afterdel,
            'anonymousDeleteDeniedUnchanged':andel['status']==401 and updated==afterandel,
            'ownerDeleteEffective':removed['status']==200 and missing['status']==404}
    # Preserve B account as an actor-distinct discovery fixture; native/DAST A uses old A fixture1.
    goals={}
    for a in ('A','B'):
        r=req('create-goal-'+a,a,'/api/v1/goals','POST',{'goal_type':'Saving','category_id':None,'target_amount':'1000','start_date':'2026-10-01','end_date':'2026-12-31'})
        if r['status']!=201:raise ValueError('saving goal create failed')
        goals[a]=data(r)['goal_id']
    gpath=f'/api/v1/goals/{goals["A"]}'
    g0=data(req('goal-owner-before','A','/api/v1/goals'));gb=req('goal-cross-update','B',gpath,'PUT',{'target_amount':2000})
    g1=data(req('goal-owner-after-cross','A','/api/v1/goals'));ga=req('goal-anonymous-update',None,gpath,'PUT',{'target_amount':2000})
    g2=data(req('goal-owner-after-anonymous','A','/api/v1/goals'));go=req('goal-owner-update','A',gpath,'PUT',{'target_amount':1500})
    g3=data(req('goal-owner-after-update','A','/api/v1/goals'))
    checks.update(goalCrossUpdateDeniedUnchanged=gb['status']==403 and g0==g1,
                  goalAnonymousUpdateDeniedUnchanged=ga['status']==401 and g0==g2,
                  goalOwnerUpdateEffective=go['status']==200 and g3['savingGoal']['target_amount']==1500)
    write(p.root/'business-result.json',{'checks':checks,'verified':all(checks.values()),'observations':rows,
          'createdAccountIds':ids,'createdGoalIds':goals,'retained':{'accountB':ids['B'],'goals':goals},
          'transactionCreation':'blocked: no owned category creation API; inspect baseline categories before extending',
          'goalDelete':'not applicable: no DELETE route'})

def native_browser(p):
    # One supported browser login and real UI journeys; credential-bearing script/history stay restricted.
    a=json.loads(p.credentials.read_text())['actors'][p.actor]
    script='''const Control=Java.type('org.parosproxy.paros.control.Control');
const Selenium=Java.type('org.zaproxy.zap.extension.selenium.ExtensionSelenium');
const By=Java.type('org.openqa.selenium.By');const Thread=Java.type('java.lang.Thread');
const Vars=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
let d=null;let result={steps:[]};
try {d=Control.getSingleton().getExtensionLoader().getExtension(Selenium.class).getWebDriverProxyingViaZAP(1,'firefox-headless');
d.get('__ORIGIN__/login');Thread.sleep(2000);
d.findElement(By.id('login-email')).sendKeys('__EMAIL__');d.findElement(By.id('login-password')).sendKeys('__PASSWORD__');
d.findElement(By.cssSelector('button[type=submit]')).click();Thread.sleep(3000);
result.loginUrl=String(d.getCurrentUrl());result.loggedIn=d.executeScript("return localStorage.getItem('finebank.accessToken')!==null");
for(const path of ['/accounts','/accounts/1','/transactions','/transactions/new','/expenses','/bills','/goals','/goals/new']) {
d.get('__ORIGIN__'+path);Thread.sleep(2000);result.steps.push({path:path,url:String(d.getCurrentUrl()),text:String(d.findElement(By.tagName('body')).getText()).substring(0,3000)});}
}catch(e){result.error=String(e);}finally{if(d!==null)d.quit();Vars.setGlobalVar('p0.result',JSON.stringify(result));}'''
    for k,v in {'__ORIGIN__':ORIGIN,'__EMAIL__':a['email'],'__PASSWORD__':a['password']}.items():script=script.replace(k,v)
    j=p.script('ui-journeys',script);write(p.root/'ui-journeys.json',j)
    if j.get('error') or not j.get('loggedIn'):raise ValueError('native UI login/journey failed: '+str(j)[:400])
    # Configure the actual supported browser context; no experimental JSON-bearer provider.
    name='finalsource-native-A';cid=p.engine('context','action','newContext',{'contextName':name})['contextId']
    p.engine('context','action','includeInContext',{'contextName':name,'regex':r'http://127\.0\.0\.1:18080/.*'})
    p.engine('authentication','action','setAuthenticationMethod',{'contextId':cid,'authMethodName':'browserBasedAuthentication',
        'authMethodConfigParams':urlencode({'loginPageUrl':ORIGIN+'/login','browserId':'firefox-headless'})})
    p.engine('authentication','action','setLoggedInIndicator',{'contextId':cid,'loggedInIndicatorRegex':'"user_id":'+str(a['userId'])})
    p.engine('authentication','action','setLoggedOutIndicator',{'contextId':cid,'loggedOutIndicatorRegex':'"statusCode":401'})
    p.engine('sessionManagement','action','setSessionManagementMethod',{'contextId':cid,'methodName':'autoDetectSessionManagement','methodConfigParams':''})
    uid=p.engine('users','action','newUser',{'contextId':cid,'name':'fixture-A'})['userId']
    p.engine('users','action','setAuthenticationCredentials',{'contextId':cid,'userId':uid,'authCredentialsConfigParams':urlencode({'username':a['email'],'password':a['password']})})
    p.engine('users','action','setUserEnabled',{'contextId':cid,'userId':uid,'enabled':'true'})
    started=p.tool('zap_client_spider_start',{'targetUrl':ORIGIN+'/accounts','contextName':name,'userName':'fixture-A','maxDepth':2})
    sid=field(started,'Scan ID');polls=[];deadline=time.monotonic()+150
    while time.monotonic()<deadline:
        s=p.tool('zap_client_spider_status',{'scanId':sid});polls.append({'at':time.time(),'status':s})
        if 'Progress: 100%' in s or 'Status: 100%' in s or re.search(r'\b100%',s):break
        time.sleep(3)
    else:
        p.tool('zap_client_spider_stop',{'scanId':sid});raise TimeoutError('native Client Spider')
    nativeStatus=p.engine('clientSpider','view','status',{'scanId':sid})
    if str(nativeStatus.get('status'))!='100':raise ValueError('Client Spider terminal unconfirmed')
    p.completed.append({'kind':'clientSpider','scanId':sid,'polls':polls,'terminal':True,'nativeStatus':nativeStatus})

def transaction_controls(p):
    rows=[]
    def req(label,actor,path,method='GET',body=None):
        x={'op':'request','actor':actor,'path':path,'method':method}
        if body is not None:x['body']=body
        r=p.control(x,label);rows.append({'label':label,'actor':actor,'method':method,'path':path,'status':r['status'],'evidence':'controls/'+label+'.json'})
        return r
    def data(r):return json.loads(r['body'])['data']
    categories={r['actor']:r['id'] for r in json.loads(p.category_fixture.read_text())['created']}
    ids={};baseline={}
    for a in ['A','B']:
        options=data(req('owned-category-options-'+a,a,'/api/v1/categories/options'))
        if categories[a] not in {r['category_id'] for r in options}:raise ValueError('category API ownership control')
        baseline[a]=data(req('transaction-list-before-'+a,a,'/api/v1/transactions?type=All&limit=100&offset=0'))
        body={'bank_name':p.run_id+'-'+a,'account_type':'Checking','branch_name':'Transaction fixture',
              'account_number_full':str(int(uuid.uuid4().hex[:12],16)),'balance':100}
        r=req('transaction-account-create-'+a,a,'/api/v1/accounts','POST',body)
        if r['status']!=201:raise ValueError('transaction owner account create')
        ids[a]=data(r)['account']['id']
    def account(a):return data(req('account-state-'+str(len(rows)),a,f'/api/v1/accounts/{ids[a]}'))
    def txbody(actor,amount,label,account_actor=None,category_actor=None,kind='Expense'):
        return {'accountId':ids[account_actor or actor],'transactionDate':'2026-10-18T00:00:00Z','type':kind,
                'itemDescription':p.run_id+'-'+label,'category_id':categories[category_actor or actor],
                'shopName':'Dedicated security fixture','amount':str(amount),'paymentMethod':'Test','status':'Complete'}
    before=account('A');denied=req('transaction-cross-account','B','/api/v1/transactions','POST',txbody('B',20,'cross',account_actor='A'));after=account('A')
    anonymous=req('transaction-anonymous',None,'/api/v1/transactions','POST',txbody('A',20,'anonymous'));afteranon=account('A')
    foreigncat=req('transaction-cross-category','A','/api/v1/transactions','POST',txbody('A',20,'crosscategory',category_actor='B'));aftercat=account('A')
    checks={'crossAccountDeniedUnchanged':denied['status']==400 and before==after,
            'anonymousDeniedUnchanged':anonymous['status']==401 and before==afteranon,
            'crossCategoryDeniedUnchanged':foreigncat['status']==400 and before==aftercat}
    aexpense=req('transaction-owner-A-expense','A','/api/v1/transactions','POST',txbody('A',10,'A-expense'))
    checks['ownerAExpenseBalanceEffective']=aexpense['status']==201 and account('A')['balance']==90
    bexpense=req('transaction-owner-B-expense','B','/api/v1/transactions','POST',txbody('B',5,'B-expense'))
    checks['ownerBExpenseBalanceEffective']=bexpense['status']==201 and account('B')['balance']==95
    beforeinsuff=account('A');insuff=req('transaction-insufficient-funds','A','/api/v1/transactions','POST',txbody('A',1000,'insufficient'));afterinsuff=account('A')
    checks['insufficientFundsDeniedUnchanged']=insuff['status']==400 and beforeinsuff==afterinsuff
    income=req('transaction-owner-A-revenue','A','/api/v1/transactions','POST',txbody('A','2.5','A-revenue',kind='Revenue'))
    checks['ownerARevenueBalanceEffective']=income['status']==201 and account('A')['balance']==92.5
    aid={data(aexpense)['transactionId'],data(income)['transactionId']};bid={data(bexpense)['transactionId']}
    final={a:data(req('transaction-list-after-'+a,a,'/api/v1/transactions?type=All&limit=100&offset=0')) for a in ['A','B']}
    finalids={a:{t['transactionId'] for t in final[a]['data']} for a in ['A','B']}
    checks['ownerListsContainOnlyOwnNewTransactions']=aid<=finalids['A'] and bid<=finalids['B'] and not(aid&finalids['B']) and not(bid&finalids['A'])
    checks['noDeniedTransactionPersisted']=len(finalids['A']-{t['transactionId'] for t in baseline['A']['data']})==2 and len(finalids['B']-{t['transactionId'] for t in baseline['B']['data']})==1
    breakdown={a:data(req('expense-breakdown-'+a,a,'/api/v1/expenses/breakdown?month=2026-10')) for a in ['A','B']}
    items={a:{t['item_description'] for c in breakdown[a]['data'] for t in c['subCategories']} for a in ['A','B']}
    checks['expenseBreakdownIsolated']=p.run_id+'-A-expense' in items['A'] and p.run_id+'-B-expense' not in items['A'] and p.run_id+'-B-expense' in items['B'] and p.run_id+'-A-expense' not in items['B']
    for a in ['A','B']:
        for key,path in [('expenses-summary','/api/v1/expenses/summary'),('savings-summary','/api/v1/savings/summary'),('goals','/api/v1/goals')]:req(key+'-populated-'+a,a,path)
    write(p.root/'transaction-business-result.json',{'verified':all(checks.values()),'checks':checks,'observations':rows,
        'accountIds':ids,'categoryIds':categories,'transactionIds':{'A':sorted(aid),'B':sorted(bid)},
        'retainedFor':'authenticated populated DAST and retest; all new fixture records; no old balances changed'})
    if not all(checks.values()):raise ValueError('transaction business oracle failed')

def delegated_scan(p):
    # Supported scanner traffic through a per-actor authenticating mirror. No target JWT in ZAP.
    transactions_path='/api/v1/transactions?type=All&limit=20&offset=0';breakdown_path='/api/v1/expenses/breakdown?month=2026-10'
    paths=['/api/v1/accounts',*[f'/api/v1/accounts/{i}' for i in p.initial_accounts],'/api/v1/accounts/options','/api/v1/categories/options',
           transactions_path,'/api/v1/goals','/api/v1/bills','/api/v1/savings/summary','/api/v1/expenses/summary',breakdown_path]
    for i,path in enumerate(paths):p.seed(path,f'protected-{i}')
    if p.actor=='A':
        for i,path in enumerate(paths):p.control({'op':'request','path':path},f'anonymous-api-{i}')
        p.control({'op':'request','path':'/api/v1/accounts/1','tokenOverride':'intentionally-invalid-local-test-token'},'invalid-token-control')
    s=p.tool('zap_crawl_start',{'targetUrl':ORIGIN+'/api/v1/accounts','strategy':'http'});op=field(s,'Operation ID')
    polls=[];deadline=time.monotonic()+100
    while time.monotonic()<deadline:
        s=p.tool('zap_crawl_status',{'operationId':op});polls.append({'at':time.time(),'status':s})
        if field(s,'Completed')=='yes':break
        time.sleep(2)
    else:p.tool('zap_crawl_stop',{'operationId':op});raise TimeoutError('authenticated crawl')
    p.completed.append({'kind':'httpSpider','operationId':op,'terminal':True,'polls':polls})
    # Restrict active checks to XSS and SQLi rules, GET-only and nonrecursive.
    # Dynamic active scripts can still execute even when their scanner entry
    # reports enabled=false. Disable the script itself and validate actual traffic.
    inventory=p.engine('script','view','listScripts')
    def script_entries(value):
        if isinstance(value,dict):
            if value.get('type')=='active' and 'name' in value:yield value
            for v in value.values():yield from script_entries(v)
        elif isinstance(value,list):
            for v in value:yield from script_entries(v)
    disabled=[]
    for entry in script_entries(inventory):
        # Disabling the wrapper did not unregister its generated scan rule in
        # the pinned add-on. Remove only this owned scanner's active script.
        p.engine('script','action','remove',{'scriptName':entry['name']});disabled.append(entry['name'])
    write(p.root/'active-script-policy.json',{'before':inventory,'disabledActiveScripts':disabled,
          'after':p.engine('script','view','listScripts'),'reason':'strict two-rule policy; observed dynamic100043 bypass of enabled=false retained in prior phases'})
    policy='p0-bounded';p.engine('ascan','action','addScanPolicy',{'scanPolicyName':policy})
    p.engine('ascan','action','disableAllScanners',{'scanPolicyName':policy})
    p.engine('ascan','action','enableScanners',{'ids':'40012,40018','scanPolicyName':policy})
    p.engine('ascan','action','setScannerAttackStrength',{'id':'40012','attackStrength':'LOW','scanPolicyName':policy})
    p.engine('ascan','action','setScannerAttackStrength',{'id':'40018','attackStrength':'LOW','scanPolicyName':policy})
    write(p.root/'active-policy.json',p.engine('ascan','view','scanners',{'scanPolicyName':policy}))
    # Parameterized business queries ensure real active payload traffic, beyond health/docs.
    for path in [transactions_path,breakdown_path]:
        s=p.tool('zap_attack_start',{'targetUrl':ORIGIN+path,'recurse':'false','policy':policy})
        op=field(s,'Operation ID');sid=field(s,'Scan ID');polls=[];deadline=time.monotonic()+150
        while time.monotonic()<deadline:
            s=p.tool('zap_attack_status',{'operationId':op});polls.append({'at':time.time(),'status':s})
            if p.control({'op':'state'},f'auth-monitor-{p.tools}')['authLost']:
                p.tool('zap_attack_stop',{'operationId':op});raise ValueError('authentication lost during scan')
            if field(s,'Completed')=='yes':break
            time.sleep(3)
        else:p.tool('zap_attack_stop',{'operationId':op});raise TimeoutError('active deadline')
        progress=p.engine('ascan','view','scanProgress',{'scanId':sid})
        def plugins(value):
            if isinstance(value,dict):
                if 'Plugin' in value:yield value['Plugin']
                for v in value.values():yield from plugins(v)
            elif isinstance(value,list):
                for v in value:yield from plugins(v)
        traffic=[{'name':v[0],'id':v[1],'status':v[3],'requestsSent':int(v[5])} for v in plugins(progress)]
        if any(v['requestsSent']>0 and v['id'] not in ['40012','40018'] for v in traffic):raise ValueError('unexpected active rule traffic')
        if {v['id'] for v in traffic if v['requestsSent']>0}!={'40012','40018'} or any(v['status']!='Complete' for v in traffic if v['requestsSent']>0):
            raise ValueError('required active rule coverage incomplete')
        p.completed.append({'kind':'activeScan','path':path,'operationId':op,'scanId':sid,'terminal':True,'polls':polls,'ruleProgress':progress,
                            'policyConformance':True,'observedRuleTraffic':traffic})
    p.seed('/api/v1/accounts','post-scan-identity')
    # Fault during a separate live producer; completed baseline scans retain their evidence.
    fault=p.tool('zap_attack_start',{'targetUrl':ORIGIN+transactions_path,'recurse':'false','policy':policy})
    faultop=field(fault,'Operation ID');before=p.tool('zap_attack_status',{'operationId':faultop})
    if field(before,'Completed')=='yes':raise ValueError('auth-loss fault missed live producer')
    p.control({'op':'invalidate'},'invalidate-token');p.seed('/api/v1/accounts','auth-loss-trigger')
    state=p.control({'op':'state'},'auth-loss-observation');p.seed('/api/v1/accounts','auth-loss-fail-closed')
    if not state['authLost']:raise ValueError('auth loss undetected')
    stopped=p.tool('zap_attack_stop',{'operationId':faultop});deadline=time.monotonic()+30;polls=[]
    while time.monotonic()<deadline:
        s=p.tool('zap_attack_status',{'operationId':faultop});polls.append({'at':time.time(),'status':s})
        if field(s,'Completed')=='yes':break
        time.sleep(1)
    else:raise ValueError('auth-loss stop unconfirmed')
    p.completed.append({'kind':'authLossFault','operationId':faultop,'terminal':True,'polls':polls,'intentionalCancellation':True})
    write(p.root/'auth-loss-result.json',{'detected':True,'stoppedNewAuthenticatedWork':True,'state':state,
        'operationId':faultop,'before':before,'stopAcknowledgement':stopped,'terminal':polls[-1],
        'limitation':'invalid-token fault; natural token expiry and refresh not exercised'})

def main():
    if sys.argv[1:2] == ['coverage']:
        # Offline branch reuses the conservative collector; no Pilot/credentials.
        from finalsource_p0_coverage import main as coverage_main
        return coverage_main(sys.argv[2:])
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--credentials',type=Path,required=True)
    ap.add_argument('--receipt',type=Path,required=True)
    ap.add_argument('--mode',choices=['native','delegated','business'],required=True);ap.add_argument('--actor',choices=['A','B'],default='A');ap.add_argument('--business',action='store_true')
    ap.add_argument('--category-fixture',type=Path);ap.add_argument('--accounts',default='1')
    a=ap.parse_args()
    try:
        require_p0_mode(a.mode)
    except Blocked as exc:
        print(json.dumps({'executionStatus':'not_started','evidenceStatus':'incomplete',
                          'securityVerdict':'inconclusive','cleanupStatus':'clean',
                          'gateDecision':'block','reason':str(exc),'targetRequests':0}))
        return 2
    receipt=json.loads(a.receipt.read_text())
    if receipt.get('environment')!='finalsource-zap-test' or not receipt.get('userRequest') or ((a.business or a.mode=='business') and not receipt.get('fixtureCreationAuthorized')):
        raise ValueError('explicit local scan/fixture authority required')
    accounts=[int(x) for x in a.accounts.split(',')]
    if any(x<=0 for x in accounts) or (a.mode=='business' and not a.category_fixture):raise ValueError('fixture IDs required')
    p=Pilot(a.output.resolve(),a.actor,a.mode,a.credentials.resolve(),accounts,a.business or a.mode=='business',a.category_fixture);write(p.root/'user-authorization.json',receipt)
    r=p.execute(a.business);print(json.dumps(r));return 0 if r['executionStatus']=='completed' else 1
if __name__=='__main__':sys.exit(main())
