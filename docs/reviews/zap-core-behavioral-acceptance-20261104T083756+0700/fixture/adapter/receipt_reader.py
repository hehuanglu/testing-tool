"""Offline fixture reader for captured and retained receipts."""
import argparse
import json
from pathlib import Path


def read_receipt(path, action, case, object_ref):
    envelope = json.loads(Path(path).read_bytes())
    if not isinstance(envelope, dict) or envelope.get('synthetic') is not True:
        raise ValueError('synthetic receipt envelope required')
    payload = envelope.get('payload')
    if not isinstance(payload, dict):
        raise ValueError('nested fixture receipt required')
    if (payload.get('actionId'), payload.get('caseId'), payload.get('objectRef')) != (action, case, object_ref):
        raise ValueError('receipt action, case or object mismatch')
    if payload.get('terminal') is not True:
        raise ValueError('receipt terminal marker missing')
    return payload


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('path', 'action', 'case', 'object_ref'):
        parser.add_argument(name)
    args = parser.parse_args()
    try:
        print(json.dumps(read_receipt(args.path, args.action, args.case, args.object_ref), sort_keys=True))
    except ValueError as exc:
        parser.exit(2, str(exc) + '\n')
