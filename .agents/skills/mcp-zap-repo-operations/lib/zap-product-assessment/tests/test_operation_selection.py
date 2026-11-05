import copy
import unittest
from datetime import datetime, timezone

from test_criteria_workflow import approve, working
from zap_assessment.criteria_resume import resume_next
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.operation_selection import delivery_digest, select_next
from zap_assessment.operator_state import default_operator, validate_operator

NOW = datetime(2026, 11, 4, tzinfo=timezone.utc)


def schedule_fixture(*, dependent=False):
    run = working(None)
    workflow = run['criteriaWorkflow']
    case = workflow['plan']['cases'][0]
    case['resourceIds'] = ['scanner']
    case['actions'] = [
        dict(id='effect', caseId='T1', effect='read'),
        dict(id='reader', caseId='T1', effect='read', readbackOf='effect'),
        dict(id='ttl', caseId='T1', effect='read'),
    ]
    second = dict(copy.deepcopy(case), id='T2', actions=[dict(id='other-effect', caseId='T2', effect='read')])
    if dependent:
        case['dependsOnCases'] = ['T2']
    workflow['plan']['cases'].append(second)
    workflow['criteria'][0]['caseIds'].append('T2')
    approve(run)
    return run, default_operator(run)


def work(wid, case='T1', *, block='default', action=None, original=None, **changes):
    return dict(dict(id=wid, blockId=block, caseIds=[case],
                     kind='readback' if original else 'dispatch' if action else 'source-review',
                     mode='runtime' if action else 'offline', phase='execution', order=0,
                     dependsOnWorkIds=[], resourceIds=['scanner'] if action else [],
                     state='ready', basisRefs=['fixture'], completionRefs=[],
                     nextStep='Review fixture', actionRef=dict(caseId=case, actionId=action) if action else None,
                     readbackOf=original, notBefore=None, waiting=None), **changes)


def closure_work(case='T2', **changes):
    return work('final-resource-review', case, kind='resource-review', phase='closure', **changes)


