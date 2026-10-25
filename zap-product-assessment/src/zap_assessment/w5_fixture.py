"""Loopback-only synthetic identity/TTL fixture, never a product adapter.

Canaries are generated in memory. The server owns expiry/revocation timestamps;
the client does not mutate tokens to simulate natural expiry. No database, shared
Docker or finalsource traffic. This fixture cannot attest ZAP secret sinks.
"""
from contextlib import contextmanager
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import secrets
import threading
import time

from .auth_lifecycle import ActorSession, ProducerStop
from .secret_audit import CanaryAuditor

BUILD = 'synthetic-auth/1.0'


class Target:
    def __init__(self):
        self.lock = threading.RLock()
        self.canaries = []
        self.passwords = {a: self.secret() for a in ('A', 'B')}
        self.sessions = {}
        self.rows = []
        self.ttl = 10
        self.reject_refresh = False
        self.login_failure = False
        self.identity_mode = 'json'
        self.protected_mode = 'json'
        self.roles = {'A': 'member', 'B': 'member'}
        self.release_request = threading.Event()
        self.request_entered = threading.Event()
        self.build = BUILD

    def secret(self):
        token = 'W5-canary-' + secrets.token_urlsafe(30)
        self.canaries.append(token)
        return token

    def issue(self, actor):
        token = self.secret()
        self.sessions[token] = {'actor': actor, 'expiry': time.monotonic() + self.ttl, 'revoked': False}
        return token

    def fault(self, kind, actor='A'):
        with self.lock:
            for row in self.sessions.values():
                if row['actor'] == actor:
                    if kind in ('revoke', 'invalid-token'):
                        row['revoked'] = True
                    elif kind == 'role-change':
                        self.roles[actor] = 'viewer'
            self.rows.append({'event': 'server_fault', 'kind': kind, 'actorRef': actor,
                              'atMonotonic': time.monotonic()})

    def handle(self, method, path, token, data):
        with self.lock:
            now = time.monotonic()
            session = self.sessions.get(token)
            actor = session['actor'] if session else None
            valid = session and not session['revoked'] and now < session['expiry']
            self.rows.append({'event': 'arrival', 'method': method, 'path': path,
                              'actorRef': actor, 'atMonotonic': now,
                              'authenticated': bool(valid),
                              'serverExpiry': session['expiry'] if session else None})
            if path == '/login':
                actor = data.get('actor')
                if self.login_failure or actor not in self.passwords or data.get('password') != self.passwords[actor]:
                    return 401, {}, {'error': 'login'}
                return 200, {}, {'accessToken': self.issue(actor)}
            if not valid:
                return 401, {}, {'error': 'expired-or-revoked'}
            if path == '/identity':
                if self.identity_mode == 'html':
                    return 200, {'Content-Type': 'text/html'}, '<html>login</html>'
                if self.identity_mode == 'wrong-actor':
                    actor = 'B' if actor == 'A' else 'A'
                return 200, {}, {'subject': 'subject-' + actor, 'role': self.roles[actor], 'buildRef': self.build}
            if path == '/refresh':
                if self.reject_refresh:
                    return 401, {}, {'error': 'refresh-rejected'}
                session['revoked'] = True
                return 200, {}, {'accessToken': self.issue(actor)}
            if path == '/logout':
                session['revoked'] = True
                return 200, {}, {'loggedOut': True}
            if path == '/api/v1/accounts':
                if self.protected_mode == '401':
                    return 401, {}, {'error': 'auth-lost'}
                if self.protected_mode == 'html':
                    return 200, {'Content-Type': 'text/html'}, '<html>login</html>'
                if self.protected_mode == 'echo-secret':
                    return 200, {}, {'secret': token}
                if self.protected_mode == 'cookie':
                    return 200, {'Set-Cookie': 'session=' + token}, {'ok': True}
                return 200, {}, {'actorRef': actor, 'accounts': ['owned-' + actor]}
            return 404, {}, {'error': 'route'}


class FixtureServer(ThreadingHTTPServer):
    daemon_threads = True


