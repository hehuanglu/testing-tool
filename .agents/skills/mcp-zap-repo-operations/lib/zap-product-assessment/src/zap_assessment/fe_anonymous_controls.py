"""Executable FE transport controls, exact owned target/runtime resources only."""
import hashlib,json,os,ssl,subprocess,time,threading
from pathlib import Path
from .runtime import docker
from .journal import Journal
from .anonymous_runner import RecordedMCP
from .transport import field
from .evidence import read_report
from .fe_anonymous_runtime import FERuntime,ROOT
from .fe_anonymous_contract import save,digest,canonical,load


def configure(rt):
    rt.engine('network','action','setHttpProxy',{'host':'127.0.0.1','port':18888})
    rt.engine('network','action','setHttpProxyAuthEnabled',{'enabled':'false'})
    for r in rt.engine('network','view','getHttpProxyExclusions',{}).get('getHttpProxyExclusions',[]):rt.engine('network','action','setHttpProxyExclusionEnabled',{'host':r['host'],'enabled':'false'})
    rt.engine('network','action','setHttpProxyEnabled',{'enabled':'true'})
    rt.engine('core','action','setOptionHttpStateEnabled',{'Boolean':'false'})
    proxy=rt.engine('network','view','getHttpProxy',{});enabled=rt.engine('network','view','isHttpProxyEnabled',{})
    if proxy['getHttpProxy']['host']!='127.0.0.1' or str(proxy['getHttpProxy']['port'])!='18888' or str(enabled['isHttpProxyEnabled']).lower()!='true':raise ValueError('upstream proxy readback failed')
    save(rt.root,'PROXY.json',{'proxy':proxy,'enabled':enabled,'httpState':rt.engine('core','view','optionHttpStateEnabled',{})})


def browser_case(rt,journey,fixtures=None):
    rt.mode(journey['id'],transition=journey.get('transition',False))
    allowed=sorted({c for r in rt.p.get('requestPolicies',[]) for c in r.get('anonymousCookies',[]) if r.get('cookieProvenance')})
    file=save(rt.root/'browser','job.pending',{'origin':rt.p['selection']['origin'],'journey':journey,'fixtures':fixtures or {},'anonymousCookieNames':allowed});file.chmod(0o444);os.replace(file,rt.root/'browser'/'job.json')
    r=subprocess.run(['docker','exec','--user','1004:1004',rt.names[4],'python3','-m','zap_assessment.fe_anonymous_browser','/browser/job.json'],capture_output=True,timeout=160)
    save(rt.root,'browser/'+journey['id']+'-worker.log',r.stdout+r.stderr)
    path=rt.root/'browser'/journey['id']/'RESULT.json'
    if not path.exists():raise ValueError('browser capture missing; '+r.stdout.decode(errors='replace')[-300:])
    return load(path)


