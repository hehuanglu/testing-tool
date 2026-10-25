import base64
import copy
import gzip
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

from zap_assessment.opaque_canary import fingerprints,OpaqueCanaryAuditor,source_controls,PUBLIC_DB_CONTROL,validate_source_boundary
from zap_assessment.scanner_secret_audit import check_views
from zap_assessment.errors import SecretLeak
from zap_assessment import w5_scanner_fixture as fixture


class OpaqueCanaryTests(unittest.TestCase):
    def setUp(self):
        self.seed='0123456789abcdef'*4
        self.token='W5-canary-'+self.seed
        self.rows=fingerprints([self.seed,self.token,PUBLIC_DB_CONTROL])
        self.auditor=OpaqueCanaryAuditor(self.rows)

    def test_host_inventory_contains_only_hashes_and_lengths(self):
        encoded=json.dumps(self.rows)
        self.assertNotIn(self.seed,encoded);self.assertNotIn(self.token,encoded)
        self.assertFalse(hasattr(self.auditor,'_secrets'))
        self.assertTrue(all(set(row)=={'bytes','sha256'} for row in self.rows))

    def test_private_source_controls_cover_all_declared_forms(self):
        result=source_controls([self.seed,self.token,PUBLIC_DB_CONTROL])
        self.assertEqual(36,result['controls']['tested']);self.assertEqual(0,result['controls']['missed'])
        self.assertFalse(result['sourceValuesIncluded'])
        self.assertNotIn(self.seed,json.dumps(result))

    def test_embedded_base64_and_percent_json_nested_forms_detected(self):
        for raw in (self.seed.encode(),self.token.encode()):
            forms=[b'prefix'+base64.b64encode(raw).rstrip(b'=')+b'suffix',
                   b'prefix'+raw+b'suffix',
                   b''.join(('%%%02x'%b).encode() for b in raw),
                   b''.join(('\\u%04x'%b).encode() for b in raw),
                   base64.b64encode(base64.b64encode(raw))]
            for blob in forms:
                with self.subTest(length=len(raw),blobLength=len(blob)):
                    self.assertTrue(self.auditor.matches(blob))

    def test_unknown_canary_and_hash_metadata_do_not_match(self):
        self.assertFalse(self.auditor.matches(('W5-canary-'+'f'*64).encode()))
        self.assertFalse(self.auditor.matches(json.dumps(self.rows).encode()))

    def test_real_compression_reader_works_with_no_source_value_in_auditor(self):
        with self.assertRaises(SecretLeak):check_views(self.auditor,gzip.compress(self.token.encode()))

    def test_invalid_inventory_and_other_secret_families_rejected(self):
        for rows in ([],self.rows*2,[{'bytes':1,'sha256':'0'*64}]):
            with self.assertRaises(ValueError):OpaqueCanaryAuditor(rows)
        with self.assertRaises(ValueError):fingerprints(['arbitrary-product-password'])

    def test_guard_generates_private_source_once_and_refuses_host_seed(self):
        state=copy.deepcopy(fixture.STATE)
        with tempfile.TemporaryDirectory() as tmp,patch.object(fixture,'ROOT',Path(tmp)),patch.dict(fixture.STATE,state,clear=True),patch.object(fixture.secrets,'token_hex',return_value=self.seed) as generate:
            (Path(tmp)/'w5-binding.json').write_text(json.dumps({'runId':'owned','planHash':'0'*64}))
            result=fixture.control({'op':'auditor-bind'})
            validate_source_boundary(result)
            self.assertEqual(816,result['controls']['detected']);generate.assert_called_once_with(32)
            self.assertNotIn(self.seed,json.dumps(result))
            self.assertNotIn(fixture.derive(self.seed,'password-A'),json.dumps(result))
            with self.assertRaises(ValueError):fixture.control({'op':'auditor-bind'})
            with patch.object(fixture,'make_session',side_effect=AssertionError('boot accepted host source')):
                with self.assertRaises(ValueError):fixture.control({'op':'boot','seed':'untrusted-host-value','actor':'A','caseId':'bad'})

    def test_controller_has_no_private_canary_generation_or_seed_control_field(self):
        import ast
        source=(Path(__file__).resolve().parents[1]/'scripts/remediation_w5_scanner.py').read_text()
        tree=ast.parse(source)
        for call in (n for n in ast.walk(tree) if isinstance(n,ast.Call)):
            self.assertFalse(isinstance(call.func,ast.Attribute) and call.func.attr=='token_hex')
            if isinstance(call.func,ast.Attribute) and call.func.attr=='control':
                for arg in call.args:
                    if isinstance(arg,ast.Dict):self.assertNotIn('seed',[k.value for k in arg.keys if isinstance(k,ast.Constant)])


if __name__=='__main__':unittest.main()
