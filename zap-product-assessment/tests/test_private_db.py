import base64
import copy
import io
import json
from pathlib import Path
import struct
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from zap_assessment.errors import Blocked
from zap_assessment import private_db as D,private_db_bridge as B
from support.private_db_controls import PASSWORD,FORMS,UnitZone,control_files,decoded_control,encode,receipt


class PrivateDatabaseOracleTests(unittest.TestCase):
    def test_fixed_encoding_oracle_and_complete_typed_row_shape(self):
        self.assertEqual(FORMS,D.control_forms(PASSWORD))
        result=D.audit_private_control(encode(decoded_control()),PASSWORD)
        self.assertEqual(15,result['decodedCells']);self.assertEqual(10,result['canaryMatches'])
        self.assertEqual(list(D.ENCODINGS),[r['encoding'] for r in result['encodingControls']])
        self.assertNotIn(PASSWORD,json.dumps(result));self.assertFalse(result['contentHashesIncluded'])

    def test_text_matches_cannot_replace_binary_or_encoding_binding(self):
        for fault in ('binary-is-text','missing-encoding','duplicate-column','duplicate-tag','wrong-bytes','wrong-row','unknown-column','table'):
            rows=decoded_control()
            if fault=='binary-is-text':
                for r in rows:
                    if r.get('column')=='BINARY_VALUE':r['sqlType']=12
            elif fault=='missing-encoding':rows=rows[:-4]+rows[-1:]
            elif fault=='duplicate-column':rows[3]['column']='TEXT_VALUE'
            elif fault=='duplicate-tag':rows[4]['base64']=rows[1]['base64']
            elif fault=='wrong-bytes':rows[2]['base64']=base64.b64encode(FORMS['base64-standard']).decode()
            elif fault=='wrong-row':rows[2]['row']=0
            elif fault=='unknown-column':rows[2]['column']='ARBITRARY'
            else:rows[2]['table']='OTHER'
            with self.subTest(fault=fault),self.assertRaises(Blocked):D.audit_private_control(encode(rows),PASSWORD)

    def test_duplicate_json_keys_and_post_terminal_records_block(self):
        raw=encode(decoded_control())
        duplicate=raw.replace(b'"row": 1',b'"row": 0, "row": 1',1)
        for value in (duplicate,raw+b'{"kind":"table","name":"LATE"}\n'):
            with self.assertRaises(Blocked):D.audit_private_control(value,PASSWORD)

    def test_missing_real_control_files_and_wrong_permissions_block(self):
        D.validate_control_files(control_files())
        for fault in ('disk','uid','mode','missing-data','link','hash','extra-name'):
            value=control_files()
            if fault=='disk':value['filesystem']='ext4'
            elif fault=='uid':value['files'][0]['uid']=1000
            elif fault=='mode':value['files'][0]['mode']=0o644
            elif fault=='missing-data':value['files']=value['files'][1:]
            elif fault=='link':value['files'][0]['links']=2
            elif fault=='hash':value['contentHashesIncluded']=True
            else:value['files'][0]['name']='unexpected'
            with self.subTest(fault=fault),self.assertRaises(Blocked):D.validate_control_files(value)

    def test_receipt_rejects_unknown_fields_public_values_and_wrong_binding(self):
        value=receipt();kwargs=dict(run_id='owned-db',plan_hash='a'*64,actor='A',case_id='success',mode='control')
        D.validate_public_receipt(value,**kwargs)
        for fault in ('actor','case','extra-value','source-value','public-cells','missing-encoding','cleanup','time','nonce'):
            r=receipt()
            if fault=='actor':r['actorRef']='B'
            elif fault=='case':r['caseId']='other'
            elif fault=='extra-value':r['password']=PASSWORD
            elif fault=='source-value':r['sourceMetadata']['password']=PASSWORD
            elif fault=='public-cells':r['rawCellsExportedToController']=True
            elif fault=='missing-encoding':r['audit']['encodingControls'].pop()
            elif fault=='cleanup':r['cleanup']['removedControlFiles']=0
            elif fault=='time':r['completedAtMonotonic']=99
            else:r['nonce']='g'*32
            with self.subTest(fault=fault),self.assertRaises(Blocked):D.validate_public_receipt(r,**kwargs)


