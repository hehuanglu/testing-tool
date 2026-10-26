"""One resource, one object GET. No ZAP, cookie jar, fixture writes or plugins."""
from __future__ import annotations

import argparse
import copy
import hashlib
import http.client
import ipaddress
import json
import os
import re
import socket
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .contracts import ROOT, Blocked, Plan, canonical, digest, origin, utcnow, validate
from .evidence import EvidenceInvalid, publish, safe_path, secret_check, write_file
from .journal import Journal

LIST = '/api/v1/accounts'
EXPECTED = [{'method': 'GET', 'path': LIST+'/{id}'}]
OPERATIONS = ['account-list-identity', 'account-detail-owner',
              'account-detail-cross-user', 'account-detail-anonymous']
FIELDS = {'bank_name', 'account_type', 'branch_name', 'account_number_last_4',
          'balance', 'recent_transactions', 'description', 'receipt_id'}
SEQUENCE = [('anonymous', 'anonymous-identity', LIST), ('A', 'identity-before', LIST),
            ('B', 'identity-before', LIST), ('A', 'owner-before', 'object'),
            ('B', 'negative', 'object'), ('B', 'identity-after', LIST),
            ('A', 'owner-after', 'object'), ('A', 'identity-after', LIST),
            ('anonymous', 'anonymous', 'object')]
LOGIN = '/api/auth/login'
LOGIN_SEQUENCE = [('A', 'login', LOGIN), ('B', 'login', LOGIN)]+SEQUENCE
STATUS_KEYS = ('executionStatus', 'evidenceStatus', 'securityVerdict', 'cleanupStatus', 'gateDecision')


def source_digest():
    paths = (sorted((ROOT/'src/zap_assessment').glob('*.py')) + sorted((ROOT/'schemas/v1.2').glob('*.json'))
             + sorted((ROOT/'schemas/v1.3').glob('*.json')) + sorted((ROOT/'schemas/v1.4').glob('*.json')))
    return digest({str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})


def check_config(config):
    validate('bola-config', config)
    origin(config['origin'], True)
    url = urlsplit(config['origin'])
    try:
        address = ipaddress.IPv4Address(url.hostname)
    except ValueError as exc:
        raise Blocked('only pinned literal IPv4 is supported') from exc
    if address.is_link_local or address.is_unspecified or address.is_multicast or not address.is_private:
        raise Blocked('only private test IPv4 is supported')
    f = config['fixture']
    if f['ownerId'] == f['nonOwnerId']:
        raise Blocked('actors must be independent')
    if config['credentials']['A'] == config['credentials']['B']:
        raise Blocked('distinct credential references required')
    synthetic = config['environment']['kind'] == 'synthetic'
    if synthetic and config['schemaVersion'] != '1.4':
        expected_product = 'finalsource-synthetic' if config['schemaVersion'] == '1.3' else 'synthetic-account'
        if config['productId'] != expected_product or not address.is_loopback or config['binding'] is not None:
            raise Blocked('synthetic fixture must be loopback and unbound')
    else:
        b = config['binding']
        expected_product = 'borrowed-synthetic-account' if synthetic else 'finalsource'
        if config['productId'] != expected_product or not b or b['address'] != str(address):
            raise Blocked('product requires exact approved Docker binding')
        if not re.fullmatch(r'[a-f0-9]{64}', b['containerId']) or not re.fullmatch(r'sha256:[a-f0-9]{64}', b['imageId']):
            raise Blocked('immutable container/image identifiers required')
        if not re.fullmatch(r'[a-f0-9]{64}', b['networkId']) or config['targetBuildRef'] != b['imageId']:
            raise Blocked('immutable network/build identifiers required')
        if config['retentionDays'] != (14 if synthetic else 30):
            raise Blocked('evidence retention does not match environment')
    return config


def check_authority(config, authority, now=None):
    validate('bola-authority', authority)
    now = now or utcnow()
    start, end = (datetime.fromisoformat(authority[k].replace('Z', '+00:00')) for k in ('validFrom', 'validUntil'))
    if not start <= now < end:
        raise Blocked('BOLA authority expired or not yet valid')
    if authority['configHash'] != digest(config):
        raise Blocked('BOLA authority does not match exact config')
    if config['schemaVersion'] == '1.4':
        if (authority['productId'] != config['productId']
                or authority['environmentIdentity'] != config['environment']['identity']):
            raise Blocked('borrowed authority target identity mismatch')
        if config['environment']['kind'] != 'synthetic' and any(
                re.search(r'(?i)(synthetic|assumed|fictional|run-secret://)', authority[k])
                for k in ('owner', 'issuer', 'approvalRef')):
            raise Blocked('synthetic/assumed authority cannot authorize product')
    for key in ('owner', 'issuer', 'approvalRef', 'recordId'):
        if re.search(r'(?i)(TODO|TBD|DRAFT|PLACEHOLDER|UNRESOLVED|OWNER_REQUIRED|[<>\[\]])', authority[key]):
            raise Blocked('unresolved BOLA authority')


