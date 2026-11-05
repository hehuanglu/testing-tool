"""Independent fixture probes. No product/network effects or source changes."""
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LIB = ROOT / '.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
sys.path[:0] = [str(LIB / 'src'), str(LIB / 'tests')]
os.environ['PYTHONPATH'] = os.pathsep.join([str(LIB / 'src'), str(LIB / 'tests')])

from test_criteria_workflow import working, approve
from test_operation_selection import work, schedule_fixture
from test_operator_state import repair_proposal, advance, VERIFIED
from zap_assessment.criteria_delegation import Coordinator, make_packet
from zap_assessment.operator_state import default_operator, validate_operator, change_repair
from zap_assessment.assessment_store import register_store
from test_assessment_state_cli import call


def owned_lease_probe():
    with tempfile.TemporaryDirectory(prefix='zap-own-lease-audit-') as directory:
        base = Path(directory).resolve()
        run = working(None)
        case = run['criteriaWorkflow']['plan']['cases'][0]
        case['resourceIds'] = ['scanner']
        case['actions'] = [dict(id='effect', caseId='T1', effect='read')]
        approve(run)
        coordinator = Coordinator(base / 'coordinator', run['assessmentId'])
        run['coordinatorState'] = dict(directory=str(coordinator.root), assessmentId=run['assessmentId'])
        operator = default_operator(run)
        operator['workItems'] = [work('fresh', action='effect')]
        validate_operator(run, operator)
        source = base / 'RUN.json'
        source.write_text(json.dumps(run))
        register_store(base / 'registry', base / 'state', source, operator, registration_id='fixture-genesis')
        packet = make_packet(run, 'owned-task', ['T1'], 'coordinator')
        coordinator.acquire(run, packet)
        process = call('state-next', '--state-dir', base / 'state')
        assert process.returncode == 0, process.stdout + process.stderr
        decision = json.loads(process.stdout)
        calls = []
        coordinator.dispatch(run, packet, case['actions'][0], lambda action: calls.append(action['id']))
        return dict(probe='V01', expected='Continue or resolve the exact own task; do not conclude a resource dependency',
                    actual={key: decision[key] for key in ('nextAction', 'deferred', 'canConcludeTurn')},
                    same_packet_fake_callback_calls=calls)


def recurrence_probe():
    run, operator = schedule_fixture()
    operator['workItems'] = [work('reader', action='reader', original='effect')]
    operator = change_repair(operator, repair_proposal(), opening=True)
    for status in ('reproducing', 'implementing', 'verifying'):
        operator = advance(operator, status)
    operator = advance(operator, 'verified', **VERIFIED)
    operator = change_repair(operator, repair_proposal(id='recurred'), opening=True)
    validate_operator(run, operator)
    repair = operator['repairs'][0]
    return dict(probe='V02', expected='A newly reported recurrence needs review; retain prior verification as history',
                actual=dict(status=repair['status'], lastEvent=repair['history'][-1]))


if __name__ == '__main__':
    print(json.dumps([owned_lease_probe(), recurrence_probe()], ensure_ascii=False, indent=2))
