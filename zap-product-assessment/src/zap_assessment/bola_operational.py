"""Profile-to-bundle entry for one owned synthetic account fixture; no product traffic."""
import argparse
import json
import socket
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

from .bola import (EXPECTED, LIST, LOGIN_SEQUENCE, STATUS_KEYS, make_bola_plan,
                   run_bola, source_digest, summarize)
from .bola_fixture import account_fixture
from .contracts import ROOT, Blocked, canonical, digest, utcnow, validate
from .evidence import EvidenceInvalid, safe_path, verify_bundle


def login_assertion(status, body, size, actor, config):
    summary = summarize(status, {}, size, actor, 'login', '/api/auth/login', config['fixture'], {})
    data = body.get('data', {}) if isinstance(body, dict) else {}
    expected = config['fixture']['ownerId' if actor == 'A' else 'nonOwnerId']
    token = data.get('accessToken') if isinstance(data, dict) else None
    user = data.get('user') if isinstance(data, dict) else None
    import re
    valid = (status == 200 and isinstance(body, dict) and body.get('success') is True and isinstance(user, dict)
             and type(user.get('id')) is int and user['id'] == expected
             and isinstance(token, str) and re.fullmatch(r'[A-Za-z0-9_.~-]{16,8192}', token) is not None)
    summary['identityValid'] = valid
    return summary, token if valid else None


def membership_valid(status, body, account_id, owner):
    # Deliberately ignore data.user_id: account lists are not identity evidence.
    data = body.get('data') if isinstance(body, dict) else None
    accounts = data.get('accounts') if isinstance(data, dict) else None
    if status != 200 or not isinstance(body, dict) or body.get('success') is not True or not isinstance(accounts, list):
        return False
    if any(not isinstance(a, dict) or type(a.get('id')) is not int for a in accounts):
        return False
    ids = [a['id'] for a in accounts]
    return len(ids) == len(set(ids)) and (account_id in ids) == owner


def wire_valid(observed, wire):
    return wire == [{'actor': o['actor'], 'path': o['path'], 'method': o['method'], 'cookiePresent': False}
                    for o in observed]


def login_oracle(observed, execution, wire):
    by_key = {(o['actor'], o['phase']): o['response'] for o in observed}
    controls = execution == 'completed' and len(observed) == len(LOGIN_SEQUENCE) and wire_valid(observed, wire)
    for actor in ('A', 'B'):
        controls = controls and by_key.get((actor, 'login'), {}).get('identityValid') is True
        for phase in ('identity-before', 'identity-after'):
            response = by_key.get((actor, phase), {})
            controls = controls and response.get('membershipValid') is True and response.get('identityValid') is False
    for phase in ('owner-before', 'owner-after'):
        controls = controls and by_key.get(('A', phase), {}).get('ownerObjectValid') is True
    controls = controls and by_key.get(('anonymous', 'anonymous-identity'), {}).get('denialValid') is True
    if not controls:
        return 'inconclusive', False
    negative = [by_key[('B', 'negative')], by_key[('anonymous', 'anonymous')]]
    if any(r['disclosure'] for r in negative):
        return 'fail', True
    return ('pass', True) if all(r['denialValid'] for r in negative) else ('inconclusive', False)


class OwnedAccountFixture:
    """A concrete account_fixture handle, not a configurable lifecycle/plugin interface."""
    def __init__(self, profile, variant=None):
        validate('bola-profile', profile)
        self.profile = profile
        self.run_id = 'bola-'+uuid.uuid4().hex
        self.created = utcnow()
        self.state = {}
        self.variant = variant or profile['variant']
        self.context = account_fixture(self.variant, self.state)
        self.config, _, self.env, _ = self.context.__enter__()
        self.closed = False
        fixture_source = ROOT/'src/zap_assessment/bola_fixture.py'
        import hashlib
        source_hash = hashlib.sha256(fixture_source.read_bytes()).hexdigest()
        self.manifest = {
            'createdByRun': self.run_id, 'sourceVersion': 'account-fixture-login-v1',
            'sourceSha256': source_hash, 'variant': self.variant,
            'buildRef': 'sha256:'+digest({'sourceSha256': source_hash, 'variant': self.variant}),
            'origin': self.config['origin'], 'logicalBindings': profile['logicalBindings'], 'wireIds': profile['wireIds'],
            'ownership': {'accountId': 'synthetic-account-a-001', 'owner': 'synthetic-user-a',
                          'notOwner': 'synthetic-user-b', 'sharedAccessGrants': []},
            'profile': profile, 'profileHash': digest(profile), 'createdAt': self.created.isoformat(),
        }
        self.config.update(schemaVersion='1.3', productId=profile['productId'],
            environment={'kind': profile['environmentClass'], 'identity': profile['environmentIdentity'],
                         'evidenceRef': profile['approvalRef']},
            targetBuildRef=self.manifest['buildRef'], logicalBindings=profile['logicalBindings'],
            credentials={a: {'tokenEnv': 'BOLA_LOGIN_'+a} for a in ('A', 'B')},
            totalTimeoutSeconds=profile['maxRuntimeSeconds'], maxRate=profile['maxRate'])
        self.config['fixture']['provenanceRef'] = 'sha256:'+digest(self.manifest)

    def authority(self):
        return {'schemaVersion': '1.3', 'recordId': self.run_id, 'owner': self.profile['owner'],
                'issuer': self.profile['issuer'], 'reviewer': self.profile['reviewer'],
                'approvalRef': self.profile['approvalRef'], 'validFrom': self.created.isoformat(),
                'validUntil': (self.created+timedelta(minutes=60)).isoformat(), 'configHash': digest(self.config),
                'operations': ['actor-login', 'account-list-ownership', 'account-detail-owner',
                               'account-detail-cross-user', 'account-detail-anonymous'],
                'fixtureMode': 'run-owned-synthetic'}

    def preflight(self, plan, env):
        c = plan.data['config']
        ids = self.profile['wireIds']
        valid = (c == self.config and c['fixture']['provenanceRef'] == 'sha256:'+digest(self.manifest)
                 and self.manifest['createdByRun'] == self.run_id and not self.state['arrivals']
                 and {'A': c['fixture']['ownerId'], 'B': c['fixture']['nonOwnerId'],
                      'account': c['fixture']['accountId']} == ids
                 and all(env.get(c['credentials'][a]['tokenEnv']) == self.env[c['credentials'][a]['tokenEnv']]
                         for a in ('A', 'B')) and not self.closed)
        if not valid:
            raise Blocked('owned synthetic fixture preflight failed')
        return {'planHash': plan.hash, 'fixtureManifestHash': digest(self.manifest),
                'noPriorRequests': True, 'ownedByRun': self.run_id, 'origin': c['origin'],
                'sourceDigest': plan.data['sourceDigest'], 'secretReferencesResolved': True,
                'ownershipProven': True}

    def close(self):
        if self.closed:
            return
        try:
            self.context.__exit__(None, None, None)
            self.env.clear()
            address = urlsplit(self.config['origin'])
            with socket.socket() as probe:
                probe.settimeout(0.2)
                closed = probe.connect_ex((address.hostname, address.port)) != 0
            self.closed = closed and not self.state['thread'].is_alive()
        except (OSError, RuntimeError):
            self.closed = False


