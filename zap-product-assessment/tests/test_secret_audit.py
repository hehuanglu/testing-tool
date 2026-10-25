import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from zap_assessment.capabilities import SINKS, LIFECYCLE
from zap_assessment.secret_audit import CanaryAuditor


def encoded_forms(secret):
    raw = secret.encode()
    percent = ''.join('%%%02X' % b for b in raw)
    return {
        'raw-utf8': raw,
        'base64-standard': base64.b64encode(raw),
        'base64-standard-unpadded': base64.b64encode(raw).rstrip(b'='),
        'base64-url': base64.urlsafe_b64encode(raw),
        'base64-url-unpadded': base64.urlsafe_b64encode(raw).rstrip(b'='),
        'url-percent-upper': percent.encode(),
        'url-percent-lower': percent.lower().encode(),
        'url-percent-mixed': ''.join(c.lower() if i%2 else c for i,c in enumerate(percent)).encode(),
        'json-escape': json.dumps(secret, ensure_ascii=True).encode(),
        'json-unicode-all': ''.join('\\u%04x' % ord(c) for c in secret).encode(),
        'nested-base64-json': json.dumps(base64.b64encode(raw).decode()).encode(),
        'nested-url-json': json.dumps(quote(secret, safe='')).encode(),
    }


class SecretAuditTests(unittest.TestCase):
    def setUp(self):
        # Synthetic test value, never a live credential.
        self.secret = 'fixture-Canary+/"\\_unique-secret'
        self.auditor = CanaryAuditor([self.secret])
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        (self.root/'clear').write_bytes(b'{"safe":true}')
        self.inventory = [{'sinkId': s, 'lifecycle': c, 'path': 'clear', 'reader': 'utf8'}
                          for s in sorted(SINKS) for c in sorted(LIFECYCLE)]

    def tearDown(self):
        self.tmp.cleanup()

    def test_each_encoding_detected_in_embedded_text(self):
        for name, encoded in encoded_forms(self.secret).items():
            with self.subTest(encoding=name):
                self.assertTrue(self.auditor.matches(b'prefix: ' + encoded + b' suffix'))

    def test_unicode_utf8_percent_json_and_base64(self):
        secret = 'fixture-mật-khẩu-bí-mật'
        auditor = CanaryAuditor([secret])
        for name, blob in encoded_forms(secret).items():
            with self.subTest(encoding=name):
                self.assertTrue(auditor.matches(blob))

    def test_seeded_text_controls_for_every_sink_and_lifecycle(self):
        inv = [{**r, 'path': r['sinkId'] + '-' + r['lifecycle']} for r in self.inventory]
        for encoding, blob in encoded_forms(self.secret).items():
            with self.subTest(encoding=encoding):
                for row in inv:
                    (self.root/row['path']).write_bytes(blob)
                result = self.auditor.audit(self.root, inv)
                self.assertEqual('fail', result['auditStatus'])
                self.assertEqual(len(inv), sum(x['status'] == 'leak' for x in result['results']))
                self.assertFalse(self.auditor.matches(json.dumps(result).encode()))

    def test_clear_synthetic_files_cannot_grant_g3(self):
        result = self.auditor.audit(self.root, self.inventory)
        self.assertEqual('clear', result['auditStatus'])
        self.assertEqual('blocked', result['g3Status'])

    def test_missing_inventory_pair_is_not_silent_skip(self):
        with self.assertRaises(ValueError):
            self.auditor.audit(self.root, self.inventory[:-1])

    def test_duplicate_inventory_pair_rejected(self):
        with self.assertRaises(ValueError):
            self.auditor.audit(self.root, [*self.inventory[:-1], self.inventory[0]])

    def test_unreadable_sink_blocks(self):
        self.inventory[0]['path'] = 'missing'
        self.assertEqual('blocked', self.auditor.audit(self.root, self.inventory)['auditStatus'])

    def test_binary_database_needs_decoder_even_without_match(self):
        self.inventory[0]['reader'] = 'zap-hsqldb-unproven'
        self.assertEqual('blocked', self.auditor.audit(self.root, self.inventory)['auditStatus'])
        (self.root/'binary').write_bytes(b'\xff\x00')
        self.inventory[0].update(path='binary', reader='utf8')
        self.assertEqual('blocked', self.auditor.audit(self.root, self.inventory)['auditStatus'])

    def test_symlink_parent_link_hardlink_fifo_traversal_blocked(self):
        (self.root/'alias').symlink_to(self.root/'clear')
        (self.root/'dir-alias').symlink_to(self.root, target_is_directory=True)
        (self.root/'original').write_bytes(b'clear')
        os.link(self.root/'original', self.root/'hardlink')
        os.mkfifo(self.root/'pipe')
        for path in ('alias', 'dir-alias/clear', 'hardlink', 'pipe', '../clear'):
            with self.subTest(path=path):
                self.inventory[0]['path'] = path
                self.assertEqual('blocked', self.auditor.audit(self.root, self.inventory)['auditStatus'])

    def test_size_bound_is_fail_closed(self):
        with (self.root/'large').open('wb') as stream:
            stream.truncate(8*1024*1024+1)
        self.inventory[0]['path'] = 'large'
        self.assertEqual('blocked', self.auditor.audit(self.root, self.inventory)['auditStatus'])

    def test_nested_decoder_has_global_work_budget(self):
        calls=[]
        def branching(*args,**kwargs):
            calls.append(True)
            return b' '.join([b'YWJjZGVmZ2hpamtsbW5vcA==']*200)
        with patch('zap_assessment.secret_audit.base64.b64decode',side_effect=branching):
            self.assertFalse(self.auditor.matches(b' '.join([b'YWJjZGVmZ2hpamtsbW5vcA==']*200)))
        self.assertLessEqual(len(calls),256)

    def test_secret_response_and_session_headers_denied(self):
        for response in ({'body': self.secret}, {'headers': {'sEt-CoOkIe': 'unrecognized-new-secret'}},
                         {'headers': {'Authorization': 'unknown-token'}}):
            self.assertFalse(self.auditor.response_safe(response))
        self.assertTrue(self.auditor.response_safe({'body':'{"ok":true}', 'headers': {}}))


if __name__ == '__main__':
    unittest.main()
