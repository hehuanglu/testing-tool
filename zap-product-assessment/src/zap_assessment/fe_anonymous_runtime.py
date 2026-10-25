"""FE-only isolated Docker namespace. Reuses ownership, never backend transport."""
import json
import os
from pathlib import Path
import secrets
import subprocess
from types import SimpleNamespace
from urllib.parse import urlsplit
from .runtime import DockerRuntime,docker,ZAP
from .fe_anonymous_contract import save,load,digest

ROOT=Path(__file__).resolve().parents[2]

class FERuntime(DockerRuntime):
    broker_module='fe_anonymous_transport'
    def mcp_environment(self,env):return env
    def mcp_mounts(self):return []
    def __init__(self,plan,out,journal):
        super().__init__(plan['runId'],out,journal);self.p=plan
        self.names=[f'zpa-{self.run_id}-{n}' for n in ('net','broker','zap','mcp','browser')];self.anchor=self.names[0]
        self.plan=SimpleNamespace(data={'runtime':load(ROOT/'profiles/runtime-baseline.json')});self.stop_timeout=60
        for name in ('config','workspace','broker','browser'):
            f=self.root/name;f.mkdir(mode=0o777);f.chmod(0o777)
        self.config=self.root/'config';self.work=self.root/'workspace';self.capture=self.root/'broker'
        self.mcp_key=secrets.token_urlsafe(32);self.zap_key=secrets.token_urlsafe(32)
        save(self.config,'plan.json',plan);(self.config/'plan.json').chmod(0o444)
        self.mode(None)
    def mode(self,case,*,transition=False,campaign=None,fixed=None,baseline_hash=None):
        path=save(self.config,'mode.pending',{'caseId':case,'transition':transition,'campaignId':campaign,'fixedFields':fixed or {},'baselineHash':baseline_hash});path.chmod(0o444);os.replace(path,self.config/'mode.json')
    def certificates(self):
        import shutil
        shutil.copyfile(self.p['selection']['certificate']['path'],self.config/'upstream.crt');(self.config/'upstream.crt').chmod(0o444)
        hostname=urlsplit(self.p['selection']['origin']).hostname
        # Owned short-lived broker cert; product key never read or mounted.
        subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN='+hostname,'-addext','subjectAltName=DNS:'+hostname,'-keyout',str(self.config/'broker.key'),'-out',str(self.config/'broker.crt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        (self.config/'broker.key').chmod(0o444);(self.config/'broker.crt').chmod(0o444)
        save(self.config,'policies.json',{'policies':{'Certificates':{'Install':['/config/zap-root.crt']},'DisableAppUpdate':True,'DisableTelemetry':True}})
        (self.config/'policies.json').chmod(0o444)
    def engine(self,component,kind,name,args):
        # Controller authentication; key stays out of persisted typed engine requests.
        from urllib.parse import urlencode
        r=self.request('http://127.0.0.1:8090/JSON/'+component+'/'+kind+'/'+name+'/?'+urlencode(args),timeout=15)
        if r['status']!=200:raise ValueError('engine API HTTP failure')
        result=json.loads(r['body'])
        if 'code' in result:raise ValueError('engine rejected '+name)
        return result
    def provision(self):
        sel=self.p['selection'];pin=self.plan.data['runtime'];self.certificates()
        self.commands={self.names[0]:['sleep','7200'],self.names[1]:['python','/broker.py','/config/plan.json','/config','/evidence'],
          self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=false','-config','api.key='+self.zap_key,'-config','api.disableui=true','-config','autoupdate.checkOnStart=false','-config','connection.timeoutInSecs=10','-config','spider.processForm=false','-config','spider.postForm=false'],self.names[3]:[],self.names[4]:['sleep','7200']}
        extra_hosts=[] if urlsplit(sel['origin']).hostname=='localhost' else ['--add-host',urlsplit(sel['origin']).hostname+':'+sel['binding']['address']]
        self.create(self.anchor,pin['boundary'],['--no-healthcheck','--network',sel['binding']['networkId'],'--cap-add','NET_ADMIN','--memory','64m',*extra_hosts])
        base=['iptables -P OUTPUT DROP','iptables -P INPUT DROP','iptables -P FORWARD DROP','ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP',
          'iptables -A INPUT -i lo -j ACCEPT','iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT','iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 18888 -m owner --uid-owner 1000 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1000 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 1024:7455,7457:65535 -m owner --uid-owner 1000 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090,4444 -m owner --uid-owner 1002 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 8090,2828,4444 -m owner --uid-owner 1004 -j ACCEPT',
          f'iptables -A OUTPUT -p tcp -d {sel["binding"]["address"]} --dport {sel["targetPort"]} -m owner --uid-owner 1003 -j ACCEPT']
        for rule in base:docker(['exec',self.anchor,*rule.split()])
        save(self.root,'FIREWALL.json',{'ipv4':docker(['exec',self.anchor,'iptables-save']),'ipv6':docker(['exec',self.anchor,'ip6tables-save'])})
        shared=['--no-healthcheck','--network','container:'+self.anchor,'--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','512']
        broker_args=['--no-healthcheck','--network','container:'+self.anchor,'--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','512','--user','1003:1003','--memory','160m','-e','PYTHONPATH=/package/src','-v',str(ROOT)+':/package:ro','-v',str(self.config)+':/config:ro','-v',str(self.capture)+':/evidence']
        self.commands[self.names[1]]=['python','-m','zap_assessment.'+self.broker_module,'/config/plan.json','/config','/evidence']
        self.create(self.names[1],pin['boundary'],broker_args)
        self.commands[self.names[2]]+=['-config','selenium.firefoxDriver=/owned-geckodriver']
        self.create(self.names[2],sel['images']['zap'],[*shared,'--user','1000:1000','--memory','1536m','--cpus','2','-e','ZAP_MEMORY=800m','-e','JAVA_TOOL_OPTIONS=-Djava.net.preferIPv4Stack=true','-v',str(self.work)+':/zap/wrk','-v',str(self.config)+':/config:ro','-v',str(Path(__file__).with_name('fe_anonymous_geckodriver.py'))+':/owned-geckodriver:ro','-v',str(self.config/'policies.json')+':/usr/share/firefox-esr/distribution/policies.json:ro'])
        env={'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'api-key','MCP_API_KEY':self.mcp_key,'MCP_CLIENT_ID':'fe-anonymous-research',
             'ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':self.zap_key,'ZAP_REPORT_DIRECTORY':'/zap/wrk','ZAP_ALLOW_LOCALHOST':'true','ZAP_ALLOW_PRIVATE_NETWORKS':'true','ZAP_URL_WHITELIST':urlsplit(sel['origin']).hostname,
             'MCP_SERVER_TOOLS_SURFACE':'guided','ZAP_SCAN_HISTORY_BACKEND':'in-memory','ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory','JAVA_TOOL_OPTIONS':'-Xmx320m','ZAP_INIT_CONNECTION_TIMEOUT':'90','MCP_PROTECTION_RATE_LIMIT_CAPACITY':'600','MCP_PROTECTION_RATE_LIMIT_REFILL_TOKENS':'600',
             'ZAP_THREAD_PER_HOST':'1','ZAP_HOST_PER_SCAN':'1','ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1','ZAP_MAX_CONCURRENT_SPIDER_SCANS':'1'}
        env=self.mcp_environment(env)
        envfile=self.config/'private-mcp.env';envfile.write_text(''.join(k+'='+v+'\n' for k,v in env.items()));envfile.chmod(0o600)
        self.create(self.names[3],sel['images']['mcp'],[*shared,'--user','1001:1000','--memory','448m','--cpus','1','--env-file',str(envfile),'-v',sel['jar']['path']+':/app/app.jar:ro','-v',str(self.work)+':/zap/wrk',*self.mcp_mounts()])
        # Trust only the owned ZAP root in Firefox policy, installed in each fresh profile.
        self.wait_health()
        cert=self.request('http://127.0.0.1:8090/OTHER/core/other/rootcert/')['body']
        if 'BEGIN CERTIFICATE' not in cert:raise ValueError('ZAP root certificate export')
        (self.config/'zap-root.crt').write_text(cert);(self.config/'zap-root.crt').chmod(0o444)
        self.create(self.names[4],sel['images']['browser'],[*shared,'--user','1004:1004','--memory','1400m','--cpus','2','-e','HOME=/browser/home','-e','PYTHONPATH=/package/src',
          '-v',str(ROOT)+':/package:ro','-v',str(self.root/'browser')+':/browser','-v',str(self.config)+':/config:ro','-v',str(self.config/'policies.json')+':/usr/share/firefox-esr/distribution/policies.json:ro'])
        save(self.root,'RUNTIME_PINS.json',{n:{'containerId':(i:=self.check_owner(n))['Id'],'imageId':i['Image'],'startedAt':i['State']['StartedAt']} for n in self.names})
    def request(self,url,method='GET',headers=None,body=None,timeout=10):
        headers=dict(headers or {})
        if url.startswith('http://127.0.0.1:7456/'):headers['X-API-Key']=self.mcp_key
        if url.startswith('http://127.0.0.1:8090/'):headers['X-ZAP-API-Key']=self.zap_key
        return super().request(url,method,headers,body,timeout)
    def sample(self):
        s=os.statvfs(self.root)
        code="import os,json;v=os.statvfs('/');m=dict(x.split(':',1) for x in open('/proc/meminfo'));print(json.dumps({'dockerFree':v.f_bavail*v.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024}))"
        v=json.loads(docker(['exec','--user','1002:1002',self.anchor,'python','-c',code],timeout=5));v['hostFree']=s.f_bavail*s.f_frsize
        raw=docker(['stats','--no-stream','--format','{{json .}}',*self.names],timeout=10)
        v['containers']=[json.loads(x) for x in raw.splitlines()]
        v['cgroups']={}
        for name in self.names:
            try:
                values=docker(['exec','--user','1002:1002',name,'cat','/sys/fs/cgroup/memory.peak','/sys/fs/cgroup/memory.events','/sys/fs/cgroup/pids.peak'],timeout=3).splitlines()
                v['cgroups'][name]={'memoryPeakBytes':int(values[0]),'memoryEvents':values[1:-1],'pidsPeak':int(values[-1])}
            except Exception as e:v['cgroups'][name]={'sampleMissed':True,'errorType':type(e).__name__}
        return v
    def boundary(self):
        b=self.p['selection']['binding'];port=self.p['selection']['targetPort']
        probes=[['zap','127.0.0.1',8090],['broker-bypass','127.0.0.1',18888],['direct-fe',b['address'],port],['canonical-direct','127.0.0.1',urlsplit(self.p['selection']['origin']).port or 443],['management','127.0.0.1',7456]]
        code="import socket,json;out={};\nfor k,h,p in "+repr(probes)+":\n s=socket.socket();s.settimeout(.3);out[k]=s.connect_ex((h,p))==0;s.close()\nprint(json.dumps(out))"
        v=json.loads(docker(['exec','--user','1004:1004',self.anchor,'python','-c',code]))
        if v.get('zap') is not True or any(x for k,x in v.items() if k!='zap'):raise ValueError('browser kernel bypass')
        save(self.root,'BOUNDARY.json',v);return v
    def terminate(self,deadline=None):
        # Browser producer stops before broker/ZAP; inherited cleanup verifies every owned identity.
        try:
            info=self.check_owner(self.names[4])
            if info['State']['Running']:
                self.journal.append('intent',{'action':'container-stop','resource':self.names[4]});docker(['stop','--time','2',self.names[4]])
                self.journal.append('ack',{'action':'container-stopped','resource':self.names[4]})
        except Exception:
            if docker(['ps','-aq','--filter','name=^'+self.names[4]+'$']).strip():raise
        return super().terminate(deadline)
