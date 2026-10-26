"""Narrow borrowed Docker login/account read entry. No target provisioning or mutations."""
import argparse
import base64
import hashlib
import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import ROOT, Blocked, Plan, canonical, digest, utcnow
from .evidence import EvidenceInvalid, safe_path

WORKER = ROOT/'src/zap_assessment/bola_http.py'


def command(args, payload=None, timeout=10):
    # No interpolated shell, no credential arguments/env, no stderr echo.
    result = subprocess.run(['docker', *args], input=payload, capture_output=True, timeout=timeout)
    if result.returncode:
        raise Blocked('borrowed Docker operation failed; diagnostic values withheld')
    return result.stdout


def token_matches_actor(token, actor, config):
    """Claim consistency only. Identity proof is server login + protected acceptance, not decode alone."""
    from .bola_http import decode
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return False
        head, body = (decode(base64.urlsafe_b64decode(p+'='*((-len(p)) % 4))) for p in parts[:2])
        expected = config['fixture']['ownerId' if actor == 'A' else 'nonOwnerId']
        exp = body.get('exp')
        return (head.get('alg') == 'HS256' and type(body.get('sub')) is int and body['sub'] == expected
                and body.get('iss') == config['jwt']['issuer'] and body.get('aud') == config['jwt']['audience']
                and type(exp) in (int, float) and exp > time.time()
                and type(body.get('nbf', 0)) in (int, float) and body.get('nbf', 0) <= time.time())
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        return False


def preflight(plan):
    """Selected metadata only: zero HTTP, zero credential resolution, zero created resources."""
    from .bola import binding_readback, check_config, check_authority, source_digest
    c = check_config(plan.data['config'])
    check_authority(c, plan.data['authority'])
    if plan.data['schemaVersion'] != '1.4' or plan.data['sourceDigest'] != source_digest() or plan.encoded != canonical(plan.data):
        raise Blocked('borrowed plan/source mismatch')
    binding = binding_readback(c)
    image = command(['image', 'inspect', '--format', '{{.Id}}', c['runtime']['imageId']]).decode().strip()
    network = json.loads(command(['network', 'inspect', '--format',
        '{"id":{{json .Id}},"driver":{{json .Driver}},"scope":{{json .Scope}},"ingress":{{json .Ingress}}}', c['binding']['networkId']]))
    if image != c['runtime']['imageId'] or network != {'id': c['binding']['networkId'], 'driver': 'bridge', 'scope': 'local', 'ingress': False}:
        raise Blocked('borrowed runtime image/network mismatch')
    if hashlib.sha256(WORKER.read_bytes()).hexdigest() != c['runtime']['workerSha256']:
        raise Blocked('borrowed worker source mismatch')
    return {'planHash': plan.hash, 'sourceDigest': plan.data['sourceDigest'], 'binding': binding,
            'runtimeImageId': image, 'workerSha256': c['runtime']['workerSha256'],
            'httpRequests': 0, 'credentialValuesRead': False, 'resourcesCreated': 0}


