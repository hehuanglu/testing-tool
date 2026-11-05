"""Check checkpoint metadata and journal without parsing the retained effect receipt."""
import hashlib
import json
from pathlib import Path

from zap_assessment.assessment_store import load_current
from zap_assessment.criteria_delegation import Coordinator

base = Path(__file__).resolve().parents[1]
fixture = base / 'fixture'
snap = load_current(fixture / 'state')
read = lambda label: json.loads((base / 'evidence' / (label + '.stdout')).read_bytes())
decision = read('a4-next')
review = read('a4-review')
inspection = read('a4-inspect-recovery')
dispatch = read('a4-dispatch')
packet_ref = fixture / 'packets/effect-task.json'
receipt_ref = Path(dispatch['receiptRef'])
assert receipt_ref == fixture / 'receipts/effect-once.json' and receipt_ref.is_file()
work = {row['id']: row for row in snap.operator['workItems']}
assert work['effect-dispatch']['state'] == 'in_progress'
assert work['effect-dispatch']['executionBinding']['packetRef'] == str(packet_ref)
assert work['effect-reader']['executionBinding'] == work['effect-dispatch']['executionBinding']
assert work['source-review']['state'] == work['control-review']['state'] == 'done'
assert snap.operator['stopRecord'] is None and not snap.run['criteriaWorkflow'].get('userRequest')
assert snap.operator['delivery'] is None and not snap.run['criteriaWorkflow'].get('resolutions')
assert {row['caseId'] for row in snap.run['criteriaWorkflow']['caseResults']} == {'T-SOURCE', 'T-CONTROL'}
assert {row['caseId'] for row in snap.run['operations']} == {'T-SOURCE', 'T-CONTROL'}
assert read('a4-counter-before')['count'] == 0
assert read('a4-counter-after')['entries'] == [dict(sequence=1, actionId='effect-once')]
assert decision['pendingActionIds'] == ['effect-once']
assert decision['nextAction']['workId'] == 'effect-reader' and not decision['canConcludeTurn']
assert {row['workId']: row['reasonCode'] for row in decision['deferred']} == {
    'effect-dispatch': 'consumed-action', 'dependent-review': 'case-dependency', 'ttl-review': 'not-before'}
assert review['assessmentStatus'] == 'executing' and not review['eligibleForCompletion']
assert {row['caseId']: row['outcome'] for row in review['caseResults']} == {
    'T-EFFECT': None, 'T-AFTER': None, 'T-SOURCE': 'violated', 'T-CONTROL': 'matched', 'T-TTL': None, 'T-FINAL': None}
state = snap.run['coordinatorState']
events = Coordinator(state['directory'], state['assessmentId'])._journal().events
assert [row['kind'] for row in events] == ['lease_acquire_intent', 'leased', 'intent', 'acknowledged']
assert [row['data'].get('actionId') for row in events[-2:]] == ['effect-once', 'effect-once']
assert set(inspection['leases']) == {'synthetic-scanner', 'synthetic-session'}
assert {row['taskId'] for row in inspection['leases'].values()} == {'effect-task'}
repair, = snap.operator['repairs']
assert repair['status'] == 'verified' and repair['verificationLevel'] == 'offline-checked'
assert sum(row['kind'] == 'reopened-after-verification' for row in repair['history']) == 1
print(json.dumps(dict(generationId=snap.generation_id, count=1, packetRef=str(packet_ref),
    packetDigest=work['effect-dispatch']['executionBinding']['packetDigest'], receiptRef=str(receipt_ref),
    receiptSha256=hashlib.sha256(receipt_ref.read_bytes()).hexdigest(),
    journalPath=inspection['journalPath'], journalEvents=[dict(seq=row['seq'], kind=row['kind'],
        actionId=row['data'].get('actionId'), hash=row['hash']) for row in events],
    pendingActionIds=decision['pendingActionIds'], retainedResources=sorted(inspection['leases']),
    nextAction=decision['nextAction'], criterionCounts=review['criterionCounts'],
    caseOutcomes={row['caseId']: row['outcome'] for row in review['caseResults']},
    assessmentStatus=review['assessmentStatus'], repairRevision=repair['revision'],
    projections=read('a4-render')), indent=2))
