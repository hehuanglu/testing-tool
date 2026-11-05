"""Individual offline fixture primitives. The caller selects and persists work."""
import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path

from test_coordinator_recovery import interrupt
from test_criteria_workflow import approve
from test_operation_selection import work
from zap_assessment import assessment_store as store
from zap_assessment.contracts import canonical, digest
from zap_assessment.criteria_delegation import Coordinator, make_packet, validate_packet
from zap_assessment.operator_state import default_operator, validate_operator
from zap_assessment.safety_io import atomic_bytes

BASE = Path(__file__).resolve().parents[1]
FIXTURE = BASE / 'fixture'
STATE = FIXTURE / 'state'
COUNTER = FIXTURE / 'control' / 'callback-count.jsonl'


def save(path, value):
    atomic_bytes(path, canonical(value) + b'\n')
    return path


def setup():
    aid = 'synthetic-' + BASE.name
    context = dict(product='synthetic-fixture', environment='offline')
    catalog = [
        ('C-EFFECT', 'The recorded effect can be linked to the exact fixture object', ['T-EFFECT']),
        ('C-AFTER', 'Dependent review follows sufficient effect evidence', ['T-AFTER']),
        ('C-SOURCE', 'The fixture configuration denies cross-account access', ['T-SOURCE']),
        ('C-CONTROL', 'The negative control configuration denies cross-account access', ['T-CONTROL']),
        ('C-TTL', 'The fake subject expires at its deadline while its control remains usable', ['T-TTL']),
        ('C-FINAL', 'Resource disposition evidence is reviewed before delivery', ['T-FINAL']),
    ]
    units = dict(zip([cases[0] for _, _, cases in catalog],
                     ['receipt-readback', 'dependency-readback', 'config-access-rule',
                      'config-access-rule', 'ttl-subject-control', 'resource-disposition']))
    criteria, cases = [], []
    for cid, rule, members in catalog:
        tid = members[0]
        criteria.append(dict(id=cid, rawText='Synthetic catalog — ' + rule, source='synthetic-catalog.json',
            requirement=rule, oracle=rule, applicability='applicable', caseIds=members, stoppingRule='all_cases'))
        cases.append(dict(id=tid, criterionIds=[cid], objective=rule, expectedBehavior=rule,
            expectationBasis='Predeclared synthetic fixture oracle', requiredEvidence=[units[tid]],
            coverageContext=dict(context, objective=rule, objectRef={
                'T-EFFECT': 'synthetic-object-1', 'T-TTL': 'synthetic-ttl-subject'}.get(tid, tid)),
            effects=['read'], resourceIds=[], actions=[]))
    indexed = {case['id']: case for case in cases}
    effect = indexed['T-EFFECT']
    effect['effects'] = ['mutation', 'read']
    effect['resourceIds'] = ['synthetic-scanner', 'synthetic-session']
    effect['actions'] = [dict(id='effect-once', caseId='T-EFFECT', effect='mutation'),
                         dict(id='read-effect-receipt', caseId='T-EFFECT', effect='read', readbackOf='effect-once')]
    indexed['T-AFTER']['dependsOnCases'] = ['T-EFFECT']
    ttl = indexed['T-TTL']
    ttl['resourceIds'] = ['synthetic-clock-resource']
    ttl['actions'] = [dict(id='read-ttl', caseId='T-TTL', effect='read')]
    coordinator = Coordinator(FIXTURE / 'coordinator', aid)
    run = dict(assessmentId=aid, coordinatorState=dict(directory=str(coordinator.root), assessmentId=aid),
        operations=[], criteriaWorkflow=dict(version=2, context=context, criteriaRevision='synthetic-catalog-1',
        planRevision='synthetic-plan-1', criteria=criteria, approvals=[], caseResults=[],
        plan=dict(cases=cases, authority=dict(source='synthetic fixture-only approval',
                    target='https://fixture.invalid', allowedEffects=['read', 'mutation']))))
    approve(run)
    for approval in run['criteriaWorkflow']['approvals']:
        approval['source'] = 'synthetic fixture-only ' + approval['kind']
    packet = make_packet(run, 'effect-task', ['T-EFFECT'], 'coordinator')
    packet_path = save(FIXTURE / 'packets' / 'effect-task.json', packet)
    binding = {key: packet[key] for key in ('taskId', 'workerId', 'packetDigest')}
    binding['packetRef'] = str(packet_path)
    operator = default_operator(run)
    operator['activeBlockId'] = 'B-STATE'
    operator['blocks'] = [
        dict(id='B-STATE', caseIds=['T-EFFECT', 'T-AFTER'], order=0, exitCondition='Retain exact effect and dependent review'),
        dict(id='B-INDEPENDENT', caseIds=['T-SOURCE', 'T-CONTROL'], order=1, exitCondition='Review both config fixtures'),
        dict(id='B-TIME-CLOSE', caseIds=['T-TTL', 'T-FINAL'], order=2, exitCondition='Review TTL and resource disposition'),
    ]
    operator['workItems'] = [
        work('effect-dispatch', 'T-EFFECT', block='B-STATE', action='effect-once',
             resourceIds=packet['resourceIds'], executionBinding=binding, basisRefs=[str(packet_path)],
             nextStep='Invoke the fixture-only callback once under Coordinator.dispatch'),
        work('effect-reader', 'T-EFFECT', block='B-STATE', action='read-effect-receipt', original='effect-once',
             resourceIds=packet['resourceIds'], executionBinding=binding, basisRefs=[str(FIXTURE / 'receipts' / 'effect-once.json')],
             nextStep='Inspect the retained effect receipt and review the exact action and object'),
        work('dependent-review', 'T-AFTER', block='B-STATE',
             nextStep='Review the evidence dependency after sufficient T-EFFECT evidence'),
        work('source-review', 'T-SOURCE', block='B-INDEPENDENT',
             basisRefs=[str(FIXTURE / 'control' / 'source-config.json')], nextStep='Read the synthetic source access rule'),
        work('control-review', 'T-CONTROL', block='B-INDEPENDENT', order=1,
             basisRefs=[str(FIXTURE / 'control' / 'control-config.json')], nextStep='Read the synthetic control access rule'),
        work('ttl-review', 'T-TTL', block='B-TIME-CLOSE', action='read-ttl', resourceIds=ttl['resourceIds'],
             phase='ttl-readback', notBefore='2026-11-05T00:00:00Z',
             subjectRefs=[str(FIXTURE / 'control' / 'ttl-subject.json')],
             controlRefs=[str(FIXTURE / 'control' / 'ttl-control.json')],
             nextStep='Compare the fixture subject and control at the injected time'),
        work('final-resource-review', 'T-FINAL', block='B-TIME-CLOSE', kind='resource-review', phase='closure',
             nextStep='Reconcile the fixture resource disposition against readback before delivery'),
    ]
    validate_operator(run, operator)
    save(BASE / 'setup' / 'synthetic-catalog.json', dict(synthetic=True, criteria=criteria))
    save(BASE / 'setup' / 'expected-results.json', dict(synthetic=True, expected={
         'T-EFFECT': dict(required='Exact retained action/object receipt after ACK', outcome='matched'),
         'T-AFTER': dict(required='Only after T-EFFECT sufficient reviewed evidence', outcome='matched'),
         'T-SOURCE': dict(expectedCrossAccountAccess='deny', injected='allow', outcome='violated'),
         'T-CONTROL': dict(expectedCrossAccountAccess='deny', injected='deny', outcome='matched'),
         'T-TTL': dict(deadline='2026-11-05T00:00:00Z', before='active', atOrAfter='expired', control='active'),
         'T-FINAL': dict(required='Reviewed disposition for all fixture resources'),
         'adapter': dict(positive='Read action/case/object and true terminal marker from envelope',
                         negative='Reject wrong action/object or false terminal marker')}))
    save(FIXTURE / 'control' / 'source-config.json', dict(crossAccountAccess='allow', fixture='source'))
    save(FIXTURE / 'control' / 'control-config.json', dict(crossAccountAccess='deny', fixture='control'))
    save(FIXTURE / 'control' / 'ttl-subject.json', dict(id='synthetic-ttl-subject', expiresAt='2026-11-05T00:00:00Z'))
    save(FIXTURE / 'control' / 'ttl-control.json', dict(id='synthetic-ttl-control', expiresAt='2026-11-06T00:00:00Z'))
    save(FIXTURE / 'control' / 'object-before.json', dict(objectRef='synthetic-object-1', value=0))
    COUNTER.touch(mode=0o600, exist_ok=False)
    save(FIXTURE / 'RUN-input.json', run)
    save(FIXTURE / 'OPERATOR-input.json', operator)
    baseline = (BASE / 'setup' / 'final-source-sha256.txt').read_text().splitlines()
    save(BASE / 'manifest.json', dict(version=1, episodeId=BASE.name, assessmentId=aid, synthetic=True,
        registryDir=str(FIXTURE / 'registry'), stateDir=str(STATE), coordinatorDir=str(coordinator.root),
        phaseAStartedAt=(BASE / 'setup' / 'phase-A-started.txt').read_text().strip(),
        phaseBStartedAt=None, sourceDigests={path: value for value, path in
                                            (line.split('  ', 1) for line in baseline)},
        head=(BASE / 'setup' / 'git-head.txt').read_text().strip()))
    print(json.dumps(dict(assessmentId=aid, packetRef=str(packet_path), packetDigest=packet['packetDigest'])))


