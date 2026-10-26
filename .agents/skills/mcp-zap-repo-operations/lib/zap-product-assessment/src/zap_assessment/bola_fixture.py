"""Isolated synthetic account contract. Only this server owns its in-memory fixtures."""
import secrets
import threading
import time
from contextlib import contextmanager
from datetime import timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from .bola import LIST, OPERATIONS, strict_json
from .contracts import canonical, digest, utcnow


@contextmanager
def account_fixture(variant='fixed', operational=None):
    tokens = {actor: secrets.token_urlsafe(32) for actor in ('A', 'B')}
    issued_tokens = dict(tokens)
    logins = {a: {'email': secrets.token_hex(12)+'@fixture.invalid', 'password': secrets.token_urlsafe(32)}
              for a in ('A', 'B')} if operational is not None else {}
    if operational is not None:
        tokens.clear()
    arrivals = []  # Actor labels, never Authorization headers or token fingerprints.
    account = {'id': 101, 'bank_name': 'Synthetic Private Bank A', 'account_type': 'Checking',
               'branch_name': 'Run-owned branch', 'account_number_last_4': '9876', 'balance': 123.45,
               'recent_transactions': [{'date': '2026-10-18', 'amount': -5, 'description': 'Private synthetic purchase',
                                        'status': 'Complete', 'receipt_id': 'SYNTH-A-RECEIPT', 'type': 'Expense'}]}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            if operational is None or self.path != '/api/auth/login':
                self.error(404, 'Not Found')
                return
            size = int(self.headers.get('Content-Length', '0'))
            if not 0 < size <= 8192:
                self.error(400, 'Bad Request')
                return
            try:
                payload = strict_json(self.rfile.read(size))
            except (ValueError, TypeError):
                self.error(400, 'Bad Request')
                return
            actor = next((a for a, credentials in logins.items() if payload == credentials), 'anonymous')
            arrivals.append({'actor': actor, 'path': self.path, 'method': 'POST',
                             'cookiePresent': 'Cookie' in self.headers})
            if actor == 'anonymous' or actor == 'B' and variant == 'login-failure':
                self.error(401, 'Unauthorized')
                return
            tokens[actor] = issued_tokens[actor]
            subject = 11 if actor == 'A' else 22
            if actor == 'B' and variant == 'login-wrong-identity':
                subject = 11
            self.reply(200, {'success': True, 'data': {'user': {'id': subject}, 'accessToken': tokens[actor]}})

        def do_GET(self):
            actor = next((a for a, t in tokens.items() if self.headers.get('Authorization') == 'Bearer '+t), 'anonymous')
            arrivals.append({'actor': actor, 'path': self.path, 'method': 'GET',
                             'cookiePresent': 'Cookie' in self.headers})
            if variant == 'timeout':
                time.sleep(0.4)
            if variant == 'redirect':
                self.send_response(302)
                self.send_header('Location', 'http://127.0.0.1:1/canary')
                self.end_headers()
                return
            if variant == 'oversize':
                self.reply(200, {'data': 'x'*65537})
                return
            if actor == 'anonymous' or actor == 'B' and variant == 'auth-failure':
                self.error(401, 'Unauthorized')
                return
            if self.path == LIST:
                user_id = 11 if actor == 'A' else 22
                if actor == 'B' and variant == 'wrong-identity':
                    user_id = 11
                self.reply(200, {'success': True, 'data': {'user_id': user_id,
                           'accounts': [] if variant == 'missing-fixture' or actor == 'B' else [account]}})
            elif self.path == LIST+'/101':
                if actor == 'A':
                    if variant == 'owner-failure':
                        self.error(404, 'This account was not found.')
                    else:
                        self.reply(200, {'success': True, 'data': account})
                elif variant in ('vulnerable', 'leak-403', 'leak-404'):
                    self.reply({'vulnerable': 200, 'leak-403': 403, 'leak-404': 404}[variant], {'success': True, 'data': account})
                elif variant == 'message-leak':
                    self.error(403, account['bank_name'])
                elif variant == 'ambiguous-denial':
                    self.reply(403, {'success': False, 'data': {}})
                elif variant == 'fixed-404':
                    self.error(404, 'This account was not found.')
                else:
                    self.error(403, 'You do not have permission to view this account information.')
            else:
                self.error(404, 'This account was not found.')

        def error(self, status, message):
            self.reply(status, {'success': False, 'statusCode': status, 'message': message,
                               'timestamp': '2026-10-18T00:00:00.000Z', 'path': self.path})

        def reply(self, status, body):
            raw = canonical(body)
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(raw)))
            # Client must ignore Set-Cookie, never replay it.
            self.send_header('Set-Cookie', 'fixture-cookie=discard; HttpOnly')
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    config = {'schemaVersion': '1.2', 'adapter': 'finalsource-account-read-v1', 'productId': 'synthetic-account',
              'environment': {'kind': 'synthetic', 'identity': 'isolated-loopback-'+variant,
                              'evidenceRef': 'user-authorized-synthetic:M3-pilot'},
              'origin': 'http://127.0.0.1:'+str(server.server_port), 'targetBuildRef': 'synthetic-account-'+variant+'-v1',
              'binding': None, 'fixture': {'accountId': 101, 'ownerId': 11, 'nonOwnerId': 22,
                                          'provenanceRef': 'in-memory-run-owned-fixture'},
              'credentials': {'A': {'tokenEnv': 'BOLA_TEST_A'}, 'B': {'tokenEnv': 'BOLA_TEST_B'}},
              'anonymous': True, 'requestTimeoutSeconds': 1, 'totalTimeoutSeconds': 20, 'maxRate': 2,
              'retentionDays': 14}
    now = utcnow()
    def authority():
        return {'schemaVersion': '1.2', 'recordId': 'synthetic-M3-account', 'owner': 'isolated-fixture-harness',
                'issuer': 'isolated-fixture-harness', 'approvalRef': 'user-authorized-synthetic:M3-pilot',
                'validFrom': (now-timedelta(minutes=1)).isoformat(), 'validUntil': (now+timedelta(minutes=10)).isoformat(),
                'configHash': digest(config), 'operations': OPERATIONS, 'fixtureMode': 'borrowed-read-only'}
    if operational is not None:
        operational.update(server=server, thread=thread, arrivals=arrivals,
                           canaries=[*issued_tokens.values(), *(x for v in logins.values() for x in v.values())])
        env = {'BOLA_LOGIN_'+a: canonical(logins[a]).decode() for a in ('A', 'B')}
    else:
        env = {'BOLA_TEST_A': tokens['A'], 'BOLA_TEST_B': tokens['B']}
    try:
        yield config, authority, env, arrivals
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        tokens.clear()
        issued_tokens.clear()
        logins.clear()
