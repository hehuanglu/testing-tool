"""Unit negative integration; synthetic bytes are never runtime acceptance."""
from dataclasses import replace
import hashlib
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import Mock
import test_native_secret_gate as native_fixture
from zap_assessment.auth_lifecycle import ProducerStop
from zap_assessment.credential_broker import GeneratedReference
from zap_assessment.delegated_attestation import GATES, RuntimeAttestor, RuntimeSnapshot
from zap_assessment.delegated_holder import DelegatedHolder
from zap_assessment.errors import Blocked
from zap_assessment.native_secret_gate import NativeG3Replay


class NativeAdmissionBoundaryTests(unittest.TestCase):
    def test_private_native_replay_cannot_resolve_source_with_partial_or_mismatched_matrix(self):
        fixture=native_fixture.NativeSecretGateTests();fixture.setUp()
        now=time.time();binding=replace(fixture.binding,expires_at=now+60)
        pair=replace(fixture.pair(),binding=binding,collected_at=now-1,expires_at=now+30)
        variants=[pair,replace(pair,epoch='b'*32),replace(pair,target=replace(pair.target,started_at='restarted'))]
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'source.py').write_bytes(b'unit-source')
            (root/'reference').write_bytes(b'private-native-g3-replay/1.0')
            pin=lambda p:hashlib.sha256((root/p).read_bytes()).hexdigest()
            for candidate in variants:
                with self.subTest(epoch=candidate.epoch,target=candidate.target.started_at):
                    resolve=Mock(side_effect=AssertionError('secret boundary must not open'))
                    stops=[]
                    snapshot=RuntimeSnapshot(fixture.target,'e'*64,'sha256:'+'f'*64,'1'*64,'sha256:'+'2'*64,100)
                    attestor=RuntimeAttestor(binding=binding,target=fixture.target,scanner_id=snapshot.scanner_id,
                        scanner_image=snapshot.scanner_image,holder_id=snapshot.holder_id,holder_image=snapshot.holder_image,
                        source_root=root,source_pins={'source.py':pin('source.py')},evidence_root=root,
                        evidence_pins={gate:[('reference',pin('reference'))] for gate in GATES},
                        replay=NativeG3Replay(secret=fixture.secret,pairs=(candidate,)),observe=lambda:snapshot,
                        stop=lambda:stops.append('stop'),clock=lambda:now,monotonic=lambda:100)
                    holder=DelegatedHolder(attestor=attestor,source=GeneratedReference('unused','control',resolve),
                        producer=ProducerStop(lambda:True,lambda:True),record=lambda row:None,
                        forbidden_roots=['/repo'],operations=['/api/v1/accounts'])
                    with self.assertRaisesRegex(Blocked,'bootstrap_failed'):holder.bootstrap()
                    self.assertTrue(attestor.latched);self.assertFalse(attestor.resolution_reserved)
                    self.assertEqual('lost',holder.phase);self.assertEqual(['stop'],stops)
                    resolve.assert_not_called()
                    with self.assertRaises(Blocked):holder.bootstrap()
                    resolve.assert_not_called();holder.destroy()


if __name__=='__main__':unittest.main()
