#!/usr/bin/env python3
"""Record whether the pinned image can run a reproducible Firefox journey."""

import argparse
import json
import shutil
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(); parser.add_argument("--out", required=True); args = parser.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=False)
    dependencies = {name: shutil.which(name) for name in ("firefox", "geckodriver")}
    missing = [name for name, path in dependencies.items() if path is None]
    status = "BLOCKED" if missing else "READY_FOR_SPIKE"
    result = {"schemaVersion": 1, "experiment": "browser-journey-v1",
              "status": status, "dependencies": dependencies,
              "missing": missing,
              "nextAction": ("Pin and package geckodriver matching Firefox, then run click/no-click controls"
                             if missing else "Implement and run the fixed click/no-click proxy journey")}
    (out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
