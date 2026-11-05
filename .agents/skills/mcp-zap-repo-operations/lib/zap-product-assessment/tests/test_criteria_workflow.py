import copy
import multiprocessing
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from zap_assessment.criteria_delegation import Coordinator, coordinator_lock, make_packet, merge_result
from zap_assessment.criteria_workflow import approval_digest, review_workflow


def working(outcome="matched"):
    context = {"product":"example", "environment":"test"}
    case = dict(id="T1", criterionIds=["C1"], objective="owner boundary", expectedBehavior="denied",
        expectationBasis="expert rule", requiredEvidence=["owner-control", "denial"],
        coverageContext=dict(context, objective="owner boundary"), effects=["read"], resourceIds=[], allowedLimitations=["method_boundary", "capability"])
    cw = dict(version=2, context=context, criteriaRevision="C-1", planRevision="P-1",
        criteria=[dict(id="C1", rawText="Owner access only", source="expert-message", requirement="Owner only",
          oracle="Owner succeeds, other actor denied", applicability="applicable", caseIds=["T1"], stoppingRule="all_cases")],
        plan=dict(cases=[case], authority=dict(source="approved-plan", target="https://example.test", allowedEffects=["read"])),
        approvals=[], caseResults=[], resourceReview=dict(reviewed=True,basis="No resources created",resources=[]))
    run = dict(assessmentId="A1", criteriaWorkflow=cw, operations=[])
    if outcome:
        run["operations"] = [dict(id="O1", status="completed", coverageContext=case["coverageContext"],
            provenance={"transport":"zap-proxy"}, readback={"denied":True})]
        cw["caseResults"] = [dict(caseId="T1", outcome=outcome, basis="Read exact response and positive control",
            evidenceLinks=[dict(operationId="O1", resultPath="/readback", observationUnits=case["requiredEvidence"],
             resultRead=True, basis="Verified facts", context=case["coverageContext"], role="support")])]
    approve(run)
    return run


def approve(run):
    w=run["criteriaWorkflow"]
    w["approvals"]=[dict(kind=k, revision=w[k+"Revision"], digest=approval_digest(w,k),source="user-approved-"+k) for k in ("criteria","plan")]


def limitation():
    return dict(reason="method_boundary",basis="Dynamic method cannot inspect this property",missingEvidence=["denial"],
        attemptedAlternatives=[], unavailableAlternatives=["Source review outside approved method"],remainingFeasibleActions=[],reopenCondition="Source review assigned")


