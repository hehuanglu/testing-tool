import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from zap_assessment.contracts import Blocked, validate
from zap_assessment.evidence import EvidenceInvalid, publish, verify_bundle
from support.verification_fixture import encoded, make_bundle, sha
from support.verification_corpus import cases

PACKAGE = Path(__file__).resolve().parents[1]


class VerificationV2Tests(unittest.TestCase):
    def test_bound_fixture_is_verified_without_granting_security_approval(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh')
            result = verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])
            self.assertTrue(result['verified'])
            self.assertEqual(result['applicationOracleCounts'], {'pass': 1, 'fail': 0, 'inconclusive': 0})
            self.assertEqual(result['securityVerdict'], 'inconclusive')
            self.assertEqual(result['gateDecision'], 'block')
            self.assertEqual(result['coverageEvidenceStatus'], 'complete')
            self.assertEqual(result['evidenceStatus'], 'incomplete')

    def test_full_declared_adversarial_corpus(self):
        for case in cases():
            with self.subTest(case=case['caseId']), tempfile.TemporaryDirectory() as temp:
                options = {'tag': case['caseId'], 'variants': (case['variant'],), **case['options']}
                bundle = make_bundle(Path(temp) / 'directory-not-used-as-identity', **options)
                if case['mutate']:
                    case['mutate'](bundle)
                try:
                    result = verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])
                except Blocked:
                    self.assertFalse(case['expectedVerified'])
                else:
                    self.assertTrue(case['expectedVerified'])
                    self.assertTrue(result['verified'])
                    self.assertEqual(result['gateDecision'], 'block')
                    self.assertNotEqual(result['securityVerdict'], 'pass')
                    self.assertFalse(result['securityApproval'])
                    self.assertFalse(result['liveAssessmentPermitted'])

    def test_verifier_never_calls_builder_or_opens_network_or_process(self):
        import zap_assessment.coverage
        for module in ('verification.py', 'oracle_verification.py'):
            tree = ast.parse((PACKAGE / 'src/zap_assessment' / module).read_text())
            imports = [node.module or '' for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)]
            self.assertFalse(any(m.endswith('coverage') or 'finalsource_p0' in m for m in imports))
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'independent')
            with patch('zap_assessment.coverage.evaluate', side_effect=AssertionError('builder called')), \
                    patch('socket.socket', side_effect=AssertionError('network called')), \
                    patch('subprocess.Popen', side_effect=AssertionError('process started')):
                result = verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])
            self.assertEqual(result['applicationOracleCounts']['pass'], 1)

    def test_independence_when_builder_is_perturbed(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'violation', variants=('violation',))
            with patch('zap_assessment.coverage.evaluate', return_value={'oracleResult': 'pass'}):
                result = verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])
            self.assertEqual(result['securityVerdict'], 'fail')
            self.assertEqual(result['applicationOracleCounts']['fail'], 1)

    def test_external_pin_required_and_no_legacy_downgrade_bypass(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh')
            for pin in (None, '0' * 64, 'invalid'):
                with self.subTest(pin=pin), self.assertRaises(Blocked):
                    verify_bundle(bundle['root'], expected_plan_hash=pin)
            value = json.loads((bundle['root'] / 'manifest.json').read_bytes())
            value.update(schemaVersion='1.4', planHash='0' * 64)
            (bundle['root'] / 'manifest.json').write_bytes(encoded(value))
            (bundle['root'] / 'manifest.sha256').write_text(sha(encoded(value)) + '\n')
            with self.assertRaisesRegex(EvidenceInvalid, 'external_plan_pin_mismatch'):
                verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])

    def test_cli_verification_exit0_can_preserve_application_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh', variants=('violation',))
            before = {p.relative_to(bundle['root']): p.read_bytes() for p in bundle['root'].rglob('*') if p.is_file()}
            cmd = [sys.executable, '-m', 'zap_assessment.cli', 'verify', str(bundle['root']),
                   '--expect-plan-hash', bundle['planHash']]
            run = subprocess.run(cmd, cwd=PACKAGE, capture_output=True,
                                 env={**os.environ, 'PYTHONPATH': str(PACKAGE / 'src')})
            self.assertEqual(run.returncode, 0, run.stderr.decode())
            result = json.loads(run.stdout)
            self.assertEqual(result['securityVerdict'], 'fail')
            self.assertEqual(result['assessmentExitCode'], 1)
            after = {p.relative_to(bundle['root']): p.read_bytes() for p in bundle['root'].rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            missing = subprocess.run(cmd[:-2], cwd=PACKAGE, capture_output=True,
                                     env={**os.environ, 'PYTHONPATH': str(PACKAGE / 'src')})
            self.assertEqual(missing.returncode, 2)
            self.assertEqual(json.loads(missing.stdout)['gateDecision'], 'block')

    def test_supported_schema_versions_do_not_fall_back(self):
        for version in ('0.0', '2.1', '9.0', ['2.0'], None):
            with self.subTest(version=version), self.assertRaises(Blocked):
                validate('manifest', {'schemaVersion': version})
        for version in ('1.0', '1.1', '1.2', '1.3', '1.4'):
            with self.subTest(version=version), self.assertRaises(Blocked):
                validate('manifest', {'schemaVersion': version})  # select its real schema, fail required fields

    def test_v2_publisher_refuses_before_writing(self):
        with tempfile.TemporaryDirectory() as temp:
            staging = Path(temp) / 'staging'; staging.mkdir()
            with self.assertRaisesRegex(EvidenceInvalid, 'verification-only'):
                publish(staging, Path(temp) / 'destination', {'schemaVersion': '2.0'})
            self.assertEqual(list(staging.iterdir()), [])

    def test_manifest_duplicate_json_key_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh')
            p = bundle['root'] / 'manifest.json'
            p.write_bytes(b'{"schemaVersion":"2.0",' + p.read_bytes()[1:])
            (bundle['root'] / 'manifest.sha256').write_text(sha(p.read_bytes()) + '\n')
            with self.assertRaises(Blocked):
                verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])

    def test_unsupported_expected_schema_kind_is_blocked(self):
        with self.assertRaises(Blocked):
            validate('not-a-contract', {'schemaVersion': '2.0'})

    def test_root_symlink_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh')
            alias = Path(temp) / 'alias'; alias.symlink_to(bundle['root'], target_is_directory=True)
            with self.assertRaises(Blocked):
                verify_bundle(alias, expected_plan_hash=bundle['planHash'])

    def test_special_manifest_cannot_block_on_a_fifo(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            os.mkfifo(root / 'manifest.json')
            with self.assertRaisesRegex(EvidenceInvalid, 'must be regular'):
                verify_bundle(root, expected_plan_hash='a' * 64)

    def test_individual_file_limits_fail_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh')
            with patch('zap_assessment.verification.MAX_FILE', 128), self.assertRaises(Blocked):
                verify_bundle(bundle['root'], expected_plan_hash=bundle['planHash'])

    def test_inode_replacement_after_inventory_is_rejected(self):
        from zap_assessment.verification import BundleReader
        with tempfile.TemporaryDirectory() as temp:
            bundle = make_bundle(Path(temp) / 'fresh')
            with BundleReader(bundle['root']) as reader:
                name = bundle['documents']['observations']; p = bundle['root'] / name
                raw = p.read_bytes(); p.unlink(); p.write_bytes(raw)
                with self.assertRaises(EvidenceInvalid):
                    reader.read(name)


if __name__ == '__main__':
    unittest.main()
