"""Offline checkpoint/resume contracts, including isolated process windows.

All product/scanner state is synthetic. Worker processes receive only persisted
reports/journals plus a supplied fake current-state file; no live access occurs.
"""
import base64
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from urllib.parse import quote

from zap_assessment.active_questions import assess_question
from zap_assessment.product_scope import compact_results, continue_work, reconcile
from zap_assessment.security_scope import validate_bundle

SKILL = Path(__file__).resolve().parents[3]
HELPER = SKILL / 'scripts/review_open_work.py'
spec = importlib.util.spec_from_file_location('checkpoint_review', HELPER)
review = importlib.util.module_from_spec(spec)
spec.loader.exec_module(review)
NAMES = ('RUN.json', 'ALERTS.json', 'SCOPE_ALERTS.json')


def metadata():
    return dict(version=1, status='checkpointed', reason='context-handoff',
        updatedAt='2026-10-31T08:00:00Z',
        currentFocus=dict(questionIds=['processing'], progress='Baseline and configuration read; processing still open.'),
        nextActions=[dict(questionIds=['processing'], action='Read actor expiry and fixture state, then prepare missing processing test.',
                          readFirst=['private-fixture-ledger'], dependsOn=[])],
        revalidate=[dict(subject='actor/fixture', reason='Expiry, membership, state and quota can change.',
                         readVia='private-fixture-ledger', affects=['processing'])],
        userGuidance=dict(contextRecommendation='continue-here',
            reason='The current window remains suitable once the external dependency is resolved.',
            userAction='Send the resume prompt right here when the dependency is available.',
            resumePrompt='Continue from /synthetic/official/RUN.json; first reconcile pending state, then prepare the processing test without replay.'),
        pendingOperations=[], resourceDisposition=[])


def question_scope():
    return dict(assessmentId='synthetic-checkpoint', product='orchard', environment='offline', revision='r1', complete=True,
        sources=[dict(id='policy-source',location='synthetic-policy')],
        criteria=[dict(id='policy', originalText='Retain audit records and process valid owned updates.',
                       source=dict(id='policy-source',location='synthetic-policy'),
                       applicability=dict(status='applicable', basis='Assigned configuration and update questions'))],
        questions=[dict(id='retention', criterionIds=['policy'], question='Is retention configured for thirty days?',
                        closureCondition='Read setting and compare with policy.', requiredObservations=['setting-compared']),
                   dict(id='processing', criterionIds=['policy'], question='Does a changed title reach owned update processing?',
                        closureCondition='Observe changed title at intended processing branch with valid identity.',
                        requiredObservations=['changed-title-processed'])])


def working_run():
    return dict(product='orchard', environment='offline', operations=[], continuation=metadata(),
                taskCompletion='partial', handoffClosesTask=False,
                facts=dict(sourceRevision='stable-source', expectedRetentionDays=30, origin='https://orchard.test'))


def read_bundle(path):
    return [json.loads((path / name).read_text()) for name in NAMES]


def inventory():
    return dict(productLocation='/synthetic/orchard', track='be-authenticated', complete=True,
        cases=[dict(caseId='update', evidenceRefs=['synthetic-policy'], requiredEvidence=['state-read'],
                    actions=[dict(id='write', kind='execute', effect='mutation'),
                             dict(id='read-state', kind='reconcile-state', effect='read')])])


