"""Bound work packets and durable, exclusive coordinator dispatch for workflow v2.

This is orchestration, not a transport or an authorization issuer. Callbacks must
be existing admitted executors. All coordinators sharing a scanner must use the
same state directory and resource ID. Journal/lease files are private working
state; the coordinator alone writes the canonical RUN.
"""
from __future__ import annotations

import copy
import fcntl
import hashlib
import json
import os
import threading
from contextlib import contextmanager
from pathlib import Path

from .contracts import digest
from .journal import Journal
from .safety_io import atomic_bytes


_LOCKS = {}
_LOCKS_GUARD = threading.Lock()


def _reset_locks_after_fork():
    global _LOCKS, _LOCKS_GUARD
    _LOCKS = {}
    _LOCKS_GUARD = threading.Lock()


os.register_at_fork(after_in_child=_reset_locks_after_fork)


class DelegationError(ValueError):
    pass


@contextmanager
def coordinator_lock(run):
    """Serialize a working RUN transaction without creating missing state."""
    state = run.get('coordinatorState')
    if state is None:
        yield
        return
    if (not isinstance(state, dict) or state.get('assessmentId') != run.get('assessmentId')
        or not isinstance(state.get('directory'), str) or not Path(state['directory']).is_dir()):
        raise DelegationError('missing or foreign coordinator state')
    coordinator = Coordinator(state['directory'], state['assessmentId'])
    with coordinator.locked():
        yield


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise DelegationError(name + ' must be a nonempty string')
    return value


def _approved(run):
    from .criteria_workflow import _approval_status, validate_workflow
    workflow = validate_workflow(run.get('criteriaWorkflow'))
    workflow.setdefault('approvals', [])
    if not all(_approval_status(workflow).values()):
        raise DelegationError('current workflow approval required')
    cw = run['criteriaWorkflow']
    if cw.get('userRequest', {}).get('kind') in ('stop', 'pause'):
        raise DelegationError('user stop/pause prevents dispatch')
    return cw


def effective_resources(plan, cases):
    resources = set(plan.get('resourceIds', []))
    for case in cases:
        resources.update(case.get('resourceIds', []))
    return sorted(resources or {'target:' + digest(plan['authority']['target'])})


def make_packet(run, task_id, case_ids, worker_id, refs=None, *, operational=True):
    """Select only assigned cases and references; never copy a parent transcript."""
    from .criteria_workflow import approval_digest
    cw = _approved(run)
    if operational:
        from .criteria_workflow import review_workflow
        review_workflow(run)
    _text(task_id, 'taskId'); _text(worker_id, 'workerId')
    if not isinstance(case_ids, list) or not case_ids or len(set(case_ids)) != len(case_ids):
        raise DelegationError('nonempty unique caseIds required')
    cases = {c['id']: c for c in cw['plan']['cases']}
    if set(case_ids) - cases.keys():
        raise DelegationError('case outside approved plan')
    refs = copy.deepcopy(refs or {})
    if set(refs) - {'productFactsRef', 'workingStateRef', 'executorRef', 'secretRefs',
                    'pendingEffectsRef', 'resourceLeaseRef'}:
        raise DelegationError('only minimal reference fields allowed')
    for key, value in refs.items():
        if key == 'secretRefs':
            if not isinstance(value, list):raise DelegationError('secretRefs must be references')
            for ref in value:_text(ref, 'secret reference')
        else:_text(value, key)
    selected = [cases[cid] for cid in case_ids]
    if cw['plan'].get('delegation', {}).get('allowed') is not True and worker_id != 'coordinator':
        raise DelegationError('worker delegation must be included in the approved plan')
    # This fallback serializes the same target even when an operator omits the
    # finer-grained resource map. Shared scanner IDs must still be explicit.
    resources = effective_resources(cw['plan'], selected)
    for value in resources:_text(value, 'resourceId')
    fields = ('id', 'criterionIds', 'objective', 'expectedBehavior', 'expectationBasis',
              'requiredEvidence', 'coverageContext', 'effects', 'actions', 'dependsOnCases', 'requireZapMessageEvidence')
    packet = dict(version=2, taskId=task_id, workerId=worker_id,
        assessmentId=_text(run.get('assessmentId'), 'assessmentId'),
        criteriaRevision=cw['criteriaRevision'], planRevision=cw['planRevision'],
        criteriaDigest=approval_digest(cw, 'criteria'), planDigest=approval_digest(cw, 'plan'),
        criterionIds=sorted({cid for c in selected for cid in c['criterionIds']}),
        caseIds=case_ids, cases=[{k:copy.deepcopy(c[k]) for k in fields if k in c} for c in selected],
        authority=copy.deepcopy(cw['plan']['authority']), resourceIds=sorted(resources), refs=refs)
    packet['packetDigest'] = digest(packet)
    return packet


