"""Offline contracts: expectations describe permitted conclusions, not scan results."""
import contextlib
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zap_assessment.product_cli import main
from zap_assessment.product_scope import compact_results, reconcile
from zap_assessment.security_scope import canonical_alerts, normalize_scope


def scope(product='orchard', **changes):
    value = dict(assessmentId='unit-assessment', product=product, environment='offline', revision='r1', complete=True,
        sources=[dict(id='business-policy', location='policy.md')],
        criteria=[dict(id='retention', sourceId='KEEP-RECORDS', originalText='Retain the audit log <for review>.',
            source=dict(id='business-policy', location='policy.md#L3'), applicability=dict(status='applicable', basis='Product has an audit log'))],
        questions=[dict(id='log-review', criterionIds=['retention'], question='Does the deployed retention setting match policy?',
            closureCondition='Read the actual retention value and compare with policy.', requiredObservations=['setting-read', 'policy-compared'])])
    value.update(changes)
    return value


def run(**changes):
    value = dict(product='orchard', environment='offline', operations=[dict(id='read-config', type='config-review', status='completed',
        target='deployment logging configuration', criterionIds=['retention'], questionIds=['log-review'])])
    value.update(changes)
    return value


def assessment(**changes):
    value = dict(scopeRevision='r1', questionObservations={'log-review':dict(operationIds=['read-config'],
        observationUnits=['setting-read', 'policy-compared'], resultRead=True, outcome='matched', basis='Read value meets stated retention interval.')}, mappings=[])
    value.update(changes)
    return value


def finding(fid='short-retention', **changes):
    value = dict(findingId=fid, source='config-review', nativeId='local-check', description='Retention value is shorter than policy.',
                 severity='source-defined', confidence='observed', provenance=dict(document='deployment config', environment='offline'))
    value.update(changes)
    return value


def mapping(fid='short-retention', cid='retention', **changes):
    value = dict(findingId=fid, criterionId=cid, rationale='The observed setting retains logs for less time than this requirement.',
        certainty='supported', violation=True, observationBasis='Observed deployment retention value.', questionIds=['log-review'], operationIds=['read-config'])
    value.update(changes)
    return value


