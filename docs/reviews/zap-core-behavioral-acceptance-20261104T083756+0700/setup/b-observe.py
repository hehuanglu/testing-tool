"""Offline evidence and input primitives. Work selection and writes are separate."""
import json
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from zap_assessment.assessment_store import load_current, read_json
from zap_assessment.contracts import canonical
from zap_assessment.criteria_delegation import Coordinator, coordinator_lock, validate_packet
from zap_assessment.operator_state import timestamp

base = Path(__file__).resolve().parents[1]
fixture = base / 'fixture'
evidence = base / 'evidence'
setup = base / 'setup'
manifest = read_json(base / 'manifest.json')
snapshot = load_current(manifest['stateDir'])
run, operator = snapshot.run, snapshot.operator

def emit(value):
    print(json.dumps(value, ensure_ascii=False))

def save(path, value):
    with path.open('xb') as stream:
        stream.write(canonical(value) + b'\n')
    return str(path)

def evidence_ref(name):
    return evidence / (name + '.stdout')

def observe_effect():
    checkpoint = read_json(Path(manifest['checkpointRef']))
    receipt = Path(checkpoint['receiptRef'])
    packet = read_json(Path(checkpoint['packetRef']))
    validate_packet(run, packet, operational=False)
    payload = read_json(evidence_ref('b-receipt'))
    envelope = read_json(receipt)
    raw_digest = sha256(receipt.read_bytes()).hexdigest()
    assert raw_digest == checkpoint['receiptSha256']
    for field in ('assessmentId', 'taskId', 'packetDigest'):
        assert envelope[field] == packet[field], field
    assert packet['packetDigest'] == checkpoint['packetDigest']
    assert payload == envelope['payload'] and payload['terminal'] is True
    case, = packet['cases']
    assert (payload['actionId'], payload['caseId'], payload['objectRef']) == (
        'effect-once', case['id'], case['coverageContext']['objectRef'])
    for suffix, key in [('before', 'valueBefore'), ('after', 'valueAfter')]:
        actual = read_json(fixture / 'control' / ('object-' + suffix + '.json'))
        assert actual == {'objectRef': payload['objectRef'], 'value': payload[key]}
    assert payload['valueAfter'] == payload['valueBefore'] + 1
    emit(dict(payload, receiptRef=str(receipt), receiptSha256=raw_digest,
              packetDigest=packet['packetDigest'], assessmentId=packet['assessmentId'], taskId=packet['taskId']))

def case_result(label, packet_path, observation_label, pointer, basis, outcome):
    packet = read_json(packet_path)
    validate_packet(run, packet, operational=False)
    case, = packet['cases']
    cid = case['id']
    observation_path = evidence_ref(observation_label)
    observation = read_json(observation_path)
    oid = 'observation-' + cid.lower()
    context = case['coverageContext']
    op = dict(id=oid, caseId=cid, status='completed', effect='read', coverageContext=context,
              provenance=dict(transport='synthetic-offline-fixture', observationRef=str(observation_path)),
              readback=observation)
    if cid == 'T-EFFECT':
        assert observation['terminal'] and observation['objectRef'] == context['objectRef']
        op.update(context={'assessmentId': packet['assessmentId']}, actionId='read-effect-receipt',
                  reconciledActionId=observation['actionId'], effectStatus='terminal')
    if cid == 'T-TTL':
        assert observation['actionId'] == 'read-ttl'
        op.update(context={'assessmentId': packet['assessmentId']}, actionId='read-ttl',
                  reconciledActionId='read-ttl', effectStatus='terminal')
    result = dict(caseId=cid, outcome=outcome, basis=basis, evidenceLinks=[
        dict(operationId=oid, observationUnits=case['requiredEvidence'], resultPath='/readback' + pointer,
             resultRead=True, basis=basis, context=context, role='support')])
    worker = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
    emit(dict(resultRef=save(setup / (label + '-result.json'),
                            dict(worker, operations=[op], caseResults=[result])),
              caseId=cid, operationId=oid, outcome=outcome, basis=basis))

def prepare(label, *ids_and_refs):
    ids, refs = ids_and_refs[0].split(','), ids_and_refs[1:]
    assert refs and all(Path(ref).is_file() for ref in refs)
    for wid in ids:
        item = next(work for work in operator['workItems'] if work['id'] == wid)
        item.update(state='done', waiting=None, completionRefs=list(refs))
    emit(dict(generationId=snapshot.generation_id, runRef=str(snapshot.run_path),
              operatorRef=save(setup / (label + '-operator.json'), operator)))

def dependency(review_label, decision_label):
    review, decision = (read_json(evidence_ref(label)) for label in (review_label, decision_label))
    assert decision['generationId'] == snapshot.generation_id
    assert decision['nextAction']['workId'] == 'dependent-review'
    assert not decision['pendingActionIds']
    plan = run['criteriaWorkflow']['plan']['cases']
    case = next(c for c in plan if c['id'] == 'T-AFTER')
    assert case['dependsOnCases'] == ['T-EFFECT']
    prerequisite = next(r for r in review['caseResults'] if r['caseId'] == 'T-EFFECT')
    assert prerequisite['outcome'] in ('matched', 'violated')
    assert prerequisite['evidence']['supportedUnits'] == ['receipt-readback']
    assert not prerequisite['evidence']['missingUnits']
    assert prerequisite['evidence']['supportOperationIds'] == ['observation-t-effect']
    emit(dict(caseId=case['id'], prerequisite=prerequisite, ready=True,
              reviewRef=str(evidence_ref(review_label)), generationId=snapshot.generation_id))


