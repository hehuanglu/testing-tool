"""Cross-check final retained facts and produce the auditor's decision index."""
import json
from hashlib import sha256
from pathlib import Path

from zap_assessment.assessment_store import load_current, read_json

base = Path(__file__).resolve().parents[1]
ev = base / 'evidence'
prior = read_json(ev / 'b-manifest-at-a4.json')
snapshot = load_current(prior['stateDir'])

def raw(name):
    return read_json(ev / (name + '.stdout'))

cold, final = raw('b-cold-inspect'), raw('b-final-inspect')
cold_recovery, recovery = raw('b-cold-recovery'), raw('b-final-recovery')
selector, review = raw('b-final-next'), raw('b-final-review')
readback = raw('b-delivery-readback')
assert raw('b-resolve')['storePath'] == prior['stateDir']
assert cold['assessmentId'] == final['assessmentId'] == prior['assessmentId']
assert cold['generationId'] == prior['checkpointGenerationId']
assert final['generationId'] == selector['generationId'] == snapshot.generation_id
assert cold['integrity'] == final['currentIntegrity'] == final['historyIntegrity'] == recovery['integrity'] == 'clean'
assert recovery['pendingCertainty'] == 'complete'
assert not recovery['pendingEffects'] and not recovery['leases'] and not recovery['openTransactions']
assert not selector['readyWorkIds'] and not selector['deferred'] and not selector['pendingActionIds']
assert selector['nextAction']['kind'] == 'workflow-done' and selector['canConcludeTurn']
assert review['eligibleForCompletion'] and review['assessmentStatus'] == 'completed'
assert not any(review[k] for k in ('pendingEffects', 'nextWork', 'diagnostics'))
assert all(x['state'] == 'done' for x in snapshot.operator['workItems'])
assert len(review['caseResults']) == 6
assert {r['caseId']: r['outcome'] for r in review['caseResults']} == {
    'T-EFFECT': 'matched', 'T-AFTER': 'matched', 'T-SOURCE': 'violated',
    'T-CONTROL': 'matched', 'T-TTL': 'matched', 'T-FINAL': 'matched'}
delivery = snapshot.operator['delivery']
assert readback['verified'] and delivery['status'] == 'verified'
assert delivery['sourceDigest'] == selector['nextAction']['sourceDigest'] == readback['table']['sourceDigest']
assert Path(delivery['readbackRefs'][0]) == ev / 'b-delivery-readback.stdout'
counter = raw('b-final-count')
assert counter['entries'] == raw('b-cold-count')['entries'] == [{'sequence': 1, 'actionId': 'effect-once'}]
journal = Path(recovery['journalPath'])
events = [json.loads(line) for line in journal.read_bytes().splitlines()]
a4 = read_json(Path(prior['checkpointRef']))
assert [r['hash'] for r in a4['journalEvents']] == [r['hash'] for r in events[:4]]
assert cold_recovery['lastValidHash'] == events[3]['hash']
assert [r['data']['actionId'] for r in events if r['kind'] == 'intent'] == ['effect-once', 'read-ttl']
assert [r['data']['actionId'] for r in events if r['kind'] == 'reconciled'] == ['effect-once', 'read-ttl']
assert sha256(Path(a4['receiptRef']).read_bytes()).hexdigest() == a4['receiptSha256']
ledger = (base / 'runbook-decisions.jsonl').read_bytes()
prefix = (ev / 'b-ledger-at-a4.jsonl').read_bytes()
assert ledger.startswith(prefix)
decisions = [json.loads(row) for row in ledger[len(prefix):].splitlines()]
assert [r['seq'] for r in decisions] == list(range(22, 37))
assert all(r['phase'] == 'B' and r['effectCount'] == 1 and not r['stopReason'] for r in decisions)
assert [r['userIntervention'] for r in decisions if r['userIntervention']] == ['planned-user-B-resume']
assert all((base / ref).is_file() for row in decisions for ref in [row['decisionRef'], *row['resultRefs']])
bug = raw('b-repro-closure-selector')
assert bug['reproduced'] and bug['observed']['canConcludeTurn']
print(json.dumps(dict(status='candidate-for-auditor-review', assessmentStatus='completed',
    assessmentId=prior['assessmentId'], checkpointGenerationId=cold['generationId'],
    finalGenerationId=final['generationId'], committedGenerationCount=final['committedGenerationCount'],
    currentIntegrity=final['currentIntegrity'], historyIntegrity=final['historyIntegrity'],
    coordinatorIntegrity=recovery['integrity'], finalSelector=selector['nextAction']['kind'],
    canConcludeTurn=selector['canConcludeTurn'], criterionCounts=review['criterionCounts'],
    caseOutcomes={r['caseId']: r['outcome'] for r in review['caseResults']},
    workItemsClosedInB=['effect-dispatch', 'effect-reader', 'dependent-review', 'ttl-review', 'final-resource-review'],
    workItemsExecutedInB=['effect-reader', 'dependent-review', 'ttl-review', 'final-resource-review'],
    totalWorkItemsDone=len(snapshot.operator['workItems']),
    effectCount=counter['count'], pendingActionIds=selector['pendingActionIds'],
    activeLeases=recovery['leases'], openTransactions=recovery['openTransactions'],
    resources={r['id']: r['status'] for r in snapshot.run['criteriaWorkflow']['resourceReview']['resources']},
    delivery=delivery, phaseBDecisionRange=[decisions[0]['seq'], decisions[-1]['seq']],
    phaseBUserInterventions=dict(plannedResume=1, unplannedContinuation=0, corrections=0,
                                 missingFacts=0, hostStops=0),
    historicalLedgerPrefixSha256=sha256(prefix).hexdigest(),
    coreFinding=dict(id='B-CORE-01', status='reproduced', ref='evidence/b-repro-closure-selector.stdout'),
    evidenceRefs=dict(identity='evidence/b-resolve.stdout', chats='evidence/b-app-chats.json',
        cold='evidence/b-cold-next.stdout', reviewer='evidence/b-final-review.stdout',
        selector='evidence/b-final-next.stdout', integrity='evidence/b-final-inspect.stdout',
        recovery='evidence/b-final-recovery.stdout', resource='evidence/b-resource-observation.stdout',
        counter='evidence/b-final-count.stdout', readback='evidence/b-delivery-readback.stdout',
        decisions='runbook-decisions.jsonl')), indent=2))
