import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from zap_assessment.anonymous_runner import AnonymousRun, baseline_key


class BaselineBindingTests(unittest.TestCase):
    def test_long_labels_are_bounded_stable_and_distinct(self):
        label = 'register-name-xss-validation'
        self.assertLessEqual(len(baseline_key(label)), 30)
        self.assertEqual(baseline_key(label), baseline_key(label))
        self.assertNotEqual(baseline_key(label), baseline_key(label + '-sql'))

    def test_delayed_result_never_reexecutes_baseline_script(self):
        with tempfile.TemporaryDirectory() as temp:
            run = AnonymousRun.__new__(AnonymousRun)
            run.out = Path(temp)
            run.rt = Mock(work=Path(temp))
            run.j = Mock()
            calls, reads = [], []
            def engine(component, kind, name, args=None):
                calls.append(name)
                if name == 'globalVar':
                    reads.append(args['varKey'])
                    if len(reads) == 1:
                        raise RuntimeError('not ready')
                    return {'globalVar': json.dumps({'historyId': 1, 'method': 'POST', 'body': '{}'})}
                return {'listScripts': []}
            run.engine = engine
            with patch('zap_assessment.anonymous_runner.time.sleep'):
                run.bind_baseline({'requestHeader': 'POST /api HTTP/1.1\r\n', 'requestBody': '{}',
                                   'responseHeader': 'HTTP/1.1 400\r\n', 'responseBody': '{}'}, 'a' * 100)
            self.assertEqual(calls.count('runStandAloneScript'), 1)
            self.assertEqual(calls.count('sendRequest'), 0)
            self.assertTrue(all(len(key) <= 30 for key in reads))

class BaselineFailureTests(unittest.TestCase):
    def test_error_and_timeout_never_double_dispatch(self):
        for mode in ('error','timeout'):
            with tempfile.TemporaryDirectory() as tmp:
                run=AnonymousRun.__new__(AnonymousRun);run.out=Path(tmp);run.rt=Mock(work=Path(tmp));run.j=Mock();calls=[]
                def engine(component,kind,name,args=None):
                    calls.append(name)
                    if name=='globalVar':
                        if mode=='timeout':raise RuntimeError('not completed')
                        return {'globalVar':json.dumps({'error':'controlled script failure'})}
                    return {'listScripts':[]}
                run.engine=engine
                with patch('zap_assessment.anonymous_runner.time.monotonic',side_effect=[0,6]),patch('zap_assessment.anonymous_runner.time.sleep'):
                    with self.assertRaises((ValueError,RuntimeError)):
                        run.bind_baseline({'requestHeader':'POST /x HTTP/1.1\r\n','requestBody':'{}','responseHeader':'HTTP/1.1 400\r\n','responseBody':'{}'},mode)
                self.assertEqual(calls.count('runStandAloneScript'),1);self.assertEqual(calls.count('sendRequest'),0);self.assertEqual(calls.count('remove'),1)

if __name__ == '__main__':
    unittest.main()