class SecurityScopeTests(unittest.TestCase):
    def compose(self, s=None, r=None, a=None, alerts=None, **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)/'reports'
            compact_results(out, r if r is not None else run(), alerts if alerts is not None else {'alerts':[]},
                security_scope=s if s is not None else scope(), scope_assessment=a, **kwargs)
            self.assertEqual({p.name for p in out.iterdir()}, {'RUN.json','ALERTS.json','SCOPE_ALERTS.json'})
            return [json.loads((out/name).read_text()) for name in ('RUN.json','ALERTS.json','SCOPE_ALERTS.json')]

    def test_non_endpoint_question_and_narrow_scope_complete_without_whole_tracks(self):
        reports = self.compose(a=assessment())
        self.assertEqual([r['taskCompletion'] for r in reports], ['complete']*3)
        c = reports[2]['criteria'][0]
        self.assertEqual((c['coverage'],c['securityAssessment']), ('observed','no-violation-observed'))
        self.assertIn('<for review>',c['originalText'])
        self.assertNotIn('track',c['questions'][0])
        self.assertNotIn('method',c['questions'][0])
        self.assertEqual(reports[0]['notPerformed'],[])

    def test_cli_json_scope_produces_three_reports_without_transport(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for name, value in {'scope':scope(), 'run':run(), 'alerts':{'alerts':[]}, 'assessment':assessment()}.items():
                (root/(name+'.json')).write_text(json.dumps(value))
            args=['scope','report','--run',str(root/'run.json'),'--alerts',str(root/'alerts.json'),
                '--security-scope',str(root/'scope.json'),'--scope-assessment',str(root/'assessment.json'),'--output',str(root/'out')]
            with patch('socket.socket',side_effect=AssertionError('network forbidden')), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(args),0)
                self.assertEqual(main(args+['--overwrite']),0)
            self.assertEqual(len(list((root/'out').iterdir())),3)
            self.assertEqual(json.loads((root/'out/SCOPE_ALERTS.json').read_text())['criteria'][0]['source']['location'],'policy.md#L3')
            for name,value in {'inventory':dict(productLocation='/offline',track='bola-ownership',complete=True,cases=[dict(caseId='read',evidenceRefs=['product source'],requiredEvidence=['direct'])]),
                'observations':{'read':dict(outcome='matched',resultRead=True,evidenceUnits=['direct'])},'prerequisites':{}}.items():
                (root/(name+'.json')).write_text(json.dumps(value))
            legacy=['scope','report','--run',str(root/'run.json'),'--alerts',str(root/'alerts.json'),'--output',str(root/'legacy')]
            for name in ('inventory','observations','prerequisites'):legacy+=['--'+name,str(root/(name+'.json'))]
            with patch('socket.socket',side_effect=AssertionError('network forbidden')),contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(legacy),0)
            old=json.loads((root/'legacy/SCOPE_ALERTS.json').read_text())
            self.assertEqual(old['scopeStatus'],'not-provided');self.assertEqual(old['taskCompletion'],'complete')

    def test_idless_text_source_stable_under_reordering_and_additions(self):
        s=scope()
        del s['criteria'][0]['id'];del s['criteria'][0]['sourceId'];s['questions']=[]
        c=copy.deepcopy(s['criteria'][0]);c['originalText']='A second independent rule.';c['source']['location']='policy.md#L8'
        first=normalize_scope(s)['criteria'][0]['id']
        s['criteria'].insert(0,c)
        self.assertEqual(normalize_scope(s)['criteria'][1]['id'],first)
        self.assertEqual(len({c['id'] for c in normalize_scope(s)['criteria']}),2)

    def test_distinct_source_namespaces_preserve_overlapping_ids(self):
        s=scope();s['sources'].append(dict(id='contract',location='contract.txt'))
        other=copy.deepcopy(s['criteria'][0]);other.pop('id');other['source']['id']='contract'
        s['criteria'][0].pop('id');s['criteria'].append(other);s['questions']=[]
        normalized=normalize_scope(s)
        self.assertEqual(len({c['id'] for c in normalized['criteria']}),2)
        self.assertEqual(len(self.compose(s=normalized,r=run(operations=[]))[2]['criteria']),2)

    def test_many_to_many_mapping_keeps_canonical_count_and_native_metadata(self):
        s=scope();second=copy.deepcopy(s['criteria'][0]);second['id']='incident-review';second['sourceId']='INCIDENTS';s['criteria'].append(second)
        s['questions'][0]['criterionIds'].append('incident-review')
        a=assessment(mappings=[mapping(cid='incident-review'), mapping(), mapping(fid='missing-export')])
        reports=self.compose(s=s,a=a,alerts={'alerts':[finding(),finding('missing-export',nativeId='another')]})
        self.assertEqual(reports[2]['summary'],dict(criteria=2,uniqueFindings=2,criterionAssociations=3,mappedFindings=2,unmappedFindings=0))
        self.assertEqual([len(c['findingIds']) for c in reports[2]['criteria']],[2,1])
        self.assertEqual(reports[1]['alerts'][0]['severity'],'source-defined')
        self.assertEqual(reports[1]['alerts'][0]['confidence'],'observed')

    def test_unmapped_and_uncertain_alerts_retained_without_confirming_violation(self):
        reports=self.compose(a=assessment(mappings=[mapping(certainty='uncertain')]),alerts={'alerts':[finding(),finding('incidental',scopeMapping='outside-assignment')]})
        self.assertEqual(len(reports[1]['alerts']),2)
        self.assertEqual(reports[1]['alerts'][1]['scopeMapping'],'outside-assignment')
        self.assertEqual(reports[2]['summary']['unmappedFindings'],1)
        self.assertEqual(reports[2]['criteria'][0]['securityAssessment'],'no-violation-observed')

    def test_zero_alerts_open_work_is_neither_pass_nor_complete(self):
        r, _, p=self.compose(r=run(handoffClosesTask=True,taskCompletion='complete'))
        self.assertEqual(r['taskCompletion'],'partial')
        self.assertFalse(r['handoffClosesTask'])
        self.assertEqual(p['criteria'][0]['coverage'],'not-performed')
        self.assertEqual(p['criteria'][0]['securityAssessment'],'inconclusive')
        self.assertTrue(r['notPerformed'])

    def test_violation_and_partial_coverage_are_independent(self):
        a=assessment(mappings=[mapping()]);a['questionObservations']['log-review']['observationUnits']=['setting-read']
        r,_,p=self.compose(a=a,alerts={'alerts':[finding()]})
        self.assertEqual((r['taskCompletion'],p['criteria'][0]['coverage'],p['criteria'][0]['securityAssessment']),
                         ('partial','partial','violation-supported'))

    def test_not_applicable_differs_from_missing_actor_and_capability(self):
        s=scope();s['criteria'][0]['applicability']=dict(status='not-applicable',basis='Product does not have audit logging.');s['questions']=[]
        r,_,p=self.compose(s=s,r=run(operations=[]))
        self.assertEqual(r['taskCompletion'],'complete')
        self.assertEqual(p['completionMeaning'],'applicability-only')
        self.assertEqual(p['criteria'][0]['coverage'],'not-performed')
        for kind in ('role','fixture','capability','source','configuration','auth','permission'):
            bad=copy.deepcopy(s);bad['criteria'][0]['applicability']['gapKind']=kind
            with self.subTest(kind=kind),self.assertRaisesRegex(ValueError,'N/A'):normalize_scope(bad)
        a=assessment();a['questionObservations']['log-review']=dict(blockers=['No permission to read configuration.'])
        r,_,p=self.compose(a=a)
        self.assertEqual((r['taskCompletion'],p['criteria'][0]['coverage']),('partial','blocked'))

    def test_black_box_observations_do_not_prove_internal_mechanism(self):
        s=scope();s['questions'][0].update(requiredObservations=['source-parameter-binding'],closureCondition='Verify query uses parameter binding in source.')
        a=assessment();a['questionObservations']['log-review']['observationUnits']=['active-no-sqli-alerts']
        r,_,p=self.compose(s=s,a=a)
        self.assertEqual(r['taskCompletion'],'partial')
        self.assertEqual(p['criteria'][0]['securityAssessment'],'inconclusive')
        self.assertEqual(p['criteria'][0]['questions'][0]['missingObservations'],['source-parameter-binding'])

    def test_unknown_ack_running_and_planned_do_not_close_questions(self):
        for status in ('acknowledged','running'):
            r=run();r['operations'][0]['status']=status
            with self.subTest(status=status):self.assertEqual(self.compose(r=r,a=assessment())[0]['taskCompletion'],'partial')
        r=run();r['operations'][0]['status']='planned'
        with self.assertRaisesRegex(ValueError,'nextSteps'):self.compose(r=r,a=assessment())
        a=assessment();a['questionObservations']['log-review']['outcomeUnknown']=True
        r,_,p=self.compose(a=a)
        self.assertEqual(r['taskCompletion'],'partial');self.assertTrue(p['criteria'][0]['questions'][0]['outcomeUnknown'])

    def test_structure_and_dangling_joins_rejected(self):
        for field in ('criteria','questions','sources'):
            s=scope();s[field].append(copy.deepcopy(s[field][0]))
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'duplicate'):normalize_scope(s)
        s=scope();s['questions'][0]['criterionIds']=['missing']
        with self.assertRaisesRegex(ValueError,'criterion reference'):normalize_scope(s)
        a=assessment();a['questionObservations']['log-review']['operationIds']=['missing']
        with self.assertRaisesRegex(ValueError,'operation reference'):self.compose(a=a)
        a=assessment(mappings=[mapping(fid='missing')])
        with self.assertRaisesRegex(ValueError,'finding reference'):self.compose(a=a)
        a=assessment(mappings=[mapping(cid='missing')])
        with self.assertRaisesRegex(ValueError,'criterion reference'):self.compose(a=a,alerts={'alerts':[finding()]})
        s=scope();s['questions'][0]['responsibilityIds']=['missing']
        with self.assertRaisesRegex(ValueError,'responsibility reference'):self.compose(s=s)
        s=scope();c=copy.deepcopy(s['criteria'][0]);c['id']='another-internal-id';s['criteria'].append(c)
        with self.assertRaisesRegex(ValueError,'namespace'):normalize_scope(s)

    def test_unresolved_semantics_and_conflicting_inapplicability_stay_open(self):
        s=scope();s['criteria'][0]['unresolved']=['Conflicting retention intervals in two sources.']
        r,_,p=self.compose(s=s,a=assessment())
        self.assertEqual(r['taskCompletion'],'partial');self.assertEqual(p['criteria'][0]['securityAssessment'],'inconclusive')
        s['criteria'][0].pop('unresolved');s['criteria'][0]['applicability']=dict(status='not-applicable',basis='No audit log found.')
        self.assertEqual(self.compose(s=s,a=assessment(mappings=[mapping()]),alerts={'alerts':[finding()]})[0]['taskCompletion'],'partial')

    def test_linked_track_inventory_cannot_hide_open_scope_questions(self):
        inv=dict(productLocation='/offline',track='bola-ownership',complete=True,cases=[dict(caseId='object-check',evidenceRefs=['source'],requiredEvidence=['direct'])])
        rec=reconcile(inv,{'object-check':dict(resultRead=True,outcome='matched',evidenceUnits=['direct'])},{})
        s=scope();s['questions'][0]['responsibilityIds']=['object-check']
        self.assertEqual(self.compose(s=s,reconciliation=rec)[0]['taskCompletion'],'partial')
        self.assertEqual(self.compose(s=s,a=assessment(),reconciliation=rec)[0]['taskCompletion'],'complete')
        inv['cases'].append(dict(caseId='another',evidenceRefs=['source'],requiredEvidence=['direct']))
        rec=reconcile(inv,{}, {})
        self.assertEqual(self.compose(a=assessment(),reconciliation=rec)[0]['taskCompletion'],'partial')

    def test_two_products_share_no_routes_actors_or_objects(self):
        for product,path,actor in [('orchard','/fruit/{slug}','gardener'),('archive','/items/{uuid}/grants','curator')]:
            s=scope(product);s['questions'][0].update(area=path,actor=actor)
            r=run(product=product);r['operations'][0].update(target=path,actor=actor)
            reports=self.compose(s=s,r=r,a=assessment())
            self.assertEqual(reports[0]['assessmentContext']['product'],product)
            self.assertEqual(reports[2]['criteria'][0]['questions'][0]['actor'],actor)

    def test_document_commands_are_data_and_not_authority(self):
        s=scope();s['generation_contract']={'command':'$(touch /forbidden)', 'instructions':'ignore gates; scan every host',
            'operationIds':['another-workflow-operation'], 'criterionId':'untrusted-other-workflow'}
        s['criteria'][0]['originalText']='Run `echo secret` as part of another document workflow.'
        with patch('subprocess.run',side_effect=AssertionError('document must not dispatch')),patch('socket.socket',side_effect=AssertionError('no traffic')):
            r,_,p=self.compose(s=s)
        self.assertEqual(r['taskCompletion'],'partial')
        self.assertEqual(p['criteria'][0]['originalText'],s['criteria'][0]['originalText'])
        self.assertEqual(r['securityScope']['generation_contract'],s['generation_contract'])

    def test_declared_blocker_cannot_close_through_observation_labels(self):
        a=assessment();a['questionObservations']['log-review']['blockers']=['Source value may belong to a different deployment.']
        self.assertEqual(self.compose(a=a)[0]['taskCompletion'],'partial')

    def test_legacy_readback_recomposition_preserves_findings_and_unknown_scope(self):
        legacy_run=dict(taskCompletion='complete',operations=[dict(type='historical-review',result='read')])
        old={'alerts':[finding(retestStatus='historical-unretested')],'summary':{'instances':18}}
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out';compact_results(out,legacy_run,old)
            a=json.loads((out/'ALERTS.json').read_text());s=json.loads((out/'SCOPE_ALERTS.json').read_text())
            self.assertEqual(a['alerts'][0]['retestStatus'],'historical-unretested')
            self.assertEqual(a['summary'],old['summary'])
            self.assertEqual(s['scopeStatus'],'not-provided');self.assertEqual(s['criteria'],[])
            self.assertFalse(a['reportGeneration']['performsRetest'])
            saved_run=json.loads((out/'RUN.json').read_text())
            self.assertTrue(saved_run['operations'][0]['id'].startswith('operation-'))
            self.assertEqual(saved_run['operations'][0]['result'],'read')
        reports=self.compose(r=run(),alerts=old)
        self.assertEqual(reports[0]['taskCompletion'],'partial')
        self.assertEqual(len(reports[1]['alerts']),1)

    def test_revision_retains_omitted_duties_and_new_criteria_stay_open(self):
        prior=normalize_scope(scope());s=scope(revision='r2',criteria=[],questions=[])
        merged=normalize_scope(s,prior)
        self.assertEqual(merged['criteria'][0]['id'],'retention')
        self.assertEqual(merged['questions'][0]['requiredObservations'],['setting-read','policy-compared'])
        self.assertEqual(len(merged['history']),1)
        s=scope(revision='r2');c=copy.deepcopy(s['criteria'][0]);c.update(id='new-rule',sourceId='NEW');s['criteria'].append(c)
        r,_,p=self.compose(s=s,a=assessment(scopeRevision='r2'),previous_scope=prior)
        self.assertEqual(r['taskCompletion'],'partial');self.assertEqual(p['criteria'][1]['coverage'],'not-performed')
        with self.assertRaisesRegex(ValueError,'revision mismatch'):self.compose(s=s,a=assessment())
        bad=copy.deepcopy(s);bad['revision']='r1'
        with self.assertRaisesRegex(ValueError,'new revision'):normalize_scope(bad,prior)
        bad=scope();bad['criteria'][0]['originalText']='Changed requirement.'
        with self.assertRaisesRegex(ValueError,'new revision'):normalize_scope(bad,prior)
        bad=scope(revision='r2');bad['questions'][0]['closureCondition']='A weaker question.'
        with self.assertRaisesRegex(ValueError,'new ID'):normalize_scope(bad,prior)

    def test_only_user_can_exclude_prior_requirements(self):
        prior=scope();s=scope(revision='r2');s['criteria'][0]['disposition']='user-excluded'
        with self.assertRaisesRegex(ValueError,'only user'):normalize_scope(s,prior)
        s['criteria'][0]['scopeBasis']='User limits this assessment to configuration discovery.'
        self.assertEqual(self.compose(s=s,previous_scope=prior)[0]['taskCompletion'],'complete')

    def test_canonical_ids_stable_across_reorder_and_native_sessions_separate(self):
        values=[finding(nativeId='1',session='one'),finding(nativeId='1',session='two')]
        for f in values:f.pop('findingId')
        first=canonical_alerts(values)['alerts'];second=canonical_alerts(values[::-1])['alerts']
        self.assertNotEqual(first[0]['findingId'],first[1]['findingId'])
        self.assertEqual(first[0]['findingId'],second[1]['findingId'])
        self.assertEqual(first[0]['nativeId'],'1')
        changed=copy.deepcopy(values[0]);changed['severity']='updated native classification'
        self.assertEqual(canonical_alerts([changed])['alerts'][0]['findingId'],first[0]['findingId'])

    def test_shared_implementation_pins_cover_new_dependency(self):
        import hashlib
        from zap_assessment import security_scope
        from zap_assessment.product_workflow import implementation_pins
        from zap_assessment.fe_anonymous_contract import pins as anonymous_pins
        from zap_assessment.fe_authenticated_contract import pins as authenticated_pins
        path=Path(security_scope.__file__)
        expected=hashlib.sha256(path.read_bytes()).hexdigest()
        for pins in (implementation_pins,anonymous_pins,authenticated_pins):
            self.assertEqual(pins()[str(path)],expected)
            for name in ('business_discovery.py','question_evidence.py','work_selection.py','readiness.py','coverage_presentation.py','residual_review.py'):
                helper=path.with_name(name)
                self.assertEqual(pins()[str(helper)],hashlib.sha256(helper.read_bytes()).hexdigest())

    def test_secret_redaction_across_three_reports_and_collision_validation(self):
        s=scope();s['criteria'][0]['interpretation']='password validation; private=opaque-canary';s['token']='opaque-canary';s['opaque-canary']='private key name'
        a=assessment(mappings=[mapping(rationale='Observed opaque-canary in private setting')])
        r,alerts,p=self.compose(s=s,a=a,alerts={'alerts':[finding(description='opaque-canary',password='hidden')]},secrets=['opaque-canary'])
        serialized=json.dumps([r,alerts,p]);self.assertNotIn('opaque-canary',serialized);self.assertNotIn('hidden',serialized)
        self.assertIn('password validation',serialized)
        self.assertEqual(p['criteria'][0]['findingIds'],['short-retention'])
        r=run();r['operations']=[dict(id='first-secret',status='completed'),dict(id='second-secret',status='completed')]
        with self.assertRaisesRegex(ValueError,'duplicate'):self.compose(r=r,secrets=['first-secret','second-secret'])

    def test_safe_write_invalid_inputs_do_not_damage_existing_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out';compact_results(out,run(),{'alerts':[]},security_scope=scope(),scope_assessment=assessment())
            before={p.name:p.read_bytes() for p in out.iterdir()}
            for bad in (object(),float('nan')):
                r=run(unsafelySerializable=bad)
                with self.subTest(bad=type(bad).__name__),self.assertRaises((ValueError,TypeError)):
                    compact_results(out,r,{},security_scope=scope(),overwrite=True)
                self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},before)
            a=assessment(mappings=[mapping(fid='dangling')])
            with self.assertRaisesRegex(ValueError,'finding reference'):
                compact_results(out,run(),{},security_scope=scope(),scope_assessment=a,overwrite=True)
            self.assertEqual({p.name:p.read_bytes() for p in out.iterdir()},before)
            (out/'unrelated.txt').write_text('preserve')
            with self.assertRaisesRegex(ValueError,'overwrite only'):compact_results(out,run(),{},overwrite=True)
            self.assertEqual((out/'unrelated.txt').read_text(),'preserve')
            link=Path(tmp)/'link';link.symlink_to(out,target_is_directory=True)
            with self.assertRaisesRegex(ValueError,'symlink'):compact_results(link,run(),{},overwrite=True)
            (out/'unrelated.txt').unlink();(out/'ALERTS.json').unlink();(out/'ALERTS.json').symlink_to(out/'RUN.json')
            with self.assertRaisesRegex(ValueError,'overwrite only'):compact_results(out,run(),{},overwrite=True)

    def test_legacy_two_file_destination_can_be_explicitly_upgraded(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'out';out.mkdir()
            for name in ('RUN.json','ALERTS.json'):(out/name).write_text('{}')
            compact_results(out,run(),{},security_scope=scope(),overwrite=True)
            self.assertEqual(len(list(out.iterdir())),3)


if __name__=='__main__':unittest.main()