class BytesSocket:
    def __init__(self,raw=b''):self.input=io.BytesIO(raw);self.output=bytearray()
    def recv(self,size):return self.input.read(min(size,7))
    def sendall(self,raw):self.output.extend(raw)


class PrivateDatabaseProtocolTests(unittest.TestCase):
    def test_length_bound_duplicate_keys_and_truncated_frames_fail_closed(self):
        for raw in (b'{"op":1,"op":2}',b'[]'):
            with self.assertRaises((Blocked,ValueError)):D.receive(BytesSocket(struct.pack('!I',len(raw))+raw))
        with self.assertRaises(Blocked):D.receive(BytesSocket(struct.pack('!I',4097)),4096)
        with self.assertRaises(Blocked):D.receive(BytesSocket(struct.pack('!I',10)+b'{}'))
        s=BytesSocket();D.send(s,{'kind':'metadata'});self.assertEqual({'kind':'metadata'},D.receive(BytesSocket(bytes(s.output))))

    def server(self):
        self.zone=UnitZone();self.events=[]
        return D.PrivateDbServer(run_id='owned-db',plan_hash='a'*64,actor='A',zone=self.zone,
            current_case=lambda:'success',canaries=lambda:[PASSWORD],record=self.events.append)
    def request(self,mode='control'):
        return {'op':'private-db','runId':'owned-db','planHash':'a'*64,'actorRef':'A','caseId':'success','mode':mode}

    def test_wrong_peer_actor_and_plan_deny_before_source_resolve(self):
        for fault in ('uid','actor','plan'):
            server=self.server();request=self.request();sent=[]
            if fault=='actor':request['actorRef']='B'
            if fault=='plan':request['planHash']='c'*64
            peer={'uid':1000,'gid':1000} if fault=='uid' else {'uid':1003,'gid':1003}
            with patch.object(D,'peer_identity',return_value=peer),patch.object(D,'receive',return_value=request),patch.object(D,'send',side_effect=lambda _,v:sent.append(copy.deepcopy(v))):
                server.handle(None)
            self.assertEqual(0,self.zone.resolves);self.assertEqual('denied',sent[-1]['status'])
            self.assertFalse(sent[-1]['sourceRead']);self.assertFalse(sent[-1]['privateValueDelivered'])
            self.assertEqual('private_db_channel_denied',self.events[-1]['event'])

    def test_replay_denied_before_source_resolve(self):
        server=self.server();server.used.add(('control','success'));sent=[]
        with patch.object(D,'peer_identity',return_value={'uid':1003,'gid':1003}),patch.object(D,'receive',return_value=self.request()),patch.object(D,'send',side_effect=lambda _,v:sent.append(v)):
            server.handle(None)
        self.assertEqual(0,self.zone.resolves);self.assertEqual('no_replay',sent[-1]['reasonCode'])

    def exchange(self,mode='control',raw=None,wrong_nonce=False):
        server=self.server();sent=[];nonce='b'*32
        if raw is None:raw=encode(decoded_control())
        frames=[self.request(mode),{'nonce':'c'*32 if wrong_nonce else nonce,'decoderExit':0,
                 'decodedBase64':base64.b64encode(raw).decode(),'controlFiles':control_files() if mode=='control' else None},
                {'nonce':nonce,'controlZoneRemoved':True,'removedControlFiles':3 if mode=='control' else 0}]
        with patch.object(D,'peer_identity',return_value={'uid':1003,'gid':1003}),patch.object(D,'receive',side_effect=frames), \
                patch.object(D,'send',side_effect=lambda _,v:sent.append(copy.deepcopy(v))),patch.object(D.secrets,'token_hex',return_value=nonce):
            server.handle(None)
        return sent

    def test_source_and_cells_use_private_frames_while_final_receipt_is_metadata(self):
        sent=self.exchange()
        self.assertEqual(PASSWORD,sent[0]['password'])  # allowed private socket only
        public=json.dumps(sent[-1]);self.assertNotIn(PASSWORD,public);self.assertNotIn('decodedBase64',public)
        self.assertEqual(10,sent[-1]['audit']['canaryMatches']);self.assertEqual(1,self.zone.resolves)
        D.validate_public_receipt(sent[-1],run_id='owned-db',plan_hash='a'*64,actor='A',case_id='success',mode='control')

    def test_bad_nonce_cannot_become_audited_receipt(self):
        with self.assertRaises(Blocked):self.exchange(wrong_nonce=True)

    def test_saved_session_leak_returns_only_leak_metadata(self):
        raw=encode([{'kind':'table','name':'HISTORY'},
            {'kind':'cell','table':'HISTORY','row':1,'column':'RESPONSE','sqlType':12,'base64':base64.b64encode(PASSWORD.encode()).decode()},
            {'kind':'complete','tables':1,'rows':1,'cells':1,'decodedBytes':len(PASSWORD)}])
        sent=self.exchange('session',raw)
        self.assertNotIn('password',sent[0]);self.assertEqual('leak',sent[-1]['status'])
        self.assertTrue(sent[-1]['leakDetected']);self.assertNotIn(PASSWORD,json.dumps(sent[-1]))


