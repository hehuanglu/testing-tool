#!/usr/bin/env python3
"""One pinned W9 diagnostic entry point. Required browser never becomes optional."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import SimpleNamespace
import uuid

ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from zap_assessment.contracts import canonical, digest
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.verification import BundleReader, strict_json
from zap_assessment.journal import Journal
from zap_assessment.unified_contract import VERSION, TRACKS, REQUIRED, make_plan, validate_plan, binding_for, aggregate, require
from zap_assessment.unified_verification import check_child, post_state, verify_unified_bundle
from zap_assessment.active_verification import compare_active
import w6_business_campaign as business
import w7_ui_campaign as browser
import w8_active_campaign as active


def write(path, value): atomic_bytes(path, canonical(value))
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pins():
    names = [*sorted((ROOT / 'src/zap_assessment').rglob('*.py')),
             ROOT / 'src/zap_assessment/probes/TrafficProbe.java',
             *[ROOT / 'scripts' / name for name in ('w6_business_campaign.py', 'w7_ui_campaign.py', 'w8_active_campaign.py', 'w9_unified_campaign.py')],
             ROOT / 'schemas/remediation/ui-plan.schema.json', ROOT / 'schemas/remediation/business-fixture.schema.json', ROOT / 'profiles/runtime-baseline.json']
    return {str(p.relative_to(ROOT)): sha(p) for p in names}


def load_plan(path, pin):
    with BundleReader(Path(path).parent) as reader:
        raw = reader.read(Path(path).name); p = validate_plan(strict_json(raw)); reader.unchanged()
    require(canonical(p) == raw and hashlib.sha256(raw).hexdigest() == pin, 'external_plan_pin_mismatch')
    return p


def seal(root):
    rows = []
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.relative_to(root).as_posix() not in ('manifest.json', 'manifest.sha256'):
            b = p.read_bytes(); rows.append({'path': p.relative_to(root).as_posix(), 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()})
    raw = canonical({'contractVersion': VERSION, 'artifacts': rows}); atomic_bytes(root / 'manifest.json', raw)
    atomic_bytes(root / 'manifest.sha256', (hashlib.sha256(raw).hexdigest() + '\n').encode())


def prepare(path, seed, adapter, reverse, api_fault, ui_fault):
    path = path.resolve(); path.parent.mkdir(parents=True, exist_ok=True)
    image = json.loads((ROOT / 'profiles/runtime-baseline.json').read_bytes())['boundary']
    p = make_plan('w9-' + uuid.uuid4().hex, seed, adapter, reverse, image, source_pins(), api_fault, ui_fault)
    write(path, p); return {'plan': str(path), 'planHash': digest(p), 'assessmentId': p['assessmentId'], 'executableScope': 'owned-synthetic-diagnostic-only'}


def run(plan_path, pin, output):
    p = load_plan(plan_path, pin); require(p['sourcePins'] == source_pins(), 'source_drift_before_run')
    output = output.resolve(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    write(output / 'locked-plan.json', p)
    journal = Journal(output / 'journal.jsonl', p['assessmentId'], pin); journal.append('plan_locked', {'planHash': pin})
    rows = []
    try:
        s = os.statvfs(output); free = s.f_bavail * s.f_frsize; budget = p['resourceBudget']
        require(free >= 2 * budget['estimatedHostGrowthBytes'] + budget['reserveBytes'], 'host_disk_preflight_blocked')
        journal.append('preflight_passed', {'hostFreeBytes': free})
        for spec in p['tracks']:
            phase = spec['phase']; context = binding_for(p, phase); folder = output / 'tracks' / phase
            require(source_pins() == p['sourcePins'], 'source_drift_between_tracks')
            require([r['phase'] for r in rows] == spec['dependsOn'], 'track_dependency')
            journal.append('track_intent', {'phase': phase, 'bindingHash': digest(context), 'containerName': spec['containerName'],
                           'image': spec['image'], 'childRunId': spec['childRunId'], 'profileVolume': spec['profileVolume']})
            print(json.dumps({'assessmentId': p['assessmentId'], 'phase': phase, 'state': 'running'}), flush=True)
            if phase == 'api': business.run(folder, p['seed'], p['adapter'], p['reverse'], p['faults']['api'], context=context)
            elif phase in ('session', 'ui'):
                args = SimpleNamespace(output=folder, seed=p['seed'], adapter=p['adapter'], reverse=p['reverse'],
                    fault='fixed' if phase == 'session' else p['faults']['ui'], spike_only=phase == 'session',
                    session_spike=None if phase == 'session' else output / 'tracks/session/bundle',
                    expect_spike_plan_sha=None if phase == 'session' else rows[0]['childPlanHash'])
                browser.run(args, context=context)
            else: active.run(folder, p['seed'], phase.removeprefix('active-'), 'none', context=context)
            child_pin = sha(folder / 'locked-plan.json')
            row = check_child(p, phase, folder / 'bundle', child_pin); rows.append(row)
            journal.append('track_recorded', {'phase': phase, 'childPlanHash': child_pin, 'resultHash': digest(row['result']),
                                            'childManifestSha256': row['childManifestSha256']})
            print(json.dumps({'phase': phase, 'state': 'recorded', 'securityVerdict': row['result']['securityVerdict']}), flush=True)
        require(source_pins() == p['sourcePins'], 'source_drift_before_publication')
        closure = namespace_snapshot(p['assessmentId'])
        require(not closure['containers'] and not closure['volumes'], 'namespace_cleanup_unconfirmed')
        journal.append('namespace_clean', closure)
        pending = output / 'bundle.pending'; pending.mkdir(mode=0o700); (pending / 'children').mkdir()
        for phase in TRACKS: shutil.copytree(output / 'tracks' / phase / 'bundle', pending / 'children' / phase)
        post = post_state(pending / 'children'); journal.append('post_state_recorded', {'sha256': digest(post)})
        pair = compare_active(pending / 'children/active-vulnerable', rows[3]['childPlanHash'], pending / 'children/active-fixed', rows[4]['childPlanHash'])
        journal.append('verifying', {'requiredTracks': list(REQUIRED)})
        for name, value in [('plan.json', p), ('track-matrix.json', rows), ('post-state.json', post), ('active-pair.json', pair), ('result.json', aggregate(p, rows, True))]: write(pending / name, value)
        atomic_bytes(pending / 'journal.jsonl', (output / 'journal.jsonl').read_bytes())
        seal(pending); result = verify_unified_bundle(pending, pin); pending.rename(output / 'bundle')
        write(output / 'readback.json', result); return result
    except BaseException as exc:
        # A failure stays partial. No manufactured complete manifest or restart.
        write(output / 'partial-result.json', {'errorType': type(exc).__name__, 'planHash': pin,
              **aggregate(p, rows, False, interrupted=isinstance(exc, KeyboardInterrupt), cleanup_clean=False)})
        raise


def inspect(name):
    r = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=15)
    if r.returncode:
        # Distinguish absent identity from daemon outage; a failed list is not clean.
        listing = subprocess.run(['docker', 'ps', '-aq', '--no-trunc', '--filter', 'name=^' + name + '$'], capture_output=True, text=True, timeout=15)
        require(listing.returncode == 0 and not listing.stdout.strip(), 'docker_state_unknown')
        return None
    return json.loads(r.stdout)[0]


def inspect_volume(name):
    r = subprocess.run(['docker', 'volume', 'inspect', name], capture_output=True, text=True, timeout=15)
    if r.returncode:
        listing = subprocess.run(['docker', 'volume', 'ls', '-q', '--filter', 'name=^' + name + '$'], capture_output=True, text=True, timeout=15)
        require(listing.returncode == 0 and not listing.stdout.strip(), 'docker_volume_state_unknown')
        return None
    return json.loads(r.stdout)[0]


def namespace_snapshot(assessment_id):
    result = {'assessmentId': assessment_id, 'dockerStateObserved': True}
    for key, args in [('containers', ['ps', '-aq', '--no-trunc']), ('volumes', ['volume', 'ls', '-q'])]:
        r = subprocess.run(['docker', *args, '--filter', 'label=zpa.assessment=' + assessment_id], capture_output=True, text=True, timeout=15)
        require(r.returncode == 0, 'namespace_docker_state_unknown')
        result[key] = sorted(r.stdout.split())
    return result


def verify_owned(info, spec, plan, pin):
    labels = info.get('Config', {}).get('Labels') or {}
    require(info['Name'] == '/' + spec['containerName'] and info['Image'] == spec['image'] and bool(info['Id']), 'recovery_container_identity')
    require(all(labels.get(k) == v for k, v in {'zpa.run': spec['childRunId'], 'zpa.assessment': plan['assessmentId'], 'zpa.phase': spec['phase'], 'zpa.plan': pin}.items()), 'recovery_ownership_labels')
    if spec['profileVolume']:
        profiles = [m for m in info.get('Mounts', []) if m.get('Destination') == '/home/zap']
        require(len(profiles) == 1 and profiles[0].get('Type') == 'volume' and profiles[0].get('Name') == spec['profileVolume'], 'recovery_profile_mount')
    return info['Id']


def recover(run_path, pin, output):
    run_path = run_path.resolve(); p = load_plan(run_path / 'locked-plan.json', pin)
    output = output.resolve(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    original_paths = [run_path / 'journal.jsonl', *sorted((run_path / 'tracks').glob('*/journal.jsonl'))]
    before = {str(path): sha(path) for path in original_paths}
    original = Journal(run_path / 'journal.jsonl', p['assessmentId'], pin, allow_partial_tail=True)
    intents = [e['data']['phase'] for e in original.events if e['kind'] == 'track_intent']
    require(len(intents) == len(set(intents)) and intents == list(TRACKS[:len(intents)]), 'recovery_intent_graph')
    journal = Journal(output / 'recovery.jsonl', p['assessmentId'], pin); resources = []; rows = []; clean = True
    for phase in intents:
        spec = next(s for s in p['tracks'] if s['phase'] == phase); folder = run_path / 'tracks' / phase
        acknowledged = [e for e in original.events if e['kind'] == 'track_recorded' and e['data']['phase'] == phase]
        if acknowledged:
            row = check_child(p, phase, folder / 'bundle', acknowledged[0]['data']['childPlanHash'])
            require(digest(row['result']) == acknowledged[0]['data']['resultHash'], 'recovery_recorded_result'); rows.append(row)
        info = inspect(spec['containerName'])
        if info:
            cid = verify_owned(info, spec, p, pin)
            if spec['profileVolume']:
                volume = inspect_volume(spec['profileVolume']); require(volume is not None, 'recovery_profile_volume_missing')
                labels = volume.get('Labels') or {}
                require(all(labels.get(k) == v for k, v in {'zpa.run': spec['childRunId'], 'zpa.assessment': p['assessmentId'], 'zpa.plan': pin, 'zpa.phase': phase}.items()), 'recovery_profile_ownership_before_read')
            child_plan = strict_json((folder / 'locked-plan.json').read_bytes())
            require(child_plan['unifiedBinding'] == binding_for(p, phase), 'recovery_child_plan')
            # Reconcile an available creation ACK. A lost ACK uses exact name,
            # external-plan ownership labels and image, never a blind start.
            if (folder / 'journal.jsonl').exists():
                child_j = Journal(folder / 'journal.jsonl', spec['childRunId'], digest(child_plan), allow_partial_tail=True)
                acks = [e['data'] for e in child_j.events if e['kind'] == 'container_created']
                if acks: require(acks[-1].get('id') == cid, 'recovery_creation_ack')
            journal.append('stop_intent', {'phase': phase, 'id': cid, 'image': spec['image']})
            if phase.startswith('active-') and info['State']['Running']:
                code = "import pathlib,json; out={}; paths=['/zap/wrk/sender-events.jsonl','/fixture/boundary.jsonl','/fixture/arrivals.jsonl'];\nfor n in paths:\n p=pathlib.Path(n)\n if p.exists():\n  b=p.read_bytes();assert len(b)<=4*1024**2;out[n]=b.decode('utf-8')\nprint(json.dumps(out))"
                r = subprocess.run(['docker', 'exec', cid, 'python', '-c', code], capture_output=True, text=True, timeout=15)
                if r.returncode == 0: write(output / (phase + '-partial-captures.json'), {'classification': 'incomplete-prefix-never-coverage', 'captures': json.loads(r.stdout)})
            if info['State']['Running']: active.docker(['stop', '--time', '5', cid])
            stopped = inspect(spec['containerName']); require(stopped and stopped['Id'] == cid and not stopped['State']['Running'], 'stop_unconfirmed')
            if spec['profileVolume']:
                private = Path.home() / '.codex/private-evidence/mcp-zap' / (spec['childRunId'] + '-w9-recovery')
                private.mkdir(mode=0o700, parents=True, exist_ok=False); active.docker(['cp', cid + ':/home/zap/.', str(private)])
                index = []
                for path in sorted(private.rglob('*')):
                    require(not path.is_symlink(), 'recovery_private_profile_alias')
                    if path.is_file(): path.chmod(0o600); index.append({'path': str(path.relative_to(private)), 'bytes': path.stat().st_size, 'sha256': sha(path)})
                    elif path.is_dir(): path.chmod(0o700)
                write(private / 'private-index.json', {'files': index})
                write(output / (phase + '-private-retention.json'), {'path': str(private), 'indexSha256': sha(private / 'private-index.json'), 'sourceValuesIncluded': False})
            active.docker(['rm', cid]); require(inspect(spec['containerName']) is None, 'remove_unconfirmed')
            resources.append({'phase': phase, 'id': cid, 'stopped': True, 'removed': True})
            journal.append('stop_confirmed', resources[-1])
        if spec['profileVolume']:
            volume = inspect_volume(spec['profileVolume'])
            if volume is not None:
                labels = volume.get('Labels') or {}
                require(all(labels.get(k) == v for k, v in {'zpa.run': spec['childRunId'], 'zpa.assessment': p['assessmentId'], 'zpa.plan': pin, 'zpa.phase': phase}.items()), 'recovery_volume_ownership')
                if info:
                    active.docker(['volume', 'rm', spec['profileVolume']])
                    require(inspect_volume(spec['profileVolume']) is None, 'volume_remove_unconfirmed')
                else:
                    # No raw-profile reader was proven without its container.
                    clean = False; resources.append({'phase': phase, 'volume': spec['profileVolume'], 'quarantined': True})
    closure = namespace_snapshot(p['assessmentId'])
    if closure['containers'] or closure['volumes']: clean = False
    unchanged = all(sha(Path(path)) == h for path, h in before.items()); require(unchanged, 'recovery_modified_original_journal')
    result = {'mode': 'stop-only-no-auth-no-start-replay', 'originalJournalsUnchanged': unchanged,
              'originalJournalHashes': before, 'resources': resources, 'planHash': pin, 'assessmentId': p['assessmentId'],
              'namespaceClosure': closure,
              **aggregate(p, rows, False, interrupted=True, cleanup_clean=clean)}
    journal.append('recovery_complete', {'cleanupStatus': result['cleanupStatus'], 'originalJournalsUnchanged': unchanged})
    write(output / 'recovery-result.json', result); return result


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='mode', required=True)
    a = sub.add_parser('prepare'); a.add_argument('--output', type=Path, required=True); a.add_argument('--seed', type=int, required=True)
    a.add_argument('--adapter', choices=('finalsource-shaped', 'alternate-ledger'), default='finalsource-shaped'); a.add_argument('--reverse', action='store_true')
    a.add_argument('--fault-api', choices=('fixed', 'denied-mutated', 'denied-disclosure', 'list-leak'), default='fixed')
    a.add_argument('--fault-ui', choices=('fixed', 'wrong-balance', 'error-page', 'denied-mutated', 'denied-disclosure', 'no-submit'), default='fixed')
    a = sub.add_parser('run'); a.add_argument('--plan', type=Path, required=True); a.add_argument('--expect-plan-sha', required=True); a.add_argument('--output', type=Path, required=True)
    a = sub.add_parser('verify'); a.add_argument('--bundle', type=Path, required=True); a.add_argument('--expect-plan-sha', required=True)
    a = sub.add_parser('recover'); a.add_argument('--run-path', type=Path, required=True); a.add_argument('--expect-plan-sha', required=True); a.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    try:
        if args.mode == 'prepare': result = prepare(args.output, args.seed, args.adapter, args.reverse, args.fault_api, args.fault_ui)
        elif args.mode == 'run': result = run(args.plan, args.expect_plan_sha, args.output)
        elif args.mode == 'verify': result = verify_unified_bundle(args.bundle, args.expect_plan_sha)
        else: result = recover(args.run_path, args.expect_plan_sha, args.output)
        print(json.dumps(result))
        if args.mode == 'run': return 0 if result['orchestrationVerdict'] == 'verified' else 1
        if args.mode == 'recover': return 0 if result['cleanupStatus'] == 'clean' else 2
        return 0
    except Exception as exc:
        print(json.dumps({'errorType': type(exc).__name__, 'reason': str(exc)[:180], 'gateDecision': 'block'})); return 2


if __name__ == '__main__': sys.exit(main())
