#!/usr/bin/env python3
"""Owned W8 active fixture. No product URL, credentials, shared ZAP or admission."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'src'))
from zap_assessment.active_fixture import fixture
from zap_assessment.active_verification import VERSION, IMAGE, audit_active, verify_active_bundle, compare_active
from zap_assessment.contracts import canonical, digest
from zap_assessment.journal import Journal
from zap_assessment.safety_io import atomic_bytes
from zap_assessment.unified_binding import validate_context, bind_fixture, docker_labels

FAULTS = ('none', 'invalid-seed', 'missing-parameter', 'guard-filter', 'missing-sink', 'disabled-rule')


def docker(args, timeout=30):
    r = subprocess.run(['docker', *args], capture_output=True, text=True, timeout=timeout)
    if r.returncode: raise RuntimeError('w8_docker_' + args[0] + '_failed')
    return r.stdout


def write(path, value): atomic_bytes(path, canonical(value))
def inspect(name): return json.loads(docker(['inspect', name]))[0]


def source_pins():
    names = [*sorted((ROOT / 'src/zap_assessment').glob('active_*.py')),
             *[ROOT / 'src/zap_assessment' / n for n in ('traffic.py', 'egress.py', 'verification.py', 'evidence.py', 'contracts.py', 'safety_io.py', 'journal.py', 'probes/TrafficProbe.java', 'unified_binding.py')], Path(__file__).resolve()]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in names}


def seal(root):
    rows = []
    for p in sorted(root.iterdir()):
        if p.name in ('manifest.json', 'manifest.sha256'): continue
        b = p.read_bytes(); rows.append({'path': p.name, 'bytes': len(b), 'sha256': hashlib.sha256(b).hexdigest()})
    raw = canonical({'contractVersion': VERSION, 'artifacts': rows}); atomic_bytes(root / 'manifest.json', raw)
    atomic_bytes(root / 'manifest.sha256', (hashlib.sha256(raw).hexdigest() + '\n').encode())


def run(output, seed, variant, fault, context=None):
    context = validate_context(context, {"active-vulnerable", "active-fixed"})
    output = Path(output).resolve(); output.mkdir(mode=0o700, parents=True, exist_ok=False)
    run_id = context['childRunId'] if context else 'w8-' + uuid.uuid4().hex; name = run_id + '-active'; config = fixture(seed)
    bind_fixture(context, digest(config))
    plan = {'contractVersion': VERSION, 'mode': 'owned-synthetic-active', 'runId': run_id, 'seed': seed,
            'variant': variant, 'fault': fault, 'fixtureHash': digest(config), 'sourcePins': source_pins(),
            'image': IMAGE, 'containerName': name, 'productRequestsPermitted': False, 'securityApproval': False,
            'scope': 'GET query only; real SQLite and HTML body sinks, anonymous network-none fixture',
            'startedAt': datetime.now(timezone.utc).isoformat()}
    if context: plan['unifiedBinding'] = context
    plan['targetBuildHash'] = digest({'source': plan['sourcePins']['src/zap_assessment/active_fixture.py'], 'variant': variant})
    write(output / 'locked-plan.json', plan); write(output / 'job.json', {'plan': plan, 'fixture': config}); (output / 'job.json').chmod(0o444)
    fs = os.statvfs(output); free = fs.f_bavail * fs.f_frsize
    write(output / 'resource-preflight.json', {'hostFreeBytes': free, 'estimatedGrowthBytes': 32 * 1024**2,
          'reserveBytes': 2 * 1024**3, 'memoryLimitBytes': 1536 * 1024**2,
          'classification': 'bounded tmpfs diagnostic; no new G6 operational calibration/admission'})
    if free < 2 * 32 * 1024**2 + 2 * 1024**3: raise RuntimeError('w8_host_disk_preflight_blocked')
    if docker(['image', 'inspect', IMAGE, '--format', '{{.Id}}']).strip() != IMAGE: raise RuntimeError('w8_image_pin')
    journal = Journal(output / 'journal.jsonl', run_id, digest(plan)); journal.append('plan_locked', {'planHash': digest(plan)})
    cid = None; observation = None; cleanup = None; host_samples = []
    try:
        journal.append('container_create_intent', {'name': name, 'image': IMAGE, 'runId': run_id})
        cid = docker(['run', '-d', '--name', name, '--label', 'zpa.run=' + run_id, '--label', 'zpa.mode=w8-owned-active',
            *docker_labels(context), '--network', 'none', '--read-only', '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--user', '1000:1000',
            '--memory', '1536m', '--memory-swap', '1536m', '--cpus', '2', '--pids-limit', '256', '--ulimit', 'core=0',
            '--log-driver', 'json-file', '--log-opt', 'max-size=1m', '--log-opt', 'max-file=1',
            '--tmpfs', '/work:rw,nosuid,size=64m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/home/zap:rw,nosuid,size=512m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/zap/wrk:rw,nosuid,size=64m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/fixture:rw,nosuid,size=32m,uid=1000,gid=1000,mode=0700',
            '--tmpfs', '/tmp:rw,exec,nosuid,size=128m,uid=1000,gid=1000,mode=1777',
            '--mount', 'type=bind,src=' + str(ROOT / 'src') + ',dst=/source,readonly',
            '--mount', 'type=bind,src=' + str(output / 'job.json') + ',dst=/job.json,readonly',
            '--env', 'PYTHONPATH=/source', '--env', 'PYTHONDONTWRITEBYTECODE=1', '--env', 'HOME=/home/zap',
            '--entrypoint', 'python', IMAGE, '-m', 'zap_assessment.active_worker']).strip()
        info = inspect(cid)
        if info['Id'] != cid or info['Config']['Labels'].get('zpa.run') != run_id or info['Image'] != IMAGE: raise RuntimeError('w8_create_identity')
        journal.append('container_created', {'id': cid, 'name': name, 'image': info['Image'], 'runId': run_id})
        deadline = time.monotonic() + 350
        while True:
            fs = os.statvfs(output); host_samples.append({'at': time.monotonic(), 'freeBytes': fs.f_bavail * fs.f_frsize})
            if host_samples[-1]['freeBytes'] < 2 * 1024**3: raise RuntimeError('w8_disk_reserve_latch')
            ready = subprocess.run(['docker', 'exec', cid, 'test', '-f', '/work/result.json'], capture_output=True, timeout=5)
            if ready.returncode == 0: break
            if not inspect(cid)['State']['Running'] or time.monotonic() >= deadline: raise RuntimeError('w8_worker_deadline')
            time.sleep(.5)
        script = 'import pathlib,sys; b=pathlib.Path("/work/result.json").read_bytes(); assert len(b)<=16*1024**2; sys.stdout.buffer.write(b)'
        raw = subprocess.run(['docker', 'exec', cid, 'python', '-c', script], capture_output=True, timeout=15)
        if raw.returncode or len(raw.stdout) > 16 * 1024**2: raise RuntimeError('w8_export_budget')
        atomic_bytes(output / 'worker-result.json', raw.stdout); observation = json.loads(raw.stdout)
    finally:
        # Reconcile an uncertain create ACK by exact name + ownership + image.
        if cid is None:
            probe = subprocess.run(['docker', 'inspect', name], capture_output=True, text=True, timeout=10)
            if probe.returncode == 0:
                found = json.loads(probe.stdout)[0]
                if found['Config']['Labels'].get('zpa.run') == run_id and found['Image'] == IMAGE: cid = found['Id']
        if cid:
            info = inspect(cid)
            if info['Id'] != cid or info['Config']['Labels'].get('zpa.run') != run_id or info['Image'] != IMAGE: raise RuntimeError('w8_cleanup_ownership')
            journal.append('container_stop_intent', {'id': cid})
            if info['State']['Running']: docker(['stop', '--time', '5', cid])
            stopped = inspect(cid)
            if stopped['State']['Running']: raise RuntimeError('w8_stop_unconfirmed')
            cleanup = {'id': cid, 'name': name, 'runId': run_id, 'image': IMAGE, 'networkMode': info['HostConfig']['NetworkMode'],
                       'readOnlyRoot': info['HostConfig']['ReadonlyRootfs'], 'oomKilled': stopped['State']['OOMKilled'], 'containerRemoved': False}
            journal.append('container_remove_intent', {'id': cid}); docker(['rm', cid])
            cleanup['containerRemoved'] = not docker(['ps', '-aq', '--no-trunc', '--filter', 'id=' + cid]).strip()
            write(output / 'cleanup.json', cleanup); journal.append('cleanup_confirmed', cleanup)
        write(output / 'host-samples.json', host_samples)
    if not observation or 'workerFailure' in observation: raise RuntimeError('w8_worker_failure_see_preserved_result')
    if source_pins() != plan['sourcePins']: raise RuntimeError('w8_source_changed_during_run')
    result = audit_active(plan, config, observation, cleanup)
    bundle = output / 'bundle.pending'; bundle.mkdir()
    for filename, value in [('plan', plan), ('fixture', config), ('observations', observation), ('cleanup', cleanup), ('result', result)]: write(bundle / (filename + '.json'), value)
    seal(bundle); readback = verify_active_bundle(bundle, digest(plan)); bundle.rename(output / 'bundle')
    write(output / 'readback.json', readback)
    return {'planHash': digest(plan), 'bundle': str(output / 'bundle'), **result}


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='mode', required=True)
    r = sub.add_parser('run'); r.add_argument('--output', type=Path, required=True); r.add_argument('--seed', type=int, default=8101)
    r.add_argument('--variant', choices=('vulnerable', 'fixed'), required=True); r.add_argument('--fault', choices=FAULTS, default='none')
    v = sub.add_parser('verify'); v.add_argument('--bundle', type=Path, required=True); v.add_argument('--expect-plan-sha', required=True)
    c = sub.add_parser('compare'); c.add_argument('--vulnerable', type=Path, required=True); c.add_argument('--vulnerable-plan-sha', required=True)
    c.add_argument('--fixed', type=Path, required=True); c.add_argument('--fixed-plan-sha', required=True); c.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.mode == 'run':
        result = run(a.output, a.seed, a.variant, a.fault); expected = result['G9Synthetic'] == ('pass' if a.fault == 'none' else 'blocked')
    elif a.mode == 'verify': result = verify_active_bundle(a.bundle, a.expect_plan_sha); expected = True
    else:
        result = compare_active(a.vulnerable, a.vulnerable_plan_sha, a.fixed, a.fixed_plan_sha); write(a.output, result); expected = result['G9Synthetic'] == 'pass'
    print(json.dumps(result)); return 0 if expected else 2


if __name__ == '__main__': sys.exit(main())
