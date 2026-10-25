"""Checks for the offline G0 checkpoint, not coverage/security acceptance."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from jsonschema.exceptions import ValidationError

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('remediation_w0', PACKAGE / 'scripts/remediation_w0.py')
w0 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(w0)


class OfflineCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.file = self.root / 'source.py'
        self.file.write_text('original\n')
        self.records = w0.file_records(self.root, [self.file])

    def test_unchanged_baseline_reads_back(self):
        self.assertEqual(w0.verify_records(self.root, self.records), 1)

    def test_dirty_content_change_detected_without_head_change(self):
        self.file.write_text('modified\n')
        with self.assertRaisesRegex(ValueError, 'content drift'):
            w0.verify_records(self.root, self.records)

    def test_missing_file_is_rejected(self):
        self.file.unlink()
        with self.assertRaisesRegex(ValueError, 'missing'):
            w0.verify_records(self.root, self.records)

    def test_duplicate_and_traversal_rejected(self):
        for records in [self.records * 2, [{**self.records[0], 'path': '../source.py'}]]:
            with self.subTest(records=records), self.assertRaisesRegex(ValueError, 'unsafe or duplicate'):
                w0.verify_records(self.root, records)

    def test_symlink_parent_rejected(self):
        (self.root / 'alias').symlink_to(self.root, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            w0.verify_records(self.root, [{**self.records[0], 'path': 'alias/source.py'}])

    def test_plan_or_build_inventory_drift_rejected(self):
        lock = {'planSha256': w0.sha(b'plan'), 'runtimeSha256': w0.sha(b'build')}
        w0.verify_lock(b'plan', lock, b'build')
        for plan, runtime in [(b'changed-plan', b'build'), (b'plan', b'changed-build')]:
            with self.subTest(plan=plan), self.assertRaisesRegex(ValueError, 'drift'):
                w0.verify_lock(plan, lock, runtime)

    def test_live_refusal_before_io_or_producer_creation(self):
        with patch.object(sys, 'argv', ['w0', '/does/not/exist', '--live']), \
                patch('socket.socket') as socket, \
                patch.object(w0.subprocess, 'check_output') as process, \
                patch.object(Path, 'read_bytes') as read, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(w0.main(), 2)
        socket.assert_not_called()
        process.assert_not_called()
        read.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())['targetRequests'], 0)


class PlanContractTests(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((PACKAGE / 'schemas/remediation/w0-plan.schema.json').read_text())
        self.plan = {
            'schemaVersion': '2.0', 'assessmentId': 'unit-only',
            'planKind': 'offline-remediation-development', 'releaseScope': 'R2-full-required-browser',
            'executionPolicy': {'liveTrafficPermitted': False, 'stopAt': 'G0',
                                'authorityRef': None, 'scope': 'offline-only'},
            'sourcePlan': {'path': 'plan.md', 'sha256': 'a' * 64},
            'actorRefs': ['anonymous', 'A', 'B'],
            'operations': [{'method': 'GET', 'path': '/dynamic'}],
            'operationActorDenominator': [
                {'method': 'GET', 'path': '/dynamic', 'actorRef': a, 'status': 'unknown',
                 'oracleRef': 'adapter-contract-v2', 'resourceBinding': 'required-at-live-entry'}
                for a in ['anonymous', 'A', 'B']],
            'tracks': [{'trackId': t, 'required': True, 'gates': ['unit-only']} for t in [
                'api-ownership-business', 'active-controls', 'browser-business',
                'evidence-verification', 'regression', 'alternate-product']],
            'caseIds': [f'C{i:02}' for i in range(1, 37)],
            'bindings': {}, 'oracleContract': {}, 'thresholds': {}, 'modes': [],
            'statusModel': {}, 'phaseReuse': {}}

    def test_operation_ids_not_pinned_to_historical_fixture(self):
        self.assertEqual(w0.verify_plan(self.plan, self.schema), 3)

    def test_missing_or_duplicate_required_row_rejected(self):
        for rows in [self.plan['operationActorDenominator'][:-1],
                     self.plan['operationActorDenominator'] * 2]:
            plan = copy.deepcopy(self.plan)
            plan['operationActorDenominator'] = rows
            with self.assertRaisesRegex(ValueError, 'denominator'):
                w0.verify_plan(plan, self.schema)

    def test_browser_cannot_become_optional(self):
        self.plan['tracks'][2]['required'] = False
        with self.assertRaisesRegex(ValueError, 'required R2 track'):
            w0.verify_plan(self.plan, self.schema)

    def test_no_implicit_live_authority_or_verified_row(self):
        for mutate in ('live', 'authority', 'verified'):
            plan = copy.deepcopy(self.plan)
            if mutate == 'live':
                plan['executionPolicy']['liveTrafficPermitted'] = True
            elif mutate == 'authority':
                plan['executionPolicy']['authorityRef'] = 'invented'
            else:
                plan['operationActorDenominator'][0]['status'] = 'pass'
            with self.subTest(mutate=mutate), self.assertRaises(ValidationError):
                w0.verify_plan(plan, self.schema)

    def test_missing_minimum_case_rejected(self):
        self.plan['caseIds'].remove('C36')
        with self.assertRaisesRegex(ValueError, 'catalog incomplete'):
            w0.verify_plan(self.plan, self.schema)


if __name__ == '__main__':
    unittest.main()
