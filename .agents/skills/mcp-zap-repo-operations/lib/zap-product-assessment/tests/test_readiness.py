import asyncio
import copy
import unittest
from unittest.mock import patch
from zap_assessment.readiness import wait_for_observation
from workflow_fixtures import FakeTime


class ReadinessTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.time=FakeTime();self.context=dict(objectRef='object-one',actorRef='owner',operationId='attempt-a',stage='consumer',outcomeUnknown=True)
        self.options=dict(context=self.context,timeout_seconds=10,interval_seconds=2,remaining_seconds=30,clock=self.time.clock,sleep=self.time.sleep,cancelled=lambda:False)
        self.calls=[]

    def evaluate(self, value):
        return dict(status='ready' if value.get('ready') else 'pending',stage=value['stage'],facts=value.get('facts',{}),missingConditions=[] if value.get('ready') else ['consumer-not-ready'])

    def sample(self, rows):
        async def read(*,context,timeout_seconds):
            self.calls.append(timeout_seconds)
            row=rows.pop(0) if len(rows)>1 else rows[0]
            return dict(context={k:v for k,v in self.context.items() if k not in ('stage','outcomeUnknown')},**row)
        return read

    async def test_ack_pending_then_right_consumer_only_closes_at_last_sample(self):
        read=self.sample([dict(stage='ack',ready=True),dict(stage='processing',ready=False),dict(stage='consumer',ready=True,facts={'delivered':True})])
        result=await wait_for_observation(read,self.evaluate,**self.options)
        self.assertEqual(result['status'],'ready');self.assertEqual(result['elapsed'],4)
        self.assertEqual(self.calls,[10,8,6]);self.assertTrue(result['outcomeUnknown'])

    async def test_mismatch_actor_object_or_operation_stops_immediately(self):
        for key in ('actorRef','objectRef','operationId'):
            async def read(**_):return dict(context={**self.context,key:'other'},stage='consumer',ready=True)
            result=await wait_for_observation(read,self.evaluate,**self.options)
            self.assertEqual(result['status'],'context-mismatch');self.assertFalse(self.time.sleeps)

    async def test_timeout_does_not_overrun_sleep_or_repeat_mutation(self):
        self.options.update(timeout_seconds=5,remaining_seconds=3)
        result=await wait_for_observation(self.sample([dict(stage='ack',ready=False)]),self.evaluate,**self.options)
        self.assertEqual(result['status'],'timeout');self.assertEqual(result['elapsed'],3)
        self.assertEqual(self.time.sleeps,[2,1]);self.assertEqual(self.calls,[3,1])
        self.assertTrue(result['outcomeUnknown'])

    async def test_sample_receives_budget_and_late_sample_cannot_pass(self):
        async def read(*,context,timeout_seconds):
            self.assertEqual(timeout_seconds,10)
            self.time.now+=11
            return dict(context=context,stage='consumer',ready=True)
        result=await wait_for_observation(read,self.evaluate,**self.options)
        self.assertEqual(result['status'],'timeout')

    async def test_transport_hang_is_bounded_and_cancellation_is_preserved(self):
        async def read(**_):return dict(context=self.context,stage='consumer',ready=True)
        async def timeout(awaitable,timeout):
            self.assertEqual(timeout,10);awaitable.close();raise asyncio.TimeoutError()
        with patch('zap_assessment.readiness.asyncio.wait_for',side_effect=timeout):
            self.assertEqual((await wait_for_observation(read,self.evaluate,**self.options))['status'],'timeout')
        async def cancelled(**_):raise asyncio.CancelledError()
        self.assertEqual((await wait_for_observation(cancelled,self.evaluate,**self.options))['status'],'cancelled')
        self.options['cancelled']=lambda:True
        self.assertEqual((await wait_for_observation(read,self.evaluate,**self.options))['status'],'cancelled')

    async def test_reader_errors_are_sanitized_and_not_retried(self):
        calls=[]
        async def read(**_):calls.append(1);raise RuntimeError('token=do-not-emit')
        result=await wait_for_observation(read,self.evaluate,**self.options)
        self.assertEqual(result['status'],'reader-error');self.assertEqual(len(calls),1)
        self.assertNotIn('do-not-emit',str(result));self.assertFalse(self.time.sleeps)

    async def test_terminal_failure_and_explicit_transient_pending(self):
        read=self.sample([dict(stage='consumer',ready=False,facts={'terminal':True})])
        def evaluate(value):return dict(status='terminal-failure',stage='consumer',facts=value['facts'])
        result=await wait_for_observation(read,evaluate,**self.options)
        self.assertEqual(result['status'],'terminal-failure');self.assertEqual(len(self.calls),1)

    async def test_boundary_only_needs_domain_result_no_media(self):
        self.options['context']={**self.context,'stage':'domain'}
        read=self.sample([dict(stage='domain',ready=True,facts={'rejected':True,'stateUnchanged':True,'token':'private','requestBody':'raw'})])
        result=await wait_for_observation(read,self.evaluate,**self.options)
        self.assertEqual(result['status'],'ready');self.assertEqual(result['facts']['token'],'[private]')
        self.assertNotIn('requestBody',result['facts'])

    async def test_opaque_fixture_credentials_are_redacted_from_nested_facts(self):
        facts = {'setupToken': 'opaque-setup-value', 'nested': [{'session_token': 'opaque-session-value',
            'client-secret': 'opaque-client-value', 'privateKey': 'opaque-key-value'}],
            'caseId': 'issueAccessToken:CUSTOMER', 'basis': 'password validation'}
        result = await wait_for_observation(self.sample([dict(stage='consumer', ready=True, facts=facts)]),
                                           self.evaluate, **self.options)
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['facts']['setupToken'], '[private]')
        self.assertEqual(set(result['facts']['nested'][0].values()), {'[private]'})
        self.assertEqual(result['facts']['caseId'], 'issueAccessToken:CUSTOMER')
        self.assertEqual(result['facts']['basis'], 'password validation')
        self.assertEqual(facts['setupToken'], 'opaque-setup-value')

    async def test_positive_finite_budgets_and_async_reader_required(self):
        read=self.sample([dict(stage='consumer',ready=True)])
        for key in ('timeout_seconds','interval_seconds','remaining_seconds'):
            for value in (0,-1,float('inf'),float('nan'),True):
                options={**self.options,key:value}
                with self.subTest(key=key,value=value),self.assertRaises(ValueError):await wait_for_observation(read,self.evaluate,**options)
        with self.assertRaises(ValueError):await wait_for_observation(lambda **_:None,self.evaluate,**self.options)

    async def test_execution_remaining_can_shrink_during_poll(self):
        self.options['remaining_seconds']=lambda:3-self.time.now
        result=await wait_for_observation(self.sample([dict(stage='ack',ready=False)]),self.evaluate,**self.options)
        self.assertEqual(result['status'],'timeout');self.assertEqual(self.calls,[3,1])
