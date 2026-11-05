"""Offline regression controls for verification findings R01–R04."""
import copy
import multiprocessing
import tempfile
import unittest
from pathlib import Path

import test_assessment_state_cli as cli_fixture
from test_coordinator_recovery import interrupt
from test_criteria_workflow import approve, working
from test_operation_selection import NOW, schedule_fixture, work
from test_operator_state import VERIFIED, advance, repair_proposal
from zap_assessment import assessment_store as store
from zap_assessment.contracts import canonical, digest
from zap_assessment.criteria_delegation import Coordinator, make_packet
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.operation_selection import select_next
from zap_assessment.operator_state import change_repair, default_operator, validate_operator


def history_fixture():
    run = working()
    context = dict(run['criteriaWorkflow']['plan']['cases'][0]['coverageContext'], objectRef='object-one')
    intent = dict(actionId='mutation-1', state='intent', effect='mutation', caseId='T1',
                  coverageContext=context)
    run['actionHistory'] = [intent]
    return run, intent


class PendingHistoryTests(unittest.TestCase):
    def test_R01_plain_envelope_mixed_unknown_and_bare_labels(self):
        for style in ('plain', 'envelope', 'mixed'):
            for steps in (['acknowledged'], ['unknown', 'acknowledged'], ['accepted'], ['reconciled']):
                with self.subTest(style=style, steps=steps):
                    run, intent = history_fixture()
                    history = [intent, *(dict(actionId=intent['actionId'], state=state) for state in steps)]
                    run['actionHistory'] = [
                        dict(kind=row['state'], data={key: value for key, value in row.items() if key != 'state'})
                        if style == 'envelope' or style == 'mixed' and index == 0 else row
                        for index, row in enumerate(history)]
                    reviewed = review_workflow(run)
                    pending, = reviewed['pendingEffects']
                    self.assertEqual(pending['state'], 'unknown')
                    self.assertEqual(pending['caseId'], intent['caseId'])
                    self.assertEqual(pending['coverageContext'], intent['coverageContext'])
                    self.assertFalse(reviewed['eligibleForCompletion'])

    def test_R01_exact_resolution_closes_and_wrong_binding_rejects(self):
        run, intent = history_fixture()
        run['actionHistory'].append(dict(actionId=intent['actionId'], state='reconciled'))
        fact = dict(actionId=intent['actionId'], caseId='T1', resolved=True)
        run['operations'].append(dict(id='readback', status='completed',
            coverageContext=intent['coverageContext'], readback=dict(resolution=fact)))
        run['criteriaWorkflow']['resolutions'] = [dict(actionId=intent['actionId'],
            resolutionOperationId='readback', resultPath='/readback/resolution', basis='Read fixture state')]
        self.assertTrue(review_workflow(run)['eligibleForCompletion'])
        for field, value in (('actionId', 'wrong'), ('caseId', 'T2'), ('context', {'objectRef': 'other'}),
                             ('context', {'environment': 'other'})):
            with self.subTest(field=field, value=value):
                changed = copy.deepcopy(run)
                changed['operations'][-1]['readback']['resolution'][field] = value
                with self.assertRaises(ValueError):
                    review_workflow(changed)

    def test_R01_coordinator_run_history_and_operation_are_deduplicated(self):
        with tempfile.TemporaryDirectory() as temp:
            run, intent = history_fixture()
            workflow = run['criteriaWorkflow']
            case = workflow['plan']['cases'][0]
            case['coverageContext'] = intent['coverageContext']
            run['operations'][0]['coverageContext'] = intent['coverageContext']
            workflow['caseResults'][0]['evidenceLinks'][0]['context'] = intent['coverageContext']
            case['effects'].append('mutation')
            workflow['plan']['authority']['allowedEffects'].append('mutation')
            descriptor = dict(id=intent['actionId'], caseId='T1', effect='mutation')
            case['actions'] = [descriptor]
            approve(run)
            coordinator = Coordinator(Path(temp).resolve(), 'A1')
            run['coordinatorState'] = dict(assessmentId='A1', directory=str(coordinator.root))
            history = run.pop('actionHistory')
            packet = make_packet(run, 'mutation-task', ['T1'], 'coordinator')
            coordinator.acquire(run, packet)
            coordinator.dispatch(run, packet, descriptor, lambda _: None)
            run['actionHistory'] = history
            run['operations'].append(dict(id='uncertain', actionId=intent['actionId'], caseId='T1',
                status='partial', coverageContext=intent['coverageContext'], outcomeUnknown=True))
            run['pendingEffects'] = [dict(actionId=intent['actionId'], caseId='T1')]
            self.assertEqual([row['actionId'] for row in review_workflow(run)['pendingEffects']], [intent['actionId']])


