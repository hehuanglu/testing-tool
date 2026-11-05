"""Synthetic integration example. No client, product defaults or plugin loading.

Inject a reviewed transport whose execute/prepare/cleanup enforce the real
executor's admission, target/auth binding and ownership checks. This example is
not registered in the CLI allowlist and grants no authority itself.
"""
import copy
from zap_assessment.readiness import wait_for_observation


class QuestionAdapter:
    def __init__(self, transport, persist, *, unit_checkers, evaluate, verdict):
        self.transport = transport
        self.persist = persist
        self.unit_checkers = unit_checkers  # reviewed Python functions, never JSON code
        self.evaluate = evaluate
        self.verdict = verdict
        self.history = []
        self.fixture = None
        self.actor_ref = None

    def record(self, event):
        self.persist(copy.deepcopy(event))  # durable intent must succeed before effect
        self.history.append(copy.deepcopy(event))

    async def prepare(self):
        # Transport owns fixture journaling/admission too; creation is not a read.
        self.fixture = await self.transport.prepare()
        if not self.fixture.get('owned') or not self.fixture.get('objectRef'):
            raise ValueError('fixture ownership readback required')
        return copy.deepcopy(self.fixture)

    async def identity(self):
        value = await self.transport.identity(self.fixture)
        if not value.get('actorRef') or not value.get('verified'):
            raise ValueError('verified identity required')
        self.actor_ref = value['actorRef']
        return value

    async def execute(self, action, *, attempts=()):
        if (not self.fixture or not self.actor_ref or
            action['coverageContext'].get('objectRef') != self.fixture['objectRef'] or
            action['coverageContext'].get('actorRef') != self.actor_ref):
            raise ValueError('action must bind the prepared fixture and verified actor')
        consumed = {e['actionId'] for e in list(attempts) + self.history if e.get('state') in ('intent', 'acknowledged', 'unknown')}
        if action['id'] in consumed:
            raise ValueError('read existing result/state; do not replay action')
        event = dict(actionId=action['id'], caseId=action['caseId'], effect=action['effect'], state='intent',
                     coverageContext=copy.deepcopy(action['coverageContext']))
        self.record(event)
        try:
            ack = await self.transport.execute(action, self.fixture)
        except Exception:
            self.record({**event, 'state': 'unknown'})
            raise
        self.record({**event, 'state': 'acknowledged'})
        return dict(id=ack['operationId'], actionId=action['id'], caseId=action['caseId'],
            status='acknowledged', coverageContext=copy.deepcopy(action['coverageContext']),
            ack=dict(accepted=True))  # sanitized ACK is retained, never counts as units

    async def readback(self, question, operation, **wait_options):
        context = {**question['coverageContext'], 'operationId': operation['id'],
            'stage': question['observationStage'], 'outcomeUnknown': operation.get('outcomeUnknown', False)}
        result = await wait_for_observation(self.transport.sample, self.evaluate, context=context, **wait_options)
        read_operation = copy.deepcopy(operation)
        read_operation['readback'] = result
        units = [unit for unit, check in self.unit_checkers.items() if result['status'] == 'ready' and check(result['facts'])]
        # Keep original operation on disk unchanged; return a derived projection.
        observation = dict(outcome=self.verdict(result['facts']) if result['status'] == 'ready' else 'unknown',
            resultRead=result['status'] == 'ready', basis='Reviewed semantic facts from the bound reader', evidenceLinks=[])
        if units:
            observation['evidenceLinks'].append(dict(operationId=operation['id'], observationUnits=units,
                resultPath='/readback/facts', resultRead=True, basis='Independent unit checkers read facts at the required stage',
                context=copy.deepcopy(question['coverageContext']), role='support'))
            if operation.get('actionId'):
                read_operation['readback']['resolution'] = dict(actionId=operation['actionId'], caseId=question['caseId'],
                    resolved=True, context=copy.deepcopy(question['coverageContext']))
                observation['resolvedEffects'] = [dict(actionId=operation['actionId'],
                    resolutionOperationId=operation['id'], resultPath='/readback/resolution',
                    basis='Read exact action/object state')]
        return dict(observations={question['caseId']: observation}, operations=[read_operation], readiness=result)

    async def cleanup(self):
        if self.fixture is None or not self.fixture.get('owned') or not self.fixture.get('cleanupAssigned'):
            return {'status': 'retained'}
        return await self.transport.cleanup(self.fixture)  # transport journals its own cleanup intent
