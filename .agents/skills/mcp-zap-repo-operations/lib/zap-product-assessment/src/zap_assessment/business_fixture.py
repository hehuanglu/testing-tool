"""Independent owned HTTP product double. No oracle/adapter imports.

Only public synthetic subject headers are accepted. Server parses actual wire
requests and writes its own state/arrival receipts; it never consumes transitions
or expected outcomes. Nothing here connects to finalsource or ZAP.
"""
import copy
from decimal import Decimal
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import random
import sys
from urllib.parse import urlsplit


def generate_manifest(run_id, seed, adapter='finalsource-shaped', reverse=False):
    rng=random.Random(seed)
    def wire():
        n=rng.randrange(100000,999999999)
        return n if adapter=='finalsource-shaped' else 'k-'+format(n,'x')+'-'+format(rng.getrandbits(64),'016x')
    m={'contractVersion':'w6-owned-business-1','runId':run_id,'adapter':adapter,'scale':4,
       'actors':[{'actorRef':a,'subject':wire() if a!='anonymous' else None} for a in ('A','B','anonymous')],
       'resources':[],'transitions':[],'coverageGaps':[
           {'capability':'populated-bills','disposition':'skipped','reason':'Available BillsController has GET only; no authorized product fixture-create API found. No DB writes authorized.'},
           {'capability':'cross-owner-account-create','disposition':'unsupported','reason':'Account create binds owner to principal; no owner ID input exists. B own-create and anonymous denial are tested.'},
           {'capability':'product-category-provision','disposition':'skipped','reason':'Available category options are GET only. Categories here are owned synthetic seeds, not product fixture proof.'},
           {'capability':'product-runtime','disposition':'skipped','reason':'No product HTTP or real credentials authorized; mode-specific G3/G4 prerequisites remain blocked.'}]}
    for a in ('A','B'):
        for suffix,kind,exists in [('main','account',True),('new','account',False),('anonnew','account',False),('delete','account',True),('goal','goal',True),('category','category',True)]:
            ref=a+'_'+suffix; initial={'exists':exists}
            if kind=='account':initial.update(balanceMinor=rng.randrange(1000000,2000000),name=ref+'-'+str(seed))
            elif kind=='goal':initial['targetMinor']=rng.randrange(3000000,5000000)
            else:initial['name']=ref+'-'+str(seed)
            m['resources'].append({'resourceRef':ref,'wireId':wire(),'kind':kind,'ownerActorRef':a,'initial':initial,
                                  'provenance':{'runId':run_id,'sourceRef':'synthetic-seed-'+str(seed),'method':'owned-synthetic-seed'}})
    def add(cid,a,op,ref,inp=None,positive=None):
        c={'caseId':cid,'actorRef':a,'operation':op,'resourceRef':ref,'input':inp or {}}
        if positive:c['positiveCaseId']=positive
        m['transitions'].append(c)
    for a in (('B','A') if reverse else ('A','B')):
        b='B' if a=='A' else 'A'; ref=a+'_main'
        ops=[('create','account.create',a+'_new',{}),('read','account.read',ref,{}),
             ('update','account.update',ref,{'balance':'213.4123','name':a+' updated '+str(seed)}),
             ('goal','goal.update',a+'_goal',{'target':'834.1234'}),
             ('expense','expense',ref,{'categoryRef':a+'_category','amount':'7.1234'}),
             ('revenue','revenue',ref,{'categoryRef':a+'_category','amount':'3.9999'}),
             ('delete-control','account.delete',a+'_delete',{})]
        for name,op,target,inp in ops:
            pos=a+'-'+name+'-owner';add(pos,a,op,target,inp)
            if op != 'account.create':
                negtarget=ref if op=='account.delete' else target
                cross_input={**inp,'categoryRef':b+'_category'} if op in ('expense','revenue') else inp
                add(a+'-'+name+'-cross',b,op,negtarget,cross_input,pos)
                add(a+'-'+name+'-anonymous','anonymous',op,negtarget,inp,pos)
            else:add(a+'-create-anonymous','anonymous',op,a+'_anonnew',{},pos)
        add(a+'-insufficient',a,'expense',ref,{'categoryRef':a+'_category','amount':'999999.0001'},a+'-expense-owner')
        for op in ('expense','revenue'):
            add(a+'-'+op+'-cross-category',a,op,ref,{'categoryRef':b+'_category','amount':'1.0001'},a+'-'+op+'-owner')
        for kind,suffix in [('account','main'),('goal','goal'),('category','category'),('transaction','main')]:
            op=kind+'.list'; pos=a+'-'+kind+'-list-owner';add(pos,a,op,a+'_'+suffix)
            add(a+'-'+kind+'-list-anonymous','anonymous',op,a+'_'+suffix,positive=pos)
        add(a+'-delete-final',a,'account.delete',ref)
        # Cascading deletion is followed by a populated/empty exact transaction-list oracle.
        add(a+'-transactions-after-delete',a,'transaction.list',ref)
    if reverse:m['resources'].reverse();m['actors'].reverse()
    return m


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def sha(value):return hashlib.sha256(encode(value)).hexdigest()
def units(value):return int(Decimal(str(value))*10000)
def cash(value):return format(Decimal(value)/10000,'.4f')


