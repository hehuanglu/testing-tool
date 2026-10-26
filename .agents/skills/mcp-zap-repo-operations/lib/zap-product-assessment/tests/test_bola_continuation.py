"""Separate state arithmetic/tamper corpus and real HTTP POST controls."""
import copy,json,tempfile,threading,unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from zap_assessment.bola_research_check import check_state,check_pages,check_faults,verify
from zap_assessment.bola_http import exchange

def manifest():
    return {'actors':{'A':{'subject':11},'B':{'subject':22}},'accounts':[{'id':1,'user_id':11,'bank_name':'A','balance':'100.1250'},{'id':2,'user_id':22,'bank_name':'B','balance':'201.3750'}],'categories':[{'id':3,'user_id':11,'name':'Ac'},{'id':4,'user_id':22,'name':'Bc'}],'transactions':[],'goals':[],'bills':[]}

@contextmanager
def post_server(mode):
    state=manifest();arrivals=[]
    class H(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def do_POST(self):
            b=json.loads(self.rfile.read(int(self.headers['Content-Length'])));actor=self.headers.get('X-Actor');arrivals.append({'actor':actor,'body':b});uid=11 if actor=='A' else 22 if actor=='B' else None
            acc=next((r for r in state['accounts'] if r['id']==b['account']),None);cat=next((r for r in state['categories'] if r['id']==b['category']),None)
            allowed=uid is not None and acc is not None and cat is not None and acc['user_id']==uid and cat['user_id']==uid
            mutate=allowed or mode in ('vulnerable','error-side-effect') and uid is not None and acc and cat
            if mutate:
                from decimal import Decimal
                acc['balance']=str(Decimal(acc['balance'])-Decimal(b['amount']));state['transactions'].append({'id':len(state['transactions'])+100,'account_id':b['account'],'category_id':b['category'],'type':'Expense','amount':b['amount'],'status':'Complete','item_description':'control','transaction_date':'2026-10-15 12:00:00.000'})
            status=201 if allowed or mutate and mode=='vulnerable' else 500 if mutate else 400
            raw=json.dumps({'created':bool(mutate)}).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    s=ThreadingHTTPServer(('127.0.0.1',0),H);t=threading.Thread(target=s.serve_forever,daemon=True);t.start()
    try:yield 'http://127.0.0.1:'+str(s.server_port),state,arrivals
    finally:s.shutdown();s.server_close();t.join()

class IndependentChecks(unittest.TestCase):
    def test_fault_claims_require_dispatch_proxy_and_independent_state(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);events=[];results=[]
            def put(name,value):
                p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(value))
            for mode in ('lost-response','hard-kill-inflight','lost-response-denied'):
                denied=mode.endswith('denied');label='fault-'+mode;action='actions/'+label+'.json';base='faults/'+mode+'/'
                request={'method':'POST','path':'/transactions','body':{'itemDescription':label}}
                before=manifest();after=copy.deepcopy(before)
                if not denied:
                    after['transactions']=[{'id':100,'account_id':1,'category_id':3,'type':'Revenue','amount':'1.2500','status':'Complete','item_description':label,'transaction_date':'2026-10-15 12:00:00'}]
                    after['accounts'][0]['balance']='101.3750'
                put(action,{'request':request,'actorRef':'A'});put(base+'LOCKED_REQUEST.json',{'request':request,'actorRef':'A','expected':'deny' if denied else 'allow'})
                put(base+'FORWARDED.json',{'request':request,'actorRef':'A','status':400 if denied else 201,'body':{} if denied else {'data':{'transactionId':100}},'forwardCount':1,'captureComplete':True})
                put(base+'EXPECTED.json',after);put(base+'before.json',before);put(base+'after.json',after)
                results.append({'mode':mode,'proxyRef':base+'FORWARDED.json','beforeRef':base+'before.json','afterRef':base+'after.json','forwardCount':1,'runnerReceivedResponse':False,'replayedMutation':False,'createdIds':[] if denied else [100],'hardKillConfirmed':mode=='hard-kill-inflight','reconciliation':'denied-no-effect' if denied else 'succeeded-once','status':'proved','problems':[]})
                events.extend([{'kind':'intent','data':{'actionRef':action}},{'kind':'recovery-observation-only' if mode=='hard-kill-inflight' else 'unknown-outcome','data':{'actionRef':action,'signal':'SIGKILL' if mode=='hard-kill-inflight' else None}}])
            put('FAILURE_MODE_RESULTS.json',{'results':results})
            (root/'journal.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
            self.assertEqual(check_faults(root),[])
            path=root/'faults/lost-response/FORWARDED.json';original=path.read_text()
            for mutation in (lambda x:x.update(forwardCount=2),lambda x:x.update(actorRef='B'),lambda x:x.update(status=500),lambda x:x.update(body={'data':{'transactionId':999}}),lambda x:x.update(captureComplete=False)):
                v=json.loads(original);mutation(v);path.write_text(json.dumps(v));self.assertTrue(check_faults(root));path.write_text(original)
            p=root/'faults/lost-response/after.json';original=p.read_text();v=json.loads(original);v['accounts'][0]['balance']='0';p.write_text(json.dumps(v));self.assertTrue(check_faults(root));p.write_text(original)
            with (root/'journal.jsonl').open('a') as f:f.write('\n'+json.dumps(events[0]))
            self.assertTrue(check_faults(root))

    def test_exact_balance_foreign_ids_orphan_and_projection(self):
        m=manifest();self.assertEqual(check_state(m,m),[])
        for change in [lambda x:x['accounts'][0].update(balance='100.1251'),lambda x:x['accounts'][0].update(user_id=22),lambda x:x['categories'][0].update(id=44),lambda x:x.pop('bills'),lambda x:x['transactions'].append({'id':10,'account_id':999,'category_id':3})]:
            o=copy.deepcopy(m);change(o);self.assertTrue(check_state(m,o))
    def test_incomplete_pages_wrong_actor_and_foreign(self):
        expected=[{'id':1},{'id':2}];pages=[{'actorRef':'A','subject':11,'offset':i,'body':{'data':{'data':[{'transactionId':i+1}],'total':2,'hasMore':i==0}}} for i in range(2)]
        self.assertEqual(check_pages(expected,pages,'A',11),[])
        self.assertTrue(check_pages(expected,pages[:1],'A',11))
        p=copy.deepcopy(pages);p[1]['actorRef']='B';self.assertTrue(check_pages(expected,p,'A',11))
        p=copy.deepcopy(pages);p[1]['body']['data']['data'][0]['transactionId']=99;self.assertTrue(check_pages(expected,p,'A',11))
    def test_omitted_branch_and_wrong_actor_artifact(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'PLAN.json').write_text(json.dumps({'actors':{'A':{'subject':11}},'cases':[{'id':'c','branchRef':'expense','actorRef':'A','request':{'method':'GET'}}],'inventory':{'operations':[{'operationRef':'read','branches':[]}]}}));(p/'RESULTS.json').write_text(json.dumps([{'caseId':'c','actorRef':'B','attemptRef':'http/c.json'}]));(p/'PAGINATION.json').write_text('[]')
            self.assertIn('unknown branch',verify(p)['errors'])
    def test_real_post_owned_foreign_secure_vulnerable_and_error_sideeffect(self):
        for mode in ('secure','vulnerable','error-side-effect'):
            for actor,aid,cid in [('A',2,3),('A',1,4),('A',2,4),('B',1,4),('B',2,3),('B',1,3)]:
                with self.subTest(mode=mode,actor=actor,account=aid,category=cid),post_server(mode) as (url,state,arrivals):
                    before=copy.deepcopy(state);s,b,_=exchange(url,'POST','/entry',{'Content-Type':'application/json','X-Actor':actor},json.dumps({'account':aid,'category':cid,'amount':'0.1250'}).encode(),2)
                    self.assertEqual(s,400 if mode=='secure' else 201 if mode=='vulnerable' else 500)
                    self.assertEqual(bool(check_state(before,state)),mode!='secure');self.assertEqual(len(arrivals),1)
        for actor,aid,cid in [('A',1,3),('B',2,4)]:
            with post_server('secure') as (url,state,arrivals):
                s,b,_=exchange(url,'POST','/entry',{'Content-Type':'application/json','X-Actor':actor},json.dumps({'account':aid,'category':cid,'amount':'0.1250'}).encode(),2);self.assertEqual(s,201);self.assertEqual(len(state['transactions']),1)
