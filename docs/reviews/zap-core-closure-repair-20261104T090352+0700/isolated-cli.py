"""Verify pre-closure to verified delivery with a new offline managed fixture."""
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

from test_assessment_state_cli import packet_result
from test_criteria_workflow import approve, working
from test_operation_selection import closure_work
from zap_assessment.criteria_delegation import Coordinator
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.operation_selection import delivery_digest
from zap_assessment.operator_state import default_operator

REVIEW = Path(__file__).resolve().parent
FIXTURE = REVIEW / 'isolated-cli-fixture'
STATE = FIXTURE / 'state'
REGISTRY = FIXTURE / 'registry'
ASSESSMENT = 'synthetic-closure-selector-repair'
CASE = 'T-FINAL'
RESOURCE = 'synthetic-resource'
NOW = '2026-11-05T00:00:00Z'


def read(path):
    return json.loads(Path(path).read_bytes())


def write(name, value):
    path = FIXTURE / (name + '.json')
    with path.open('x') as stream:
        json.dump(value, stream, indent=2)
        stream.write('\n')
    return str(path)


def capture(label, *args):
    subprocess.run([sys.executable, '-B', str(REVIEW / 'capture.py'), label, *map(str, args)],
                   check=True)
    return read(REVIEW / (label + '.stdout'))


def cli(label, command, *args):
    return capture('cli-' + label, sys.executable, '-B', '-m', 'zap_assessment.product_cli',
                   'scope', command, *args)


def state(label, command, *args):
    return cli(label, command, '--state-dir', STATE, *args)


def verify_table(table_path, inspect_path, review_path):
    source = read(review_path)
    inspect = read(inspect_path)
    run = read(inspect['runRef'])
    raw = Path(table_path).read_bytes()
    table = json.loads(raw)
    assert source == review_workflow(run) and source['eligibleForCompletion']
    assert table['rows'] == source['criterionResults']
    assert [row['criterionId'] for row in table['rows']] == [c['id'] for c in run['criteriaWorkflow']['criteria']]
    assert table['sourceDigest'] == delivery_digest(run, source)
    assert table['synthetic'] and table['fileId'].startswith('synthetic-')
    print(json.dumps(dict(verified=True, generationId=inspect['generationId'], tableRef=table_path,
                          tableSha256=sha256(raw).hexdigest(), table=table)))


