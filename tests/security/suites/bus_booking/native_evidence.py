"""Read the product-native regression artifacts without opening raw traffic or logs."""

from hashlib import sha256
import json
import re

from security_framework.evidence import SHA256
from security_framework.execution import Engine
from security_framework.manifest import require
from security_framework.project import COMMIT
from security_framework.receipt import artifact, pointer, receipt, witness

from .adapter import command

POLICY = "bus-booking-security-acceptance-v1"
STATUSES = ("FAIL", "MISSING", "REVIEW", "PASS")
ID = re.compile(r"[A-Za-z0-9_.:#-]{1,200}\Z")
SUITE_FILE = re.compile(r"tests/security/[A-Za-z0-9_.-]+\Z")
DIGEST_FIELDS = ("checkout_status_sha256", "backend_jar_sha256", "scope_sha256", "manifest_sha256",
                 "openapi_sha256", "repository_openapi_sha256", "zap_plan_sha256")
PROVENANCE_FIELDS = (*DIGEST_FIELDS, "suite_files_sha256", "images", "java_version", "python_version",
                     "docker_version", "maven_distribution", "github_run_id", "github_run_attempt")
OBSERVED_SOURCES = {"log-secret-markers": "runtime_log", "log-crlf-marker": "runtime_log",
                    "security-event-review": "runtime_log", "http-auth-locations": "http_capture"}


def verify_inputs(manifest, product, revision):
    expected = dict(manifest["suite_files_sha256"])
    required_files = {"tests/security/run.py", "tests/security/scope.json", "tests/security/zap.yaml",
                      "tests/security/assessment.py", "tests/security/traffic.py",
                      "tests/security/journeys.py", "tests/security/authorization_matrix.py"}
    require(required_files <= expected.keys() and all(SUITE_FILE.fullmatch(path) for path in expected),
            "native suite sources")
    require(expected["tests/security/scope.json"] == manifest["manifest_sha256"]
            and expected["tests/security/zap.yaml"] == manifest["zap_plan_sha256"], "native configuration")
    expected["docs/openapi.json"] = manifest["repository_openapi_sha256"]
    expected["docs/security-assessment-scope.md"] = manifest["scope_sha256"]
    scope = None
    for path, digest in expected.items():
        blob = command(["git", "-C", str(product), "show", f"{revision}:{path}"],
                       reason="PROJECT_SOURCE_UNAVAILABLE")
        require(SHA256.fullmatch(digest) and sha256(blob).hexdigest() == digest, "native input digest")
        if path == "tests/security/scope.json":
            scope = json.loads(blob)
    return scope


def criterion_witnesses(result, criterion, mode):
    http = criterion.get("http", []) + (criterion.get("long", []) if mode == "long" else [])
    checks = {f"http:{case}": result["http_case_status"].get(case, "MISSING") for case in http}
    checks.update({f"maven:{case}": result["maven"].get(case, "MISSING") for case in criterion.get("maven", [])})
    checks.update({f"{OBSERVED_SOURCES.get(case, 'static')}:{case}": result["static"].get(case, {}).get("status", "MISSING")
                   for case in criterion.get("static", [])})
    checks.update({f"zap:{case}": result.get("zap", {}).get("status", "MISSING")
                   for case in criterion.get("zap", [])})
    checks.update({f"browser:{case}": result["frontend"]["e2e"]["status"]
                   for case in criterion.get("browser", [])})
    return checks


