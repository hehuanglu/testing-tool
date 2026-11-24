"""Create a receipt from reviewed, filtered artifacts and a recorded process exit."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

from .execution import ExecutionError
from .manifest import ROOT, read_suite, require
from .project import COMMIT
from .receipt import artifact, suite_receipt


def framework_inputs(root, revision=None):
    top = root.parents[1]
    commit = subprocess.check_output(["git", "-C", str(top), "rev-parse", "HEAD"], timeout=10).decode().strip()
    status = subprocess.check_output(["git", "-C", str(top), "status", "--porcelain", "--untracked-files=all"],
                                     timeout=10)
    require(COMMIT.fullmatch(commit) and (revision is None or (revision == commit and not status)),
            "framework revision and cleanliness")
    return {"revision": commit, "clean": not status, "checkoutStatusSha256": sha256(status).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True, help="new receipt JSON path")
    parser.add_argument("--exit-code", type=int, required=True, help="exit observed by the invoking shell")
    source = parser.add_subparsers(dest="format", required=True)
    shared = source.add_parser("shared")
    shared.add_argument("result", type=Path)
    shared.add_argument("--input-root", type=Path, default=ROOT, help="tests/security at the source revision")
    shared.add_argument("--framework-revision", help="require a clean checkout of this SHA")
    product = source.add_parser("bus-booking-native")
    product.add_argument("directory", type=Path)
    product.add_argument("--project", type=Path, required=True, help="Git checkout containing the source commit")
    product.add_argument("--project-revision", required=True)
    product.add_argument("--mode", choices=("full", "long"), required=True)
    product.add_argument("--acceptance-gate", action="store_true", help="source ran with --require-acceptance")
    args = parser.parse_args(argv)

    try:
        if args.format == "shared":
            result, digest = artifact(args.result)
            root = args.input_root.resolve()
            framework = framework_inputs(root, args.framework_revision)
            suite = read_suite(result["suite"], result["scenario"], root=root)
            record = suite_receipt(result, suite, args.exit_code, digest, framework)
        else:
            from suites.bus_booking.native_evidence import HAR_PASSIVE_RECEIPT

            record = HAR_PASSIVE_RECEIPT.run(None, (), (
                args.directory, args.project, args.project_revision, args.mode, args.exit_code, args.acceptance_gate))
        record["provenance"]["validator"] = {
            "python": platform.python_version(), "os": platform.system(), "architecture": platform.machine(),
            "environment": "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local",
        }
        with args.out.open("x", encoding="utf-8") as stream:
            json.dump(record, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ExecutionError, subprocess.SubprocessError):
        print("ERROR RECEIPT_VALIDATION_FAILURE", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
