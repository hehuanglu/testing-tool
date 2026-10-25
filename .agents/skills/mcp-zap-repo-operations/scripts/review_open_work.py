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
        'canHandOffPartial': bool(dependencies) and not unresolved and not actions,
        'limits': 'Caller-declared inventory and grounds only; no proof of completeness, authority, policy or live execution. Planned actions still require execution.'
    }


def review_checkpoint(checkpoint, current):
    conflicts = []
    for field in ('product', 'environment'):
        if not nonblank(checkpoint.get(field)) or checkpoint.get(field) != current.get(field):
            conflicts.append(field + '-missing-or-different')
    for field in ('runId', 'attemptId', 'origin', 'targetBinding'):
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
    args = parser.parse_args(argv)
    try:
        if args.command == 'work':
            result = review_work(read(args.input))
            attention = bool(result['unresolved'] or result['nextActions'])
        else:
            result = review_checkpoint(read(args.checkpoint), read(args.current))
            attention = result['requiresReconciliation']
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # Do not echo arbitrary file contents/exception messages containing secrets.
        print(json.dumps({'error': 'invalid-or-unreadable-review-input'}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if attention else 0


if __name__ == '__main__':
    raise SystemExit(main())
