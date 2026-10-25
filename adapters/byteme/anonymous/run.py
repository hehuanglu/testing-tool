import collections, importlib.util, json, os, re, secrets, sys, time
from pathlib import Path
from urllib.parse import urlsplit
CODE_ROOT=Path(__file__).resolve().parent
WS=CODE_ROOT.parents[2]
ROOT=Path(os.environ.get('BYTEME_ANON_ROOT',str(WS/'operations/byteme/anonymous'))).resolve()
ROOT.mkdir(parents=True,exist_ok=True,mode=0o700)
sys.path.insert(0,str(WS/'zap-product-assessment/src'))
from zap_assessment.runtime import DockerRuntime,docker,ZAP,MCP_IMAGE,PROBE
from zap_assessment.journal import Journal
from zap_assessment.transport import MCP,field,Scanner
from zap_assessment.anonymous_runner import AnonymousRun
from zap_assessment.product_scope import reconcile,compact_results
from zap_assessment.result_readers import read_jsonl,collect_alerts
os.umask(0o077)
def save(name,v):
    p=ROOT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2))
def load(name):return json.loads((ROOT/name).read_text())
class Runtime(DockerRuntime):
    def __init__(self):
        self.cfg=load('private.json');super().__init__(self.cfg['id'],ROOT,Journal(ROOT/'journal.jsonl',self.cfg['id'],'fresh-product-adapter'))
        self.work=ROOT/'workspace';self.work.mkdir(exist_ok=True,mode=0o777);self.work.chmod(0o777)
    def request(self,url,method='GET',headers=None,body=None,timeout=10):
        h=dict(headers or {})
        if url.startswith('http://127.0.0.1:7456/'):h['X-API-Key']=self.cfg['key']
        import base64
        payload={'url':url,'method':method,'headers':h,'body':base64.b64encode(body).decode() if body is not None else None,'timeout':timeout}
        return json.loads(docker(['exec','-i','--user','1002:1002',self.anchor,'python','-c',PROBE.replace('2000001','8000001').replace('2000000','8000000')],json.dumps(payload).encode(),timeout=timeout+10))
    def provision(self):
        c=self.cfg; boundary='sha256:ef7533a958152d8737944296ed388d697d6589e26ee5d81d5436693564173cd1'
        self.commands={self.anchor:['sleep','14400'],self.names[1]:['python','/guard.py','/private'],self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=true','-config','autoupdate.checkOnStart=false','-config','connection.timeoutInSecs=15','-config','spider.processForm=false','-config','spider.postForm=false'],self.names[3]:[]}
        self.create(self.anchor,boundary,['--network',c['network'],'--cap-add','NET_ADMIN','--memory','64m','--no-healthcheck'])
        rules=['iptables -P OUTPUT DROP','iptables -P INPUT DROP','iptables -P FORWARD DROP','ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP','iptables -A INPUT -i lo -j ACCEPT','iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT','iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT','iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 18888 -m owner --uid-owner 1000 -j ACCEPT','iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT','iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090 -m owner --uid-owner 1002 -j ACCEPT',f"iptables -A OUTPUT -p tcp -d {c['address']} --dport 8080 -m owner --uid-owner 1003 -j ACCEPT"]
        for rule in rules:docker(['exec',self.anchor,*rule.split()])
        shared=['--network','container:'+self.anchor,'--no-healthcheck','--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256']
        # Only owned scanner containers can access this private working directory.
        ROOT.chmod(0o755)
        private=ROOT/'guard-private';private.mkdir(mode=0o777);private.chmod(0o777)
        for name in ('private.json','mode.json'):
            (private/name).write_text((ROOT/name).read_text());(private/name).chmod(0o444)
        self.create(self.names[1],boundary,[*shared,'--user','1003:1003','--memory','128m','-v',str(CODE_ROOT/'guard.py')+':/guard.py:ro','-v',str(WS/'zap-product-assessment/src/zap_assessment/result_readers.py')+':/result_readers.py:ro','-v',str(private)+':/private'])
        self.create(self.names[2],ZAP,[*shared,'--user','1000:1000','--memory','1200m','--cpus','2','-e','ZAP_MEMORY=800m','-v',str(self.work)+':/zap/wrk'])
        env={'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'api-key','MCP_API_KEY':c['key'],'MCP_CLIENT_ID':c['id'],'ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':'','ZAP_REPORT_DIRECTORY':'/zap/wrk','ZAP_ALLOW_LOCALHOST':'true','ZAP_ALLOW_PRIVATE_NETWORKS':'true','ZAP_URL_WHITELIST':c['address'],'MCP_SERVER_TOOLS_SURFACE':'expert','ZAP_THREAD_PER_HOST':'1','ZAP_HOST_PER_SCAN':'1','ZAP_MAX_ACTIVE_SCAN_DURATION':'5','ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1','ZAP_SCAN_HISTORY_BACKEND':'in-memory','ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory','JAVA_TOOL_OPTIONS':'-Xmx320m','ZAP_INIT_CONNECTION_TIMEOUT':'90','MCP_PROTECTION_RATE_LIMIT_CAPACITY':'600','MCP_PROTECTION_RATE_LIMIT_REFILL_TOKENS':'600'}
        envfile=ROOT/'mcp.env';envfile.write_text(''.join(k+'='+v+'\n' for k,v in env.items()))
        self.create(self.names[3],MCP_IMAGE,[*shared,'--user','1001:1000','--memory','448m','--cpus','1','--env-file',str(envfile),'-v',str(self.work)+':/zap/wrk'])
        self.wait_health()
def get():
    rt=Runtime();m=MCP(rt.request);listing=m.initialize();save('runtime-tools.json',listing)
    return rt,m
def mode(v):
    save('mode.json',v);p=ROOT/'guard-private/mode.pending';p.write_text(json.dumps(v));p.chmod(0o444);os.replace(p,p.with_name('mode.json'))
def seed(rt,v,body=None):
    mode(v);url=rt.cfg['origin']+v['path']+v.get('query','');raw=v.get('rawBody',json.dumps(body) if body is not None else '')
    request=f"{v['method']} {url} HTTP/1.1\r\nHost: {urlsplit(url).netloc}\r\nConnection: close\r\n"+("Content-Type: "+v.get('contentType','application/json')+'\r\n' if body is not None or v.get('rawBody') else '')+f"Content-Length: {len(raw.encode())}\r\n\r\n"+raw
    rt.journal.append('intent',{'action':'seed','id':v['id'],'method':v['method'],'path':v['path']})
    result=rt.engine('core','action','sendRequest',{'request':request,'followRedirects':'false'})
    rows=result.get('sendRequest',[])
    if len(rows)!=1:raise ValueError('seed no single response')
    row=rows[0];save('seeds/'+v['id']+'.json',row)
    rt.journal.append('ack',{'action':'seed','id':v['id'],'status':row['responseHeader'].splitlines()[0]})
    return row
def bind(rt,msg,label):
    # Reuse existing exact native SiteNode binding without invoking research admission.
    a=AnonymousRun.__new__(AnonymousRun);a.rt=rt;a.out=ROOT;a.j=rt.journal;a.engine=lambda component,kind,name,args=None:rt.engine(component,kind,name,args or {})
    a.bind_baseline(msg,label,expected_method=msg['requestHeader'].split()[0])
def setup():
    if (ROOT/'private.json').exists():raise ValueError('fresh setup refuses prior private state')
    free=os.statvfs(ROOT).f_bavail*os.statvfs(ROOT).f_frsize
    assert free>=2*1024**3+2*64*1024**2,'preflight: 64MiB estimated growth, twofold headroom plus unchanged 2GiB reserve'
    info=json.loads(docker(['inspect','byteme-backend-1']))[0];labels=info['Config']['Labels'];assert labels['com.docker.compose.project.working_dir']=='/Users/hahoangloc/Working/UET/SA/ByteMe'
    assert info['State']['Running']
    net=next(iter(info['NetworkSettings']['Networks'].values()));tag=secrets.token_hex(3)
    cfg={'id':'bmclean'+tag,'tag':tag,'password':secrets.token_urlsafe(18),'key':secrets.token_urlsafe(32),'address':net['IPAddress'],'network':net['NetworkID'],'origin':'http://'+net['IPAddress']+':8080','startedAt':time.time(),'targetContainerId':info['Id'],'targetImageId':info['Image']}
    save('private.json',cfg);save('mode.json',{'id':'initial','method':'GET','path':'/actuator/health'})
    rt=Runtime();rt.provision();rt,m=get()
    for comp,action,args in [('network','setHttpProxy',{'host':'127.0.0.1','port':18888}),('network','setHttpProxyEnabled',{'enabled':'true'}),('core','setOptionHttpStateEnabled',{'Boolean':'false'}),('ascan','setOptionThreadPerHost',{'Integer':1}),('ascan','setOptionHostPerScan',{'Integer':1}),('ascan','setOptionInjectPluginIdInHeader',{'Boolean':'true'}),('ascan','setOptionAddQueryParam',{'Boolean':'false'}),('ascan','setOptionMaxScanDurationInMins',{'Integer':5})]:rt.engine(comp,'action',action,args)
    inventory={k:rt.engine(c,'view',k,{}) for c,k in [('ascan','scanners'),('ascan','scanPolicyNames'),('ascan','optionTargetParamsInjectable'),('ascan','optionTargetParamsEnabledRPC'),('autoupdate','installedAddons')]};save('scanner-inventory.json',inventory)
    msg=seed(rt,{'id':'health','method':'GET','path':'/actuator/health'})
    assert int(msg['responseHeader'].split()[1])==200
    save('preflight.json',{'hostFreeBytes':free,'reserveBytes':2*1024**3,'estimatedGrowthBytes':64*1024**2,'twofoldHeadroom':True})
    print(json.dumps({'runId':cfg['id'],'health':msg['responseHeader'].splitlines()[0],'tools':len(m.contracts)}),flush=True)
def discovery():
    import yaml
    src=Path('/Users/hahoangloc/Working/UET/SA/ByteMe');spec=yaml.safe_load((src/'src/main/resources/static/openapi.yaml').read_text())
    operations=[]
    for path,item in spec['paths'].items():
        for method,op in item.items():
            if method not in ('get','post','put','delete','patch'):continue
            operations.append({'id':op['operationId'],'method':method.upper(),'path':path,'protected':bool(op.get('security',spec.get('security',[]))),'input':op.get('parameters',[]),'body':op.get('requestBody')})
    extras=[('GET','/openapi.yaml'),('GET','/actuator/health'),('GET','/swagger-ui.html'),('GET','/swagger-ui/index.html'),('GET','/v3/api-docs/swagger-config'),('GET','/error')]
    rt,m=get();live=seed(rt,{'id':'live-openapi','method':'GET','path':'/openapi.yaml','technique':'runtime discovery'})
    assert int(live['responseHeader'].split()[1])==200 and yaml.safe_load(live['responseBody'])==spec
    save('discovery.json',{'product':'ByteMe','source':str(src),'operations':operations,'auxiliaryPublic':extras,'sourceSpecRuntimeCompared':True,'sourceHead':docker_source_head(src)})
    save('responsibility-inventory.json',source_inventory(spec,operations))
    save('fixture-plan.json',fixture_forecast())
    print(json.dumps({'public':[o for o in operations if not o['protected']],'protectedCount':sum(o['protected'] for o in operations)},ensure_ascii=False),flush=True)
def docker_source_head(src):
    import subprocess
    return subprocess.check_output(['git','-C',str(src),'rev-parse','HEAD'],text=True).strip()
def source_inventory(spec,operations):
    def resolve(value):
        while '$ref' in value:
            node=spec
            for part in value['$ref'].removeprefix('#/').split('/'):node=node[part]
            value=node
        return value
    cases=[]
    for op in operations:
        if op['protected']:continue
        inputs=[]
        if op.get('body'):
            body=resolve(op['body']);schema=resolve(body['content']['application/json']['schema'])
            inputs.extend({'vector':'JSON-body','field':key} for key in schema['properties'])
        inputs.extend({'vector':'query','field':resolve(p)['name']} for p in op['input'] if resolve(p)['in']=='query')
        inputs.extend({'vector':'path','field':key} for key in re.findall(r'\{([^{}]+)\}',op['path']))
        cases.append({'caseId':'source:'+op['id'],'operationId':op['id'],'method':op['method'],'path':op['path'],'role':'anonymous','question':'Assess every discovered public operation and source input, independently of allocated campaigns.','inputs':inputs,'requiredEvidence':['source-active-result-read']+['source-input:'+x['vector']+':'+x['field'] for x in inputs],'evidenceRefs':['verified live OpenAPI and current controllers/DTO/security source'],'prerequisites':[]})
    return {'productLocation':'/Users/hahoangloc/Working/UET/SA/ByteMe','track':'be-anonymous','complete':True,'cases':cases}
def registration_rules(field):return [40018,40012] if field in ('fullName','email') else [40018]
def fixture_forecast():
    prior=ROOT/'guard-private/traffic.jsonl';counts=collections.Counter()
    if prior.exists():
        for row in read_jsonl(prior):
            if row.get('status')!=201:continue
            if row.get('kind')=='fixture-register':counts['loginFixtures']+=1;continue
            name=row.get('campaign','')
            if row.get('path')!='/api/auth/register' or not name.startswith('register-'):continue
            field=name.removeprefix('register-');rules=[909901] if field=='phone-valid' else registration_rules(field)
            if row.get('technique')!='ZAP active' or str(row.get('ruleId')) in set(map(str,rules)):counts[name]+=1
    return {'basis':'Previous successful native creates and baselines restricted to newly selected rule sets; login fixture rotation from observed quota. Forecast only, not a pass threshold or coverage source. LOW alert threshold may change rule behavior.','estimatedAccountCreates':sum(counts.values()) if counts else None,'breakdown':dict(counts),'planningTiming':'before workload in discovery'}
def campaign(rt,m,v,rules,guided=False):
    name=v['id'];opfile='campaigns/'+name+'.json'
    if (ROOT/opfile).exists():raise ValueError('refuse campaign replay')
    policy='bm-'+name
    rt.engine('ascan','action','setOptionTargetParamsInjectable',{'Integer':16 if v.get('vector')=='path' else 1 if v['method']=='GET' else 2})
    rt.engine('ascan','action','setOptionTargetParamsEnabledRPC',{'Integer':4 if v['method']=='POST' else 0})
    names=rt.engine('ascan','view','scanPolicyNames',{})['scanPolicyNames']
    strength=v.get('strength','LOW');threshold=v.get('threshold','LOW' if 40012 in rules else 'MEDIUM')
    if policy not in names:rt.engine('ascan','action','addScanPolicy',{'scanPolicyName':policy,'attackStrength':strength,'alertThreshold':threshold})
    for action,args in [('disableAllScanners',{'scanPolicyName':policy}),('enableScanners',{'ids':','.join(map(str,rules)),'scanPolicyName':policy})]:rt.engine('ascan','action',action,args)
    readback=rt.engine('ascan','view','scanners',{'scanPolicyName':policy})['scanners'];assert {int(r['id']) for r in readback if r['enabled']=='true'}==set(rules)
    v={**v,'technique':'ZAP active','rules':rules};body={v['field']:v['baseline']} if v.get('field') else None
    msg=seed(rt,{**v,'technique':'active-baseline'},body);status=int(msg['responseHeader'].split()[1])
    if status not in v.get('baselineStatuses',[200]):raise ValueError('baseline not valid '+name+':'+str(status))
    bind(rt,msg,name);mode(v)
    url=rt.cfg['origin']+v['path']+v.get('query','');known={str(s['id']) for s in rt.engine('ascan','view','scans',{})['scans']}
    questions=[{'id':name+'-rule-'+str(rule),'ruleIds':[rule],'minimumStage':'processing' if name.startswith('token-') and rule==40018 else 'boundary','basis':v.get('basis','Native input validation and response handling for discovered ByteMe surface'),'field':'q' if name=='foods-search' and rule==40012 else v.get('field')} for rule in rules]
    op={'id':name,'method':v['method'],'path':v['path'],'query':v.get('query'),'field':v.get('field'),'vector':v.get('vector'),'rules':rules,'questions':questions,'policy':policy,'strength':strength,'threshold':threshold,'startedAt':time.time(),'terminal':False,'guided':guided}
    save(opfile,op);rt.journal.append('intent',{'action':'active-start',**op,'knownIds':sorted(known)})
    try:
        if guided:
            start=m.call('zap_attack_start',{'targetUrl':url,'recurse':'false','policy':policy});op['guidedId']=field(start,'Operation ID');op['startResult']=start
            new=[s for s in rt.engine('ascan','view','scans',{})['scans'] if str(s['id']) not in known];assert len(new)==1
            op['nativeId']=str(new[0]['id'])
        else:
            args={'url':url,'recurse':'false','scanPolicyName':policy,'method':v['method']}
            if body is not None:args['postData']=json.dumps(body)
            op['nativeId']=str(rt.engine('ascan','action','scan',args)['scan'])
    except Exception:
        new=[s for s in rt.engine('ascan','view','scans',{})['scans'] if str(s['id']) not in known]
        if len(new)!=1:op['unknownStart']=True;save(opfile,op);raise
        op['nativeId']=str(new[0]['id']);op['startReconciled']=True
    rt.journal.append('ack',{'action':'active-start',**op});save(opfile,op)
    while True:
        st=os.statvfs(ROOT)
        if st.f_bavail*st.f_frsize<2*1024**3:
            rt.engine('ascan','action','stop',{'scanId':op['nativeId']});op['resourceStop']=True;break
        status=int(rt.engine('ascan','view','status',{'scanId':op['nativeId']})['status'])
        if status>=100:op['terminal']=True;break
        if time.time()-op['startedAt']>420:
            rt.engine('ascan','action','stop',{'scanId':op['nativeId']});op['timeout']=True;break
        time.sleep(2)
    op['finishedAt']=time.time();op['progress']=rt.engine('ascan','view','scanProgress',{'scanId':op['nativeId']});op['messageIds']=rt.engine('ascan','view','messagesIds',{'scanId':op['nativeId']})
    if op.get('guidedId'):op['finalGuidedStatus']=m.call('zap_attack_status',{'operationId':op['guidedId']})
    records=read_jsonl(ROOT/'guard-private/traffic.jsonl')
    rows=[r for r in records if r.get('campaign')==name and r.get('technique')=='ZAP active']
    op['applicationRequests']=len(rows);op['statusCounts']=dict(collections.Counter(str(r['status']) for r in rows));op['ruleCounts']=dict(collections.Counter(str(r.get('ruleId') or 'unattributed') for r in rows))
    if v.get('field'):
        mutated=[r for r in rows if r.get('nativeBody') and json.loads(r['nativeBody']).get(v['field'])!=v['baseline'] and json.loads(r['actualBody']).get(v['field'])==json.loads(r['nativeBody'])[v['field']]]
        op['mutatedInputRequests']=len(mutated);op['mutatedInputStatusCounts']=dict(collections.Counter(r['status'] for r in mutated));op['mutatedInputBusinessCodes']=dict(collections.Counter(json.loads(r['response']).get('code',str(r['status'])) for r in mutated))
    save(opfile,op);rt.journal.append('terminal',op)
    print(json.dumps({k:op[k] for k in ('id','terminal','applicationRequests','statusCounts','ruleCounts')}),flush=True)
def run_group(group):
    rt,m=get();c=rt.cfg
    if group=='catalog':
        msg=seed(rt,{'id':'catalog-discovery','method':'GET','path':'/api/foods','queryKeys':[],'technique':'populated catalog discovery'})
        assert int(msg['responseHeader'].split()[1])==200
        foods=json.loads(msg['responseBody']);food=foods[0];save('catalog-baseline.json',foods)
        cases=[({'id':'foods-category','method':'GET','path':'/api/foods','query':'?categoryId='+str(food['categoryId']),'queryKeys':['categoryId'],'vector':'query','basis':'Numeric filter conversion/SQL boundary and CRLF handling; no textual rendering sink.'},[40018,40003]), ({'id':'foods-search','method':'GET','path':'/api/foods/search','query':'?q='+__import__('urllib.parse',fromlist=['quote']).quote(food['name'][:2])+'&categoryId='+str(food['categoryId']),'queryKeys':['q','categoryId'],'vector':'query','strength':'MEDIUM','basis':'Populated textual search reaches SQL LIKE handling; separately inspect reflection in JSON, without claiming browser execution.'},[40018,40012]), ({'id':'foods-id','method':'GET','path':'/api/foods/'+str(food['id']),'vector':'path','basis':'Existing numeric selector; SQL/parser and header/error handling boundaries.'},[40018,40003])]
        for v,rules in cases:campaign(rt,m,v,rules,guided=True)
    if group=='register':
        values={'fullName':'ByteMe clean input','email':f"baseline{c['tag']}@example.test",'phone':'08'+str(int(c['tag'],16))[-8:].zfill(8),'password':'NativeSeedPassword123!','confirmPassword':'NativeSeedPassword123!'}
        for field_,baseline in values.items():
            rules=registration_rules(field_)
            campaign(rt,m,{'id':'register-'+field_,'method':'POST','path':'/api/auth/register','field':field_,'baseline':baseline,'adapt':True,'vector':'JSON-body','baselineStatuses':[201],'basis':'Fresh account create and storage with valid siblings; SQL boundary for all fields, JSON reflection only for returned name/email. Phone valid-format and password dependency receive separate controls.'},rules)
    if group=='login':
        for field_,baseline in [('email',f"baseline{c['tag']}@example.test"),('password','NativeSeedPassword123!')]:
            campaign(rt,m,{'id':'token-'+field_,'method':'POST','path':'/api/auth/token','field':field_,'baseline':baseline,'adapt':True,'vector':'JSON-body','strength':'MEDIUM','basis':'Credential lookup/comparison and SQL injection with real positive and negative login outcomes; no password reflection or response-header sink in source.'},[40018])
    if group=='auxiliary':
        for n,path in enumerate(['/openapi.yaml','/actuator/health','/swagger-ui/index.html','/v3/api-docs/swagger-config','/error']):
            campaign(rt,m,{'id':'aux-'+str(n),'method':'GET','path':path,'queryKeys':[],'baselineStatuses':[200,500]},[10104],guided=True)
    if group=='phone-boundary':
        script='byteme-phone-boundary';(rt.work/'phone-boundary.js').write_text((CODE_ROOT/'phone-boundary.js').read_text())
        loaded=rt.engine('script','view','listScripts',{})['listScripts']
        if any(s['name']==script for s in loaded):rt.engine('script','action','remove',{'scriptName':script})
        rt.engine('script','action','load',{'scriptName':script,'scriptType':'active','scriptEngine':'Graal.js','fileName':'/zap/wrk/phone-boundary.js'})
        rt.engine('script','action','enable',{'scriptName':script})
        save('phone-script-state-before.json',rt.engine('script','view','listScripts',{}))
        campaign(rt,m,{'id':'register-phone-valid','method':'POST','path':'/api/auth/register','field':'phone','baseline':'08'+str(int(c['tag'],16))[-8:].zfill(8),'adapt':True,'vector':'JSON-body','baselineStatuses':[201]},[909901])
        save('phone-script-state-after.json',rt.engine('script','view','listScripts',{}))
def controls():
    rt,m=get();out=[]
    for op in load('discovery.json')['operations']:
        if not op['protected']:continue
        # Guard must reject at authentication before business binding; IDs are syntactic placeholders, not owned objects.
        path=re.sub(r'\{[^}]+\}','1',op['path']);v={'id':'denial-'+op['id'],'method':op['method'],'path':path,'technique':'anonymous protected-denial control'}
        msg=seed(rt,v,{} if op['method'] in ('POST','PUT') else None)
        out.append({'id':v['id'],'method':v['method'],'path':op['path'],'status':int(msg['responseHeader'].split()[1]),'bodyCode':json.loads(msg['responseBody']).get('code')})
    for n,path in enumerate(['/swagger-ui.html','/swagger-ui/swagger-ui.css','/swagger-ui/index.css','/swagger-ui/swagger-ui-bundle.js','/swagger-ui/swagger-ui-standalone-preset.js','/swagger-ui/swagger-initializer.js','/swagger-ui/favicon-32x32.png','/swagger-ui/favicon-16x16.png','/swagger-ui/oauth2-redirect.html','/actuator/health/liveness','/actuator/health/readiness']):
        msg=seed(rt,{'id':'aux-control-'+str(n),'method':'GET','path':path,'technique':'public auxiliary baseline/passive'})
        out.append({'id':'aux-control-'+str(n),'method':'GET','path':path,'status':int(msg['responseHeader'].split()[1])})
    for path in ('/api/auth/register','/api/auth/token'):
        prefix='register' if path.endswith('register') else 'token'
        for suffix,body,ct in [('malformed','{','application/json'),('xml','<test>anonymous</test>','application/xml')]:
            msg=seed(rt,{'id':prefix+'-'+suffix,'method':'POST','path':path,'technique':'content-type/parser control','rawControl':True,'rawBody':body,'contentType':ct})
            out.append({'id':prefix+'-'+suffix,'method':'POST','path':path,'status':int(msg['responseHeader'].split()[1]),'bodyCode':json.loads(msg['responseBody']).get('code')})
        msg=seed(rt,{'id':prefix+'-method-get','method':'GET','path':path,'technique':'HTTP method control'})
        out.append({'id':prefix+'-method-get','method':'GET','path':path,'status':int(msg['responseHeader'].split()[1])})
    save('controls.json',out);print(json.dumps(out),flush=True)
def poststate():
    rt,m=get();rows=read_jsonl(ROOT/'guard-private/traffic.jsonl')
    checks=[]
    for name in ('register-fullName','register-email','register-phone-valid','register-password','register-confirmPassword'):
        candidates=[r for r in rows if r.get('campaign')==name and r.get('technique')=='ZAP active' and r.get('status')==201 and r.get('field')]
        # Select an actual changed target field; baseline lives in native requestBody.
        baseline=json.loads(load('seeds/'+name+'.json')['requestBody'])
        candidates=[r for r in candidates if json.loads(r['nativeBody'])[r['field']]!=baseline[r['field']]]
        if not candidates:raise ValueError('no created mutated input '+name)
        row=candidates[0];actual=json.loads(row['actualBody']);created=json.loads(row['response'])
        msg=seed(rt,{'id':'readback-'+name,'method':'POST','path':'/api/auth/token','technique':'public login post-state readback'}, {k:actual[k] for k in ('email','password')})
        code=int(msg['responseHeader'].split()[1]);resp=json.loads(msg['responseBody']);user=resp.get('user',{})
        checks.append({'id':name,'technique':'public login with created credentials, token not propagated','status':code,'accountIdMatched':user.get('id')==created.get('id'),'storedFieldsMatched':all(user.get(k)==created.get(k) for k in ('fullName','email','phone','role','status')),'role':user.get('role'),'inputField':row['field'],'responseContentType':'application/json' in msg['responseHeader'],'passwordEchoed':any(k in resp or k in user for k in ('password','confirmPassword','passwordHash'))})
    created=next(r for r in reversed(rows) if r.get('method')=='POST' and r.get('path')=='/api/auth/register' and r.get('status')==201)
    duplicate=json.loads(created['actualBody']);msg=seed(rt,{'id':'register-duplicate-control','method':'POST','path':'/api/auth/register','technique':'duplicate-identity control'},duplicate)
    checks.append({'id':'register-duplicate','status':int(msg['responseHeader'].split()[1]),'bodyCode':json.loads(msg['responseBody']).get('code')})
    mismatch=dict(duplicate);mismatch['confirmPassword']='Mismatch-control-678!';msg=seed(rt,{'id':'register-mismatch-control','method':'POST','path':'/api/auth/register','technique':'password dependency validation control'},mismatch)
    checks.append({'id':'register-password-mismatch','status':int(msg['responseHeader'].split()[1]),'bodyCode':json.loads(msg['responseBody']).get('code')})
    for n,(path,query,keys) in enumerate([('/api/foods','',[]),('/api/foods/search','?q=%25',['q']),('/api/foods/search','?q=%5F',['q']),('/api/foods/search','?q=',['q']),('/api/foods/999999999','',[]) ]):
        msg=seed(rt,{'id':'catalog-semantic-'+str(n),'method':'GET','path':path,'query':query,'queryKeys':keys,'technique':'catalog positive/literal-wildcard/validation/not-found control'})
        parsed=json.loads(msg['responseBody']);checks.append({'id':'catalog-semantic-'+str(n),'method':'GET','path':path+query,'status':int(msg['responseHeader'].split()[1]),'count':len(parsed) if isinstance(parsed,list) else None,'bodyCode':parsed.get('code') if isinstance(parsed,dict) else None})
    save('poststate.json',checks);print(json.dumps(checks),flush=True)
def export():
    from zap_assessment.evidence import read_report
    rt,m=get();deadline=time.monotonic()+90;stable=0;statuses=[]
    while True:
        result=m.call('zap_passive_scan_status',{});statuses.append(result)
        stable=stable+1 if field(result,'Completed')=='yes' and field(result,'Records remaining')=='0' else 0
        if stable>=2:break
        if time.monotonic()>deadline:raise TimeoutError('passive backlog')
        time.sleep(1)
    save('passive-status.json',statuses)
    scanner=Scanner(m,rt.engine,rt.request)
    if (ROOT/'report-path.json').exists():path=load('report-path.json')['path']
    else:
        path=scanner.report(rt.cfg['origin']);save('report-path.json',{'path':path})
    if not (ROOT/'native-report.json').exists():
        data=read_report(scanner.chunk,path,32*1024**2);(ROOT/'native-report.json').write_bytes(data)
    try:summary=m.call('zap_findings_summary',{'baseUrl':rt.cfg['origin']})
    except Exception:
        save('root-summary-error.json',getattr(m,'last_response',{}))
        summary=m.call('zap_findings_summary',{'baseUrl':rt.cfg['origin']+'/api/foods'})
    save('findings-summary.json',{'summary':summary})
    count=int(rt.engine('core','view','numberOfAlerts',{'baseurl':rt.cfg['origin']})['numberOfAlerts'])
    alerts=collect_alerts(lambda start,size:rt.engine('alert','view','alerts',{'baseurl':rt.cfg['origin'],'start':start,'count':size})['alerts'],count,page_size=50)
    assert count==int(rt.engine('core','view','numberOfAlerts',{'baseurl':rt.cfg['origin']})['numberOfAlerts'])
    assert len(alerts)==count and len({a['id'] for a in alerts})==count
    save('alerts-native.json',{'alerts':alerts,'count':count})
    attribution=[]
    for aid in dict.fromkeys(str(a['messageId']) for a in alerts):
        msg=rt.engine('core','view','message',{'id':aid})['message']
        attribution.append({'messageId':aid,'emptyGuardResponse':not msg['responseBody'] and '403' in msg['responseHeader'].splitlines()[0],'applicationHeadersPresent':any(x in msg['responseHeader'].lower() for x in ('content-type:','cache-control:','x-content-type-options:'))})
    save('alert-response-attribution.json',attribution)
    scans=rt.engine('ascan','view','scans',{});save('all-scan-status.json',scans);assert all(s['state']=='FINISHED' for s in scans['scans'])
    print(summary,flush=True);print(json.dumps({'nativeAlertInstances':count,'families':dict(collections.Counter((a.get('risk') or 'unknown')+' '+a['name'] for a in alerts))}),flush=True)
def cleanup():
    rt,m=get();assert (ROOT/'alerts-native.json').exists()
    assert all(s['state'] in ('FINISHED','STOPPED') for s in rt.engine('ascan','view','scans',{})['scans'])
    rt.cleanup();ROOT.chmod(0o700);(ROOT/'guard-private').chmod(0o700)
    save('cleanup.json',{'status':'complete','ownedContainersRemoved':rt.owned_names(),'privateRetention':'working root and guard-private directory restored to owner-only access after container removal','at':time.time()})
if __name__=='__main__':
    if sys.argv[1]=='setup':setup()
    elif sys.argv[1]=='discover':discovery()
    elif sys.argv[1]=='run':run_group(sys.argv[2])
    elif sys.argv[1]=='controls':controls()
    elif sys.argv[1]=='poststate':poststate()
    elif sys.argv[1]=='export':export()
    elif sys.argv[1]=='cleanup':cleanup()
    elif sys.argv[1]=='restart-guard':
        rt=Runtime();rt.check_owner(rt.names[1]);assert all(s['state'] in ('FINISHED','STOPPED') for s in rt.engine('ascan','view','scans',{})['scans']);docker(['restart',rt.names[1]])
        time.sleep(1);assert rt.check_owner(rt.names[1])['State']['Running'];print('owned guard restarted between campaigns')
    elif sys.argv[1]=='reconcile-catalog':
        rt,m=get();p=load('campaigns/foods-id.json');status=rt.engine('ascan','view','status',{'scanId':p['nativeId']});assert status['status']=='100'
        p['ruleCounts']={str(k):v for k,v in p['ruleCounts'].items()};save('campaigns/foods-id.json',p)
        rt.journal.append('reconcile',{'action':'terminal-after-local-serialization-error','id':p['id'],'nativeId':p['nativeId'],'status':status,'rerun':False})
        print(json.dumps({'id':p['id'],'nativeStatus':status,'rerun':False,'requests':p['applicationRequests']}))
    elif sys.argv[1]=='repair-static-read':
        rt,m=get();msg=seed(rt,{'id':'aux-bundle-read-repaired','method':'GET','path':'/swagger-ui/swagger-ui-bundle.js','technique':'public static asset baseline/passive'})
        save('static-read-repair.json',{'priorOutcome':'guard rejected response over 1MB after read-only GET','repair':'4MB target response cap, 8MB internal API reader; reserve unchanged','method':'GET','path':'/swagger-ui/swagger-ui-bundle.js','status':int(msg['responseHeader'].split()[1]),'responseBytes':len(msg['responseBody'].encode())});print(load('static-read-repair.json'))
