import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zap_assessment.contracts import canonical,digest
from zap_assessment.errors import Blocked

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('actual_sink_runner',ROOT/'scripts/actual_zap_sink_control.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class ActualSinkRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.parent=Path(self.temp.name).resolve();self.work=self.parent/'run'
    def tearDown(self):self.temp.cleanup()
    def test_prepare_freezes_readonly_source_without_secret_input(self):
        path=ROOT/'src/zap_assessment/live_sink_probe.py';pin=hashlib.sha256(path.read_bytes()).hexdigest()
        with patch.object(runner,'source_pin',return_value={str(path.relative_to(ROOT)):pin}),patch.object(runner,'call',return_value=b'sha256:'+b'a'*64):
            result=runner.prepare(self.work)
        copied=self.work/'source'/path.relative_to(ROOT)
        self.assertEqual(path.read_bytes(),copied.read_bytes());self.assertEqual(0o444,copied.stat().st_mode&0o777)
        self.assertEqual(result['planHash'],digest(json.loads((self.work/'plan.json').read_bytes())))
        self.assertFalse(json.loads((self.work/'plan.json').read_bytes())['productInputAccepted'])
    def test_wrong_external_pin_and_source_drift_fail_before_docker(self):
        self.work.mkdir();plan={'sourcePins':{},'expiresAt':100}
        (self.work/'plan.json').write_bytes(canonical(plan))
        with patch.object(runner,'call') as docker:
            with self.assertRaises(Blocked):runner.run(self.work,'0'*64)
            docker.assert_not_called()
        self.assertFalse((self.work/'attempt.lock').exists())
    def test_child_output_allowlist_rejects_untrusted_strings_and_fields(self):
        base={'schemaVersion':'actual-zap-sink-control/1.0','status':'blocked','productRequests':0,
              'operationalAdmission':False,'sourceValuesIncluded':False,'rawCellsExportedToController':False,
              'reasonCode':'live_sink_probe_failed','diagnostic':{'stage':'initial'}}
        self.assertEqual(base,runner.validate_result(base))
        for bad in ({**base,'secret':'do not publish'}, {**base,'reasonCode':'target body arbitrary'},
                    {**base,'diagnostic':{'stage':'raw secret'}}, {**base,'sourceValuesIncluded':True}):
            with self.assertRaises(Blocked):runner.validate_result(bad)
    def test_lost_create_ack_recovery_only_stops_exact_owned_resource(self):
        self.work.mkdir();plan={'runId':'owned-test','imageId':'sha256:'+'a'*64}
        (self.work/'plan.json').write_bytes(canonical(plan));h=digest(plan)
        (self.work/'create-intent.json').write_bytes(canonical({'name':'zpa-owned-test','planHash':h,'imageId':plan['imageId']}))
        calls=[]
        def docker(args,**kwargs):
            calls.append(args)
            if args[0]=='ps':return b'c'*64
            return b''
        info={'Id':'c'*64,'State':{'Running':False}}
        with patch.object(runner,'call',side_effect=docker),patch.object(runner,'owner',return_value=info):
            result=runner.recover(self.work,h)
        self.assertTrue(result['noReplay']);self.assertEqual(['ps','stop','rm'],[c[0] for c in calls])
        self.assertTrue(list(self.parent.glob('run-recovery-*.json')))
        self.assertFalse(list(self.work.glob('recovery-*.json')))
    def test_ownership_mismatch_refuses_remove_and_start(self):
        info={'Id':'x','Image':'wrong','Config':{'Labels':{'zpa.run':'someone-else'}}}
        with patch.object(runner,'call',return_value=json.dumps([info]).encode()):
            with self.assertRaises(Blocked):runner.owner('name',{'runId':'owned','imageId':'expected'},None)

if __name__=='__main__':unittest.main()
