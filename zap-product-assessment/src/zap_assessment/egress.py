"""Mandatory HTTP forward guard for the isolated, anonymous, read-only fixture.

The scanner UID can connect only to this guard. Forward sockets use a fixed
literal IP/port and redirects are returned to ZAP for another origin check.
"""
import hashlib
import http.client
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

ORIGIN='http://127.0.0.1:18080'
class Denied(ValueError):pass

def request_target(method,url,headers,approved_origin=ORIGIN):
    if method!='GET': raise Denied('method')
    if not isinstance(url,str) or any(c.isspace() or ord(c)<32 for c in url) or '\\' in url: raise Denied('url')
    try:u=urlsplit(url)
    except ValueError as e:raise Denied('url') from e
    if u.scheme!='http' or u.username or u.password or u.fragment or not u.hostname:raise Denied('origin')
    expected=urlsplit(approved_origin)
    if (u.scheme,u.hostname,u.port or 80)!=(expected.scheme,expected.hostname,expected.port or 80) or u.netloc!=expected.netloc: raise Denied('origin')
    values={k.lower():v for k,v in headers.items()}
    if values.get('host')!=expected.netloc: raise Denied('host')
    if any(values.get(k) for k in ('authorization','proxy-authorization','cookie','transfer-encoding')) or values.get('content-length','0')!='0':raise Denied('anonymous-read-only')
    return (u.path or '/')+('?' + u.query if u.query else '')

def policy_target(method,url,headers,approved_origin,allowed_paths):
    """Narrow anonymous boundary shared by bound guard and W4 conformance cases."""
    relative=request_target(method,url,headers,approved_origin)
    if urlsplit(url).query or urlsplit(url).path not in allowed_paths:raise Denied('path')
    return relative

class EgressGuard(BaseHTTPRequestHandler):
    target_origin=ORIGIN
    minimum_interval=.5
    rate_lock=threading.Lock()
    last_sent=0.0
    log_path=Path('/fixture/egress.jsonl')
    def log_message(self,*args):pass
    def record(self,action,reason=None,status=None):
        item={'action':action,'method':self.command,'urlSha256':hashlib.sha256(self.path.encode()).hexdigest()}
        if reason:item['reason']=reason
        if status is not None:item['status']=status
        try:
            data=json.dumps(item)+'\n'
            with self.log_path.open('a') as f:
                if f.write(data)!=len(data):raise OSError('guard short write')
                f.flush();os.fsync(f.fileno())
        except OSError:
            self.server.safety_halted=True
            raise
    def reject(self,reason):
        self.record('denied',reason);self.send_response(403);self.send_header('Content-Length','0');self.end_headers()
    def do_GET(self):
        if getattr(self.server,'safety_halted',False):
            self.send_response(503);self.send_header('Content-Length','0');self.end_headers();return
        try:relative=request_target('GET',self.path,self.headers,self.target_origin)
        except Denied as e:self.reject(str(e));return
        target=urlsplit(self.target_origin)
        connection=http.client.HTTPConnection(target.hostname,target.port,timeout=2)
        try:
            # No arbitrary target/DNS/Host, credentials, redirect following or proxy environment.
            with self.rate_lock:
                delay=type(self).last_sent+self.minimum_interval-time.monotonic()
                if delay>0:time.sleep(delay)
                connection.request('GET',relative,headers={'Host':target.netloc,'Connection':'close'})
                type(self).last_sent=time.monotonic()
            response=connection.getresponse();data=response.read(1048577)
            if len(data)>1048576:raise ValueError('fixture response too large')
            self.send_response(response.status)
            for k,v in response.getheaders():
                if k.lower() not in ('connection','transfer-encoding','content-length','server','date'):
                    self.send_header(k,v)
            self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            self.record('forwarded',status=response.status)
        except (OSError,ValueError):
            self.record('failed','upstream');self.send_response(502);self.send_header('Content-Length','0');self.end_headers()
        finally:connection.close()
    def do_CONNECT(self):self.reject('scheme')
    def do_POST(self):self.reject('method')
    def do_PUT(self):self.reject('method')
    def do_DELETE(self):self.reject('method')
    def do_PATCH(self):self.reject('method')
    def do_OPTIONS(self):self.reject('method')
    def do_HEAD(self):self.reject('method')