def transport_control(output,jar,jar_pin,variant='vulnerable'):
    out=Path(output).resolve();out.mkdir(parents=True,mode=0o700,exist_ok=False)
    from .fe_anonymous_contract import pins
    save(out,'IMPLEMENTATION_PINS.json',pins())
    rid='fe-proof-'+str(time.time_ns())[-10:];net=rid+'-targets';target=rid+'-target';config=out/'target-config';config.mkdir(mode=0o755);arrivals=out/'arrivals';arrivals.mkdir(mode=0o777);arrivals.chmod(0o777)
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN=control.test','-addext','subjectAltName=DNS:control.test','-keyout',str(config/'target.key'),'-out',str(config/'target.crt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for f in config.iterdir():f.chmod(0o444)
    pin=load(ROOT/'profiles/runtime-baseline.json');jp=load(jar_pin)
    if digest(jar)!=jp['jarSha256']:raise ValueError('JAR mismatch')
    for row in jp['sourceFiles']:
        if digest(row['path'])!=row['sha256']:raise ValueError('scanner source mismatch')
    docker(['network','create','--label','zpa.controlOwner='+rid,net]);rt=None
    result={'gate':'failed'};samples=[];done=threading.Event();breach=[]
    def monitor():
        while not done.wait(1):
            v=os.statvfs(out);free=v.f_bavail*v.f_frsize;samples.append({'at':time.time(),'hostFree':free})
            if free<2*1024**3:
                breach.append('host reserve');
                if rt:
                    (rt.config/'STOP').touch()
                    try:rt.terminate()
                    except Exception:pass
                return
    watcher=threading.Thread(target=monitor,daemon=True);watcher.start()
    try:
        docker(['run','-d','--name',target,'--label','zpa.controlOwner='+rid,'--network',net,'--user','1005:1005','--cap-drop','ALL','--memory','96m','-v',str(Path(__file__).with_name('fe_anonymous_control_fixture.py'))+':/app.py:ro','-v',str(Path(__file__).with_name('anonymous_control_fixture.py'))+':/legacy_control.py:ro','-v',str(config)+':/config:ro','-v',str(arrivals)+':/evidence',pin['boundary'],'python','/app.py',variant])
        v=json.loads(docker(['inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"started":{{json .State.StartedAt}},"networks":{{json .NetworkSettings.Networks}}}',target]));n=v['networks'][net]
        cert=config/'target.crt';sel={'origin':'https://control.test:9443','productLocation':str(out),'environment':rid,'targetPort':8443,'binding':{'containerId':v['id'],'imageId':v['image'],'startedAt':v['started'],'networkId':n['NetworkID'],'address':n['IPAddress']},'composeFiles':[],'configPins':[],
          'certificate':{'path':str(cert),'sha256':digest(cert),'derSha256':hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()},'jar':{'path':str(Path(jar).resolve()),'sha256':digest(jar)},'scannerSourcePins':jp['sourceFiles'],'images':{'zap':pin['zap'],'browser':pin['zap'],'mcp':'mcp-zap-server:dev'}}
        p={'runId':rid,'selection':sel,'requestPolicies':[{'method':'GET','pathRegex':'/(?:|app.js|data|public|client.mjs|lookup|catalog|redirect)','queryKeys':['q']},{'method':'POST','pathRegex':'/query','jsonFields':['input']}],'limits':{'maxRequests':400,'maxBodyBytes':2*1024**2,'requestsPerSecond':2,'reserveBytes':2*1024**3,'artifactBytes':128*1024**2}}
        save(out,'PLAN.json',p);rt=FERuntime(p,out,Journal(out/'journal.jsonl',rid,canonical(p)))
        sample=rt.resource_sample();save(out,'PREFLIGHT.json',sample)
        if min(sample['hostFree'],sample['dockerFree'])<2*1024**3+2*128*1024**2:raise ValueError('FE control disk headroom')
        if sample['ramAvailable']<4*1024**3:raise ValueError('FE control RAM headroom')
        rt.provision();configure(rt);rt.boundary();m=RecordedMCP(rt,out);save(out,'MCP_SCHEMA.json',m.initialize())
        j={'id':'tls-render','branch':'public','steps':[{'action':'navigate','path':'/public','predicate':{'kind':'text','selector':'#result','value':'deferred-verified'}},{'action':'fill','selector':'#term','value':'owned nonce'},{'action':'submit','selector':'#send'}],
           'expected':[{'kind':'text','selector':'#route','value':'TLS control'},{'kind':'text','selector':'#echo','value':'owned nonce'}],'network':[{'method':'GET','path':'/data','statuses':[200]}]}
        if variant=='fixed':
            j['id']='catalog-search';j['steps'][0]['path']='/catalog';j['steps'][0]['predicate']['selector']='#loaded';j['steps'][1]['selector']='input[name=search]';j['steps'][2]['selector']='#go';j['expected'][0]['selector']='#catalog-heading';j['expected'][1]['selector']='#answer';j['network'][0]['path']='/lookup'
        observed=browser_case(rt,j);save(out,'CONTROL_BROWSER.json',observed)
        if breach:raise ValueError('resource reserve breached')
        if observed['outcome']!='observed':raise ValueError('browser control failed: '+str(observed.get('errorCode')))
        messages=rt.engine('core','view','messages',{'baseurl':sel['origin'],'start':0,'count':100})['messages'];save(out,'CONTROL_MESSAGES.json',messages)
        records=[load(f) for f in sorted(rt.capture.glob('*.json'))]
        arrival=[json.loads(x) for x in (arrivals/'arrivals.jsonl').read_text().splitlines()]
        for path in (('/catalog','/client.mjs','/lookup') if variant=='fixed' else ('/public','/app.js','/data')):
            if not any(path in r['requestHeader'].splitlines()[0] for r in messages) or not any(urlsplit_path(r['url'])==path and r['forwarded'] for r in records) or not any(r['path']==path for r in arrival):raise ValueError('browser/ZAP/arrival correlation missing '+path)
        # Native reflected-XSS control, delivered through the same verified TLS broker.
        rt.mode('native-control',campaign='native-control')
        for action,args in [('setOptionTargetParamsInjectable',{'Integer':1}),('setOptionAddQueryParam',{'Boolean':'false'}),('setOptionInjectPluginIdInHeader',{'Boolean':'true'}),('setOptionThreadPerHost',{'Integer':1}),('setOptionMaxScanDurationInMins',{'Integer':1}),('addScanPolicy',{'scanPolicyName':'fe-control','attackStrength':'LOW','alertThreshold':'MEDIUM'}),('disableAllScanners',{'scanPolicyName':'fe-control'}),('enableScanners',{'scanPolicyName':'fe-control','ids':'40012'})]:rt.engine('ascan','action',action,args)
        url=sel['origin']+('/catalog' if variant=='fixed' else '/public')+'?q=owned-control'
        rt.engine('core','action','sendRequest',{'request':'GET '+url+' HTTP/1.1\r\nHost: control.test:9443\r\nConnection: close\r\n\r\n','followRedirects':'false'})
        op=field(m.call('zap_attack_start',{'targetUrl':url,'recurse':'false','policy':'fe-control'}),'Operation ID');deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            status=m.call('zap_attack_status',{'operationId':op})
            if field(status,'Completed')=='yes':break
            if breach:raise ValueError('resource reserve during native control')
            time.sleep(1)
        else:
            m.call('zap_attack_stop',{'operationId':op});raise TimeoutError('native control deadline')
        alertdoc=rt.engine('core','view','alerts',{'baseurl':sel['origin'],'start':0,'count':1000});save(out,'NATIVE_ALERTS.json',alertdoc)
        expected=any(str(a['pluginId'])=='40012' for a in alertdoc['alerts'])
        if expected!=(variant=='vulnerable'):raise ValueError('native vulnerable/fixed detection control mismatch')
        delivered=[load(f) for f in rt.capture.glob('[0-9]*.json') if load(f).get('forwarded') and str(load(f).get('ruleId'))=='40012']
        if not delivered:raise ValueError('native rule payload not delivered')
        rt.mode('native-json-control',campaign='native-json-control')
        for action,args in [('setOptionTargetParamsInjectable',{'Integer':2}),('setOptionTargetParamsEnabledRPC',{'Integer':4}),('addScanPolicy',{'scanPolicyName':'fe-json-control','attackStrength':'LOW','alertThreshold':'MEDIUM'}),('disableAllScanners',{'scanPolicyName':'fe-json-control'}),('enableScanners',{'scanPolicyName':'fe-json-control','ids':'40018'})]:rt.engine('ascan','action',action,args)
        url=sel['origin']+'/query';body='{"input":"marker"}'
        seed=rt.engine('core','action','sendRequest',{'request':'POST '+url+' HTTP/1.1\r\nHost: control.test:9443\r\nContent-Type: application/json\r\nContent-Length: '+str(len(body))+'\r\nConnection: close\r\n\r\n'+body,'followRedirects':'false'})['sendRequest'][0]
        from types import SimpleNamespace
        from .anonymous_runner import AnonymousRun
        adapter=SimpleNamespace(rt=rt,out=out,j=rt.journal,engine=lambda c,k,n,args=None:rt.engine(c,k,n,args or {}))
        AnonymousRun.bind_baseline(adapter,seed,'fe-json-control')
        sid=str(rt.engine('ascan','action','scan',{'url':url,'recurse':'false','scanPolicyName':'fe-json-control','method':'POST','postData':body})['scan']);deadline=time.monotonic()+100
        while time.monotonic()<deadline:
            if int(rt.engine('ascan','view','status',{'scanId':sid})['status'])==100:break
            if breach:raise ValueError('resource reserve during JSON control')
            time.sleep(1)
        else:rt.engine('ascan','action','stop',{'scanId':sid});raise TimeoutError('JSON control deadline')
        alertdoc=rt.engine('core','view','alerts',{'baseurl':sel['origin'],'start':0,'count':1000});save(out,'NATIVE_ALERTS_JSON_CONTROL.json',alertdoc)
        detected=any(str(a['pluginId'])=='40018' for a in alertdoc['alerts'])
        if detected!=(variant=='vulnerable'):raise ValueError('native JSON vulnerable/fixed detection mismatch')
        json_delivered=[load(f) for f in rt.capture.glob('[0-9]*.json') if load(f).get('forwarded') and str(load(f).get('ruleId'))=='40018']
        if not json_delivered:raise ValueError('native JSON rule not delivered')
        save(out,'NATIVE_JSON_CONTROL.json',{'nativeScanId':sid,'terminal':True,'ruleId':'40018','vector':'scalar-json','variant':variant,'detection':detected,'delivered':len(json_delivered)})
        arrival=[json.loads(x) for x in (arrivals/'arrivals.jsonl').read_text().splitlines()]
        for fmt in ('json','html'):
            path=field(m.call('zap_report_generate',{'baseUrl':sel['origin'],'format':fmt}),'Path');pages=[]
            def reader(path,offset,sha):
                args={'reportPath':path,'offset':offset,'maxChars':100000}
                if sha:args['expectedSha256']=sha
                page=json.loads(m.call('zap_report_read_chunk',args));pages.append({k:v for k,v in page.items() if k!='content'});return page
            blob=read_report(reader,path,32*1024**2);save(out,'reports/native.'+fmt,blob);save(out,'reports/'+fmt+'-readback.json',{'bytes':len(blob),'sha256':hashlib.sha256(blob).hexdigest(),'pages':pages,'endOfFile':True})
        save(out,'NATIVE_CONTROL.json',{'ruleId':'40012','operationId':op,'terminal':True,'variant':variant,'nativeDetection':expected,'delivered':len(delivered)})
        # Actual browser redirect and HTTP/protocol guards, before the identity latch.
        before_redirect=len(arrival)
        redirect=browser_case(rt,{'id':'redirect-denial','branch':'negative-control','steps':[{'action':'navigate','path':'/redirect'}],'expected':[{'kind':'exists','selector':'#never-outside-scope'}],'network':[]})
        denied_redirect=[load(f) for f in rt.capture.glob('[0-9]*.json') if load(f).get('caseId')=='redirect-denial' and load(f).get('reason')=='connect-origin' and load(f).get('url')=='owned-denied.invalid:443']
        arrival=[json.loads(x) for x in (arrivals/'arrivals.jsonl').read_text().splitlines()]
        if redirect['outcome']!='failed' or not denied_redirect or len(arrival)!=before_redirect+1 or arrival[-1]['path']!='/redirect':raise ValueError('browser redirect guard control')
        save(out,'REDIRECT_CONTROL.json',{'outsideConnectDenied':True,'outsideAppArrival':False,'browserOutcome':redirect['outcome'],'app302ArrivalCount':1})
        for label,url,extra in [('downgrade','http://control.test:9443/public',''),('websocket',sel['origin']+'/public','Upgrade: websocket\r\n'),('query-identity',sel['origin']+'/public?token=owned-control','')]:
            rt.mode(label);before=len(arrival)
            reply=rt.engine('core','action','sendRequest',{'request':'GET '+url+' HTTP/1.1\r\nHost: control.test:9443\r\n'+extra+'Connection: close\r\n\r\n','followRedirects':'false'})['sendRequest'][0]
            if ' 403 ' not in reply['responseHeader'] or len((arrivals/'arrivals.jsonl').read_text().splitlines())!=before:raise ValueError(label+' guard control')
            save(out,label+'-CONTROL.json',{'appArrival':False,'guardStatus':403})
        # Actual anonymous guard rejection and management authentication control.
        before=len(arrival)
        url=sel['origin']+'/public'
        denied=rt.engine('core','action','sendRequest',{'request':'GET '+url+' HTTP/1.1\r\nHost: control.test:9443\r\nAuthorization: Bearer owned-control\r\nConnection: close\r\n\r\n','followRedirects':'false'})
        if ' 403 ' not in denied['sendRequest'][0]['responseHeader']:raise ValueError('credential guard control')
        if len((arrivals/'arrivals.jsonl').read_text().splitlines())!=before:raise ValueError('credential reached app')
        # New phase after deliberately latching the anonymous outside-transition control.
        # Native controls use a new broker policy only in a fresh runtime, so no reset here.
        save(out,'NEGATIVE_CONTROLS.json',{'credentialNotForwarded':True,'arrivalBefore':before,'arrivalAfter':before,'latchTerminal':True})
        code="import http.client,json\ntry:\n c=http.client.HTTPConnection('127.0.0.1',8090,timeout=2);c.request('GET','/JSON/core/view/version/');r=c.getresponse();print(json.dumps({'status':r.status}));r.read();c.close()\nexcept (http.client.RemoteDisconnected,ConnectionResetError,TimeoutError) as e:print(json.dumps({'status':None,'rejectionType':type(e).__name__}))"
        status=json.loads(docker(['exec','--user','1004:1004',rt.anchor,'python','-c',code]))
        if status['status'] not in (400,401,403) and not (status['status'] is None and status.get('rejectionType') in ('RemoteDisconnected','ConnectionResetError','TimeoutError')):raise ValueError('browser can access ZAP management without key')
        save(out,'MANAGEMENT_CONTROL.json',status)
        save(out,'RESOURCE_OBSERVED.json',rt.sample())
        result={'gate':'transport-boundary-pass','browserTLSVerified':observed['browser']['acceptInsecureCerts'] is False,'canonicalOrigin':sel['origin'],'upstreamTLS':'CA+hostname+DER fingerprint verified per request','browserNativeMessages':len(messages),'arrivalCount':len(arrival),'nativeSelectedRules':[40012,40018],'variant':variant,'controlLimitations':['Controlled fixture only; product qualification separate; no whole-session hard-kill recovery claim']}
    except Exception as exc:
        result.update(errorType=type(exc).__name__,detail=str(exc)[:400]);raise
    finally:
        done.set();watcher.join(timeout=2);save(out,'HOST_SAMPLES.json',samples)
        if rt:
            try:rt.cleanup();result['cleanupStatus']='clean'
            except Exception as exc:result['cleanupStatus']='unconfirmed';result['cleanupError']=type(exc).__name__
        # target belongs to this exact control; never product/DB.
        if docker(['ps','-aq','--filter','name=^'+target+'$']).strip():
            if docker(['inspect','--format','{{index .Config.Labels "zpa.controlOwner"}}',target]).strip()!=rid:raise ValueError('control ownership drift')
            docker(['rm','-f',target])
        docker(['network','rm',net]);save(out,'CONTROL_RESULT.json',result)
    return result

def urlsplit_path(url):
    from urllib.parse import urlsplit
    return urlsplit(url).path
