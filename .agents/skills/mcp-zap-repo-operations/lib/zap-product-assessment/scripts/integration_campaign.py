"""Foreground synthetic ZAP campaign: two isolated runs, interruption and lost ACK."""
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from zap_assessment.contracts import ROOT,canonical,make_plan,utcnow
from zap_assessment.evidence import verify_bundle
from zap_assessment.executor import Executor,InjectedCrash
from zap_assessment.pilot import fixture_inputs,live_executor,LiveScanner
from zap_assessment.runtime import DockerRuntime,docker
from zap_assessment.transport import MCP,LostAck

summary={'transport':'REAL digest-pinned MCP/ZAP, isolated synthetic namespace','startedAt':utcnow().isoformat(),'command':'PYTHONPATH=src .venv/bin/python scripts/integration_campaign.py','runs':[],'assertions':{}}
import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
path=Path(args.output)
if path.exists():raise FileExistsError('evidence output already exists')
path.parent.mkdir(parents=True,exist_ok=True)
def save():path.write_bytes(canonical(summary))
def record(kind,result):
    summary['runs'].append({'case':kind,'result':result});save();print(json.dumps({'case':kind,**result}),flush=True)

root=ROOT/'runs';ex=live_executor(root)
for i in (1,2):
    p=make_plan(*fixture_inputs('alternate-synthetic-'+str(i)))
    r=ex.run(p);record('clean-'+str(i),r)
    assert r['executionStatus']=='completed' and r['evidenceStatus']=='complete' and r['cleanupStatus']=='clean',r
    manifest=verify_bundle(r['bundle'])
    assert manifest['provenance']['initialSession']['sites']=={'sites':[]}
    assert manifest['sourceRefs']['orchestrator'].startswith('sha256:')
    assert json.loads((Path(r['bundle'])/'network.json').read_text())['forbiddenRequests']==0
    assert len(json.loads((Path(r['bundle'])/'report-readback.json').read_text())['pages'])>=2
first,second=[verify_bundle(x['result']['bundle']) for x in summary['runs']]
assert first['runId']!=second['runId'] and first['provenance']['namespace']!=second['provenance']['namespace']
assert first['sourceRefs']['orchestrator']==second['sourceRefs']['orchestrator']
summary['assertions']['twoFreshSessionsIndependentEvidence']=True;save()

run_id='r'+uuid.uuid4().hex
p=make_plan(*fixture_inputs('interruption-synthetic'))
try:ex.run(p,run_id,interrupt_after_start=True)
except InjectedCrash:pass
else:raise AssertionError('interruption was not injected')
r=ex.recover(root/run_id);record('interrupted-recovery',r)
events=[json.loads(x) for x in (root/run_id/'journal.jsonl').read_text().splitlines()]
assert sum(e['kind']=='intent' and e['data'].get('action')=='start-crawl' for e in events)==1
assert r['cleanupStatus']=='clean' and r['gateDecision']=='block' and r['evidenceStatus']=='incomplete'
summary['assertions']['interruptedNoDuplicateStopConfirmed']=True;save()

class AckLossScanner(LiveScanner):
    def start(self,kind,target):
        operation=super().start(kind,target)
        scans=self.engine('spider','view','scans',{})
        assert len(scans['scans'])==1
        self.runtime.journal.append('fault-observation',{'fault':'ACK deliberately withheld from executor after real start','upstreamOperationId':operation,'actualScans':scans})
        raise LostAck('injected ACK loss')
def scanner(rt):
    s=AckLossScanner(MCP(rt.request),rt.engine,rt.request);s.runtime=rt;return s
lost=Executor(root,DockerRuntime,scanner)
p=make_plan(*fixture_inputs('lost-ack-synthetic'));r=lost.run(p);record('lost-ack',r)
events=[json.loads(x) for x in (root/r['runId']/'journal.jsonl').read_text().splitlines()]
assert sum(e['kind']=='intent' and e['data'].get('action')=='start-crawl' for e in events)==1
assert r['cleanupStatus']=='clean' and r['gateDecision']=='block' and r['evidenceStatus']=='incomplete'
summary['assertions']['lostAckOneActualScanStopConfirmed']=True
assert not docker(['ps','-aq','--filter','label=zpa.run']).strip(),'owned campaign resources remain'
summary['assertions']['allCampaignResourcesRemoved']=True;summary['endedAt']=utcnow().isoformat();summary['allAssertionsPassed']=True;save()
print(json.dumps({'allAssertionsPassed':True,'evidence':str(path)}),flush=True)
