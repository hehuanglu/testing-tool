"""Foreground real MCP/ZAP integration against independently owned synthetic target."""
import argparse,copy,hashlib,json,sys,uuid
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'tests/support')]
from borrowed_target import IndependentTarget
from zap_assessment.contracts import ROOT,canonical,digest,make_plan,utcnow
from zap_assessment.evidence import verify_bundle
from zap_assessment.executor import Executor,InjectedCrash
from zap_assessment.pilot import live_executor,LiveScanner
from zap_assessment.transport import MCP,LostAck
from zap_assessment.existing import ExistingDockerRuntime
from zap_assessment.runtime import DockerRuntime,docker
original_wait=DockerRuntime.wait_health
def diagnostic_wait(self,*args):
    try:return original_wait(self,*args)
    except Exception:
        try:
            logs=docker(['logs','--tail','120',self.names[3]])
            causes=[line for line in logs.splitlines() if 'Caused by:' in line]
            (self.root/'synthetic-startup-causes.json').write_bytes(canonical({'syntheticOnly':True,'causes':causes}))
        except Exception:pass
        raise
DockerRuntime.wait_health=diagnostic_wait
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);parser.add_argument('--cases',nargs='*',default=['clean-1','clean-2','identity','build','interrupted','lost-ack','import-ack','cancelled','hash','truncated']);args=parser.parse_args()
output=Path(args.output);assert not output.exists();output.parent.mkdir(parents=True,exist_ok=True)
summary={'transport':'REAL pinned MCP/ZAP + independent borrowed synthetic target; NOT finalsource authority','startedAt':utcnow().isoformat(),'runs':[],'assertions':{}}
def save():output.write_bytes(canonical(summary))
root=ROOT/'runs';target=IndependentTarget(root/('binding-harness-'+uuid.uuid4().hex)).start()
try:
    inputs=target.inputs();plan=make_plan(*inputs);ex=live_executor(root)
    for case in args.cases:
        p=plan
        if case=='health-only':
            values=list(copy.deepcopy(inputs));product=values[0];product.update({'healthPath':'/api/health','crawlPath':'/api/health','publicSeeds':['/api/health'],'allowedPaths':['/api/health'],'expectedOperations':[{'method':'GET','path':'/api/health','status':200}],'healthAssertions':[{'pointer':'/target','equals':'independent-A'},{'pointer':'/success','equals':True},{'pointer':'/data/status','equals':'ok'}]})
            schema=json.loads(values[3]);schema['paths']={'/api/health':{'get':{'responses':{'200':{'description':'health smoke only'}}}}};values[3]=canonical(schema);product['schema']['sha256']=hashlib.sha256(values[3]).hexdigest();values[2].records['binding-synthetic-authority']['allowedPaths']=['/api/health'];p=make_plan(*values)
        if case in ('identity','build'):
            values=copy.deepcopy(inputs)
            if case=='identity':values[0]['healthAssertions'][0]['equals']='WRONG-target'
            else:
                values[0]['binding']['imageId']='sha256:'+'0'*64;values[0]['targetBuildRef']=values[0]['binding']['imageId'];values[2].records['binding-synthetic-authority']['bindingHash']=digest(values[0]['binding'])
            p=make_plan(*values)
        if case=='interrupted':
            run='r'+uuid.uuid4().hex
            try:ex.run(p,run,True)
            except InjectedCrash:pass
            else:raise AssertionError('interruption absent')
            result=ex.recover(root/run)
        elif case in ('lost-ack','import-ack','cancelled','hash','truncated'):
            class FaultScanner(LiveScanner):
                def start(self,kind,url):
                    op=super().start(kind,url)
                    if case=='lost-ack':
                        actual=self.engine('spider','view','scans',{});assert len(actual['scans'])==1
                        self.rt.journal.append('fault-observation',{'fault':'ACK withheld after real start','actualScans':actual,'upstreamOperationId':op});raise LostAck()
                    return op
                def import_content(self,*args):
                    value=super().import_content(*args)
                    if case=='import-ack':
                        self.rt.journal.append('fault-observation',{'fault':'ACK withheld after real content import','actualImports':1});raise LostAck()
                    return value
                def status(self,*args):
                    if case=='cancelled':raise KeyboardInterrupt()
                    return super().status(*args)
                def chunk(self,*args):
                    page=super().chunk(*args)
                    if case=='hash' and page['offset']==0:page['content']='X'+page['content'][1:]
                    if case=='truncated' and page['endOfFile']:page['totalCharacters']+=1
                    return page
            def factory(run,folder,j):
                rt=ExistingDockerRuntime(run,folder,j);rt.plan=p;return rt
            def scanner(rt):
                s=FaultScanner(MCP(rt.request),rt.engine,rt.request);s.rt=rt;return s
            result=Executor(root,factory,scanner).run(p)
        else:result=ex.run(p)
        locked=root/result['runId']/('bundle' if 'bundle' in result else 'staging')/'plan.json'
        assert locked.read_bytes()==p.encoded,'target data changed immutable plan'
        obs=target.observations()
        assert obs['before']==obs['after'],'borrowed target changed during scanner cleanup'
        assert obs['canaryRequests']==0 and obs['credentialRequests']==0,obs
        events=[json.loads(x) for x in (root/result['runId']/'journal.jsonl').read_text().splitlines()]
        assert not any(e['data'].get('action')=='start-active' for e in events),'malicious target text changed operations'
        assert not any(e['data'].get('resource') in (target.cid,target.name,target.network_id,target.network) for e in events),'borrowed target mutated'
        if case.startswith('clean') or case=='health-only':
            assert result['executionStatus']=='completed' and result['evidenceStatus']=='complete',result
            manifest=verify_bundle(result['bundle']);assert manifest['ownership']['borrowed']==[p.data['product']['binding']]
            assert manifest['provenance']['initialSession']['sites']=={'sites':[]}
        else:
            assert result['gateDecision']=='block' and not (root/result['runId']/'bundle').exists(),result
            if case in ('hash','truncated'):assert result['evidenceStatus']=='invalid',result
            if case in ('identity','build'):assert not any(e['data'].get('action')=='start-crawl' for e in events),result
            if case in ('interrupted','lost-ack','import-ack','cancelled'):assert sum(e['kind']=='intent' and e['data'].get('action')=='start-crawl' for e in events)==1
        if case=='import-ack':assert sum(e['kind']=='intent' and e['data'].get('action')=='import-openapi' for e in events)==1
        if case=='cancelled':assert result['executionStatus']=='cancelled'
        if case=='health-only':
            assert all(x['port']==3000 and x['pathSha256']==hashlib.sha256(b'/api/health').hexdigest() for x in obs['requests']),obs
            summary['assertions']['onlyApprovedHealthGetReachedTarget']=True
        assert result['cleanupStatus']=='clean',result
        summary['runs'].append({'case':case,'result':result,'borrowedTargetPreserved':True,'canaryRequests':0,'credentialRequests':0});save();print(json.dumps({'case':case,**result}),flush=True)
    clean=[verify_bundle(x['result']['bundle']) for x in summary['runs'] if x['case'].startswith('clean')]
    if len(clean)==2:
        assert clean[0]['runId']!=clean[1]['runId'] and clean[0]['provenance']['namespace']!=clean[1]['provenance']['namespace']
        assert clean[0]['sourceRefs']['orchestrator']==clean[1]['sourceRefs']['orchestrator']
        summary['assertions']['twoFreshSessionsIndependentEvidence']=True
    from tempfile import TemporaryDirectory
    import shutil
    if clean:
        with TemporaryDirectory() as t:
            tampered=Path(t)/'bundle';shutil.copytree(next(x['result']['bundle'] for x in summary['runs'] if x['case'].startswith('clean')),tampered)
            (tampered/'binding.json').unlink()
            try:verify_bundle(tampered)
            except (ValueError,OSError):summary['assertions']['missingBindingEvidenceRejected']=True
            else:raise AssertionError('missing binding evidence accepted')
    summary['assertions'].update({'borrowedTargetPreservedEveryCase':True,'zeroForbiddenEgressAndCredentialForwarding':True,'noBorrowedMutationJournal':True,'maliciousDataPlanUnchanged':True})
    summary['targetEvidence']=target.observations()
    for item in summary['runs']:
        rid=item['result']['runId']
        assert not docker(['ps','-aq','--filter','label=zpa.run='+rid]).strip()
        assert not docker(['volume','ls','-q','--filter','label=zpa.run='+rid]).strip()
    summary['assertions']['allOwnedContainersAndVolumesRemoved']=True
    summary['allAssertionsPassed']=True;summary['endedAt']=utcnow().isoformat();save()
finally:target.close()
print(json.dumps({'allAssertionsPassed':True,'evidence':str(output)}),flush=True)
