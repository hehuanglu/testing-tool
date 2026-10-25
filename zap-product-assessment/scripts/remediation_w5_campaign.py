#!/usr/bin/env python3
"""Locked synthetic W5 development campaign. No product/scanner admission.

Only loopback fixture HTTP and owned child processes are used. No credential file,
Docker operation, target option or real credential is accepted by this command.
Exit0 means expected development outcomes, including blocked G3/product capability.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import platform
import sys
import unittest
import uuid

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE/'src'), str(PACKAGE/'tests')]

from zap_assessment.capabilities import SINKS, LIFECYCLE
from zap_assessment.contracts import canonical
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.secret_audit import CanaryAuditor

MODULES = ('test_auth_lifecycle', 'test_secret_audit', 'test_finalsource_p0_guard')
SOURCES = ('src/zap_assessment/auth_lifecycle.py', 'src/zap_assessment/secret_audit.py',
           'src/zap_assessment/w5_fixture.py', 'scripts/finalsource_p0_guard.py',
           'scripts/remediation_w5_campaign.py', 'tests/test_auth_lifecycle.py',
           'tests/test_secret_audit.py', 'tests/test_finalsource_p0_guard.py',
           'src/zap_assessment/capabilities.py', 'src/zap_assessment/safety_io.py',
           'src/zap_assessment/contracts.py', 'schemas/remediation/auth-campaign.schema.json')
SOURCES=(*SOURCES,'src/zap_assessment/errors.py','src/zap_assessment/secret_inventory.py')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def source_pin():
    return {name: sha((PACKAGE/name).read_bytes()) for name in SOURCES}


def cases():
    return sorted(f'{module}.{cls.__name__}.{method}' for module in MODULES
                  for cls in vars(importlib.import_module(module)).values()
                  if isinstance(cls, type) and issubclass(cls, unittest.TestCase)
                  for method in unittest.defaultTestLoader.getTestCaseNames(cls))


def prepare(work):
    work = Path(work).absolute()
    if work.exists() or work.is_symlink():
        raise ValueError('fresh work directory required')
    work.mkdir(mode=0o700)
    plan = {'schemaVersion': 'w5-auth-plan/1.0', 'assessmentId': 'w5-' + uuid.uuid4().hex,
            'scope': 'synthetic-loopback-development', 'targetBuild': 'synthetic-auth/1.0',
            'sourcePins': source_pin(), 'caseIds': cases(),
            'budgets': {'identityPollMaxSeconds': 5, 'httpTimeoutMaxSeconds': 8,
                        'stopRequestMaxSeconds': 10, 'stopTerminalMaxSeconds': 120},
            'expected': 'all development cases pass; G3 and product G4 remain blocked',
            'requiredLifecycle': sorted(LIFECYCLE), 'requiredSinkIds': sorted(SINKS),
            'productTrafficPermitted': False, 'scannerTrafficPermitted': False,
            'securityApproval': False}
    data = canonical(plan)
    atomic_bytes(work/'plan.json', data)
    return {'planSha256': sha(data), 'workDir': str(work), 'caseCount': len(plan['caseIds'])}


class Results(unittest.TestResult):
    """Do not publish traceback/exception messages that may contain a canary."""
    def __init__(self):
        super().__init__()
        self.rows = []

    def addSuccess(self, test):
        super().addSuccess(test)
        self.rows.append({'caseId': test.id(), 'status': 'pass'})

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self.rows.append({'caseId': test.id(), 'status': 'fail', 'reason': 'assertion_failed'})

    def addError(self, test, err):
        super().addError(test, err)
        self.rows.append({'caseId': test.id(), 'status': 'fail', 'reason': 'case_error'})

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self.rows.append({'caseId': test.id(), 'status': 'blocked', 'reason': 'required_case_skipped'})

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err:
            self.rows.append({'caseId': test.id(), 'status': 'fail', 'reason': 'subcase_failed'})


def validate_result(value):
    from jsonschema import Draft202012Validator
    schema = json.loads((PACKAGE/'schemas/remediation/auth-campaign.schema.json').read_bytes())
    Draft202012Validator(schema).validate(value)


def run(work, expected_hash):
    work = Path(work).absolute()
    data = CanaryAuditor.read_file(work, 'plan.json')
    if sha(data) != expected_hash:
        raise ValueError('external plan hash mismatch')
    plan = json.loads(data)
    if (plan['sourcePins'] != source_pin() or plan['caseIds'] != cases()
            or plan['requiredLifecycle'] != sorted(LIFECYCLE)
            or plan['requiredSinkIds'] != sorted(SINKS)):
        raise ValueError('locked campaign source/case inventory drift')
    # Claim exclusive execution BEFORE opening any fixture socket/process.
    atomic_bytes(work/'attempt.json', canonical({'startedAt': datetime.now(timezone.utc).isoformat(),
                                               'planSha256': expected_hash}))
    observations = []
    auth = importlib.import_module('test_auth_lifecycle')
    auth.AuthLifecycleTests.observations = observations
    auth.AuthLifecycleTests.binding = (plan['assessmentId'], expected_hash)
    result = Results()
    began = datetime.now(timezone.utc).isoformat()
    try:
        unittest.defaultTestLoader.loadTestsFromNames(MODULES).run(result)
    finally:
        auth.AuthLifecycleTests.observations = None
        auth.AuthLifecycleTests.binding = None
    intact = source_pin() == plan['sourcePins']
    passed = (result.wasSuccessful() and not result.skipped and intact
              and sorted(r['caseId'] for r in result.rows) == plan['caseIds'])
    # This records exactly which operational sinks the fixture DID NOT access.
    # It deliberately does not create empty placeholder files and call them clear.
    missing = [{'sinkId': sink, 'lifecycle': lifecycle, 'status': 'blocked',
                'reason': 'no_operational_sink_access_and_decoder_proof'}
               for sink in sorted(SINKS) for lifecycle in sorted(LIFECYCLE)]
    value = {'schemaVersion': 'w5-auth-campaign/1.0', 'assessmentId': plan['assessmentId'],
             'planSha256': expected_hash, 'startedAt': began,
             'finishedAt': datetime.now(timezone.utc).isoformat(),
             'scope': plan['scope'], 'sourcePins': plan['sourcePins'],
             'runtime': {'python': platform.python_version(), 'imagePins': [],
                         'transport': 'owned-loopback-http', 'dockerOperations': 0},
             'caseCount': result.testsRun, 'cases': result.rows,
             'allExpectedOutcomes': passed,
             'executionStatus': 'completed' if passed else 'incomplete',
             'evidenceStatus': 'complete' if passed else 'partial',
             'securityVerdict': 'inconclusive', 'cleanupStatus': 'fixture-contexts-closed' if passed else 'unknown',
             'gateDecision': 'block', 'securityApproval': False,
             'gates': [
                 {'gateId': 'G4-development-synthetic', 'status': 'pass' if passed else 'fail',
                  'reason': 'expected synthetic auth/epoch/stop outcomes; process restart is fail-stop only'},
                 {'gateId': 'G3-auditor-development', 'status': 'pass' if passed else 'fail',
                  'reason': 'seeded text parser controls and fail-closed inventory/decoder negatives'},
                 {'gateId': 'G3-delegated-operational', 'status': 'blocked',
                  'reason': 'all operational sink/lifecycle pairs need real access, decoding and canary proof'},
                 {'gateId': 'G4-finalsource-product', 'status': 'blocked',
                  'reason': 'no new product authority/endpoint contract or product lifecycle campaign'},
             ],
             'missingSecretProof': missing,
             'limits': ['No ZAP/MCP crawl, active, browser, history/session DB, dump or export campaign',
                        'Seeded UTF-8 controls named by sink/lifecycle are parser controls, not real sink integration',
                        'Revocation detection windows and identity-to-response intervals remain uncertain',
                        'Child SIGKILL with RLIMIT_CORE=0 does not attest host swap or OS diagnostics',
                        'Refresh only covers a live session with explicit contract, not expired-session renewal',
                        'Historical P0 credential-copy path and runtime admission remain blocked']}
    validate_result(value)
    atomic_bytes(work/'observations.json', canonical(observations))
    atomic_bytes(work/'gate-results.json', canonical(value))
    # This is a development readback index, never a scan/assessment manifest.
    index = {name: sha((work/name).read_bytes()) for name in
             ('plan.json', 'attempt.json', 'observations.json', 'gate-results.json')}
    atomic_bytes(work/'readback-index.json', canonical(index))
    return value


def verify(work, expected_hash):
    work = Path(work).absolute()
    plan_raw = CanaryAuditor.read_file(work, 'plan.json')
    if sha(plan_raw) != expected_hash:
        raise ValueError('external plan hash mismatch')
    index = json.loads(CanaryAuditor.read_file(work, 'readback-index.json'))
    names = {'plan.json', 'attempt.json', 'observations.json', 'gate-results.json'}
    if set(index) != names:
        raise ValueError('development artifact inventory mismatch')
    for name, checksum in index.items():
        if sha(CanaryAuditor.read_file(work, name)) != checksum:
            raise ValueError('development artifact checksum mismatch')
    value = json.loads(CanaryAuditor.read_file(work, 'gate-results.json'))
    validate_result(value)
    plan = json.loads(plan_raw)
    if (value['planSha256'] != expected_hash or value['sourcePins'] != plan['sourcePins']
            or sorted(r['caseId'] for r in value['cases']) != plan['caseIds']
            or value['caseCount'] != len(plan['caseIds'])
            or not value['allExpectedOutcomes'] or any(r['status'] != 'pass' for r in value['cases'])
            or any(g['status'] != 'pass' for g in value['gates'][:2])):
        raise ValueError('development result contradicts locked cases')
    observations = json.loads(CanaryAuditor.read_file(work, 'observations.json'))
    expected_auth = {name.split('.')[-1] for name in plan['caseIds'] if name.startswith('test_auth_lifecycle.')}
    if len(observations) != len(expected_auth) or {c['caseId'] for c in observations} != expected_auth:
        raise ValueError('auth case observations missing or duplicated')
    # Independent timeline audit: never call ActorSession to decide these facts.
    for case in observations:
        events, arrivals = case['events'], case['target']
        losses = [e for e in events if e['event'] == 'auth_lost']
        for loss in losses:
            next_epoch = min((e['atMonotonic'] for e in events if e['event'] == 'epoch_started'
                              and e['actorRef'] == loss['actorRef']
                              and e['atMonotonic'] > loss['atMonotonic']), default=float('inf'))
            if any(r.get('path') == '/api/v1/accounts' and r.get('actorRef') == loss['actorRef']
                   and loss['atMonotonic'] < r['atMonotonic'] < next_epoch for r in arrivals):
                raise ValueError('protected arrival after latch')
        epochs = {e['authEpoch'] for e in events if e['event'] == 'epoch_started'}
        for e in events:
            if e['runId'] != plan['assessmentId'] or e['planHash'] != expected_hash:
                raise ValueError('auth event campaign binding mismatch')
            if e['event'] == 'protected_start' and e['authEpoch'] not in epochs:
                raise ValueError('protected operation without admitted epoch')
    expected_pairs = {(s, c) for s in SINKS for c in LIFECYCLE}
    missing = value['missingSecretProof']
    if (len(missing) != len(expected_pairs)
            or {(r['sinkId'], r['lifecycle']) for r in missing} != expected_pairs
            or any(r['status'] != 'blocked' for r in missing)):
        raise ValueError('operational G3 missing proof hidden')
    return {'readbackStatus': 'pass', 'developmentCases': value['caseCount'],
            'operationalG3': 'blocked', 'productG4': 'blocked', 'securityApproval': False,
            'limitation': 'Development consistency only; no operational admission or complete semantic verifier.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('prepare', 'run', 'verify'))
    parser.add_argument('--work-dir', required=True, type=Path)
    parser.add_argument('--expect-plan-sha256')
    args = parser.parse_args()
    try:
        if args.command == 'prepare':
            value = prepare(args.work_dir)
        else:
            if not args.expect_plan_sha256:
                raise ValueError('external plan hash required')
            if args.command == 'verify':
                value = verify(args.work_dir, args.expect_plan_sha256)
            else:
                result = run(args.work_dir, args.expect_plan_sha256)
                value = {k: result[k] for k in ('allExpectedOutcomes', 'caseCount', 'gateDecision', 'gates')}
        print(json.dumps(value, ensure_ascii=False))
        return 0 if value.get('allExpectedOutcomes', True) else 1
    except Exception:
        print(json.dumps({'status': 'blocked', 'gateDecision': 'block',
                          'reason': 'campaign input, source, cases or evidence invalid', 'securityApproval': False}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
