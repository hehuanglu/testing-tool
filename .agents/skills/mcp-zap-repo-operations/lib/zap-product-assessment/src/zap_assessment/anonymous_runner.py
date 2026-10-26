"""Anonymous research orchestration: admission -> native traffic -> MCP reports -> cleanup."""
import copy
import hashlib
import json
import os
from pathlib import Path
import signal
import threading
import time
from urllib.parse import urlsplit
from jsonschema import Draft202012Validator
from .anonymous import validate_plan,expected_response,validate_exports
from .discovery import canonical_hash,verify_local_sources
from .anonymous_product import save
from .anonymous_runtime import AnonymousRuntime,inspect_binding
from .journal import Journal
from .transport import MCP,field
from .evidence import read_report
from .runtime import docker


def implementation_pin():
    root=Path(__file__).parent
    files=[*root.glob('anonymous*.py'),root/'discovery.py',root/'runtime.py',root/'transport.py',root/'journal.py',root/'evidence.py',root/'research_product.py',root/'research.py',root/'discovery_handoff.py',root.parent.parent/'scripts/be_anonymous_research.py',root.parent.parent/'profiles/runtime-baseline.json',root.parent.parent/'schemas/be-anonymous-research-plan-v1.schema.json']
    return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)}


def baseline_key(label):
    # ZAP ScriptVars rejects keys longer than 30 characters.
    return 'anb-'+hashlib.sha256(label.encode()).hexdigest()[:24]


class RecordedMCP(MCP):
    def __init__(self,rt,out):super().__init__(rt.request);self.out=out;self.index=0
    def record_response(self,prefix,result):save(self.out,prefix+'-response.json',result)
    def call(self,name,args):
        if name not in self.contracts:raise ValueError('missing MCP capability '+name)
        Draft202012Validator(self.contracts[name]).validate(args)
        self.index+=1;prefix=f'tools/{self.index:04d}-{name}'
        save(self.out,prefix+'-request.json',{'tool':name,'arguments':args})
        result=self.rpc('tools/call',{'name':name,'arguments':args});self.record_response(prefix,result)
        if result.get('isError'):raise RuntimeError('native MCP tool failed '+name)
        text='\n'.join(x['text'] for x in result['content'] if x.get('type')=='text')
        if text.startswith('"'):text=json.loads(text)
        return text


