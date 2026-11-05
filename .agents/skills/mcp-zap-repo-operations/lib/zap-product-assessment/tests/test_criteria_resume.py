import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_criteria_workflow import approve, limitation, working
from zap_assessment.criteria_resume import resume_next


class CriteriaResumeTests(unittest.TestCase):
    def test_resume_after_ack_before_case_write(self):
        run = working()
        workflow = run['criteriaWorkflow']
        saved_result, = workflow['caseResults']
        workflow['caseResults'] = []
        index = [{'caseId': 'T1', 'directAcks': [{'operationId': 'O1'}]}]

        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / 'WORKING_RUN.json'
            snapshot.write_text(json.dumps(run))
            restored = json.loads(snapshot.read_text())
            action = resume_next(restored, index)['nextAction']
            self.assertEqual(action['kind'], 'reconcile-case')
            self.assertEqual(action['caseId'], 'T1')
            self.assertEqual(action['missingUnits'], ['owner-control', 'denial'])
            self.assertEqual(restored['criteriaWorkflow']['caseResults'], [])

            restored['criteriaWorkflow']['caseResults'] = [saved_result]
            self.assertEqual(resume_next(restored, index)['nextAction']['kind'],
                             'verify-final-delivery')

    def test_unknown_effect_leaves_independent_case_available(self):
        run = working(None)
        workflow = run['criteriaWorkflow']
        second = copy.deepcopy(workflow['plan']['cases'][0])
        second['id'] = 'T2'
        workflow['plan']['cases'].append(second)
        workflow['criteria'][0]['caseIds'].append('T2')
        approve(run)
        run['pendingEffects'] = [{'actionId': 'unacked', 'caseId': 'T1'}]

        result = resume_next(run)
        self.assertEqual(result['pendingActionIds'], ['unacked'])
        self.assertEqual(result['blockedCases'], {'T1': 'reconcile-original-effect'})
        self.assertEqual(result['nextAction']['caseId'], 'T2')

    def test_dependency_does_not_end_assessment(self):
        run = working(None)
        run['criteriaWorkflow']['caseResults'] = [{
            'caseId': 'T1', 'outcome': None, 'basis': 'Method boundary',
            'limitation': limitation(),
        }]
        result = resume_next(run)
        self.assertEqual(result['assessmentStatus'], 'executing')
        self.assertEqual(result['nextAction']['kind'], 'review-dependencies')

    def test_approval_precedes_evidence_work(self):
        run = working(None)
        run['criteriaWorkflow']['approvals'].pop()
        self.assertEqual(resume_next(run)['nextAction']['kind'], 'awaiting_plan_approval')
