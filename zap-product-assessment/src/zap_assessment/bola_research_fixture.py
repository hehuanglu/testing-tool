"""Independent owned synthetic HTTP control. No core/oracle imports.

Route, fields and error schema intentionally differ from finalsource. Server state
and arrived actor/method/requests are observable by the test harness independently.
"""
from contextlib import contextmanager
import copy
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
import secrets
import threading
import uuid
from urllib.parse import urlsplit,parse_qs


@contextmanager
def fixture(mode='secure'):
    prefix=uuid.uuid4().hex[:10];keys={k:prefix+'-'+k for k in ('a','b','shared','pa','pb','da','db')}
    records={keys[k]:{'key':keys[k],'custodian':'A' if k in ('a','shared','pa','da') else 'B',
       'caption':'private-cargo-'+prefix+'-'+k,'units':100,'members':['B'] if k=='shared' else []} for k in keys}
    tokens={a:secrets.token_urlsafe(32) for a in ('A','B')};state={'records':records,'arrivals':[],'sideEffects':0,'expired':False,'attempts':{}}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def reply(self,status,value,lose=False):
            raw=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(raw)));self.end_headers()
            if lose:self.close_connection=True;return
            self.wfile.write(raw)
        def handle_request(self):
            u=urlsplit(self.path);actor=next((a for a,t in tokens.items() if self.headers.get('Authorization')=='Bearer '+t),'anonymous')
            size=int(self.headers.get('Content-Length','0'));body=json.loads(self.rfile.read(size)) if size else None
            state['arrivals'].append({'actor':actor,'method':self.command,'path':self.path,'body':body,'cookie':'Cookie' in self.headers})
            if u.path=='/session' and self.command=='POST':
                who=body.get('name') if isinstance(body,dict) else None
                return self.reply(200,{'credential':tokens[who],'principal':who}) if who in tokens else self.reply(401,{'error':'auth'})
            if actor=='anonymous' or state['expired']:return self.reply(401,{'error':{'code':'NO_SESSION'}})
            if u.path=='/me':return self.reply(200,{'principal':actor})
            if u.path=='/cargo':
                owned=[v for v in records.values() if v['key'] in [keys['a'],keys['b'],keys['shared']] and (v['custodian']==actor or actor in v['members'] or mode=='list-leak')]
                page=int(parse_qs(u.query).get('page',['0'])[0]);items=owned[page:page+1]
                return self.reply(200,{'items':copy.deepcopy(items),'more':page+1<len(owned)})
            key=u.path.split('/')[-1] if u.path.startswith('/cargo/') else parse_qs(u.query).get('key',[None])[0] if u.path=='/lookup' else body.get('reference',{}).get('cargoKey') if isinstance(body,dict) and u.path=='/move' else None
            value=records.get(key)
            if not value or mode=='missing' and key==keys['a']:return self.reply(404,{'error':{'code':'MISSING'}})
            allowed=value['custodian']==actor or self.command=='GET' and actor in value['members']
            if self.command=='GET':
                if allowed or mode in ('vulnerable','leak403','leak404'):
                    return self.reply(403 if mode=='leak403' and not allowed else 404 if mode=='leak404' and not allowed else 200,{'payload':copy.deepcopy(value)})
                return self.reply(403,{'error':{'code':'DENIED'}})
            if not allowed and mode not in ('vulnerable','denied-sideeffect','lost-ack'):
                return self.reply(403,{'error':{'code':'DENIED','fieldName':'caption'}})
            state['attempts'][key]=state['attempts'].get(key,0)+1
            if self.command in ('PATCH','POST'):value['units']=body.get('units',value['units']);state['sideEffects']+=1
            elif self.command=='DELETE':del records[key]
            if mode=='expire-mid' and not allowed:state['expired']=True
            return self.reply(403 if not allowed and mode=='denied-sideeffect' else 200,{'changed':True},lose=mode=='lost-ack' and not allowed)
        do_GET=handle_request;do_POST=handle_request;do_PATCH=handle_request;do_DELETE=handle_request
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:yield {'origin':'http://127.0.0.1:'+str(server.server_port),'keys':keys,'tokens':tokens,'state':state,'mode':mode,'prefix':prefix}
    finally:server.shutdown();server.server_close();thread.join(timeout=3)
