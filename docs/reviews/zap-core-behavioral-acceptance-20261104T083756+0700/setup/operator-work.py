"""Prepare one work-state transition as an input for the managed CAS command."""
import json
import sys
from pathlib import Path
from zap_assessment.assessment_store import load_current
from zap_assessment.contracts import canonical

base = Path(__file__).resolve().parents[1]
wid, state, name, *refs = sys.argv[1:]
snap = load_current(base / 'fixture/state')
item = next(work for work in snap.operator['workItems'] if work['id'] == wid)
item.update(state=state, waiting=None)
if state == 'done':
    item['completionRefs'] = refs
path = base / 'setup' / (name + '-operator.json')
with path.open('xb') as stream:
    stream.write(canonical(snap.operator))
print(json.dumps(dict(runRef=str(snap.run_path), operatorRef=str(path), generationId=snap.generation_id)))
