import base64
from dataclasses import replace
import json
import unittest
from zap_assessment.credential_broker import BrokerBinding
from zap_assessment.errors import Blocked,SecretLeak
from zap_assessment.finalsource_delegated import TargetBinding
from zap_assessment.native_secret_gate import (NativeHistory,NativePair,NativeG3Replay,collect_history,
    history_rows,strict_database,audit_zero,audit_positive,encode)
from zap_assessment.private_db import control_forms
from zap_assessment.secret_audit import CanaryAuditor

class NativeSecretGateTests(unittest.TestCase):
    def setUp(self):
        self.secret='owned-private-control-for-native-replay-12345!'
        self.binding=BrokerBinding('run-1','a'*64,'control','owned',None,'build','http://127.0.0.1:18080',200)
        self.target=TargetBinding('b'*64,'sha256:'+'c'*64,'started','d'*64,'127.0.0.1',18080)
    def messages(self,positive):
        return [{'id':str(i),'requestHeader':'GET /control HTTP/1.1\r\nX-Zpa-Seed: '+(v.decode() if positive else 'owned-clean')+'\r\n',
                 'requestBody':'','responseHeader':'HTTP/1.1 200 OK\r\n','responseBody':'{"owned":true}'}
                for i,v in enumerate(control_forms(self.secret).values(),1)]
    def snapshot(self,positive=False):
        rows=self.messages(positive)
        return NativeHistory(encode({'numberOfMessages':'5'}),tuple(encode({'messages':rows[i:i+2]}) for i in (0,2,4)),
                             encode({'messages':[]}),encode({'numberOfMessages':'5'}))
    def database(self,positive=False):
        rows=[{'kind':'table','name':'HISTORY'}]
        for i,msg in enumerate(self.messages(positive),1):
            raw=msg['requestHeader'].encode();rows.append({'kind':'cell','table':'HISTORY','row':i,'column':'REQHEADER',
                'sqlType':12,'base64':base64.b64encode(raw).decode()})
        return self.db_bytes(rows)
    def db_bytes(self,rows):
        end={'kind':'complete','tables':1,'rows':5,'cells':len(rows)-1,
             'decodedBytes':sum(len(base64.b64decode(r['base64'])) for r in rows if r['kind']=='cell')}
        return b'\n'.join(encode(r) for r in [*rows,end])+b'\n'
    def pair(self):
        return NativePair('success',self.binding,self.target,None,'owned-native-canary',self.snapshot(),self.database(),
                          self.snapshot(True),self.database(True),100,150)
    def test_collector_reads_count_pages_and_eof_from_engine(self):
        calls=[];rows=self.messages(True)
        def engine(c,k,n,args):
            calls.append((n,args))
            return {'numberOfMessages':'5'} if n=='numberOfMessages' else {'messages':rows[int(args['start'])-1:int(args['start'])-1+int(args['count'])]}
        snapshot=collect_history(engine,page_size=2)
        self.assertEqual(5,len(history_rows(snapshot)))
        self.assertEqual([('numberOfMessages',{}),('messages',{'start':'1','count':'2'}),
            ('messages',{'start':'3','count':'2'}),('messages',{'start':'5','count':'1'}),
            ('messages',{'start':'6','count':'1'}),('numberOfMessages',{})],calls)
        self.assertNotIn(self.secret,repr(snapshot))
    def test_changed_total_duplicate_ids_missing_eof_and_empty_pages_fail(self):
        original=self.snapshot()
        variants=[replace(original,after=encode({'numberOfMessages':'6'})),
                  replace(original,eof=encode({'messages':self.messages(False)[:1]})),
                  replace(original,pages=original.pages[:-1]),replace(original,pages=(encode({'messages':[]}),)),
                  replace(original,pages=(*original.pages,original.pages[-1]))]
        for value in variants:
            with self.assertRaises(Blocked):history_rows(value)
    def test_collector_blocks_nonprogress_and_timeout(self):
        def engine(c,k,n,args):return {'numberOfMessages':'5'} if n=='numberOfMessages' else {'messages':[]}
        with self.assertRaises(Blocked):collect_history(engine,page_size=2)
        times=iter([0,9])
        with self.assertRaises(Blocked):collect_history(engine,clock=lambda:next(times))
    def test_strict_db_rejects_rehashed_duplicates_unknown_type_bool_row_and_records_after_eof(self):
        raw=self.database();strict_database(raw.replace(b'REQHEADER',b'installed_rank'))
        rows=[json.loads(r) for r in raw.splitlines()[:-1]]
        bad=[self.db_bytes(rows+[rows[-1]]),raw.replace(b'"sqlType":12',b'"sqlType":9999'),
             raw.replace(b'"row":1',b'"row":true'),raw+b'{"kind":"table","name":"EXTRA"}\n',
             raw.replace(b'"sqlType":12',b'"sqlType":-4,"sqlType":12')]
        for candidate in bad:
            with self.assertRaises((Blocked,ValueError)):strict_database(candidate)
    def test_zero_audits_all_history_fields_and_database(self):
        audit=audit_zero(self.snapshot(),self.database(),CanaryAuditor([self.secret]))
        self.assertEqual(0,audit['historyForbiddenMatches']);self.assertEqual(0,audit['database']['canaryMatches'])
        for encoded in control_forms(self.secret).values():
            rows=self.messages(False);rows[0]['responseBody']=encoded.decode()
            snapshot=replace(self.snapshot(),pages=(encode({'messages':rows}),))
            with self.assertRaises(SecretLeak):audit_zero(snapshot,self.database(),CanaryAuditor([self.secret]))
        with self.assertRaises(SecretLeak):audit_zero(self.snapshot(),self.database(True),CanaryAuditor([self.secret]))
    def test_positive_replay_requires_all_five_exact_private_source_forms(self):
        result=audit_positive(self.snapshot(True),self.database(True),self.secret)
        self.assertEqual(5,len(result['historyControls']));self.assertEqual(5,len(result['database']['controls']))
        self.assertNotIn(self.secret,json.dumps(result))
        with self.assertRaises(Blocked):audit_positive(self.snapshot(True),self.database(True),'wrong-private-source-123456')
        with self.assertRaises(Blocked):audit_positive(self.snapshot(),self.database(True),self.secret)
    def test_real_private_byte_replay_keeps_143_denominator_and_refuses_json_allow(self):
        replay=NativeG3Replay(secret=self.secret,pairs=(self.pair(),))
        result=replay.inspect(binding=self.binding,target=self.target,epoch=None,now=110)
        self.assertEqual(143,result['requiredPairs']);self.assertEqual(2,result['nativePairsReplayed'])
        self.assertEqual(141,len(result['missingPairs']))
        with self.assertRaisesRegex(Blocked,'matrix_incomplete'):
            replay.verify('G3',(b'private-native-g3-replay/1.0',),binding=self.binding,target=self.target,epoch=None,now=110)
        with self.assertRaises(Blocked):replay.verify('G3',(b'{"gateDecision":"allow"}',),binding=self.binding,target=self.target,epoch=None,now=110)
    def test_wrong_binding_epoch_expiry_duplicate_and_fake_source_are_refused(self):
        pair=self.pair()
        for candidate in [replace(pair,binding=replace(self.binding,actor_ref='wrong')),
                          replace(pair,target=replace(self.target,started_at='restarted')),
                          replace(pair,epoch='new-epoch'),replace(pair,expires_at=109),
                          replace(pair,source_kind='product-external'),replace(pair,collected_at=float('nan'))]:
            with self.assertRaises(Blocked):NativeG3Replay(secret=self.secret,pairs=(candidate,)).inspect(
                binding=self.binding,target=self.target,epoch=None,now=110)
        with self.assertRaises(Blocked):NativeG3Replay(secret=self.secret,pairs=(pair,pair)).inspect(
            binding=self.binding,target=self.target,epoch=None,now=110)
    def test_metadata_statuses_are_not_private_snapshots(self):
        with self.assertRaises(Blocked):history_rows({'status':'pass','messages':5})
        with self.assertRaises(Blocked):NativeG3Replay(secret=self.secret,pairs=({'status':'pass'},)).inspect(
            binding=self.binding,target=self.target,epoch=None,now=110)

if __name__=='__main__':unittest.main()
