"""Append one reviewed Phase B action after recording its raw evidence."""
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

base = Path(__file__).resolve().parents[1]
decision, selected, action, intervention, *result_refs = sys.argv[1:]
ledger = base / "runbook-decisions.jsonl"
prior = json.loads(ledger.read_text().splitlines()[-1])
decision_ref = "evidence/" + decision + ".stdout"
snapshot = json.loads((base / decision_ref).read_text())
for ref in [decision_ref, *result_refs]:
    assert (base / ref).is_file(), ref
state = Path(json.loads((base / "manifest.json").read_text())["stateDir"])
current = json.loads((state / "current.json").read_text())["generationId"]
record = dict(seq=prior["seq"] + 1, phase="B",
    at=datetime.now(ZoneInfo("Asia/Ho_Chi_Minh")).isoformat(),
    generationBefore=prior["generationAfter"], decisionGeneration=snapshot["generationId"],
    decisionRef=decision_ref, selectedWorkId=None if selected == "-" else selected,
    actualAction=action, resultRefs=result_refs, generationAfter=current,
    effectCount=len((base / "fixture/control/callback-count.jsonl").read_bytes().splitlines()),
    stopReason=None, userIntervention=None if intervention == "-" else intervention)
with ledger.open("a") as stream:
    stream.write(json.dumps(record, ensure_ascii=False) + "\n")
print(json.dumps(record, ensure_ascii=False))
