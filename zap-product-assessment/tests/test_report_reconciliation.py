import copy
import unittest
from zap_assessment.report_reconciliation import parse_findings_instances,reconcile_findings_report,unique_rows


def details(count=1,total=None):
    return 'Guided findings details.\nAlert instances returned: '+str(count)+' of '+str(count if total is None else total)+'\n'+''.join(
        f'\n- Alert ID: {i} | Plugin ID: 10015 | Name: Cache | Risk: Informational | Confidence: Low\n  URL: https://owned/p/{i}\n  Param: cache-control\n  Attack: <none>\n  Evidence: no-store\n  Message ID: {i+10}\n  Method: GET\n' for i in range(count))

def report(ids):
    return {'site':[{'@name':'https://owned/','alerts':[{'pluginid':'10015','name':'Cache','riskcode':'0','confidence':'1','count':str(len(ids)),
        'systemic':True,'instances':[{'id':str(i),'uri':f'https://owned/p/{i}','method':'GET','param':'cache-control','evidence':'no-store'} for i in ids]}]}]}

class ReconciliationTests(unittest.TestCase):
    def test_known_fixture_keeps_full_totals_and_samples_distinct(self):
        data=reconcile_findings_report(parse_findings_instances(details(8),'engine-A'),report([0,1,2,3,4]))
        self.assertEqual((data['findingsRowsRead'],data['reportSampleRows'],data['omittedCount']),(8,5,3))
        self.assertEqual(len(data['groups']),1)
        self.assertFalse(data['nativeReportExhaustive'])
        self.assertEqual(data['commonIdFieldDifferences'],[])
    def test_bounded_findings_not_silently_complete(self):
        snapshot=parse_findings_instances(details(100,150),'engine-A')
        self.assertEqual(snapshot['status'],'partial')
        r=reconcile_findings_report(snapshot,report([0]))
        self.assertEqual(r['status'],'partial');self.assertEqual(r['findingsDeclaredTotal'],150)
        self.assertIn('offset or cursor',r['nextAction'])
    def test_message_id_absent_is_not_invented_and_secrets_not_exported(self):
        s=parse_findings_instances(details(),'engine-A');s['rows'][0]['evidence']='private-value'
        r=reconcile_findings_report(s,report([1]))
        self.assertNotIn('private-value',str(r))
        self.assertIsNone(r['reportOnly'][0]['report']['messageId'])
        self.assertEqual(r['omitted'][0]['messageId'],'10')
    def test_distinct_sessions_do_not_collapse_same_id(self):
        a=parse_findings_instances(details(),'engine-A')['rows'][0]
        b=copy.deepcopy(a);b['session']='engine-B'
        self.assertEqual(len(unique_rows([a,b])),2)
        self.assertEqual(len(unique_rows([a,a])),1)
        b['session']='engine-A';b['method']='POST'
        with self.assertRaises(ValueError):unique_rows([a,b])
    def test_native_confidence_and_scope_differences_retained(self):
        s=parse_findings_instances(details(),'engine-A');r=report([0]);r['site'][0]['alerts'][0]['confidence']='3'
        out=reconcile_findings_report(s,r)
        self.assertEqual(out['commonIdFieldDifferences'][0]['fields']['confidence'],{'findings':'Low','report':'High'})
    def test_count_mismatch_is_error(self):
        with self.assertRaises(ValueError):parse_findings_instances(details().replace('1 of 1','2 of 2'),'engine-A')

if __name__=='__main__':unittest.main()
