import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import copy
import importlib.util
from types import SimpleNamespace

from zap_assessment.errors import Blocked
from zap_assessment.private_source import TmpfsSourceZone,TrackedSourceReference


class PrivateSourceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name).resolve();self.root.chmod(0o700)
        self.values={'A':{'username':'A','password':'owned-unique-secret-A-123456'},
                     'B':{'username':'B','password':'owned-unique-secret-B-123456'}}
        self.events=[];self.zone=TmpfsSourceZone(self.root/'source',run_id='run-A',plan_hash='a'*64)
        self.mount=patch('zap_assessment.private_source.mount_type',return_value='tmpfs');self.mount.start()
    def tearDown(self):self.mount.stop();self.tmp.cleanup()
    def create(self):return self.zone.create(self.values)

    def test_source_file_resolves_by_private_reference_and_only_metadata_leaves(self):
        meta=self.create();ref=self.zone.reference('A',self.events.append)
        self.assertEqual(self.values['A'],ref.resolve(actor_ref='A',forbidden_roots=[self.root/'repo']))
        public=json.dumps([meta,self.events])
        for row in self.values.values():self.assertNotIn(row['password'],public)
        self.assertFalse(meta['contentHashesIncluded']);self.assertFalse(meta['sourceValuesIncluded'])
        self.assertEqual(0o600,meta['files'][0]['mode']);self.assertEqual(1,meta['files'][0]['links'])
        self.assertEqual('private_source_resolved',self.events[0]['event'])

    def test_unknown_actor_wrong_binding_and_repository_source_refuse(self):
        self.create();ref=self.zone.reference('A',self.events.append)
        with self.assertRaises(Blocked):ref.resolve(actor_ref='B',forbidden_roots=[self.root/'repo'])
        with self.assertRaises(Blocked):ref.resolve(actor_ref='A',forbidden_roots=[self.root])
        with self.assertRaises(Blocked):self.zone.reference('C',self.events.append)
        self.assertEqual([],self.events)

    def test_file_replacement_mutation_alias_permission_or_extra_file_block(self):
        for fault in ('replace','content','symlink','hardlink','permission','extra'):
            with self.subTest(fault=fault),tempfile.TemporaryDirectory(dir=self.root) as t:
                zone=TmpfsSourceZone(Path(t)/'source',run_id='run',plan_hash='b'*64);zone.create(self.values)
                p=zone.path/'A.json'
                if fault=='replace':raw=p.read_bytes();p.unlink();p.write_bytes(raw);p.chmod(0o600)
                if fault=='content':p.write_bytes(p.read_bytes().replace(b'secret-A',b'secret-X'))
                if fault=='symlink':p.unlink();p.symlink_to(zone.path/'B.json')
                if fault=='hardlink':os.link(p,Path(t)/'copy')
                if fault=='permission':p.chmod(0o644)
                if fault=='extra':(zone.path/'unexpected').write_text('extra')
                with self.assertRaises(Blocked):zone.metadata()

    def test_non_tmpfs_and_insecure_parent_block_before_source_creation(self):
        with patch('zap_assessment.private_source.mount_type',return_value='ext4'):
            with self.assertRaises(Blocked):self.create()
        self.assertFalse(self.zone.path.exists())
        self.root.chmod(0o755)
        with self.assertRaises(Blocked):self.create()
        self.assertFalse(self.zone.path.exists())

    def test_unsupported_source_content_or_second_creation_does_not_overwrite(self):
        wrong={'A':self.values['A'],'B':{'username':'A','password':'invalid-but-long-password'}}
        with self.assertRaises(Blocked):self.zone.create(wrong)
        self.assertFalse(self.zone.path.exists())
        self.create();before=(self.zone.path/'A.json').read_bytes()
        with self.assertRaises(Blocked):self.create()
        self.assertEqual(before,(self.zone.path/'A.json').read_bytes())

    def test_journal_failure_cannot_return_source_credential(self):
        self.create()
        def fail(_):raise OSError('journal-unavailable')
        ref=self.zone.reference('A',fail)
        with self.assertRaises(OSError):ref.resolve(actor_ref='A',forbidden_roots=[self.root/'repo'])


class GuardPrivateSourceTests(unittest.TestCase):
    def test_guard_private_file_reference_has_no_source_value_in_control_or_journal(self):
        from zap_assessment import w5_scanner_fixture as f
        from zap_assessment.opaque_canary import validate_source_boundary
        with tempfile.TemporaryDirectory() as t:
            root=Path(t).resolve();fixture=root/'fixture';fixture.mkdir();private=root/'private';private.mkdir(mode=0o700)
            (fixture/'w5-binding.json').write_text(json.dumps({'runId':'owned-private','planHash':'a'*64,'sourceMode':'private-file'}))
            state=copy.deepcopy(f.STATE);state.update(seed=None,session=None,source_zone=None,case='source-case')
            with patch.object(f,'ROOT',fixture),patch.object(f,'PRIVATE_SOURCE_ROOT',private/'w5-private-source'), \
                    patch.dict(f.STATE,state,clear=True),patch.object(f.secrets,'token_hex',return_value='b'*64), \
                    patch('zap_assessment.private_source.mount_type',return_value='tmpfs'):
                self.assertFalse(f.control({'op':'source-status'})['sourceCreated'])
                bound=f.control({'op':'auditor-bind'});status=f.control({'op':'source-status'})
                validate_source_boundary(bound,source_kind='owned-guard-private-file-reference')
                with self.assertRaises(ValueError):validate_source_boundary(bound)
                candidate=f.make_session('A');self.assertIsInstance(candidate.broker._reference,TrackedSourceReference)
                value=candidate.broker._reference.resolve(actor_ref='A',forbidden_roots=[fixture])
                public=json.dumps([bound,status])+(fixture/'auth-source.jsonl').read_text()+(fixture/'auth-reference.jsonl').read_text()
                self.assertNotIn(value['password'],public);self.assertFalse(status['sourceValuesIncluded'])
                self.assertFalse((fixture/'A.json').exists());self.assertTrue((private/'w5-private-source/A.json').exists())
                (private/'unexpected-file').write_text('unexpected persistence')
                with self.assertRaises(ValueError):f.control({'op':'source-status'})


