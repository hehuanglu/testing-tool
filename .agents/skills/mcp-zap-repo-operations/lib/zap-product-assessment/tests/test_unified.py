"""W9 pure graph/status counterexamples. These do not create browser evidence."""
from copy import deepcopy
import importlib.util
import tempfile
from pathlib import Path
import unittest
from zap_assessment.contracts import ROOT, digest
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.unified_contract import TRACKS, REQUIRED, make_plan, validate_plan, binding_for, aggregate
from zap_assessment.unified_binding import validate_context, bind_fixture, docker_labels
from zap_assessment.unified_verification import verify_unified_bundle, identity_shape, expected_journal_kinds

spec = importlib.util.spec_from_file_location('w9_test_runner', ROOT / 'scripts/w9_unified_campaign.py')
runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)


def plan(seed=9101, ident='1' * 32, adapter='finalsource-shaped', reverse=False):
    return make_plan('w9-' + ident, seed, adapter, reverse, 'sha256:' + '2' * 64, {'test': '3' * 64})


def status_rows():
    # Only aggregation unit data. No child bundles, runtime or operational proof.
    results = {'session': {'executionStatus': 'completed', 'scope': 'session-spike'},
               'api': {'syntheticContractStatus': 'pass'},
               'ui': {'functionalVerdict': 'pass', 'requiredSteps': 13, 'observedSteps': 13},
               'active-vulnerable': {'G9Synthetic': 'pass'}, 'active-fixed': {'G9Synthetic': 'pass'}}
    return [{'phase': t, 'result': {'securityVerdict': 'inconclusive', **results[t]}} for t in TRACKS]


