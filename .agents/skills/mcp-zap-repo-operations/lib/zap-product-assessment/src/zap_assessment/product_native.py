"""Recipe-neutral native execution using ResearchRun, existing provisioning and readback."""
import hashlib
import json
from pathlib import Path
import re
import time
from urllib.parse import urlsplit
from .discovery import execution_origin,verify_identity,matches
from .research import ResearchRun,manifest,write_json
from .research_product import provision,seed_as_user,docker
from .product_workflow import validate_workflow,compile_track
from .bola_research import save


def protected_success(message):
    """Count native bearer responses with a complete 2xx status, even without a reason phrase."""
    return ('Authorization: Bearer ' in message.get('requestHeader','')
            and re.match(r'HTTP/\S+ 2\d\d(?: [^\r\n]*)?\r?\n', message.get('responseHeader','')) is not None)


def read_history(zap, origin, page_size=100):
    """ZAP 2.17 core.messages uses a one-based record position after page one."""
    if type(page_size) is not int or page_size < 1:raise ValueError('history page size invalid')
    count = int(zap.call('core', 'view', 'numberOfMessages', baseurl=origin)['numberOfMessages'])
    if count < 0:raise ValueError('negative history count')
    messages, cursor = [], 0
    while len(messages) < count:
        requested = min(page_size, count - len(messages))
        page = zap.call('core', 'view', 'messages', baseurl=origin, start=cursor, count=requested)['messages']
        ids = [int(m['id']) for m in page]
        if len(page) != requested or ids != sorted(set(ids)):
            raise ValueError('history page incomplete or cursor invalid')
        messages.extend(page)
        cursor = len(messages) + 1
    if [int(m['id']) for m in messages] != sorted(set(int(m['id']) for m in messages)) or len(messages) != count or int(zap.call('core', 'view', 'numberOfMessages', baseurl=origin)['numberOfMessages']) != count:
        raise ValueError('history duplicate or export drift')
    return messages


def profile(doc,actor,run_id,mapping=None):
    a=doc['auth'];ops={o['id']:o for o in doc['operations']};base=execution_origin(doc,'scanner')
    result={'id':'product-'+run_id,'kind':'json-bearer','allowed-origin':base,'credential-reference':'file:/research/password',
        'login-url':base+ops[a['loginOperationId']]['pathTemplate'],'username':actor['username'],'zap-user-name':'product-actor',
        'username-json-field':a['usernameField'],'password-json-field':a['passwordField'],'token-json-pointer':a['tokenPointer'],
        'header-name':a['headerName'],'header-prefix':a['headerPrefix'],
        'verification-url':base+ops[a['identity']['operationId']]['pathTemplate'],
        'logged-in-indicator-regex':'.*','logged-out-indicator-regex':'"(?:status|statusCode)"\\s*:\\s*401',
        'subject-json-pointer':a['identity']['subjectPointer'],'expected-subject':str(actor['subject'])}
    if mapping and mapping['version']=='signed-jwt-protected-probe/1.0':
        result.pop('subject-json-pointer');result['verification-url']=base+ops[mapping['operationId']]['pathTemplate']
        result['signed-jwt-identity']={'public-key-file':actor['jwtTrust']['publicKey']['path'],'public-key-sha256':actor['jwtTrust']['publicKey']['sha256'],
            'issuer':mapping['issuer'],'audience':mapping['audience'],'role-claim':mapping['roleClaim'],'expected-role':actor['role'],
            'expected-status':mapping['expectedStatus'],'response-pointer':mapping['responsePointer'],'response-value':mapping['responseValue']}
    return result


