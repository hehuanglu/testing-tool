import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from zap_assessment.product_handoff import compose_handoff,selected_direct_dimensions

class LineageTests(unittest.TestCase):
    def test_raw_case_selection_supersedes_prior_observation_without_changing_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[]
            for n in (0,1):
                data={'plan':{'cases':[{'id':'raw'+str(n),'relation':'owner','request':{'operationRef':'list'},'policyEvidenceRefs':['source']}],'policyStatus':'source-hypothesis'},'checks':[{'caseId':'raw'+str(n),'outcome':'matched','reasons':[]}],'run':dict(executionStatus='completed',evidenceStatus='complete',securityVerdict='inconclusive',cleanupStatus='retained',gateDecision='review_required')};row={'cases':[{'caseId':'raw'+str(n),'unitId':'same-logical-case'}]}
                for kind,value in data.items():
                    p=root/f'{n}-{kind}.json';p.write_text(json.dumps(value));row[kind]={'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                rows.append(row)
            result=selected_direct_dimensions(rows[1:]);self.assertEqual(result['caseOutcomes'],{'matched':1});self.assertEqual(result['policy']['status'],'source-hypothesis')
            self.assertEqual(result['selectedSources'][0]['originalCaseId'],'raw1')
            with self.assertRaisesRegex(ValueError,'duplicate direct lineage'):selected_direct_dimensions(rows)
    def test_continuation_retains_statuses_and_deduplicates_evidence_not_native_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);rows=[]
            statuses=dict(executionStatus='completed',evidenceStatus='complete',securityVerdict='inconclusive',cleanupStatus='retained',gateDecision='review_required')
            for track in ('be-anonymous','be-authenticated','bola-ownership'):
                for attempt in range(2 if track=='be-authenticated' else 1):
                    ref=str(root/f'{track}-{attempt}.json');alert={'source':'ZAP','nativeRuleId':'1','name':'Observed','severity':'Low','confidence':'Medium','instances':[{'nativeAlertId':'0','evidenceRef':ref+'#/0','otherInfo':'userParam=handle\nuserValue=private-login-identifier\npasswordValue=private-login-password'}],'evidenceRefs':[{'path':ref}],'instanceCount':1}
                    p=Path(ref);p.write_text(json.dumps({'schemaVersion':'pm-alerts/1.0','product':{'location':'/owned'},'run':p.stem,**statuses,'scope':{'track':track},'alerts':[alert] if track=='be-authenticated' else []}))
                    rows.append({'track':track,'path':ref,'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'units':[str(attempt)],'retentionReason':'distinct obligation'})
            actor=root/'identity.json';actor.write_text(json.dumps({'nativeValidated':True,'role':'CURATOR','subject':'fixture-owner'}))
            for row in rows:
                if row['track']=='be-authenticated':row['actorEvidence']={'path':str(actor),'sha256':hashlib.sha256(actor.read_bytes()).hexdigest()}
            selection={'runId':'combined','coverageNote':'partial','runs':rows}
            result=compose_handoff(selection,root/'handoff')
            self.assertEqual(result['summary']['instances'],2);self.assertEqual(result['summary']['alertGroups'],1)
            self.assertEqual(result['alerts'][0]['trackResult'],str(root/'handoff/be-authenticated/ALERTS.json'))
            self.assertEqual(len(result['alerts'][0]['sourceFindings']),2)
            self.assertTrue(all(i['actor']=='CURATOR / subject fixture-owner' for i in result['alerts'][0]['instances']))
            self.assertNotIn('private-login-identifier',json.dumps(result));self.assertNotIn('private-login-password',json.dumps(result))
            self.assertEqual(result['securityVerdict'],'inconclusive');self.assertEqual(result['scope']['taskCompletion'],'partial')
            self.assertTrue(all(r['rawStatuses']==statuses for r in result['selectedLineage']))
            bad=copy.deepcopy(selection);bad['runs'].append(bad['runs'][1])
            with self.assertRaisesRegex(ValueError,'duplicate lineage'):compose_handoff(bad,root/'duplicate')
            self.assertFalse((root/'duplicate').exists())
            bad=copy.deepcopy(selection);bad['runs'][0]['sha256']='0'*64
            with self.assertRaisesRegex(ValueError,'drift'):compose_handoff(bad,root/'drift')