SPEC=importlib.util.spec_from_file_location('private_w5_contract',Path(__file__).resolve().parents[1]/'scripts/remediation_w5_scanner.py')
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)


class PrivateSourceScannerContractTests(unittest.TestCase):
    def plan(self):
        return {'schemaVersion':'w5-scanner-plan/1.1','runId':'owned','sourceMode':'private-file',
                'sourceContract':'owned-private-source/1.0','allowedSourceZone':'/tmp/w5-private-source',
                'secretSource':C.PRIVATE_SECRET_SOURCE,'actorRef':'A','cases':['success','crash'],
                'runtimePins':{'python':'python@sha256:'+'b'*64}}
    def proof(self):
        p=self.plan();h=C.digest(p)
        info={'inode':10,'device':20,'bytes':100,'uid':1003,'gid':1003,'links':1,'mode':0o600,'mtimeNs':123,'ctimeNs':124}
        files=[{'actorRef':a,'referenceId':'owned-private-file:'+a,'relativePath':a+'.json',**info,'inode':i} for i,a in enumerate(('A','B'),11)]
        meta={'schemaVersion':'owned-private-source/1.0','runId':'owned','planHash':h,
              'sourceKind':'owned-guard-private-file-reference','filesystem':'tmpfs','zonePath':'/tmp/w5-private-source',
              'zone':{**info,'mode':0o700,'links':2},'files':files,'sourceValuesIncluded':False,'contentHashesIncluded':False}
        receipts=[]
        for stage in ['before-source','after-source','case-success']:
            exists=stage!='before-source'
            receipts.append({'stage':stage,'containerId':'a'*64,'imageId':'sha256:'+'b'*64,
                'holderUser':'1003:1003','readonlyRoot':True,'tmpfsOptions':['rw','size=16m','uid=1003','gid=1003','mode=0700'],
                'sourceStatus':{'sourceMode':'private-file','sourceCreated':exists,'sourceMetadata':copy.deepcopy(meta) if exists else None,
                                'tmpfsPaths':['w5-control.sock','w5-private-source'] if exists else ['w5-control.sock'],'sourceValuesIncluded':False}})
        refs=[{'caseId':'success','event':'private_source_resolved','runId':'owned','planHash':h,
               'sourceKind':'owned-guard-private-file-reference','sourceValuesIncluded':False,'contentHashesIncluded':False,
               'source':files[0],'atMonotonic':1}]
        target=[{'caseId':'success','event':'login','atMonotonic':2}]
        journal=SimpleNamespace(events=[{'kind':'ack','data':{'action':'container-create','resource':'zpa-owned-fixture','containerId':'a'*64}}])
        return p,{'privateSourceReceipts':receipts},refs,target,journal

    def test_private_source_explicit_contract_does_not_expand_legacy_mode(self):
        self.assertEqual('private-file',C.source_mode(self.plan()))
        self.assertEqual('generated',C.source_mode({'schemaVersion':'w5-scanner-plan/1.0'}))
        for key,value in [('sourceContract','wrong'),('sourceMode','product'),('allowedSourceZone','/fixture/private')]:
            p=self.plan();p[key]=value
            with self.assertRaises(Blocked):C.source_mode(p)
        with self.assertRaises(Blocked):C.source_mode({'schemaVersion':'w5-scanner-plan/1.0','sourceMode':'private-file'})

    def test_complete_source_receipts_prove_diagnostic_without_admission(self):
        p,r,refs,target,journal=self.proof()
        result=C.verify_source_receipts(r,p,refs,target,journal)
        self.assertEqual('private-file-diagnostic-pass',result['sourceContractStatus'])
        self.assertFalse(result['operationalAdmission'])

    def test_wrong_actor_file_mutation_stale_time_and_rehashed_receipts_block(self):
        for fault in ('actor','file-identity','uid','disk','time','creation-ack','missing','secret-value'):
            p,r,refs,target,journal=self.proof()
            if fault=='actor':refs[0]['source']['actorRef']='B'
            elif fault=='file-identity':r['privateSourceReceipts'][-1]['sourceStatus']['sourceMetadata']['files'][0]['inode']+=1
            elif fault=='uid':r['privateSourceReceipts'][-1]['holderUser']='0:0'
            elif fault=='disk':r['privateSourceReceipts'][-1]['sourceStatus']['sourceMetadata']['filesystem']='ext4'
            elif fault=='time':refs[0]['atMonotonic']=3
            elif fault=='creation-ack':journal.events[0]['data']['containerId']='c'*64
            elif fault=='missing':r['privateSourceReceipts'].pop()
            else:r['privateSourceReceipts'][-1]['sourceStatus']['sourceValuesIncluded']=True
            # Re-encode the mutated receipt: checksum consistency cannot repair semantics.
            r=json.loads(json.dumps(r))
            with self.subTest(fault=fault),self.assertRaises(Blocked):C.verify_source_receipts(r,p,refs,target,journal)


if __name__=='__main__':unittest.main()