def make_bola_plan(config, authority):
    check_config(config)
    check_authority(config, authority)
    data = {'schemaVersion': config['schemaVersion'], 'config': copy.deepcopy(config),
            'authority': copy.deepcopy(authority), 'sourceDigest': source_digest()}
    validate('bola-plan', data)
    return Plan(canonical(data))


def binding_readback(config, timeout=5):
    """Selected Docker fields only: never inspect Config.Env or exec the target."""
    b = config['binding']
    if b is None:
        return None
    template = ('{"containerId":{{json .Id}},"imageId":{{json .Image}},'
                '"startedAt":{{json .State.StartedAt}},"running":{{json .State.Running}},'
                '"networks":{{json .NetworkSettings.Networks}},"mounts":{{json .Mounts}}}')
    result = subprocess.run(['docker', 'inspect', '--format', template, b['containerId']],
                            capture_output=True, timeout=max(0.01, min(5, timeout)), check=False)
    if result.returncode:
        raise Blocked('approved target metadata unavailable')
    data = json.loads(result.stdout)
    if not data['running'] or any(data[k] != b[k] for k in ('containerId', 'imageId', 'startedAt')):
        raise Blocked('approved target identity changed')
    if not any(n['NetworkID'] == b['networkId'] and n['IPAddress'] == b['address'] for n in data['networks'].values()):
        raise Blocked('approved target address/network changed')
    if any(m['Type'] == 'bind' for m in data['mounts']):
        raise Blocked('mutable target bind mount unsupported')
    return {**b, 'running': True}


def strict_json(data):
    def pairs(items):
        result = {}
        for k, v in items:
            if k in result:
                raise Blocked('duplicate response JSON field')
            result[k] = v
        return result
    return json.loads(data, object_pairs_hook=pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(Blocked('nonfinite JSON')))


class DirectClient:
    """Guard at the send point. Fresh connection, no proxies/redirects/cookies/retries."""
    def __init__(self, plan, credentials, deadline=None):
        self.plan = plan
        self.config = plan.data['config']
        self.credentials = dict(credentials)
        self.deadline = deadline or time.monotonic() + self.config['totalTimeoutSeconds']
        self.last = None
        self.count = 0
        self.runner = None
        self.bound_credentials = {}
        self.dispatch = []

    def get(self, actor, path):
        return self.request(actor, path)

    def request(self, actor, path, method='GET', payload=None):
        c = self.config
        check_authority(c, self.plan.data['authority'])
        if c['schemaVersion'] == '1.4' and self.runner is None:
            raise Blocked('borrowed traffic requires the isolated runner')
        login = c['schemaVersion'] in ('1.3', '1.4') and method == 'POST' and path == LOGIN and actor in ('A', 'B')
        object_get = method == 'GET' and path in (LIST, LIST+'/'+str(c['fixture']['accountId'])) and payload is None
        if actor not in ('A', 'B', 'anonymous') or not (login or object_get):
            raise Blocked('request outside exact BOLA scope')
        if login and (not isinstance(payload, dict) or set(payload) != {'email', 'password'}):
            raise Blocked('login payload contract rejected')
        sequence = LOGIN_SEQUENCE if c['schemaVersion'] in ('1.3', '1.4') else SEQUENCE
        if self.count >= len(sequence):
            raise Blocked('request budget exhausted')
        if self.last is not None:
            delay = max(0, 1/c['maxRate'] - (time.monotonic()-self.last))
            if time.monotonic()+delay >= self.deadline:
                raise TimeoutError('total BOLA deadline')
            time.sleep(delay)
        remaining = self.deadline-time.monotonic()
        if remaining <= 0:
            raise TimeoutError('total BOLA deadline')
        check_authority(c, self.plan.data['authority'])
        timeout = min(c['requestTimeoutSeconds'], remaining)
        u = urlsplit(c['origin'])
        connection_type = http.client.HTTPSConnection if u.scheme == 'https' else http.client.HTTPConnection
        connection = connection_type(u.hostname, u.port, timeout=timeout)
        headers = {'Accept': 'application/json', 'Connection': 'close'}
        if actor != 'anonymous' and not login:
            headers['Authorization'] = 'Bearer '+self.credentials[actor]
        raw_payload = canonical(payload) if login else None
        if login:
            headers['Content-Type'] = 'application/json'
        self.last = time.monotonic()
        request_deadline = self.last+timeout
        self.count += 1
        proof = None
        if c['schemaVersion'] == '1.4':
            from .bola_borrowed import token_matches_actor
            authenticated = actor != 'anonymous' and not login
            if authenticated and (self.credentials.get(actor) != self.bound_credentials.get(actor)
                                  or not token_matches_actor(self.credentials[actor], actor, c)):
                raise Blocked('credential slot/subject mismatch')
            proof = {'actor': actor, 'method': method, 'path': path,
                     'credentialSlot': actor if actor != 'anonymous' else 'none',
                     'identitySource': 'server-login' if authenticated else 'login-input' if login else 'anonymous',
                     'credentialSourceMatched': True, 'subjectMatchesExpected': authenticated,
                     'cookiePresent': False, 'responseReceived': False, 'status': None}
            self.dispatch.append(proof)
        self.last = time.monotonic()
        if self.runner is not None:
            result = self.runner.exchange(method, path, headers, raw_payload, timeout)
        else:
            from .bola_http import exchange
            expiry = datetime.fromisoformat(self.plan.data['authority']['validUntil'].replace('Z', '+00:00')).timestamp()
            result = exchange(c['origin'], method, path, headers, raw_payload, timeout, expiry)
        if proof is not None:
            proof.update(responseReceived=True, status=result[0])
        return result