class CriteriaTests(unittest.TestCase):
    def test_met_unmet_and_pending(self):
        for outcome,verdict in (("matched","met"),("violated","unmet"),(None,None)):
            with self.subTest(outcome=outcome):
                r=review_workflow(working(outcome))
                self.assertEqual(r["criterionResults"][0]["verdict"],verdict)
                self.assertEqual(r["eligibleForCompletion"],outcome is not None)
    def test_stale_approval_and_legacy_inventory(self):
        run=working();run["responsibilityInventory"]={"cases":[{"caseId":"unrelated"}]}
        self.assertTrue(review_workflow(run)["eligibleForCompletion"])
        run["criteriaWorkflow"]["criteria"][0]["oracle"]="different"
        self.assertFalse(review_workflow(run)["eligibleForCompletion"])
    def test_missing_and_wrong_context_evidence(self):
        run=working();run["criteriaWorkflow"]["caseResults"][0]["evidenceLinks"][0]["observationUnits"]=["denial"]
        self.assertFalse(review_workflow(run)["eligibleForCompletion"])
        run=working();run["operations"][0]["coverageContext"]={"product":"other","environment":"test"}
        self.assertFalse(review_workflow(run)["eligibleForCompletion"])

    def test_retained_build_evidence_requires_explicit_compatibility(self):
        run = working()
        case = run['criteriaWorkflow']['plan']['cases'][0]
        case['coverageContext'] = dict(case['coverageContext'], build='current-build')
        run['operations'][0]['coverageContext'] = dict(case['coverageContext'], build='retained-build')
        link = run['criteriaWorkflow']['caseResults'][0]['evidenceLinks'][0]
        link['context'] = dict(run['operations'][0]['coverageContext'])
        approve(run)
        self.assertFalse(review_workflow(run)['eligibleForCompletion'])
        link['compatibility'] = dict(basis='Reviewed unchanged owner boundary across these builds',
            dimensions={'build': {'from': 'retained-build', 'to': 'current-build'}}, operationIds=['O1'])
        self.assertTrue(review_workflow(run)['eligibleForCompletion'])
        self.assertEqual(run['operations'][0]['coverageContext']['build'], 'retained-build')
        for placeholder in ('unknown', 'unresolved', 'product-defined'):
            with self.subTest(placeholder=placeholder):
                changed = copy.deepcopy(run)
                changed['operations'][0]['coverageContext']['build'] = placeholder
                changed_link = changed['criteriaWorkflow']['caseResults'][0]['evidenceLinks'][0]
                changed_link['context']['build'] = placeholder
                changed_link['compatibility']['dimensions']['build']['from'] = placeholder
                self.assertFalse(review_workflow(changed)['eligibleForCompletion'])

    def test_compatibility_cannot_invent_operation_context_or_change_origin(self):
        run = working()
        # A caller-written link cannot fill an absent operation dimension.
        run['operations'][0]['coverageContext'] = dict(run['operations'][0]['coverageContext'])
        run['operations'][0]['coverageContext'].pop('objective')
        with self.assertRaises(ValueError): review_workflow(run)
        run = working()
        case = run['criteriaWorkflow']['plan']['cases'][0]
        case['coverageContext'] = dict(case['coverageContext'], origin='https://current.test')
        run['operations'][0]['coverageContext'] = dict(case['coverageContext'], origin='https://foreign.test')
        link = run['criteriaWorkflow']['caseResults'][0]['evidenceLinks'][0]
        link['context'] = dict(run['operations'][0]['coverageContext'])
        link['compatibility'] = dict(basis='Caller claims origins equivalent',
            dimensions={'origin': {'from': 'https://foreign.test', 'to': 'https://current.test'}}, operationIds=['O1'])
        approve(run)
        with self.assertRaises(ValueError): review_workflow(run)

    def test_compatibility_cannot_replace_assessment_identity(self):
        for dimension in ('product', 'environment', 'build'):
            with self.subTest(dimension=dimension):
                run = working(); w = run['criteriaWorkflow']
                if dimension == 'build':
                    # An assessment-wide build is immutable too; a build bound
                    # only on a case may use the finite mapping tested above.
                    w['context']['build'] = 'assessment-build'
                    w['plan']['cases'][0]['coverageContext'] = dict(
                        w['plan']['cases'][0]['coverageContext'], build='assessment-build')
                actual = dict(w['plan']['cases'][0]['coverageContext'])
                actual[dimension] = 'foreign-' + dimension
                run['operations'][0]['coverageContext'] = actual
                link = w['caseResults'][0]['evidenceLinks'][0]
                link['context'] = dict(actual)
                link['compatibility'] = dict(basis='Caller claims foreign identity equivalent',
                    dimensions={dimension: {'from': actual[dimension], 'to': w['context'][dimension]}},
                    operationIds=['O1'])
                approve(run)
                with self.assertRaises(ValueError): review_workflow(run)

    def test_method_limit_never_completes_applicable_criterion(self):
        run=working(None);run["criteriaWorkflow"]["caseResults"]=[dict(caseId="T1",outcome="not_evaluable",basis="method limit",limitation=limitation())]
        review = review_workflow(run)
        self.assertIsNone(review["criterionResults"][0]["verdict"])
        self.assertFalse(review["eligibleForCompletion"])
        self.assertEqual(review['criterionCounts']['pending'], 1)
        self.assertEqual(review['limitations'][0]['reason'], 'method_boundary')
        self.assertTrue(review['nextWork'])
        run["criteriaWorkflow"]["caseResults"][0]["limitation"]["remainingFeasibleActions"]=["read existing result"]
        self.assertFalse(review_workflow(run)["eligibleForCompletion"])

    def test_pending_limits_and_legacy_claims_cannot_finalize(self):
        from zap_assessment.criteria_reporting import CriteriaFinalizationError, publish_reports
        for outcome in (None, 'not_evaluable'):
            for reason in ('method_boundary', 'access', 'policy', 'capability', 'environment', 'budget_exhausted'):
                with self.subTest(outcome=outcome, reason=reason):
                    run = working(None); w = run['criteriaWorkflow']
                    w['plan']['cases'][0]['allowedLimitations'] = [reason]; approve(run)
                    limit = dict(limitation(), reason=reason)
                    w['caseResults'] = [dict(caseId='T1', outcome=outcome, basis='Unresolved evidence', limitation=limit)]
                    w['criterionResults'] = [dict(criterionId='C1', verdict='not_evaluable', basis='Old completion claim')]
                    review = review_workflow(run)
                    self.assertIsNone(review['criterionResults'][0]['verdict'])
                    self.assertFalse(review['eligibleForCompletion'])
                    with tempfile.TemporaryDirectory() as directory:
                        with self.assertRaises(CriteriaFinalizationError):
                            publish_reports(Path(directory)/'reports', run, {'alerts': []}, finalize=True)
                        self.assertFalse((Path(directory)/'reports').exists())

    def test_only_product_grounded_not_applicable_is_terminal_not_evaluable(self):
        run = working(None); w = run['criteriaWorkflow']
        w['criteria'][0].update(applicability='not_applicable', applicabilityBasis='No named component in this product', caseIds=[])
        w['plan']['cases'] = []
        limit = dict(limitation(), reason='not_applicable', basis='Named component absent')
        w['criterionResults'] = [dict(criterionId='C1', verdict='not_evaluable', limitation=limit)]
        approve(run)
        review = review_workflow(run)
        self.assertTrue(review['eligibleForCompletion'])
        self.assertEqual(review['criterionCounts']['not_evaluable'], 1)
        self.assertEqual(review['criterionCounts']['notApplicable'], 1)
        w['criteria'][0].pop('applicabilityBasis')
        with self.assertRaises(ValueError): review_workflow(run)
    def test_missing_resources_unknown_effect_and_user_stop(self):
        for field,value in (("resources",[{"id":"scanner"}]),("pendingEffects",[{"actionId":"unknown","caseId":"T1"}])):
            run=working();run[field]=value
            self.assertFalse(review_workflow(run)["eligibleForCompletion"])
        run=working();run["criteriaWorkflow"]["userRequest"]={"kind":"stop","source":"user stop"}
        self.assertEqual(review_workflow(run)["assessmentStatus"],"stopped_by_user")
    def test_counterexample_does_not_waive_other_criterion(self):
        run=working("violated");w=run["criteriaWorkflow"]
        c=copy.deepcopy(w["plan"]["cases"][0]);c["id"]="T2";w["plan"]["cases"].append(c)
        w["criteria"][0].update(caseIds=["T1","T2"],stoppingRule="counterexample");approve(run)
        self.assertTrue(review_workflow(run)["eligibleForCompletion"])
        w["criteria"][0]["stoppingRule"]="all_cases";approve(run)
        self.assertFalse(review_workflow(run)["eligibleForCompletion"])
    def test_invalid_link_and_conflicting_claim(self):
        run=working();run["criteriaWorkflow"]["caseResults"][0]["evidenceLinks"][0]["resultPath"]="/missing"
        with self.assertRaises(ValueError):review_workflow(run)
        run=working();run["criteriaWorkflow"]["criterionResults"]=[dict(criterionId="C1",verdict="unmet")]
        self.assertFalse(review_workflow(run)["eligibleForCompletion"])

    def test_approval_content_binding_preserves_the_two_gates(self):
        for field in ('rawText', 'source', 'requirement', 'oracle'):
            run = working()
            run['criteriaWorkflow']['criteria'][0][field] += ' changed'
            self.assertEqual(review_workflow(run)['approvalStatus'], {'criteria': False, 'plan': False})
        run = working()
        run['criteriaWorkflow']['plan']['authority']['target'] += '/changed'
        self.assertEqual(review_workflow(run)['approvalStatus'], {'criteria': True, 'plan': False})

    def test_counterexample_removes_feasible_work_only_for_waived_case(self):
        run = working('violated'); w = run['criteriaWorkflow']
        second = copy.deepcopy(w['plan']['cases'][0]); second['id'] = 'T2'
        w['plan']['cases'].append(second)
        w['criteria'][0].update(caseIds=['T1', 'T2'], stoppingRule='counterexample')
        limit = limitation(); limit['remainingFeasibleActions'] = ['repair available reader']
        w['caseResults'].append(dict(caseId='T2', outcome='not_evaluable', basis='reader failed', limitation=limit))
        approve(run)
        review = review_workflow(run)
        self.assertTrue(review['eligibleForCompletion'])
        self.assertEqual(review['nextWork'], [])
        second['criterionIds'].append('C2')
        w['criteria'].append(dict(w['criteria'][0], id='C2', caseIds=['T2'], stoppingRule='all_cases'))
        approve(run)
        review = review_workflow(run)
        self.assertFalse(review['eligibleForCompletion'])
        self.assertIn('repair available reader', [r['action'] for r in review['nextWork']])

    def test_case_action_descriptors_must_bind_the_approved_case_effect(self):
        for action in (dict(id='A1', caseId='other', effect='read'),
                       dict(id='A1', caseId='T1', effect='mutation'),
                       dict(id='A1', caseId='T1', effect='read', readbackOf='')):
            run = working(); run['criteriaWorkflow']['plan']['cases'][0]['actions'] = [action]
            approve(run)
            with self.assertRaises(ValueError): review_workflow(run)

    def test_unknown_applicability_requires_a_product_fact_before_final_verdict(self):
        for outcome in ('matched', 'violated'):
            run = working(outcome)
            run['criteriaWorkflow']['criteria'][0]['applicability'] = 'unknown'; approve(run)
            review = review_workflow(run)
            self.assertIsNone(review['criterionResults'][0]['verdict'])
            self.assertIn({'criterionId': 'C1', 'action': 'resolve-product-applicability'}, review['nextWork'])

    def test_resource_readback_must_bind_the_workflow_context(self):
        run = working(); w = run['criteriaWorkflow']
        run['resources'] = [{'id': 'scanner'}]
        run['operations'].append(dict(id='resource', status='completed', coverageContext=dict(w['context']),
            readback={'resourceId': 'scanner', 'status': 'stopped', 'producerActive': False}))
        w['resourceReview']['resources'] = [dict(id='scanner', basis='Native state read', status='stopped',
            operationId='resource', resultPath='/readback')]
        self.assertTrue(review_workflow(run)['eligibleForCompletion'])
        run['operations'][-1]['coverageContext']['product'] = 'other'
        with self.assertRaises(ValueError): review_workflow(run)

    def test_global_scanner_requires_disposition_and_explicit_producer_stop(self):
        run = working(); w = run['criteriaWorkflow']
        w['plan']['resourceIds'] = ['scanner']; approve(run)
        review = review_workflow(run)
        self.assertFalse(review['eligibleForCompletion'])
        self.assertIn('unreviewed-resources:scanner', review['diagnostics'])
        run['operations'].append(dict(id='resource', status='completed', coverageContext=dict(w['context']),
            readback={'resourceId': 'scanner', 'status': 'stopped'}))
        w['resourceReview']['resources'] = [dict(id='scanner', basis='Native state read', status='stopped',
            operationId='resource', resultPath='/readback')]
        for active in (None, True, False):
            run['operations'][-1]['readback']['producerActive'] = active
            self.assertEqual(review_workflow(run)['eligibleForCompletion'], active is False)

    def test_containment_readback_must_bind_original_case_and_context(self):
        run = working(); w = run['criteriaWorkflow']
        context = dict(w['context'], objectRef='independent-object')
        run['pendingEffects'] = [dict(actionId='unknown', caseId='other-case', coverageContext=context)]
        run['operations'].append(dict(id='containment', status='completed', coverageContext=context,
            readback={'actionId': 'unknown', 'caseId': 'other-case', 'contained': True}))
        w['containedEffects'] = [dict(actionId='unknown', lastKnownState='ACK unavailable',
            unknownImpact='Unknown final state', unavailableReaderReason='Reader unavailable under plan',
            reopenCondition='Native reader restored', noReplay=True, operationId='containment', resultPath='/readback')]
        self.assertTrue(review_workflow(run)['eligibleForCompletion'])
        run['operations'][-1]['readback']['caseId'] = 'foreign-case'
        with self.assertRaises(ValueError): review_workflow(run)
        run['operations'][-1]['readback']['caseId'] = 'other-case'
        run['operations'][-1]['coverageContext'] = dict(context, objectRef='foreign-object')
        with self.assertRaises(ValueError): review_workflow(run)