class Product:
    def __init__(self, manifest, root, fault='fixed'):
        self.m=manifest;self.root=Path(root);self.fault=fault
        self.resources={r['resourceRef']:r for r in manifest['resources']}
        self.subjects={str(a['subject']):a['actorRef'] for a in manifest['actors'] if a['subject'] is not None}
        self.state={'resources':{r['resourceRef']:copy.deepcopy(r['initial']) for r in manifest['resources']},'transactions':{}}
        self.alt=manifest['adapter']=='alternate-ledger';self.sequence=0;self.save()

    def save(self):
        path=self.root/'state.json';tmp=self.root/'state.tmp';tmp.write_bytes(encode(self.state));os.replace(tmp,path)

    def value(self,ref):
        r=self.resources[ref];s=self.state['resources'][ref];owner=next(a['subject'] for a in self.m['actors'] if a['actorRef']==r['ownerActorRef'])
        if self.alt:
            v={'key':r['wireId'],'principal':owner}
            if r['kind']=='account':v.update(label=s['name'],units=s['balanceMinor'])
            elif r['kind']=='goal':v['ceilingUnits']=s['targetMinor']
            else:v['label']=s['name']
            return v
        if r['kind']=='account':return {'id':r['wireId'],'bank_name':s['name'],'balance':cash(s['balanceMinor'])}
        if r['kind']=='goal':return {'goal_id':r['wireId'],'target_amount':cash(s['targetMinor'])}
        return {'category_id':r['wireId'],'name':s['name']}

    def handle(self, method, path, body, subject, case_id):
        actor=self.subjects.get(subject,'anonymous');url=urlsplit(path).path
        if url=='/__w6/identity':return 200,{'actorRef':actor,'subject':None if actor=='anonymous' else next(a['subject'] for a in self.m['actors'] if a['actorRef']==actor)}
        def error(status):return status,({'fault':{'code':status,'text':'request rejected'}} if self.alt else {'statusCode':status,'message':'request rejected'})
        if actor=='anonymous':return error(401)
        account_base='/vault/wallets' if self.alt else '/api/v1/accounts'
        goal_base='/targets' if self.alt else '/api/v1/goals'
        cat_base='/labels' if self.alt else '/api/v1/categories/options'
        tx_base='/journal' if self.alt else '/api/v1/transactions'
        value=None;status=200
        if method=='GET' and url in (account_base,goal_base,cat_base,tx_base):
            kind={account_base:'account',goal_base:'goal',cat_base:'category',tx_base:'transaction'}[url]
            refs=[ref for ref,r in self.resources.items() if r['kind']==kind and r['ownerActorRef']==actor and self.state['resources'][ref]['exists']]
            if self.fault=='list-leak' and kind=='account':refs=[ref for ref,r in self.resources.items() if r['kind']==kind and self.state['resources'][ref]['exists']]
            rows=[self.value(ref) for ref in reversed(refs)]
            if kind=='transaction':
                rows=[]
                for memo,t in self.state['transactions'].items():
                    if t['ownerActorRef']!=actor:continue
                    account=self.resources[t['accountRef']]['wireId'];category=self.resources[t['categoryRef']]['wireId']
                    rows.append({'memo':memo,'walletKey':account,'units':t['amountMinor'],'side':t['type']} if self.alt else
                                {'transactionId':memo,'itemDescription':memo,'accountId':account,'category_id':category,'amount':cash(t['amountMinor']),'type':'Expense' if t['type']=='expense' else 'Revenue'})
            if self.alt:value=rows
            elif kind=='account':value={'user_id':next(a['subject'] for a in self.m['actors'] if a['actorRef']==actor),'accounts':rows}
            elif kind=='goal':value={'savingGoal':rows[0] if rows else None,'expenseGoals':[]}
            elif kind=='transaction':value={'data':rows,'total':len(rows),'hasMore':False}
            else:value=rows
        elif method=='POST' and url==account_base:
            label=body['label'] if self.alt else body['bank_name']
            matches=[ref for ref,r in self.resources.items() if r['kind']=='account' and r['ownerActorRef']==actor and r['initial']['name']==label]
            if len(matches)!=1:return error(400)
            ref=matches[0];slot=self.state['resources'][ref]
            if slot['exists']:return error(409)
            slot['exists']=True;slot['balanceMinor']=body['openingUnits'] if self.alt else units(body['balance']);slot['name']=label
            value=self.value(ref);status=201
            if not self.alt:value={'account':{**value,'user_id':next(a['subject'] for a in self.m['actors'] if a['actorRef']==actor)}}
        elif method=='POST' and url in (tx_base,'/journal/debits','/journal/credits'):
            aid=body['walletKey'] if self.alt else body['accountId'];catid=body['labelKey'] if self.alt else body['category_id']
            acc=next((ref for ref,r in self.resources.items() if r['kind']=='account' and r['wireId']==aid),None)
            cat=next((ref for ref,r in self.resources.items() if r['kind']=='category' and r['wireId']==catid),None)
            if not acc or not cat or self.resources[acc]['ownerActorRef']!=actor or self.resources[cat]['ownerActorRef']!=actor:return error(400)
            slot=self.state['resources'][acc];amount=body['units'] if self.alt else units(body['amount'])
            expense=url=='/journal/debits' if self.alt else body['type']=='Expense'
            if not slot['exists'] or amount<=0 or expense and amount>slot['balanceMinor']:return error(400)
            slot['balanceMinor']+= -amount if expense else amount
            memo=case_id if self.alt else body['itemDescription']
            self.state['transactions'][memo]={'accountRef':acc,'categoryRef':cat,'ownerActorRef':actor,'amountMinor':amount,'type':'expense' if expense else 'revenue'}
            value={'memo':memo,'walletKey':aid,'units':amount,'side':'expense' if expense else 'revenue'} if self.alt else {'transactionId':memo,'accountId':aid,'category_id':catid,'amount':cash(amount),'type':body['type']}
            status=201
        else:
            base=account_base if url.startswith(account_base+'/') else goal_base
            rid=url.rsplit('/',1)[-1]
            ref=next((ref for ref,r in self.resources.items() if str(r['wireId'])==rid and r['kind']==('account' if base==account_base else 'goal')),None)
            if not ref or not self.state['resources'][ref]['exists']:return error(404)
            slot=self.state['resources'][ref]
            if self.resources[ref]['ownerActorRef']!=actor:
                if self.fault=='denied-mutated' and method in ('PUT','PATCH'):
                    slot['balanceMinor' if base==account_base else 'targetMinor']+=1
                if self.fault=='denied-disclosure':return 403,({'fault':{'code':403,'text':'request rejected'},'leak':self.value(ref)} if self.alt else {'statusCode':403,'message':'request rejected','data':self.value(ref)})
                return error(403)
            if method in ('PUT','PATCH'):
                if base==account_base:slot['balanceMinor']=body['units'] if self.alt else units(body['balance']);slot['name']=body['label'] if self.alt else body['bank_name']
                else:slot['targetMinor']=body['ceilingUnits'] if self.alt else units(body['target_amount'])
            if method=='DELETE':
                slot['exists']=False;self.state['transactions']={k:v for k,v in self.state['transactions'].items() if v['accountRef']!=ref}
                value={'removed':self.resources[ref]['wireId']} if self.alt else {'deleted_account_id':self.resources[ref]['wireId']}
            else:
                value=self.value(ref)
                if not self.alt and method=='PUT':
                    if base==account_base:
                        value['account_id']=value.pop('id');value['user_id']=next(a['subject'] for a in self.m['actors'] if a['actorRef']==actor);value={'account':value}
                    else:value={'updated_goal':value}
        return status,({'result':{'value':value}} if self.alt else {'data':value})


