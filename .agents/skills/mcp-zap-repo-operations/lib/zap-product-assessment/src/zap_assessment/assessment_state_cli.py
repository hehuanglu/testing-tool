"""Managed state CLI. All commands here operate on local metadata only."""
import json
from datetime import datetime, timezone
from pathlib import Path

from . import assessment_store as store
from .contracts import Blocked, digest
from .criteria_delegation import DelegationError, coordinator_lock, merge_result, validate_packet
from .criteria_workflow import approval_digest, review_workflow
from .operation_selection import select_next
from .operator_state import change_repair, timestamp


COMMANDS = {
    'state-init': ('run', 'operator', 'state-dir', 'registry-dir', 'registration-id'),
    'state-resolve': ('registry-dir', 'assessment-id'),
    'state-inspect': ('state-dir',),
    'state-commit': ('state-dir', 'expected-generation', 'commit-id', 'run', 'operator'),
    'state-merge': ('state-dir', 'expected-generation', 'commit-id', 'packet', 'result'),
    'state-next': ('state-dir',),
    'state-render': ('state-dir',),
    'state-inspect-recovery': ('state-dir',),
    'state-recover-leases': ('state-dir', 'packet'),
    'state-repair-open': ('state-dir', 'expected-generation', 'commit-id', 'repair'),
    'state-repair-update': ('state-dir', 'expected-generation', 'commit-id', 'repair'),
}


def add_commands(subparsers):
    for command, fields in COMMANDS.items():
        parser = subparsers.add_parser(command)
        for field in fields:
            parser.add_argument('--' + field, required=True)
        if command == 'state-next':
            parser.add_argument('--evidence-index')
            parser.add_argument('--now')


def managed_run_argument(parser):
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--run', type=Path)
    group.add_argument('--state-dir', type=Path)


def inspection_for(run):
    coordinator = store.coordinator_for(run)
    return coordinator.inspect_recovery() if coordinator else dict(
        integrity='clean', effectsAllowed=True, pendingCertainty='complete')


def execution_binding_facts(snapshot, inspection):
    """Match saved packet bytes against approval, action and durable ownership."""
    facts = {}
    leases = inspection.get('leases', {})
    active = inspection.get('activeLeases', {})
    pending = {row['actionId']: row for row in inspection.get('knownPendingEffects', [])}
    for work in snapshot.operator['workItems']:
        saved = work.get('executionBinding')
        if not saved or work['state'] == 'done':
            continue
        fact = facts[work['id']] = {'status': 'conflict', 'refs': [saved['packetRef']]}
        try:
            packet = store.read_json(snapshot.resolve_reference(saved['packetRef']))
        except FileNotFoundError:
            fact['status'] = 'unavailable'
            continue
        except (OSError, ValueError, TypeError, KeyError):
            continue
        if not isinstance(packet, dict):
            continue
        keys = ('taskId', 'workerId', 'packetDigest')
        if any(packet.get(key) != saved[key] for key in keys):
            continue
        if digest({key: value for key, value in packet.items() if key != 'packetDigest'}) != saved['packetDigest']:
            continue
        if packet.get('assessmentId') != snapshot.run['assessmentId']:
            continue
        reference = work['actionRef']
        owner = {key: packet[key] for key in (*keys, 'assessmentId')}
        claim = active.get(saved['taskId'])
        original = pending.get(work.get('readbackOf'))
        original_read = (claim and original and original.get('caseId') == reference['caseId']
                         and all(original.get(key) == value for key, value in owner.items()))
        try:
            if not original_read:
                validate_packet(snapshot.run, packet, operational=False)
            descriptor = next((action for case in packet['cases'] if case['id'] == reference['caseId']
                               for action in case.get('actions', []) if action['id'] == reference['actionId']), None)
            resources = packet['resourceIds']
            if (descriptor is None or descriptor.get('readbackOf') != work.get('readbackOf')
                or not set(work['caseIds']) <= set(packet['caseIds'])
                or not set(work['resourceIds']) <= set(resources)
                or original_read and descriptor.get('effect') != 'read'):
                continue
        except (ValueError, KeyError, TypeError, AttributeError):
            continue
        if claim is None:
            if not any(resource in leases for resource in work['resourceIds']):
                fact['status'] = 'unleased'
            continue
        if (claim.get('resourceIds') != resources
            or any(claim.get(key) != value for key, value in owner.items())
            or not all(all(leases.get(resource, {}).get(key) == value for key, value in owner.items())
                       for resource in resources)):
            continue
        fact.update(status='verified', taskId=saved['taskId'])
    return facts


