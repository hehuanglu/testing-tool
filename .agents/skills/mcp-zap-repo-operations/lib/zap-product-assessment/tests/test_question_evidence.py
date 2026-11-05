import copy
import json
from pathlib import Path
import tempfile
import unittest
from zap_assessment.question_evidence import resolve_question_evidence, collect_pending_effects, read_pointer
from zap_assessment.product_scope import reconcile, compact_results
from zap_assessment.security_scope import project_scope, canonical_alerts, normalize_scope
from workflow_fixtures import case, inventory, operation, observed, link, context


def scope():
    return dict(workflowVersion=1,revision='r1',complete=True,sources=[dict(id='user',location='assignment')],
        criteria=[dict(id='setting',source=dict(id='user',location='assignment#setting'),originalText='Check setting ownership',applicability=dict(status='applicable')),
                  dict(id='governance',source=dict(id='user',location='assignment#governance'),originalText='Review retention policy',applicability=dict(status='applicable'))],
        questions=[dict(id='q-pin',criterionIds=['setting'],question='Is owner isolated?',methodClass='zap-business-observation',
            objectiveDepth='persistence',coverageContext=context(),expectedBehavior='Only owner changes',expectationBasis='Assigned rule',closureCondition='Read owner and sibling',requiredObservations=['own-read','sibling-read']),
            dict(id='q-policy',criterionIds=['governance'],question='Is retention policy reviewed?',methodClass='outside-zap',closureCondition='Review policy',requiredObservations=['policy-review'])])


def assessment(observation=None):
    return dict(scopeRevision='r1',questionObservations={'q-pin':observation or observed()},mappings=[])


