import contextlib
import copy
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.product_scope import compact_results, reconcile
from zap_assessment.product_scope_cli import inspect_resume, load_work_state, main
from workflow_fixtures import inventory, operation, observed


class ResumeInputsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.inv=inventory(product='synthetic',environment='offline',scopeRevision='r1',assessmentId='a')
        self.context=dict(assessmentId='a',product='synthetic',environment='offline',scopeRevision='r1')
        self.inputs=dict(inventory=self.inv,observations={'pin':observed()},prerequisites={},operations=[operation()],history=[])
        self.working=dict(version=1,purpose='executable-working-inputs',reportIsProjection=True,**self.context)
        for key,value in self.inputs.items():
            self.save(key,value);self.working[key]=key+'.json'
        self.run=dict(assessmentContext=self.context,reportGeneration={'kind':'recomposition'},continuation=dict(workingInputs=self.working))
        self.path=self.save('RUN',self.run)

    def save(self,name,data):
        path=self.root/(name+'.json');path.write_text(json.dumps(data));return path

    def inspect(self):
        self.save('RUN',self.run)
        with patch('socket.socket',side_effect=AssertionError('no traffic')):
            return inspect_resume(self.path)

    def test_compact_report_points_to_valid_private_working_inputs(self):
        result=self.inspect()
        self.assertEqual(result['status'],'working-inputs-available')
        self.assertIn('report-projection-not-executable',[d['code'] for d in result['diagnostics']])
        self.assertEqual([r['status'] for r in result['inputs']],['available']*5)
        self.assertNotIn('ownerChanged',json.dumps(result))
        self.assertIn('revalidate',result['readiness'])

    def test_missing_contract_is_hint_only_and_never_guesses_filenames(self):
        self.run['continuation']={};self.run['privateWorkingDirectory']=str(self.root)
        result=self.inspect();self.assertEqual(result['status'],'missing-inputs')
        self.assertFalse(result['inputs']);self.assertEqual(result['privateWorkingDirectoryHint'],str(self.root))
        self.assertIn('working-inputs-not-supplied',[d['code'] for d in result['diagnostics']])

    def test_missing_file_context_and_schema_conflicts_are_specific(self):
        self.working['operations']='absent.json'
        result=self.inspect();self.assertEqual(result['inputs'][3]['status'],'missing-or-nonregular-file')
        self.working['operations']='operations.json'
        for key in ('product','environment','scopeRevision','assessmentId'):
            self.working[key]='different'
            result=self.inspect()
            self.assertIn(dict(code='working-input-context-conflict',field=key),result['diagnostics'])
            self.assertNotEqual(result['status'],'working-inputs-available')
            self.working[key]=self.context[key]
        bad=dict(self.inv,environment='other');self.save('inventory',bad)
        self.assertEqual(self.inspect()['inputs'][0]['status'],'schema-or-context-conflict')
        self.save('inventory',self.inv);self.save('observations',[])
        self.assertEqual(self.inspect()['inputs'][1]['status'],'schema-or-context-conflict')

    def test_private_working_run_pointers_and_empty_collections(self):
        self.save('private-run',self.inputs)
        for key in self.inputs:self.working[key]=dict(path='private-run.json',pointer='/'+key)
        self.assertEqual(self.inspect()['status'],'working-inputs-available')
        self.run['privateState']=self.inputs
        for key in self.inputs:self.working[key]=dict(pointer='/privateState/'+key)
        self.assertEqual(self.inspect()['status'],'working-inputs-available')
        self.working['history']=dict(pointer='/privateState/missing')
        self.assertEqual(self.inspect()['inputs'][4]['status'],'unresolved-pointer')

    def test_untrusted_command_module_and_symlink_are_only_data(self):
        for ref in ('$(touch SHOULD-NOT-EXIST)', 'import arbitrary_module', 'module.py'):
            self.working['inventory']=ref
            result=self.inspect();self.assertNotEqual(result['status'],'working-inputs-available')
            self.assertFalse((self.root/'SHOULD-NOT-EXIST').exists())
        link=self.root/'link.json';link.symlink_to(self.root/'inventory.json')
        self.working['inventory']='link.json'
        self.assertEqual(self.inspect()['inputs'][0]['status'],'missing-or-nonregular-file')

    def test_private_path_can_be_explicitly_redacted(self):
        self.working['inventory']=dict(unavailable=True,reason='shared outside workspace')
        result=self.inspect();self.assertEqual(result['inputs'][0]['status'],'unavailable')
        self.assertEqual(result['status'],'missing-inputs')

    def test_previous_rejects_report_with_actionable_inspect_message_but_accepts_working_run(self):
        with self.assertRaisesRegex(ValueError,'report-projection-not-executable.*inspect-resume'):
            load_work_state(self.inv,{}, {},previous=[self.path])
        saved=dict(scope={k:self.inv[k] for k in ('productLocation','track','environment')},inventory=self.inv,
            observations=self.inputs['observations'],operations=self.inputs['operations'],prerequisites={},actionHistory=[])
        private=self.save('private',saved)
        loaded=load_work_state(self.inv,{}, {},previous=[private])
        self.assertEqual(loaded[0],self.inputs['observations'])
        saved['inventory']=copy.deepcopy(self.inv);saved['inventory']['cases'][0].pop('evidenceRefs');self.save('private',saved)
        with self.assertRaisesRegex(ValueError,'report-projection-not-executable'):load_work_state(self.inv,{}, {},previous=[private])

    def test_inspect_cli_outside_repo_is_read_only_and_never_returns_secrets(self):
        self.inputs['operations'][0].update(token='secret-canary',raw={'value':'private-raw-canary'})
        self.save('operations',self.inputs['operations'])
        before={p.name:p.read_bytes() for p in self.root.iterdir()}
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(['inspect-resume','--run',str(self.path)]),0)
        self.assertNotIn('canary',output.getvalue());self.assertEqual(before,{p.name:p.read_bytes() for p in self.root.iterdir()})
        script=Path(__file__).resolve().parents[1]/'scripts/product_assessment.py'
        self.assertTrue(script.is_file())
        result=subprocess.run([sys.executable,'-B',str(script),'scope','inspect-resume','--run',str(self.path)],cwd=self.root,capture_output=True,text=True,timeout=15)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'],'working-inputs-available')

    def test_checkpoint_without_new_metadata_remains_saveable(self):
        rec=reconcile(self.inv,{}, {})
        result=compact_results(self.root/'reports',dict(operations=[],continuation=dict(status='checkpointed')),[],rec)
        inspected=inspect_resume(self.root/'reports/RUN.json')
        self.assertEqual(result['taskCompletion'],'partial');self.assertEqual(inspected['status'],'missing-inputs')

    def test_next_work_context_mismatch_rejects_before_any_dispatch(self):
        from test_question_evidence import scope,assessment
        s=scope();s.update(assessmentId='a',product='synthetic',environment='offline')
        self.save('scope',s)
        # Unrelated historical finding joins need no fabricated ALERTS objects
        # when next-work only asks for current question evidence/planning.
        a=assessment();a['mappings']=[dict(findingId='historical-finding',criterionId='setting',certainty='uncertain',rationale='Historical context only')]
        self.save('assessment',a)
        run=dict(self.run,operations=self.inputs['operations']);self.save('working',run)
        args=['next-work']
        for key,name in [('inventory','inventory'),('observations','observations'),('prerequisites','prerequisites'),('security-scope','scope'),('scope-assessment','assessment'),('run','working')]:
            args+=['--'+key,str(self.root/(name+'.json'))]
        with patch('zap_assessment.product_cli.main',side_effect=AssertionError('no dispatch')),contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args),0)
        self.assertEqual(json.loads(output.getvalue())['residualReviewStatus'],'not-supplied')
        self.save('inventory',dict(self.inv,scopeRevision='wrong'))
        with self.assertRaisesRegex(ValueError,'inventory scopeRevision'):main(args)

    def test_assessment_path_and_coverage_slug_use_retained_namespaces(self):
        inv=copy.deepcopy(self.inv);inv['product']='/synthetic/source'
        self.context['product']='/synthetic/source';self.working['product']='/synthetic/source'
        self.run['responsibilityInventory']=copy.deepcopy(inv);self.save('inventory',inv)
        self.assertEqual(self.inspect()['status'],'working-inputs-available')
        inv['cases'][0]['coverageContext']['product']='unrelated-slug';self.save('inventory',inv)
        result=self.inspect()
        self.assertIn(dict(code='working-input-file-context-conflict',input='inventory',field='caseBoundary'),result['diagnostics'])
