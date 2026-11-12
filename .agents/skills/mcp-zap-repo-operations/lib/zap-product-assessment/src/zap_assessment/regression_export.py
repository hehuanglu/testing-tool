"""Deterministically export reviewed assessment cases into portable CI cases."""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

from .contracts import ROOT
from .criteria_workflow import approval_digest, review_workflow, validate_workflow
from .question_evidence import operation_index, read_pointer


class ExportError(ValueError):
    def __init__(self, code: str, field: str, reason: str):
        super().__init__(reason)
        self.code = code
        self.field = field
        self.reason = reason

    def as_dict(self):
        return {"status": self.code, "field": self.field, "reason": self.reason}


def canonical_bytes(value) -> bytes:
    return (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2,
                       sort_keys=True) + "\n").encode("utf-8")


def _load_json(path: Path, field: str):
    if path.is_symlink():
        raise ExportError("INVALID_INPUT", field, "symlink input is not allowed")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ExportError("INVALID_INPUT", field, type(error).__name__) from None


def _schema(name: str):
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _validate_schema(value, name: str, field: str):
    errors = sorted(Draft202012Validator(_schema(name)).iter_errors(value),
                    key=lambda error: list(error.absolute_path))
    if errors:
        error = errors[0]
        location = "/".join(str(item) for item in error.absolute_path)
        instance = error.instance
        if (location.endswith("expect") and isinstance(instance, dict)
                and (not isinstance(instance.get("basis"), str)
                     or not instance.get("basis", "").strip())):
            location += "/basis"
        raise ExportError("INVALID_INPUT", field + ("/" + location if location else ""),
                          error.message)


def _validate_route(route: str, field: str):
    if (not route.startswith("/") or route.startswith("//") or "?" in route or "#" in route
            or "\r" in route or "\n" in route or "\\" in route
            or any(part in (".", "..") for part in route.split("/"))):
        raise ExportError("INVALID_INPUT", field,
                          "literal absolute route without query, fragment, traversal, CRLF or scheme required")


def validate_case(case):
    supported = ("passive-http-v1", "anti-framing-http-v1")
    if isinstance(case, dict) and case.get("profile") not in supported:
        raise ExportError("UNSUPPORTED_OPERATION", "case/profile",
                          "profile is not qualified")
    for index, request in enumerate(case.get("requests", []) if isinstance(case, dict) else []):
        if isinstance(request, dict) and request.get("method") != "GET":
            raise ExportError("UNSUPPORTED_OPERATION", f"case/requests/{index}/method",
                              "qualified HTTP profiles support GET only")
    _validate_schema(case, "regression-case-v1.schema.json", "case")
    request_ids = []
    for index, request in enumerate(case["requests"]):
        request_ids.append(request["id"])
        _validate_route(request["path"], f"case/requests/{index}/path")
    if len(request_ids) != len(set(request_ids)):
        raise ExportError("INVALID_INPUT", "case/requests", "request IDs must be unique")
    expected_fields = ({"basis", "alertRef", "presentOn", "absentOn", "requireNonEmptyCspOn"}
                       if case["profile"] == "passive-http-v1" else
                       {"basis", "evaluateOn", "trustedAncestors", "assumption"})
    if set(case["expect"]) != expected_fields:
        raise ExportError("INVALID_INPUT", "case/expect",
                          "expectation fields do not match the selected profile")
    references = (("presentOn", "absentOn", "requireNonEmptyCspOn")
                  if case["profile"] == "passive-http-v1" else ("evaluateOn",))
    for field in references:
        if case["expect"][field] not in request_ids:
            raise ExportError("MISSING_PREREQUISITE", "case/expect/" + field,
                              "assertion must reference an existing request ID")
    if (case["profile"] == "passive-http-v1"
            and case["expect"]["presentOn"] == case["expect"]["absentOn"]):
        raise ExportError("INVALID_INPUT", "case/expect",
                          "positive control and protected request must differ")
    return case


def _synthetic_source(value, run_path):
    source = value.get("source")
    if run_path is not None:
        if source is not None:
            raise ExportError("INVALID_INPUT", "source", "RUN export mapping must not declare source")
        return None
    if not source or source.get("kind") not in ("synthetic-demo", "product-qualification"):
        raise ExportError("INVALID_INPUT", "source/kind",
                          "standalone export accepts synthetic-demo or product-qualification only")
    path = Path(source["path"])
    if path.is_absolute() or ".." in path.parts:
        raise ExportError("INVALID_INPUT", "source/path", "source path must be repository-relative")
    return copy.deepcopy(source)


