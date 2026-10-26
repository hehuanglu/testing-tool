import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zap_assessment.errors import Blocked
from zap_assessment.runtime_safety import ResourceGate,GIB
from zap_assessment.w5_resources import bounded_profile,validate_profile,verify_measurements,W5ResourceGate,MIB
from zap_assessment import w5_resources


class W5ResourceTests(unittest.TestCase):
    def setUp(self):
        # Resource-gate regression tests must not depend on a retained real run.
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        workspace=Path(temp.name)
        def receipt(name,peak):
            value={'status':'development_pass_operational_blocked','cleanupConfirmed':True,
                   'artifactAudit':[{'bytes':128*MIB}], 'resourceMetrics':[{'hostGrowth':peak}]}
            raw=json.dumps(value).encode();path=workspace/name
            path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
            return hashlib.sha256(raw).hexdigest()
        checksum=receipt(w5_resources.BASELINE,0)
        measurements=tuple((name,receipt(name,peak),peak) for name,_,peak in w5_resources.MEASUREMENTS)
        for key,value in [('BASELINE_SHA',checksum),('MEASUREMENTS',measurements)]:
            change=patch.object(w5_resources,key,value);change.start();self.addCleanup(change.stop)
        self.profile=bounded_profile(workspace)
        self.at=10
        self.sample={'hostFree':3*GIB,'dockerFree':5*GIB,'ramAvailable':3*GIB,'dockerAvailable':True}
        self.contract={'sampleSeconds':5,'reserveBytes':2*GIB,'ramHeadroomBytes':4*GIB,'stopSeconds':120,
                       'growth':{'host':GIB,'docker':GIB},'calibration':{'classification':'owned-synthetic','evidenceSha256':'0'*64}}

    def gate(self):return W5ResourceGate(self.contract,lambda:self.sample,self.profile,clock=lambda:self.at)

    def test_candidate_preflight_and_runtime_use_distinct_locked_ram_budgets(self):
        gate=self.gate();gate.preflight()
        self.at+=2;self.sample['ramAvailable']=2*GIB;gate.check(force=True)
        self.assertEqual([3*GIB,3*GIB//2],[s['ramRequiredBytes'] for s in gate.samples])
        self.at+=2;self.sample['ramAvailable']=GIB
        with self.assertRaisesRegex(Blocked,'RAM'):gate.check(force=True)

    def test_low_ram_preflight_and_disk_reserve_still_block(self):
        self.sample['ramAvailable']=2*GIB
        with self.assertRaisesRegex(Blocked,'RAM'):self.gate().preflight()
        self.sample['ramAvailable']=3*GIB;gate=self.gate();gate.preflight()
        self.at+=2;self.sample['hostFree']=2*GIB
        with self.assertRaisesRegex(Blocked,'reserve'):gate.check(force=True)

    def test_legacy_ram_requirement_is_unchanged(self):
        gate=ResourceGate(self.contract,lambda:{**self.sample,'hostFree':5*GIB},clock=lambda:self.at)
        with self.assertRaisesRegex(Blocked,'RAM'):gate.preflight()

    def test_profile_cannot_silently_drop_capacity_or_grant_admission(self):
        for key,value in [('ramDuringBytes',1),('ramPreflightBytes',GIB),('reserveBytes',GIB),
                          ('operationalAdmission',True),('artifactCapBytes',MIB)]:
            p=copy.deepcopy(self.profile);p[key]=value
            with self.subTest(key=key),self.assertRaises(Blocked):validate_profile(p)

    def observations(self):
        gate=self.gate();gate.preflight();self.at+=2;gate.check(force=True)
        metrics=[]
        for s in gate.samples:
            row={'containerId':'a'*64,'limitBytes':GIB,'currentBytes':64*MIB,'peakBytes':128*MIB,
                 'events':{'oom':0,'oom_kill':0},'oomKilled':False,'running':True}
            metrics.append({'at':s['at']-.01,'hostGrowth':10*MIB,'hostFree':s['hostFree'],
                'dockerFree':s['dockerFree'],'ramAvailable':s['ramAvailable'],
                'containerMemoryPeakBytes':{'owned':128*MIB},'containerMemory':{'owned':row}})
        return metrics,gate.samples

    def test_persisted_measurements_bind_memory_to_identity_and_gate_samples(self):
        metrics,samples=self.observations();verify_measurements(self.profile,metrics,samples)

    def test_recomputed_memory_receipts_cannot_hide_oom_ownership_or_cap_failure(self):
        for fault in ('oom','owner','missing','cap','ram','peak','missing-oom','threshold'):
            metrics,samples=self.observations();row=metrics[-1]['containerMemory']['owned']
            if fault=='oom':row['events']['oom_kill']=1
            elif fault=='owner':row['containerId']='b'*64
            elif fault=='missing':metrics[-1]['containerMemory']={}
            elif fault=='cap':metrics[-1]['hostGrowth']=self.profile['artifactCapBytes']+1
            elif fault=='ram':metrics[-1]['ramAvailable']-=1
            elif fault=='missing-oom':row['events']={}
            elif fault=='threshold':samples[-1]['ramRequiredBytes']=0
            else:row['peakBytes']=GIB+1;metrics[-1]['containerMemoryPeakBytes']['owned']=GIB+1
            with self.subTest(fault=fault),self.assertRaises(Blocked):verify_measurements(self.profile,metrics,samples)


if __name__=='__main__':unittest.main()
