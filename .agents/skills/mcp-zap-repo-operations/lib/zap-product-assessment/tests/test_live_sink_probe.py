import base64
import json
import unittest
from zap_assessment.live_sink_probe import inspect_history_control
from zap_assessment.private_db import control_forms
from zap_assessment.errors import Blocked

class LiveSinkControlTests(unittest.TestCase):
    def setUp(self):
        self.secret='private-owned-fixture-canary-for-parser-123456'
        self.rows=[{'kind':'table','name':'HISTORY'}]
        for i,form in enumerate(control_forms(self.secret).values(),1):
            data=b'GET /control HTTP/1.1\r\nX-Zpa-Seed: '+form+b'\r\n\r\n'
            self.rows.append({'kind':'cell','table':'HISTORY','row':i,'column':'REQHEADER','sqlType':-4,
                              'base64':base64.b64encode(data).decode()})
    def raw(self,rows=None):
        rows=rows or self.rows
        size=sum(len(base64.b64decode(r['base64'])) for r in rows if r['kind']=='cell')
        end={'kind':'complete','rows':5,'cells':len(rows)-1,'decodedBytes':size,'tables':1}
        return b'\n'.join(json.dumps(r).encode() for r in [*rows,end])+b'\n'
    def test_all_five_encodings_must_appear_in_actual_history_typed_headers(self):
        value=inspect_history_control(self.raw(),self.secret)
        self.assertEqual(5,len(value['controls']))
        self.assertEqual({-4},{r['sqlType'] for r in value['controls']})
        self.assertNotIn(self.secret,json.dumps(value))
        self.assertFalse(value['rawCellsExportedToController'])
    def test_missing_duplicate_wrong_column_and_table_are_not_acceptance(self):
        variants=[self.rows[:-1],self.rows+[self.rows[-1]],
                  [self.rows[0],*[{**r,'column':'RESPHEADER'} for r in self.rows[1:]]],
                  [{'kind':'table','name':'CONTROL'},*[{**r,'table':'CONTROL'} for r in self.rows[1:]]]]
        for rows in variants:
            with self.subTest(case=len(rows)):
                with self.assertRaises(Blocked):inspect_history_control(self.raw(rows),self.secret)
    def test_truncated_bad_decoder_and_extra_terminal_records_block(self):
        raw=self.raw()
        for candidate in (raw.rsplit(b'\n',2)[0],raw+b'{"kind":"table","name":"EXTRA"}\n',
                          raw.replace(b'"sqlType": -4',b'"sqlType": 1111')):
            with self.assertRaises(Blocked):inspect_history_control(candidate,self.secret)

if __name__=='__main__':unittest.main()
