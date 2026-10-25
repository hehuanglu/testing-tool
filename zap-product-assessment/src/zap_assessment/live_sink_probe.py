"""In-container actual ZAP HISTORY controls; never accepts product credentials.

All seeds, API messages, reports and JDBC cells stay in this private process and
owned tmpfs. Stdout is metadata only. This is one success-lifecycle observation,
not 143-pair G3 acceptance or platform proof. No active/product request is made.
"""
import base64
import http.client
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import resource
import secrets
import subprocess
import threading
import time
from urllib.parse import urlencode

from .errors import Blocked
from .private_db import control_forms, strict_json
from .scanner_secret_audit import audit_database, decoded_views
from .secret_audit import CanaryAuditor

PROGRESS = {'stage': 'initial'}


def header_seed(blob):
    values = [line.partition(b':')[2].strip(b' \t') for line in blob.splitlines()
              if line.partition(b':')[0].lower() == b'x-zpa-seed']
    if len(values) > 1:
        raise Blocked('live_sink_duplicate_seed_header')
    return values[0] if values else None


class _ShapeAuditor:
    # Validate JDBC framing/counts first; inspect seeded cells separately below.
    def matches(self, blob):
        return False


def inspect_history_control(raw, secret):
    """Replay real typed HISTORY cells against every exact seeded request header.

    HISTORY's actual SQL types are retained; we never invent a TEXT family when
    the scanner stores request headers as BINARY. Unknown/duplicate cells block.
    """
    summary = audit_database(_ShapeAuditor(), raw)
    forms = control_forms(secret)
    expected = forms
    found = {}; cells = set(); auditor = CanaryAuditor([secret])
    for line in raw.splitlines():
        row = strict_json(line)
        if row['kind'] != 'cell':
            continue
        if type(row.get('row')) is not int or row['row'] <= 0:
            raise Blocked('live_sink_row_invalid')
        key = (row['table'], row['row'], row['column'])
        if key in cells:
            raise Blocked('live_sink_duplicate_cell')
        cells.add(key)
        value = base64.b64decode(row['base64'], validate=True)
        for tag, marker in expected.items():
            if header_seed(value) != marker:
                continue
            if (row['table'] != 'HISTORY' or row['column'] != 'REQHEADER'
                    or not any(auditor.matches(v) for v in decoded_views(value))):
                raise Blocked('live_sink_seed_binding_invalid')
            if tag in found and found[tag]['sqlType'] != row['sqlType']:
                raise Blocked('live_sink_seed_type_changed')
            previous = found.get(tag, {}).get('occurrences', 0)
            found[tag] = {'encoding': tag, 'sqlType': row['sqlType'], 'detected': True,
                          'occurrences': previous + 1}
    if set(found) != set(forms):
        raise Blocked('live_sink_positive_control_missed')
    return {'decoder': summary['decoder'], 'tables': summary['tables'],
            'decodedCells': summary['decodedCells'], 'decodedBytes': summary['decodedBytes'],
            'controls': [found[k] for k in forms], 'seededRequests': len(forms),
            'sourceValuesIncluded': False, 'rawCellsExportedToController': False}


def api(component, kind, endpoint, **params):
    conn = http.client.HTTPConnection('127.0.0.1', 8090, timeout=5)
    try:
        conn.request('GET', '/' + '/'.join(('JSON', component, kind, endpoint, '')) + '?' + urlencode(params))
        response = conn.getresponse(); raw = response.read(8 * 1024 * 1024 + 1)
        if response.status != 200 or len(raw) > 8 * 1024 * 1024:
            raise Blocked('live_sink_api_failed')
        value = strict_json(raw)
        if not isinstance(value, dict) or 'code' in value:
            raise Blocked('live_sink_api_contract')
        return value
    finally:
        conn.close()


class Target(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        body = b'{"ownedControl":true}'
        self.send_response(200); self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)


def start_engine(log):
    return subprocess.Popen(['/zap/zap.sh', '-daemon', '-host', '127.0.0.1', '-port', '8090',
        '-config', 'api.disablekey=true', '-config', 'autoupdate.checkOnStart=false',
        '-config', 'connection.timeoutInSecs=2'], stdout=log, stderr=subprocess.STDOUT)


def wait_engine(proc, timeout=100):
    end=time.monotonic()+timeout
    while True:
        if proc.poll() is not None or time.monotonic() >= end:
            raise Blocked('live_sink_startup_failed')
        try:return api('core','view','version')['version']
        except (OSError,Blocked):time.sleep(.5)


def stop_engine(proc):
    api('core','action','shutdown');proc.wait(timeout=30)


def read_session_database():
    if not Path('/tmp/SessionDbReadback.class').exists():
        result=subprocess.run(['javac','-cp','/zap/lib/hsqldb-2.7.4.jar','-d','/tmp',
            '/package/src/zap_assessment/probes/SessionDbReadback.java'],capture_output=True,timeout=30)
        if result.returncode:raise Blocked('live_sink_decoder_compile_failed')
    result=subprocess.run(['java','-cp','/tmp:/zap/lib/hsqldb-2.7.4.jar','SessionDbReadback','session'],
                          capture_output=True,timeout=15)
    if result.returncode:raise Blocked('live_sink_database_read_failed')
    return result.stdout


