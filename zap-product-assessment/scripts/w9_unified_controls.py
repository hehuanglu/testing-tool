#!/usr/bin/env python3
"""Offline semantic/tamper controls on actual W9 evidence. Zero product traffic."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
ROOT = Path(__file__).resolve().parents[1]; sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'scripts')]
from zap_assessment.contracts import canonical, digest
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.unified_verification import verify_unified_bundle
from w9_unified_campaign import seal


def read(path): return json.loads(path.read_bytes())
def put(path, value): path.write_bytes(canonical(value))


def reseal(folder):
    for name in ('manifest.json', 'manifest.sha256'): (folder / name).unlink(missing_ok=True)
    seal(folder)


def rechain(path):
    rows = [json.loads(line) for line in path.read_bytes().splitlines()]; previous = '0' * 64
    for i, row in enumerate(rows):
        row.pop('hash', None); row['seq'] = i; row['prev'] = previous; row['hash'] = digest(row); previous = row['hash']
    path.write_bytes(b''.join(canonical(r) + b'\n' for r in rows))


def refresh_child_metadata(folder):
    matrix = read(folder / 'track-matrix.json')
    for row in matrix:
        child = folder / 'children' / row['phase']
        if (child / 'manifest.json').exists():
            row['childManifestSha256'] = hashlib.sha256((child / 'manifest.json').read_bytes()).hexdigest()
            row['childPlanHash'] = hashlib.sha256((child / 'plan.json').read_bytes()).hexdigest()
    put(folder / 'track-matrix.json', matrix)


def run(bundle, pin, other, other_pin, output):
    output.mkdir(mode=0o700, parents=True, exist_ok=False); cases = []
    a = verify_unified_bundle(bundle, pin); b = verify_unified_bundle(other, other_pin)
    pa = read(bundle / 'plan.json'); pb = read(other / 'plan.json')
    same_source = pa['sourcePins'] == pb['sourcePins']
    ids_a = {str(r['wireId']) for r in pa['tracks'][1]['scope']['resources']}
    ids_b = {str(r['wireId']) for r in pb['tracks'][1]['scope']['resources']}
    fresh = a['assessmentId'] != b['assessmentId'] and not ids_a & ids_b and same_source
    cases.append({'case': 'two-fresh-runs-distinct-IDs-same-source', 'expected': True, 'observed': fresh, 'pass': fresh})
    cases.append({'case': 'required-browser-secret-failure-blocks-operational-G10', 'expected': True,
                  'observed': a['G10Operational'] == b['G10Operational'] == 'blocked' and a['securityVerdict'] == b['securityVerdict'] == 'fail',
                  'pass': a['G10Operational'] == b['G10Operational'] == 'blocked' and a['securityVerdict'] == b['securityVerdict'] == 'fail'})
    def control(name, mutate):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary) / 'bundle'; shutil.copytree(bundle, folder)
            try:
                mutate(folder); refresh_child_metadata(folder); reseal(folder); verify_unified_bundle(folder, pin); observed = 'accepted'
            except (EvidenceInvalid, OSError): observed = 'reject'
        cases.append({'case': name, 'expected': 'reject', 'observed': observed, 'pass': observed == 'reject'})
    def change(path, fn):
        value = read(path); fn(value); put(path, value)
    def leaf(folder, phase, name, fn):
        child = folder / 'children' / phase; change(child / name, fn); reseal(child)
    control('missing-required-browser-track', lambda f: change(f / 'track-matrix.json', lambda v: v.pop(2)))
    control('post-state-missing', lambda f: (f / 'post-state.json').unlink())
    control('post-state-from-wrong-branch', lambda f: change(f / 'post-state.json', lambda v: v['branches'][0].update({'postStateHash': '0' * 64})))
    control('summary-cannot-erase-observed-security-failure', lambda f: change(f / 'result.json', lambda v: v.update({'securityVerdict': 'pass', 'gateDecision': 'allow'})))
    control('missing-required-phase-not-overridden-by-pass-summary', lambda f: change(f / 'track-matrix.json', lambda v: v.pop()))
    control('wrong-phase-binding-after-rehash', lambda f: leaf(f, 'ui', 'observations.json', lambda v: v['unifiedBinding'].update({'phase': 'api'})))
    control('foreign-parent-plan-after-rehash', lambda f: leaf(f, 'api', 'observations.json', lambda v: v['unifiedBinding'].update({'planHash': '0' * 64})))
    control('wrong-child-source', lambda f: leaf(f, 'ui', 'plan.json', lambda v: v['sourcePins'].update({'src/zap_assessment/ui_fixture.py': '0' * 64})))
    control('wrong-actor-observation', lambda f: leaf(f, 'api', 'observations.json', lambda v: v['cases'][0]['identity'].update({'actorRef': 'B'})))
    control('wrong-resource-ID', lambda f: leaf(f, 'ui', 'fixture.json', lambda v: v['resources'][0].update({'wireId': 'foreign'})))
    control('cleanup-missing', lambda f: (f / 'children/ui/cleanup.json').unlink())
    control('cleanup-unconfirmed', lambda f: leaf(f, 'ui', 'cleanup.json', lambda v: v.update({'containerRemoved': False})))
    control('UI-submit-cannot-be-replaced-by-API', lambda f: leaf(f, 'ui', 'observations.json', lambda v: v['steps'][1].update({'commandKinds': []})))
    control('actual-browser-cannot-be-unit-contract-corpus', lambda f: leaf(f, 'ui', 'observations.json', lambda v: v.update({'evidenceKind': 'unit-contract-corpus'})))
    control('session-spike-from-other-assessment', lambda f: leaf(f, 'ui', 'plan.json', lambda v: v.update({'spikePlanHash': '1' * 64})))
    control('wrong-active-build', lambda f: leaf(f, 'active-fixed', 'observations.json', lambda v: v.update({'targetBuildHash': '0' * 64})))
    control('active-track-result-cannot-hide-missing-coverage', lambda f: leaf(f, 'active-fixed', 'result.json', lambda v: v.update({'techniqueVerdict': 'blocked'})))
    def old_ui(f):
        child = f / 'children/ui'; shutil.rmtree(child); shutil.copytree(other / 'children/ui', child)
    control('old-run-UI-even-with-updated-child-hashes', old_ui)
    def failed_phase(f):
        change(f / 'track-matrix.json', lambda rows: rows[2]['result'].update({'securityVerdict': 'pass', 'functionalVerdict': 'pass'}))
        journal = f / 'journal.jsonl'; data = [json.loads(line) for line in journal.read_bytes().splitlines()]
        rows = read(f / 'track-matrix.json')
        for event in data:
            if event['kind'] == 'track_recorded' and event['data']['phase'] == 'ui': event['data']['resultHash'] = digest(rows[2]['result'])
        journal.write_bytes(b''.join(canonical(e) + b'\n' for e in data)); rechain(journal)
    control('phase-security-failure-not-erased-by-rechained-journal', failed_phase)
    def remove_state(f):
        path = f / 'journal.jsonl'; values = [json.loads(line) for line in path.read_bytes().splitlines()]
        values = [r for r in values if r['kind'] != 'verifying']; path.write_bytes(b''.join(canonical(v) + b'\n' for v in values)); rechain(path)
    control('verification-state-required-after-rechain', remove_state)
    control('symlink-artifact', lambda f: ((f / 'post-state.json').unlink(), (f / 'post-state.json').symlink_to(bundle / 'post-state.json')))
    for name, wrong in [('missing-external-plan-pin', None), ('wrong-external-plan-pin', '0' * 64)]:
        try: verify_unified_bundle(bundle, wrong); observed = 'accepted'
        except EvidenceInvalid: observed = 'reject'
        cases.append({'case': name, 'expected': 'reject', 'observed': observed, 'pass': observed == 'reject'})
    result = {'classification': 'offline-controls-on-actual-unified-bundles', 'targetRequests': 0,
              'allExpected': all(c['pass'] for c in cases), 'cases': cases, 'securityApproval': False}
    put(output / 'controls.json', result); return result


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--bundle', type=Path, required=True); p.add_argument('--expect-plan-sha', required=True)
    p.add_argument('--other-bundle', type=Path, required=True); p.add_argument('--other-plan-sha', required=True); p.add_argument('--output', type=Path, required=True)
    args = p.parse_args(); r = run(args.bundle.resolve(), args.expect_plan_sha, args.other_bundle.resolve(), args.other_plan_sha, args.output.resolve())
    print(json.dumps(r)); sys.exit(0 if r['allExpected'] else 2)
