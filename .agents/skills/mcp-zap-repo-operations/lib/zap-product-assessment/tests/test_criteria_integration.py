import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from test_criteria_workflow import working, approve
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.criteria_reporting import publish_reports, CriteriaFinalizationError
from zap_assessment.criteria_delegation import Coordinator, make_packet, merge_result
from zap_assessment.product_scope import compact_results
from zap_assessment.product_scope_cli import main


def alerts():
    return {'alerts':[dict(findingId='F1',recordKind='observed-security-alert',source='tester',
        provenance={'transport':'zap-proxy'},securitySignal='Cross-owner disclosure',expectedBehavior='Denied',
        observedBehavior='Object returned',expectationBasis='Expert owner policy',status='suspected',operationIds=['O1'])]}


class ReportingTests(unittest.TestCase):
    def test_v2_dispatch_alert_subset_and_controls(self):
        run=working('violated');run['criteriaWorkflow']['alertMappings']=[dict(findingId='F1',criterionId='C1',rationale='Disclosed owner-only object')]
        data=alerts();data['alerts'].append(dict(findingId='control',recordKind='control-observation',basis='Owner control succeeded'))
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'reports'
            report=compact_results(out,run,data,finalize_round=True)
            self.assertEqual(report['assessmentStatus'],'completed')
            self.assertEqual(report['criterionCounts']['unmet'],1)
            scoped=json.loads((out/'SCOPE_ALERTS.json').read_text())
            self.assertNotIn('criteria',scoped)
            self.assertEqual(scoped['summary']['mappedAlertCount'],1)
            self.assertEqual(report['alertSummary']['alertCount'],1)
            self.assertEqual(len(report['controlObservations']),1)
            with self.assertRaises(ValueError):review_workflow(report)
    def test_ambiguous_legacy_alert_and_unmapped(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):publish_reports(Path(td)/'bad',working(),{'alerts':[{'recordKind':'zap-derived-observation'}]})
            report=publish_reports(Path(td)/'good',working(),alerts())
            self.assertEqual(report['alertSummary']['unmappedAlertCount'],1)
    def test_open_finalization_and_legacy_inventory_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'reports'
            with self.assertRaises(CriteriaFinalizationError):publish_reports(out,working(None),[],finalize=True)
            self.assertFalse(out.exists())
            with self.assertRaises(ValueError):compact_results(out,working(),[],reconciliation={})
    def test_real_cli_review_digest_and_report(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td);(p/'run.json').write_text(json.dumps(working()));(p/'alerts.json').write_text(json.dumps(alerts()))
            for command in (['criteria-review','--run',str(p/'run.json')],['criteria-digest','--run',str(p/'run.json'),'--kind','plan'],
                ['report','--run',str(p/'run.json'),'--alerts',str(p/'alerts.json'),'--output',str(p/'reports'),'--finalize-round']):
                with contextlib.redirect_stdout(io.StringIO()):self.assertEqual(main(command),0)
            self.assertTrue((p/'reports/RUN.json').exists())
    def test_redaction_cannot_remove_support_pointer(self):
        run=working();run['operations'][0]['raw']={'value':True}
        run['criteriaWorkflow']['caseResults'][0]['evidenceLinks'][0]['resultPath']='/raw/value'
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):publish_reports(Path(td)/'reports',run,[])
    def test_invalid_mapping_and_direct_observation_rejected(self):
        run=working();run['criteriaWorkflow']['alertMappings']=[dict(findingId='F1',criterionId='missing',rationale='unsupported')]
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):publish_reports(Path(td)/'reports',run,alerts())
            run=working();run['operations'][0]['provenance']['transport']='direct'
            with self.assertRaises(ValueError):publish_reports(Path(td)/'reports',run,alerts())


