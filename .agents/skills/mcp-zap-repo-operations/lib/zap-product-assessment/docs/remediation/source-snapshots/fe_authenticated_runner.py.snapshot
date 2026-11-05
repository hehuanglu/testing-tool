"""Session-group orchestration over owned W3C browser and validated native MCP operations."""
import json,os,signal,subprocess,threading,time
from pathlib import Path
from urllib.parse import urlsplit,urlencode
from .fe_authenticated_contract import validate_plan,canonical,digest,load,save,admission
from .fe_authenticated_runtime import AuthenticatedRuntime
from .fe_authenticated_binding import inspect
from .fe_anonymous_controls import configure
from .journal import Journal
from .fe_authenticated_mcp import RecordedMCP
from .transport import field
from .evidence import read_report
from .fe_authenticated_transport import valid_owned_id
from .fe_authenticated_auth import pointer

class AuthenticatedRun:
    def __init__(self,plan,out,actors,*,calibration=False):
        from .fe_authenticated_auth import validate_actor_roles
        validate_actor_roles(plan['journeys']['auth'],actors)
        if not calibration:validate_plan(plan,live=True)
        inspect(plan['selection']);self.p=plan;self.out=Path(out).resolve();self.out.mkdir(parents=True,mode=0o700,exist_ok=False)
        self.hash=canonical(plan);save(self.out,'PLAN.json',plan);self.j=Journal(self.out/'journal.jsonl',plan['runId'],self.hash);self.rt=AuthenticatedRuntime(plan,self.out,self.j,actors)
        self.actors=actors;save(self.out,'private/ACTORS_INITIAL.json',actors);self.calibration=calibration;self.cancel=threading.Event();self.done=threading.Event();self.samples=[];self.ops=[];self.errors=[];self.mcp=None;self.ei=0;self.started=time.monotonic();self.native={};self.group_results=[];self.prepared={}
        self.result={'executionStatus':'running','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block','taskCompletion':'partial'}
    def engine(self,c,k,n,args=None):
        self.ei+=1;prefix='engine/'+str(self.ei).zfill(5)+'-'+c+'-'+n
        save(self.out,prefix+'-request.json',{'component':c,'kind':k,'name':n,'arguments':args or {}});value=self.rt.engine(c,k,n,args or {})
        recorded=value
        if (c,k,n)==('core','view','messages'):
            from .fe_authenticated_semantics import sha
            recorded={'rawRef':'messages.json','recording':'native history retained in full once; this call records IDs and byte hashes','messages':[{'id':m['id'],'requestHeaderSha256':sha(m['requestHeader'].encode()),'requestBodySha256':sha(m['requestBody'].encode()),'responseHeaderSha256':sha(m['responseHeader'].encode()),'responseBodySha256':sha(m['responseBody'].encode())} for m in value['messages']]}
        save(self.out,prefix+'-response.json',recorded);return value
    def current(self):
        if self.cancel.is_set():raise InterruptedError('owned stop requested')
        if time.monotonic()-self.started>self.p['limits']['executionSeconds']:raise TimeoutError('run deadline')
        if not self.calibration:validate_plan(self.p,live=True)
        inspect(self.p['selection'])
    def monitor(self):
        while not self.done.wait(2):
            try:
                v=os.statvfs(self.out);sample={'at':time.time(),'hostFree':v.f_bavail*v.f_frsize}
                if len(self.samples)%3==0 and self.rt.names[4] in self.rt.created:sample.update(self.rt.sample())
                self.samples.append(sample)
                if min(sample['hostFree'],sample.get('dockerFree',sample['hostFree']))<self.p['limits']['reserveBytes']:raise ValueError('resource reserve breached')
                sizes=[]
                for f in self.out.rglob('*'):
                    try:
                        if f.is_file():sizes.append(f.stat().st_size)
                    except FileNotFoundError:continue  # owned profile disposal / atomic IPC rename
                sample['artifactBytes']=sum(sizes)
                if sample['artifactBytes']>self.p['limits'].get('artifactBytes',128*1024**2):raise ValueError('artifact budget breached')
                if sample.get('ramAvailable',4*1024**3)<1024**3:raise ValueError('RAM reserve breached')
                records=[load(p) for p in self.rt.capture.glob('[0-9]*.json')]
                if any(r.get('identityFailure') or r.get('policyLatched') or r.get('reconciliationRequired') for r in records):raise ValueError('identity/unknown mutation latch')
            except Exception as e:
                self.errors.append({'kind':'monitor','errorType':type(e).__name__,'reason':str(e)[:100]});self.cancel.set();(self.rt.config/'STOP').touch();return
    def configure(self):
        configure(self.rt)
        save(self.out,'FRESH_SESSION.json',{'sites':self.engine('core','view','sites'),'messages':self.engine('core','view','numberOfMessages'),'active':self.engine('ascan','view','scans')})
        fresh=load(self.out/'FRESH_SESSION.json')
        if fresh!={'sites':{'sites':[]},'messages':{'numberOfMessages':'0'},'active':{'scans':[]}}:raise ValueError('owned scanner session not fresh')
        for name,args in [('setOptionThreadPerHost',{'Integer':1}),('setOptionHostPerScan',{'Integer':1}),('setOptionMaxScanDurationInMins',{'Integer':1}),('setOptionAddQueryParam',{'Boolean':'false'}),('setOptionInjectPluginIdInHeader',{'Boolean':'true'})]:self.engine('ascan','action',name,args)
        save(self.out,'SCANNER.json',{'version':self.engine('core','view','version'),'addons':self.engine('autoupdate','view','installedAddons'),'activeRules':self.engine('ascan','view','scanners'),'passiveRules':self.engine('pscan','view','scanners')})
    def capture_bindings(self,group,journeys):
        path=self.out/'browser'/group['id']/'FIXTURE_BINDINGS.json'
        if not path.exists():return
        stamp=digest(path)
        if getattr(self,'binding_stamps',{}).get(group['id'])==stamp:return
        proofs=[]
        for binding in load(path):
            journey=next(j for j in journeys if j['id']==binding['journeyId']);step=journey['steps'][binding['stepIndex']];actor=self.actors[journey['actorRef']]
            if step['action']!='readback' or binding['actorRef']!=journey['actorRef'] or binding['field']!=step['fixtureField']:raise ValueError('unreviewed browser ID binding')
            concrete=step['path'].format_map(actor.get('fixtures',{}));response=binding['response']
            if response.get('status')!=200 or response.get('url')!=self.p['selection']['origin']+concrete:raise ValueError('readback response origin/status')
            values=pointer(response['body'],step['pointer']);values=values if isinstance(values,list) else [values]
            if step.get('matchPointer'):values=[v for v in values if pointer(v,step['matchPointer'])==actor['fixtures'][step['matchFixture']]]
            if len(values)!=1 or pointer(values[0],step['valuePointer'])!=binding['value'] or not valid_owned_id(binding['value'],step.get('idFormat','integer')):raise ValueError('readback owned ID derivation mismatch')
            messages=self.engine('core','view','messages',{'baseurl':self.p['selection']['origin']+concrete,'start':0,'count':30})['messages']
            candidates=[]
            for message in messages:
                try:
                    if json.loads(message['responseBody'])!=response['body']:continue
                    body_hash=__import__('hashlib').sha256(message['responseBody'].encode()).hexdigest()
                    rows=[load(f) for f in self.rt.capture.glob('[0-9]*.json')]
                    from .fe_authenticated_semantics import request,sha
                    wire=request(message,self.p['selection']['origin'])
                    matching=[r for r in rows if r.get('forwarded') and r.get('actorRef')==journey['actorRef'] and r.get('sessionGroup')==group['id'] and r.get('authSlot')=='browser' and r.get('caseId')==journey['id'] and r['method']=='GET' and r['url']==response['url'] and r.get('responseBodySha256')==body_hash and r.get('identityPhase')=='authenticated' and r.get('credentialFingerprint')==sha(wire['headers'].get('authorization','').encode())]
                    if matching:candidates.append({'nativeMessageId':str(message['id']),'brokerSequences':[r['sequence'] for r in matching]})
                except (ValueError,KeyError,TypeError):continue
            if not candidates:raise ValueError('owned ID lacks independent native/broker response')
            previous=actor.setdefault('fixtures',{}).get(binding['field'])
            if previous is not None and previous!=binding['value']:raise ValueError('owned ID drift')
            actor['fixtures'][binding['field']]=binding['value'];proofs.append({**binding,'wireProof':candidates})
        save(self.out,'private/BINDINGS-'+group['id']+'.json',proofs);self.rt.update_bindings()
        ack=save(self.rt.root/'browser','BINDINGS_ACK.pending',{'group':group['id'],'sha256':stamp});ack.chmod(0o444);os.replace(ack,self.rt.root/'browser/BINDINGS_ACK.json')
        if not hasattr(self,'binding_stamps'):self.binding_stamps={}
        self.binding_stamps[group['id']]=stamp
    def group(self,g,journeys):
        self.current();actor=self.actors[g['actorRef']];fixtures={**actor.get('fixtures',{}),'username':actor['username'],'password':actor['password']}
        actor_refs=[ref for ref in g.get('actorRefs',[g['actorRef']]) if ref in self.actors]
        job={'group':g,'journeys':journeys,'auth':self.p['journeys']['auth'],'origin':self.p['selection']['origin'],'fixtures':fixtures,'actors':{ref:{'username':self.actors[ref]['username'],'password':self.actors[ref]['password'],'fixtures':self.actors[ref].get('fixtures',{})} for ref in actor_refs}}
        f=save(self.rt.root/'browser','job-'+g['id']+'.json',job);f.chmod(0o444)
        self.j.append('intent',{'action':'browser-session-group','group':g['id'],'actorRef':g['actorRef'],'replay':False})
        proc=subprocess.Popen(['docker','exec','--user','1004:1004',self.rt.names[4],'python3','-m','zap_assessment.fe_authenticated_browser','/browser/'+f.name],stdout=subprocess.DEVNULL,stderr=(self.out/('worker-'+g['id']+'.log')).open('wb'))
        deadline=time.monotonic()+min(900,self.p['limits']['executionSeconds']);seen=set()
        try:
            while proc.poll() is None:
                self.current()
                self.capture_bindings(g,journeys)
                if time.monotonic()>deadline:raise TimeoutError('session group deadline')
                waiting=self.rt.root/'browser/WAITING.json'
                if waiting.exists():
                    try:w=load(waiting)
                    except ValueError:w={}
                    if w.get('group')==g['id'] and w.get('id') not in seen:
                        j=next(x for x in journeys if x['id']==w['id'])
                        self.capture_bindings(g,journeys)
                        skip=[]
                        if set(j.get('setupRefs',[]))-self.prepared.get(j['actorRef'],set()):
                            try:
                                from .fe_authenticated_recipes import prepare
                                setup=prepare(j,self.p,self.actors[j['actorRef']],self.out/'private/fixtures'/j['actorRef'])
                                self.actors[j['actorRef']].setdefault('fixtures',{}).update(setup['fixtures']);self.prepared.setdefault(j['actorRef'],set()).update(setup['fulfilledRefs']);self.rt.update_bindings()
                            except Exception as e:skip=['setup dependency: '+str(e)[:180]]
                        completed={x['id'] for x in journeys if (f:=self.rt.root/'browser'/g['id']/(x['id']+'.json')).exists() and load(f)['outcome'] in ('observed','assertion-mismatch')}
                        allowed={x['id'] for x in admission(self.p) if x['kind']=='campaign' and x['admitted']}
                        eligible=[c for c in self.p['campaigns'] if c['id'] in allowed and c['actorRef']==g['actorRef'] and set(c['journeyIds'])<=completed and not any(o.get('campaignId')==c['id'] for o in self.ops)]
                        if eligible and not skip:
                            if getattr(self,'before_native_hook',None):self.before_native_hook(self,g,j)
                            if g['actorRef'] not in self.native:self.native_auth(g['actorRef'],g['id'])
                            self.browser_continuity(g,j)
                            for c in eligible:self.attack(c)
                        if getattr(self,'qualification_hook',None):self.qualification_hook(self,g,j)
                        self.rt.mode(j['id'],actor=j['actorRef'],group=g['id'],phase=j['phase'])
                        ack=save(self.rt.root/'browser','ACK.pending',{'id':j['id'],'actorRef':j['actorRef'],'fixtureUpdates':self.actors[j['actorRef']].get('fixtures',{}),'skip':skip});ack.chmod(0o444);os.replace(ack,self.rt.root/'browser/ACK.json');seen.add(j['id'])
                self.cancel.wait(.1)
        except Exception:
            self.j.append('stop-request',{'action':'browser-session-group','group':g['id'],'replay':False});raise
        finally:
            if proc.poll() is None:
                # Stop the exact owned browser producer; never target/shared scanner.
                from .runtime import docker
                self.rt.check_owner(self.rt.names[4]);docker(['stop','--time','2',self.rt.names[4]]);proc.wait(timeout=8)
        path=self.rt.root/'browser'/g['id']/'GROUP.json'
        self.capture_bindings(g,journeys)
        if not path.exists():raise ValueError('browser group evidence absent')
        result=load(path);self.group_results.append(result);self.j.append('ack',{'action':'browser-session-group','group':g['id'],'journeyIds':result['journeyIds']})
        if set(result['journeyIds'])!={j['id'] for j in journeys} or any(load(self.rt.root/'browser'/g['id']/(j['id']+'.json'))['outcome']=='failed' for j in journeys):raise ValueError('browser group incomplete/failed; no dependent native dispatch')
        return result
    def browser_continuity(self,group,journey):
        label='continuity-'+str(time.time_ns());self.rt.mode(label,actor=journey['actorRef'],group=group['id'])
        f=save(self.rt.root/'browser','PROBE_REQUEST.pending',{'id':label,'group':group['id'],'actorRef':journey['actorRef']});f.chmod(0o444);os.replace(f,self.rt.root/'browser/PROBE_REQUEST.json')
        deadline=time.monotonic()+12
        while time.monotonic()<deadline:
            self.current();path=self.rt.root/'browser/PROBE_RESPONSE.json'
            if path.exists():
                response=load(path)
                if response['id']==label:
                    value=response['response'];identity=self.p['journeys']['auth']['identity'];actor=self.actors[journey['actorRef']]
                    if value.get('status')!=200 or str(pointer(value['body'],identity['subjectPointer']))!=str(actor['subject']) or identity.get('rolePointer') and pointer(value['body'],identity['rolePointer'])!=actor['role']:raise ValueError('browser continuity lost after native login; no attack')
                    save(self.out,'continuity/'+label+'.json',response);return
            self.cancel.wait(.1)
        raise TimeoutError('browser continuity did not ACK; no native dispatch')
    def native_auth(self,actor,group):
        self.rt.mode('native-auth-'+actor,actor=actor,group=group,slot='native',phase='login-pending')
        self.j.append('pending-start',{'action':'native-prepare','actorRef':actor,'retry':False})
        prepared=self.mcp.call('zap_auth_session_prepare',{'profileId':actor,'targetUrl':self.p['selection']['origin']});sid=field(prepared,'Session ID')
        if not sid:raise ValueError('native session handle absent')
        self.native[actor]={'sessionId':sid,'group':group,'prepared':prepared};self.native_validate(actor);save(self.out,'NATIVE_SESSIONS.json',self.native)
    def native_validate(self,actor):
        a=self.native[actor];value=self.mcp.call('zap_auth_session_validate',{'sessionId':a['sessionId']});a['validation']=value;a['validatedAt']=time.time()
        if field(value,'Valid')!='true':raise ValueError('native validation not confirmed')
        return value
    def attack(self,c):
        from .fe_authenticated_campaigns import materialize
        c=materialize(c,self.actors[c['actorRef']].get('fixtures',{}))
        self.materialized=getattr(self,'materialized',[])+[c];save(self.out,'MATERIALIZED_CAMPAIGNS.json',self.materialized)
        self.current();actor=c['actorRef'];group=self.native[actor]['group'];sid=self.native[actor]['sessionId'];label=c['id'];policy='fa-'+label
        self.rt.mode(label,actor=actor,group=group,slot='native',phase='authenticated')
        self.native_validate(actor)
        body=c.get('body',{});fixed={k:v for k,v in body.items() if k not in c['vectorFields']};query=c.get('query',{});fq={k:v for k,v in query.items() if k not in c['vectorFields']}
        self.rt.mode(label,actor=actor,group=group,slot='native',campaign=label,fixed=fixed,fixed_query=fq)
        for name,args in [('setOptionTargetParamsInjectable',{'Integer':1 if c['vector']=='query' else 2}),('setOptionTargetParamsEnabledRPC',{'Integer':4}),('addScanPolicy',{'scanPolicyName':policy,'attackStrength':'LOW','alertThreshold':'MEDIUM'}),('disableAllScanners',{'scanPolicyName':policy}),('enableScanners',{'scanPolicyName':policy,'ids':','.join(map(str,c['ruleIds']))})]:self.engine('ascan','action',name,args)
        save(self.out,'policies/'+label+'.json',self.engine('ascan','view','scanners',{'scanPolicyName':policy}))
        url=self.p['selection']['origin']+c['path']+('?' + urlencode(query) if query else '')
        if c['vector']=='json-body':
            # ZAP SiteNode can still point at a same-URL GET after UI reload. Bind the
            # actual reviewed UI exchange without sending the mutation again.
            from .fe_authenticated_semantics import request,sha
            history=self.engine('core','view','messages',{'baseurl':url,'start':0,'count':100})['messages'];records=[load(f) for f in self.rt.capture.glob('[0-9]*.json')];candidates=[]
            for message in history:
                wire=request(message,self.p['selection']['origin'])
                if not wire or wire['method']!=c['method'] or wire['url']!=url or wire['status'] not in (200,201):continue
                try:
                    if json.loads(wire['body'])!=body:continue
                except ValueError:continue
                if any(r.get('caseId') in c['journeyIds'] and r.get('actorRef')==actor and r.get('authSlot')=='browser' and r.get('forwarded') and r.get('url')==url and r.get('method')==c['method'] and r.get('responseBodySha256')==sha(wire['response'].encode()) and r.get('credentialFingerprint')==sha(wire['headers'].get('authorization','').encode()) for r in records):candidates.append(message)
            if not candidates:raise ValueError('reviewed UI mutation baseline missing; no seed replay')
            from .anonymous_runner import AnonymousRun
            AnonymousRun.bind_baseline(self,candidates[-1],label,expected_method=c['method'])
        args={'targetUrl':url,'recurse':'false','policy':policy,'authSessionId':sid,'method':c['method']}
        if body:args['postData']=json.dumps(body,separators=(',',':'))
        known={str(x['id']) for x in self.engine('ascan','view','scans')['scans']}
        self.j.append('pending-start',{'action':'native-active','campaignId':label,'actorRef':actor,'targetUrl':url,'method':c['method'],'knownNativeIds':sorted(known),'replay':False})
        try:text=self.mcp.call('zap_attack_start',args)
        except Exception:
            inventory=self.engine('ascan','view','scans')['scans'];new=[x for x in inventory if str(x['id']) not in known]
            save(self.out,'UNKNOWN_STARTS.json',{'campaignId':label,'knownNativeIds':sorted(known),'observedNewScans':new,'targetBindings':[],'replayed':False,'recovery':'stop/export only; target binding pending'})
            from .fe_authenticated_native_inventory import targets
            bound=targets(self,[x['id'] for x in new],label) if new else []
            eligible={t['id'] for t in bound if t['url']==url and t['method']==c['method']}
            reconciliation={'campaignId':label,'knownNativeIds':sorted(known),'observedNewScans':new,'targetBindings':bound,'replayed':False,'recovery':'stop/export only'}
            save(self.out,'UNKNOWN_STARTS.json',reconciliation);self.j.append('reconcile',reconciliation)
            for scan in new:
                if str(scan['id']) in eligible:self.engine('ascan','action','stop',{'scanId':str(scan['id'])})
            save(self.out,'UNKNOWN_START_RECONCILIATION.json',{'campaignId':label,'replayed':False,'inventory':self.engine('ascan','view','scans')['scans'],'statuses':{str(scan['id']):self.engine('ascan','view','status',{'scanId':str(scan['id'])}) for scan in new if str(scan['id']) in eligible}})
            raise
        op={'kind':'active','campaignId':label,'operationId':field(text,'Operation ID'),'start':text,'startedAt':time.time()};self.ops.append(op);self.j.append('ack',op)
        if not op['operationId']:raise ValueError('native start ACK missing; reconcile only')
        deadline=time.monotonic()+65;last=time.monotonic()
        while time.monotonic()<deadline:
            self.current();status=self.mcp.call('zap_attack_status',{'operationId':op['operationId']});op['lastStatus']=status
            if field(status,'Completed')=='yes':break
            if time.monotonic()-last>10:self.native_validate(actor);last=time.monotonic()
            self.cancel.wait(.4)
        self.mcp.call('zap_attack_stop',{'operationId':op['operationId']});op['finalStatus']=self.mcp.call('zap_attack_status',{'operationId':op['operationId']});op['endedAt']=time.time();self.j.append('terminal',op)
        if c.get('resultBindings'):
            rows=[load(f) for f in self.rt.capture.glob('[0-9]*.json')];rows=sorted((r for r in rows if r.get('campaignId')==label and r.get('forwarded') and r.get('status') in (200,201) and r.get('method')==c['method'] and r.get('url')==url),key=lambda r:r['sequence'])
            if not rows:raise ValueError('campaign mutation has no acknowledged result; reconcile only')
            messages=self.engine('core','view','messages',{'baseurl':url,'start':0,'count':60})['messages'];last=rows[-1]
            from .fe_authenticated_semantics import request,sha
            candidates=[m for raw in messages if (m:=request(raw,self.p['selection']['origin'])) and m['method']==c['method'] and sha(m['response'].encode())==last['responseBodySha256'] and sha(m['headers'].get('authorization','').encode())==last['credentialFingerprint']]
            if not candidates:raise ValueError('campaign result lacks native/credential join')
            for name,path in c['resultBindings'].items():self.actors[actor].setdefault('fixtures',{})[name]=pointer(json.loads(candidates[-1]['response']),path)
            self.rt.update_bindings()
    def export(self):
        passive=[]
        for i in range(100):
            text=self.mcp.call('zap_passive_scan_status',{});passive.append({'at':time.time(),'raw':text})
            if len(passive)>=2 and all(field(x['raw'],'Completed')=='yes' and field(x['raw'],'Records remaining')=='0' for x in passive[-2:]):break
            time.sleep(.5)
        else:raise TimeoutError('passive settle missing')
        save(self.out,'PASSIVE.json',passive)
        for fmt in ('json','html'):
            path=field(self.mcp.call('zap_report_generate',{'baseUrl':self.p['selection']['origin'],'format':fmt}),'Path');pages=[]
            def reader(path,offset,expected):
                args={'reportPath':path,'offset':offset,'maxChars':100000}
                if expected:args['expectedSha256']=expected
                page=json.loads(self.mcp.call('zap_report_read_chunk',args));pages.append({k:v for k,v in page.items() if k!='content'});return page
            data=read_report(reader,path,32*1024**2);save(self.out,'reports/native.'+fmt,data);save(self.out,'reports/'+fmt+'-readback.json',{'bytes':len(data),'sha256':__import__('hashlib').sha256(data).hexdigest(),'pages':pages})
        origin=self.p['selection']['origin'];count=int(self.engine('core','view','numberOfMessages',{'baseurl':origin})['numberOfMessages']);messages=[]
        while len(messages)<count:
            page=self.engine('core','view','messages',{'baseurl':origin,'start':0 if not messages else len(messages)+1,'count':1})['messages']
            if not page:raise ValueError('history incomplete')
            messages.extend(page)
        if len({str(x['id']) for x in messages})!=count or int(self.engine('core','view','numberOfMessages',{'baseurl':origin})['numberOfMessages'])!=count:raise ValueError('history duplication/drift')
        save(self.out,'messages.json',{'count':count,'messages':messages})
        alerts=[];n=int(self.engine('core','view','numberOfAlerts',{'baseurl':origin})['numberOfAlerts'])
        while len(alerts)<n:
            page=self.engine('core','view','alerts',{'baseurl':origin,'start':len(alerts),'count':100})['alerts']
            if not page:raise ValueError('alerts incomplete')
            alerts.extend(page)
        save(self.out,'alerts-native.json',{'count':n,'alerts':alerts})
    def execute(self,interrupt_after=None):
        ready=False;watcher=None;old={}
        try:
            for sig in (signal.SIGINT,signal.SIGTERM):old[sig]=signal.signal(sig,lambda *a:self.cancel.set())
            sample=self.rt.resource_sample();save(self.out,'PREFLIGHT.json',sample)
            growth=128*1024**2 if self.calibration else self.p['selection']['resourceCalibration']['observedGrowthBytes']
            if min(sample['hostFree'],sample['dockerFree'])<self.p['limits']['reserveBytes']+2*growth or sample['ramAvailable']<4*1024**3:raise ValueError('FE auth headroom insufficient')
            watcher=threading.Thread(target=self.monitor,daemon=True);watcher.start();self.rt.provision();ready=True;self.configure();self.rt.boundary();self.mcp=RecordedMCP(self.rt,self.out);save(self.out,'MCP_SCHEMA.json',self.mcp.initialize())
            contracts=self.mcp.contracts
            if not {'method','postData'}<=set(contracts['zap_attack_start']['properties']):raise ValueError('owned MCP has stale attack contract')
            save(self.out,'ADMISSION.json',admission(self.p))
            for i,g in enumerate(self.p['journeys']['sessionGroups']):
                if interrupt_after is not None and i>=interrupt_after:raise InterruptedError('qualification checkpoint')
                admitted={x['id'] for x in admission(self.p) if x['kind']=='journey' and x['admitted']}
                journeys=[]
                for journey in self.p['journeys']['journeys']:
                    if journey['sessionGroup']!=g['id'] or journey['id'] not in admitted or journey['actorRef'] not in self.actors:continue
                    if not set(journey['prerequisites'])<={j['id'] for j in journeys}:continue
                    journeys.append(journey)
                if not journeys or g['actorRef'] not in self.actors:continue
                self.group(g,journeys)
            self.result['executionStatus']='completed'
        except InterruptedError as e:self.result.update(executionStatus='interrupted',reason=str(e))
        except Exception as e:self.result.update(executionStatus='failed',errorType=type(e).__name__,reason=str(e)[:200])
        finally:
            if ready:(self.rt.config/'STOP').touch()
            if ready and self.mcp:
                for op in self.ops:
                    try:self.mcp.call('zap_attack_stop',{'operationId':op['operationId']})
                    except Exception as e:self.errors.append({'kind':'stop','errorType':type(e).__name__})
                try:self.export();self.result['evidenceStatus']='complete'
                except Exception as e:self.errors.append({'kind':'export','errorType':type(e).__name__,'reason':str(e)[:160]})
            self.done.set()
            if watcher:watcher.join(timeout=12)
            if ready:
                try:save(self.out,'RESOURCE_FINAL.json',self.rt.sample())
                except Exception:pass
            from .runtime import docker
            for name in self.rt.names:
                try:self.rt.check_owner(name);save(self.out,'runtime-logs/'+name+'.log',docker(['logs','--tail','500',name],timeout=5).encode())
                except Exception:pass
            try:self.rt.cleanup();self.result['cleanupStatus']='clean'
            except Exception as e:self.result.update(cleanupStatus='unconfirmed',cleanupError=type(e).__name__)
            if self.p['journeys']['recipe']=='finalsource-fe-auth/1.0' and self.result['executionStatus']=='completed' and self.result['evidenceStatus']=='complete' and not self.errors:
                try:
                    from .fe_authenticated_cleanup_finalsource import cleanup
                    cleanup(self.p,self.out,self.actors)
                except Exception as e:self.errors.append({'kind':'fixture-cleanup','errorType':type(e).__name__,'reason':str(e)[:160]})
            from .fe_authenticated_contract import pins
            end=pins();save(self.out,'IMPLEMENTATION_PINS_END.json',end)
            if self.p.get('implementationPins',end)!=end:self.errors.append({'kind':'implementation-drift'})
            if self.result['evidenceStatus']=='complete':self.result['securityVerdict']='requires-triage'
            if self.result['executionStatus']=='completed' and self.result['evidenceStatus']=='complete' and not self.errors:self.result['gateDecision']='review_required'
            from .product_scope import task_readback,apply_completion
            self.result=apply_completion(self.result,task_readback(self.p))
            save(self.out,'RUN.json',self.result);save(self.out,'OPERATIONS.json',self.ops);save(self.out,'ERRORS.json',self.errors);save(self.out,'RESOURCES.json',{'samples':self.samples,'calibrationRun':self.calibration});save(self.out,'GROUPS.json',self.group_results)
            save(self.out,'ACTOR_BINDINGS.json',{k:{**{n:a[n] for n in ('subject','role','provenance')},'fixtures':a.get('fixtures',{})} for k,a in self.actors.items()})
            rows=[load(f) for f in self.rt.capture.glob('[0-9]*.json')]
            save(self.out,'COUNTERS.json',{'brokerRequests':len(rows),'policyRequests':sum(r.get('method')!='CONNECT' for r in rows),'appArrivals':sum(r.get('forwarded') is True for r in rows),'unknownRequests':sum(r.get('transportState') in ('sent','response-headers','unknown') for r in rows),'campaignAppArrivals':{c['id']:sum(r.get('campaignId')==c['id'] and r.get('forwarded') is True and r.get('method')==c['method'] for r in rows) for c in self.p['campaigns']}})
            save(self.out,'CLEANUP_RETENTION.json',{'scanner':self.result['cleanupStatus'],'fixtures':{'status':'mixed-cleanup-and-retention','evidence':'FIXTURE_CLEANUP.json'} if (self.out/'FIXTURE_CLEANUP.json').exists() else {'status':'retained','reason':'control/interrupted/failed run; preserve exact ID ledgers; no unverified cleanup'},'unknownMutationReplay':False,'reviewerApproval':None})
            entries=[]
            for f in sorted(self.out.rglob('*')):
                if f.is_file():f.chmod(0o600);entries.append({'path':str(f.relative_to(self.out)),'bytes':f.stat().st_size,'sha256':digest(f)})
            save(self.out,'EVIDENCE_INDEX.json',{'schemaVersion':'fe-authenticated-evidence/1.0','runId':self.p['runId'],'planHash':self.hash,'result':self.result,'artifacts':entries});save(self.out,'EVIDENCE_INDEX.sha256',(digest(self.out/'EVIDENCE_INDEX.json')+'\n').encode())
            for sig,handler in old.items():signal.signal(sig,handler)
        return self.result
