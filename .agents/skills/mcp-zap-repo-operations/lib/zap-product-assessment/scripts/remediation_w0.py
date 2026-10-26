#!/usr/bin/env python3
"""Offline W0 contract/baseline checks. This command has no live execution path.

This is a development checkpoint, not the v2 coverage or semantic verifier.
Historical evidence is read in place; no report bodies or credentials are emitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from jsonschema import Draft202012Validator

PACKAGE = Path(__file__).resolve().parents[1]
WORKSPACE = PACKAGE.parent


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def source_files(workspace):
    """Include nonignored additions; exclude runtime, secret sources and artifacts."""
    files = set()
    for repo in (workspace, workspace / 'mcp-zap-server'):
        names = subprocess.check_output([
            'git', '-C', str(repo), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'
        ]).decode().split('\0')
        for name in names:
            if not name:
                continue
            p = repo / name
            if not p.is_file() or p.is_symlink():
                continue
            rel = p.relative_to(workspace)
            if repo == workspace and rel.parts[0] != 'finalsource' and len(rel.parts) > 1:
                continue
            if any(x in rel.parts for x in ('node_modules', 'dist', '__pycache__')):
                continue
            if p.name.startswith('.env') and p.name != '.env.example':
                continue
            files.add(p)
    package = workspace / 'zap-product-assessment'
    for name in ('src', 'scripts', 'schemas', 'profiles', 'tests', 'docs', 'skills'):
        for p in (package / name).rglob('*'):
            if (p.is_file() and not p.is_symlink() and '__pycache__' not in p.parts
                    and not p.is_relative_to(package / 'docs/evidence')):
                files.add(p)
    files.update(package / name for name in ('.gitignore', 'pyproject.toml', 'requirements.lock'))
    return sorted(files)


def file_records(workspace, files):
    return [{'path': str(p.relative_to(workspace)), 'bytes': p.stat().st_size,
             'sha256': sha(p.read_bytes())} for p in files]


def verify_records(workspace, records):
    workspace = workspace.resolve()
    seen = set()
    for item in records:
        rel = Path(item['path'])
        if rel.is_absolute() or '..' in rel.parts or item['path'] in seen:
            raise ValueError('unsafe or duplicate baseline path')
        seen.add(item['path'])
        p = workspace / rel
        ancestors = [parent for parent in p.parents if parent.is_relative_to(workspace)]
        if any(parent.is_symlink() for parent in (p, *ancestors)):
            raise ValueError('symlink baseline path')
        if not p.resolve().is_relative_to(workspace.resolve()) or not p.is_file():
            raise ValueError('missing baseline file')
        blob = p.read_bytes()
        if len(blob) != item['bytes'] or sha(blob) != item['sha256']:
            raise ValueError('baseline content drift: ' + item['path'])
    return len(seen)


def verify_lock(plan_bytes, lock, runtime_bytes):
    if sha(plan_bytes) != lock['planSha256']:
        raise ValueError('locked plan drift')
    if sha(runtime_bytes) != lock['runtimeSha256']:
        raise ValueError('runtime/build inventory drift')


def verify_plan(plan, schema):
    Draft202012Validator(schema).validate(plan)
    if len(plan['caseIds']) != len(set(plan['caseIds'])):
        raise ValueError('duplicate case')
    if set(plan['caseIds']) != {f'C{i:02}' for i in range(1, 37)}:
        raise ValueError('minimum case catalog incomplete')
    rows = plan['operationActorDenominator']
    keys = {(r['method'], r['path'], r['actorRef']) for r in rows}
    expected = {(o['method'], o['path'], actor) for o in plan['operations']
                for actor in plan['actorRefs']}
    if keys != expected or len(rows) != len(keys):
        raise ValueError('required denominator mismatch')
    if len(plan['operations']) != len({(o['method'], o['path']) for o in plan['operations']}):
        raise ValueError('duplicate operation')
    tracks = {t['trackId']: t for t in plan['tracks']}
    required = {'api-ownership-business', 'active-controls', 'browser-business',
                'evidence-verification', 'regression', 'alternate-product'}
    if not required <= tracks.keys() or any(not tracks[k]['required'] for k in required):
        raise ValueError('required R2 track removed')
    if len(tracks) != len(plan['tracks']):
        raise ValueError('duplicate track')
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--live', action='store_true', help='always refused; offline command')
    args = parser.parse_args()
    if args.live:
        print(json.dumps({'status': 'blocked', 'reason': 'offline_only_no_live_authority',
                          'targetRequests': 0}))
        return 2
    root = args.checkpoint.resolve()
    try:
        load = lambda name: json.loads((root / name).read_bytes())
        lock = load('contract-lock.json')
        plan_bytes = (root / 'normalized-plan.json').read_bytes()
        verify_lock(plan_bytes, lock, (root / 'runtime-inventory.json').read_bytes())
        schema_bytes = (PACKAGE / 'schemas/remediation/w0-plan.schema.json').read_bytes()
        if sha(schema_bytes) != lock['schemaSha256']:
            raise ValueError('contract schema drift')
        rows = verify_plan(json.loads(plan_bytes), json.loads(schema_bytes))
        historical = verify_records(WORKSPACE, load('baseline-index.json')['artifacts'])
        original = verify_records(WORKSPACE, load('source-before.json')['files'])
        preservation = load('preservation.json')
        snapshot = Path(preservation['privateSnapshot'])
        if not snapshot.resolve().is_relative_to(PACKAGE / '.baseline'):
            raise ValueError('snapshot outside baseline directory')
        verify_records(snapshot, [
            {'path': item['name'], 'sha256': item['sha256'], 'bytes': item['bytes']}
            for item in preservation['files']])
        current = load('source-final.json')
        count = verify_records(WORKSPACE, current['files'])
        if {r['path'] for r in current['files']} != {
                str(p.relative_to(WORKSPACE)) for p in source_files(WORKSPACE)}:
            raise ValueError('source file inventory drift')
        for key, name in [('baselineSha256', 'baseline-index.json'),
                          ('sourceSha256', 'source-final.json'),
                          ('sourceBeforeSha256', 'source-before.json'),
                          ('preservationSha256', 'preservation.json'),
                          ('caseIndexSha256', 'case-index.json'),
                          ('endpointInventorySha256', 'endpoint-inventory.json')]:
            if sha((root / name).read_bytes()) != lock[key]:
                raise ValueError('checkpoint reference drift: ' + name)
        print(json.dumps({'status': 'pass', 'scope': 'G0-offline-development-only',
                          'sourceFiles': count, 'historicalArtifactsUnchanged': historical,
                          'originalSourceFilesUnchanged': original,
                          'requiredOperationActorRows': rows, 'targetRequests': 0,
                          'securityApproval': False, 'liveAssessmentPermitted': False}))
        return 0
    except Exception as exc:
        # Exceptions contain paths/reason codes only; never serialize input documents.
        print(json.dumps({'status': 'fail', 'reason': str(exc).splitlines()[0],
                          'targetRequests': 0, 'securityApproval': False}))
        return 1


if __name__ == '__main__':
    sys.exit(main())
