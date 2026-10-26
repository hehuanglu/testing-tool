#!/usr/bin/env python3
"""Owned W3C driver transport: enforce verified TLS before native crawler navigation.

ZAP Selenium's default requests insecure TLS. This wrapper changes session options,
then verifies the actual driver capability. Product requests and DOM are unmodified.
"""
import hashlib,http.client,json,os,platform,signal,socket,subprocess,sys,time,zipfile
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path

def harden(payload):
    caps=payload.setdefault('capabilities',{});always=caps.setdefault('alwaysMatch',{})
    matches=caps.get('firstMatch',[])
    requested=always.get('acceptInsecureCerts',next((m['acceptInsecureCerts'] for m in matches if 'acceptInsecureCerts' in m),None))
    always['acceptInsecureCerts']=False
    holders=([always] if 'moz:firefoxOptions' in always else matches if any('moz:firefoxOptions' in m for m in matches) else [always])
    for holder in holders:
        options=holder.setdefault('moz:firefoxOptions',{});prefs=options.setdefault('prefs',{})
        prefs.update({'network.proxy.no_proxies_on':'','network.proxy.allow_hijacking_localhost':True,'network.http.http3.enable':False,'network.trr.mode':5,'media.peerconnection.enabled':False,'browser.chrome.site_icons':False})
    for match in matches:match.pop('acceptInsecureCerts',None)
    payload.pop('desiredCapabilities',None)
    return payload,requested

class Relay(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def log_message(self,*a):pass
    def process(self):
        n=int(self.headers.get('Content-Length','0'))
        if n<0 or n>16*1024**2:self.send_error(413);return
        body=self.rfile.read(n);requested=None;new=self.command=='POST' and self.path.rstrip('/')=='/session'
        if new:
            payload,requested=harden(json.loads(body));body=json.dumps(payload).encode()
        c=http.client.HTTPConnection('127.0.0.1',self.server.backend,timeout=90)
        try:
            headers={k:v for k,v in self.headers.items() if k.lower() not in ('content-length','connection','host')};headers['Connection']='close';headers['Content-Length']=str(len(body))
            c.request(self.command,self.path,body,headers);r=c.getresponse();blob=r.read(16*1024**2+1)
            if len(blob)>16*1024**2:raise ValueError('driver response budget')
            if new:
                value=json.loads(blob).get('value',{});cap=value.get('capabilities',{})
                row={'requestedAcceptInsecureCerts':requested,'effectiveAcceptInsecureCerts':cap.get('acceptInsecureCerts'),'status':r.status,'browserName':cap.get('browserName'),'browserVersion':cap.get('browserVersion'),'geckodriverVersion':cap.get('moz:geckodriverVersion'),'driverSha256':self.server.driver_sha,'addonSha256':self.server.addon_sha,'at':time.time()}
                if r.status!=200:row['driverError']={'error':value.get('error'),'message':str(value.get('message'))[:500]}
                file=self.server.evidence/('session-'+str(os.getpid())+'.json');tmp=file.with_suffix('.pending');tmp.write_text(json.dumps(row)+'\n');tmp.chmod(0o600);os.replace(tmp,file)
                if r.status==200 and cap.get('acceptInsecureCerts') is not False:
                    sid=value.get('sessionId')
                    if sid:
                        kill=http.client.HTTPConnection('127.0.0.1',self.server.backend,timeout=3);kill.request('DELETE','/session/'+sid);kill.getresponse().read();kill.close()
                    raise ValueError('driver did not enforce TLS')
            self.send_response_only(r.status)
            for k,v in r.getheaders():
                if k.lower() not in ('content-length','connection','transfer-encoding'):self.send_header(k,v)
            self.send_header('Content-Length',str(len(blob)));self.send_header('Connection','close');self.end_headers();self.wfile.write(blob)
        except Exception:
            self.send_error(502,'Owned driver transport failed closed')
        finally:c.close();self.close_connection=True
    do_GET=do_POST=do_DELETE=process

def main():
    out=Path('/zap/wrk/client-driver');out.mkdir(mode=0o700,exist_ok=True)
    addon=sorted(Path('/zap/plugin').glob('webdriverlinux-release-*.zap'),key=lambda p:int(p.stem.rsplit('-',1)[1]))[-1]
    member='webdriver/linux/'+('arm64' if platform.machine()=='aarch64' else '64')+'/geckodriver'
    with zipfile.ZipFile(addon) as z:binary=z.read(member)
    driver=out/'geckodriver'
    if not driver.exists() or driver.read_bytes()!=binary:driver.write_bytes(binary)
    driver.chmod(0o755)
    args=list(sys.argv[1:])
    if '--version' in args:return subprocess.call([str(driver),'--version'])
    front=4444;rest=[];i=0
    while i<len(args):
        arg=args[i]
        if arg in ('--port','-p','--host'):
            if arg!='--host':front=int(args[i+1])
            i+=2;continue
        if arg.startswith('--port='):front=int(arg.split('=',1)[1]);i+=1;continue
        if arg.startswith('--host='):i+=1;continue
        rest.append(arg);i+=1
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));backend=sock.getsockname()[1]
    args=rest+['--port',str(backend),'--host','127.0.0.1']
    if not Path('/config/zap-root.crt').is_file():raise ValueError('owned ZAP trust absent')
    log=(out/('backend-'+str(os.getpid())+'.log')).open('wb')
    proc=subprocess.Popen([str(driver),*args],stdout=log,stderr=log)
    def stop(*unused):
        proc.terminate();raise SystemExit(0)
    signal.signal(signal.SIGTERM,stop);signal.signal(signal.SIGINT,stop)
    try:
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            if proc.poll() is not None:raise ValueError('driver exited: '+str(proc.returncode))
            with socket.socket() as sock:
                sock.settimeout(.1)
                if sock.connect_ex(('127.0.0.1',backend))==0:break
            time.sleep(.05)
        else:raise TimeoutError('driver did not bind')
        server=ThreadingHTTPServer(('127.0.0.1',front),Relay);server.backend=backend;server.evidence=out;server.driver_sha=hashlib.sha256(binary).hexdigest();server.addon_sha=hashlib.sha256(addon.read_bytes()).hexdigest();server.serve_forever()
    finally:
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
    return 0

if __name__=='__main__':
    try:raise SystemExit(main())
    except Exception:
        import traceback
        out=Path('/zap/wrk/client-driver');out.mkdir(mode=0o700,exist_ok=True)
        (out/('startup-'+str(os.getpid())+'.log')).write_text(traceback.format_exc())
        raise
