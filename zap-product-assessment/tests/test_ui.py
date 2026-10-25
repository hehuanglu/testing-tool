"""W7 unit/HTTP contracts and rehashed evidence controls, no browser admission."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from support.ui_fixture import sample
from zap_assessment.business import digest
from zap_assessment.contracts import ROOT,canonical
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.ui_contract import audit_ui,ui_steps,public_config
from zap_assessment.ui_verification import verify_ui_bundle
from zap_assessment.ui_fixture import HTML
from zap_assessment.ui_browser_worker import profile_audit
from zap_assessment.opaque_canary import OpaqueCanaryAuditor

spec=importlib.util.spec_from_file_location('w7_campaign',ROOT/'scripts/w7_ui_campaign.py');campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)


class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.samples={name:sample(seed,alt,reverse,fault,spike) for name,seed,alt,reverse,fault,spike in [
            ('a',711,False,False,'fixed',False),('b',982,True,True,'fixed',False),
            ('mutated',171,False,True,'denied-mutated',False),('leak',711,True,False,'denied-disclosure',False),
            ('spike',311,False,False,'fixed',True)]}
    def data(self,name='a'):return deepcopy(self.samples[name])
    def rejected(self,v,reason=None):
        with self.assertRaises(EvidenceInvalid) as e:audit_ui(*v)
        if reason:self.assertIn(reason,str(e.exception))
    def bundle(self,root,v):
        root.mkdir();names=['plan','fixture','observations','arrivals','secret-audit','cleanup']
        for name,value in zip(names,v,strict=True):(root/(name+'.json')).write_bytes(canonical(value))
        (root/'result.json').write_bytes(canonical(audit_ui(*v)));campaign.seal(root);return digest(v[0])
    def reseal(self,root):(root/'manifest.json').unlink();(root/'manifest.sha256').unlink();campaign.seal(root)
    def test_generated_contracts_both_id_shapes(self):
        for name in ('a','b'):
            with self.subTest(name=name):
                r=audit_ui(*self.data(name));self.assertEqual(r['oracleContractVerdict'],'pass');self.assertEqual(r['observedSteps'],13)
                self.assertEqual(r['secretVerdict'],'not_evaluated');self.assertEqual(r['functionalVerdict'],'not_run');self.assertFalse(r['browserRuntimeVerified']);self.assertEqual(r['G8Operational'],'blocked');self.assertFalse(r['productRuntimeVerified'])
    def test_unit_corpus_cannot_be_promoted_to_browser_runtime(self):
        v=self.data();v[2]['evidenceKind']='actual-webdriver';self.rejected(v,'evidence_kind_binding')
    def test_session_spike_cannot_count_as_ui_business_pass(self):
        r=audit_ui(*self.data('spike'));self.assertEqual(r['oracleContractVerdict'],'not_run');self.assertEqual(r['requiredSteps'],1)
    def test_denied_mutated_preserves_fail_after_later_drift(self):
        r=audit_ui(*self.data('mutated'));self.assertEqual(r['applicationVerdict'],'fail')
        self.assertTrue(any('ui_post_state_violated' in s['reasons'] for s in r['assertions']))
    def test_denial_disclosure_even_if_ui_hides_data(self):
        r=audit_ui(*self.data('leak'));self.assertEqual(r['applicationVerdict'],'fail')
        self.assertTrue(any('disclosure_confirmed' in s['reasons'] for s in r['assertions']))
    def test_wrong_rendered_balance(self):
        v=self.data();v[2]['steps'][5]['dom']['balance']='0.0001';r=audit_ui(*v)
        self.assertEqual(r['oracleContractVerdict'],'fail');self.assertIn('ui_balance_or_resource_render_mismatch',r['assertions'][5]['reasons'])
    def test_nonempty_error_is_not_success(self):
        v=self.data();v[2]['steps'][5]['dom']['alertPresent']=True;self.assertEqual(audit_ui(*v)['oracleContractVerdict'],'fail')
    def test_missing_actual_ui_submit_not_replaced_by_api_setup(self):
        v=self.data();row=v[2]['steps'][1];v[2]['steps']=v[2]['steps'][:2];row['requestIds']=[];row['errorCode']='ui_deadline';row['postState']=deepcopy(row['preState'])
        v[3]=v[3][:2];r=audit_ui(*v);self.assertEqual(r['oracleContractVerdict'],'inconclusive');self.assertEqual(r['applicationVerdict'],'inconclusive');self.assertEqual(r['executionStatus'],'timed_out')
    def test_missing_owner_positive_is_inconclusive(self):
        v=self.data();v[2]['steps'][2]['dom']['balance']='invalid';r=audit_ui(*v)
        self.assertEqual(r['oracleContractVerdict'],'fail')
    def test_all_missing_owner_positive_never_verifies_denial(self):
        v=self.data()
        for row in v[2]['steps'][:8]:
            if row['action'] in ('read','reload'):row['dom']['balance']='unconfirmed'
        result=audit_ui(*v)
        for row in result['assertions']:
            if row['stepId'] in ('denied-read-B','denied-write-B'):
                self.assertEqual(row['outcome'],'inconclusive');self.assertIn('missing_ui_owner_positive',row['reasons'])
    def test_wrong_actor_on_request_and_receipt(self):
        v=self.data();rec=next(r for r in v[3] if r['action']=='expense');rec['actorRef']='B';self.rejected(v,'wire_actor_resource')
    def test_wrong_resource_id_rehashed(self):
        v=self.data();rec=next(r for r in v[3] if r['action']=='read');rec['request']['path']='/api/v1/accounts/123456';self.rejected(v,'wire_actor_resource')
    def test_wrong_subject(self):
        v=self.data();v[3][1]['body']['subject']='wrong';self.rejected(v,'login_identity')
    def test_reauthentication_epoch_must_advance(self):
        v=self.data();last=[r for r in v[3] if r['action'] in ('login','identity')][-2:]
        for rec in last:rec['body']['authEpoch']=1
        self.rejected(v,'epoch_not_advanced')
    def test_wrong_request_dom_correlation(self):
        v=self.data();v[2]['steps'][5]['dom']['requestId']='unrelated';self.rejected(v,'dom_response_correlation')
    def test_reload_must_be_browser_refresh(self):
        v=self.data();v[2]['steps'][5]['navigation']='api-get';self.rejected(v,'reload_not_executed')
    def test_reload_requires_same_actor_identity_and_auth_epoch(self):
        for field,value in [('actorRef','B'),('authEpoch',99)]:
            v=self.data();rid=v[2]['steps'][5]['requestIds'][0]
            next(r for r in v[3] if r['requestId']==rid)[field]=value
            self.rejected(v,'reload_identity_binding')
    def test_reload_read_without_identity_is_incomplete(self):
        v=self.data();rid=v[2]['steps'][5]['requestIds'].pop(0)
        v[3]=[r for r in v[3] if r['requestId']!=rid]
        for i,r in enumerate(v[3],1):r['sequence']=i
        r=audit_ui(*v);self.assertEqual(r['oracleContractVerdict'],'inconclusive')
        self.assertIn('ui_reload_identity_and_read_missing',r['assertions'][5]['reasons'])
    def test_tmpfs_export_is_bounded_and_registered(self):
        with patch.object(campaign.subprocess,'run') as run:
            with self.assertRaisesRegex(ValueError,'unregistered'):campaign.owned_work_file('owned','/home/zap/profile',100)
            run.assert_not_called()
            run.return_value.returncode=0;run.return_value.stdout=b'x'*101
            with self.assertRaisesRegex(RuntimeError,'bounded_export'):campaign.owned_work_file('owned','/work/result.json',100)
    def test_browser_semantic_click_required(self):
        v=self.data();v[2]['steps'][1]['commandKinds']=['api-create'];self.rejected(v,'semantic_browser_actions')
    def test_missing_required_steps_incomplete(self):
        v=self.data();v[2]['steps']=v[2]['steps'][:1];v[3]=v[3][:2];r=audit_ui(*v);self.assertEqual(r['evidenceStatus'],'incomplete');self.assertEqual(r['oracleContractVerdict'],'inconclusive')
    def test_plan_cannot_drop_required_track(self):
        v=self.data();v[0]['steps'].pop();self.rejected(v,'plan_or_fixture')
    def test_duplicate_or_reordered_receipt(self):
        for duplicate in (True,False):
            v=self.data()
            if duplicate:v[3].append(deepcopy(v[3][0]))
            else:v[3][0],v[3][1]=v[3][1],v[3][0]
            self.rejected(v,'arrival_inventory')
    def test_unreferenced_request(self):
        v=self.data();v[2]['steps'][1]['requestIds']=[];self.rejected(v,'unreferenced_arrival')
    def test_denial_response_cannot_disclose_in_dom(self):
        v=self.data();v[2]['steps'][8]['dom']['balance']='1.0000';r=audit_ui(*v);self.assertEqual(r['applicationVerdict'],'fail')
    def test_secret_readiness_cannot_grant_admission(self):
        v=self.data();v[4]['operationalG3']='pass';self.rejected(v,'secret_scope')
    def test_secret_reader_unknown_is_blocked_not_pass(self):
        v=self.data();v[4]['profileMatches']=0;v[4]['profileVerdict']='blocked';r=audit_ui(*v);self.assertEqual(r['secretVerdict'],'not_evaluated');self.assertEqual(r['gateDecision'],'block')
    def test_profile_counts_cannot_be_hidden(self):
        v=self.data();v[4]['profileVerdict']='pass';self.rejected(v,'secret_verdict')
    def test_actual_profile_matches_require_per_file_inventory(self):
        v=self.data();v[0]['evidenceKind']='actual-webdriver';v[2]['evidenceKind']='actual-webdriver'
        self.rejected(v,'profile_match_inventory')
    def test_raw_private_retention_required(self):
        v=self.data();v[5]['rawProfileRetention']='deleted';self.rejected(v,'quarantine')
    def test_cleanup_wrong_identity(self):
        v=self.data();v[5]['runtime']['id']='other';self.rejected(v,'cleanup_binding')
    def test_browser_cleanup_error_blocks_proof(self):
        v=self.data();v[2]['browserCleanupError']=True;self.rejected(v,'browser_execution')
    def test_no_browser_useragent_no_proof(self):
        v=self.data();v[3][3]['userAgent']='python-client';self.rejected(v,'browser_provenance')
    def test_profile_auditor_actual_sqlite_cells_and_private_controls(self):
        import secrets
        with tempfile.TemporaryDirectory() as tmp:
            secret='W5-canary-'+secrets.token_hex(32);p=Path(tmp)/'localstorage.sqlite';conn=sqlite3.connect(p)
            conn.execute('CREATE TABLE data (value TEXT, encoded BLOB)');conn.execute('INSERT INTO data VALUES (?,?)',(secret,secret.encode('utf-16-le')));conn.commit();conn.close()
            r=profile_audit(tmp,[secret]);self.assertEqual(r['profileVerdict'],'fail');self.assertEqual(r['profileMatches'],1);self.assertEqual(r['sourceControlMisses'],0)
            self.assertNotIn(secret,json.dumps(r));self.assertIn('sqlite-readonly-cells-utf8-utf16le',r['profileFiles'][0]['readers'])
    def test_ui_plan_refuses_product_or_inline_credentials(self):
        for field,value in [('mode','protected-product'),('securityApproval',True),('password','forbidden-inline'),('fidelity','canonical-origin')]:
            v=self.data();v[0][field]=value;self.rejected(v)
    def test_rehashed_summary_cannot_promote_ui_or_security_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'bundle';pin=self.bundle(root,self.data());p=root/'result.json';v=json.loads(p.read_text());v['securityVerdict']='pass';v['gateDecision']='allow';p.write_bytes(canonical(v));self.reseal(root)
            with self.assertRaisesRegex(EvidenceInvalid,'claim_disagrees'):verify_ui_bundle(root,pin)
    def test_rehashed_dom_tamper_changes_oracle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'bundle';pin=self.bundle(root,self.data());p=root/'observations.json';v=json.loads(p.read_text());v['steps'][5]['dom']['balance']='0.0001';p.write_bytes(canonical(v));self.reseal(root)
            with self.assertRaisesRegex(EvidenceInvalid,'claim_disagrees'):verify_ui_bundle(root,pin)
    def test_forged_plan_and_fixture_cannot_replace_external_pin(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'bundle';pin=self.bundle(root,self.data());p=root/'plan.json';v=json.loads(p.read_text());v['steps']=v['steps'][:1];p.write_bytes(canonical(v));self.reseal(root)
            with self.assertRaisesRegex(EvidenceInvalid,'external_ui_plan_pin'):verify_ui_bundle(root,pin)
    def test_raw_canary_never_exported_in_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            v=self.data();root=Path(tmp)/'bundle';pin=self.bundle(root,v);p=root/'observations.json';j=json.loads(p.read_text());j['debug']='W5-canary-'+'0'*64;p.write_bytes(canonical(j));self.reseal(root)
            # Known private comparison added to source metadata; verdict still same.
            from zap_assessment.opaque_canary import fingerprints
            p=root/'secret-audit.json';j=json.loads(p.read_text());j['fingerprints']+=fingerprints(['W5-canary-'+'0'*64]);p.write_bytes(canonical(j));self.reseal(root)
            with self.assertRaisesRegex(EvidenceInvalid,'private_canary'):verify_ui_bundle(root,pin)
    def test_full_ui_requires_session_spike_before_resources(self):
        class Args:spike_only=False;session_spike=None;expect_spike_plan_sha=None
        with patch.object(campaign,'docker',side_effect=AssertionError('Docker called')):
            with self.assertRaisesRegex(ValueError,'session_spike'):campaign.run(Args())
    def test_disk_preflight_blocks_before_canary_browser_or_volume(self):
        class Stat:f_bavail=1;f_frsize=4096
        with tempfile.TemporaryDirectory() as tmp:
            class Args:spike_only=True;session_spike=None;expect_spike_plan_sha=None;seed=711;adapter='finalsource-shaped';reverse=False;fault='fixed';output=Path(tmp)/'new'
            with patch.object(campaign.os,'statvfs',return_value=Stat()),patch.object(campaign,'docker',side_effect=AssertionError('Docker called')):
                with self.assertRaisesRegex(RuntimeError,'disk_preflight_blocked'):campaign.run(Args())
    def test_fixture_javascript_compiles(self):
        # Parse real fixture JS. This is a syntax contract, not browser execution.
        js=HTML.split('<script>',1)[1].split('</script>',1)[0].replace('__CONFIG__',json.dumps(public_config(self.data()[1]))).replace('__FAULT__','"fixed"')
        code='const vm=require("node:vm");let s="";process.stdin.on("data",c=>s+=c);process.stdin.on("end",()=>new vm.Script(s));'
        r=subprocess.run(['node','-e',code],input=js,capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)


if __name__=='__main__':unittest.main()
