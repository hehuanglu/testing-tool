#!/usr/bin/env python3
"""Run one fixture case in an owned, network-disabled container and retain its CI result."""

import argparse
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from runner import EXIT, METHODS, SCENARIOS, failed_checks, finish, result_for
CONTAINER_TIMEOUT = 220


def docker_run(scenario, image):
    name = f"zap-feasibility-{uuid4().hex}"
    command = [
        "docker", "run", "--rm", "--name", name, "--pull", "never", "--network", "none",
        "--hostname", "localhost", "--entrypoint", "python3", "-e", "PYTHONPATH=/suite", "-v", f"{ROOT}:/suite:ro",
        image, "/suite/feasibility/runner.py", scenario,
    ]
    try:
        process = subprocess.run(command, capture_output=True, timeout=CONTAINER_TIMEOUT)
    except subprocess.TimeoutExpired:
        subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=15, check=False)
        return failed_checks(result_for(scenario), "CONTAINER_TIMEOUT")
    result = result_for(scenario)
    if process.returncode not in EXIT.values():
        result["evidence"]["containerExit"] = process.returncode
        return failed_checks(result, "INFRASTRUCTURE_FAILURE")
    try:
        child = json.loads(process.stdout)
        check_names = {"authenticatedActive"} if scenario == "active-blocked" else set(METHODS)
        if (child["schemaVersion"] != 1 or child["scenario"] != scenario
                or type(child["exitCode"]) is not int or child["exitCode"] != process.returncode
                or EXIT[child["verdict"]] != process.returncode
                or set(child["checks"]) != check_names or not isinstance(child["evidence"], dict)):
            raise ValueError("untrusted result")
        recomputed = finish({"checks": child["checks"]})
        if (recomputed["verdict"], recomputed["decisiveChecks"]) != (
                child["verdict"], child["decisiveChecks"]):
            raise ValueError("miscomputed result")
        if child["verdict"] == "PASS" and any(row["verdict"] != "PASS"
                                              for row in child["checks"].values()):
            raise ValueError("unknown check verdict")
    except (KeyError, ValueError, TypeError):
        reason = "MISSING_EVIDENCE" if not process.stdout.strip() else "INVALID_EVIDENCE"
        result["evidence"]["containerExit"] = process.returncode
        return failed_checks(result, reason)
    return child


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=SCENARIOS)
    parser.add_argument("--out", type=Path, required=True, help="a new result JSON file")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must be a new file")
    image = (ROOT / "zap-image.txt").read_text(encoding="utf-8").strip()
    try:
        result = docker_run(args.scenario, image)
    except (OSError, subprocess.SubprocessError):
        result = failed_checks(result_for(args.scenario), "INFRASTRUCTURE_FAILURE")
    result["evidence"]["scannerImage"] = image
    try:
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(result, output, indent=2, sort_keys=True)
            output.write("\n")
    except OSError:
        print("ERROR EVIDENCE_WRITE_FAILURE", file=sys.stderr)
        return EXIT["ERROR"]
    print(f'{result["verdict"]} {args.out}')
    return result["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
