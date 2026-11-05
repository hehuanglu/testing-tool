"""Read local resource disposition or prepare one managed closure input."""
import json
import sys
from pathlib import Path

from zap_assessment.assessment_store import load_current, read_json
from zap_assessment.contracts import canonical

base = Path(__file__).resolve().parents[1]
ev = base / 'evidence'
manifest = read_json(base / 'manifest.json')
snapshot = load_current(manifest['stateDir'])
workflow = snapshot.run['criteriaWorkflow']
oid = 'observation-t-final'

if sys.argv[1] == 'observe':
    decision = read_json(ev / 'b-resource-next.stdout')
    assert snapshot.generation_id == decision['generationId']
    assert decision['readyWorkIds'] == ['final-resource-review'] and not decision['deferred']
    recovery_path = ev / 'b-ttl-released.stdout'
    recovery = read_json(recovery_path)
    assert recovery['integrity'] == 'clean' and recovery['pendingCertainty'] == 'complete'
    assert not any(recovery[k] for k in ('pendingEffects', 'leases', 'openTransactions'))
    resources_dir = Path(manifest['coordinatorDir']) / 'resources'
    assert list(resources_dir.iterdir()) == []
    required = {rid for case in workflow['plan']['cases'] for rid in case['resourceIds']}
    assert required == {'synthetic-scanner', 'synthetic-session', 'synthetic-clock-resource'}
    released = {}
    journal_path = Path(recovery['journalPath'])
    events = [json.loads(line) for line in journal_path.read_bytes().splitlines()]
    assert events[-1]['hash'] == recovery['lastValidHash']
    for label in ('b-effect-reconcile', 'b-ttl-reconcile'):
        release_path = ev / (label + '.stdout')
        receipt = read_json(release_path)
        assert receipt['released'] and receipt['assessmentId'] == snapshot.run['assessmentId']
        event, = [row for row in events if row['kind'] == 'released'
                  and row['data']['transactionId'] == receipt['transactionId']]
        assert event['data']['resourceIds'] == receipt['resourceIds']
        for rid in receipt['resourceIds']:
            assert rid not in released
            released[rid] = dict(resourceId=rid, status='stopped', producerActive=False,
                basis='Fixture resources are in-process stand-ins. The finite callback exited and the owned lease was released.',
                releaseRef=str(release_path), journalSeq=event['seq'], journalHash=event['hash'])
    assert set(released) == required
    print(json.dumps(dict(synthetic=True, resources=released, recoveryRef=str(recovery_path),
                          resourceDirectory=str(resources_dir), leaseFiles=[], journalRef=str(journal_path))))
elif sys.argv[1] == 'prepare':
    evidence_path = ev / 'b-resource-observation.stdout'
    observed = read_json(evidence_path)
    op = next(op for op in snapshot.run['operations'] if op['id'] == oid)
    assert op['readback'] == observed
    workflow['resourceReview'] = dict(reviewed=True,
        basis='Checked all case resources against clean coordinator state, matching release receipts, and empty lease directory',
        resources=[dict(id=rid, status=row['status'], basis=row['basis'], operationId=oid,
                        resultPath='/readback/resources/' + rid)
                   for rid, row in sorted(observed['resources'].items())])
    item = next(w for w in snapshot.operator['workItems'] if w['id'] == 'final-resource-review')
    item.update(state='done', waiting=None, completionRefs=[str(evidence_path)])
    refs = dict(generationId=snapshot.generation_id)
    for key, name, value in [('runRef', 'b-closure-run.json', snapshot.run),
                             ('operatorRef', 'b-closure-operator.json', snapshot.operator)]:
        path = base / 'setup' / name
        with path.open('xb') as stream:
            stream.write(canonical(value) + b'\n')
        refs[key] = str(path)
    print(json.dumps(refs))
else:
    raise SystemExit('Expected observe or prepare')