class SelectorTests(unittest.TestCase):
    def choose(self, run, operator, inspection=None, *, evidence_index=(), review=None):
        return select_next(run, operator, review if review is not None else review_workflow(run),
                           inspection or {}, evidence_index=evidence_index, now=NOW, managed=True)

    def test_C01_dependency_requires_reviewed_outcome(self):
        run, operator = schedule_fixture(dependent=True)
        self.assertEqual(resume_next(run)['nextAction']['caseId'], 'T2')
        recorded = working('violated')
        run['operations'] = recorded['operations']
        run['criteriaWorkflow']['caseResults'] = [
            dict(recorded['criteriaWorkflow']['caseResults'][0], caseId='T2')]
        review = review_workflow(run)
        self.assertEqual(review['caseResults'][1]['outcome'], 'violated')
        self.assertEqual(self.choose(run, operator, review=review)['nextAction']['caseId'], 'T1')

    def test_C03_C04_C05_reader_before_fresh_shared_resource(self):
        run, operator = schedule_fixture()
        run['pendingEffects'] = [dict(actionId='effect', caseId='T1', taskId='worker')]
        operator['workItems'] = [work('reader', action='reader', original='effect'),
                                 work('fresh', 'T2', action='other-effect'), work('offline', 'T2')]
        facts = dict(leases={'scanner': dict(assessmentId='A1', taskId='worker')})
        self.assertEqual(self.choose(run, operator, facts)['nextAction']['workId'], 'reader')
        operator['workItems'][0].update(state='waiting', waiting=dict(reason='Unavailable',
            reopenCondition='Reader repaired', basisRefs=['repair'], nextStep='Repair'))
        decision = self.choose(run, operator, facts)
        self.assertEqual(decision['nextAction']['workId'], 'offline')
        self.assertEqual(decision['pendingActionIds'], ['effect'])
        self.assertIn('resource-conflict', [row['reasonCode'] for row in decision['deferred']])

    def test_C06_C16_C18_active_block_and_determinism(self):
        run, operator = schedule_fixture()
        operator['blocks'] = [dict(id='one', caseIds=['T1'], order=1, exitCondition='review'),
                              dict(id='two', caseIds=['T2'], order=0, exitCondition='review')]
        operator['activeBlockId'] = 'one'
        operator['workItems'] = [work('one', block='one'), work('two', 'T2', block='two')]
        validate_operator(run, operator)
        before = copy.deepcopy((run, operator))
        decision = self.choose(run, operator)
        self.assertEqual(decision['nextAction']['workId'], 'one')
        self.assertFalse(decision['canConcludeTurn'])
        self.assertEqual(decision, self.choose(run, operator))
        self.assertEqual(before, (run, operator))
        operator['workItems'][0]['notBefore'] = '2026-11-05T00:00:00Z'
        self.assertEqual(self.choose(run, operator)['nextAction']['workId'], 'two')

    def test_C07_C08_retained_hint_and_done_metadata_do_not_close(self):
        run, operator = schedule_fixture()
        operator['workItems'] = [work('done', state='done', completionRefs=['fixture']), work('fresh', 'T2')]
        decision = self.choose(run, operator, evidence_index=[dict(caseId='T1', directAcks=['hint'])])
        self.assertEqual(decision['nextAction']['reasonCode'], 'retained-evidence')
        self.assertGreater(decision['criterionCounts']['pending'], 0)
        operator['workItems'].pop()
        self.assertEqual(self.choose(run, operator)['nextAction']['kind'], 'prepare')

    def test_C09_C10_C11_ttl_after_feasible_execution(self):
        run, operator = schedule_fixture()
        ttl = work('expiry', action='ttl', phase='ttl-readback', notBefore='2026-11-05T00:00:00Z',
                   subjectRefs=['same-session'], controlRefs=['control'])
        other = work('other', 'T2')
        operator['workItems'] = [ttl, other]
        validate_operator(run, operator)
        decision = self.choose(run, operator)
        self.assertEqual(decision['nextAction']['workId'], 'other')
        self.assertEqual(decision['nextWakeAt'], '2026-11-05T00:00:00+00:00')
        ttl.update(notBefore='2026-11-03T00:00:00Z', controlRefs=[])
        other.update(state='waiting', waiting=dict(reason='fixture unavailable', basisRefs=['fixture'],
            reopenCondition='fixture available', nextStep='Verify fixture'))
        self.assertEqual(self.choose(run, operator)['nextAction']['reasonCode'], 'ttl-control-required')
        ttl['controlRefs'] = ['known-control']
        self.assertEqual(self.choose(run, operator)['nextAction']['workId'], 'expiry')

    def test_C12_C13_stop_and_stale_schedule(self):
        run, operator = schedule_fixture()
        operator['planDigest'] = 'old'
        self.assertEqual(self.choose(run, operator)['nextAction']['kind'], 'rebase-schedule')
        run['criteriaWorkflow']['userRequest'] = dict(kind='pause', source='fixture')
        facts = dict(leases={'scanner': dict(assessmentId='A1', taskId='worker')})
        decision = self.choose(run, operator, facts)
        self.assertEqual(decision['mode'], 'stopped')
        self.assertEqual(decision['nextAction']['kind'], 'resource-review')

    def test_C14_C15_delivery_receipt_and_stable_source_digest(self):
        run = working()
        operator = default_operator(run)
        operator['workItems'] = [closure_work('T1', state='done', completionRefs=['fixture'])]
        decision = self.choose(run, operator)
        self.assertEqual(decision['nextAction']['kind'], 'verify-final-delivery')
        self.assertFalse(decision['canConcludeTurn'])
        operator['delivery'] = dict(status='verified', sourceDigest='stale', fileId='synthetic',
            worksheetId='1', verifiedAt='2026-11-03T00:00:00Z', readbackRefs=['fixture'])
        decision = self.choose(run, operator)
        self.assertEqual(decision['nextAction']['kind'], 'verify-final-delivery')
        self.assertFalse(decision['canConcludeTurn'])
        operator['delivery']['sourceDigest'] = delivery_digest(run, review_workflow(run))
        for at in ('2026-11-03T00:00:00Z', '2026-11-04T00:00:00Z'):
            operator['delivery']['verifiedAt'] = at
            decision = self.choose(run, operator)
            self.assertEqual(decision['nextAction']['kind'], 'workflow-done')
            self.assertTrue(decision['canConcludeTurn'])

    def test_C17_degraded_journal_permits_independent_source_review(self):
        run, operator = schedule_fixture()
        operator['workItems'] = [work('fresh', action='effect'), work('offline', 'T2')]
        decision = self.choose(run, operator, dict(effectsAllowed=False, pendingCertainty='prefix-only'), review={})
        self.assertEqual(decision['mode'], 'recovery-only')
        self.assertEqual(decision['nextAction']['workId'], 'offline')
        self.assertFalse(decision['canConcludeTurn'])

    def test_closure_resolves_its_own_evidence_obligation(self):
        run = working(None)
        workflow = run['criteriaWorkflow']
        workflow['plan']['cases'][0].update(id='T-FINAL', requiredEvidence=['resource-disposition'])
        workflow['criteria'][0]['caseIds'] = ['T-FINAL']
        workflow.pop('resourceReview')
        approve(run)
        operator = default_operator(run)
        operator['workItems'] = [closure_work('T-FINAL')]
        validate_operator(run, operator)
        review = review_workflow(run)
        self.assertEqual([row['caseId'] for row in review['nextWork']], ['T-FINAL'])
        self.assertFalse(review['eligibleForCompletion'])
        decision = self.choose(run, operator, review=review)
        self.assertEqual(decision['pendingActionIds'], [])
        self.assertEqual(decision['nextAction']['kind'], 'resource-review')
        self.assertEqual(decision['nextAction']['workId'], 'final-resource-review')
        self.assertFalse(decision['canConcludeTurn'])

    def test_independent_closure_runs_while_other_work_waits_for_deadline(self):
        run, operator = schedule_fixture()
        operator['workItems'] = [closure_work(), work('expiry', action='ttl', phase='ttl-readback',
            notBefore='2026-11-05T00:00:00Z', subjectRefs=['same-session'], controlRefs=['control'])]
        validate_operator(run, operator)
        decision = self.choose(run, operator)
        self.assertEqual(decision['nextAction'].get('workId'), 'final-resource-review')
        self.assertFalse(decision['canConcludeTurn'])
        self.assertEqual(decision['nextWakeAt'], '2026-11-05T00:00:00+00:00')
        expiry, = decision['deferred']
        self.assertEqual((expiry['workId'], expiry['reasonCode'], expiry['earliestAt']),
                         ('expiry', 'not-before', decision['nextWakeAt']))

    def test_closure_stays_deferred_for_unfinished_work_or_case(self):
        for reason, dependency in (('work-dependency', 'prerequisite'), ('case-dependency', 'T1')):
            with self.subTest(reason=reason):
                run, operator = schedule_fixture()
                closure = closure_work()
                if reason == 'work-dependency':
                    closure['dependsOnWorkIds'] = [dependency]
                else:
                    run['criteriaWorkflow']['plan']['cases'][1]['dependsOnCases'] = [dependency]
                    approve(run)
                    operator = default_operator(run)
                prerequisite = work('prerequisite', state='waiting', waiting=dict(
                    reason='fixture unavailable', basisRefs=['fixture'],
                    reopenCondition='fixture available', nextStep='Verify fixture'))
                operator['workItems'] = [closure, prerequisite]
                validate_operator(run, operator)
                decision = self.choose(run, operator)
                self.assertEqual(decision['nextAction']['kind'], 'review-dependencies')
                deferred = next(row for row in decision['deferred'] if row.get('workId') == closure['id'])
                self.assertEqual((deferred['reasonCode'], deferred['dependsOn']), (reason, [dependency]))
                self.assertGreater(decision['criterionCounts']['pending'], 0)

    def test_pending_readback_and_reconciliation_precede_ready_closure(self):
        run, operator = schedule_fixture()
        run['pendingEffects'] = [dict(actionId='effect', caseId='T1', taskId='worker')]
        operator['workItems'] = [closure_work(), work('reader', action='reader', original='effect')]
        facts = dict(leases={'scanner': dict(assessmentId='A1', taskId='worker')})
        validate_operator(run, operator)
        decision = self.choose(run, operator, facts)
        self.assertIn('final-resource-review', decision['readyWorkIds'])
        self.assertEqual(decision['nextAction']['workId'], 'reader')
        self.assertFalse(decision['canConcludeTurn'])

        operator['workItems'].pop()
        decision = self.choose(run, operator, facts)
        self.assertEqual(decision['nextAction']['kind'], 'reconcile-original-effect')
        self.assertEqual(decision['pendingActionIds'], ['effect'])
        self.assertFalse(decision['canConcludeTurn'])

    def test_due_ttl_precedes_ready_closure(self):
        run, operator = schedule_fixture()
        operator['workItems'] = [closure_work(), work('expiry', action='ttl', phase='ttl-readback',
            notBefore='2026-11-04T00:00:00Z', subjectRefs=['same-session'], controlRefs=['control'])]
        validate_operator(run, operator)
        decision = self.choose(run, operator)
        self.assertIn('final-resource-review', decision['readyWorkIds'])
        self.assertEqual(decision['nextAction']['workId'], 'expiry')
        self.assertEqual(decision['nextAction']['reasonCode'], 'ttl-revalidate-control')
        self.assertFalse(decision['canConcludeTurn'])

    def test_closure_respects_open_repair_and_foreign_resource(self):
        from test_operator_state import repair_proposal
        from zap_assessment.operator_state import change_repair

        run, operator = schedule_fixture()
        closure = closure_work()
        operator['workItems'] = [closure]
        repairing = change_repair(operator, repair_proposal(affectedCaseIds=['T2'],
            affectedWorkIds=[closure['id']], resumeWorkIds=[closure['id']]), opening=True)
        validate_operator(run, repairing)
        decision = self.choose(run, repairing)
        self.assertEqual(decision['nextAction']['kind'], 'repair')
        self.assertEqual(decision['deferred'][0]['reasonCode'], 'repair-open')

        operator['workItems'] = [
            work(closure['id'], 'T2', action='other-effect', phase='closure'), work('offline')]
        validate_operator(run, operator)
        facts = dict(leases={'scanner': dict(assessmentId='foreign', taskId='worker')})
        decision = self.choose(run, operator, facts)
        self.assertEqual(decision['nextAction']['workId'], 'offline')
        self.assertEqual(decision['deferred'][0]['reasonCode'], 'resource-conflict')