class PrivateDatabaseBridgeTests(unittest.TestCase):
    def binding(self):return {'runId':'owned-db','planHash':'a'*64,'sourceMode':'private-file','actorRef':'A','privateDbControls':True}

    def bridge(self,final):
        sent=[]
        class Channel:
            def __enter__(self):return self
            def __exit__(self,*_):pass
            def settimeout(self,_):pass
            def connect(self,_):pass
        ready={'status':'ready','nonce':'b'*32,'password':PASSWORD}
        frames=[ready,{'status':'audited','leakDetected':False},final]
        with patch.object(B.socket,'socket',return_value=Channel()),patch.object(B,'receive',side_effect=frames), \
                patch.object(B,'send',side_effect=lambda _,v:sent.append(copy.deepcopy(v))), \
                patch.object(B,'java_decode',return_value=(0,encode(decoded_control()))), \
                patch.object(B,'control_inventory',return_value=control_files()),patch.object(B,'remove_control',return_value=3):
            value=B.execute(binding=self.binding(),actor='A',case_id='success',mode='control')
        return value,sent

    def test_bridge_exports_metadata_and_keeps_decoded_bytes_in_socket_frame(self):
        final,sent=self.bridge(receipt())
        private=[r for r in sent if 'decodedBase64' in r];self.assertEqual(1,len(private))
        cells=[json.loads(line) for line in base64.b64decode(private[0]['decodedBase64']).splitlines()]
        self.assertEqual(PASSWORD.encode(),base64.b64decode(cells[2]['base64']))
        self.assertNotIn('decodedBase64',json.dumps(final));self.assertNotIn(PASSWORD,json.dumps(final))

    def test_bridge_refuses_holder_extra_value_instead_of_printing_it(self):
        value=receipt();value['rawSecret']=PASSWORD
        with self.assertRaises(Blocked):self.bridge(value)

    def test_bridge_error_stdout_is_redacted_and_process_umask_is_preserved(self):
        # main changes only its own process umask in production; restore test runner.
        import os
        before=os.umask(0o077);os.umask(before)
        try:
            out=io.StringIO()
            with patch('sys.argv',['bridge','--actor','A','--case','success']),patch.object(Path,'read_bytes',return_value=json.dumps(self.binding()).encode()), \
                    patch.object(B,'execute',side_effect=RuntimeError(PASSWORD)),redirect_stdout(out):
                code=B.main()
            self.assertEqual(2,code);self.assertNotIn(PASSWORD,out.getvalue());self.assertEqual('blocked',json.loads(out.getvalue())['status'])
        finally:os.umask(before)


if __name__=='__main__':unittest.main()
