"""Synthetic finite native allocation controls, exercised through the v2 reviewer."""
import copy
import unittest

from zap_assessment.contracts import digest
from zap_assessment.criteria_workflow import approval_digest, review_workflow
from zap_assessment.question_evidence import bound_context, resolve_question_evidence
from test_criteria_workflow import working, approve, limitation


def mapping(op, unit):
    return dict(operationId=op['id'], observationUnits=[unit], resultPath='/readback',
                context=copy.deepcopy(op['coverageContext']), provenance=copy.deepcopy(op['provenance']),
                receiptDigest=digest(op['zapMessageReceipt']), captureDigest=digest(op['zapCapture']))


def native(oid, route, request_ref, message_id, context):
    ctx = dict(context, origin='http://scanner-alias.invalid:8081', route=route, requestRef=request_ref)
    identity = dict(scannerResourceId='synthetic-scanner', sessionId='synthetic-session', messageId=message_id)
    hashes = dict(requestSha256=digest([oid, 'request']), responseSha256=digest([oid, 'response']))
    return dict(id=oid, caseId='T1', effect='read', status='completed', coverageContext=ctx,
        readback={'observed': oid}, provenance=dict(identity, transport='zap-native', rawRef='private:' + oid),
        zapCapture=dict(identity, **hashes), zapMessageReceipt=dict(identity, **hashes, caseId='T1',
            actorRef=ctx['actorRef'], fixtureRef=ctx['fixtureRef'], requestRef=request_ref, resultPath='/zapCapture'))


def allocated_run(pair=True):
    run = working(None); w = run['criteriaWorkflow']; case = w['plan']['cases'][0]
    case['coverageContext'].update(origin='http://approved.invalid:8081', build='synthetic-build',
        actorRef='anonymous', fixtureRef='fixture-one', method='GET')
    case['requireZapMessageEvidence'] = True
    approve(run)
    ops = [native('directory', '/public/', 'request-directory', '11', case['coverageContext'])]
    if pair:
        ops.append(native('asset', '/public/asset.bin', 'request-asset', '12', case['coverageContext']))
    run['operations'] = ops
    rows = [mapping(op, unit) for op, unit in zip(ops, case['requiredEvidence'])]
    run['evidenceAllocations'] = [dict(version=1, assessmentId=run['assessmentId'], caseId='T1',
        criteriaDigest=approval_digest(w, 'criteria'), planDigest=approval_digest(w, 'plan'),
        workflowContext=copy.deepcopy(w['context']), baseContext=bound_context(case, question=True),
        requiredEvidence=copy.deepcopy(case['requiredEvidence']), basis='Synthetic coordinator reviewed finite pair',
        authorityRefs=['synthetic:existing-authority'], deploymentRefs=['synthetic:same-mount'],
        originBindings=[], operations=rows)]
    run['evidenceAllocations'][0]['originBindings'] = [{'from':case['coverageContext']['origin'], 'to':ops[0]['coverageContext']['origin']}]
    w['caseResults'] = [dict(caseId='T1', outcome='matched', basis='Synthetic independently interpreted facts',
        evidenceLinks=[dict(operationId=row['operationId'], observationUnits=row['observationUnits'],
            resultPath=row['resultPath'], context=copy.deepcopy(row['context']), role='support',
            resultRead=True, basis='Synthetic semantic read') for row in rows])]
    return run


def case_result(run):
    return review_workflow(run)['caseResults'][0]


