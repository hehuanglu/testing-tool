#!/usr/bin/env python3
"""Run each scenario twice and keep both raw CI outcomes and their qualification verdict."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EXPECTED = {
    "baseline": (0, "automation", "ASSERTIONS_SATISFIED", 0),
    "public-csp-regression": (1, "passive", "CSP_REGRESSION", 0),
    "private-csp-regression": (1, "authenticatedPassive", "CSP_REGRESSION", 0),
    "coverage-regression": (1, "apiExploration", "API_LINK_MISSING", 0),
    "authorization-regression": (1, "authorization", "AUTHORIZATION_ASSERTION_VIOLATED", 0),
    "bad-password": (2, "authenticatedPassive", "AUTHENTICATION_FAILURE", 2),
    "warning": (2, "automation", "SCANNER_WARNING", 2),
    "bad-plan": (2, "automation", "PLAN_VALIDATION_FAILURE", None),
    "scanner-failure": (2, "automation", "SCANNER_FAILURE", -9),
    "incomplete": (2, "passive", "INCOMPLETE_EXECUTION", 0),
    "missing-evidence": (2, "automation", "MISSING_EVIDENCE", 0),
    "invalid-evidence": (2, "automation", "INVALID_EVIDENCE", 0),
    "active-blocked": (3, "authenticatedActive", "ACTIVE_EXECUTION_RESTRICTED", None),
}


def qualify(destination, repetition, scenario):
    path = destination / f"{repetition}-{scenario}.json"
    process = subprocess.run([sys.executable, str(HERE / "run.py"), scenario, "--out", str(path)],
                             check=False, capture_output=True, text=True, timeout=245)
    result = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    exit_code, check_name, reason, native_exit = EXPECTED[scenario]
    matched = bool(result and process.returncode == result["exitCode"] == exit_code
                   and result["checks"][check_name]["reason"] == reason
                   and result["evidence"].get("execution", {}).get("exit") == native_exit)
    print(f'{repetition} {scenario} {result["verdict"] if result else "missing"} '
          f'({"matched" if matched else "unexpected"})', flush=True)
    return {
        "repetition": repetition, "scenario": scenario, "observedProcessExit": process.returncode,
        "expected": {"exitCode": exit_code, "check": check_name, "reason": reason,
                     "nativeExit": native_exit},
        "matched": matched, "result": result,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True, help="new directory for the qualification")
    parser.add_argument("--workers", type=int, choices=range(1, 5), default=3)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    jobs = [(args.out, repeat, scenario) for repeat in (1, 2) for scenario in EXPECTED]
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        runs = list(executor.map(lambda job: qualify(*job), jobs))

    # Assertions and classifications must agree across both clean executions of a scenario.
    pairs = {scenario: [run["result"] for run in runs if run["scenario"] == scenario]
             for scenario in EXPECTED}
    repeatable = {scenario: all(pair) and pair[0]["checks"] == pair[1]["checks"]
                  for scenario, pair in pairs.items()}
    qualified = all(run["matched"] for run in runs) and all(repeatable.values())
    summary = {"schemaVersion": 1, "qualificationPassed": qualified,
               "repeatableVerdicts": repeatable, "runs": runs}
    (args.out / "qualification.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0 if qualified else 1


if __name__ == "__main__":
    sys.exit(main())
