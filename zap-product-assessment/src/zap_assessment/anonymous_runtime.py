"""Dedicated backend HTTP namespace, reusing DockerRuntime ownership and transport."""
import json
import os
from pathlib import Path
import secrets
from types import SimpleNamespace
from urllib.parse import urlsplit
from .runtime import DockerRuntime,docker,ZAP,MCP_IMAGE
from .anonymous_product import save

ROOT=Path(__file__).resolve().parents[2]


def inspect_binding(container,environment,port):
    fmt='{"containerId":{{json .Id}},"imageId":{{json .Image}},"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},"project":{{json (index .Config.Labels "com.docker.compose.project")}},"networks":{{json .NetworkSettings.Networks}},"exposed":{{json .Config.ExposedPorts}}}'
    v=json.loads(docker(['inspect','--format',fmt,container]));nets=v.pop('networks');exposed=v.pop('exposed')
    if v.pop('project')!=environment or v.pop('running') is not True or len(nets)!=1 or str(port)+'/tcp' not in (exposed or {}):raise ValueError('unverified backend deployment/port')
    n=next(iter(nets.values()));v.update(networkId=n['NetworkID'],address=n['IPAddress'])
    aliases=[a for a in n.get('Aliases',[]) if a];origins=['http://'+h+':'+str(port) for h in [n['IPAddress'],*aliases]]
    return v,{'environment':environment,'targetBinding':v,'scannerOrigins':origins,'directOrigins':[]}


