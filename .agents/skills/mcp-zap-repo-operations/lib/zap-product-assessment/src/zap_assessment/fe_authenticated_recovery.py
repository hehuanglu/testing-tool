"""Owned controller hard-loss recovery: exact stop/export/cleanup only; never starts traffic."""
import json,time
from pathlib import Path
from types import SimpleNamespace
from .runtime import DockerRuntime
from .journal import Journal
from .fe_authenticated_runtime import AuthenticatedRuntime
from .fe_authenticated_runner import AuthenticatedRun
from .fe_authenticated_contract import load,save,canonical,digest
from .fe_authenticated_mcp import RecordedMCP

def recover(root):
    root=Path(root).resolve();p=load(root/'PLAN.json');j=Journal(root/'journal.jsonl',p['runId'],canonical(p),allow_partial_tail=True)
    if j.partial_tail:raise ValueError('partial journal tail retained; manual stop-only reconciliation needed')
    target=root/'recovery-01';target.mkdir(mode=0o700,exist_ok=False)
    rt=object.__new__(AuthenticatedRuntime);DockerRuntime.__init__(rt,p['runId'],root,j)
    rt.names=[f'zpa-{p["runId"]}-{n}' for n in ('net','broker','zap','mcp','browser')];rt.anchor=rt.names[0];rt.p=p;rt.config=root/'config';rt.work=root/'workspace';rt.capture=root/'broker';rt.stop_timeout=60
    rt.plan=SimpleNamespace(data={'runtime':load(Path(__file__).resolve().parents[2]/'profiles/runtime-baseline.json')})
    env=dict(line.split('=',1) for line in (rt.config/'private-mcp.env').read_text().splitlines())
    rt.mcp_key=env['MCP_API_KEY'];rt.zap_key=env['ZAP_API_KEY']
    pins=load(root/'RUNTIME_PINS.json')
    for name in rt.names:
        info=rt.check_owner(name)
        if info['Id']!=pins[name]['containerId'] or info['Image']!=pins[name]['imageId']:raise ValueError('recovery runtime identity drift')
    # First stop the exact browser producer; the scanner remains alive only for stop/export.
    from .runtime import docker
    docker(['stop','--time','2',rt.names[4]])
    run=object.__new__(AuthenticatedRun);run.rt=rt;run.out=target;run.ei=0;run.p=p;run.j=j
    run.mcp=RecordedMCP(rt,target);save(target,'MCP_SCHEMA.json',run.mcp.initialize())
    inventory=run.engine('ascan','view','scans')['scans'];stopped=[]
    known=set()
    for event in j.events:
        if event['kind']=='pending-start' and event['data'].get('action')=='native-active':known.update(event['data'].get('knownNativeIds',[]))
    from .fe_authenticated_native_inventory import targets
    bound=targets(run,[scan['id'] for scan in inventory],'controller-recovery')
    authorized={(e['data']['targetUrl'],e['data']['method']) for e in j.events if e['kind']=='pending-start' and e['data'].get('action')=='native-active' and e['data'].get('targetUrl')}
    if any((t['url'],t['method']) not in authorized or not t['url'].startswith(p['selection']['origin']+'/') for t in bound):raise ValueError('unowned recovery scan URL/method')
    for scan in inventory:
        run.engine('ascan','action','stop',{'scanId':str(scan['id'])});stopped.append(str(scan['id']))
    terminal=run.engine('ascan','view','scans')['scans'];run.export()
    unknown=[load(f) for f in rt.capture.glob('[0-9]*.json') if load(f).get('transportState') in ('intent','sent','response-headers','unknown')]
    rt.cleanup()
    result={'mode':'stop-export-cleanup-only','controllerMemoryRecovered':False,'startReplayed':False,'mutationReplayed':False,'inventory':inventory,'targetBindings':bound,'stoppedNativeIds':stopped,'terminalInventory':terminal,'unknownRequests':unknown,'cleanupStatus':'clean','reportsReadFully':True,'reviewerApproval':None}
    from .product_scope import task_readback
    result['taskCompletion']='partial';result['responsibilityReconciliation']=task_readback(p)
    result['nextAction']='reconcile ACK/state and create a new allocation for remaining independent duties'
    save(target,'RECOVERY.json',result);return result

def stop_owned_only(root):
    """Failsafe after failed controller recovery: exact journal-owned containers only."""
    root=Path(root).resolve();p=load(root/'PLAN.json');j=Journal(root/'journal.jsonl',p['runId'],canonical(p),allow_partial_tail=True)
    if j.partial_tail:raise ValueError('partial journal retained; exact runtime pins required before manual stop')
    rt=object.__new__(AuthenticatedRuntime);DockerRuntime.__init__(rt,p['runId'],root,j);rt.names=[f'zpa-{p["runId"]}-{n}' for n in ('net','broker','zap','mcp','browser')];rt.anchor=rt.names[0];rt.stop_timeout=60
    rt.cleanup();save(root,'RECOVERY_FAILSAFE_STOP.json',{'cleanupStatus':'clean','action':'exact journal-owned runtime stop/remove only','newTraffic':False,'startReplayed':False,'mutationReplayed':False})
