import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.product_scope import compact_results, reconcile
from zap_assessment.product_scope_cli import main
from zap_assessment.residual_review import project_residual_work, validate_source_texts
from zap_assessment.security_scope import canonical_alerts, normalize_scope, project_scope
from zap_assessment.work_selection import select_next_work
from test_question_evidence import scope, assessment
from workflow_fixtures import inventory, operation, observed, action, case


def item(iid='processing', **changes):
    row=dict(id=iid,sourceRef='prior',sourcePointer='/criteria/0/remainingWork/0',
        originalText='Processing remains unread. Not every browser context is proven.',selectedText='Processing remains unread.',
        criterionIds=['setting'],questionIds=['q-pin'],caseIds=[],kind='test-gap',basis='Assigned processing observation missing',
        nextStep='Read retained exact-object processing result',actionClass='readback',dependency=None)
    row.update(changes);return row


def review(items=None, **changes):
    row=dict(version=1,scopeRevision='r1',sources=[dict(id='prior',location='prior.json',kind='retained-report')],
        items=items if items is not None else [item()],
        reviewExtent=dict(kind='selected-groups',sourceIds=['prior'],criterionIds=['setting'],basis='Review one retained group'),unreviewedRefs=[])
    row.update(changes);return row


class ResidualReviewTests(unittest.TestCase):
    def project(self, r, a=None, s=None, rec=None, ops=None, findings=None):
        s=s or scope();ops=[operation()] if ops is None else ops
        p=project_scope(s,dict(a or assessment(),residualReview=r),dict(operations=ops),canonical_alerts(findings or []),rec)
        return p['residualWork'],p

    def test_mixed_paragraph_split_into_distinct_next_actions_and_exact_source(self):
        atoms=[item(kind='readback-gap',resultRefs=[dict(operationId='attempt-a',resultPath='/readback/pin')]),
            item('browser-limit',kind='generalization-limit',questionIds=[],selectedText='Not every browser context is proven.',
                basis='Assigned finite owner setting scope excludes unrelated browser matrix',scopeBasis='Finite owner-setting assignment',
                excludedConclusions=['Every browser/rendering context is safe'],actionClass='none',nextStep='Bound conclusion to retained contexts')]
        r=review(atoms);result,_=self.project(r)
        self.assertEqual([i['id'] for i in result['actionableReadback']],['processing'])
        self.assertEqual([i['id'] for i in result['conclusionLimits']],['browser-limit'])
        self.assertEqual(result['decision'],'continue')
        docs={'prior':dict(criteria=[dict(remainingWork=[atoms[0]['originalText']])])}
        validate_source_texts(r,docs)
        docs['prior']['criteria'][0]['remainingWork'][0]='Different original'
        with self.assertRaisesRegex(ValueError,'originalText'):validate_source_texts(r,docs)

    def test_generalization_label_cannot_close_assigned_open_question(self):
        r=review([item(kind='generalization-limit',scopeBasis='Caller claim',excludedConclusions=['all contexts'],actionClass='none')])
        result,p=self.project(r,a={'scopeRevision':'r1'})
        self.assertEqual(result['decision'],'review-needed')
        self.assertEqual(result['unclassified'][0]['id'],'processing')
        self.assertIn('conclusion-limit-conflicts-with-assigned-open-question',[d['code'] for d in result['reviewDiagnostics']])
        self.assertEqual(p['scopeCompletion'],'partial')

    def test_answered_requires_current_observed_not_completed_operation_or_old_label(self):
        r=review([item(kind='answered',actionClass='none')])
        result,_=self.project(r)
        self.assertEqual(len(result['answered']),1)
        result,_=self.project(r,a={'scopeRevision':'r1'},ops=[operation(status='completed')])
        self.assertFalse(result['answered']);self.assertTrue(result['unclassified'])
        result,_=self.project(r,ops=[operation(outcomeUnknown=True,actionId='change')])
        self.assertFalse(result['answered']);self.assertTrue(result['investigationNeeded'])

    def test_method_limit_keeps_governance_catalog_open_without_execution(self):
        r=review([item(kind='method-limit',criterionIds=['governance'],questionIds=['q-policy'],methodBoundary='Governance policy review is outside assigned ZAP methods',actionClass='none')])
        r['reviewExtent']['criterionIds']=['governance']
        result,p=self.project(r)
        self.assertEqual(result['decision'],'no-further-dynamic-action-in-reviewed-scope')
        self.assertTrue(result['methodLimits']);self.assertFalse(result['actionableExecution'])
        self.assertEqual(p['scopeCompletion'],'partial')

    def test_method_limit_cannot_propose_outside_method_execution_and_all_result_refs_validate(self):
        r=review([item(kind='method-limit',methodBoundary='Outside ZAP',actionClass='execute')])
        result,_=self.project(r)
        self.assertFalse(result['actionableExecution']);self.assertTrue(result['unclassified'])
        self.assertIn('limit-cannot-authorize-execution',[d['code'] for d in result['reviewDiagnostics']])
        r=review([item(kind='answered',actionClass='none',resultRefs=[dict(operationId='foreign',resultPath='/result')])])
        with self.assertRaisesRegex(ValueError,'result operation'):self.project(r)

    def test_missing_reader_with_available_preparation_is_not_external_dependency(self):
        r=review([item(kind='dependency',actionClass='external-dependency',dependency=dict(blockedBy='No adapter',
            optionsEvaluated=['Retained result reader can be prepared'],resumptionCondition='Reader available',preparationNextStep='Prepare semantic reader from retained JSON'))])
        result,_=self.project(r)
        self.assertEqual(result['decision'],'continue');self.assertTrue(result['preparationNeeded']);self.assertFalse(result['externalDependencies'])

    def test_true_dependency_handoff_has_no_fixed_attempt_quota(self):
        r=review([item(kind='dependency',actionClass='external-dependency',dependency=dict(blockedBy='Tenant policy is not supplied',
            optionsEvaluated=['Local membership readback does not define tenant policy'],resumptionCondition='Authoritative tenant model supplied'))])
        result,_=self.project(r)
        self.assertEqual(result['decision'],'handoff-with-dependencies');self.assertEqual(result['decisionScope'],'reviewed-scope-only')
        self.assertEqual(result['unreviewedRefs'][0]['criterionId'],'governance')

    def test_missing_rationale_and_next_step_are_saveable_diagnostics(self):
        r=review([item(basis='',nextStep='',kind='dependency',actionClass='external-dependency',dependency=None)])
        result,_=self.project(r)
        self.assertEqual(result['decision'],'review-needed')
        with tempfile.TemporaryDirectory() as temp:
            saved=compact_results(Path(temp)/'reports',dict(operations=[operation()]),[],security_scope=scope(),scope_assessment=dict(assessment(),residualReview=r))
            self.assertEqual(saved['taskCompletion'],'partial')
            self.assertTrue(saved['residualWork']['reviewDiagnostics'])

    def test_extent_requires_explicit_backlog_and_unreviewed_groups_stay_visible(self):
        r=review([item(kind='answered',actionClass='none')]);result,_=self.project(r)
        self.assertEqual(result['decision'],'no-further-dynamic-action-in-reviewed-scope')
        self.assertEqual(result['unreviewedRefs'][0]['criterionId'],'governance')
        r['reviewExtent']['criterionIds'].append('governance')
        r['reviewExtent']['kind']='all-declared-residuals'
        result,_=self.project(r)
        self.assertEqual(result['decision'],'review-needed')
        self.assertTrue(result['reviewDiagnostics'])
        r.pop('unreviewedRefs')
        with self.assertRaisesRegex(ValueError,'unreviewedRefs'):self.project(r)

    def test_all_declared_extent_cannot_ignore_explicit_unreviewed_refs(self):
        r=review([item(kind='answered',actionClass='none')],unreviewedRefs=[dict(criterionId='governance')])
        r['reviewExtent']['kind']='all-declared-residuals'
        result,_=self.project(r)
        self.assertEqual(result['decision'],'review-needed')

    def test_foreign_duplicate_ids_and_source_shapes_are_input_errors(self):
        for mutate in (lambda r:r['items'].append(copy.deepcopy(r['items'][0])),
            lambda r:r['items'][0].update(questionIds=['foreign']),lambda r:r['items'][0].update(caseIds=['foreign']),
            lambda r:r['items'][0].update(findingIds=['foreign']),lambda r:r['items'][0].update(sourceRef='foreign'),
            lambda r:r.update(version=2),lambda r:r.update(scopeRevision='different'),
            lambda r:r['items'][0].update(criterionIds=['foreign'])):
            r=review();mutate(r)
            with self.assertRaises(ValueError):self.project(r)

    def test_new_finite_question_is_planning_only_and_remediation_needs_assignment(self):
        proposal=dict(id='new-q',question='Does valid title reach processing?',closureCondition='Read exact processing result',requiredObservations=['title-processed'])
        r=review([item(questionIds=[],proposedQuestion=proposal,actionClass='prepare'),
            item('fix',kind='remediation',questionIds=[],findingIds=['f'],assignmentBasis='not-assigned',actionClass='none')])
        result,p=self.project(r,findings=[dict(findingId='f',source='ZAP')])
        self.assertTrue(result['preparationNeeded']);self.assertEqual(result['remediation'][0]['assignmentBasis'],'not-assigned')
        self.assertNotIn('new-q',[q['id'] for q in p['securityScope']['questions']])

    def test_aggregate_refinement_preserves_obligation_revision_and_boundary(self):
        prior=scope();prior['questions'][0]['questionRole']='retained-aggregate'
        s=copy.deepcopy(prior);s['revision']='r2'
        child=copy.deepcopy(s['questions'][0]);child.update(id='child',questionRole='executable',refinesQuestionId='q-pin')
        s['questions'].append(child)
        normalized=normalize_scope(s,prior)
        self.assertEqual(len(normalized['questions']),3)
        a=dict(scopeRevision='r2',questionObservations={'child':observed()})
        p=project_scope(normalized,a,dict(operations=[operation()]),canonical_alerts([]))
        self.assertEqual(p['scopeCompletion'],'partial');self.assertEqual(p['openWork'][0]['nextStep'],'review-decomposition')
        s['revision']='r1'
        with self.assertRaisesRegex(ValueError,'revision'):normalize_scope(s,prior)
        for mutate in (lambda c:c.update(criterionIds=['governance']),lambda c:c['coverageContext'].update(objectRef='other')):
            bad=copy.deepcopy(normalized);mutate(bad['questions'][-1])
            with self.assertRaisesRegex(ValueError,'boundary'):normalize_scope(bad)
        bad=copy.deepcopy(normalized);bad['questions'][0]['refinesQuestionId']='q-pin'
        with self.assertRaisesRegex(ValueError,'cycle'):normalize_scope(bad)

    def test_user_stop_and_independent_case_do_not_create_parallel_scheduler(self):
        inv=inventory([case(actions=[action('run')])]);rec=reconcile(inv,{}, {})
        residual,_=self.project(review())
        result=select_next_work(inv,rec,{},[],{'run'},residual_work=residual)
        self.assertEqual(result['selectedActionId'],'run');self.assertTrue(result['planningProposal'])
        self.assertEqual(result['executionProposal']['selectedActionId'],'run')
        rec['continuationStoppedByUser']=True
        result=select_next_work(inv,rec,{},[],{'run'},residual_work=residual)
        self.assertIsNone(result['selectedActionId']);self.assertTrue(result['planningProposal'])
        self.assertEqual(result['reviewedScopeDecision']['decision'],'review-needed')

    def test_absent_review_keeps_legacy_execution_and_explicit_review_limit(self):
        inv=inventory([case(actions=[action('run')])]);rec=reconcile(inv,{}, {})
        result=select_next_work(inv,rec,{},[],{'run'})
        self.assertEqual(result['selectedActionId'],'run');self.assertEqual(result['residualReviewStatus'],'not-supplied')
        self.assertTrue(result['reviewedScopeDecision']['reviewDiagnostics'])

    def test_cli_review_verifies_source_and_never_dispatches_or_echoes_raw(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);r=review();r['sources'][0]['location']=str(root/'prior.json')
            s=scope();s.update(assessmentId='a',product='synthetic',environment='offline')
            a=dict(assessment(),residualReview=r);working=dict(assessmentId='a',product='synthetic',environment='offline',operations=[operation()])
            for name,data in dict(scope=s,assessment=a,run=working,prior=dict(criteria=[dict(remainingWork=[item()['originalText']])])).items():
                (root/(name+'.json')).write_text(json.dumps(data))
            args=['review-residuals','--security-scope',str(root/'scope.json'),'--scope-assessment',str(root/'assessment.json'),'--run',str(root/'run.json')]
            before={p.name:p.read_bytes() for p in root.iterdir()}
            with patch('socket.socket',side_effect=AssertionError('no traffic')),patch('zap_assessment.product_cli.main',side_effect=AssertionError('no dispatch')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args),0)
            result=json.loads(output.getvalue());self.assertEqual(result['decision'],'continue')
            self.assertNotIn('originalText',output.getvalue());self.assertEqual(before,{p.name:p.read_bytes() for p in root.iterdir()})
            (root/'prior.json').write_text('{}')
            with self.assertRaises(ValueError):main(args)
