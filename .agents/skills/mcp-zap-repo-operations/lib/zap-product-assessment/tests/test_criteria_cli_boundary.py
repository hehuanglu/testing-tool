"""Actual entrypoint tests with no network or nested executor process allowed."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from types import SimpleNamespace

from test_criteria_workflow import working, approve
from zap_assessment.criteria_delegation import Coordinator, make_packet
from zap_assessment.product_scope import apply_completion
from zap_assessment.product_scope_cli import closure_work_state, inspect_resume, residual_context, safe_review_output


ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / 'scripts/product_assessment.py'


class CriteriaCliBoundaryTests(unittest.TestCase):
    def test_summary_redacts_opaque_fixture_credentials_and_keeps_semantic_ids(self):
        value = {'setupToken': 'opaque-setup-value', 'nested': [{'session_token': 'opaque-session-value',
            'passwordValue': 'opaque-password-value', 'set-cookie': 'opaque-cookie-value'}],
            'caseId': 'issueAccessToken:CUSTOMER', 'basis': 'password validation'}
        result = safe_review_output(value)
        self.assertEqual(result['setupToken'], '[private]')
        self.assertEqual(set(result['nested'][0].values()), {'[private]'})
        self.assertEqual(result['caseId'], 'issueAccessToken:CUSTOMER')
        self.assertEqual(result['basis'], 'password validation')
        self.assertEqual(value['setupToken'], 'opaque-setup-value')

    def invoke(self, directory, *arguments):
        guard = directory / 'guard'
        guard.mkdir(exist_ok=True)
        (guard / 'sitecustomize.py').write_text(
            "import sys\n"
            "def guard(event, args):\n"
            "    if event in ('socket.connect', 'subprocess.Popen', 'os.system'):\n"
            "        raise RuntimeError('offline CLI attempted external effect')\n"
            "sys.addaudithook(guard)\n")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=str(guard) + os.pathsep + str(ROOT / 'src'))
        return subprocess.run([sys.executable, '-B', str(ENTRY), 'scope', *arguments],
                              cwd=directory, env=env, capture_output=True, text=True, timeout=30)

    def inputs(self, directory, run):
        path = directory / 'private-working.json'
        path.write_text(json.dumps(run))
        (directory / 'alerts.json').write_text('{"alerts":[]}')
        return path

    def test_real_entrypoint_revision_review_and_finalize(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary)
            run = working()
            # Discovery/legacy metadata cannot become new v2 assignment or closure.
            run.update(responsibilityInventory={'cases': [{'caseId': 'unassigned'}]},
                       assessmentRound={'version': 1, 'status': 'open'}, taskCompletion='partial')
            path = self.inputs(p, run)
            digest = self.invoke(p, 'criteria-digest', '--run', str(path), '--kind', 'plan')
            self.assertEqual(digest.returncode, 0, digest.stderr)
            self.assertEqual(len(json.loads(digest.stdout)['digest']), 64)
            review = self.invoke(p, 'criteria-review', '--run', str(path))
            self.assertTrue(json.loads(review.stdout)['eligibleForCompletion'])
            result = self.invoke(p, 'report', '--run', str(path), '--alerts', str(p / 'alerts.json'),
                                 '--output', str(p / 'reports'), '--finalize-round')
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((p / 'reports/RUN.json').read_text())
            self.assertEqual(report['assessmentStatus'], 'completed')
            self.assertNotIn('taskCompletion', report)
            self.assertEqual(report['criterionCounts']['met'], 1)
            self.assertEqual(json.loads((p / 'reports/SCOPE_ALERTS.json').read_text())['alerts'], [])
            projected = self.invoke(p, 'criteria-review', '--run', str(p / 'reports/RUN.json'))
            self.assertNotEqual(projected.returncode, 0)

    def test_stale_approval_and_pending_are_not_finalizable(self):
        for change in ('oracle', 'target', 'pending'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as temporary:
                p = Path(temporary)
                run = working()
                if change == 'oracle':
                    run['criteriaWorkflow']['criteria'][0]['oracle'] = 'changed oracle'
                elif change == 'target':
                    run['criteriaWorkflow']['plan']['authority']['target'] = 'https://foreign.test'
                else:
                    run['criteriaWorkflow']['caseResults'] = []
                path = self.inputs(p, run)
                result = self.invoke(p, 'report', '--run', str(path), '--alerts', str(p / 'alerts.json'),
                                     '--output', str(p / 'reports'), '--finalize-round')
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertFalse((p / 'reports').exists())
                reviewed = json.loads(result.stdout)
                self.assertFalse(reviewed['eligibleForCompletion'])
                self.assertEqual(reviewed['criterionCounts']['pending'], 1)

    def test_old_run_cannot_hide_worker_intent_or_lease(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary)
            run = working()
            cw = run['criteriaWorkflow']
            cw['plan']['delegation'] = {'allowed': True}
            cw['plan']['cases'][0]['actions'] = [dict(id='read', caseId='T1', effect='read')]
            approve(run)
            run['coordinatorState'] = dict(directory=str(p / 'coord'), assessmentId='A1')
            old = copy.deepcopy(run)
            coordinator = Coordinator(p / 'coord', 'A1')
            packet = make_packet(run, 'task', ['T1'], 'worker')
            coordinator.acquire(run, packet)
            with self.assertRaises(TimeoutError):
                coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0],
                                     lambda action: (_ for _ in ()).throw(TimeoutError('lost ACK')))
            path = self.inputs(p, old)
            result = self.invoke(p, 'report', '--run', str(path), '--alerts', str(p / 'alerts.json'),
                                 '--output', str(p / 'reports'), '--finalize-round')
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertFalse((p / 'reports').exists())
            self.assertEqual(coordinator.status()['tasks'][0]['pendingActionIds'], ['read'])

    def test_packet_worker_merge_review_and_export_through_real_cli(self):
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary)
            run = working(None)
            run['criteriaWorkflow']['plan']['delegation'] = {'allowed': True}
            approve(run)
            Coordinator(p / 'coord', 'A1')
            run['coordinatorState'] = dict(directory=str(p / 'coord'), assessmentId='A1')
            path = self.inputs(p, run)
            made = self.invoke(p, 'criteria-packet', '--run', str(path), '--task-id', 'W1',
                               '--worker-id', 'worker', '--case-id', 'T1', '--output', str(p / 'packet.json'))
            self.assertEqual(made.returncode, 0, made.stderr)
            packet = json.loads((p / 'packet.json').read_text())
            # This worker result is a synthetic retained observation, not a live executor.
            observation = working()
            result = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
            result.update(operations=observation['operations'],
                          caseResults=observation['criteriaWorkflow']['caseResults'])
            (p / 'result.json').write_text(json.dumps(result))
            merged = self.invoke(p, 'criteria-merge', '--run', str(path), '--packet', str(p / 'packet.json'),
                                 '--result', str(p / 'result.json'), '--output', str(p / 'merged.json'))
            self.assertEqual(merged.returncode, 0, merged.stderr)
            reviewed = self.invoke(p, 'criteria-review', '--run', str(p / 'merged.json'))
            self.assertTrue(json.loads(reviewed.stdout)['eligibleForCompletion'])
            reported = self.invoke(p, 'report', '--run', str(p / 'merged.json'), '--alerts', str(p / 'alerts.json'),
                                   '--output', str(p / 'reports'), '--finalize-round')
            self.assertEqual(reported.returncode, 0, reported.stderr)
            self.assertEqual(json.loads((p / 'reports/RUN.json').read_text())['criterionCounts']['met'], 1)
            packet['planRevision'] = 'stale-worker-plan'
            (p / 'packet.json').write_text(json.dumps(packet))
            rejected = self.invoke(p, 'criteria-merge', '--run', str(path), '--packet', str(p / 'packet.json'),
                                   '--result', str(p / 'result.json'), '--output', str(p / 'invalid-merge.json'))
            self.assertNotEqual(rejected.returncode, 0)
            self.assertFalse((p / 'invalid-merge.json').exists())

    def test_legacy_completion_and_recovery_helpers_fail_closed_on_v2(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self.inputs(Path(temporary), working())
            with self.assertRaisesRegex(ValueError, 'legacy'):
                apply_completion(working(), {})
            with self.assertRaisesRegex(ValueError, 'legacy'):
                inspect_resume(path)
            with self.assertRaisesRegex(ValueError, 'legacy'):
                closure_work_state(SimpleNamespace(run=path))
            with self.assertRaisesRegex(ValueError, 'legacy'):
                residual_context({}, {}, working(), {})
            reviewer_path = ROOT.parents[1] / 'scripts/review_open_work.py'
            spec = importlib.util.spec_from_file_location('legacy_review_boundary', reviewer_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            with self.assertRaisesRegex(ValueError, 'legacy'):
                module.review_session(working())

    def test_report_publication_holds_lease_lock_until_bundle_written(self):
        from zap_assessment import criteria_reporting
        with tempfile.TemporaryDirectory() as temporary:
            p = Path(temporary)
            run = working()
            run['criteriaWorkflow']['plan']['delegation'] = {'allowed': True}
            approve(run)
            coordinator = Coordinator(p / 'coord', 'A1')
            run['coordinatorState'] = dict(directory=str(p / 'coord'), assessmentId='A1')
            packet = make_packet(run, 'later-task', ['T1'], 'worker')
            acquired = threading.Event()
            started = threading.Event()
            errors = []
            thread = None
            original = criteria_reporting.write_bundle

            def acquire():
                started.set()
                try:
                    coordinator.acquire(run, packet)
                    acquired.set()
                except BaseException as error:
                    errors.append(error)

            def guarded_write(*args, **kwargs):
                nonlocal thread
                thread = threading.Thread(target=acquire)
                thread.start()
                self.assertTrue(started.wait(1))
                self.assertFalse(acquired.wait(.1), 'lease changed before snapshot publication')
                return original(*args, **kwargs)

            try:
                with patch.object(criteria_reporting, 'write_bundle', side_effect=guarded_write):
                    criteria_reporting.publish_reports(p / 'reports', run, [], finalize=True)
            finally:
                if thread is not None:
                    thread.join(3)
                    self.assertFalse(thread.is_alive())
            self.assertFalse(errors, errors)
            self.assertTrue(acquired.is_set())
            coordinator.release(run, packet)


if __name__ == '__main__':
    unittest.main()
