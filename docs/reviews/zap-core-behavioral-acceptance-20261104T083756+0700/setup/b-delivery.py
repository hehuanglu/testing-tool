"""One local synthetic table write or one verified receipt preparation."""
import json
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

from zap_assessment.assessment_store import load_current, read_json
from zap_assessment.contracts import canonical
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.operation_selection import delivery_digest

base = Path(__file__).resolve().parents[1]
ev = base / 'evidence'
manifest = read_json(base / 'manifest.json')
snapshot = load_current(manifest['stateDir'])
decision = read_json(ev / 'b-delivery-next.stdout')
source = read_json(ev / 'b-reviewed-source.stdout')
table_path = ev / 'b-synthetic-table.json'
readback_path = ev / 'b-delivery-readback.stdout'
assert snapshot.generation_id == decision['generationId']
assert decision['nextAction']['kind'] == 'verify-final-delivery'
assert source == review_workflow(snapshot.run) and source['eligibleForCompletion']
source_digest = delivery_digest(snapshot.run, source)
assert source_digest == decision['nextAction']['sourceDigest']
table = dict(synthetic=True, fileId='synthetic-file-' + manifest['episodeId'],
             worksheetId='synthetic-worksheet-results', sourceDigest=source_digest,
             rows=source['criterionResults'])

if sys.argv[1] == 'write':
    with table_path.open('xb') as stream:
        stream.write(canonical(table) + b'\n')
    print(json.dumps(dict(tableRef=str(table_path), rowsWritten=len(table['rows']),
                          sourceDigest=source_digest, tableSha256=sha256(table_path.read_bytes()).hexdigest())))
elif sys.argv[1] == 'receipt':
    readback = read_json(readback_path)
    assert readback['verified'] is True and readback['generationId'] == snapshot.generation_id
    assert readback['tableRef'] == str(table_path) and readback['table'] == table == read_json(table_path)
    assert readback['tableSha256'] == sha256(table_path.read_bytes()).hexdigest()
    snapshot.operator['delivery'] = dict(
        {key: table[key] for key in ('fileId', 'worksheetId', 'sourceDigest')}, status='verified',
        verifiedAt=datetime.now(timezone.utc).isoformat(), readbackRefs=[str(readback_path)])
    operator_path = base / 'setup/b-delivery-operator.json'
    with operator_path.open('xb') as stream:
        stream.write(canonical(snapshot.operator) + b'\n')
    print(json.dumps(dict(generationId=snapshot.generation_id, runRef=str(snapshot.run_path),
                          operatorRef=str(operator_path), delivery=snapshot.operator['delivery'])))
else:
    raise SystemExit('Expected write or receipt')