class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def dispatch(self):
        p=self.server.product
        size=int(self.headers.get('Content-Length','0'))
        if size>65536:raise ValueError('body limit')
        body=json.loads(self.rfile.read(size)) if size else None
        subject=self.headers.get('X-W6-Subject');ident=self.headers.get('X-W6-Request')
        before=copy.deepcopy(p.state)
        status,response=p.handle(self.command,self.path,body,subject,self.headers.get('X-W6-Case',''))
        p.save();p.sequence+=1
        receipt={'sequence':p.sequence,'requestId':ident,'actorRef':p.subjects.get(subject,'anonymous'),
                 'request':{'method':self.command,'path':self.path,'body':body},'status':status,'body':response,
                 'preStateSha256':sha(before),'postStateSha256':sha(p.state)}
        with (p.root/'arrivals.jsonl').open('ab') as f:f.write(encode(receipt)+b'\n');f.flush();os.fsync(f.fileno())
        raw=encode(response);self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    do_GET=do_POST=do_PUT=do_PATCH=do_DELETE=dispatch


if __name__=='__main__':
    product=Product(json.loads(Path(sys.argv[1]).read_text()),sys.argv[2],sys.argv[3])
    server=HTTPServer(('127.0.0.1',18080),Handler);server.product=product
    server.serve_forever()
