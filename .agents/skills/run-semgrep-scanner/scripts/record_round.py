#!/usr/bin/env python3
"""Capture a local scan. No shell, env dump, triage or completion decisions.

Spec: id, purpose, source_state_id, cwd, targets, argv, privacy, rules_selection,
exclusions, optional redact_values. argv must contain {native_json} exactly once.
Read the installed CLI help and choose a local OSS scan before invoking.
"""
import argparse
import json
import os
import re
import subprocess
from collections import defaultdict
from pathlib import Path

from report_records import now, write_new

COUNT_FIELDS = ("native_matches", "rules_configured", "rules_loaded", "rules_executed",
                "candidate_files", "scanned_files", "skipped_files", "excluded_binary_files")


def scrub(value, secrets):
    if isinstance(value, str):
        for secret in sorted((s for s in secrets if s), key=len, reverse=True):
            value = value.replace(secret, "[REDACTED]")
        value = re.sub(r"(?i)\b(password|token|secret|authorization|api[_-]?key)=([^\s]+)",
                       r"\1=[REDACTED]", value)
        return value
    if isinstance(value, list):
        result, hide = [], False
        for item in value:
            result.append("[REDACTED]" if hide else scrub(item, secrets))
            hide = isinstance(item, str) and bool(re.fullmatch(
                r"--(?:password|token|secret|authorization|api[-_]key)", item, re.I))
        return result
    if isinstance(value, dict):
        return {k: scrub(v, secrets) for k, v in value.items()}
    return value