def packet_operation(mode):
    run = store.load_current(STATE).run
    packet = store.read_json(FIXTURE / 'packets' / 'effect-task.json')
    validate_packet(run, packet, operational=False)
    coordinator = Coordinator(run['coordinatorState']['directory'], run['assessmentId'])
    if mode == 'validate-packet':
        print(json.dumps({key: packet[key] for key in ('assessmentId', 'taskId', 'workerId', 'packetDigest', 'resourceIds')}))
        return
    if mode == 'interrupt-acquire':
        print(json.dumps(dict(pid=os.getpid(), boundary='after-first-lease', taskId=packet['taskId'])), flush=True)
        interrupt(run, packet, coordinator, 'lease-1')
        raise RuntimeError('Expected child interruption')
    action = packet['cases'][0]['actions'][0]
    assert action['id'] == 'effect-once' and packet['authority']['target'] == 'https://fixture.invalid'

    def fake_effect(approved):
        sequence = len(COUNTER.read_bytes().splitlines()) + 1
        with COUNTER.open('ab') as log:
            log.write(canonical(dict(sequence=sequence, actionId=approved['id'])) + b'\n')
            log.flush()
            os.fsync(log.fileno())
        before = store.read_json(FIXTURE / 'control' / 'object-before.json')
        after = dict(before, value=before['value'] + 1)
        save(FIXTURE / 'control' / 'object-after.json', after)
        return str(save(FIXTURE / 'receipts' / 'effect-once.json', dict(synthetic=True,
            payload=dict(actionId=approved['id'], caseId=approved['caseId'], objectRef=after['objectRef'],
                         terminal=True, valueBefore=before['value'], valueAfter=after['value']),
            assessmentId=run['assessmentId'], taskId=packet['taskId'], packetDigest=packet['packetDigest'])))

    receipt = coordinator.dispatch(run, packet, action, fake_effect)
    print(json.dumps(dict(acknowledged=True, receiptRef=receipt, counterRef=str(COUNTER))))


