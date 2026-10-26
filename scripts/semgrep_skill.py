#!/usr/bin/env python3
"""Install or compare the complete repository Semgrep skill using Python stdlib."""
import argparse
from datetime import datetime, timezone
import filecmp
from pathlib import Path
import shutil
import tempfile
import uuid


SOURCE = Path(__file__).resolve().parents[1] / ".agents/skills/run-semgrep-scanner"
IGNORED = {"__pycache__", ".DS_Store"}


def files(root):
    if not root.is_dir():
        raise ValueError(f"skill directory is missing: {root}")
    result = {}
    for path in root.rglob("*"):
        relative = path.relative_to(root)
        if any(part in IGNORED for part in relative.parts) or path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise ValueError(f"symlink is not supported: {path}")
        if path.is_file():
            result[relative] = path
    return result


def differences(source, target):
    expected = files(source)
    actual = files(target) if target.exists() else {}
    return sorted(str(p) for p in expected.keys() | actual.keys()
                  if p not in expected or p not in actual
                  or not filecmp.cmp(expected[p], actual[p], shallow=False))


def install(source, target, update=False):
    source = source.resolve()
    if not (source / "SKILL.md").is_file():
        raise ValueError(f"source skill entrypoint is missing: {source}")
    if target.is_symlink():
        raise ValueError(f"target must not be a symlink: {target}")
    target = target.resolve()
    if target == source or target in source.parents or source in target.parents:
        raise ValueError("source and target must be separate directories")
    if target.exists() and not target.is_dir():
        raise ValueError(f"target is not a directory: {target}")
    changed = differences(source, target)
    if not changed:
        return None
    if target.exists() and not update:
        raise ValueError("installed copy differs; inspect with check, then use install --update (keeps a backup)")
    target.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".semgrep-install-", dir=target.parent))
    backup = None
    try:
        for relative, path in files(source).items():
            destination = staging / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, destination)
        if differences(source, staging):
            raise ValueError("staged skill does not match repository")
        if target.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = target.parent.parent / "skill-backups" / f"{target.name}-{stamp}-{uuid.uuid4().hex[:8]}"
            backup.parent.mkdir(parents=True, exist_ok=True)
            target.rename(backup)
        try:
            staging.rename(target)
        except OSError:
            if backup is not None:
                backup.rename(target)
            raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return backup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    parser.add_argument("--target", type=Path,
                        default=Path.home() / ".codex/skills/run-semgrep-scanner")
    parser.add_argument("--update", action="store_true", help="replace a differing copy after backing it up outside skills/")
    args = parser.parse_args()
    try:
        if args.action == "check":
            if args.update:
                parser.error("--update applies only to install")
            if args.target.is_symlink():
                raise ValueError("target must not be a symlink")
            changed = differences(SOURCE, args.target)
            if changed:
                print("Missing or different files:\n" + "\n".join(changed))
                return 1
        else:
            backup = install(SOURCE, args.target, args.update)
            if backup:
                print(f"Previous copy: {backup}")
        print(f"Skill matches repository: {args.target}")
        return 0
    except (OSError, ValueError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