def guard(zap,zapname,plan,out,login_path,workflow):
    """Exact inventory/seed scope, fixed nonmutable JSON reference fields, fail closed locally."""
    paths={};d=workflow['discovery'];ops=d['operations'];path_rules=[]
    from .discovery import matches
    for action in plan['execution']['seeds']+plan['execution']['attacks']:
        path=urlsplit(action['path']).path;key=action['method']+' '+path
        candidates=[op for op in ops if op['method']==action['method'] and matches(op['pathTemplate'],path)]
        literal=[op for op in candidates if op['pathTemplate']==path]
        op=(literal or candidates)[0]
        mutable=workflow['workload'].get('mutableBodyFields',{}).get(op['id'],[])
        body=action.get('body')
        rule={'query':op['input'].get('query',[]),'keys':list(body) if isinstance(body,dict) else [],
              'fixed':{k:v for k,v in body.items() if k not in mutable} if isinstance(body,dict) else {},'jsonBody':isinstance(body,dict),'bootstrap':False}
        paths.setdefault(key,[]).append(rule)
    from .anonymous_guard import path_scope,PATH_GUARD_JS
    for i in workflow['workload'].get('pathAttackIndices',[]):
        action=plan['execution']['attacks'][i];path=urlsplit(action['path']).path
        op=next(o for o in ops if o['method']==action['method'] and matches(o['pathTemplate'],path))
        path_rules.append({**path_scope(op['pathTemplate'],path),'method':action['method']})
    paths.setdefault('GET '+plan['identityPath'],[{'query':[],'keys':[],'fixed':{},'jsonBody':False}])
    paths['POST '+login_path]=[{'query':[],'keys':[],'fixed':{},'jsonBody':False,'bootstrap':True}]
    script=PATH_GUARD_JS+'\nconst PATH_RULES='+json.dumps(path_rules)+';const ORIGIN='+json.dumps(plan['origin'])+';const MAX_REQUESTS='+str(workflow['limits']['maxRequests'])+';const PATHS='+json.dumps(paths)+''';
const Vars=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
const URI=Java.type('org.apache.commons.httpclient.URI');
function sendingRequest(msg,initiator,helper){
 const u=msg.getRequestHeader().getURI();const key=String(msg.getRequestHeader().getMethod())+' '+String(u.getPath());
 const count=Number(Vars.getGlobalVar('product.guard.requests')||0)+1;Vars.setGlobalVar('product.guard.requests',String(count));
 const pathAllowed=!u.getQuery()&&String(msg.getRequestBody()).length===0&&PATH_RULES.some(s=>s.method===String(msg.getRequestHeader().getMethod())&&scopedPath(s,String(u.getPath())));
 let ok=count<=MAX_REQUESTS && String(u.toString()).indexOf(ORIGIN+'/')===0 && (Boolean(PATHS[key])||pathAllowed);
 try{if(ok&&!pathAllowed){ok=PATHS[key].some(function(c){
   if(u.getQuery()){for(const part of String(u.getQuery()).split('&')){if(c.query.indexOf(decodeURIComponent(part.split('=')[0]))<0)return false;}}
   if(!c.jsonBody&&!c.bootstrap&&String(msg.getRequestBody()).length>0)return false;
   if(c.jsonBody){try{const b=JSON.parse(String(msg.getRequestBody()));if(b===null||Array.isArray(b)||typeof b!=='object'||Object.keys(b).length!==c.keys.length||Object.keys(b).some(k=>c.keys.indexOf(k)<0))return false;
     if(Object.values(b).some(v=>v!==null&&(typeof v==='object'||!['string','number','boolean'].includes(typeof v)||(typeof v==='number'&&!Number.isFinite(v)))))return false;
     for(const k of Object.keys(c.fixed)){if(JSON.stringify(b[k])!==JSON.stringify(c.fixed[k]))return false;}
   }catch(e){return false;}}
   return true;
 });}}catch(e){ok=false;}
 if(!ok){
  Vars.setGlobalVar('product.guard.blocks',String(Number(Vars.getGlobalVar('product.guard.blocks')||0)+1));
  msg.getRequestHeader().setURI(new URI(ORIGIN+'/__research_scope_denied__',false));
  msg.getRequestHeader().setMethod('GET');msg.setRequestBody('');msg.getRequestHeader().setContentLength(0);
  for(const h of ['Authorization','Cookie','Proxy-Authorization'])msg.getRequestHeader().setHeader(h,null);
  msg.getRequestHeader().setHeader('Content-Type',null);
  msg.getRequestHeader().setHeader('Transfer-Encoding',null);
  msg.getRequestHeader().setHeader('Host',String(new URI(ORIGIN,false).getAuthority()));
 }
}
function responseReceived(msg,initiator,helper){}
'''
    f=Path(out)/'product-scope.js';f.write_text(script);docker('cp',f,zapname+':/zap/wrk/product-scope.js')
    zap.call('script','action','load',scriptName='product-scope',scriptType='httpsender',scriptEngine='Graal.js',fileName='/zap/wrk/product-scope.js')
    zap.call('script','action','enable',scriptName='product-scope')
    return hashlib.sha256(f.read_bytes()).hexdigest()


