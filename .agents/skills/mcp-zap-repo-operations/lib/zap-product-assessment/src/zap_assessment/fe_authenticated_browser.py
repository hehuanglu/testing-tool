"""Finite session-group W3C worker. Credentials are read from private jobs, never printed."""
import hashlib,json,os,platform,socket,subprocess,time,zipfile,shutil
from pathlib import Path
from .fe_anonymous_browser import FEBrowser,ELEMENT
from .ui_webdriver import wait_for,BrowserError
from .fe_authenticated_transport import valid_owned_id
from .fe_authenticated_auth import pointer

EXTRA_PREDICATE="""const p=arguments[0],e=p.selector?document.querySelector(p.selector):null;
if(p.kind==='storageAbsent')return !(p.area==='session'?sessionStorage:localStorage).getItem(p.key);
if(p.kind==='imageLoaded')return !!e&&e.complete&&e.naturalWidth>0;if(p.kind==='checked')return !!e&&e.checked===p.value;if(p.kind==='count')return document.querySelectorAll(p.selector).length===p.value;
if(p.kind==='textAbsent')return !!e&&!e.textContent.includes(p.value);return null;"""
PROBE="""const a=arguments[0],done=arguments[arguments.length-1];const token=localStorage.getItem(a.storageKey)||sessionStorage.getItem(a.storageKey);fetch(a.identity.path,{headers:token?{Authorization:'Bearer '+token}:{},cache:'no-store',credentials:'omit'}).then(async r=>done({status:r.status,body:await r.json(),url:r.url})).catch(()=>done({captureError:true}));"""
EXTRA_SNAPSHOT="""return arguments[0].map(s=>({selector:s,count:document.querySelectorAll(s).length,checked:!!document.querySelector(s)?.checked,imageLoaded:!!document.querySelector(s)?.complete&&document.querySelector(s)?.naturalWidth>0,attributes:document.querySelector(s)?Object.fromEntries(['aria-selected','src','href','datetime'].filter(k=>document.querySelector(s).hasAttribute(k)).map(k=>[k,document.querySelector(s).getAttribute(k)])):{}}));"""
DOM_TEXT="""return arguments[0].map(s=>{const e=document.querySelector(s),t=e?e.textContent:'';return {selector:s,text:t.slice(0,16000),textTruncated:t.length>16000};});"""

class AuthenticatedBrowser(FEBrowser):
    def css(self,selector):
        wait_for(lambda:self.predicate({'kind':'exists','selector':selector}),8)
        return super().css(selector)
    def start(self,profile):
        self.owned_profile=Path(profile).resolve();return super().start(profile)
    def reopen(self):
        profile=self.owned_profile
        if self.session is not None or profile.is_symlink() or not profile.is_dir():raise ValueError('owned closed profile required for reopen')
        return self._start_profile(profile)
    def snapshot(self,selectors):
        if len(selectors)>48:raise ValueError('snapshot selector budget')
        state=super().snapshot(selectors);texts={x['selector']:x for x in self.evaluate(DOM_TEXT,[selectors])}
        for element in state['elements']:element.update(texts[element['selector']])
        facts=self.evaluate(EXTRA_SNAPSHOT,[selectors]);state['selectorFacts']=facts
        for element,fact in zip(state['elements'],facts):element['attributes'].update(fact['attributes'])
        return state
    def predicate(self,p):
        if p['kind'] in ('storageAbsent','checked','count','textAbsent','imageLoaded'):return self.evaluate(EXTRA_PREDICATE,[p])
        return super().predicate(p)
    def step(self,s,origin,fixtures):
        a=s['action']
        if a in ('select','check','uncheck'):
            e=self.css(s['selector'])
            if a=='select':
                value=str(fixtures[s['fixtureField']] if s.get('fixtureField') else s['value'])
                option_selector=s['selector']+' option[value="'+value.replace('\\','\\\\').replace('"','\\"')+'"]'
                wait_for(lambda:self.predicate({'kind':'exists','selector':option_selector}),8)
                option=self.command('POST','/element/'+e+'/element',{'using':'css selector','value':'option[value="'+value.replace('"','\\"')+'"]'})[ELEMENT]
                self.command('POST','/element/'+option+'/click',{})
            elif self.command('GET','/element/'+e+'/selected')!=(a=='check'):self.command('POST','/element/'+e+'/click',{})
        elif a in ('back','forward'):self.command('POST','/'+a,{})
        elif a=='new-tab':
            w=self.command('POST','/window/new',{'type':'tab'});self.command('POST','/window',{'handle':w['handle']});self.command('POST','/url',{'url':origin+s['path'].format_map(fixtures)})
        else:return super().step(s,origin,fixtures)
        if s.get('predicate'):wait_for(lambda:self.predicate(s['predicate']),s.get('seconds',6))

def atomic(path,value):
    p=Path(path);tmp=p.with_suffix('.pending');tmp.write_text(json.dumps(value)+'\n');tmp.chmod(0o644);os.replace(tmp,p)

