"""FE research orchestration, native ZAP producer/report lifecycle, evidence and stop ledger."""
import hashlib,json,os,secrets,signal,subprocess,threading,time
from pathlib import Path
from urllib.parse import urlsplit
from .fe_anonymous_contract import validate_plan,canonical,digest,save,load,pins,admission
from .fe_anonymous_runtime import FERuntime
from .fe_anonymous_binding import inspect
from .fe_anonymous_controls import configure,browser_case
from .journal import Journal
from .anonymous_runner import RecordedMCP,AnonymousRun
from .transport import field
from .evidence import read_report

class FERun:
    def __init__(self,p,out):
        validate_plan(p,live=True);inspect(p['selection'])
        self.p=p;self.out=Path(out).resolve();self.out.mkdir(parents=True,mode=0o700,exist_ok=False);self.hash=canonical(p)
        save(self.out,'PLAN.json',p);self.j=Journal(self.out/'journal.jsonl',p['runId'],self.hash);self.rt=FERuntime(p,self.out,self.j)
        self.cancel=threading.Event();self.done=threading.Event();self.samples=[];self.ops=[];self.checks=[];self.errors=[];self.mcp=None;self.ei=0;self.started=time.monotonic();self.fixture_client=None;self.fixture_ledger=None;self.fixture_setup_attempted=False;self.fixture_cleanup={};self.fixture_recipe=None
        self.result={'executionStatus':'running','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block','taskCompletion':'partial'}
    def current(self):
        if self.cancel.is_set():raise InterruptedError('owned stop requested')
        if time.monotonic()-self.started>self.p['limits']['executionSeconds']:raise TimeoutError('execution deadline')
        if canonical(load(self.out/'PLAN.json'))!=self.hash:raise ValueError('plan file drift')
        validate_plan(self.p,live=True);inspect(self.p['selection'])
    def engine(self,c,k,n,args=None):
        self.ei+=1;prefix='engine/'+str(self.ei).zfill(5)+'-'+c+'-'+n
        save(self.out,prefix+'-request.json',{'component':c,'kind':k,'name':n,'arguments':args or {}})
        v=self.rt.engine(c,k,n,args or {});save(self.out,prefix+'-response.json',v);return v
    def monitor(self):
        count=0
        while not self.done.wait(2):
            at=time.monotonic();v=os.statvfs(self.out);s={'at':time.time(),'hostFree':v.f_bavail*v.f_frsize}
            try:
                if count%3==0 and self.rt.names[4] in self.rt.created:
                    s.update(self.rt.sample());validate_plan(self.p,live=True);inspect(self.p['selection'])
                s['artifactBytes']=sum(p.stat().st_size for p in self.out.rglob('*') if p.is_file())
                self.samples.append(s);count+=1;s['sampleSeconds']=time.monotonic()-at
                if min(s['hostFree'],s.get('dockerFree',s['hostFree']))<self.p['limits']['reserveBytes'] or s['artifactBytes']>self.p['limits']['artifactBytes']:raise ValueError('resource reserve/cap')
                if s.get('ramAvailable',2*1024**3)<1024**3:raise ValueError('RAM reserve')
                if any(load(f).get('unexpectedIdentityTransition') for f in self.rt.capture.glob('[0-9]*.json')):raise ValueError('unplanned identity transition')
            except Exception as e:
                self.errors.append({'kind':'resource','errorType':type(e).__name__,'reason':str(e)[:100]});self.cancel.set();(self.rt.config/'STOP').touch();return
    def configure(self):
        configure(self.rt)
        fresh={'sites':self.engine('core','view','sites'),'messages':self.engine('core','view','numberOfMessages'),'active':self.engine('ascan','view','scans')}
        if fresh['sites']!={'sites':[]} or int(fresh['messages']['numberOfMessages'])!=0 or fresh['active']!={'scans':[]}:raise ValueError('native session is not fresh')
        save(self.out,'FRESH_SESSION.json',fresh)
        for action,args in [('setOptionThreadPerHost',{'Integer':1}),('setOptionHostPerScan',{'Integer':1}),('setOptionMaxScanDurationInMins',{'Integer':2}),('setOptionTargetParamsInjectable',{'Integer':2}),('setOptionTargetParamsEnabledRPC',{'Integer':4}),('setOptionAddQueryParam',{'Boolean':'false'}),('setOptionInjectPluginIdInHeader',{'Boolean':'true'})]:self.engine('ascan','action',action,args)
        save(self.out,'SCANNER.json',{'version':self.engine('core','view','version'),'addons':self.engine('autoupdate','view','installedAddons'),'activeRules':self.engine('ascan','view','scanners'),'passiveRules':self.engine('pscan','view','scanners')})
    def crawl(self):
        self.current();self.rt.mode('client-discovery');self.j.append('pending-start',{'action':'client-crawl','retry':False})
        try:
            text=self.mcp.call('zap_crawl_start',{'targetUrl':self.p['selection']['origin']+'/','strategy':'client'})
        except Exception:
            self.j.append('reconcile',{'action':'client-crawl','retry':False,'inventory':self.engine('clientSpider','view','scanStatus',{'scanId':'0'})});raise
        op={'kind':'crawl','operationId':field(text,'Operation ID'),'startedAt':time.time(),'strategy':'client'};self.ops.append(op);self.j.append('ack',op)
        deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            self.current();status=self.mcp.call('zap_crawl_status',{'operationId':op['operationId']})
            if field(status,'Progress')=='100%':op['terminal']=True;break
            self.cancel.wait(1)
        else:
            self.mcp.call('zap_crawl_stop',{'operationId':op['operationId']});op['boundedStop']=True
        op['finalStatus']=self.mcp.call('zap_crawl_status',{'operationId':op['operationId']})
        op['deliveryProven']=any(load(f).get('caseId')=='client-discovery' and load(f).get('forwarded') for f in self.rt.capture.glob('[0-9]*.json'))
        browser_caps=[load(f) for f in sorted((self.rt.work/'client-driver').glob('session-*.json'))]
        save(self.out,'CLIENT_BROWSER_CAPABILITIES.json',browser_caps)
        if not browser_caps or any(r.get('status')!=200 or r.get('effectiveAcceptInsecureCerts') is not False for r in browser_caps):raise ValueError('native client browser TLS capability not verified')
        self.j.append('terminal',op)
        if not op['deliveryProven']:self.errors.append({'kind':'crawl','reason':'Client Spider produced no app traffic; scripted journeys remain separately evidenced'})
    def fixture_values(self):
        # Synthetic values are private, freshly generated per run, never from prior profiles.
        marker=self.p['runId']+'-'+secrets.token_hex(4)
        values={'email':marker+'@example.test','unknownEmail':marker+'-absent@example.test','activeEmail':marker+'-active@example.test','password':'Owned!'+secrets.token_urlsafe(18),'differentPassword':'Different!'+secrets.token_hex(6),'weakPassword':'x','serverInvalidEmail':marker+'@owned.c','marker':marker,'syntaxEmail':marker+'-syntax@example.test','boundaryEmail':marker+'-boundary@example.test','queryEmail':marker+'-query@example.test','quotedEmail':"o'brien-"+marker+'@example.test','longPassword':'P'*73}
        save(self.out,'private/fixture-values.json',values);return values
    def journey(self,j,fixtures):
        self.current();self.j.append('intent',{'action':'browser-journey','journeyId':j['id'],'profile':'new','replay':False})
        observed=browser_case(self.rt,j,fixtures);save(self.out,'journeys/'+j['id']+'.json',observed)
        records=[load(f) for f in sorted(self.rt.capture.glob('[0-9]*.json')) if load(f).get('caseId')==j['id']]
        network=[]
        for spec in j['network']:
            attempted=[r for r in records if r.get('method')==spec['method'] and urlsplit(r['url']).path==spec['path']]
            matches=[r for r in attempted if r.get('forwarded')]
            ok=not attempted if spec.get('absent') else bool(matches) and all(r['status'] in spec['statuses'] for r in matches)
            network.append({'expected':spec,'passed':ok,'sequences':[r['sequence'] for r in matches]})
        phase=observed.get('finalState',{});allowed={c for r in self.p['requestPolicies'] for c in r.get('anonymousCookies',[]) if r.get('cookieProvenance')};has_identity=bool(phase.get('storageKeys') or phase.get('sessionKeys') or set(phase.get('cookieNames',[]))-allowed)
        anonymous=(not has_identity or j.get('transition')) and not any(r.get('forwarded') and r.get('reason')!='app' for r in records)
        passed=observed['outcome']=='observed' and observed.get('profileClosed') is True and all(n['passed'] for n in network) and anonymous
        check={'journeyId':j['id'],'outcome':'pass' if passed else 'failed','uiOutcome':observed['outcome'],'network':network,'anonymousInvariant':anonymous,'phase':'terminal-identity-transition' if has_identity and j.get('transition') else 'anonymous','attempted':len(records),'forwarded':sum(bool(r.get('forwarded')) for r in records),'blocked':sum(not r.get('forwarded') for r in records),'uiRef':'journeys/'+j['id']+'.json'}
        from .fe_anonymous_analysis import transport_accounting
        check.update(transport_accounting(records))
        self.checks.append(check);self.j.append('ack',{'action':'browser-journey',**check});return check
    def attack(self,camp,fixtures):
        self.current();label=camp['id'];policy='fe-'+label
        self.engine('ascan','action','addScanPolicy',{'scanPolicyName':policy,'attackStrength':'LOW','alertThreshold':'MEDIUM'})
        self.engine('ascan','action','disableAllScanners',{'scanPolicyName':policy});self.engine('ascan','action','enableScanners',{'ids':','.join(map(str,camp['ruleIds'])),'scanPolicyName':policy})
        rules=self.engine('ascan','view','scanners',{'scanPolicyName':policy})['scanners'];save(self.out,'policies/'+label+'.json',rules)
        if {int(r['id']) for r in rules if str(r['enabled']).lower()=='true'}!=set(camp['ruleIds']):raise ValueError('native rule selection drift')
        body={k:fixtures[v] for k,v in camp['fixtureBody'].items()};fixed={k:v for k,v in body.items() if k not in camp['vectorFields']}
        self.rt.mode(label,campaign=label,fixed=fixed,baseline_hash=hashlib.sha256(json.dumps(body,separators=(',',':')).encode()).hexdigest())
        wire_body=json.dumps(body,separators=(',',':'));url=self.p['selection']['origin']+camp['path'];host=urlsplit(url).netloc
        wire=camp['method']+' '+url+' HTTP/1.1\r\nHost: '+host+'\r\nContent-Type: application/json\r\nContent-Length: '+str(len(wire_body.encode()))+'\r\nConnection: close\r\n\r\n'+wire_body
        self.j.append('pending-start',{'action':'native-baseline','campaignId':label,'replay':False})
        baseline=self.engine('core','action','sendRequest',{'request':wire,'followRedirects':'false'})['sendRequest']
        if len(baseline)!=1 or 'x-zpa-guard:' in baseline[0].get('responseHeader','').lower():raise ValueError('baseline guard/capture failed')
        save(self.out,'baselines/'+label+'.json',baseline[0]);AnonymousRun.bind_baseline(self,baseline[0],label)
        known={str(s['id']) for s in self.engine('ascan','view','scans')['scans']};self.j.append('pending-start',{'action':'native-active','campaignId':label,'knownIds':sorted(known),'replay':False})
        try:native=str(self.engine('ascan','action','scan',{'url':url,'recurse':'false','scanPolicyName':policy,'method':camp['method'],'postData':wire_body})['scan'])
        except Exception:
            found=[s for s in self.engine('ascan','view','scans')['scans'] if str(s['id']) not in known]
            if len(found)!=1:raise ValueError('unknown native start ACK; stop-only, no replay')
            native=str(found[0]['id']);self.j.append('reconcile',{'action':'native-active','nativeId':native,'replayed':False})
        op={'kind':'active','campaignId':label,'nativeId':native,'ruleIds':camp['ruleIds'],'vectorFields':camp['vectorFields'],'branch':camp['branch'],'terminal':False};self.ops.append(op);self.j.append('ack',op)
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            self.current();records=[load(f) for f in self.rt.capture.glob('[0-9]*.json')];delivered=[r for r in records if r.get('campaignId')==label and r.get('forwarded') and r.get('ruleId') and r.get('payloadChanged')]
            if len(delivered)>=camp['maxDelivered']:
                self.engine('ascan','action','stop',{'scanId':native});op['boundedStop']=True;break
            if int(self.engine('ascan','view','status',{'scanId':native})['status'])==100:op['terminal']=True;break
            self.cancel.wait(.3)
        else:self.engine('ascan','action','stop',{'scanId':native});op['deadlineStop']=True
        op['finalNativeStatus']=int(self.engine('ascan','view','status',{'scanId':native})['status']);op['terminal']=op['finalNativeStatus']==100
        delivered=[load(f) for f in self.rt.capture.glob('[0-9]*.json') if load(f).get('campaignId')==label and load(f).get('forwarded') and load(f).get('ruleId') and load(f).get('payloadChanged')]
        op['progress']=self.engine('ascan','view','scanProgress',{'scanId':native});op['deliveredByRule']={str(r):sum(str(x.get('ruleId'))==str(r) for x in delivered) for r in camp['ruleIds']};op['deliveryProven']=all(op['deliveredByRule'].values())
        self.j.append('terminal',op)
    def export(self):
        stable=0;deadline=time.monotonic()+60
        while time.monotonic()<deadline:
            text=self.mcp.call('zap_passive_scan_status',{});stable=stable+1 if field(text,'Completed')=='yes' and field(text,'Records remaining')=='0' else 0
            if stable>=2:break
            self.cancel.wait(.5) if not self.cancel.is_set() else time.sleep(.5)
        else:raise TimeoutError('passive not settled')
        save(self.out,'PASSIVE.json',{'settled':True,'stableSamples':stable})
        for fmt in ('json','html'):
            path=field(self.mcp.call('zap_report_generate',{'baseUrl':self.p['selection']['origin'],'format':fmt,'theme':'light'}),'Path');pages=[]
            def reader(path,offset,sha):
                args={'reportPath':path,'offset':offset,'maxChars':100000}
                if sha:args['expectedSha256']=sha
                page=json.loads(self.mcp.call('zap_report_read_chunk',args));pages.append({k:v for k,v in page.items() if k!='content'});return page
            data=read_report(reader,path,32*1024**2);save(self.out,'reports/native.'+fmt,data);save(self.out,'reports/'+fmt+'-readback.json',{'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest(),'pages':pages,'endOfFile':True})
        # All producers are stopped before export. Refresh final counters after terminal/passive settle.
        for op in self.ops:
            if op['kind']=='active':
                final=[load(f) for f in self.rt.capture.glob('[0-9]*.json') if load(f).get('campaignId')==op['campaignId'] and load(f).get('forwarded') and load(f).get('ruleId') and load(f).get('payloadChanged')]
                op['deliveredByRule']={str(rule):sum(str(r.get('ruleId'))==str(rule) for r in final) for rule in op['ruleIds']}
                op['deliveryProven']=all(op['deliveredByRule'].values())
        origin=self.p['selection']['origin'];count=int(self.engine('core','view','numberOfMessages',{'baseurl':origin})['numberOfMessages']);messages=[];cursor=0
        while len(messages)<count:
            page=self.engine('core','view','messages',{'baseurl':origin,'start':cursor,'count':1})['messages']
            if not page:raise ValueError('native history incomplete')
            messages.extend(page);cursor=len(messages)+1
        ids=[m['id'] for m in messages]
        if len(ids)!=count or len(set(ids))!=count or int(self.engine('core','view','numberOfMessages',{'baseurl':origin})['numberOfMessages'])!=count:raise ValueError('native history duplication/count/drift')
        save(self.out,'messages.json',{'count':count,'messages':messages})
        alerts=[];n=int(self.engine('core','view','numberOfAlerts',{'baseurl':origin})['numberOfAlerts'])
        while len(alerts)<n:
            page=self.engine('core','view','alerts',{'baseurl':origin,'start':len(alerts),'count':100})['alerts']
            if not page:raise ValueError('native alert pagination incomplete')
            alerts.extend(page)
        save(self.out,'alerts-native.json',{'count':n,'alerts':alerts})
        from .fe_anonymous_analysis import correlate,response_policies
        records=[load(f) for f in sorted(self.rt.capture.glob('[0-9]*.json'))]
        save(self.out,'TRAFFIC_CORRELATION.json',correlate(self.p,records,messages))
        save(self.out,'RESPONSE_POLICY_OBSERVATIONS.json',response_policies(messages))
        # Browser process close can race the broker's final denied CONNECT record.
        # Re-derive the sealed snapshot only after producers have stopped and history settled.
        from .fe_anonymous_analysis import transport_accounting
        for check in self.checks:
            if check['outcome']=='not-run':continue
            relevant=[r for r in records if r.get('caseId')==check['journeyId']]
            check.update(transport_accounting(relevant))
            for network in check['network']:
                expected=network['expected']
                attempted=[r for r in relevant if r['method']==expected['method'] and urlsplit(r['url']).path==expected['path']]
                responses=[r for r in attempted if r.get('forwarded')]
                network.update(passed=not attempted if expected.get('absent') else bool(responses) and all(r['status'] in expected['statuses'] for r in responses),sequences=[r['sequence'] for r in responses])
            if check['unknown'] or not all(n['passed'] for n in check['network']):check['outcome']='failed'
        save(self.out,'FINAL_JOURNEY_ACCOUNTING.json',{'derivedAfterProducerStop':True,'checks':self.checks})
        from .fe_anonymous_analysis import mutation_obligations,active_delivery
        selected={o.get('campaignId') for o in self.ops if o['kind']=='active'}
        active_plan=dict(self.p,campaigns=[c for c in self.p['campaigns'] if c['id'] in selected])
        delivery=active_delivery(active_plan,records,messages,{c['id']:load(self.out/('baselines/'+c['id']+'.json')) for c in active_plan['campaigns']})
        for op in self.ops:
            if op['kind']=='active':op.update(delivery[op['campaignId']])
        from .fe_anonymous_recipes import select
        try:recipe=select(self.p['journeys']['recipe'])
        except ValueError:recipe=None
        if recipe and hasattr(recipe,'public_retention'):
            marker=load(self.out/'private/fixture-values.json')['marker']
            save(self.out,'private/PUBLIC_FIXTURE_RETENTION.json',recipe.public_retention(messages,marker))
        save(self.out,'UNKNOWN_MUTATIONS.json',{'obligations':mutation_obligations(records),'mutationReplay':False})
        from .fe_anonymous_semantics import check
        save(self.out,'SEMANTIC_DERIVATION.json',check(self.out,self.p,records,messages,self.ops,require_all=False))
    def stop(self):
        (self.rt.config/'STOP').touch();self.j.append('stop-request',{'at':time.time(),'noReplay':True})
        for op in self.ops:
            try:
                if op['kind']=='crawl':self.mcp.call('zap_crawl_stop',{'operationId':op['operationId']})
                elif op['kind']=='active':self.engine('ascan','action','stop',{'scanId':op['nativeId']})
            except Exception as e:self.errors.append({'kind':'stop','errorType':type(e).__name__})
        self.j.append('reconcile',{'scans':self.engine('ascan','view','scans'),'replayedMutations':False})
    def execute(self,interrupt_after=None):
        ready=False;watcher=None;old={}
        try:
            for sig in (signal.SIGINT,signal.SIGTERM):old[sig]=signal.signal(sig,lambda *a:self.cancel.set())
            sample=self.rt.resource_sample();save(self.out,'PREFLIGHT.json',sample)
            calibration=self.p['selection']['resourceCalibration'];required=self.p['limits']['reserveBytes']+2*calibration['observedGrowthBytes']
            if min(sample['hostFree'],sample['dockerFree'])<required or sample['ramAvailable']<calibration['requiredRamBytes']:raise ValueError('calibrated FE headroom unavailable')
            watcher=threading.Thread(target=self.monitor,daemon=True);watcher.start();self.rt.provision();ready=True;self.configure();self.rt.boundary()
            self.mcp=RecordedMCP(self.rt,self.out);save(self.out,'MCP_SCHEMA.json',self.mcp.initialize());fixtures=self.fixture_values();branches=admission(self.p);save(self.out,'ADMISSION.json',branches)
            # Journeys first: crawler never performs unreviewed form success/identity transition.
            for i,j in enumerate(self.p['journeys']['journeys']):
                if j['id'] not in self.p['journeyIds']:continue
                permit=next(r for r in branches if r['kind']=='journey' and r['id']==j['id'])
                if not permit['admitted']:
                    self.checks.append({'journeyId':j['id'],'outcome':'not-run','dependencies':permit['missingPermissions']});continue
                if interrupt_after is not None and i>=interrupt_after:raise InterruptedError('qualification checkpoint')
                unmet=[p for p in j.get('prerequisites',[]) if not any(c['journeyId']==p and c['outcome']=='pass' for c in self.checks)]
                if unmet:self.checks.append({'journeyId':j['id'],'outcome':'not-run','dependencies':unmet});continue
                if j.get('setupHook'):
                    if not self.fixture_setup_attempted:
                        self.fixture_setup_attempted=True
                        try:
                            from .fe_anonymous_recipes import select
                            self.fixture_recipe=select(self.p['journeys']['recipe'])
                            from .fe_anonymous_fixtures import DirectFixtures
                            self.fixture_client=DirectFixtures(self.p['selection'],self.out)
                            def record(ledger):self.fixture_ledger=ledger;save(self.out,'private/FIXTURE_LEDGER.json',ledger)
                            msgs=[]
                            for path in self.fixture_recipe.fixture_evidence_paths(j['setupHook']):
                                if not path.startswith('/') or path.startswith('//'):raise ValueError('fixture evidence outside binding')
                                msgs.extend(self.engine('core','view','messages',{'baseurl':self.p['selection']['origin']+path,'start':0,'count':10})['messages'])
                            values,self.fixture_ledger=self.fixture_recipe.prepare_fixtures(j['setupHook'],msgs,self.fixture_client.send,fixtures['marker'],record);fixtures.update(values)
                        except Exception as e:self.errors.append({'kind':'fixture','errorType':type(e).__name__,'reason':str(e)[:150]})
                    if not all(k in fixtures for k in j.get('fixtureRefs',[])):
                        self.checks.append({'journeyId':j['id'],'outcome':'not-run','dependencies':['direct owned fixture unresolved; no replay']});continue
                self.journey(j,fixtures)
            self.crawl()
            for c in self.p['campaigns']:
                permit=next(r for r in branches if r['kind']=='campaign' and r['id']==c['id'])
                if permit['admitted']:self.attack(c,fixtures)
                else:self.errors.append({'kind':'admission','campaignId':c['id'],'missingPermissions':permit['missingPermissions']})
            self.result['executionStatus']='completed'
        except InterruptedError as e:self.result.update(executionStatus='interrupted',reason=str(e))
        except Exception as e:self.result.update(executionStatus='failed',errorType=type(e).__name__,reason=str(e)[:250])
        finally:
            if ready and self.mcp:
                try:self.stop();self.export();self.result['evidenceStatus']='complete'
                except Exception as e:self.errors.append({'kind':'evidence','errorType':type(e).__name__,'reason':str(e)[:180]})
            self.done.set()
            if watcher:watcher.join(timeout=12)
            for name in self.rt.names:
                try:
                    self.rt.check_owner(name)
                    from .runtime import docker
                    save(self.out,'runtime-logs/'+name+'.log',docker(['logs','--tail','600',name],timeout=5).encode())
                except Exception:pass
            try:self.rt.cleanup();self.result['cleanupStatus']='clean'
            except Exception as e:self.result.update(cleanupStatus='unconfirmed',cleanupError=type(e).__name__)
            try:inspect(self.p['selection']);self.result['targetBindingUnchanged']=True
            except Exception:self.result['targetBindingUnchanged']=False
            gaps=[o for o in self.p['journeys']['responsibilities'] if o['disposition']=='gap']
            required={j['id'] for j in self.p['journeys']['journeys']}
            observed={c['journeyId'] for c in self.checks if c['outcome']=='pass'}
            active={o['campaignId'] for o in self.ops if o['kind']=='active' and o.get('deliveryProven')}
            if (self.result['executionStatus']=='completed' and self.result['evidenceStatus']=='complete'
                and self.result['cleanupStatus']=='clean' and self.result.get('targetBindingUnchanged')
                and not (load(self.out/'UNKNOWN_MUTATIONS.json')['obligations'] if (self.out/'UNKNOWN_MUTATIONS.json').exists() else True)
                and observed==required and not gaps and not self.cancel.is_set() and not self.errors and all(o.get('deliveryProven',True) and o.get('terminal') is True for o in self.ops)
                and active=={c['id'] for c in self.p['journeys']['campaigns']}):self.result['workloadCompletion']='complete'
            if self.result['evidenceStatus']=='complete':self.result['securityVerdict']='requires-triage'
            if self.result['executionStatus']=='completed' and self.result['evidenceStatus']=='complete' and self.result['cleanupStatus']=='clean':self.result['gateDecision']='review_required'
            if self.fixture_ledger and self.fixture_client:
                try:
                    self.fixture_cleanup=self.fixture_recipe.cleanup_fixtures(self.fixture_ledger,self.fixture_client.send)
                except Exception as e:self.fixture_cleanup={'status':'unconfirmed','errorType':type(e).__name__};self.result['taskCompletion']='partial'
            from .product_scope import task_readback,apply_completion
            self.result=apply_completion(self.result,task_readback(self.p))
            save(self.out,'RUN.json',self.result);save(self.out,'CHECKS.json',self.checks);save(self.out,'OPERATIONS.json',self.ops);save(self.out,'ERRORS.json',self.errors);save(self.out,'RESOURCES.json',{'samples':self.samples,'calibration':self.p['selection']['resourceCalibration']})
            save(self.out,'CLEANUP_RETENTION.json',{'scanner':self.result['cleanupStatus'],'profiles':'exact fresh owned profiles disposed after closed-state inventory, UI/network capture; PROFILE_DISPOSAL.json retained','publicFixtures':'acknowledged created identity retained; no user DELETE API','mutationReplay':False,'unknownMutationObligations':load(self.out/'UNKNOWN_MUTATIONS.json')['obligations'] if (self.out/'UNKNOWN_MUTATIONS.json').exists() else 'capture incomplete; retain intents and reconcile without replay','publicFixtureLedger':'private/PUBLIC_FIXTURE_RETENTION.json','directFixtureCleanup':self.fixture_cleanup})
            entries=[]
            for p in sorted(self.out.rglob('*')):
                if p.is_file():p.chmod(0o600);entries.append({'path':str(p.relative_to(self.out)),'bytes':p.stat().st_size,'sha256':digest(p)})
            m={'schemaVersion':'fe-anonymous-evidence/2.0','runId':self.p['runId'],'planHash':self.hash,'result':self.result,'artifacts':entries};save(self.out,'EVIDENCE_INDEX.json',m);save(self.out,'EVIDENCE_INDEX.sha256',(digest(self.out/'EVIDENCE_INDEX.json')+'\n').encode())
            for sig,handler in old.items():signal.signal(sig,handler)
        return self.result
