import copy
import json
from pathlib import Path
import tempfile
import unittest

from zap_assessment.coverage_presentation import import_coverage_history, work_units
from zap_assessment.product_scope import compact_results, reconcile
from zap_assessment.security_scope import canonical_alerts, normalize_scope, project_scope, validate_bundle
from test_question_evidence import scope, assessment
from workflow_fixtures import inventory, operation, observed


def historical(document=None, source_id='prior', build='old'):
    document=document or scope()
    identity=dict(assessmentId='old-'+build, product='synthetic', environment='offline', build=build)
    report=dict(assessmentContext=identity, criteria=[dict(id=c['id'],coverage='partial',securityAssessment='inconclusive',
        applicability={'status':'applicable'}, interpretation='Retained historical meaning', raw={'token':'never-import'}) for c in document['criteria']])
    source=dict(id=source_id,location='/explicit/prior-report.json',assessmentContext=identity)
    return import_coverage_history(document,report,source)


class CoveragePresentationTests(unittest.TestCase):
    def project(self, s=None, a=None):
        return project_scope(s or historical(),a or dict(scopeRevision='r1'),dict(operations=[operation()]),canonical_alerts([]))

    def test_history_only_preserves_current_coverage_and_partial_assignment(self):
        p=self.project();c=p['criteria'][0]
        self.assertEqual(c['coverage'],'not-performed')
        self.assertEqual(c['coverageMeaning'],'current-question-projection')
        self.assertEqual(c['coverageView']['displayStatus'],'historical-only')
        self.assertIn('Historical partial',c['coverageView']['displayMeaning'])
        self.assertEqual(c['coverageView']['historical']['credit'],'historical-only')
        self.assertEqual(p['scopeCompletion'],'partial')
        self.assertNotIn('never-import',json.dumps(p))
        self.assertEqual(p['coveragePresentation']['counts']['historical-only'],2)

    def test_history_and_finite_delta_do_not_close_aggregate_or_criterion(self):
        s=historical();q=copy.deepcopy(s['questions'][0]);q.update(id='aggregate',questionRole='retained-aggregate',unresolved=['Review full assignment'])
        s['questions'].append(q)
        p=self.project(s,assessment());c=p['criteria'][0]
        self.assertEqual(c['coverageView']['displayStatus'],'historical-with-current-delta')
        self.assertEqual(c['coverageView']['current']['observedQuestionIds'],['q-pin'])
        self.assertEqual(p['openWork'][0]['nextStep'],'review-decomposition')
        self.assertEqual(p['scopeCompletion'],'partial')

    def test_current_blocker_is_not_presented_as_observed_delta(self):
        p=self.project(historical(),dict(scopeRevision='r1',questionObservations={'q-pin':dict(blockers=['Missing actor'])}))
        view=p['criteria'][0]['coverageView']
        self.assertEqual(view['displayStatus'],'historical-only')
        self.assertEqual(view['current']['status'],'blocked')
        self.assertIn('observations not established',view['displayMeaning'])

    def test_observed_violation_has_current_credit_without_remediation_assignment(self):
        p=self.project(historical(),assessment(observed(outcome='violated')))
        c=p['criteria'][0]
        self.assertEqual(c['coverageView']['displayStatus'],'current-observed')
        self.assertEqual(c['securityAssessment'],'violation-supported')

    def test_na_and_user_exclusion_are_separate_and_conflicts_stay_open(self):
        for disposition in ('not-applicable','user-excluded'):
            s=historical()
            if disposition=='not-applicable':s['criteria'][0]['applicability']=dict(status=disposition,basis='No local password store')
            else:s['criteria'][0].update(disposition=disposition,scopeBasis='User narrowed scope')
            p=self.project(s,assessment())
            self.assertEqual(p['criteria'][0]['coverageView']['displayStatus'],disposition)
            self.assertEqual(p['coveragePresentation']['counts'][disposition],1)
            self.assertTrue(p['criteria'][0]['openWork'])

    def test_multiple_contexts_stay_records_without_max_or_union(self):
        s=historical(historical(),source_id='prior2',build='older')
        c=self.project(s)['criteria'][0]
        self.assertEqual(c['coverageView']['historical']['status'],'mixed-history')
        self.assertEqual(len(c['coverageView']['historical']['records']),2)
        self.assertEqual(c['coverage'],'not-performed')

    def test_legacy_embedded_is_visible_with_missing_binding(self):
        s=scope();s['criteria'][0]['priorAssessment']=dict(coverage='partial',securityAssessment='old result')
        c=self.project(s)['criteria'][0]
        self.assertEqual(c['coverageView']['historical']['records'][0]['binding'],'legacy-embedded')
        self.assertTrue(c['coverageView']['diagnostics'])
        self.assertEqual(c['coverage'],'not-performed')

    def test_import_explicit_identity_and_source_binding_validation(self):
        s=historical();normalize_scope(s)
        for mutate in (lambda c:c['coverageHistory'].update(version=2),
                       lambda c:c['coverageHistory']['records'][0].update(sourceRef='missing'),
                       lambda c:c['coverageHistory']['records'][0].update(meaning='current-credit'),
                       lambda c:c['coverageHistory']['records'][0].update(sourceCriterionId='wrong'),
                       lambda c:c['coverageHistory']['records'][0]['context'].update(assessmentId='wrong')):
            bad=copy.deepcopy(s);mutate(bad['criteria'][0])
            with self.assertRaises(ValueError):normalize_scope(bad)
        with self.assertRaisesRegex(ValueError,'identity mismatch'):
            import_coverage_history(scope(),dict(assessmentContext={'assessmentId':'a'},criteria=[]),dict(id='p',location='x',assessmentContext={'assessmentId':'b'}))

    def test_work_unit_identity_multiple_questions_cases_and_extra_requirements(self):
        rec=reconcile(inventory(),{'pin':observed()},{},operations=[operation()])
        q=dict(id='one',responsibilityIds=['pin'],requiredObservations=['own-read','sibling-read'],coverage='observed')
        other=dict(q,id='two')
        self.assertEqual(len(work_units([q,other],rec)),1)
        units=work_units([q,dict(other,requiredObservations=['additional-processing'])],rec)
        self.assertEqual([u['id'] for u in units],['case:pin','question:two'])
        self.assertIn('additional-processing',units[1]['basis'])
        pending=work_units([dict(q,coverage='not-performed')],rec)[0]
        self.assertEqual(pending['caseCoverage'],'observed')
        self.assertEqual(pending['coverage'],'partial')
        self.assertEqual(pending['openQuestionIds'],['one'])
        second=copy.deepcopy(rec);second['inventory']['cases'].append(dict(second['inventory']['cases'][0],caseId='second'))
        units=work_units([dict(q,responsibilityIds=['pin','second'])],second)
        self.assertEqual({u['id'] for u in units},{'case:pin','case:second'})

    def test_bundle_rejects_corrupted_views_and_work_unit_counts(self):
        with tempfile.TemporaryDirectory() as temp:
            compact_results(Path(temp)/'reports',dict(operations=[operation()]),[],security_scope=historical(),scope_assessment=assessment())
            reports=[json.loads((Path(temp)/'reports'/name).read_text()) for name in ('RUN.json','ALERTS.json','SCOPE_ALERTS.json')]
            validate_bundle(*reports)
            bad=copy.deepcopy(reports);bad[2]['criteria'][0]['coverageView']['displayStatus']='historical-only'
            with self.assertRaisesRegex(ValueError,'coverageView'):validate_bundle(*bad)
            bad=copy.deepcopy(reports);bad[0]['completionSummary']['dast']['workUnits']=[]
            with self.assertRaisesRegex(ValueError,'completion summary'):validate_bundle(*bad)
            bad=copy.deepcopy(reports);bad[2]['coveragePresentation']['counts']['not-performed']=50
            with self.assertRaisesRegex(ValueError,'presentation counts'):validate_bundle(*bad)

    def test_discovery_delta_labels_are_not_whole_track_retest(self):
        inv=inventory();inv['discoveryReview']['extent']=dict(kind='delta',featureIds=['pin'],caseIds=['pin'],basis='One omitted finite question')
        rec=reconcile(inv,{'pin':observed()},{},operations=[operation()])
        self.assertEqual(rec['completionSummary']['trackSummary'][0]['reviewExtent'],'delta')
        self.assertEqual(rec['completionSummary']['discovery']['featureGroupsReviewed'],1)
        self.assertEqual(rec['completionSummary']['dast']['questionIdsMeaning'],'references-not-independent-test-count')
