"""Select one bounded continuation task from a private v2 RUN."""
from datetime import datetime, timezone

from .assessment_store import coordinator_for
from .criteria_delegation import effective_resources
from .criteria_workflow import review_workflow
from .operation_selection import select_next
from .operator_state import default_operator


def resume_next(run, evidence_index=()):
    coordinator = coordinator_for(run)
    inspection = coordinator.inspect_recovery() if coordinator else {}
    review = review_workflow(run) if inspection.get('effectsAllowed', True) else {}
    operator = default_operator(run)
    pending = {row['actionId'] for row in inspection.get('knownPendingEffects', [])}
    plan = run['criteriaWorkflow']['plan']
    for case in plan['cases']:
        for action in case.get('actions', []):
            original = action.get('readbackOf')
            if original not in pending:
                continue
            operator['workItems'].append(dict(
                id=action['id'], blockId='default', caseIds=[case['id']], kind='readback',
                mode='runtime', phase='execution', order=0, state='ready', basisRefs=[original],
                nextStep='Use the retained original packet and verify executor admission',
                resourceIds=effective_resources(plan, [case]), dependsOnWorkIds=[],
                actionRef=dict(caseId=case['id'], actionId=action['id']), readbackOf=original))
    return select_next(run, operator, review, inspection,
                       evidence_index=evidence_index, now=datetime.now(timezone.utc))