class DockerBolaRunner:
    """One disposable client container. It never owns the target/network."""
    def __init__(self, plan, run_id, journal):
        self.plan, self.run_id, self.journal = plan, run_id, journal
        self.name = 'zpa-'+run_id+'-bola-client'
        self.container_id = None
        self.removed = False
        self.proof = None
        self.created = utcnow().isoformat()

    def metadata(self):
        fmt = ('{"id":{{json .Id}},"imageId":{{json .Image}},"running":{{json .State.Running}},'
               '"labels":{{json .Config.Labels}},"created":{{json .Created}},"mounts":{{json .Mounts}}}')
        return json.loads(command(['inspect', '--format', fmt, self.name]))

    def owned(self, meta):
        mounts = meta['mounts']
        worker_mount = (len(mounts) == 1 and mounts[0]['Type'] == 'bind' and mounts[0]['Destination'] == '/worker.py'
                        and mounts[0]['RW'] is False and mounts[0]['Source'] in (str(WORKER), '/host_mnt'+str(WORKER)))
        return (meta['labels'].get('zpa.bola.run') == self.run_id
                and meta['labels'].get('zpa.bola.plan') == self.plan.hash
                and meta['imageId'] == self.plan.data['config']['runtime']['imageId']
                and worker_mount)

    def prepare(self):
        c = self.plan.data['config']
        self.journal.append('runner-create-intent', {'name': self.name, 'createdByRun': self.run_id})
        self.container_id = command(['create', '-i', '--name', self.name,
            '--label', 'zpa.bola.run='+self.run_id, '--label', 'zpa.bola.plan='+self.plan.hash,
            '--network', c['binding']['networkId'], '--read-only', '--cap-drop', 'ALL', '--cap-add', 'NET_ADMIN',
            '--mount', 'type=bind,source='+str(WORKER)+',target=/worker.py,readonly',
            '--security-opt', 'no-new-privileges', '--memory', '128m', '--cpus', '1', '--pids-limit', '64',
            '--no-healthcheck', c['runtime']['imageId'], 'sleep', '1800']).decode().strip()
        command(['start', self.name])
        meta = self.metadata()
        if not self.owned(meta) or meta['id'] != self.container_id:
            raise Blocked('owned runner identity mismatch')
        u = urlsplit(c['origin']); port = u.port or (443 if u.scheme == 'https' else 80)
        rules = [['iptables', '-P', 'OUTPUT', 'DROP'], ['iptables', '-P', 'INPUT', 'DROP'], ['iptables', '-P', 'FORWARD', 'DROP'],
            ['iptables', '-A', 'INPUT', '-m', 'conntrack', '--ctstate', 'ESTABLISHED,RELATED', '-j', 'ACCEPT'],
            ['iptables', '-A', 'OUTPUT', '-p', 'tcp', '-d', c['binding']['address'], '--dport', str(port),
             '-m', 'owner', '--uid-owner', '1004', '-j', 'ACCEPT'],
            ['ip6tables', '-P', 'OUTPUT', 'DROP'], ['ip6tables', '-P', 'INPUT', 'DROP'], ['ip6tables', '-P', 'FORWARD', 'DROP']]
        for rule in rules:
            command(['exec', self.name, *rule])
        firewall = command(['exec', self.name, 'iptables-save', '-t', 'filter']).decode()
        ipv6 = command(['exec', self.name, 'ip6tables-save', '-t', 'filter']).decode()
        check = "import hashlib,json,os;print(json.dumps({'worker':hashlib.sha256(open('/worker.py','rb').read()).hexdigest(),'uid':os.getuid(),'status':open('/proc/self/status').read()}))"
        observed = json.loads(command(['exec', '--user', '1004:1004', self.name, 'python', '-c', check]))
        cap = next(x.split(':', 1)[1].strip() for x in observed['status'].splitlines() if x.startswith('CapEff:'))
        if observed['worker'] != c['runtime']['workerSha256'] or observed['uid'] != 1004 or int(cap, 16):
            raise Blocked('unprivileged worker/source mismatch')
        self.proof = {'name': self.name, 'containerId': self.container_id, 'createdByRun': self.run_id,
                      'imageId': c['runtime']['imageId'], 'workerSha256': observed['worker'],
                      'uid': 1004, 'effectiveCapabilities': 0, 'firewall': firewall, 'ipv6Firewall': ipv6,
                      'credentialTransport': 'stdin-only', 'mounts': [{'destination': '/worker.py', 'readOnly': True,
                                                                    'sourceSha256': observed['worker']}]}
        self.journal.append('runner-ready', self.proof)

    def exchange(self, method, path, headers, payload, timeout):
        from .bola import binding_readback, check_authority
        c = self.plan.data['config']
        deadline = time.monotonic()+timeout
        binding_readback(c, min(2, timeout))
        check_authority(c, self.plan.data['authority'])
        if hashlib.sha256(WORKER.read_bytes()).hexdigest() != c['runtime']['workerSha256']:
            raise Blocked('worker source changed after preflight')
        timeout = deadline-time.monotonic()
        if timeout <= 0:
            raise TimeoutError('borrowed request metadata deadline')
        job = {'origin': c['origin'], 'accountId': c['fixture']['accountId'], 'method': method,
               'path': path, 'headers': headers, 'payload': payload.decode() if payload is not None else None,
               'timeout': timeout, 'notAfter': datetime.fromisoformat(
                   self.plan.data['authority']['validUntil'].replace('Z', '+00:00')).timestamp()}
        raw = command(['exec', '-i', '--user', '1004:1004', self.name, 'python', '/worker.py'],
                      canonical(job), timeout=timeout+1)
        result = json.loads(raw)
        if result.get('ok') is not True:
            raise Blocked('isolated bounded HTTP exchange failed')
        return result['status'], result['body'], result['size']

    def close(self):
        if self.removed:
            return True
        # Exact-name reconciliation after uncertain create; no duplicate create/start/request.
        exists = command(['ps', '-aq', '--filter', 'name=^/'+self.name+'$']).decode().strip()
        if not exists:
            self.removed = True
            return True
        meta = self.metadata()
        if not self.owned(meta) or self.container_id and meta['id'] != self.container_id:
            raise Blocked('runner cleanup ownership mismatch')
        self.journal.append('runner-remove-intent', {'containerId': meta['id'], 'createdByRun': self.run_id})
        command(['rm', '-f', meta['id']])
        self.removed = not command(['ps', '-aq', '--filter', 'name=^/'+self.name+'$']).strip()
        self.journal.append('runner-removed', {'removed': self.removed})
        return self.removed


