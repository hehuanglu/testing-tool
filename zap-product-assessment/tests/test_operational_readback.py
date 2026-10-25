import copy
import json
from pathlib import Path
import tempfile
import unittest

from zap_assessment.active_questions import assess_question
from zap_assessment.discovery_handoff import clean
from zap_assessment.product_checks import check_pages
from zap_assessment.product_scope import reconcile, compact_results
from zap_assessment.result_readers import read_jsonl, collect_alerts
from zap_assessment.transport import Scanner


class OperationalReadbackTests(unittest.TestCase):
    def probe(self, rule='40018', stage='boundary', **kw):
        return dict(ruleId=rule, changed=True, application=True, identityValid=True,
                    stage=stage, resultRead=True, **kw)

    def test_sqli_cannot_close_selected_xss_and_open_work_survives_handoff(self):
        questions=[dict(id='sql',ruleIds=[40018]),dict(id='reflection',ruleIds=[40012])]
        answers=[assess_question(q,[self.probe()]) for q in questions]
        self.assertEqual([a['status'] for a in answers],['observed','open'])
        case=dict(caseId='update',evidenceRefs=['product source'],requiredEvidence=[a['unit'] for a in answers])
        inv=dict(productLocation='/test',track='be-authenticated',complete=True,cases=[case])
        obs={'update':dict(outcome='matched',resultRead=True,evidenceUnits=sum((a['evidenceUnits'] for a in answers),[]))}
        rec=reconcile(inv,obs,{})
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'result';compact_results(out,{}, {},rec)
            run=json.loads((out/'RUN.json').read_text())
            self.assertEqual(run['taskCompletion'],'partial')
            self.assertEqual(run['notPerformed'][0]['caseId'],'update')
            self.assertTrue(run['nextSteps'])

    def test_inapplicability_is_local_and_missing_fixture_is_not_na(self):
        q=dict(id='reflection',disposition='not-applicable',basis='Only JSON response; no browser execution sink in this question')
        self.assertEqual(assess_question(q,[])['status'],'not-applicable')
        self.assertEqual(assess_question(dict(id='sql',ruleIds=[40018]),[])['status'],'open')
        with self.assertRaises(ValueError):assess_question({**q,'gapKind':'fixture'},[])

    def test_grouped_technique_keeps_an_unprobed_text_field_open(self):
        q=dict(id='reflection',ruleIds=[40012],fields=['title','description'],minimumStage='processing')
        p=self.probe(rule='40012',stage='processing',field='title')
        self.assertEqual(assess_question(q,[p])['missingFields'],['description'])
        self.assertEqual(assess_question(q,[p,{**p,'field':'description'}])['status'],'observed')

    def test_ack_and_overwritten_snapshot_do_not_prove_variant_persistence(self):
        q=dict(id='store-variant',ruleIds=[40018],minimumStage='persistence')
        self.assertEqual(assess_question(q,[self.probe(stage='processing')])['status'],'open')
        self.assertEqual(assess_question(q,[self.probe(stage='final-snapshot')])['status'],'open')
        self.assertEqual(assess_question(q,[self.probe(stage='persistence')])['status'],'observed')

    def test_parser_is_valid_for_boundary_but_fixture_conflict_is_not_processing(self):
        q=dict(id='handler',ruleIds=[40018],minimumStage='processing')
        self.assertEqual(assess_question(q,[self.probe(stage='fixture-blocked')])['status'],'open')
        self.assertEqual(assess_question(q,[self.probe()])['status'],'open')
        q['minimumStage']='boundary'
        self.assertEqual(assess_question(q,[self.probe()])['status'],'observed')
        for key in ('changed','application','identityValid','resultRead'):
            p=self.probe();p[key]=False
            self.assertEqual(assess_question(q,[p])['status'],'open')

    def test_jsonl_unicode_and_malformed_http_control_body(self):
        records=[dict(body='a\u2028b\u2029c'),dict(body='{')]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'traffic.jsonl';p.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in records)+'\n')
            self.assertEqual(read_jsonl(p),records)
            p.write_text(p.read_text()+'{\n')
            with self.assertRaisesRegex(ValueError,'line 3'):read_jsonl(p)

    def test_alert_standard_and_boundary_overlap_no_missing_or_duplicates(self):
        records=[dict(id=str(i),name='native') for i in range(207)]
        for overlap in (False,True):
            def fetch(start,count):
                pos=max(0,start-1) if overlap else start
                return records[pos:pos+count]
            self.assertEqual(collect_alerts(fetch,len(records),page_size=50),records)
        with self.assertRaises(ValueError):collect_alerts(lambda s,n:records[:2],3,page_size=2)
        with self.assertRaises(ValueError):collect_alerts(lambda s,n:[],1)

    def test_empty_terminal_and_nonempty_pages_keep_integrity_checks(self):
        kwargs=dict(rows='/content',page='/page',size='/size',total='/total',identity='/id',owner='/owner',expected_owner=9,terminal=True)
        empty=[dict(content=[],page=0,size=2,total=0)]
        self.assertTrue(check_pages(empty,expected_ids=[],**kwargs))
        pages=[dict(content=[dict(id=1,owner=9),dict(id=2,owner=9)],page=0,size=2,total=2),dict(content=[],page=1,size=2,total=2)]
        self.assertTrue(check_pages(pages,expected_ids=[1,2],**kwargs))
        self.assertFalse(check_pages(pages[:1],expected_ids=[1,2],**kwargs))
        for change in ('duplicate','owner','total','page'):
            bad=copy.deepcopy(pages)
            if change=='duplicate':bad[0]['content'][1]['id']=1
            elif change=='owner':bad[0]['content'][1]['owner']=8
            elif change=='total':bad[1]['total']=3
            else:bad[1]['page']=2
            self.assertFalse(check_pages(bad,expected_ids=[1,2],**kwargs))

    def test_redaction_preserves_metadata_but_hides_real_credentials(self):
        for role in ('CUSTOMER','ADMIN','EMPLOYEE','anonymous'):
            self.assertEqual(clean('issueAccessToken:'+role),'issueAccessToken:'+role)
        self.assertEqual(clean('password validation'),'password validation')
        self.assertEqual(clean('native JSON bearer authSessionId'),'native JSON bearer authSessionId')
        self.assertEqual(clean('Bearer authentication'),'Bearer authentication')
        for text in ('password=secret-canary','"password": "secret-canary"','Cookie: session=secret-canary','Authorization: Bearer secret-canary'):
            self.assertNotIn('secret-canary',clean(text))
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'result';rec=dict(taskCompletion='complete',openResponsibilities=[],inventoryGaps=[],nextActions=[])
            run=dict(operations=[dict(id='request-A'),dict(id='request-B')],coverage=[dict(caseId='issueAccessToken:CUSTOMER',operationIds=['request-A'])],description='opaque-canary')
            compact_results(out,run,{},rec,secrets=['opaque-canary'])
            self.assertNotIn('opaque-canary',(out/'RUN.json').read_text())
            self.assertIn('issueAccessToken:CUSTOMER',(out/'RUN.json').read_text())
            with self.assertRaises(FileExistsError):compact_results(out,run,{},rec)
            compact_results(out,run,{},rec,overwrite=True,secrets=['opaque-canary'])
            run['operations'][1]['id']='request-A'
            with self.assertRaisesRegex(ValueError,'duplicate'):compact_results(out,run,{},rec,overwrite=True)
            run['operations'][1]['id']='request-B';run['coverage'][0]['operationIds']=['group-prefix']
            with self.assertRaisesRegex(ValueError,'unresolved'):compact_results(out,run,{},rec,overwrite=True)

    def test_chunk_size_respects_published_schema(self):
        class MCP:
            contracts={'zap_report_read_chunk':{'properties':{'maxChars':{'maximum':90000}}}}
            def call(self,name,args):self.args=args;return '{}'
        m=MCP();Scanner(m,None,None).chunk('/zap/wrk/a',0,None)
        self.assertEqual(m.args['maxChars'],90000)
        with self.assertRaises(ValueError):Scanner(m,None,None,chunk_size=200001)


if __name__=='__main__':unittest.main()
