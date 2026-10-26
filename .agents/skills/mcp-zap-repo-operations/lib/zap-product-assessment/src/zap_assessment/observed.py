"""Instrumented synthetic-only Docker runtime for W4 calibration/conformance.

No registration for borrowed products or protected modes. Reuses DockerRuntime
and Executor; observer headers make header/body vectors explicitly unsupported.
"""
import hashlib,json,os,time
from pathlib import Path
from .contracts import Blocked,ROOT,canonical
from .runtime import DockerRuntime,docker
from .traffic import read_rows,correlate,capture_snapshot

class ObservedDockerRuntime(DockerRuntime):
    def __init__(self,*args):
        super().__init__(*args);self.capture_ready=False;self.capture_terminal=False;self.probe_name=None;self.metrics=[];self.sample_baseline=None;self.phase='startup';self.pending_since={};self.peak_cache={};self.resource_cleanup=False
    def owned_names(self):
        # A fresh recovery instance has not sampled yet. Reconcile its helper
        # from the original creation intent, then use normal ID/image ownership
        # checks before stopping or removing it.
        helper=f'zpa-{self.run_id}-measurement'
        recorded=any(e['kind']=='intent' and e['data'].get('action')=='container-create' and e['data'].get('resource')==helper and e['data'].get('createdByRun')==self.run_id for e in self.journal.events)
        return list(dict.fromkeys([*super().owned_names(),*([helper] if recorded else [])]))
    def resource_sample(self):
        if self.plan.data['product']['adapter']!='synthetic-http-v1':raise Blocked('W4 collector only accepts owned anonymous fixture')
        if self.probe_name is None:
            self.probe_name=f'zpa-{self.run_id}-measurement'
            self.names.append(self.probe_name);self.commands={self.probe_name:['sleep','3000']}
            # Read kernel cgroup counters from the owned measurement helper.
            # Distroless MCP has no cat/shell; never require tools in workloads.
            self.create(self.probe_name,self.plan.data['runtime']['boundary'],['--network','none','--read-only','--cap-drop','ALL','--pid','host','--cgroupns','host','--security-opt','no-new-privileges','--memory','32m','--pids-limit','32'])
        s=os.statvfs(self.root)
        code="import os,json; s=os.statvfs('/'); m=dict(x.split(':',1) for x in open('/proc/meminfo')); print(json.dumps({'dockerFree':s.f_bavail*s.f_frsize,'ramAvailable':int(m['MemAvailable'].split()[0])*1024}))"
        data=json.loads(docker(['exec',self.probe_name,'python','-c',code],timeout=2))
        usage=sum(p.stat().st_size for p in self.root.rglob('*') if p.is_file() and not p.is_symlink())
        peaks={};writable={}
        # W5 adds a bounded no-network DB reader. Measure every owned workload,
        # retaining stopped peaks; the sampler itself remains the only exclusion.
        for name in self.names:
            if name==self.probe_name:continue
            if name not in self.created:continue
            try:info=self.check_owner(name,timeout=1)
            except Blocked:
                removed=any(e['kind']=='ack' and e['data'].get('action')=='container-removed' and e['data'].get('resource')==name for e in self.journal.events)
                if self.resource_cleanup and removed:
                    peaks[name]=self.peak_cache.get(name,0);continue
                raise
            if self.resource_cleanup and not info['State']['Running']:
                peaks[name]=self.peak_cache.get(name,0)
                writable[name]=int(docker(['inspect','--size','--format','{{.SizeRw}}',name],timeout=1).strip());continue
            pid=info['State']['Pid']
            if type(pid) is not int or pid<=0:raise Blocked('owned workload has no live cgroup')
            code="import pathlib,sys; rows=pathlib.Path('/proc/'+sys.argv[1]+'/cgroup').read_text().splitlines(); paths=[r.split(':',2)[2] for r in rows if r.startswith('0::')]; assert len(paths)==1; p=pathlib.PurePosixPath(paths[0]); assert '..' not in p.parts and (sys.argv[2] in p.parts or p.name=='docker-'+sys.argv[2]+'.scope'); print((pathlib.Path('/sys/fs/cgroup')/str(p).lstrip('/')/'memory.peak').read_text())"
            peaks[name]=int(docker(['exec',self.probe_name,'python','-c',code,str(pid),info['Id']],timeout=1).strip())
            after=self.check_owner(name,timeout=1)
            if after['State']['Pid']!=pid or not after['State']['Running']:
                if after['State']['Running'] or not self.resource_cleanup:raise Blocked('owned cgroup identity changed while sampling')
            self.peak_cache[name]=max(self.peak_cache.get(name,0),peaks[name])
            writable[name]=int(docker(['inspect','--size','--format','{{.SizeRw}}',name],timeout=1).strip())
        row={'hostFree':s.f_bavail*s.f_frsize,'dockerAvailable':True,**data}
        if self.sample_baseline is None:self.sample_baseline=dict(row)
        self.metrics.append({'at':time.monotonic(),'phase':self.phase,'hostGrowth':usage,
                             'dockerGrowth':sum(writable.values()),'containerMemoryPeakBytes':peaks,'containerWritableBytes':writable,
                             'ramAvailable':data['ramAvailable'],'hostFree':row['hostFree'],'dockerFree':row['dockerFree']})
        return row
    phase_capture=True
    def set_phase(self,phase):
        self.phase=phase
        if self.capture_ready:
            from .safety_io import write_all
            dst=self.root/'zap-workspace/observer-phase.txt';tmp=dst.with_suffix('.pending')
            fd=os.open(tmp,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o644)
            try:write_all(fd,phase.encode());os.fsync(fd)
            finally:os.close(fd)
            os.replace(tmp,dst)
    def configure_active_policy(self):
        if not self.plan.data['workflow']['active']:return
        # The image's dynamic active script auto-enables during scan startup.
        # Remove it explicitly from this owned minimal policy before inventory.
        self.engine('script','action','remove',{'scriptName':'SwaggerSecretDetector.js'})
        self.journal.append('active-policy',{'policy':'w4-query-only','rules':['40012'],'removedOwnedScripts':['SwaggerSecretDetector.js'],'supportedVectors':['GET-query']})
        self.engine('ascan','action','addScanPolicy',{'scanPolicyName':'w4-query-only'})
        self.engine('ascan','action','disableAllScanners',{'scanPolicyName':'w4-query-only'})
        self.engine('ascan','action','enableScanners',{'ids':'40012','scanPolicyName':'w4-query-only'})
        self.engine('ascan','action','setOptionTargetParamsInjectable',{'Integer':'1'})
        self.engine('ascan','action','setOptionTargetParamsEnabledRPC',{'Integer':'0'})
        self.engine('ascan','action','setOptionAddQueryParam',{'Boolean':'false'})
    def provision(self):
        result=super().provision()
        return result|{'trafficCollector':'native HttpSender + boundary + independent target arrival; synthetic only',
                       'unsupportedVectors':['header','body','cookie'],'fidelity':'HTTP anonymous fixture with non-secret correlation header'}
    def configure_rate(self,rate):
        result=super().configure_rate(rate)
        self.configure_active_policy();self.install_capture();return result
    def target_request(self,url):
        # After activation every target request needs an actual engine sender
        # receipt. The controller cannot bypass capture with a trusted marker.
        from urllib.parse import urlsplit
        from .egress import policy_target
        target=urlsplit(url)
        policy_target('GET',url,{'Host':target.netloc},self.plan.data['product']['attackOrigins'][0],{'/health'})
        raw='GET '+url+' HTTP/1.1\r\nHost: '+target.netloc+'\r\nConnection: close\r\n\r\n'
        result=self.engine('core','action','sendRequest',{'request':raw,'followRedirects':'false'})
        try:
            rows=result['sendRequest']
            if len(rows)!=1:raise ValueError('response count')
            row=rows[0];status=int(row['responseHeader'].splitlines()[0].split()[1])
            return {'status':status,'body':row['responseBody']}
        except (KeyError,IndexError,TypeError,ValueError) as exc:
            raise Blocked('captured health response contract') from exc
    def install_capture(self):
        wrk=self.root/'zap-workspace'
        source=(ROOT/'src/zap_assessment/probes/TrafficProbe.java').read_bytes()
        (wrk/'TrafficProbe.java').write_bytes(source)
        (wrk/'observer-phase.txt').write_text(self.phase);(wrk/'observer-phase.txt').chmod(0o644)
        identity=wrk/'observer-run-id.txt';identity.write_text(self.run_id);identity.chmod(0o644)
        rules=self.engine('ascan','view','scanners',{}).get('scanners')
        if not isinstance(rules,list) or not rules:raise Blocked('loaded scanner IDs unavailable')
        ids=[str(r['id']) for r in rules]
        if len(ids)!=len(set(ids)) or any(not v.isdecimal() for v in ids):raise Blocked('loaded scanner ID shape')
        rule_file=wrk/'observer-rule-ids.txt';rule_file.write_text(','.join(sorted(ids)));rule_file.chmod(0o644)
        # Existing run-owned Java image includes javac; no downloads, host
        # classpath or add-on modification. Compile only the native observer.
        docker(['exec',self.names[2],'javac','-cp','/zap/*:/zap/lib/*','-d','/zap/wrk/probe-classes','/zap/wrk/TrafficProbe.java'],timeout=30)
        bootstrap="""const URLClassLoader=Java.type('java.net.URLClassLoader');
const File=Java.type('java.io.File');const HttpSender=Java.type('org.parosproxy.paros.network.HttpSender');
const Vars=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
const loader=new URLClassLoader(Java.to([new File('/zap/wrk/probe-classes').toURI().toURL()],'java.net.URL[]'),HttpSender.class.getClassLoader());
const cls=loader.loadClass('TrafficProbe');Vars.setGlobalCustomVar('w4.class',cls);
const Files=Java.type('java.nio.file.Files');const Path=Java.type('java.nio.file.Path');
cls.getMethod('install',Java.type('java.lang.String').class).invoke(null,Files.readString(Path.of('/zap/wrk/observer-run-id.txt')));
cls.getMethod('bindRules',Java.type('java.lang.String').class).invoke(null,Files.readString(Path.of('/zap/wrk/observer-rule-ids.txt')));
"""
        inventory="""const Vars=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
Vars.getGlobalCustomVar('w4.class').getMethod('inventory',Java.type('java.lang.String').class).invoke(null,'');
"""
        for name,code in [('w4-capture',bootstrap),('w4-inventory',inventory)]:
            f=wrk/(name+'.js');f.write_text(code);f.chmod(0o644)
            self.engine('script','action','load',{'scriptName':name,'scriptType':'standalone','scriptEngine':'Graal.js','fileName':'/zap/wrk/'+name+'.js'})
        self.engine('script','action','runStandAloneScript',{'scriptName':'w4-capture'})
        ready=self.engine('script','view','globalVar',{'varKey':'w4.installed'})
        self.capture_install_readback=ready
        if ready.get('globalVar')!=self.run_id:raise Blocked('collector install unconfirmed')
        # Sender file contains only IDs/hashes/public engine initiator. Read by
        # boundary through a read-only mount; no shared writable script context.
        events=wrk/'sender-events.jsonl'
        if not events.exists():events.write_bytes(b'')
        events.chmod(0o644)
        allowed={'/api/echo','/','/health','/api/items','/openapi.json','/redirect','/redirect-alias','/redirect-scheme'}
        cfg={'senderPath':'/capture/sender-events.jsonl','origin':self.plan.data['product']['attackOrigins'][0],'allowedPaths':sorted(allowed),'activeRules':['40012'] if self.plan.data['workflow']['active'] else [],'queryPath':'/api/echo','requirePhase':True}
        f=self.root/'fixture/traffic-config.json';f.write_bytes(canonical(cfg));f.chmod(0o644)
        self.capture_ready=True
        self.journal.append('capture-installed',{'observerSourceSha256':hashlib.sha256(source).hexdigest(),'fidelity':'correlation header added, header/body vectors unsupported','allowedPaths':sorted(allowed),'startMonotonic':time.monotonic()})
    def policy_inventory(self):
        result=super().policy_inventory()
        if self.plan.data['workflow']['active']:
            rows=self.engine('ascan','view','scanners',{'scanPolicyName':'w4-query-only'})['scanners']
            from .runtime import engine_bool
            result['rules']=[{'id':str(r['id']),'enabled':engine_bool(r['enabled'])} for r in rows]
        self.engine('script','action','runStandAloneScript',{'scriptName':'w4-inventory'})
        raw=(self.root/'zap-workspace/script-inventory.json').read_bytes()
        expected=self.engine('script','view','globalVar',{'varKey':'w4.inventory'})
        if expected.get('globalVar')!=hashlib.sha256(raw).hexdigest():raise Blocked('in-memory script content readback changed')
        rows=json.loads(raw)
        # Native introspection of actual ScriptWrapper.getContents, not hash of
        # the path or only the original source file.
        result['scripts']=rows
        return result
    def policy_traffic(self):
        if not self.capture_ready:return {'events':[],'complete':False}
        sender,boundary,target=capture_snapshot([self.root/'zap-workspace/sender-events.jsonl',self.root/'fixture/boundary.jsonl',self.root/'fixture/arrivals.jsonl'])
        result=correlate(sender,boundary,target,terminal=self.capture_terminal)
        # In-flight requests are expected while producers run. Their missing
        # receipts are tolerated only transiently and bound to request count.
        if result['pending'] and not self.capture_terminal:
            completed={e['requestId'] for e in result['events']}
            now=time.monotonic()
            for req in (e for e in sender if e.get('kind')=='request' and e['requestId'] not in completed):
                at=self.pending_since.setdefault(req['requestId'],now)
                if now-at>8:raise Blocked('traffic receipt deadline exceeded')
            result['complete']=True
        return result
    def observations(self):
        result=super().observations();self.capture_terminal=True
        # No new producers after settle/report. Allow receipt callback to flush
        # before strict terminal count matching, bounded below ordinary timeout.
        for _ in range(20):
            try:
                result['trafficCorrelation']=self.policy_traffic();self.final_traffic=result['trafficCorrelation'];return result
            except Blocked as exc:
                if str(exc)!='terminal traffic capture incomplete':raise
                time.sleep(.1)
        raise Blocked('terminal traffic capture incomplete')
    def cleanup(self):
        super().cleanup()
        if not hasattr(self,'final_traffic'):return
        # Cleanup has confirmed that every owned producer/guard/target stopped.
        # Re-read durable logs now: a late background request must invalidate the
        # earlier network artifact rather than disappear from a complete bundle.
        final=self.policy_traffic()
        if final!=self.final_traffic:raise Blocked('traffic changed after terminal snapshot')
        self.closure_evidence={'schemaVersion':'traffic-closure/1.0','runId':self.run_id,
                               'allOwnedResourcesStopped':True,'terminalCaptureUnchanged':True,
                               'trafficSha256':hashlib.sha256(canonical(final)).hexdigest(),'counts':final['counts']}