def identity_valid(status, body, expected_id, account_id, owner):
    if status != 200 or not isinstance(body, dict) or body.get('success') is not True:
        return False, False
    data = body.get('data')
    if not isinstance(data, dict) or type(data.get('user_id')) is not int or data['user_id'] != expected_id:
        return False, False
    accounts = data.get('accounts')
    if not isinstance(accounts, list) or any(not isinstance(a, dict) or type(a.get('id')) is not int for a in accounts):
        return False, False
    ids = [a['id'] for a in accounts]
    return True, len(ids) == len(set(ids)) and (account_id in ids) == owner


def owner_valid(status, body, account_id):
    if status != 200 or not isinstance(body, dict) or body.get('success') is not True:
        return False
    data = body.get('data')
    fields = {'id', 'bank_name', 'account_type', 'branch_name', 'account_number_last_4', 'balance', 'recent_transactions'}
    if not isinstance(data, dict) or set(data) != fields or type(data['id']) is not int or data['id'] != account_id:
        return False
    if any(not isinstance(data[k], str) for k in ('bank_name', 'account_type', 'branch_name', 'account_number_last_4')):
        return False
    if not re.fullmatch('[0-9]{4}', data['account_number_last_4']) or type(data['balance']) not in (int, float):
        return False
    transactions = data['recent_transactions']
    return isinstance(transactions, list) and len(transactions) <= 5 and all(isinstance(t, dict) for t in transactions)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from strings(v)