def summarize(native_path):
    counts = dict.fromkeys(COUNT_FIELDS)
    result = dict(version=None, engine=None, engine_requested=None, errors=None,
                  skips=None, timeouts=None, counts=counts, count_sources={},
                  native_results=None, review_groups=[], output_state=None,
                  diagnostics=[], log_count_adapter=None, skipped_rules=None)
    try:
        native = json.loads(Path(native_path).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        result["output_state"] = "unreadable-or-missing"
        return result
    if not isinstance(native, dict):
        result["output_state"] = "invalid-top-level"
        return result
    result["output_state"] = "readable"
    for key in ("version", "engine_requested"):
        if isinstance(native.get(key), str):
            result[key] = native[key]
    # Requested engine is not evidence of the engine actually used.
    if isinstance(native.get("engine"), str):
        result["engine"] = native["engine"]
    if isinstance(native.get("skipped_rules"), list):
        result["skipped_rules"] = [dict(native_skipped_rule_index=i,
            rule_id=r.get("rule_id", r.get("id")) if isinstance(r, dict) else r,
            detail_reference=f"native.json#/skipped_rules/{i}")
            for i, r in enumerate(native["skipped_rules"])]
        if result["skipped_rules"]:
            result["diagnostics"].append("native skipped rules present; review applicability and errors")
    results = native.get("results")
    if isinstance(results, list) and all(isinstance(r, dict) for r in results):
        counts["native_matches"] = len(results)
        result["count_sources"]["native_matches"] = "native.results.length"
        safe_results, groups = [], defaultdict(list)
        for index, item in enumerate(results):
            extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
            metadata = extra.get("metadata") if isinstance(extra.get("metadata"), dict) else {}
            location = dict(path=item.get("path"))
            for key in ("start", "end"):
                position = item.get(key) if isinstance(item.get(key), dict) else {}
                location[key] = dict(line=position.get("line"), column=position.get("col"))
            safe_results.append(dict(native_result_index=index,
                rule_id=item.get("check_id"), location=location,
                native_severity=extra.get("severity"),
                native_confidence=metadata.get("confidence"),
                message_reference=f"native.json#/results/{index}/extra/message"))
            groups[json.dumps(location, sort_keys=True)].append(index)
        result["native_results"] = safe_results
        result["review_groups"] = [dict(location=json.loads(loc), native_result_indexes=ids,
            basis="same native location only; tester must review callers/control/root cause")
            for loc, ids in groups.items() if len(ids) > 1]
    else:
        result["diagnostics"].append("results unavailable or malformed; match count remains null")
    paths = native.get("paths") if isinstance(native.get("paths"), dict) else {}
    if isinstance(paths.get("scanned"), list):
        counts["scanned_files"] = len(paths["scanned"])
        result["count_sources"]["scanned_files"] = "native.paths.scanned.length"
        result["scanned_paths"] = paths["scanned"]
        if not paths["scanned"]:
            result["diagnostics"].append("zero scanned paths; this is not a clean assessment")
    # A present empty list is known zero in that native field, not all filtered files.
    if isinstance(paths.get("skipped"), list):
        counts["skipped_files"] = len(paths["skipped"])
        result["count_sources"]["skipped_files"] = "native.paths.skipped.length (reported entries only)"
        result["skips"] = [dict(native_skipped_index=i,
            path=p.get("path") if isinstance(p, dict) else p,
            reason=p.get("reason") if isinstance(p, dict) else None)
            for i, p in enumerate(paths["skipped"])]
    if isinstance(native.get("errors"), list) and all(isinstance(e, dict) for e in native["errors"]):
        result["errors"] = [dict(native_error_index=i, type=e.get("type"),
            level=e.get("level"), code=e.get("code"), path=e.get("path"),
            detail_reference=f"native.json#/errors/{i}")
            for i, e in enumerate(native["errors"])]
        result["timeouts"] = [e for e in result["errors"]
            if "timeout" in json.dumps(e.get("type", "")).lower()]
        if result["errors"]:
            result["diagnostics"].append("native errors present; review partial analysis")
    # Never infer configured/loaded/executed from timing rules or manual coverage.
    return result


def capture(spec, directory):
    directory = Path(directory).resolve()
    cwd = Path(spec["cwd"]).resolve(strict=True)
    if not isinstance(spec.get("argv"), list) or not all(isinstance(a, str) for a in spec["argv"]):
        raise ValueError("argv must be a string array")
    if spec["argv"].count("{native_json}") != 1:
        raise ValueError("argv requires exactly one {native_json} token for --json-output")
    for target in spec["targets"]:
        root = (cwd / target).resolve()
        if directory == root or root in directory.parents:
            raise ValueError("capture directory must be outside every source target")
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    native_path = directory / "native.json"
    argv = [str(native_path) if a == "{native_json}" else a for a in spec["argv"]]
    started = now()
    exit_code, launch_error = None, None
    with (directory / "stdout.log").open("xb") as stdout, (directory / "stderr.log").open("xb") as stderr:
        try:
            exit_code = subprocess.run(argv, cwd=cwd, stdout=stdout, stderr=stderr,
                                       check=False).returncode
        except OSError as exc:
            # Error text can include paths/arguments; retain only the mechanical type.
            launch_error = type(exc).__name__
    finished = now()
    observed = summarize(native_path)
    round_record = {key: spec.get(key) for key in (
        "id", "purpose", "source_state_id", "cwd", "targets", "rules_selection", "exclusions")}
    round_record.update(started_at=started, finished_at=finished, command=argv,
        privacy=dict(declared=spec.get("privacy"),
            note="Supplied settings describe configuration, not verified network isolation."),
        exit_code=exit_code, status=None, finding_ids=[], launch_error=launch_error,
        raw_output=dict(native=str(native_path), stdout=str(directory / "stdout.log"),
                        stderr=str(directory / "stderr.log")), **observed)
    record = scrub(round_record, spec.get("redact_values", []))
    write_new(directory / "round.json", record)
    for path in directory.iterdir():
        if path.is_file():
            path.chmod(0o600)
    return record


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    try:
        spec = json.loads(args.spec.read_text(encoding="utf-8"))
        capture(spec, args.output_dir)
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(2, "capture failed: check private spec paths, required fields and new output directory\n")
    # Do not print raw messages, matched code, secret values or command arguments.
    print("Captured round.json and private raw output; tester must review status and limitations.")


if __name__ == "__main__":
    main()
