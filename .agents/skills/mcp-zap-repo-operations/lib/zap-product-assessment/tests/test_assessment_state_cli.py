import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_criteria_workflow import working
from test_operation_selection import schedule_fixture
from zap_assessment import assessment_store as store
from zap_assessment.contracts import canonical
from zap_assessment.criteria_delegation import make_packet
from zap_assessment.operator_state import default_operator


def call(*args):
    return subprocess.run([sys.executable, '-B', '-m', 'zap_assessment.product_cli', 'scope',
                           *map(str, args)], capture_output=True, text=True, timeout=15)


def packet_result(packet, operations=(), results=()):
    row = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
    return dict(row, operations=list(operations), caseResults=list(results))


class CliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.state = self.base / 'state'
        self.registry = self.base / 'registry'

    def write(self, name, value):
        path = self.base / (name + '.json')
        path.write_bytes(canonical(value))
        return path

    def check(self, *args, code=0):
        result = call(*args)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def register(self, run, operator):
        return self.check('state-init', '--run', self.write('run', run),
                          '--operator', self.write('operator', operator), '--state-dir', self.state,
                          '--registry-dir', self.registry, '--registration-id', 'fixture')

    def test_B12_D07_managed_merge_retry_after_another_commit(self):
        run, operator = schedule_fixture()
        run['fixturePrivate'] = dict(token='CANARY_SECRET')
        parent = self.register(run, operator)['generationId']
        self.assertEqual(self.check('state-resolve', '--registry-dir', self.registry,
                                   '--assessment-id', 'A1')['storePath'], str(self.state))
        self.assertEqual(self.check('state-inspect', '--state-dir', self.state)['generationId'], parent)
        self.assertEqual(self.check('state-next', '--state-dir', self.state)['nextAction']['caseId'], 'T1')
        packet = make_packet(run, 'fixture-task', ['T1'], 'coordinator')
        complete = working()
        result = packet_result(packet, complete['operations'], complete['criteriaWorkflow']['caseResults'])
        result_path = self.write('result', result)
        base_args = ('state-merge', '--state-dir', self.state, '--packet', self.write('packet', packet),
                     '--result', result_path)
        first = self.check(*base_args, '--commit-id', 'merge', '--expected-generation', parent)
        after = self.check('state-next', '--state-dir', self.state)
        self.assertEqual(after['nextAction']['caseId'], 'T2')
        self.assertNotIn('CANARY_SECRET', json.dumps(after))
        snapshot = store.load_current(self.state)
        second = store.commit_snapshot(self.state, expected_generation=first['generationId'],
            commit_id='after-merge', run=snapshot.run, operator_state=snapshot.operator)
        retry = self.check(*base_args, '--commit-id', 'merge', '--expected-generation', parent)
        self.assertTrue(retry['alreadyApplied'])
        self.assertEqual(retry['currentGenerationId'], second['generationId'])
        result['operations'][0]['status'] = 'partial'
        self.write('result', result)
        self.assertEqual(self.check(*base_args, '--commit-id', 'merge', '--expected-generation', parent,
                                    code=3)['code'], 'commit-id-conflict')
        self.assertEqual(self.check(*base_args, '--commit-id', 'new-merge',
                                    '--expected-generation', second['generationId'], code=3)['code'],
                         'merge-rejected')

    def test_B13_legacy_output_idempotent_and_preserves_input(self):
        run = working()
        source = self.write('run', run)
        packet = make_packet(run, 'fixture-task', ['T1'], 'coordinator')
        output = self.base / 'merged.json'
        args = ('criteria-merge', '--run', source, '--packet', self.write('packet', packet),
                '--result', self.write('result', packet_result(packet)), '--output', output)
        self.assertFalse(self.check(*args)['alreadyApplied'])
        self.assertTrue(self.check(*args)['alreadyApplied'])
        output.write_text('{}')
        self.assertNotEqual(call(*args).returncode, 0)
        self.assertEqual(source.read_bytes(), canonical(run))

    def test_D09_D11_diagnostics_and_generated_continuation(self):
        run = working()
        self.register(run, default_operator(run))
        self.assertEqual(self.check('state-next', '--state-dir', self.state, '--now', 'bad',
                                    code=2)['code'], 'invalid-input')
        paths = self.check('state-render', '--state-dir', self.state)
        prompt = Path(paths['CONTINUE-PROMPT.md']).read_text()
        self.assertIn(str(self.state), prompt)
        self.assertIn('whole remaining approved workflow', prompt)
        self.assertIn('state-inspect-recovery', prompt)
        skill = Path(__file__).resolve().parents[3] / 'SKILL.md'
        self.assertTrue(skill.is_file())
        self.assertIn(str(skill), prompt)
        snapshot = store.load_current(self.state)
        snapshot.run_path.write_text('{}')
        self.assertEqual(self.check('state-inspect', '--state-dir', self.state, code=4)['code'],
                         'generation-integrity')

    def test_D10_managed_effect_entrypoints_reload_and_reject_stale_packet(self):
        import contextlib
        import copy
        import io
        from unittest.mock import patch

        from test_coordinator_recovery import prepared
        from zap_assessment.product_scope_cli import main

        coord = self.base / 'coordinator'
        coord.mkdir()
        run, packet, coordinator = prepared(coord)
        operator = default_operator(run)
        self.register(run, operator)
        coordinator.acquire(run, packet)
        packet_path = self.write('packet', packet)
        snapshot = store.load_current(self.state)
        changed = copy.deepcopy(run)
        changed['criteriaWorkflow']['planRevision'] = 'P-2'
        store.commit_snapshot(self.state, expected_generation=snapshot.generation_id,
                              commit_id='new-plan', run=changed, operator_state=operator)
        with patch('zap_assessment.criteria_native_read.MCP') as transport:
            with self.assertRaises(ValueError):
                main(['criteria-native-read', '--state-dir', str(self.state),
                      '--packet', str(packet_path), '--action-id', 'read-1'])
            transport.assert_not_called()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            main(['criteria-release-task', '--state-dir', str(self.state), '--packet', str(packet_path)])
        self.assertTrue(json.loads(output.getvalue())['released'])
