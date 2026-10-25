import copy, unittest
from zap_assessment.bola_research_branches import validate,coverage

class BranchTests(unittest.TestCase):
    def model(self):
        bs=[dict(operationRef='create',branchRef='create:'+n,predicate='goal_type='+n,relevant=True,objectReferences=[],policyRefs=['s'],evidenceRefs=['s'],fixtureDependencies=[],disposition=d,reason='policy') for n,d in [('Saving','candidate'),('Expense','blocked')]]
        return dict(schemaVersion='bola-inventory/1.1',operations=[dict(operationRef='create',disposition='not-run',branches=bs)])
    def proof(self):return {'caseRefs':['case'],'evidenceRefs':['http/case.json']}
    def test_saving_covered_expense_blocked_rolls_partial(self):
        x=self.model();validate(x,{'s'});c=coverage(x,{'create:Saving':self.proof()});self.assertEqual(c['operations'][0]['coverage'],'partial');self.assertEqual(c['branches'][1]['executionStatus'],'blocked')
    def test_expense_executed_and_unproved_operation(self):
        x=self.model();self.assertEqual(coverage(x,{})['operations'][0]['coverage'],'blocked');self.assertEqual(coverage(x,{k:self.proof() for k in ('create:Saving','create:Expense')})['operations'][0]['coverage'],'tested')
        with self.assertRaises(ValueError):coverage(x,{'unknown':self.proof()})
        with self.assertRaises(ValueError):coverage(x,{'create:Saving':{}})
    def test_aggregate_implicit_subject_relevant(self):
        x=self.model();x['operations'][0]['branches']=x['operations'][0]['branches'][:1];b=x['operations'][0]['branches'][0];b['objectReferences']=[{'location':'implicit-subject','name':'user'}];validate(x,{'s'});self.assertEqual(coverage(x,{})['operations'][0]['coverage'],'not-run')
        x['operations'][0]['disposition']='not-applicable'
        with self.assertRaises(ValueError):validate(x,{'s'})
    def test_legacy_is_version_aware(self):validate({'schemaVersion':'bola-inventory/1.0'},set())
