#!/usr/bin/env python3
"""Scan synthetic fixtures with local rules and compare exact ID/path/start.line.

No downloads/provisioning. Read installed scan --help first. Optional --prefix-json
supplies an already verified network guard. Work directory must be new and private.
"""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess


def annotated(source):
    positive, negative = set(), set()
    for number, line in enumerate(source.splitlines(), 1):
        marker = re.search(r"(?:ruleid|ok):\s*([\w, -]+)", line)
        if marker:
            target = positive if "ruleid:" in marker[0] else negative
            target.update((rid.strip(), number + 1) for rid in marker[1].split(","))
    return positive, negative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, required=True)
    parser.add_argument("--prefix-json", default="[]")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    work = args.work_dir.resolve()
    os.umask(0o077)
    work.mkdir(mode=0o700, parents=True, exist_ok=False)
    prefix = json.loads(args.prefix_json)
    env = os.environ.copy()
    env.update(SEMGREP_SETTINGS_FILE=str(work / "settings.yml"),
               SEMGREP_VERSION_CACHE_PATH=str(work / "version-cache"),
               SEMGREP_LOG_FILE=str(work / "semgrep.log"),
               SEMGREP_SEND_METRICS="off", SEMGREP_ENABLE_VERSION_CHECK="0", SEMGREP_APP_TOKEN="")
    blocks = {}
    for path in (root / "rules").glob("*.yml"):
        for rid, body in re.findall(r"^  - id: ([\w-]+)\n(.*?)(?=^  - id: |\Z)", path.read_text(), re.M | re.S):
            if rid in blocks:
                raise ValueError(f"duplicate rule id {rid}")
            blocks[rid] = f"  - id: {rid}\n{body}"
    shutil.copytree(root / "tests/fixtures", work / "cases")
    report = []
    for source in sorted((work / "cases").rglob("*")):
        if not source.is_file():
            continue
        positive, negative = annotated(source.read_text())
        limitations = {
            "compose.prod.yaml": ("config-compose-privileged", "rule basename filter"),
            "outside-language.py": ("nestjs-public-request-to-sql-text-local", "selected rule does not analyze Python"),
        }
        limitation = limitations.get(source.name) if not positive and not negative else None
        selected = {rid for rid, _ in positive | negative}
        if limitation:
            selected = {limitation[0]}
        if not selected:
            continue
        output = work / f"case-{len(report) + 1:02d}"
        output.mkdir(mode=0o700)
        config = output / "rules.yml"
        config.write_text("rules:\n" + "".join(blocks[rid] for rid in sorted(selected)))
        command = prefix + ["semgrep", "scan", "--oss-only", "--config", str(config),
            "--metrics=off", "--disable-version-check", "--strict", "--no-rewrite-rule-ids",
            "--verbose", "--time", "--json-output", str(output / "native.json"), str(source)]
        process = subprocess.run(command, cwd=work, env=env, capture_output=True)
        (output / "stdout.log").write_bytes(process.stdout)
        (output / "stderr.log").write_bytes(process.stderr)
        native = json.loads((output / "native.json").read_text())
        actual = {(r["check_id"], Path(r["path"]).resolve(), r["start"]["line"]) for r in native["results"]}
        expected = {(rid, source.resolve(), line) for rid, line in positive}
        forbidden = {(rid, source.resolve(), line) for rid, line in negative}
        scanned = {Path(p).resolve() for p in native.get("paths", {}).get("scanned", [])}
        passed = (process.returncode == 0 and native.get("errors") == []
                  and not native.get("skipped_rules") and actual == expected
                  and not actual & forbidden
                  and ((source.resolve() not in scanned) if limitation else (source.resolve() in scanned)))
        row = dict(fixture=str(source.relative_to(work / "cases")), exit_code=process.returncode,
            native_errors=len(native.get("errors", [])), scanned_files=len(scanned),
            expected_matches=len(expected), actual_matches=len(actual),
            negative_positions=len(forbidden), capability_limitation=limitation[1] if limitation else None, passed=passed)
        report.append(row)
        print(json.dumps(row))
        if not passed:
            print("missing:", sorted((r, str(p), n) for r, p, n in expected - actual))
            print("unexpected:", sorted((r, str(p), n) for r, p, n in actual - expected))
    (work / "fixture-results.json").write_text(json.dumps(report, indent=2) + "\n")
    raise SystemExit(0 if report and all(r["passed"] for r in report) else 1)


if __name__ == "__main__":
    main()