def verify_guard(zap, origin, out):
    """Two denied probes must remain rewritten with the sender script enabled."""
    probes=[]
    for index in range(2):
        wire='GET '+origin+'/__zpa_guard_probe_'+str(index)+' HTTP/1.1\r\nHost: '+urlsplit(origin).netloc+'\r\n\r\n'
        rows=zap.call('core','action','sendRequest',request=wire,followRedirects='false')['sendRequest']
        scripts=zap.call('script','view','listScripts')['listScripts']
        enabled=any(s.get('name')=='product-scope' and str(s.get('enabled')).lower()=='true' for s in scripts)
        if len(rows)!=1 or '/__research_scope_denied__' not in rows[0]['requestHeader'].splitlines()[0] or not enabled:
            raise ValueError('scope guard containment control failed')
        probes.append({'index':index,'rewritten':True,'scriptEnabled':enabled,'status':rows[0]['responseHeader'].splitlines()[0]})
    save(out,'GUARD_CONTROLS.json',{'probes':probes,'notBusinessCoverage':True,'blockedDestination':origin+'/__research_scope_denied__'})


def report_readback(run,out):
    """Resume the same artifact after reader faults, without replaying producers."""
    from .evidence import collect_report, ReportReadFailure
    from .safety_io import atomic_bytes
    for fmt in ('json','html'):
        cache = Path(out)/'report-readback'/fmt
        cache.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor = cache/'artifact.json'
        if descriptor.exists():
            binding = json.loads(descriptor.read_text())
            if binding.get('origin') != run.plan['origin']:raise ValueError('report cache origin changed')
            path = binding['reportPath']
        else:
            text = run.tool('zap_report_generate',{'baseUrl':run.plan['origin'],'format':fmt})
            path = next(l.split(': ',1)[1] for l in text.splitlines() if l.startswith('Path: '))
            atomic_bytes(descriptor, json.dumps({'reportPath':path,'origin':run.plan['origin']}).encode())
        saved = [json.loads(p.read_text()) for p in sorted(cache.glob('page-*.json'))]
        def reader(p,offset,sha):
            args={'reportPath':p,'offset':offset,'maxChars':8192}
            if sha is not None:args['expectedSha256']=sha
            return json.loads(run.tool('zap_report_read_chunk',args))
        def checkpoint(page):
            atomic_bytes(cache/('page-'+str(page['offset']).zfill(12)+'.json'),
                         json.dumps(page,ensure_ascii=False).encode())
        result = collect_report(reader,path,32*1024*1024,saved_pages=saved,on_page=checkpoint,parse_json=fmt=='json')
        write_json(cache/'status.json', result.summary())
        if result.status != 'complete':raise ReportReadFailure(result)
        blob=result.data
        if fmt=='html' and b'</html>' not in blob.lower():raise ValueError('HTML report EOF missing')
        destination=Path(out)/('report.'+fmt)
        if destination.exists():
            if destination.read_bytes()!=blob:raise ValueError('report changed during partial readback')
        else:atomic_bytes(destination,blob)


