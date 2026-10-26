"""Owned W8 SQLite/HTML sinks. No product URL, auth or external dependencies."""
import hashlib
import html
import json
import os
from pathlib import Path
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit

ORIGIN = 'http://127.0.0.1:18080'
RULES = {'sqli': '40018', 'xss': '40012'}
WITNESSES = {'sqli': "' OR '1'='1' -- ", 'xss': '<script>alert(937)</script>'}


def fixture(seed):
    tag = hashlib.sha256(str(seed).encode()).hexdigest()[:12]
    return {'tag': tag, 'names': ['alpha-' + tag, 'hidden-' + tag],
            'vectors': [{'technique': t, 'ruleId': RULES[t], 'method': 'GET',
                         'path': '/' + t, 'parameter': 'name' if t == 'sqli' else 'q',
                         'baseline': 'alpha-' + tag if t == 'sqli' else 'hello-' + tag,
                         'sink': 'sqlite-select' if t == 'sqli' else 'html-body-text'}
                        for t in RULES]}


def exercise(variant, config, technique, value, missing_sink=False):
    """Telemetry is captured around actual sqlite execute / HTML rendering."""
    if missing_sink:
        return 200, 'text/html', b'<html><body>no sink</body></html>', {'kind': 'missing'}
    if technique == 'sqli':
        connection = sqlite3.connect(':memory:')
        connection.execute('CREATE TABLE items (name TEXT)')
        connection.executemany('INSERT INTO items VALUES (?)', [(n,) for n in config['names']])
        statement = "SELECT name FROM items WHERE name = '" + value + "'" if variant == 'vulnerable' else 'SELECT name FROM items WHERE name = ?'
        parameters = [] if variant == 'vulnerable' else [value]
        rows = []; error = None
        try:
            rows = [r[0] for r in connection.execute(statement, parameters).fetchall()]
        except sqlite3.Error as exc:
            error = str(exc)
        finally:
            connection.close()
        body = ('SQLite error: ' + error) if error else json.dumps({'items': rows})
        return 500 if error else 200, 'text/plain', body.encode(), {
            'kind': 'sqlite-select', 'statement': statement, 'parameters': parameters,
            'rows': rows, 'error': error}
    rendered = value if variant == 'vulnerable' else html.escape(value, quote=True)
    body = '<!doctype html><html><body><main id="result">' + rendered + '</main></body></html>'
    return 200, 'text/html; charset=utf-8', body.encode(), {'kind': 'html-body-text', 'rendered': rendered}


class ActiveHandler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def do_GET(self):
        u = urlsplit(self.path); technique = u.path.removeprefix('/')
        config = self.server.config; variant = self.server.variant
        status, kind, body, sink = 400, 'text/plain', b'invalid seed', None
        parameter = 'name' if technique == 'sqli' else 'q'
        query = parse_qs(u.query, keep_blank_values=True)
        valid = (technique in RULES and set(query) == {parameter} and len(query[parameter]) == 1
                 and self.headers.get('Host') == '127.0.0.1:18080')
        value = query[parameter][0] if valid else None
        if valid:
            status, kind, body, sink = exercise(variant, config, technique, value, self.server.fault == 'missing-sink')
        row = {'kind': 'arrival', 'requestId': self.headers.get('X-Zpa-Correlation'),
               'method': 'GET', 'url': ORIGIN + self.path, 'urlSha256': hashlib.sha256((ORIGIN + self.path).encode()).hexdigest(),
               'bodySha256': hashlib.sha256(b'').hexdigest(), 'status': status,
               'responseBodySha256': hashlib.sha256(body).hexdigest(), 'response': body.decode(),
               'contentType': kind, 'technique': technique, 'parameter': parameter,
               'input': value, 'valid': valid, 'sink': sink, 'variant': variant, 'fixtureTag': config['tag']}
        with self.server.receipt_lock:
            raw = (json.dumps(row, separators=(',', ':')) + '\n').encode()
            with Path('/fixture/arrivals.jsonl').open('ab') as stream:
                stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        self.send_response(status); self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
