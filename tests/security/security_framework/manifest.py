"""Read suite metadata and verify all traceability links before performing work."""

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SCANNER_METHODS = {"passive-dast", "authenticated-passive-dast", "automation-framework"}
APP_METHODS = {"authorization", "application-assertion"}
ACTIVE = "authenticated-active-dast"
AUTHENTICATED = {"authenticated-passive-dast", "authorization", ACTIVE}
METHODS = SCANNER_METHODS | APP_METHODS | {ACTIVE}
AUTH_KINDS = {"none", "form-cookie", "jwt-bearer"}
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
SUITE_NAME = re.compile(r"[a-z][a-z0-9_]{0,63}\Z")
CWE = re.compile(r"CWE-[1-9][0-9]*\Z")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, field):
    if not condition:
        raise ValueError(f"invalid suite field: {field}")


def identifiers(values, field, *, allow_empty=False):
    require(isinstance(values, list) and (allow_empty or values), field)
    require(all(isinstance(value, str) and IDENTIFIER.fullmatch(value) for value in values), field)
    require(len(set(values)) == len(values), field)
    return values


@dataclass(frozen=True)
class Suite:
    name: str
    scenario: str
    cases: dict
    objectives: dict
    profiles: dict
    inputs: dict


def read_suite(name, scenario):
    require(isinstance(name, str) and SUITE_NAME.fullmatch(name), "suite")
    directory = ROOT / "suites" / name
    require(directory.resolve() == directory, "suite directory")
    inputs = {}

    def record(relative, base=directory):
        candidate = Path(relative)
        path = (base / candidate).resolve()
        require(not candidate.is_absolute() and path.is_relative_to(base)
                and path.suffix in {".json", ".md", ".py", ".txt"} and path.is_file(), "input files")
        inputs[path.relative_to(ROOT).as_posix()] = digest(path)
        return path

    def document(path):
        data = json.loads(record(path).read_text(encoding="utf-8"))
        require(isinstance(data, dict) and type(data.get("schemaVersion")) is int
                and data["schemaVersion"] == 1, path)
        return data

    def records(path, key):
        rows = document(path).get(key)
        require(isinstance(rows, list) and all(isinstance(row, dict) for row in rows), key)
        keys = identifiers([row.get("id") for row in rows], key)
        return dict(zip(keys, rows))

    suite = document("suite.json")
    require(suite.get("id") == name, "suite id")
    objectives = records("objectives/objectives.json", "objectives")
    for objective in objectives.values():
        cwes = objective.get("cwe")
        require(isinstance(cwes, list) and cwes and
                all(isinstance(cwe, str) and CWE.fullmatch(cwe) for cwe in cwes)
                and len(set(cwes)) == len(cwes), "objective CWE")
        require(isinstance(objective.get("statement"), str) and objective["statement"].strip(),
                "objective statement")

    profiles = records("authentication/profiles.json", "profiles")
    for profile in profiles.values():
        require(profile.get("kind") in AUTH_KINDS, "auth profile kind")
        if profile["kind"] == "form-cookie":
            identifiers(profile.get("actors"), "form-cookie actors")

    cases = records("cases/cases.json", "cases")
    for case in cases.values():
        require(case.get("objectiveId") in objectives, "case objective")
        method = case.get("method")
        require(method in METHODS and case.get("authProfile") in profiles, "case method/authentication")
        kind = profiles[case["authProfile"]]["kind"]
        require(method not in AUTHENTICATED or kind != "none", "case authenticated method")
        require(method != "passive-dast" or kind == "none", "case anonymous method")
        identifiers(case.get("requiredEvidence"), "required evidence")
        require(isinstance(case.get("oracle"), str) and IDENTIFIER.fullmatch(case["oracle"]), "oracle")
        require(isinstance(case.get("expected"), str) and case["expected"].strip(), "expected")
        spec = case.get("specification")
        require(isinstance(spec, str) and spec.startswith("specifications/") and spec.endswith(".md"),
                "specification")
        require(record(spec).is_relative_to(directory / "specifications"), "specification location")

    declared = suite.get("scenarios")
    require(isinstance(declared, dict) and declared, "scenarios")
    identifiers(list(declared), "scenario names")
    for case_ids in declared.values():
        require(all(case_id in cases for case_id in identifiers(case_ids, "scenario cases")), "scenario cases")
    require(scenario in declared, "selected scenario")

    record("adapter.py")
    for file in ("zap-image.txt", "zap_report.py"):
        record(file, ROOT)
    for relative in sorted((ROOT / "security_framework").glob("*.py")):
        record(relative.relative_to(ROOT).as_posix(), ROOT)
    sources = suite.get("sources", [])
    require(isinstance(sources, list) and all(isinstance(item, str) for item in sources), "sources")
    for source in sources:
        record(source, ROOT)

    return Suite(name, scenario, {key: cases[key] for key in declared[scenario]},
                 objectives, profiles, inputs)
