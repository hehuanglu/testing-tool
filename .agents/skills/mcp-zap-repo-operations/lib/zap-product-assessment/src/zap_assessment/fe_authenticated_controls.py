"""Owned runtime controls and calibration; second app uses the reviewed finite recipe."""
import hashlib,json,ssl,subprocess,time,secrets
from pathlib import Path
from .fe_authenticated_contract import save,load,digest,canonical,pins,validate_journeys
from .fe_authenticated_runner import AuthenticatedRun
from .runtime import docker
from .fe_anonymous_runtime import ROOT

def observations(source,expected_subject='person-71'):
    sources=[{'id':'control-source','path':str(source),'sha256':digest(source)}];prov=['control-source'];actor='actor-a';group='control-a'
    def pred(kind,selector=None,value=None,**kw):return {k:v for k,v in dict(kind=kind,selector=selector,value=value,**kw).items() if v is not None}
    def nav(path,selector):return {'action':'navigate','path':path,'predicate':pred('exists',selector)}
    def journey(id,steps,expected,network,effect='read',post=None):return {'id':id,'responsibilityIds':[id],'provenance':prov,'sessionGroup':group,'actorRef':actor,'phase':'login-pending' if id=='ui-login' else 'authenticated','prerequisites':[],'steps':steps,'expectedUi':expected,'expectedNetwork':network,'postState':post or [],'effect':effect,'evidenceDepth':'UI+network+protected identity+persistence'}
    js=[journey('ui-login',[nav('/signin','#handle'),{'action':'fill','selector':'#handle','fixtureField':'username'},{'action':'fill','selector':'#phrase','fixtureField':'password'},{'action':'submit','selector':'#enter','predicate':pred('text','#principal',expected_subject)},{'action':'identity-probe'}],[pred('text','#principal',expected_subject),pred('storagePresent',key='session.cardinal')],[{'method':'POST','path':'/session/open','statuses':[200]},{'method':'GET','path':'/people/current','statuses':[200]}]),
        journey('ui-mutation',[{'action':'identity-probe'},{'action':'fill','selector':'#record-title','value':'finite-owned-marker'},{'action':'click','selector':'#add','predicate':pred('text','#records','finite-owned-marker')},{'action':'reload','predicate':pred('text','#records','finite-owned-marker')},{'action':'identity-probe'}],[pred('text','#records','finite-owned-marker')],[{'method':'POST','path':'/records','statuses':[201]}],'mutation',[{'kind':'ui-reload','ref':'ui-mutation'}]),
        journey('ui-query',[{'action':'identity-probe'},{'action':'click','selector':'#lookup','predicate':pred('text','#answer','seed')}],[pred('text','#answer','seed')],[{'method':'POST','path':'/query','statuses':[200]}]),
        journey('native-ui-readback',[{'action':'identity-probe'},{'action':'reload','predicate':pred('text','#records','finite-owned-marker')}],[pred('text','#records','finite-owned-marker')],[{'method':'GET','path':'/records','statuses':[200]}])]
    js[1]['steps'][1:1]=[{'action':'fill','selector':'#when','value':'2026-10-24'},{'action':'click','selector':'#record-title'},{'action':'wait','predicate':pred('text','#when-view','2026-10-24')},{'action':'fill','selector':'#period','value':'2026-10'},{'action':'click','selector':'#record-title'},{'action':'wait','predicate':pred('text','#period-view','2026-10')}]
    js[1]['steps'] += [{'action':'readback','path':'/inventory','pointer':'/ledger/entries','valuePointer':'/id','fixtureField':'ownedRecordId','matchPointer':'/title','matchFixture':'recordMarker'},{'action':'post-state','path':'/records/{ownedRecordId}','pointer':'/entry/title','expectedFixture':'recordMarker'}]
    js[1]['postState']=[{'kind':'owned-readback','ref':'ui-mutation'}]
    js.insert(3,journey('ui-query-put',[{'action':'identity-probe'},{'action':'click','selector':'#lookup-put','predicate':pred('text','#answer','seed')}],[pred('text','#answer','seed')],[{'method':'PUT','path':'/query','statuses':[200]}]))
    js[-1]['steps'] += [{'action':'readback','path':'/inventory','pointer':'/ledger/entries','valuePointer':'/id','fixtureField':'terminalRecordId','matchPointer':'/title','matchFixture':'recordMarker'},{'action':'post-state','path':'/records/{terminalRecordId}','pointer':'/entry/quantity','expectedValue':1}]
    rs=[{'id':j['id'],'provenance':prov,'route':'/workspace','action':j['id'],'role':'researcher','state':'owned','input':'finite marker','journeyIds':[j['id']],'branchIds':[j['effect']],'disposition':'planned'} for j in js]
    policies=[{'method':m,'path':path,'phase':phase,'effect':effect,'provenance':prov,**extra} for m,path,phase,effect,extra in [('GET','/signin','public','read',{}),('GET','/workspace','public','read',{}),('GET','/client.js','public','read',{}),('POST','/session/open','bootstrap','bootstrap',{'jsonFields':['handle','phrase']}),('GET','/people/current','identity','read',{}),('GET','/records','protected','read',{'queryKeys':['q']}),('POST','/records','protected','mutation',{'jsonFields':['title','quantity']}),('POST','/query','protected','read',{'jsonFields':['title','quantity']})]]
    policies += [{'method':'GET','path':'/inventory','phase':'protected','effect':'read','provenance':prov},{'method':'GET','path':'/records/{ownedRecordId}','phase':'protected','effect':'read','provenance':prov},{'method':'GET','path':'/records/{terminalRecordId}','phase':'protected','effect':'read','provenance':prov},{'method':'PUT','path':'/query','phase':'protected','effect':'read','jsonFields':['title','quantity'],'provenance':prov}]
    campaigns=[{'id':'native-query','journeyIds':['ui-login'],'actorRef':actor,'authKind':'json-bearer','method':'GET','path':'/records','query':{'q':'seed'},'vector':'query','vectorFields':['q'],'ruleIds':[40012],'maxDelivered':4,'maxAppRequests':9,'postState':[{'kind':'ui-reload','ref':'native-ui-readback'}],'sinkProvenance':prov,'depth':'protected reflection','effect':'read'}]
    campaigns.append({'id':'native-json-body','journeyIds':['ui-query'],'actorRef':actor,'authKind':'json-bearer','method':'POST','path':'/query','body':{'title':'seed','quantity':1},'vector':'json-body','vectorFields':['title'],'ruleIds':[40018],'maxDelivered':6,'maxAppRequests':12,'postState':[{'kind':'ui-reload','ref':'native-ui-readback'}],'sinkProvenance':prov,'depth':'protected SQL sink/error or parameterized fixed control','effect':'read'})
    import copy
    third=copy.deepcopy(campaigns[-1]);third.update(id='native-json-put',method='PUT',journeyIds=['ui-query-put']);campaigns.append(third)
    return validate_journeys({'schemaVersion':'fe-authenticated-journeys/1.0','recipe':'reviewed-fe-auth/1.0','sources':sources,'auth':{'maxLoginsPerActor':4,'kind':'json-bearer','loginPath':'/session/open','usernameField':'handle','passwordField':'phrase','tokenPointer':'/payload/credential','storageKey':'session.cardinal','identity':{'path':'/people/current','subjectPointer':'/envelope/person/subject','rolePointer':'/envelope/person/role','expectedRole':'researcher','roleProvenance':prov},'loginSelectors':{'username':'#handle','password':'#phrase','submit':'#enter'}},'sessionGroups':[{'id':group,'actorRef':actor,'remember':True,'terminal':'dispose'}],'journeys':js,'responsibilities':rs,'requestPolicies':policies,'campaigns':campaigns})