def verify_operational(root, plan, manifest, track, wire):
    fixture = json.loads(safe_path(root, 'fixture-manifest.json').read_bytes())
    preflight = json.loads(safe_path(root, 'preflight.json').read_bytes())
    config = plan['config']
    profile = fixture['profile']
    validate('bola-profile', profile)
    if (fixture['profileHash'] != digest(profile) or fixture['createdByRun'] != manifest['runId']
            or fixture['origin'] != config['origin'] or fixture['logicalBindings'] != config['logicalBindings']
            or fixture['wireIds'] != profile['wireIds'] or fixture['logicalBindings'] != profile['logicalBindings']
            or fixture['ownership'] != {'accountId': 'synthetic-account-a-001', 'owner': 'synthetic-user-a',
                                      'notOwner': 'synthetic-user-b', 'sharedAccessGrants': []}
            or config['fixture']['provenanceRef'] != 'sha256:'+digest(fixture)
            or config['targetBuildRef'] != 'sha256:'+digest({'sourceSha256': fixture['sourceSha256'], 'variant': fixture['variant']})):
        raise EvidenceInvalid('operational fixture ownership/source context mismatch')
    expected = {'planHash': manifest['planHash'], 'fixtureManifestHash': digest(fixture),
                'noPriorRequests': True, 'ownedByRun': manifest['runId'], 'origin': config['origin'],
                'sourceDigest': plan['sourceDigest'], 'secretReferencesResolved': True, 'ownershipProven': True}
    if preflight != expected and not (preflight is None and manifest['executionStatus'] == 'not_started'):
        raise EvidenceInvalid('operational preflight missing or inconsistent')
    authority = plan['authority']
    created = datetime.fromisoformat(fixture['createdAt'])
    if (datetime.fromisoformat(authority['validFrom']) != created
            or datetime.fromisoformat(authority['validUntil']) != created+timedelta(minutes=60)
            or any(authority[k] != profile[k] for k in ('owner', 'issuer', 'reviewer', 'approvalRef'))
            or manifest['reviewReferences'] != []):
        raise EvidenceInvalid('synthetic labels/authority/review context mismatch')
    if not isinstance(wire, list) or any(set(x) != {'actor', 'path', 'method', 'cookiePresent'} for x in wire):
        raise EvidenceInvalid('invalid minimized wire proof')


def run_profile(profile, output, variant=None):
    validate('bola-profile', profile)
    owned = OwnedAccountFixture(profile, variant)
    try:
        plan = make_bola_plan(owned.config, owned.authority())
        result = run_bola(plan, output, plan.hash, owned.env, owned)
        verify_bundle(result['bundle'])
        return result
    finally:
        owned.close()
        owned.state.get('canaries', []).clear()


def main():
    parser = argparse.ArgumentParser(description='Owned synthetic account: profile → preflight → login/read → cleanup → verified bundle')
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output', default=str(ROOT/'runs/m3-operational'))
    args = parser.parse_args()
    try:
        result = run_profile(json.loads(Path(args.profile).read_bytes()), args.output)
        print(json.dumps(result, indent=2))
        return result['exitCode']
    except (Blocked, OSError, ValueError, KeyError, TypeError):
        print(json.dumps({'executionStatus': 'failed', 'evidenceStatus': 'incomplete', 'securityVerdict': 'inconclusive',
                          'cleanupStatus': 'incomplete', 'gateDecision': 'block', 'detail': 'operational failure; values withheld'}))
        return 2


if __name__ == '__main__':
    from zap_assessment.bola_operational import main as operational_main
    raise SystemExit(operational_main())
