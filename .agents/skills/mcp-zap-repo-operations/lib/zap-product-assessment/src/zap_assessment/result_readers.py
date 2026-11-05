"""Bounded readers for hostile test data. These functions never start producers."""
import json
from pathlib import Path


def read_jsonl(path):
    """JSONL is delimited by LF, not by Unicode separators inside JSON strings.

    Invalid outer records fail with their line number. Deliberately malformed
    HTTP bodies are strings within valid records and must remain available.
    """
    result = []
    for number, line in enumerate(Path(path).read_text().split('\n'), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f'invalid JSONL record at line {number}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'JSONL object required at line {number}')
        result.append(row)
    return result


def collect_alerts(fetch, total, *, page_size=100, max_pages=1000):
    """Read all native IDs, allowing an identical boundary overlap.

    fetch(start, count) returns native records. Advance by records received,
    including overlaps, rather than by unique IDs or a product-specific +1.
    Empty, repeated, conflicting and incomplete pages never become a full read.
    Call after producers/passive tasks stop; caller verifies total is stable.
    """
    if type(total) is not int or total < 0 or type(page_size) is not int or page_size < 1:
        raise ValueError('invalid alert pagination limits')
    found = {}; start = 0
    for _ in range(max_pages):
        if len(found) == total:
            return list(found.values())
        batch = fetch(start, page_size)
        if not isinstance(batch, list) or len(batch) > page_size:
            raise ValueError('invalid alert page')
        before = len(found)
        for row in batch:
            if not isinstance(row, dict) or row.get('id') is None:
                raise ValueError('native alert ID missing')
            key = str(row['id'])
            if key in found and found[key] != row:
                raise ValueError('native alert changed during pagination')
            found[key] = row
        if len(found) > total:
            raise ValueError('native alert count changed')
        if len(found) == before:
            raise ValueError('alert page made no progress; collection incomplete')
        start += len(batch)
    raise ValueError('alert page limit; collection incomplete')


def read_native_alerts(engine, origin, *, page_size=100):
    """Export native IDs with stable pre/post totals, including zero.

    engine(component, category, name, arguments) is an admitted read transport.
    Producers must already be stopped and passive analysis settled by the caller.
    Equal totals cannot prove absence of same-count concurrent replacement.
    """
    if type(page_size) is not int or page_size < 1:
        raise ValueError('invalid native alert page size')
    def total():
        count = int(engine('core', 'view', 'numberOfAlerts', {'baseurl': origin})['numberOfAlerts'])
        if count < 0:
            raise ValueError('negative native alert total')
        return count
    expected = total()
    # ZAP can repeat the boundary record at a positive start offset. Request
    # full bounded pages and let the existing identity/content-aware collector
    # advance by actual returned rows. Truncating the last request to the unique
    # remainder can omit its final record when that page contains an overlap.
    alerts = collect_alerts(lambda start, count: engine('alert', 'view', 'alerts',
        {'baseurl': origin, 'start': start, 'count': count})['alerts'],
        expected, page_size=page_size)
    if total() != expected:
        raise ValueError('native alert total changed during export')
    return alerts


def bind_zap_message(operation, fetch_message, *, scanner_resource, session, message_id, request_sha256, response_sha256):
    """Read one native message from an already-admitted, session-bound reader.

    The caller derives the expected digest from the verified actor's exact wire
    request. The reader returns scannerResourceId, sessionId and the raw message
    from the bound scanner session. No HTTP
    headers, cookies, or body bytes are copied into the operation.
    """
    import copy
    import hashlib

    if operation.get('provenance', {}).get('transport') not in ('zap-proxy', 'zap-sendRequest', 'zap-native'):
        raise ValueError('ZAP transport required')
    message_id = str(message_id)
    if not message_id.isascii() or not message_id.isdecimal():
        raise ValueError('native message ID required')
    captured = fetch_message(message_id)
    if (not isinstance(captured, dict) or captured.get('scannerResourceId') != scanner_resource
            or captured.get('sessionId') != session or not isinstance(captured.get('message'), dict)):
        raise ValueError('native message scanner/session mismatch')
    message = captured['message']
    if str(message.get('id')) != message_id:
        raise ValueError('native message ID mismatch')
    digests = {}
    for kind, expected in (('request', request_sha256), ('response', response_sha256)):
        header, body = message.get(kind + 'Header'), message.get(kind + 'Body')
        if not isinstance(header, str) or not header or not isinstance(body, str):
            raise ValueError('native message ' + kind + ' incomplete')
        observed = hashlib.sha256(json.dumps([header, body], ensure_ascii=False,
                                             separators=(',', ':')).encode()).hexdigest()
        if observed != expected:
            raise ValueError('native message differs from verified ' + kind)
        digests[kind + 'Sha256'] = observed
    result = copy.deepcopy(operation)
    identity = {'scannerResourceId': scanner_resource, 'sessionId': session, 'messageId': message_id}
    result['provenance'].update(identity)
    result['zapCapture'] = {**identity, **digests}
    context = result.get('coverageContext', {})
    result['zapMessageReceipt'] = {**identity, 'caseId': result.get('caseId'), 'resultPath': '/zapCapture',
                                  **{key: context.get(key) for key in ('actorRef', 'fixtureRef', 'requestRef')},
                                  **digests}
    from .question_evidence import verified_zap_message
    if not verified_zap_message(result):
        raise ValueError('native message receipt lacks case or session binding')
    return result
