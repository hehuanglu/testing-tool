import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from zap_assessment.product_scope import reconcile, compact_results
from workflow_fixtures import inventory, case, context, FakeTime

spec=importlib.util.spec_from_file_location('synthetic_question_adapter',Path(__file__).resolve().parents[1]/'examples/question_adapter.py')
example=importlib.util.module_from_spec(spec);spec.loader.exec_module(example)


class FakeTransport:
    def __init__(self,events):self.events=events;self.reads=0;self.mutations=0;self.cleaned=[]
    async def prepare(self):return dict(objectRef='object-one',owned=True,cleanupAssigned=True)
    async def identity(self,fixture):return dict(actorRef='owner',verified=True)
    async def execute(self,action,fixture):
        assert self.events[-1]['state']=='intent'
        self.mutations+=1
        return dict(operationId='sample-attempt')
    async def sample(self,*,context,timeout_seconds):
        assert timeout_seconds>0
        self.reads+=1
        return dict(context=context,stage='ack' if self.reads==1 else 'persistence',ready=True,
                    facts={'ownerChanged':True,'siblingUnchanged':True} if self.reads>1 else {'accepted':True})
    async def cleanup(self,fixture):self.cleaned.append(fixture['objectRef']);return dict(status='cleaned')


def evaluate(value):return dict(status='ready' if value['ready'] else 'pending',stage=value['stage'],facts=value['facts'])


class AdapterTests(unittest.IsolatedAsyncioTestCase):
    async def test_fake_transport_through_readiness_evidence_reconciliation_and_report(self):
        events=[];transport=FakeTransport(events);time=FakeTime()
        adapter=example.QuestionAdapter(transport,events.append,
            unit_checkers={'own-read':lambda f:f.get('ownerChanged') is True,'sibling-read':lambda f:f.get('siblingUnchanged') is True},
            evaluate=evaluate,verdict=lambda f:'matched' if f.get('siblingUnchanged') else 'violated')
        fixture=await adapter.prepare();identity=await adapter.identity()
        self.assertEqual(identity['actorRef'],'owner');self.assertTrue(fixture['owned'])
        action=dict(id='change',caseId='pin',effect='mutation',coverageContext=context())
        operation=await adapter.execute(action);original=copy.deepcopy(operation)
        question=case(observationStage='persistence')
        value=await adapter.readback(question,operation,timeout_seconds=8,interval_seconds=1,remaining_seconds=10,clock=time.clock,sleep=time.sleep,cancelled=lambda:False)
        self.assertEqual(transport.mutations,1);self.assertEqual(transport.reads,2)
        self.assertEqual(operation,original)
        rec=reconcile(inventory(),value['observations'],{},operations=value['operations'],attempts=adapter.history)
        self.assertEqual(rec['taskCompletion'],'complete')
        self.assertEqual(rec['questionEvidence']['pin']['supportedUnits'],['own-read','sibling-read'])
        with tempfile.TemporaryDirectory() as temp:
            result=compact_results(Path(temp)/'reports',dict(taskCompletion='partial',operations=value['operations']),[],rec)
            self.assertEqual(result['taskCompletion'],'complete')
            self.assertEqual(result['completionSummary']['dast']['status'],'complete')
            self.assertEqual(result['operations'][0]['status'],'acknowledged')
        with self.assertRaises(ValueError):await adapter.execute(action)
        self.assertEqual(transport.mutations,1)
        self.assertEqual((await adapter.cleanup())['status'],'cleaned');self.assertEqual(transport.cleaned,['object-one'])
        adapter.fixture['owned']=False
        self.assertEqual((await adapter.cleanup())['status'],'retained')

    async def test_missing_semantic_fact_never_copies_required_units(self):
        events=[];transport=FakeTransport(events);time=FakeTime()
        adapter=example.QuestionAdapter(transport,events.append,unit_checkers={'own-read':lambda _:False},evaluate=evaluate,verdict=lambda _:'matched')
        await adapter.prepare()
        await adapter.identity()
        operation=await adapter.execute(dict(id='change',caseId='pin',effect='mutation',coverageContext=context()))
        value=await adapter.readback(case(observationStage='persistence'),operation,timeout_seconds=8,interval_seconds=1,remaining_seconds=10,clock=time.clock,sleep=time.sleep,cancelled=lambda:False)
        self.assertEqual(value['observations']['pin']['evidenceLinks'],[])
        self.assertEqual(reconcile(inventory(),value['observations'],{},operations=value['operations'])['taskCompletion'],'partial')

    async def test_adapter_observation_through_history_residual_planning_and_three_reports(self):
        import json
        from test_question_evidence import scope,assessment
        from test_coverage_presentation import historical
        from test_residual_review import review,item
        from zap_assessment.security_scope import project_scope,canonical_alerts
        from zap_assessment.work_selection import select_next_work
        events=[];transport=FakeTransport(events);time=FakeTime()
        adapter=example.QuestionAdapter(transport,events.append,
            unit_checkers={'own-read':lambda f:f.get('ownerChanged') is True,'sibling-read':lambda f:f.get('siblingUnchanged') is True},
            evaluate=evaluate,verdict=lambda _:'matched')
        await adapter.prepare();await adapter.identity()
        op=await adapter.execute(dict(id='change',caseId='pin',effect='mutation',coverageContext=context()))
        value=await adapter.readback(case(observationStage='persistence'),op,timeout_seconds=8,interval_seconds=1,remaining_seconds=10,clock=time.clock,sleep=time.sleep,cancelled=lambda:False)
        rec=reconcile(inventory(),value['observations'],{},operations=value['operations'],attempts=adapter.history)
        s=historical(scope());s['questions'][0]['responsibilityIds']=['pin']
        a=assessment(value['observations']['pin']);a['residualReview']=review([item(kind='answered',actionClass='none',caseIds=['pin'])])
        run=dict(operations=value['operations'],actionHistory=adapter.history)
        residual=project_scope(s,a,run,canonical_alerts([]),rec)['residualWork']
        next_work=select_next_work(inventory(),rec,{},adapter.history,set(),residual_work=residual)
        self.assertIsNone(next_work['selectedActionId'])
        self.assertEqual(next_work['reviewedScopeDecision']['decision'],'no-further-dynamic-action-in-reviewed-scope')
        with tempfile.TemporaryDirectory() as temp:
            result=compact_results(Path(temp)/'reports',run,[],rec,security_scope=s,scope_assessment=a)
            projection=json.loads((Path(temp)/'reports/SCOPE_ALERTS.json').read_text())
            self.assertEqual(result['taskCompletion'],'partial')
            self.assertEqual(result['completionSummary']['dast']['status'],'complete')
            self.assertEqual(len(result['completionSummary']['dast']['workUnits']),1)
            self.assertEqual(projection['criteria'][0]['coverageView']['displayStatus'],'current-observed')
            self.assertEqual(projection['criteria'][1]['coverageView']['displayStatus'],'historical-only')
        self.assertEqual(transport.mutations,1);self.assertEqual(transport.reads,2)
