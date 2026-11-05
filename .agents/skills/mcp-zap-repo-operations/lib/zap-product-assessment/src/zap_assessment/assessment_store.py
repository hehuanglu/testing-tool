"""Private immutable snapshots and explicit assessment registration."""
import fcntl
import hashlib
import json
import os
import re
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .contracts import canonical, digest
from .criteria_delegation import Coordinator, coordinator_lock
from .safety_io import atomic_bytes


class StateError(ValueError):
    def __init__(self, code, message, *, status=4, refs=()):
        super().__init__(message)
        self.code, self.status, self.refs = code, status, list(refs)


def conflict(code, message):
    return StateError(code, message, status=3)


def checksum(data):
    return hashlib.sha256(data).hexdigest()


def identifier(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('identifier required')
    return checksum(value.encode())


def directory(path, *, create=False):
    path = Path(os.path.abspath(path))
    for part in (*reversed(path.parents), path):
        if part.is_symlink():
            raise StateError('unsafe-path', 'Symbolic link in state path', refs=[str(part)])
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise StateError('missing-directory', 'State directory unavailable', refs=[str(path)])
    return path


def read_bytes(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise StateError('unsafe-file', 'Expected a regular state file', refs=[str(path)])
        return stream.read()


def read_json(path):
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError('duplicate JSON key')
            value[key] = item
        return value
    return json.loads(read_bytes(path), object_pairs_hook=unique)


def sync(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


@contextmanager
def lock(path):
    fd = os.open(path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise StateError('unsafe-file', 'Expected a regular lock file')
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def immutable(path, data):
    try:
        atomic_bytes(path, data)
    except FileExistsError:
        if read_bytes(path) != data:
            raise conflict('immutable-conflict', 'Staged immutable bytes differ')
        sync(path.parent)


def replace(path, data):
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise StateError('unsafe-file', 'Invalid replacement destination', refs=[str(path)])
    fd, name = tempfile.mkstemp(prefix='.publish-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        sync(path.parent)
    finally:
        Path(name).unlink(missing_ok=True)


@dataclass(frozen=True)
class Snapshot:
    state_dir: Path
    generation_id: str
    run: dict
    operator: dict
    manifest: dict
    run_path: Path
    operator_path: Path

    def resolve_reference(self, ref):
        return resolve_reference(ref, self.manifest['source']['artifactBaseDir'])


def resolve_reference(ref, base_dir):
    if isinstance(ref, dict):
        base_dir, ref = ref['baseDir'], ref['path']
    if not isinstance(ref, str) or '://' in ref or not Path(base_dir).is_absolute():
        raise ValueError('invalid filesystem artifact reference')
    return Path(base_dir) / ref


def generation_path(root, gid):
    if not isinstance(gid, str) or not re.fullmatch('[a-f0-9]{64}', gid):
        raise StateError('invalid-generation', 'Malformed generation identifier')
    return root / 'generations' / gid


def _generation(root, gid, manifest_hash=None):
    base = directory(generation_path(root, gid))
    try:
        data = read_bytes(base / 'manifest.json')
        manifest = json.loads(data)
        if ((manifest_hash is not None and checksum(data) != manifest_hash)
            or manifest['version'] != 1 or manifest['generationId'] != gid
            or identifier(manifest['commitId']) != gid
            or manifest['parentGenerationId'] != manifest['expectedGenerationId']):
            raise ValueError('manifest binding')
        source = manifest['source']
        if (not Path(source['sourceRunPath']).is_absolute() or
            str(Path(source['sourceRunPath']).parent) != source['artifactBaseDir'] or
            not re.fullmatch('[a-f0-9]{64}', source['sourceRunSha256'])):
            raise ValueError('invalid source provenance')
        payloads = []
        for name in ('RUN.json', 'OPERATOR.json'):
            raw = read_bytes(base / name)
            if manifest['files'][name] != {'sha256': checksum(raw), 'bytes': len(raw)}:
                raise ValueError('snapshot hash')
            payloads.append(json.loads(raw))
        if any(value['assessmentId'] != manifest['assessmentId'] for value in payloads):
            raise ValueError('assessment binding')
        from .criteria_workflow import validate_workflow
        from .operator_state import validate_operator
        run, operator = payloads
        if run.get('reportProjection'):
            raise ValueError('report projection')
        validate_workflow(run.get('criteriaWorkflow'))
        validate_operator(run, operator, allow_stale=manifest['parentGenerationId'] is not None)
        return Snapshot(root, gid, *payloads, manifest, base / 'RUN.json', base / 'OPERATOR.json')
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise StateError('generation-integrity', 'Generation files failed verification', refs=[str(base)]) from exc


def load_current(state_dir):
    root = directory(state_dir)
    path = root / 'current.json'
    try:
        pointer = read_json(path)
        if set(pointer) != {'version', 'assessmentId', 'generationId', 'manifestSha256'} or pointer['version'] != 1:
            raise ValueError('pointer envelope')
        if not isinstance(pointer['manifestSha256'], str) or not re.fullmatch('[a-f0-9]{64}', pointer['manifestSha256']):
            raise ValueError('pointer manifest hash')
        snap = _generation(root, pointer['generationId'], pointer['manifestSha256'])
        if pointer['assessmentId'] != snap.run['assessmentId']:
            raise ValueError('pointer assessment')
        return snap
    except StateError:
        raise
    except (ValueError, TypeError, KeyError, OSError) as exc:
        raise StateError('pointer-integrity', 'Current pointer unavailable or invalid', refs=[str(path)]) from exc


def coordinator_for(run):
    state = run.get('coordinatorState')
    if state is None:
        return None
    if state.get('assessmentId') != run.get('assessmentId'):
        raise ValueError('coordinator identity mismatch')
    root = directory(state['directory'])
    directory(root / 'resources')
    directory(root / identifier(state['assessmentId']))
    return Coordinator(root, state['assessmentId'])


def _preserve(previous, candidate, key):
    old = previous.get(key, [])
    new = candidate.get(key, [])
    if not isinstance(old, list) or not isinstance(new, list) or new[:len(old)] != old:
        raise ValueError('retained ' + key + ' must be append-only')


def validate_snapshot(run, operator, previous=None, *, repair_mutation=False):
    from .criteria_workflow import review_workflow, validate_workflow
    from .operator_state import validate_operator

    if not isinstance(run, dict) or run.get('reportProjection'):
        raise ValueError('private working RUN required')
    identifier(run.get('assessmentId'))
    workflow = validate_workflow(run.get('criteriaWorkflow'))
    validate_operator(run, operator, allow_stale=previous is not None and operator == previous.operator)
    if previous:
        for key in ('assessmentId', 'coordinatorState'):
            if run.get(key) != previous.run.get(key):
                raise ValueError(key + ' cannot change')
        from .question_evidence import operation_index
        prior_operations = operation_index(previous.run.get('operations', []))
        operations = operation_index(run.get('operations', []))
        if any(operations.get(key) != value for key, value in prior_operations.items()):
            raise ValueError('retained operations cannot be removed or changed')
        for key in ('actionHistory', 'pendingEffects'):
            _preserve(previous.run, run, key)
        if not repair_mutation and operator['repairs'] != previous.operator['repairs']:
            raise ValueError('use the repair lifecycle to change repairs')
        if operator['planDigest'] != previous.operator['planDigest']:
            from .operator_state import validate_rebase
            validate_rebase(previous.operator, operator)
    coordinator = coordinator_for(run)
    inspection = coordinator.inspect_recovery() if coordinator else {}
    if not inspection.get('effectsAllowed', True):
        if not previous or digest(run) != digest(previous.run) or operator.get('delivery') != previous.operator.get('delivery'):
            raise StateError('coordinator-recovery-required', 'Only unchanged RUN and delivery can be committed during recovery')
    else:
        if previous:
            from .question_evidence import collect_run_pending, merge_pending_binding
            coordinator_effects = inspection.get('knownPendingEffects', [])
            retained = {row['actionId']: row for row in collect_run_pending(run, coordinator_effects)}
            for row in collect_run_pending(previous.run, coordinator_effects):
                candidate = retained.get(row['actionId'])
                if candidate is None or merge_pending_binding(row, candidate) != candidate:
                    raise ValueError('retained pending action binding cannot change')
        review = review_workflow(run)
        delivery = operator.get('delivery')
        if delivery and delivery['status'] == 'verified' and (not previous or delivery != previous.operator.get('delivery')):
            from .operation_selection import delivery_digest
            if not review['eligibleForCompletion'] or delivery['sourceDigest'] != delivery_digest(run, review):
                raise ValueError('verified delivery must bind the current eligible report')
        for approval in workflow.get('approvals', []):
            from .criteria_workflow import approval_digest
            kind = approval.get('kind')
            if kind in ('criteria', 'plan') and approval.get('digest') != approval_digest(workflow, kind):
                if not previous or approval not in previous.run['criteriaWorkflow'].get('approvals', []):
                    raise ValueError('approval does not match the current content')


def _stage(root, run, operator, gid, parent, commit_id, request, kind, payload, source, parent_hash=None):
    base = directory(generation_path(root, gid), create=True)
    files = {}
    for name, value in (('RUN.json', run), ('OPERATOR.json', operator)):
        json.dumps(value, allow_nan=False)
        data = canonical(value)
        immutable(base / name, data)
        files[name] = dict(sha256=checksum(data), bytes=len(data))
    manifest = dict(version=1, assessmentId=run['assessmentId'], generationId=gid,
                    parentGenerationId=parent, expectedGenerationId=parent, parentManifestSha256=parent_hash,
                    commitId=commit_id, requestDigest=request, requestKind=kind,
                    requestPayloadDigest=payload, files=files, source=source)
    path = base / 'manifest.json'
    try:
        existing = read_json(path)
    except FileNotFoundError:
        manifest['timestamp'] = datetime.now(timezone.utc).isoformat()
    else:
        manifest['timestamp'] = existing.get('timestamp')
    immutable(path, canonical(manifest))
    sync(base)
    sync(base.parent)
    sync(root)
    return manifest


def _publish(root, manifest):
    replace(root / 'current.json', canonical(dict(version=1, assessmentId=manifest['assessmentId'],
            generationId=manifest['generationId'], manifestSha256=digest(manifest))))
    snap = load_current(root)
    if snap.manifest != manifest:
        raise StateError('pointer-readback', 'Published pointer did not verify')
    return snap


def _receipt(snap, current, applied):
    return dict(assessmentId=snap.run['assessmentId'], generationId=snap.generation_id,
                currentGenerationId=current.generation_id, commitId=snap.manifest['commitId'],
                runRef=str(snap.run_path), operatorRef=str(snap.operator_path), alreadyApplied=applied)


def request_digest(parent, kind, payload):
    return digest(dict(expectedGenerationId=parent, kind=kind, payloadDigest=payload))


def committed_history(current):
    """Follow only hash-bound committed parents, newest first."""
    seen = set()
    snap = current
    while True:
        yield snap
        seen.add(snap.generation_id)
        parent = snap.manifest['parentGenerationId']
        if parent is None:
            return
        if parent in seen:
            raise StateError('ancestry-integrity', 'Generation ancestry has a cycle',
                             refs=[str(snap.run_path.parent / 'manifest.json')])
        parent_path = generation_path(current.state_dir, parent)
        parent_hash = snap.manifest.get('parentManifestSha256')
        if not isinstance(parent_hash, str) or not re.fullmatch('[a-f0-9]{64}', parent_hash):
            raise StateError('ancestry-integrity', 'Parent manifest hash is missing or invalid',
                             refs=[str(snap.run_path.parent / 'manifest.json')])
        snap = _generation(current.state_dir, parent, parent_hash)
        if snap.run['assessmentId'] != current.run['assessmentId']:
            raise StateError('ancestry-integrity', 'Foreign parent generation', refs=[str(parent_path)])


def find_receipt(current, commit_id, request):
    gid = identifier(commit_id)
    for snap in committed_history(current):
        if snap.generation_id == gid:
            if snap.manifest['commitId'] != commit_id or snap.manifest['requestDigest'] != request:
                raise conflict('commit-id-conflict', 'Commit ID is bound to a different request')
            return _receipt(snap, current, True)
    return None


def commit_snapshot(state_dir, *, expected_generation, commit_id, run, operator_state,
                    request_kind='state-commit', request_payload_digest=None):
    initial = load_current(state_dir)
    payload = request_payload_digest or digest([run, operator_state])
    request = request_digest(expected_generation, request_kind, payload)
    with coordinator_lock(initial.run), lock(initial.state_dir / 'store.lock'):
        current = load_current(initial.state_dir)
        receipt = find_receipt(current, commit_id, request)
        if receipt:
            sync(current.state_dir)
            return receipt
        if expected_generation != current.generation_id:
            raise conflict('stale-generation', 'Expected generation is no longer current')
        validate_snapshot(run, operator_state, current, repair_mutation=request_kind in
                          ('state-repair-open', 'state-repair-update'))
        manifest = _stage(current.state_dir, run, operator_state, identifier(commit_id),
                          expected_generation, commit_id, request, request_kind, payload,
                          current.manifest['source'], digest(current.manifest))
        snap = _publish(current.state_dir, manifest)
    receipt = _receipt(snap, snap, False)
    try:
        from .assessment_state_cli import render_current
        render_current(snap)
    except (OSError, ValueError, RuntimeError):
        receipt['projectionsPending'] = True
    return receipt


def register_store(registry_dir, state_dir, source_run, operator_state, *, registration_id):
    from .operator_state import default_operator
    source = Path(os.path.abspath(source_run))
    raw = read_bytes(source)
    run = json.loads(raw)
    aid = run['assessmentId']
    key = identifier(aid)
    gid = identifier(registration_id)
    registry = directory(registry_dir, create=True)
    sync(registry.parent)
    root = Path(os.path.abspath(state_dir))
    path = registry / (key + '.json')
    entry = dict(version=1, assessmentId=aid, storePath=str(root), registrationId=registration_id,
                 sourceRunPath=str(source), sourceRunSha256=checksum(raw))
    operator = default_operator(run) if operator_state == {} else operator_state
    provenance = dict(sourceRunPath=str(source), sourceRunSha256=checksum(raw), artifactBaseDir=str(source.parent))
    payload = digest([provenance, run, operator])
    request = request_digest(None, 'state-init', payload)
    with lock(registry / 'registry.lock'):
        try:
            existing = read_json(path)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if existing != entry:
                raise conflict('registration-conflict', 'Assessment already has a different registration')
            current = load_current(root)
            receipt = find_receipt(current, registration_id, request)
            if not receipt:
                raise StateError('registration-integrity', 'Registered genesis is missing')
            return receipt
    root = directory(root, create=True)
    sync(root.parent)
    with coordinator_lock(run), lock(root / 'store.lock'):
        pointer = root / 'current.json'
        if pointer.exists() or pointer.is_symlink():
            current = load_current(root)
            receipt = find_receipt(current, registration_id, request)
            if not receipt or current.run['assessmentId'] != aid:
                raise conflict('store-registration-conflict', 'Store belongs to another registration')
        else:
            reservation = dict(entry, requestDigest=request)
            immutable(root / 'registration.json', canonical(reservation))
            validate_snapshot(run, operator)
            manifest = _stage(root, run, operator, gid, None, registration_id, request, 'state-init', payload, provenance)
            current = _publish(root, manifest)
            receipt = _receipt(current, current, False)
    with lock(registry / 'registry.lock'):
        immutable(path, canonical(entry))
    return receipt


def resolve_store(registry_dir, assessment_id):
    path = directory(registry_dir) / (identifier(assessment_id) + '.json')
    entry = read_json(path)
    if entry.get('version') != 1 or entry.get('assessmentId') != assessment_id:
        raise StateError('registration-integrity', 'Registry assessment binding failed')
    snap = load_current(entry['storePath'])
    if (snap.run['assessmentId'] != assessment_id or any(
            entry[key] != snap.manifest['source'][key] for key in ('sourceRunPath', 'sourceRunSha256'))):
        raise StateError('registration-integrity', 'Registered store binding failed')
    genesis = _generation(snap.state_dir, identifier(entry['registrationId']))
    if genesis.manifest['requestKind'] != 'state-init' or genesis.manifest['parentGenerationId'] is not None or not find_receipt(
            snap, entry['registrationId'], genesis.manifest['requestDigest']):
        raise StateError('registration-integrity', 'Registered genesis is missing')
    return entry


def inspect_store(state_dir):
    snap = load_current(state_dir)
    try:
        count = sum(1 for _ in committed_history(snap))
    except StateError as exc:
        raise StateError('committed-history-integrity', 'Current snapshot verified, but committed history failed',
                         refs=exc.refs or [str(snap.run_path.parent / 'manifest.json')]) from exc
    return dict(integrity='clean', currentIntegrity='clean', historyIntegrity='clean',
                committedGenerationCount=count, assessmentId=snap.run['assessmentId'], generationId=snap.generation_id,
                runRef=str(snap.run_path), operatorRef=str(snap.operator_path))


def render_projections(snapshot, decision):
    from .assessment_state_cli import projection_text
    return projection_text(snapshot, decision)
