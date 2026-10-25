"""Bounded readers for hostile test data. These functions never start producers."""
import json
from pathlib import Path


def read_jsonl(path):
    """JSONL is delimited by LF, not by Unicode separators inside JSON strings.

    Invalid outer records fail with their line number. Deliberately malformed
    HTTP bodies are strings within valid records and must remain available.
    """
    result = []
    for number, line in enumerate(Path(path).read_text().split('\n'), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as exc:
            raise ValueError(f'invalid JSONL record at line {number}') from exc
        if not isinstance(row, dict):
            raise ValueError(f'JSONL object required at line {number}')
        result.append(row)
    return result


def collect_alerts(fetch, total, *, page_size=100, max_pages=1000):
    """Read all native IDs, allowing an identical boundary overlap.

    fetch(start, count) returns native records. Advance by records received,
    including overlaps, rather than by unique IDs or a product-specific +1.
    Empty, repeated, conflicting and incomplete pages never become a full read.
    Call after producers/passive tasks stop; caller verifies total is stable.
    """
    if type(total) is not int or total < 0 or type(page_size) is not int or page_size < 1:
        raise ValueError('invalid alert pagination limits')
    found = {}; start = 0
    for _ in range(max_pages):
        if len(found) == total:
            return list(found.values())
        batch = fetch(start, page_size)
        if not isinstance(batch, list) or len(batch) > page_size:
            raise ValueError('invalid alert page')
        before = len(found)
        for row in batch:
            if not isinstance(row, dict) or row.get('id') is None:
                raise ValueError('native alert ID missing')
            key = str(row['id'])
            if key in found and found[key] != row:
                raise ValueError('native alert changed during pagination')
            found[key] = row
        if len(found) > total:
            raise ValueError('native alert count changed')
        if len(found) == before:
            raise ValueError('alert page made no progress; collection incomplete')
        start += len(batch)
    raise ValueError('alert page limit; collection incomplete')
