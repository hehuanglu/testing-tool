import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.fe_authenticated_discovery import discover
from zap_assessment.fe_authenticated_evidence_finalsource import cleanup_readback
from zap_assessment.fe_authenticated_semantics import derive
from zap_assessment.fe_authenticated_verify import verify
from zap_assessment.fe_authenticated_contract import canonical
from zap_assessment.fe_authenticated_handoff import apply_triage

WORKSPACE = Path(__file__).resolve().parents[2]


class CleanupReadbackTests(unittest.TestCase):
    def write(self, name, value):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('private/ACTORS_INITIAL.json', {'actor-a': {'subject': 123}, 'actor-b': {'subject': 124}})
        self.write('private/fixtures/actor-a/FIXTURE_DAG.json', {
            'subject': 123, 'accounts': [{'id': 456}, {'id': 457}],
            'database': {'categoryId': 9, 'billId': 10}})
        self.owned = [{'actorRef': 'actor-a', 'field': 'ownedGoalId', 'id': 600},
                      {'actorRef': 'actor-a', 'field': 'uiAccountId', 'id': 458}]
        self.receipt = {'accounts': {'actor-a': [456, 457]}, 'retained': [
            {'actorRef': ref, 'kind': kind, 'ids': [identifier], 'reason': 'Unsupported delete; retained'}
            for ref, kind, identifier in [('actor-a', 'principal', 123), ('actor-b', 'principal', 124),
                                           ('actor-a', 'category', 9), ('actor-a', 'bill', 10),
                                           ('actor-a', 'goal', 600)]], 'replay': False}
        folder = 'private/cleanup/actor-a/'
        self.write(folder + 'CLEANUP_INTENT.json', {
            'subject': 123, 'exactAccountIds': [456, 457], 'state': 'acknowledged'})
        self.write(folder + 'setup/001-response.json', {
            'body': {'data': {'user_id': 123, 'accounts': [{'id': 456}, {'id': 457}]}}})
        self.write(folder + 'setup/004-response.json', {'body': {'data': {'user_id': 123, 'accounts': []}}})
        for number, identifier in [(2, 456), (3, 457)]:
            self.write(folder + f'setup/{number:03}-request.json', {
                'method': 'DELETE', 'path': f'/api/v1/accounts/{identifier}', 'state': 'response-observed'})
            self.write(folder + f'setup/{number:03}-response.json', {
                'body': {'data': {'deleted_account_id': identifier}}})

    def check(self, receipt=None):
        self.write('FIXTURE_CLEANUP.json', self.receipt if receipt is None else receipt)
        return cleanup_readback(self.root, self.owned)

    def test_all_owned_cleanup_and_exact_retention_are_accepted(self):
        self.assertEqual(self.check(), self.receipt)

    def test_omitted_actor_cleanup_or_retention_cannot_disappear(self):
        for change in ('accounts', 'principal', 'goal', 'category', 'bill'):
            with self.subTest(change=change):
                receipt = copy.deepcopy(self.receipt)
                if change == 'accounts':
                    receipt['accounts'] = {}
                else:
                    receipt['retained'] = [r for r in receipt['retained'] if r['kind'] != change]
                with self.assertRaisesRegex(ValueError, 'obligations'):
                    self.check(receipt)

    def test_wrong_ids_duplicate_retention_and_remaining_ui_account_reject(self):
        receipt = copy.deepcopy(self.receipt)
        receipt['accounts']['actor-a'] = [456, 999]
        with self.assertRaisesRegex(ValueError, 'exact owned intent'):
            self.check(receipt)
        receipt = copy.deepcopy(self.receipt)
        receipt['retained'].append(copy.deepcopy(receipt['retained'][0]))
        with self.assertRaisesRegex(ValueError, 'retention obligations'):
            self.check(receipt)
        self.write('private/cleanup/actor-a/setup/004-response.json', {
            'body': {'data': {'user_id': 123, 'accounts': [{'id': 458}]}}})
        with self.assertRaisesRegex(ValueError, 'UI-created account'):
            self.check()


class PartialJourneyReadbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = WORKSPACE / 'test-artifacts/fe-authenticated-20261023T174107Z/fa-product-diagnostic-08/runtime'
        if not cls.root.exists():
            raise unittest.SkipTest('Historical diagnostic receipt unavailable')
        cls.plan = json.loads((cls.root / 'PLAN.json').read_bytes())
        cls.records = [json.loads(p.read_bytes()) for p in sorted((cls.root / 'broker').glob('[0-9]*.json'))]
        cls.messages = json.loads((cls.root / 'messages.json').read_bytes())['messages']

    def test_real_failed_prefix_returns_partial_without_fabricated_tls_error(self):
        result = verify(self.root, canonical(self.plan))
        self.assertEqual(result['taskCompletion'], 'partial')
        self.assertFalse(result['errors'])
        self.assertTrue(any('failed journey reload-isolation-b' in x for x in result['missing']))
        self.assertEqual(sum(j['completed'] for j in result['journeys']), 53)

    def test_failed_outcome_does_not_hide_changed_recorded_action(self):
        target = self.root / 'browser/isolation-b/reload-isolation-b.json'
        original = Path.read_bytes
        def changed(path):
            data = original(path)
            if path == target:
                receipt = json.loads(data)
                receipt['steps'][0]['actionSpec']['path'] = '/unreviewed'
                return json.dumps(receipt).encode()
            return data
        with patch.object(Path, 'read_bytes', changed):
            result = derive(self.root, self.plan, self.records, self.messages)
        self.assertTrue(any('reviewed UI action specification mismatch' in x for x in result['errors']))

    def test_accounts_reload_uses_source_defined_heading(self):
        model = discover(WORKSPACE / 'finalsource', 'finalsource-fe-auth/1.0')['journeys']
        journey = next(j for j in model['journeys'] if j['id'] == 'reload-isolation-b')
        step = next(s for s in journey['steps'] if s['action'] == 'reload')
        self.assertEqual(step['predicate']['selector'], '#accounts-heading')
        self.assertIn('id="accounts-heading"', (WORKSPACE / 'finalsource/fe/src/pages/AccountListPage.tsx').read_text())


