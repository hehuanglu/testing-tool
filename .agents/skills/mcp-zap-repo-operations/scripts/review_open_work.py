#!/usr/bin/env python3
"""Optional read-only responsibility/checkpoint review. Never dispatches or grants authority.

The caller maps existing inventory/observations; text grounds remain for human review.
No executor/report schema, network client, file writer or automatic replay is involved.
"""
import argparse
import json


def nonblank(value):
    return isinstance(value, str) and bool(value.strip())


def string_list(value):
    return isinstance(value, list) and all(nonblank(x) for x in value)


def review_work(document):
    responsibilities = document['responsibilities']
    observations = document.get('observations', {})
    decisions = document.get('decisions', {})
    if not isinstance(responsibilities, list) or not isinstance(observations, dict) or not isinstance(decisions, dict):
        raise ValueError('invalid review collections')
    ids = [r['id'] for r in responsibilities]
    if not all(nonblank(i) for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('missing or duplicate responsibility ID')
    unresolved, actions, grounded, completed = [], [], [], []
    if not ids:
        unresolved.append({'id': None, 'reason': 'responsibility-inventory-empty'})
    if set(observations) - set(ids) or set(decisions) - set(ids):
        unresolved.append({'id': None, 'reason': 'record-outside-responsibility-inventory'})
    for row in responsibilities:
        rid = row['id']
        required = row.get('requiredObservations')
        if not string_list(required) or not required:
            unresolved.append({'id': rid, 'reason': 'observation-requirements-not-defined'})
            continue
        seen = observations.get(rid, [])
        if isinstance(seen, list):
            seen = {'completed': seen}
        if not isinstance(seen, dict) or not string_list(seen.get('completed', [])):
            raise ValueError('invalid observation mapping')
        unknown = seen.get('outcomeUnknown', False)
        if not isinstance(unknown, bool):
            raise ValueError('outcomeUnknown must be boolean')
        missing = sorted(set(required) - set(seen.get('completed', [])))
        # An ACK or matched body cannot resolve a still unknown mutation outcome.
        if not missing and not unknown:
            completed.append(rid)
            continue
        decision = decisions.get(rid, {})
        if not isinstance(decision, dict):
            raise ValueError('invalid decision mapping')
        action = decision.get('action')
        reason = None
        if not nonblank(decision.get('basis')):
            reason = 'decision-basis-missing'
        elif unknown and action not in ('reconcile', 'dependency'):
            reason = 'unknown-outcome-requires-reconciliation'
        elif action in ('execute', 'repair', 'prepare-fixture', 'reconcile'):
            if not nonblank(decision.get('nextStep')):
                reason = 'next-step-missing'
            else:
                actions.append({'id': rid, 'action': action, 'missingObservations': missing})
        elif action == 'dependency':
            options = decision.get('optionsEvaluated')
            if unknown and decision.get('unknownOutcomeRetained') is not True:
                reason = 'unknown-outcome-must-remain-explicit'
            elif row.get('gapKind') == 'policy-acceptance':
                reason = 'policy-assurance-is-not-an-execution-blocker'
            elif (not nonblank(decision.get('diagnosis')) or not nonblank(decision.get('blockedBy'))
                  or not nonblank(decision.get('nextStep')) or not isinstance(options, list) or not options
                  or any(not isinstance(o, dict) or not nonblank(o.get('option'))
                         or not nonblank(o.get('basis')) for o in options)):
                reason = 'dependency-not-diagnosed'
        elif action == 'not-applicable':
            if row.get('gapKind') in ('fixture', 'auth', 'capability', 'configuration'):
                reason = 'missing-prerequisite-is-not-inapplicability'
            elif not nonblank(decision.get('applicability')):
                reason = 'applicability-basis-missing'
        elif action in ('user-excluded', 'outside-assignment'):
            if not nonblank(decision.get('scopeBasis')):
                reason = 'user-scope-basis-missing'
        else:
            reason = 'handling-decision-missing'
        if reason:
            unresolved.append({'id': rid, 'reason': reason, 'missingObservations': missing})
        else:
            grounded.append({'id': rid, 'action': action})
    dependencies = [r['id'] for r in grounded if r['action'] == 'dependency']
    return {
        'completedResponsibilities': completed,
        'unresolved': unresolved,
        'nextActions': actions,
        'openWorkWithDecisions': grounded,
        'allOpenWorkHasGroundedDecision': not unresolved,
        'taskCompletion': 'unverified-by-review-helper',
        'continuationRequired': bool(actions),
        'workComplete': bool(ids) and not unresolved and not actions and not dependencies,
        'declaredListHandled': bool(ids) and not unresolved and not actions and not dependencies,
        'canHandOffPartial': bool(dependencies) and not unresolved and not actions,
        'limits': 'workComplete/declaredListHandled mean only the declared list was handled, not assignment completion. Caller-declared inventory and grounds only; no proof of completeness, authority, policy or live execution. Planned actions still require execution.'
    }


def review_checkpoint(checkpoint, current):
    conflicts = []
    for field in ('product', 'environment'):
        if not nonblank(checkpoint.get(field)) or checkpoint.get(field) != current.get(field):
            conflicts.append(field + '-missing-or-different')
    for field in ('runId', 'attemptId', 'origin', 'targetBinding', 'runtimeBinding',
                  'image', 'build', 'schemaRevision', 'scopeRevision'):
        if (field in checkpoint or field in current) and checkpoint.get(field) != current.get(field):
            conflicts.append(field + '-missing-or-different')
    for label, snapshot in (('checkpoint', checkpoint), ('current', current)):
        operations = snapshot.get('operations')
        if not isinstance(operations, list):
            conflicts.append(label + '-operations-unavailable')
            continue
        if 'requestCount' in snapshot and (type(snapshot['requestCount']) is not int
                                           or snapshot['requestCount'] != len(operations)):
            conflicts.append(label + '-request-count-inconsistent')
        if snapshot.get('outcomeUnknown') is True or any(
                isinstance(op, dict) and (op.get('outcomeUnknown') is True or op.get('pendingStart') is True)
                for op in operations):
            conflicts.append(label + '-unknown-outcome')
    # Compare the declared lineage as a whole; never pick the longest/newest file.
    if checkpoint.get('operations') != current.get('operations'):
        conflicts.append('operation-lineage-different')
    for field in ('executionStatus', 'finishedAt'):
        if checkpoint.get(field) != current.get(field):
            conflicts.append(field + '-different')
    return {
        'requiresReconciliation': bool(conflicts),
        'conflicts': conflicts,
        'limits': 'Read-only comparison of supplied snapshots; does not select a canonical state, merge files, verify liveness or permit replay.'
    }


def review_session(run, current=None, *, alerts=None, scope_alerts=None):
    """Review handoff data, independently of dependency-based canHandOffPartial.

    Pending reconciliation does not prevent a usable checkpoint. Missing data is
    recoverable; this helper neither writes state nor determines task completion.
    Diagnostics contain field paths/codes only, never untrusted checkpoint prose.
    """
    if 'criteriaWorkflow' in run or run.get('workflowVersion') == 2:
        raise ValueError('legacy session reviewer cannot evaluate v2; use scope criteria-review')
    missing, conflicts = [], []
    context = run.get('assessmentContext', {})
    scope = run.get('scope', {})
    if not isinstance(context, dict):
        missing.append('assessmentContext')
        context = {}
    if not isinstance(scope, dict):
        scope = {}
    for field in ('product', 'environment'):
        value = context.get(field, run.get(field, scope.get(field)))
        if field == 'product' and value is None:
            value = scope.get('productLocation')
        if value is None or value == 'unknown' or value == '':
            missing.append('assessmentContext.' + field)
    continuation = run.get('continuation')
    if not isinstance(continuation, dict):
        missing.append('continuation')
        continuation = {}
    if type(continuation.get('version')) is not int or continuation['version'] != 1:
        missing.append('continuation.version')
    for key in ('status', 'reason', 'updatedAt'):
        if not nonblank(continuation.get(key)):
            missing.append('continuation.' + key)
    focus = continuation.get('currentFocus')
    if not isinstance(focus, dict) or not nonblank(focus.get('progress')):
        missing.append('continuation.currentFocus.progress')

    def rows(key, fields):
        value = continuation.get(key)
        if not isinstance(value, list):
            missing.append('continuation.' + key)
            return []
        for i, row in enumerate(value):
            for field in fields:
                if not isinstance(row, dict) or not nonblank(row.get(field)):
                    missing.append('continuation.' + key + '.' + str(i) + '.' + field)
        return value

    # An actual handoff needs actionable user guidance. In-progress recovery
    # saves need no continuation prompt; missing legacy data remains saveable.
    if continuation.get('status') == 'checkpointed':
        guidance = continuation.get('userGuidance')
        if not isinstance(guidance, dict):
            guidance = {}
        if guidance.get('contextRecommendation') not in ('continue-here', 'new-context-recommended'):
            missing.append('continuation.userGuidance.contextRecommendation')
        for field in ('reason', 'userAction', 'resumePrompt'):
            if not nonblank(guidance.get(field)):
                missing.append('continuation.userGuidance.' + field)

    actions = rows('nextActions', ('action',))
    if not actions and run.get('taskCompletion') != 'complete':
        missing.append('continuation.nextActions.first-step')
    for i, row in enumerate(actions):
        for field in ('readFirst', 'dependsOn'):
            if not isinstance(row, dict) or not string_list(row.get(field)):
                missing.append('continuation.nextActions.' + str(i) + '.' + field)
    revalidate = rows('revalidate', ('subject', 'reason', 'readVia'))
    pending = rows('pendingOperations', ('operationRef', 'lastKnownState', 'owner', 'readVia', 'nextAction'))
    rows('resourceDisposition', ('resourceRef', 'disposition', 'reason'))
    # Known live/unknown work must remain visible, even when metadata lagged.
    pending_refs = {p['operationRef'] for p in pending
                    if isinstance(p, dict) and nonblank(p.get('operationRef'))}
    unrecorded_pending = False
    operations = run.get('operations', [])
    if not isinstance(operations, list):
        missing.append('operations')
        operations = []
    for i, op in enumerate(operations):
        if not isinstance(op, dict):
            missing.append('operations.' + str(i))
            continue
        state = op.get('status', op.get('executionStatus', op.get('state')))
        live = (op.get('outcomeUnknown') is True or op.get('pendingStart') is True or
                state in ('running', 'queued', 'pending', 'accepted', 'acknowledged', 'unknown',
                          'stop-requested', 'stop-acknowledged') or
                (op.get('effect') in ('start', 'mutation') and state == 'intent'))
        if live and not any(str(op.get(k)) in pending_refs for k in
                            ('id', 'operationId', 'actionId', 'nativeScanId') if op.get(k) is not None):
            missing.append('operations.' + str(i) + '.pending-readback')
            unrecorded_pending = True
    if continuation and run.get('taskCompletion') != 'complete' and run.get('handoffClosesTask') is not False:
        missing.append('handoffClosesTask.false-for-open-work')
    if current is not None:
        def snapshot(value):
            context = value.get('assessmentContext', {})
            if not isinstance(context, dict):
                conflicts.append('assessmentContext-invalid')
                context = {}
            return {**context, **value}
        conflicts.extend(review_checkpoint(snapshot(run), snapshot(current))['conflicts'])
    if alerts is not None or scope_alerts is not None:
        reports = (run, alerts, scope_alerts)
        if any(not isinstance(r, dict) for r in reports):
            conflicts.append('report-bundle-incomplete')
        else:
            for field in ('assessmentContext', 'taskCompletion'):
                if any(r.get(field) != run.get(field) for r in reports[1:]):
                    conflicts.append('report-bundle-' + field + '-different')
            generations = [r.get('reportGeneration', {}) for r in reports]
            ids = [g.get('bundleId') if isinstance(g, dict) else None for g in generations]
            if (any(not isinstance(g, dict) for g in generations) or
                    (any(i is not None for i in ids) and
                     (not all(nonblank(i) for i in ids) or ids[1:] != ids[:-1]))):
                conflicts.append('report-bundle-generation-different')
    steps = ['read-official-run-and-related-artifacts']
    if missing:
        steps.append('recover-missing-checkpoint-information')
    if pending or unrecorded_pending or conflicts:
        steps.append('reconcile-journal-ack-status-and-object-state-before-dependent-effects')
    if revalidate:
        steps.append('revalidate-next-action-dependencies')
    steps.append('choose-next-work-unit-under-existing-admission')
    return {
        'checkpointReady': not missing,
        'missingInformation': missing,
        'requiresReconciliation': bool(pending or unrecorded_pending or conflicts),
        'conflicts': conflicts,
        'nextActionCount': len(actions),
        'revalidationRequired': bool(revalidate),
        'resumeSteps': steps,
        'limits': 'Handoff data only; does not verify facts/liveness, justify ending a work session, close the task, grant authority, dispatch, read private references or permit replay. Incomplete checkpoints may still be saved.'
    }


def read(path):
    with open(path, encoding='utf-8') as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError('document must be object')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    work = commands.add_parser('work')
    work.add_argument('--input', required=True)
    checkpoint = commands.add_parser('checkpoint')
    checkpoint.add_argument('--checkpoint', required=True)
    checkpoint.add_argument('--current', required=True)
    session = commands.add_parser('session', help='Review RUN continuation data; runnable work may remain')
    session.add_argument('--run', required=True)
    session.add_argument('--current')
    session.add_argument('--alerts')
    session.add_argument('--scope-alerts')
    args = parser.parse_args(argv)
    try:
        if args.command == 'work':
            result = review_work(read(args.input))
            attention = bool(result['unresolved'] or result['nextActions'])
        elif args.command == 'checkpoint':
            result = review_checkpoint(read(args.checkpoint), read(args.current))
            attention = result['requiresReconciliation']
        else:
            result = review_session(read(args.run), read(args.current) if args.current else None,
                alerts=read(args.alerts) if args.alerts else None,
                scope_alerts=read(args.scope_alerts) if args.scope_alerts else None)
            attention = not result['checkpointReady'] or result['requiresReconciliation']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Do not echo arbitrary file contents/exception messages containing secrets.
        print(json.dumps({'error': 'invalid-or-unreadable-review-input'}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if attention else 0


if __name__ == '__main__':
    raise SystemExit(main())
