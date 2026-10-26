from dataclasses import asdict,replace
import copy,importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.credential_broker import BrokerBinding
from zap_assessment.errors import Blocked
from zap_assessment.source_broker_fixture import validate
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('source_control_runner',ROOT/'scripts/private_source_control.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)

class PrivateSourceControlTests(unittest.TestCase):
    def setUp(self):
        base=BrokerBinding('source-control-unit','a'*64,'A','11',None,'owned-source-broker/1.0','http://127.0.0.1:18080',200)
        self.config={'contract':'owned-source-control/1.0','runId':base.run_id,'productInputAccepted':False,'grants':{}}
        for i,key in enumerate(('A','B','lost','gated'),1):
            binding=replace(base,actor_ref='B',subject='12') if key=='B' else base
            self.config['grants'][key]={'referenceId':str(i)*32,'binding':asdict(binding),'uid':1004 if key=='B' else 1003}
        self.status={'contract':'owned-source-control/1.0','runId':base.run_id,'ready':True,'uid':1005,'sourceReads':0,
            'usedReferences':[],'sourceMetadata':[1,2,1005,1005,1,0o600,1000,1,1],'events':[],
            'authRequests':[],'sourceValuesIncluded':False,'productRequests':0}
    def test_fixture_contract_cannot_take_product_url_secret_fields_or_arbitrary_uid(self):
        self.assertEqual(self.config,validate(self.config))
        bad=[]
        value=copy.deepcopy(self.config);value['password']='must not be accepted';bad.append(value)
        value=copy.deepcopy(self.config);value['grants']['A']['binding']['origin']='https://unapproved.example';bad.append(value)
        value=copy.deepcopy(self.config);value['grants']['B']['uid']=1003;bad.append(value)
        for value in bad:
            with self.assertRaises(Blocked):validate(value)
    def test_status_allowlist_blocks_raw_values_unknown_fields_and_bad_modes(self):
        self.assertEqual(self.status,runner.validate_status(self.status,self.config))
        bad=[]
        value=copy.deepcopy(self.status);value['rawSource']='never publish';bad.append(value)
        value=copy.deepcopy(self.status);value['sourceMetadata'][5]=0o644;bad.append(value)
        value=copy.deepcopy(self.status);value['events']=[{'event':'exception','body':'never publish'}];bad.append(value)
        value=copy.deepcopy(self.status);value['authRequests']=[{'method':'GET','operation':'identity',
            'accepted':True,'actorRef':'A','response':'never publish'}];bad.append(value)
        for value in bad:
            with self.assertRaises(Blocked):runner.validate_status(value,self.config)
    def test_bad_plan_pin_refused_before_docker_and_attempt(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'plan.json').write_text('{"sourcePins":{},"expiresAt":1}')
            with patch.object(runner.native,'call') as docker:
                with self.assertRaises(Blocked):runner.run(root,'0'*64)
                docker.assert_not_called()
            self.assertFalse((root/'attempt.lock').exists())

if __name__=='__main__':unittest.main()
