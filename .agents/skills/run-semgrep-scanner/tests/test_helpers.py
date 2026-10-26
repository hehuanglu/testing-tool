"""Synthetic bookkeeping/collector cases; no product assessment or external network."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_report_links import check
from record_round import capture, summarize, scrub
from report_records import draft, question, write_new
from select_rules import catalog


class Links(unittest.TestCase):
    def setUp(self):
        self.run = json.loads((ROOT / 'examples/reporting/RUN.example.json').read_text())
        self.alerts = json.loads((ROOT / 'examples/reporting/ALERTS.example.json').read_text())

    def verify(self):
        return check(self.run, self.alerts)

    def recount(self):
        from collections import Counter
        findings = self.alerts['findings']
        summary = self.alerts['summary']
        summary.update(finding_records=len(findings),
            by_source=dict(Counter(f['source'] for f in findings)),
            by_native_severity=dict(Counter(f['native_severity'] for f in findings if f['native_severity'] is not None)),
            by_triage=dict(Counter(f['triage']['status'] for f in findings)),
            native_severity_null_records=sum(f['native_severity'] is None for f in findings))

    def retain(self, fids):
        self.alerts['findings'] = [f for f in self.alerts['findings'] if f['id'] in fids]
        mids = {mid for f in self.alerts['findings'] for mid in f['manual_review_ids']}
        self.run['manual_reviews'] = [m for m in self.run['manual_reviews'] if m['id'] in mids]
        for q in self.run['questions']:
            q['manual_review_ids'] = [m for m in q['manual_review_ids'] if m in mids]
        for r in self.run['rounds']:
            r['finding_ids'] = [f for f in r['finding_ids'] if f in fids]
        self.run['coverage']['inventory_candidate_reviews'] = []
        self.run['coverage']['untriaged_finding_ids'] = [f for f in self.run['coverage']['untriaged_finding_ids'] if f in fids]
        self.recount()

    def test_mixed_support_example(self):
        self.assertEqual([], self.verify())

    def test_manual_round_contamination(self):
        self.run['rounds'][0]['finding_ids'].append('F-04')
        self.assertTrue(any('only/exactly' in e for e in self.verify()))

    def test_manual_only(self):
        self.retain({'F-04'})
        self.run['rounds'] = []
        for q in self.run['questions']: q['round_ids'] = []
        self.alerts['summary']['native_matches_by_round'] = {}
        self.assertEqual([], self.verify())

    def test_native_only(self):
        self.retain({'F-01'})
        finding = self.alerts['findings'][0]
        finding['manual_review_ids'] = []
        finding['evidence'] = [e for e in finding['evidence'] if e['provenance'] == 'semgrep']
        self.run['manual_reviews'] = []
        for q in self.run['questions']: q['manual_review_ids'] = []
        self.assertEqual([], self.verify())

    def test_many_rounds(self):
        second = copy.deepcopy(self.run['rounds'][0]); second.update(id='R-02',finding_ids=['F-01'])
        self.run['rounds'].append(second)
        finding=self.alerts['findings'][0]
        occurrence=copy.deepcopy(finding['occurrences'][0]);occurrence.update(id='O-RETEST',round_id='R-02')
        finding['occurrences'].append(occurrence);finding['round_ids'].append('R-02')
        self.alerts['summary']['native_matches_by_round']['R-02']=3
        self.assertEqual([],self.verify())

    def test_partial_unreadable_counts(self):
        r=self.run['rounds'][0];r['status']='partial'
        r['counts']['native_matches']=None;r['errors']=None
        self.alerts['summary']['native_matches_by_round']['R-01']=None
        self.assertEqual([],self.verify())

    def test_source_change_retest_does_not_rewrite_prior_evidence(self):
        previous=copy.deepcopy(self.alerts['findings'][0]['evidence'])
        self.run['source_states'].append(dict(id='SS-02', roots=['synthetic/'],
            revision=None,dirty=True,observed_at=None,notes='Synthetic source/filter change; no fixed verdict.'))
        retest=copy.deepcopy(self.run['rounds'][0])
        retest.update(id='R-02', source_state_id='SS-02', finding_ids=[], errors=[])
        retest['counts'].update(native_matches=0,scanned_files=1)
        retest['exclusions']=['Synthetic rule/path/ignore change requires review before fixed claim.']
        self.run['rounds'].append(retest)
        self.alerts['summary']['native_matches_by_round']['R-02']=0
        self.assertEqual([],self.verify())
        self.assertEqual(previous,self.alerts['findings'][0]['evidence'])

    def test_policy_dependency_does_not_default_to_not_applicable(self):
        q=self.run['questions'][1]
        q['result']=dict(source_fact='Synthetic material and consumers were reviewed.',
            policy_dependency='Need the session persistence requirement and authority.',
            remaining_source_steps=['Read logout writer; independent step remains feasible.'],
            external_step='Confirm only the persistence policy needed for this claim.')
        self.assertEqual([],self.verify())
        self.assertEqual('blocked',q['status'])
        self.assertTrue(q['result']['remaining_source_steps'])

    def test_source_state_mismatch(self):
        self.run['source_states'].append(dict(id='SS-OTHER'))
        self.alerts['findings'][0]['evidence'][0]['source_state_id']='SS-OTHER'
        self.assertTrue(any('differs from operation' in e for e in self.verify()))

    def test_broken_manual_backlink(self):
        self.run['manual_reviews'][0]['evidence_ids']=[]
        self.assertTrue(any('evidence backlink' in e for e in self.verify()))

    def test_duplicate_and_unknown_ids(self):
        self.run['questions'].append(copy.deepcopy(self.run['questions'][0]))
        self.alerts['findings'][0]['question_ids'].append('MISSING')
        errors=self.verify()
        self.assertTrue(any('duplicate id' in e for e in errors))
        self.assertTrue(any('unknown reference' in e for e in errors))

    def test_candidate_outside_native_results(self):
        self.run['coverage']['inventory_candidate_reviews'][0]['native_result_index']=3
        self.assertTrue(any('outside round results' in e for e in self.verify()))

    def test_zero_targets_not_completed(self):
        self.run['rounds'][0]['counts']['scanned_files']=0
        self.assertTrue(any('zero scanned' in e for e in self.verify()))

    def test_no_mutation(self):
        before=copy.deepcopy((self.run,self.alerts))
        self.verify()
        self.assertEqual(before,(self.run,self.alerts))

    def test_manual_native_severity_separate(self):
        self.alerts['findings'][-1]['native_severity']='WARNING'
        self.assertTrue(any('manual-only native_severity' in e for e in self.verify()))


class Collector(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def native(self,data):
        path=self.directory/'native.json'
        path.write_text(json.dumps(data));return summarize(path)

    def test_missing_and_broken_native(self):
        for content in (None,'{bad','[]'):
            path=self.directory/'broken.json'
            if content is not None: path.write_text(content)
            record=summarize(path)
            self.assertIsNone(record['counts']['native_matches'])
            self.assertIsNone(record['errors'])

    def test_partial_preserves_null(self):
        record=self.native(dict(results=[{}],errors=[dict(type='Timeout',message='SENSITIVE')],
            skipped_rules=[dict(rule_id='synthetic-rule',details='SENSITIVE')],time=dict(rules=[1,2])))
        self.assertEqual(1,record['counts']['native_matches'])
        self.assertEqual(1,len(record['timeouts']))
        self.assertIsNone(record['counts']['scanned_files'])
        self.assertIsNone(record['counts']['rules_executed'])
        self.assertEqual('synthetic-rule',record['skipped_rules'][0]['rule_id'])
        self.assertNotIn('SENSITIVE',json.dumps(record))

    def test_zero_and_unsupported(self):
        record=self.native(dict(results=[],errors=[],paths=dict(scanned=[],skipped=[])))
        self.assertEqual(0,record['counts']['scanned_files'])
        self.assertTrue(any('not a clean' in d for d in record['diagnostics']))
        self.assertIsNone(record['counts']['candidate_files'])

    def test_review_group_preserves_occurrences(self):
        results=[dict(check_id=rule,path='file.ts',start=dict(line=1),end=dict(line=1),extra=dict(message='PRIVATE',lines='PRIVATE',severity='WARNING')) for rule in ('rule-a','rule-b')]
        record=self.native(dict(results=results,version='1.176.0',engine_requested='OSS'))
        self.assertEqual(2,record['counts']['native_matches'])
        self.assertEqual([0,1],record['review_groups'][0]['native_result_indexes'])
        self.assertEqual(['rule-a','rule-b'],[v['rule_id'] for v in record['native_results']])
        self.assertIsNone(record['engine'])
        self.assertNotIn('PRIVATE',json.dumps(record))

    def test_redaction(self):
        value=scrub(dict(command=['scan','--token','VALUE','password=VALUE','CUSTOM'],targets=['CUSTOM']),['CUSTOM'])
        self.assertNotIn('VALUE',json.dumps(value));self.assertNotIn('CUSTOM',json.dumps(value))

    def test_capture_exit_and_private_raw(self):
        cwd=self.directory/'source';cwd.mkdir()
        spec=dict(id='R-TEST',cwd=str(cwd),targets=['.'],argv=[sys.executable,'-c',
            'import pathlib,sys;pathlib.Path(sys.argv[1]).write_text(\'{"results":[],"errors":[],"paths":{"scanned":[]}}\');raise SystemExit(7)',
            '{native_json}'],privacy=dict(metrics='off'))
        out=self.directory/'capture'
        record=capture(spec,out)
        self.assertEqual(7,record['exit_code'])
        self.assertIsNone(record['status'])
        self.assertTrue(record['started_at'] and record['finished_at'])
        self.assertEqual(0o600,(out/'native.json').stat().st_mode & 0o777)
        with self.assertRaises(FileExistsError):capture(spec,out)
        with self.assertRaises(ValueError):capture(spec,cwd/'inside')

    def test_no_default_judgments_or_overwrite(self):
        run,alerts=draft('TEST')
        self.assertIsNone(run['status']);self.assertIsNone(alerts['summary']['unique_issues'])
        q=question('Q')
        for field in ('expectation','status','result','closure_condition'):self.assertIsNone(q[field])
        target=self.directory/'RUN.json';write_new(target,run)
        with self.assertRaises(FileExistsError):write_new(target,run)

    def test_catalog_projection_limits(self):
        entries=catalog(ROOT)
        self.assertEqual(85,len(entries));self.assertEqual(85,len({e['id'] for e in entries}))
        compose=next(e for e in entries if e['id']=='config-compose-privileged')
        self.assertIn('compose.yaml',compose['path_limits_yaml'])
        self.assertEqual(['CFG-02'],compose['base_ids'])


if __name__=='__main__': unittest.main()
