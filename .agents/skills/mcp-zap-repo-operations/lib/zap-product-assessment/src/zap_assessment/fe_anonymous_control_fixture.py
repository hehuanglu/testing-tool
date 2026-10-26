"""Owned HTTPS control app only; structurally different recipes, no product adapter."""
import html,json,ssl,sys,time,io,hashlib
from legacy_control import Control
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_POST(self):
        raw=self.rfile.read(int(self.headers.get('Content-Length','0')));row={'at':time.time(),'method':'POST','path':self.path,'bodySha256':hashlib.sha256(raw).hexdigest(),'host':self.headers.get('Host')}
        with (Path('/evidence')/'arrivals.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        self.rfile=io.BytesIO(raw);self.path='/control/'+self.server.variant;Control.do_POST(self)
    def do_GET(self):
        p=urlsplit(self.path);q=parse_qs(p.query);mode=self.server.variant
        mapped={'/lookup':'/data','/client.mjs':'/app.js','/catalog':'/public'}
        path=mapped.get(p.path,p.path)
        row={'at':time.time(),'method':'GET','path':self.path,'host':self.headers.get('Host')}
        with (Path('/evidence')/'arrivals.jsonl').open('a') as f:f.write(json.dumps(row)+'\n')
        if path=='/data':b=json.dumps({'value':'deferred-verified'}).encode();content='application/json'
        elif path=='/app.js':
            b=b"setTimeout(()=>fetch('/data').then(r=>r.json()).then(x=>document.querySelector('#result').textContent=x.value),30);document.querySelector('form').onsubmit=e=>{e.preventDefault();document.querySelector('#echo').textContent=document.querySelector('input').value};";content='application/javascript'
        elif path=='/redirect':self.send_response(302);self.send_header('Location','https://owned-denied.invalid/collect');self.send_header('Content-Length','0');self.end_headers();return
        else:
            value=q.get('q',[''])[0];value=html.escape(value) if mode=='fixed' else value
            b=('<!doctype html><html><head><title>Control</title></head><body><h1 id="route">TLS control</h1><div id="result">waiting</div><form><label for="term">Term</label><input id="term" required><button id="send">Go</button></form><div id="echo"></div><div id="reflection">'+value+'</div><a href="/redirect">external redirect</a><script src="/app.js"></script></body></html>').encode();content='text/html'
        if mode=='fixed':
            if p.path=='/lookup':b=json.dumps({'data':{'label':'deferred-verified'}}).encode()
            elif p.path=='/client.mjs':
                b=b"fetch('/lookup').then(r=>r.json()).then(x=>document.querySelector('#loaded').textContent=x.data.label);document.querySelector('#search-form').onsubmit=e=>{e.preventDefault();document.querySelector('#answer').textContent=document.querySelector('[name=search]').value};"
            else:
                b=('<!doctype html><html><head><title>Catalog control</title></head><body><main><header><h2 id="catalog-heading">TLS control</h2></header><section><output id="loaded">waiting</output><form id="search-form"><fieldset><legend>Catalog</legend><input id="needle" name="search" required><button id="go">Query</button></fieldset></form><aside><output id="answer"></output><p>'+html.escape(q.get('q',[''])[0])+'</p></aside></section></main><script type="module" src="/client.mjs"></script></body></html>').encode()
        self.send_response(200);self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)

if __name__=='__main__':
    s=ThreadingHTTPServer(('0.0.0.0',8443),Handler);s.variant=sys.argv[1];ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain('/config/target.crt','/config/target.key');s.socket=ctx.wrap_socket(s.socket,server_side=True);s.serve_forever()
