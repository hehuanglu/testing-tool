"""Historical/current views only. Nothing here supplies evidence or closes work."""
import copy
from collections import Counter

from .business_discovery import records, references


DISPLAY_STATUSES = ('not-applicable', 'user-excluded', 'current-observed', 'current-partial',
    'historical-with-current-delta', 'historical-only', 'not-performed', 'unresolved')


def validate_coverage_history(history, sources, criterion_id):
    if not isinstance(history, dict) or type(history.get('version')) is not int or history['version'] != 1:
        raise ValueError('unsupported coverageHistory version')
    for row in records(history.get('records'), 'coverage history').values():
        references([row.get('sourceRef')], sources, 'coverage history source')
        if row.get('sourceCriterionId') != criterion_id:
            raise ValueError('coverage history criterion mismatch')
        if (row.get('meaning') != 'historical-only' or not isinstance(row.get('context'), dict) or
            any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in row['context'].items()) or
            not all(isinstance(row.get(k), str) and row[k].strip() for k in
                ('sourcePointer', 'coverage', 'securityAssessment', 'basis')) or
            not row['sourcePointer'].startswith('/')):
            raise ValueError('invalid historical-only record')
        source = sources[row['sourceRef']]
        identity = source.get('assessmentContext', {})
        if not isinstance(identity, dict) or not identity.get('assessmentId'):
            raise ValueError('coverage history source assessment identity required')
        if any(row['context'].get(k) != v for k, v in identity.items()):
            raise ValueError('coverage history source context mismatch')


def import_coverage_history(scope, report, source):
    """Explicit adapter: caller supplies one identified report and its metadata.

    Only criterion interpretation is copied, never raw operations/credentials.
    Unknown source context remains unknown; current scope context is not used.
    """
    from .security_scope import index
    if not isinstance(source, dict) or not source.get('location') or not source.get('id'):
        raise ValueError('identified historical source required')
    identity = report.get('assessmentContext') or {
        k: report.get(k) or 'unknown' for k in ('assessmentId', 'product', 'environment')}
    if not identity.get('assessmentId') or identity['assessmentId'] == 'unknown':
        raise ValueError('historical report assessment identity required')
    if source.get('assessmentContext') != identity:
        raise ValueError('historical report source identity mismatch')
    result = copy.deepcopy(scope)
    sources = index(result.get('sources', []), 'source')
    if source['id'] in sources and sources[source['id']] != source:
        raise ValueError('historical source binding changed')
    if source['id'] not in sources:
        result.setdefault('sources', []).append(copy.deepcopy(source))
    prior = index(report.get('criteria', []), 'historical criterion')
    for criterion in result.get('criteria', []):
        old = prior.get(criterion['id'])
        if old is None:
            continue
        row = dict(id=source['id'] + ':' + criterion['id'], sourceRef=source['id'],
            sourceCriterionId=old['id'], sourcePointer='/criteria/' + str(report['criteria'].index(old)),
            coverage=old.get('coverage', 'unknown'), securityAssessment=old.get('securityAssessment', 'unknown'),
            context=copy.deepcopy(identity), meaning='historical-only',
            basis='Copied from the identified prior report; not a current retest')
        for key in ('applicability', 'interpretation'):
            if key in old:
                row[key] = copy.deepcopy(old[key])
        history = criterion.setdefault('coverageHistory', dict(version=1, records=[]))
        existing = records(history['records'], 'coverage history')
        if row['id'] in existing and existing[row['id']] != row:
            raise ValueError('historical record binding changed')
        if row['id'] not in existing:
            history['records'].append(row)
        validate_coverage_history(history, index(result['sources'], 'source'), criterion['id'])
    return result


def coverage_view(criterion):
    history = copy.deepcopy(criterion.get('coverageHistory', {}).get('records', []))
    diagnostics = []
    if not history and criterion.get('priorAssessment'):
        old = criterion['priorAssessment']
        history = [dict(id='legacy-embedded:' + criterion['id'], binding='legacy-embedded',
            coverage=old.get('coverage', 'unknown'), securityAssessment=old.get('securityAssessment', 'unknown'),
            context={'assessmentId': 'unknown'}, meaning='historical-only')]
        diagnostics.append('legacy-embedded-history-without-source-binding')
    questions = criterion.get('questions', [])
    observed = [q['id'] for q in questions if q.get('coverage') == 'observed']
    open_ids = [q['id'] for q in questions if q.get('coverage') not in ('observed', 'user-excluded')]
    partial = any(q.get('questionEvidence', {}).get('supportedUnits') if 'questionEvidence' in q else
        q.get('observation', {}).get('observationUnits') for q in questions)
    current = criterion.get('coverage', 'not-performed')
    if criterion.get('disposition') == 'user-excluded':
        status = 'user-excluded'; meaning = 'Excluded by the recorded user scope basis'
    elif criterion.get('applicability', {}).get('status') == 'not-applicable':
        status = 'not-applicable'; meaning = 'Reviewed as inapplicable in the assigned product scope'
    elif current == 'observed':
        status = 'current-observed'; meaning = 'Current mapped questions answered; security outcome is separate'
    elif history and (observed or partial):
        status = 'historical-with-current-delta'; meaning = 'Historical coverage retained; current observations leave assigned obligations open'
    elif history:
        status = 'historical-only'
        labels = sorted({h['coverage'] for h in history})
        meaning = 'Historical ' + '/'.join(labels) + ('; current mapped questions not performed' if
            all(q.get('coverage') == 'not-performed' for q in questions) else '; current required observations not established')
    elif observed or partial or current == 'partial':
        status = 'current-partial'; meaning = 'Current attempts leave required observations open'
    elif not questions or current == 'blocked' or criterion.get('applicability', {}).get('status') == 'unknown' or any(q.get('unresolved') for q in questions):
        status = 'unresolved'; meaning = 'Current applicability or question mapping requires review'
    else:
        status = 'not-performed'; meaning = 'Current mapped questions not performed'
    contexts = {str(sorted(h.get('context', {}).items())) for h in history}
    return dict(version=1, historical=dict(records=history, credit='historical-only',
            status='mixed-history' if len(contexts) > 1 else 'retained' if history else 'none'),
        current=dict(status=current, questionIds=[q['id'] for q in questions],
            observedQuestionIds=observed, openQuestionIds=open_ids),
        applicability=copy.deepcopy(criterion.get('applicability', {'status': 'unknown'})),
        displayStatus=status, displayMeaning=meaning, diagnostics=diagnostics)


