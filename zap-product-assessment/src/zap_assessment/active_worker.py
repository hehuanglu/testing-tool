"""Real pinned ZAP active controls in one owned network-none namespace."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode
import urllib.request
from .active_fixture import ActiveHandler, ORIGIN, RULES, WITNESSES
from .traffic import CorrelatedGuard, capture_snapshot, correlate


def encode(v): return json.dumps(v, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
def sha(v): return hashlib.sha256(v).hexdigest()


def phase(value):
    p = Path('/zap/wrk/observer-phase.pending'); p.write_text(value)
    os.replace(p, '/zap/wrk/observer-phase.txt')


def api(component, kind, name, args=None):
    url = 'http://127.0.0.1:8090/JSON/' + component + '/' + kind + '/' + name + '/?' + urlencode(args or {})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=10) as r:
        raw = r.read(4 * 1024**2 + 1)
    if len(raw) > 4 * 1024**2: raise ValueError('api_budget')
    result = json.loads(raw)
    if 'code' in result: raise ValueError('api_rejected_' + name + '_' + str(result['code']))
    return result


def send(url):
    raw = 'GET ' + url + ' HTTP/1.1\r\nHost: 127.0.0.1:18080\r\nConnection: close\r\n\r\n'
    rows = api('core', 'action', 'sendRequest', {'request': raw, 'followRedirects': 'false'})['sendRequest']
    if len(rows) != 1: raise ValueError('seed_response_count')
    return rows[0]


def install(run_id):
    wrk = Path('/zap/wrk')
    shutil.copy('/source/zap_assessment/probes/TrafficProbe.java', wrk / 'TrafficProbe.java')
    (wrk / 'probe-classes').mkdir()
    subprocess.run(['javac', '-cp', '/zap/*:/zap/lib/*', '-d', str(wrk / 'probe-classes'), str(wrk / 'TrafficProbe.java')], check=True, capture_output=True, timeout=40)
    phase('seed')
    ids = ','.join(str(r['id']) for r in api('ascan', 'view', 'scanners')['scanners'])
    (wrk / 'observer-run-id.txt').write_text(run_id)
    (wrk / 'observer-rule-ids.txt').write_text(ids)
    bootstrap = """const V=Java.type('org.zaproxy.zap.extension.script.ScriptVars');
