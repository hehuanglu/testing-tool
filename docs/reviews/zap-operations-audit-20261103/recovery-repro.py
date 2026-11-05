"""Offline, synthetic recovery probes; no network and no source mutations.
Run with python3 docs/reviews/zap-operations-audit-20261103/recovery-repro.py.
"""
from pathlib import Path
import contextlib
import io
import json
import os
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / '.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
sys.path[:0] = [str(LIB / 'src'), str(LIB / 'tests')]
from test_criteria_workflow import CoordinatorRecoveryTests, approve
from zap_assessment.criteria_delegation import Coordinator, make_packet
from zap_assessment.criteria_resume import resume_next
from zap_assessment.journal import Journal
from zap_assessment.safety_io import atomic_bytes


def attempt(name, callback):
    try:
        result = callback()
        print(name + ': OK ' + str(result))
    except Exception as error:
        print(name + ': ' + type(error).__name__ + ': ' + str(error))


with tempfile.TemporaryDirectory() as td:
    run, packet, coordinator = CoordinatorRecoveryTests().prepare(td)
    run['criteriaWorkflow']['plan']['resourceIds'] = ['one', 'two']
    approve(run)
    packet = make_packet(run, 'W1', ['T1'], 'worker')
    coordinator.acquire(run, packet)
    unlink = Path.unlink
    count = [0]
    def fail_second_unlink(path, *args, **kwargs):
        if path.parent == coordinator.resources:
            count[0] += 1
            if count[0] == 2:
                raise OSError('injected second unlink failure')
        return unlink(path, *args, **kwargs)
    with patch.object(Path, 'unlink', fail_second_unlink):
        attempt('R1 partial release', lambda: coordinator.release(run, packet))
    attempt('R1 cold resume', lambda: resume_next(run))
    attempt('R1 retry release', lambda: Coordinator(td, 'A1').release(run, packet))
    attempt('R1 retry acquire', lambda: Coordinator(td, 'A1').acquire(run, packet))

with tempfile.TemporaryDirectory() as td:
    run, packet, coordinator = CoordinatorRecoveryTests().prepare(td)
    # Exact on-disk state after durable lease publication, before leased append.
    resource = packet['resourceIds'][0]
    atomic_bytes(coordinator._path(resource), json.dumps(dict(coordinator._binding(packet), resourceId=resource)).encode())
    attempt('R2 orphan acquisition resume', lambda: resume_next(run))
    attempt('R2 orphan acquisition retry', lambda: Coordinator(td, 'A1').acquire(run, packet))
    attempt('R2 orphan acquisition release', lambda: Coordinator(td, 'A1').release(run, packet))

with tempfile.TemporaryDirectory() as td:
    run, packet, coordinator = CoordinatorRecoveryTests().prepare(td)
    append = Journal.append
    def lost_fsync_ack(journal, kind, data):
        result = append(journal, kind, data)
        if kind == 'leased':
            raise OSError('injected failure after leased record reached disk')
        return result
    with patch.object(Journal, 'append', lost_fsync_ack):
        attempt('R3 acquisition ambiguous journal append', lambda: coordinator.acquire(run, packet))
    attempt('R3 acquisition cold resume', lambda: resume_next(run))
    attempt('R3 acquisition retry', lambda: Coordinator(td, 'A1').acquire(run, packet))

with tempfile.TemporaryDirectory() as td:
    run, packet, coordinator = CoordinatorRecoveryTests().prepare(td)
    coordinator.acquire(run, packet)
    coordinator.dispatch(run, packet, packet['cases'][0]['actions'][0], lambda action: {'fixture': 'retained ACK'})
    # Exact crash image of a subsequent append that did not finish its record.
    with open(coordinator.directory / 'journal.jsonl', 'ab') as stream:
        stream.write(b'{"seq":3,')
        stream.flush()
        os.fsync(stream.fileno())
    attempt('R4 torn journal resume', lambda: resume_next(run))
    attempt('R4 torn journal status', lambda: Coordinator(td, 'A1').status())
    attempt('R4 torn journal release', lambda: Coordinator(td, 'A1').release(run, packet))

with tempfile.TemporaryDirectory() as td:
    run, packet, coordinator = CoordinatorRecoveryTests().prepare(td)
    paths = {name: Path(td) / (name + '.json') for name in ('run', 'packet', 'result', 'merged')}
    result = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
    result.update(operations=[], caseResults=[])
    for name, value in [('run', run), ('packet', packet), ('result', result)]:
        paths[name].write_text(json.dumps(value))
    args = ['criteria-merge', '--run', str(paths['run']), '--packet', str(paths['packet']), '--result', str(paths['result']), '--output', str(paths['merged'])]
    def merge():
        from zap_assessment.product_scope_cli import main
        with contextlib.redirect_stdout(io.StringIO()):
            return main(args)
    attempt('R5 first merge', merge)
    attempt('R5 repeat merge same output', merge)
    print('R5 original input still exists:', paths['run'].exists())
