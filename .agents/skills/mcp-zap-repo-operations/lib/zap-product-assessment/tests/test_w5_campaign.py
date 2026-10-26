"""External lock, no-replay and semantic tamper checks for W5 development output."""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.contracts import canonical

SPEC = importlib.util.spec_from_file_location('w5_campaign', Path(__file__).resolve().parents[1]/'scripts/remediation_w5_campaign.py')
CAMPAIGN = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAMPAIGN)


class W5CampaignTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.original = cls.root/'original'
        cls.prepared = CAMPAIGN.prepare(cls.original)
        cls.result = CAMPAIGN.run(cls.original, cls.prepared['planSha256'])

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def mutated(self):
        target = self.root/self._testMethodName
        shutil.copytree(self.original, target)
        return target

    def rehash(self, target):
        names = ('plan.json', 'attempt.json', 'observations.json', 'gate-results.json')
        (target/'readback-index.json').write_bytes(canonical({n: CAMPAIGN.sha((target/n).read_bytes()) for n in names}))

    def test_readback_is_offline_and_capability_remains_blocked(self):
        import socket
        with patch.object(socket, 'socket', side_effect=AssertionError('readback opened socket')):
            result = CAMPAIGN.verify(self.original, self.prepared['planSha256'])
        self.assertEqual('pass', result['readbackStatus'])
        self.assertEqual('blocked', result['operationalG3'])
        self.assertEqual('blocked', result['productG4'])

    def test_locked_source_drift_refused_before_socket(self):
        work = self.root/'drift'
        lock = CAMPAIGN.prepare(work)
        with patch.object(CAMPAIGN, 'source_pin', return_value={'drift': '0'*64}), self.assertRaises(ValueError):
            CAMPAIGN.run(work, lock['planSha256'])
        self.assertFalse((work/'attempt.json').exists())

    def test_same_attempt_cannot_run_twice(self):
        with self.assertRaises(OSError):
            CAMPAIGN.run(self.original, self.prepared['planSha256'])

    def test_external_lock_is_required(self):
        with self.assertRaises(ValueError):
            CAMPAIGN.verify(self.original, '0'*64)

    def test_missing_observations_recomputed_hash_rejected(self):
        work = self.mutated()
        (work/'observations.json').write_bytes(b'[]')
        self.rehash(work)
        with self.assertRaises(ValueError):
            CAMPAIGN.verify(work, self.prepared['planSha256'])

    def test_post_latch_arrival_recomputed_hash_rejected(self):
        work = self.mutated()
        observations = json.loads((work/'observations.json').read_bytes())
        case = next(c for c in observations if c['caseId'] == 'test_revocation_prevents_refresh_and_relogin')
        loss = next(e for e in case['events'] if e['event'] == 'auth_lost')
        case['target'].append({'path': '/api/v1/accounts', 'actorRef': 'A',
                               'atMonotonic': loss['atMonotonic'] + .01})
        (work/'observations.json').write_bytes(canonical(observations))
        self.rehash(work)
        with self.assertRaisesRegex(ValueError, 'after latch'):
            CAMPAIGN.verify(work, self.prepared['planSha256'])

    def test_g3_cannot_be_promoted_by_rehashing(self):
        from jsonschema.exceptions import ValidationError
        work = self.mutated()
        value = copy.deepcopy(self.result)
        value['gates'][2]['status'] = 'pass'
        (work/'gate-results.json').write_bytes(canonical(value))
        self.rehash(work)
        with self.assertRaises(ValidationError):
            CAMPAIGN.verify(work, self.prepared['planSha256'])

    def test_missing_lifecycle_sink_cannot_be_hidden(self):
        from jsonschema.exceptions import ValidationError
        work = self.mutated()
        value = copy.deepcopy(self.result)
        value['missingSecretProof'].pop()
        (work/'gate-results.json').write_bytes(canonical(value))
        self.rehash(work)
        with self.assertRaises(ValidationError):
            CAMPAIGN.verify(work, self.prepared['planSha256'])


if __name__ == '__main__':
    unittest.main()