const L=Java.type('java.net.URLClassLoader');const U=Java.type('java.net.URL');
const loader=new L(Java.to([new U('file:/zap/wrk/probe-classes/')],'java.net.URL[]'),Java.type('org.parosproxy.paros.network.HttpSender').class.getClassLoader());
const cls=loader.loadClass('TrafficProbe');V.setGlobalCustomVar('w4.class',cls);
const F=Java.type('java.nio.file.Files');const P=Java.type('java.nio.file.Path');
cls.getMethod('install',Java.type('java.lang.String').class).invoke(null,F.readString(P.of('/zap/wrk/observer-run-id.txt')));
cls.getMethod('bindRules',Java.type('java.lang.String').class).invoke(null,F.readString(P.of('/zap/wrk/observer-rule-ids.txt')));
"""
    inventory = "Java.type('org.zaproxy.zap.extension.script.ScriptVars').getGlobalCustomVar('w4.class').getMethod('inventory',Java.type('java.lang.String').class).invoke(null,'');"
    for name, code in [('w8-capture', bootstrap), ('w8-inventory', inventory)]:
        (wrk / (name + '.js')).write_text(code)
        api('script', 'action', 'load', {'scriptName': name, 'scriptType': 'standalone', 'scriptEngine': 'Graal.js', 'fileName': str(wrk / (name + '.js'))})
    api('script', 'action', 'runStandAloneScript', {'scriptName': 'w8-capture'})
    if api('script', 'view', 'globalVar', {'varKey': 'w4.installed'})['globalVar'] != run_id: raise ValueError('capture_install')


def inventory(policy):
    api('script', 'action', 'runStandAloneScript', {'scriptName': 'w8-inventory'})
    raw = Path('/zap/wrk/script-inventory.json').read_bytes()
    if api('script', 'view', 'globalVar', {'varKey': 'w4.inventory'})['globalVar'] != sha(raw): raise ValueError('script_inventory_hash')
    proxy = api('network', 'view', 'getHttpProxy')['getHttpProxy']
    enabled = api('network', 'view', 'isHttpProxyEnabled')['isHttpProxyEnabled']
    if enabled not in ('true', 'false'): raise ValueError('proxy_boolean_contract')
    return {'version': api('core', 'view', 'version')['version'],
            'addons': api('autoupdate', 'view', 'installedAddons')['installedAddons'],
            'scripts': json.loads(raw), 'rules': api('ascan', 'view', 'scanners', {'scanPolicyName': policy})['scanners'],
            'proxy': {'host': proxy['host'], 'port': proxy['port'], 'enabled': enabled == 'true',
                      'exclusions': api('network', 'view', 'getHttpProxyExclusions')['getHttpProxyExclusions']},
            'vectors': {n: api('ascan', 'view', n) for n in ('optionTargetParamsInjectable', 'optionTargetParamsEnabledRPC', 'optionAddQueryParam')}}


class FilterGuard(CorrelatedGuard):
    minimum_interval = .1
    def forward(self, target, relative, ident, req):
        if self.server.fault == 'guard-filter' and req['initiator'] == 2 and not req.get('activeControl'):
            return 403, b'', [], False, 'owned_fault_payload_filtered'
        return super().forward(target, relative, ident, req)


def run(job):
    plan = job['plan']; config = job['fixture']; fault = plan['fault']; wrk = Path('/zap/wrk')
    samples = []; stop = threading.Event(); errors = []; process = None; servers = []; scans = []
    def sample():
        mem = dict(x.split(':', 1) for x in Path('/proc/meminfo').read_text().splitlines())
        cg = Path('/sys/fs/cgroup')
        row = {'at': time.monotonic(), 'ramAvailable': int(mem['MemAvailable'].split()[0]) * 1024,
               'dockerFree': os.statvfs('/').f_bavail * os.statvfs('/').f_frsize,
               'currentBytes': int((cg / 'memory.current').read_text()), 'peakBytes': int((cg / 'memory.peak').read_text()),
               'events': dict((k, int(v)) for k, v in (r.split() for r in (cg / 'memory.events').read_text().splitlines()))}
        samples.append(row)
        if row['ramAvailable'] < 4 * 1024**3 or row['events'].get('oom', 0) or row['events'].get('oom_kill', 0): raise ValueError('resource_headroom_or_oom')
    def watch():
        while not stop.wait(1):
            try: sample()
            except Exception as exc:
                errors.append(type(exc).__name__ + ':' + str(exc)[:120])
                if process and process.poll() is None: process.terminate()
                return
    sample(); monitor = threading.Thread(target=watch, daemon=True); monitor.start()
    try:
        target = ThreadingHTTPServer(('127.0.0.1', 18080), ActiveHandler)
        target.config = config; target.variant = plan['variant']; target.fault = fault; target.receipt_lock = threading.RLock()
        guard = ThreadingHTTPServer(('127.0.0.1', 18888), FilterGuard); guard.fault = fault; guard.capture_lock = threading.RLock()
        for s in (target, guard):
            servers.append(s); threading.Thread(target=s.serve_forever, daemon=True).start()
        log = Path('/work/zap.log').open('wb')
        process = subprocess.Popen(['/zap/zap.sh', '-daemon', '-host', '127.0.0.1', '-port', '8090',
            '-config', 'api.disablekey=true', '-config', 'autoupdate.checkOnStart=false',
            '-config', 'connection.timeoutInSecs=2', '-config', 'ascan.threadPerHost=1'], stdout=log, stderr=subprocess.STDOUT,
            env={**os.environ, 'ZAP_MEMORY': '512m'})
        deadline = time.monotonic() + 100
        while True:
            try: api('core', 'view', 'version'); break
            except Exception:
                if process.poll() is not None or time.monotonic() >= deadline: raise ValueError('scanner_startup_failed')
                time.sleep(.2)
        api('script', 'action', 'remove', {'scriptName': 'SwaggerSecretDetector.js'})
        api('ascan', 'action', 'setOptionTargetParamsInjectable', {'Integer': '1'})
        api('ascan', 'action', 'setOptionTargetParamsEnabledRPC', {'Integer': '0'})
        api('ascan', 'action', 'setOptionAddQueryParam', {'Boolean': 'false'})
        api('network', 'action', 'setHttpProxy', {'host': '127.0.0.1', 'port': '18888'})
        for exclusion in api('network', 'view', 'getHttpProxyExclusions')['getHttpProxyExclusions']:
            api('network', 'action', 'setHttpProxyExclusionEnabled', {'host': exclusion['host'], 'enabled': 'false'})
        api('network', 'action', 'setHttpProxyEnabled', {'enabled': 'true'})
        install(plan['runId'])
        for vector in config['vectors']:
            t = vector['technique']; rule = vector['ruleId']; policy = 'w8-' + t
            api('ascan', 'action', 'addScanPolicy', {'scanPolicyName': policy})
            api('ascan', 'action', 'disableAllScanners', {'scanPolicyName': policy})
            if fault != 'disabled-rule': api('ascan', 'action', 'enableScanners', {'ids': rule, 'scanPolicyName': policy})
            api('ascan', 'action', 'setScannerAlertThreshold', {'id': rule, 'alertThreshold': 'MEDIUM', 'scanPolicyName': policy})
            api('ascan', 'action', 'setScannerAttackStrength', {'id': rule, 'attackStrength': 'LOW', 'scanPolicyName': policy})
            if fault == 'disabled-rule': api('ascan', 'action', 'disableScanners', {'ids': rule, 'scanPolicyName': policy})
            Path('/fixture/traffic-config.json').write_bytes(encode({'senderPath': '/zap/wrk/sender-events.jsonl', 'origin': ORIGIN,
                'allowedPaths': [vector['path']], 'queryPath': vector['path'], 'activeRules': [rule], 'requirePhase': True}))
            phase('seed')
            before = inventory(policy)
            suffix = urlencode({vector['parameter']: vector['baseline']})
            if fault == 'missing-parameter': suffix = ''
            if fault == 'invalid-seed': suffix = urlencode([(vector['parameter'], vector['baseline']), (vector['parameter'], 'duplicate')])
            url = ORIGIN + vector['path'] + ('?' + suffix if suffix else '')
            seed = send(url)
            # sendRequest persists the Sites node asynchronously. Observe the
            # exact seed before the single scan start; never replay a start.
            seed_deadline = time.monotonic() + 5
            while url not in api('core', 'view', 'urls')['urls']:
                if time.monotonic() >= seed_deadline: raise ValueError('seed_not_registered_in_sites')
                time.sleep(.05)
            start = len(capture_snapshot([wrk / 'sender-events.jsonl'])[0])
            phase('active')
            ack = api('ascan', 'action', 'scan', {'url': url, 'recurse': 'false', 'inScopeOnly': 'false', 'scanPolicyName': policy})
            sid = ack['scan']; progress = []; deadline = time.monotonic() + 100
            while True:
                status = api('ascan', 'view', 'status', {'scanId': sid})['status']
                if status == '100': break
                if errors or time.monotonic() >= deadline: raise ValueError('scan_deadline_or_safety')
                time.sleep(.1)
            progress = api('ascan', 'view', 'scanProgress', {'scanId': sid})
            phase('oracle')
            after = inventory(policy)
            witness_url = ORIGIN + vector['path'] + '?' + urlencode({vector['parameter']: WITNESSES[t]})
            witness = send(witness_url)
            alerts = [a for a in api('core', 'view', 'alerts', {'baseurl': ORIGIN + vector['path'], 'start': 0, 'count': 1000})['alerts'] if str(a['pluginId']) == rule]
            messages = {a['messageId']: api('core', 'view', 'message', {'id': a['messageId']})['message'] for a in alerts}
            scans.append({'technique': t, 'ruleId': rule, 'scanId': sid, 'status': status, 'progress': progress,
                          'seedUrl': url, 'seedResponse': seed, 'witnessResponse': witness, 'before': before, 'after': after,
                          'alerts': alerts, 'messages': messages, 'senderStartOffset': start})
        api('core', 'action', 'shutdown'); process.wait(timeout=20)
        for s in servers: s.shutdown(); s.server_close()
        servers.clear()
        captures = capture_snapshot([wrk / 'sender-events.jsonl', Path('/fixture/boundary.jsonl'), Path('/fixture/arrivals.jsonl')])
        traffic = correlate(*captures, terminal=True)
        # Freeze the periodic writer before the final synchronous reading. Two
        # concurrent readers could append timestamps in reverse order at close.
        stop.set(); monitor.join(5)
        if monitor.is_alive(): raise ValueError('resource_monitor_stop_unconfirmed')
        sample()
        return {'unifiedBinding': plan.get('unifiedBinding'), 'evidenceKind': 'actual-zap-native', 'scans': scans, 'sender': captures[0], 'boundary': captures[1], 'arrivals': captures[2],
                'traffic': traffic, 'resourceSamples': samples, 'resourceErrors': errors, 'scannerStopped': process.poll() is not None,
                'fixtureStopped': True, 'fixtureBuild': sha(Path('/source/zap_assessment/active_fixture.py').read_bytes()),
                'targetBuildHash': sha(encode({'source': sha(Path('/source/zap_assessment/active_fixture.py').read_bytes()), 'variant': plan['variant']}))}
    finally:
        if process and process.poll() is None:
            process.terminate()
            try: process.wait(timeout=10)
            except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        for s in servers: s.shutdown(); s.server_close()
        stop.set(); monitor.join(5)


if __name__ == '__main__':
    try:
        job = json.loads(Path('/job.json').read_bytes()); result = run(job)
    except Exception as exc:
        result = {'workerFailure': type(exc).__name__ + ':' + str(exc)[:400]}
        if Path('/work/zap.log').exists(): result['scannerLogTail'] = Path('/work/zap.log').read_text(errors='replace')[-8000:]
        try:
            result['partialCaptures'] = capture_snapshot([Path('/zap/wrk/sender-events.jsonl'), Path('/fixture/boundary.jsonl'), Path('/fixture/arrivals.jsonl')])
        except Exception as read_error: result['partialCaptureFailure'] = type(read_error).__name__
    Path('/work/result.json').write_bytes(encode(result))
    time.sleep(600)
