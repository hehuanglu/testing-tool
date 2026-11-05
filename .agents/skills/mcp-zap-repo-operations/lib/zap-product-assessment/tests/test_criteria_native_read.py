import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_criteria_workflow import approve, working
from zap_assessment.contracts import Blocked
from zap_assessment.criteria_delegation import Coordinator, make_packet
from zap_assessment.criteria_native_read import ENDPOINT, execute_read
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.product_scope_cli import main
from zap_assessment.result_readers import bind_zap_message


class CriteriaNativeReadTests(unittest.TestCase):
    def test_history_cli_reads_once_and_preserves_terminal_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            coordinator = Coordinator(root / 'coord', 'A1')
            run = working(None)
            run['coordinatorState'] = {'directory': str(coordinator.root), 'assessmentId': 'A1'}
            case = run['criteriaWorkflow']['plan']['cases'][0]
            case['resourceIds'] = ['scanner-1']
            tool = 'zap_scan_history_get'
            workflow = run['criteriaWorkflow']
            workflow['plan']['authority']['allowedEffects'].append('start')
            case['effects'].append('start')
            common = dict(caseId='T1', effect='read', readbackOf='start', mcpEndpoint=ENDPOINT,
                          scannerResourceId='scanner-1')
            list_tool = 'zap_scan_history_list'
            case['actions'] = [dict(id='start', caseId='T1', effect='start'),
                               dict(common, id='list', toolName=list_tool,
                                    arguments={'target': 'https://example.test', 'limit': 2}),
                               dict(common, id='history', toolName=tool, historyEntryFrom='list')]
            approve(run)
            packet = make_packet(run, 'W1', ['T1'], 'coordinator')
            for name, value in (('run', run), ('packet', packet)):
                (root / (name + '.json')).write_text(json.dumps(value))
            coordinator.acquire(run, packet)

            def lost_ack(_):
                raise TimeoutError('lost start ACK')

            with self.assertRaises(TimeoutError):
                coordinator.dispatch(run, packet, case['actions'][0], lost_ack)
            calls = []

            def request(url, method, headers, body, timeout):
                payload = json.loads(body)
                command = payload['method']
                if command == 'initialize':
                    result = {'protocolVersion': '2025-03-26', 'serverInfo': {'name': 'fake'}}
                elif command == 'tools/list':
                    result = {'tools': [
                        {'name': tool, 'inputSchema': {'type': 'object',
                         'properties': {'entryId': {'type': 'string'}}}},
                        {'name': list_tool, 'inputSchema': {'type': 'object',
                         'properties': {'target': {'type': 'string'}, 'limit': {'type': 'integer'}}}},
                    ]}
                elif command == 'tools/call':
                    calls.append(payload['params'])
                    if payload['params']['name'] == list_tool:
                        response = ('Scan history ledger\n1. entry-1 [scan_run]\n'
                                    '   Target: https://example.test\n2. foreign [scan_run]\n'
                                    '   Target: https://example.test/foreign')
                    else:
                        response = 'Entry ID: entry-1\nTarget: https://example.test\nStatus: started'
                    result = {'content': [{'type': 'text', 'text': response}]}
                else:
                    return {'status': 202, 'headers': {}, 'body': ''}
                return {'status': 200, 'headers': {'mcp-session-id': 'transport-session'},
                        'body': json.dumps({'id': payload['id'], 'result': result})}

            command = ['criteria-native-read', '--run', str(root / 'run.json'),
                       '--packet', str(root / 'packet.json'), '--action-id']
            get_command = [*command, 'history', '--history-entry-id', 'entry-1']
            with patch('zap_assessment.criteria_native_read.execute_read',
                       side_effect=lambda *args, **kwargs: execute_read(*args, request=request, **kwargs)):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(main([*command, 'list']), 0)
                with self.assertRaisesRegex(Blocked, 'outside the retained exact-target'):
                    main([*command, 'history', '--history-entry-id', 'foreign'])
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    self.assertEqual(main(get_command), 0)
                receipt = json.loads(Path(json.loads(output.getvalue())['receipt']).read_text())
                self.assertFalse(receipt['terminalEvidence'])
                with self.assertRaisesRegex(Blocked, 'receipt already exists'):
                    main(get_command)
            self.assertEqual(calls, [
                {'name': list_tool, 'arguments': {'target': 'https://example.test', 'limit': 2}},
                {'name': tool, 'arguments': {'entryId': 'entry-1'}},
            ])
            self.assertEqual(coordinator.status()['tasks'][0]['pendingActionIds'], ['history', 'list', 'start'])
            self.assertFalse(review_workflow(run)['eligibleForCompletion'])
            run['operations'].append(dict(id='reviewed-history', reconciledActionId='history',
                                          effectStatus='terminal', status='completed',
                                          context={'assessmentId': 'A1'},
                                          coverageContext=case['coverageContext'],
                                          readback={'historyReadCompleted': True}))
            (root / 'run.json').write_text(json.dumps(run))
            reconcile = ['criteria-reconcile-action', '--run', str(root / 'run.json'),
                         '--packet', str(root / 'packet.json'), '--operation-id', 'reviewed-history',
                         '--release', '--action-id']
            with self.assertRaisesRegex(ValueError, 'does not establish terminal action readback'):
                main([*reconcile, 'start'])
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main([*reconcile, 'history']), 0)
            self.assertEqual(json.loads(output.getvalue())['pendingActionIds'], ['list', 'start'])

    def test_approved_fixture_substitution_keeps_action_identity(self):
        with tempfile.TemporaryDirectory() as directory:
            coordinator = Coordinator(Path(directory) / 'coord', 'A1')
            run = working(None)
            run['coordinatorState'] = {'directory': str(coordinator.root), 'assessmentId': 'A1'}
            workflow = run['criteriaWorkflow']
            case = workflow['plan']['cases'][0]
            case['coverageContext']['fixtureClass'] = 'same-state'
            action = dict(id='probe', caseId='T1', effect='read', fixtureOptions=['fixture-a', 'fixture-b'])
            case['actions'] = [action]
            approve(run)
            approved = json.dumps(workflow, sort_keys=True)
            packet = make_packet(run, 'W1', ['T1'], 'coordinator')
            coordinator.acquire(run, packet)
            with self.assertRaisesRegex(ValueError, 'select an approved fixture'):
                coordinator.dispatch(run, packet, action, self.fail)
            with self.assertRaisesRegex(ValueError, 'fixture outside'):
                coordinator.dispatch(run, packet, action, self.fail, fixture_ref='foreign')
            self.assertEqual(coordinator.dispatch(run, packet, action, lambda selected: selected['fixtureRef'],
                                                 fixture_ref='fixture-b'), 'fixture-b')
            self.assertEqual(coordinator.status()['tasks'][0]['pendingActionIds'], ['probe'])
            self.assertEqual(json.dumps(workflow, sort_keys=True), approved)

    def test_zap_message_requires_matching_actor_session_and_request(self):
        run = working()
        workflow = run['criteriaWorkflow']
        case = workflow['plan']['cases'][0]
        case['requireZapMessageEvidence'] = True
        context = dict(case['coverageContext'], actorRef='reader', fixtureRef='fixture-1', requestRef='GET-owner')
        workflow['caseResults'][0]['evidenceLinks'][0]['context'] = context
        operation = run['operations'][0]
        operation.update(caseId='T1', coverageContext=context)
        approve(run)
        self.assertIsNone(review_workflow(run)['caseResults'][0]['outcome'])
        header = 'GET /owner HTTP/1.1\r\nHost: example.test\r\n\r\n'
        response = 'HTTP/1.1 403 Forbidden\r\n\r\n'
        message = {'id': '1', 'requestHeader': header, 'requestBody': '',
                   'responseHeader': response, 'responseBody': ''}
        request_hash = hashlib.sha256(json.dumps([header, ''], separators=(',', ':')).encode()).hexdigest()
        response_hash = hashlib.sha256(json.dumps([response, ''], separators=(',', ':')).encode()).hexdigest()
        capture = {'scannerResourceId': 'scanner-1', 'sessionId': 'zap-session', 'message': message}
        with self.assertRaisesRegex(ValueError, 'scanner/session mismatch'):
            bind_zap_message(operation, lambda _: capture, scanner_resource='scanner-1', session='other',
                             message_id='1', request_sha256=request_hash, response_sha256=response_hash)
        op = bind_zap_message(operation, lambda _: capture, scanner_resource='scanner-1', session='zap-session',
                              message_id='1', request_sha256=request_hash, response_sha256=response_hash)
        run['operations'][0] = op
        self.assertEqual(review_workflow(run)['caseResults'][0]['outcome'], 'matched')
        for key, replacement in (('actorRef', 'wrong-actor'), ('sessionId', 'wrong-session'), ('messageId', '2')):
            receipt = op['zapMessageReceipt']
            original = receipt[key]
            receipt[key] = replacement
            self.assertIsNone(review_workflow(run)['caseResults'][0]['outcome'])
            receipt[key] = original
        op['provenance']['transport'] = 'direct-http'
        self.assertIsNone(review_workflow(run)['caseResults'][0]['outcome'])
