import copy,hashlib,json,tempfile,unittest
from pathlib import Path
from zap_assessment.archive_control import ArchiveControl,discovery,fixture_signing_key
from zap_assessment.signed_identity import verify_token,check_probe,check_native,check_wire_history
from zap_assessment.product_identity import import_actor,verify_import
from zap_assessment.product_workflow import compile_track,canonical_hash
from zap_assessment.recipes import archive
from test_multi_product import workflow,ROOT
from test_research import BIND

class SignedIdentityTests(unittest.TestCase):
    def test_real_signed_import_wrong_swapped_role_and_native_wire_controls(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t);jwt,pub=fixture_signing_key(root/'keys')
            seed={'jwt':jwt,'members':{'curator':{'key':'custodian-42','role':'CURATOR','password':'owned-private'},'other':{'key':'custodian-43','role':'CURATOR','password':'other-private'},'auditor':{'key':'audit-7','role':'AUDITOR','password':'audit-private'}}}
            server=ArchiveControl(seed=seed).start()
            try:
                d=discovery(ROOT,BIND,['http://owned-alias:18080'],[server.origin]);w={'operationIds':['access','list'],'permissions':['read','active','login'],'actorRole':'CURATOR','requests':[{'method':'GET','path':'/access'},{'method':'GET','path':'/documents'}],'execution':{'crawl':'/access','seeds':[{'method':'GET','path':'/access','expected':[200]}],'attacks':[{'method':'GET','path':'/documents?index=0&limit=1'}]}}
                p,inspection=workflow(d,w=w);source=root/'subjects.json';source.write_text(json.dumps({'members':seed['members']}));trustsource=root/'trust.json';sha=hashlib.sha256(pub.read_bytes()).hexdigest();trustsource.write_text(json.dumps({'targetBinding':BIND,'publicKeySha256':sha}))
                ref=lambda p:{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                trust={'publicKey':ref(pub),'bindingSha256':canonical_hash(BIND),'sourceEvidence':[ref(trustsource)]}
                private={'username':'curator','password':'owned-private','subject':'custodian-42','role':'CURATOR','jwtTrust':trust,'sourceEvidence':[{**ref(source),'subjectPointer':'/members/curator/key','rolePointer':'/members/curator/role'}]}
                self.assertEqual(import_actor(p,inspection,root/'valid',private)['executionStatus'],'imported')
                actor=json.loads((root/'valid/actor.json').read_text());verify_import(actor)
                q=compile_track(p,actor=actor['provenance'],identity_strategy=actor['identityStrategy']);self.assertEqual(q['identityPath'],'/access')
                for user,password in [('other','other-private'),('auditor','audit-private')]:
                    with self.assertRaisesRegex(ValueError,'subject/role mismatch'):import_actor(p,inspection,root/user,{**private,'username':user,'password':password})
                mapping=actor['identityStrategy'];token=actor['token'];verify_token(token,trust,mapping,'custodian-42','CURATOR')
                row={'requestHeader':'GET http://owned-alias:18080/access HTTP/1.1\r\nAuthorization: Bearer '+token+'\r\n','responseHeader':'HTTP/1.1 200\r\nContent-Type: application/json\r\n','responseBody':'{"gate":{"state":"present"}}'}
                self.assertTrue(check_native(row,'http://owned-alias:18080','/access',trust,mapping,'custodian-42','CURATOR'))
                for subject,role in [('custodian-43','CURATOR'),('custodian-42','AUDITOR')]:
                    with self.assertRaisesRegex(ValueError,'subject/role mismatch'):check_native(row,'http://owned-alias:18080','/access',trust,mapping,subject,role)
                with self.assertRaises(ValueError):check_probe(401,{},token,trust,mapping,'custodian-42','CURATOR')
                with self.assertRaises(ValueError):verify_token(token[:-3]+'bad',trust,mapping,'custodian-42','CURATOR')
                pub.write_text('drift')
                with self.assertRaisesRegex(ValueError,'key drift'):verify_import(actor)
            finally:server.close()

    def test_signed_authenticated_denial_is_distinct_from_anonymous_and_claim_only(self):
        with tempfile.TemporaryDirectory() as t:
            jwt,pub=fixture_signing_key(t);server=ArchiveControl(seed={'jwt':jwt});mapping=archive.IDENTITY_STRATEGIES['AUDITOR'];trust={'publicKey':{'path':str(pub),'sha256':hashlib.sha256(pub.read_bytes()).hexdigest()}}
            token=server.issue_token({'key':'audit-owned','role':'AUDITOR'});server.server.server_close()
            self.assertTrue(check_probe(403,{'problem':{'key':'role-denied'}},token,trust,mapping,'audit-owned','AUDITOR'))
            for status,body,bearer in [(401,{'problem':{'key':'role-denied'}},token),(403,{'problem':{'key':'other'}},token),(403,{'problem':{'key':'role-denied'}},'none.fake.signature')]:
                with self.assertRaises(ValueError):check_probe(status,body,bearer,trust,mapping,'audit-owned','AUDITOR')
            good={'id':'1','requestHeader':'GET http://owned/access HTTP/1.1\r\nAuthorization: Bearer '+token+'\r\n','responseHeader':'HTTP/1.1 403\r\n','responseBody':'{}'}
            control={'id':'2','requestHeader':'GET http://owned/access HTTP/1.1\r\nAuthorization: Bearer owned-invalid-session\r\n','responseHeader':'HTTP/1.1 401\r\n','responseBody':'{}'}
            placeholder={**control,'id':'3','requestHeader':control['requestHeader'].replace('/access','/'),'responseHeader':'HTTP/1.0 0\r\n','responseBody':''}
            result=check_wire_history([good,control,placeholder],'http://owned','/access',trust,mapping,'audit-owned','AUDITOR');self.assertEqual(len(result['messages']),1);self.assertEqual(len(result['excluded']),2)
            with self.assertRaises(ValueError):check_wire_history([good,{**control,'responseHeader':'HTTP/1.1 200\r\n'}],'http://owned','/access',trust,mapping,'audit-owned','AUDITOR')
