import copy
import unittest
from zap_assessment.product_workflow import reconcile_responsibilities
from zap_assessment.product_handoff import direct_dimensions
from zap_assessment.product_checks import check_pages

class ContinuationTests(unittest.TestCase):
    def test_case_dependencies_missing_direction_pages_and_exclusions(self):
        rows=[{'caseId':c,'evidenceRefs':['reviewed-policy'],'prerequisites':deps,'requiredEvidence':units} for c,deps,units in [
            ('reverse-delete',['actors','mutation'],['before','after','positive','disclosure']),
            ('collection',['actors'],['page0','page1','terminal']),('privileged',['role'],['native']),('header',['header-vector'],['native'])]]
        rows += [{'caseId':'excluded','disposition':'user-excluded','reason':'explicit narrow scope','evidenceRefs':['user']},
                 {'caseId':'shared','disposition':'not-applicable','reason':'shared catalog has no ownership','evidenceRefs':['source']}]
        observed={'collection':{'outcome':'matched','evidenceUnits':['page0']}}
        result=reconcile_responsibilities(rows,observed,{'actors':True,'mutation':True})
        self.assertEqual(result['nextEligibleCaseIds'],['reverse-delete','collection'])
        self.assertEqual([r['dependencies'] for r in result['cases'] if r['status']=='blocked'],[['role'],['header-vector']])
        self.assertEqual(result['taskCompletion'],'partial');self.assertFalse(result['handoffClosesTask'])
        observed['reverse-delete']={'outcomeUnknown':True}
        self.assertEqual(reconcile_responsibilities(rows,observed,{'actors':True,'mutation':True})['nextEligibleCaseIds'],['collection'])
    def test_twenty_matched_policy_separate_and_mixed_finding_visible(self):
        cases=[{'id':str(i),'relation':'nonowner','request':{'operationRef':'rename'},'policyEvidenceRefs':['source']} for i in range(20)]
        plan={'cases':cases,'policyStatus':'source-hypothesis'}
        checks=[{'caseId':c['id'],'outcome':'matched'} for c in cases]
        run=dict(executionStatus='completed',evidenceStatus='complete',securityVerdict='inconclusive',cleanupStatus='retained',gateDecision='review_required')
        original=copy.deepcopy(run);r=direct_dimensions(plan,checks,run,[])
        self.assertEqual(r['caseOutcomes'],{'matched':20});self.assertEqual(r['policy']['status'],'source-hypothesis');self.assertEqual(run,original)
        checks[0]['outcome']='violated';checks[1]['outcome']='inconclusive'
        r=direct_dimensions(plan,checks,run,[]);self.assertEqual(r['findingsCaseIds'],['0']);self.assertEqual(r['rawStatuses']['securityVerdict'],'inconclusive')
        with self.assertRaises(ValueError):direct_dimensions(plan,checks+checks[:1],run,[])
    def test_final_page_leak_missing_terminal_and_duplicate_detected(self):
        pages=[{'entries':[{'key':str(i),'owner':'reader-one'}],'meta':{'index':i,'limit':1,'count':3}} for i in range(3)]
        pages.append({'entries':[],'meta':{'index':3,'limit':1,'count':3}})
        kw=dict(rows='/entries',page='/meta/index',size='/meta/limit',total='/meta/count',identity='/key',expected_ids=['0','1','2'],owner='/owner',expected_owner='reader-one',terminal=True)
        self.assertTrue(check_pages(pages,**kw));self.assertFalse(check_pages(pages[:-1],**kw))
        pages[2]['entries'][0]['owner']='reader-two';self.assertFalse(check_pages(pages,**kw))
        pages[2]['entries'][0]['owner']='reader-one';pages[2]['entries'][0]['key']='0';self.assertFalse(check_pages(pages,**kw))
