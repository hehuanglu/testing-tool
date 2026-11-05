"""Finite v2 readback executor for a plan-bound local MCP scanner."""
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, ProxyHandler, build_opener

from .contracts import Blocked, digest
from .safety_io import atomic_bytes
from .transport import MCP, field

ENDPOINT = 'http://127.0.0.1:7456/mcp'
TOOLS = frozenset({'zap_findings_summary', 'zap_findings_details',
                   'zap_scan_history_list', 'zap_scan_history_get'})


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def local_request(url, method, headers, body, timeout):
    if url != ENDPOINT or method != 'POST':
        raise Blocked('local MCP binding mismatch')
    key = os.environ.get('ZAP_MCP_API_KEY')
    if key:
        headers = {**headers, 'X-API-Key': key}
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(Request(url, data=body, headers=headers, method=method), timeout=timeout) as response:
            data = response.read(8_000_001)
            if len(data) > 8_000_000:
                raise Blocked('MCP HTTP response exceeds limit')
            return {'status': response.status, 'headers': {k.lower(): v for k, v in response.headers.items()},
                    'body': data.decode('utf-8')}
    except (HTTPError, URLError, TimeoutError) as exc:
        raise Blocked('local MCP transport failed') from exc


def receipt_path(coordinator, packet, action_id):
    return coordinator.root / ('native-read-' + digest([packet['taskId'], action_id]) + '.json')


def history_candidates(text, target):
    """Accept only exact-target rows from the server's bounded text ledger."""
    rows = re.split(r'(?m)^\d+\. ', text)[1:]
    result = []
    for row in rows:
        lines = row.splitlines()
        if not lines:
            continue
        heading = re.fullmatch(r'([A-Za-z0-9._:-]+) \[([A-Za-z0-9_-]+)\]', lines[0])
        if heading and lines.count('   Target: ' + target) == 1:
            result.append(heading[1])
    return sorted(set(result))


def execute_read(run, packet, action_id, coordinator, *, request=local_request, history_entry_id=None):
    matches = [action for case in packet['cases'] for action in case.get('actions', []) if action['id'] == action_id]
    if len(matches) != 1:
        raise Blocked('approved native read action required')
    action = matches[0]
    recovering = coordinator.validate_dispatch_binding(run, packet, action)
    tool = action.get('toolName')
    target = packet['authority']['target']
    args = action.get('arguments', {})
    target_url = urlsplit(target)
    if (target_url.scheme not in ('http', 'https') or not target_url.hostname or target_url.username is not None
            or target_url.fragment or any(char.isspace() for char in target) or not isinstance(args, dict)):
        raise Blocked('native read requires an absolute approved target and object arguments')
    scanner = action.get('scannerResourceId')
    if (action['effect'] != 'read' or tool not in TOOLS or action.get('mcpEndpoint') != ENDPOINT
        or not scanner or scanner not in packet['resourceIds'] or action.get('fixtureOptions')):
        raise Blocked('native read requires explicit tool, local endpoint and scanner lease')
    from_action = action.get('historyEntryFrom')
    if from_action is not None:
        if (tool != 'zap_scan_history_get' or not isinstance(from_action, str)
                or not isinstance(history_entry_id, str) or not history_entry_id or args):
            raise Blocked('approved history lookup requires a retained list and candidate entry ID')
        previous = receipt_path(coordinator, packet, from_action)
        if previous.is_symlink() or not previous.is_file():
            raise Blocked('approved history list receipt missing')
        retained = json.loads(previous.read_bytes())
        if (retained.get('packetDigest') != packet['packetDigest'] or retained.get('actionId') != from_action
                or retained.get('toolName') != 'zap_scan_history_list' or retained.get('scannerResourceId') != scanner
                or history_entry_id not in history_candidates(retained.get('readback', ''), target)):
            raise Blocked('entry is outside the retained exact-target history list')
        args = {'entryId': history_entry_id}
    elif history_entry_id is not None:
        raise Blocked('history entry selection was not approved')
    if tool in ('zap_findings_summary', 'zap_findings_details'):
        if args.get('baseUrl') != target:
            raise Blocked('native findings target differs from approved target')
        if tool == 'zap_findings_details' and args.get('includeInstances') is True:
            if type(args.get('limit')) is not int or not 1 <= args['limit'] <= 20:
                raise Blocked('native findings sample requires limit 1–20')
    elif tool == 'zap_scan_history_list':
        if args.get('target') != target or type(args.get('limit')) is not int or not 1 <= args['limit'] <= 20:
            raise Blocked('history list requires approved target filter and limit 1–20')
    elif not isinstance(args.get('entryId'), str) or not args['entryId'].strip():
        raise Blocked('history get requires an explicit approved entry ID')

    mcp = MCP(request, allowed_tools=TOOLS, required_tools={tool})
    info = mcp.initialize()
    server_digest = digest(info['serverInfo'])
    schema_digest = digest(info['tools'][tool])
    if action.get('mcpServerInfoDigest', server_digest) != server_digest:
        raise Blocked('receiving MCP server info differs from approved binding')
    mcp.validate_call(tool, args)
    receipt = receipt_path(coordinator, packet, action_id)
    if receipt.exists() or receipt.is_symlink():
        raise Blocked('native read receipt already exists; inspect retained readback')
    candidate = {'id': scanner, 'tools': {'tools': [
        {'name': name, 'inputSchema': schema} for name, schema in info['tools'].items()]},
        'support': {key: {'verified': True, 'basis': 'local scanner native read contract'}
                    for key in ('transport', 'auth', 'request', 'fixture', 'readback')}}

    def read(_approved):
        text = mcp.call(tool, args)
        if tool == 'zap_scan_history_get':
            if field(text, 'Entry ID') != args['entryId'] or field(text, 'Target') != target:
                raise Blocked('history entry does not match approved entry and target')
        value = {'taskId': packet['taskId'], 'packetDigest': packet['packetDigest'], 'actionId': action_id,
                 'scannerResourceId': scanner, 'toolName': tool, 'arguments': args, 'readback': text,
                 'serverInfoDigest': server_digest, 'toolSchemaDigest': schema_digest,
                 'terminalEvidence': False}
        atomic_bytes(receipt, json.dumps(value, ensure_ascii=False).encode())
        return str(receipt)

    if not recovering:
        coordinator.acquire(run, packet)
    if from_action is not None:
        outcome = coordinator.dispatch(run, packet, action, read, executor_id=scanner)
        return {'dispatched': True, 'outcome': outcome}
    return coordinator.dispatch_routed(run, packet, action, [candidate], {scanner: read})