class UnifiedTests(unittest.TestCase):
    def test_volume_outage_is_not_assumed_absent(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        failed=SimpleNamespace(returncode=1,stdout='')
        with patch.object(runner.subprocess,'run',return_value=failed),self.assertRaises(EvidenceInvalid):runner.inspect_volume('owned-volume')

    def test_namespace_observation_requires_docker_success(self):
        from unittest.mock import patch
        from types import SimpleNamespace
        with patch.object(runner.subprocess,'run',return_value=SimpleNamespace(returncode=1,stdout='')),self.assertRaises(EvidenceInvalid):runner.namespace_snapshot('w9-'+'a'*32)

    def test_browser_uses_dedicated_startup_context_once(self):
        from zap_assessment.ui_webdriver import WebDriver
        from unittest.mock import patch
        driver=WebDriver();answers=[{'sessionId':'unit-private-session','capabilities':{'browserName':'firefox','browserVersion':'153.5.0'}},None,['initial'],None,'complete',{'handle':'unit-context'},None]
        with patch.object(driver,'command',side_effect=answers) as call:
            result=driver.start(Path('/unit-profile'))
        self.assertEqual(call.call_args_list[5].args,('POST','/window/new',{'type':'tab'}))
        self.assertEqual(call.call_args_list[6].args,('POST','/window',{'handle':'unit-context'}))
        self.assertNotIn('unit-private-session',str(result));self.assertNotIn('unit-context',str(result))

    def test_idle_browser_preconnect_does_not_block_navigation(self):
        import http.client,socket,threading
        from http.server import BaseHTTPRequestHandler
        from zap_assessment.ui_browser_worker import OwnedUIServer
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                self.send_response(200);self.send_header('Content-Length','2');self.end_headers();self.wfile.write(b'ok')
        server=OwnedUIServer(('127.0.0.1',0),Handler);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        idle=socket.create_connection(server.server_address);client=http.client.HTTPConnection(*server.server_address,timeout=1)
        try:
            client.request('GET','/ui');response=client.getresponse();self.assertEqual((response.status,response.read()),(200,b'ok'))
        finally:client.close();idle.close();server.shutdown();server.server_close();thread.join(2)

    def test_normal_plan_has_required_browser_and_graph(self):
        p = plan(); self.assertEqual(p['requiredTracks'], list(REQUIRED))
        for i, row in enumerate(p['tracks']): self.assertEqual(row['dependsOn'], list(TRACKS[:i]))
        self.assertFalse(p['productRequestsPermitted']); self.assertFalse(p['securityApproval'])

    def test_missing_browser_cannot_amend_acceptance(self):
        for field in ('requiredTracks', 'tracks'):
            p = plan(); p[field] = [r for r in p[field] if (r if isinstance(r, str) else r['phase']) != 'ui']
            with self.assertRaises(EvidenceInvalid): validate_plan(p)

    def test_optional_browser_and_phase_reorder_rejected(self):
        p = plan(); p['tracks'][2]['required'] = False
        with self.assertRaises(EvidenceInvalid): validate_plan(p)
        p = plan(); p['tracks'].reverse()
        with self.assertRaises(EvidenceInvalid): validate_plan(p)

    def test_changed_actor_or_resource_is_not_same_scope(self):
        for key in ('actors', 'resources'):
            p = plan(); p['tracks'][1]['scope'][key].reverse()
            with self.assertRaises(EvidenceInvalid): validate_plan(p)

    def test_fresh_assessment_and_seed_change_bindings(self):
        a = plan(); b = plan(9102, '4' * 32, 'alternate-ledger', True)
        self.assertNotEqual(a['tracks'][1]['fixtureHash'], b['tracks'][1]['fixtureHash'])
        self.assertNotEqual(binding_for(a, 'ui'), binding_for(b, 'ui'))
        self.assertNotEqual(a['tracks'][3]['scope']['actors'], a['tracks'][1]['scope']['actors'])

    def test_phase_bindings_are_not_interchangeable(self):
        p = plan(); a = binding_for(p, 'api'); b = binding_for(p, 'ui')
        self.assertNotEqual(a, b); self.assertEqual(a['planHash'], b['planHash'])
        with self.assertRaises(ValueError): validate_context(a, {'ui'})

    def test_context_requires_all_fields_and_fresh_epoch_policy(self):
        original = binding_for(plan(), 'api')
        for mutate in (lambda x: x.pop('planHash'), lambda x: x.update({'epochPolicy': 'resume-persisted-token'}),
                       lambda x: x.update({'assessmentId': '../foreign'}), lambda x: x.update({'phase': None})):
            c = deepcopy(original); mutate(c)
            with self.assertRaises(ValueError): validate_context(c, {'api'})

    def test_fixture_mismatch_fails_before_runtime(self):
        c = binding_for(plan(), 'api')
        with self.assertRaises(ValueError): bind_fixture(c, '0' * 64)
        bind_fixture(c, c['fixtureHash']); self.assertEqual(docker_labels(None), [])
        self.assertIn('zpa.plan=' + c['planHash'], docker_labels(c))

    def test_all_functional_statuses_still_no_operational_pass(self):
        result = aggregate(plan(), status_rows(), True)
        self.assertEqual(result['orchestrationVerdict'], 'verified')
        self.assertEqual(result['G10Operational'], 'blocked'); self.assertEqual(result['gateDecision'], 'block')
        self.assertFalse(result['R1R2Admission'])

    def test_missing_required_track_never_all_pass(self):
        for phase in TRACKS:
            result = aggregate(plan(), [r for r in status_rows() if r['phase'] != phase], True)
            self.assertEqual(result['orchestrationVerdict'], 'blocked'); self.assertIn(phase, result['missingRequiredTracks'])

    def test_api_failure_not_overridden_by_active_success(self):
        rows = status_rows(); rows[1]['result']['syntheticContractStatus'] = 'fail'; rows[1]['result']['securityVerdict'] = 'fail'
        r = aggregate(plan(), rows, True)
        self.assertEqual(r['orchestrationVerdict'], 'blocked'); self.assertEqual(r['securityVerdict'], 'fail')

    def test_ui_functional_failure_not_overridden_by_api(self):
        rows = status_rows(); rows[2]['result']['functionalVerdict'] = 'fail'
        self.assertEqual(aggregate(plan(), rows, True)['orchestrationVerdict'], 'blocked')

    def test_ui_secret_failure_survives_all_functional_tracks(self):
        rows = status_rows(); rows[0]['result']['securityVerdict'] = rows[2]['result']['securityVerdict'] = 'fail'
        r = aggregate(plan(), rows, True); self.assertEqual(r['securityVerdict'], 'fail'); self.assertEqual(r['gateDecision'], 'block')

    def test_missing_poststate_and_unknown_cleanup_block(self):
        r = aggregate(plan(), status_rows(), False); self.assertIn('post-state', r['missingRequiredTracks']); self.assertEqual(r['evidenceStatus'], 'incomplete')
        self.assertEqual(aggregate(plan(), status_rows(), True, cleanup_clean=False)['cleanupStatus'], 'quarantined')

    def test_interrupted_never_becomes_complete(self):
        r = aggregate(plan(), status_rows(), True, interrupted=True)
        self.assertEqual(r['executionStatus'], 'interrupted'); self.assertEqual(r['evidenceStatus'], 'incomplete'); self.assertEqual(r['orchestrationVerdict'], 'blocked')

    def test_duplicate_or_unknown_tracks_rejected(self):
        for rows in (status_rows() + [status_rows()[0]], [{'phase': 'foreign', 'result': {}}]):
            with self.assertRaises(EvidenceInvalid): aggregate(plan(), rows, True)

    def test_recovery_refuses_foreign_labels_or_images(self):
        p = plan(); s = p['tracks'][3]; pin = digest(p)
        i = {'Id': 'a' * 64, 'Name': '/' + s['containerName'], 'Image': s['image'], 'Config': {'Labels': {
            'zpa.run': s['childRunId'], 'zpa.assessment': p['assessmentId'], 'zpa.phase': s['phase'], 'zpa.plan': pin}}}
        self.assertEqual(runner.verify_owned(i, s, p, pin), i['Id'])
        for key in ('zpa.run', 'zpa.assessment', 'zpa.phase', 'zpa.plan'):
            bad = deepcopy(i); bad['Config']['Labels'][key] = 'foreign'
            with self.assertRaises(EvidenceInvalid): runner.verify_owned(bad, s, p, pin)
        i['Image'] = 'sha256:' + '9' * 64
        with self.assertRaises(EvidenceInvalid): runner.verify_owned(i, s, p, pin)

    def test_recovery_refuses_borrowed_profile_mount(self):
        p = plan(); s = p['tracks'][2]; pin = digest(p)
        i = {'Id': 'a' * 64, 'Name': '/' + s['containerName'], 'Image': s['image'], 'Config': {'Labels': {
            'zpa.run': s['childRunId'], 'zpa.assessment': p['assessmentId'], 'zpa.phase': s['phase'], 'zpa.plan': pin}},
             'Mounts': [{'Destination': '/home/zap', 'Type': 'volume', 'Name': 'borrowed-profile'}]}
        with self.assertRaises(EvidenceInvalid): runner.verify_owned(i, s, p, pin)

    def test_poststate_replay_consumes_generator_without_claiming_runtime(self):
        from zap_assessment.business_fixture import generate_manifest
        from zap_assessment.business import expected_states, initial_state, transition
        from zap_assessment.ui_contract import ui_steps
        from zap_assessment.unified_verification import post_state
        from zap_assessment.contracts import canonical
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for phase in ('session', 'api', 'ui'):
                run_id = 'w6-w7-unit-' + phase; fixture = generate_manifest(run_id, 9101)
                if phase == 'api': state = list(expected_states(fixture))[-1][3]; observations = {'cases': [{'postState': state}]}
                else:
                    state = initial_state(fixture)
                    for step in ui_steps(fixture):
                        if 'case' in step: _, state = transition(fixture, state, step['case'])
                    observations = {'steps': [{'postState': state}]}
                folder = root / phase; folder.mkdir()
                for name, value in [('plan', {'runId': run_id}), ('fixture', fixture), ('observations', observations)]:
                    (folder / (name + '.json')).write_bytes(canonical(value))
            result = post_state(root)
            self.assertFalse(result['sameLiveProductDatabase']); self.assertEqual(len(result['branches']), 2)

    def test_external_pin_and_real_child_evidence_required(self):
        with tempfile.TemporaryDirectory() as path:
            for pin in (None, '0' * 64):
                with self.assertRaises(EvidenceInvalid): verify_unified_bundle(path, pin)

    def test_explicit_track_state_transitions(self):
        k = expected_journal_kinds(); self.assertEqual(k.count('track_intent'), 5); self.assertEqual(k.count('track_recorded'), 5)
        self.assertEqual(k[-2:], ['post_state_recorded', 'verifying'])


if __name__ == '__main__': unittest.main()