def worker(stage, root):
    """Two real processes model losing all controller memory between windows."""
    root = Path(root)
    live = json.loads((root / 'fake-current.json').read_text())
    if stage == 'first':
        run = working_run()
        # Derive observed units from a separate fake setting read, not requirements.
        observed = {}
        if live['retentionDays'] == run['facts']['expectedRetentionDays']:
            run['operations'] = [dict(id='setting', status='completed', type='config-review', value=live['retentionDays'])]
            observed['retention'] = dict(operationIds=['setting'], observationUnits=['setting-compared'],
                resultRead=True, outcome='matched', basis='Supplied fake deployment setting equals policy interval.')
        compact_results(root / 'official', run, {'alerts': []}, security_scope=question_scope(),
                        scope_assessment=dict(scopeRevision='r1', questionObservations=observed))
    elif stage == 'second':
        run, alerts, scope_alerts = read_bundle(root / 'official')
        before = copy.deepcopy(run['scopeAssessment']['questionObservations'])
        # Revalidation affects only upcoming work. No discovery or login function
        # is available in this worker; stable facts and old observations survive.
        reusable = live['tokenValid'] and live['fixtureState'] == 'JOINED' and live['quota'] > 0
        if not reusable:
            run['continuation']['nextActions'][0]['action'] = 'Prepare a fresh authorized actor/fixture for processing.'
        # Exercise the existing executor gate with freshly read prerequisites;
        # a stale checkpoint's ready flag cannot substitute for this readback.
        inv = inventory()
        inv['cases'][0]['prerequisites'] = ['current-actor-and-fixture']
        inv['cases'][0]['actions'] = [dict(id='next-test',kind='execute',effect='read',requires=['current-actor-and-fixture'])]
        calls = []
        def next_test(action):
            assert reusable
            calls.append(action['id'])
            return {'observations':{}}  # no processing response yet, no invented units
        continue_work(inv, {}, {'current-actor-and-fixture':reusable}, {'next-test':next_test}, persist=lambda event:None)
        assert bool(calls) == reusable
        run['continuation']['currentFocus']['progress'] = 'Prior retention observation retained; live fixture dependencies revalidated.'
        compact_results(root / 'official', run, alerts, security_scope=run['securityScope'],
                        scope_assessment=run['scopeAssessment'], overwrite=True)
        after, _, projection = read_bundle(root / 'official')
        assert after['scopeAssessment']['questionObservations'] == before
        assert after['facts'] == run['facts']
        (root / 'resume-result.json').write_text(json.dumps(dict(reusable=reusable,
            review=review.review_session(after), states={q['id']:q['coverage'] for q in projection['criteria'][0]['questions']})))
    elif stage == 'lost-ack':
        (root/'working-inventory.json').write_text(json.dumps(inventory()))
        def persist(event):
            with (root / 'journal.jsonl').open('a') as stream:
                stream.write(json.dumps(event) + '\n')
        def mutation(action):
            raise TimeoutError('synthetic ACK lost after application effect')
        result = continue_work(inventory(), {}, {}, {'write': mutation}, persist=persist, max_actions=1)
        run = {**working_run(), **result}
        run['operations'] = [dict(id='write', effect='mutation', state='unknown', outcomeUnknown=True)]
        run['continuation']['pendingOperations'] = [dict(operationRef='write', lastKnownState='unknown',
            owner='synthetic-allocation', readVia='journal.jsonl', nextAction='Read object state before any retry.')]
        run['continuation']['nextActions'][0]['readFirst'] = ['working-inventory.json','journal.jsonl']
        compact_results(root / 'official', run, {}, result)
    elif stage == 'reconcile':
        run, alerts, _ = read_bundle(root / 'official')
        attempts = [json.loads(line) for line in (root / 'journal.jsonl').read_text().splitlines()]
        def no_replay(action):
            raise AssertionError('Unknown mutation replayed')
        def read_state(action):
            assert live['mutationApplied']
            return dict(observations={'update':dict(stateReconciled=True, resultRead=True,
                evidenceUnits=['state-read'], outcome='matched')})
        # Compact reports omit technical provenance; reuse the referenced working
        # inventory rather than fabricating provenance from the sanitized report.
        inv = json.loads((root/'working-inventory.json').read_text())
        result = continue_work(inv, run['observations'], run['prerequisites'],
            {'write':no_replay, 'read-state':read_state}, attempts=attempts, persist=lambda event: None)
        assert [e['actionId'] for e in result['actionsPerformed']] == ['read-state', 'read-state']
        assert not result['observations']['update']['outcomeUnknown']
        (root / 'resume-result.json').write_text(json.dumps(result))
    else:
        raise AssertionError('unknown synthetic stage')


class WorkSessionCheckpointTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        # In-process code must never access even an accidentally configured runtime.
        self.network = patch('socket.socket', side_effect=AssertionError('network forbidden'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def publish(self, run=None, **kwargs):
        compact_results(self.root/'reports', run or working_run(), {'alerts':[]},
                        security_scope=question_scope(), overwrite=(self.root/'reports').exists(), **kwargs)
        return read_bundle(self.root/'reports')

    def window(self, stage):
        env = os.environ.copy()
        env['PYTHONDONTWRITEBYTECODE'] = '1'
        env['PYTHONPATH'] = str(SKILL/'lib/zap-product-assessment/src')
        result = subprocess.run([sys.executable, '-B', str(Path(__file__).resolve()), '--window', stage, str(self.root)],
                                env=env, capture_output=True, text=True, cwd=self.root, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_preparation_checkpoint_with_runnable_work_does_not_change_old_partial_gate(self):
        run, _, _ = self.publish()
        self.assertEqual(run['operations'], [])
        self.assertEqual((run['taskCompletion'], run['handoffClosesTask']), ('partial', False))
        checked = review.review_session(run)
        self.assertTrue(checked['checkpointReady'])
        self.assertEqual(checked['nextActionCount'], 1)
        work = dict(responsibilities=[dict(id='processing', requiredObservations=['processed'])],
                    decisions={'processing':dict(action='execute', basis='Valid baseline prepared', nextStep='Run changed-title case')})
        self.assertFalse(review.review_work(work)['canHandOffPartial'])
        work['decisions']['processing'] = dict(action='dependency', basis='Owned source unavailable', diagnosis='Missing authorized source',
            blockedBy='source access', nextStep='Provide authorized source', optionsEvaluated=[dict(option='existing source',basis='Unavailable')])
        self.assertTrue(review.review_work(work)['canHandOffPartial'])

    def test_handoff_guidance_is_checked_without_authorizing_stop_or_preventing_recovery_save(self):
        for recommendation in ('continue-here', 'new-context-recommended'):
            run = working_run()
            run['continuation']['userGuidance']['contextRecommendation'] = recommendation
            saved, _, _ = self.publish(run)
            self.assertTrue(review.review_session(saved)['checkpointReady'])
            self.assertEqual(saved['taskCompletion'], 'partial')
        for guidance in (None, [], {}, {'contextRecommendation': 'reset-budget'}):
            run = working_run()
            run['continuation']['userGuidance'] = guidance
            saved, _, _ = self.publish(run)
            checked = review.review_session(saved)
            self.assertFalse(checked['checkpointReady'])
            self.assertIn('continuation.userGuidance.resumePrompt', checked['missingInformation'])
            self.assertEqual(saved['taskCompletion'], 'partial')
            self.assertFalse(saved['handoffClosesTask'])
        # Recovery persistence mid-session is distinct from handing off to the user.
        run['continuation']['status'] = 'in-progress'
        saved, _, _ = self.publish(run)
        self.assertTrue(review.review_session(saved)['checkpointReady'])

    def test_isolated_windows_inherit_scope_results_and_selectively_revalidate_stale_dependencies(self):
        for changes in ({}, {'tokenValid':False}, {'fixtureState':'ENDED'}, {'quota':0}):
            with self.subTest(changes=changes):
                # A fresh namespace for each complete pair of independent windows.
                with tempfile.TemporaryDirectory() as tmp:
                    old_root = self.root
                    self.root = Path(tmp)
                    try:
                        live = dict(retentionDays=30, tokenValid=True, fixtureState='JOINED', quota=2)
                        (self.root/'fake-current.json').write_text(json.dumps(live))
                        self.window('first')
                        first = read_bundle(self.root/'official')[0]
                        (self.root/'fake-current.json').write_text(json.dumps({**live, **changes}))
                        self.window('second')
                        second = read_bundle(self.root/'official')[0]
                        outcome = json.loads((self.root/'resume-result.json').read_text())
                        self.assertEqual(outcome['reusable'], not bool(changes))
                        self.assertEqual(outcome['states'], {'retention':'observed','processing':'not-performed'})
                        expected_scope = copy.deepcopy(first['securityScope'])
                        expected_scope.setdefault('history', [])  # normalization records empty revision history
                        self.assertEqual(expected_scope, second['securityScope'])
                        self.assertEqual(second['taskCompletion'], 'partial')
                        self.assertFalse(second['handoffClosesTask'])
                        self.assertEqual(len(second['operations']), 1)
                        if changes:
                            self.assertIn('fresh authorized', second['continuation']['nextActions'][0]['action'])
                    finally:
                        self.root = old_root

    def test_lost_ack_persists_across_processes_and_reconciliation_precedes_any_retry(self):
        (self.root/'fake-current.json').write_text(json.dumps(dict(mutationApplied=True)))
        self.window('lost-ack')
        first = read_bundle(self.root/'official')[0]
        self.assertTrue(first['observations']['update']['outcomeUnknown'])
        checked = review.review_session(first)
        self.assertTrue(checked['checkpointReady'])
        self.assertTrue(checked['requiresReconciliation'])
        self.window('reconcile')
        resumed = json.loads((self.root/'resume-result.json').read_text())
        self.assertFalse(resumed['continuationStoppedByUser'])
        self.assertEqual(resumed['taskCompletion'], 'complete')  # supplied one-case scope, after actual fake readback

    def test_running_and_stop_ack_are_saveable_without_becoming_terminal(self):
        for state in ('running', 'acknowledged', 'stop-requested', 'stop-acknowledged'):
            run = working_run()
            run['operations'] = [dict(id='scan-7', status=state, nativeScanId='7')]
            run['continuation']['pendingOperations'] = [dict(operationRef='scan-7', lastKnownState=state,
                owner='owned-allocation', readVia='private-scan-journal', nextAction='Read native scan status before dependent effects.')]
            saved, _, _ = self.publish(run)
            self.assertEqual(saved['operations'][0]['status'], state)
            checked = review.review_session(saved)
            self.assertTrue(checked['checkpointReady'])
            self.assertTrue(checked['requiresReconciliation'])
            self.assertIn('reconcile-journal-ack-status-and-object-state-before-dependent-effects',checked['resumeSteps'])
            self.assertEqual(saved['taskCompletion'],'partial')

    def test_missing_pending_metadata_marks_recovery_without_preventing_save(self):
        run = working_run()
        run['operations'] = [dict(id='start', effect='start', state='intent')]
        del run['continuation']['nextActions']
        saved, _, _ = self.publish(run)
        checked = review.review_session(saved)
        self.assertFalse(checked['checkpointReady'])
        self.assertTrue(checked['requiresReconciliation'])
        self.assertIn('operations.0.pending-readback', checked['missingInformation'])
        self.assertEqual(saved['operations'][0]['state'], 'intent')

    def test_malformed_checkpoint_fields_produce_recovery_paths_without_losing_saved_data(self):
        run = working_run()
        run['continuation'].update(nextActions=[None],revalidate=None,pendingOperations=[{'operationRef':[]}])
        saved, _, _ = self.publish(run)
        checked = review.review_session(saved)
        self.assertFalse(checked['checkpointReady'])
        self.assertIn('continuation.nextActions.0.action',checked['missingInformation'])
        self.assertIn('continuation.pendingOperations.0.readVia',checked['missingInformation'])
        self.assertEqual(saved['continuation']['nextActions'],[None])

    def test_binding_drift_requires_reconciliation_and_does_not_merge_or_mutate_snapshots(self):
        saved, _, _ = self.publish()
        for field, value in [('image','changed-image'), ('origin','https://other.test'),
                             ('schemaRevision','schema-2'), ('targetBinding','other-binding')]:
            current = copy.deepcopy(saved)
            current[field] = value
            before = copy.deepcopy(current)
            checked = review.review_session(saved, current)
            self.assertTrue(checked['requiresReconciliation'])
            self.assertIn(field+'-missing-or-different', checked['conflicts'])
            self.assertEqual(current, before)
        current = copy.deepcopy(saved)
        current['assessmentContext']['scopeRevision'] = 'r2'
        self.assertIn('scopeRevision-missing-or-different', review.review_session(saved,current)['conflicts'])

    def test_interrupted_overwrite_detected_even_with_same_context_and_completion(self):
        first = self.publish()
        changed = working_run()
        changed['continuation']['currentFocus']['progress'] = 'Additional preparation completed; remaining work is eligible.'
        replace = os.replace
        def interrupt(source, destination):
            if Path(destination).resolve() == (self.root/'reports/ALERTS.json').resolve():
                raise OSError('synthetic interruption after RUN replacement')
            return replace(source, destination)
        with patch('os.replace',side_effect=interrupt), self.assertRaises(OSError):
            self.publish(changed)
        mixed = read_bundle(self.root/'reports')
        second = self.publish(changed)
        self.assertEqual(first[0]['assessmentContext'], second[0]['assessmentContext'])
        self.assertEqual(first[0]['taskCompletion'], second[0]['taskCompletion'])
        with self.assertRaisesRegex(ValueError, 'generation'):
            validate_bundle(second[0], first[1], second[2])
        with self.assertRaisesRegex(ValueError, 'generation'):
            validate_bundle(*mixed)
        checked = review.review_session(second[0], alerts=first[1], scope_alerts=second[2])
        self.assertTrue(checked['requiresReconciliation'])
        self.assertIn('report-bundle-generation-different',checked['conflicts'])
        self.assertEqual({p.name for p in (self.root/'reports').iterdir()}, set(NAMES))

    def test_forged_completion_in_metadata_cannot_close_unobserved_scope(self):
        run = working_run()
        run.update(taskCompletion='complete',handoffClosesTask=True)
        run['continuation'].update(taskCompletion='complete',scopeCompletion='complete',checkpointReady=True)
        saved, alerts, projection = self.publish(run)
        self.assertEqual([r['taskCompletion'] for r in (saved,alerts,projection)],['partial']*3)
        self.assertFalse(saved['handoffClosesTask'])
        self.assertTrue(saved['nextSteps'])

    def test_version_one_checkpoint_keeps_unit_links_summary_and_unknown_continuation(self):
        from test_question_evidence import scope, assessment
        from workflow_fixtures import operation
        run=dict(operations=[operation()],continuation=metadata())
        run['continuation']['pendingOperations']=[dict(operationRef='attempt-a',lastKnownState='unknown',
            owner='synthetic',readVia='saved-state',nextAction='read exact action state')]
        output=self.root/'v1'
        result=compact_results(output,run,[],security_scope=scope(),scope_assessment=assessment())
        self.assertEqual(result['completionSummary']['dast']['status'],'partial')
        question=json.loads((output/'SCOPE_ALERTS.json').read_text())['criteria'][0]['questions'][0]
        self.assertTrue(question['outcomeUnknown'])
        self.assertEqual(question['observation']['evidenceLinks'][0]['resultPath'],'/readback/pin')
        self.assertEqual(result['operations'][0]['status'],'partial')
        handled=review.review_work(dict(responsibilities=[dict(id='done',requiredObservations=['read'])],
            observations={'done':dict(completed=['read'])},decisions={}))
        self.assertEqual(handled['declaredListHandled'],handled['workComplete'])
        self.assertTrue(handled['declaredListHandled'])
        self.assertEqual(handled['taskCompletion'],'unverified-by-review-helper')

    def test_checkpoint_working_references_survive_compact_without_restoring_provenance(self):
        from workflow_fixtures import inventory as finite_inventory,operation,observed
        from zap_assessment.product_scope_cli import inspect_resume
        inv=finite_inventory(assessmentId='resume-a',product='synthetic',environment='offline',scopeRevision='r1')
        private=self.root/'private-working.json'
        data=dict(inventory=inv,observations={'pin':observed()},prerequisites={},operations=[operation()],history=[])
        private.write_text(json.dumps(data))
        context=dict(assessmentId='resume-a',product='synthetic',environment='offline',scopeRevision='r1')
        working=dict(version=1,purpose='executable-working-inputs',reportIsProjection=True,**context,
            **{key:dict(path=str(private),pointer='/'+key) for key in data})
        out=self.root/'resumable'
        compact_results(out,dict(operations=[operation()],assessmentContext=context,continuation=dict(workingInputs=working)),[],
            reconcile(inv,data['observations'],{},operations=data['operations']))
        saved=json.loads((out/'RUN.json').read_text())
        self.assertNotIn('evidenceRefs',json.dumps(saved))
        self.assertEqual(saved['continuation']['workingInputs'],working)
        self.assertEqual(inspect_resume(out/'RUN.json')['status'],'working-inputs-available')
        self.assertEqual({p.name for p in out.iterdir()},set(NAMES))

    def test_raw_and_encoded_secrets_stay_out_of_metadata_reports_and_diagnostics(self):
        secret = 'checkpoint-canary+/=private'
        variants = [secret, quote(secret,safe=''), base64.b64encode(secret.encode()).decode()]
        run = working_run()
        run['continuation']['currentFocus']['progress'] += ' ' + ' '.join(variants)
        run['continuation']['private_key'] = 'opaque-private-key'
        run['continuation']['token'] = 'opaque-token'
        saved, _, _ = self.publish(run, secrets=[secret])
        for name in NAMES:
            content = (self.root/'reports'/name).read_text()
            for value in variants + ['opaque-private-key','opaque-token']:
                self.assertNotIn(value, content)
        checked = json.dumps(review.review_session(saved))
        for value in variants:
            self.assertNotIn(value,checked)

    def test_untrusted_checkpoint_prose_is_neither_executed_nor_echoed_by_helper(self):
        run = working_run()
        run['continuation']['nextActions'][0]['action'] = '$(touch SHOULD-NOT-EXIST); import arbitrary secret-canary'
        saved, _, _ = self.publish(run)
        path = self.root/'reports/RUN.json'
        before = path.read_bytes()
        result = subprocess.run([sys.executable,'-B',str(HELPER),'session','--run',str(path)],
                                cwd=self.root, capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertNotIn('secret-canary', result.stdout)
        self.assertEqual(path.read_bytes(),before)
        self.assertFalse((self.root/'SHOULD-NOT-EXIST').exists())

    def test_old_run_and_legacy_generation_remain_readable_without_automatic_checkpoint(self):
        run = working_run()
        del run['continuation']
        saved, alerts, projection = self.publish(run)
        self.assertNotIn('continuation',saved)
        self.assertFalse(review.review_session(saved)['checkpointReady'])
        for report in (saved,alerts,projection):
            del report['reportGeneration']['bundleId']
        validate_bundle(saved,alerts,projection)
        self.assertFalse(review.review_session(saved,alerts=alerts,scope_alerts=projection)['requiresReconciliation'])

    def test_auxiliary_active_requests_do_not_become_input_coverage_at_checkpoint(self):
        answer = assess_question(dict(id='title',ruleIds=[40018],fields=['title'],minimumStage='processing'),
            [dict(ruleId=40018,changed=False,application=True,identityValid=True,resultRead=True,stage='processing',field='other')])
        inv = inventory()
        inv['cases'][0]['requiredEvidence'] = ['question:title']
        rec = reconcile(inv, {'update':dict(outcome='matched',resultRead=True,evidenceUnits=answer['evidenceUnits'])}, {})
        run = working_run()
        run['operations'] = [dict(id='scan',status='completed',requests=11,resultMeaning='auxiliary/site-wide; zero target-input probes')]
        compact_results(self.root/'auxiliary',run,{},rec)
        saved = read_bundle(self.root/'auxiliary')[0]
        self.assertEqual(answer['requests'],0)
        self.assertEqual(saved['taskCompletion'],'partial')
        self.assertFalse(saved['handoffClosesTask'])
        self.assertEqual(saved['operations'][0]['resultMeaning'], run['operations'][0]['resultMeaning'])
        self.assertEqual(saved['responsibilityReconciliation']['openResponsibilities'][0]['caseId'],'update')


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '--window':
        with patch('socket.socket', side_effect=AssertionError('network forbidden in synthetic window')):
            worker(sys.argv[2], sys.argv[3])
    else:
        unittest.main()