def presentation_summary(criteria):
    counts = Counter(c['coverageView']['displayStatus'] for c in criteria)
    return dict(version=1, denominator='criteria', criteria=len(criteria),
        counts={key: counts[key] for key in DISPLAY_STATUSES})


def work_units(questions, reconciliation):
    """Identity for display counts; question sufficiency is checked independently."""
    inventory = reconciliation.get('inventory') or {}
    cases = {c['caseId']: c for c in inventory.get('cases', [])}
    states = {c['caseId']: c for c in reconciliation.get('cases', [])}
    units = {}
    for cid, case in cases.items():
        if case.get('disposition') in ('not-applicable', 'user-excluded'):
            continue
        units['case:' + cid] = dict(id='case:' + cid, questionIds=[], caseIds=[cid],
            coverage=states.get(cid, {}).get('status', 'not-performed'), countedAs='case',
            basis='Responsibility case identity; linked questions retain independent evidence requirements')
    for question in questions:
        linked = question.get('responsibilityIds', [])
        covered = set()
        for cid in linked:
            if cid not in cases:
                raise ValueError('unresolved work unit case')
            covered.update(cases[cid].get('requiredEvidence', []))
            key = 'case:' + cid
            if key not in units:
                units[key] = dict(id=key, questionIds=[], caseIds=[cid], coverage=states.get(cid, {}).get('status', 'not-performed'),
                    countedAs='case', basis='Linked responsibility; question sufficiency remains independent')
            units[key]['questionIds'].append(question['id'])
        extra = set(question.get('requiredObservations', [])) - covered
        if not linked or extra:
            key = 'question:' + question['id']
            if not linked and question.get('underlyingDutyId'):
                key = 'duty:' + question['underlyingDutyId']
                prior = next((q for q in questions if q['id'] in units.get(key, {}).get('questionIds', [])), None)
                if prior and any(prior.get(k) != question.get(k) for k in ('coverageContext','requiredObservations','methodClass')):
                    key = 'question:' + question['id']
            if key in units:
                units[key]['questionIds'].append(question['id'])
                if question['coverage'] != 'observed':units[key]['coverage']='partial'
            else:
                units[key] = dict(id=key, questionIds=[question['id']], caseIds=[], coverage=question['coverage'],
                    countedAs='question', basis='Additional observation requirements beyond linked cases: ' + ', '.join(sorted(extra))
                        if linked else 'Shared declared underlying duty with equal context/requirements' if question.get('underlyingDutyId') else 'Question has no linked responsibility case')
    for unit in units.values():
        if unit['countedAs'] == 'case':
            unit['caseCoverage'] = unit['coverage']
            linked = [q for q in questions if q['id'] in unit['questionIds']]
            unit['questionCoverage'] = {q['id']: q['coverage'] for q in linked}
            unit['openQuestionIds'] = [q['id'] for q in linked if q['coverage'] not in ('observed', 'user-excluded')]
            if unit['coverage'] == 'observed' and unit['openQuestionIds']:
                unit['coverage'] = 'partial'
    return list(units.values())


def round_outcome(assessment_round, task_completion):
    """Lifecycle headline; coverage and the security verdict keep their own meaning."""
    from .round_closure import CLOSED
    status = (assessment_round or {}).get('status', 'undefined')
    labels = {'undefined':'Lifecycle not established for this legacy report', 'in-progress':'Assessment round in progress',
        'checkpointed':'Assessment round checkpointed for continuation', 'completed':'Assessment round completed',
        'completed-with-limitations':'Assessment round completed with limitations', 'stopped-by-user':'Assessment round stopped by user'}
    return dict(status=status, roundClosed=status in CLOSED, headline=labels[status],
        assignedObligationCoverage=task_completion,
        reopenConditions=copy.deepcopy((assessment_round or {}).get('closure', {}).get('review', {}).get('reopenConditions', [])))
