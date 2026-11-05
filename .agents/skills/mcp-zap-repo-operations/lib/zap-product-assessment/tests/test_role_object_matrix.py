"""Offline role/object admission; never infers a security outcome from status codes."""
import copy
import unittest

from zap_assessment.contracts import digest
from zap_assessment.criteria_workflow import review_workflow
from test_evidence_allocation import allocated_run, native, mapping, case_result


def matrix_run(reciprocal=False, anonymous=False):
    run = allocated_run(False); w = run['criteriaWorkflow']; case = w['plan']['cases'][0]
    base = case['coverageContext']; base = {k:v for k,v in base.items() if k not in ('actorRef', 'fixtureRef')}
    # Original fixture plan binds these dimensions; reapprove only this synthetic
    # fixture definition before constructing any tested allocation.
    case['coverageContext'] = base
    from test_criteria_workflow import approve
    from zap_assessment.criteria_workflow import approval_digest
    from zap_assessment.question_evidence import bound_context
    approve(run)
    participants = [dict(id='A', actorRef='A', fixtureRef='fixture-A', role='member', identityRef='identity-A'),
        dict(id='B', actorRef='anonymous' if anonymous else 'B', fixtureRef='fixture-anonymous' if anonymous else 'fixture-B',
             role='anonymous' if anonymous else 'member', identityRef='anonymous' if anonymous else 'identity-B')]
    ops, mappings, groups = [], [], []
    def add(oid, pid, role, obj, route, second, group_ids, units):
        p = next(p for p in participants if p['id']==pid)
        relation = {'owner-positive':'owner', 'owner-after':'owner', 'nonowner-negative':'nonowner',
            'anonymous-negative':'anonymous', 'session-before':'session-control', 'session-after':'session-control'}[role]
        ctx = dict(base, actorRef=p['actorRef'], fixtureRef=p['fixtureRef'], role=p['role'], relation=relation, objectRef=obj)
        op = native(oid, route, 'request-'+oid, str(len(ops)+20), ctx)
        at = '2026-11-03T08:00:%02d+00:00' % second
        fact = dict(participantId=pid, identityRef=p['identityRef'], semanticRole=role, groupIds=group_ids,
                    objectRef=obj, selector=dict(method='GET',route=route,query=[]), observedAt=at)
        op['readback'] = dict(at=at, matrixContext=fact, reviewedFacts={'synthetic':oid})
        row = mapping(op, units[0]) if units else mapping(op, 'temporary')
        row.update(observationUnits=units, resultPath='/readback/reviewedFacts', matrixContextPath='/readback/matrixContext',
                   matrixContext=copy.deepcopy(fact), capturedAtPath='/readback/at')
        ops.append(op);mappings.append(row)
    gids = ['object-A','object-B'] if reciprocal else ['object-A']
    for pid in (['A'] if anonymous else ['A','B']):
        add(pid+'-session-before',pid,'session-before','session-'+pid,'/session',1,gids,[])
        add(pid+'-session-after',pid,'session-after','session-'+pid,'/session',50,gids,[])
    for index, (owner, other) in enumerate([('A','B'),('B','A')] if reciprocal else [('A','B')]):
        gid=gids[index]; obj='object-'+owner; route='/objects/'+owner
        add(owner+'-baseline',owner,'owner-positive',obj,route,10+index*5,[gid],['owner-control'])
        add(owner+'-negative',other,'anonymous-negative' if anonymous else 'nonowner-negative',obj,route,11+index*5,[gid],['denial'])
        add(owner+'-after',owner,'owner-after',obj,route,40+index,[gid],[])
        groups.append(dict(id=gid,kind='missing-identity' if anonymous else 'object-authorization',objectRef=obj,
            selector=dict(method='GET',route=route,query=[]),ownerParticipantId=owner,negativeParticipantId=other,
            baselineOperationId=owner+'-baseline',negativeOperationId=owner+'-negative',ownerAfterOperationId=owner+'-after',
            sessionControls=[dict(participantId=pid,beforeOperationId=pid+'-session-before',afterOperationId=pid+'-session-after')
                             for pid in (['A'] if anonymous else ['A','B'])]))
    run['operations']=ops
    a=run['evidenceAllocations'][0]
    a.update(criteriaDigest=approval_digest(w,'criteria'),planDigest=approval_digest(w,'plan'),baseContext=bound_context(case,question=True),
             operations=mappings,comparisonMatrix=dict(version=1,participants=participants,groups=groups))
    w['caseResults'][0]['evidenceLinks']=[dict(operationId=row['operationId'],observationUnits=row['observationUnits'],
        resultPath=row['resultPath'],context=copy.deepcopy(row['context']),role='support' if row['observationUnits'] else 'context',
        resultRead=True,basis='Synthetic reviewed native semantic fact') for row in mappings]
    return run