def observe_config(cid):
    run = store.load_current(STATE).run
    case = next(row for row in run['criteriaWorkflow']['plan']['cases'] if row['id'] == cid)
    path = FIXTURE / 'control' / {'T-SOURCE': 'source-config.json', 'T-CONTROL': 'control-config.json'}[cid]
    raw = path.read_bytes()
    observed = json.loads(raw)['crossAccountAccess']
    if observed not in ('allow', 'deny'):
        raise ValueError('Unknown fixture config rule')
    print(json.dumps(dict(caseId=cid, sourceRef=str(path), sourceSha256=hashlib.sha256(raw).hexdigest(),
                          crossAccountAccess=observed, coverageContext=case['coverageContext'])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('primitive', choices=('setup', 'validate-packet', 'interrupt-acquire', 'dispatch',
                                             'observe-config', 'counter'))
    parser.add_argument('--case', choices=('T-SOURCE', 'T-CONTROL'))
    args = parser.parse_args()
    if args.primitive == 'setup':
        setup()
    elif args.primitive == 'observe-config':
        observe_config(args.case)
    elif args.primitive == 'counter':
        rows = [json.loads(line) for line in COUNTER.read_text().splitlines()]
        print(json.dumps(dict(count=len(rows), entries=rows, logRef=str(COUNTER))))
    else:
        packet_operation(args.primitive)