def control(output,jar,jar_pin,authority,variant='vulnerable',fault=None,calibration_ref=None):
    out=Path(output).resolve();out.mkdir(parents=True,mode=0o700,exist_ok=False)
    if authority.get('scope')!='owned-fe-auth-control' or authority.get('profile')!='fe-authenticated-research/1.0' or authority.get('rawRetention')!='local-private' or not authority.get('authorizationRef'):raise ValueError('explicit owned-control authority required')
    begin_pins=pins();save(out,'IMPLEMENTATION_PINS_BEGIN.json',begin_pins)
    snapshots=out/'implementation-source';snapshots.mkdir(mode=0o700)
    for name in begin_pins:
        path=Path(name);save(snapshots,path.name,path.read_bytes())
    jp=load(jar_pin)
    from .product_resources import verify_jar
    verify_jar(jar,jp)
    rid='fa-control-'+str(time.time_ns())[-10:];net=rid+'-targets';target=rid+'-app';config=out/'target-config';config.mkdir(mode=0o755);arrivals=out/'arrivals';arrivals.mkdir(mode=0o777);arrivals.chmod(0o777)
    source=Path(__file__).with_name('fe_authenticated_control_fixture.py')
    username='owned-'+secrets.token_hex(5);password=secrets.token_urlsafe(24);subject='person-'+secrets.token_hex(6)
    users={username:{'password':password,'subject':subject,'role':'researcher'},'peer-'+secrets.token_hex(5):{'password':secrets.token_urlsafe(24),'subject':'person-'+secrets.token_hex(6),'role':'researcher'}}
    save(config,'actors.json',users).chmod(0o444)
    j=observations(source,subject);save(out,'OBSERVATIONS.json',j)
    if fault:
        j['campaigns']=j['campaigns'][:1]
        save(out,'OBSERVATIONS.json',j)
    cert_host='wrong-cardinal.test' if fault=='tls-hostname' else 'cardinal.test'
    subprocess.run(['openssl','req','-x509','-newkey','rsa:2048','-nodes','-days','2','-subj','/CN='+cert_host,'-addext','subjectAltName=DNS:'+cert_host,'-keyout',str(config/'target.key'),'-out',str(config/'target.crt')],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    for f in config.iterdir():f.chmod(0o444)
    pin=load(ROOT/'profiles/runtime-baseline.json');docker(['network','create','--label','zpa.controlOwner='+rid,net]);run=None
    try:
        docker(['run','-d','--name',target,'--label','zpa.controlOwner='+rid,'--network',net,'--user','1005:1005','--cap-drop','ALL','--memory','96m','-v',str(source)+':/app.py:ro','-v',str(config)+':/config:ro','-v',str(arrivals)+':/evidence',pin['boundary'],'python','/app.py',variant])
        v=json.loads(docker(['inspect','--format','{"id":{{json .Id}},"image":{{json .Image}},"started":{{json .State.StartedAt}},"networks":{{json .NetworkSettings.Networks}},"mounts":{{json .Mounts}},"labels":{{json .Config.Labels}}}',target]));n=v['networks'][net];cert=config/'target.crt'
        sel={'origin':'https://cardinal.test:9543','productLocation':str(source.parent),'environment':rid,'targetPort':8443,'binding':{'containerId':v['id'],'imageId':v['image'],'startedAt':v['started'],'networkId':n['NetworkID'],'address':n['IPAddress']},'composeFiles':[],'configPins':[],'certificate':{'path':str(cert),'sha256':digest(cert),'derSha256':hashlib.sha256(ssl.PEM_cert_to_DER_cert(cert.read_text())).hexdigest()},'jar':{'path':str(Path(jar).resolve()),'sha256':digest(jar)},'scannerSourcePins':jp['sourceFiles'],'images':{'zap':pin['zap'],'browser':pin['zap'],'mcp':json.loads(docker(['image','inspect','--format','{{json .Id}}','mcp-zap-server:dev']))}}
        if v['labels'].get('zpa.controlOwner')!=rid or not any(m['Source']==str(source) and m['Destination']=='/app.py' and not m['RW'] for m in v['mounts']):raise ValueError('control source/deployment mount binding absent')
        save(out,'TARGET_BINDING.json',{'deployment':v,'source':{'path':str(source),'sha256':digest(source)},'actorConfig':{'path':str(config/'actors.json'),'sha256':digest(config/'actors.json')},'origin':sel['origin']})
        d={'schemaVersion':'fe-authenticated-discovery/1.0','stage':'runtime-bound','recipe':j['recipe'],'productLocation':str(source.parent),'sources':j['sources'],'journeys':j,'selection':sel}
        auth={'permissions':['network','browser','private-research-retention','active','owned-mutation'],'authorizationRef':authority['authorizationRef']}
        p={'runId':rid,'profile':'fe-authenticated-research/1.0','track':'fe-authenticated','selection':sel,'discovery':d,'journeys':j,'requestPolicies':j['requestPolicies'],'campaigns':j['campaigns'],'authority':auth,'limits':{'reserveBytes':2*1024**3,'maxRequests':250,'maxBodyBytes':2*1024**2,'requestsPerSecond':3,'executionSeconds':600,'maxLoginsPerActor':6,'identityMaxGapSeconds':30}}
        if fault in ('tls-ca','tls-pin','tls-hostname'):p['ownedControlFault']=fault
        if calibration_ref:
            calibration_root=Path(calibration_ref).resolve();pre=load(calibration_root/'PREFLIGHT.json');samples=load(calibration_root/'RESOURCES.json')['samples']
            if load(calibration_root/'RUN.json')['evidenceStatus']!='complete' or not samples:raise ValueError('actual browser TLS auth calibration absent')
            growth=max(pre['hostFree']-min(x['hostFree'] for x in samples),pre['dockerFree']-min(x.get('dockerFree',pre['dockerFree']) for x in samples),1)
            sel['resourceCalibration']={'observedGrowthBytes':growth,'requiredRamBytes':4*1024**3,'evidence':[{'path':str(calibration_root/n),'sha256':digest(calibration_root/n)} for n in ('RESOURCES.json','PREFLIGHT.json','RUNTIME_PINS.json')]}
            from .fe_authenticated_contract import compile_plan,validate_plan
            auth.update(scopeOrigin='explicit-user-authorization',selectionSha256=canonical(sel),productLocation=d['productLocation'],profile='fe-authenticated-research/1.0',tracks=['fe-authenticated'],rawRetention='local-private',notBefore=time.time()-60,notAfter=time.time()+7200,controlScope='owned-fe-auth-control')
            p=compile_plan(d,j,sel,auth,rid);p['limits'].update(maxRequests=250,executionSeconds=600)
            if fault in ('tls-ca','tls-pin','tls-hostname'):p['ownedControlFault']=fault
            validate_plan(p,live=True)
        actors={'actor-a':{'username':username,'password':password,'subject':subject,'role':'researcher','fixtures':{'recordMarker':'finite-owned-marker'},'provenance':[{'path':str(config/'actors.json'),'sha256':digest(config/'actors.json')}]}}
        if fault=='wrong-password':actors['actor-a']['password']='controlled-wrong-password'
        run=AuthenticatedRun(p,out/'runtime',actors,calibration=not bool(calibration_ref))
        if fault:
            from .fe_authenticated_faults import install
            install(run,fault,config,arrivals)
        if fault=='controller-crash':
            import os
            child=os.fork()
            if child==0:
                try:run.execute()
                finally:os._exit(0)
            _,status=os.waitpid(child,0)
            if not os.WIFSIGNALED(status) or os.WTERMSIG(status)!=9:raise ValueError('controller crash did not reach owned SIGKILL checkpoint')
            from .fe_authenticated_recovery import recover
            result=recover(out/'runtime')
        else:result=run.execute()
        save(out,'CONTROL_RESULT.json',{'variant':variant,'fault':fault,'result':result,'sourcePins':pins(),'implementationDrift':pins()!=begin_pins,'qualification':'pending independent readback; runtime source drift disqualifies final-pin qualification'})
        return result
    finally:
        if fault=='controller-crash' and run is not None:
            from .fe_authenticated_recovery import stop_owned_only
            stop_owned_only(out/'runtime')
        if docker(['ps','-aq','--filter','name=^'+target+'$']).strip():
            if docker(['inspect','--format','{{index .Config.Labels "zpa.controlOwner"}}',target]).strip()!=rid:raise ValueError('control target ownership drift')
            docker(['rm','-f',target])
        docker(['network','rm',net])
