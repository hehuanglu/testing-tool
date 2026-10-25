import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zap_assessment.evidence import collect_report, read_report, report_preview_document, ReportReadFailure
from zap_assessment.product_native import report_readback

PATH='/zap/wrk/report.json'
def pages(text, width=4):
    sha=hashlib.sha256(text.encode()).hexdigest();result=[]
    for start in range(0,len(text),width):
        part=text[start:start+width];end=start+len(part)
        result.append(dict(reportPath=PATH,offset=start,nextOffset=None if end==len(text) else end,
            charactersReturned=len(part),endOfFile=end==len(text),totalCharacters=len(text),
            offsetUnit='unicodeCodePoints',artifactSha256=sha,content=part))
    return result

def source(parts, calls=None):
    def reader(path,offset,sha):
        if calls is not None:calls.append((path,offset,sha))
        return copy.deepcopy(next(p for p in parts if p['offset']==offset))
    return reader

class ReportCollectionTests(unittest.TestCase):
    def test_one_page_eof_null_and_valid_json(self):
        r=collect_report(source(pages('{}')),PATH,100,parse_json=True)
        self.assertEqual((r.status,r.document,r.next_offset),('complete',{},2))
    def test_unicode_and_hash_pinning(self):
        text='{"v":"Việt🧪𐍈"}';p=pages(text,2);calls=[]
        r=collect_report(source(p,calls),PATH,1000,parse_json=True)
        self.assertEqual(r.data,text.encode());self.assertEqual(r.document,{'v':'Việt🧪𐍈'})
        self.assertTrue(all(c[2]==p[0]['artifactSha256'] for c in calls[1:]))
    def test_transport_fault_retains_private_pages_and_resumes_suffix(self):
        p=pages('{"value":"abcdefgh"}');saved=[]
        def failing(path,offset,sha):
            if offset==8:raise OSError('secret canary in transport exception')
            return source(p)(path,offset,sha)
        r=collect_report(failing,PATH,100,on_page=saved.append)
        self.assertEqual(r.status,'partial');self.assertEqual(r.next_offset,8)
        self.assertNotIn('secret canary',r.reason);self.assertEqual(len(saved),2)
        calls=[];r2=collect_report(source(p,calls),PATH,100,saved_pages=saved,parse_json=True)
        self.assertEqual(r2.status,'complete');self.assertEqual(calls[0][1],8)
    def test_complete_cache_never_calls_transport(self):
        r=collect_report(lambda *a:self.fail('replayed transport'),PATH,100,saved_pages=pages('{"a":1}'),parse_json=True)
        self.assertEqual(r.status,'complete')
    def test_invalid_contract_pages_and_nonprogress(self):
        for change in ({'offset':2},{'nextOffset':0},{'nextOffset':None},{'content':''},{'offsetUnit':'bytes'},
                       {'artifactSha256':'bad'},{'totalCharacters':-1},{'charactersReturned':True}):
            with self.subTest(change=change):
                p=pages('{"a":"long"}');p[0].update(change)
                self.assertEqual(collect_report(source(p),PATH,100).status,'error')
    def test_missing_saved_page_rejected_without_reading(self):
        p=pages('{"a":"longer"}')
        r=collect_report(lambda *a:self.fail('gap must be rejected'),PATH,100,saved_pages=[p[0],p[2]])
        self.assertEqual(r.status,'error')
    def test_artifact_changes_between_pages(self):
        p=pages('{"a":"long"}');p[1]['artifactSha256']='0'*64
        r=collect_report(source(p),PATH,100)
        self.assertEqual((r.status,r.reason),('error','report changed during export'))
        self.assertEqual(len(r.pages),1)
    def test_hash_and_parse_errors_cannot_be_complete(self):
        p=pages('{}');p[0]['artifactSha256']='0'*64
        self.assertEqual(collect_report(source(p),PATH,100).reason,'report hash mismatch')
        self.assertEqual(collect_report(source(pages('not-json')),PATH,100,parse_json=True).reason,'report JSON parse failed')
    def test_page_budget_and_byte_budget_return_partial_with_saved_data(self):
        text='{"a":"Việt🧪"}';p=pages(text)
        a=collect_report(source(p),PATH,100,max_pages=1)
        self.assertEqual((a.status,len(a.pages)),('partial',1))
        b=collect_report(source(p),PATH,4)
        self.assertEqual(b.status,'partial');self.assertGreater(len(b.pages),0)
        c=collect_report(source(p),PATH,100,saved_pages=b.pages)
        self.assertEqual(c.data,text.encode());self.assertEqual(c.status,'complete')
    def test_premature_eof_and_trailing_saved_pages(self):
        p=pages('{"a":"long"}');p[0].update(endOfFile=True,nextOffset=None)
        self.assertEqual(collect_report(source(p),PATH,100).status,'error')
        p=pages('{}');self.assertEqual(collect_report(source(p),PATH,100,saved_pages=p+p).status,'error')
    def test_legacy_entry_remains_fail_closed_and_exposes_progress(self):
        p=pages('{"a":1234}')
        with self.assertRaises(ReportReadFailure) as e:read_report(source(p),PATH,1)
        self.assertEqual(e.exception.result.status,'partial')
    def test_preview_explicit_complete_only(self):
        text='Report artifact\nPath: '+PATH+'\nCharacters Returned: 2\nTruncated: no\n\n{}'
        self.assertEqual(report_preview_document(text,PATH),{})
        self.assertIsNone(report_preview_document(text.replace('Truncated: no','Truncated: yes'),PATH))
        self.assertIsNone(report_preview_document(text+'x',PATH))
        self.assertIsNone(report_preview_document('{}',PATH))
    def test_native_entry_reuses_artifact_and_pages_after_fault(self):
        class Run:
            plan={'origin':'http://owned'}
            def __init__(self):self.calls=[];self.fail_once=True
            def tool(self,name,args):
                self.calls.append((name,args))
                if name=='zap_report_generate':return 'Path: /zap/wrk/report.'+args['format']
                if args['reportPath'].endswith('json'):
                    if args['offset']==4 and self.fail_once:
                        self.fail_once=False;raise ConnectionError('lost')
                    return json.dumps(source(pages('{"a":123}'))(args['reportPath'],args['offset'],None))
                text='<html>ok</html>';p=pages(text,100)[0];p['reportPath']=args['reportPath'];return json.dumps(p)
        with tempfile.TemporaryDirectory() as tmp:
            r=Run()
            with self.assertRaises(ReportReadFailure):report_readback(r,tmp)
            report_readback(r,tmp)
            self.assertEqual(json.loads((Path(tmp)/'report.json').read_bytes()),{'a':123})
            self.assertEqual(len([a for n,a in r.calls if n=='zap_report_generate' and a['format']=='json']),1)
            self.assertEqual(len([a for n,a in r.calls if n=='zap_report_read_chunk' and a['offset']==0 and a['reportPath'].endswith('json')]),1)
            self.assertEqual((Path(tmp)/'report-readback/json/page-000000000000.json').stat().st_mode & 0o777,0o600)
            self.assertFalse(any(n in ('zap_attack_start','zap_crawl_start') for n,a in r.calls))

if __name__=='__main__':unittest.main()
