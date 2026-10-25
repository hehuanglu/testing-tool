"""Owned UI target: W6 independent product double plus real browser login/forms.

Passwords/tokens are generated only inside this process. Auth receipts are
minimized before persistence; no raw credential value is written or printed.
"""
import copy
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit
from .business_fixture import Product, encode, sha

HTML='''<!doctype html><html><head><meta charset="utf-8"><title>Owned W7 UI fixture</title>
<style>body{font:16px system-ui;max-width:840px;margin:30px auto}label{display:inline-block;margin:8px}input{display:block;padding:6px}button{margin:8px;padding:8px}#summary{padding:20px;border:1px solid #888;width:400px} [hidden]{display:none!important}</style></head>
<body><h1>Owned synthetic UI — W7 diagnostic</h1><p>Source-derived fixture; product runtime unverified.</p>
<div role="alert" id="alert" hidden></div><form id="login-form"><label>Email<input data-testid="email" type="email" autocomplete="off"></label><label>Password<input data-testid="password" type="password" autocomplete="off"></label><button data-testid="sign-in">Sign in</button></form>
<main id="app" hidden><p>Actor: <output data-testid="actor">anonymous</output></p><button data-testid="logout" type="button">Log out</button>
<form id="create-form"><label>Account name<input data-testid="account-name"></label><label>Opening balance<input data-testid="opening-balance"></label><button data-testid="create">Create account</button></form>
<label>Account ID<input data-testid="account-id"></label><button data-testid="read" type="button">View account</button>
<form id="expense-form"><label>Expense amount<input data-testid="amount"></label><button data-testid="expense">Add expense</button></form>
<form id="update-form"><label>New account name<input data-testid="update-name"></label><label>New balance<input data-testid="update-balance"></label><button data-testid="update">Update account</button></form>
<section id="summary" data-testid="summary"><h2>Account state</h2><p>ID: <output data-testid="shown-id"></output></p><p>Balance: <output data-testid="balance"></output></p><p data-testid="outcome"></p></section></main>
<script>
const config=__CONFIG__;const fault=__FAULT__;const q=id=>document.querySelector('[data-testid="'+id+'"]');
let actor='anonymous',subject='',lastRequest='',status=0,complete=0;
const key='finebank.accessToken';const accountBase=config.alternate?'/vault/wallets':'/api/v1/accounts';
const value=body=>config.alternate?body.result.value:body.data;
const units=text=>{const [a,b='']=text.split('.');return Number(BigInt(a)*10000n+BigInt((b+'0000').slice(0,4)));};
const money=n=>{const x=BigInt(n);return String(x/10000n)+'.'+String(x%10000n).padStart(4,'0');};
function clearSummary(){q('shown-id').textContent='';q('balance').textContent='';q('outcome').textContent='';}
function clearError(){document.querySelector('#alert').hidden=true;document.querySelector('#alert').textContent='';}
function fail(){document.querySelector('#alert').hidden=false;document.querySelector('#alert').textContent='Fixture UI operation failed';}
function done(){complete++;document.documentElement.dataset.complete=String(complete);document.documentElement.dataset.request=lastRequest;document.documentElement.dataset.status=String(status);}
function authView(){q('actor').textContent=actor;document.querySelector('#app').hidden=actor==='anonymous';document.querySelector('#login-form').hidden=actor!=='anonymous';}
async function api(action,method,path,body){
 const seq=Number(localStorage.getItem('w7.seq')||0)+1;localStorage.setItem('w7.seq',String(seq));
 lastRequest=config.runId+'-browser-'+seq;let headers={'Content-Type':'application/json','X-W7-Request':lastRequest,'X-W7-Action':action,'X-W6-Case':'ui-expense'};
 const token=localStorage.getItem(key)||sessionStorage.getItem(key);if(token)headers.Authorization='Bearer '+token;
 const r=await fetch(path,{method,headers,body:body===null?undefined:JSON.stringify(body),cache:'no-store'});status=r.status;return {status:r.status,body:await r.json()};
}
async function identity(){const r=await api('identity','GET','/__w7/identity',null);if(r.status!==200)throw Error('identity');actor=r.body.actorRef;subject=String(r.body.subject);authView();}
async function read(){clearError();clearSummary();try{
 const id=q('account-id').value;sessionStorage.setItem('w7.account',id);const r=await api('read','GET',accountBase+'/'+encodeURIComponent(id),null);
 if(r.status===200){const obj=value(r.body);q('shown-id').textContent=String(config.alternate?obj.key:obj.id);q('balance').textContent=config.alternate?money(obj.units):money(units(String(obj.balance)));
 if(fault==='wrong-balance')q('balance').textContent=money(units(q('balance').textContent)+1);
 q('outcome').textContent='Loaded';}else{q('outcome').textContent='Denied';}
 if(fault==='error-page')fail();
 }catch{fail();}finally{done();}}
document.querySelector('#login-form').onsubmit=async e=>{e.preventDefault();clearError();clearSummary();try{
 const r=await api('login','POST','/api/auth/login',{email:q('email').value,password:q('password').value});q('password').value='';
 if(r.status!==200)throw Error('login');localStorage.setItem(key,r.body.data.accessToken);await identity();
 }catch{fail();}finally{done();}};
q('logout').onclick=()=>{clearError();localStorage.removeItem(key);sessionStorage.removeItem(key);actor='anonymous';subject='';clearSummary();authView();done();};
document.querySelector('#create-form').onsubmit=async e=>{e.preventDefault();clearError();clearSummary();if(fault==='no-submit')return;try{
 const name=q('account-name').value,balance=q('opening-balance').value;
 const body=config.alternate?{label:name,openingUnits:units(balance)}:{bank_name:name,account_type:'Synthetic',branch_name:'W6',account_number_full:String(config.accountId).padStart(8,'0'),balance:money(units(balance))};
 const r=await api('create','POST',accountBase,body);if(r.status!==201)throw Error('create');q('outcome').textContent='Created';
 }catch{fail();}finally{done();}};
document.querySelector('#expense-form').onsubmit=async e=>{e.preventDefault();clearError();clearSummary();try{
 const id=config.alternate?q('account-id').value:Number(q('account-id').value),amount=q('amount').value;
 const body=config.alternate?{walletKey:id,labelKey:config.categoryId,units:units(amount)}:{accountId:id,category_id:config.categoryId,type:'Expense',amount:money(units(amount)),transactionDate:'2026-10-19T00:00:00Z',itemDescription:'ui-expense',shopName:'W6',paymentMethod:'Synthetic',status:'Complete'};
 const r=await api('expense','POST',config.alternate?'/journal/debits':'/api/v1/transactions',body);if(r.status!==201)throw Error('expense');q('outcome').textContent='Expense added';
 }catch{fail();}finally{done();}};
document.querySelector('#update-form').onsubmit=async e=>{e.preventDefault();clearError();clearSummary();try{
 const body=config.alternate?{label:q('update-name').value,units:units(q('update-balance').value)}:{bank_name:q('update-name').value,account_type:'Synthetic',branch_name:'W6',balance:money(units(q('update-balance').value))};
 const r=await api('update',config.alternate?'PATCH':'PUT',accountBase+'/'+encodeURIComponent(q('account-id').value),body);q('outcome').textContent=r.status===200?'Updated':'Denied';
 }catch{fail();}finally{done();}};
q('read').onclick=read;q('account-id').value=sessionStorage.getItem('w7.account')||String(config.accountId);
window.w7Snapshot=()=>({actorRef:actor,subject,requestId:lastRequest,status,loginVisible:!document.querySelector('#login-form').hidden,
 passwordCleared:q('password').value==='',accountId:q('shown-id').textContent,balance:q('balance').textContent,
 alertPresent:!document.querySelector('#alert').hidden&&document.querySelector('#alert').textContent.trim().length>0,complete});
window.w7Ready=(async()=>{if(localStorage.getItem(key)||sessionStorage.getItem(key)){await identity();await read();}else authView();})();
</script></body></html>'''


