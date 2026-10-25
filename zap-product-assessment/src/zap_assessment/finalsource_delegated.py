"""Finalsource subject-only adapter for a trusted isolated credential holder.

No entry point admits product use. Caller must supply the operational attestor,
private SourceReference and owned producer through CredentialBroker. This module
never trusts JWT claims, a login subject, or a constant role as an identity oracle.
"""
from dataclasses import dataclass
import http.client
import ipaddress
import json
import re
import threading
import time
from urllib.parse import urlsplit, unquote_to_bytes

from .credential_broker import BrokerBinding
from .errors import Blocked
from .private_db import strict_json


@dataclass(frozen=True)
class TargetBinding:
    container_id: str
    image_id: str
    started_at: str
    network_id: str
    address: str
    port: int

    def __post_init__(self):
        if (not re.fullmatch('[0-9a-f]{64}', self.container_id)
                or not re.fullmatch('sha256:[0-9a-f]{64}', self.image_id)
                or not re.fullmatch('[0-9a-f]{64}', self.network_id)
                or not isinstance(self.started_at, str) or not self.started_at
                or type(self.port) is not int or not 1 <= self.port <= 65535):
            raise Blocked('finalsource_target_binding_invalid')
        try:
            if str(ipaddress.ip_address(self.address)) != self.address:
                raise ValueError()
        except (ValueError, TypeError):
            raise Blocked('finalsource_target_address_invalid') from None


class GetPolicy:
    """Validate names without reserializing any admitted active query payload."""
    PARAMETERS = {'/api/v1/accounts': frozenset(),
                  '/api/v1/transactions': frozenset(('type', 'limit', 'offset')),
                  '/api/v1/savings/summary': frozenset(('year',))}

    def __init__(self, operations, max_query_bytes=4096):
        if not operations or not set(operations) <= self.PARAMETERS.keys():
            raise Blocked('finalsource_operations_invalid')
        self.operations = frozenset(operations); self.max_query_bytes = max_query_bytes

    def check(self, method, path, body=None):
        if (method != 'GET' or body is not None or not isinstance(path, str)
                or not path.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in path)
                or '\\' in path or path.startswith('//')):
            raise Blocked('finalsource_request_outside_scope')
        u = urlsplit(path)
        if (u.scheme or u.netloc or u.fragment or u.path not in self.operations
                or len(u.query) > self.max_query_bytes):
            raise Blocked('finalsource_request_outside_scope')
        seen = set()
        for pair in u.query.split('&') if u.query else []:
            name, sep, value = pair.partition('=')
            # Encoded/duplicate parameter names and malformed escapes introduce
            # parser disagreement; values retain their original wire bytes.
            if (not sep or name not in self.PARAMETERS[u.path] or name in seen
                    or re.search(r'%(?![0-9a-fA-F]{2})', value)):
                raise Blocked('finalsource_query_outside_scope')
            seen.add(name)
        return path


def accounts_subject(response):
    """Protected principal projection, independent of account membership."""
    try:
        if response['status'] != 200 or response['contentType'] != 'application/json':
            raise ValueError()
        value = strict_json(response['body']); data = value['data']
        if (value['success'] is not True or type(data['user_id']) is not int
                or data['user_id'] <= 0 or not isinstance(data['accounts'], list)):
            raise ValueError()
        return str(data['user_id'])
    except Exception:
        raise Blocked('finalsource_subject_oracle_rejected') from None


class FinalsourceAdapter:
    def __init__(self, *, binding, target, policy, require_current, record,
                 timeout=5, minimum_interval=.5, clock=time.monotonic):
        if (not isinstance(binding, BrokerBinding) or binding.role is not None
                or not isinstance(target, TargetBinding) or not isinstance(policy, GetPolicy)
                or binding.origin != f'http://{target.address}:{target.port}'
                or not callable(require_current) or not callable(record)
                or not 0 < timeout <= 8 or minimum_interval < .5):
            raise Blocked('finalsource_adapter_contract_invalid')
        self.binding = binding; self.target = target; self.policy = policy
        self.require_current = require_current; self.record = record; self.timeout = timeout
        self.interval = minimum_interval; self.clock = clock; self.last = None
        self.lock = threading.RLock(); self.latched = False; self.login_attempted = False

    def _exchange(self, method, path, token=None, data=None):
        with self.lock:
            if self.latched:
                raise Blocked('finalsource_adapter_latched')
            try:
                if self.require_current(self.binding, self.target) is not True:
                    raise ValueError()
                if self.last is not None:
                    time.sleep(max(0, self.interval - (self.clock() - self.last)))
                # Recheck after waiting; expiry/drift may occur while rate-limited.
                if self.require_current(self.binding, self.target) is not True:
                    raise ValueError()
                headers = {'Host': urlsplit(self.binding.origin).netloc, 'Accept': 'application/json',
                           'Connection': 'close'}
                if token is not None:
                    if (not isinstance(token, str) or not token or len(token) > 8192
                            or not token.isascii() or any(ord(c) < 33 for c in token)):
                        raise ValueError()
                    headers['Authorization'] = 'Bearer ' + token
                if data is not None: headers['Content-Type'] = 'application/json'
                self.last = self.clock()
                conn = http.client.HTTPConnection(self.target.address, self.target.port, timeout=self.timeout)
                try:
                    conn.request(method, path, body=data, headers=headers)
                    response = conn.getresponse(); blob = response.read(2 * 1024 * 1024 + 1)
                    pairs = response.getheaders(); names = [k.lower() for k, v in pairs]
                    if (len(blob) > 2 * 1024 * 1024 or len(names) != len(set(names))
                            or any(k in names for k in ('set-cookie', 'authorization', 'location'))
                            or 300 <= response.status < 400):
                        raise ValueError()
                    result = {'status': response.status, 'headers': dict(pairs),
                              'contentType': response.getheader('Content-Type', '').split(';')[0].lower(),
                              'body': blob.decode('utf-8')}
                finally:
                    conn.close()
                if self.require_current(self.binding, self.target) is not True:
                    raise ValueError()
                # No URL/query/body/headers/token or exception strings in journal.
                self.record({'event': 'final_hop_response', 'method': method,
                             'operationPath': urlsplit(path).path, 'status': result['status'],
                             'actorRef': self.binding.actor_ref, 'bindingObserved': True,
                             'atMonotonic': self.clock(), 'attribution': 'holder-transport-observation'})
                return result
            except Exception:
                self.latched = True
                raise Blocked('finalsource_transport_or_binding_lost') from None

    def login(self, credential):
        if self.login_attempted:
            raise Blocked('finalsource_login_no_replay')
        self.login_attempted = True
        try:
            data = json.dumps({'email': credential['username'], 'password': credential['password']}).encode()
            response = self._exchange('POST', '/api/auth/login', data=data)
            value = strict_json(response['body'])
            token = value['data']['accessToken']
            if (response['status'] != 200 or response['contentType'] != 'application/json'
                    or value['success'] is not True or not isinstance(token, str) or not token):
                raise ValueError()
            return token
        except Exception:
            self.latched = True
            raise Blocked('finalsource_login_rejected_no_replay') from None

    def identity(self, token):
        subject = accounts_subject(self._exchange('GET', '/api/v1/accounts', token))
        return {'subject': subject, 'role': None, 'buildRef': self.binding.build_ref}

    def protected(self, token, method, path, body):
        self.policy.check(method, path, body)
        return self._exchange(method, path, token)

    def refresh(self, token):
        raise Blocked('finalsource_refresh_not_observed')

    def logout(self, token):
        raise Blocked('finalsource_server_logout_not_observed')
