"""W6 actual HTTP plus independent state/receipt replay and rehashed tamper cases."""
from copy import deepcopy
import hashlib
from http.server import HTTPServer
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest

from zap_assessment.business import validate_manifest, initial_state, expected_states, digest, minor
from zap_assessment.business_fixture import Product, Handler, generate_manifest
from zap_assessment.business_worker import collect
from zap_assessment.business_verification import audit_business, verify_business_bundle
from zap_assessment.contracts import canonical, ROOT
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.product_adapter import ProductAdapter, prepare_jobs

spec=importlib.util.spec_from_file_location('w6_campaign',ROOT/'scripts/w6_business_campaign.py')
campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)


class BusinessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name);cls.samples={}
        for name,adapter,seed,reverse,fault in [('a','finalsource-shaped',61,False,'fixed'),
                ('b','finalsource-shaped',971,True,'fixed'),('alt','alternate-ledger',413,True,'fixed'),
                ('mutated','finalsource-shaped',61,False,'denied-mutated'),
                ('leak','alternate-ledger',61,False,'denied-disclosure'),
                ('list','alternate-ledger',61,False,'list-leak')]:
            root=cls.root/name;root.mkdir();m=generate_manifest('w6-test-'+name,seed,adapter,reverse);validate_manifest(m)
            target=Product(m,root,fault)
            server=HTTPServer(('127.0.0.1',18080),Handler);server.product=target
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            try:observations={'cases':collect(prepare_jobs(m),root/'state.json',m['runId'])}
            finally:server.shutdown();server.server_close();thread.join()
            runtime={'id':'test-container-'+name,'name':m['runId']+'-fixture','image':'sha256:'+'a'*64,
                     'runId':m['runId'],'networkMode':'none','readOnlyRoot':True}
            observations['runtime']=runtime
            arrivals=[json.loads(line) for line in (root/'arrivals.jsonl').read_text().splitlines()]
            plan={'contractVersion':m['contractVersion'],'mode':'owned-synthetic-business','runId':m['runId'],
                  'fixtureHash':digest(m),'image':runtime['image'],'containerName':runtime['name'],
                  'sourcePins':{'test':'b'*64},'securityApproval':False}
            cleanup={'runtime':deepcopy(runtime),'cleanupStatus':'clean','removed':True}
            cls.samples[name]=(plan,m,observations,arrivals,cleanup)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def sample(self,name='a'):return list(deepcopy(self.samples[name]))
    def audit(self,values):return audit_business(*values)
    def negative(self,values,reason=None):
        with self.assertRaises(EvidenceInvalid) as caught:self.audit(values)
        if reason:self.assertIn(reason,str(caught.exception))
    def write_bundle(self,values):
        root=self.root/('bundle-'+str(len(list(self.root.glob('bundle-*')))));root.mkdir()
        result=self.audit(values)
        for name,v in zip(['plan','fixture','observations','arrivals','cleanup'],values,strict=True):(root/(name+'.json')).write_bytes(canonical(v))
        (root/'result.json').write_bytes(canonical(result));campaign.seal(root)
        return root,digest(values[0])
    def reseal(self,root):
        (root/'manifest.json').unlink();(root/'manifest.sha256').unlink();campaign.seal(root)

    def test_three_shapes_share_replay(self):
        for name in ('a','b','alt'):
            with self.subTest(name=name):
                result=self.audit(self.sample(name));self.assertEqual(result['syntheticContractStatus'],'pass')
                self.assertEqual(result['applicationOracleCounts']['fail'],0)
                self.assertEqual(result['skippedUnsupportedCount'],4)
                self.assertEqual(result['securityVerdict'],'inconclusive');self.assertEqual(result['gateDecision'],'block')
    def test_ids_and_orders_actually_differ(self):
        a=self.samples['a'][1];b=self.samples['b'][1];alt=self.samples['alt'][1]
        self.assertNotEqual([r['wireId'] for r in a['resources']],[r['wireId'] for r in b['resources']])
        self.assertNotEqual([r['resourceRef'] for r in a['resources']],[r['resourceRef'] for r in b['resources']])
        self.assertTrue(all(isinstance(r['wireId'],str) for r in alt['resources']))
        self.assertNotEqual(ProductAdapter(a).request(a['transitions'][0])['path'],ProductAdapter(alt).request(alt['transitions'][0])['path'])
    def test_denied_but_mutated_is_security_failure(self):
        result=self.audit(self.sample('mutated'))
        self.assertEqual(result['securityVerdict'],'fail')
        self.assertEqual(result['evidenceStatus'],'incomplete')
        self.assertTrue(any(not r['proofComplete'] for r in result['assertions']))
        self.assertTrue(any('post_state_oracle_violated' in r['reasons'] for r in result['assertions']))
        # The very first violation is a 403, never silently skipped.
        row=next(r for r in result['assertions'] if 'post_state_oracle_violated' in r['reasons'])
        raw=next(r for r in self.samples['mutated'][2]['cases'] if r['caseId']==row['caseId'])
        self.assertEqual(raw['exchange']['status'],403)
    def test_denial_disclosure_is_fail(self):
        result=self.audit(self.sample('leak'));self.assertEqual(result['securityVerdict'],'fail')
        self.assertTrue(any('disclosure_confirmed' in r['reasons'] for r in result['assertions']))
    def test_list_isolation_is_exact_not_empty_success(self):
        result=self.audit(self.sample('list'));self.assertEqual(result['securityVerdict'],'fail')
        self.assertTrue(any('list_isolation_or_state_violated' in r['reasons'] for r in result['assertions']))
    def test_wrong_actor_rehashed_target_receipt_rejected(self):
        v=self.sample();row=v[2]['cases'][1]['exchange'];row['actorRef']='B'
        rec=next(a for a in v[3] if a['requestId']==row['requestId']);rec['actorRef']='B'
        self.negative(v,'actor_resource_or_wire')
    def test_wrong_resource_request_rehashed_rejected(self):
        v=self.sample();row=v[2]['cases'][2]['exchange'];row['request']['path']='/api/v1/accounts/777777'
        next(a for a in v[3] if a['requestId']==row['requestId'])['request']=deepcopy(row['request'])
        self.negative(v,'actor_resource_or_wire')
    def test_wrong_expected_delta_rejected(self):
        v=self.sample();v[2]['cases'][0]['expectedPostStateSha256']='0'*64
        self.negative(v,'delta_disagrees')
    def test_missing_positive_never_passes(self):
        v=self.sample();row=v[2]['cases'][2];rid=row.pop('ownerPositive')['requestId']
        v[3]=[a for a in v[3] if a['requestId']!=rid]
        for i,a in enumerate(v[3],1):a['sequence']=i
        result=self.audit(v)
        self.assertEqual(result['assertions'][2]['outcome'],'inconclusive')
        self.assertIn('missing_owner_positive',result['assertions'][2]['reasons'])
    def test_missing_operation_positive_is_inconclusive(self):
        v=self.sample();c=next(c for c in v[1]['transitions'] if c['actorRef']=='anonymous');c.pop('positiveCaseId')
        v[0]['fixtureHash']=digest(v[1]);result=self.audit(v)
        row=next(r for r in result['assertions'] if r['caseId']==c['caseId']);self.assertEqual(row['outcome'],'inconclusive')
    def test_wrong_positive_resource_rejected(self):
        v=self.sample();c=next(c for c in v[1]['transitions'] if c['caseId']=='A-update-cross');c['positiveCaseId']='A-read-owner'
        v[0]['fixtureHash']=digest(v[1]);self.negative(v,'positive_binding')
    def test_positive_after_negative_rejected(self):
        v=self.sample();row=v[2]['cases'][2];a=next(a for a in v[3] if a['requestId']==row['ownerPositive']['requestId']);b=next(a for a in v[3] if a['requestId']==row['exchange']['requestId']);a['requestId'],b['requestId']=b['requestId'],a['requestId']
        self.negative(v)
    def test_duplicate_receipt(self):
        v=self.sample();v[3].append(deepcopy(v[3][0]));self.negative(v)
    def test_wrong_provenance_run(self):
        v=self.sample();v[1]['resources'][0]['provenance']['runId']='w6-other';self.negative(v,'provenance')
    def test_duplicate_wire_id(self):
        v=self.sample();v[1]['resources'][1]['wireId']=v[1]['resources'][0]['wireId'];self.negative(v,'identity_or_owner')
    def test_duplicate_subject(self):
        v=self.sample();v[1]['actors'][1]['subject']=v[1]['actors'][0]['subject'];self.negative(v)
    def test_monetary_precision_and_no_float(self):
        self.assertEqual(minor('0.0001'),1);self.assertEqual(minor('0.1')+minor('0.2'),3000)
        for x in ('0.00001','NaN','Infinity',0.1,True,'9007199254740992'):
            with self.subTest(x=x),self.assertRaises(EvidenceInvalid):minor(x)
    def test_insufficient_and_cross_category_keep_all_state(self):
        m=self.sample()[1]
        for c,status,before,after in expected_states(m):
            if 'insufficient' in c['caseId'] or 'cross-category' in c['caseId']:
                self.assertEqual(status,400);self.assertEqual(digest(before),digest(after))
    def test_cross_account_uses_requesters_own_category(self):
        m=self.sample()[1];resources={r['resourceRef']:r for r in m['resources']}
        for c in m['transitions']:
            if c['operation'] in ('expense','revenue') and c['caseId'].endswith('-cross'):
                self.assertNotEqual(resources[c['resourceRef']]['ownerActorRef'],c['actorRef'])
                self.assertEqual(resources[c['input']['categoryRef']]['ownerActorRef'],c['actorRef'])
    def test_failed_owner_positive_is_inconclusive(self):
        v=self.sample();control=v[2]['cases'][2]['ownerPositive'];control['status']=403;control['body']={'statusCode':403,'message':'request rejected'}
        rec=next(a for a in v[3] if a['requestId']==control['requestId']);rec['status']=403;rec['body']=deepcopy(control['body'])
        result=self.audit(v);self.assertEqual(result['assertions'][2]['outcome'],'inconclusive')
    def test_final_delete_cascades_transactions(self):
        for c,status,before,after in expected_states(self.sample()[1]):
            if c['caseId']=='A-delete-final':
                self.assertTrue(any(t['accountRef']=='A_main' for t in before['transactions'].values()))
                self.assertFalse(any(t['accountRef']=='A_main' for t in after['transactions'].values()))
    def test_valid_fail_bundle_exit_zero_does_not_pass_security(self):
        root,pin=self.write_bundle(self.sample('mutated'));r=verify_business_bundle(root,pin)
        self.assertTrue(r['verified']);self.assertEqual(r['securityVerdict'],'fail');self.assertFalse(r['R1Admitted'])
    def test_rehash_claim_to_pass_rejected(self):
        root,pin=self.write_bundle(self.sample('mutated'));p=root/'result.json';value=json.loads(p.read_text());value['securityVerdict']='pass';p.write_bytes(canonical(value));self.reseal(root)
        with self.assertRaisesRegex(EvidenceInvalid,'claim_disagrees'):verify_business_bundle(root,pin)
    def test_rehash_expected_delta_rejected(self):
        root,pin=self.write_bundle(self.sample());p=root/'observations.json';value=json.loads(p.read_text());value['cases'][0]['expectedPostStateSha256']='f'*64;p.write_bytes(canonical(value));self.reseal(root)
        with self.assertRaisesRegex(EvidenceInvalid,'delta_disagrees'):verify_business_bundle(root,pin)
    def test_fixture_and_plan_rehashed_external_pin_rejects(self):
        root,pin=self.write_bundle(self.sample());p=root/'fixture.json';v=json.loads(p.read_text());v['resources'][0]['wireId']+=1;p.write_bytes(canonical(v));p=root/'plan.json';q=json.loads(p.read_text());q['fixtureHash']=digest(v);p.write_bytes(canonical(q));self.reseal(root)
        with self.assertRaisesRegex(EvidenceInvalid,'external_business_plan_pin'):verify_business_bundle(root,pin)
    def test_bundle_requires_external_pin(self):
        root,pin=self.write_bundle(self.sample())
        with self.assertRaises(EvidenceInvalid):verify_business_bundle(root,None)
    def test_checksum_drift(self):
        root,pin=self.write_bundle(self.sample());(root/'result.json').write_text('{}')
        with self.assertRaisesRegex(EvidenceInvalid,'artifact_digest'):verify_business_bundle(root,pin)
    def test_symlink_bundle_artifact_rejected(self):
        root,pin=self.write_bundle(self.sample());p=root/'result.json';p.unlink();p.symlink_to(self.root/'a/state.json')
        with self.assertRaises(EvidenceInvalid):verify_business_bundle(root,pin)
    def test_mixed_product_mode_not_admitted(self):
        v=self.sample();v[0]['mode']='protected-product';self.negative(v,'plan_binding')
    def test_cleanup_identity_mismatch(self):
        v=self.sample();v[4]['runtime']['id']='foreign';self.negative(v,'cleanup_binding')


if __name__=='__main__':unittest.main()
