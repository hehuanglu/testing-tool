import json
import unittest
from zap_assessment.transport import MCP
from zap_assessment.contracts import Blocked

class SseTests(unittest.TestCase):
    def client(self,body):
        return MCP(lambda *a,**k:{'status':200,'headers':{'content-type':'text/event-stream'},'body':body})
    def test_report_unicode_nel_and_line_separators_do_not_truncate_json(self):
        value='report\u0085with\u2028unicode\u2029separators'
        result={'jsonrpc':'2.0','id':1,'result':{'content':[{'type':'text','text':value}]}}
        wire=': keepalive\r\n\r\nevent: message\r\ndata: '+json.dumps(result,ensure_ascii=False)+'\r\n\r\n'
        self.assertEqual(value,self.client(wire).rpc('tools/call')['content'][0]['text'])
    def test_multiline_data_and_unrelated_notifications(self):
        wire='event: message\ndata: {"jsonrpc":"2.0","method":"notice"}\n\ndata: {"jsonrpc":"2.0",\ndata: "id":1,"result":{"ok":true}}\n\n'
        self.assertEqual({'ok':True},self.client(wire).rpc('tools/call'))
    def test_duplicate_or_wrong_rpc_identity_is_rejected(self):
        doc=json.dumps({'jsonrpc':'2.0','id':1,'result':{}})
        for wire in ['data: '+doc+'\n\ndata: '+doc+'\n\n','data: {"jsonrpc":"2.0","id":2,"result":{}}\n\n']:
            with self.assertRaises(Blocked):self.client(wire).rpc('tools/call')

if __name__=='__main__':unittest.main()
