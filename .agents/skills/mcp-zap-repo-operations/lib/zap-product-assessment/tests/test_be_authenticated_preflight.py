import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.errors import Blocked
from zap_assessment.secret_inventory import SINKS,LIFECYCLE

spec=importlib.util.spec_from_file_location('be_preflight',Path(__file__).resolve().parents[1]/'scripts/be_authenticated_preflight.py')
C=importlib.util.module_from_spec(spec);spec.loader.exec_module(C)


class BeAuthenticatedPreflightTests(unittest.TestCase):
    def gate(self):
        return {'schemaVersion':'w5-scanner-campaign/1.0','operationalG3':'blocked',
                'productG4':'blocked','gateDecision':'block','securityApproval':False,
                'actualHistoryAudits':[{'caseId':c} for c in sorted(LIFECYCLE)],
                'containerSinkAudits':[{}],'artifactAudit':[{}],
                'databaseReadback':{'positiveControl':{'seededControl':True}},
                'envelopeAudits':[{}],'sourceBoundary':{'sourceValuesIncluded':False}}

    def test_143_pairs_cannot_be_promoted_from_zero_match_observations(self):
        result=C.matrix(self.gate())
        self.assertEqual(143,len(result['pairs']));self.assertEqual(0,result['completePairs'])
        self.assertEqual({(s,c) for s in SINKS for c in LIFECYCLE},
                         {(r['sinkId'],r['lifecycle']) for r in result['pairs']})
        self.assertTrue(all(r['proofStatus']=='blocked' for r in result['pairs']))
        self.assertGreater(result['pairsWithPartialObservationRefs'],0)

    def test_self_declared_operational_pass_or_review_approval_rejected(self):
        for key,value in [('operationalG3','pass'),('productG4','pass'),('gateDecision','allow'),
                          ('securityApproval',True),('schemaVersion','product/v1')]:
            g=self.gate();g[key]=value
            with self.subTest(key=key),self.assertRaises(Blocked):C.matrix(g)

    def test_duplicate_lifecycle_cannot_hide_missing_history_case(self):
        g=self.gate();g['actualHistoryAudits'].append(copy.deepcopy(g['actualHistoryAudits'][0]))
        with self.assertRaises(Blocked):C.matrix(g)

    def test_write_inside_sealed_bundle_or_clobber_refused_before_verifier(self):
        with tempfile.TemporaryDirectory() as t,patch.object(C.importlib.util,'spec_from_file_location',side_effect=AssertionError('verifier loaded')):
            p=Path(t);out=p/'existing';out.write_text('old')
            for work,dest in [(p,p/'inside'),(p/'bundle',out)]:
                with self.assertRaises(Blocked):C.evaluate(work,'0'*64,dest)
            self.assertEqual('old',out.read_text())

    def test_consistent_historical_bundle_does_not_claim_current_source(self):
        old={'implementation':'sha256:'+'a'*64,'harness':'b'*64}
        current={**old,'implementation':'sha256:'+'c'*64}
        value=C.source_classification({'sourcePins':old},current)
        self.assertFalse(value['sourcePinsMatchCurrent'])
        self.assertEqual('owned-synthetic-historical-source-readback',value['evidenceClass'])
        self.assertEqual(old,value['recordedSourcePins'])
        fresh=C.source_classification({'sourcePins':current},current)
        self.assertTrue(fresh['sourcePinsMatchCurrent'])
        self.assertEqual('owned-synthetic-current-source-readback',fresh['evidenceClass'])

    def test_source_comparison_requires_full_pin_dimensions(self):
        for plan in ({},{'sourcePins':{}},{'sourcePins':{'implementation':''}}):
            with self.assertRaises(Blocked):C.source_classification(plan,{'implementation':'sha256:pin','harness':'pin'})


if __name__=='__main__':unittest.main()