def rewrite_fact(run, oid, **changes):
    """Simulate consistently rewritten metadata; invariant checks must still fail."""
    op=next(o for o in run['operations'] if o['id']==oid)
    row=next(o for o in run['evidenceAllocations'][0]['operations'] if o['operationId']==oid)
    op['readback']['matrixContext'].update(changes)
    row['matrixContext']=copy.deepcopy(op['readback']['matrixContext'])


class RoleObjectMatrixTests(unittest.TestCase):
    def test_explicit_complete_single_and_reciprocal_groups_admitted(self):
        for reciprocal in (False,True):
            with self.subTest(reciprocal=reciprocal):
                run=matrix_run(reciprocal=reciprocal); before=copy.deepcopy(run)
                result=case_result(run)
                self.assertEqual(result['outcome'],'matched')
                self.assertEqual(result['evidence']['supportedUnits'],['denial','owner-control'])
                self.assertFalse(result['evidence']['contextDiagnostics'])
                self.assertEqual(run,before)

    def test_owner_anonymous_requires_explicit_missing_identity_group(self):
        run=matrix_run(anonymous=True)
        self.assertEqual(case_result(run)['outcome'],'matched')
        run['evidenceAllocations'][0]['comparisonMatrix']['groups'][0]['kind']='object-authorization'
        with self.assertRaisesRegex(ValueError,'anonymous'):review_workflow(run)

    def test_default_allocation_still_rejects_cross_actor(self):
        run=matrix_run();run['evidenceAllocations'][0].pop('comparisonMatrix')
        with self.assertRaises(ValueError):review_workflow(run)

    def test_missing_baseline_negative_and_post_controls_fail_closed(self):
        for key in ('baselineOperationId','negativeOperationId','ownerAfterOperationId'):
            with self.subTest(key=key):
                run=matrix_run();run['evidenceAllocations'][0]['comparisonMatrix']['groups'][0].pop(key)
                with self.assertRaises(ValueError):review_workflow(run)
        run=matrix_run();run['evidenceAllocations'][0]['comparisonMatrix']['groups'][0]['sessionControls'].pop()
        with self.assertRaisesRegex(ValueError,'missing authenticated'):review_workflow(run)

    def test_wrong_actor_object_selector_and_role_even_with_rewritten_metadata(self):
        mutations=[('participantId','A'),('objectRef','other-object'),('semanticRole','owner-positive'),
            ('identityRef','wrong-identity'),('selector',dict(method='GET',route='/objects/other',query=[]))]
        for key,value in mutations:
            with self.subTest(key=key):
                run=matrix_run();rewrite_fact(run,'A-negative',**{key:value})
                with self.assertRaises(ValueError):review_workflow(run)
        # A query is a selector dimension even though it is outside coverageContext.
        run=matrix_run();rewrite_fact(run,'A-negative',selector=dict(method='GET',route='/objects/A',query=[['id','wrong']]))
        with self.assertRaisesRegex(ValueError,'same exact object and selector'):review_workflow(run)

    def test_wrong_object_or_route_after_all_per_operation_contexts_rebound(self):
        for dimension,value in [('objectRef','object-B'),('route','/objects/B')]:
            with self.subTest(dimension=dimension):
                run=matrix_run();op=next(o for o in run['operations'] if o['id']=='A-negative')
                row=next(o for o in run['evidenceAllocations'][0]['operations'] if o['operationId']==op['id'])
                op['coverageContext'][dimension]=value;row['context']=copy.deepcopy(op['coverageContext'])
                fact=op['readback']['matrixContext']
                if dimension=='route':fact['selector']['route']=value
                else:fact['objectRef']=value
                row['matrixContext']=copy.deepcopy(fact)
                with self.assertRaisesRegex(ValueError,'same exact object and selector'):review_workflow(run)

    def test_query_must_be_explicit_exact_pairs_never_wildcard(self):
        for query in (None,{},[['id','*']],['id=value']):
            with self.subTest(query=query):
                run=matrix_run();rewrite_fact(run,'A-negative',selector=dict(method='GET',route='/objects/A',query=query))
                with self.assertRaises(ValueError):review_workflow(run)
        run=matrix_run();run['evidenceAllocations'][0]['comparisonMatrix']['groups'][0]['selector'].pop('query')
        with self.assertRaises(ValueError):review_workflow(run)

    def test_session_controls_bind_participant_selector_identity_and_time(self):
        for oid,changes in [('A-session-before',{'participantId':'B'}),('A-session-after',{'identityRef':'identity-B'}),
            ('A-session-after',{'objectRef':'session-B'}),('A-session-after',{'semanticRole':'session-before'}),
            ('A-session-after',{'selector':dict(method='GET',route='/other',query=[])})]:
            with self.subTest(oid=oid,changes=changes):
                run=matrix_run();rewrite_fact(run,oid,**changes)
                with self.assertRaises(ValueError):review_workflow(run)
        for oid,second in [('A-session-before',12),('A-session-after',9),('A-after',10),('A-negative',9)]:
            with self.subTest(oid=oid):
                run=matrix_run();at='2026-11-03T08:00:%02d+00:00'%second
                rewrite_fact(run,oid,observedAt=at)
                next(o for o in run['operations'] if o['id']==oid)['readback']['at']=at
                with self.assertRaisesRegex(ValueError,'order'):review_workflow(run)
        run=matrix_run();rewrite_fact(run,'A-negative',observedAt='2026-11-03T08:00:20+00:00')
        with self.assertRaisesRegex(ValueError,'time binding'):review_workflow(run)
        run=matrix_run();next(o for o in run['evidenceAllocations'][0]['operations'] if o['operationId']=='A-negative')['capturedAtPath']='/readback/matrixContext/observedAt'
        with self.assertRaisesRegex(ValueError,'time binding'):review_workflow(run)

    def test_stale_native_receipt_and_matrix_context_pointer(self):
        for mutate in [lambda r:r['evidenceAllocations'][0].update(planDigest='stale'),
            lambda r:r['operations'][0]['zapMessageReceipt'].update(requestSha256='0'*64),
            lambda r:r['evidenceAllocations'][0]['operations'][0].update(matrixContextPath='/absent'),
            lambda r:r['operations'][0]['provenance'].update(sessionId='other')]:
            with self.subTest(mutate=mutate):
                run=matrix_run();mutate(run)
                with self.assertRaises(ValueError):review_workflow(run)

    def test_mismatched_scanner_build_origin_method_objective_still_rejected(self):
        for dimension in ('build','origin','method','objective'):
            with self.subTest(dimension=dimension):
                run=matrix_run();op=run['operations'][0];op['coverageContext'][dimension]='wrong'
                run['evidenceAllocations'][0]['operations'][0]['context']=copy.deepcopy(op['coverageContext'])
                with self.assertRaises(ValueError):review_workflow(run)

    def test_missing_or_unread_control_link_withholds_entire_comparison(self):
        for mutation in ('missing','unread','wrong-role','wrong-pointer'):
            with self.subTest(mutation=mutation):
                run=matrix_run();links=run['criteriaWorkflow']['caseResults'][0]['evidenceLinks']
                if mutation=='missing':links.pop(0)
                elif mutation=='unread':links[0]['resultRead']=False
                elif mutation=='wrong-role':links[0]['role']='support';links[0]['observationUnits']=['owner-control']
                else:links[0]['resultPath']='/readback/at'
                result=case_result(run)
                self.assertEqual(result['evidence']['supportedUnits'],[])
                self.assertIsNone(result['outcome'])
                self.assertIn('matrix-group-readback-links-required',result['evidence']['contextDiagnostics'])

    def test_unknown_effects_still_withhold_units(self):
        run=matrix_run();run['actionHistory']=[dict(actionId='unknown-write',caseId='T1',effect='mutation',state='intent')]
        result=case_result(run)
        self.assertEqual(result['evidence']['supportedUnits'],[])
        self.assertEqual(result['evidence']['unresolvedEffectIds'],['unknown-write'])

    def test_unlisted_group_members_operation_and_unit_never_admitted(self):
        run=matrix_run();rewrite_fact(run,'A-negative',groupIds=['unlisted'])
        with self.assertRaises(ValueError):review_workflow(run)
        run=matrix_run();run['evidenceAllocations'][0]['comparisonMatrix']['groups'][0]['negativeOperationId']='unlisted'
        with self.assertRaises(ValueError):review_workflow(run)
        run=matrix_run();run['evidenceAllocations'][0]['operations'][0]['observationUnits']=['unlisted-unit']
        with self.assertRaises(ValueError):review_workflow(run)
        run=matrix_run();links=run['criteriaWorkflow']['caseResults'][0]['evidenceLinks'];extra=copy.deepcopy(links[-2]);extra['operationId']='unlisted'
        links.append(extra)
        with self.assertRaises(ValueError):review_workflow(run)

    def test_source_only_operation_cannot_supply_native_census_unit(self):
        run=matrix_run();op=next(o for o in run['operations'] if o['id']=='A-baseline');op.pop('zapMessageReceipt')
        with self.assertRaises(ValueError):review_workflow(run)

    def test_control_cannot_be_relabeled_baseline_to_allow_empty_units(self):
        run=matrix_run();row=next(o for o in run['evidenceAllocations'][0]['operations'] if o['operationId']=='A-baseline')
        row['observationUnits']=[]
        with self.assertRaisesRegex(ValueError,'baseline and negative require'):review_workflow(run)

    def test_null_observation_exposes_supported_units_without_closing(self):
        run=matrix_run();run['criteriaWorkflow']['caseResults'][0]['outcome']=None
        result=case_result(run)
        self.assertEqual(result['evidence']['supportedUnits'],['denial','owner-control'])
        self.assertIsNone(result['outcome'])