def run(job):
    root=Path('/browser');case=root/job['group']['id'];case.mkdir(mode=0o700);(root/'home').mkdir(exist_ok=True);(root/'bin').mkdir(exist_ok=True)
    addon=sorted(Path('/zap/plugin').glob('webdriverlinux-release-*.zap'),key=lambda p:int(p.stem.rsplit('-',1)[1]))[-1];member='webdriver/linux/'+('arm64' if platform.machine()=='aarch64' else '64')+'/geckodriver'
    with zipfile.ZipFile(addon) as z:binary=z.read(member)
    driver=root/'bin/geckodriver';driver.write_bytes(binary);driver.chmod(0o755)
    proc=subprocess.Popen([str(driver),'--host','127.0.0.1','--port','4444','--marionette-port','2828','--log','fatal'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);d=AuthenticatedBrowser();results=[];derived=[]
    fixture_maps={ref:{**a.get('fixtures',{}),'username':a['username'],'password':a['password']} for ref,a in job.get('actors',{}).items()}
    group={'sessionGroup':job['group']['id'],'actorRef':job['group']['actorRef'],'startedAt':time.time(),'profileFresh':True,'driverSha256':hashlib.sha256(binary).hexdigest(),'addonSha256':hashlib.sha256(addon.read_bytes()).hexdigest()}
    try:
        def ready():
            with socket.socket() as sock:sock.settimeout(.1);return sock.connect_ex(('127.0.0.1',4444))==0
        wait_for(ready,10);group['browser']=d.start(case/'profile')
        for j in job['journeys']:
            if job.get('actors'):
                job['fixtures']=fixture_maps[j['actorRef']]
            row={'journeyId':j['id'],'sessionGroup':j['sessionGroup'],'actorRef':j['actorRef'],'startedAt':time.time(),'steps':[],'assertions':[],'outcome':'failed'}
            atomic(root/'WAITING.json',{'id':j['id'],'group':j['sessionGroup']})
            def ack():
                probe=root/'PROBE_REQUEST.json'
                try:request=json.loads(probe.read_bytes())
                except (FileNotFoundError,ValueError):request=None
                if request:
                    reply=root/'PROBE_RESPONSE.json'
                    if request.get('group')==j['sessionGroup'] and request.get('actorRef')==j['actorRef'] and (not reply.exists() or json.loads(reply.read_bytes()).get('id')!=request['id']):
                        response=d.command('POST','/execute/async',{'script':PROBE,'args':[job['auth']]})
                        atomic(reply,{'id':request['id'],'actorRef':j['actorRef'],'group':j['sessionGroup'],'at':time.time(),'response':response})
                try:return json.loads((root/'ACK.json').read_bytes()).get('id')==j['id']
                except (FileNotFoundError,ValueError):return False
            wait_for(ack,180)
            control=json.loads((root/'ACK.json').read_bytes())
            if control.get('actorRef') not in (None,j['actorRef']):raise ValueError('controller actor mismatch')
            job['fixtures'].update(control.get('fixtureUpdates',{}))
            if control.get('skip'):
                row.update(outcome='not-run',dependencies=control['skip'],endedAt=time.time());atomic(case/(j['id']+'.json'),row);results.append(row);continue
            try:
                for index,step in enumerate(j['steps']):
                    s=dict(step)
                    if s.get('predicate',{}).get('fixtureField'):s['predicate']={**s['predicate'],'value':job['fixtures'][s['predicate']['fixtureField']]}
                    start=time.time();extra={}
                    if s['action']=='identity-probe':extra['identityProbe']=d.command('POST','/execute/async',{'script':PROBE,'args':[job['auth']]})
                    elif s['action']=='post-state':
                        auth={**job['auth'],'identity':{**job['auth']['identity'],'path':s['path'].format_map(job['fixtures'])}}
                        response=d.command('POST','/execute/async',{'script':PROBE,'args':[auth]})
                        expected=job['fixtures'][s['expectedFixture']] if s.get('expectedFixture') else s['expectedValue']
                        extra['postState']={'response':response,'pointer':s['pointer'],'expected':expected}
                        if response.get('status')!=200:raise ValueError('owned post-state unavailable; no mutation replay')
                        if pointer(response['body'],s['pointer'])!=expected:row.setdefault('productMismatches',[]).append({'stepIndex':index,'kind':'post-state','pointer':s['pointer']})
                    elif s['action']=='readback':
                        auth={**job['auth'],'identity':{**job['auth']['identity'],'path':s['path'].format_map(job['fixtures'])}}
                        response=d.command('POST','/execute/async',{'script':PROBE,'args':[auth]})
                        if response.get('status')!=200:raise ValueError('owned readback unavailable; no mutation replay')
                        values=pointer(response['body'],s['pointer']);values=values if isinstance(values,list) else [values]
                        if s.get('matchPointer'):values=[v for v in values if pointer(v,s['matchPointer'])==job['fixtures'][s['matchFixture']]]
                        if len(values)!=1:raise ValueError('owned readback binding ambiguous')
                        value=pointer(values[0],s['valuePointer'])
                        if not valid_owned_id(value,s.get('idFormat','integer')):raise ValueError('owned ID format mismatch')
                        if s['fixtureField'] in job['fixtures'] and job['fixtures'][s['fixtureField']]!=value:raise ValueError('owned ID binding changed')
                        job['fixtures'][s['fixtureField']]=value;extra['readback']=response
                        derived.append({'journeyId':j['id'],'stepIndex':index,'actorRef':j['actorRef'],'field':s['fixtureField'],'value':value,'path':auth['identity']['path'],'pointer':s['pointer'],'valuePointer':s['valuePointer'],'matchPointer':s.get('matchPointer'),'matchFixture':s.get('matchFixture'),'response':response})
                        atomic(case/'FIXTURE_BINDINGS.json',derived)
                        stamp=hashlib.sha256((case/'FIXTURE_BINDINGS.json').read_bytes()).hexdigest()
                        def bound():
                            try:return json.loads((root/'BINDINGS_ACK.json').read_bytes())=={'group':j['sessionGroup'],'sha256':stamp}
                            except (FileNotFoundError,ValueError):return False
                        wait_for(bound,20)
                    elif s['action']=='reopen':
                        d.close();extra['reopenedBrowser']=d.reopen();d.command('POST','/url',{'url':job['origin']+s['path'].format_map(job['fixtures'])})
                    elif s['action']=='logout-boundary':pass
                    else:d.step(s,job['origin'],job['fixtures'])
                    if s['action'] in ('reopen','identity-probe','readback','post-state') and s.get('predicate'):wait_for(lambda:d.predicate(s['predicate']),s.get('seconds',6))
                    selectors=sorted({p['selector'] for p in j['expectedUi'] if p.get('selector')}|{s['selector']} if s.get('selector') else {p['selector'] for p in j['expectedUi'] if p.get('selector')})
                    if s.get('predicate',{}).get('selector'):selectors=sorted(set(selectors)|{s['predicate']['selector']})
                    state=d.snapshot(selectors);state['selectorFacts']=d.evaluate(EXTRA_SNAPSHOT,[selectors]);image='step-'+str(len(results))+'-'+str(index)+'.png'
                    shot=d.capture(case/image);row['steps'].append({'index':index,'action':s['action'],'actionSpec':s,'startedAt':start,'endedAt':time.time(),'state':state,'screenshot':{'path':str(case/image),'sha256':shot['sha256']},**extra})
                for p in j['expectedUi']:
                    p=dict(p)
                    if p.get('fixtureField'):p['value']=job['fixtures'][p['fixtureField']]
                    try:passed=wait_for(lambda:d.predicate(p),p.get('seconds',6))
                    except BrowserError as e:
                        if str(e)!='ui_deadline':raise
                        passed=False;row.setdefault('productMismatches',[]).append({'kind':'ui','predicate':p})
                    row['assertions'].append({'predicate':p,'passed':bool(passed)})
                row['finalState']=d.snapshot(sorted({p['selector'] for p in j['expectedUi'] if p.get('selector')}));row['outcome']='assertion-mismatch' if row.get('productMismatches') else 'observed'
            except Exception as e:
                row.update(errorType=type(e).__name__,errorCode=str(e)[:100] if isinstance(e,(BrowserError,ValueError)) else 'private-details-omitted')
                if isinstance(e,BrowserError):row.update(errorCategory=e.category,errorCause=e.cause)
                try:row['failureState']=d.snapshot(['body'])
                except Exception:pass
            row['endedAt']=time.time();atomic(case/(j['id']+'.json'),row);results.append(row)
            if row['outcome']=='failed':break
    except Exception as e:
        import traceback
        group.update(errorType=type(e).__name__,errorCode=str(e)[:100] if isinstance(e,(BrowserError,ValueError)) else 'private-details-omitted',errorFrames=[{'file':Path(frame.filename).name,'line':frame.lineno,'function':frame.name} for frame in traceback.extract_tb(e.__traceback__)])
    finally:
        try:d.close();group['profileClosed']=True
        except Exception:group['profileClosed']=False
        proc.terminate()
        try:proc.wait(timeout=5)
        except subprocess.TimeoutExpired:proc.kill();proc.wait(timeout=5)
        profile=case/'profile'
        if group.get('profileClosed') and profile.is_dir() and not profile.is_symlink() and profile.resolve().parent==case.resolve():
            inventory=[{'path':str(f.relative_to(profile)),'sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'bytes':f.stat().st_size} for f in profile.rglob('*') if f.is_file() and not f.is_symlink()]
            atomic(case/'PROFILE_DISPOSAL.json',{'ownedGroup':job['group']['id'],'closed':True,'files':inventory});shutil.rmtree(profile);group['profileDisposed']=True
        group.update(endedAt=time.time(),journeyIds=[r['journeyId'] for r in results]);atomic(case/'GROUP.json',group)
    return group

if __name__=='__main__':
    import sys
    run(json.loads(Path(sys.argv[1]).read_bytes()))