class AnonymousRuntime(DockerRuntime):
    def __init__(self,p,out,journal):
        super().__init__(p['runId'],out,journal);self.locked=p
        self.plan=SimpleNamespace(data={'runtime':json.loads((ROOT/'profiles/runtime-baseline.json').read_bytes())})
        self.config=self.root/'config';self.config.mkdir(mode=0o755);self.config.chmod(0o755)
        self.work=self.root/'workspace';self.work.mkdir(mode=0o777);self.work.chmod(0o777)
        self.capture=self.root/'guard';self.capture.mkdir(mode=0o777);self.capture.chmod(0o777)
        from .anonymous_private_body import materialize_guard_plan
        save(self.config,'guard-plan.json',materialize_guard_plan(p));(self.config/'guard-plan.json').chmod(0o444)
        save(self.config,'mode.json',{'caseId':None});(self.config/'mode.json').chmod(0o444)
        self.mcp_key=secrets.token_urlsafe(32);self.stop_timeout=60
    def sample(self):
        v=os.statvfs(self.root);sample={'hostFree':v.f_bavail*v.f_frsize}
        code="import os,json; s=os.statvfs('/'); m=dict(x.split(':',1) for x in open('/proc/meminfo')); print(json.dumps({'dockerFree':s.f_bavail*s.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024}))"
        sample.update(json.loads(docker(['exec','--user','1002:1002',self.anchor,'python','-c',code],timeout=4)))
        return sample
    def request(self,url,method='GET',headers=None,body=None,timeout=10):
        headers=dict(headers or {})
        if url.startswith('http://127.0.0.1:7456/'):headers['X-API-Key']=self.mcp_key
        return super().request(url,method,headers,body,timeout)
    def provision(self):
        p=self.locked;base=urlsplit(p['origin']);pin=self.plan.data['runtime'];back=p['targetBinding']
        self.commands={self.names[0]:['sleep','2400'],self.names[1]:['python','/guard.py','/config/guard-plan.json','/config/mode.json','/evidence'],
        self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=true','-config','autoupdate.checkOnStart=false','-config','connection.timeoutInSecs=8','-config','spider.processForm=false','-config','spider.postForm=false'],self.names[3]:[]}
        if getattr(self,'precreated_anchor',False):self.check_owner(self.anchor)
        else:self.create(self.anchor,pin['boundary'],['--no-healthcheck','--network',back['networkId'],'--cap-add','NET_ADMIN','--memory','64m'])
        rules=['iptables -P OUTPUT DROP','iptables -P INPUT DROP','iptables -P FORWARD DROP','ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP',
          'iptables -A INPUT -i lo -j ACCEPT','iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
          'iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 18888 -m owner --uid-owner 1000 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT',
          'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090 -m owner --uid-owner 1002 -j ACCEPT',
          f'iptables -A OUTPUT -p tcp -d {back["address"]} --dport {base.port or 80} -m owner --uid-owner 1003 -j ACCEPT']
        for rule in rules:docker(['exec',self.anchor,*rule.split()])
        save(self.root,'firewall.json',{'ipv4':docker(['exec',self.anchor,'iptables-save']),'ipv6':docker(['exec',self.anchor,'ip6tables-save'])})
        shared=['--no-healthcheck','--network','container:'+self.anchor,'--cap-drop','ALL','--security-opt','no-new-privileges','--pids-limit','256']
        self.create(self.names[1],pin['boundary'],[*shared,'--user','1003:1003','--memory','128m','-v',str(Path(__file__).with_name('anonymous_guard.py'))+':/guard.py:ro','-v',str(self.config)+':/config:ro','-v',str(self.capture)+':/evidence'])
        self.create(self.names[2],ZAP,[*shared,'--user','1000:1000','--memory','1200m','--cpus','2','-e','ZAP_MEMORY=800m','-v',str(self.work)+':/zap/wrk'])
        env={'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'api-key','MCP_API_KEY':self.mcp_key,'MCP_CLIENT_ID':'anonymous-research',
          'ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':'','ZAP_REPORT_DIRECTORY':'/zap/wrk','ZAP_ALLOW_LOCALHOST':'true','ZAP_ALLOW_PRIVATE_NETWORKS':'true',
          'ZAP_URL_WHITELIST':base.hostname,'MCP_SERVER_TOOLS_SURFACE':'expert','ZAP_SPIDER_THREAD_COUNT':'1','ZAP_MAX_ACTIVE_SCAN_DURATION':'3','ZAP_THREAD_PER_HOST':'1','ZAP_HOST_PER_SCAN':'1','ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1',
          'ZAP_SCAN_HISTORY_BACKEND':'in-memory','ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory','JAVA_TOOL_OPTIONS':'-Xmx320m','ZAP_INIT_CONNECTION_TIMEOUT':'90','MCP_PROTECTION_RATE_LIMIT_CAPACITY':'600','MCP_PROTECTION_RATE_LIMIT_REFILL_TOKENS':'600'}
        envfile=self.config/'private-mcp.env';envfile.write_text(''.join(k+'='+v+'\n' for k,v in env.items()));envfile.chmod(0o600)
        self.create(self.names[3],MCP_IMAGE,[*shared,'--user','1001:1000','--memory','448m','--cpus','1','--env-file',str(envfile),'-v',str(self.work)+':/zap/wrk'])
        pins={}
        for name in self.names:
            i=self.check_owner(name);pins[name]={'containerId':i['Id'],'imageId':i['Image'],'startedAt':i['State']['StartedAt']}
        save(self.root,'runtime-pins.json',{'images':{'zap':ZAP,'mcp':MCP_IMAGE,'boundary':pin['boundary']},'resources':pins,'mcpAuthentication':'api-key, namespace only, no host ports'})
    def boundary(self):
        b=self.locked['targetBinding'];port=urlsplit(self.locked['origin']).port or 80
        code="""import socket,json
result={}
for key,host,port in json.loads(INPUT):
 s=socket.socket(socket.AF_INET,socket.SOCK_STREAM);s.settimeout(.3)
 try:s.connect((host,port));result[key]=True
 except OSError:result[key]=False
 finally:s.close()
print(json.dumps(result))
""".replace('INPUT',repr(json.dumps([['proxy','127.0.0.1',18888],['backend-bypass',b['address'],port],['management','127.0.0.1',8090],['metadata','169.254.169.254',80],['external','1.1.1.1',80]])))
        v=json.loads(docker(['exec','--user','1000:1000',self.anchor,'python','-c',code]))
        if v.get('proxy') is not True or any(x for k,x in v.items() if k!='proxy'):raise ValueError('kernel boundary failed')
        save(self.root,'boundary-proof.json',v);return v