def _product_source(run, case_id: str):
    if not isinstance(run, dict) or not isinstance(run.get("assessmentId"), str):
        raise ExportError("INVALID_INPUT", "run/assessmentId", "assessmentId required")
    try:
        workflow = validate_workflow(run.get("criteriaWorkflow"))
    except ValueError as error:
        raise ExportError("INVALID_INPUT", "run/criteriaWorkflow", str(error)) from None
    if workflow["version"] != 3:
        raise ExportError("INVALID_INPUT", "run/criteriaWorkflow/version", "RUN v3 required")
    current_digest = approval_digest(workflow, "plan")
    approved = any(row.get("kind") == "plan"
                   and row.get("revision") == workflow["planRevision"]
                   and row.get("digest") == current_digest
                   for row in workflow.get("approvals", []))
    if not approved:
        raise ExportError("MISSING_PREREQUISITE", "run/criteriaWorkflow/approvals",
                          "current plan revision and digest are not approved")
    cases = [row for row in workflow["plan"]["cases"] if row.get("id") == case_id]
    if len(cases) != 1:
        raise ExportError("MISSING_PREREQUISITE", "run/criteriaWorkflow/plan/cases",
                          "exactly one matching case required")
    results = [row for row in workflow.get("caseResults", []) if row.get("caseId") == case_id]
    if len(results) != 1 or results[0].get("outcome") not in ("matched", "violated"):
        raise ExportError("MISSING_PREREQUISITE", "run/criteriaWorkflow/caseResults",
                          "reviewed matched or violated case result required")
    try:
        review = review_workflow(run)
    except ValueError as error:
        raise ExportError("MISSING_PREREQUISITE", "run", str(error)) from None
    reviewed = next(row for row in review["caseResults"] if row["caseId"] == case_id)
    evidence = reviewed.get("evidence", {})
    if (reviewed.get("outcome") not in ("matched", "violated")
            or evidence.get("missingUnits") or evidence.get("contextDiagnostics")
            or not evidence.get("supportOperationIds")):
        raise ExportError("MISSING_PREREQUISITE", "run/criteriaWorkflow/caseResults",
                          "case lacks complete support readback for its current context")
    operations = operation_index(run.get("operations", []))
    links = []
    for link in results[0].get("evidenceLinks", []):
        if link.get("role") != "support" or link.get("resultRead") is not True:
            continue
        operation = operations[link["operationId"]]
        context = operation.get("coverageContext", {})
        method = context.get("method")
        route = context.get("route")
        if method not in (None, "GET"):
            raise ExportError("UNSUPPORTED_OPERATION", "run/operations/" + operation["id"],
                              "qualified HTTP profiles support GET evidence only")
        if route is not None:
            _validate_route(route, "run/operations/" + operation["id"] + "/coverageContext/route")
        fact = read_pointer(operation, link["resultPath"])
        links.append({
            "operationId": operation["id"],
            "resultPath": link["resultPath"],
            "sha256": hashlib.sha256(canonical_bytes(fact)).hexdigest(),
        })
    if not links:
        raise ExportError("MISSING_PREREQUISITE", "run/evidenceLinks", "support evidence required")
    case = cases[0]
    return ({
        "kind": "assessment-run-v3",
        "assessmentId": run["assessmentId"],
        "caseId": case_id,
        "criterionIds": copy.deepcopy(case["criterionIds"]),
        "planRevision": workflow["planRevision"],
        "planDigest": current_digest,
        "evidence": links,
    }, case)


def build_case(value, run=None, case_id=None):
    _validate_schema(value, "regression-export-v1.schema.json", "input")
    source = _synthetic_source(value, run)
    reviewed_case = None
    if run is not None:
        if not case_id:
            raise ExportError("INVALID_INPUT", "case-id", "--case-id is required with --run")
        source, reviewed_case = _product_source(run, case_id)
    ci = copy.deepcopy(value["ci"])
    if source["caseId"] != ci["id"] and source["kind"] in ("synthetic-demo", "product-qualification"):
        raise ExportError("INVALID_INPUT", "source/caseId", "source caseId must equal ci.id")
    if source["kind"] == "product-qualification":
        target = ci.get("target", {})
        if (source.get("repository") != target.get("repository")
                or source.get("commitSha") != target.get("commitSha")):
            raise ExportError("INVALID_INPUT", "source",
                              "product qualification source and target repository/commit must match")
    if reviewed_case is not None:
        if ci["id"] != case_id:
            raise ExportError("INVALID_INPUT", "ci/id", "ci.id must equal --case-id")
        if ci["expect"]["basis"] != reviewed_case["expectationBasis"]:
            raise ExportError("MISSING_PREREQUISITE", "ci/expect/basis",
                              "CI expectation basis must equal the reviewed case expectationBasis")
    case = {"schemaVersion": 1, "source": source, **ci}
    return validate_case(case)


def write_case(case, out_dir: Path):
    if out_dir.is_symlink():
        raise ExportError("INVALID_INPUT", "out-dir", "symlink output directory is not allowed")
    out_dir.mkdir(parents=True, exist_ok=True)
    resolved = out_dir.resolve()
    target = out_dir / (case["id"] + ".json")
    if target.is_symlink() or target.resolve().parent != resolved:
        raise ExportError("INVALID_INPUT", "out-dir", "output path escapes the requested directory")
    payload = canonical_bytes(case)
    if target.exists():
        if target.read_bytes() == payload:
            return "UNCHANGED", target, payload
        return "REVIEW_REQUIRED", target, payload
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(target, flags, 0o644)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        try:
            target.unlink()
        except OSError:
            pass
        raise
    return "CREATED", target, payload


def generate(input_path, out_dir, run_path=None, case_id=None):
    value = _load_json(Path(input_path), "input")
    run = _load_json(Path(run_path), "run") if run_path else None
    case = build_case(value, run, case_id)
    return write_case(case, Path(out_dir))


def cli_generate(args):
    try:
        status, target, payload = generate(args.input, args.out_dir, args.run, args.case_id)
        if status == "REVIEW_REQUIRED":
            sys.stdout.buffer.write(payload)
            print(json.dumps({"status": status, "path": str(target)}), file=sys.stderr)
            return 2
        print(json.dumps({"status": status, "path": str(target),
                          "sha256": hashlib.sha256(payload).hexdigest()}, sort_keys=True))
        return 0
    except ExportError as error:
        print(json.dumps(error.as_dict(), sort_keys=True), file=sys.stderr)
        return 2