class UIProduct:
    def __init__(self,manifest,config,state_root,fault):
        self.manifest=manifest;self.config=config;self.fault=fault;self.run_id=manifest['runId']
        self.product=Product(manifest,state_root,fault if fault in ('denied-mutated','denied-disclosure') else 'fixed')
        self.passwords={a:'W5-canary-'+secrets.token_hex(32) for a in ('A','B')}
        self.tokens={a:'W5-canary-'+secrets.token_hex(32) for a in ('A','B')}
        self.epochs={a:0 for a in ('A','B')};self.arrivals=[];self.lock=threading.Lock()
    def canaries(self):return list(self.passwords.values())+list(self.tokens.values())
    def identity(self,actor):
        return {'actorRef':actor,'subject':self.config['actors'][actor]['subject'],'authEpoch':self.epochs[actor]}


class UIHandler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def respond(self,status,body,media='application/json'):
        raw=body if isinstance(body,bytes) else encode(body)
        self.send_response(status);self.send_header('Content-Type',media);self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; connect-src 'self'; img-src 'none'")
        self.end_headers();self.wfile.write(raw)
    def dispatch(self):
        p=self.server.product
        if self.command=='GET' and self.path in ('/','/ui'):
            html=HTML.replace('__CONFIG__',json.dumps(p.config).replace('<','\\u003c')).replace('__FAULT__',json.dumps(p.fault))
            return self.respond(200,html.encode(),'text/html; charset=utf-8')
        if self.path=='/favicon.ico':return self.respond(404,{})
        length=int(self.headers.get('Content-Length','0'))
        if length>65536:return self.respond(413,{})
        data=json.loads(self.rfile.read(length)) if length else None
        token=self.headers.get('Authorization','').removeprefix('Bearer ')
        actor=next((a for a,t in p.tokens.items() if secrets.compare_digest(t,token)),'anonymous')
        request={'method':self.command,'path':self.path,'body':data}
        with p.lock:
            before=copy.deepcopy(p.product.state)
            if self.path=='/api/auth/login' and self.command=='POST':
                selected=next((a for a,v in p.config['actors'].items() if v['email']==data.get('email')),'anonymous')
                valid=selected!='anonymous' and secrets.compare_digest(p.passwords[selected],data.get('password',''))
                if valid:
                    actor=selected;p.epochs[actor]+=1;status=200;body={'data':{'accessToken':p.tokens[actor],'user':{'id':p.config['actors'][actor]['subject']}}};safe_body=p.identity(actor)
                else:status=401;body={'statusCode':401,'message':'request rejected'};safe_body=body
                request['body']={'credentialRef':selected}
            elif self.path=='/__w7/identity':
                status=200 if actor!='anonymous' else 401;body=p.identity(actor) if actor!='anonymous' else {'statusCode':401};safe_body=body
            else:
                subject=p.config['actors'][actor]['subject'] if actor!='anonymous' else None
                status,body=p.product.handle(self.command,self.path,data,str(subject) if subject is not None else None,self.headers.get('X-W6-Case',''))
                safe_body=body
            p.product.save()
            receipt={'sequence':len(p.arrivals)+1,'requestId':self.headers.get('X-W7-Request'),
                     'runId':p.run_id,'source':'target','actorRef':actor,'action':self.headers.get('X-W7-Action'),
                     'userAgent':self.headers.get('User-Agent',''),'origin':'http://'+self.headers.get('Host',''),
                     'authEpoch':p.epochs.get(actor,0),'request':request,'status':status,'body':safe_body,
                     'preStateSha256':sha(before),'postStateSha256':sha(p.product.state)}
            p.arrivals.append(receipt)
        self.respond(status,body)
    do_GET=do_POST=do_PUT=do_PATCH=dispatch