def disclosure(body, owner_body):
    keys = set()
    def walk(value):
        if isinstance(value, dict):
            keys.update(set(value) & FIELDS)
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
    walk(body)
    # Values are compared only in memory. Never persist balances, last4, names or transactions.
    owner_strings = []
    def sensitive_strings(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k in {'bank_name', 'branch_name', 'account_number_last_4', 'description', 'receipt_id'}:
                    owner_strings.extend(s for s in strings(v) if len(s) >= 4)
                elif isinstance(v, (dict, list)):
                    sensitive_strings(v)
        elif isinstance(value, list):
            for v in value:
                sensitive_strings(v)
    sensitive_strings(owner_body.get('data', {}))
    matched = any(s in candidate for s in owner_strings for candidate in strings(body))
    return sorted(keys), matched


def denial_valid(status, body, path, anonymous):
    allowed = {401: {'Unauthorized', 'Invalid access token.'}} if anonymous else {
        403: {'You do not have permission to view this account information.'},
        404: {'This account was not found.'}}
    if status not in allowed or not isinstance(body, dict):
        return False
    if set(body) != {'success', 'statusCode', 'message', 'timestamp', 'path'}:
        return False
    return (body['success'] is False and type(body['statusCode']) is int and body['statusCode'] == status
            and isinstance(body['message'], str) and body['message'] in allowed[status]
            and body['path'] == path and isinstance(body['timestamp'], str)
            and re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z', body['timestamp']) is not None)


def summarize(status, body, size, actor, phase, path, fixture, owner_body):
    result = {'status': status, 'bodyBytes': size, 'identityValid': False, 'membershipValid': False,
              'ownerObjectValid': False, 'denialValid': False, 'disclosure': False,
              'ownerValueMatch': False, 'disclosureFields': []}
    if phase in ('identity-before', 'identity-after'):
        result['identityValid'], result['membershipValid'] = identity_valid(
            status, body, fixture['ownerId'] if actor == 'A' else fixture['nonOwnerId'], fixture['accountId'], actor == 'A')
    elif phase.startswith('owner-'):
        result['ownerObjectValid'] = owner_valid(status, body, fixture['accountId'])
    else:
        result['denialValid'] = denial_valid(status, body, path, actor == 'anonymous')
        fields, matched = disclosure(body, owner_body)
        result.update(disclosureFields=fields, ownerValueMatch=matched, disclosure=bool(fields) or matched)
    return result


def oracle(observed, execution):
    """Replayed by the verifier. Incomplete controls can never produce pass."""
    by_key = {(o['actor'], o['phase']): o['response'] for o in observed}
    controls = execution == 'completed' and len(observed) == len(SEQUENCE)
    for actor in ('A', 'B'):
        for phase in ('identity-before', 'identity-after'):
            r = by_key.get((actor, phase), {})
            controls = controls and r.get('identityValid') is True and r.get('membershipValid') is True
    for phase in ('owner-before', 'owner-after'):
        controls = controls and by_key.get(('A', phase), {}).get('ownerObjectValid') is True
    controls = controls and by_key.get(('anonymous', 'anonymous-identity'), {}).get('denialValid') is True
    if not controls:
        return 'inconclusive', False
    negatives = [by_key[('B', 'negative')], by_key[('anonymous', 'anonymous')]]
    if any(r['disclosure'] for r in negatives):
        return 'fail', True
    if all(r['denialValid'] for r in negatives):
        return 'pass', True
    return 'inconclusive', False


def track_result(observed, execution, cleanup, warnings, wire=None, dispatch=None):
    if dispatch is not None:
        from .bola_borrowed import borrowed_oracle
        verdict, controls = borrowed_oracle(observed, execution, dispatch)
    elif wire is not None:
        from .bola_operational import login_oracle
        verdict, controls = login_oracle(observed, execution, wire)
    else:
        verdict, controls = oracle(observed, execution)
    gate = 'allow' if verdict == 'pass' and cleanup == 'clean' else 'block'
    return {'track': 'ownership-bola', 'executionStatus': execution, 'evidenceStatus': 'complete',
            'securityVerdict': verdict, 'cleanupStatus': cleanup, 'gateDecision': gate,
            'expected': EXPECTED, 'observed': observed, 'warnings': warnings}


def run_bola(plan, output_root, expected_plan_hash, environ=None, owned_fixture=None):
    data = plan.data
    validate('bola-plan', data)
    config = check_config(data['config'])
    check_authority(config, data['authority'])
    if plan.hash != expected_plan_hash or data['sourceDigest'] != source_digest():
        raise Blocked('reviewed plan/source hash mismatch')
    if plan.encoded != canonical(data):
        raise Blocked('noncanonical BOLA plan')
    output_root = Path(output_root)
    if output_root.is_symlink():
        raise Blocked('output root symlink refused')
    output_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    operational = config['schemaVersion'] == '1.3'
    borrowed = config['schemaVersion'] == '1.4'
    login_mode = operational or borrowed
    if operational:
        from .bola_operational import OwnedAccountFixture
        if not isinstance(owned_fixture, OwnedAccountFixture):
            raise Blocked('operational synthetic execution requires its owned fixture')
    run_id = owned_fixture.run_id if operational else 'bola-'+uuid.uuid4().hex
    run = output_root/run_id
    run.mkdir(mode=0o700)
    staging = run/'staging'
    staging.mkdir(mode=0o700)
    started = utcnow().isoformat()
    journal = Journal(staging/'journal.jsonl', run_id, plan.hash)
    journal.append('plan-locked', {'adapter': config['adapter']})
    if borrowed:
        write_file(staging, 'plan.json', plan.encoded)
    observed, warnings, credentials = [], [], {}
    execution, cleanup = 'not_started', 'clean'
    before = after = None
    wire = [] if operational else None
    preflight = None
    runner = None
    dispatch = [] if borrowed else None
    login_inputs = {}
    client = None
    canaries = list(owned_fixture.state['canaries']) if operational else []
    deadline = time.monotonic()+config['totalTimeoutSeconds']
    try:
        env = os.environ if environ is None else environ
        if operational:
            preflight = owned_fixture.preflight(plan, env)
        if borrowed:
            from .bola_borrowed import preflight as borrowed_preflight, DockerBolaRunner, resolve_login_inputs
            preflight = borrowed_preflight(plan)
            journal.append('preflight-passed', preflight)
            # Resolve references only after actual authority and selected metadata preflight.
            login_inputs, secrets = resolve_login_inputs(config, env)
            canaries.extend(secrets)
            runner = DockerBolaRunner(plan, run_id, journal)
            runner.prepare()
        for actor in (() if login_mode else ('A', 'B')):
            token = env.get(config['credentials'][actor]['tokenEnv'], '')
            if not re.fullmatch(r'[A-Za-z0-9_.~-]{16,8192}', token):
                raise Blocked('missing or invalid credential reference')
            credentials[actor] = token
        if not login_mode and credentials['A'] == credentials['B']:
            raise Blocked('same credential used for both actors')
        before = binding_readback(config, deadline-time.monotonic())
        client = DirectClient(plan, credentials, deadline)
        client.runner = runner
        owner_body = {}
        execution = 'running'
        for actor, phase, path in (LOGIN_SEQUENCE if login_mode else SEQUENCE):
            if path == 'object':
                path = LIST+'/'+str(config['fixture']['accountId'])
            method = 'POST' if phase == 'login' else 'GET'
            journal.append('request-intent', {'actor': actor, 'phase': phase, 'method': method, 'path': path})
            if phase == 'login':
                payload = login_inputs[actor] if borrowed else strict_json(env[config['credentials'][actor]['tokenEnv']])
                status, body, size = client.request(actor, path, method, payload)
                from .bola_operational import login_assertion
                summary, token = login_assertion(status, body, size, actor, config)
                if borrowed and token:
                    from .bola_borrowed import token_matches_actor
                    if not token_matches_actor(token, actor, config):
                        summary['identityValid'] = False
                        token = None
                    else:
                        client.bound_credentials[actor] = token
                if token:
                    credentials[actor] = token
                    client.credentials[actor] = token
                    canaries.append(token)
            else:
                status, body, size = client.get(actor, path)
                summary = summarize(status, body, size, actor, phase, path, config['fixture'], owner_body)
                if login_mode and phase in ('identity-before', 'identity-after'):
                    from .bola_operational import membership_valid
                    summary['identityValid'] = False
                    summary['membershipValid'] = membership_valid(status, body, config['fixture']['accountId'], actor == 'A')
            observed.append({'method': method, 'path': path, 'actor': actor, 'phase': phase,
                             'credentialSlot': actor if actor != 'anonymous' else 'none', 'response': summary})
            journal.append('response', observed[-1])
            if phase == 'login' and (not summary['identityValid'] or actor == 'B' and credentials.get('A') == token):
                raise Blocked('login identity or independent credential control failed')
            if phase == 'owner-before':
                owner_body = body if summary['ownerObjectValid'] else {}
            # Do not send the cross-user request if identity/ownership/owner-positive is unproven.
            if phase in ('identity-before',) and not (summary['membershipValid'] and (login_mode or summary['identityValid'])):
                raise Blocked('identity or ownership control failed')
            if phase == 'owner-before' and not summary['ownerObjectValid']:
                raise Blocked('owner-positive control failed')
        if time.monotonic() >= deadline:
            raise TimeoutError('total BOLA deadline')
        after = binding_readback(config, deadline-time.monotonic())
        execution = 'completed'
    except (TimeoutError, socket.timeout):
        execution = 'timed_out'
        warnings.append('bounded transport deadline reached')
    except (Blocked, OSError, ValueError, KeyError, TypeError, RecursionError, http.client.HTTPException, subprocess.SubprocessError):
        if execution != 'not_started':
            execution = 'failed'
        warnings.append('control, scope, binding, credential or transport failure; diagnostic values withheld')
    finally:
        if borrowed:
            dispatch = client.dispatch if client else []
            login_inputs.clear()
            if runner:
                try:
                    if not runner.close():
                        cleanup = 'incomplete'
                except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError):
                    cleanup = 'incomplete'
                    warnings.append('owned runner cleanup unconfirmed; reconcile exact ownership')
        if operational:
            owned_fixture.close()
            wire = list(owned_fixture.state['arrivals'])
            if not owned_fixture.closed:
                cleanup = 'incomplete'
        # No user/account deletion is permitted. Every connection closes in DirectClient.finally.
        if config['binding'] is not None and before is not None and after is None:
            try:
                after = binding_readback(config, deadline-time.monotonic())
            except (Blocked, OSError, ValueError, KeyError, subprocess.SubprocessError):
                cleanup = 'incomplete'
                warnings.append('borrowed target readback unavailable or changed')
    track = track_result(observed, execution, cleanup, warnings, wire, dispatch)
    journal.append('assessment-complete', {k: track[k] for k in STATUS_KEYS})
    cleanup_proof = {'createdByRun': run_id, 'borrowedFixture': config['fixture'],
                     'targetCleanupActions': [], 'fixtureWrites': 0, 'connectionsClosed': True,
                     'cleanupVerified': cleanup == 'clean', 'before': before, 'after': after}
    if operational:
        cleanup_proof.update(fixtureOwnedByRun=run_id, listenerClosed=owned_fixture.closed,
                             fixtureDataDiscarded=owned_fixture.closed)
    artifacts = []
    values = [('plan.json', data), ('bola-evidence.json', track), ('cleanup.json', cleanup_proof)]
    if operational:
        values += [('fixture-manifest.json', owned_fixture.manifest), ('preflight.json', preflight),
                   ('wire-proof.json', wire)]
    if borrowed:
        values += [('preflight.json', preflight), ('credential-binding.json', dispatch),
                   ('borrowed-runtime.json', {'runner': runner.proof if runner else None,
                    'runnerRemoved': runner.removed if runner else True, 'targetCleanupActions': [],
                    'evidenceKind': 'client-dispatch; not target-side wire attestation'})]
    for name, value in values:
        raw = canonical(value)
        secret_check(raw, [*credentials.values(), *canaries])
        if borrowed and name == 'plan.json':
            artifacts.append({'path': name, 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
        else:
            artifacts.append(write_file(staging, name, raw))
    raw = (staging/'journal.jsonl').read_bytes()
    artifacts.append({'path': 'journal.jsonl', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()})
    manifest = {
        'schemaVersion': data['schemaVersion'], 'runId': run_id, 'planHash': plan.hash,
        'startedAt': started, 'endedAt': utcnow().isoformat(), 'targetBuildRef': config['targetBuildRef'],
        'sourceRefs': {'orchestrator': data['sourceDigest'], 'mcp': 'not-used'},
        'provenance': {'adapter': config['adapter'], 'transport': 'direct-literal-ip-no-proxy-no-cookie-no-redirect',
                       'zapUsed': False, 'credentialStorage': 'memory-only', 'configHash': digest(config)},
        'scope': [config['origin']], 'ownership': cleanup_proof, 'operationIds': ['GET '+LIST+'/{id}'],
        'tracks': [track], **{k: track[k] for k in STATUS_KEYS}, 'artifacts': artifacts,
        'retentionDays': config['retentionDays'], 'reviewReferences': [],
        'limitations': ['one borrowed account; read only; no writes or fixture cleanup authorized',
                        'responses minimized in memory; raw payloads and credential fingerprints not stored',
                        'synthetic verified; finalsource unverified' if config['environment']['kind'] == 'synthetic'
                        else 'one authorized product object only; no broader M3 completion or release approval'],
        'initiator': data['authority']['owner'],
    }
    if operational:
        from datetime import timedelta
        manifest['provenance'].update(retentionClass='synthetic',
            retentionExpiresAt=(datetime.fromisoformat(started)+timedelta(days=14)).isoformat())
        manifest['limitations'][0] = 'one run-owned synthetic account; no business mutation; no reviewer sign-off'
    if borrowed:
        from datetime import timedelta
        manifest['provenance'].update(retentionClass='synthetic' if config['environment']['kind'] == 'synthetic' else 'product-internal',
            retentionExpiresAt=(datetime.fromisoformat(started)+timedelta(days=config['retentionDays'])).isoformat(),
            credentialProof='server-login+JWT-claim-consistency+isolated-slot-dispatch')
        manifest['limitations'] += ['JWT decoding is not signature verification; server login and protected acceptance required',
                                    'dispatch proof is client-side, not target-side wire attestation; borrowed target retained']
    publish(staging, run/'bundle', manifest, [*credentials.values(), *canaries])
    credentials.clear()
    return {'runId': run_id, 'bundle': str(run/'bundle'), **{k: track[k] for k in STATUS_KEYS},
            'exitCode': 0 if track['gateDecision'] == 'allow' else 1 if track['securityVerdict'] == 'fail' else 2}


def verify_bola_bundle(root, manifest):
    operational = manifest['schemaVersion'] == '1.3'
    borrowed = manifest['schemaVersion'] == '1.4'
    seen = set()
    for artifact in manifest['artifacts']:
        if artifact['path'] in seen:
            raise EvidenceInvalid('duplicate BOLA artifact')
        seen.add(artifact['path'])
        raw = safe_path(root, artifact['path']).read_bytes()
        secret_check(raw)
        if len(raw) != artifact['bytes'] or hashlib.sha256(raw).hexdigest() != artifact['sha256']:
            raise EvidenceInvalid('BOLA artifact readback mismatch')
    required = {'plan.json', 'bola-evidence.json', 'cleanup.json', 'journal.jsonl'}
    if operational:
        required |= {'fixture-manifest.json', 'preflight.json', 'wire-proof.json'}
    if borrowed:
        required |= {'preflight.json', 'credential-binding.json', 'borrowed-runtime.json'}
    if seen != required:
        raise EvidenceInvalid('BOLA artifacts missing or unexpected')
    raw = safe_path(root, 'plan.json').read_bytes()
    plan = json.loads(raw)
    validate('bola-plan', plan)
    config = check_config(plan['config'])
    check_authority(config, plan['authority'], datetime.fromisoformat(manifest['startedAt']))
    if raw != canonical(plan) or hashlib.sha256(raw).hexdigest() != manifest['planHash']:
        raise EvidenceInvalid('BOLA plan digest mismatch')
    if manifest['scope'] != [config['origin']] or manifest['targetBuildRef'] != config['targetBuildRef']:
        raise EvidenceInvalid('BOLA target context mismatch')
    if manifest['sourceRefs'] != {'orchestrator': plan['sourceDigest'], 'mcp': 'not-used'}:
        raise EvidenceInvalid('BOLA source provenance mismatch')
    provenance = {
        'adapter': config['adapter'], 'transport': 'direct-literal-ip-no-proxy-no-cookie-no-redirect',
        'zapUsed': False, 'credentialStorage': 'memory-only', 'configHash': digest(config)}
    if operational:
        from datetime import timedelta
        provenance.update(retentionClass='synthetic',
            retentionExpiresAt=(datetime.fromisoformat(manifest['startedAt'])+timedelta(days=14)).isoformat())
    if borrowed:
        from datetime import timedelta
        provenance.update(retentionClass='synthetic' if config['environment']['kind'] == 'synthetic' else 'product-internal',
            retentionExpiresAt=(datetime.fromisoformat(manifest['startedAt'])+timedelta(days=config['retentionDays'])).isoformat(),
            credentialProof='server-login+JWT-claim-consistency+isolated-slot-dispatch')
    if manifest['provenance'] != provenance:
        raise EvidenceInvalid('BOLA transport provenance mismatch')
    track = json.loads(safe_path(root, 'bola-evidence.json').read_bytes())
    if manifest['tracks'] != [track] or any(manifest[k] != track[k] for k in STATUS_KEYS):
        raise EvidenceInvalid('BOLA track mismatch')
    observations = track['observed']
    sequence = LOGIN_SEQUENCE if operational or borrowed else SEQUENCE
    if len(observations) > len(sequence):
        raise EvidenceInvalid('BOLA request budget exceeded')
    for obs, (actor, phase, path) in zip(observations, sequence):
        path = LIST+'/'+str(config['fixture']['accountId']) if path == 'object' else path
        if any(obs[k] != v for k, v in {'actor': actor, 'phase': phase, 'path': path, 'method': 'POST' if phase == 'login' else 'GET',
                                      'credentialSlot': actor if actor != 'anonymous' else 'none'}.items()):
            raise EvidenceInvalid('BOLA actor/operation mismatch')
        r = obs['response']
        if r['disclosure'] != bool(r['disclosureFields'] or r['ownerValueMatch']):
            raise EvidenceInvalid('BOLA disclosure assertion inconsistent')
        if r['identityValid'] and r['status'] != 200 or r['ownerObjectValid'] and r['status'] != 200:
            raise EvidenceInvalid('BOLA positive status inconsistent')
        if r['denialValid'] and r['status'] not in ((401,) if actor == 'anonymous' else (403, 404)):
            raise EvidenceInvalid('BOLA denial status inconsistent')
    wire = json.loads(safe_path(root, 'wire-proof.json').read_bytes()) if operational else None
    dispatch = json.loads(safe_path(root, 'credential-binding.json').read_bytes()) if borrowed else None
    expected = track_result(observations, track['executionStatus'], track['cleanupStatus'], track['warnings'], wire, dispatch)
    if track != expected:
        raise EvidenceInvalid('BOLA verdict not supported by controls')
    cleanup = json.loads(safe_path(root, 'cleanup.json').read_bytes())
    expected_cleanup = {
        'createdByRun': manifest['runId'], 'borrowedFixture': config['fixture'], 'targetCleanupActions': [],
        'fixtureWrites': 0, 'connectionsClosed': True, 'cleanupVerified': track['cleanupStatus'] == 'clean',
        'before': cleanup.get('before'), 'after': cleanup.get('after')}
    if operational:
        expected_cleanup.update(fixtureOwnedByRun=manifest['runId'],
            listenerClosed=track['cleanupStatus'] == 'clean', fixtureDataDiscarded=track['cleanupStatus'] == 'clean')
    if manifest['ownership'] != cleanup or cleanup != expected_cleanup:
        raise EvidenceInvalid('BOLA cleanup ownership mismatch')
    if config['binding'] is not None and track['executionStatus'] == 'completed':
        if any(cleanup[k] != {**config['binding'], 'running': True} for k in ('before', 'after')):
            raise EvidenceInvalid('BOLA borrowed binding proof missing')
    if config['binding'] is None and (cleanup['before'] is not None or cleanup['after'] is not None):
        raise EvidenceInvalid('synthetic cannot assert product binding')
    journal = Journal(safe_path(root, 'journal.jsonl'), manifest['runId'], manifest['planHash'])
    responses = [e['data'] for e in journal.events if e['kind'] == 'response']
    intents = [e['data'] for e in journal.events if e['kind'] == 'request-intent']
    if responses != observations or len(intents) not in (len(observations), len(observations)+1):
        raise EvidenceInvalid('BOLA journal response mismatch')
    if not journal.events or journal.events[-1]['kind'] != 'assessment-complete':
        raise EvidenceInvalid('BOLA journal not complete')
    if journal.events[-1]['data'] != {k: track[k] for k in STATUS_KEYS}:
        raise EvidenceInvalid('BOLA journal status mismatch')
    if manifest['operationIds'] != ['GET '+LIST+'/{id}'] or manifest['retentionDays'] != config['retentionDays']:
        raise EvidenceInvalid('BOLA contract context mismatch')
    if operational:
        from .bola_operational import verify_operational
        verify_operational(root, plan, manifest, track, wire)
    if borrowed:
        from .bola_borrowed import verify_borrowed
        verify_borrowed(root, plan, manifest, track)
    return manifest


def main():
    parser = argparse.ArgumentParser(description='Narrow direct BOLA account adapter (no ZAP)')
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('plan')
    p.add_argument('--config', required=True)
    p.add_argument('--authority', required=True)
    p = sub.add_parser('run')
    p.add_argument('--plan', required=True)
    p.add_argument('--expect-plan-hash', required=True)
    p.add_argument('--output', required=True)
    p = sub.add_parser('verify')
    p.add_argument('bundle')
    args = parser.parse_args()
    execution_entered = False
    try:
        if args.command == 'plan':
            plan = make_bola_plan(json.loads(Path(args.config).read_bytes()), json.loads(Path(args.authority).read_bytes()))
            result = {'planHash': plan.hash, 'plan': plan.data}
        elif args.command == 'run':
            execution_entered = True
            result = run_bola(Plan(Path(args.plan).read_bytes()), args.output, args.expect_plan_hash)
        else:
            from .evidence import verify_bundle
            manifest = verify_bundle(args.bundle)
            result = {'verified': True, 'runId': manifest['runId'], **{k: manifest[k] for k in STATUS_KEYS}}
        print(json.dumps(result, indent=2))
        return result.get('exitCode', 0)
    except (Blocked, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'executionStatus': 'failed' if execution_entered else 'not_started', 'evidenceStatus': 'incomplete',
                          'securityVerdict': 'inconclusive', 'cleanupStatus': 'incomplete' if execution_entered else 'clean', 'gateDecision': 'block',
                          'detail': 'BOLA input, authority, integrity or output check failed; values withheld'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