def execute(p,inspection,out,actor,jar,*,interrupt_after=None):
    recipe=validate_workflow(p,inspection)
    from .product_identity import strategy,verify_import
    mapping=strategy(recipe,p['discovery'],actor['role'],imported=actor['provenance'].get('provenanceKind')=='private-credential-import/1.0')
    if p['workload'].get('actorRole') and actor['role']!=p['workload']['actorRole']:raise ValueError('native actor role differs from frozen workload')
    if actor['provenance'].get('provenanceKind')=='private-credential-import/1.0':
        receipt=verify_import(actor)
        if receipt['bindingSha256']!=p['authority']['bindingSha256'] or receipt['authoritySha256']!=p['authoritySha256']:raise ValueError('import authority/binding drift')
    q=compile_track(p,actor=actor['provenance'],fixtures=actor.get('fixtures',[]),identity_strategy=mapping)
    out=Path(out);out.mkdir(parents=True,mode=0o700,exist_ok=False)
    resources=None;run=None;result={'executionStatus':'failed','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'pending','gateDecision':'block'}
    from .product_workflow import archive_sources
    archive_sources(p,out)
    save(out,'PRODUCT_DISCOVERY.json',p['discovery'])
    try:
        # Calibrated native research workload, read-only preflight before setup/provision.
        from .product_resources import preflight
        save(out,'PREFLIGHT.json',preflight(out))
        validate_workflow(p,inspection)
        native=profile(p['discovery'],actor,p['runId'],mapping)
        # Legacy provision requires A only as a private storage slot, not actor/policy semantics.
        slot={'A':{'email':actor['username'],'password':actor['password'],'userId':actor['subject']}}
        resources,zap,client,monitor=provision(out,Path(jar).resolve(),q['targetBinding'],slot,p['discovery'],native_profile=native)
        def bound():validate_workflow(p,inspection);return inspection()[0]
        def native_identity(current):
            row=zap.call('users','action','pollAsUser',**current.native_context)
            if mapping['version']=='signed-jwt-protected-probe/1.0':
                from .signed_identity import check_native
                return check_native(row,q['origin'],q['identityPath'],actor['jwtTrust'],mapping,actor['subject'],actor['role'])
            from .product_identity import check_identity
            header=row['responseHeader'];body=json.loads(row['responseBody'])
            check_identity(int(header.split()[1]),header,body,actor['subject'],actor['role'],mapping)
            return True
        run=ResearchRun(plan=q,binding=bound,client=client,monitor_client=monitor,zap=zap,output=out/'mcp-run',identity_validator=native_identity if mapping['version'] in ('protected-json-subject-role/1.0','signed-jwt-protected-probe/1.0') else None)
        prepared=run.prepare(native['id']);session={k:next(l.split(': ',1)[1] for l in prepared.splitlines() if l.startswith(prefix)) for k,prefix in [('contextId','Context ID: '),('userId','User ID: ')]}
        ops={o['id']:o for o in p['discovery']['operations']};login=ops[p['discovery']['auth']['loginOperationId']]['pathTemplate']
        guard(zap,resources['zap'],q,out,login,p)
        verify_guard(zap,q['origin'],out)
        verify_body_guard(zap,q,p,out)
        verify_path_guard(zap,q,p,out)
        if mapping['version']=='signed-jwt-protected-probe/1.0':
            from .signed_identity import check_native
            row=zap.call('users','action','pollAsUser',**run.native_context)
            check_native(row,q['origin'],q['identityPath'],actor['jwtTrust'],mapping,actor['subject'],actor['role'])
            controls=[]
            for label,subject,role in [('wrong-subject','owned-mismatch-'+str(actor['subject']),actor['role']),('wrong-role',actor['subject'],'owned-mismatch-'+actor['role'])]:
                try:check_native(row,q['origin'],q['identityPath'],actor['jwtTrust'],mapping,subject,role)
                except ValueError:controls.append({'control':label,'rejected':True,'basis':'real native wire observation; changed expected principal'})
                else:raise ValueError('signed identity negative control missed mismatch')
            wire='GET '+q['origin']+q['identityPath']+' HTTP/1.1\r\nHost: '+urlsplit(q['origin']).netloc+'\r\nAuthorization: Bearer owned-invalid-session\r\n\r\n'
            invalid=zap.call('core','action','sendRequest',request=wire,followRedirects='false')['sendRequest']
            if len(invalid)!=1 or int(invalid[0]['responseHeader'].split()[1])!=401:raise ValueError('signed identity native invalid-session control failed')
            controls.append({'control':'invalid-session','status':401,'lane':'native ZAP request; not business coverage'})
            save(out,'SIGNED_IDENTITY_CONTROLS.json',controls)
        zap.call('network','action','addRateLimitRule',description=p['runId'],enabled='true',matchRegex='false',matchString=urlsplit(q['origin']).hostname,requestsPerSecond=p['limits']['requestsPerSecond'],groupBy='rule')
        zap.call('ascan','action','addScanPolicy',scanPolicyName='product-selected',alertThreshold='MEDIUM',attackStrength='LOW')
        zap.call('ascan','action','setOptionTargetParamsInjectable',Integer=1)
        zap.call('ascan','action','setOptionInjectPluginIdInHeader',Boolean='true')
        zap.call('ascan','action','setOptionAddQueryParam',Boolean='false')
        zap.call('ascan','action','disableAllScanners',scanPolicyName='product-selected')
        zap.call('ascan','action','enableScanners',ids=','.join(map(str,q['ruleIds'])),scanPolicyName='product-selected')
        assertions=p['workload'].get('nativeAssertions',{})
        for i,seed in enumerate(q['execution']['seeds']):
            assertion=assertions.get('seed-'+str(i));before=snapshot(p,inspection,out,actor,assertion['reads'],'seed-'+str(i)+'-before') if assertion else None
            run.current();observed=seed_as_user(zap,resources['zap'],session,seed,out,i,q['origin'])
            save(out,f'seeds/{i:03d}-result.json',observed)
            if observed['status'] not in seed['expected']:raise ValueError('native protected seed did not match expected status')
            if assertion:
                after=snapshot(p,inspection,out,actor,assertion['reads'],'seed-'+str(i)+'-after')
                check_native_assertion(assertion,before,after)
        op=run.start('crawl',q['origin']+q['identityPath'],strategy='http');run.wait(op)
        for index,action in enumerate(q['execution']['attacks']):
            assertion=assertions.get('attack-'+str(index));before=snapshot(p,inspection,out,actor,assertion['reads'],'attack-'+str(index)+'-before') if assertion else None
            path_attack=index in p['workload'].get('pathAttackIndices',[])
            zap.call('ascan','action','setOptionTargetParamsInjectable',Integer=16 if path_attack else 2 if action.get('body') is not None else 1)
            zap.call('ascan','action','setOptionTargetParamsEnabledRPC',Integer=4 if action.get('body') is not None else 0)
            save(out,'vectors-'+str(index)+'.json',{'injectable':zap.call('ascan','view','optionTargetParamsInjectable'),'rpc':zap.call('ascan','view','optionTargetParamsEnabledRPC')})
            args={'recurse':'false','policy':'product-selected','method':action['method']}
            if action.get('body') is not None:args['postData']=json.dumps(action['body'])
            op=run.start('attack',q['origin']+action['path'],**args);run.wait(op,interrupt_after=interrupt_after)
            save(out,'active-attribution-'+str(index)+'.json',{
                'nativeScanId':op['nativeScanId'],
                'scanProgress':zap.call('ascan','view','scanProgress',scanId=op['nativeScanId']),
                'messageIds':zap.call('ascan','view','messagesIds',scanId=op['nativeScanId'])})
            if path_attack:
                ids=zap.call('ascan','view','messagesIds',scanId=op['nativeScanId'])['messagesIds']
                messages=[zap.call('core','view','message',id=mid)['message'] for mid in ids]
                inventory=next(o for o in p['discovery']['operations'] if o['method']==action['method'] and matches(o['pathTemplate'],urlsplit(action['path']).path))
                save(out,'path-delivery-'+str(index)+'.json',check_path_delivery(inventory['pathTemplate'],action,messages,q['origin'],q['ruleIds']))
            if assertion:
                after=snapshot(p,inspection,out,actor,assertion['reads'],'attack-'+str(index)+'-after')
                if assertion.get('transition'):
                    ids=zap.call('ascan','view','messagesIds',scanId=op['nativeScanId'])['messagesIds']
                    messages=[zap.call('core','view','message',id=mid)['message'] for mid in ids]
                    save(out,'transition-'+str(index)+'.json',check_transition(assertion['transition'],before,after,messages,action,q['origin']))
                else:check_native_assertion(assertion,before,after)
            if interrupt_after is not None:break
        if not run.validate(client):raise ValueError('protected subject continuity lost')
        # Terminal producers and final subject validation precede stable export.
        run.done.set()
        if run.thread:
            run.thread.join(timeout=15)
            if run.thread.is_alive():raise ValueError('identity monitor still running during export')
        passive=run.tool('zap_passive_scan_wait',{'timeoutSeconds':60,'pollIntervalMs':1000})
        if 'timed out' in passive.lower():raise ValueError('passive scan incomplete')
        report_readback(run,out)
        history=read_history(zap,q['origin'])
        save(out,'raw-history.json',history)
        if mapping['version']=='signed-jwt-protected-probe/1.0':
            from .signed_identity import check_wire_history
            save(out,'WIRE_IDENTITY.json',check_wire_history(history,q['origin'],q['identityPath'],actor['jwtTrust'],mapping,actor['subject'],actor['role']))
        protected=[m for m in history if protected_success(m)]
        if not protected:raise ValueError('protected ZAP traffic absent')
        alerts=[];count=int(zap.call('core','view','numberOfAlerts',baseurl=q['origin'])['numberOfAlerts'])
        for offset in range(0,count,100):
            batch=zap.call('alert','view','alerts',baseurl=q['origin'],start=offset,count=min(100,count-offset))['alerts']
            if len(batch)!=min(100,count-offset):raise ValueError('alert pagination incomplete')
            alerts.extend(batch)
        from .anonymous import validate_exports
        validate_exports(history,alerts,len(history),count)
        save(out,'alerts-native.json',alerts);save(out,'ALERTS.json',{'alerts':alerts})
        save(out,'GUARD_ACCOUNTING.json',{'attempted':zap.call('script','view','globalVar',varKey='product.guard.requests'),'blocked':zap.call('script','view','globalVar',varKey='product.guard.blocks'),'maxRequests':p['limits']['maxRequests'],'requestsPerSecond':p['limits']['requestsPerSecond'],'blockedIsAppCoverage':False})
        save(out,'COVERAGE.json',{'protectedZapResponses':len(protected),'setupAndOracleSeparate':True,'nativeOperationIds':[o['operationId'] for o in run.operations],
                               'activeCoverage':'requires native message/rule attribution; enabled rules are not exercised proof'})
        save(out,'IDENTITY_STRATEGY.json',{'mapping':mapping,'role':actor['role'],'subject':actor['subject'],'nativeValidated':True})
        body_counts=[json.loads(f.read_text())['deliveredBodyMessages'] for f in out.glob('transition-*.json')]
        if p['workload'].get('nativeControl') and body_counts:
            from .product_workflow import body_proof_pins
            evidence=[out/'GUARD_CONTROLS.json',out/'BODY_GUARD_CONTROLS.json',out/'raw-history.json',out/'report.json',out/'report.html',*out.glob('WIRE_IDENTITY.json'),*out.glob('SIGNED_IDENTITY_CONTROLS.json'),*out.glob('transition-*.json'),*out.glob('active-attribution-*.json')]
            save(out,'BODY_CAPABILITY_PROOF.json',{'capability':'native-flat-json-update/1.0','implementationPins':body_proof_pins(),'controlledFixtureOwner':p['authority']['controlledFixtureOwner'],'guardControls':True,'deliveredBodyMessages':sum(body_counts),'allTerminal':all(o['terminal'] for o in run.operations),'reportReadback':True,'evidence':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in evidence]})
        path_counts=[json.loads(f.read_text())['deliveredPathMessages'] for f in out.glob('path-delivery-*.json')]
        if p['workload'].get('nativeControl') and path_counts:
            from .product_workflow import path_proof_pins
            evidence=[out/'PATH_GUARD_CONTROLS.json',out/'GUARD_CONTROLS.json',out/'raw-history.json',out/'report.json',out/'report.html',*out.glob('path-delivery-*.json'),*out.glob('active-attribution-*.json')]
            save(out,'PATH_CAPABILITY_PROOF.json',{'capability':'native-numeric-path/1.0','provenMethods':sorted({q['execution']['attacks'][i]['method'] for i in p['workload']['pathAttackIndices']}),'implementationPins':path_proof_pins(),'controlledFixtureOwner':p['authority']['controlledFixtureOwner'],'guardControls':True,'deliveredPathMessages':sum(path_counts),'allTerminal':all(o['terminal'] for o in run.operations),'reportReadback':True,'evidence':[{'path':str(f),'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in evidence]})
        result.update(executionStatus='interrupted' if interrupt_after is not None else 'completed',evidenceStatus='complete',securityVerdict='requires-triage')
    except Exception as e:
        result['errorType']=type(e).__name__
        # Exceptions can contain rejected secrets; retain location/type without values.
        import traceback
        save(out,'ERROR.json',{'type':type(e).__name__,'frames':[{'file':Path(f.filename).name,'line':f.lineno,'function':f.name} for f in traceback.extract_tb(e.__traceback__)]})
    finally:
        if run:
            run.finish()
            if not (out/'report.json').exists():
                try:
                    run.tool('zap_passive_scan_wait',{'timeoutSeconds':60,'pollIntervalMs':1000})
                    report_readback(run,out)
                    save(out,'PARTIAL_REPORT.json',{'status':'readback-complete','executionStatus':result['executionStatus'],'securityVerdict':'inconclusive'})
                except Exception as partial:
                    save(out,'PARTIAL_REPORT.json',{'status':'unavailable','errorType':type(partial).__name__,'securityVerdict':'inconclusive'})
        if resources is None and (out/'resources.json').exists():resources=json.loads((out/'resources.json').read_text())
        if resources:
            try:
                for key in ('mcp','zap'):
                    name=resources[key]
                    if key+'ContainerId' not in resources:continue
                    if docker('inspect','--format','{{.Id}}',name)!=resources[key+'ContainerId']:raise ValueError('cleanup rebound container')
                    if docker('inspect','--format','{{index .Config.Labels "zpa.research"}}',name)!=resources['runLabel']:raise ValueError('cleanup ownership mismatch')
                    docker('rm','-f',name)
                save(out,'IMAGE_CLEANUP.json',cleanup_images(resources))
                result['cleanupStatus']='clean'
            except Exception:result['cleanupStatus']='incomplete'
        if (result['executionStatus']=='completed' and result['evidenceStatus']=='complete'
                and result['cleanupStatus']=='clean' and result['securityVerdict']=='requires-triage'):
            result['gateDecision']='review_required'
        from .product_scope import task_readback,apply_completion
        result=apply_completion(result,task_readback(p))
        save(out,'RUN.json',result);manifest(out)
    if (out/'ALERTS.json').exists():
        from .product_handoff import native_handoff
        native_handoff(p,out)
    return result

def snapshot(p,inspection,out,actor,requests,label):
    """Separate direct oracle lane; never counted as protected ZAP coverage."""
    from .bola_research import DirectClient
    from .product_prepare import verify_actor
    verify_actor(actor)
    client=DirectClient(p['discovery'],p['discovery']['product']['binding'],inspection,Path(out)/('oracle-'+label),{'permissions':['read','poststate']},
        actor_refs=('subject',),allow_empty=True,not_after=p['notAfter'])
    client.set_tokens({'subject':actor});values={}
    for i,req in enumerate(requests):
        status,body,ref=client.request(label+'-'+str(i),'subject',req,'poststate')
        if status!=200:raise ValueError('native business oracle read failed')
        values[req['operationRef']]=body
    save(out,'oracle-'+label+'.json',{'lane':'direct-oracle','count':client.count,'state':values});return values


def verify_path_guard(zap,plan,workflow,out):
    from .anonymous_guard import path_scope
    controls=[]
    for i in workflow['workload'].get('pathAttackIndices',[]):
        action=plan['execution']['attacks'][i];op=next(o for o in workflow['discovery']['operations'] if o['method']==action['method'] and matches(o['pathTemplate'],action['path']))
        scope=path_scope(op['pathTemplate'],action['path']);foreign=scope['prefix']+str(int(scope['baseline'])+1)+scope['suffix']
        probes=[(action['method'],foreign),(action['method'],action['path']+'?undeclared=1'),('OPTIONS',action['path']),(action['method'],'/undeclared'+action['path'])]
        for method,path in probes:
            # These sentinel credentials must be stripped before the denied destination.
            wire=method+' '+plan['origin']+path+' HTTP/1.1\r\nHost: '+urlsplit(plan['origin']).netloc+'\r\nAuthorization: Bearer owned-path-control\r\nCookie: sentinel=owned\r\n\r\n'
            rows=zap.call('core','action','sendRequest',request=wire,followRedirects='false')['sendRequest']
            header=rows[0]['requestHeader'] if len(rows)==1 else ''
            scripts=zap.call('script','view','listScripts')['listScripts']
            enabled=any(s.get('name')=='product-scope' and str(s.get('enabled')).lower()=='true' for s in scripts)
            if not enabled or '/__research_scope_denied__' not in header.splitlines()[0] or 'authorization:' in header.lower() or 'cookie:' in header.lower() or rows[0].get('requestBody'):raise ValueError('native path containment control failed')
            controls.append({'attackIndex':i,'method':method,'rewritten':True,'credentialsRemoved':True,'scriptEnabled':True,'notBusinessCoverage':True})
    save(out,'PATH_GUARD_CONTROLS.json',controls)


def check_path_delivery(template,action,messages,origin,rules):
    from .anonymous_guard import path_scope,scoped_path
    scope=path_scope(template,action['path']);delivered=[]
    for message in messages:
        parts=message.get('requestHeader','').splitlines()[0].split()
        if len(parts)<2:raise ValueError('path wire request missing')
        target=parts[1];u=urlsplit(target if '://' in target else origin+target)
        if u.path=='/__research_scope_denied__':continue
        if (parts[0]!=action['method'] or u.scheme+'://'+u.netloc!=origin or u.query or u.fragment or message.get('requestBody')
                or not scoped_path(scope,u.path) or 'authorization: bearer ' not in message['requestHeader'].lower()):raise ValueError('native path wire scope/identity mismatch')
        status=int(message['responseHeader'].split()[1])
        if status in (401,403):raise ValueError('native path authentication/authorization loss')
        if u.path!=action['path']:
            rule=re.search(r'(?im)^X-ZAP-Scan-ID:\s*(\d+)',message['requestHeader'])
            if not rule or int(rule[1]) not in rules:raise ValueError('path rule attribution missing')
            delivered.append({'messageId':str(message['id']),'ruleId':int(rule[1]),'status':status,'vector':'path'})
    if not delivered:raise ValueError('native active path payload absent')
    return {'deliveredPathMessages':len(delivered),'attribution':delivered,'scopeContained':True}


def check_native_assertion(assertion,before,after):
    from .product_checks import pointer
    if assertion.get('unchanged') is True:
        if before!=after:raise ValueError('native operation unexpected business side effect')
    elif assertion.get('postEquals'):
        for path,value in assertion['postEquals'].items():
            if pointer(after,path)!=value:raise ValueError('native business poststate mismatch')
    else:raise ValueError('native business assertion missing')


def cleanup_images(resources):
    """Remove only exact tags created by this run. No prune/force/shared-image deletion."""
    result=[]
    for tag,expected in [(resources['image'],resources['mcpImageId']),(resources['runLabel']+'-runtime-base',resources['runtimeBaseImageId'])]:
        current=docker('image','inspect','--format','{{.Id}}',tag)
        if current!=expected:raise ValueError('run image tag rebound; retain for reconciliation')
        docker('image','rm',tag)
        result.append({'tag':tag,'imageId':expected,'removedRunTag':True})
    return result


def verify_body_guard(zap,plan,workflow,out):
    controls=[]
    for action in plan['execution']['attacks']:
        if not isinstance(action.get('body'),dict):continue
        variants=[{**action['body'],'__undeclared_reference':'foreign'},'{malformed']
        from .discovery import matches
        op=next(o for o in workflow['discovery']['operations'] if o['method']==action['method'] and matches(o['pathTemplate'],urlsplit(action['path']).path))
        mutable=workflow['workload']['mutableBodyFields'][op['id']]
        variants.extend([{**action['body'],mutable[0]:{'nested':'owned-control'}},{**action['body'],mutable[0]:['owned-control']}])
        fixed=[k for k in action['body'] if k not in mutable]
        if fixed:variants.append({**action['body'],fixed[0]:'foreign-reference'})
        for body in variants:
            wire_body=body if isinstance(body,str) else json.dumps(body)
            wire=action['method']+' '+plan['origin']+action['path']+' HTTP/1.1\r\nHost: '+urlsplit(plan['origin']).netloc+'\r\nAuthorization: Bearer owned-guard-control\r\nCookie: owned=control\r\nContent-Type: application/json\r\nContent-Length: '+str(len(wire_body.encode()))+'\r\n\r\n'+wire_body
            rows=zap.call('core','action','sendRequest',request=wire,followRedirects='false')['sendRequest']
            header=rows[0]['requestHeader'] if len(rows)==1 else ''
            scripts=zap.call('script','view','listScripts')['listScripts']
            enabled=any(s.get('name')=='product-scope' and str(s.get('enabled')).lower()=='true' for s in scripts)
            if '/__research_scope_denied__' not in header.splitlines()[0] or 'authorization:' in header.lower() or 'cookie:' in header.lower() or rows[0].get('requestBody') or not enabled:raise ValueError('native body guard control failed')
            controls.append({'rewritten':True,'scriptEnabled':enabled,'credentialsRemoved':True,'notBusinessCoverage':True})
    save(out,'BODY_GUARD_CONTROLS.json',controls)


def check_transition(contract,before,after,messages,action,origin):
    """Independent body wire/response/post-state oracle, with recipe-defined pointers only."""
    from .product_checks import pointer
    field=contract['field'];last=pointer(before,contract['statePointer']);accepted=rejected=delivered=0;attributed=[]
    for m in sorted(messages,key=lambda r:int(r['id'])):
        line=m.get('requestHeader','').splitlines()[0].split()
        if len(line)<2 or line[0]!=action['method'] or line[1] not in (origin+action['path'],action['path']):continue
        body=json.loads(m['requestBody']);status=int(m['responseHeader'].split()[1]);response=json.loads(m['responseBody'])
        if set(body)!=set(action['body']) or any(body[k]!=v for k,v in action['body'].items() if k!=field):raise ValueError('native fixed body reference escaped')
        if 'authorization: bearer ' not in m['requestHeader'].lower():raise ValueError('native body missing authenticated transport')
        if status in (401,403):raise ValueError('native body auth loss')
        if status in contract['acceptedStatuses']:
            if pointer(response,contract['responsePointer'])!=body[field]:raise ValueError('accepted native body response mismatch')
            for path,value in contract.get('responseEquals',{}).items():
                if pointer(response,path)!=value:raise ValueError('accepted native body identity/reference mismatch')
            last=body[field];accepted+=1
        elif status in contract['rejectedStatuses']:rejected+=1
        else:raise ValueError('native body response outside oracle')
        rule=re.search(r'(?im)^X-ZAP-Scan-ID:\s*(\d+)',m['requestHeader'])
        if body!=action['body']:
            if not rule or int(rule[1]) not in (40012,40018):raise ValueError('native body rule attribution missing')
            delivered+=1;attributed.append({'messageId':str(m['id']),'ruleId':int(rule[1]),'vector':'JSON-body','status':status})
    if delivered<1:raise ValueError('native active body payload absent')
    if pointer(after,contract['statePointer'])!=last:raise ValueError('native final state does not match last accepted payload')
    for path,value in contract['fixedState'].items():
        if pointer(before,path)!=value or pointer(after,path)!=value:raise ValueError('native state identity/reference drift')
    return {'deliveredBodyMessages':delivered,'acceptedResponses':accepted,'rejectedResponses':rejected,'attribution':attributed,'finalStateMatched':True}
