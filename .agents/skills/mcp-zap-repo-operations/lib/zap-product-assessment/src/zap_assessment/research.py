"""Explicit native research admission and MCP orchestration (strict P0 unchanged).

Reuses the upstream CI MCP client, response parsers and completion semantics. Native
ZAP owns scanning; this module owns plan binding, monitoring, journal and readback.
"""
from __future__ import annotations
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import threading
import time
import urllib.parse
import urllib.error
import urllib.request

PROFILE = 'be-authenticated-research/1.0'
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BUNDLED_ROOT = PACKAGE_ROOT.parent
# Legacy product adapters use an explicitly selected workspace, never the skill folder.
WORKSPACE = Path(os.environ.get('ZAP_PRODUCT_WORKSPACE', os.getcwd())).resolve()
_spec = importlib.util.spec_from_file_location('research_ci_helpers', BUNDLED_ROOT/'mcp-zap-server/.github/actions/zap-security-gate/mcp_zap_gate.py')
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)


def write_json(path, value):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(value, indent=2, ensure_ascii=False)+'\n').encode()
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'wb') as f: f.write(data)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def admit(plan, live_binding):
    """Independent versioned entry, never a label overriding require_p0_mode."""
    if plan.get('schemaVersion') in ('research-plan/2.0','research-plan/2.1'):
        from .discovery import validate_plan
        return validate_plan(plan, live_binding)
    from jsonschema import Draft202012Validator
    schema=json.loads((PACKAGE_ROOT/'schemas/be-authenticated-research-plan-v1.schema.json').read_text())
    if not Draft202012Validator(schema).is_valid(plan):raise ValueError('invalid research plan schema')
    if plan.get('assuranceProfile') != PROFILE or plan.get('secretPersistenceAccepted') is not True:
        raise ValueError('explicit research contract required')
    if plan.get('environment') != 'finalsource-zap-test' or not plan.get('authority', {}).get('fixtureActiveAuthorized'):
        raise ValueError('test target and fixture/active authority required')
    if plan.get('targetBinding') != live_binding:
        raise ValueError('target binding drift')
    if plan.get('jobStore') != 'in-memory' or plan.get('coordinator') != 'single-node':
        raise ValueError('research JSON bearer requires direct topology')
    if not plan.get('operations') or not plan.get('ruleIds') or not plan.get('actorSubject'):
        raise ValueError('locked operations/rules/actor required')
    for operation in plan['operations']:
        if operation['method'] not in ('GET','POST','PUT','DELETE') or not operation['path'].startswith('/api/v1/'):
            raise ValueError('operation outside research API scope')
        if operation['method'] != 'GET' and operation.get('fixtureOwned') is not True:
            raise ValueError('mutation must bind owned fixtures')
    if not 0 < plan['limits']['monitorIntervalSeconds'] <= 2 or plan['limits']['stopDeadlineSeconds'] > 10:
        raise ValueError('invalid auth monitor limits')
    return plan


class ZapApi:
    def __init__(self, url, key, output):
        self.url=url; self.key=key; self.output=Path(output); self.counter=0
    def call(self, component, category, name, **params):
        encoded=urllib.parse.urlencode({'apikey':self.key,**params}).encode()
        request=urllib.request.Request(f'{self.url}/JSON/{component}/{category}/{name}/', data=encoded,headers={'Host':'zap'})
        try:
            response=urllib.request.urlopen(request, timeout=12)
        except urllib.error.HTTPError as error:
            response=error
        with response as r:
            blob=r.read(32*1024*1024+1)
        if len(blob)>32*1024*1024: raise ValueError('ZAP response too large')
        result=json.loads(blob)
        self.counter+=1
        write_json(self.output/f'{self.counter:05d}-{component}-{name}.json',result)
        if isinstance(result,dict) and 'code' in result and 'message' in result:
            raise RuntimeError('ZAP API error: '+result['code'])
        return result