def main():
    FIXTURE.mkdir(mode=0o700)
    coordinator = Coordinator(FIXTURE / 'coordinator', ASSESSMENT)
    run = working(None)
    run.update(assessmentId=ASSESSMENT,
               coordinatorState=dict(directory=str(coordinator.root), assessmentId=ASSESSMENT))
    workflow = run['criteriaWorkflow']
    workflow.pop('resourceReview')
    workflow['context'] = dict(product='synthetic-closure', environment='offline')
    workflow['plan']['authority'].update(target='https://fixture.invalid', source='synthetic read-only plan')
    rule = 'Verify local fixture resource disposition before delivery'
    context = dict(workflow['context'], objective=rule)
    workflow['plan']['cases'][0].update(
        id=CASE, objective=rule, expectedBehavior='Stopped', expectationBasis='Predeclared fixture oracle',
        requiredEvidence=['resource-disposition'], resourceIds=[RESOURCE], coverageContext=context)
    workflow['criteria'][0].update(id='C-FINAL', rawText=rule, requirement=rule, oracle='Stopped', caseIds=[CASE])
    workflow['plan']['cases'][0]['criterionIds'] = ['C-FINAL']
    approve(run)
    operator = default_operator(run)
    operator['workItems'] = [closure_work(CASE)]
    resource_input = write('resource-input', dict(resourceId=RESOURCE, status='stopped', producerActive=False))
    registered = state('init', 'state-init', '--registry-dir', REGISTRY, '--registration-id', 'closure-repair',
                       '--run', write('run-input', run), '--operator', write('operator-input', operator))
    resolved = cli('resolve', 'state-resolve', '--registry-dir', REGISTRY, '--assessment-id', ASSESSMENT)
    assert Path(resolved['storePath']) == STATE
    start = state('pre-closure-inspect', 'state-inspect')
    initial = state('pre-closure-review', 'criteria-review')
    recovery = state('pre-closure-recovery', 'state-inspect-recovery')
    assert start['generationId'] == registered['generationId']
    assert [row['caseId'] for row in initial['nextWork']] == [CASE]
    assert not initial['eligibleForCompletion']
    assert recovery['integrity'] == 'clean'
    assert not any(recovery[key] for key in ('leases', 'pendingEffects', 'openTransactions', 'consumedActionIds'))
    decision = state('pre-closure-next', 'state-next', '--now', NOW)
    action = decision['nextAction']
    assert decision['readyWorkIds'] == ['final-resource-review'] and decision['mode'] == 'normal'
    assert (action['kind'], action['workId'], action['caseId']) == ('resource-review', 'final-resource-review', CASE)
    assert not decision['canConcludeTurn']

    packet_path = FIXTURE / 'packet.json'
    state('packet', 'criteria-packet', '--task-id', 'closure-read', '--worker-id', 'coordinator',
          '--case-id', CASE, '--output', packet_path)
    raw_resource = Path(resource_input).read_bytes()
    observed = json.loads(raw_resource)
    assert observed == dict(resourceId=RESOURCE, status='stopped', producerActive=False)
    assert list(coordinator.resources.iterdir()) == []
    observation_path = write('resource-observation', dict(resource=observed, inputRef=resource_input,
        inputSha256=sha256(raw_resource).hexdigest(), recoveryRef=str(REVIEW / 'cli-pre-closure-recovery.stdout'),
        leaseFiles=[]))
    op = dict(id='resource-observation', caseId=CASE, status='completed', effect='read',
              coverageContext=context, readback=read(observation_path))
    basis = 'Read fixture resource state and checked empty lease directory'
    link = dict(operationId=op['id'], resultPath='/readback/resource', observationUnits=['resource-disposition'],
                resultRead=True, context=context, role='support', basis=basis)
    result = dict(caseId=CASE, outcome='matched', basis=basis, evidenceLinks=[link])
    merged = state('merge', 'state-merge', '--expected-generation', start['generationId'],
                   '--commit-id', 'closure-merge', '--packet', packet_path,
                   '--result', write('worker-result', packet_result(read(packet_path), [op], [result])))
    run = read(merged['runRef'])
    operator = read(merged['operatorRef'])
    run['criteriaWorkflow']['resourceReview'] = dict(reviewed=True, basis=basis, resources=[
        dict(id=RESOURCE, status=observed['status'], basis=basis, operationId=op['id'], resultPath='/readback/resource')])
    operator['workItems'][0].update(state='done', completionRefs=[observation_path])
    closed = state('closure-commit', 'state-commit', '--expected-generation', merged['generationId'],
                   '--commit-id', 'closure-complete', '--run', write('run-closed', run),
                   '--operator', write('operator-closed', operator))
    source = state('delivery-source', 'criteria-review')
    assert source['eligibleForCompletion'] and source['assessmentStatus'] == 'completed'
    inspect = state('delivery-inspect', 'state-inspect')
    assert inspect['generationId'] == closed['generationId']
    delivery = state('delivery-next', 'state-next', '--now', NOW)
    source_digest = delivery['nextAction']['sourceDigest']
    assert delivery['nextAction']['kind'] == 'verify-final-delivery' and not delivery['canConcludeTurn']
    table_path = write('synthetic-table', dict(synthetic=True, fileId='synthetic-closure-file',
        worksheetId='synthetic-closure-tab', sourceDigest=source_digest, rows=source['criterionResults']))
    readback = capture('cli-delivery-readback', sys.executable, '-B', __file__, '--readback', table_path,
                       REVIEW / 'cli-delivery-inspect.stdout', REVIEW / 'cli-delivery-source.stdout')
    assert readback['verified'] and readback['generationId'] == inspect['generationId']
    operator['delivery'] = dict({key: readback['table'][key] for key in ('fileId', 'worksheetId', 'sourceDigest')},
        status='verified', verifiedAt=NOW, readbackRefs=[str(REVIEW / 'cli-delivery-readback.stdout')])
    receipt = state('delivery-commit', 'state-commit', '--expected-generation', closed['generationId'],
                    '--commit-id', 'closure-delivery', '--run', closed['runRef'],
                    '--operator', write('operator-delivered', operator))
    final = state('final-next', 'state-next', '--now', NOW)
    integrity = state('final-inspect', 'state-inspect')
    recovery = state('final-recovery', 'state-inspect-recovery')
    assert final['generationId'] == receipt['generationId'] == integrity['generationId']
    assert final['nextAction']['kind'] == 'workflow-done' and final['canConcludeTurn']
    assert final['nextAction']['sourceDigest'] == source_digest
    assert integrity['currentIntegrity'] == integrity['historyIntegrity'] == recovery['integrity'] == 'clean'
    assert integrity['committedGenerationCount'] == 4
    assert not any(recovery[key] for key in ('leases', 'pendingEffects', 'openTransactions', 'consumedActionIds'))
    print(json.dumps(dict(assessmentId=ASSESSMENT, storePath=str(STATE), finalGenerationId=final['generationId'],
                          generations=4, sourceDigest=source_digest, dispatches=0, finalSelector='workflow-done')))


if __name__ == '__main__':
    if sys.argv[1:] and sys.argv[1] == '--readback':
        verify_table(*sys.argv[2:])
    else:
        main()
