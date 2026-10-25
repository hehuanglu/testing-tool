"""Persist explicitly FAKE fault evidence; never represents scanner integration."""
import json
import sys
import uuid
from pathlib import Path
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'tests')]
from test_assessment import FakeClock,FakeRuntime,FakeScanner
from zap_assessment.contracts import ROOT,canonical,make_plan,utcnow
from zap_assessment.executor import Executor,InjectedCrash
from zap_assessment.pilot import fixture_inputs

import argparse
parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args();output=Path(args.output)
if output.exists():raise FileExistsError('evidence output already exists')
output.parent.mkdir(parents=True,exist_ok=True)
root=ROOT/'runs'/('fault-campaign-'+uuid.uuid4().hex[:12]);root.mkdir(parents=True,mode=0o700)
cases=[]
for fault,expected in [('lost_ack',('failed','incomplete','clean')),('import_ack',('failed','incomplete','clean')),('backlog',('timed_out','incomplete','clean')),('crawl_timeout',('timed_out','incomplete','clean')),('hash',('failed','invalid','clean')),('truncated',('failed','invalid','clean')),('stop',('failed','incomplete','incomplete')),('secret',('failed','invalid','retained_by_policy'))]:
    scanner=FakeScanner(fault);clock=FakeClock()
    ex=Executor(root,lambda *args:FakeRuntime(*args,fault=fault),lambda rt:scanner,clock,clock.sleep)
    p=make_plan(*fixture_inputs());result=ex.run(p,'case-'+fault.replace('_','-'))
    actual=tuple(result[k] for k in ('executionStatus','evidenceStatus','cleanupStatus'))
    assert actual==expected,(fault,actual,expected)
    assert result['gateDecision']=='block' and scanner.starts==1
    cases.append({'case':fault,'inputFixture':'tests/test_assessment.py:FakeScanner + FakeRuntime','inputPlan':str((root/result['runId']/'staging/plan.json').relative_to(ROOT)),'planHash':p.hash,'expected':{'executionStatus':expected[0],'evidenceStatus':expected[1],'cleanupStatus':expected[2],'gateDecision':'block'},'observed':result,'startCalls':scanner.starts,'artifact':str((root/result['runId']/'journal.jsonl').relative_to(ROOT)),'recovery':'stop-only reconciliation; retain ownership for unconfirmed stop/secret integrity failure'})
summary={'transport':'FAKE — unit/fault proof only, not ZAP capability evidence','observedAt':utcnow().isoformat(),'command':'PYTHONPATH=src .venv/bin/python scripts/fault_campaign.py','cases':cases,'allAssertionsPassed':True}
output.write_bytes(canonical(summary));print(json.dumps({'cases':len(cases),'allAssertionsPassed':True,'evidence':str(output)}))