class AnonymousRun:
    def __init__(self,plan,out,inspection):
        self.p=copy.deepcopy(plan);self.out=Path(out);self.out.mkdir(mode=0o700,parents=True,exist_ok=False)
        self.inspect=inspection;b,proof=inspection();validate_plan(self.p,b,proof);verify_local_sources(self.p['discovery'])
        self.hash=canonical_hash(self.p);self.pins=implementation_pin();save(self.out,'PLAN.json',self.p);save(self.out,'implementation-pins.json',self.pins)
        self.j=Journal(self.out/'journal.jsonl',plan['runId'],self.hash);self.rt=AnonymousRuntime(plan,self.out,self.j)
        self.ops=[];self.coverage=[];self.engine_index=0;self.cancelled=threading.Event();self.monitor_stop=threading.Event();self.resource_failure=None;self.samples=[]
        self.result={'executionStatus':'running','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block'}
        self.mcp=None;self.report_errors=[]
    def current(self):
        if self.cancelled.is_set():raise InterruptedError('cancel requested')
        if self.resource_failure:raise RuntimeError('resource monitor: '+self.resource_failure)
        if canonical_hash(self.p)!=self.hash or canonical_hash(json.loads((self.out/'PLAN.json').read_bytes()))!=self.hash:raise ValueError('locked plan drift')
        if implementation_pin()!=self.pins:raise ValueError('implementation drift')
        b,proof=self.inspect();validate_plan(self.p,b,proof);verify_local_sources(self.p['discovery'])
    def engine(self,component,kind,name,args=None):
        self.engine_index+=1;prefix=f'engine/{self.engine_index:05d}-{component}-{name}'
        save(self.out,prefix+'-request.json',{'component':component,'kind':kind,'name':name,'arguments':args or {}})
        value=self.rt.engine(component,kind,name,args or {});save(self.out,prefix+'-response.json',value);return value
    def mode(self,case,campaign=None,native=None):
        value={'caseId':case['id'],'campaignId':campaign['id'] if campaign else None,'producer':'active' if campaign else 'seed','nativeOperationId':native}
        tmp=self.rt.config/'mode.pending';tmp.write_text(json.dumps(value));tmp.chmod(0o444);os.replace(tmp,self.rt.config/'mode.json')
    def resources(self,preflight=False):
        s=self.rt.resource_sample() if preflight else self.rt.sample();s['at']=time.time()
        s['artifactBytes']=sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())
        self.samples.append(s)
        reserve=self.p['limits']['reserveBytes'];cap=self.p['limits']['artifactBytes']
        if s['artifactBytes']>cap:raise RuntimeError('artifact byte budget')
        required=reserve+2*cap if preflight else reserve
        if min(s['hostFree'],s['dockerFree'])<required:raise RuntimeError('disk reserve')
        if s['ramAvailable']<(3*1024**3 if preflight else 1024**3):raise RuntimeError('RAM headroom')
        return s
    def monitor(self):
        while not self.monitor_stop.wait(5):
            try:self.resources()
            except Exception as exc:self.resource_failure=type(exc).__name__+':'+str(exc);self.cancelled.set();return
    def configure(self):
        self.engine('network','action','setHttpProxy',{'host':'127.0.0.1','port':18888})
        self.engine('network','action','setHttpProxyAuthEnabled',{'enabled':'false'})
        for rule in self.engine('network','view','getHttpProxyExclusions').get('getHttpProxyExclusions',[]):self.engine('network','action','setHttpProxyExclusionEnabled',{'host':rule['host'],'enabled':'false'})
        self.engine('network','action','setHttpProxyEnabled',{'enabled':'true'})
        self.engine('network','action','addRateLimitRule',{'description':self.p['runId'],'enabled':'true','matchRegex':'false','matchString':urlsplit(self.p['origin']).hostname,'requestsPerSecond':self.p['limits']['requestsPerSecond'],'groupBy':'rule'})
        self.engine('ascan','action','setOptionThreadPerHost',{'Integer':1})
        self.engine('ascan','action','setOptionHostPerScan',{'Integer':1})
        self.engine('ascan','action','setOptionMaxScanDurationInMins',{'Integer':3})
        self.engine('ascan','action','setOptionTargetParamsInjectable',{'Integer':2})
        self.engine('ascan','action','setOptionTargetParamsEnabledRPC',{'Integer':4})
        self.engine('ascan','action','setOptionAddQueryParam',{'Boolean':'false'})
        # Disable HTTP state/session handling: responses remain native evidence, no cookie jar propagation.
        self.engine('core','action','setOptionHttpStateEnabled',{'Boolean':'false'})
        self.engine('ascan','action','setOptionInjectPluginIdInHeader',{'Boolean':'true'})
        save(self.out,'scanner.json',{'version':self.engine('core','view','version'),'addons':self.engine('autoupdate','view','installedAddons'),
         'passiveRules':self.engine('pscan','view','scanners'),'proxy':self.engine('network','view','getHttpProxy'),'proxyEnabled':self.engine('network','view','isHttpProxyEnabled'),'rate':self.engine('network','view','getRateLimitRules'),
         'vectors':{'injectable':self.engine('ascan','view','optionTargetParamsInjectable'),'rpc':self.engine('ascan','view','optionTargetParamsEnabledRPC')},'httpState':self.engine('core','view','optionHttpStateEnabled'),'nativeRuleHeader':self.engine('ascan','view','optionInjectPluginIdInHeader')})
    def seed(self,c):
        self.current()
        from .anonymous_private_body import resolve_case
        c=resolve_case(self.p,c)
        self.mode(c);url=self.p['origin']+c['path'];body=b'' if c['body'] is None else json.dumps(c['body'],separators=(',',':')).encode()
        headers={'Host':urlsplit(self.p['origin']).netloc,'Connection':'close','Accept':'application/json',**c.get('headers',{})}
        if body:headers.update({'Content-Type':'application/json','Content-Length':str(len(body))})
        request=f'{c["method"]} {url} HTTP/1.1\r\n'+''.join(f'{k}: {v}\r\n' for k,v in headers.items())+'\r\n'+body.decode()
        self.j.append('intent',{'action':'seed','caseId':c['id'],'requestSha256':hashlib.sha256(request.encode()).hexdigest()})
        self.j.append('pending-start',{'action':'seed','caseId':c['id']})
        started=time.monotonic()
        try:v=self.engine('core','action','sendRequest',{'request':request,'followRedirects':'false'})
        except Exception:
            # Preserve app record if available. Never dispatch POST twice after unknown ACK.
            records=[]
            for path in self.rt.capture.glob('[0-9]*.json'):
                row=json.loads(path.read_bytes())
                if row.get('caseId')==c['id'] and not row.get('campaignId'):records.append({'path':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            self.j.append('reconcile',{'action':'seed','caseId':c['id'],'guardRecords':records,'retry':False});raise
        rows=v.get('sendRequest',[])
        if len(rows)!=1:raise ValueError('seed response count')
        message=rows[0];result=expected_response(c,message);result['elapsedSeconds']=time.monotonic()-started
        if c['category']=='protocol-control':
            h=message.get('responseHeader','').lower();status=int(message.get('responseHeader','HTTP/1.1 0').split()[1]);result={'matched':status in c['expected']['statuses'] and 'x-zpa-response-origin: app' in h,'status':status,'category':'protocol-control','businessCoverage':False}
            if c['method']=='OPTIONS':result['matched']=result['matched'] and 'access-control-allow-methods:' in h and ('access-control-allow-origin: '+c['headers']['Origin'].lower()) in h
        row={'caseId':c['id'],'operationId':c['operationId'],'method':c['method'],'path':c['path'],'expected':c['expected'],'observed':result,'evidence':f'http/{c["id"]}.json'}
        save(self.out,row['evidence'],message);self.coverage.append(row);self.j.append('ack',{'action':'seed','caseId':c['id'],'matched':result['matched']})
        # Continue independent cases on oracle failure; never mark coverage from counts.
        return result
    def reconcile_start(self,known):
        observed=[]
        for _ in range(3):
            scans=self.engine('ascan','view','scans')['scans'];new=[s for s in scans if str(s['id']) not in known];observed.append(scans)
            if len(new)==1:return str(new[0]['id'])
            if len(new)>1:break
            time.sleep(.5)
        self.j.append('reconcile',{'action':'active-start','observations':observed,'result':'ambiguous-stop-only','retry':False});raise RuntimeError('lost start ACK unresolved; no retry')
    def attack(self,camp,interrupt_after=None):
        self.current();c=next(c for c in self.p['cases'] if c['id']==camp['caseId']);policy='an-'+camp['id']
        from .anonymous_private_body import resolve_case
        c=resolve_case(self.p,c)
        query=camp['vectors']==['query'];path=camp['vectors']==['path'];body_vector=not(query or path)
        self.engine('ascan','action','setOptionTargetParamsInjectable',{'Integer':16 if path else 1 if query else 2})
        self.engine('ascan','action','setOptionTargetParamsEnabledRPC',{'Integer':4 if body_vector else 0})
        self.engine('ascan','action','addScanPolicy',{'scanPolicyName':policy,'attackStrength':camp['strength'],'alertThreshold':'MEDIUM'})
        self.engine('ascan','action','disableAllScanners',{'scanPolicyName':policy})
        self.engine('ascan','action','enableScanners',{'ids':','.join(map(str,camp['ruleIds'])),'scanPolicyName':policy})
        rules=self.engine('ascan','view','scanners',{'scanPolicyName':policy})['scanners']
        enabled={int(r['id']) for r in rules if str(r['enabled']).lower()=='true'}
        if enabled!=set(camp['ruleIds']):raise ValueError('selected rule drift')
        save(self.out,'policies/'+camp['id']+'.json',rules)
        self.mode(c,camp,'pending-native-ack')
        # ZAP's SiteNode retains the latest same-name POST parameters, not necessarily postData values.
        # This explicit, budgeted baseline dispatch is a planned action, never an ACK retry.
        body=json.dumps(c['body'],separators=(',',':')).encode() if body_vector else b'';url=self.p['origin']+c['path']
        wire=f'{c["method"]} {url} HTTP/1.1\r\nHost: {urlsplit(url).netloc}\r\nConnection: close\r\n'
        if body_vector:wire+=f'Content-Type: application/json\r\nContent-Length: {len(body)}\r\n'
        wire+='\r\n'+body.decode()
        self.j.append('intent',{'action':'campaign-baseline-seed','campaignId':camp['id'],'maxDispatch':1,'bodySha256':hashlib.sha256(body).hexdigest()})
        self.j.append('pending-start',{'action':'campaign-baseline-seed','campaignId':camp['id']})
        baseline=self.engine('core','action','sendRequest',{'request':wire,'followRedirects':'false'})
        rows=baseline.get('sendRequest',[])
        if len(rows)!=1 or not expected_response(c,rows[0])['matched']:raise ValueError('campaign baseline not accepted by app oracle')
        self.j.append('ack',{'action':'campaign-baseline-seed','campaignId':camp['id'],'retry':False})
        self.bind_baseline(rows[0],camp['id'],expected_method=c['method'])
        known={str(s['id']) for s in self.engine('ascan','view','scans')['scans']}
        args={'url':self.p['origin']+c['path'],'recurse':'false','scanPolicyName':policy,'method':c['method']}
        if body_vector:args['postData']=json.dumps(c['body'],separators=(',',':'))
        self.j.append('intent',{'action':'active-start','campaignId':camp['id'],'knownNativeIds':sorted(known),'policy':policy})
        self.j.append('pending-start',{'action':'active-start','campaignId':camp['id']})
        try:native=str(self.engine('ascan','action','scan',args)['scan'])
        except Exception:native=self.reconcile_start(known)
        op={'campaignId':camp['id'],'nativeScanId':native,'operationKind':'native-ascan','terminal':False,'startedAt':time.time()};self.ops.append(op)
        self.j.append('ack',{'action':'active-start',**op});self.mode(c,camp,native);start=time.monotonic()
        while True:
            if self.cancelled.is_set() or (interrupt_after is not None and time.monotonic()-start>=interrupt_after):raise InterruptedError('qualification interruption')
            if time.time()>=self.p['notAfter'] or time.monotonic()-start>=self.p['limits']['operationSeconds']:raise TimeoutError('active execution deadline')
            status=self.engine('ascan','view','status',{'scanId':native})
            if int(status['status'])>=100:op.update(terminal=True,completedAt=time.time());break
            time.sleep(1)
        op['scanProgress']=self.engine('ascan','view','scanProgress',{'scanId':native});op['messageIds']=self.engine('ascan','view','messagesIds',{'scanId':native})
        records=[json.loads(p.read_bytes()) for p in self.rt.capture.glob('[0-9]*.json')]
        delivered=[v for v in records if v.get('campaignId')==camp['id']]
        op['forwardedAppRequests']=len(delivered)
        op['forwardedByNativeRule']={str(rule):sum(str(v.get('ruleId'))==str(rule) for v in delivered) for rule in camp['ruleIds']}
        op['techniqueExercised']=bool(delivered) and all(op['forwardedByNativeRule'].values())
        self.j.append('terminal',op)
    def bind_baseline(self,message,label,expected_method='POST'):
        # Bind the exact guarded anonymous exchange to the native SiteNode. No extra HTTP send.
        key=baseline_key(label)
        values={k:message[k] for k in ('requestHeader','requestBody','responseHeader','responseBody')}
        code="""const M=Java.type('org.parosproxy.paros.model.Model');
const H=Java.type('org.parosproxy.paros.model.HistoryReference');
const Message=Java.type('org.parosproxy.paros.network.HttpMessage');
const RH=Java.type('org.parosproxy.paros.network.HttpRequestHeader');
const SH=Java.type('org.parosproxy.paros.network.HttpResponseHeader');
const V=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
const msg=new Message();msg.setRequestHeader(new RH(X.requestHeader));msg.setRequestBody(X.requestBody);
msg.setResponseHeader(new SH(X.responseHeader));msg.setResponseBody(X.responseBody);
const history=new H(M.getSingleton().getSession(),H.TYPE_MANUAL,msg);
const node=M.getSingleton().getSession().getSiteTree().addPath(history);node.setHistoryReference(history);
V.setGlobalVar(KEY,JSON.stringify({historyId:history.getHistoryId(),method:node.getHistoryReference().getHttpMessage().getRequestHeader().getMethod(),body:node.getHistoryReference().getHttpMessage().getRequestBody().toString()}));
"""
        code='const X='+json.dumps(values)+';const KEY='+json.dumps(key)+';\ntry {\n'+code+"\n}catch(e){Java.type('org.zaproxy.zap.extension.script.ScriptVars').setGlobalVar(KEY,JSON.stringify({error:String(e)}));}\n"
        filename='baseline-'+label+'.js';(self.rt.work/filename).write_text(code)
        self.engine('script','action','load',{'scriptName':key,'scriptType':'standalone','scriptEngine':'Graal.js','fileName':'/zap/wrk/'+filename})
        try:
            self.j.append('intent',{'action':'bind-native-baseline','campaignId':label,'scriptSha256':hashlib.sha256(code.encode()).hexdigest()})
            self.engine('script','action','runStandAloneScript',{'scriptName':key})
            # Standalone scripts can finish after the action ACK. Poll only the
            # result; never rerun the script or its native baseline dispatch.
            deadline=time.monotonic()+5
            while True:
                try:
                    value=json.loads(self.engine('script','view','globalVar',{'varKey':key})['globalVar'])
                    break
                except Exception:
                    if time.monotonic()>=deadline:raise
                    time.sleep(.1)
            if value.get('error'):
                save(self.out,'baseline-binding/'+label+'-error.json',value)
                raise ValueError('native baseline binding script failed')
            if value['method']!=expected_method or value['body']!=message['requestBody']:raise ValueError('native baseline binding drift')
            save(self.out,'baseline-binding/'+label+'.json',{'historyId':value['historyId'],'requestBodySha256':hashlib.sha256(value['body'].encode()).hexdigest(),'method':value['method'],'extraTargetRequests':0})
            self.j.append('ack',{'action':'bind-native-baseline','campaignId':label,'historyId':value['historyId']})
        finally:
            save(self.out,'baseline-binding/'+label+'-script-state.json',self.engine('script','view','listScripts'))
            self.engine('script','action','remove',{'scriptName':key})
    def stop(self):
        start=time.monotonic();requested=time.time();save(self.rt.config,'STOP',b'stop\n')
        before=json.loads((self.rt.capture/'accounting.json').read_bytes()) if (self.rt.capture/'accounting.json').exists() else None
        errors=[]
        try:
            for s in self.engine('ascan','view','scans')['scans']:
                sid=str(s['id'])
                if s.get('state') not in ('FINISHED','STOPPED'):self.engine('ascan','action','stop',{'scanId':sid})
            deadline=time.monotonic()+self.p['limits']['stopSeconds']
            while True:
                scans=self.engine('ascan','view','scans')['scans']
                if all(s.get('state') in ('FINISHED','STOPPED') for s in scans):
                    gauge=json.loads((self.rt.capture/'accounting.json').read_bytes()) if (self.rt.capture/'accounting.json').exists() else {'inFlight':0}
                    if gauge.get('inFlight')==0:break
                if time.monotonic()>=deadline:raise TimeoutError('native stop terminal deadline')
                time.sleep(.2)
            for op in self.ops:
                op['terminal']=any(str(s['id'])==op['nativeScanId'] and s.get('state') in ('FINISHED','STOPPED') for s in scans)
                if 'scanProgress' not in op:op['scanProgress']=self.engine('ascan','view','scanProgress',{'scanId':op['nativeScanId']})
            after=json.loads((self.rt.capture/'accounting.json').read_bytes()) if (self.rt.capture/'accounting.json').exists() else None
        except Exception as exc:errors.append(type(exc).__name__);after=None
        record={'requestedAt':requested,'latencySeconds':time.monotonic()-start,'deadlineSeconds':self.p['limits']['stopSeconds'],'before':before,'after':after,'errors':errors,'nativeScans':scans if 'scans' in locals() else None,'zeroInstantForwardingClaim':False}
        save(self.out,'STOP_ACCOUNTING.json',record);self.j.append('stop-accounting',record)
        return not errors
    def export(self):
        if not self.mcp:return
        stable=0;deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            text=self.mcp.call('zap_passive_scan_status',{});stable=stable+1 if field(text,'Completed')=='yes' and field(text,'Records remaining')=='0' else 0
            self.j.append('passive',{'stable':stable,'text':text})
            if stable>=2:break
            time.sleep(1)
        else:raise TimeoutError('passive settle')
        for fmt in ('json','html'):
            generated=self.mcp.call('zap_report_generate',{'baseUrl':self.p['origin'],'format':fmt,'theme':'light'});path=field(generated,'Path');pages=[]
            def reader(path,offset,sha):
                args={'reportPath':path,'offset':offset,'maxChars':100000}
                if sha:args['expectedSha256']=sha
                page=json.loads(self.mcp.call('zap_report_read_chunk',args));pages.append({k:v for k,v in page.items() if k!='content'});return page
            data=read_report(reader,path,32*1024**2);save(self.out,'reports/backend.'+fmt,data);save(self.out,'reports/'+fmt+'-readback.json',{'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'pages':pages,'endOfFile':True})
        for tool,name in [('zap_findings_summary','findings-summary.md'),('zap_findings_snapshot','snapshot.json')]:
            if tool in self.mcp.contracts:
                try:save(self.out,name,self.mcp.call(tool,{'baseUrl':self.p['origin']}).encode())
                except Exception as exc:self.report_errors.append({'tool':tool,'supplemental':True,'reason':'Native explicit POST operations have no guided history entry; keep tool failure, use native alert/message/report reconciliation','errorType':type(exc).__name__})
        # Full page export after producers stopped/passive settled. Snapshot-only remains explicit in synthesis.
        count=int(self.engine('core','view','numberOfMessages')['numberOfMessages']);messages=[]
        cursor=0
        while len(messages)<count:
            requested=min(5,count-len(messages))
            page=self.engine('core','view','messages',{'start':cursor,'count':requested})['messages']
            if len(page)!=requested:raise ValueError('missing message page')
            messages.extend(page);cursor=len(messages)+1
        if len({m['id'] for m in messages})!=count or int(self.engine('core','view','numberOfMessages')['numberOfMessages'])!=count:raise ValueError('message export drift or duplicate')
        save(self.out,'messages.json',{'messages':messages,'count':count,'complete':True})
        alerts=[];expected=int(self.engine('core','view','numberOfAlerts',{'baseurl':self.p['origin']})['numberOfAlerts'])
        for start in range(0,expected,50):
            page=self.engine('alert','view','alerts',{'baseurl':self.p['origin'],'start':start,'count':min(50,expected-start)})['alerts']
            if len(page)!=min(50,expected-start):raise ValueError('missing alert page')
            alerts.extend(page)
        if len({str(a['id']) for a in alerts})!=expected:raise ValueError('duplicate alert page')
        save(self.out,'alerts-native.json',{'alerts':alerts,'count':expected,'complete':True})
        mids={str(m['id']) for m in messages};missing=[str(a['id']) for a in alerts if str(a.get('messageId')) not in mids]
        save(self.out,'ALERT_MESSAGE_RECONCILIATION.json',{'alertCount':expected,'messageCount':count,'missingMessageRefs':missing,'detailStatus':'complete' if not missing else 'partial'})
        validate_exports(messages,alerts,count,expected)
    def execute(self,interrupt_after=None):
        old_handlers={}
        for sig in (signal.SIGINT,signal.SIGTERM):
            if threading.current_thread() is threading.main_thread():old_handlers[sig]=signal.signal(sig,lambda *a:self.cancelled.set())
        watcher=None;ready=False
        try:
            self.resources(True);print('Preflight passed; provisioning owned scanner',flush=True)
            self.rt.provision();self.rt.wait_health(180);ready=True;self.rt.boundary()
            self.mcp=RecordedMCP(self.rt,self.out);save(self.out,'mcp-discovery.json',self.mcp.initialize());self.configure()
            watcher=threading.Thread(target=self.monitor,daemon=True);watcher.start()
            print('Anonymous seeds via native ZAP',flush=True)
            for c in self.p['cases']:self.seed(c)
            print('Selected bounded active campaigns',flush=True)
            for camp in self.p['campaigns']:self.attack(camp,interrupt_after)
            self.result['executionStatus']='completed' if all(c['observed']['matched'] for c in self.coverage) and all(o.get('techniqueExercised') for o in self.ops) else 'partial'
        except BaseException as exc:
            self.result.update(executionStatus='cancelled' if isinstance(exc,(InterruptedError,KeyboardInterrupt)) else 'failed',errorType=type(exc).__name__,detail=str(exc)[:250]);print('Run stopped:',type(exc).__name__,str(exc)[:150],flush=True)
        finally:
            if ready:
                stop_ok=self.stop()
                try:self.export();self.resources();self.result['evidenceStatus']='complete' if stop_ok else 'incomplete'
                except Exception as exc:self.report_errors.append({'errorType':type(exc).__name__,'detail':str(exc)[:200]});print('Evidence partial:',type(exc).__name__,str(exc)[:150],flush=True)
            self.monitor_stop.set()
            if watcher:watcher.join(timeout=6)
            try:self.rt.cleanup();self.result['cleanupStatus']='clean'
            except Exception as exc:self.result['cleanupStatus']='incomplete';self.result['cleanupErrorType']=type(exc).__name__
            try:b,proof=self.inspect();self.result['targetBindingUnchanged']=b==self.p['targetBinding']
            except Exception:self.result['targetBindingUnchanged']=False
            self.result['targetPreservation']='removed-owned-target' if self.p['targetOwnership']=='run-owned' and self.result['cleanupStatus']=='clean' else 'unchanged' if self.result['targetBindingUnchanged'] else 'drift-or-unverified'
            self.result['gateDecision']='review_required' if self.result['executionStatus']=='completed' and self.result['evidenceStatus']=='complete' and self.result['cleanupStatus']=='clean' and self.result['targetPreservation']!='drift-or-unverified' else 'block'
            self.result['securityVerdict']='requires-triage' if self.result['evidenceStatus']=='complete' else 'inconclusive'
            save(self.out,'RUN.json',self.result);save(self.out,'COVERAGE.json',{'cases':self.coverage,'dispositions':self.p['dispositions'],'operationsExpected':len(self.p['discovery']['operations']),'scope':'anonymous; denial is not authenticated business coverage'})
            save(self.out,'OPERATIONS.json',self.ops);save(self.out,'RESOURCES.json',{'samples':self.samples,'resourceFailure':self.resource_failure,'profile':'bounded research candidate, not W4 operational calibration','artifactCap':self.p['limits']['artifactBytes']});save(self.out,'EVIDENCE_ERRORS.json',self.report_errors)
            # No extra work after seal. Raw capture and native files stay private local.
            entries=[]
            for path in sorted(self.out.rglob('*')):
                if path.is_file():path.chmod(0o600);entries.append({'path':str(path.relative_to(self.out)),'bytes':path.stat().st_size,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
            manifest={'contract':'be-anonymous-research-evidence/1.0','runId':self.p['runId'],'planHash':self.hash,'result':self.result,'artifacts':entries,'notReleaseApproval':True}
            save(self.out,'manifest.json',manifest);save(self.out,'manifest.sha256',hashlib.sha256((self.out/'manifest.json').read_bytes()).hexdigest().encode()+b'\n')
            for sig,handler in old_handlers.items():signal.signal(sig,handler)
        return self.result


def verify(root):
    root=Path(root).resolve();m=json.loads((root/'manifest.json').read_bytes())
    if hashlib.sha256((root/'manifest.json').read_bytes()).hexdigest()!=(root/'manifest.sha256').read_text().strip():raise ValueError('manifest hash mismatch')
    seen=set()
    for a in m['artifacts']:
        p=root/a['path']
        if p.is_symlink() or not p.resolve().is_relative_to(root) or a['path'] in seen:raise ValueError('invalid artifact path')
        seen.add(a['path']);b=p.read_bytes()
        if len(b)!=a['bytes'] or hashlib.sha256(b).hexdigest()!=a['sha256']:raise ValueError('artifact mismatch')
    plan=json.loads((root/'PLAN.json').read_bytes())
    if canonical_hash(plan)!=m['planHash']:raise ValueError('plan hash mismatch')
    Journal(root/'journal.jsonl',plan['runId'],m['planHash'])
    complete=m['result']['evidenceStatus']=='complete'
    if complete:
        for name in ('reports/backend.json','reports/backend.html','messages.json','alerts-native.json','STOP_ACCOUNTING.json','ALERT_MESSAGE_RECONCILIATION.json'):
            if name not in seen:raise ValueError('required evidence missing')
        for fmt in ('json','html'):
            b=(root/('reports/backend.'+fmt)).read_bytes();r=json.loads((root/('reports/'+fmt+'-readback.json')).read_bytes())
            if not r['endOfFile'] or r['bytes']!=len(b) or hashlib.sha256(b).hexdigest()!=r['sha256']:raise ValueError('report readback mismatch')
        messages=json.loads((root/'messages.json').read_bytes());alerts=json.loads((root/'alerts-native.json').read_bytes())
        validate_exports(messages['messages'],alerts['alerts'],messages['count'],alerts['count'])
        # Replay the recorded MCP chunk sequence offline, including offsets/EOF/hash.
        for fmt in ('json','html'):
            readback=json.loads((root/('reports/'+fmt+'-readback.json')).read_bytes());upstream=readback['pages'][0]['reportPath'];recorded=[]
            for req in sorted((root/'tools').glob('*zap_report_read_chunk-request.json')):
                request=json.loads(req.read_bytes())
                if request['arguments']['reportPath']!=upstream:continue
                response=json.loads(req.with_name(req.name.replace('-request.json','-response.json')).read_bytes())
                text='\n'.join(c['text'] for c in response['content'] if c.get('type')=='text')
                if text.startswith('"'):text=json.loads(text)
                recorded.append(json.loads(text))
            iterator=iter(recorded)
            data=read_report(lambda *args:next(iterator),upstream,32*1024**2)
            if data!=(root/('reports/backend.'+fmt)).read_bytes():raise ValueError('recorded chunk/report mismatch')
            if next(iterator,None) is not None:raise ValueError('unexpected trailing chunk page')
    return {'integrityVerified':True,'artifactCount':len(seen),'evidenceComplete':complete,'result':m['result'],'meaning':'integrity/status consistency only, not security approval'}