class ResearchRun:
    def __init__(self, *, plan, binding, client, monitor_client, zap, output, clock=time.monotonic, identity_validator=None):
        admit(plan,binding())
        self.plan=copy.deepcopy(plan);self.binding=binding;self.client=client;self.monitor_client=monitor_client
        self.zap=zap;self.out=Path(output);self.clock=clock;self.identity_validator=identity_validator;self.native_context=None
        self.out.mkdir(mode=0o700,parents=True,exist_ok=True)
        self.session=None;self.operations=[];self.lost=threading.Event();self.done=threading.Event()
        self.lock=threading.RLock();self.auth_samples=[];self.stop_records=[];self.thread=None
        self.plan_path=self.out/'plan.json';write_json(self.plan_path,plan);self.plan_digest=digest(self.plan_path)
        self.memory_plan_digest=hashlib.sha256(json.dumps(self.plan,sort_keys=True).encode()).hexdigest()
        self.event('plan-locked',sha256=self.plan_digest)
    def event(self, event_type, **fields):
        with self.lock:
            with (self.out/'journal.jsonl').open('a') as f:
                f.write(json.dumps({'event':event_type,'at':time.time(),'monotonic':self.clock(),**fields})+'\n')
    def tool(self, name, args, client=None):
        self.event('mcp-intent',tool=name,arguments=args)
        result=(client or self.client).call_tool(name,args)
        self.event('mcp-response',tool=name,result=result)
        return result
    def current(self):
        if self.lost.is_set():raise RuntimeError('auth continuity lost; new work forbidden')
        if digest(self.plan_path)!=self.plan_digest:raise RuntimeError('locked plan changed')
        if hashlib.sha256(json.dumps(self.plan,sort_keys=True).encode()).hexdigest()!=self.memory_plan_digest:raise RuntimeError('in-memory locked plan changed')
        admit(self.plan,self.binding())
        if os.statvfs(self.out).f_bavail*os.statvfs(self.out).f_frsize < self.plan['limits']['hostReserveBytes']:
            raise RuntimeError('host artifact reserve reached')
    def prepare(self, profile_id):
        self.current()
        result=self.tool('zap_auth_session_prepare',{'profileId':profile_id,'targetUrl':self.plan['origin']+self.plan.get('identityPath','/api/v1/accounts')})
        self.session=next(line.split(': ',1)[1] for line in result.splitlines() if line.startswith('Session ID: '))
        if self.identity_validator:
            self.native_context={k:next(line.split(': ',1)[1] for line in result.splitlines() if line.startswith(prefix)) for k,prefix in [('contextId','Context ID: '),('userId','User ID: ')]}
        if not self.validate(self.client):raise RuntimeError('protected subject validation failed')
        self.thread=threading.Thread(target=self.monitor,daemon=True);self.thread.start()
        return result
    def validate(self, client):
        start=self.clock()
        try:
            result=self.tool('zap_auth_session_validate',{'sessionId':self.session},client)
            valid='\nValid: true\n' in '\n'+result+'\n'
            if valid and self.identity_validator:valid=self.identity_validator(self) is True
        except Exception as e:
            result=type(e).__name__;valid=False
        self.auth_samples.append({'start':start,'end':self.clock(),'valid':valid,'result':result})
        if not valid:self.lost.set()
        return valid
    def monitor(self):
        while not self.done.wait(self.plan['limits']['monitorIntervalSeconds']):
            try:self.current()
            except Exception as e:
                self.event('binding-or-resource-loss',error=type(e).__name__);self.lost.set()
            if self.lost.is_set() or not self.validate(self.monitor_client):
                self.lost.set();self.stop_all('auth-or-binding-loss');return
    def stop_all(self, reason):
        with self.lock: owned=list(self.operations)
        for op in owned:
            if op.get('terminal'):continue
            begin=self.clock()
            try:
                result=self.tool('zap_'+op['kind']+'_stop',{'operationId':op['operationId']},self.monitor_client)
                self.stop_records.append({'operationId':op['operationId'],'reason':reason,'requestedAt':begin,
                                          'ackAt':self.clock(),'result':result})
            except Exception as e:
                self.stop_records.append({'operationId':op['operationId'],'reason':reason,'requestedAt':begin,'error':type(e).__name__})
        write_json(self.out/'stops.json',self.stop_records)
    def start(self, kind, target, **args):
        self.current()
        if self.plan.get('schemaVersion') in ('research-plan/2.0','research-plan/2.1'):
            u=urllib.parse.urlsplit(target)
            if (u.scheme+'://'+u.netloc != self.plan['origin'] or u.fragment
                    or not any(op['path']==u.path and (kind=='crawl' or op['method']==args.get('method','GET')) for op in self.plan['operations'])):
                raise ValueError('start outside locked discovery plan')
            if kind=='attack' and args.get('recurse','false')!='false':raise ValueError('recursive attack outside selected subset')
            if 'execution' not in self.plan:raise ValueError('executable actions not bound')
            if kind=='crawl' and u.path!=self.plan['execution']['crawl']:raise ValueError('crawl target outside plan')
            if kind=='attack':
                body=json.loads(args['postData']) if 'postData' in args else None
                if not any(a['method']==args.get('method','GET') and a['path']==u.path+('?' + u.query if u.query else '') and a.get('body')==body for a in self.plan['execution']['attacks']):
                    raise ValueError('attack input outside frozen actions')
        intent={'kind':kind,'targetUrl':target,'pendingStart':True,'requestedAt':self.clock()}
        self.event('pending-start',**intent)
        try:
            result=self.tool('zap_'+kind+'_start',{'targetUrl':target,'authSessionId':self.session,**args})
            op={'kind':kind,'operationId':gate.parse_operation_id(result),'nativeScanId':gate.parse_scan_id(result),
                'terminal':False,'requestedAt':intent['requestedAt'],'ackAt':self.clock(),'startResponse':result}
        except Exception:
            self.event('uncertain-start-no-retry',**intent)
            # Dedicated scanner only: record its state; the caller must reconcile,
            # never blindly dispatch another scan on ambiguous ACK.
            write_json(self.out/'uncertain-scans.json',self.zap.call('ascan','view','scans'))
            self.lost.set();raise
        with self.lock:self.operations.append(op)
        self.event('start-ack',**op)
        if self.lost.is_set():self.stop_all('loss-during-start-ACK')
        return op
    def wait(self, op, interrupt_after=None):
        deadline=self.clock()+self.plan['limits']['operationTimeoutSeconds'];interrupted=False
        while self.clock()<deadline:
            result=self.tool('zap_'+op['kind']+'_status',{'operationId':op['operationId']})
            if gate.parse_completed(result):
                op.update(terminal=True,terminalAt=self.clock(),terminalResponse=result)
                self.event('terminal',**op);return op
            if interrupt_after is not None and self.clock()-op['ackAt']>=interrupt_after and not interrupted:
                self.stop_all('requested-interruption');interrupted=True
            if self.lost.is_set():
                self.stop_all('auth-loss')
                failures=[x['end'] for x in self.auth_samples if not x['valid']]
                if failures:deadline=min(deadline,min(failures)+30)
            time.sleep(.5)
        self.stop_all('timeout');raise TimeoutError('operation terminal deadline')
    def finish(self):
        self.done.set()
        if self.thread:self.thread.join(timeout=15)
        self.stop_all('finalize')
        write_json(self.out/'auth-samples.json',self.auth_samples)
        write_json(self.out/'operations.json',self.operations)
        write_json(self.out/'stops.json',self.stop_records)
        return {'authLost':self.lost.is_set(),'operations':self.operations,'samples':len(self.auth_samples)}


def verify_manifest(root):
    root=Path(root);index=json.loads((root/'EVIDENCE_INDEX.json').read_text())
    for row in index['files']:
        p=(root/row['path']).resolve()
        if not p.is_relative_to(root.resolve()) or p.stat().st_size!=row['bytes'] or digest(p)!=row['sha256']:
            raise ValueError('artifact missing/truncated/hash mismatch')
    return {'evidenceStatus':'consistent','checkedFiles':len(index['files']),
            'securityVerdict':'not_implied_by_readback'}


def manifest(root):
    root=Path(root)
    rows=[{'path':str(p.relative_to(root)),'bytes':p.stat().st_size,'sha256':digest(p),
           'classification':'sensitive-local-research'} for p in sorted(root.rglob('*'))
          if p.is_file() and p.name not in ('EVIDENCE_INDEX.json','VERIFICATION.json')]
    write_json(root/'EVIDENCE_INDEX.json',{'assuranceProfile':PROFILE,'secretPersistenceAccepted':True,'files':rows})
    result=verify_manifest(root);write_json(root/'VERIFICATION.json',result);return result
