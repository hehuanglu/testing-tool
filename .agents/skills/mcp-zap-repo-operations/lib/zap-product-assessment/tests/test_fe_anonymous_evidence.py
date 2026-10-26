"""Adversarial offline evidence checks; resealing cannot legitimize a false claim."""
import copy,hashlib,tempfile,unittest
from pathlib import Path
from zap_assessment.fe_anonymous_contract import canonical,digest,save
from zap_assessment.fe_anonymous_verify import verify
from zap_assessment.journal import Journal

class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.root.chmod(0o700)
        predicate={'kind':'exists','selector':'#independent-marker'}
        journey={'id':'read-public','branch':'public','provenance':['source'], 'steps':[{'action':'navigate','path':'/public'}], 'expected':[predicate], 'network':[{'method':'POST','path':'/input','absent':True}]}
        doc={'schemaVersion':'fe-anonymous-journeys/1.0','recipe':'reviewed-fe/1.0','sources':[{'id':'source','path':'independent-source','sha256':'a'*64}],'journeys':[journey],'responsibilities':[{'id':'public','kind':'ui','provenance':['source'],'journeyIds':['read-public'],'disposition':'planned'}],'requestPolicies':[],'campaigns':[]}
        self.plan={'schemaVersion':'fe-anonymous-research-plan/1.0','profile':'fe-anonymous-research/1.0','track':'fe-anonymous','runId':'test-evidence','discovery':{},'discoverySha256':canonical({}),'journeys':doc,'journeysSha256':canonical(doc),'selection':{'origin':'https://site.test:9443','certificate':{'derSha256':'a'*64}},'authority':{},'journeyIds':['read-public'],'requestPolicies':[],'campaigns':[],'implementationPins':{},'notAfter':1,'limits':{},'retention':{},'stopPolicy':'no replay'}
        self.expected=canonical(self.plan);save(self.root,'PLAN.json',self.plan)
        Journal(self.root/'journal.jsonl','test-evidence',self.expected).append('intent',{'action':'owned-check'})
        state={'url':'https://site.test:9443/public','secure':True,'storageKeys':[],'sessionKeys':[],'cookieNames':[],'serviceWorkerControlled':False,'extendedState':{'cacheNames':[],'serviceWorkerRegistrations':0,'indexedDBNames':[]},'elements':[{'selector':'#independent-marker','exists':True,'text':'Independent marker'}]}
        png=b'\x89PNG\r\n\x1a\nowned-test-capture'
        self.observed={'journeyId':'read-public','profileFresh':True,'profileClosed':True,'profileDisposed':True,'outcome':'observed','browser':{'acceptInsecureCerts':False},'initialState':state,'finalState':state,'steps':[{'index':0,'action':'navigate','url':state['url']}],'assertions':[{'predicate':predicate,'passed':True}],'screenshot':{'sha256':hashlib.sha256(png).hexdigest(),'bytes':len(png)}}
        save(self.root,'journeys/read-public.json',self.observed);save(self.root,'browser/read-public/RESULT.json',self.observed);save(self.root,'browser/read-public/screen.png',png)
        self.checks=[{'journeyId':'read-public','outcome':'pass','network':[{'expected':journey['network'][0],'passed':True,'sequences':[]}],'forwarded':0,'anonymousInvariant':True,'uiRef':'journeys/read-public.json'}]
        save(self.root,'CHECKS.json',self.checks);save(self.root,'OPERATIONS.json',[])
        self.run={'executionStatus':'interrupted','evidenceStatus':'incomplete','securityVerdict':'inconclusive','cleanupStatus':'clean','gateDecision':'block','taskCompletion':'partial'}
        save(self.root,'RUN.json',self.run);self.seal()
    def seal(self):
        rows=[]
        for p in sorted(self.root.rglob('*')):
            if p.is_file() and p.name not in ('EVIDENCE_INDEX.json','EVIDENCE_INDEX.sha256'):
                p.chmod(0o600);rows.append({'path':str(p.relative_to(self.root)),'bytes':p.stat().st_size,'sha256':digest(p)})
        save(self.root,'EVIDENCE_INDEX.json',{'planHash':self.expected,'result':self.run,'artifacts':rows})
        save(self.root,'EVIDENCE_INDEX.sha256',(digest(self.root/'EVIDENCE_INDEX.json')+'\n').encode())
    def test_interrupted_integrity_does_not_claim_completion(self):
        result=verify(self.root,self.expected)
        self.assertTrue(result['integrityVerified']);self.assertFalse(result['evidenceComplete']);self.assertEqual(result['result']['taskCompletion'],'partial')
    def test_byte_tamper_rejected(self):
        (self.root/'browser/read-public/screen.png').write_bytes(b'changed')
        with self.assertRaises(ValueError):verify(self.root,self.expected)
    def test_independent_plan_hash_required(self):
        with self.assertRaises(ValueError):verify(self.root,'0'*64)
    def test_omitted_network_claim_rejected_after_reseal(self):
        self.checks[0]['network']=[];save(self.root,'CHECKS.json',self.checks);self.seal()
        with self.assertRaises(ValueError):verify(self.root,self.expected)
    def test_unindexed_artifact_rejected(self):
        save(self.root,'unindexed.json',{'claim':'unverified'})
        with self.assertRaises(ValueError):verify(self.root,self.expected)
    def test_incomplete_native_evidence_cannot_be_complete(self):
        self.run['taskCompletion']='complete';save(self.root,'RUN.json',self.run);self.seal()
        with self.assertRaises(ValueError):verify(self.root,self.expected)
    def test_stale_indexeddb_rejected_after_reseal(self):
        self.observed['initialState']['extendedState']['indexedDBNames']=['session-state']
        save(self.root,'journeys/read-public.json',self.observed);save(self.root,'browser/read-public/RESULT.json',self.observed);self.seal()
        with self.assertRaises(ValueError):verify(self.root,self.expected)
    def test_guard_denial_is_not_absent_api(self):
        save(self.root,'broker/000001.json',{'method':'POST','url':'https://site.test:9443/input','caseId':'read-public','forwarded':False,'reason':'input-policy','sequence':1})
        self.seal()
        with self.assertRaises(ValueError):verify(self.root,self.expected)

if __name__=='__main__':unittest.main()
