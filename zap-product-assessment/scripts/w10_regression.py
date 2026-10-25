#!/usr/bin/env python3
"""Prepare, compare and independently replay pinned W10 offline A→B evidence."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / 'src'))
from zap_assessment.contracts import canonical
from zap_assessment.evidence import EvidenceInvalid
from zap_assessment.regression import make_request, reference, compare_request, read_document, VERSION
from zap_assessment.safety_io import atomic_bytes


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='command', required=True)
    prepare = sub.add_parser('prepare')
    prepare.add_argument('--baseline', type=Path); prepare.add_argument('--baseline-plan-sha')
    prepare.add_argument('--current', type=Path, required=True); prepare.add_argument('--current-plan-sha', required=True)
    prepare.add_argument('--kind', choices=('active', 'unified'), default='active')
    prepare.add_argument('--mode', choices=('enforce', 'seed'), default='enforce')
    prepare.add_argument('--scope-amendments', type=Path)
    prepare.add_argument('--output', type=Path, required=True)
    for command in ('compare', 'verify'):
        c = sub.add_parser(command); c.add_argument('--request', type=Path, required=True)
        c.add_argument('--expect-request-sha', required=True)
        if command == 'compare': c.add_argument('--output', type=Path, required=True)
        else: c.add_argument('--result', type=Path, required=True)
    args = p.parse_args(argv)
    try:
        if args.command == 'prepare':
            if bool(args.baseline) != bool(args.baseline_plan_sha): raise EvidenceInvalid('regression_baseline_pin_pair')
            if args.output.exists(): raise EvidenceInvalid('regression_output_exists')
            amendments = read_document(args.scope_amendments)[1] if args.scope_amendments else []
            r = make_request(reference(args.baseline, args.baseline_plan_sha) if args.baseline else None,
                             reference(args.current, args.current_plan_sha), args.kind, args.mode, amendments)
            raw = canonical(r); atomic_bytes(args.output, raw)
            print(json.dumps({'requestSha256': hashlib.sha256(raw).hexdigest(), 'request': str(args.output.absolute())})); return 0
        r = compare_request(args.request, args.expect_request_sha)
        if args.command == 'verify':
            if read_document(args.result)[0] != canonical(r): raise EvidenceInvalid('regression_result_disagrees_with_replay')
            print(json.dumps({'verified': True, 'gateDecision': r['gateDecision'], 'comparisonExitCode': r['exitCode']})); return 0
        # A directory is reserved exclusively, result published only after both sides replay.
        args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
        raw = canonical(r); atomic_bytes(args.output / 'result.json', raw)
        atomic_bytes(args.output / 'manifest.json', canonical({'contractVersion': VERSION, 'requestSha256': args.expect_request_sha,
                     'artifacts': [{'path': 'result.json', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}]}))
        print(json.dumps(r)); return r['exitCode']
    except (EvidenceInvalid, OSError, KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        # Never echo artifact contents, paths supplied by documents or secret values.
        reason = str(exc) if isinstance(exc, EvidenceInvalid) else 'regression_invalid_or_unreadable_input'
        print(json.dumps({'contractVersion': VERSION, 'evidenceStatus': 'invalid', 'gateDecision': 'block',
                          'reason': reason, 'exitCode': 2, 'R1R2Admission': False}), file=sys.stderr)
        return 2


if __name__ == '__main__': sys.exit(main())