def decision_for(snapshot, *, evidence_index=(), now=None):
    inspection = inspection_for(snapshot.run)
    review = review_workflow(snapshot.run) if inspection['effectsAllowed'] else {}
    if inspection['effectsAllowed'] and snapshot.operator['planDigest'] == approval_digest(
            snapshot.run['criteriaWorkflow'], 'plan'):
        inspection['executionBindings'] = execution_binding_facts(snapshot, inspection)
    decision = select_next(snapshot.run, snapshot.operator, review, inspection, managed=True,
                           evidence_index=evidence_index, now=now or datetime.now(timezone.utc))
    if decision['nextAction'] and decision['nextAction']['kind'] in ('inspect-recovery', 'recover-leases'):
        decision['nextAction']['refs'] = [inspection['journalPath']]
    if inspection['integrity'] != 'clean':
        decision['recoveryRepair'] = dict(
            kind='journal-integrity', journalRef=inspection['journalPath'],
            tailDigest=inspection['tailDigest'], lastValidHash=inspection['lastValidHash'],
            validPrefixBytes=inspection['validPrefixBytes'],
            nextStep='Reconcile the valid journal prefix against retained executor evidence')
    return dict(decision, generationId=snapshot.generation_id)


def projection_text(snapshot, decision):
    skill = Path(__file__).resolve().parents[4] / 'SKILL.md'
    locator = str(snapshot.state_dir)
    action = decision['nextAction'] or {}
    observed = datetime.now(timezone.utc).isoformat()
    header = (f"Assessment {json.dumps(snapshot.run['assessmentId'])}\n"
              f"Generation {snapshot.generation_id}\nPlan digest {decision['planDigest']}\n"
              f"Journal observed at {observed}\n")
    checklist = [header, 'Generated projection. Recompute with state-next before acting.',
                 f"Mode {decision['mode']}", f"Next action {json.dumps(action.get('kind'))}",
                 f"Pending actions {json.dumps(decision['pendingActionIds'])}",
                 f"Pending certainty {decision['pendingCertainty']}"]
    for work in snapshot.operator['workItems']:
        mark = 'x' if work['state'] == 'done' else ' '
        checklist.append(f"- [{mark}] {json.dumps(work['id'])} ({work['state']})")
    from .product_scope_cli import safe_review_output
    first = safe_review_output({key: action[key] for key in
        ('kind', 'reasonCode', 'workId', 'caseId', 'actionId', 'repairId') if key in action})
    prompt = (
        f"Use the skill at {json.dumps(str(skill))}. Official state directory {json.dumps(locator)}.\n"
        "Run scope state-inspect and scope state-next with that --state-dir. "
        "Use scope state-inspect-recovery to reconcile pending effects before starting conflicting work.\n"
        f"First priority {json.dumps(first)}. "
        "Continue the whole remaining approved workflow. Revalidate executor admission, retain "
        "observations, and persist canonical updates before selecting again. Apply the workflow "
        "stopping rule and retain pending supervision at any handoff.\n")
    return {'checklist.md': '\n'.join(checklist) + '\n', 'CONTINUE-PROMPT.md': prompt}


def render_current(snapshot):
    decision = decision_for(snapshot)
    base = store.directory(snapshot.state_dir / 'projections' / snapshot.generation_id, create=True)
    outputs = {}
    for name, body in projection_text(snapshot, decision).items():
        path = base / name
        store.replace(path, body.encode())
        outputs[name] = str(path)
    return outputs


def _typed_commit(args):
    read = store.read_json
    command = args.command
    initial = store.load_current(args.state_dir)
    if command == 'state-merge':
        packet, result = read(args.packet), read(args.result)
        unsigned = {key: value for key, value in packet.items() if key != 'packetDigest'}
        if digest(unsigned) != packet.get('packetDigest'):
            raise ValueError('invalid packet digest')
        payload = digest([packet['packetDigest'], result])
    else:
        proposal = read(args.repair)
        payload = digest(proposal)
    request = store.request_digest(args.expected_generation, command, payload)
    with coordinator_lock(initial.run):
        current = store.load_current(args.state_dir)
        receipt = store.find_receipt(current, args.commit_id, request)
        if receipt:
            store.sync(current.state_dir)
            return receipt
        if args.expected_generation != current.generation_id:
            raise store.conflict('stale-generation', 'Expected generation is no longer current')
        run, operator = current.run, current.operator
        if command == 'state-merge':
            if not inspection_for(run)['effectsAllowed']:
                raise store.StateError('coordinator-recovery-required', 'Merge requires verified coordinator state')
            try:
                run = merge_result(run, packet, result)
            except DelegationError as exc:
                raise store.conflict('merge-rejected', 'Worker result or packet conflicts with current state') from exc
        else:
            from .criteria_workflow import approval_digest
            if operator['planDigest'] != approval_digest(run['criteriaWorkflow'], 'plan'):
                raise store.conflict('stale-schedule', 'Rebase the schedule before updating repair metadata')
            operator = change_repair(operator, proposal, opening=command == 'state-repair-open')
        return store.commit_snapshot(args.state_dir, expected_generation=args.expected_generation,
            commit_id=args.commit_id, run=run, operator_state=operator, request_kind=command,
            request_payload_digest=payload)


