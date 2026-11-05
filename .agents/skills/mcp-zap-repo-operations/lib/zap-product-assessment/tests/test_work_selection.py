import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zap_assessment.product_scope import reconcile, continue_work
from zap_assessment.product_scope_cli import main, load_work_state
from zap_assessment.work_selection import select_next_work
from zap_assessment.executor_routing import map_question_capability
from workflow_fixtures import inventory, case, observed, operation, link, context, action
from test_executor_routing import candidate, ARGS


def selection(inv, handlers, pre=None, attempts=(), observations=None, operations=()):
    rec=reconcile(inv,observations or {},pre or {},operations=operations,attempts=attempts)
    rec.update(observations=observations or {},operations=list(operations))
    return select_next_work(inv,rec,pre or {},attempts,set(handlers))


class WorkSelectionTests(unittest.TestCase):
    def test_independent_ready_branch_selected_and_missing_handler_visible(self):
        inv=inventory([case('media',prerequisites=['decoder'],actions=[action('media')]),case('reaction',actions=[action('reaction')])])
        result=selection(inv,['reaction'])
        self.assertEqual(result['selectedActionId'],'reaction')
        self.assertIn('case-prerequisites',result['deferred'][0]['reasonCodes'])
        result=selection(inv,[],pre={'decoder':True})
        self.assertEqual([r['actionId'] for r in result['missingHandlers']],['media','reaction'])
        self.assertEqual(result['nextPreparation'][0]['action'],'prepare-adapter')

    def test_existing_result_priority_and_high_impact_preparation(self):
        inv=inventory([case('low',priority='low',actions=[action('execute-low')]),
            case('media',priority='high',prerequisites=['fixture'],actions=[action('prepare',kind='prepare',unblocksCaseIds=['media'],selectionBasis='Owned fixture unlocks high-impact media boundary')])])
        self.assertEqual(selection(inv,['execute-low','prepare'])['selectedActionId'],'prepare')
        inv['cases'][0]['actions'].append(action('readback',kind='readback',usesExistingResult=True))
        self.assertEqual(selection(inv,['execute-low','prepare','readback'])['selectedActionId'],'readback')

    def test_unknown_reader_first_only_related_branch_blocked_no_replay(self):
        inv=inventory([case('media',coverageContext=context(objectRef='media-object'),actions=[action('mutate',effect='mutation'),action('read-state',kind='reconcile-state')]),
            case('reaction',coverageContext=context(objectRef='reaction-object'),actions=[action('reaction')])])
        history=[dict(caseId='media',actionId='mutate',effect='mutation',state='unknown',coverageContext=context(objectRef='media-object'))]
        result=selection(inv,['mutate','read-state','reaction'],attempts=history)
        self.assertEqual(result['selectedActionId'],'read-state')
        result=selection(inv,['reaction'],attempts=history)
        self.assertEqual(result['selectedActionId'],'reaction')
        self.assertIn('read-state',[r['actionId'] for r in result['missingHandlers']])

    def test_unknown_resolved_flag_and_boolean_readback_cannot_hide_effect(self):
        inv=inventory();pending=[dict(effectId='mutate',actionId='mutate',caseId='pin',resolved=True)]
        rec=reconcile(inv,{'pin':observed(stateReconciled=True,resolvedActionIds=['mutate'])},{},operations=[operation()],pending_effects=pending)
        self.assertTrue(rec['cases'][0]['outcomeUnknown'])

    def test_valid_resolution_unblocks_dependent_case_without_rewriting_old_unknown(self):
        inv=inventory([case(),case('reaction',coverageContext=context(objectRef='other'),actions=[action('react',dependsOnCases=['pin'])])])
        unknown=operation(outcomeUnknown=True,actionId='change',caseId='pin')
        reader=operation('followup',status='completed')
        reader['readback']['resolution']=dict(actionId='change',caseId='pin',resolved=True,context=context())
        obs={'pin':observed([link('followup')],outcomeUnknown=True,resolvedEffects=[dict(actionId='change',resolutionOperationId='followup',resultPath='/readback/resolution',basis='Read exact action and object')])}
        result=selection(inv,['react'],observations=obs,operations=[unknown,reader])
        self.assertEqual(result['selectedActionId'],'react')
        self.assertTrue(unknown['outcomeUnknown'])
        self.assertTrue(obs['pin']['outcomeUnknown'])

    def test_continue_accepts_exact_effect_resolution_returned_by_state_reader(self):
        inv=inventory([case(actions=[action('read-state',kind='reconcile-state')])])
        unknown=operation(outcomeUnknown=True,actionId='change',caseId='pin')
        history=[dict(actionId='change',caseId='pin',effect='mutation',state='unknown',coverageContext=context())]
        reader=operation('followup',status='completed')
        reader['readback']['resolution']=dict(actionId='change',caseId='pin',resolved=True,context=context())
        observation=observed([link('followup')],resolvedEffects=[dict(actionId='change',resolutionOperationId='followup',resultPath='/readback/resolution',basis='Read exact action outcome')])
        result=continue_work(inv,{'pin':dict(outcomeUnknown=True)},{},
            {'read-state':lambda _:dict(observations={'pin':observation},operations=[reader])},
            persist=lambda _:None,attempts=history,operations=[unknown])
        self.assertEqual(result['taskCompletion'],'complete')
        self.assertTrue(result['pendingEffects'][0]['resolved'])
        self.assertEqual(result['actionsPerformed'][-1]['state'],'acknowledged')
        self.assertEqual(history[0]['state'],'unknown')
        self.assertTrue(unknown['outcomeUnknown'])
        for dimension in ('objectRef','objective'):
            wrong=copy.deepcopy(reader)
            wrong['readback']['resolution']['context'][dimension]='different'
            with self.subTest(dimension=dimension):
                blocked=continue_work(inv,{'pin':dict(outcomeUnknown=True)},{},
                    {'read-state':lambda _:dict(observations={'pin':observation},operations=[wrong])},
                    persist=lambda _:None,attempts=history,operations=[unknown])
                self.assertEqual(blocked['taskCompletion'],'partial')
                self.assertTrue(blocked['cases'][0]['outcomeUnknown'])
                self.assertEqual(blocked['actionsPerformed'][-1]['state'],'failed')

    def test_stop_and_durable_intent_ordering(self):
        inv=inventory([case(actions=[action('run',effect='mutation')])]);events=[];calls=[]
        def handler(_):
            self.assertEqual(events[-1]['state'],'intent');calls.append('run')
            return {'observations':{'pin':observed()},'operations':[operation()]}
        result=continue_work(inv,{}, {},{'run':handler},persist=events.append,stop=True)
        self.assertFalse(events);self.assertFalse(calls)
        result=continue_work(inv,{}, {},{'run':handler},persist=events.append)
        self.assertEqual(calls,['run']);self.assertEqual(result['taskCompletion'],'partial')
        self.assertTrue(result['cases'][0]['outcomeUnknown'])
        self.assertEqual(result['actionsPerformed'][-1]['state'],'acknowledged')
        self.assertEqual(result['selectionDecisions'][0]['selectedActionId'],'run')
        for state in ('intent','acknowledged','unknown'):
            with self.subTest(state=state):
                continue_work(inv,{}, {},{'run':lambda _:self.fail('no replay')},persist=lambda _:None,
                    attempts=[dict(actionId='run',caseId='pin',effect='mutation',state=state,coverageContext=context())])

    def test_intent_write_failure_prevents_dispatch(self):
        inv=inventory([case(actions=[action('run',effect='mutation')])])
        def reject(_):raise OSError('durable store unavailable')
        with self.assertRaises(OSError):continue_work(inv,{}, {},{'run':lambda _:self.fail('must not dispatch')},persist=reject)

    def test_operation_ack_without_action_history_still_prevents_replay(self):
        inv=inventory([case(actions=[action('run',effect='mutation')])])
        ops=[operation(status='acknowledged',actionId='run')]
        rec=reconcile(inv,{}, {},operations=ops)
        self.assertIsNone(select_next_work(inv,rec,{},[],{'run'})['selectedActionId'])
        result=continue_work(inv,{}, {},{'run':lambda _:self.fail('ACK must not replay')},persist=lambda _:self.fail('no new intent'),operations=ops)
        self.assertEqual(result['taskCompletion'],'partial')

    def test_unbacked_old_violation_does_not_override_current_supported_match(self):
        inv=inventory([case(actions=[action('read',kind='readback')])])
        result=continue_work(inv,{'pin':observed([],outcome='violated')},{},
            {'read':lambda _:dict(observations={'pin':observed()},operations=[operation()])},persist=lambda _:None)
        self.assertEqual(result['taskCompletion'],'complete')
        self.assertEqual(result['observations']['pin']['outcome'],'matched')

    def test_missing_handler_never_closes_assignment(self):
        result=continue_work(inventory([case(actions=[action('run')])]),{}, {},{},persist=lambda _:self.fail('read-only'))
        self.assertEqual(result['taskCompletion'],'partial')
        self.assertEqual(result['workSelection']['missingHandlers'][0]['actionId'],'run')

    def test_continuation_does_not_accumulate_wrong_context_or_old_violation(self):
        inv=inventory([case(actions=[action('read',kind='readback')])])
        old=observed([link('old',units=['own-read'],context=context(build='old'))],outcome='violated')
        new=observed([link('new',units=['sibling-read'])])
        result=continue_work(inv,{'pin':old},{},{'read':lambda _:dict(observations={'pin':new},operations=[operation('new')])},
            persist=lambda _:None,operations=[operation('old',coverageContext=context(build='old'))])
        self.assertEqual(result['taskCompletion'],'partial')
        obs=result['observations']['pin']
        self.assertEqual(obs['outcome'],'matched')
        self.assertEqual(obs['contextHistory'][0]['outcome'],'violated')
        self.assertEqual(result['questionEvidence']['pin']['missingUnits'],['own-read'])

    def test_next_work_cli_no_actions_has_no_executor_and_preserves_previous_unknown(self):
        inv=inventory([case(actions=[action('mutate',effect='mutation'),action('read',kind='reconcile-state')])])
        previous=dict(scope={'productLocation':'/synthetic','track':'fe-authenticated'},inventory=inv,observations={},prerequisites={},
            actionHistory=[dict(actionId='mutate',caseId='pin',effect='mutation',state='intent',coverageContext=context())])
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            for name,data in [('inv',inv),('obs',{}),('pre',{}),('previous',previous)]:
                (root/(name+'.json')).write_text(json.dumps(data))
            args=['next-work','--inventory',str(root/'inv.json'),'--observations',str(root/'obs.json'),'--prerequisites',str(root/'pre.json'),'--previous',str(root/'previous.json')]
            before={p.name:p.read_bytes() for p in root.iterdir()}
            with patch('socket.socket',side_effect=AssertionError('no traffic')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(args),0)
            result=json.loads(output.getvalue())
            self.assertIsNone(result['selectedActionId'])
            self.assertEqual(result['missingHandlers'][0]['actionId'],'read')
            self.assertEqual({p.name:p.read_bytes() for p in root.iterdir()},before)
            loaded=load_work_state(inv,{}, {},previous=[root/'previous.json'])
            self.assertEqual(loaded[2][0]['state'],'intent')

    def test_legacy_metadata_absent_preserves_input_order(self):
        inv=inventory([case('low',priority='low',actions=[action('first')]),case('high',priority='high',actions=[action('second')])]);inv.pop('workflowVersion')
        self.assertEqual(selection(inv,['first','second'])['selectedActionId'],'first')

    def test_residual_missing_adapter_is_visible_beside_independent_execution(self):
        from test_residual_review import review,item
        from test_question_evidence import scope,assessment
        from zap_assessment.security_scope import project_scope,canonical_alerts
        residual=project_scope(scope(),dict(assessment(),residualReview=review([item(actionClass='prepare',nextStep='Prepare retained semantic result reader')])),
            dict(operations=[operation()]),canonical_alerts([]))['residualWork']
        inv=inventory([case('blocked',actions=[]),case('ready',actions=[action('run')])])
        rec=reconcile(inv,{}, {})
        proposal=select_next_work(inv,rec,{},[],{'run'},residual_work=residual)
        self.assertEqual(proposal['selectedActionId'],'run')
        self.assertIn('processing',[r.get('id') for r in proposal['planningProposal']])
        self.assertIn('blocked',[r.get('caseId') for r in proposal['planningProposal']])
        self.assertEqual(proposal['reviewedScopeDecision']['decision'],'continue')