class DelegationTests(unittest.TestCase):
    def prepare(self,td):
        run=working();w=run['criteriaWorkflow'];w['plan']['delegation']={'allowed':True}
        w['plan']['cases'][0]['actions']=[dict(id='read-1',caseId='T1',effect='read')]
        approve(run)
        run['coordinatorState']={'directory':str(Path(td).absolute()),'assessmentId':'A1'}
        packet=make_packet(run,'W1',['T1'],'worker')
        return run,packet,Coordinator(td,'A1')
    def test_routed_executor_preserves_approval_and_blocks_fallback_after_lost_ack(self):
        with tempfile.TemporaryDirectory() as td:
            run, _, coordinator = self.prepare(td)
            workflow = run['criteriaWorkflow']
            case = workflow['plan']['cases'][0]
            action = case['actions'][0]
            tool = 'zap_findings_summary'
            action.update(toolName=tool, arguments={'baseUrl': 'https://example.test'},
                          requiredSupport=['transport', 'readback'])
            approve(run)
            approved = copy.deepcopy(workflow)
            packet = make_packet(run, 'W1', ['T1'], 'worker')
            coordinator.acquire(run, packet)
            schema = {'type': 'object', 'properties': {'baseUrl': {'type': 'string'}}}
            good = dict(id='compatible', tools={'tools': [{'name': tool, 'inputSchema': schema}]},
                        support={key: {'verified': True, 'basis': 'offline fixture'}
                                 for key in action['requiredSupport']})
            absent = dict(id='missing', tools={'tools': []})

            def lost_ack(_):
                raise TimeoutError('lost ACK')

            self.assertFalse(coordinator.dispatch_routed(run, packet, action, [absent], {})['dispatched'])
            with self.assertRaisesRegex(ValueError, 'differs from approved'):
                coordinator.dispatch_routed(run, packet, dict(action, id='unapproved'), [good],
                                            {'compatible': lost_ack})
            with self.assertRaises(TimeoutError):
                coordinator.dispatch_routed(run, packet, action, [absent, good], {'compatible': lost_ack})
            alternate = dict(good, id='alternate')
            with self.assertRaisesRegex(ValueError, 'pending shared task effects'):
                coordinator.dispatch_routed(run, packet, action, [alternate],
                                            {'alternate': lambda _: self.fail('replayed')})
            self.assertEqual(workflow, approved)

    def test_routed_readback_closes_case_through_scope_merge(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            run, _, coordinator = self.prepare(td)
            workflow = run['criteriaWorkflow']
            observation = working()
            run['operations'].clear()
            workflow['caseResults'].clear()
            tool = 'zap_findings_summary'
            action = workflow['plan']['cases'][0]['actions'][0]
            action.update(toolName=tool, arguments={'baseUrl': 'https://example.test'},
                          requiredSupport=['readback'])
            approve(run)
            packet = make_packet(run, 'W1', ['T1'], 'worker')
            coordinator.acquire(run, packet)
            schema = {'type': 'object', 'properties': {'baseUrl': {'type': 'string'}}}
            candidate = dict(id='offline', tools={'tools': [{'name': tool, 'inputSchema': schema}]},
                             support={'readback': {'verified': True, 'basis': 'synthetic fixture'}})
            operation = observation['operations'][0]
            operation.update(actionId=action['id'], reconciledActionId=action['id'],
                             effectStatus='terminal', context={'assessmentId': 'A1'})
            result = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
            result.update(operations=[operation], caseResults=observation['criteriaWorkflow']['caseResults'])

            def offline_executor(approved):
                self.assertEqual(approved, action)
                from zap_assessment.safety_io import atomic_bytes
                atomic_bytes(root / 'result.json', json.dumps(result).encode())
                return operation['id']

            routed = coordinator.dispatch_routed(run, packet, action, [candidate], {'offline': offline_executor})
            self.assertEqual(routed['outcome'], 'O1')
            for filename, value in (('run.json', run), ('packet.json', packet)):
                (root / filename).write_text(json.dumps(value))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['criteria-merge', '--run', str(root / 'run.json'),
                                       '--packet', str(root / 'packet.json'),
                                       '--result', str(root / 'result.json'),
                                       '--output', str(root / 'merged.json')]), 0)
            merged = json.loads((root / 'merged.json').read_text())
            recovered = Coordinator(td, 'A1')
            self.assertFalse(review_workflow(merged)['eligibleForCompletion'])
            recovered.reconcile(merged, packet, action['id'], ['O1'])
            recovered.release(merged, packet)
            self.assertTrue(review_workflow(merged)['eligibleForCompletion'])

    def test_lease_conflict_dispatch_unknown_and_closure(self):
        with tempfile.TemporaryDirectory() as td:
            run,packet,c=self.prepare(td);c.acquire(run,packet)
            other=make_packet(run,'W2',['T1'],'worker2')
            with self.assertRaises(ValueError):c.acquire(run,other)
            action=packet['cases'][0]['actions'][0]
            def fail(a):raise TimeoutError('lost ACK')
            with self.assertRaises(TimeoutError):c.dispatch(run,packet,action,fail)
            self.assertFalse(review_workflow(run)['eligibleForCompletion'])
            with self.assertRaises(ValueError):c.dispatch(run,packet,action,lambda a:None)
            with self.assertRaises(ValueError):c.release(run,packet)
            self.assertEqual(Coordinator(td,'A1').status()['tasks'][0]['pendingActionIds'],['read-1'])
    def test_reconcile_release_and_stale_packet(self):
        with tempfile.TemporaryDirectory() as td:
            run,packet,c=self.prepare(td);c.acquire(run,packet)
            c.dispatch(run,packet,packet['cases'][0]['actions'][0],lambda a:{'ack':'1'})
            run['operations'].append(dict(id='terminal',reconciledActionId='read-1',effectStatus='terminal',status='completed',
                context={'assessmentId':'A1'},coverageContext=packet['cases'][0]['coverageContext'],readback={'done':True}))
            c.reconcile(run,packet,'read-1',['terminal']);c.release(run,packet)
            self.assertTrue(review_workflow(run)['eligibleForCompletion'])
            run['criteriaWorkflow']['planRevision']='P-2';approve(run)
            with self.assertRaises(ValueError):c.acquire(run,packet)
    def test_worker_cannot_change_scope_or_approve_itself(self):
        run=working()
        with self.assertRaises(ValueError):make_packet(run,'W1',['T1'],'worker')
        with tempfile.TemporaryDirectory() as td:
            run,packet,c=self.prepare(td)
            result={k:packet[k] for k in ('taskId','packetDigest','criteriaRevision','planRevision')}
            result['criteriaWorkflow']={}
            with self.assertRaises(ValueError):merge_result(run,packet,result)
            result.pop('criteriaWorkflow');result['caseResults']=[dict(caseId='other')]
            with self.assertRaises(ValueError):merge_result(run,packet,result)
    def test_descriptor_effect_cannot_be_smuggled(self):
        with tempfile.TemporaryDirectory() as td:
            run,packet,c=self.prepare(td);c.acquire(run,packet)
            with self.assertRaises(ValueError):c.dispatch(run,packet,dict(id='other',caseId='T1',effect='read',url='foreign'),lambda a:self.fail('executed'))