def resolve_login_inputs(config, env):
    from .bola_http import decode
    result, secrets = {}, []
    for actor in ('A', 'B'):
        value = env.get(config['credentials'][actor]['loginEnv'])
        if not isinstance(value, str) or len(value.encode()) > 8192:
            raise Blocked('login credential reference unavailable')
        data = decode(value)
        if (not isinstance(data, dict) or set(data) != {'email', 'password'}
                or any(not isinstance(v, str) or not v for v in data.values())
                or len(data['email']) > 254 or len(data['password']) > 72):
            raise Blocked('login credential contract rejected')
        result[actor] = data
        secrets.extend(data.values())
    if result['A']['email'].strip().lower() == result['B']['email'].strip().lower():
        raise Blocked('same login used for both actors')
    return result, secrets


def dispatch_valid(observed, dispatch):
    if len(dispatch) not in (len(observed), len(observed)+1):
        return False
    for obs, proof in zip(observed, dispatch):
        authenticated = obs['actor'] != 'anonymous' and obs['phase'] != 'login'
        expected = {'actor': obs['actor'], 'method': obs['method'], 'path': obs['path'],
                    'credentialSlot': obs['credentialSlot'],
                    'identitySource': 'server-login' if authenticated else 'login-input' if obs['phase'] == 'login' else 'anonymous',
                    'credentialSourceMatched': True, 'subjectMatchesExpected': authenticated, 'cookiePresent': False,
                    'responseReceived': True, 'status': obs['response']['status']}
        if proof != expected:
            return False
    return True


def borrowed_oracle(observed, execution, dispatch):
    from .bola_operational import login_oracle
    # Reuse the same identity/membership/disclosure rules, but never invent server-wire attestation.
    if not dispatch_valid(observed, dispatch) or execution == 'completed' and len(dispatch) != len(observed):
        return 'inconclusive', False
    wire_shape = [{'actor': o['actor'], 'method': o['method'], 'path': o['path'], 'cookiePresent': False} for o in observed]
    return login_oracle(observed, execution, wire_shape)


def verify_borrowed(root, plan, manifest, track):
    c = plan['config']
    pf = json.loads(safe_path(root, 'preflight.json').read_bytes())
    runtime = json.loads(safe_path(root, 'borrowed-runtime.json').read_bytes())
    dispatch = json.loads(safe_path(root, 'credential-binding.json').read_bytes())
    if track['executionStatus'] == 'completed':
        if pf is None or pf.get('planHash') != manifest['planHash'] or pf.get('binding') != {**c['binding'], 'running': True}:
            raise EvidenceInvalid('borrowed preflight missing')
        runner = runtime.get('runner')
        if (not runner or runner['createdByRun'] != manifest['runId'] or runner['imageId'] != c['runtime']['imageId']
                or runner['workerSha256'] != c['runtime']['workerSha256'] or runner['uid'] != 1004
                or runner['effectiveCapabilities'] != 0 or runner['credentialTransport'] != 'stdin-only'
                or runner['mounts'] != [{'destination': '/worker.py', 'readOnly': True,
                                        'sourceSha256': c['runtime']['workerSha256']}]):
            raise EvidenceInvalid('borrowed isolated runner proof missing')
        from urllib.parse import urlsplit
        u = urlsplit(c['origin']);port = u.port or (443 if u.scheme == 'https' else 80)
        fw = runner['firewall']; v6 = runner['ipv6Firewall']
        accepts = [x for x in fw.splitlines() if x.startswith('-A OUTPUT')]
        if (':OUTPUT DROP' not in fw or ':INPUT DROP' not in fw or ':FORWARD DROP' not in fw or len(accepts) != 1
                or f"-d {c['binding']['address']}/32" not in accepts[0] or f'--dport {port}' not in accepts[0]
                or '--uid-owner 1004' not in accepts[0] or not accepts[0].endswith('-j ACCEPT')
                or ':OUTPUT DROP' not in v6 or ':INPUT DROP' not in v6 or ':FORWARD DROP' not in v6):
            raise EvidenceInvalid('borrowed firewall scope proof invalid')
    if (type(runtime.get('runnerRemoved')) is not bool or track['cleanupStatus'] == 'clean' and runtime['runnerRemoved'] is not True
            or runtime.get('targetCleanupActions') != []):
        raise EvidenceInvalid('borrowed cleanup proof mismatch')
    if not dispatch_valid(track['observed'], dispatch):
        raise EvidenceInvalid('borrowed credential dispatch mismatch')
    if runtime.get('evidenceKind') != 'client-dispatch; not target-side wire attestation':
        raise EvidenceInvalid('borrowed provenance mislabeled')