def execute():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0)); os.umask(0o077)
    secret = secrets.token_urlsafe(48); forms = control_forms(secret)
    target = ThreadingHTTPServer(('127.0.0.1', 18080), Target)
    threading.Thread(target=target.serve_forever, daemon=True).start()
    log = open('/tmp/private-zap.log', 'wb')
    proc = subprocess.Popen(['/zap/zap.sh', '-daemon', '-host', '127.0.0.1', '-port', '8090',
        '-config', 'api.disablekey=true', '-config', 'autoupdate.checkOnStart=false',
        '-config', 'connection.timeoutInSecs=2'], stdout=log, stderr=subprocess.STDOUT)
    try:
        end = time.monotonic() + 100
        while True:
            if proc.poll() is not None or time.monotonic() >= end:
                raise Blocked('live_sink_startup_failed')
            try:
                version = api('core', 'view', 'version')['version']; break
            except (OSError, Blocked):
                time.sleep(.5)
        # Each payload is injected inside this process, never Docker/controller.
        messages = []
        for index, (tag, form) in enumerate(forms.items()):
            proxy = http.client.HTTPConnection('127.0.0.1', 8090, timeout=5)
            try:
                proxy.request('GET', 'http://127.0.0.1:18080/control/' + str(index),
                              headers={'X-Zpa-Seed': form.decode('ascii'), 'Connection': 'close'})
                response = proxy.getresponse(); response.read(4096)
                if response.status != 200:
                    raise Blocked('live_sink_seed_response_failed')
            finally:
                proxy.close()
        time.sleep(1)
        history = api('core', 'view', 'messages', baseurl='http://127.0.0.1:18080', start=0, count=100)['messages']
        PROGRESS.update(stage='history', historyMessages=len(history))
        controls = []
        for tag, form in forms.items():
            matched = [r for r in history if header_seed(r.get('requestHeader', '').encode()) == form]
            PROGRESS.update(encoding=tag, matchedMessages=len(matched))
            if not matched or not all(CanaryAuditor([secret]).matches(r['requestHeader'].encode()) for r in matched):
                raise Blocked('live_sink_history_control_missed')
            controls.append({'encoding': tag, 'detected': True, 'occurrences': len(matched)})
        PROGRESS.update(stage='save-session')
        api('core', 'action', 'saveSession', name='/session/w5-saved-session', overwrite='true')
        passive_end = time.monotonic() + 30
        while api('pscan', 'view', 'recordsToScan')['recordsToScan'] != '0':
            if time.monotonic() >= passive_end:
                raise Blocked('live_sink_passive_timeout')
            time.sleep(.25)
        # Writer terminal is required before opening the actual file database.
        PROGRESS.update(stage='shutdown')
        api('core', 'action', 'shutdown'); proc.wait(timeout=30)
        compile_result = subprocess.run(['javac', '-cp', '/zap/lib/hsqldb-2.7.4.jar', '-d', '/tmp',
            '/package/src/zap_assessment/probes/SessionDbReadback.java'], capture_output=True, timeout=30)
        if compile_result.returncode:
            raise Blocked('live_sink_decoder_compile_failed')
        decoded = subprocess.run(['java', '-cp', '/tmp:/zap/lib/hsqldb-2.7.4.jar', 'SessionDbReadback', 'session'],
                                 capture_output=True, timeout=15)
        if decoded.returncode:
            raise Blocked('live_sink_database_read_failed')
        PROGRESS.update(stage='database')
        database = inspect_history_control(decoded.stdout, secret)
        return {'schemaVersion': 'actual-zap-sink-control/1.0', 'status': 'pass',
                'zapVersion': version, 'history': {'controls': controls, 'messages': len(history)},
                'database': database, 'writerTerminal': True, 'passiveSettled': True,
                'lifecycle': 'success', 'productRequests': 0, 'activeRequests': 0,
                'sourceValuesIncluded': False, 'rawCellsExportedToController': False,
                'platformAcceptance': False, 'operationalAdmission': False}
    finally:
        if proc.poll() is None:
            proc.terminate()
            try: proc.wait(timeout=10)
            except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
        log.close(); target.shutdown()


def main():
    try:
        value = execute()
    except BaseException as exc:
        # Never print exception message, target body, API/decoder stdout or log.
        value = {'schemaVersion': 'actual-zap-sink-control/1.0', 'status': 'blocked',
                 'reasonCode': str(exc) if isinstance(exc, Blocked) else 'live_sink_probe_failed',
                 'sourceValuesIncluded': False, 'rawCellsExportedToController': False,
                 'productRequests': 0, 'operationalAdmission': False}
        value['diagnostic'] = PROGRESS
    print(json.dumps(value, separators=(',', ':')))
    return 0 if value['status'] == 'pass' else 2


if __name__ == '__main__':
    raise SystemExit(main())
