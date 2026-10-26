from dataclasses import replace
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zap_assessment.credential_broker import BrokerBinding
from zap_assessment.delegated_attestation import GATES,ProofReplay,RuntimeAttestor,RuntimeSnapshot,OperationLedger
from zap_assessment.errors import Blocked
from zap_assessment.finalsource_delegated import TargetBinding
from zap_assessment.journal import Journal

class FakeReplay(ProofReplay):
    """Unit contract double. It supplies NO operational gate evidence."""
    def __init__(self):self.calls=[];self.failure=None;self.answer=None
    def verify(self,gate,evidence,**kwargs):
        self.calls.append((gate,evidence,kwargs['epoch']))
        if gate==self.failure:raise Blocked('unit-gate-failed')
        return self.answer

class DelegatedAttestorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.stops=[]
        (self.root/'source.py').write_text('trusted unit source')
        (self.root/'evidence.json').write_text('{"gateDecision":"allow"}')
        self.pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.iterdir()}
        self.target=TargetBinding('a'*64,'sha256:'+'b'*64,'started','c'*64,'127.0.0.1',3000)
        self.binding=BrokerBinding('run-A','d'*64,'A','11',None,'build','http://127.0.0.1:3000',200)
        self.view=RuntimeSnapshot(self.target,'e'*64,'sha256:'+'f'*64,'1'*64,'sha256:'+'2'*64,100)
        self.now=100;self.mono=100;self.replay=FakeReplay()
    def tearDown(self):self.tmp.cleanup()
    def attestor(self):
        return RuntimeAttestor(binding=self.binding,target=self.target,scanner_id=self.view.scanner_id,
            scanner_image=self.view.scanner_image,holder_id=self.view.holder_id,holder_image=self.view.holder_image,
            source_root=self.root,source_pins={'source.py':self.pins['source.py']},evidence_root=self.root,
            evidence_pins={g:[('evidence.json',self.pins['evidence.json'])] for g in GATES},
            replay=self.replay,observe=lambda:self.view,stop=lambda:self.stops.append('stop'),
            clock=lambda:self.now,monotonic=lambda:self.mono)
    def boot(self):
        a=self.attestor();a.before_resolve(self.binding,self.target);a.bind_epoch('a'*32);return a
    def test_pins_and_every_gate_replayed_before_resolve_and_dispatch(self):
        a=self.boot();a.before_dispatch(self.binding,self.target,'a'*32)
        self.assertEqual(2*len(GATES),len(self.replay.calls))
        self.assertEqual({None},{v[2] for v in self.replay.calls[:len(GATES)]})
        self.assertEqual({'a'*32},{v[2] for v in self.replay.calls[len(GATES):]})
        with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
        with self.assertRaises(Blocked):a.bind_epoch('b'*32)
    def test_data_flag_and_new_checksum_do_not_replace_gate_replay(self):
        self.replay.failure='G3';a=self.attestor()
        with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
        self.assertTrue(a.latched);self.assertTrue(self.stops);self.assertFalse(a.resolution_reserved)
        self.replay.failure=None
        with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
        self.replay.answer=True;a=self.attestor()
        with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
    def test_missing_corrupt_source_and_evidence_never_admit(self):
        for filename in ('source.py','evidence.json'):
            original=(self.root/filename).read_bytes();a=self.attestor()
            (self.root/filename).write_bytes(b'tampered')
            with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
            (self.root/filename).write_bytes(original)
        (self.root/'evidence.json').unlink();a=self.attestor()
        with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
    def test_wrong_actor_epoch_target_image_and_stale_snapshot_latch(self):
        a=self.boot()
        with self.assertRaises(Blocked):a.before_dispatch(replace(self.binding,actor_ref='B'),self.target,'a'*32)
        a=self.boot()
        with self.assertRaises(Blocked):a.before_dispatch(self.binding,self.target,'b'*32)
        for field,value in [('target',replace(self.target,started_at='restarted')),('holder_image','sha256:'+'9'*64),
                            ('observed_at',90),('observed_at',101)]:
            original=self.view;a=self.boot();self.view=replace(self.view,**{field:value})
            with self.assertRaises(Blocked):a.before_dispatch(self.binding,self.target,'a'*32)
            self.view=original
    def test_resource_policy_platform_failure_and_expiry_are_fail_closed(self):
        for gate in ('G4','G5','G6','platform'):
            a=self.boot();self.replay.failure=gate
            with self.assertRaises(Blocked):a.before_dispatch(self.binding,self.target,'a'*32)
            self.replay.failure=None
        a=self.boot();self.now=200
        with self.assertRaises(Blocked):a.before_dispatch(self.binding,self.target,'a'*32)
    def test_symlink_missing_replay_and_missing_gate_cannot_be_turned_into_receipt(self):
        (self.root/'source.py').unlink();(self.root/'source.py').symlink_to(self.root/'evidence.json')
        a=self.attestor()
        with self.assertRaises(Blocked):a.before_resolve(self.binding,self.target)
        with self.assertRaises(TypeError):ProofReplay()
    def test_lost_ack_and_writer_failure_do_not_replay_start(self):
        path=self.root/'journal.jsonl';j=Journal(path,'run-A','d'*64);ledger=OperationLedger(j)
        ledger.reserve('active-A','active')
        recovered=OperationLedger(Journal(path,'run-A','d'*64))
        with self.assertRaises(Blocked):recovered.reserve('active-A','active')
        ledger.acknowledge('active-A','native-42')
        with self.assertRaises(Blocked):ledger.acknowledge('active-A','native-43')
        class BrokenJournal:
            events=[]
            def append(self,*args):raise OSError('ENOSPC')
        with self.assertRaises(OSError):OperationLedger(BrokenJournal()).reserve('login-A','login')

if __name__=='__main__':unittest.main()