def cleanup_run(folder):
    """Stop-only recovery. Never resume/replay login or change an existing bundle."""
    from .contracts import validate
    from .evidence import write_file
    from .journal import Journal
    folder = Path(folder).resolve()
    import re
    if not re.fullmatch(r'bola-[a-f0-9]{32}', folder.name):
        raise Blocked('cleanup run identity invalid')
    source = folder/'bundle' if (folder/'bundle').is_dir() else folder/'staging'
    plan = Plan(safe_path(source, 'plan.json').read_bytes())
    validate('bola-plan', plan.data)
    if plan.data['schemaVersion'] != '1.4':
        raise Blocked('cleanup requires borrowed1.4 evidence')
    original = Journal(safe_path(source, 'journal.jsonl'), folder.name, plan.hash)
    name = 'zpa-'+folder.name+'-bola-client'
    if not any(e['kind'] == 'runner-create-intent' and e['data'] == {'name': name, 'createdByRun': folder.name}
               for e in original.events):
        raise Blocked('runner ownership intent missing; cleanup refused')
    # Separate recovery record keeps the original bundle immutable.
    journal = Journal(folder/'cleanup-recovery.jsonl', folder.name, plan.hash)
    runner = DockerBolaRunner(plan, folder.name, journal)
    clean = runner.close()
    return {'cleanupStatus': 'clean' if clean else 'incomplete', 'securityVerdict': 'not_evaluated',
            'targetCleanupActions': [], 'httpRequests': 0, 'originalBundleModified': False}


def prepare_candidate(container, port, output):
    """Discover only candidate metadata. Never manufacture executable authority or fixture IDs."""
    fmt = ('{"containerId":{{json .Id}},"imageId":{{json .Image}},"startedAt":{{json .State.StartedAt}},'
           '"running":{{json .State.Running}},"networks":{{json .NetworkSettings.Networks}},'
           '"ports":{{json .NetworkSettings.Ports}},"mounts":{{json .Mounts}}}')
    metadata = json.loads(command(['inspect', '--format', fmt, container]))
    # Docker filters before returning output. Never return JWT_SECRET or full Config.Env.
    selected = '{{range .Config.Env}}{{$p := split . "="}}{{if or (eq (index $p 0) "JWT_ISSUER") (eq (index $p 0) "JWT_AUDIENCE")}}{{println .}}{{end}}{{end}}'
    public_jwt = dict(line.split('=', 1) for line in command(['inspect', '--format', selected, container]).decode().splitlines() if line)
    networks = [v for v in metadata['networks'].values() if v['IPAddress']]
    if len(networks) != 1 or not 1 <= port <= 65535:
        raise Blocked('candidate requires one unambiguous IPv4 network/port')
    n = networks[0]
    binding = {k: metadata[k] for k in ('containerId', 'imageId', 'startedAt')}
    binding.update(networkId=n['NetworkID'], address=n['IPAddress'])
    image = command(['image', 'inspect', '--format', '{{.Id}}', 'zap-assessment-boundary:local']).decode().strip()
    c = {'schemaVersion': '1.4', 'adapter': 'finalsource-account-read-v1', 'productId': 'finalsource',
        'environment': {'kind': 'test', 'identity': 'OWNER_REQUIRED', 'evidenceRef': 'OWNER_REQUIRED'},
        'origin': 'http://'+binding['address']+':'+str(port), 'targetBuildRef': metadata['imageId'], 'binding': binding,
        'fixture': {'accountId': 0, 'ownerId': 0, 'nonOwnerId': 0, 'provenanceRef': 'OWNER_REQUIRED'},
        'credentials': {a: {'loginEnv': 'FINALSOURCE_BOLA_'+a+'_LOGIN'} for a in ('A', 'B')},
        'anonymous': True, 'requestTimeoutSeconds': 5, 'totalTimeoutSeconds': 900, 'maxRate': 2, 'retentionDays': 30,
        'jwt': {'issuer': public_jwt.get('JWT_ISSUER', 'security-vibe-coding'),
                'audience': public_jwt.get('JWT_AUDIENCE', 'security-vibe-coding-web'), 'algorithm': 'HS256'},
        'runtime': {'kind': 'docker-isolated-client', 'imageId': image,
                    'workerSha256': hashlib.sha256(WORKER.read_bytes()).hexdigest()}}
    a = {'schemaVersion': '1.4', 'recordId': 'OWNER_REQUIRED', 'owner': 'OWNER_REQUIRED', 'issuer': 'OWNER_REQUIRED',
        'reviewer': 'pending-human-review', 'approvalRef': 'OWNER_REQUIRED', 'validFrom': 'OWNER_REQUIRED',
        'validUntil': 'OWNER_REQUIRED', 'configHash': 'OWNER_REQUIRED', 'fixtureMode': 'borrowed-read-only',
        'assumed': False, 'productId': 'finalsource', 'environmentIdentity': 'OWNER_REQUIRED',
        'operations': ['actor-login', 'account-list-ownership', 'account-detail-owner',
                       'account-detail-cross-user', 'account-detail-anonymous']}
    from .evidence import write_file
    out = Path(output);out.mkdir(mode=0o700, parents=True, exist_ok=False)
    record = {'observedAt': utcnow().isoformat(), 'candidateOnly': True, 'executable': False, 'httpRequests': 0,
              'credentialValuesRead': False, 'metadata': metadata, 'jwtPublicConfiguration': public_jwt,
              'portSource': 'operator-selected source-derived candidate; not HTTP verified',
              'remaining': ['real BOLA authority for this exact binding/scope', 'A/B numeric IDs and login references',
                            'one A-owned account ID/provenance', 'owner confirmation of environment/evidence policy']}
    for name, value in [('candidate.json', c), ('authority.template.json', a), ('discovery.json', record)]:
        write_file(out, name, canonical(value))
    return {'candidate': str(out/'candidate.json'), 'authorityTemplate': str(out/'authority.template.json'),
            'executable': False, 'httpRequests': 0, 'credentialValuesRead': False}


