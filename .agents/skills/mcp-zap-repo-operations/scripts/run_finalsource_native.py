#!/usr/bin/env python3
"""Run native MCP public scan paths against the explicitly selected local test app.

Owns a fresh pinned MCP/ZAP namespace. Backend traffic passes a GET-only guard;
frontend traffic is anonymous HTTP Spider plus explicit GETs, not browser auth.
No credential is sent to ZAP. Each tool request/response is recorded. This is an
operational wrapper, not a replacement scan engine or release approval system.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import threading
import time
from urllib.parse import urlsplit
import uuid

ASSESSMENT_ROOT=Path(__file__).resolve().parents[1]/'lib/zap-product-assessment'
sys.path.insert(0,str(ASSESSMENT_ROOT/'src'))
sys.dont_write_bytecode=True


def raw(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def sha(data):return hashlib.sha256(data).hexdigest()
def write(root,name,value):
    p=Path(root)/name;p.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
    b=value if isinstance(value,bytes) else raw(value)+b'\n'
    fd=os.open(p,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as f:f.write(b)
    return p


def guard_main(config_path):
    c=json.loads(Path(config_path).read_bytes())
    class Guard(BaseHTTPRequestHandler):
        lock=threading.Lock();last=0
        def log_message(self,*args):pass
        def record(self,action,**extra):
            row={'at':datetime.now(timezone.utc).isoformat(),'action':action,'method':self.command,'url':self.path,**extra}
            with self.lock:
                with open('/evidence/proxy.jsonl','ab') as f:f.write(raw(row)+b'\n')
        def deny(self,reason):
            self.record('denied',reason=reason,guardGenerated=True)
            self.send_response_only(403);self.send_header('Content-Length','0');self.end_headers()
        def do_GET(self):
            u=urlsplit(self.path)
            if self.server.server_port==18081:
                if self.path!='/public-openapi.json':self.deny('schema-path');return
                b=Path('/config/public-openapi.json').read_bytes()
                self.send_response_only(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b);return
            if (time.time()>c['notAfter'] or u.scheme!='http' or u.netloc!=c['backendAuthority']
                or u.path not in c['allowedPaths'] or u.username or u.password
                or any(self.headers.get(k) for k in ('Authorization','Cookie','Proxy-Authorization','Transfer-Encoding'))
                or self.headers.get('Content-Length','0')!='0'):
                self.deny('scope-method-or-credentials');return
            connection=http.client.HTTPConnection(c['backendAddress'],3000,timeout=8)
            try:
                with self.lock:
                    wait=type(self).last+.5-time.monotonic()
                    if wait>0:time.sleep(wait)
                    if time.time()>c['notAfter']:raise TimeoutError('run expired')
                    headers={k:v for k,v in self.headers.items() if k.lower() not in ('connection','proxy-connection','host','content-length')}
                    headers.update(Host=c['backendAuthority'],Connection='close')
                    connection.request('GET',u.path+('?' + u.query if u.query else ''),headers=headers)
                    type(self).last=time.monotonic()
                response=connection.getresponse();b=response.read(1048577)
                if len(b)>1048576:raise ValueError('response limit')
                if response.getheader('Set-Cookie'):raise ValueError('anonymous response sets cookie')
                self.send_response_only(response.status)
                for k,v in response.getheaders():
                    if k.lower() not in ('connection','transfer-encoding','content-length'):self.send_header(k,v)
                self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
                self.record('forwarded',status=response.status,responseBytes=len(b),responseBodySha256=sha(b),guardGenerated=False)
            except Exception as exc:
                self.record('failed',errorType=type(exc).__name__,guardGenerated=True)
                try:self.send_response_only(502);self.send_header('Content-Length','0');self.end_headers()
                except OSError:pass
            finally:connection.close()
        def do_POST(self):self.deny('method')
        do_PUT=do_POST;do_PATCH=do_POST;do_DELETE=do_POST;do_OPTIONS=do_POST;do_HEAD=do_POST;do_CONNECT=do_POST
    threading.Thread(target=ThreadingHTTPServer(('127.0.0.1',18081),Guard).serve_forever,daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1',18888),Guard).serve_forever()


def metadata(name):
    from zap_assessment.runtime import docker
    fmt='{"id":{{json .Id}},"image":{{json .Image}},"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},"networks":{{json .NetworkSettings.Networks}},"project":{{json (index .Config.Labels "com.docker.compose.project")}}}'
    d=json.loads(docker(['inspect','--format',fmt,name]));ns=[n for n in d.pop('networks').values() if n['IPAddress']]
    if len(ns)!=1 or not d['running'] or d['project']!='finalsource-zap-test':raise ValueError('test target binding ambiguous')
    d.update(networkId=ns[0]['NetworkID'],address=ns[0]['IPAddress']);return d


def run_scan(args):
    from zap_assessment.runtime import DockerRuntime,docker,ZAP,MCP_IMAGE
    from zap_assessment.journal import Journal
    from zap_assessment.transport import MCP,field
    from jsonschema import Draft202012Validator
    out=args.output.resolve();out.mkdir(mode=0o700,parents=True,exist_ok=False)
    receipt=json.loads(args.receipt.read_bytes())
    if receipt.get('environment')!='finalsource-zap-test' or not receipt.get('userRequest'):raise ValueError('actual scan authorization required')
    front=metadata('finalsource-zap-test-frontend-1');back=metadata('finalsource-zap-test-backend-1')
    if front['networkId']!=back['networkId']:raise ValueError('app network mismatch')
    frontend='https://'+front['address']+':8443';backend='http://'+back['address']+':3000'
    run_id='native-'+uuid.uuid4().hex[:16]
    plan={'runId':run_id,'frontend':front,'backend':back,'authorizationSha256':sha(args.receipt.read_bytes()),
          'activeTargets':[backend+'/api/health',backend+'/docs-json'],'maxActiveMinutesPerTarget':3,
          'frontendMode':'anonymous HTTP Spider and explicit GETs; no browser or credentials',
          'backendMode':'anonymous GET-only proxy; no business writes',
          'images':{'zap':ZAP,'mcp':MCP_IMAGE},'notAfter':time.time()+2400,
          'wrapperSourceSha256':sha(Path(__file__).read_bytes())}
    write(out,'plan.json',plan);journal=Journal(out/'journal.jsonl',run_id,sha(raw(plan)))
    class Runtime(DockerRuntime):
        def __init__(self):
            super().__init__(run_id,out,journal)
            self.names=[f'zpa-{run_id}-{x}' for x in ('net','guard','zap','mcp')]
            self.anchor=self.names[0]
        def binding(self):
            if metadata('finalsource-zap-test-frontend-1')!=front or metadata('finalsource-zap-test-backend-1')!=back:
                raise ValueError('borrowed app binding changed')
        def provision(self):
            baseline=json.loads((ASSESSMENT_ROOT/'profiles/runtime-baseline.json').read_bytes())
            wrk=out/'workspace';wrk.mkdir(mode=0o777);wrk.chmod(0o777)
            config=out/'config';config.mkdir(mode=0o755);config.chmod(0o755)
            evidence=out/'guard';evidence.mkdir(mode=0o777);evidence.chmod(0o777)
            # Read-only public schema starts minimal; replaced before its one import.
            guard={'backendAddress':back['address'],'backendAuthority':urlsplit(backend).netloc,
                   'allowedPaths':['/','/api/health','/docs-json'],'notAfter':plan['notAfter']}
            (config/'guard.json').write_bytes(raw(guard));(config/'guard.json').chmod(0o444)
            self.commands={self.names[0]:['sleep','3000'],self.names[1]:['python','/runner.py','guard','/config/guard.json'],
                self.names[2]:['zap.sh','-daemon','-host','127.0.0.1','-port','8090','-config','api.disablekey=true',
                    '-config','autoupdate.checkOnStart=false','-config','spider.processForm=false','-config','spider.postForm=false',
                    '-config','spider.parseRobotsTxt=false','-config','spider.parseSitemapXml=false','-config','connection.timeoutInSecs=8'],self.names[3]:[]}
            self.create(self.anchor,baseline['boundary'],['--no-healthcheck','--network',back['networkId'],'--cap-add','NET_ADMIN'])
            rules=['iptables -P OUTPUT DROP','iptables -P INPUT DROP','iptables -P FORWARD DROP','ip6tables -P OUTPUT DROP','ip6tables -P INPUT DROP',
                'iptables -A INPUT -i lo -j ACCEPT','iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
                'iptables -A OUTPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT',
                'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 18888,18081 -m owner --uid-owner 1000 -j ACCEPT',
                f'iptables -A OUTPUT -p tcp -d {front["address"]} --dport 8443 -m owner --uid-owner 1000 -j ACCEPT',
                'iptables -A OUTPUT -p tcp -d 127.0.0.1 --dport 8090 -m owner --uid-owner 1001 -j ACCEPT',
                'iptables -A OUTPUT -p tcp -d 127.0.0.1 -m multiport --dports 7456,8090,18888,18081 -m owner --uid-owner 1002 -j ACCEPT',
                f'iptables -A OUTPUT -p tcp -d {back["address"]} --dport 3000 -m owner --uid-owner 1003 -j ACCEPT']
            for rule in rules:docker(['exec',self.anchor,*rule.split()])
            write(out,'firewall.json',{'ipv4':docker(['exec',self.anchor,'iptables-save']),'ipv6':docker(['exec',self.anchor,'ip6tables-save'])})
            shared=['--no-healthcheck','--network','container:'+self.anchor,'--cap-drop','ALL','--security-opt','no-new-privileges']
            self.create(self.names[1],baseline['boundary'],[*shared,'--user','1003:1003','--memory','192m',
                '-v',str(Path(__file__).resolve())+':/runner.py:ro','-v',str(config)+':/config:ro','-v',str(evidence)+':/evidence'])
            self.create(self.names[2],ZAP,[*shared,'--user','1000:1000','--memory','1536m','--cpus','2','-e','ZAP_MEMORY=1024m','-v',str(wrk)+':/zap/wrk'])
            env={'SERVER_ADDRESS':'127.0.0.1','SPRING_PROFILES_ACTIVE':'test','MCP_SECURITY_MODE':'none','MCP_SECURITY_ENABLED':'false',
                'ZAP_API_URL':'127.0.0.1','ZAP_API_PORT':'8090','ZAP_API_KEY':'','ZAP_REPORT_DIRECTORY':'/zap/wrk',
                'ZAP_ALLOW_LOCALHOST':'true','ZAP_ALLOW_PRIVATE_NETWORKS':'true','MCP_SERVER_TOOLS_SURFACE':'expert',
                'ZAP_SPIDER_THREAD_COUNT':'1','ZAP_SPIDER_MAX_DEPTH':'3','ZAP_MAX_SPIDER_SCAN_DURATION':'2',
                'ZAP_MAX_ACTIVE_SCAN_DURATION':'3','ZAP_THREAD_PER_HOST':'1','ZAP_HOST_PER_SCAN':'1',
                'ZAP_MAX_CONCURRENT_ACTIVE_SCANS':'1','ZAP_SCAN_HISTORY_BACKEND':'in-memory','ZAP_SCAN_JOBS_STORE_BACKEND':'in-memory',
                'JAVA_TOOL_OPTIONS':'-Xmx384m','ZAP_INIT_CONNECTION_TIMEOUT':'90'}
            opts=[*shared,'--user','1001:1000','--memory','512m','--cpus','2','-v',str(wrk)+':/zap/wrk']
            for k,v in env.items():opts+=['-e',k+'='+v]
            self.create(self.names[3],MCP_IMAGE,opts)
    runtime=Runtime();outcome={'executionStatus':'running','evidenceStatus':'incomplete','cleanupStatus':'pending','limitations':[
        'Anonymous scanner: protected business APIs are not authenticated DAST coverage',
        'GET-only backend guard can suppress method/header/path attack coverage; guard responses are not app vulnerabilities',
        'Frontend uses literal container HTTPS origin and scanner TLS behavior; browser trust and deployed public DNS are not evaluated',
        'Direct in-memory history does not establish durable queued terminal lifecycle',
        'BOLA is collected separately using isolated login client; no JWT/password enters ZAP',
        'No production, mutation fuzzing, queue/HA, rollback, restore or release approval']}
    transcripts=[];completed=[]
    class RecordedMCP(MCP):
        def call(self,name,arguments):
            runtime.binding()
            if time.time()>plan['notAfter']:raise TimeoutError('native run deadline')
            Draft202012Validator(self.contracts[name]).validate(arguments)
            index=len(transcripts);start=datetime.now(timezone.utc).isoformat()
            write(out,f'tools/{index:04d}-{name}-request.json',{'at':start,'tool':name,'arguments':arguments})
            response=self.rpc('tools/call',{'name':name,'arguments':arguments})
            write(out,f'tools/{index:04d}-{name}-response.json',response)
            transcripts.append({'tool':name,'index':index,'at':start,'isError':bool(response.get('isError'))})
            if response.get('isError'):raise RuntimeError('native tool failed: '+name)
            text='\n'.join(v['text'] for v in response.get('content',[]) if v.get('type')=='text')
            if text.startswith('"'):
                text=json.loads(text)
            return text
    def engine(component,kind,name,arguments=None):
        value=runtime.engine(component,kind,name,arguments or {})
        write(out,f'engine/{uuid.uuid4().hex[:8]}-{component}-{name}.json',{'component':component,'kind':kind,'name':name,'arguments':arguments or {},'result':value})
        return value
    def seed(url,label):
        value=engine('core','action','sendRequest',{'request':f'GET {url} HTTP/1.1\r\nHost: {urlsplit(url).netloc}\r\nConnection: close\r\n\r\n','followRedirects':'false'})
        write(out,'http/'+label+'.json',{'url':url,'response':value});return value
    def crawl(url,label):
        text=mcp.call('zap_crawl_start',{'targetUrl':url,'strategy':'http'})
        op=field(text,'Operation ID');deadline=time.monotonic()+180
        while time.monotonic()<deadline:
            text=mcp.call('zap_crawl_status',{'operationId':op})
            if field(text,'Completed')=='yes':
                completed.append({'kind':'crawl','label':label,'operationId':op,'status':text});return
            time.sleep(3)
        mcp.call('zap_crawl_stop',{'operationId':op});raise TimeoutError('crawl deadline: '+label)
    def report(origin,label,format):
        text=mcp.call('zap_report_generate',{'baseUrl':origin,'format':format,'theme':'light'})
        path=field(text,'Path');offset=0;expected=None;chunks=[];pages=[]
        for _ in range(300):
            a={'reportPath':path,'offset':offset,'maxChars':120000}
            if expected:a['expectedSha256']=expected
            page=json.loads(mcp.call('zap_report_read_chunk',a));expected=expected or page['artifactSha256']
            if page['artifactSha256']!=expected:raise ValueError('report hash changed')
            chunks.append(page['content']);pages.append({k:v for k,v in page.items() if k!='content'})
            if page['endOfFile']:break
            if page['nextOffset']<=offset:raise ValueError('report offset not increasing')
            offset=page['nextOffset']
        else:raise ValueError('report page budget')
        content=''.join(chunks).encode('utf-8')
        if sha(content)!=expected:raise ValueError('report full hash mismatch')
        write(out,'reports/'+label+'.'+format,content)
        write(out,'reports/'+label+'-'+format+'-readback.json',{'sha256':expected,'bytes':len(content),'pages':pages,'reportPath':path,'endOfFile':True})
    try:
        print('Provisioning fresh pinned scanner',flush=True);runtime.provision();runtime.wait_health(180)
        mcp=RecordedMCP(runtime.request);write(out,'mcp-discovery.json',mcp.initialize())
        write(out,'scanner.json',{'version':engine('core','view','version'),'addons':engine('autoupdate','view','installedAddons')})
        # HTTP backend guard. Frontend HTTPS bypasses this HTTP-only proxy but is
        # restricted to its single IP/port at the kernel and only GET-seeded.
        engine('network','action','setHttpProxy',{'host':'127.0.0.1','port':18888})
        for rule in engine('network','view','getHttpProxyExclusions').get('getHttpProxyExclusions',[]):
            engine('network','action','setHttpProxyExclusionEnabled',{'host':rule['host'],'enabled':'false'})
        for host in (front['address'],'127.0.0.1'):
            engine('network','action','addHttpProxyExclusion',{'host':host,'enabled':'true'})
        engine('network','action','setHttpProxyEnabled',{'enabled':'true'})
        engine('network','action','addRateLimitRule',{'description':'pm-public-run','enabled':'true','matchRegex':'true',
            'matchString':re.escape(front['address'])+'|'+re.escape(back['address']),'requestsPerSecond':2,'groupBy':'rule'})
        write(out,'network-config.json',{'proxy':engine('network','view','getHttpProxy'),'exclusions':engine('network','view','getHttpProxyExclusions'),'rateRules':engine('network','view','getRateLimitRules')})
        print('Native HTTP crawl and explicit frontend GETs',flush=True)
        crawl(frontend,'frontend');seed(frontend+'/login','frontend-login');seed(frontend+'/register','frontend-register')
        home=seed(frontend+'/','frontend-home')
        home_text=json.dumps(home)
        assets=sorted(set(re.findall(r'/assets/[A-Za-z0-9._-]+\.(?:js|css)',home_text)))
        write(out,'frontend-assets.json',assets)
        for i,path in enumerate(assets[:12]):seed(frontend+path,f'frontend-asset-{i}')
        seed(frontend+'/docs-json','frontend-openapi')
        print('Backend GET crawl and sanitized OpenAPI import',flush=True)
        crawl(backend,'backend');seed(backend+'/api/health','backend-health')
        schema_response=seed(backend+'/docs-json','backend-openapi')
        messages=schema_response.get('sendRequest',[])
        if not isinstance(messages,list) or not messages:raise ValueError('schema response missing')
        schema=json.loads(messages[0]['responseBody'])
        write(out,'original-openapi.json',schema)
        # Public native import proof is intentionally limited to non-parameter GETs.
        paths={p:{'get':v['get']} for p,v in schema.get('paths',{}).items() if 'get' in v and '{' not in p}
        selected={'openapi':schema.get('openapi','3.0.0'),'info':schema.get('info',{}),'paths':paths,
                  'components':schema.get('components',{}),'servers':[{'url':backend}]}
        write(out,'selected-openapi.json',selected)
        schema_file=out/'config/public-openapi.json';schema_file.write_bytes(raw(selected));schema_file.chmod(0o444)
        # Extend the GET allowlist before import, then replace guard container only.
        # The scanner namespace and session remain owned by this run.
        guard_file=out/'config/guard.json';guard=json.loads(guard_file.read_bytes());guard['allowedPaths']=sorted(set(guard['allowedPaths'])|set(paths));guard_file.chmod(0o600);guard_file.write_bytes(raw(guard));guard_file.chmod(0o444)
        info=runtime.check_owner(runtime.names[1]);docker(['restart',info['Id']]);time.sleep(1)
        mcp.call('zap_target_import',{'definitionType':'openapi','sourceKind':'url','source':'http://127.0.0.1:18081/public-openapi.json','hostOverride':backend})
        for i,path in enumerate(paths):seed(backend+path,f'backend-public-get-{i}')
        print('Bounded native active checks: GET health and OpenAPI only',flush=True)
        mcp.call('zap_scan_policies_list',{})
        engine('ascan','action','addScanPolicy',{'scanPolicyName':'pm-public-get','attackStrength':'LOW'})
        mcp.call('zap_scan_policy_view',{'scanPolicyName':'pm-public-get','limit':'100'})
        for target in plan['activeTargets']:
            text=mcp.call('zap_attack_start',{'targetUrl':target,'recurse':'false','policy':'pm-public-get'})
            op=field(text,'Operation ID');deadline=time.monotonic()+240
            while time.monotonic()<deadline:
                text=mcp.call('zap_attack_status',{'operationId':op})
                if field(text,'Completed')=='yes':break
                time.sleep(5)
            else:
                mcp.call('zap_attack_stop',{'operationId':op});raise TimeoutError('active scan deadline')
            completed.append({'kind':'active','target':target,'operationId':op,'status':text})
        write(out,'active-engine-state.json',engine('ascan','view','scans'))
        print('Settling passive analysis and exporting complete native evidence',flush=True)
        mcp.call('zap_passive_scan_wait',{'timeoutSeconds':180})
        stable=0
        for _ in range(60):
            text=mcp.call('zap_passive_scan_status',{})
            stable=stable+1 if field(text,'Completed')=='yes' and field(text,'Records remaining')=='0' else 0
            if stable>=2:break
            time.sleep(2)
        else:raise TimeoutError('passive backlog did not settle')
        for label,origin in [('frontend',frontend),('backend',backend)]:
            write(out,label+'-findings-summary.md',mcp.call('zap_findings_summary',{'baseUrl':origin}).encode())
            snapshot=mcp.call('zap_findings_snapshot',{'baseUrl':origin});write(out,label+'-snapshot.json',snapshot.encode())
            # Same-run replay proves the diff contract only, not remediation.
            diff=mcp.call('zap_findings_diff',{'baseUrl':origin,'baselineSnapshot':snapshot,'maxGroups':20})
            write(out,label+'-self-diff.txt',diff.encode())
            report(origin,label,'json');report(origin,label,'html')
            write(out,label+'-release-evidence.txt',mcp.call('zap_scan_history_release_evidence',{'releaseName':run_id,'target':urlsplit(origin).hostname,'limit':100}).encode())
            write(out,label+'-customer-handoff.md',mcp.call('zap_scan_history_customer_handoff',{'handoffName':run_id,'target':urlsplit(origin).hostname,'limit':100}).encode())
        write(out,'native-history.json',mcp.call('zap_scan_history_export',{'limit':200}).encode())
        # Reports already contain the complete findings export. Bulk history can
        # exceed the bounded management transport because it includes JS bodies.
        # Keep only a small diagnostic sample; never call it full traffic capture.
        write(out,'engine-messages-sample.json',engine('core','view','messages',{'start':0,'count':3}))
        write(out,'engine-message-export-scope.json',{'sampleOnly':True,'start':0,'count':3,
            'completeFindingsArtifacts':'reports/frontend.json and reports/backend.json',
            'limitReason':'bounded management response; not a complete HTTP traffic archive'})
        write(out,'engine-urls.json',engine('core','view','urls'))
        outcome.update(executionStatus='completed',evidenceStatus='complete',securityVerdict='requires-triage')
    except Exception as exc:
        outcome.update(executionStatus='failed',errorType=type(exc).__name__,detail=str(exc)[:250],securityVerdict='inconclusive')
        print('Native run stopped:',type(exc).__name__,str(exc)[:200],flush=True)
    finally:
        write(out,'tool-index.json',transcripts);write(out,'operations.json',completed)
        try:
            runtime.cleanup();outcome['cleanupStatus']='clean'
        except Exception as exc:
            outcome.update(cleanupStatus='incomplete',cleanupErrorType=type(exc).__name__)
        try:runtime.binding();outcome['borrowedTargetBindingUnchanged']=True
        except Exception:outcome['borrowedTargetBindingUnchanged']=False
        write(out,'result.json',outcome)
        entries=[]
        for p in sorted(out.rglob('*')):
            if p.is_file():
                p.chmod(0o600)
                entries.append({'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':sha(p.read_bytes())})
        manifest={'contract':'finalsource-native-operational-evidence/v1','runId':run_id,'createdAt':datetime.now(timezone.utc).isoformat(),
                  'result':outcome,'artifacts':entries,'notReleaseApproval':True}
        write(out,'manifest.json',manifest);write(out,'manifest.sha256',sha((out/'manifest.json').read_bytes()).encode()+b'\n')
        print(json.dumps({'output':str(out),**outcome},ensure_ascii=False),flush=True)
    return 0 if outcome['executionStatus']=='completed' and outcome['cleanupStatus']=='clean' else 2


def verify(root):
    manifest=json.loads((root/'manifest.json').read_bytes())
    if sha((root/'manifest.json').read_bytes())!=(root/'manifest.sha256').read_text().strip():raise ValueError('manifest digest mismatch')
    for artifact in manifest['artifacts']:
        p=(root/artifact['path']).resolve()
        if not p.is_relative_to(root.resolve()) or p.is_symlink() or not p.is_file():raise ValueError('artifact outside bundle')
        b=p.read_bytes()
        if len(b)!=artifact['bytes'] or sha(b)!=artifact['sha256']:raise ValueError('artifact integrity mismatch')
    return {'verified':True,'artifacts':len(manifest['artifacts']),'result':manifest['result']}


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='guard':guard_main(sys.argv[2])
    else:
        p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='command',required=True)
        q=sub.add_parser('run');q.add_argument('--receipt',type=Path,required=True);q.add_argument('--output',type=Path,required=True)
        q=sub.add_parser('verify');q.add_argument('path',type=Path)
        a=p.parse_args()
        if a.command=='verify':print(json.dumps(verify(a.path),ensure_ascii=False))
        else:raise SystemExit(run_scan(a))