class CoordinatorRecoveryTests(unittest.TestCase):
    def prepare(self, directory, assessment_id='A1'):
        run = working(); run['assessmentId'] = assessment_id
        w = run['criteriaWorkflow']; w['plan']['delegation'] = {'allowed': True}
        w['plan']['resourceIds'] = ['shared-scanner']
        w['plan']['cases'][0]['actions'] = [dict(id='read-1', caseId='T1', effect='read')]
        approve(run)
        run['coordinatorState'] = {'directory': str(Path(directory).absolute()), 'assessmentId': assessment_id}
        return run, make_packet(run, 'W1', ['T1'], 'worker'), Coordinator(directory, assessment_id)

    def terminal(self, run, packet, **context):
        run['operations'].append(dict(id='terminal', reconciledActionId='read-1', effectStatus='terminal',
            status='completed', context={'assessmentId': run['assessmentId']},
            coverageContext=dict(packet['cases'][0]['coverageContext'], **context), readback={'done': True}))

    def test_lock_reenters_across_instances_and_nested_workflow_review(self):
        with tempfile.TemporaryDirectory() as directory:
            run, packet, coordinator = self.prepare(directory)
            parent, child = multiprocessing.get_context('fork').Pipe()
            def nested():
                try:
                    with coordinator.locked():
                        with Coordinator(directory, 'A1').locked():
                            with coordinator_lock(run):
                                review_workflow(run)
                    child.send('completed')
                finally:
                    child.close()
            process = multiprocessing.get_context('fork').Process(target=nested)
            process.start()
            try:
                self.assertTrue(parent.poll(5), 'nested coordinator lock deadlocked')
                self.assertEqual(parent.recv(), 'completed')
                process.join(5)
                self.assertEqual(process.exitcode, 0)
            finally:
                if process.is_alive(): process.terminate(); process.join(5)
                parent.close(); child.close()

    def test_lock_remains_exclusive_across_processes_after_fork(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = Coordinator(directory, 'A1')
            parent, child = multiprocessing.get_context('fork').Pipe()
            def acquire():
                try:
                    child.send('attempting')
                    with Coordinator(directory, 'A1').locked():
                        child.send('acquired')
                finally:
                    child.close()
            process = multiprocessing.get_context('fork').Process(target=acquire)
            try:
                with coordinator.locked():
                    process.start()
                    self.assertTrue(parent.poll(5))
                    self.assertEqual(parent.recv(), 'attempting')
                    self.assertFalse(parent.poll(0.15), 'child bypassed parent process flock')
                self.assertTrue(parent.poll(5))
                self.assertEqual(parent.recv(), 'acquired')
                process.join(5)
                self.assertEqual(process.exitcode, 0)
            finally:
                if process.is_alive(): process.terminate(); process.join(5)
                parent.close(); child.close()

    def test_coordinator_lock_without_state_and_invalid_state(self):
        with coordinator_lock(working()):
            pass
        with tempfile.TemporaryDirectory() as directory:
            for state in ({}, {'directory': directory, 'assessmentId': 'foreign'},
                          {'directory': str(Path(directory)/'missing'), 'assessmentId': 'A1'}):
                run = working(); run['coordinatorState'] = state
                with self.assertRaises(ValueError):
                    with coordinator_lock(run): self.fail('invalid state was admitted')
            self.assertFalse((Path(directory)/'missing').exists())

    def inherited_effect(self, directory):
        run, _, coordinator = self.prepare(directory)
        w = run['criteriaWorkflow']; case = w['plan']['cases'][0]
        w['plan']['authority']['allowedEffects'] = ['read', 'mutation']
        case['effects'] = ['read', 'mutation']
        case['coverageContext']['objectRef'] = 'object-one'
        case['actions'] = [dict(id='write-new', caseId='T1', effect='mutation'),
                           dict(id='read-old', caseId='T1', effect='read', readbackOf='old'),
                           dict(id='read-no-target', caseId='T1', effect='read'),
                           dict(id='read-wrong-target', caseId='T1', effect='read', readbackOf='another-action')]
        independent = copy.deepcopy(case); independent['id'] = 'T2'
        independent['coverageContext']['objectRef'] = 'object-two'
        independent['actions'] = [dict(id='independent-write', caseId='T2', effect='mutation')]
        w['plan']['cases'].append(independent); w['criteria'][0]['caseIds'].append('T2')
        approve(run)
        packet = make_packet(run, 'W1', ['T1', 'T2'], 'worker', refs={
            'pendingEffectsRef': 'private-pending-reference', 'resourceLeaseRef': 'private-lease-reference'})
        effect = dict(actionId='old', caseId='T1', effect='mutation', state='unknown',
                      coverageContext=copy.deepcopy(case['coverageContext']))
        return run, packet, coordinator, effect

    def test_inherited_unknown_effect_blocks_mutation_but_allows_readback_and_independent_case(self):
        for source in ('pendingEffects', 'actionHistory', 'operations', 'journal-history'):
            for allowed in ('readback', 'independent'):
                with self.subTest(source=source, allowed=allowed), tempfile.TemporaryDirectory() as directory:
                    run, packet, coordinator, effect = self.inherited_effect(directory)
                    if source == 'operations':
                        run['operations'].append(dict(effect, id='prior-operation', status='partial', outcomeUnknown=True))
                    elif source == 'journal-history':
                        row = dict(effect); row.pop('state')
                        run['actionHistory'] = [{'kind': 'unknown', 'data': row}]
                    else:
                        run[source] = [effect]
                    coordinator.acquire(run, packet)
                    actions = packet['cases'][0]['actions']
                    self.assertEqual(review_workflow(run)['pendingEffects'][0]['actionId'], 'old')
                    with self.assertRaises(ValueError):
                        coordinator.dispatch(run, packet, actions[0], lambda action: self.fail('replayed unknown mutation'))
                    for action in actions[2:]:
                        with self.assertRaises(ValueError):
                            coordinator.dispatch(run, packet, action, lambda action: self.fail('read did not name exact pending action'))
                    self.assertEqual(coordinator.pending_effects(), [])
                    action = actions[1] if allowed == 'readback' else packet['cases'][1]['actions'][0]
                    seen = []
                    coordinator.dispatch(run, packet, action, lambda action: seen.append(action['id']))
                    self.assertEqual(seen, [action['id']])

    def test_same_task_unknown_effect_blocks_other_object_actions_on_shared_scanner(self):
        with tempfile.TemporaryDirectory() as directory:
            run, _, coordinator, _ = self.inherited_effect(directory)
            w = run['criteriaWorkflow']
            w['plan']['authority']['allowedEffects'].append('start')
            independent = w['plan']['cases'][1]
            independent['effects'].append('start')
            independent['actions'].extend([
                dict(id='independent-start', caseId='T2', effect='start'),
                dict(id='independent-read', caseId='T2', effect='read')])
            approve(run)
            packet = make_packet(run, 'W1', ['T1', 'T2'], 'worker')
            self.assertIn('shared-scanner', packet['resourceIds'])
            self.assertNotEqual(packet['cases'][0]['coverageContext']['objectRef'],
                                packet['cases'][1]['coverageContext']['objectRef'])
            coordinator.acquire(run, packet)
            def lost_ack(action): raise TimeoutError('lost scanner acknowledgement')
            with self.assertRaises(TimeoutError):
                coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lost_ack)
            for action in packet['cases'][1]['actions']:
                with self.subTest(effect=action['effect']), self.assertRaisesRegex(ValueError, 'pending shared task effects'):
                    coordinator.dispatch(run, packet, action, lambda action: self.fail('shared scanner reused before readback'))
            self.assertEqual(coordinator.status()['tasks'][0]['pendingActionIds'], ['write-new'])

    def test_consumed_raw_operation_or_history_action_cannot_replay(self):
        for source in ('operation-action-id', 'operation-id', 'history', 'journal-history'):
            with self.subTest(source=source), tempfile.TemporaryDirectory() as directory:
                run, packet, coordinator, _ = self.inherited_effect(directory)
                if source.startswith('operation'):
                    row = dict(id='previous', status='completed')
                    if source == 'operation-id': row['id'] = 'write-new'
                    else: row['actionId'] = 'write-new'
                    run['operations'].append(row)
                else:
                    row = dict(actionId='write-new', caseId='T1', effect='mutation', state='acknowledged')
                    run['actionHistory'] = [{'kind': 'acknowledged', 'data': row} if source == 'journal-history' else row]
                coordinator.acquire(run, packet)
                with self.assertRaises(ValueError):
                    coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: self.fail('replayed consumed action'))

    def test_exact_resolution_removes_inherited_pending_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            run, packet, coordinator, effect = self.inherited_effect(directory)
            run['pendingEffects'] = [effect]
            run['operations'].append(dict(id='resolve-old', status='completed', coverageContext=effect['coverageContext'],
                readback={'actionId': 'old', 'caseId': 'T1', 'resolved': True}))
            run['criteriaWorkflow']['resolutions'] = [dict(actionId='old', resolutionOperationId='resolve-old',
                resultPath='/readback', basis='Read exact prior action/object result')]
            self.assertEqual(review_workflow(run)['pendingEffects'], [])
            coordinator.acquire(run, packet)
            seen = []
            coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: seen.append(action['id']))
            self.assertEqual(seen, ['write-new'])

    def test_stopped_revised_plan_can_recover_original_effect_without_dispatch(self):
        with tempfile.TemporaryDirectory() as directory:
            run, packet, coordinator = self.prepare(directory)
            coordinator.acquire(run, packet)
            old_run = copy.deepcopy(run)
            coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: {'ack': 'native-id'})
            self.assertFalse(review_workflow(old_run)['eligibleForCompletion'])
            run['criteriaWorkflow']['planRevision'] = 'P-2'; approve(run)
            run['criteriaWorkflow']['userRequest'] = {'kind': 'stop', 'source': 'user request'}
            self.terminal(run, packet)
            recovered = Coordinator(directory, 'A1')
            with self.assertRaises(ValueError):
                recovered.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: self.fail('replayed'))
            recovered.reconcile(run, packet, 'read-1', ['terminal'])
            self.assertTrue(recovered.release(run, packet)['released'])
            self.assertEqual(review_workflow(run)['assessmentStatus'], 'stopped_by_user')

    def test_wrong_context_cannot_release_unknown_effect(self):
        with tempfile.TemporaryDirectory() as directory:
            run, packet, coordinator = self.prepare(directory)
            coordinator.acquire(run, packet)
            def fail(action): raise TimeoutError('lost acknowledgement')
            with self.assertRaises(TimeoutError):
                coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], fail)
            self.terminal(run, packet, product='other')
            with self.assertRaises(ValueError): coordinator.reconcile(run, packet, 'read-1', ['terminal'])
            with self.assertRaises(ValueError): coordinator.release(run, packet)
            self.assertEqual(coordinator.status()['tasks'][0]['pendingActionIds'], ['read-1'])

    def test_missing_lease_or_journal_cannot_make_stale_run_complete(self):
        for missing in ('lease', 'journal'):
            with self.subTest(missing=missing), tempfile.TemporaryDirectory() as directory:
                run, packet, coordinator = self.prepare(directory)
                coordinator.acquire(run, packet)
                coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: None)
                if missing == 'lease':
                    coordinator._path(packet['resourceIds'][0]).unlink()
                else:
                    (coordinator.directory / 'journal.jsonl').unlink()
                with self.assertRaises(ValueError): review_workflow(run)

    def test_active_lease_blocks_closure_before_intent_and_after_reconciliation(self):
        with tempfile.TemporaryDirectory() as directory:
            run, packet, coordinator = self.prepare(directory)
            context = dict(run['criteriaWorkflow']['context'])
            run['operations'].append(dict(id='scanner-state', status='completed', coverageContext=context,
                readback={'resourceId': 'shared-scanner', 'status': 'stopped', 'producerActive': False}))
            run['criteriaWorkflow']['resourceReview']['resources'] = [dict(id='shared-scanner',
                status='stopped', basis='Native producer state', operationId='scanner-state', resultPath='/readback')]
            stale_run = copy.deepcopy(run)
            self.assertTrue(review_workflow(stale_run)['eligibleForCompletion'])
            coordinator.acquire(run, packet)
            acquired = review_workflow(stale_run)
            self.assertFalse(acquired['eligibleForCompletion'])
            self.assertIn('active-coordinator-lease:W1', acquired['diagnostics'])
            self.assertEqual(coordinator.pending_effects(), [])
            coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: None)
            self.terminal(run, packet)
            coordinator.reconcile(run, packet, 'read-1', ['terminal'])
            reconciled = review_workflow(stale_run)
            self.assertFalse(reconciled['eligibleForCompletion'])
            self.assertIn('active-coordinator-lease:W1', reconciled['diagnostics'])
            self.assertEqual(coordinator.pending_effects(), [])
            coordinator.release(run, packet)
            self.assertTrue(review_workflow(stale_run)['eligibleForCompletion'])

    def test_concurrent_assessments_cannot_both_lease_shared_scanner(self):
        with tempfile.TemporaryDirectory() as directory:
            prepared = [self.prepare(directory, aid) for aid in ('A1', 'A2')]
            def acquire(args):
                run, packet, coordinator = args
                try:
                    coordinator.acquire(run, packet)
                    return True
                except (ValueError, OSError):
                    return False
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(acquire, prepared))
            self.assertEqual(sum(results), 1)
            run, packet, coordinator = prepared[results.index(True)]
            coordinator.release(run, packet)

    def test_worker_operations_confined_to_packet_and_duplicate_rows_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            run, packet, coordinator = self.prepare(directory)
            result = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
            result['operations'] = [dict(run['operations'][0], id='foreign', coverageContext={'product': 'other'})]
            with self.assertRaises(ValueError): merge_result(run, packet, result)
            result['operations'] = [copy.deepcopy(run['operations'][0])] * 2
            with self.assertRaises(ValueError): merge_result(run, packet, result)
