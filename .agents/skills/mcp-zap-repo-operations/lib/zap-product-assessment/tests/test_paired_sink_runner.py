import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch
import test_native_secret_gate as native_fixture
from zap_assessment.native_secret_gate import NativeG3Replay
from zap_assessment.errors import Blocked

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('paired_sink_runner',ROOT/'scripts/actual_zap_sink_control.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class PairedSinkOutputTests(unittest.TestCase):
    def setUp(self):
        fixture=native_fixture.NativeSecretGateTests('test_collector_reads_count_pages_and_eof_from_engine');fixture.setUp()
        replay=NativeG3Replay(secret=fixture.secret,pairs=(fixture.pair(),))
        receipt=replay.inspect(binding=fixture.binding,target=fixture.target,epoch=None,now=110)
        self.secret=fixture.secret
        self.value={'schemaVersion':'actual-zap-sink-control/1.1','status':'pass','zapVersion':'2.17.0',
            'privateReplay':receipt,'incompleteMatrixRejected':True,'writerTerminals':2,'freshSessions':2,
            'controlRequests':10,'activeRequests':0,'productRequests':0,'sourceValuesIncluded':False,
            'rawCellsExportedToController':False,'platformAcceptance':False,'operationalAdmission':False}
    def test_current_contract_output_is_metadata_only_and_does_not_admit(self):
        import json
        self.assertEqual(self.value,runner.validate_result(self.value))
        self.assertNotIn(self.secret,json.dumps(self.value));self.assertFalse(self.value['operationalAdmission'])
    def test_false_denominator_counts_and_missing_pair_inventory_block(self):
        for field,value in [('requiredPairs',142),('nativePairsReplayed',143)]:
            candidate=copy.deepcopy(self.value);candidate['privateReplay'][field]=value
            with self.assertRaises(Blocked):runner.validate_result(candidate)
        candidate=copy.deepcopy(self.value);candidate['privateReplay']['missingPairs'].pop()
        with self.assertRaises(Blocked):runner.validate_result(candidate)
    def test_hidden_raw_fields_leak_counts_and_fake_platform_acceptance_block(self):
        bad=[]
        for field,value in [('sourceValuesIncluded',True),('platformAcceptance',True),('writerTerminals',1)]:
            candidate=copy.deepcopy(self.value);candidate[field]=value;bad.append(candidate)
        candidate=copy.deepcopy(self.value);candidate['privateReplay']['samples'][0]['zero']['database']['canaryMatches']=1;bad.append(candidate)
        candidate=copy.deepcopy(self.value);candidate['privateReplay']['samples'][0]['positive']['database']['controls'][0]['raw']=self.secret;bad.append(candidate)
        candidate=copy.deepcopy(self.value);candidate['privateReplay']['rawHistory']=self.secret;bad.append(candidate)
        for candidate in bad:
            with self.assertRaises(Blocked):runner.validate_result(candidate)
    def test_blocked_child_cannot_echo_target_error_text(self):
        value={'schemaVersion':'actual-zap-sink-control/1.1','status':'blocked','stage':'zero-history',
               'reasonCode':'paired_private_probe_failed','productRequests':0,'sourceValuesIncluded':False,
               'rawCellsExportedToController':False,'operationalAdmission':False}
        self.assertEqual(value,runner.validate_result(value))
        value['reasonCode']=self.secret
        with self.assertRaises(Blocked):runner.validate_result(value)

if __name__=='__main__':unittest.main()