def ttl_work(state):
    return next(w for w in state.operator['workItems'] if w['id'] == 'ttl-review')

def clock_facts(work, when):
    now = timestamp(when)
    sources = {}
    for role, field in [('subject', 'subjectRefs'), ('control', 'controlRefs')]:
        path, = map(Path, work[field])
        assert path.parent == fixture / 'control'
        raw = path.read_bytes()
        value = json.loads(raw)
        sources[role] = dict(value, ref=str(path), sha256=sha256(raw).hexdigest(),
                             observedStatus='active' if now < timestamp(value['expiresAt']) else 'expired')
    assert sources['subject']['id'] == 'synthetic-ttl-subject'
    assert sources['control']['id'] == 'synthetic-ttl-control'
    assert timestamp(sources['subject']['expiresAt']) == timestamp(work['notBefore'])
    return dict(synthetic=True, injectedAt=when, **sources)

def ttl_before(when, decision_label):
    work = ttl_work(snapshot)
    decision = read_json(evidence_ref(decision_label))
    assert decision['generationId'] == snapshot.generation_id
    assert any(d['workId'] == work['id'] and d['reasonCode'] == 'not-before'
               for d in decision['deferred'])
    assert timestamp(when) < timestamp(work['notBefore'])
    emit(clock_facts(work, when))

def ttl_bind(packet_path, decision_label):
    decision = read_json(evidence_ref(decision_label))
    work = ttl_work(snapshot)
    assert decision['generationId'] == snapshot.generation_id
    assert decision['nextAction']['workId'] == work['id']
    packet = read_json(packet_path)
    validate_packet(run, packet)
    assert packet['resourceIds'] == work['resourceIds']
    assert any(a['id'] == work['actionRef']['actionId'] and a['effect'] == 'read'
               for c in packet['cases'] for a in c['actions'])
    assert 'executionBinding' not in work
    work['executionBinding'] = dict({k: packet[k] for k in ('taskId', 'workerId', 'packetDigest')},
                                    packetRef=packet_path)
    emit(dict(generationId=snapshot.generation_id, runRef=str(snapshot.run_path),
              operatorRef=save(setup / 'b-ttl-bind-operator.json', operator)))

def ttl_runtime(mode, decision_label, when):
    with coordinator_lock(run):
        current = load_current(manifest['stateDir'])
        work = ttl_work(current)
        decision = read_json(evidence_ref(decision_label))
        assert decision['generationId'] == current.generation_id
        assert decision['nextAction']['workId'] == work['id']
        assert timestamp(when) >= timestamp(work['notBefore'])
        binding = work['executionBinding']
        packet = read_json(binding['packetRef'])
        validate_packet(current.run, packet)
        assert packet['authority']['target'] == 'https://fixture.invalid'
        assert all(packet[k] == binding[k] for k in ('taskId', 'workerId', 'packetDigest'))
        assert packet['resourceIds'] == ['synthetic-clock-resource'] == work['resourceIds']
        coordinator = Coordinator(current.run['coordinatorState']['directory'], current.run['assessmentId'])
        if mode == 'acquire':
            assert decision['nextAction']['reasonCode'] == 'acquire-execution-lease'
            emit(coordinator.acquire(current.run, packet))
            return
        assert mode == 'read' and decision['nextAction']['kind'] == 'dispatch'
        case, = packet['cases']
        action, = case['actions']
        assert action == dict(id='read-ttl', caseId='T-TTL', effect='read')
        assert case['coverageContext']['objectRef'] == 'synthetic-ttl-subject'

        def read_clock(admitted):
            assert admitted == action
            value = clock_facts(work, when)
            baseline_path = evidence_ref('b-ttl-before-read')
            baseline = read_json(baseline_path)
            for role in ('subject', 'control'):
                for field in ('id', 'ref', 'sha256', 'expiresAt'):
                    assert baseline[role][field] == value[role][field]
            result = dict(value, actionId=admitted['id'], caseId=case['id'], assessmentId=packet['assessmentId'],
                          packetDigest=packet['packetDigest'], resourceIds=packet['resourceIds'],
                          baselineRef=str(baseline_path), terminal=True)
            receipt = fixture / 'receipts' / 'b-ttl-read.json'
            save(receipt, result)
            return dict(result, receiptRef=str(receipt))

        emit(coordinator.dispatch(current.run, packet, action, read_clock))

if __name__ == '__main__':
    actions = {'effect': observe_effect, 'case': case_result, 'done': prepare, 'dependency': dependency,
               'ttl-before': ttl_before, 'ttl-bind': ttl_bind, 'ttl-runtime': ttl_runtime}
    actions[sys.argv[1]](*sys.argv[2:])
