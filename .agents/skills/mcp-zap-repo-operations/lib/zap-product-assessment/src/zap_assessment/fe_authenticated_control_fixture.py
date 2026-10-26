"""Owned second application with different auth routes/storage/envelope and real persistence."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import hashlib,html,json,os,secrets,sqlite3,ssl,sys,threading,time
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
USERS=json.loads(Path('/config/actors.json').read_bytes())
TOKENS={};ROWS={};LOCK=threading.RLock();VARIANT=sys.argv[1] if len(sys.argv)>1 else 'vulnerable'
PAGE='''<!doctype html><meta charset="utf-8"><title>Cardinal ledger</title><h1 id="heading">Cardinal ledger</h1><form id="signin"><input id="handle"><input id="phrase" type="password"><button id="enter">Enter workspace</button></form><section id="workspace" hidden><p id="principal"></p><input id="record-title"><input id="when" type="date"><input id="period" type="month"><output id="when-view"></output><output id="period-view"></output><button id="add">Add record</button><button id="search">Search</button><button id="lookup">Lookup record</button><button id="lookup-put">Lookup PUT</button><pre id="answer"></pre><pre id="records"></pre><button id="exit">Exit</button></section><script src="/client.js"></script>'''
JS='''const key='session.cardinal';const show=async()=>{const t=localStorage.getItem(key);if(!t)return;const r=await fetch('/people/current',{headers:{Authorization:'Bearer '+t}});if(r.status!==200){document.querySelector('#principal').textContent='Session lost';return;}const a=await r.json();document.querySelector('#signin').hidden=true;document.querySelector('#workspace').hidden=false;document.querySelector('#principal').textContent=a.envelope.person.subject;await list();};const list=async()=>{const r=await fetch('/records?q=seed',{headers:{Authorization:'Bearer '+localStorage.getItem(key)}});document.querySelector('#records').textContent=await r.text();};document.querySelector('#signin').onsubmit=async e=>{e.preventDefault();const r=await fetch('/session/open',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({handle:document.querySelector('#handle').value,phrase:document.querySelector('#phrase').value})});const a=await r.json();if(r.ok){localStorage.setItem(key,a.payload.credential);await show();}};document.querySelector('#add').onclick=async()=>{await fetch('/records',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+localStorage.getItem(key)},body:JSON.stringify({title:document.querySelector('#record-title').value,quantity:1})});await list();};document.querySelector('#search').onclick=list;document.querySelector('#lookup').onclick=async()=>{const r=await fetch('/query',{method:'POST',headers:{'Content-Type':'application/json',Authorization:'Bearer '+localStorage.getItem(key)},body:JSON.stringify({title:'seed',quantity:1})});document.querySelector('#answer').textContent=await r.text();};document.querySelector('#lookup-put').onclick=async()=>{const r=await fetch('/query',{method:'PUT',headers:{'Content-Type':'application/json',Authorization:'Bearer '+localStorage.getItem(key)},body:JSON.stringify({title:'seed',quantity:1})});document.querySelector('#answer').textContent=await r.text();};document.querySelector('#when').onchange=e=>document.querySelector('#when-view').textContent=e.target.value;document.querySelector('#period').onchange=e=>document.querySelector('#period-view').textContent=e.target.value;document.querySelector('#exit').onclick=()=>{localStorage.removeItem(key);location.href='/signin';};show();'''
class H(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def process(self):
        u=urlsplit(self.path);body=self.rfile.read(int(self.headers.get('Content-Length',0)));token=self.headers.get('Authorization','').removeprefix('Bearer ');user=TOKENS.get(token);status=200;mime='application/json';result={};principal=USERS.get(user,{}).get('subject')
        fault_path=Path('/config/fault.json');fault=json.loads(fault_path.read_bytes()) if fault_path.exists() else {};fingerprint=hashlib.sha256(self.headers.get('Authorization','').encode()).hexdigest()
        if fingerprint in fault.get('revoked',[]):user=None;principal=None
        if fingerprint in fault.get('wrongSubject',[]):principal='controlled-wrong-person'
        with LOCK:
            if self.command=='GET' and u.path in ('/signin','/workspace'):result=PAGE;mime='text/html'
            elif self.command=='GET' and u.path=='/client.js':result=JS;mime='application/javascript'
            elif self.command=='POST' and u.path=='/session/open':
                b=json.loads(body);actor=USERS.get(b.get('handle'))
                if actor and secrets.compare_digest(str(b.get('phrase')),actor['password']):
                    t=secrets.token_urlsafe(30);TOKENS[t]=b['handle'];result={'payload':{'credential':t}}
                else:status=401;result={'error':'credentials'}
            elif not user:status=401;result={'error':'session missing'}
            elif self.command=='GET' and u.path=='/people/current':result={'envelope':{'person':{'subject':principal,'role':USERS[user]['role']}}}
            elif self.command=='GET' and u.path=='/inventory':result={'ledger':{'owner':principal,'entries':ROWS.get(user,[])}}
            elif self.command=='GET' and u.path.startswith('/records/'):
                found=next((row for row in ROWS.get(user,[]) if str(row['id'])==u.path.rsplit('/',1)[-1]),None);result={'entry':found,'owner':principal};status=200 if found else 404
            elif self.command=='GET' and u.path=='/records':
                q=parse_qs(u.query).get('q',[''])[0];result='<div>'+('search '+(q if VARIANT=='vulnerable' else html.escape(q)))+'</div><pre>'+html.escape(json.dumps(ROWS.get(user,[])))+'</pre>';mime='text/html'
            elif self.command=='POST' and u.path=='/records':
                b=json.loads(body);record={'id':len(ROWS.get(user,[]))+1,'title':b['title'],'quantity':b['quantity']};ROWS.setdefault(user,[]).append(record);result={'receipt':record,'owner':principal};status=201
            elif self.command in ('POST','PUT') and u.path=='/query':
                b=json.loads(body);db=sqlite3.connect(':memory:');db.execute('CREATE TABLE records(title TEXT)');db.execute('INSERT INTO records VALUES (?)',('seed',))
                try:
                    result={'rows':db.execute("SELECT title FROM records WHERE title = '"+b['title']+"'").fetchall() if VARIANT=='vulnerable' else db.execute('SELECT title FROM records WHERE title = ?', (b['title'],)).fetchall()}
                except sqlite3.Error:result={'error':'sqlite3.OperationalError: SQL syntax error'};status=500
                finally:db.close()
            else:status=404;result={'error':'missing'}
            blob=result.encode() if isinstance(result,str) else json.dumps(result).encode()
            row={'at':time.time(),'method':self.command,'path':u.path,'query':u.query,'bodySha256':hashlib.sha256(body).hexdigest(),'status':status,'principal':principal,'responseSha256':hashlib.sha256(blob).hexdigest(),'rows':ROWS}
            f=Path('/evidence/arrivals.jsonl')
            with f.open('a') as out:out.write(json.dumps(row)+'\n');out.flush();os.fsync(out.fileno())
        if self.command=='POST' and u.path=='/records':
            if fault.get('delayMutation'):time.sleep(min(5,fault['delayMutation']))
            if fault.get('dropMutation'):self.close_connection=True;return
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(len(blob)));self.send_header('Connection','close');self.end_headers();self.wfile.write(blob)
    do_GET=do_POST=do_PUT=process
if __name__=='__main__':
    server=ThreadingHTTPServer(('0.0.0.0',8443),H);ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain('/config/target.crt','/config/target.key');server.socket=ctx.wrap_socket(server.socket,server_side=True);server.serve_forever()
