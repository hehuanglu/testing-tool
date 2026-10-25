import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.fe_anonymous_contract import validate_journeys,canonical
from zap_assessment.fe_anonymous_discovery import discover
from zap_assessment.fe_anonymous_browser import FEBrowser
from zap_assessment.product_handoff import compose_handoff

class OfflineTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_source_only_never_calls_runtime(self):
        with patch('zap_assessment.runtime.docker',side_effect=AssertionError('network in source-only')):
            d=discover(Path(__file__).resolve().parents[2]/'finalsource','finalsource-fe/1.0')
        self.assertFalse(d['runtimeObserved']);self.assertEqual(d['stage'],'source-only')
        self.assertGreater(len(d['journeys']['responsibilities']),len(d['journeys']['journeys']))
    def test_stale_profile_rejected_before_session(self):
        with tempfile.TemporaryDirectory() as d:
            browser=FEBrowser()
            with patch.object(browser,'command',side_effect=AssertionError('stale profile reached driver')):
                with self.assertRaisesRegex(ValueError,'stale browser profile'):browser.start(Path(d))
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_unknown_journey_and_provenance_rejected(self):
        d=discover(Path(__file__).resolve().parents[2]/'finalsource','finalsource-fe/1.0')['journeys']
        bad=copy.deepcopy(d);bad['responsibilities'][0]['journeyIds']=['unknown']
        with self.assertRaisesRegex(ValueError,'unknown responsibility'):validate_journeys(bad)
        bad=copy.deepcopy(d);bad['journeys'][0]['provenance']=['invented']
        with self.assertRaisesRegex(ValueError,'journey provenance'):validate_journeys(bad)
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_no_arbitrary_document_js(self):
        d=discover(Path(__file__).resolve().parents[2]/'finalsource','finalsource-fe/1.0')['journeys'];d['journeys'][0]['steps'][0]['script']='return true'
        with self.assertRaises(Exception):validate_journeys(d)
    def test_backend_track_registry_not_broadened(self):
        from zap_assessment.product_workflow import TRACKS,FE_TRACKS
        self.assertEqual(TRACKS,('be-anonymous','be-authenticated','bola-ownership'));self.assertEqual(FE_TRACKS,('fe-anonymous','fe-authenticated'))

if __name__=='__main__':unittest.main()

class CommonEntryTests(unittest.TestCase):
    def test_fe_only_handoff_does_not_require_backend_tracks(self):
        import hashlib
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);p=root/'source.json'
            statuses=dict(executionStatus='completed',evidenceStatus='complete',securityVerdict='requires-triage',cleanupStatus='clean',gateDecision='review_required')
            p.write_text(json.dumps({'schemaVersion':'pm-alerts/1.0','product':{'location':'/owned'},'run':'fe-selected',**statuses,'scope':{'track':'fe-anonymous','taskCompletion':'partial'},'alerts':[]}))
            row={'track':'fe-anonymous','path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'units':['public-ui'],'retentionReason':'current selected subset'}
            result=compose_handoff({'tracks':['fe-anonymous'],'runId':'composed','coverageNote':'FE only, backend not executed','runs':[row]},root/'handoff')
            self.assertEqual(result['scope']['tracks'],['fe-anonymous']);self.assertFalse((root/'handoff/be-anonymous').exists());self.assertEqual(result['executionStatus'],'completed')
            with self.assertRaisesRegex(ValueError,'duplicate lineage'):
                compose_handoff({'tracks':['fe-anonymous'],'runId':'duplicate','coverageNote':'must reject','runs':[row,row]},root/'duplicate')
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_common_status_is_offline(self):
        import contextlib,io
        from zap_assessment.product_cli import main
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);candidate=discover(Path(__file__).resolve().parents[2]/'finalsource','finalsource-fe/1.0');f=root/'candidate.json';f.write_text(json.dumps(candidate))
            with patch('zap_assessment.runtime.docker',side_effect=AssertionError('status started runtime')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['fe-anonymous','status','--discovery',str(f)]),0)
            self.assertEqual(json.loads(output.getvalue())['executionStatus'],'not-run')