class QuestionEvidenceTests(unittest.TestCase):
    def test_partial_attempt_supports_pin_but_not_background(self):
        inv=inventory([case(),case('background',units=['processing'],featureIds=['background'])])
        result=reconcile(inv,{'pin':observed()},{},operations=[operation()])
        self.assertEqual([c['status'] for c in result['cases']],['observed','eligible'])
        self.assertEqual(result['questionEvidence']['background']['missingUnits'],['processing'])
        self.assertEqual(result['taskCompletion'],'partial')

    def test_completed_attempt_does_not_supply_any_units(self):
        result=reconcile(inventory(),{'pin':observed([])},{},operations=[operation(status='completed')])
        self.assertEqual(result['cases'][0]['status'],'eligible')
        self.assertEqual(result['cases'][0]['missingEvidence'],['own-read','sibling-read'])

    def test_context_history_is_not_support_and_followup_is_support(self):
        old=operation();new=operation('followup',status='completed')
        obs=observed([link(role='context',observationUnits=[]),link('followup')])
        result=resolve_question_evidence(case(),obs,[old,new])
        self.assertEqual(result['supportOperationIds'],['followup'])
        self.assertEqual(result['contextOperationIds'],['attempt-a'])
        self.assertFalse(result['missingUnits'])
        self.assertEqual(old['status'],'partial')

    def test_unknown_context_link_still_blocks_and_exact_readback_resolves(self):
        op=operation(outcomeUnknown=True,actionId='change',caseId='pin')
        pending=collect_pending_effects([op])
        obs=observed([link(role='context',observationUnits=[]),link('followup')])
        followup=operation('followup',status='completed')
        result=resolve_question_evidence(case(),obs,[op,followup],pending)
        self.assertEqual(result['unresolvedEffectIds'],['change'])
        self.assertEqual(result['supportedUnits'],[])
        followup['readback']['resolution']=dict(actionId='change',caseId='pin',resolved=True,context=context())
        obs['resolvedEffects']=[dict(actionId='change',resolutionOperationId='followup',resultPath='/readback/resolution',basis='Read exact action/object state')]
        result=resolve_question_evidence(case(),obs,[op,followup],pending)
        self.assertEqual(result['unresolvedEffectIds'],[])
        self.assertFalse(result['missingUnits'])
        followup['readback']['resolution']['context']['objectRef']='wrong'
        with self.assertRaisesRegex(ValueError,'context'):resolve_question_evidence(case(),obs,[op,followup],pending)

    def test_unknown_intent_union_and_independent_object(self):
        history=[dict(actionId='lost',caseId='background',effect='mutation',state='intent',coverageContext=context(objectRef='background-object'))]
        pending=collect_pending_effects([],history)
        self.assertEqual(resolve_question_evidence(case(),observed(),[operation()],pending)['unresolvedEffectIds'],[])
        del pending[0]['caseId'];del pending[0]['coverageContext']
        self.assertEqual(resolve_question_evidence(case(),observed(),[operation()],pending)['unresolvedEffectIds'],['lost'])
        history.append({**history[0],'state':'acknowledged'})
        retained, = collect_pending_effects([], history)
        self.assertEqual(retained['actionId'], 'lost')
        self.assertEqual(retained['coverageContext']['objectRef'], 'background-object')

    def test_different_context_never_unions_and_reviewed_inheritance_is_explicit(self):
        for dimension,value in [('objectRef','other'),('build','b2'),('origin','https://other.invalid'),('inputLocation','query:q')]:
            with self.subTest(dimension=dimension):
                changed=context(**{dimension:value});op=operation(coverageContext=changed);obs=observed([link(context=changed)])
                result=resolve_question_evidence(case(),obs,[op])
                self.assertEqual(result['supportedUnits'],[])
                self.assertTrue(result['contextDiagnostics'])
        changed=context(build='b0');obs=observed([link(context=changed,compatibility=dict(basis='Explicit finite same-handler review',dimensions={'build':{'from':'b0','to':'b1'}},operationIds=['attempt-a']))])
        self.assertFalse(resolve_question_evidence(case(),obs,[operation(coverageContext=changed)])['missingUnits'])
        obs['evidenceLinks'][0]['compatibility']['dimensions']={'origin':{'from':changed['origin'],'to':context()['origin']}}
        with self.assertRaises(ValueError):resolve_question_evidence(case(),obs,[operation(coverageContext=changed)])

    def test_invalid_refs_pointers_claimed_units_and_contexts_are_errors(self):
        mutations=[lambda o:o['evidenceLinks'][0].update(operationId='missing'),
            lambda o:o['evidenceLinks'][0].update(resultPath='/absent'),
            lambda o:o.update(evidenceUnits=['processing']),
            lambda o:o['evidenceLinks'][0].update(resultRead=False),
            lambda o:o['evidenceLinks'][0].update(role='invented'),
            lambda o:o['evidenceLinks'][0].update(context='owner')]
        for mutate in mutations:
            obs=observed();mutate(obs)
            with self.subTest(obs=obs),self.assertRaises(ValueError):resolve_question_evidence(case(),obs,[operation()])
        self.assertFalse(read_pointer({'facts':{'zero':False}},'/facts/zero'))
        with self.assertRaises(ValueError):read_pointer({'facts':{}},'/facts')

    def test_boundary_rejection_does_not_answer_processing_or_need_media(self):
        c=case(units=['rejection','no-effect'],objectiveDepth='boundary')
        obs=observed([link(units=['rejection','no-effect'])])
        self.assertFalse(resolve_question_evidence(c,obs,[operation()])['missingUnits'])
        c['requiredEvidence'].append('sink-processing')
        self.assertEqual(resolve_question_evidence(c,obs,[operation()])['missingUnits'],['sink-processing'])

    def test_different_support_contexts_cannot_union_even_without_question_dimensions(self):
        c=case(coverageContext={})
        ops=[operation(),operation('other',coverageContext=context(objectRef='other'))]
        obs=observed([link(units=['own-read']),link('other',units=['sibling-read'],context=context(objectRef='other'))])
        result=resolve_question_evidence(c,obs,ops)
        self.assertEqual(result['supportedUnits'],[])
        self.assertIn('support-contexts-conflict-review-required',result['contextDiagnostics'])

    def test_explicit_top_level_actor_and_pending_object_are_not_lost(self):
        c=case(coverageContext={},actorRef='owner')
        obs=observed([link(context={'actorRef':'different'})])
        result=resolve_question_evidence(c,obs,[operation(coverageContext={})])
        self.assertFalse(result['supportedUnits'])
        history=[dict(actionId='write',caseId='pin',state='intent',effect='mutation',objectRef='object-one'),
            dict(actionId='write',caseId='pin',state='unknown',effect='mutation')]
        pending=collect_pending_effects([],history,[dict(actionId='write',effectId='write')])
        self.assertEqual(pending[0]['coverageContext']['objectRef'],'object-one')
        op=operation('resolve',coverageContext={},readback={'resolution':dict(actionId='write',caseId='pin',resolved=True,context={'objectRef':'other'})})
        obs=observed([],resolvedEffects=[dict(actionId='write',resolutionOperationId='resolve',resultPath='/readback/resolution',basis='Read state')])
        with self.assertRaisesRegex(ValueError,'context'):resolve_question_evidence(case(),obs,[op],pending)

    def test_workflow_contract_cannot_downgrade_with_prior_scope(self):
        prior=normalize_scope(scope());current=scope();current.pop('workflowVersion');current['revision']='r2'
        with self.assertRaisesRegex(ValueError,'downgrade'):normalize_scope(current,prior)

    def test_legacy_resolver_labels_remain_legacy(self):
        obs=dict(evidenceUnits=['own-read'],resultRead=True,outcome='matched')
        result=resolve_question_evidence(case(),obs,[])
        self.assertEqual(result['supportedUnits'],['own-read'])
        self.assertEqual(result['contextDiagnostics'],['legacy-unit-labels'])

    def test_required_case_still_blocks_criterion_despite_valid_followup(self):
        s=scope();s['questions'][0]['responsibilityIds']=['pin']
        rec=reconcile(inventory(),{}, {},operations=[operation()])
        projection=project_scope(s,assessment(),{'operations':[operation()]},canonical_alerts([]),rec)
        question=projection['criteria'][0]['questions'][0]
        self.assertNotEqual(question['coverage'],'observed')
        self.assertFalse(question['missingObservations'])
        rec=reconcile(inventory(),{'pin':observed()},{},operations=[operation()])
        projection=project_scope(s,assessment(),{'operations':[operation()]},canonical_alerts([]),rec)
        self.assertEqual(projection['criteria'][0]['questions'][0]['coverage'],'observed')

    def test_violation_complete_dast_partial_catalog_and_history_preserved(self):
        op=operation();op['implementationPins']={'old':'original'};old=copy.deepcopy(op)
        raw=dict(taskCompletion='partial',operations=[op])
        alerts={'alerts':[dict(findingId='original-finding',source='zap-business-observation',severity='observation',status='open')]}
        original=copy.deepcopy(alerts)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'reports'
            result=compact_results(output,raw,alerts,security_scope=scope(),scope_assessment=assessment(observed(outcome='violated')))
            self.assertEqual(result['taskCompletion'],'partial')
            summary=result['completionSummary']
            self.assertEqual(summary['dast']['status'],'complete')
            self.assertEqual(summary['assignment']['unresolvedIds'],['governance'])
            self.assertEqual(summary['remediation']['status'],'not-assigned')
            self.assertEqual(summary['securityOutcome']['findingIds'],['original-finding'])
            for name in ('RUN','ALERTS','SCOPE_ALERTS'):
                report=json.loads((output/(name+'.json')).read_text())
                self.assertEqual(report['taskCompletion'],'partial')
            self.assertEqual(result['operations'][0]['status'],'partial')
            self.assertEqual(len(result['notPerformed']),1)
        self.assertEqual(op,old);self.assertEqual(alerts,original)

    def test_unknown_method_mapping_is_a_dast_gap_not_outside_scope(self):
        s=scope();s['questions'][1].pop('methodClass')
        with tempfile.TemporaryDirectory() as temp:
            result=compact_results(Path(temp)/'reports',{'operations':[operation()]},[],security_scope=s,scope_assessment=assessment())
            self.assertEqual(result['completionSummary']['dast']['status'],'partial')
            self.assertIn('q-policy',result['completionSummary']['dast']['gaps'])

    def test_redaction_removed_pointer_is_rejected_before_publication(self):
        op=operation();op['responseBody']={'result':True}
        obs=observed([link(resultPath='/responseBody/result')])
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'reports'
            with self.assertRaisesRegex(ValueError,'resultPath'):
                compact_results(output,{'operations':[op]},[],security_scope=scope(),scope_assessment=assessment(obs))
            self.assertFalse(output.exists())

    def test_expectation_required_keeps_policy_question_open(self):
        s=scope();q=s['questions'][0];q['expectationRequired']=True;q.pop('expectationBasis')
        result=project_scope(s,assessment(),{'operations':[operation()]},canonical_alerts([]))
        self.assertEqual(result['criteria'][0]['questions'][0]['securityAssessment'],'inconclusive')
