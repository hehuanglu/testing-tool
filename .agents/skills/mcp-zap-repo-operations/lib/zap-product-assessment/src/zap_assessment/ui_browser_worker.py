"""Actual isolated Firefox UI worker and private in-container canary audit."""
import copy
import hashlib
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import platform
import sqlite3
import subprocess
import sys
import threading
import zipfile
from .ui_fixture import UIProduct,UIHandler
from .ui_webdriver import WebDriver,BrowserError,wait_for
from .opaque_canary import source_controls,OpaqueCanaryAuditor

RUN_STAGE='initializing'


def stage(value):
    global RUN_STAGE
    RUN_STAGE=value


class OwnedUIServer(ThreadingHTTPServer):
    """Browser idle preconnects must not block the document or fetch requests."""
    daemon_threads=True
    def get_request(self):
        connection,address=super().get_request();connection.settimeout(3)
        return connection,address


def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':')).encode()
def sha_file(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def profile_audit(root,canaries):
    source=source_controls(canaries);auditor=OpaqueCanaryAuditor(source['fingerprints']);rows=[];matches=0;unknown=0
    for p in sorted(Path(root).rglob('*')):
        if not p.is_file() or p.is_symlink():continue
        size=p.stat().st_size;readers=[];hit=False
        if size>8*1024*1024:
            unknown+=1;readers.append('oversize-unproven')
        else:
            raw=p.read_bytes();hit=auditor.matches(raw);readers.append('bounded-raw-encoding-scan')
            if raw.startswith(b'SQLite format 3\x00'):
                try:
                    connection=sqlite3.connect('file:'+str(p)+'?mode=ro&immutable=1',uri=True)
                    try:
                        tables=connection.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall();count=0
                        for (table,) in tables:
                            if not table.replace('_','').isalnum():raise ValueError('unsupported_table')
                            for values in connection.execute('SELECT * FROM "'+table+'"'):
                                count+=1
                                if count>100000:raise ValueError('cell_budget')
                                for cell in values:
                                    if isinstance(cell,str):hit|=auditor.matches(cell.encode())
                                    elif isinstance(cell,bytes):
                                        if len(cell)>8*1024*1024:raise ValueError('blob_budget')
                                        hit|=auditor.matches(cell)
                                        try:hit|=auditor.matches(cell.decode('utf-16-le').encode())
                                        except UnicodeError:pass
                        readers.append('sqlite-readonly-cells-utf8-utf16le')
                    finally:connection.close()
                except (sqlite3.Error,ValueError):unknown+=1;readers.append('sqlite-decoder-incomplete')
            if p.name.endswith('-wal') and size:unknown+=1;readers.append('wal-lifecycle-unproven')
        if hit:matches+=1
        rows.append({'path':str(p.relative_to(root)),'bytes':size,'sha256':sha_file(p),'matched':bool(hit),'readers':readers})
    return {'scope':'browser-profile-diagnostic-only','profileMatches':matches,'profileVerdict':'fail' if matches else 'blocked',
            'fingerprints':source['fingerprints'],'sourceValuesIncluded':False,'sourceControlTests':source['controls']['tested'],
            'sourceControlMisses':source['controls']['missed'],'unknownReaderCount':unknown,'profileFiles':rows,
            'requiredOperationalPairs':143,'operationalG3':'blocked','browserClosedBeforeAudit':True,
            'limitations':['Actual native-style localStorage persistence control only; no full operational sink/lifecycle gate.',
                           'No claim of comprehensive compressed browser storage, dumps, swap or crash lifecycle decoding.']}


def run(job):
    stage('prepare-browser')
    root=Path('/work');(root/'bin').mkdir();(root/'state').mkdir();(root/'screens').mkdir()
    addon=Path('/zap/plugin/webdriverlinux-release-228.zap')
    member='webdriver/linux/'+('arm64' if platform.machine()=='aarch64' else '64')+'/geckodriver'
    with zipfile.ZipFile(addon) as archive:binary=archive.read(member)
    driver_path=root/'bin/geckodriver';driver_path.write_bytes(binary);driver_path.chmod(0o755)
    profile=Path('/home/zap/w7-profile');profile.mkdir(mode=0o700,exist_ok=False)
    product=UIProduct(job['fixture'],job['config'],root/'state',job['plan']['fault'])
    server=OwnedUIServer(('127.0.0.1',18080),UIHandler);server.product=product
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    driver_process=subprocess.Popen([str(driver_path),'--host','127.0.0.1','--port','4444','--marionette-port','2828','--log','fatal'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    driver=WebDriver();rows=[];screens=[];version=None;cleanup_error=False
    try:
        stage('wait-driver')
        wait_for(lambda: driver_process.poll() is None and __import__('socket').socket().connect_ex(('127.0.0.1',4444))==0,10)
        stage('start-session')
        version=driver.start(profile)
        stage('navigate-fixture')
        driver.command('POST','/url',{'url':'http://127.0.0.1:18080/ui'})
        wait_for(lambda:driver.snapshot() is not None)
        for spec in job['plan']['steps']:
            stage('ui-step')
            before=json.loads((root/'state/state.json').read_text());start=len(product.arrivals);prior=driver.snapshot();commands=[];navigation='none';error=None
            def fill(label,field,value):driver.fill(field,value);commands.append(label)
            def click(label,field):driver.click(field);commands.append(label)
            try:
                action=spec['action'];config=job['config']
                if action=='login':
                    actor=spec['actorRef'];fill('fill-email','email',config['actors'][actor]['email'])
                    fill('fill-password-private','password',product.passwords[actor]);click('click-sign-in','sign-in')
                elif action=='logout':click('click-logout','logout')
                elif action=='create':
                    fill('fill-account-name','account-name',config['accountName']);fill('fill-opening-balance','opening-balance',config['openingBalance']);click('click-create','create')
                elif action=='expense':
                    fill('fill-account-id','account-id',config['accountId']);fill('fill-amount','amount',spec['case']['input']['amount']);click('click-expense','expense')
                elif action=='update':
                    fill('fill-account-id','account-id',config['accountId']);fill('fill-update-name','update-name',spec['case']['input']['name']);fill('fill-update-balance','update-balance',spec['case']['input']['balance']);click('click-update','update')
                elif action=='read':fill('fill-account-id','account-id',config['accountId']);click('click-read','read')
                elif action=='reload':driver.command('POST','/refresh',{});commands.append('webdriver-refresh');navigation='webdriver-refresh'
                else:raise BrowserError('unknown_ui_action')
                if action=='reload':
                    wait_for(lambda:driver.snapshot() and driver.snapshot()['requestId']!=prior['requestId'] and driver.snapshot()['complete']>0,5)
                else:wait_for(lambda:driver.snapshot() and driver.snapshot()['complete']>prior['complete'],5)
            except BrowserError as exc:error=str(exc)
            dom=driver.snapshot() or {'actorRef':'anonymous','subject':'','requestId':'','status':0,'loginVisible':True,'passwordCleared':False,'accountId':'','balance':'','alertPresent':True,'complete':0}
            # Snapshot schema deliberately contains no password/token/HTML/console fields.
            row={'stepId':spec['stepId'],'actorRef':spec['actorRef'],'action':spec['action'],'commandKinds':commands,
                 'navigation':navigation,'requestIds':[r['requestId'] for r in product.arrivals[start:]],'dom':dom,
                 'preState':before,'postState':json.loads((root/'state/state.json').read_text()),'errorCode':error}
            rows.append(row)
            if spec['stepId']=='balance-after-reload' and not error and not dom['alertPresent']:
                meta=driver.screenshot(root/'screens/balance-after-reload.png');screens.append({'path':'balance-after-reload.png',**meta})
            if error:break
    finally:
        if sys.exc_info()[0] is None:stage('close-browser')
        try:driver.close()
        except BrowserError:cleanup_error=True
        driver_process.terminate()
        try:driver_process.wait(timeout=5)
        except subprocess.TimeoutExpired:driver_process.kill();driver_process.wait(timeout=5)
        server.shutdown();server.server_close();thread.join()
    stage('audit-profile');audit=profile_audit('/home/zap',product.canaries())
    result={'steps':rows,'arrivals':product.arrivals,'secretAudit':audit,'screenshots':screens,
            'browser':version,'browserCleanupError':cleanup_error,
            'driverPin':{'addon':str(addon),'addonSha256':sha_file(addon),'member':member,'driverSha256':hashlib.sha256(binary).hexdigest()}}
    if job['plan'].get('unifiedBinding'):result['unifiedBinding']=job['plan']['unifiedBinding']
    # Verify minimized export against private comparisons before stdout leaves the container.
    if OpaqueCanaryAuditor(audit['fingerprints']).matches(encode(result)):
        raise ValueError('private_canary_in_minimized_export')
    return result


if __name__=='__main__':
    try:
        result=run(json.loads(Path('/job.json').read_text()));Path('/work/result.json').write_bytes(encode(result));print(json.dumps({'workerCompleted':True,'steps':len(result['steps'])}),flush=True);threading.Event().wait(900)
    except Exception as exc:
        # Raw WebDriver messages, command values and browser diagnostics stay private.
        allowed={'webdriver_response_budget','webdriver_command_failed','webdriver_transport_failed','ui_deadline','screenshot_budget_or_format'}
        reason=str(exc) if isinstance(exc,BrowserError) and str(exc) in allowed else 'private-details-omitted'
        counters={}
        for name in ('pids.current','pids.peak','pids.events','memory.events'):
            try:counters[name]=Path('/sys/fs/cgroup',name).read_text().strip()
            except OSError:counters[name]='unavailable'
        print(json.dumps({'workerCompleted':False,'errorType':type(exc).__name__,'stage':RUN_STAGE,'reasonCode':reason,
                          'driverCategory':getattr(exc,'category',None),'driverCause':getattr(exc,'cause',None),'cgroupCounters':counters}));raise SystemExit(2)
