import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.contracts import canonical,digest,Blocked
from zap_assessment.journal import Journal

SPEC=importlib.util.spec_from_file_location('w5_scanner_campaign',Path(__file__).resolve().parents[1]/'scripts/remediation_w5_scanner.py')
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)


class W5ScannerCampaignTests(unittest.TestCase):
    def safety_receipts(self):
        inventory={'addons':[{'id':'ascanrules','version':'pinned'}], 'scripts':[],
                   'rules':[{'id':'40012','enabled':True}],'inputVectors':['query']}
        traffic={'complete':True,'events':[{'requestId':'native-1','producer':'active','ruleId':'40012',
            'forwarded':True,'boundaryCorrelated':True,'targetAllowed':True,'credentialForwarded':False,
            'unsupportedVectors':[],'phase':'active'}]}
        policy=C.calmod.EffectivePolicy(inventory,active_execution_allowed=True,require_phase=True)
        for phase in ('before','during','after'):policy.snapshot(phase,inventory)
        policy.traffic(traffic['events'],complete=True);result=policy.finalize()
        samples=[{'at':at,'dockerAvailable':True,'hostFree':5*1024**3,'dockerFree':5*1024**3,
                  'ramAvailable':5*1024**3} for at in (10,12,14)]
        result['resources']={'samples':samples,'maxObservedGapSeconds':2,
            'monitoredThrough':'all workloads stopped and removed','measurementHelperShutdownSeconds':.5}
        db={'decoder':'HSQL JDBC all PUBLIC table typed cells','rows':1,'decodedCells':2,'decodedBytes':32}
        receipt={'canaryLeakDetected':False,'securityApproval':False,'securityVerdict':'inconclusive',
            'cleanupStatus':'clean','executionStatus':'completed','evidenceStatus':'complete-development-only',
            'error':None,'safetyFailure':None,'resourceFailure':None,'resourceSamples':samples,
            'maxObservedResourceGapSeconds':2,'policy':result,
            'activePolicyProof':{'pass':True,'expectedRuleIds':['40012'],'nativeRequestCounts':{'40012':1},
                'scanProgressRequestCounts':{'40012':1},'vulnerabilityDetectionVerified':False},
            'databaseReadback':{'positiveControl':{**db,'tables':['CANARY_CONTROL'],'seededControl':True,'canaryMatches':2},
                'savedSession':{**db,'tables':['HISTORY'],'seededControl':False,'canaryMatches':0}}}
        return receipt,traffic

    def test_offline_safety_replay_never_touches_runtime(self):
        receipt,traffic=self.safety_receipts()
        with patch.object(C,'docker',side_effect=AssertionError('offline verifier called Docker')):
            C.verify_runtime_receipts(receipt,traffic)

    def test_recomputed_resource_summary_cannot_hide_gap_or_reserve_loss(self):
        for fault in ('gap','reserve','nan','helper'):
            with self.subTest(fault=fault):
                receipt,traffic=self.safety_receipts()
                if fault=='gap':
                    receipt['resourceSamples'][-1]['at']=20
                    receipt['maxObservedResourceGapSeconds']=8
                    receipt['policy']['resources']['maxObservedGapSeconds']=8
                elif fault=='reserve':receipt['resourceSamples'][-1]['hostFree']=2*1024**3
                elif fault=='nan':receipt['resourceSamples'][1]['at']=float('nan')
                else:receipt['policy']['resources']['measurementHelperShutdownSeconds']=5.01
                with self.assertRaises(Blocked):C.verify_runtime_receipts(receipt,traffic)

    def test_database_receipt_requires_both_seeded_controls_and_zero_saved_matches(self):
        for field,value,control in (('canaryMatches',1,True),('decodedCells',1,True),
                                    ('canaryMatches',1,False),('tables',[],False)):
            with self.subTest(field=field,value=value,control=control):
                receipt,traffic=self.safety_receipts()
                receipt['databaseReadback']['positiveControl' if control else 'savedSession'][field]=value
                with self.assertRaises(Blocked):C.verify_runtime_receipts(receipt,traffic)

    def test_policy_or_count_summary_cannot_override_independent_traffic(self):
        for fault in ('count','phase','unknown-rule','leak','approval'):
            with self.subTest(fault=fault):
                receipt,traffic=self.safety_receipts()
                if fault=='count':receipt['activePolicyProof']['nativeRequestCounts']={'40012':2}
                elif fault=='phase':traffic['events'][0]['phase']='report'
                elif fault=='unknown-rule':traffic['events'][0]['ruleId']='unknown'
                elif fault=='leak':receipt['canaryLeakDetected']=True
                else:receipt['securityApproval']=True
                with self.assertRaises(Blocked):C.verify_runtime_receipts(receipt,traffic)

    def test_recovery_new_journal_preserves_original_and_never_starts(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);p={'runId':'owned-fixture'};pin=digest(p)
            (work/'w5-plan.json').write_bytes(canonical(p));root=work/'runtime';root.mkdir()
            j=Journal(root/'journal.jsonl',p['runId'],pin)
            j.append('intent',{'action':'container-create','resource':'owned-helper','createdByRun':p['runId']})
            before=j.path.read_bytes();seen=[]
            class FakeRuntime:
                def __init__(self,run,root,journal):self.names=[];self.journal=journal
                def cleanup(self):
                    self.assertions=[e for e in self.journal.events if e['kind']=='intent']
                    seen.extend(self.assertions)
                    self.journal.append('ack',{'action':'container-removed','resource':'owned-helper'})
                def provision(self):raise AssertionError('recovery started resources')
                def create(self,*args):raise AssertionError('recovery created resources')
            with patch.object(C,'Runtime',FakeRuntime):result=C.recover(work,pin)
            self.assertTrue(result['originalJournalUnchanged']);self.assertTrue(result['noReplay'])
            self.assertEqual(before,j.path.read_bytes());self.assertEqual(1,len(seen))
            recovery=next(work.glob('recovery-*'));new=Journal(recovery/'journal.jsonl',p['runId'],pin)
            self.assertEqual(['recovery-source','ack'],[e['kind'] for e in new.events])

    def test_recovery_wrong_external_hash_refused_before_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp);(work/'w5-plan.json').write_bytes(canonical({'runId':'owned'}))
            with patch.object(C,'Runtime',side_effect=AssertionError('runtime touched')),self.assertRaises(Blocked):
                C.recover(work,'0'*64)

    def test_prepare_locks_cases_and_cannot_reuse_work_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            work=Path(tmp)/'fresh';result=C.prepare(work,'A');p=json.loads((work/'w5-plan.json').read_bytes())
            self.assertEqual(result['planHash'],digest(p));self.assertEqual(list(C.CASES),p['cases'])
            self.assertFalse(p['operationalAdmission'])
            with self.assertRaises(FileExistsError):C.prepare(work,'B')


if __name__=='__main__':unittest.main()