class TriageTests(unittest.TestCase):
    def test_reviewed_assessment_preserves_native_classification_and_binds_evidence(self):
        import hashlib
        with tempfile.TemporaryDirectory() as td:
            evidence = Path(td) / 'response.json'
            evidence.write_text('{"status":200}')
            groups = [{'findingId': 'ZAP-001', 'nativeRuleId': '10020', 'severity': 'Medium',
                       'instances': [{'nativeAlertId': '7'}]}]
            triage = {'findingId': 'ZAP-001', 'nativeRuleId': '10020', 'nativeAlertIds': ['7'],
                      'verificationStatus': 'configuration-only', 'rationale': 'Header absent in captured response',
                      'impact': 'Framing impact not demonstrated', 'remediation': 'Set reviewed frame policy',
                      'reproduction': 'Inspect the pinned response', 'evidenceRefs': [
                          {'path': str(evidence), 'sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}]}
            self.assertEqual(apply_triage(groups, [triage]), {'ZAP-001'})
            self.assertEqual(groups[0]['severity'], 'Medium')
            self.assertEqual(groups[0]['testerAssessment']['impact'], triage['impact'])
            altered = copy.deepcopy(triage)
            altered['nativeAlertIds'] = ['8']
            with self.assertRaisesRegex(ValueError, 'attribution'):
                apply_triage(groups, [altered])
            evidence.write_text('{"status":403}')
            with self.assertRaisesRegex(ValueError, 'evidence drift'):
                apply_triage(groups, [triage])


class FaultBaselineTests(unittest.TestCase):
    def test_mutation_receipt_excludes_later_connect_and_other_requests(self):
        from zap_assessment.fe_authenticated_faults import mutation_records
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            expected = {'caseId': 'fault-pre-send', 'method': 'POST',
                        'url': 'https://cardinal.test:9543/records', 'transportState': 'not-sent'}
            rows = [dict(caseId='fault-pre-send', method='CONNECT'), expected,
                    dict(caseId='fault-pre-send', method='CONNECT'),
                    dict(caseId='fault-pre-send', method='POST', url='https://outside.test/records'),
                    dict(caseId='other-case', method='POST', url='https://cardinal.test:9543/records')]
            for i, row in enumerate(rows):
                (root / f'{i:06}.json').write_text(json.dumps(row))
            self.assertEqual(mutation_records(root, 'fault-pre-send', 'https://cardinal.test:9543'), [expected])

    def test_fault_counter_starts_after_wire_credential_readback(self):
        import hashlib
        from types import SimpleNamespace
        from zap_assessment.fe_authenticated_faults import install
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            capture = root / 'broker'
            capture.mkdir()
            arrivals = root / 'arrivals'
            arrivals.mkdir()
            log = arrivals / 'arrivals.jsonl'
            log.write_text('{}\n')
            headers = ['Bearer owned-native-unit', 'Bearer owned-browser-unit']
            for number, (slot, credential) in enumerate(zip(['native', 'browser'], headers)):
                (capture / f'{number:06}.json').write_text(json.dumps({
                    'sequence': number, 'authSlot': slot, 'observedPrincipal': 'owned-person',
                    'credentialFingerprint': hashlib.sha256(credential.encode()).hexdigest()}))
            calls = []
            def engine(component, kind, name, args):
                if name == 'messages':
                    if not calls:
                        # The preceding browser request completes while native history is read.
                        with log.open('a') as stream:
                            stream.write('{}\n')
                    calls.append(name)
                    return {'messages': [{'id': str(i), 'requestHeader':
                        'GET /people/current HTTP/1.1\r\nAuthorization: ' + credential + '\r\n',
                        'responseHeader': 'HTTP/1.1 200 OK\r\n'} for i, credential in enumerate(headers)]}
                return {'sendRequest': [{'responseHeader': 'HTTP/1.1 403 Forbidden\r\n'}]}
            run = SimpleNamespace(
                p={'selection': {'environment': 'fa-control-unit', 'origin': 'https://cardinal.test:9543'},
                   'journeys': {'auth': {'identity': {'path': '/people/current'}}}},
                out=root, rt=SimpleNamespace(capture=capture, mode=lambda *a, **k: None), engine=engine)
            install(run, 'stale-credential', root, arrivals)
            with self.assertRaises(InterruptedError):
                run.qualification_hook(run, {'id': 'control-a'}, {'id': 'native-ui-readback'})
            proof = json.loads((root / 'FAULT_OBSERVED.json').read_text())
            self.assertEqual(proof['beforeAppCount'], 2)
            self.assertEqual(proof['afterAppCount'], 2)
