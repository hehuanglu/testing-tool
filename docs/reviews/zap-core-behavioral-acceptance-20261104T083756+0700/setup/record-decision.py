"""Append a caller-reported decision and its retained result references."""
import json
import sys
from pathlib import Path

base = Path(__file__).resolve().parents[1]
decision, action, selected, stop, *results = sys.argv[1:]
ledger = base / 'runbook-decisions.jsonl'
rows = ledger.read_text().splitlines() if ledger.exists() else []
current = json.loads((base / 'fixture/state/current.json').read_text())['generationId']
counter = (base / 'fixture/control/callback-count.jsonl').read_bytes().splitlines()
ref = None if decision == '-' else 'evidence/' + decision + '.stdout'
work = None if selected == '-' else selected
if ref and (base / ref).exists() and work is None:
    value = json.loads((base / ref).read_text())
    work = (value.get('nextAction') or {}).get('workId')
for item in [*results, *([ref] if ref else [])]:
    if not (base / item).is_file():
        raise ValueError('Missing evidence reference ' + item)
entry = dict(seq=len(rows) + 1, phase='A', generationBefore=(
    json.loads(rows[-1])['generationAfter'] if rows else None), decisionRef=ref, selectedWorkId=work,
    actualAction=action, resultRefs=results, generationAfter=current, effectCount=len(counter),
    stopReason=None if stop == '-' else stop, userIntervention=None)
with ledger.open('a') as stream:
    stream.write(json.dumps(entry, ensure_ascii=False) + '\n')
