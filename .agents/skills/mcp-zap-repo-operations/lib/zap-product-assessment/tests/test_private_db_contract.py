import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from zap_assessment.errors import Blocked
from support.private_db_controls import receipt,source_metadata

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location('private_db_w5_contract',ROOT/'scripts/remediation_w5_scanner.py')
C=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(C)
SPEC=importlib.util.spec_from_file_location('private_db_readiness',ROOT/'scripts/be_authenticated_preflight.py')
R=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(R)


class PrivateDatabaseContractTests(unittest.TestCase):
    def test_mode_requires_explicit_new_plan_and_private_source_before_directory(self):
        with tempfile.TemporaryDirectory() as t:
            work=Path(t)/'unsupported'
            with self.assertRaises(Blocked):C.prepare(work,'A',private_db=True)
            self.assertFalse(work.exists())
            result=C.prepare(Path(t)/'valid','A',source='private-file',private_db=True)
            p=json.loads((Path(result['workDir'])/'w5-plan.json').read_text())
            self.assertEqual('w5-scanner-plan/1.2',p['schemaVersion']);self.assertTrue(C.private_db_mode(p))
            for fault in ('old-schema','missing-contract','wrong-zone','missing-source-pin'):
                q=copy.deepcopy(p)
                if fault=='old-schema':q['schemaVersion']='w5-scanner-plan/1.1'
                elif fault=='missing-contract':q.pop('privateDbContract')
                elif fault=='wrong-zone':q['allowedPrivateControlZone']='/tmp/other'
                else:q.pop('privateDbReaderSourceSha256')
                with self.subTest(fault=fault),self.assertRaises(Blocked):C.private_db_mode(q)
        self.assertFalse(C.private_db_mode({'schemaVersion':'w5-scanner-plan/1.0'}))

    def proof(self,work):
        source=b'public unit reader source';run='owned-db';plan={
            'schemaVersion':'w5-scanner-plan/1.2','runId':run,'actorRef':'A','cases':['success','cleanup','crash'],
            'sourceMode':'private-file','sourceContract':'owned-private-source/1.0','secretSource':C.PRIVATE_SECRET_SOURCE,
            'allowedSourceZone':'/tmp/w5-private-source','privateDbControls':True,'privateDbContract':C.PRIVATE_DB_CONTRACT,
            'allowedPrivateControlZone':'/tmp/w5-private-db-control','privateDbReaderSourceSha256':hashlib.sha256(source).hexdigest(),
            'runtimePins':{'zap':'zap@sha256:'+'c'*64}}
        h=C.digest(plan);meta=source_metadata(run,h);root=work/'runtime';(root/'fixture').mkdir(parents=True)
        def save(name,value):p=root/name;p.write_text(json.dumps(value))
        reader={'contract':C.PRIVATE_DB_CONTRACT,'containerId':'d'*64,'imageId':'sha256:'+'c'*64,
            'networkAnchorId':'e'*64,'networkMode':'container:'+'e'*64,'readerUser':'1003:1003','readonlyRoot':True,
            'memoryBytes':256*1024**2,'swapBytes':256*1024**2,'tmpfsOptions':['rw','size=32m','uid=1003','gid=1003'],
            'observed':{'pythonVersion':[3,12,3],'uid':1003,'gid':1003,'tmpFilesystem':'tmpfs',
                'readerSourceSha256':plan['privateDbReaderSourceSha256'],'readerClassSha256':'f'*64,'hsqldbJarSha256':'1'*64},
            'sourceValuesIncluded':False,'rawCellsExportedToController':False}
        save('private-db-reader.json',reader);(root/'private-db-reader-source.java').write_bytes(source)
        save('fixture/w5-binding.json',{'runId':run,'planHash':h,'sourceMode':'private-file','actorRef':'A','privateDbControls':True})
        controls=[receipt(case,run=run,plan=h,nonce=n*32) for case,n in [('success','2'),('cleanup','3')]]
        session=receipt('cleanup','session',run,h,'4'*32)
        negatives=[]
        for probe in ('wrong-uid','wrong-actor','wrong-plan','replay'):
            r={'caseId':'success' if probe=='replay' else 'uninitialized','probe':probe,'status':'denied',
                'reasonCode':'peer_uid' if probe=='wrong-uid' else 'no_replay' if probe=='replay' else 'binding',
                'peer':{'uid':1000,'gid':1000} if probe=='wrong-uid' else {'uid':1003,'gid':1003},
                'sourceRead':False,'privateValueDelivered':False,'sourceValuesIncluded':False,
                'requestedActorMatches':probe!='wrong-actor','requestedPlanMatches':probe!='wrong-plan',
                'requestedRunMatches':True,'requestedCaseMatches':True}
            negatives.append(r);save('private-db-probe-'+probe+'.json',r)
        log=[]
        for v in [*controls,session]:
            save('private-db-'+(v['caseId'] if v['mode']=='control' else 'saved-session')+'.json',v)
            log.extend([{'event':'private_db_source_resolved','runId':run,'planHash':h,'caseId':v['caseId'],'mode':v['mode'],
                'source':meta['files'][0],'sourceValuesIncluded':False,'contentHashesIncluded':False,'atMonotonic':1.5},
                {'event':'private_db_audited',**v}])
        # Denials interleave in production; semantic replay independently groups them.
        for r in negatives:log.append({'event':'private_db_channel_denied','atMonotonic':1,**{k:v for k,v in r.items() if k!='probe'}})
        (root/'fixture/private-db-audit.jsonl').write_bytes(b''.join(C.canonical(r)+b'\n' for r in log))
        events=[]
        def event(kind,data):events.append({'kind':kind,'data':data})
        for role,cid in [('db-reader','d'*64),('net','e'*64),('zap','5'*64)]:
            event('ack',{'action':'container-create','resource':'zpa-'+run+'-'+role,'containerId':cid})
        for value in [*controls,*negatives]:
            intent={'action':'private-db-call','caseId':value['caseId'],'mode':'control','probe':value.get('probe','valid'),'reader':'zpa-'+run+'-db-reader'}
            event('intent',intent);ack={**intent,'metadataSha256':C.digest(value)}
            if 'nonce' in value:ack['nonce']=value['nonce']
            event('ack',ack)
        event('ack',{'action':'w5-zap-graceful-shutdown'})
        intent={'action':'private-db-call','caseId':'cleanup','mode':'session','probe':'valid','reader':'zpa-'+run+'-db-reader','writerContainerId':'5'*64,'writerNotRunning':True}
        event('intent',intent);event('ack',{**intent,'metadataSha256':C.digest(session),'nonce':session['nonce']})
        event('intent',{'action':'w5-owned-guard-sigkill'})
        result={'privateDbContract':C.PRIVATE_DB_CONTRACT,'privateDbReader':reader,'privateDbAudits':controls,
            'privateDbSessionAudit':session,'privateDbChannelControls':negatives,
            'privateSourceReceipts':[{}, {'sourceStatus':{'sourceMetadata':meta}}],
            'databaseReadback':{'privateChannel':True,'positiveControl':controls[-1]['audit'],'savedSession':session['audit']}}
        return plan,result,SimpleNamespace(events=events)

    def test_complete_private_reader_proof_remains_diagnostic(self):
        with tempfile.TemporaryDirectory() as t:
            p,r,j=self.proof(Path(t));value=C.verify_private_db_receipts(Path(t),p,r,j)
            self.assertEqual(2,value['controlLifecycleCases']);self.assertEqual(20,value['sourceEncodingTextBinaryDetections'])
            self.assertFalse(value['rawCellsExportedToController']);self.assertEqual('blocked',value['operationalG3'])

    def test_rehashed_receipts_cannot_hide_owner_source_nonce_or_stop_order(self):
        for fault in ('reader-uid','reader-image','source-actor','nonce-replay','missing-control','denial-delivered','missing-ack','writer-live','guard-before-audit','source-copy'):
            with tempfile.TemporaryDirectory() as t:
                work=Path(t);p,r,j=self.proof(work)
                if fault=='reader-uid':r['privateDbReader']['readerUser']='1000:1000'
                elif fault=='reader-image':r['privateDbReader']['imageId']='sha256:'+'0'*64
                elif fault=='source-actor':r['privateDbAudits'][0]['actorRef']='B'
                elif fault=='nonce-replay':r['privateDbAudits'][1]['nonce']=r['privateDbAudits'][0]['nonce']
                elif fault=='missing-control':r['privateDbAudits'].pop()
                elif fault=='denial-delivered':r['privateDbChannelControls'][0]['privateValueDelivered']=True
                elif fault=='missing-ack':j.events.pop(-2)
                elif fault=='writer-live':j.events[-3]['data']['writerNotRunning']=False
                elif fault=='guard-before-audit':j.events.insert(0,j.events.pop())
                else:(work/'runtime/private-db-reader-source.java').write_text('other code')
                # Recomputed outer JSON cannot repair contradictory semantic bindings.
                r=json.loads(json.dumps(r))
                with self.subTest(fault=fault),self.assertRaises(Blocked):C.verify_private_db_receipts(work,p,r,j)

    def test_private_session_never_starts_reader_call_while_writer_is_live(self):
        class RT:
            db_reader='reader';names=['anchor','holder','writer']
            def check_owner(self,name):return {'Id':'id','State':{'Running':True}}
            @property
            def journal(self):raise AssertionError('journal action before writer prerequisite')
        with patch.object(C,'docker',side_effect=AssertionError('executed reader')),self.assertRaises(Blocked):
            C.private_db_call(RT(),{},'cleanup','session')

    def matrix_fixture(self):
        gate={'schemaVersion':'w5-scanner-campaign/1.0','operationalG3':'blocked','productG4':'blocked',
              'gateDecision':'block','securityApproval':False,'actualHistoryAudits':[],
              'privateDbContract':C.PRIVATE_DB_CONTRACT,'privateDbAudits':[{'caseId':c} for c in C.CASES if c!='crash']}
        proof={'contract':C.PRIVATE_DB_CONTRACT,'controlLifecycleCases':14,'sourceEncodingTextBinaryDetections':140,
               'savedSessionAuditedInHolder':True,'channelNegativeControls':4,'rawCellsExportedToController':False,
               'operationalG3':'blocked'}
        return gate,proof

    def test_reader_control_proof_does_not_promote_live_sink_or_full_matrix_acceptance(self):
        gate,proof=self.matrix_fixture();value=R.matrix(gate,private_db_proof=proof)
        self.assertEqual(143,value['requiredPairs']);self.assertEqual(0,value['completePairs'])
        row=next(r for r in value['pairs'] if r['sinkId']=='zap-session-db' and r['lifecycle']=='active')
        self.assertEqual('blocked',row['proofStatus']);self.assertTrue(any('/privateDbAudits/' in r for r in row['observationRefs']))
        self.assertTrue(any('separate_HSQL_control_DB_not_live_ZAP_sink' in r for r in row['reasonCodes']))
        self.assertIsNone(R.matrix(gate)['privateDbReaderControls'])

    def test_readiness_requires_verifier_proof_and_unique_reader_control_cases(self):
        for fault in ('count','admission','duplicate'):
            gate,proof=self.matrix_fixture()
            if fault=='count':proof['sourceEncodingTextBinaryDetections']=10
            elif fault=='admission':proof['operationalG3']='pass'
            else:gate['privateDbAudits'][-1]=gate['privateDbAudits'][0]
            with self.subTest(fault=fault),self.assertRaises(Blocked):R.matrix(gate,private_db_proof=proof)


if __name__=='__main__':unittest.main()
