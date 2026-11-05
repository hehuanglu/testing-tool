import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from zap_assessment.business_discovery import review_business_coverage, validate_discovery_review
from zap_assessment.product_scope import reconcile
from zap_assessment.product_scope_cli import main
from workflow_fixtures import inventory, case, observed, operation


class BusinessDiscoveryTests(unittest.TestCase):
    def test_reviewed_feature_cannot_be_hidden_by_complete_flag(self):
        inv=inventory();inv['discoveryReview']['features'].append(dict(id='background',name='background',sourceIds=['ui'],disposition='unresolved',caseIds=[]))
        result=reconcile(inv,{'pin':observed()},{},operations=[operation()])
        self.assertEqual(result['taskCompletion'],'partial')
        self.assertIn('feature-unmapped:background',result['inventoryGaps'])
        self.assertEqual(result['cases'][0]['status'],'observed')
        from zap_assessment.work_selection import select_next_work
        proposal=select_next_work(inv,result,{},[],set())
        self.assertEqual(proposal['nextPreparation'],[dict(action='review-discovery',reasonCode='inventory-review-gap')])
        inv['discoveryReview']['features'][-1].update(disposition='outside-assignment',scopeBasis='User explicitly assigns personal pin only')
        self.assertEqual(reconcile(inv,{'pin':observed()},{},operations=[operation()])['taskCompletion'],'complete')

    def test_delta_case_and_missing_review_are_open_not_invalid_input(self):
        inv=inventory();inv['cases'].append(case('reaction',featureIds=[]))
        self.assertEqual(review_business_coverage(inv)['unreviewedCases'],['reaction'])
        inv.pop('discoveryReview')
        self.assertEqual(reconcile(inv,{}, {})['taskCompletion'],'partial')

    def test_extent_bounds_review_counts_and_does_not_count_unresolved_as_reviewed(self):
        inv=inventory();review=inv['discoveryReview']
        review['features'].append(dict(id='unresolved',name='unknown boundary',sourceIds=['ui'],caseIds=[],disposition='unresolved'))
        review['extent']=dict(kind='delta',featureIds=['pin','unresolved'],caseIds=['pin'],basis='Two declared groups; one still unresolved')
        result=review_business_coverage(inv)
        self.assertEqual(result['featureGroupsReviewed'],1)
        self.assertEqual(result['mappedFeatureGroups'],1)
        self.assertEqual(result['reviewStatus'],'gaps')
        review['extent']['featureIds']=['missing']
        with self.assertRaisesRegex(ValueError,'extent features'):review_business_coverage(inv)

    def test_representative_variants_with_exclusions_and_decoration(self):
        inv=inventory();inv['cases'][0]['representation']=dict(basis='Shared owner preference boundary',representedVariants=['grid','tiles'],excludedConclusions=['other-owner or consumer paths'])
        inv['discoveryReview']['features'][0].update(disposition='represented',basis='Same owner storage path; excludes shared spotlight')
        inv['discoveryReview']['features'].append(dict(id='decoration',name='layout decoration',sourceIds=['ui'],disposition='no-additional-question',caseIds=[],basis='Presentation only; assigned related API case remains'))
        self.assertEqual(review_business_coverage(inv)['reviewStatus'],'reviewed')
        self.assertEqual(len(inv['cases']),1)
        inv['discoveryReview']['features'][0].pop('basis')
        self.assertEqual(review_business_coverage(inv)['unmappedFeatures'],['pin'])

    def test_remaining_source_requires_assignment_relevance_basis(self):
        inv=inventory();source=inv['discoveryReview']['sources'][0]
        source['remainingScope']='unassigned export page'
        self.assertEqual(review_business_coverage(inv)['unresolvedSources'],['ui'])
        source.update(affectsAssignment=False,limitationBasis='User excludes export')
        self.assertEqual(review_business_coverage(inv)['reviewStatus'],'reviewed')

    def test_invalid_references_types_and_duplicates_rejected(self):
        mutations=[lambda i:i['discoveryReview']['features'].append(copy.deepcopy(i['discoveryReview']['features'][0])),
            lambda i:i['discoveryReview']['features'][0].update(caseIds=['missing']),
            lambda i:i['discoveryReview']['features'][0].update(sourceIds=['missing']),
            lambda i:i['cases'][0].update(objectiveDepth='everything'),
            lambda i:i.update(workflowVersion=True),
            lambda i:i['discoveryReview']['features'][0].update(disposition='outside-assignment',gapKind='capability',scopeBasis='No runner')]
        for mutate in mutations:
            with self.subTest(mutate=mutate):
                inv=inventory();mutate(inv)
                with self.assertRaises(ValueError):validate_discovery_review(inv)

    def test_legacy_keeps_completion_and_exposes_unreviewed_diagnostic(self):
        inv=inventory();inv.pop('workflowVersion');inv.pop('discoveryReview')
        obs={'pin':dict(outcome='matched',resultRead=True,evidenceUnits=['own-read','sibling-read'])}
        result=reconcile(inv,obs,{})
        self.assertEqual(result['taskCompletion'],'complete')
        self.assertEqual(result['discoveryReview']['reviewStatus'],'legacy-unreviewed')

    def test_review_cli_is_read_only_exit_zero_for_gaps_and_invalid_nonzero(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'inventory.json';inv=inventory();inv['discoveryReview']['basis']=''
            path.write_text(json.dumps(inv));before=path.read_bytes()
            with patch('socket.socket',side_effect=AssertionError('no traffic')),contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(main(['review-business','--inventory',str(path)]),0)
            self.assertEqual(json.loads(output.getvalue())['reviewStatus'],'gaps')
            self.assertEqual(path.read_bytes(),before)
            self.assertEqual(list(Path(temp).iterdir()),[path])
            inv['discoveryReview']['reviewedCaseIds']=['foreign'];path.write_text(json.dumps(inv))
            with self.assertRaises(ValueError):main(['review-business','--inventory',str(path)])
