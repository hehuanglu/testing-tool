#!/usr/bin/env python3
"""Reconcile the saved Docker inventory for this invocation."""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from run_zap_product_suite import CI_ADAPTER, SLUG, atomic_json, reconcile_inventory


def cleanup(root):
    suite_path = root / "suite-results.json"
    suite = json.loads(suite_path.read_text()) if suite_path.is_file() else None
    records = []
    failures = []
    for path in sorted(root.glob("*/inventory.json")):
        try:
            case_id = path.parent.name
            if path.is_symlink() or path.parent.is_symlink() or not SLUG.fullmatch(case_id):
                raise ValueError("invalid inventory path")
            inventory = json.loads(path.read_text(encoding="utf-8"))
            owner = inventory["owner"]
            if (not re.fullmatch(r"[0-9a-f]{32}-[0-9a-f]{8}", owner)
                    or inventory["adapter"] != CI_ADAPTER
                    or (suite and not owner.startswith(suite["runId"] + "-"))):
                raise ValueError("invalid inventory owner")
            short = owner[:12] + "-" + case_id[:20]
            if (inventory["containers"] != [f"zap-byteme-{role}-{short}"
                                            for role in ("scan", "ready", "app", "db")]
                    or inventory["network"] != "zap-byteme-" + short
                    or inventory["image"] != "testing-tool/byteme-zap:" + short):
                raise ValueError("invalid inventory resource")
            failures.extend(reconcile_inventory(inventory, records))
        except (OSError, KeyError, TypeError, ValueError) as error:
            failures.append(error)
    status = "UNVERIFIED" if failures else "COMPLETE" if records else "NO_INVENTORY"
    atomic_json(root / "fallback-cleanup.json", {"status": status, "records": records})
    return int(bool(failures))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    raise SystemExit(cleanup(parser.parse_args().root))
