"""Owned one-request fault proxy. Actual product forwarded once, no mutation replay."""
import http.client,json,os,signal,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit
from . import bola_research as br
from .bola_http import exchange
from .bola_research_product import req
from .bola_research_check import check_state

def qualify(out,doc,client,db,raw,actors,model,accounts,categories,body_factory,incorporate,observe,identity):
    results=[]
    for mode,a,expected in [('lost-response','A','allow'),('hard-kill-inflight','B','allow'),('lost-response-denied','A','deny')]:
        label='fault-'+mode;account=accounts[a]['target'];category=categories[a]
        if expected=='deny':category=categories['B']
        body=body_factory(a,account,category,'Revenue',label,'6.3750');request=req(doc,'POST','/api/v1/transactions',body)
        br.save(out,'faults/'+mode+'/LOCKED_REQUEST.json',{'actorRef':a,'request':request,'expected':expected,'maxDispatch':1,'retry':False})
        before,bref=observe(label+'-before');arrived=threading.Event();release=threading.Event();state={};origin=urlsplit(client.origin)
        class Proxy(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                data=self.rfile.read(int(self.headers['Content-Length']))
                if self.path!=request['path'] or json.loads(data)!=request['body']:raise ValueError('fault proxy exact request')
                conn=http.client.HTTPSConnection(origin.hostname,origin.port,context=client.ssl,timeout=5)
                try:
                    conn.request('POST',self.path,body=data,headers={'Content-Type':'application/json','Accept':'application/json','Authorization':self.headers.get('Authorization','')})
                    res=conn.getresponse();payload=json.loads(res.read());state.update(status=res.status,body=payload,forwardCount=1)
                    projected,complete=br.project_response(payload,client.capture_fields,client.secret_values)
                    br.save(out,'faults/'+mode+'/FORWARDED.json',{'status':res.status,'body':projected,'captureComplete':complete,'request':request,'actorRef':a,'forwardCount':1,'observation':'owned proxy received actual app response; downstream client receives no ACK','at':time.time()})
                finally:conn.close();arrived.set()
                if mode=='hard-kill-inflight':release.wait(10)
                self.close_connection=True
        proxy=ThreadingHTTPServer(('127.0.0.1',0),Proxy);thread=threading.Thread(target=proxy.serve_forever,daemon=True);thread.start()
        # Child runner has only one request. Controller retains in-memory login slots;
        # it never resends the child's mutation and only reads/reconciles afterwards.
        real_exchange=br.exchange
        def via_proxy(_origin,method,path,headers,payload,*args,**kw):
            return exchange('http://127.0.0.1:'+str(proxy.server_port),method,path,headers,payload,5)
        killed=None
        try:
            if mode=='hard-kill-inflight':
                pid=os.fork()
                if pid==0:
                    try:
                        br.exchange=via_proxy;client.request(label,a,request,'mutation')
                    except BaseException:pass
                    os._exit(0)
                if not arrived.wait(8):
                    os.kill(pid,signal.SIGKILL);os.waitpid(pid,0);raise ValueError('fault forward missing; outcome unknown')
                os.kill(pid,signal.SIGKILL);_,status=os.waitpid(pid,0);killed=os.WIFSIGNALED(status) and os.WTERMSIG(status)==signal.SIGKILL
                client.count+=1;client.seen.add(label)
                client.j.events=client.j.read()
                client.j.append('recovery-observation-only',{'actionRef':'actions/'+label+'.json','runnerPid':pid,'signal':'SIGKILL','retry':False,'controllerCredentialSource':'same run memory; no token persisted or replayed'})
            else:
                try:
                    br.exchange=via_proxy;client.request(label,a,request,'mutation')
                except (OSError,ValueError,TimeoutError,http.client.HTTPException):pass
                finally:br.exchange=real_exchange
                if not arrived.wait(2):raise ValueError('lost-response forward missing')
        finally:
            br.exchange=real_exchange;release.set();proxy.shutdown();proxy.server_close();thread.join(2)
        # The API response was observed by the owned proxy, never the runner. Obtain
        # the single created ID independently from exact marker, without replay.
        after,aref=observe(label+'-reconcile');created=[r for r in after['transactions'] if r['item_description']==body['itemDescription']]
        if expected=='allow' and len(created)==1:
            incorporate({'id':label,'actorRef':a,'expected':'allow','request':request},201,{'data':{'transactionId':created[0]['id']}})
        br.save(out,'faults/'+mode+'/EXPECTED.json',model)
        problems=check_state(model,after)
        if expected=='allow' and len(created)!=1:problems.append('succeeded create not uniquely reconciled')
        if expected=='deny' and created:problems.append('denied mutation side effect')
        if mode=='hard-kill-inflight' and not killed:problems.append('runner not hard killed')
        refs=[identity(w,label+'-owner-read-'+w) for w in ('A','B')]
        result={'mode':mode,'forwardCount':state.get('forwardCount'),'runnerReceivedResponse':False,'actualProductExchange':True,'replayedMutation':False,'beforeRef':bref,'afterRef':aref,'proxyRef':'faults/'+mode+'/FORWARDED.json','ownerReadbacks':refs,'createdIds':[r['id'] for r in created],'hardKillConfirmed':killed,'reconciliation':'succeeded-once' if expected=='allow' and len(created)==1 else 'denied-no-effect' if not created else 'unknown','problems':problems,'status':'proved' if not problems else 'failed'}
        results.append(result);br.save(out,'faults/'+mode+'/RESULT.json',result)
    br.save(out,'FAILURE_MODE_RESULTS.json',{'results':results,'naturalJwtExpiry':{'status':'not-run','reason':'fresh JWT TTL not changed; no wait for expiry; independent expired-session fixture is separate proof'},'credentialRecoveryBoundary':'controller surviving in same run retains credentials in memory; no proof after loss of whole controller/session'})