class CapabilityMappingTests(unittest.TestCase):
    def mapping(self):
        q=dict(id='q',toolName='zap_attack_start',arguments=copy.deepcopy(ARGS),authKind='json-bearer')
        c=candidate();c['support']={k:dict(verified=True,basis='Reviewed adapter primitive') for k in ('transport','auth','request','fixture','readback')}
        return q,c

    def test_source_compatible_is_not_runtime_verified(self):
        q,c=self.mapping();result=map_question_capability(q,[c])
        self.assertEqual(result['selectedExecutor'],'shared')
        self.assertEqual(result['verificationLevel'],'source-reviewed')
        self.assertEqual(result['execution'],'not-operated')
        c.update(verificationLevel='runtime-observed',verificationBasis='Recorded run')
        self.assertEqual(map_question_capability(q,[c])['verificationLevel'],'source-reviewed')
        c['deploymentContext']={'environment':'isolated-synthetic'}
        self.assertEqual(map_question_capability(q,[c])['verificationLevel'],'runtime-observed')

    def test_schema_auth_and_missing_reader_still_rejected(self):
        q,c=self.mapping();del c['tools']['tools'][0]['inputSchema']['properties']['postData']
        result=map_question_capability(q,[c])
        self.assertIsNone(result['selectedExecutor'])
        self.assertEqual(result['decisions'][0]['reason'],'schema-field-missing')
        q,c=self.mapping();c['support']['readback']['verified']=False
        result=map_question_capability(q,[c])
        self.assertEqual(result['missingPrimitive'],['readback'])
        self.assertEqual(result['nextPreparation'],['prepare-readback'])
        q,c=self.mapping();q['authKind']='browser-cookie'
        self.assertIsNone(map_question_capability(q,[c])['selectedExecutor'])
