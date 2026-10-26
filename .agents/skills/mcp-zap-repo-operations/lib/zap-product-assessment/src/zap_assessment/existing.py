"""Borrow an existing Docker target; own only scanner, guard, network namespace.

Inspect exposes whitelisted identity fields only. No target env or credentials.
"""
import json
import os
from urllib.parse import urlsplit
from .contracts import ROOT,Blocked,canonical,validate_locked_plan
from .runtime import DockerRuntime,docker,ZAP,MCP_IMAGE,PYTHON

META='{{json .Id}} {{json .Image}} {{json .State.Running}} {{json .State.StartedAt}} {{json .NetworkSettings.Networks}}'
def target_metadata(container):
    # NetworkSettings.Networks contains only network identity/address data.
    raw=docker(['inspect','--format',META,container]).strip();dec=json.JSONDecoder();fields=[]
    while raw:
        value,end=dec.raw_decode(raw);fields.append(value);raw=raw[end:].lstrip()
    cid,image,running,started,networks=fields
    return {'containerId':cid,'imageId':image,'running':running,'startedAt':started,'networks':{n:{'networkId':v['NetworkID'],'address':v['IPAddress']} for n,v in networks.items()}}

class ExistingDockerRuntime(DockerRuntime):
    def __init__(self,*args):
        super().__init__(*args)
        self.names=[f'zpa-{self.run_id}-{x}' for x in ['net','guard','zap','mcp']]
        self.import_volume=f'zpa-{self.run_id}-imports'
    def assert_binding(self):
        expected=self.plan.data['product']['binding'];observed=target_metadata(expected['containerId'])
        if not observed['running'] or any(observed[k]!=expected[k] for k in ('containerId','imageId','startedAt')) or {'networkId':expected['networkId'],'address':expected['address']} not in observed['networks'].values():raise Blocked('borrowed target identity/build/network drift')
        return observed
    def preflight(self):
        validate_locked_plan(self.plan)
        self.before=self.assert_binding()
        if self.plan.data['product']['environment']['kind']!='synthetic':
            mounts=json.loads(docker(['inspect','--format','{{json .Mounts}}',self.plan.data['product']['binding']['containerId']]))
            if mounts:raise Blocked('mounted product application identity unsupported; image-only binding insufficient')
        network=json.loads(docker(['network','inspect','--format','{{json .}}',self.plan.data['product']['binding']['networkId']]))
        if network['Driver']!='bridge' or network['Scope']!='local' or network.get('Ingress'):raise Blocked('unsupported target network topology')
    def provision(self):
        self.preflight();d=self.plan.data;b=d['product']['binding'];baseline=d['runtime']
        if (baseline['zap'],baseline['mcp'],baseline['python'])!=(ZAP,MCP_IMAGE,PYTHON):raise Blocked('runtime baseline drift')
        wrk=self.root/'zap-workspace';imports=self.import_volume;guard=self.root/'guard'
        for folder in (wrk,guard):folder.mkdir(mode=0o777);os.chmod(folder,0o777)
        # Guard reads only immutable normalized plan, not arbitrary profile paths.
        config=self.root/'guard-config';config.mkdir(mode=0o755);os.chmod(config,0o755)
        (config/'plan.json').write_bytes(self.plan.encoded);os.chmod(config/'plan.json',0o444)
        # UID1001 must have a named POSIX principal for upstream's strict writer check.
        (config/'passwd').write_text('root:x:0:0:root:/root:/sbin/nologin\napp:x:1000:1000:app:/home/app:/sbin/nologin\nmcp:x:1001:1000:mcp:/home/app:/sbin/nologin\n')
        os.chmod(config/'passwd',0o444)
        self.journal.append('intent',{'action':'volume-create','resource':self.import_volume,'createdByRun':self.run_id})
        docker(['volume','create','--label','zpa.run='+self.run_id,self.import_volume])
        volume=json.loads(docker(['volume','inspect',self.import_volume]))[0]
        self.journal.append('ack',{'action':'volume-create','resource':self.import_volume,'createdAt':volume['CreatedAt']})
        self.commands={self.names[0]:['sleep','3600'],self.names[1]:['python','-m','zap_assessment.guard_server'],self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=true','-config','connection.timeoutInSecs=2','-config','spider.thread=1','-config','spider.maxDuration=5','-config','spider.processForm=false','-config','spider.postForm=false','-config','autoupdate.checkOnStart=false'],self.names[3]:[]}
        docker(['image','inspect',baseline['boundary']])
        # Only inert PID1 (sleep) exists until DROP rules are installed. Docker
        # refuses connecting a namespace created in its special 'none' mode.
        self.create(self.anchor,baseline['boundary'],['--no-healthcheck','--network',b['networkId'],'--cap-add','NET_ADMIN','-v',f'{imports}:/tmp/zpa-imports'])
        self.configure_firewall()
        self.journal.append('intent',{'action':'prepare-content-staging','resource':self.names[0]})
        docker(['exec',self.anchor,'chown','1001:1000','/tmp/zpa-imports'])
        docker(['exec',self.anchor,'chmod','0750','/tmp/zpa-imports'])
        self.journal.append('ack',{'action':'prepare-content-staging','resource':self.names[0]})
        shared=['--no-healthcheck','--network',f'container:{self.anchor}','--cap-drop','ALL','--security-opt','no-new-privileges']
        # The guard verifies the digest of the fully validated read-only plan.
        self.create(self.names[1],baseline['boundary'],['--memory','128m','--cpus','1',*shared,'--user','1003:1003','-e','PYTHONPATH=/package/src','-e','PLAN_SHA256='+self.plan.hash,'-v',f'{ROOT}:/package:ro','-v',f'{config}:/config:ro','-v',f'{guard}:/guard'])
        self.create(self.names[2],ZAP,['--memory','1024m','--cpus','2',*shared,'--user','1000:1000','-e','ZAP_MEMORY=768m','-v',f'{wrk}:/zap/wrk','-v',f'{imports}:/tmp/zpa-imports:ro'])
        env={'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'none','MCP_SECURITY_ENABLED':'false','ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':'','ZAP_REPORT_DIRECTORY':'/zap/wrk','ZAP_ALLOW_LOCALHOST':'false','ZAP_ALLOW_PRIVATE_NETWORKS':'true','ZAP_URL_BLACKLIST':'169.254.0.0/16','ZAP_URL_WHITELIST':b['address'],'ZAP_SPIDER_THREAD_COUNT':'1','ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1','ZAP_MAX_CONCURRENT_SPIDER_SCANS':'1','MCP_SERVER_TOOLS_SURFACE':'guided','ZAP_SCAN_HISTORY_BACKEND':'in-memory','ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory','JAVA_TOOL_OPTIONS':'-Xmx384m -Duser.name=mcp','ZAP_INIT_CONNECTION_TIMEOUT':'60','ZAP_OPENAPI_CONTENT_IMPORT_ENABLED':'true','ZAP_OPENAPI_CONTENT_IMPORT_LOCAL_DIRECTORY':'/tmp/zpa-imports','ZAP_OPENAPI_CONTENT_IMPORT_ZAP_DIRECTORY':'/tmp/zpa-imports'}
        opts=['--memory','512m','--cpus','2',*shared,'--user','1001:1000','-v',f'{config}/passwd:/etc/passwd:ro','-v',f'{wrk}:/zap/wrk','-v',f'{imports}:/tmp/zpa-imports']
        for k,v in env.items():opts+=['-e',k+'='+v]
        self.create(self.names[3],MCP_IMAGE,opts);self.match_host=b['address']
        return {'zapImage':ZAP,'mcpImage':MCP_IMAGE,'pythonImage':PYTHON,'boundaryImageId':baseline['boundary'],'network':'borrowed-bridge+UID-firewall+plan-guard','namespace':self.anchor,'binding':b,'contentStagingVolume':self.import_volume}
    def configure_firewall(self):
        c=self.plan.data['guard']
        self.journal.append('intent',{'action':'namespace-firewall','resource':self.anchor})
        rules=['iptables -P OUTPUT DROP','iptables -P INPUT DROP','iptables -A INPUT -i lo -j ACCEPT','iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT','iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT','iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 18888 -m owner --uid-owner 1000 -j ACCEPT','iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT','iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090,18888 -m owner --uid-owner 1002 -j ACCEPT',f"iptables -A OUTPUT -p tcp -d {c['address']} --dport {c['port']} -m owner --uid-owner 1003 -j ACCEPT",'ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP']
        for rule in rules:docker(['exec',self.anchor,*rule.split()])
        self.journal.append('ack',{'action':'namespace-firewall','resource':self.anchor})
    def target_request(self,url):
        from .egress import request_target
        self.assert_binding();host=urlsplit(self.plan.data['guard']['origin']).netloc
        request_target('GET',url,{'Host':host},self.plan.data['guard']['origin'])
        code="""import http.client,json,sys
x=json.load(sys.stdin);c=http.client.HTTPConnection('127.0.0.1',18888,timeout=5);c.request('GET',x['url'],headers={'Host':x['host'],'Connection':'close'});r=c.getresponse();data=r.read(1048577)
if len(data)>1048576:raise ValueError('response limit')
print(json.dumps({'status':r.status,'body':data.decode('utf-8')}));c.close()
"""
        return json.loads(docker(['exec','-i','--user','1002:1002',self.anchor,'python','-c',code],canonical({'url':url,'host':host}),timeout=15))
    def guard_probe(self):
        c=self.plan.data['guard'];outside=1 if c['port']==65535 else c['port']+1;url=c['origin']+self.plan.data['product']['healthPath'];host=urlsplit(url).netloc
        cases=[('allowedTarget','GET',url,host,{}),('outsidePort','GET',f"http://{c['address']}:{outside}/",f"{c['address']}:{outside}",{}),('hostAlias','GET','http://localhost/','localhost',{}),('schemeChange','GET',url.replace('http:','https:'),host,{}),('connectTunnel','CONNECT',host,host,{}),('metadata','GET','http://169.254.169.254/','169.254.169.254',{}),('hostOverride','GET',url,'localhost',{}),('forbiddenPath','GET',c['origin']+'/__unapproved__',host,{}),('credentialForward','GET',url,host,{'Authorization':'Bearer binding-test-canary'}),('cookieForward','GET',url,host,{'Cookie':'binding-test-canary=1'})]
        code="""import http.client,json,sys
checks={}
for label,method,url,host,extra in json.load(sys.stdin):
 c=http.client.HTTPConnection('127.0.0.1',18888,timeout=5);c.request(method,url,headers={'Host':host,'Connection':'close',**extra});r=c.getresponse();checks[label]=r.status;r.read();c.close()
print(json.dumps(checks))
"""
        result=json.loads(docker(['exec','-i','--user','1000:1000',self.anchor,'python','-c',code],canonical(cases)))
        if result.get('allowedTarget')!=200 or any(v!=403 for k,v in result.items() if k!='allowedTarget'):raise Blocked('plan guard probe failed')
        return result
    def boundary_probe(self):
        c=self.plan.data['guard']
        checks=[('approvedProxy','127.0.0.1',18888),('directTarget',c['address'],c['port']),('outside-port',c['address'],c['port']+1),('control-api','127.0.0.1',8090),('metadata','169.254.169.254',80),('external','1.1.1.1',80),('ipv6','::1',80)]
        code="""import socket,json,sys
result={}
for label,host,port in json.load(sys.stdin):
 s=socket.socket(socket.AF_INET6 if ':' in host else socket.AF_INET,socket.SOCK_STREAM);s.settimeout(.3)
 try:s.connect((host,port));result[label]=True
 except OSError:result[label]=False
 finally:s.close()
print(json.dumps(result))
"""
        result=json.loads(docker(['exec','-i','--user','1000:1000',self.anchor,'python','-c',code],canonical(checks)))
        if result.get('approvedProxy') is not True or any(v for k,v in result.items() if k!='approvedProxy'):raise Blocked('binding kernel probe failed')
        return result
    def cleanup(self):
        super().cleanup()
        intents=[e for e in self.journal.events if e['kind']=='intent' and e['data'].get('action')=='volume-create' and e['data'].get('resource')==self.import_volume and e['data'].get('createdByRun')==self.run_id]
        if not intents:return True
        if not docker(['volume','ls','-q','--filter','name=^'+self.import_volume+'$']).strip():return True
        volume=json.loads(docker(['volume','inspect',self.import_volume]))[0]
        stamps=[e['data']['createdAt'] for e in self.journal.events if e['kind']=='ack' and e['data'].get('action')=='volume-create' and e['data'].get('resource')==self.import_volume]
        if (volume.get('Labels') or {}).get('zpa.run')!=self.run_id or not stamps or stamps[-1]!=volume['CreatedAt']:raise Blocked('content volume ownership mismatch or creation ACK unproven')
        self.journal.append('intent',{'action':'volume-remove','resource':self.import_volume})
        docker(['volume','rm',self.import_volume]);self.journal.append('ack',{'action':'volume-removed','resource':self.import_volume})
        if docker(['volume','ls','-q','--filter','name=^'+self.import_volume+'$']).strip():raise Blocked('content volume cleanup unconfirmed')
        return True
    def observations(self):
        self.assert_binding();path=self.root/'guard/egress.jsonl'
        entries=[json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []
        import hashlib
        c=self.plan.data['guard'];approved={hashlib.sha256((c['origin']+p).encode()).hexdigest() for p in c['allowedPaths']}
        forbidden=sum(e.get('action')=='forwarded' and e.get('urlSha256') not in approved for e in entries)
        return {'originGuardProof':self.guard_proof,'egress':entries,'forbiddenRequests':forbidden,'requests':[],'boundaryProbe':self.boundary_probe(),'firewall':docker(['exec',self.anchor,'iptables','-nvL','OUTPUT'])}
    def binding_evidence(self):
        b=self.plan.data['product']['binding']
        actions=[e['data'] for e in self.journal.events if e['kind']=='intent' and e['data'].get('resource') in (b['containerId'],b['networkId']) and e['data'].get('action') in ('container-stop','container-remove','volume-remove','network-remove')]
        return {'before':self.before,'after':self.assert_binding(),'borrowed':b,'targetCleanupActions':actions}
