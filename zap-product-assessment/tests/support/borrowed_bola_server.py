"""Standalone independent test target. Credentials arrive once on stdin; logs contain actor labels only."""
import base64
import hashlib
import hmac
import json
import secrets
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

inputs = json.loads(sys.stdin.readline())
variant = inputs['variant']
passwords = inputs['credentials']
key = secrets.token_bytes(32)
tokens = {}
account = {'id': 101, 'bank_name': 'Independent synthetic bank A', 'account_type': 'Checking',
           'branch_name': 'Synthetic branch', 'account_number_last_4': '9876', 'balance': 100.5,
           'recent_transactions': [{'date': '2026-10-18', 'amount': -5, 'description': 'Private A purchase',
                                    'status': 'Complete', 'receipt_id': 'SYNTH-A-001', 'type': 'Expense'}]}


def encode(value):
    return base64.urlsafe_b64encode(json.dumps(value, separators=(',', ':')).encode()).rstrip(b'=')


def token(actor):
    sub = 11 if actor == 'A' else 22
    if actor == 'B' and variant == 'wrong-subject':
        sub = 11
    body = encode({'sub': sub, 'iss': 'independent-bola-fixture', 'aud': 'bola-test-client',
                   'iat': int(time.time()), 'exp': int(time.time())+900})
    content = encode({'alg': 'HS256', 'typ': 'JWT'})+b'.'+body
    return (content+b'.'+base64.urlsafe_b64encode(hmac.digest(key, content, 'sha256')).rstrip(b'=')).decode()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def reply(self, status, body, actor):
        print(json.dumps({'actor': actor, 'method': self.command, 'path': self.path,
                          'status': status, 'cookiePresent': 'Cookie' in self.headers}), flush=True)
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.send_header('Set-Cookie', 'discard=this-synthetic-cookie; HttpOnly')
        self.end_headers()
        self.wfile.write(raw)

    def error(self, status, message, actor):
        self.reply(status, {'success': False, 'statusCode': status, 'message': message,
                           'timestamp': '2026-10-18T00:00:00.000Z', 'path': self.path}, actor)

    def do_POST(self):
        if self.path != '/api/auth/login':
            self.error(404, 'Not Found', 'anonymous')
            return
        size = int(self.headers.get('Content-Length', '0'))
        if not 0 < size <= 8192:
            self.error(400, 'Bad Request', 'anonymous')
            return
        payload = json.loads(self.rfile.read(size))
        actor = next((a for a, value in passwords.items() if payload == value), 'anonymous')
        if actor == 'anonymous' or actor == 'B' and variant == 'auth-failure':
            self.error(401, 'Unauthorized', actor)
            return
        issued = token(actor)
        tokens[issued] = actor
        self.reply(200, {'success': True, 'data': {'user': {'id': 11 if actor == 'A' else 22},
                                                 'accessToken': issued}}, actor)

    def do_GET(self):
        header = self.headers.get('Authorization', '')
        actor = tokens.get(header.removeprefix('Bearer '), 'anonymous')
        if actor == 'anonymous':
            self.error(401, 'Unauthorized', actor)
        elif self.path == '/api/v1/accounts':
            self.reply(200, {'success': True, 'data': {'user_id': 11 if actor == 'A' else 22,
                'accounts': [] if actor == 'B' or variant == 'missing-fixture' else [account]}}, actor)
        elif self.path == '/api/v1/accounts/101':
            if actor == 'A' or variant in ('vulnerable', 'leak-403', 'leak-404'):
                status = {'leak-403': 403, 'leak-404': 404}.get(variant, 200) if actor == 'B' else 200
                self.reply(status, {'success': True, 'data': account}, actor)
            else:
                self.error(403, 'You do not have permission to view this account information.', actor)
        else:
            self.error(404, 'This account was not found.', actor)


print(json.dumps({'ready': True, 'sourceVersion': 'independent-borrowed-account-v1'}), flush=True)
ThreadingHTTPServer(('0.0.0.0', 18080), Handler).serve_forever()
