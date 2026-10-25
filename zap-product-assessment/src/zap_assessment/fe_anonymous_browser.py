"""Generic finite WebDriver worker. Code-owned probes; selectors/facts from pinned recipe."""
import base64
import hashlib
import json
from pathlib import Path
import platform
import socket
import subprocess
import shutil
import sys
import time
import zipfile
from .ui_webdriver import WebDriver,wait_for,BrowserError

ELEMENT='element-6066-11e4-a52e-4f735466cecf'
# Input values, storage values and document scripts never leave this probe.
SNAPSHOT='''const selectors=arguments[0];return {url:location.href,ready:document.readyState,secure:window.isSecureContext,
 storageKeys:Object.keys(localStorage),sessionKeys:Object.keys(sessionStorage),cookieNames:document.cookie.split(';').filter(Boolean).map(x=>x.split('=')[0].trim()),
 serviceWorkerControlled:!!navigator.serviceWorker.controller,
 elements:selectors.map(s=>{const e=document.querySelector(s);return {selector:s,exists:!!e,text:e?e.textContent.slice(0,300):'',disabled:e?!!e.disabled:false,valid:e&&e.validity?e.validity.valid:null,type:e?e.type:null,valueLength:e&&typeof e.value==='string'?e.value.length:null,attributes:e?Object.fromEntries(e.getAttributeNames().filter(k=>['type','aria-disabled','aria-invalid','autocomplete','disabled','maxlength','required','role'].includes(k)).map(k=>[k,e.getAttribute(k)])): {}}})}'''
STATE='''const done=arguments[arguments.length-1];Promise.all([caches.keys(),navigator.serviceWorker.getRegistrations(),indexedDB.databases?indexedDB.databases():Promise.resolve(null)]).then(([c,s,d])=>done({cacheNames:c,serviceWorkerRegistrations:s.length,indexedDBNames:d===null?null:d.map(x=>x.name)})).catch(()=>done({captureError:true}));'''
PREDICATE='''const p=arguments[0];const e=p.selector?document.querySelector(p.selector):null;
 if(p.kind==='valueLength')return !!e&&e.value.length===p.value;if(p.kind==='exists')return !!e;if(p.kind==='absent')return !e;if(p.kind==='text')return !!e&&e.textContent.includes(p.value);
 if(p.kind==='urlPath')return location.pathname===p.value;if(p.kind==='invalid')return !!e&&e.validity&&!e.validity.valid;
 if(p.kind==='disabled')return !!e&&e.disabled;if(p.kind==='attribute')return !!e&&e.getAttribute(p.attribute)===p.value;if(p.kind==='storagePresent')return Object.keys(p.area==='session'?sessionStorage:localStorage).includes(p.key);
 if(p.kind==='ready')return document.readyState==='complete';return false;'''

