"""Replay the B pre-closure decision from retained RUN, OPERATOR and inspection."""
import json
import sys

from zap_assessment.assessment_store import read_json
from zap_assessment.operation_selection import select_next
from zap_assessment.operator_state import timestamp

inspect, recovery, review, observed, now = sys.argv[1:]
snapshot = read_json(inspect)
run = read_json(snapshot['runRef'])
operator = read_json(snapshot['operatorRef'])
decision = select_next(run, operator, read_json(review), read_json(recovery),
                       now=timestamp(now), managed=True)
actual = read_json(observed)
for key in ('readyWorkIds', 'pendingActionIds', 'deferred', 'nextAction',
            'nextWakeAt', 'canConcludeTurn', 'conclusionReason'):
    assert decision[key] == actual[key], key
assert decision['readyWorkIds'] == ['final-resource-review']
assert not decision['deferred'] and not decision['pendingActionIds'] and decision['nextWakeAt'] is None
assert decision['canConcludeTurn'] and decision['nextAction']['kind'] == 'review-dependencies'
print(json.dumps(dict(generationId=snapshot['generationId'], reproduced=True,
    expected=dict(workId='final-resource-review', canConcludeTurn=False),
    observed={k: decision[k] for k in ('readyWorkIds', 'nextAction', 'canConcludeTurn', 'conclusionReason')})))