class RepairCliTests(unittest.TestCase):
    check = cli_fixture.CliTests.check
    write = cli_fixture.CliTests.write
    register = cli_fixture.CliTests.register
    setUp = cli_fixture.CliTests.setUp

    def snapshot(self):
        return store.load_current(self.state)

    def commit(self, key, run, operator, *, code=0):
        return self.check('state-commit', '--state-dir', self.state, '--expected-generation',
                          self.snapshot().generation_id, '--commit-id', key, '--run', self.write(key + '-run', run),
                          '--operator', self.write(key + '-operator', operator), code=code)

    def next(self):
        return self.check('state-next', '--state-dir', self.state)

    def test_R01_managed_ack_commit_succeeds_and_verified_delivery_rejects(self):
        run, intent = history_fixture()
        operator = default_operator(run)
        self.register(run, operator)
        run['actionHistory'].append(dict(actionId=intent['actionId'], state='acknowledged'))
        self.commit('ack', run, operator)
        self.assertEqual(self.next()['pendingActionIds'], [intent['actionId']])
        self.assertNotEqual(self.next()['nextAction']['kind'], 'workflow-done')
        operator['delivery'] = dict(fileId='fake', worksheetId='fake', status='verified',
            sourceDigest='fake-digest', verifiedAt='2026-11-04T00:00:00Z', readbackRefs=['fixture'])
        self.assertEqual(self.commit('premature', run, operator, code=2)['code'], 'invalid-input')
        operator['delivery'] = None
        run['operations'].append(dict(id='readback', status='completed', coverageContext=intent['coverageContext'],
            readback=dict(resolution=dict(actionId=intent['actionId'], caseId='T1', resolved=True))))
        run['criteriaWorkflow']['resolutions'] = [dict(actionId=intent['actionId'],
            resolutionOperationId='readback', resultPath='/readback/resolution', basis='Read fixture state')]
        self.commit('terminal-readback', run, operator)
        decision = self.next()
        self.assertEqual(decision['pendingActionIds'], [])
        self.assertEqual(decision['nextAction']['kind'], 'verify-final-delivery')

    def lease_fixture(self, *, binding=True, extra_action=False):
        run, operator = schedule_fixture()
        coordinator = Coordinator(self.base / 'coordinator', 'A1')
        run['coordinatorState'] = dict(assessmentId='A1', directory=str(coordinator.root))
        cases = run['criteriaWorkflow']['plan']['cases']
        if extra_action:
            cases[1]['actions'].append(dict(id='other-reader', caseId='T2', effect='read', readbackOf='other-effect'))
            approve(run)
            operator = default_operator(run)
        packet = make_packet(run, 'owned-task', ['T1', 'T2'], 'coordinator')
        path = self.write('packet', packet)
        saved = {key: packet[key] for key in ('taskId', 'workerId', 'packetDigest')}
        saved['packetRef'] = path.name
        operator['workItems'] = [work('fresh', action='effect')]
        if binding:
            operator['workItems'][0]['executionBinding'] = saved
        if extra_action:
            operator['workItems'].append(work('read-original', 'T2', action='other-reader',
                                              original='other-effect', executionBinding=saved))
        self.register(run, operator)
        return run, operator, packet, coordinator

    def assert_fresh(self):
        decision = self.next()
        self.assertEqual(decision['nextAction']['kind'], 'dispatch')
        self.assertEqual(decision['nextAction']['actionId'], 'effect')
        self.assertFalse(decision['canConcludeTurn'])

    def test_R02_cold_selection_after_acquire_and_consumed_action(self):
        run, _, packet, coordinator = self.lease_fixture()
        self.assertEqual(self.next()['nextAction']['reasonCode'], 'acquire-execution-lease')
        coordinator.acquire(run, packet)
        self.assert_fresh()
        calls = []
        coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: calls.append(action['id']))
        self.assertEqual(calls, ['effect'])
        decision = self.next()
        self.assertNotEqual(decision['nextAction']['kind'], 'dispatch')
        self.assertIn('consumed-action', [row['reasonCode'] for row in decision['deferred']])

    def test_R02_cold_selection_after_partial_acquire_recovery(self):
        run, _ = schedule_fixture()
        run['criteriaWorkflow']['plan']['resourceIds'] = ['scanner', 'second']
        approve(run)
        operator = default_operator(run)
        coordinator = Coordinator(self.base / 'coordinator', 'A1')
        run['coordinatorState'] = dict(assessmentId='A1', directory=str(coordinator.root))
        packet = make_packet(run, 'owned-task', ['T1'], 'coordinator')
        path = self.write('packet', packet)
        saved = {key: packet[key] for key in ('taskId', 'workerId', 'packetDigest')}
        operator['workItems'] = [work('fresh', action='effect', resourceIds=['scanner', 'second'],
                                      executionBinding=dict(saved, packetRef=str(path)))]
        self.register(run, operator)
        worker = multiprocessing.get_context('fork').Process(target=interrupt, args=(run, packet, coordinator, 'lease-1'))
        worker.start()
        worker.join(10)
        if worker.is_alive():
            worker.kill()
            worker.join()
        self.assertEqual(worker.exitcode, 77)
        self.assertEqual(self.next()['nextAction']['kind'], 'recover-leases')
        self.check('state-recover-leases', '--state-dir', self.state, '--packet', path)
        self.assert_fresh()

    def test_R02_missing_binding_prepares_and_forged_digest_conflicts(self):
        run, operator, packet, coordinator = self.lease_fixture(binding=False)
        coordinator.acquire(run, packet)
        decision = self.next()
        self.assertEqual(decision['nextAction']['reasonCode'], 'resolve-execution-binding')
        self.assertEqual(decision['nextAction']['kind'], 'prepare')
        self.assertTrue(decision['nextAction']['refs'])
        self.assertFalse(decision['canConcludeTurn'])
        operator['workItems'][0]['executionBinding'] = dict(taskId=packet['taskId'], workerId=packet['workerId'],
            packetDigest='0' * 64, packetRef='packet.json')
        self.commit('forged-binding', run, operator)
        decision = self.next()
        self.assertNotEqual(decision['nextAction']['kind'], 'dispatch')
        self.assertIn('execution-binding-conflict', [row['reasonCode'] for row in decision['deferred']])

    def test_R02_other_task_foreign_assessment_and_missing_resource(self):
        run, _, packet, coordinator = self.lease_fixture()
        other = make_packet(run, 'different-task', ['T1'], 'coordinator')
        coordinator.acquire(run, other)
        self.assertNotEqual(self.next()['nextAction']['kind'], 'dispatch')
        coordinator.release(run, other)
        foreign = dict(run, assessmentId='foreign', coordinatorState=dict(assessmentId='foreign', directory=str(coordinator.root)))
        owner = Coordinator(coordinator.root, 'foreign')
        foreign_packet = make_packet(foreign, 'owned-task', ['T1'], 'coordinator')
        owner.acquire(foreign, foreign_packet)
        self.assertNotEqual(self.next()['nextAction']['kind'], 'dispatch')
        owner.release(foreign, foreign_packet)
        coordinator.acquire(run, packet)
        coordinator._path('scanner').unlink()
        self.assertEqual(self.next()['mode'], 'recovery-only')
        self.assertNotEqual(self.next()['nextAction']['kind'], 'dispatch')

    def test_R02_same_task_with_different_valid_packet_digest_conflicts(self):
        run, operator, packet, coordinator = self.lease_fixture()
        coordinator.acquire(run, packet)
        alternative = make_packet(run, packet['taskId'], ['T1'], packet['workerId'])
        path = self.write('alternative', alternative)
        operator['workItems'][0]['executionBinding'].update(packetDigest=alternative['packetDigest'],
                                                           packetRef=str(path))
        self.commit('alternative-binding', run, operator)
        decision = self.next()
        self.assertNotEqual(decision['nextAction']['kind'], 'dispatch')
        self.assertIn('execution-binding-conflict', [row['reasonCode'] for row in decision['deferred']])

    def test_R02_pending_effect_in_another_case_of_same_packet(self):
        run, _, packet, coordinator = self.lease_fixture(extra_action=True)
        coordinator.acquire(run, packet)
        coordinator.dispatch(run, packet, packet['cases'][1]['actions'][0], lambda _: None)
        decision = self.next()
        self.assertEqual(decision['nextAction']['actionId'], 'other-reader')
        self.assertIn('pending-shared-task-effect', [row['reasonCode'] for row in decision['deferred']])

    def test_R03_typed_recurrence_reopens_once_and_requires_new_checks(self):
        run, operator = schedule_fixture()
        operator['workItems'] = [work('reader', action='reader', original='effect'), work('independent', 'T2')]
        self.register(run, operator)
        original = repair_proposal()

        def update(command, key, payload, *, parent=None):
            return self.check(command, '--state-dir', self.state,
                              '--expected-generation', parent or self.snapshot().generation_id,
                              '--commit-id', key, '--repair', self.write(key, payload))

        update('state-repair-open', 'original', original)
        for stage in ('reproducing', 'implementing', 'verifying', 'verified'):
            repair = self.snapshot().operator['repairs'][0]
            update('state-repair-update', stage, dict(id=repair['id'], revision=repair['revision'],
                status=stage, **(VERIFIED if stage == 'verified' else {})))
        verified = self.snapshot()
        recurrence = dict(original, id='recurred', reproductionRefs=['new-capture'])
        first = update('state-repair-open', 'recurrence', recurrence)
        reopened = self.snapshot().operator
        row, = reopened['repairs']
        self.assertEqual(row['status'], 'open')
        self.assertEqual(row['symptom'], original['symptom'])
        self.assertNotIn('verificationLevel', row)
        self.assertEqual(row['history'][-1]['kind'], 'reopened-after-verification')
        self.assertEqual(row['history'][-1]['previousVerification']['verificationRefs'], VERIFIED['verificationRefs'])
        self.assertEqual(row['history'][-1]['reproductionRefs'], ['new-capture'])
        retry = update('state-repair-open', 'recurrence', recurrence, parent=verified.generation_id)
        self.assertTrue(retry['alreadyApplied'])
        self.assertEqual(retry['generationId'], first['generationId'])
        self.assertEqual(change_repair(reopened, recurrence, opening=True), reopened)
        decision = self.next()
        self.assertEqual(decision['nextAction']['workId'], 'independent')
        self.assertIn('repair-open', [item['reasonCode'] for item in decision['deferred']])
        for stage in ('reproducing', 'implementing', 'verifying'):
            reopened = advance(reopened, stage)
        with self.assertRaisesRegex(ValueError, 'new verificationRefs'):
            advance(reopened, 'verified', **VERIFIED)
        fresh = dict(VERIFIED, verificationRefs=['new-transcript'], positiveCheckRefs=['new-positive'],
                     negativeCheckRefs=['new-negative'])
        reverified = advance(reopened, 'verified', **fresh)
        validate_operator(run, reverified)
        # A second repair does not clear the consumed effect. With the original
        # lease and pending action retained, the distinct reader is eligible.
        run['pendingEffects'] = [dict(actionId='effect', taskId='fixture-task', caseId='T1')]
        reverified['workItems'].append(work('replay-attempt', action='effect'))
        facts = dict(leases={'scanner': dict(assessmentId='A1', taskId='fixture-task')})
        decision = select_next(run, reverified, review_workflow(run), facts, now=NOW)
        self.assertEqual(decision['nextAction']['actionId'], 'reader')
        self.assertIn('consumed-action', [item['reasonCode'] for item in decision['deferred']])
        run.pop('pendingEffects')
        replaced = copy.deepcopy(self.snapshot().operator)
        replaced['repairs'] = []
        self.assertEqual(self.commit('overwrite-repair', run, replaced, code=2)['code'], 'invalid-input')

    def test_R04_inspect_intact_history_ignores_staged_generation(self):
        run = working()
        operator = default_operator(run)
        self.register(run, operator)
        self.commit('child', run, operator)
        (self.state / 'generations' / store.identifier('staged')).mkdir()
        decision = self.check('state-inspect', '--state-dir', self.state)
        self.assertEqual(decision['currentIntegrity'], 'clean')
        self.assertEqual(decision['historyIntegrity'], 'clean')
        self.assertEqual(decision['committedGenerationCount'], 2)

    def test_R04_missing_and_tampered_parent_reject_inspect(self):
        run = working()
        operator = default_operator(run)
        self.register(run, operator)
        parent = self.snapshot()
        self.commit('child', run, operator)
        manifest = parent.run_path.parent / 'manifest.json'
        original = manifest.read_bytes()
        manifest.write_bytes(b'{}')
        for remove in (False, True):
            if remove:
                manifest.unlink()
            with self.subTest(remove=remove):
                self.assertEqual(self.snapshot().manifest['commitId'], 'child')
                failure = self.check('state-inspect', '--state-dir', self.state, code=4)
                self.assertEqual(failure['code'], 'committed-history-integrity')
                self.assertTrue(failure['refs'])
        manifest.write_bytes(original)

    def test_R04_self_cycle_is_not_a_clean_store(self):
        run = working()
        self.register(run, default_operator(run))
        snapshot = self.snapshot()
        manifest = dict(snapshot.manifest, parentGenerationId=snapshot.generation_id,
                        expectedGenerationId=snapshot.generation_id)
        (snapshot.run_path.parent / 'manifest.json').write_bytes(canonical(manifest))
        pointer = self.state / 'current.json'
        pointer.write_bytes(canonical(dict(store.read_json(pointer), manifestSha256=digest(manifest))))
        self.assertEqual(self.check('state-inspect', '--state-dir', self.state, code=4)['code'],
                         'committed-history-integrity')