def execute(args):
    read = store.read_json
    command = args.command
    if command == 'state-init':
        receipt = store.register_store(args.registry_dir, args.state_dir, args.run, read(args.operator),
                                       registration_id=args.registration_id)
        if not receipt['alreadyApplied']:
            try:
                render_current(store.load_current(args.state_dir))
            except (OSError, ValueError, RuntimeError):
                receipt['projectionsPending'] = True
        return receipt
    if command == 'state-resolve':
        return store.resolve_store(args.registry_dir, args.assessment_id)
    if command == 'state-inspect':
        return store.inspect_store(args.state_dir)
    if command == 'state-commit':
        return store.commit_snapshot(args.state_dir, expected_generation=args.expected_generation,
            commit_id=args.commit_id, run=read(args.run), operator_state=read(args.operator))
    if command in ('state-merge', 'state-repair-open', 'state-repair-update'):
        return _typed_commit(args)
    snapshot = store.load_current(args.state_dir)
    if command == 'state-next':
        return decision_for(snapshot, evidence_index=read(args.evidence_index) if args.evidence_index else (),
                            now=timestamp(args.now) if args.now else None)
    if command == 'state-render':
        return render_current(snapshot)
    if command == 'state-inspect-recovery':
        facts = inspection_for(snapshot.run)
        facts.pop('activeLeases', None)
        facts['leases'] = {resource: {key: row[key] for key in ('assessmentId', 'taskId', 'resourceId')}
                           for resource, row in facts.get('leases', {}).items()}
        for key in ('knownPendingEffects', 'pendingEffects'):
            if facts.get(key) is not None:
                facts[key] = [{field: row[field] for field in ('taskId', 'caseId', 'actionId', 'state')
                               if field in row} for row in facts[key]]
        return facts
    with coordinator_lock(snapshot.run):
        current = store.load_current(args.state_dir)
        coordinator = store.coordinator_for(current.run)
        if coordinator is None:
            raise store.StateError('coordinator-unavailable', 'Retained coordinator state required', status=5)
        packet = read(args.packet)
        facts = coordinator.inspect_recovery()
        if facts['integrity'] != 'clean':
            raise store.StateError('coordinator-integrity', 'Lease recovery requires an intact journal')
        for code in ('legacy-lease-inconsistent', 'orphan-lease-no-intent'):
            if any(row.startswith(code) for row in facts['diagnostics']):
                raise store.StateError(code, 'Retain the lease and verify its original ownership evidence',
                                       refs=[facts['journalPath']])
        try:
            return coordinator.recover_transactions(current.run, packet)
        except DelegationError as exc:
            raise store.conflict('lease-recovery-conflict', 'Lease recovery rejected the binding or resource state') from exc


def handle(args):
    try:
        output = execute(args)
        if args.command == 'state-next':
            # Evidence-index records are untrusted hints and may contain raw content.
            from .product_scope_cli import safe_review_output
            output = safe_review_output(output)
            if output.get('nextAction'):
                output['nextAction'].pop('retainedCandidates', None)
        print(json.dumps(output))
        return 0
    except store.StateError as exc:
        code, message, refs, status = exc.code, str(exc), exc.refs, exc.status
    except Blocked:
        code, message, refs, status = 'coordinator-integrity', 'Coordinator verification failed', [], 4
    except (ValueError, TypeError, KeyError, AttributeError):
        code, message, refs, status = 'invalid-input', 'Input failed schema or binding validation', [], 2
    except OSError:
        code, message, refs, status = 'state-io', 'State input or dependency unavailable', [], 5
    print(json.dumps(dict(code=code, message=message, refs=refs)))
    return status
