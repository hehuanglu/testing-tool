import base64
import gzip
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import unittest
import zipfile
import tempfile
import hashlib

from zap_assessment.scanner_secret_audit import check_views,audit_tar,audit_database,audit_tree,artifact_digest
from zap_assessment.secret_audit import CanaryAuditor
from zap_assessment.contracts import Blocked
from zap_assessment.errors import SecretLeak


class ScannerSecretAuditTests(unittest.TestCase):
    def setUp(self):
        self.secret=b'seeded-scanner-Canary-unique-001'
        self.auditor=CanaryAuditor([self.secret.decode()])

    def test_stdlib_guard_imports_without_host_dependencies(self):
        code='import zap_assessment.w5_scanner_fixture; import sys; assert "jsonschema" not in sys.modules'
        result=subprocess.run([sys.executable,'-S','-c',code],capture_output=True,
            env={**os.environ,'PYTHONPATH':str(Path(__file__).resolve().parents[1]/'src')})
        self.assertEqual(0,result.returncode)

    def test_actual_compression_controls_detected(self):
        for blob in (self.secret,gzip.compress(self.secret)):
            with self.assertRaises(Blocked):check_views(self.auditor,blob)
        stream=io.BytesIO()
        with zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED) as z:z.writestr('owned-control',self.secret)
        with self.assertRaises(Blocked):check_views(self.auditor,stream.getvalue())

    def archive(self,data,kind=tarfile.REGTYPE,link=''):
        stream=io.BytesIO()
        with tarfile.open(fileobj=stream,mode='w') as tar:
            item=tarfile.TarInfo('runtime/sink');item.type=kind;item.linkname=link
            item.size=len(data) if kind==tarfile.REGTYPE else 0
            tar.addfile(item,io.BytesIO(data) if kind==tarfile.REGTYPE else None)
        return stream.getvalue()

    def test_tar_clear_bytes_and_hash_receipt(self):
        result=audit_tar(self.auditor,self.archive(b'clear'))
        self.assertEqual(1,result['files']);self.assertEqual(0,result['canaryMatches'])

    def test_tar_leak_rejected_without_value_in_exception(self):
        with self.assertRaises(Blocked) as raised:audit_tar(self.auditor,self.archive(self.secret))
        self.assertNotIn(self.secret.decode(),str(raised.exception))

    def test_tar_links_and_special_files_block(self):
        for kind in (tarfile.SYMTYPE,tarfile.LNKTYPE,tarfile.FIFOTYPE):
            with self.subTest(kind=kind),self.assertRaises(Blocked):
                audit_tar(self.auditor,self.archive(b'',kind,'external-source'))

    def test_large_unchanged_precredential_image_file_has_exact_hash_proof(self):
        raw=self.archive(b'fixed-image-runtime-library-'*(350000))
        baseline=audit_tar(self.auditor,raw,precredential=True)
        result=audit_tar(self.auditor,raw,prior_index=baseline['paths'])
        self.assertEqual(1,result['unchangedPrecredentialFiles'])

    def test_changed_large_file_cannot_inherit_precredential_absence(self):
        raw=self.archive(b'A'*(8*1024*1024+1))
        baseline=audit_tar(self.auditor,raw,precredential=True)
        changed=self.archive(b'B'*(8*1024*1024+1))
        with self.assertRaises(Blocked):audit_tar(self.auditor,changed,prior_index=baseline['paths'])

    def database(self,data,complete=True):
        rows=[{'kind':'table','name':'HISTORY'},
              {'kind':'cell','table':'HISTORY','column':'REQHEADER','sqlType':12,'base64':base64.b64encode(data).decode()},
              {'kind':'cell','table':'HISTORY','column':'REQBODY','sqlType':-3,'base64':base64.b64encode(data).decode()}]
        if complete:rows.append({'kind':'complete','tables':1,'rows':1,'cells':2,'decodedBytes':len(data)*2})
        return b'\n'.join(json.dumps(r).encode() for r in rows)

    def test_database_text_and_binary_seeded_control(self):
        result=audit_database(self.auditor,self.database(self.secret),expect_canary=True)
        self.assertEqual(2,result['canaryMatches'])
        with self.assertRaises(Blocked):audit_database(self.auditor,self.database(self.secret))

    def test_database_positive_control_must_detect(self):
        with self.assertRaises(Blocked):audit_database(self.auditor,self.database(b'clear'),expect_canary=True)

    def test_seeded_control_requires_distinct_text_and_binary_cells(self):
        raw=self.database(self.secret).replace(b'"sqlType": -3',b'"sqlType": 12')
        with self.assertRaises(Blocked):audit_database(self.auditor,raw,expect_canary=True)

    def test_database_unknown_table_duplicate_table_and_records_after_terminal_block(self):
        raw=self.database(b'clear')
        unknown=raw.replace(b'"table": "HISTORY"',b'"table": "OTHER"')
        duplicate=b'{"kind":"table","name":"HISTORY"}\n'+raw.replace(b'"tables": 1',b'"tables": 2')
        after=raw+b'\n'+b'{"kind":"table","name":"LATE"}'
        for blob in (unknown,duplicate,after):
            with self.subTest(blobBytes=len(blob)),self.assertRaises(Blocked):audit_database(self.auditor,blob)

    def test_database_complete_inventory_required(self):
        for raw in (self.database(b'clear',False),b'{"kind":"blocked"}'):
            with self.assertRaises(Blocked):audit_database(self.auditor,raw)

    def test_database_decoder_counts_not_trusted(self):
        raw=self.database(b'clear').replace(b'"cells": 2',b'"cells": 999')
        with self.assertRaises(Blocked):audit_database(self.auditor,raw)

    def test_database_decoded_gzip_control(self):
        with self.assertRaises(Blocked):audit_database(self.auditor,self.database(gzip.compress(self.secret)))

    def test_confirmed_leak_retains_distinct_violation_type(self):
        with self.assertRaises(SecretLeak):audit_database(self.auditor,self.database(self.secret))
        with self.assertRaises(SecretLeak):audit_tar(self.auditor,self.archive(self.secret))

    def test_owned_bind_reader_detects_real_file_and_compression(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'payload').write_bytes(gzip.compress(self.secret))
            with self.assertRaises(SecretLeak):audit_tree(self.auditor,root)
            (root/'payload').write_bytes(b'clear')
            self.assertEqual(1,audit_tree(self.auditor,root)['files'])

    def test_owned_bind_alias_not_followed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'alias').symlink_to('/etc/passwd')
            with self.assertRaises(Blocked):audit_tree(self.auditor,root)

    def test_changed_sqlite_sink_requires_wal_decoder(self):
        with self.assertRaisesRegex(Blocked,'WAL'):check_views(self.auditor,b'SQLite format 3\x00'+b'clear')

    def test_large_artifact_readback_streams_full_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=b'x'*(9*1024*1024);(root/'large').write_bytes(data)
            self.assertEqual(hashlib.sha256(data).hexdigest(),artifact_digest(root,'large'))

    def test_streamed_artifact_alias_and_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').write_bytes(b'clear');(root/'alias').symlink_to(root/'data')
            for path in ('alias','../data'):
                with self.subTest(path=path),self.assertRaises((Blocked,OSError)):artifact_digest(root,path)


if __name__=='__main__':unittest.main()
