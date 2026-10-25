import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from zap_assessment.delegated_attestation import OperationLedger
from zap_assessment.delegated_scanner import DelegatedScanner
from zap_assessment.errors import Blocked
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.journal import Journal

class MCPDouble:
    def __init__(self):self.calls=[];self.lost=False;self.terminal=True;self.passive=True;self.badchunk=False
    def call(self,name,args):
        self.calls.append((name,args))
        if name.endswith('_start'):
            if self.lost:raise ConnectionError('owned lost ack')
            return 'Execution Mode: direct\nOperation ID: op42\n'
        if name.endswith('_status'):
            if name=='zap_passive_scan_status':return 'Records remaining: 0\nCompleted: '+('yes' if self.passive else 'no')+'\n'
            return 'Execution Mode: direct\nOperation ID: op42\nCompleted: '+('yes' if self.terminal else 'no')+'\n'
        if name=='zap_report_generate':return 'Path: /zap/wrk/report.'+args['format']+'\n'
        if name=='zap_report_read_chunk':
            text='{"site":[]}' if args['reportPath'].endswith('.json') else '<html>Chào 𐍈</html>'
            page={'reportPath':args['reportPath'],'offset':0,'nextOffset':None,'charactersReturned':len(text),
                  'endOfFile':True,'totalCharacters':len(text),'offsetUnit':'unicodeCodePoints',
                  'artifactSha256':hashlib.sha256(text.encode()).hexdigest(),'content':text}
            if self.badchunk:page['totalCharacters']+=1
            return json.dumps(page)
        return 'stopped'

class DelegatedScannerTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.mcp=MCPDouble();self.allowed=True
        self.scanner=DelegatedScanner(self.mcp,lambda *args:{},lambda *args:{},
            ledger=OperationLedger(Journal(self.root/'journal.jsonl','unit-run','a'*64)),
            admit=lambda kind,url:self.allowed,policy_name='delegated-finalsource-query-1')
    def tearDown(self):self.tmp.cleanup()
    def test_lost_ack_never_reissues_start_and_inherited_start_is_closed(self):
        self.mcp.lost=True
        with self.assertRaises(ConnectionError):self.scanner.start_once('active-A','active','http://mirror/api/v1/accounts')
        with self.assertRaises(Blocked):self.scanner.start_once('active-A','active','http://mirror/api/v1/accounts')
        with self.assertRaises(Blocked):self.scanner.start('active','http://mirror')
        self.assertEqual(1,len(self.mcp.calls))
    def test_gate_failure_sends_nothing_and_no_shared_operation_stop(self):
        self.allowed=False
        with self.assertRaises(Blocked):self.scanner.start_once('active-A','active','http://mirror')
        with self.assertRaises(Blocked):self.scanner.seed('http://mirror')
        with self.assertRaises(Blocked):self.scanner.stop('active','someone-else')
        self.assertFalse(self.mcp.calls)
    def test_exact_policy_operation_terminal_and_full_both_format_readback(self):
        self.scanner.start_once('active-A','active','http://mirror/api/v1/transactions?type=expense')
        self.assertEqual('delegated-finalsource-query-1',self.mcp.calls[0][1]['policy'])
        self.assertEqual('false',self.mcp.calls[0][1]['recurse'])
        result=self.scanner.report_readback('http://mirror')
        self.assertEqual({'json','html'},result.keys())
        self.assertIn('Chào'.encode(),result['html']['bytes']);self.assertTrue(result['html']['chunks'][0]['endOfFile'])
    def test_nonterminal_passive_and_truncated_report_block(self):
        self.scanner.start_once('active-A','active','http://mirror')
        self.mcp.terminal=False
        with self.assertRaises(Blocked):self.scanner.report_readback('http://mirror')
        self.mcp.terminal=True;self.mcp.passive=False
        with self.assertRaises(Blocked):self.scanner.report_readback('http://mirror')
        self.mcp.passive=True;self.mcp.badchunk=True
        with self.assertRaises(EvidenceInvalid):self.scanner.report_readback('http://mirror')

if __name__=='__main__':unittest.main()
