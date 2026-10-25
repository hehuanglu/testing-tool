import contextlib,copy,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from zap_assessment.fe_authenticated_discovery import discover
from zap_assessment.fe_authenticated_contract import validate_journeys
from zap_assessment.product_cli import main

class WorkflowTests(unittest.TestCase):
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_discovery_and_status_are_offline_and_preserve_inventory_gaps(self):
        product=Path(__file__).resolve().parents[2]/'finalsource'
        with patch('zap_assessment.runtime.docker',side_effect=AssertionError('offline command touched runtime')):
            d=discover(product,'finalsource-fe-auth/1.0')
            self.assertFalse(d['runtimeObserved']);self.assertEqual(d['stage'],'source-only');self.assertGreaterEqual(len(d['journeys']['responsibilities']),40)
            self.assertTrue(all(r['journeyIds'] or r['disposition']=='not-applicable' for r in d['journeys']['responsibilities']));self.assertEqual(len(d['journeys']['campaigns']),2)
            with tempfile.TemporaryDirectory() as td:
                f=Path(td)/'discovery.json';f.write_text(json.dumps(d))
                with contextlib.redirect_stdout(io.StringIO()) as result:self.assertEqual(main(['fe-authenticated','status','--discovery',str(f)]),0)
                self.assertEqual(json.loads(result.getvalue())['taskCompletion'],'partial')
    def test_unsupported_recipe_does_not_fallback(self):
        with self.assertRaisesRegex(ValueError,'unsupported'):discover(Path('/missing'),'unknown-auth/1.0')
    @unittest.skipUnless((Path(__file__).resolve().parents[2]/'finalsource').is_dir(), 'Optional product source is not bundled')
    def test_wrong_actor_or_missing_responsibility_rejects(self):
        d=discover(Path(__file__).resolve().parents[2]/'finalsource','finalsource-fe-auth/1.0')['journeys']
        b=copy.deepcopy(d);b['journeys'][0]['actorRef']='actor-c'
        with self.assertRaisesRegex(ValueError,'actor mismatch'):validate_journeys(b)
        b=copy.deepcopy(d);b['responsibilities'].pop(0)
        with self.assertRaisesRegex(ValueError,'responsibility'):validate_journeys(b)
    def test_unknown_track_never_reaches_bola(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'p.json';path.write_text(json.dumps({'track':'unknown-auth'}))
            with patch('zap_assessment.product_bola.execute',side_effect=AssertionError('unknown fell through to BOLA')):
                with self.assertRaises((SystemExit,ValueError,KeyError)):main(['run','--plan',str(path),'--selection',str(path),'--output',str(Path(td)/'out')])

if __name__=='__main__':unittest.main()
