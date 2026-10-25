"""Regression inputs built independently of the coverage predicate."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

PACKAGE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p0coverage', PACKAGE / 'scripts/finalsource_p0_coverage.py')
coverage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(coverage)


class HistoricalCoverageRegression(unittest.TestCase):
    def fixture(self, root, status, body, *, content_type='application/json'):
        def write(name, value):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(value))
        write('native-browser-a2/controls/current-openapi.json', {
            'response': {'body': json.dumps({'paths': {'/api/v1/accounts/{id}': {'get': {}}}})}})
        write('guard-only/plan.json', {'mode': 'delegated', 'actor': 'A'})
        write('guard-only/outcome.json', {'executionStatus': 'completed'})
        write('guard-only/operations.json', [])
        write('guard-only/messages.json', {'messages': [{
            'id': 'independent-guard-only',
            'requestHeader': 'GET http://127.0.0.1:18080/api/v1/accounts/1 HTTP/1.1\r\n',
            'responseHeader': f'HTTP/1.1 {status} fixture\r\nContent-Type: {content_type}\r\n',
            'responseBody': body}]})

    def test_guard_only_403_never_application_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 403, '{"guardGenerated":true}')
            coverage.build(root)
            row = next(r for r in json.loads((root / 'coverage.json').read_text())['rows']
                       if r['actor'] == 'A')
            self.assertNotEqual(row['status'], 'verified', 'Guard response is not application evidence')

    def test_auth_loss_and_html_200_are_observations_without_oracle_pass(self):
        for status, body, media in [(401, '{"authLost":true}', 'application/json'),
                                    (200, '<html>Login</html>', 'text/html')]:
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, status, body, content_type=media)
                summary = coverage.build(root)
                rows = json.loads((root / 'coverage.json').read_bytes())['rows']
                row = next(r for r in rows if r['actor'] == 'A')
                self.assertTrue(row['observed'])
                self.assertTrue(row['requested'])
                self.assertFalse(row['techniqueExecuted'])
                self.assertEqual(row['oracleResult'], 'inconclusive')
                self.assertEqual(summary['actorRows'], 3)

    def test_published_bundle_requires_external_fresh_output_and_stays_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / 'legacy', Path(tmp) / 'candidate'
            self.fixture(root, 403, '{"guardGenerated":true}')
            (root / 'manifest.json').write_text('{}')
            before = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            with self.assertRaisesRegex(ValueError, 'immutable'):
                coverage.build(root)
            coverage.build(root, output)
            after = {str(p.relative_to(root)): p.read_bytes() for p in root.rglob('*') if p.is_file()}
            self.assertEqual(before, after)
            with self.assertRaisesRegex(ValueError, 'fresh'):
                coverage.build(root, output)
            with self.assertRaisesRegex(ValueError, 'outside'):
                coverage.build(root, root / 'nested')

    def test_failed_or_policy_deviating_phase_does_not_erase_observation(self):
        for field in ('failed', 'deviation'):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                self.fixture(root, 200, '{"data":{"id":1}}')
                if field == 'failed':
                    (root / 'guard-only/outcome.json').write_text('{"executionStatus":"failed"}')
                else:
                    (root / 'guard-only/policy-review.json').write_text('{"conformance":false}')
                coverage.build(root)
                row = next(r for r in json.loads((root / 'coverage.json').read_bytes())['rows'] if r['actor'] == 'A')
                self.assertTrue(row['observed'])
                self.assertEqual(row['oracleResult'], 'inconclusive')
                self.assertIn('policy_deviation' if field == 'deviation' else 'phase_not_completed_or_reuse_unproven', row['reasonCodes'])

    def test_active_lifecycle_is_not_technique_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 200, '{}')
            (root / 'guard-only/operations.json').write_text(json.dumps([
                {'kind': 'activeScan', 'terminal': True, 'path': '/api/v1/accounts/1', 'operationId': 'operation-1'}]))
            coverage.build(root)
            row = next(r for r in json.loads((root / 'coverage.json').read_bytes())['rows'] if r['actor'] == 'A')
            self.assertTrue(row['activeLifecycleCompleted'])
            self.assertFalse(row['techniqueExecuted'])
            self.assertIn('sink_unproven', row['reasonCodes'])

    def test_symbolic_resource_ids_and_static_route_precedence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.fixture(root, 200, '{}')
            schema = {'paths': {'/api/v1/accounts/{id}': {'get': {}}, '/api/v1/accounts/options': {'get': {}}}}
            (root / 'native-browser-a2/controls/current-openapi.json').write_text(json.dumps({'response': {'body': json.dumps(schema)}}))
            f = root / 'guard-only/messages.json'
            message = json.loads(f.read_bytes())['messages'][0]
            messages = []
            for path in ('wallet-uuid', 'options'):
                messages.append({**message, 'requestHeader': f'GET http://127.0.0.1:18080/api/v1/accounts/{path} HTTP/1.1\r\n'})
            f.write_text(json.dumps({'messages': messages}))
            coverage.build(root)
            rows = [r for r in json.loads((root / 'coverage.json').read_bytes())['rows'] if r['actor'] == 'A']
            self.assertEqual([len(r['observations']) for r in rows], [1, 1])

    def test_pilot_coverage_branch_reuses_offline_collector_without_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / 'source', Path(tmp) / 'output'
            self.fixture(root, 200, '{"password":"body-canary-not-for-output"}')
            f = root / 'guard-only/messages.json'
            value = json.loads(f.read_bytes())
            value['messages'][0]['requestHeader'] = 'GET http://127.0.0.1:18080/api/v1/accounts/abc?token=query-canary HTTP/1.1\r\n'
            f.write_text(json.dumps(value))
            result = subprocess.run([sys.executable, str(PACKAGE / 'scripts/finalsource_p0.py'),
                                     'coverage', str(root), '--output', str(output)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertFalse(json.loads(result.stdout)['securityApproval'])
            emitted = b''.join(p.read_bytes() for p in output.iterdir()) + result.stdout
            self.assertNotIn(b'query-canary', emitted)
            self.assertNotIn(b'body-canary-not-for-output', emitted)


if __name__ == '__main__':
    unittest.main()
