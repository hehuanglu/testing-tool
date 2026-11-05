"""Round lifecycle is independent of coverage and requires whole-universe review."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from test_security_scope import scope, run, assessment
from zap_assessment.product_scope import compact_results
from zap_assessment.security_scope import project_scope, canonical_alerts, validate_bundle
from zap_assessment.round_closure import review_round_closure, review_current_round


def definition(s=None):
    s=s or scope()
    return dict(version=1,id='stable-round',objective='Review assigned retention',scopeBasis='User retention assignment',
        assessmentId=s['assessmentId'],product=s['product'],environment=s['environment'],scopeRevision=s['revision'],status='in-progress',
        reviewUniverse=dict(criterionIds=[c['id'] for c in s['criteria']],questionIds=[q['id'] for q in s['questions']],
            caseIds=[],sourceIds=[x['id'] for x in s['sources']],residualSourceIds=[],inventoryRefs=[]))


def inputs():
    s=scope();a=assessment();p=project_scope(s,a,run(),canonical_alerts({'alerts':[]}))
    residual=dict(residualReviewStatus='supplied',reviewExtent=dict(kind='all-declared-residuals',criterionIds=['retention']),
        reviewDiagnostics=[],unreviewedRefs=[],unclassified=[])
    p['residualWork']=residual
    return definition(s),p,{},residual,{},{}


def report_fixture(outcome='matched'):
    s=scope();a=assessment();a['questionObservations']['log-review']['outcome']=outcome
    # The residual references source text; it supplies no evidence itself.
    text=s['questions'][0]['question']
    a['residualReview']=dict(version=1,scopeRevision='r1',sources=[dict(id='current',kind='current-scope',location='scope.json')],
        reviewExtent=dict(kind='all-declared-residuals',criterionIds=['retention'],sourceIds=['current'],basis='Whole assigned retention scope'),
        unreviewedRefs=[],items=[dict(id='answered',sourceRef='current',sourcePointer='/questions/0/question',originalText=text,selectedText=text,
            criterionIds=['retention'],questionIds=['log-review'],caseIds=[],kind='answered',actionClass='none',
            basis='Actual setting compared with policy',nextStep='Retain observation; reopen after relevant deployment change')])
    d=definition(s);d['reviewUniverse']['residualSourceIds']=['current']
    r=run(assessmentId=s['assessmentId'],assessmentRound=d,scopeAssessment=a)
    return s,a,r


class RoundClosureTests(unittest.TestCase):
    def review(self,values):return review_round_closure(*values)

    def test_observed_violation_and_open_finding_can_complete(self):
        v=list(inputs());v[1]['criteria'][0]['securityAssessment']='violation-supported'
        self.assertEqual(self.review(v)['eligibleStatus'],'completed')

    def test_partial_method_catalog_can_close_with_limitations(self):
        v=list(inputs());v[1]['criteria'][0]['questions'][0]['coverage']='not-performed'
        v[3]['methodLimits']=[dict(id='governance',kind='method-limit',questionIds=['log-review'],
            basis='Governance audit outside ZAP',reopenCondition='Assign governance method')]
        self.assertEqual(self.review(v)['eligibleStatus'],'completed-with-limitations')
        self.assertEqual(self.review(v)['unansweredObligationIds'],['log-review'])

    def test_generalization_limit_does_not_create_duty(self):
        v=list(inputs());v[3]['conclusionLimits']=[dict(id='all-builds',kind='generalization-limit')]
        self.assertEqual(self.review(v)['eligibleStatus'],'completed')

    def test_missing_definition_does_not_infer_from_last_operation(self):
        v=list(inputs());v[0]=None
        self.assertEqual(self.review(v)['diagnostics'][0]['code'],'missing-round-definition')

    def test_selected_or_empty_residual_extent_never_closes_whole_round(self):
        for change in ('selected','omitted','empty'):
            v=list(inputs())
            if change=='selected':v[3]['reviewExtent']['kind']='selected-groups'
            if change=='omitted':v[0]['reviewUniverse']['questionIds']=[]
            if change=='empty':v[3]['reviewExtent']['criterionIds']=[]
            with self.subTest(change=change):self.assertIsNone(self.review(v)['eligibleStatus'])

    def test_unanswered_fixture_gap_and_empty_actions_need_review(self):
        v=list(inputs());v[1]['criteria'][0]['questions'][0]['coverage']='blocked'
        self.assertEqual(self.review(v)['decision'],'review-needed')

    def test_runtime_feasible_offline_is_continue(self):
        v=list(inputs());v[1]['criteria'][0]['questions'][0]['coverage']='blocked'
        v[3]['actionableExecution']=[dict(id='real-processing',actionClass='execute',nextStep='Use fresh baseline and input; read processed state')]
        self.assertEqual(self.review(v)['decision'],'continue');self.assertIsNone(self.review(v)['eligibleStatus'])

    def test_missing_handler_is_preparation_not_limitation(self):
        v=list(inputs());v[4]['missingHandlers']=[dict(actionId='reader',nextPreparation='prepare-adapter')]
        self.assertEqual(self.review(v)['decision'],'continue')

    def test_pending_aggregate_and_unreviewed_refs_block(self):
        for mode in ('parent','residual'):
            v=list(inputs())
            if mode=='parent':v[1]['aggregateAccounting']=dict(states=[dict(aggregateQuestionId='parent',accountingStatus='pending')])
            else:v[3]['unreviewedRefs']=[dict(criterionId='retention')]
            self.assertEqual(self.review(v)['decision'],'review-needed')

    def test_unknown_with_reader_reconciles(self):
        v=list(inputs());v[5]['pendingEffects']=[dict(actionId='mutation',readerNextStep='Read actual state')]
        self.assertEqual(self.review(v)['decision'],'continue')
        self.assertEqual(self.review(v)['nextWork'][0]['action'],'reconcile-state')

    def test_contained_unknown_preserves_uncertainty(self):
        v=list(inputs());v[5]['pendingEffects']=[dict(actionId='mutation',unavailableReadback=dict(
            exactEffect='STOP recording',lastKnownState='ACK lost',unavailableReason='Retained object expired; no valid reader',
            unknownImpact='Final STOP outcome unknown',noReplayRule='Never replay STOP',resourceDisposition='Producer stopped via independent teardown',
            reopenCondition='Recover retained state or valid object reader',contained=True))]
        result=self.review(v);self.assertEqual(result['eligibleStatus'],'completed-with-limitations')
        self.assertEqual(result['limitations'][0]['kind'],'unknown-effect')

    def test_unknown_producer_or_prose_only_shutdown_requires_checkpoint(self):
        for state in [dict(pendingEffects=[dict(actionId='start')]),dict(resources=[dict(resourceRef='scanner',disposition='stopped-retain')]),dict(pendingOperations=['scan']),dict(resources=[dict(resourceRef='owned-scanner',disposition='not-created')])]:
            v=list(inputs());v[5]=state;self.assertEqual(self.review(v)['decision'],'checkpoint-required')

    def test_cleanup_and_resource_readback(self):
        v=list(inputs());v[5]=dict(resources=[dict(resourceRef='scanner',disposition='stopped-retain',
            readbackRefs=[dict(operationId='exit',resultPath='/result/exitCode',expectedValue=0)])],operations=[dict(id='exit',status='completed',result=dict(exitCode=0))])
        self.assertEqual(self.review(v)['eligibleStatus'],'completed')
        v[5]['resources'][0]['cleanupNextStep']='Release fixture'
        self.assertEqual(self.review(v)['decision'],'continue')

    def test_user_pause_and_stop_are_distinct_and_source_required(self):
        for kind,decision in [('pause','checkpoint-required'),('stop','stopped-by-user')]:
            v=list(inputs());v[0]['userRequest']=dict(kind=kind,source='User message: '+kind)
            self.assertEqual(self.review(v)['decision'],decision)
        v[0]['userRequest'].pop('source')
        with self.assertRaises(ValueError):self.review(v)

    def test_invalid_round_refs_revision_fail(self):
        for field in ('scopeRevision','questionIds'):
            v=list(inputs())
            if field=='scopeRevision':v[0][field]='stale'
            else:v[0]['reviewUniverse'][field]=['foreign']
            with self.assertRaises(ValueError):self.review(v)

    def test_whole_inventory_units_must_be_reviewed(self):
        v=list(inputs());v[0]['reviewUniverse']['inventoryRefs']=['routes']
        v[1]['reviewInventories']=[dict(id='routes',scopeRevision='r1',unitIds=['a','b'],reviewedUnitIds=['a'],basis='Route inventory read')]
        self.assertIsNone(self.review(v)['eligibleStatus'])

    def test_track_only_round_needs_no_fake_catalog(self):
        v=list(inputs());v[0]['reviewUniverse'].update(criterionIds=[],questionIds=[],sourceIds=[],caseIds=['one'])
        v[1]={'criteria':[]};v[2]={'inventory':{'scopeRevision':'r1'},'cases':[{'caseId':'one','status':'observed'}], 'discoveryReview':{'reviewStatus':'reviewed','extent':{'kind':'assigned-scope'}}}
        self.assertEqual(self.review(v)['eligibleStatus'],'completed')

    def test_finalize_three_reports_and_violation_is_preserved(self):
        s,a,r=report_fixture('violated')
        alerts=dict(alerts=[dict(findingId='open',source='zap',description='Open finding',severity='high',confidence='confirmed')])
        with tempfile.TemporaryDirectory() as tmp,patch('socket.socket',side_effect=AssertionError('network forbidden')):
            out=Path(tmp)/'reports';result=compact_results(out,r,alerts,security_scope=s,scope_assessment=a,finalize_round=True)
            reports=[json.loads((out/n).read_text()) for n in ('RUN.json','ALERTS.json','SCOPE_ALERTS.json')]
            self.assertTrue(result['roundClosed']);self.assertEqual(result['assessmentRound']['status'],'completed')
            self.assertEqual(reports[1]['alerts'][0]['findingId'],'open');validate_bundle(*reports)
            for report in reports:self.assertEqual(report['completionSummary']['round']['status'],'completed')

    def test_caller_completed_cannot_override_open_work_or_touch_prior_bundle(self):
        s,a,r=report_fixture();r['assessmentRound']['status']='completed';a['questionObservations']={}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'reports';out.mkdir();(out/'RUN.json').write_text('prior')
            with self.assertRaisesRegex(ValueError,'round-finalization-ineligible'):
                compact_results(out,r,{'alerts':[]},security_scope=s,scope_assessment=a,finalize_round=True,overwrite=True)
            self.assertEqual((out/'RUN.json').read_text(),'prior')

    def test_staging_failure_does_not_publish_closed(self):
        s,a,r=report_fixture()
        with tempfile.TemporaryDirectory() as tmp,patch('zap_assessment.safety_io.atomic_bytes',side_effect=OSError('disk full')):
            out=Path(tmp)/'reports'
            with self.assertRaises(OSError):compact_results(out,r,{'alerts':[]},security_scope=s,scope_assessment=a,finalize_round=True)
            self.assertFalse(out.exists())

    def test_closed_round_reopens_after_build_change_without_replay(self):
        s,a,r=report_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            first=compact_results(Path(tmp)/'first',r,{'alerts':[]},security_scope=s,scope_assessment=a,finalize_round=True)
            first['currentTestedBuild']='new-build'
            second=compact_results(Path(tmp)/'second',first,{'alerts':[]},security_scope=s,scope_assessment=a)
            self.assertFalse(second['roundClosed']);self.assertEqual(second['assessmentRound']['status'],'in-progress')

    def test_legacy_lifecycle_is_undefined(self):
        with tempfile.TemporaryDirectory() as tmp:
            result=compact_results(Path(tmp)/'out',run(),{'alerts':[]},security_scope=scope(),scope_assessment=assessment())
            self.assertNotIn('assessmentRound',result);self.assertFalse(result['roundClosed'])


    def test_report_partial_catalog_round_closed_with_limitations(self):
        s,a,r=report_fixture();a['questionObservations']={}
        row=a['residualReview']['items'][0]
        row.update(kind='method-limit',methodBoundary='Governance method outside ZAP',reopenCondition='Assign governance review',basis='Original governance obligation not answered by dynamic tests')
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'reports'
            result=compact_results(out,r,{'alerts':[]},security_scope=s,scope_assessment=a,finalize_round=True)
            self.assertEqual(result['taskCompletion'],'partial');self.assertFalse(result['handoffClosesTask'])
            self.assertTrue(result['roundClosed']);self.assertEqual(result['assessmentRound']['status'],'completed-with-limitations')
            reports=[json.loads((out/n).read_text()) for n in ('RUN.json','ALERTS.json','SCOPE_ALERTS.json')]
            validate_bundle(*reports)
            reports[1]['completionSummary']['round']['status']='completed'
            with self.assertRaisesRegex(ValueError,'inconsistent round completion'):validate_bundle(*reports)

    def test_contained_unknown_limits_its_open_question_only(self):
        v=list(inputs());v[1]['criteria'][0]['questions'][0]['coverage']='blocked'
        v[5]['pendingEffects']=[dict(actionId='mutation',questionIds=['log-review'],unavailableReadback=dict(
            exactEffect='Change retained setting',lastKnownState='ACK lost',unavailableReason='Object expired; options reviewed',
            unknownImpact='Final setting unknown',noReplayRule='No replay',resourceDisposition='Producer stopped independently',
            reopenCondition='Recover object readback',contained=True))]
        result=self.review(v);self.assertEqual(result['eligibleStatus'],'completed-with-limitations')
        self.assertEqual(result['unansweredObligationIds'],['log-review'])

    def test_unresolved_applicability_cannot_be_completed_from_observed_child(self):
        v=list(inputs());v[1]['criteria'][0]['applicability']['status']='unknown'
        self.assertEqual(self.review(v)['decision'],'review-needed')
        self.assertIn('retention',self.review(v)['unansweredObligationIds'])

    def test_empty_round_universe_is_not_completion(self):
        v=list(inputs());v[0]['reviewUniverse']={};v[1]={'criteria':[]};v[2]={'inventory':{'scopeRevision':'r1'}}
        self.assertEqual(self.review(v)['decision'],'review-needed')

    def test_incomplete_resource_readback_or_false_terminal_does_not_close(self):
        v=list(inputs());v[5]=dict(resources=[dict(resourceRef='scanner',disposition='stopped-retain',
            readbackRefs=[dict(operationId='exit',resultPath='/result/stopped',expectedValue=True)])],
            operations=[dict(id='exit',status='completed',result=dict(stopped=False))])
        self.assertEqual(self.review(v)['decision'],'checkpoint-required')

    def test_scope_result_change_invalidates_finalized_bundle(self):
        s,a,r=report_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'reports';compact_results(out,r,{'alerts':[]},security_scope=s,scope_assessment=a,finalize_round=True)
            reports=[json.loads((out/n).read_text()) for n in ('RUN.json','ALERTS.json','SCOPE_ALERTS.json')]
            reports[0]['operations'][0]['result']={'setting':'changed'}
            with self.assertRaisesRegex(ValueError,'current round closure review|stale or unverified'):validate_bundle(*reports)

    def test_staged_corruption_is_rejected_before_publication(self):
        from zap_assessment.safety_io import atomic_bytes
        s,a,r=report_fixture()
        def corrupt(path,data):
            atomic_bytes(path,b'{}' if Path(path).name=='SCOPE_ALERTS.json' else data)
        with tempfile.TemporaryDirectory() as tmp,patch('zap_assessment.safety_io.atomic_bytes',side_effect=corrupt):
            out=Path(tmp)/'reports'
            with self.assertRaises((ValueError,KeyError)):compact_results(out,r,{'alerts':[]},security_scope=s,scope_assessment=a,finalize_round=True)
            self.assertFalse(out.exists())

    def test_same_underlying_duty_is_counted_once_without_hiding_open_child(self):
        from zap_assessment.coverage_presentation import work_units
        q=dict(id='one',underlyingDutyId='shared',coverage='observed',requiredObservations=['state'])
        other=dict(q,id='two',coverage='partial')
        units=work_units([q,other],{})
        self.assertEqual(len(units),1);self.assertEqual(units[0]['coverage'],'partial')
        self.assertEqual(units[0]['questionIds'],['one','two'])


    def test_scope_only_cli_finalizes_without_empty_reconciliation_crash(self):
        import contextlib
        import io
        from zap_assessment.product_cli import main
        s,a,r=report_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);a['residualReview']['sources'][0]['location']=str(root/'scope.json')
            for name,value in [('scope',s),('assessment',a),('run',r),('alerts',{'alerts':[]})]:
                (root/(name+'.json')).write_text(json.dumps(value))
            args=['scope','report','--run',str(root/'run.json'),'--alerts',str(root/'alerts.json'),
                '--security-scope',str(root/'scope.json'),'--scope-assessment',str(root/'assessment.json'),
                '--output',str(root/'out'),'--finalize-round']
            with contextlib.redirect_stdout(io.StringIO()),patch('socket.socket',side_effect=AssertionError('No network')):
                self.assertEqual(main(args),0)
            self.assertTrue(json.loads((root/'out/RUN.json').read_text())['roundClosed'])

    def test_known_route_units_cannot_be_omitted_from_self_declared_review(self):
        s,a,r=report_fixture();r['inventory']=[{'id':'route-a'},{'id':'route-b'}]
        p=project_scope(s,a,r,canonical_alerts({'alerts':[]}))
        r['reviewInventories']=[dict(id='routes',kind='routes',scopeRevision='r1',unitIds=['route-a'],reviewedUnitIds=['route-a'],basis='Only selected route')]
        r['assessmentRound']['reviewUniverse']['inventoryRefs']=['routes']
        result=review_current_round(r,p,{})
        self.assertIsNone(result['eligibleStatus'])
        self.assertIn('known-inventory-units-omitted',[d['code'] for d in result['diagnostics']])

    def test_aggregate_json_source_pointer_is_checked_by_cli_loader(self):
        from test_aggregate_closure import aggregate_fixture
        from zap_assessment.product_scope_cli import residual_context
        s,a=aggregate_fixture()
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/'source.json';file.write_text(json.dumps({'retention':'Original clause'}))
            s['sources'][0]['location']=str(file)
            self.assertIsNotNone(residual_context(s,a,run(),{}))
            # Aggregate sources may belong to retained residual documents rather
            # than the normalized scope sources. Keep them during evidence join.
            a['residualReview']=dict(version=1,scopeRevision='r1',sources=[dict(id='retained',kind='retained-report',location=str(file))],
                reviewExtent=dict(kind='all-declared-residuals',sourceIds=['retained'],criterionIds=['retention'],basis='Original clause reviewed'),unreviewedRefs=[],items=[dict(
                    id='limit',sourceRef='retained',sourcePointer='/retention',originalText='Original clause',selectedText='Original clause',criterionIds=['retention'],
                    questionIds=[],caseIds=[],kind='generalization-limit',actionClass='none',scopeBasis='Finite assigned question',excludedConclusions=['Other builds'],basis='Other builds not assigned',nextStep='Reopen on build change')])
            a['aggregateReviews']['rows'][0]['sourceRefs'][0]['sourceRef']='retained'
            self.assertIsNotNone(residual_context(s,a,run(),{}))
            a['aggregateReviews']['rows'][0]['sourceRefs'][0]['sourcePointer']='/missing'
            with self.assertRaisesRegex(ValueError,'unresolved resultPath'):residual_context(s,a,run(),{})


    def test_method_limit_cannot_disappear_behind_observed_subset(self):
        v=list(inputs());v[3]['methodLimits']=[dict(id='unmapped-governance',kind='method-limit',criterionIds=['retention'],
            basis='Original governance duty not answered by observed finite setting',reopenCondition='Assign governance review')]
        result=self.review(v);self.assertIsNone(result['eligibleStatus'])
        self.assertIn('limitation-not-mapped-to-unanswered-duty',[d['code'] for d in result['diagnostics']])
