import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from zap_assessment.anonymous_runner import RecordedMCP
from zap_assessment.contracts import Blocked
from zap_assessment.fe_authenticated_mcp import RecordedMCP as FERecordedMCP
from zap_assessment.transport import MCP


class MCPTransportGuardsTests(unittest.TestCase):
    def test_both_clients_validate_before_dispatch_and_bound_the_result(self):
        tool = 'zap_attack_start'
        with tempfile.TemporaryDirectory() as directory:
            request = Mock()
            clients = (MCP(request, required_tools=()), RecordedMCP(SimpleNamespace(request=request), Path(directory)))
            for client in clients:
                with self.subTest(client=type(client).__name__):
                    client.contracts = {tool: {'type': 'object', 'properties': {'targetUrl': {'type': 'string'}}}}
                    client.require_tools((tool,))
                    client.rpc = Mock(return_value={'content': [{'type': 'text', 'text': 'x' * 2000001}]})
                    with self.assertRaisesRegex(Blocked, 'unsupported MCP argument'):
                        client.call(tool, {'targetUrl': 'https://example.test', 'postData': '{}'})
                    with self.assertRaisesRegex(Blocked, 'required MCP capability absent'):
                        client.require_tools(('zap_attack_stop',))
                    client.rpc.assert_not_called()
                    with self.assertRaisesRegex(Blocked, 'output exceeds limit'):
                        client.call(tool, {'targetUrl': 'https://example.test'})

    def test_fe_report_recording_does_not_mask_malformed_envelope(self):
        tool = 'zap_report_read_chunk'
        with tempfile.TemporaryDirectory() as directory:
            client = FERecordedMCP(SimpleNamespace(request=Mock()), Path(directory))
            client.contracts = {tool: {'type': 'object', 'properties': {}}}
            for content, error in ((None, 'MCP tool error'), ([None], 'tool content contract')):
                with self.subTest(content=content):
                    client.rpc = Mock(return_value={'content': content})
                    with self.assertRaisesRegex(Blocked, error):
                        client.call(tool, {})