def validate_packet(run, packet, *, operational=True):
    if not isinstance(packet, dict):raise DelegationError('invalid packet')
    expected = make_packet(run, packet.get('taskId'), packet.get('caseIds'),
                           packet.get('workerId'), packet.get('refs'), operational=operational)
    if packet != expected:raise DelegationError('stale or changed task packet')
    return expected


def merge_result(run, packet, result):
    """Merge validated worker observations without accepting worker conclusions.

    Returns a copy. The caller is the sole canonical writer and must persist it
    under its coordinator lock. Repeated identical rows are idempotent; changed
    history or another task's cases are rejected.
    """
    validate_packet(run, packet)
    if not isinstance(result, dict):
        raise DelegationError('worker result must be an object')
    expected = {'taskId':packet['taskId'], 'packetDigest':packet['packetDigest'],
                'criteriaRevision':packet['criteriaRevision'], 'planRevision':packet['planRevision']}
    if any(result.get(k) != v for k, v in expected.items()):
        raise DelegationError('worker result task/revision mismatch')
    if set(result) - set(expected) - {'operations', 'caseResults'}:
        raise DelegationError('worker cannot write coordinator state or verdicts')
    updated = copy.deepcopy(run)
    from .business_discovery import records
    from .question_evidence import operation_index
    operations = operation_index(updated.get('operations', []))
    incoming = records(result.get('operations', []), 'worker operations')
    cases = {c['id']: c for c in packet['cases']}
    for row in incoming.values():
        oid = _text(row.get('id'), 'operation ID')
        if oid in operations and operations[oid] != row:
            raise DelegationError('historical operation conflict')
        context = row.get('coverageContext', {})
        allowed = [case for case in cases.values() if row.get('caseId') in (None, case['id'])]
        compatible = [case for case in allowed
                      if all(context.get(k) == v for k, v in case['coverageContext'].items())]
        if not compatible:
            raise DelegationError('worker operation outside task context')
        if 'effect' in row and not any(row['effect'] in case['effects'] for case in compatible):
            raise DelegationError('worker operation effect outside task authority')
        operations[oid] = copy.deepcopy(row)
    updated['operations'] = list(operations.values())
    cw = updated['criteriaWorkflow']
    results = {r['caseId']:r for r in cw.get('caseResults', [])}
    for row in records(result.get('caseResults', []), 'worker case results', 'caseId').values():
        cid = row.get('caseId')
        if cid not in packet['caseIds']:raise DelegationError('worker result outside task')
        if cid in results and results[cid] != row:
            raise DelegationError('case result conflict requires coordinator reconciliation')
        results[cid] = copy.deepcopy(row)
    cw['caseResults'] = list(results.values())
    from .criteria_workflow import review_workflow
    review_workflow(updated)  # validates evidence references, context and plan
    return updated


