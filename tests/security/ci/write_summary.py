#!/usr/bin/env python3
"""Render the suite and cleanup results as GitHub Markdown and JUnit."""

import argparse
import json
import os
from pathlib import Path
from xml.etree import ElementTree as ET


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def render(suite, fallback):
    case_rows = suite["cases"]
    suite_error = suite.get("suiteError")
    issues = []
    if suite_error:
        issues.append(("suite", suite_error["code"]))
    if fallback["status"] == "UNVERIFIED":
        issues.append(("cleanup", "FALLBACK_CLEANUP_UNVERIFIED"))
    if not case_rows and not suite_error:
        issues.append(("suite", "NO_CASE_RESULT"))
    failed = sum(row["status"] in ("REGRESSION", "MISSING_EVIDENCE") for row in case_rows)
    errors = sum(row["status"] == "EXECUTION_ERROR" for row in case_rows) + len(issues)
    document = ET.Element("testsuite", {
        "name": "ZAP regression", "tests": str(len(case_rows) + len(issues)),
        "failures": str(failed), "errors": str(errors), "skipped": "0",
    })
    overall = "ERROR" if issues else suite["status"]
    lines = [f"## ZAP regression · {overall}", "",
             f"- Suite outcome `{suite['status']}` with {suite['caseCount']} case(s)",
             f"- Fallback cleanup `{fallback['status']}`", ""]
    for row in case_rows:
        status, reason = row["status"], row["reason"]
        test = ET.SubElement(document, "testcase", name=row["id"], classname="ByteMe")
        if status != "PASS":
            tag = "error" if status == "EXECUTION_ERROR" else "failure"
            ET.SubElement(test, tag, type=status, message=reason)
        line = f"- `{row['id']}` · `{status}/{reason}`"
        if "preCleanupStatus" in row:
            line += f" · before cleanup `{row['preCleanupStatus']}/{row['preCleanupReason']}`"
        lines.append(line)
    for name, reason in issues:
        test = ET.SubElement(document, "testcase", name=name, classname="ZAP regression")
        ET.SubElement(test, "error", type="EXECUTION_ERROR", message=reason)
        lines.append(f"- `{name}` · `{reason}`")
    ET.indent(document)
    return "\n".join(lines).rstrip() + "\n", ET.tostring(document, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    root = parser.parse_args().root
    suite_path = root / "suite-results.json"
    fallback_path = root / "fallback-cleanup.json"
    if suite_path.is_file():
        suite = read_json(suite_path)
    else:
        suite = {"status": "ERROR", "caseCount": 0, "cases": [],
                 "suiteError": {"code": "BOOTSTRAP_FAILED"}}
    fallback = read_json(fallback_path) if fallback_path.is_file() else {"status": "UNVERIFIED"}
    summary, junit = render(suite, fallback)
    (root / "summary.md").write_text(summary, encoding="utf-8")
    (root / "junit.xml").write_bytes(junit + b"\n")
    step_summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary:
        with Path(step_summary).open("a", encoding="utf-8") as stream:
            stream.write(summary)
    return int(not suite_path.is_file())


if __name__ == "__main__":
    raise SystemExit(main())
