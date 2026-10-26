#!/usr/bin/env python3
"""Project canonical prose catalog + actual YAML declarations to JSON suggestions.

No scanner execution, YAML dependency, coverage judgment or persistent second catalog.
Language/path/engine declarations are exact YAML fragments for operator inspection.
"""
import argparse
import json
import re
from pathlib import Path


def declarations(block, key):
    match = re.search(r"^    " + re.escape(key) + r":.*(?:\n(?!    \S|  - id:).*)*", block, re.M)
    return match.group(0).rstrip() if match else None


def catalog(root):
    text = (root / "references/rule-catalog.md").read_text()
    entries, seen, rule_ids = [], set(), set()
    for filename, section in re.findall(r"^### ([\w-]+\.yml)\n(.*?)(?=^### |\Z)", text, re.M | re.S):
        path = root / "rules" / filename
        if not path.is_file():
            raise ValueError(f"catalog rule file missing: {filename}")
        pairs = re.findall(r"^  - id: ([\w-]+)\n(.*?)(?=^  - id: |\Z)", path.read_text(), re.M | re.S)
        blocks = dict(pairs)
        if len(blocks) != len(pairs) or rule_ids & blocks.keys():
            raise ValueError(f"duplicate bundled rule IDs in {filename}")
        rule_ids.update(blocks)
        for rid, language, role, bases, followup in re.findall(
                r"^- `([^`]+)` — language `([^`]+)`; \*\*([^*]+)\*\*; base `([^`]+)`\. (.*)$", section, re.M):
            if rid in seen or rid not in blocks:
                raise ValueError(f"duplicate or missing rule id: {rid}")
            seen.add(rid)
            block = blocks[rid]
            entries.append(dict(id=rid, rule_file=f"rules/{filename}", detector_role=role,
                base_ids=bases.split(","), manual_follow_up=followup,
                language_declaration=declarations(block, "languages"),
                path_limits_yaml=declarations(block, "paths"),
                engine_constraints_yaml=declarations(block, "options"),
                min_version_yaml=declarations(block, "min-version"),
                max_version_yaml=declarations(block, "max-version"),
                mode_yaml=declarations(block, "mode"),
                limits="Local CE; inspect full rule, ignores, framework and caller scope; suggestion is not coverage."))
    if seen != rule_ids:
        raise ValueError("catalog and bundled rule IDs differ")
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", action="append", default=[])
    args = parser.parse_args()
    try:
        entries = catalog(Path(__file__).resolve().parents[1])
    except ValueError as exc:
        parser.exit(1, str(exc) + "\n")
    print(json.dumps([e for e in entries if not args.base or set(args.base) & set(e["base_ids"])],
                     indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
