"""Finite parent accounting cannot grant evidence to an unanswered child."""
import copy
import tempfile
import unittest
from pathlib import Path

from test_security_scope import scope, run, assessment
from zap_assessment.security_scope import project_scope, canonical_alerts
from zap_assessment.product_scope import compact_results
from zap_assessment.round_closure import review_aggregate_obligations


def aggregate_fixture():
    s=scope();child=s['questions'][0];child['refinesQuestionId']='all-retention'
    parent=dict(id='all-retention',criterionIds=['retention'],question='Retain and review logs',
        closureCondition='All assigned retention duties answered',requiredObservations=['old-placeholder'],
        questionRole='retained-aggregate')
    s['questions'].insert(0,parent)
    a=assessment();a['aggregateReviews']=dict(version=1,rows=[dict(aggregateQuestionId=parent['id'],scopeRevision='r1',
        sourceRefs=[dict(sourceRef='business-policy',sourcePointer='/retention')],
        coverageBasis='Original requirement has one finite retention setting duty; mapped to the independently checked child.',
        unmappedClauses=[],obligationAtoms=[dict(id='setting',text='Retention value matches policy',basis='Original retention requirement',
            questionIds=['log-review'],residualItemIds=[],disposition='tested-question')])])
    return s,a


class AggregateClosureTests(unittest.TestCase):
    def project(self,s,a):return project_scope(s,a,run(),canonical_alerts({'alerts':[]}))

    def test_full_parent_coverage_without_placeholder_and_history_unchanged(self):
        s,a=aggregate_fixture();before=copy.deepcopy(s);p=self.project(s,a)
        parent=p['criteria'][0]['questions'][0]
        self.assertEqual((parent['coverage'],parent['aggregateAccounting']['accountingStatus']),('observed','accounted'))
        self.assertEqual(p['scopeCompletion'],'complete');self.assertEqual(s,before)
        self.assertEqual(parent['requiredObservations'],['old-placeholder'])
        with tempfile.TemporaryDirectory() as tmp:
            compact_results(Path(tmp)/'reports',run(),{'alerts':[]},security_scope=s,scope_assessment=a)

    def test_missing_review_cannot_close_parent_even_with_observed_child(self):
        s,a=aggregate_fixture();del a['aggregateReviews'];p=self.project(s,a)
        self.assertEqual(p['aggregateAccounting']['states'][0]['accountingStatus'],'pending')
        self.assertEqual(p['scopeCompletion'],'partial')

    def test_missing_clause_or_basis_keeps_accounting_pending(self):
        for field,value in [('unmappedClauses',['access protection']),('coverageBasis','')]:
            s,a=aggregate_fixture();a['aggregateReviews']['rows'][0][field]=value
            self.assertEqual(self.project(s,a)['aggregateAccounting']['states'][0]['accountingStatus'],'pending')

    def test_unmapped_child_is_not_dropped(self):
        s,a=aggregate_fixture();q=copy.deepcopy(s['questions'][1]);q['id']='other';s['questions'].append(q)
        self.assertIn('aggregate-unmapped-children',[d['code'] for d in self.project(s,a)['aggregateAccounting']['diagnostics']])

    def test_violation_is_answered_coverage(self):
        s,a=aggregate_fixture();a['questionObservations']['log-review']['outcome']='violated'
        p=self.project(s,a);self.assertEqual(p['scopeCompletion'],'complete')
        self.assertEqual(p['criteria'][0]['securityAssessment'],'violation-supported')

    def test_method_limit_accounted_but_partial(self):
        s,a=aggregate_fixture();row=a['aggregateReviews']['rows'][0]
        row['obligationAtoms'].append(dict(id='governance',text='Governance audit',basis='Original requires governance',
            questionIds=[],residualItemIds=['outside'],disposition='external-or-method-limit'))
        qs=[dict(q,coverage='observed') for q in s['questions']]
        residual=dict(methodLimits=[dict(id='outside',kind='method-limit',criterionIds=['retention'])])
        result=review_aggregate_obligations(s,a,qs,residual)['states'][0]
        self.assertEqual((result['accountingStatus'],result['coverage']),('accounted','partial'))
        self.assertEqual(result['unansweredObligationIds'],['governance'])

    def test_open_child_cannot_be_called_conclusion_limit(self):
        s,a=aggregate_fixture();atom=a['aggregateReviews']['rows'][0]['obligationAtoms'][0]
        atom.update(disposition='conclusion-limit',residualItemIds=['limit'])
        result=review_aggregate_obligations(s,a,[dict(q,coverage='partial') for q in s['questions']],
            dict(conclusionLimits=[dict(id='limit',kind='generalization-limit',criterionIds=['retention'])]))
        self.assertEqual(result['states'][0]['accountingStatus'],'pending')

    def test_bad_revision_refs_and_wrong_child_are_input_errors(self):
        for change in ('revision','child','source','residual'):
            s,a=aggregate_fixture();row=a['aggregateReviews']['rows'][0];atom=row['obligationAtoms'][0]
            if change=='revision':row['scopeRevision']='old'
            if change=='child':atom['questionIds']=['all-retention']
            if change=='source':row['sourceRefs'][0]['sourceRef']='foreign'
            if change=='residual':atom['residualItemIds']=['foreign']
            with self.subTest(change=change),self.assertRaises(ValueError):self.project(s,a)

    def test_unknown_effect_on_child_cannot_close_coverage(self):
        s,a=aggregate_fixture();a['questionObservations']['log-review']['outcomeUnknown']=True
        p=self.project(s,a);self.assertEqual(p['aggregateAccounting']['states'][0]['accountingStatus'],'accounted')
        self.assertEqual(p['scopeCompletion'],'partial')


    def test_nested_reviews_use_child_accounting_before_parent_independent_of_order(self):
        s,a=aggregate_fixture();child=s['questions'][1]
        intermediate=dict(id='nested',question='Nested retained requirement',criterionIds=['retention'],
            closureCondition='Account original clauses',requiredObservations=['old-nested-placeholder'],
            questionRole='retained-aggregate',refinesQuestionId='all-retention')
        child['refinesQuestionId']='nested';s['questions'].append(intermediate)
        outer=a['aggregateReviews']['rows'][0];nested=copy.deepcopy(outer);nested['aggregateQuestionId']='nested'
        outer['obligationAtoms'][0]['questionIds']=['nested']
        a['aggregateReviews']['rows'].append(nested)
        text=child['question']
        a['residualReview']=dict(version=1,scopeRevision='r1',sources=[dict(id='current',kind='current-scope',location='scope.json')],
            reviewExtent=dict(kind='all-declared-residuals',criterionIds=['retention'],sourceIds=['current'],basis='All original clauses reviewed'),
            unreviewedRefs=[],items=[dict(id='answered',sourceRef='current',sourcePointer='/questions/1/question',originalText=text,selectedText=text,
                criterionIds=['retention'],questionIds=['log-review'],caseIds=[],kind='answered',actionClass='none',basis='Actual setting read',nextStep='Retain results')])
        for order in (list(a['aggregateReviews']['rows']),list(reversed(a['aggregateReviews']['rows']))):
            a['aggregateReviews']['rows']=order
            result=self.project(s,a)
            self.assertEqual(result['scopeCompletion'],'complete')
            self.assertTrue(all(x['coverage']=='observed' for x in result['aggregateAccounting']['states']))
            with tempfile.TemporaryDirectory() as tmp:
                compact_results(Path(tmp)/'reports',run(),{'alerts':[]},security_scope=s,scope_assessment=a)

    def test_nested_missing_review_does_not_inherit_observed_projection(self):
        s,a=aggregate_fixture();s['questions'][1]['questionRole']='retained-aggregate'
        result=review_aggregate_obligations(s,a,[dict(q,coverage='observed') for q in s['questions']],{})
        self.assertTrue(all(x['coverage']=='partial' for x in result['states']))

    def test_nested_fixture_processing_gap_remains_open(self):
        s,a=aggregate_fixture();child=s['questions'][1];child['refinesQuestionId']='nested'
        s['questions'].append(dict(id='nested',questionRole='retained-aggregate',refinesQuestionId='all-retention',criterionIds=['retention'],
            question='Actual processing not observed',closureCondition='Read intended processing',requiredObservations=['old-placeholder']))
        outer=a['aggregateReviews']['rows'][0];nested=copy.deepcopy(outer);nested['aggregateQuestionId']='nested';outer['obligationAtoms'][0]['questionIds']=['nested']
        a['aggregateReviews']['rows'].append(nested);a['questionObservations']={}
        result=self.project(s,a)
        self.assertEqual(result['scopeCompletion'],'partial')
        self.assertTrue(all(x['coverage']=='partial' for x in result['aggregateAccounting']['states']))
