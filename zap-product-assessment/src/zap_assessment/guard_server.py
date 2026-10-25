"""Plan-bound, credential-refusing forward guard. No DNS or redirect following."""
import hashlib
import http.client
import json
import os
import time
from datetime import datetime,timezone
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from .egress import EgressGuard,Denied,request_target,policy_target

class BoundGuard(EgressGuard):
    config=None
    def authorize(self):
        c=self.config
        if getattr(self.server,'safety_halted',False):raise Denied('writer-failure-latched')
        if datetime.now(timezone.utc)>=datetime.fromisoformat(c['validUntil']): raise Denied('authority-expired')
        for header in ('Host','Authorization','Proxy-Authorization','Cookie','Content-Length','Transfer-Encoding'):
            if len(self.headers.get_all(header,[]))>1:raise Denied('duplicate-header')
        relative=policy_target(self.command,self.path,self.headers,c['origin'],c['allowedPaths'])
        return relative
    def do_GET(self):
        try:relative=self.authorize()
        except Denied as e:self.reject(str(e));return
        c=self.config;connection=http.client.HTTPConnection(c['address'],c['port'],timeout=2)
        try:
            with self.rate_lock:
                delay=type(self).last_sent+1/c['maxRate']-time.monotonic()
                if delay>0:time.sleep(delay)
                self.authorize() # expiry can occur while queued
                connection.request('GET',relative,headers={'Host':urlsplit(c['origin']).netloc,'Connection':'close'})
                type(self).last_sent=time.monotonic()
            r=connection.getresponse()
            # Refuse session material before forwarding response/history/report.
            if r.getheader('Set-Cookie') is not None or r.getheader('WWW-Authenticate') is not None:
                self.reject('credential-response');return
            data=r.read(1048577)
            if len(data)>1048576:raise ValueError('response-size')
            self.send_response(r.status)
            for k,v in r.getheaders():
                if k.lower() not in ('connection','transfer-encoding','content-length','server','date'):self.send_header(k,v)
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            self.record('forwarded',status=r.status)
        except Denied as e:self.reject(str(e))
        except (OSError,ValueError):
            self.record('failed','upstream');self.send_response(502);self.send_header('Content-Length','0');self.end_headers()
        finally:connection.close()

def main():
    raw=Path('/config/plan.json').read_bytes()
    if hashlib.sha256(raw).hexdigest()!=os.environ['PLAN_SHA256']:raise ValueError('plan digest mismatch')
    # Full validation precedes provisioning. The read-only canonical plan and its
    # digest bind this process without installing a second validator runtime.
    data=json.loads(raw)
    BoundGuard.config=data['guard'];BoundGuard.log_path=Path('/guard/egress.jsonl')
    ThreadingHTTPServer(('127.0.0.1',18888),BoundGuard).serve_forever()
if __name__=='__main__':main()
