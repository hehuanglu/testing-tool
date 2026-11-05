"""Independent offline verification. All state is temporary; no product traffic."""
import copy
import tempfile
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / '.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
sys.path[:0] = [str(LIB/'src'), str(LIB/'tests')]
from test_criteria_workflow import working
from zap_assessment import assessment_store as store
from zap_assessment.operator_state import default_operator
from zap_assessment.criteria_workflow import review_workflow
from zap_assessment.contracts import canonical

with tempfile.TemporaryDirectory() as td:
    root = Path(td).resolve()
    run = working()
    run['actionHistory'] = [dict(actionId='mutation-1', state='intent', effect='mutation', caseId='T1')]
    operator = default_operator(run)
    source = root/'source.json'
    source.write_bytes(canonical(run))
    first = store.register_store(root/'registry', root/'state', source, operator, registration_id='init')
    before = review_workflow(store.load_current(root/'state').run)
    changed = copy.deepcopy(run)
    changed['actionHistory'].append(dict(actionId='mutation-1', state='acknowledged', effect='mutation', caseId='T1'))
    store.commit_snapshot(root/'state', expected_generation=first['generationId'], commit_id='ack', run=changed, operator_state=operator)
    after = review_workflow(store.load_current(root/'state').run)
    assert len(before['pendingEffects']) == 1 and not before['eligibleForCompletion']
    assert not after['pendingEffects'] and after['eligibleForCompletion']
    print('S1 CONFIRMED: ACK-only appended history cleared pending mutation; eligibleForCompletion False -> True')
    assert changed['operations'] == run['operations']
    assert not changed['criteriaWorkflow'].get('resolutions')
    print('S1 CONTROL: no added operation, terminal readback or resolution; retained original intent unchanged')

with tempfile.TemporaryDirectory() as td:
    root = Path(td).resolve()
    run = working()
    operator = default_operator(run)
    source = root/'source.json'
    source.write_bytes(canonical(run))
    first = store.register_store(root/'registry', root/'state', source, operator, registration_id='init')
    second = store.commit_snapshot(root/'state', expected_generation=first['generationId'], commit_id='next', run=run, operator_state=operator)
    (root/'state'/'generations'/first['generationId']/'RUN.json').write_bytes(b'{}')
    print('S2 state-inspect after parent corruption:', store.inspect_store(root/'state')['integrity'])
    try:
        store.commit_snapshot(root/'state', expected_generation=second['generationId'], commit_id='third', run=run, operator_state=operator)
    except store.StateError as error:
        print('S2 next commit rejects same store:', error.code)
    else:
        raise AssertionError('expected ancestry validation failure')
