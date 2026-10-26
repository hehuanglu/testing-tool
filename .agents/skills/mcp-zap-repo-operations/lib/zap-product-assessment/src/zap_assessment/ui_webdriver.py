"""Small stdlib W3C WebDriver client for the already pinned Firefox image.

No browser command/request/exception payload containing credentials is persisted.
Only registered selectors and read-only DOM snapshot scripts are used.
"""
import base64
import hashlib
import http.client
import json
from pathlib import Path
import time
import threading


class BrowserError(Exception):
    def __init__(self,reason,category=None,cause=None):
        super().__init__(reason);self.category=category;self.cause=cause


class WebDriver:
    def __init__(self,port=4444):self.port=port;self.session=None
    def command(self,method,path,payload=None,session=True):
        connection=http.client.HTTPConnection('127.0.0.1',self.port,timeout=12)
        try:
            prefix='/session/'+self.session if session else ''
            raw=json.dumps(payload).encode() if payload is not None else None
            connection.request(method,prefix+path,raw,{'Content-Type':'application/json'})
            response=connection.getresponse();blob=response.read(1024*1024+1)
            if len(blob)>1024*1024:raise BrowserError('webdriver_response_budget')
            data=json.loads(blob)
            if response.status>=400 or isinstance(data.get('value'),dict) and data['value'].get('error'):
                value=data.get('value') if isinstance(data.get('value'),dict) else {}
                allowed={'unknown error','timeout','no such element','invalid session id','session not created','no such window','invalid argument','javascript error','stale element reference','unsupported operation'}
                category=value.get('error') if value.get('error') in allowed else 'other'
                # Emit only known categories, never raw messages/command values.
                message=value.get('message','');cause=None
                for label,fragment in [('network-error-page','about:neterror'),('marionette-response','Failed to decode response from marionette'),('browser-process-closed','Process unexpectedly closed'),('browsing-context-discarded','Browsing context has been discarded')]:
                    if fragment in message:cause=label;break
                raise BrowserError('webdriver_command_failed',category,cause)
            return data['value']
        except (OSError,ValueError,http.client.HTTPException):raise BrowserError('webdriver_transport_failed') from None
        finally:connection.close()
    def start(self,profile):
        value=self.command('POST','/session',{'capabilities':{'alwaysMatch':{'browserName':'firefox',
            'moz:firefoxOptions':{'args':['-headless','-profile',str(profile)],'prefs':{
            'signon.rememberSignons':False,'browser.cache.disk.enable':False,
            'browser.shell.checkDefaultBrowser':False,'datareporting.policy.dataSubmissionEnabled':False,
            'toolkit.telemetry.enabled':False,'browser.startup.page':0,'browser.sessionstore.interval':1000,
            'browser.aboutwelcome.enabled':False,'browser.newtabpage.enabled':False,
            'browser.startup.homepage_override.mstone':'ignore',
            'startup.homepage_welcome_url':'about:blank','startup.homepage_welcome_url.additional':''}}}}},False)
        self.session=value['sessionId'];self.command('POST','/timeouts',{'implicit':0,'pageLoad':12000,'script':3000})
        def initial_document_ready():
            handles=self.command('GET','/window/handles')
            if not handles:return False
            try:
                self.command('POST','/window',{'handle':handles[0]})
                return self.script('return document.readyState')=='complete'
            except BrowserError as exc:
                if exc.category=='no such window':return False
                raise
        wait_for(initial_document_ready,5)
        # Select an owned context once before any target/business navigation.
        context=self.command('POST','/window/new',{'type':'tab'})
        self.command('POST','/window',{'handle':context['handle']})
        return {'browserName':value['capabilities']['browserName'],'browserVersion':value['capabilities']['browserVersion'],
                'geckodriverVersion':value['capabilities'].get('moz:geckodriverVersion'),'profilePath':str(profile),
                'startupContextPolicy':'explicit-new-tab-before-target-navigation'}
    def element(self,test_id):
        value=self.command('POST','/element',{'using':'css selector','value':'[data-testid="'+test_id+'"]'})
        return value['element-6066-11e4-a52e-4f735466cecf']
    def fill(self,test_id,value):
        element=self.element(test_id);self.command('POST','/element/'+element+'/clear',{})
        self.command('POST','/element/'+element+'/value',{'text':str(value)})
    def click(self,test_id):self.command('POST','/element/'+self.element(test_id)+'/click',{})
    def script(self,source):return self.command('POST','/execute/sync',{'script':source,'args':[]})
    def snapshot(self):return self.script('return window.w7Snapshot ? window.w7Snapshot() : null')
    def screenshot(self,path):
        encoded=self.command('GET','/element/'+self.element('summary')+'/screenshot')
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>256*1024 or not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise BrowserError('screenshot_budget_or_format')
        Path(path).write_bytes(raw);return {'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),'scope':'summary-element-only-no-login-form'}
    def close(self):
        if self.session:
            try:self.command('DELETE','',None)
            finally:self.session=None


def wait_for(predicate,seconds=5):
    deadline=time.monotonic()+seconds
    while True:
        result=predicate()
        if result:return result
        remaining=deadline-time.monotonic()
        if remaining<=0:raise BrowserError('ui_deadline')
        # Polling delay only; success comes from DOM/response predicate, not elapsed time.
        threading.Event().wait(min(.05,remaining))
