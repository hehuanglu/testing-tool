"""Independently read persisted delivery bytes against the immutable reviewed source."""
import json
import sys
from hashlib import sha256
from pathlib import Path

from zap_assessment.assessment_store import read_json
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.operation_selection import delivery_digest

inspect, source_path, table_path = map(Path, sys.argv[1:])
snapshot = read_json(inspect)
run = read_json(Path(snapshot['runRef']))
source = read_json(source_path)
assert source == review_workflow(run) and source['eligibleForCompletion']
raw = table_path.read_bytes()
table = json.loads(raw)
assert table['synthetic'] is True and all(table[key].startswith('synthetic-')
                                        for key in ('fileId', 'worksheetId'))
assert table['sourceDigest'] == delivery_digest(run, source)
ids = [row['criterionId'] for row in table['rows']]
assert ids == [c['id'] for c in run['criteriaWorkflow']['criteria']]
assert len(ids) == len(set(ids)) == 6
assert table['rows'] == source['criterionResults']
assert [row['criterionId'] for row in table['rows'] if row['verdict'] == 'unmet'] == ['C-SOURCE']
print(json.dumps(dict(verified=True, idsOrderContentMatched=True, generationId=snapshot['generationId'],
                      sourceReviewRef=str(source_path), tableRef=str(table_path),
                      tableSha256=sha256(raw).hexdigest(), criterionIds=ids, table=table)))
