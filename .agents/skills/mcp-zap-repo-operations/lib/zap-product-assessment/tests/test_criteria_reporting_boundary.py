"""Offline admission, projection and publication checks for the v2 handoff."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

from test_criteria_workflow import approve, fixed_working, working
from zap_assessment.criteria_reporting import (alert_projection, publish_reports,
    validate_report_bundle)


def observed(identity='observed'):
    return dict(findingId=identity, recordKind='observed-security-alert', source='tester',
        provenance={'transport': 'zap-proxy'}, operationIds=['O1'],
        securitySignal='Cross-owner disclosure', expectedBehavior='Denied',
        observedBehavior='Owner object returned', expectationBasis='Expert owner policy',
        status='suspected')


def native(identity='native'):
    return dict(findingId=identity, recordKind='native-zap-alert', source='ZAP',
        provenance={'transport': 'zap-native', 'sessionId': 'session-1'}, nativeRuleId=0,
        nativeAlertId='native-1', severity='Informational', confidence='Low',
        instances=[{'nativeAlertId': 'native-1', 'url': 'https://example.test/read'}],
        instanceCount=1)


def mapped_working():
    run = working('violated')
    run['criteriaWorkflow']['alertMappings'] = [dict(findingId='observed',
        criterionId='C1', rationale='The owner-only object was returned to the other actor')]
    return run


class ReportingBoundaryTests(unittest.TestCase):
    def test_report_counts_follow_lists_and_occurrences_stay_separate(self):
        alerts, scoped, _ = alert_projection(mapped_working(), [observed(), native()])
        self.assertEqual(alerts['summary']['alertCount'], 2)
        self.assertEqual(alerts['summary']['totalAlertCount'], 2)
        self.assertEqual(alerts['summary']['nativeAlertCount'], 1)
        self.assertEqual(alerts['summary']['observedAlertCount'], 1)
        self.assertEqual(alerts['summary']['occurrenceCount'], 1)
        self.assertEqual(alerts['summary']['unknownOccurrenceAlertCount'], 1)
        self.assertEqual(scoped['summary']['alertCount'], 1)
        self.assertEqual(scoped['summary']['totalAlertCount'], 2)
        self.assertEqual(scoped['summary']['nativeAlertCount'], 0)
        self.assertEqual(scoped['summary']['observedAlertCount'], 1)
        self.assertEqual(scoped['summary']['occurrenceCount'], 0)
        self.assertEqual(scoped['summary']['unknownOccurrenceAlertCount'], 1)
        self.assertEqual(scoped['summary']['mappedAlertCount'] + scoped['summary']['unmappedAlertCount'], 2)

    def test_multiple_criteria_do_not_multiply_alert_or_instance_count(self):
        run = mapped_working()
        w = run['criteriaWorkflow']
        second = copy.deepcopy(w['criteria'][0]); second['id'] = 'C2'
        w['criteria'].append(second)
        w['plan']['cases'][0]['criterionIds'].append('C2')
        w['alertMappings'].append(dict(findingId='observed', criterionId='C2', rationale='Same disclosure violates this requirement'))
        approve(run)
        row = observed(); row['instanceCount'] = 3
        alerts, scoped, _ = alert_projection(run, [row])
        self.assertEqual(alerts['summary']['alertCount'], 1)
        self.assertEqual(scoped['summary']['mappingCount'], 2)
        self.assertEqual(alerts['summary']['occurrenceCount'], 3)
        self.assertEqual(scoped['alerts'], alerts['alerts'])

    def test_controls_and_bare_uncertainty_only_enter_run(self):
        rows = [dict(findingId='control', recordKind='control-observation', basis='Owner request succeeded'),
            dict(findingId='unknown', recordKind='test-uncertainty', basis='Fixture unavailable')]
        with tempfile.TemporaryDirectory() as td:
            report = publish_reports(Path(td)/'reports', working(), rows)
            self.assertEqual(report['alertSummary']['alertCount'], 0)
            self.assertEqual(len(report['controlObservations']), 2)
            self.assertEqual(json.loads((Path(td)/'reports/SCOPE_ALERTS.json').read_text())['alerts'], [])

    def test_stale_historical_associations_are_removed(self):
        row = observed()
        row.update(criterionIds=['historical'], criterionMappings=[{'criterionId': 'historical'}],
            unmappedReason='Old unmapped reason')
        alerts, scoped, _ = alert_projection(mapped_working(), [row])
        self.assertNotIn('criterionIds', alerts['alerts'][0])
        self.assertNotIn('unmappedReason', alerts['alerts'][0])
        self.assertEqual(scoped['alerts'][0]['criterionMappings'][0]['criterionId'], 'C1')

    def test_mappings_cannot_claim_criteria_without_an_approved_plan(self):
        for mode in ('absent', 'stale'):
            run = mapped_working()
            if mode == 'absent': run['criteriaWorkflow']['approvals'] = []
            else: run['criteriaWorkflow']['criteria'][0]['rawText'] = 'Changed requirement'
            with self.subTest(mode=mode), self.assertRaises(ValueError):
                alert_projection(run, [observed()])

    def test_progress_without_mapping_is_allowed_before_plan_approval(self):
        run = fixed_working('matched'); run['criteriaWorkflow']['approvals'] = []
        with tempfile.TemporaryDirectory() as td:
            report = publish_reports(Path(td)/'reports', run, [observed()])
            self.assertEqual(report['assessmentStatus'], 'awaiting_plan_approval')

    def test_delivery_projection_rejects_mappings_to_excluded_rows(self):
        script = Path(__file__).resolve().parents[3] / 'scripts/build_delivery_projection.py'
        spec = importlib.util.spec_from_file_location('build_delivery_projection_test', script)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        run = fixed_working(selected=False)
        native = [{'id': '1', 'pluginId': '1001'}]
        cases = [
            {'nativeRules': [{'pluginId': '1001', 'criterionIds': ['SEC-A01-01'], 'rationale': 'invalid'}]},
            {'nativeRules': [{'pluginId': '1001', 'unmappedReason': 'not mapped'}],
             'observedAlerts': [{'findingId': 'O1', 'criterionIds': ['SEC-A01-01']}]},
        ]
        for review_spec in cases:
            with self.subTest(review_spec=review_spec), self.assertRaisesRegex(ValueError, 'excluded from this run'):
                module.validate_review(run, native, review_spec)

    def test_source_only_or_direct_alert_provenance_is_rejected(self):
        for factory in (native, observed):
            for provenance in ({'transport': 'direct'}, {'source': 'source-review'}, 'zap-native'):
                row = factory(); row['provenance'] = provenance
                with self.subTest(kind=row['recordKind'], provenance=provenance), self.assertRaises(ValueError):
                    alert_projection(working(), [row])

    def test_observed_alert_cannot_claim_native_identity_or_ratings(self):
        for update in ({'nativeAlertId': 'n1'}, {'nativeRuleId': '40018'},
                {'nativeId': 'n1'}, {'severity': 'High'}, {'confidence': 'High'}):
            row = observed(); row.update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                alert_projection(working(), [row])
        row = observed(); row.update(severity='High', severitySource='tester')
        self.assertEqual(alert_projection(working(), [row])[0]['summary']['observedAlertCount'], 1)

    def test_native_identity_requires_scalar_detector_and_optional_real_alert_id(self):
        for update in ({'nativeRuleId': []}, {'nativeRuleId': True}, {'nativeRuleId': ' '},
                {'nativeAlertId': ''}, {'nativeAlertId': {}}, {'provenance': {'transport': 'zap-proxy'}}):
            row = native(); row.update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                alert_projection(working(), [row])
        row = native(); row.pop('nativeAlertId')
        self.assertEqual(alert_projection(working(), [row])[0]['summary']['nativeAlertCount'], 1)

    def test_observed_operation_must_retain_zap_provenance(self):
        for provenance in (None, 'zap-proxy', {'transport': 'direct'}):
            run = working(); run['operations'][0]['provenance'] = provenance
            with self.subTest(provenance=provenance), self.assertRaises(ValueError):
                alert_projection(run, [observed()])

    def test_whitespace_is_not_signal_or_mapping_rationale(self):
        for field in ('source', 'securitySignal', 'expectedBehavior', 'observedBehavior', 'expectationBasis'):
            row = observed(); row[field] = ' '
            with self.subTest(field=field), self.assertRaises(ValueError):
                alert_projection(working(), [row])
        run = mapped_working(); run['criteriaWorkflow']['alertMappings'][0]['rationale'] = ' '
        with self.assertRaises(ValueError): alert_projection(run, [observed()])

    def test_inconsistent_or_invalid_occurrence_counts_rejected(self):
        for update in ({'instanceCount': 2}, {'instances': []}, {'instances': 'not-a-list'},
                {'instanceCount': True}, {'instanceCount': -1}, {'instanceCount': 1.5}):
            row = native(); row.update(update)
            with self.subTest(update=update), self.assertRaises(ValueError):
                alert_projection(working(), [row])

    def test_exact_subset_counts_and_context_are_validated(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/'reports'
            publish_reports(out, mapped_working(), [observed(), native()])
            bundle = [json.loads((out/name).read_text()) for name in ('RUN.json', 'ALERTS.json', 'SCOPE_ALERTS.json')]
            mutations = [lambda r,a,s: s['alerts'].clear(),
                lambda r,a,s: a['summary'].update(nativeAlertCount=9),
                lambda r,a,s: s['summary'].update(observedAlertCount=9),
                lambda r,a,s: r['alertSummary'].update(mappingCount=9),
                lambda r,a,s: s.update(assessmentStatus='invented-status'),
                lambda r,a,s: a['alerts'][0]['operationIds'].append('missing')]
            for index, mutate in enumerate(mutations):
                changed = copy.deepcopy(bundle); mutate(*changed)
                with self.subTest(index=index), self.assertRaises(ValueError): validate_report_bundle(*changed)

    def test_original_criterion_mapping_details_cannot_be_rewritten(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/'reports'; publish_reports(out, mapped_working(), [observed()])
            bundle = [json.loads((out/name).read_text()) for name in ('RUN.json', 'ALERTS.json', 'SCOPE_ALERTS.json')]
            for report in bundle[1:]: report['alerts'][0]['criterionMappings'][0]['rawText'] = 'Invented requirement'
            with self.assertRaises(ValueError): validate_report_bundle(*bundle)

    def test_redaction_cannot_collapse_alert_identities(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/'reports'
            with self.assertRaises(ValueError):
                publish_reports(out, working(), [observed('secret-one'), observed('secret-two')],
                    secrets=('secret-one', 'secret-two'))
            self.assertFalse(out.exists())

    def test_redaction_cannot_remove_zap_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/'reports'
            with self.assertRaises(ValueError):
                publish_reports(out, working(), [observed()], secrets=('zap-proxy',))
            self.assertFalse(out.exists())

    def test_projection_never_modifies_private_inputs(self):
        run, rows = mapped_working(), [observed(), native()]
        original = copy.deepcopy((run, rows))
        with tempfile.TemporaryDirectory() as td: publish_reports(Path(td)/'reports', run, rows)
        self.assertEqual((run, rows), original)

    def test_projection_redacts_opaque_setup_and_session_credentials(self):
        run = working()
        run['fixtureAccess'] = {'setupToken': 'opaque-setup-value',
            'nested': [{'session_token': 'opaque-session-value'}],
            'caseId': 'issueAccessToken:CUSTOMER', 'basis': 'password validation'}
        original = copy.deepcopy(run)
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)/'reports'
            report = publish_reports(out, run, [])
            self.assertEqual(report['fixtureAccess']['setupToken'], '[private]')
            self.assertEqual(report['fixtureAccess']['nested'][0]['session_token'], '[private]')
            self.assertEqual(report['fixtureAccess']['caseId'], 'issueAccessToken:CUSTOMER')
            self.assertEqual(report['fixtureAccess']['basis'], 'password validation')
            for path in out.iterdir():
                self.assertNotIn('opaque-setup-value', path.read_text())
                self.assertNotIn('opaque-session-value', path.read_text())
        self.assertEqual(run, original)

    def test_redaction_cannot_remove_resource_resolution_or_containment_proof(self):
        for kind in ('resource', 'resolution', 'containment'):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as td:
                run = working(); w = run['criteriaWorkflow']
                context = dict(w['context'], objectRef='independent-object')
                operation = dict(id='readback', status='completed', coverageContext=context)
                if kind == 'resource':
                    run['resources'] = [{'id': 'scanner'}]
                    operation['raw'] = dict(resourceId='scanner', status='stopped', producerActive=False)
                    w['resourceReview']['resources'] = [dict(id='scanner', status='stopped',
                        basis='Native state read', operationId='readback', resultPath='/raw')]
                else:
                    run['pendingEffects'] = [dict(actionId='unknown', caseId='other-case', coverageContext=context)]
                    operation['raw'] = dict(actionId='unknown', caseId='other-case')
                    if kind == 'resolution':
                        operation['raw']['resolved'] = True
                        w['resolutions'] = [dict(actionId='unknown', resolutionOperationId='readback',
                            resultPath='/raw', basis='Exact outcome readback')]
                    else:
                        operation['raw']['contained'] = True
                        w['containedEffects'] = [dict(actionId='unknown', lastKnownState='ACK unavailable',
                            unknownImpact='Unknown final state', unavailableReaderReason='Reader unavailable',
                            reopenCondition='Reader restored', noReplay=True, operationId='readback', resultPath='/raw')]
                run['operations'].append(operation)
                out = Path(td)/'reports'
                with self.assertRaises(ValueError): publish_reports(out, run, [], finalize=True)
                self.assertFalse(out.exists())

                # Sanitized semantic readback retains the same legitimate proof.
                operation['readback'] = operation.pop('raw')
                rows = (w['resourceReview']['resources'] if kind == 'resource' else
                        w['resolutions'] if kind == 'resolution' else w['containedEffects'])
                rows[0]['resultPath'] = '/readback'
                self.assertEqual(publish_reports(out, run, [], finalize=True)['assessmentStatus'], 'completed')