class FEBrowser(WebDriver):
    def start(self,profile):
        if Path(profile).exists():raise ValueError('stale browser profile')
        Path(profile).mkdir(mode=0o700)
        return self._start_profile(profile)
    def _start_profile(self,profile):
        prefs={'network.proxy.type':1,'network.proxy.http':'127.0.0.1','network.proxy.http_port':8090,'network.proxy.ssl':'127.0.0.1','network.proxy.ssl_port':8090,'network.proxy.no_proxies_on':'','network.proxy.allow_hijacking_localhost':True,
          'network.http.http3.enable':False,'network.trr.mode':5,'network.dns.disablePrefetch':True,'network.prefetch-next':False,'browser.cache.disk.enable':False,'signon.rememberSignons':False,'browser.shell.checkDefaultBrowser':False,
          'datareporting.policy.dataSubmissionEnabled':False,'toolkit.telemetry.enabled':False,'browser.startup.page':0,'browser.aboutwelcome.enabled':False,'browser.newtabpage.enabled':False,'browser.startup.homepage_override.mstone':'ignore',
          'startup.homepage_welcome_url':'about:blank','startup.homepage_welcome_url.additional':'','media.peerconnection.enabled':False,'browser.chrome.site_icons':False}
        v=self.command('POST','/session',{'capabilities':{'alwaysMatch':{'browserName':'firefox','acceptInsecureCerts':False,'moz:firefoxOptions':{'args':['-headless','-profile',str(profile)],'prefs':prefs}}}},False)
        self.session=v['sessionId'];self.command('POST','/timeouts',{'implicit':0,'pageLoad':12000,'script':5000})
        wait_for(lambda:bool(self.command('GET','/window/handles')),6)
        w=self.command('POST','/window/new',{'type':'tab'});self.command('POST','/window',{'handle':w['handle']})
        return {k:v['capabilities'].get(k) for k in ('browserName','browserVersion','moz:geckodriverVersion','acceptInsecureCerts')}
    def css(self,selector):return self.command('POST','/element',{'using':'css selector','value':selector})[ELEMENT]
    def evaluate(self,script,args):return self.command('POST','/execute/sync',{'script':script,'args':args})
    def snapshot(self,selectors):
        value=self.evaluate(SNAPSHOT,[selectors]);value['cookieNames']=[c['name'] for c in self.command('GET','/cookie')];value['extendedState']=self.command('POST','/execute/async',{'script':STATE,'args':[]});return value
    def predicate(self,p):return self.evaluate(PREDICATE,[p])
    def step(self,s,origin,fixtures):
        a=s['action']
        if a=='navigate':self.command('POST','/url',{'url':origin+s['path'].format_map(fixtures)})
        elif a=='reload':self.command('POST','/refresh',{})
        elif a=='fill':
            e=self.css(s['selector']);self.command('POST','/element/'+e+'/clear',{});value=fixtures[s['fixtureField']] if s.get('fixtureField') else s['value'];self.command('POST','/element/'+e+'/value',{'text':value})
        elif a in ('click','submit'):self.command('POST','/element/'+self.css(s['selector'])+'/click',{})
        elif a!='wait':raise ValueError('unknown browser action')
        if s.get('predicate'):wait_for(lambda:self.predicate(s['predicate']),s.get('seconds',6))
    def capture(self,path):
        raw=base64.b64decode(self.command('GET','/screenshot'),validate=True)
        if len(raw)>2*1024**2 or not raw.startswith(b'\x89PNG'):raise ValueError('screenshot budget/format')
        Path(path).write_bytes(raw);return {'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)}

def run(job):
    root=Path('/browser');(root/'home').mkdir(exist_ok=True);(root/'bin').mkdir(exist_ok=True)
    addons=sorted(Path('/zap/plugin').glob('webdriverlinux-release-*.zap'),key=lambda p:int(p.stem.rsplit('-',1)[1]));addon=addons[-1]
    member='webdriver/linux/'+('arm64' if platform.machine()=='aarch64' else '64')+'/geckodriver'
    with zipfile.ZipFile(addon) as z:binary=z.read(member)
    path=root/'bin/geckodriver';path.write_bytes(binary);path.chmod(0o755)
    j=job['journey'];case=root/j['id'];case.mkdir(mode=0o700)
    result={'journeyId':j['id'],'caseStartedAt':time.time(),'profileFresh':True,'steps':[],'assertions':[],'outcome':'failed','driverPin':{'addonSha256':hashlib.sha256(addon.read_bytes()).hexdigest(),'member':member,'sha256':hashlib.sha256(binary).hexdigest()}}
    proc=subprocess.Popen([str(path),'--host','127.0.0.1','--port','4444','--marionette-port','2828','--log','fatal'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);d=FEBrowser()
    try:
        def ready():
            with socket.socket() as s:s.settimeout(.1);return s.connect_ex(('127.0.0.1',4444))==0
        wait_for(ready,10);result['browser']=d.start(case/'profile')
        selectors=sorted({p['selector'] for p in j['expected'] if p.get('selector')}|{s['selector'] for s in j['steps'] if s.get('selector')})
        for index,step in enumerate(j['steps']):
            row={'index':index,'action':step['action'],'startedAt':time.time()}
            d.step(step,job['origin'],job.get('fixtures',{}));row['endedAt']=time.time();row['url']=d.command('GET','/url');result['steps'].append(row)
            if index==0:
                initial=d.snapshot([]);result['initialState']=initial
                if initial['storageKeys'] or initial['sessionKeys'] or set(initial['cookieNames'])-set(job.get('anonymousCookieNames',[])) or initial['serviceWorkerControlled'] or initial['extendedState'].get('captureError') or initial['extendedState'].get('cacheNames') or initial['extendedState'].get('serviceWorkerRegistrations') or initial['extendedState'].get('indexedDBNames'):raise ValueError('initial identity/state not empty')
        for p in j['expected']:
            passed=wait_for(lambda:d.predicate(p),p.get('seconds',6));result['assertions'].append({'predicate':p,'passed':bool(passed)})
        result['finalState']=d.snapshot(selectors)
        if not result['finalState']['secure']:raise ValueError('not secure context')
        result['screenshot']=d.capture(case/'screen.png');result['outcome']='observed'
    except Exception as exc:
        result['errorType']=type(exc).__name__;result['errorCode']=str(exc)[:100] if isinstance(exc,(BrowserError,ValueError)) else 'private-details-omitted'
        result['driverCategory']=getattr(exc,'category',None);result['driverCause']=getattr(exc,'cause',None)
        try:result['failureScreenshot']=d.capture(case/'failure.png')
        except Exception:pass
    finally:
        try:d.close();result['profileClosed']=True
        except Exception:result['profileClosed']=False
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        result['caseEndedAt']=time.time()
        profile=case/'profile'
        if result.get('profileClosed') and profile.is_dir() and not profile.is_symlink() and profile.resolve().parent==case.resolve():
            inventory=[]
            for f in sorted(profile.rglob('*')):
                if f.is_file() and not f.is_symlink():inventory.append({'path':str(f.relative_to(profile)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()})
            (case/'PROFILE_DISPOSAL.json').write_text(json.dumps({'ownedProfile':str(profile),'freshlyCreatedByWorker':True,'closedBeforeDisposal':True,'files':inventory,'retention':'disposable browser state after minimized state/screenshot/traffic capture; raw native reports remain private'},indent=2)+'\n')
            shutil.rmtree(profile);result['profileDisposed']=True
        (case/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    result=run(json.loads(Path(sys.argv[1]).read_bytes()));print(json.dumps({'journeyId':result['journeyId'],'outcome':result['outcome'],'errorCode':result.get('errorCode')}));raise SystemExit(0 if result['outcome']=='observed' else 2)