def _read_native(request):
    directory, product, revision, mode, exit_code, acceptance_gate = request
    require(COMMIT.fullmatch(revision) and mode in {"full", "long"}, "native revision and mode")
    result, result_hash = artifact(directory / "results.json")
    manifest, manifest_hash = artifact(directory / "manifest.json")
    require(result["sha"] == manifest["sha"] == revision and result["dirty"] is manifest["dirty"] is False,
            "native commit and cleanliness")
    require(result["mode"] == manifest["mode"] == mode and result["selected_case"] is None
            and manifest["selected_case"] is None and result["run_id"] == manifest["run_id"]
            and ID.fullmatch(result["run_id"]) and result["finished_at"] == manifest["finished_at"]
            and bool(result["finished_at"]), "native run identity")
    require(all(result.get(key) == manifest[key] for key in PROVENANCE_FIELDS), "native provenance agreement")
    require(manifest["checkout_status_sha256"] == sha256(b"").hexdigest(), "native clean status digest")
    for key in DIGEST_FIELDS:
        if key in {"backend_jar_sha256", "openapi_sha256"} and result["gate"] == "MISSING" and manifest[key] is None:
            continue
        require(isinstance(manifest[key], str) and SHA256.fullmatch(manifest[key]), "native SHA-256")
    scope = verify_inputs(manifest, product, revision)

    acceptance = result["security_acceptance"]
    require(acceptance["policy"] == manifest["acceptance_policy"] == POLICY, "native acceptance policy")
    acceptance_checks = {}
    for check in acceptance["checks"]:
        key, status = check["id"], check["status"]
        require(ID.fullmatch(key) and key not in acceptance_checks and status in STATUSES, "native acceptance check")
        acceptance_checks[key] = status
    blockers = [check for check in acceptance["checks"] if check["status"] != "PASS"]
    acceptance_status = next(status for status in STATUSES if status == "PASS"
                             or status in {check["status"] for check in blockers})
    require(acceptance["blockers"] == blockers and result["acceptance"] == acceptance["status"] == acceptance_status,
            "native acceptance verdict")
    gate = result["gate"]
    gate_exit = {"PASS": 0, "FAIL": 1, "MISSING": 2}[gate]
    require(acceptance_checks["execution"] == gate
            and exit_code == (gate_exit or (3 if acceptance_gate and acceptance_status != "PASS" else 0)),
            "native process exit")

    require(result["criteria"].keys() == scope["criteria"].keys(), "native objective scope")
    objectives = {}
    for key, row in result["criteria"].items():
        expected = criterion_witnesses(result, scope["criteria"][key], mode)
        status = next((status for status in STATUSES if status in expected.values()), "MISSING")
        require(ID.fullmatch(key) and acceptance_checks[key] == row["status"] == status
                and row["evidence"] == expected, "native objective evidence")
        observations = {}
        for identifier, status in row["evidence"].items():
            producer, case = identifier.split(":", 1)
            require(ID.fullmatch(case) and status in STATUSES, "native observation")
            reference = pointer("criteria", key, "evidence", identifier)
            observations[identifier] = {"status": status, "witnesses": [
                witness(producer, "result", reference, status)]}
        objectives[key] = {"acceptance": row["status"], "checks": observations}

    cleanup = result["cleanup_checks"]
    cleanup_ok = (result["cleanup"] == "PASS" and set(cleanup) == {"containers", "processes", "temporary_files"}
                  and all(value is True for value in cleanup.values()))
    stages = result["stages"]
    require(stages["cleanup"]["status"] == result["cleanup"] and (gate == "MISSING" or cleanup_ok),
            "native cleanup evidence")
    zap = result.get("zap", {})
    require(all(zap.get(key) == manifest["zap"][key] for key in ("method", "version", "addons_bundled")),
            "native ZAP provenance")
    if zap.get("status") == "PASS":
        require(zap["method"] == "passive" and zap["exit_code"] == 0 and zap["self_check"] is True
                and type(zap["sent"]) is int and zap["sent"] == zap["exported"] > 0 and zap["missing"] == 0,
                "native HAR reconciliation")
    if gate == "PASS":
        require(zap["status"] == "PASS" and all(row["status"] == "PASS" for row in stages.values()),
                "native terminal stages")
        images = manifest["images"]
        require(set(images) == {"mailpit", "postgres", "zap"} and all(
            re.fullmatch(r"sha256:[a-f0-9]{64}", image["id"]) for image in images.values()), "native image identities")

    capabilities = {"har-passive": {"qualification": "NOT_EVALUATED", "checks": {
        "reconciliation": zap.get("status", "MISSING")}}}
    for key in ("active_scan", "authenticated_active_dast"):
        status = result["capabilities"][key]["status"]
        require(status == "MISSING", "native active capability")
        capabilities[key] = {"qualification": "MISSING", "checks": {}}
    required = {"execution": gate, "authenticated_active_dast": "MISSING",
                "passive_baseline": result["baseline"]["status"],
                **{key: row["status"] for key, row in result["criteria"].items()}}
    for index, alert in enumerate(zap.get("alerts", []), 1):
        required[f"passive_alert:{index}"] = alert.get("triage", {}).get("status", "MISSING")
    for index, drift in enumerate(result["contract_drift"], 1):
        required[f"contract_drift:{index}"] = drift["runtime_status"]
    if gate != "FAIL" and any("FAIL" in result[key].values() for key in ("http_case_status", "maven")):
        required["failed_assertions"] = "FAIL"
    require(acceptance_checks == required, "native acceptance coverage")
    category = None
    if gate == "MISSING":
        category = "MISSING_EVIDENCE"
        if any(row["status"] != "PASS" and row["category"] in {"tool", "fixture", "cleanup"}
               for row in stages.values()):
            category = "INFRASTRUCTURE_FAILURE"
    execution = {"status": "INCOMPLETE" if gate == "MISSING" else "COMPLETED", "sourceStatus": gate,
                 "classification": category, "exitCode": exit_code,
                 "cleanup": "PASS" if cleanup_ok else "FAIL"}
    provenance = {"productRevision": revision, "mode": mode,
                  "inputs": {"artifact": "manifest", "pointer": "#"}}
    return receipt("bus-booking-native-v1", result["run_id"], {"result": result_hash, "manifest": manifest_hash},
                   provenance, execution, {"status": acceptance_status, "policy": POLICY,
                                           "checks": acceptance_checks}, objectives, capabilities)


HAR_PASSIVE_RECEIPT = Engine("har-passive-receipt", frozenset(), _read_native)
