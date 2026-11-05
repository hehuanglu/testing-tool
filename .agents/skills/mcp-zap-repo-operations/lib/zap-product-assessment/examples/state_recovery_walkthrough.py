"""Fixture-only walkthrough. Use a new output directory and src:tests on PYTHONPATH."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path

from test_assessment_state_cli import call, packet_result
from test_coordinator_recovery import interrupt
from test_criteria_workflow import approve, working
from test_operation_selection import schedule_fixture, work
from test_operator_state import VERIFIED, repair_proposal
from zap_assessment import assessment_store as store
from zap_assessment.contracts import canonical
from zap_assessment.criteria_delegation import Coordinator, make_packet
from zap_assessment.safety_io import atomic_bytes


def write(base, name, value):
    path = base / (name + '.json')
    atomic_bytes(path, canonical(value))
    return path


def child(base, mode):
    run = store.read_json(base / 'run.json')
    packet = store.read_json(base / 'packet.json')
    coordinator = Coordinator(run['coordinatorState']['directory'], run['assessmentId'])
    if mode == 'interrupt':
        interrupt(run, packet, coordinator, 'lease-1')
        raise AssertionError('interruption did not occur')
    def effect(_):
        return write(base, 'fake-effect-receipt', dict(count=1, actionId='effect', fixture=True))
    coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], effect)


def walkthrough(base):
    base.mkdir(mode=0o700)
    state = base / 'state'
    registry = base / 'registry'
    rows = []

    def cli(command, *args, registry_command=False):
        destination = ('--registry-dir', registry) if registry_command else ('--state-dir', state)
        process = call(command, *destination, *args)
        if process.returncode:
            raise RuntimeError(process.stdout + process.stderr)
        return json.loads(process.stdout)

    def stage(name, **details):
        record = dict(stage=name, **details)
        rows.append(record)
        print(json.dumps(record), flush=True)

    def process(mode, expected):
        process = subprocess.run([sys.executable, '-B', __file__, str(base), '--child', mode], timeout=15)
        assert process.returncode == expected, process.returncode

    def current():
        return store.load_current(state)

    def commit_operator(key, operator, run=None):
        snapshot = current()
        return cli('state-commit', '--expected-generation', snapshot.generation_id, '--commit-id', key,
                   '--run', write(base, key + '-run', run if run is not None else snapshot.run),
                   '--operator', write(base, key + '-operator', operator))

    def merge(key, packet_path, packet, operations=(), results=()):
        return cli('state-merge', '--expected-generation', current().generation_id,
                   '--commit-id', key, '--packet', packet_path,
                   '--result', write(base, key + '-result', packet_result(packet, operations, results)))

    run, _ = schedule_fixture()
    workflow = run['criteriaWorkflow']
    first, second = workflow['plan']['cases']
    # Review the root T1 before its dependent T2.
    second['dependsOnCases'] = ['T1']
    third = dict(copy.deepcopy(second), id='T3', dependsOnCases=[], actions=[])
    workflow['plan']['cases'].append(third)
    workflow['criteria'][0]['caseIds'].append('T3')
    workflow['plan']['resourceIds'] = ['scanner', 'fixture-session']
    approve(run)
    coordinator = Coordinator(base / 'coordinator', run['assessmentId'])
    run['coordinatorState'] = dict(directory=str(coordinator.root), assessmentId=run['assessmentId'])
    from zap_assessment.operator_state import default_operator
    packet = make_packet(run, 'fixture-task', ['T1'], 'coordinator')
    packet_path = write(base, 'packet', packet)
    binding = {key: packet[key] for key in ('taskId', 'workerId', 'packetDigest')}
    binding['packetRef'] = str(packet_path)
    operator = default_operator(run)
    operator['workItems'] = [
        work('reader', action='reader', original='effect', resourceIds=['scanner', 'fixture-session']),
        work('independent', 'T3', order=1),
        work('ttl', action='ttl', resourceIds=['scanner', 'fixture-session'], phase='ttl-readback',
             notBefore='2026-11-05T00:00:00Z', subjectRefs=['fixture-session'], controlRefs=['fixture-control']),
        work('fresh', action='effect', resourceIds=['scanner', 'fixture-session'], executionBinding=binding),
    ]
    source = write(base, 'run', run)
    init = cli('state-init', '--registry-dir', registry, '--run', source,
               '--operator', write(base, 'operator', operator), '--registration-id', 'synthetic-registration')
    stage('1-synthetic-approval', generationId=init['generationId'],
          storePath=cli('state-resolve', '--assessment-id', 'A1', registry_command=True)['storePath'])

    process('interrupt', 77)
    assert cli('state-inspect-recovery')['openTransactions']
    cli('state-recover-leases', '--packet', packet_path)
    assert not (base / 'fake-effect-receipt.json').exists()
    after_recovery = cli('state-next')
    selected = after_recovery['nextAction']
    assert selected['kind'] == 'dispatch' and selected['actionId'] == 'effect'
    assert not after_recovery['canConcludeTurn']
    stage('2-lease-recovery', fakeEffectCount=0, nextAction=selected['kind'],
          actionId=selected['actionId'], canConcludeTurn=after_recovery['canConcludeTurn'])

    process('effect', 0)
    retained = base / 'fake-effect-receipt.json'
    assert store.read_json(retained)['count'] == 1
    stage('3-fake-effect', fakeEffectCount=1, receipt=str(retained))

    complete = working()
    first_operation = dict(complete['operations'][0], actionId='effect')
    merge('retained-merge', packet_path, packet, [first_operation])
    assert store.read_json(retained)['count'] == 1
    after_merge = cli('state-next')
    assert after_merge['pendingActionIds'] == ['effect']
    assert any(row['workId'] == 'fresh' and row['reasonCode'] == 'consumed-action'
               for row in after_merge['deferred'])
    updated = current().operator
    updated['workItems'][3].update(state='done', completionRefs=[str(retained)])
    commit_operator('fresh-done', updated)
    stage('4-cold-retained-merge', fakeEffectCount=1)

    proposal = repair_proposal(id='repair-reader')
    cli('state-repair-open', '--expected-generation', current().generation_id,
        '--commit-id', 'open-reader', '--repair', write(base, 'open-reader', proposal))
    assert cli('state-next')['nextAction']['workId'] == 'independent'

    def case_observation(cid, oid):
        operation = dict(complete['operations'][0], id=oid)
        result = copy.deepcopy(complete['criteriaWorkflow']['caseResults'][0])
        result['caseId'] = cid
        result['evidenceLinks'][0]['operationId'] = oid
        return operation, result

    independent_packet = make_packet(current().run, 'independent-source', ['T3'], 'coordinator')
    op, result = case_observation('T3', 'independent-observation')
    merge('independent-merge', write(base, 'independent-packet', independent_packet),
          independent_packet, [op], [result])
    updated = current().operator
    updated['workItems'][1].update(state='done', completionRefs=['independent-observation'])
    commit_operator('independent-done', updated)
    for revision, status in enumerate(('reproducing', 'implementing', 'verifying', 'verified'), 1):
        payload = dict(id='repair-reader', revision=revision, status=status)
        if status == 'verified':
            payload.update(VERIFIED)
        key = 'repair-' + status
        cli('state-repair-update', '--expected-generation', current().generation_id,
            '--commit-id', key, '--repair', write(base, key, payload))
    assert cli('state-next')['nextAction']['actionId'] == 'reader'
    stage('5-repair-and-independent-work', originalReadback='reader')

    terminal = dict(first_operation, id='terminal', context={'assessmentId': 'A1'},
                    reconciledActionId='effect', effectStatus='terminal')
    merge('terminal-merge', packet_path, packet, [terminal])
    cli('criteria-reconcile-action', '--packet', packet_path, '--action-id', 'effect',
        '--operation-id', 'terminal', '--release')
    followup = make_packet(current().run, 'fixture-followup', ['T1', 'T2'], 'coordinator')
    op2, result2 = case_observation('T2', 'dependent-observation')
    merge('remaining-cases', write(base, 'followup-packet', followup), followup, [op2],
          [complete['criteriaWorkflow']['caseResults'][0], result2])
    updated = current().operator
    updated['workItems'][0].update(state='done', completionRefs=['terminal'])
    commit_operator('reader-done', updated)
    before = cli('state-next', '--now', '2026-11-04T00:00:00Z')
    assert before['nextWakeAt'] == '2026-11-05T00:00:00+00:00'
    assert cli('state-next', '--now', '2026-11-05T00:00:00Z')['nextAction']['workId'] == 'ttl'
    stage('6-ttl-selection', nextWakeAt=before['nextWakeAt'])
    updated = current().operator
    updated['workItems'][2].update(state='done', completionRefs=['synthetic-ttl-check'])
    completed = current().run
    resource_ids = ['scanner', 'fixture-session']
    facts = {rid: dict(resourceId=rid, status='stopped', producerActive=False) for rid in resource_ids}
    completed['operations'].append(dict(id='fixture-resource-review', status='completed',
        coverageContext=workflow['context'], readback=facts))
    completed['criteriaWorkflow']['resourceReview'] = dict(reviewed=True, basis='Synthetic disposal readback',
        resources=[dict(id=rid, status='stopped', basis='Fixture only',
                        operationId='fixture-resource-review', resultPath='/readback/' + rid)
                   for rid in resource_ids])
    commit_operator('ttl-done', updated, completed)

    delivery = cli('state-next')['nextAction']
    assert delivery['kind'] == 'verify-final-delivery'
    updated = current().operator
    updated['delivery'] = dict(fileId='synthetic-sheet', worksheetId='synthetic-tab',
        status='verified', sourceDigest=delivery['sourceDigest'], verifiedAt='2026-11-05T00:00:00Z',
        readbackRefs=['synthetic-delivery-readback'])
    commit_operator('delivery', updated)
    decision = cli('state-next')
    assert decision['nextAction']['kind'] == 'workflow-done'
    assert store.read_json(retained)['count'] == 1
    stage('7-synthetic-delivery', decision=decision['nextAction']['kind'], fakeEffectCount=1,
          projections=cli('state-render'))
    write(base, 'walkthrough-summary', rows)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--child', choices=('interrupt', 'effect'))
    args = parser.parse_args()
    if args.child:
        child(args.output.resolve(), args.child)
    else:
        walkthrough(args.output.resolve())