def main():
    from .bola import make_bola_plan, run_bola
    from .evidence import verify_bundle, write_file
    parser = argparse.ArgumentParser(description='Borrowed Docker BOLA: no target creation, cleanup or credential logging')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare');p.add_argument('--container', required=True);p.add_argument('--port', type=int, default=3000);p.add_argument('--output', required=True)
    p = sub.add_parser('plan'); p.add_argument('--config', required=True); p.add_argument('--authority', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('preflight'); p.add_argument('--plan', required=True)
    p = sub.add_parser('run'); p.add_argument('--plan', required=True); p.add_argument('--expect-plan-hash', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('verify'); p.add_argument('bundle')
    p = sub.add_parser('cleanup'); p.add_argument('run')
    args = parser.parse_args()
    entered = False
    try:
        if args.command == 'prepare':
            result = prepare_candidate(args.container, args.port, args.output)
        elif args.command == 'plan':
            plan = make_bola_plan(json.loads(Path(args.config).read_bytes()), json.loads(Path(args.authority).read_bytes()))
            if plan.data['schemaVersion'] != '1.4':
                raise Blocked('borrowed plan requires1.4')
            out = Path(args.output);out.mkdir(mode=0o700, parents=True, exist_ok=False)
            write_file(out, 'plan.json', plan.encoded)
            result = {'planHash': plan.hash, 'plan': str(out/'plan.json'), 'httpRequests': 0}
        elif args.command == 'preflight':
            result = preflight(Plan(Path(args.plan).read_bytes()))
        elif args.command == 'run':
            entered = True
            result = run_bola(Plan(Path(args.plan).read_bytes()), args.output, args.expect_plan_hash)
        elif args.command == 'cleanup':
            entered = True
            result = cleanup_run(args.run)
        else:
            m = verify_bundle(args.bundle)
            result = {'verified': True, **{k: m[k] for k in ('executionStatus', 'evidenceStatus', 'securityVerdict', 'cleanupStatus', 'gateDecision')}}
        print(json.dumps(result, indent=2))
        return result.get('exitCode', 0)
    except (Blocked, OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        print(json.dumps({'executionStatus': 'failed' if entered else 'not_started', 'evidenceStatus': 'incomplete',
                          'securityVerdict': 'inconclusive', 'cleanupStatus': 'incomplete' if entered else 'clean',
                          'gateDecision': 'block', 'detail': 'borrowed input/authority/runtime failure; values withheld'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
