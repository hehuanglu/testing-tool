"""Assert the corrected decision on the historical probe's inputs, read only."""
import json
import sys
from pathlib import Path

from zap_assessment.operation_selection import select_next
from zap_assessment.operator_state import timestamp


def read(path):
    return json.loads(Path(path).read_bytes())


command = read(sys.argv[1])
_, _, _, inspect_ref, recovery_ref, review_ref, observed_ref, injected_time = command['argv']
inspect, recovery, review, observed = map(read, (inspect_ref, recovery_ref, review_ref, observed_ref))
run, operator = map(read, (inspect['runRef'], inspect['operatorRef']))
assert observed['generationId'] == inspect['generationId']
assert observed['nextAction']['kind'] == 'review-dependencies' and observed['canConcludeTurn']
assert [row['caseId'] for row in review['nextWork']] == ['T-FINAL']
assert not recovery['pendingEffects'] and not recovery['leases']
decision = select_next(run, operator, review, recovery, now=timestamp(injected_time), managed=True)
action = decision['nextAction']
assert decision['mode'] == 'normal' and decision['readyWorkIds'] == ['final-resource-review']
assert (action['kind'], action['workId'], action['caseId']) == ('resource-review', 'final-resource-review', 'T-FINAL')
assert not decision['canConcludeTurn'] and decision['pendingActionIds'] == []
assert decision['conclusionReason'] is None
print(json.dumps(dict(generationId=inspect['generationId'], injectedTime=injected_time,
    dispatches=0, inputs=dict(run=inspect['runRef'], operator=inspect['operatorRef'], recovery=recovery_ref,
                              review=review_ref, historicalDecision=observed_ref), decision=decision), indent=2))