class Coordinator:
    """Private persistent task leases, serialized across processes.

    A dead worker never expires a lease. Recovery must read retained effect state
    and call reconcile with operation evidence before release. No automatic
    context copying, tool import, transport dispatch or background monitoring.
    """
    def __init__(self, state_dir, assessment_id):
        self.assessment_id = _text(assessment_id, 'assessmentId')
        self.root = Path(state_dir).absolute()
        self.root.mkdir(parents=True, mode=0o700, exist_ok=True)
        if self.root.is_symlink():raise DelegationError('symlink coordinator directory')
        self.resources = self.root / 'resources'
        self.directory = self.root / hashlib.sha256(assessment_id.encode()).hexdigest()
        for path in (self.resources, self.directory):
            path.mkdir(mode=0o700, exist_ok=True)
            if path.is_symlink():raise DelegationError('symlink coordinator directory')

    @contextmanager
    def locked(self):
        """Serialize transactions, reentering across instances on this thread.

        The thread mutex also prevents another local thread from sharing the
        outer flock. Separate processes still acquire their own exclusive flock.
        """
        # Resolve aliases of the directory, while keeping NOFOLLOW protection
        # on the final lock filename itself.
        path = str(self.directory.resolve()/'coordinator.lock')
        with _LOCKS_GUARD:
            mutex, local = _LOCKS.setdefault(path, (threading.RLock(), threading.local()))
        with mutex:
            depth = getattr(local, 'depth', 0)
            if depth == 0:
                fd = os.open(path, os.O_RDWR|os.O_CREAT|os.O_NOFOLLOW, 0o600)
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX)
                except BaseException:
                    os.close(fd)
                    raise
                local.fd = fd
            local.depth = depth + 1
            try:
                yield
            finally:
                local.depth -= 1
                if local.depth == 0:
                    fd = local.fd
                    del local.fd
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    finally:
                        os.close(fd)

    def _journal_args(self):
        return (self.directory / 'journal.jsonl', self.assessment_id,
                digest({'assessmentId': self.assessment_id, 'coordinationVersion': 2}))

    def _journal(self):
        return Journal(*self._journal_args())

    @contextmanager
    def _resource_lock(self):
        fd = os.open(self.root / 'resources.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX)
            yield
        finally:
            os.close(fd)

    @staticmethod
    def _sync_directory(path):
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _sync_journal(self):
        path = self._journal_args()[0]
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        self._sync_directory(path.parent)

    def _lease(self, resource):
        path = self._path(resource)
        if path.is_symlink() or (path.exists() and not path.is_file()):
            raise DelegationError('invalid resource lease file')
        try:
            return json.loads(path.read_bytes())
        except FileNotFoundError:
            return None

    def _transaction(self, packet, kind):
        binding = dict(self._binding(packet), resourceIds=packet['resourceIds'])
        return dict(binding, transactionId=digest(dict(binding, kind=kind)))

    def inspect_recovery(self):
        """Return forensic facts. A damaged suffix makes pending effects unknown."""
        journal_path = self._journal_args()[0]
        if journal_path.is_symlink():
            return dict(integrity='corrupt-record', journalPath=str(journal_path),
                        validPrefixBytes=0, lastValidHash=None, tailBytes=None, tailDigest=None,
                        diagnostics=['unsafe-journal-path'], pendingEffects=None, knownPendingEffects=[],
                        pendingCertainty='prefix-only', openTransactions=[], leases={}, effectsAllowed=False)
        inspection = Journal.inspect(*self._journal_args())
        events = inspection.pop('validEvents')
        from types import SimpleNamespace
        journal = SimpleNamespace(events=events)
        tasks = sorted({event['data']['taskId'] for event in events if 'taskId' in event['data']})
        transactions = []
        for task in tasks:
            rows = self._events(journal, task)
            for intent, terminal in (
                ('lease_acquire_intent', {'leased', 'lease_acquire_aborted'}),
                ('lease_release_intent', {'released'}),
            ):
                if any(e['kind'] == intent for e in rows) and not any(e['kind'] in terminal for e in rows):
                    transactions.append({'taskId': task, 'kind': intent})
        leases = {}
        for path in sorted(self.resources.glob('*.json')):
            if path.is_symlink() or not path.is_file():
                inspection['diagnostics'].append('invalid-resource-lease')
                continue
            try:
                row = json.loads(path.read_bytes())
                if not isinstance(row, dict) or self._path(row['resourceId']) != path:
                    raise ValueError('invalid lease')
                leases[row['resourceId']] = {key: row[key] for key in
                                              ('assessmentId', 'taskId', 'resourceId', 'workerId', 'packetDigest')}
            except FileNotFoundError:
                continue
            except (KeyError, TypeError, ValueError):
                inspection['diagnostics'].append('invalid-resource-lease')
        active = {}
        if inspection['integrity'] == 'clean':
            try:
                active = self._validate_retained_leases(journal)
            except DelegationError as exc:
                inspection['diagnostics'].append(str(exc))
        known = [dict(row, state='unknown') for task in tasks
                 for row in self._pending(self._events(journal, task)).values()]
        clean = inspection['integrity'] == 'clean'
        return dict(inspection, journalPath=str(self._journal_args()[0]),
                    pendingEffects=known if clean else None, knownPendingEffects=known,
                    pendingCertainty='complete' if clean else 'prefix-only',
                    openTransactions=transactions, leases=leases, activeLeases=active,
                    consumedActionIds=sorted({e['data']['actionId'] for e in events if e['kind'] == 'intent'}),
                    effectsAllowed=clean and not transactions and not inspection['diagnostics'])


    def _validate_retained_leases(self, journal):
        active = {}
        released_legacy = set()
        for event in journal.events:
            row = event['data']
            if event['kind'] == 'leased':
                active[row['taskId']] = row
            elif event['kind'] == 'released':
                active.pop(row['taskId'], None)
                if not row.get('transactionId'):
                    released_legacy.add(row['taskId'])
        for row in active.values():
            try:
                self._check_leases(row)
            except DelegationError:
                if not row.get('transactionId'):
                    raise DelegationError('legacy-lease-inconsistent: verify original ownership and effect state') from None
                raise
        terminal = {e['data'].get('transactionId') for e in journal.events
                    if e['kind'] in ('leased', 'released', 'lease_acquire_aborted')}
        for event in journal.events:
            if event['kind'] not in ('lease_acquire_intent', 'lease_release_intent'):
                continue
            tid = event['data']['transactionId']
            if tid not in terminal:
                raise DelegationError('unfinished lease transaction: recover original packet')
        # A deleted journal cannot make an owned lease disappear from review.
        for path in self.resources.glob('*.json'):
            if path.is_symlink() or not path.is_file():
                if not path.exists() and not path.is_symlink():
                    continue
                raise DelegationError('invalid resource lease file')
            try:
                row = json.loads(path.read_bytes())
            except (ValueError, TypeError) as exc:
                raise DelegationError('invalid resource lease record') from exc
            except FileNotFoundError:
                # Another assessment may finish its independent lease while
                # this shared resource directory is being enumerated.
                continue
            if not isinstance(row, dict):
                raise DelegationError('invalid resource lease record')
            if row.get('assessmentId') == self.assessment_id:
                task = active.get(row.get('taskId'))
                if not task or row.get('resourceId') not in task['resourceIds']:
                    if row.get('taskId') in released_legacy:
                        raise DelegationError('legacy-released-lease-leftover')
                    raise DelegationError('orphan-lease-no-intent')
        return active

    def _path(self, resource):
        return self.resources / (hashlib.sha256(resource.encode()).hexdigest()+'.json')

    def _binding(self, packet):
        if packet['assessmentId'] != self.assessment_id:
            raise DelegationError('coordinator assessment mismatch')
        return {k:packet[k] for k in ('assessmentId','taskId','workerId','packetDigest')}

    def _check_leases(self, packet):
        binding = self._binding(packet)
        for resource in packet['resourceIds']:
            path = self._path(resource)
            if path.is_symlink() or not path.is_file():raise DelegationError('missing resource lease')
            saved = json.loads(path.read_bytes())
            if saved != dict(binding, resourceId=resource):raise DelegationError('resource belongs to another task')

    def _recovery_binding(self, run, packet, *, kinds=('leased',), check_leases=True):
        """Recover retained work even after a revision or user stop.

        A packet's self digest alone grants no authority. The exact binding must
        also match the durable lease and the original journal lease event.
        """
        if (run.get('assessmentId') != self.assessment_id or
            run.get('coordinatorState') != {'directory': str(self.root), 'assessmentId': self.assessment_id}):
            raise DelegationError('recovery requires the original coordinator state')
        if not isinstance(packet, dict):
            raise DelegationError('invalid recovery packet')
        original = copy.deepcopy(packet)
        claimed = original.pop('packetDigest', None)
        if not claimed or digest(original) != claimed:
            raise DelegationError('changed recovery packet')
        if check_leases:
            self._check_leases(packet)
        binding = self._binding(packet)
        events = self._events(self._journal(), packet['taskId'])
        if not any(e['kind'] in kinds and all(e['data'].get(k) == v for k, v in binding.items())
                   and e['data'].get('resourceIds') == packet['resourceIds'] for e in events):
            raise DelegationError('recovery packet has no durable task binding')
        return events

    @staticmethod
    def _events(journal, task_id):
        return [e for e in journal.events if e['data'].get('taskId') == task_id]

    @staticmethod
    def _pending(events):
        pending = {}
        for event in events:
            row = event['data']; aid = row.get('actionId')
            if event['kind'] == 'intent':pending[aid] = row
            elif event['kind'] == 'reconciled':pending.pop(aid, None)
        return pending

    def acquire(self, run, packet):
        with self.locked():
            validate_packet(run, packet, operational=False)
            if run.get('coordinatorState') != {'directory': str(self.root), 'assessmentId': self.assessment_id}:
                raise DelegationError('persist coordinatorState in working RUN before acquiring resources')
            journal = self._journal()
            events = self._events(journal, packet['taskId'])
            if not events:
                from .criteria_workflow import review_workflow
                review_workflow(run)
            with self._resource_lock():
                return self._acquire(journal, packet, events, recovery=False)

    def _acquire(self, journal, packet, events, *, recovery):
        transaction = self._transaction(packet, 'acquire')
        kinds = {event['kind'] for event in events}
        if any(any(event['data'].get(key) != value for key, value in self._binding(packet).items())
               for event in events):
            raise DelegationError('task ID already bound to another packet')
        if kinds & {'released', 'lease_release_intent', 'lease_acquire_aborted'}:
            raise DelegationError('closed task ID cannot be acquired again')
        if 'leased' in kinds:
            self._check_leases(packet)
            self._sync_journal()
            return dict(transaction, alreadyApplied=True)
        intent = next((e['data'] for e in events if e['kind'] == 'lease_acquire_intent'), None)
        if intent is not None and intent != transaction:
            raise DelegationError('acquire intent binding mismatch')
        binding = self._binding(packet)
        leases = {resource: self._lease(resource) for resource in packet['resourceIds']}
        conflict = any(row is not None and (intent is None or row != dict(binding, resourceId=resource))
                       for resource, row in leases.items())
        if conflict:
            if recovery and intent and not any(e['kind'] == 'intent' for e in events):
                for resource, row in leases.items():
                    if row == dict(binding, resourceId=resource):
                        self._path(resource).unlink()
                self._sync_directory(self.resources)
                journal.append('lease_acquire_aborted', dict(transaction, reason='foreign-resource-conflict'))
                return dict(transaction, aborted=True, reason='foreign-resource-conflict')
            raise DelegationError('resource already leased')
        if intent is None:
            journal.append('lease_acquire_intent', transaction)
        for resource, row in leases.items():
            if row is None:
                atomic_bytes(self._path(resource), json.dumps(dict(binding, resourceId=resource)).encode())
        self._check_leases(packet)
        self._sync_directory(self.resources)
        journal.append('leased', transaction)
        return dict(transaction, alreadyApplied=False)

    def recover_transactions(self, run, packet):
        with self.locked():
            events = self._recovery_binding(run, packet, kinds=('leased', 'lease_acquire_intent'),
                                            check_leases=False)
            kinds = {event['kind'] for event in events}
            if kinds & {'released', 'lease_release_intent'}:
                return self.release(run, packet)
            if 'lease_acquire_aborted' in kinds:
                return dict(self._transaction(packet, 'acquire'), aborted=True, alreadyApplied=True)
            if 'leased' in kinds and 'lease_acquire_intent' not in kinds:
                self._validate_retained_leases(self._journal())
            with self._resource_lock():
                return self._acquire(self._journal(), packet, events, recovery=True)

    def validate_dispatch_binding(self, run, packet, action):
        """Use original authority only for a read of an effect pending in its own task."""
        if action.get('effect') == 'read' and action.get('readbackOf'):
            with self.locked():
                events = self._events(self._journal(), packet['taskId'])
                original = self._pending(events).get(action['readbackOf'])
                if original is not None:
                    self._recovery_binding(run, packet)
                    if action.get('caseId') != original.get('caseId') or not any(
                            action in case.get('actions', []) for case in packet['cases']):
                        raise DelegationError('readback differs from original approved task')
                    self._validate_retained_leases(self._journal())
                    return True
        validate_packet(run, packet)
        return False

    def dispatch_routed(self, run, packet, action, candidates, executors, *, fixture_ref=None):
        """Select an admitted implementation for an unchanged approved action.

        Candidates describe the receiving session. Each registered callback must
        bind that session again and apply executor admission before any effect.
        JSON cannot register callbacks or change the approved action descriptor.
        """
        from .executor_routing import map_question_capability

        candidates = list(candidates)
        ids = [_text(candidate.get('id'), 'executor ID') for candidate in candidates]
        if len(ids) != len(set(ids)):
            raise DelegationError('duplicate executor ID')
        self.validate_dispatch_binding(run, packet, action)
        decision = map_question_capability(action, candidates)
        selected = decision['selectedExecutor']
        if selected is None:
            return {'routing': decision, 'dispatched': False}
        executor = executors.get(selected)
        if not callable(executor):
            raise DelegationError('selected route has no admitted callback')
        return {'routing': decision, 'dispatched': True,
                'outcome': self.dispatch(run, packet, action, executor, executor_id=selected, fixture_ref=fixture_ref)}

    def dispatch(self, run, packet, action, executor, *, executor_id=None, fixture_ref=None):
        """Invoke an already-admitted callback once, after durable intent.

        Action must name caseId, id, effect and match a declared case action when
        present. It may contain readbackOf for a read-only reconciliation action.
        The callback retains responsibility for actual target/auth/impact gates.
        It must durably retain native ACK/IDs/results in its private operation
        store before returning. The journal records execution transitions, not
        arbitrary callback responses that may contain credentials or raw data.
        Return/exception never proves a producer stopped; reconcile separately.
        """
        self.validate_dispatch_binding(run, packet, action)
        if not callable(executor):raise DelegationError('admitted callback required')
        aid = _text(action.get('id'), 'action ID')
        cases = {c['id']:c for c in packet['cases']}
        case = cases.get(action.get('caseId'))
        if case is None:raise DelegationError('action case outside packet')
        effect = action.get('effect')
        if effect not in case.get('effects', []) or effect not in packet['authority']['allowedEffects']:
            raise DelegationError('action effect outside approved case')
        if not case.get('actions') or action not in case['actions']:
            raise DelegationError('action differs from approved descriptor')
        execution_action = copy.deepcopy(action)
        if action.get('fixtureOptions') and fixture_ref is None:
            raise DelegationError('select an approved fixture before dispatch')
        if fixture_ref is not None:
            _text(fixture_ref, 'fixture reference')
            if fixture_ref not in action.get('fixtureOptions', []):
                raise DelegationError('fixture outside approved action options')
            execution_action['fixtureRef'] = fixture_ref
        from .criteria_workflow import review_workflow
        from .question_evidence import affected, operation_index
        with self.locked():
            recovering = self.validate_dispatch_binding(run, packet, action)
            self._check_leases(packet)
            review = review_workflow(run)
            reviewed = {r['caseId']:r for r in review['caseResults']}
            journal = self._journal()
            task_pending = self._pending(self._events(journal, packet['taskId']))
            bound_readback = effect == 'read' and action.get('readbackOf') in task_pending
            if not recovering and not bound_readback and any(reviewed[d]['outcome'] not in ('matched', 'violated')
                                          for d in case.get('dependsOnCases', [])):
                raise DelegationError('case dependency lacks sufficient execution evidence')
            if task_pending and not (effect == 'read' and action.get('readbackOf') in task_pending):
                raise DelegationError('pending shared task effects require readback before new dispatch')
            operations = operation_index(run.get('operations', []))
            history = [event.get('data', event) for event in run.get('actionHistory', [])]
            consumed = {row.get('actionId') for row in history if isinstance(row, dict)}
            consumed.update(row.get('actionId') for row in operations.values())
            consumed.update(operations)
            if aid in consumed or any(e['data'].get('actionId') == aid for e in journal.events):
                raise DelegationError('consumed action ID; read back, never replay')
            observation = next((r for r in run['criteriaWorkflow'].get('caseResults', [])
                                if r['caseId'] == case['id']), {})
            related = {row['actionId'] for row in review['pendingEffects']
                       if affected(dict(case, caseId=case['id']), row, observation)}
            if related and not (effect == 'read' and action.get('readbackOf') in related):
                raise DelegationError('related pending effects require explicit readback before new dispatch')
            data = dict(self._binding(packet), actionId=aid, caseId=case['id'], effect=effect,
                        coverageContext=case['coverageContext'])
            if executor_id is not None:
                data['executorId'] = _text(executor_id, 'executor ID')
            if fixture_ref is not None:
                data['fixtureRef'] = fixture_ref
            journal.append('intent', data)
            try:
                outcome = executor(execution_action)
            except BaseException:
                journal.append('unknown', data)
                raise
            journal.append('acknowledged', data)
            return outcome

    def reconcile(self, run, packet, action_id, operation_ids):
        """Record coordinator-reviewed terminal readback, without replay.

        Evidence operations must explicitly name reconciledActionId and terminal
        effectStatus. This structural check does not infer semantics from HTTP.
        """
        if not isinstance(operation_ids, list) or not operation_ids:
            raise DelegationError('terminal readback operations required')
        from .question_evidence import operation_index
        operations = operation_index(run.get('operations', []))
        for oid in operation_ids:
            op = operations.get(oid, {})
            if (op.get('reconciledActionId') != action_id or op.get('effectStatus') != 'terminal'
                or op.get('status', op.get('executionStatus')) not in ('completed','partial')
                or not op.get('readback')):
                raise DelegationError('operation does not establish terminal action readback')
            context = op.get('context', op.get('coverageContext', {}))
            if context.get('assessmentId') != packet['assessmentId']:
                raise DelegationError('terminal readback assessment mismatch')
        with self.locked():
            events = self._recovery_binding(run, packet)
            journal = self._journal()
            pending = self._pending(events)
            if action_id not in pending:
                raise DelegationError('action is not pending in this task')
            expected = pending[action_id]['coverageContext']
            for oid in operation_ids:
                actual = operations[oid].get('coverageContext', {})
                if any(actual.get(k) != v for k, v in expected.items()):
                    raise DelegationError('terminal readback action context mismatch')
            journal.append('reconciled', dict(self._binding(packet), actionId=action_id,
                                             operationIds=operation_ids))

    def release(self, run, packet):
        with self.locked(), self._resource_lock():
            events = self._recovery_binding(run, packet, check_leases=False)
            journal = self._journal()
            if self._pending(events):
                raise DelegationError('pending effects retain resource leases')
            transaction = self._transaction(packet, 'release')
            released = next((e['data'] for e in events if e['kind'] == 'released'), None)
            intent = next((e['data'] for e in events if e['kind'] == 'lease_release_intent'), None)
            if intent is not None and intent != transaction:
                raise DelegationError('release intent binding mismatch')
            if released is not None and released.get('transactionId'):
                if released != transaction:
                    raise DelegationError('release commit binding mismatch')
                self._sync_journal()
                return dict(transaction, released=True, alreadyApplied=True)
            if released is None and intent is None:
                self._check_leases(packet)
                journal.append('lease_release_intent', transaction)
            binding = self._binding(packet)
            for resource in packet['resourceIds']:
                row = self._lease(resource)
                if row == dict(binding, resourceId=resource):
                    self._path(resource).unlink()
                elif row is not None and released is None:
                    raise DelegationError('foreign resource during release')
            self._sync_directory(self.resources)
            if released is None:
                journal.append('released', transaction)
            return dict(transaction, released=True, alreadyApplied=released is not None)

    def status(self):
        with self.locked():
            journal = self._journal()
            self._validate_retained_leases(journal)
            task_ids = sorted({e['data']['taskId'] for e in journal.events})
            return {'assessmentId':self.assessment_id,'tasks':[
                {'taskId':tid,'pendingActionIds':sorted(self._pending(self._events(journal,tid))),
                 'lastState':self._events(journal,tid)[-1]['kind']} for tid in task_ids]}

    def review_state(self):
        """Read durable effects and dispatch ownership in one locked snapshot."""
        with self.locked():
            journal = self._journal()
            active = self._validate_retained_leases(journal)
            task_ids = {e['data']['taskId'] for e in journal.events}
            return {'activeTaskIds': sorted(active), 'pendingEffects': [
                dict(row, state='unknown') for tid in task_ids
                for row in self._pending(self._events(journal, tid)).values()]}

    def pending_effects(self):
        """Read durable intents directly; report closure cannot trust a stale RUN."""
        return self.review_state()['pendingEffects']
