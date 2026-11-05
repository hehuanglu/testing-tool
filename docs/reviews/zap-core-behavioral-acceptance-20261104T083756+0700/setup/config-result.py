"""Build one result from the retained config observation and predeclared oracle."""
import hashlib
import json
import sys
from pathlib import Path
from zap_assessment import assessment_store as store
from zap_assessment.contracts import canonical

base = Path(__file__).resolve().parents[1]
stem, cid = sys.argv[1:]
evidence = base / 'evidence' / (stem + '-observation.stdout')
observed = store.read_json(evidence)
packet = store.read_json(base / 'fixture/packets' / (stem + '.json'))
case, = packet['cases']
assert case['id'] == observed['caseId'] == cid
raw = Path(observed['sourceRef']).read_bytes()
assert hashlib.sha256(raw).hexdigest() == observed['sourceSha256']
assert json.loads(raw)['crossAccountAccess'] == observed['crossAccountAccess']
oracle = store.read_json(base / 'setup/expected-results.json')['expected'][cid]['expectedCrossAccountAccess']
outcome = 'matched' if observed['crossAccountAccess'] == oracle else 'violated'
context = case['coverageContext']
assert context == observed['coverageContext']
oid = 'observation-' + cid.lower()
operation = dict(id=oid, caseId=cid, status='completed', effect='read', coverageContext=context,
                 provenance=dict(transport='synthetic-offline-config'), readback=observed)
basis = 'Fixture config cross-account access is ' + observed['crossAccountAccess'] + ' against expected ' + oracle
result = dict(caseId=cid, outcome=outcome, basis=basis, evidenceLinks=[
    dict(operationId=oid, observationUnits=case['requiredEvidence'], resultPath='/readback/crossAccountAccess',
         resultRead=True, basis=basis, context=context, role='support')])
worker = {key: packet[key] for key in ('taskId', 'packetDigest', 'criteriaRevision', 'planRevision')}
worker.update(operations=[operation], caseResults=[result])
(base / 'setup' / (stem + '-result.json')).write_bytes(canonical(worker))
print(json.dumps(dict(caseId=cid, outcome=outcome, operationId=oid, basis=basis)))
