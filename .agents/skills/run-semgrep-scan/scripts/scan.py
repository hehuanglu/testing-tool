"""Portable, local-only Semgrep batch with frozen runs and read-only verification."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SKILL = Path(__file__).resolve().parents[1]
ROOT = SKILL.parents[2]
TRACKS = {
    "be-public-static": "finalsource/be",
    "fe-public-static": "finalsource/fe",
    "be-auth-static": "finalsource/be",
    "authorization-ownership-static": "finalsource/be",
    "supply-chain-config-static": "finalsource",
}
EXCLUDED_DIRS = {"node_modules", "dist", "coverage", ".git", "__pycache__"}
EXCLUDES = ("node_modules", "dist", "coverage", "**/.env", "**/.env.*",
            "**/*.spec.ts", "**/*.test.ts", "**/*.spec.tsx", "**/*.test.tsx")
POLICY = "(version 1)\n(allow default)\n(deny network*)\n"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value: dict) -> None:
    temporary = path.with_name(path.name + "." + uuid4().hex + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    os.replace(temporary, path)


def read(path: Path) -> dict:
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def product(value: str) -> Path:
    supplied = Path(value).expanduser().absolute()
    if supplied != supplied.resolve():
        raise ValueError("product path contains symlinks")
    root = supplied.parent if supplied.name == "finalsource" else supplied
    if root != ROOT:
        raise ValueError("this skill operates only on its containing repository")
    for name in ("finalsource/fe", "finalsource/be", "finalsource/compose.yaml"):
        if not (root / name).exists():
            raise ValueError(f"product path missing: {name}")
    return root


def gitdir(root: Path) -> Path:
    result = subprocess.run(["git", "-C", str(root), "rev-parse", "--absolute-git-dir"],
                            check=True, capture_output=True, text=True)
    path = Path(result.stdout.strip()).resolve()
    if not path.is_dir():
        raise ValueError("Git metadata directory unavailable")
    return path


def files(root: Path, source: str) -> dict[str, str]:
    base = root / source
    if not base.is_dir() or base.is_symlink():
        raise ValueError(f"source root missing or linked: {source}")
    found = {}
    for current, dirs, names in os.walk(base, followlinks=False):
        if any((Path(current) / name).is_symlink() for name in dirs + names):
            raise ValueError(f"source contains a symlink: {current}")
        dirs[:] = sorted(name for name in dirs if name not in EXCLUDED_DIRS)
        for name in sorted(names):
            rel = (Path(current) / name).relative_to(root).as_posix()
            if (name.startswith(".env") or rel.endswith((".spec.ts", ".test.ts", ".spec.tsx", ".test.tsx"))):
                continue
            path = root / rel
            if path.is_file():
                found[rel] = sha(path)
    if not found:
        raise ValueError(f"no candidate source files: {source}")
    return dict(sorted(found.items()))


def fingerprint(found: dict[str, str]) -> str:
    data = "".join(f"{digest}  {name}\n" for name, digest in sorted(found.items()))
    return hashlib.sha256(data.encode()).hexdigest()


def tools() -> tuple[str, str, str, str]:
    cli = shutil.which("semgrep")
    guard = shutil.which("sandbox-exec") if sys.platform == "darwin" else None
    if not cli or not guard:
        raise ValueError("local Semgrep CLI and macOS sandbox-exec are required")
    launcher = Path(cli).resolve()
    first = launcher.read_text().splitlines()[0]
    if not first.startswith("#!"):
        raise ValueError("unsupported Semgrep launcher")
    python = first[2:]
    probe = subprocess.run([python, "-B", "-c", "import importlib.util; from pathlib import Path; "
                            "print(Path(importlib.util.find_spec('semgrep').origin).parent / 'bin/semgrep-core')"],
                           check=True, capture_output=True, text=True, timeout=10)
    core = Path(probe.stdout.strip())
    if not core.is_file():
        raise ValueError("Semgrep OSS core unavailable")
    return cli, guard, str(core), python


def env(folder: Path) -> dict[str, str]:
    values = os.environ.copy()
    values.update({"SEMGREP_SETTINGS_FILE": str(folder / "settings.yml"),
                   "SEMGREP_VERSION_CACHE_PATH": str(folder / "version-cache"),
                   "SEMGREP_LOG_FILE": str(folder / "semgrep.log"),
                   "SEMGREP_SEND_METRICS": "off", "SEMGREP_ENABLE_VERSION_CHECK": "0",
                   "SEMGREP_APP_TOKEN": ""})
    return values


def execute(argv: list[str], root: Path, folder: Path, label: str, timeout: int) -> int:
    with (folder / f"{label}.stdout").open("xb") as out, (folder / f"{label}.stderr").open("xb") as err:
        try:
            return subprocess.run(argv, cwd=root, env=env(folder), stdout=out, stderr=err,
                                  check=False, timeout=timeout).returncode
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"{label} timeout; inspect {folder}") from exc


def preflight(root: Path, directory: Path, selected: list[str]) -> dict:
    cli, guard, core, python = tools()
    rule_ids = {}
    for track in selected:
        rule = SKILL / "rules" / f"{track}.yml"
        code = ("import json,sys; from ruamel.yaml import YAML; "
                "print(json.dumps([r['id'] for r in YAML(typ='safe').load(open(sys.argv[1]))['rules']]))")
        result = subprocess.run([python, "-B", "-c", code, str(rule)],
                                check=True, capture_output=True, text=True, timeout=10)
        ids = json.loads(result.stdout)
        if not isinstance(ids, list) or not ids or len(ids) != len(set(ids)):
            raise ValueError(f"invalid/duplicate rule IDs in {track}")
        rule_ids[track] = ids
    if len(set(item for ids in rule_ids.values() for item in ids)) != sum(map(len, rule_ids.values())):
        raise ValueError("duplicate rule IDs across tracks")
    for track in selected:
        files(root, TRACKS[track])
        rule = SKILL / "rules" / f"{track}.yml"
        if not rule.is_file() or rule.is_symlink():
            raise ValueError(f"missing bundled rule: {track}")
    with tempfile.TemporaryDirectory(prefix="semgrep-check-", dir=directory) as temporary:
        folder = Path(temporary)
        policy = folder / "network-deny.sb"
        policy.write_text(POLICY)
        prefix = [guard, "-f", str(policy)]
        if execute(prefix + [core, "-parse_rules", str(SKILL / "rules")], root, folder, "rules", 60):
            raise ValueError("bundled Semgrep rule parse failed")
        lints = SKILL / "references" / "offline-rule-lints.yml"
        if not lints.is_file():
            raise ValueError("bundled offline rule metachecks missing")
        if execute(prefix + [core, "-json_nodots", "-check_rules", str(lints),
                             str(SKILL / "rules")], root, folder, "metachecks", 60):
            raise ValueError("offline rule metachecks failed")
        output = (folder / "metachecks.stdout").read_text()
        checked = json.loads(re.sub(r"^\s*(?:\.\s*)*", "", output))
        if checked.get("errors") != [] or checked.get("results") != []:
            raise ValueError("offline rule metachecks reported errors/findings")
        if execute(prefix + [cli, "--version"], root, folder, "version", 60):
            raise ValueError("Semgrep CLI failed under network guard")
        version = (folder / "version.stdout").read_text().strip()
    return {"cli": cli, "guard": guard, "core": core, "version": version,
            "core_sha256": sha(Path(core)), "rule_ids": rule_ids,
            "metacheck_sha256": sha(SKILL / "references" / "offline-rule-lints.yml")}


def normalized(root: Path, value: str) -> str:
    path = Path(value)
    if path.is_absolute():
        path = path.relative_to(root)
    if ".." in path.parts:
        raise ValueError("scanner path escapes product")
    return path.as_posix()


def alerts(run_id: str, track: str, raw_path: Path, manifest: dict, complete: bool,
           reason: str | None) -> dict:
    raw_hash = sha(raw_path) if raw_path.is_file() else None
    try:
        raw = read(raw_path)
        rows = raw.get("results")
        if not isinstance(rows, list):
            raise ValueError("raw results missing")
        projected = []
        for index, item in enumerate(rows):
            if not isinstance(item, dict):
                raise ValueError("finding is not an object")
            path = normalized(ROOT, item["path"])
            if path not in manifest["files"]:
                raise ValueError("finding path not in frozen source")
            if path in manifest["excluded_binary_files"]:
                raise ValueError("finding path is non-UTF-8 binary source")
            start, end = item["start"], item["end"]
            if not isinstance(start, dict) or not isinstance(end, dict):
                raise ValueError("finding location missing")
            snapshot = Path(manifest["snapshots_dir"]) / path
            lines = snapshot.read_bytes().splitlines()
            if not (1 <= start["line"] <= end["line"] <= len(lines)):
                raise ValueError("finding line outside frozen source")
            severity = (item.get("extra") or {}).get("severity", "UNKNOWN")
            projected.append({
                "id": hashlib.sha256(f"{run_id}:{raw_hash}:{index}".encode()).hexdigest()[:24],
                "raw_index": index, "rule_id": item["check_id"], "severity": severity,
                "path": path, "start": start, "end": end,
                "source_sha256": manifest["files"][path],
            })
        counts = {}
        for item in projected:
            counts[item["severity"]] = counts.get(item["severity"], 0) + 1
        return {"schema": "semgrep-alerts-v1", "run_id": run_id, "track": track,
                "status": "complete" if complete else "partial_unverified", "reason": reason,
                "raw_sha256": raw_hash, "total": len(projected),
                "severity": counts, "alerts": projected}
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"schema": "semgrep-alerts-v1", "run_id": run_id, "track": track,
                "status": "unavailable", "reason": str(exc)[:300], "raw_sha256": raw_hash,
                "total": None, "severity": None, "alerts": []}


def source_snapshot(root: Path, run: Path, source: str) -> dict:
    selected = files(root, source)
    snapshots = run / "raw" / "source"
    excluded_binary = []
    for rel, digest in selected.items():
        target = snapshots / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / rel).read_bytes())
        try:
            target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            excluded_binary.append(rel)
        if sha(target) != digest:
            raise ValueError("source changed during snapshot")
    return {"source_root": source, "files": selected, "fingerprint": fingerprint(selected),
            "excluded_binary_files": excluded_binary, "snapshots_dir": str(snapshots)}


def verify(run: Path, directory: Path) -> dict:
    run = run.resolve()
    if not run.is_dir() or not run.is_relative_to(directory / "runs"):
        raise ValueError("run must be an explicit local run under Git metadata")
    receipt = read(run / "evidence" / "receipt.json")
    if receipt.get("schema") != "semgrep-receipt-v1" or receipt.get("run_id") != run.name:
        raise ValueError("run receipt identity mismatch")
    for rel, digest in receipt["bindings"].items():
        path = run / rel
        if not path.is_file() or not path.resolve().is_relative_to(run) or sha(path) != digest:
            raise ValueError(f"frozen evidence mismatch: {rel}")
    manifest = read(run / "inventory" / "source.json")
    if Path(manifest["snapshots_dir"]).resolve() != (run / "raw" / "source").resolve():
        raise ValueError("source snapshot directory mismatch")
    if fingerprint(manifest["files"]) != manifest["fingerprint"]:
        raise ValueError("source manifest fingerprint mismatch")
    if not isinstance(manifest.get("excluded_binary_files"), list) or not set(manifest["excluded_binary_files"]).issubset(manifest["files"]):
        raise ValueError("binary exclusion inventory missing or invalid")
    for rel, digest in manifest["files"].items():
        path = run / "raw" / "source" / rel
        if not path.is_file() or not path.resolve().is_relative_to(run) or sha(path) != digest:
            raise ValueError(f"frozen source mismatch: {rel}")
    projection = alerts(run.name, receipt["track"], run / "raw" / "results.json",
                        manifest, receipt["status"] == "completed", receipt.get("reason"))
    if projection != read(run / "evidence" / "alerts.json"):
        raise ValueError("alert projection mismatch")
    execution = read(run / "evidence" / "execution.json")
    raw_path = run / "raw" / "results.json"
    if execution["raw_sha256"] != (sha(raw_path) if raw_path.is_file() else None):
        raise ValueError("execution/raw hash mismatch")
    if receipt["status"] == "completed":
        raw = read(raw_path)
        timing = raw.get("time")
        paths = raw.get("paths")
        command = read(run / "inventory" / "command.json")
        if (execution["exit_code"] != 0 or raw.get("engine_requested") != "OSS" or
            raw.get("version") != command["semgrep_version"] or raw.get("errors") != [] or
            raw.get("skipped_rules") != [] or not isinstance(timing, dict) or
            timing.get("fixpoint_timeouts") != [] or not isinstance(paths, dict) or
            not isinstance(paths.get("scanned"), list) or not paths["scanned"] or
            any(normalized(ROOT, item) not in manifest["files"] for item in paths["scanned"]) or
            projection["status"] != "complete"):
            raise ValueError("completed receipt contradicts scanner evidence")
    for name in ("scan.stdout", "scan.stderr"):
        if sha(run / "raw" / name) != execution[name + "_sha256"]:
            raise ValueError(f"scanner output changed: {name}")
    return {"verified": True, "run_id": run.name, "track": receipt["track"],
            "status": receipt["status"], "alerts": projection["total"],
            "list_status": projection["status"]}


def scan_track(root: Path, directory: Path, batch_id: str, track: str, run_id: str, tool: dict) -> dict:
    run = directory / "runs" / run_id
    for name in ("raw", "inventory", "evidence"):
        (run / name).mkdir(parents=True, exist_ok=False)
    manifest = source_snapshot(root, run, TRACKS[track])
    save(run / "inventory" / "source.json", manifest)
    frozen_rule = run / "inventory" / "rules.yml"
    shutil.copyfile(SKILL / "rules" / f"{track}.yml", frozen_rule)
    shutil.copyfile(SKILL / "references" / "offline-rule-lints.yml",
                    run / "inventory" / "offline-rule-lints.yml")
    policy = run / "inventory" / "network-deny.sb"
    policy.write_text(POLICY)
    argv = [tool["guard"], "-f", str(policy), tool["cli"], "scan", "--oss-only",
            "--metrics=off", "--disable-version-check", "--strict", "--no-rewrite-rule-ids",
            "--verbose", "--time", "--config", str(frozen_rule),
            "--json-output", str(run / "raw" / "results.json")]
    for pattern in EXCLUDES:
        argv.extend(("--exclude", pattern))
    for path in manifest["excluded_binary_files"]:
        argv.extend(("--exclude", path))
    argv.append(TRACKS[track])
    save(run / "inventory" / "command.json", {"argv": argv, "cwd": str(root),
         "semgrep_version": tool["version"], "core_sha256": tool["core_sha256"],
         "metacheck_sha256": tool["metacheck_sha256"]})
    before = files(root, TRACKS[track])
    if before != manifest["files"]:
        raise ValueError("source changed before execution")
    try:
        code = execute(argv, root, run / "raw", "scan", 1800)
        scan_error = None
    except ValueError as exc:
        code, scan_error = None, str(exc)
    after = files(root, TRACKS[track])
    raw_path = run / "raw" / "results.json"
    reason = scan_error
    counts = {"candidate_files": len(manifest["files"]) - len(manifest["excluded_binary_files"]),
              "excluded_binary_files": len(manifest["excluded_binary_files"]), "scanned_files": None,
              "skipped_files": None, "rules_configured": len(tool["rule_ids"][track]), "rules_loaded": None,
              "rules_executed": None, "scanner_errors": None, "timeouts": None}
    complete = False
    try:
        raw = read(raw_path)
        rows, errors, paths = raw.get("results"), raw.get("errors"), raw.get("paths")
        skipped_rules = raw.get("skipped_rules")
        timing = raw.get("time")
        if not isinstance(rows, list) or not isinstance(errors, list) or not isinstance(paths, dict):
            raise ValueError("incomplete scanner JSON")
        scanned = paths.get("scanned")
        skipped = paths.get("skipped")
        if not isinstance(scanned, list) or not isinstance(skipped, list) or not isinstance(skipped_rules, list):
            raise ValueError("target or rule inventory missing")
        if not isinstance(timing, dict) or not isinstance(timing.get("fixpoint_timeouts"), list):
            raise ValueError("timeout inventory missing")
        loaded = timing.get("rules")
        if raw.get("engine_requested") != "OSS" or raw.get("version") != tool["version"]:
            raise ValueError("unexpected scanner engine/version")
        if any(normalized(root, item) not in manifest["files"] for item in scanned):
            raise ValueError("scanned target not in frozen source")
        error_timeouts = sum("timeout" in str(item.get("type", "")).lower()
                             for item in errors if isinstance(item, dict))
        fixpoint_timeouts = len(timing["fixpoint_timeouts"])
        timeout_count = (None if error_timeouts and fixpoint_timeouts
                         else error_timeouts + fixpoint_timeouts)
        counts.update(scanned_files=len(scanned), skipped_files=len(skipped), scanner_errors=len(errors),
                      rules_loaded=len(loaded) if isinstance(loaded, list) else None,
                      timeouts=timeout_count)
        if not reason and (code != 0 or errors or skipped_rules or timing["fixpoint_timeouts"]
                           or not scanned or before != after):
            reason = "scanner exit/errors/skipped rules/timeouts/empty target or source changed"
        complete = reason is None
    except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
        reason = reason or str(exc)[:300]
    projection = alerts(run_id, track, raw_path, manifest, complete, reason)
    if complete and projection["status"] != "complete":
        complete, reason = False, projection["reason"]
        projection = alerts(run_id, track, raw_path, manifest, False, reason)
    save(run / "evidence" / "alerts.json", projection)
    save(run / "evidence" / "execution.json", {"exit_code": code, "reason": reason,
         "scan.stdout_sha256": sha(run / "raw" / "scan.stdout"),
         "scan.stderr_sha256": sha(run / "raw" / "scan.stderr"),
         "raw_sha256": sha(raw_path) if raw_path.is_file() else None, "counts": counts})
    bindings = {rel: sha(run / rel) for rel in (
        "inventory/source.json", "inventory/rules.yml", "inventory/offline-rule-lints.yml",
        "inventory/network-deny.sb",
        "inventory/command.json", "evidence/execution.json", "evidence/alerts.json",
        "raw/scan.stdout", "raw/scan.stderr")}
    if raw_path.is_file():
        bindings["raw/results.json"] = sha(raw_path)
    save(run / "evidence" / "receipt.json", {"schema": "semgrep-receipt-v1", "run_id": run_id,
         "batch_id": batch_id, "track": track, "source_root": TRACKS[track],
         "source_fingerprint": manifest["fingerprint"], "status": "completed" if complete else "blocked",
         "reason": reason, "bindings": bindings})
    result = verify(run, directory)
    result.update(counts=counts, severity=projection["severity"], reason=reason,
                  alerts_path=str(run / "evidence" / "alerts.json"), run_path=str(run))
    return result


def batch_path(directory: Path, batch_id: str) -> Path:
    if not batch_id.startswith("SEMGREP-BATCH-") or "/" in batch_id or ".." in batch_id:
        raise ValueError("invalid batch ID")
    return directory / "batches" / f"{batch_id}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", default=str(ROOT))
    parser.add_argument("--tracks", nargs="+", choices=tuple(TRACKS))
    parser.add_argument("--authorized-local", action="store_true")
    parser.add_argument("--check", action="store_true", help="preflight only; no product scan")
    parser.add_argument("--resume", metavar="BATCH-ID")
    parser.add_argument("--verify", metavar="RUN-ID")
    args = parser.parse_args()
    if args.verify:
        directory = gitdir(ROOT) / "semgrep-scan"
        print(json.dumps(verify(directory / "runs" / args.verify, directory), ensure_ascii=False))
        return 0
    root = product(args.product)
    directory = gitdir(root) / "semgrep-scan"
    selected = args.tracks or list(TRACKS)
    if args.resume:
        state = read(batch_path(directory, args.resume))
        if args.tracks and args.tracks != state["tracks"]:
            raise ValueError("resume track selection differs from checkpoint")
        selected = state["tracks"]
    if len(selected) != len(set(selected)):
        raise ValueError("duplicate track")
    product_files = files(root, "finalsource")
    rule_hashes = {track: sha(SKILL / "rules" / f"{track}.yml") for track in selected}
    tool = preflight(root, gitdir(root), selected)
    if args.check:
        print(json.dumps({"status": "ready", "tracks": selected, "product": str(root),
                          "source_fingerprint": fingerprint(product_files),
                          "semgrep_version": tool["version"]}, ensure_ascii=False))
        return 0
    if not args.authorized_local:
        raise ValueError("researcher authorization and --authorized-local required for source scan")
    (directory / "runs").mkdir(parents=True, exist_ok=True)
    (directory / "batches").mkdir(parents=True, exist_ok=True)
    if args.resume:
        batch_id = args.resume
        if (state["product"] != str(root) or state["tracks"] != selected or
            state["source_fingerprint"] != fingerprint(product_files) or
            state["rule_sha256"] != rule_hashes or
            state["metacheck_sha256"] != tool["metacheck_sha256"]):
            raise ValueError("batch source/rule/product binding changed")
    else:
        batch_id = "SEMGREP-BATCH-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        state = {"schema": "semgrep-batch-v1", "batch_id": batch_id, "product": str(root),
                 "tracks": selected, "source_fingerprint": fingerprint(product_files),
                 "rule_sha256": rule_hashes, "metacheck_sha256": tool["metacheck_sha256"],
                 "progress": {track: {"status": "pending", "run_id": None} for track in selected}}
        save(batch_path(directory, batch_id), state)
    for track in selected:
        if (fingerprint(files(root, "finalsource")) != state["source_fingerprint"] or
            {name: sha(SKILL / "rules" / f"{name}.yml") for name in selected} != state["rule_sha256"] or
            sha(SKILL / "references" / "offline-rule-lints.yml") != state["metacheck_sha256"]):
            raise ValueError("batch source/rules changed before next track")
        prior = state["progress"][track]
        if prior["status"] in ("completed", "blocked"):
            result = verify(directory / "runs" / prior["run_id"], directory)
            print(json.dumps(result, ensure_ascii=False))
            if prior["status"] == "blocked":
                return 2
            continue
        if prior["status"] == "in_progress":
            run_id = prior["run_id"]
            receipt = directory / "runs" / run_id / "evidence" / "receipt.json"
            if not receipt.is_file():
                raise ValueError(f"unfinished run {run_id}; inspect its folder before a new batch")
            result = verify(directory / "runs" / run_id, directory)
            state["progress"][track] = {"status": result["status"], "run_id": run_id}
            save(batch_path(directory, batch_id), state)
            print(json.dumps(result, ensure_ascii=False))
            if result["status"] != "completed":
                return 2
            continue
        if prior["status"] != "pending":
            raise ValueError(f"invalid checkpoint status for {track}")
        run_id = "SEMGREP-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        state["progress"][track] = {"status": "in_progress", "run_id": run_id}
        save(batch_path(directory, batch_id), state)
        result = scan_track(root, directory, batch_id, track, run_id, tool)
        state["progress"][track] = {"status": result["status"], "run_id": result["run_id"]}
        save(batch_path(directory, batch_id), state)
        print(json.dumps(result, ensure_ascii=False))
        if result["status"] != "completed":
            return 2
    print(json.dumps({"batch_id": batch_id, "status": "completed", "checkpoint": str(batch_path(directory, batch_id))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        print(json.dumps({"status": "blocked", "reason": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)
