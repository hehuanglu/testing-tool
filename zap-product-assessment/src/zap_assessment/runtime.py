from contextlib import nullcontext
"""Dedicated Docker namespace, fixed fixture port and kernel egress rules.

Owned scanner namespace primitives; target provisioning belongs to adapters.
"""
import json
import os
import subprocess
import time
from pathlib import Path
from .contracts import Blocked,ROOT

ZAP='zaproxy/zap-stable@sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6'
MCP_IMAGE='dtkmn/mcp-zap-server@sha256:c62be3c0622a52cd5e81747dde3c32117e480853ae2733bb3f3281434618f673'
PYTHON='python@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a'
# This script runs in the network namespace, with no host network or socket access.
PROBE=r'''
import sys,json,urllib.request,urllib.error,base64
x=json.load(sys.stdin)
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args):return None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
req=urllib.request.Request(x['url'],data=base64.b64decode(x['body']) if x.get('body') is not None else None,headers=x['headers'],method=x['method'])
try:r=opener.open(req,timeout=x['timeout'])
except urllib.error.HTTPError as e:r=e
body=r.read(2000001)
if len(body)>2000000:raise ValueError('response exceeds limit')
print(json.dumps({'status':r.code,'headers':{k.lower():v for k,v in r.headers.items()},'body':body.decode('utf-8')}))
'''

def docker(args,input=None,timeout=45):
    r=subprocess.run(['docker',*args],input=input,capture_output=True,timeout=timeout)
    if r.returncode: raise Blocked('Docker operation failed: '+(r.stderr.decode(errors='replace')[:300]))
    return r.stdout.decode()

def engine_bool(value):
    # ZAP's scanners API encodes booleans as the strings true/false.
    # Never use bool(value): bool('false') would enable a disabled rule.
    if type(value) is bool:return value
    if type(value) is str and value in ('true','false'):return value=='true'
    raise Blocked('engine boolean state unknown')