@contextmanager
def server(target):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def handle_request(self):
            # This is a deliberately fixed synthetic route set, not a proxy.
            try:
                size = int(self.headers.get('Content-Length', '0'))
                if not 0 <= size <= 4096:
                    raise ValueError()
                body = json.loads(self.rfile.read(size)) if size else {}
                token = self.headers.get('Authorization', '').removeprefix('Bearer ')
                if self.path == '/api/v1/accounts' and target.protected_mode == 'in-flight':
                    target.request_entered.set()
                    target.release_request.wait(2)
                status, headers, value = target.handle(self.command, self.path, token, body)
                content_type = headers.pop('Content-Type', 'application/json')
                blob = json.dumps(value).encode() if content_type == 'application/json' else value.encode()
                self.send_response_only(status)
                self.send_header('Content-Type', content_type)
                for key, value in headers.items():
                    self.send_header(key, value)
                self.send_header('Content-Length', str(len(blob)))
                self.end_headers()
                self.wfile.write(blob)
            except (ValueError, OSError):
                self.close_connection = True

        do_GET = handle_request
        do_POST = handle_request

    httpd = FixtureServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=httpd.serve_forever, kwargs={'poll_interval': .02}, daemon=True)
    worker.start()
    try:
        yield httpd.server_port
    finally:
        target.release_request.set()
        httpd.shutdown()
        httpd.server_close()
        worker.join(2)
        if worker.is_alive():
            raise RuntimeError('fixture stop unconfirmed')


class Transport:
    def __init__(self, port, actor, password):
        self.port, self.actor, self.password = port, actor, password

    def exchange(self, method, path, *, token=None, data=None):
        connection = http.client.HTTPConnection('127.0.0.1', self.port, timeout=1)
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = 'Bearer ' + token
        try:
            connection.request(method, path, None if data is None else json.dumps(data).encode(), headers)
            response = connection.getresponse()
            blob = response.read(65537)
            if len(blob) > 65536:
                raise ValueError('response bound')
            return {'status': response.status, 'headers': dict(response.getheaders()),
                    'contentType': response.getheader('Content-Type'), 'body': blob.decode()}
        finally:
            connection.close()

    @staticmethod
    def parsed(response):
        if response['status'] != 200 or response['contentType'] != 'application/json':
            raise ValueError('identity/auth response rejected')
        value = json.loads(response['body'])
        if not isinstance(value, dict):
            raise ValueError('identity/auth shape rejected')
        return value

    def login(self):
        return self.parsed(self.exchange('POST', '/login', data={
            'actor': self.actor, 'password': self.password}))['accessToken']

    def identity(self, token):
        return self.parsed(self.exchange('GET', '/identity', token=token))

    def refresh(self, token):
        return self.parsed(self.exchange('POST', '/refresh', token=token))['accessToken']

    def logout(self, token):
        return self.parsed(self.exchange('POST', '/logout', token=token))

    def protected(self, token, method, path, body):
        if method != 'GET' or path != '/api/v1/accounts' or body is not None:
            raise ValueError('fixture protected scope')
        return self.exchange(method, path, token=token)


def session(target, port, events, actor='A', *, producer=None,
            run_id='w5-fixture', plan_hash='a'*64, **options):
    # Snapshot canary inventory AFTER login/refresh as tokens are minted there.
    def safe(response):
        return CanaryAuditor(target.canaries).response_safe(response)

    return ActorSession(actor=actor, subject='subject-' + actor, role='member',
                        build_ref=BUILD, run_id=run_id, plan_hash=plan_hash,
                        transport=Transport(port, actor, target.passwords[actor]),
                        record=events.append,
                        producer=producer or ProducerStop(lambda: True, lambda: True),
                        response_safe=safe, **options)


def child():
    """Owned subprocess protocol for crash/restart tests; secrets only on stdin.

    This is not a network guard or a mode-entry CLI. Dump suppression is observed
    for this process, not an attestation of host swap/OS diagnostics or scanner DB.
    """
    import resource
    import sys
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    config = json.loads(sys.stdin.readline())
    events = []
    # This subprocess cannot read target-side canary state, so it does not perform
    # protected export. It only tests bootstrap identity and empty restart state.
    candidate = ActorSession(actor='A', subject='subject-A', role='member',
                             build_ref=BUILD, run_id=config.get('runId', 'w5-child-fixture'),
                             plan_hash=config.get('planHash', 'a'*64),
                             transport=Transport(config['port'], 'A', config.get('password')),
                             record=events.append, producer=ProducerStop(lambda: True, lambda: True))
    if config.get('bootstrap'):
        candidate.bootstrap()
    print(json.dumps({'snapshot': candidate.snapshot(), 'coreLimit': list(resource.getrlimit(resource.RLIMIT_CORE))}), flush=True)
    for line in sys.stdin:
        command = json.loads(line)
        if command == 'protected':
            try:
                candidate.protected('GET', '/api/v1/accounts')
                result = 'unexpected-admission'
            except Exception:
                result = 'blocked'
            print(json.dumps({'result': result, 'snapshot': candidate.snapshot()}), flush=True)
        elif command == 'close':
            candidate.close()
            return


if __name__ == '__main__':
    import sys
    if sys.argv[1:] != ['--child']:
        raise SystemExit('synthetic child protocol only')
    child()