class EvidenceAllocationTests(unittest.TestCase):
    def test_single_unit_admitted_original_plan_unchanged_case_pending(self):
        run = allocated_run(False); before = copy.deepcopy(run)
        result = case_result(run)
        self.assertEqual(result['evidence']['supportedUnits'], ['owner-control'])
        self.assertEqual(result['evidence']['missingUnits'], ['denial'])
        self.assertIsNone(result['outcome'])
        self.assertEqual(run, before)
        self.assertTrue(all(review_workflow(run)['approvalStatus'].values()))

    def test_pair_exact_native_receipts_union_distinct_requests(self):
        run = allocated_run(); before = copy.deepcopy(run)
        result = case_result(run)
        self.assertEqual(result['outcome'], 'matched')
        self.assertEqual(result['evidence']['supportedUnits'], ['denial', 'owner-control'])
        self.assertFalse(result['evidence']['contextDiagnostics'])
        self.assertEqual(run, before)
        self.assertTrue(review_workflow(run)['eligibleForCompletion'])
        # Compatibility/origin equality behavior for old callers is unchanged.
        del run['evidenceAllocations']
        self.assertFalse(case_result(run)['evidence']['supportedUnits'])
        self.assertIsNone(case_result(run)['outcome'])

    def test_pending_observation_reviews_units_and_keeps_limitation(self):
        run = allocated_run(False)
        run['criteriaWorkflow']['caseResults'][0].update(outcome=None, limitation=limitation())
        result = case_result(run)
        self.assertEqual(result['evidence']['supportedUnits'], ['owner-control'])
        self.assertIsNone(result['outcome'])
        self.assertIn('unresolved-evidence-limitation', result['diagnostics'])
        self.assertIn('missing-unit:denial', result['diagnostics'])
        self.assertFalse(review_workflow(run)['eligibleForCompletion'])

    def test_stale_global_case_context_and_required_unit_bindings_fail_closed(self):
        for key, value in [('assessmentId', 'other'), ('caseId', 'unknown'), ('criteriaDigest', '0'*64),
                           ('planDigest', '0'*64), ('workflowContext', {'product':'foreign'}),
                           ('baseContext', {}), ('requiredEvidence', ['invented'])]:
            with self.subTest(key=key):
                run = allocated_run(); run['evidenceAllocations'][0][key] = value
                with self.assertRaises(ValueError): review_workflow(run)
        run = allocated_run(); run['criteriaWorkflow']['plan']['cases'][0]['objective'] = 'changed'
        with self.assertRaises(ValueError): review_workflow(run)

    def test_workflow_and_fixed_dimensions_remain_exact_even_if_mapping_rewritten(self):
        for dimension in ('product', 'environment', 'build', 'actorRef', 'fixtureRef', 'objective'):
            with self.subTest(dimension=dimension):
                run = allocated_run()
                for i, op in enumerate(run['operations']):
                    op['coverageContext'][dimension] = 'wrong'
                    if dimension in ('actorRef', 'fixtureRef'):
                        op['zapMessageReceipt'][dimension] = 'wrong'
                    run['evidenceAllocations'][0]['operations'][i] = mapping(op, ['owner-control', 'denial'][i])
                with self.assertRaises(ValueError): review_workflow(run)

    def test_exact_native_identity_hashes_and_actual_context_are_bound(self):
        mutations = [lambda op: op['coverageContext'].update(origin='http://unlisted.invalid:8081'),
            lambda op: op['coverageContext'].update(build='changed'),
            lambda op: op['coverageContext'].update(actorRef='different'),
            lambda op: op['provenance'].update(messageId='999'),
            lambda op: op['zapMessageReceipt'].update(responseSha256='0'*64),
            lambda op: op['zapCapture'].update(requestSha256='1'*64),
            lambda op: op.update(caseId='other')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                run = allocated_run(); mutate(run['operations'][0])
                with self.assertRaises(ValueError): review_workflow(run)

    def test_pair_cannot_mix_scanners_sessions_or_unbound_actors(self):
        for dimension in ('scannerResourceId', 'sessionId', 'actorRef', 'fixtureRef', 'build', 'method', 'origin'):
            with self.subTest(dimension=dimension):
                run = allocated_run(); op = run['operations'][1]
                if dimension in ('scannerResourceId', 'sessionId'):
                    for key in ('provenance', 'zapCapture', 'zapMessageReceipt'):
                        op[key][dimension] = 'different'
                else:
                    # Remove case binding too, isolating pair invariant checks.
                    run['criteriaWorkflow']['plan']['cases'][0]['coverageContext'].pop(dimension, None)
                    op['coverageContext'][dimension] = 'different'
                    if dimension in ('actorRef', 'fixtureRef'):
                        op['zapMessageReceipt'][dimension] = 'different'
                    approve(run)
                    a = run['evidenceAllocations'][0]
                    a['baseContext'] = bound_context(run['criteriaWorkflow']['plan']['cases'][0], question=True)
                    a['planDigest'] = approval_digest(run['criteriaWorkflow'], 'plan')
                run['evidenceAllocations'][0]['operations'][1] = mapping(op, 'denial')
                with self.assertRaises(ValueError): review_workflow(run)

    def test_unlisted_operation_unit_pointer_and_context_never_supply_units(self):
        for field, value in [('operationId', 'extra'), ('observationUnits', ['unlisted-unit']),
                             ('resultPath', '/other'), ('context', {})]:
            with self.subTest(field=field):
                run = allocated_run(); op = copy.deepcopy(run['operations'][0]); op['id'] = 'extra'
                run['operations'].append(op); run['operations'][0]['other'] = {'observed':True}
                run['criteriaWorkflow']['caseResults'][0]['evidenceLinks'][0][field] = value
                result = case_result(run)
                self.assertIsNone(result['outcome'])
                self.assertNotIn('owner-control', result['evidence']['supportedUnits'])
                self.assertTrue(result['evidence']['contextDiagnostics'])

    def test_pending_effects_cannot_be_cleared_by_allocation(self):
        run = allocated_run(); run['actionHistory'] = [dict(actionId='unknown-write', caseId='T1',
            effect='mutation', state='intent', coverageContext=run['operations'][0]['coverageContext'])]
        result = case_result(run)
        self.assertEqual(result['evidence']['supportedUnits'], [])
        self.assertEqual(result['evidence']['unresolvedEffectIds'], ['unknown-write'])
        self.assertIsNone(result['outcome'])

    def test_missing_or_blank_evidence_refs_and_duplicate_allocations_rejected(self):
        for key in ('basis', 'authorityRefs', 'deploymentRefs'):
            with self.subTest(key=key):
                run = allocated_run(); run['evidenceAllocations'][0].pop(key)
                with self.assertRaises(ValueError): review_workflow(run)
        run = allocated_run(); run['evidenceAllocations'].append(copy.deepcopy(run['evidenceAllocations'][0]))
        with self.assertRaises(ValueError): review_workflow(run)

    def test_origin_mapping_is_exact_and_preserves_scheme_and_port(self):
        for origin in ('https://scanner-alias.invalid:8081', 'http://scanner-alias.invalid:8082',
                       'http://scanner-alias.invalid:8081/path', 'http://user@scanner-alias.invalid:8081'):
            with self.subTest(origin=origin):
                run = allocated_run()
                run['evidenceAllocations'][0]['originBindings'][0]['to'] = origin
                with self.assertRaises(ValueError): review_workflow(run)

    def test_resolver_requires_current_workflow_to_use_allocation(self):
        run = allocated_run(); w = run['criteriaWorkflow']; q = dict(w['plan']['cases'][0], caseId='T1')
        with self.assertRaises(ValueError):
            resolve_question_evidence(q, w['caseResults'][0], run['operations'], allocation=run['evidenceAllocations'][0])
        result = resolve_question_evidence(q, w['caseResults'][0], run['operations'],
            allocation=run['evidenceAllocations'][0], workflow=w, assessment_id=run['assessmentId'])
        self.assertFalse(result['missingUnits'])
