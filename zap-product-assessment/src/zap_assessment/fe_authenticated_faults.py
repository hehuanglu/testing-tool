"""Code-owned qualification faults. Only installed by the owned control harness."""
import hashlib,json,os,signal,threading,time
from pathlib import Path
from urllib.parse import urlsplit
from .fe_authenticated_contract import load,save
from .fe_authenticated_semantics import request
from .runtime import docker
FAULTS={'wrong-password','wrong-actor','stale-credential','browser-loss','native-loss','pre-send','commit-drop','broker-crash','controller-crash','resource','cancel','lost-ack','native-restart','scope','tls-ca','tls-hostname','tls-pin'}

def mutation_records(capture,case_id,origin):
    rows=[load(path) for path in sorted(Path(capture).glob('[0-9]*.json'))]
    return [row for row in rows if row.get('caseId')==case_id and row.get('method')=='POST' and row.get('url')==origin+'/records']

def install(run,fault,config,arrivals):
    if fault not in FAULTS:raise ValueError('unreviewed fault')
    if run.p['selection']['environment'][:11]!='fa-control-':raise ValueError('fault hooks require owned control deployment')
    config=Path(config);arrivals=Path(arrivals)
    def count():return len((arrivals/'arrivals.jsonl').read_text().splitlines()) if (arrivals/'arrivals.jsonl').exists() else 0
    def tokens(slot):
        rows=[load(f) for f in run.rt.capture.glob('[0-9]*.json')];matches=[r for r in rows if r.get('authSlot')==slot and r.get('observedPrincipal')]
        if not matches:raise ValueError('fault has no independently protected slot')
        last=max(matches,key=lambda r:r['sequence']);messages=run.engine('core','view','messages',{'baseurl':run.p['selection']['origin'],'start':0,'count':100})['messages']
        for raw in messages:
            m=request(raw,run.p['selection']['origin']);header=m['headers'].get('authorization','') if m else ''
            if hashlib.sha256(header.encode()).hexdigest()==last['credentialFingerprint']:return header,last['credentialFingerprint']
        raise ValueError('fault slot credential lacks wire join')
    def send(method,path,authorization,body=None):
        u=urlsplit(run.p['selection']['origin']);raw=json.dumps(body,separators=(',',':')) if body is not None else ''
        wire=method+' '+run.p['selection']['origin']+path+' HTTP/1.1\r\nHost: '+u.netloc+'\r\nAuthorization: '+authorization+'\r\nContent-Type: application/json\r\nContent-Length: '+str(len(raw.encode()))+'\r\nConnection: close\r\n\r\n'+raw
        return run.engine('core','action','sendRequest',{'request':wire,'followRedirects':'false'})
    if fault in ('lost-ack','controller-crash'):
        def before(r,g,j):
            if getattr(r,'fault_installed',False):return
            r.fault_installed=True;original=r.mcp.call
            def call(name,args):
                result=original(name,args)
                if name=='zap_attack_start':
                    save(r.out,'FAULT_INJECTION.json',{'fault':fault,'at':time.time(),'afterNativeStart':True,'replayed':False})
                    if fault=='controller-crash':os.kill(os.getpid(),signal.SIGKILL)
                    raise TimeoutError('controlled lost native start ACK')
                return result
            r.mcp.call=call
        run.before_native_hook=before;return
    if fault in ('wrong-password','tls-ca','tls-hostname','tls-pin'):return
    def hook(r,g,j):
        if j['id']!='native-ui-readback' or getattr(r,'fault_installed',False):return
        r.fault_installed=True;native,nfp=tokens('native');browser,bfp=tokens('browser');before=count();base=r.p['journeys']['auth']['identity']['path'];detail={'fault':fault,'beforeAppCount':before,'at':time.time(),'replayed':False}
        save(r.out,'FAULT_INTENT.json',detail)
        if fault=='scope':
            r.rt.mode('fault-scope',actor='actor-a',group=g['id'],slot='native')
            u=urlsplit(r.p['selection']['origin']);outside='https://outside-owned.invalid:9543'+base
            try:r.engine('core','action','sendRequest',{'request':'GET '+outside+' HTTP/1.1\r\nHost: outside-owned.invalid:9543\r\nAuthorization: '+native+'\r\nConnection: close\r\n\r\n','followRedirects':'false'})
            except ValueError:pass
            denied=[load(f) for f in r.rt.capture.glob('[0-9]*.json') if load(f).get('caseId')=='fault-scope' and load(f).get('reason')=='connect-origin']
            if not denied:raise ValueError('scope denial lacks broker CONNECT proof')
            detail.update(afterAppCount=count(),deniedSequences=[x['sequence'] for x in denied],boundary=r.rt.boundary())
            if count()!=before:raise ValueError('scope denial reached app')
            protocol=[]
            for label,url,extra,reason in [('downgrade','http://'+u.netloc+base,'','origin'),('websocket',r.p['selection']['origin']+base,'Upgrade: websocket\r\n','host-or-protocol')]:
                r.rt.mode('fault-scope-'+label,actor='actor-a',group=g['id'],slot='native')
                try:r.engine('core','action','sendRequest',{'request':'GET '+url+' HTTP/1.1\r\nHost: '+u.netloc+'\r\nAuthorization: '+native+'\r\n'+extra+'Connection: close\r\n\r\n','followRedirects':'false'})
                except ValueError:pass
                rows=[load(f) for f in r.rt.capture.glob('[0-9]*.json') if load(f).get('caseId')=='fault-scope-'+label and load(f).get('reason')==reason and not load(f).get('forwarded')]
                if not rows or count()!=before:raise ValueError('protocol guard not proven '+label)
                protocol.append({'case':label,'reason':reason,'sequences':[x['sequence'] for x in rows],'appArrival':False})
            code="import socket,http.client,json;out={};s=socket.socket(socket.AF_INET6);s.settimeout(.3);out['ipv6ManagementReachable']=s.connect_ex(('::1',8090))==0;s.close()\ntry:\n c=http.client.HTTPConnection('127.0.0.1',8090,timeout=2);c.request('GET','/JSON/core/view/version/');v=c.getresponse();out['managementStatus']=v.status;v.read();c.close()\nexcept (http.client.RemoteDisconnected,ConnectionResetError,TimeoutError) as e:out['managementStatus']=None;out['rejectionType']=type(e).__name__\nprint(json.dumps(out))"
            management=json.loads(docker(['exec','--user','1004:1004',r.rt.anchor,'python','-c',code]))
            if management['ipv6ManagementReachable'] or management['managementStatus'] not in (None,400,401,403):raise ValueError('management/IPv6 boundary failed')
            detail.update(protocol=protocol,management=management,afterAppCount=count())
        elif fault=='stale-credential':
            r.rt.mode('fault-stale',actor='actor-a',group=g['id'],slot='native');response=send('GET',base,'Bearer controlled-unregistered-token');send('GET',base,native);detail.update(afterAppCount=count(),responseStatus=response['sendRequest'][0]['responseHeader'].splitlines()[0])
            if count()!=before:raise ValueError('stale credential reached app')
        elif fault in ('wrong-actor','browser-loss','native-loss'):
            # The other slot stays live; this is injected loss, never natural expiry.
            selected=bfp if fault=='browser-loss' else nfp
            save(config,'fault.pending',{'wrongSubject':[selected]} if fault=='wrong-actor' else {'revoked':[selected]}).chmod(0o444);os.replace(config/'fault.pending',config/'fault.json')
            try:
                if fault=='browser-loss':r.rt.mode('fault-native-still-valid',actor='actor-a',group=g['id'],slot='native');r.native_validate('actor-a');r.browser_continuity(g,j)
                else:r.browser_continuity(g,j);r.rt.mode('fault-'+fault,actor='actor-a',group=g['id'],slot='native');r.native_validate('actor-a')
            except Exception as e:
                detail.update(rejectionType=type(e).__name__);after_loss=count();send('GET',base,browser if fault=='browser-loss' else native);detail.update(afterLossAppCount=after_loss,afterAppCount=count())
                if count()!=after_loss:raise ValueError('latched slot forwarded a subsequent request')
            else:raise ValueError('identity loss did not stop dependent producer')
        elif fault=='native-restart':
            sid=r.native['actor-a']['sessionId'];before_runtime=r.rt.check_owner(r.rt.names[3]);r.j.append('intent',{'action':'owned-native-restart','containerId':before_runtime['Id']});docker(['restart',r.rt.names[3]]);r.rt.wait_health();after_runtime=r.rt.check_owner(r.rt.names[3]);r.j.append('ack',{'action':'owned-native-restart','containerId':after_runtime['Id']});detail['restart']={'containerId':after_runtime['Id'],'beforeStartedAt':before_runtime['State']['StartedAt'],'afterStartedAt':after_runtime['State']['StartedAt']}
            from .fe_authenticated_mcp import RecordedMCP
            r.mcp=RecordedMCP(r.rt,r.out/'restarted-mcp');(r.out/'restarted-mcp').mkdir(mode=0o700);r.mcp.initialize()
            try:r.native_validate('actor-a')
            except Exception as e:detail.update(rejectionType=type(e).__name__,oldSessionId=sid,afterAppCount=count())
            else:raise ValueError('stale native handle accepted after owned MCP restart')
        elif fault in ('commit-drop','broker-crash','pre-send'):
            r.rt.mode('fault-'+fault,actor='actor-a',group=g['id'],slot='native')
            if fault=='pre-send':
                b=r.p['selection']['binding'];rule=['iptables','-I','OUTPUT','1','-p','tcp','-d',b['address'],'--dport',str(r.p['selection']['targetPort']),'-m','owner','--uid-owner','1003','-j','REJECT'];docker(['exec',r.rt.anchor,*rule])
            else:
                save(config,'fault.pending',{'dropMutation':True} if fault=='commit-drop' else {'delayMutation':5}).chmod(0o444);os.replace(config/'fault.pending',config/'fault.json')
            failures=[]
            def dispatch():
                try:send('POST','/records',native,{'title':'owned-uncertain-marker','quantity':1})
                except Exception as e:failures.append(type(e).__name__)
            worker=threading.Thread(target=dispatch);worker.start()
            if fault=='broker-crash':
                deadline=time.monotonic()+10
                while count()==before and time.monotonic()<deadline:time.sleep(.05)
                if count()!=before+1:raise ValueError('broker crash commit checkpoint absent')
                owned=r.rt.check_owner(r.rt.names[1]);r.j.append('intent',{'action':'owned-broker-kill','containerId':owned['Id'],'signal':'KILL'});docker(['kill','--signal','KILL',r.rt.names[1]]);detail['killedBrokerId']=owned['Id']
            worker.join(timeout=25)
            if worker.is_alive():raise TimeoutError('fault dispatch unresolved; retain')
            detail.update(afterAppCount=count(),requestErrors=failures)
            rows=mutation_records(r.rt.capture,'fault-'+fault,r.p['selection']['origin']);detail['transportRows']=rows
            if fault=='pre-send' and (count()!=before or len(rows)!=1 or rows[0].get('transportState')!='not-sent'):raise ValueError('pre-send control not proven')
            if fault!='pre-send' and (count()!=before+1 or len(rows)!=1 or rows[0].get('transportState') not in ('sent','response-headers','unknown')):raise ValueError('unknown committed mutation not retained')
        elif fault=='resource':
            real=r.rt.sample();original=r.rt.sample;r.rt.sample=lambda:{**real,'hostFree':0,'injectedQualificationSample':True};detail['actualResourceSample']=real
            deadline=time.monotonic()+18
            while not r.cancel.is_set() and time.monotonic()<deadline:time.sleep(.2)
            r.rt.sample=original
            if not r.cancel.is_set():raise ValueError('injected resource breach did not latch')
            detail['monitorErrors']=r.errors
        elif fault=='cancel':r.cancel.set();(r.rt.config/'STOP').touch();detail['cancelSet']=True
        save(r.out,'FAULT_OBSERVED.json',detail)
        raise InterruptedError('owned qualification fault: '+fault)
    run.qualification_hook=hook