class DockerRuntime:
    def __init__(self,run_id,run_dir,journal):
        self.run_id=run_id; self.root=Path(run_dir).resolve(); self.journal=journal; self.anchor=f'zpa-{run_id}-net'
        self.names=[f'zpa-{run_id}-{x}' for x in ['net','fixture','zap','mcp']]
        self.created=[]; self.rate=2; self.last_send=0
    def create(self,name,image,args):
        image_id=docker(['image','inspect','--format','{{.Id}}',image]).strip()
        self.journal.append('intent',{'action':'container-create','resource':name,'image':image,'expectedImageId':image_id,'createdByRun':self.run_id})
        cid=docker(['run','-d','--name',name,'--label',f'zpa.run={self.run_id}',*args,image,*self.commands.get(name,[])]) .strip()
        self.created.append(name); self.journal.append('ack',{'action':'container-create','resource':name,'containerId':cid})
    def provision(self):
        from .adapters import prepare_synthetic
        prepare_synthetic(self.plan,self.root)
        fixture=self.root/'fixture'; fixture.mkdir(mode=0o777,exist_ok=True); os.chmod(fixture,0o777)
        wrk=self.root/'zap-workspace'; wrk.mkdir(mode=0o777); os.chmod(wrk,0o777)
        # Firewall helper image ID is pinned at preflight and retained in provenance.
        baseline=getattr(self,'runtime_baseline',json.loads((ROOT/'profiles'/'runtime-baseline.json').read_text()))
        if (baseline['zap'],baseline['mcp'],baseline['python'])!=(ZAP,MCP_IMAGE,PYTHON): raise Blocked('runtime baseline drift')
        helper=baseline['boundary']
        docker(['image','inspect',helper])
        self.commands={self.names[0]:['sleep','3600'],self.names[1]:['python','-m','zap_assessment.fixture'],self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=true','-config','connection.timeoutInSecs=2','-config','spider.thread=1','-config','spider.maxDuration=5','-config','spider.processForm=false','-config','spider.postForm=false','-config','autoupdate.checkOnStart=false'],self.names[3]:[]}
        self.create(self.anchor,helper,['--network','none','--cap-add','NET_ADMIN'])
        self.configure_firewall()
        shared=['--no-healthcheck','--network',f'container:{self.anchor}','--cap-drop','ALL','--security-opt','no-new-privileges']
        self.create(self.names[1],PYTHON,['--memory','128m','--cpus','1',*shared,'--user','1003:1003','-e','PYTHONPATH=/package/src','-v',f'{ROOT}:/package:ro','-v',f'{fixture}:/fixture','-v',f'{wrk}:/capture:ro'])
        self.create(self.names[2],ZAP,['--memory','1024m','--cpus','2',*shared,'--user','1000:1000','-e','ZAP_MEMORY=768m','-v',f'{wrk}:/zap/wrk'])
        env={'SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'none','MCP_SECURITY_ENABLED':'false','ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':'','ZAP_REPORT_DIRECTORY':'/zap/wrk','ZAP_ALLOW_LOCALHOST':'true','ZAP_ALLOW_PRIVATE_NETWORKS':'false','ZAP_URL_BLACKLIST':'169.254.0.0/16','ZAP_URL_WHITELIST':'127.0.0.1','ZAP_SPIDER_THREAD_COUNT':'1','ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1','ZAP_MAX_CONCURRENT_SPIDER_SCANS':'1','MCP_SERVER_TOOLS_SURFACE':'guided','ZAP_SCAN_HISTORY_BACKEND':'in-memory','ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory','JAVA_TOOL_OPTIONS':'-Xmx384m','ZAP_INIT_CONNECTION_TIMEOUT':'60'}
        opts=['--memory','512m','--cpus','2',*shared,'--user','1001:1001','-v',f'{wrk}:/zap/wrk']
        for k,v in env.items(): opts+=['-e',k+'='+v]
        self.create(self.names[3],MCP_IMAGE,opts)
        return {'zapImage':ZAP,'mcpImage':MCP_IMAGE,'pythonImage':PYTHON,'boundaryImageId':helper,'network':'none+UID-output-firewall+origin-guard','namespace':self.anchor}
    def configure_firewall(self):
        self.journal.append('intent',{'action':'namespace-firewall','resource':self.anchor})
        # Replies to established API/fixture connections remain possible. Fresh
        # connections by scanner UID can reach only the approved target origin.
        rules=['iptables -P OUTPUT DROP','iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
               'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 18888 -m owner --uid-owner 1000 -j ACCEPT',
               'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT',
               'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090,18888 -m owner --uid-owner 1002 -j ACCEPT',
               'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 18080 -m owner --uid-owner 1003 -j ACCEPT','ip6tables -P OUTPUT DROP']
        for rule in rules: docker(['exec',self.anchor,*rule.split()])
        self.journal.append('ack',{'action':'namespace-firewall','resource':self.anchor})
    def request(self,url,method='GET',headers=None,body=None,timeout=10):
        import base64
        payload={'url':url,'method':method,'headers':headers or {},'body':base64.b64encode(body).decode() if body is not None else None,'timeout':timeout}
        return json.loads(docker(['exec','-i','--user','1002:1002',self.anchor,'python','-c',PROBE],json.dumps(payload).encode(),timeout=timeout+10))
    def target_request(self,url):
        from .egress import request_target
        request_target('GET',url,{'Host':'127.0.0.1:18080'})
        code="""import http.client,json,sys
url=json.load(sys.stdin)['url'];c=http.client.HTTPConnection('127.0.0.1',18888,timeout=5)
c.request('GET',url,headers={'Host':'127.0.0.1:18080','Connection':'close'});r=c.getresponse();data=r.read(1048577)
if len(data)>1048576:raise ValueError('target response limit')
print(json.dumps({'status':r.status,'body':data.decode('utf-8')}));c.close()
"""
        return json.loads(docker(['exec','-i','--user','1002:1002',self.anchor,'python','-c',code],json.dumps({'url':url}).encode(),timeout=15))
    def engine(self,component,kind,name,args):
        from urllib.parse import urlencode
        # Only hard-coded caller actions reach this API. Nothing from target data selects an action.
        r=self.request(f'http://127.0.0.1:8090/JSON/{component}/{kind}/{name}/?'+urlencode(args),timeout=15)
        if r['status']!=200: raise Blocked('engine API error')
        result=json.loads(r['body'])
        if 'code' in result: raise Blocked('engine API rejected '+name)
        return result
    def wait_health(self,timeout=120):
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if not self.check_owner(self.names[3])['State']['Running']: raise Blocked('dedicated MCP exited before healthy')
            try:
                r=self.request('http://127.0.0.1:7456/actuator/health',timeout=2)
                if r['status']==200 and json.loads(r['body'])['status']=='UP': return
            except Exception: pass
            time.sleep(1)
        raise TimeoutError('dedicated scanner health timeout')
    def configure_rate(self,rate):
        self.journal.append('intent',{'action':'rate-limit','requestsPerSecond':rate})
        self.engine('network','action','setConnectionTimeout',{'timeout':2})
        self.engine('network','action','setHttpProxy',{'host':'127.0.0.1','port':18888})
        self.engine('network','action','setHttpProxyAuthEnabled',{'enabled':'false'})
        exclusions=self.engine('network','view','getHttpProxyExclusions',{})
        for exclusion in exclusions.get('getHttpProxyExclusions',[]):
            self.engine('network','action','setHttpProxyExclusionEnabled',{'host':exclusion['host'],'enabled':'false'})
        self.engine('network','action','setHttpProxyEnabled',{'enabled':'true'})
        proxy=self.engine('network','view','getHttpProxy',{})
        enabled=self.engine('network','view','isHttpProxyEnabled',{})
        config=proxy.get('getHttpProxy',{})
        if config.get('host')!='127.0.0.1' or int(config.get('port',0))!=18888 or str(enabled.get('isHttpProxyEnabled')).lower()!='true': raise Blocked('mandatory proxy readback mismatch')
        self.guard_proof=self.guard_probe()
        self.journal.append('ack',{'action':'mandatory-origin-guard','host':'127.0.0.1','port':18888,'enabled':True,'proof':self.guard_proof})
        match_host=getattr(self,'match_host','127.0.0.1')
        self.engine('network','action','addRateLimitRule',{'description':'zpa-approved-origin','enabled':'true','matchRegex':'false','matchString':match_host,'requestsPerSecond':int(rate),'groupBy':'rule'})
        result=self.engine('network','view','getRateLimitRules',{})
        rules=result.get('getRateLimitRules')
        if not isinstance(rules,list) or len(rules)!=1 or rules[0].get('enabled') is not True or rules[0].get('requestsPerSecond')!=int(rate) or rules[0].get('matchString')!=match_host or rules[0].get('groupBy')!='RULE': raise Blocked('rate limit readback mismatch')
        self.journal.append('ack',{'action':'rate-limit','rules':result})
        return result
    def check_owner(self,name,timeout=45):
        info=json.loads(docker(['inspect',name],timeout=timeout))[0]
        return self.verify_owner(name,info)
    def verify_owner(self,name,info):
        """Same identity checks for a single or atomically batched inspect read."""
        if (info.get('Config',{}).get('Labels') or {}).get('zpa.run')!=self.run_id: raise Blocked('container ownership mismatch')
        expected=[e['data']['containerId'] for e in self.journal.events if e['kind']=='ack' and e['data'].get('action')=='container-create' and e['data'].get('resource')==name]
        if expected and info['Id']!=expected[-1]: raise Blocked('container identity changed')
        if not any(e['kind']=='intent' and e['data'].get('action')=='container-create' and e['data'].get('resource')==name and e['data'].get('createdByRun')==self.run_id for e in self.journal.events): raise Blocked('container creation intent absent')
        intents=[e['data'] for e in self.journal.events if e['kind']=='intent' and e['data'].get('action')=='container-create' and e['data'].get('resource')==name]
        pin=intents[-1].get('expectedImageId')
        if not expected and not pin:raise Blocked('lost-ACK image identity unproven')
        if pin and info.get('Image')!=pin:raise Blocked('container image identity changed')
        return info
    def owned_names(self):
        measurements=[e['data']['resource'] for e in self.journal.events if e['kind']=='intent' and e['data'].get('action')=='container-create' and e['data'].get('measurementOnly') is True and e['data'].get('createdByRun')==self.run_id]
        return list(dict.fromkeys([*self.names,*measurements]))
    def terminate(self,deadline=None):
        deadline=deadline if deadline is not None else time.monotonic()+getattr(self,'stop_timeout',120)
        primary=[self.names[2],self.names[3],self.names[1],self.names[0]]
        for name in [*primary,*[n for n in self.owned_names() if n not in primary]]:
            if name==getattr(self,'cleanup_measurement_helper',None):continue
            # A gauge must not race a cgroup disappearing or a removal ACK.
            # Serialize one bounded mutation at a time, never the whole cleanup.
            with getattr(self,'cleanup_resource_lock',nullcontext()):
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('stop deadline exceeded')
                try:info=self.check_owner(name,timeout=max(.1,remaining))
                except Blocked:
                    if docker(['ps','-aq','--filter',f'name=^{name}$'],timeout=max(.1,deadline-time.monotonic())).strip():raise
                    continue
                if not info['State']['Running']:continue
                self.journal.append('intent',{'action':'container-stop','resource':name})
                docker(['stop','--time',str(max(1,min(1 if getattr(self,'cleanup_measurement_helper',None) else 5,int(remaining)))),name],timeout=max(.1,remaining))
                if self.check_owner(name,timeout=max(.1,deadline-time.monotonic()))['State']['Running']:raise Blocked('stop unconfirmed')
                self.journal.append('ack',{'action':'container-stopped','resource':name})
            if hasattr(self,'cleanup_resource_tick'):self.cleanup_resource_tick()
        return True
    def cleanup(self):
        deadline=time.monotonic()+getattr(self,'stop_timeout',120)
        self.terminate(deadline=deadline)
        helper=getattr(self,'cleanup_measurement_helper',None)
        names=[n for n in reversed(self.owned_names()) if n!=helper]+([helper] if helper else [])
        for name in names:
            if name==helper:
                self.cleanup_measurement_close()
                self.check_owner(name,timeout=2)
                self.journal.append('intent',{'action':'container-stop','resource':name})
                docker(['stop','--time','1',name],timeout=3)
                if self.check_owner(name,timeout=2)['State']['Running']:raise Blocked('measurement helper stop unconfirmed')
                self.journal.append('ack',{'action':'container-stopped','resource':name})
            with getattr(self,'cleanup_resource_lock',nullcontext()):
                remaining=deadline-time.monotonic()
                if remaining<=0:raise TimeoutError('cleanup deadline exceeded')
                try:self.check_owner(name,timeout=max(.1,remaining))
                except Blocked:
                    if docker(['ps','-aq','--filter',f'name=^{name}$'],timeout=max(.1,deadline-time.monotonic())).strip():raise
                    continue
                self.journal.append('intent',{'action':'container-remove','resource':name})
                docker(['rm',name],timeout=max(.1,deadline-time.monotonic()));self.journal.append('ack',{'action':'container-removed','resource':name})
            if name!=helper and hasattr(self,'cleanup_resource_tick'):self.cleanup_resource_tick()
        if any(docker(['ps','-aq','--filter',f'name=^{n}$'],timeout=max(.1,deadline-time.monotonic())).strip() for n in self.owned_names()):raise Blocked('cleanup verification failed')
        return True

    def resource_sample(self):
        """A bounded owned no-network helper measures Docker's backing fs and VM RAM.

        Measurement creates no scanner or target traffic. Its exact intent/name/
        immutable image are retained so lost ACK can be reconciled stop-only.
        """
        host=os.statvfs(self.root)
        helper=self.plan.data['runtime']['boundary']
        image_id=docker(['image','inspect','--format','{{.Id}}',helper],timeout=5).strip()
        number=sum(e['kind']=='intent' and e['data'].get('measurementOnly') is True for e in self.journal.events)
        name=f'zpa-{self.run_id}-measure-{number}'
        self.journal.append('intent',{'action':'container-create','resource':name,'image':helper,'expectedImageId':image_id,'createdByRun':self.run_id,'measurementOnly':True})
        self.created.append(name)
        code="import os,json; s=os.statvfs('/'); m=dict(x.split(':',1) for x in open('/proc/meminfo')); print(json.dumps({'dockerFree':s.f_bavail*s.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024}))"
        output=docker(['run','--rm','--name',name,'--label','zpa.run='+self.run_id,'--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges','--memory','32m','--pids-limit','32',helper,'python','-c',code],timeout=5)
        data=json.loads(output)
        if docker(['ps','-aq','--filter',f'name=^{name}$'],timeout=5).strip():raise Blocked('resource probe cleanup unconfirmed')
        self.journal.append('measurement-complete',{'resource':name,'sample':data})
        return {'hostFree':host.f_bavail*host.f_frsize,'dockerAvailable':True,**data}
    def policy_inventory(self):
        """Capture effective API state. Missing script content pin fails closed."""
        paths=['autoupdate/view/installedAddons','script/view/listScripts','ascan/view/scanners',
               'ascan/view/optionTargetParamsInjectable','ascan/view/optionTargetParamsEnabledRPC','ascan/view/optionAddQueryParam']
        code="""import http.client,json,sys,time
deadline=time.monotonic()+3;result=[]
for path in json.load(sys.stdin):
 remaining=deadline-time.monotonic()
 if remaining<=0:raise TimeoutError('inventory deadline')
 c=http.client.HTTPConnection('127.0.0.1',8090,timeout=min(1,remaining))
 try:
  c.request('GET','/JSON/'+path+'/');r=c.getresponse();b=r.read(4194305)
  if r.status!=200 or len(b)>4194304:raise ValueError('inventory response')
  data=json.loads(b)
  if 'code' in data:raise ValueError('inventory endpoint unsupported')
  result.append(data)
 finally:c.close()
print(json.dumps(result))
"""
        self.check_owner(self.anchor,timeout=1)
        values=json.loads(docker(['exec','-i','--user','1002:1002',self.anchor,'python','-c',code],json.dumps(paths).encode(),timeout=4))
        addons=values[0]['installedAddons'];scripts=values[1];rules=values[2]['scanners']
        options=dict(zip(paths[3:],values[3:]))
        def entries(value):
            if isinstance(value,dict):
                if 'name' in value and 'type' in value:yield value
                else:
                    for v in value.values():yield from entries(v)
            elif isinstance(value,list):
                for v in value:yield from entries(v)
        return {'addons':[{'id':a['id'],'version':str(a['version'])} for a in addons],
                'scripts':[{'name':s['name'],'type':s['type'],'enabled':s.get('enabled'),
                            'sha256':s.get('sha256','unproven')} for s in entries(scripts)],
                'rules':[{'id':str(r['id']),'enabled':engine_bool(r.get('enabled'))} for r in rules],
                'inputVectors':[json.dumps(options,sort_keys=True,separators=(',',':'))]}
    def policy_traffic(self):
        # Legacy guard records have no independent producer/rule correlation.
        # Never promote scanProgress alone to proof of passive/background egress.
        return {'events':[],'complete':False}
    def observations(self):
        f=self.root/'fixture'
        requests=[json.loads(x) for x in (f/'requests.jsonl').read_text().splitlines()] if (f/'requests.jsonl').exists() else []
        forbidden=(f/'forbidden.jsonl').read_text().splitlines() if (f/'forbidden.jsonl').exists() else []
        egress=[json.loads(x) for x in (f/'egress.jsonl').read_text().splitlines()] if (f/'egress.jsonl').exists() else []
        return {'originGuardProof':self.guard_proof,'egress':egress,'requests':requests,'forbiddenRequests':len(forbidden),'boundaryProbe':self.boundary_probe(),'firewall':docker(['exec',self.anchor,'iptables','-nvL','OUTPUT'])}

    def boundary_probe(self):
        code="""import socket,json
checks={}
for label,host,port in [('approvedProxy','127.0.0.1',18888),('directTarget','127.0.0.1',18080),('outside-port','127.0.0.1',18081),('control-api','127.0.0.1',8090),('metadata','169.254.169.254',80),('external','1.1.1.1',80),('ipv6','::1',18080)]:
 s=socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET,socket.SOCK_STREAM);s.settimeout(.3)
 try:s.connect((host,port));checks[label]=True
 except OSError:checks[label]=False
 finally:s.close()
print(json.dumps(checks))
"""
        result=json.loads(docker(['exec','--user','1000:1000',self.anchor,'python','-c',code]))
        if not result.get('approvedProxy') or any(v for k,v in result.items() if k!='approvedProxy'): raise Blocked('kernel boundary probe failed')
        return result

    def guard_probe(self):
        code="""import http.client,json
checks={}
for label,method,url,host in [('allowedTarget','GET','http://127.0.0.1:18080/health','127.0.0.1:18080'),('outsidePort','GET','http://127.0.0.1:18081/canary','127.0.0.1:18081'),('hostAlias','GET','http://localhost:18080/alias-canary','localhost:18080'),('schemeChange','GET','https://127.0.0.1:18080/scheme-canary','127.0.0.1:18080'),('connectTunnel','CONNECT','127.0.0.1:18080','127.0.0.1:18080'),('metadata','GET','http://169.254.169.254/','169.254.169.254'),('hostOverride','GET','http://127.0.0.1:18080/health','localhost:18080')]:
 c=http.client.HTTPConnection('127.0.0.1',18888,timeout=5);c.request(method,url,headers={'Host':host,'Connection':'close'});r=c.getresponse();checks[label]=r.status;r.read();c.close()
print(json.dumps(checks))
"""
        result=json.loads(docker(['exec','--user','1000:1000',self.anchor,'python','-c',code]))
        if result.get('allowedTarget')!=200 or any(v!=403 for k,v in result.items() if k!='allowedTarget'): raise Blocked('origin guard proof failed')
        return result
