import copy
import unittest

from test_operation_selection import schedule_fixture, work
from zap_assessment.assessment_store import StateError
from zap_assessment.operator_state import change_repair, validate_operator


def repair_proposal(**changes):
    return dict(dict(id='repair-reader', kind='reader', status='open', affectedCaseIds=['T1'],
                     affectedWorkIds=['reader'], affectedResourceIds=[], symptom='Reader shape rejected',
                     reproductionRefs=['fixture-capture'], reproductionDigest='fixture-digest',
                     expectedBehavior='Read retained receipt', authorityRef='fixture-authority',
                     allowedPaths=['src/reader.py'], prohibitedEffects=['replay', 'product-traffic'],
                     acceptanceChecks=['positive', 'negative'], verificationRefs=[],
                     resumeWorkIds=['reader'], dependency=None, history=[]), **changes)


def advance(operator, status, **changes):
    row = operator['repairs'][0]
    return change_repair(operator, dict(id=row['id'], revision=row['revision'], status=status, **changes), opening=False)


VERIFIED = dict(reproductionOutcome='Reproduced from capture', changedFileRefs=['fixture-sha'],
                positiveCheckRefs=['valid'], negativeCheckRefs=['invalid'], verificationRefs=['fixture-transcript'],
                verificationResult='passed', verificationLevel='offline-checked')


class OperatorTests(unittest.TestCase):
    def setUp(self):
        self.run, self.operator = schedule_fixture()
        self.operator['workItems'] = [work('reader', action='reader', original='effect'),
                                      work('independent', 'T2')]

    def test_C02_dependency_cycle_and_unknown_dependency(self):
        for dependency in ('reader', 'unknown'):
            with self.subTest(dependency=dependency):
                self.operator['workItems'][0]['dependsOnWorkIds'] = [dependency]
                with self.assertRaises(ValueError):
                    validate_operator(self.run, self.operator)

    def test_D01_deduplicate_normalized_symptom_by_context_and_repro(self):
        first = change_repair(self.operator, repair_proposal(), opening=True)
        duplicate = change_repair(first, repair_proposal(id='repeat', symptom=' READER  SHAPE rejected '), opening=True)
        self.assertEqual(len(duplicate['repairs']), 1)
        self.assertEqual(duplicate['repairs'][0]['history'][-1]['kind'], 'occurrence')
        distinct = change_repair(duplicate, repair_proposal(id='new-build', contextRef='other-build'), opening=True)
        self.assertEqual(len(distinct['repairs']), 2)
        validate_operator(self.run, distinct)

    def test_D02_D03_D04_repair_reopens_original_readback(self):
        from test_operation_selection import SelectorTests

        self.run['pendingEffects'] = [dict(actionId='effect', caseId='T1', taskId='worker')]
        operator = change_repair(self.operator, repair_proposal(), opening=True)
        choose = SelectorTests().choose
        self.assertEqual(choose(self.run, operator)['nextAction']['workId'], 'independent')
        for stage in ('reproducing', 'implementing', 'verifying'):
            operator = advance(operator, stage)
        incomplete = advance(operator, 'verified')
        with self.assertRaises(ValueError):
            validate_operator(self.run, incomplete)
        operator = advance(operator, 'verified', **VERIFIED)
        validate_operator(self.run, operator)
        facts = dict(leases={'scanner': dict(assessmentId='A1', taskId='worker')})
        decision = choose(self.run, operator, facts)
        self.assertEqual(decision['nextAction']['actionId'], 'reader')
        self.assertEqual(decision['pendingActionIds'], ['effect'])
        self.assertEqual(operator['repairs'][0]['verificationLevel'], 'offline-checked')

    def test_D05_D06_repair_scope_and_append_only_history(self):
        with self.assertRaises(ValueError):
            change_repair(self.operator, repair_proposal(oracle='rewrite'), opening=True)
        operator = change_repair(self.operator, repair_proposal(), opening=True)
        next_state = advance(operator, 'reproducing')
        before = copy.deepcopy(next_state)
        with self.assertRaises(StateError):
            change_repair(next_state, dict(id='repair-reader', revision=1, status='verified'), opening=False)
        with self.assertRaises(ValueError):
            advance(next_state, 'implementing', symptom='changed')
        self.assertEqual(next_state, before)
        self.assertEqual(next_state['repairs'][0]['history'][:-1], operator['repairs'][0]['history'])
