import json
from pathlib import Path
import tempfile
import unittest
from zap_assessment.research import manifest,write_json
from zap_assessment.research_comparison import compare_runs
class ComparisonTests(unittest.TestCase):
    def fixture(self,path):
        path.mkdir()
        values={'RUN.json':{'executionStatus':'completed','evidenceStatus':'complete','orchestration':{'authLost':False}},
                'CASES.json':[{'pass':True}], 'actual-rule-disposition.json':{'planned':[40012],'observed':[40012],'unexpected':[]},
                'resources.json':{'jarSha256':'x','mcpImageId':'a','zapImageId':'z','targetBinding':{'imageId':'target'}},
                'addons.json':{},'rules.json':{},'OPERATIONS.json':[], 'COVERAGE.json':{'activeScanMessagesMeasured':10}}
        for name,value in values.items():write_json(path/name,value)
        manifest(path)
    def test_image_id_difference_needs_bound_complete_filesystem_config_evidence(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';self.fixture(a);self.fixture(b)
            r=json.loads((b/'resources.json').read_text());r['mcpImageId']='b';write_json(b/'resources.json',r);manifest(b)
            self.assertEqual(compare_runs(a,b)['decision'],'inconclusive')
            signature={'layers':['sha256:full-filesystem-layer'],'os':'linux','architecture':'arm64','runtimeConfigSha256':'config'}
            sha=hashlib.sha256(json.dumps(signature,sort_keys=True).encode()).hexdigest()
            proof=Path(tmp)/'images.json';write_json(proof,{'images':[{'imageId':x,'signature':signature,'sha256':sha} for x in ['a','b']]})
            self.assertEqual(compare_runs(a,b,proof)['decision'],'repeatability-compatible')
            value=json.loads(proof.read_text());value['images'][1]['signature']['layers']=['different'];write_json(proof,value)
            self.assertEqual(compare_runs(a,b,proof)['decision'],'inconclusive')

    def test_failures_drift_and_truncation_are_inconclusive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a';b=Path(tmp)/'b';self.fixture(a);self.fixture(b)
            self.assertEqual(compare_runs(a,b)['decision'],'repeatability-compatible')
            for name,value in [('RUN.json',{'executionStatus':'completed','evidenceStatus':'complete','orchestration':{'authLost':True}}),
                               ('CASES.json',[{'pass':False}]),('addons.json',{'drift':True}),
                               ('OPERATIONS.json',[{'missingRoute':True}])]:
                original=(b/name).read_bytes();write_json(b/name,value);manifest(b)
                self.assertEqual(compare_runs(a,b)['decision'],'inconclusive')
                (b/name).write_bytes(original);manifest(b)
            (b/'COVERAGE.json').write_text('{')
            self.assertEqual(compare_runs(a,b)['decision'],'inconclusive')
if __name__=='__main__':unittest.main()
