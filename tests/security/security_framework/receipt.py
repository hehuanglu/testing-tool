"""Normalize evidence references and independent decisions without changing source receipts."""

import hashlib
import json

from .evidence import validate_child


def artifact(path):
    raw = path.read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def pointer(*parts):
    return "#/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in parts)


def witness(producer, source, reference, status):
    return {"producer": producer, "artifact": source, "pointer": reference, "status": status}


def receipt(source_format, run_id, artifacts, provenance, execution, acceptance, objectives, capabilities):
    return {"schemaVersion": 2, "sourceFormat": source_format, "runId": run_id, "artifacts": artifacts,
            "provenance": provenance, "execution": execution, "acceptance": acceptance,
            "objectives": objectives, "capabilities": capabilities}


def failure_class(reasons):
    if any(reason.startswith(("INFRASTRUCTURE_", "DATABASE_", "DOCKER_", "RUNTIME_IMAGE_"))
           or reason in {"JAVA_21_REQUIRED", "JAVA_HOME_REQUIRED", "MAVEN_WRAPPER_CACHE_UNAVAILABLE",
                         "PROJECT_SOURCE_UNAVAILABLE"} for reason in reasons):
        return "INFRASTRUCTURE_FAILURE"
    if "MISSING_EVIDENCE" in reasons:
        return "MISSING_EVIDENCE"
    if "INVALID_EVIDENCE" in reasons:
        return "INVALID_EVIDENCE"
    return "EXECUTION_FAILURE"


def suite_receipt(result, suite, process_exit, digest, framework):
    validate_child(result, suite, result["runId"], process_exit)
    verdict = result["verdict"]
    if verdict == "ERROR":
        status, category = "INCOMPLETE", failure_class(set(result["decisiveChecks"].values()))
    elif verdict == "BLOCKED":
        status, category = "BLOCKED", "ADMISSION_RESTRICTED"
    else:
        status, category = "COMPLETED", None
    execution = {"status": status, "sourceStatus": verdict, "exitCode": process_exit,
                 "classification": category}

    objectives = {}
    capabilities = {}
    for case_id, check in result["checks"].items():
        objective = objectives.setdefault(check["objectiveId"], {"acceptance": "NOT_EVALUATED", "checks": {}})
        observations = []
        for reference in check["evidenceRefs"]:
            key = reference.removeprefix("#/evidence/")
            observations.append(witness(result["evidence"][key]["producer"], "result", reference,
                                        "OBSERVED"))
        objective["checks"][case_id] = {"status": check["verdict"], "reason": check["reason"],
                                        "witnesses": observations}
        current = capabilities.setdefault(check["method"], {"qualification": "NOT_EVALUATED", "checks": {}})
        current["checks"][case_id] = check["verdict"]
        if check["method"] == "authenticated-active-dast":
            current["qualification"] = "BLOCKED"

    provenance = {"framework": framework, "suite": suite.name, "scenario": suite.scenario,
                  "inputSha256": suite.inputs, "recordedEnvironment": result.get("executionEnvironment")}
    if "scannerImage" in result:
        provenance["scannerImage"] = result["scannerImage"]
    if "provenance" in result["evidence"]:
        provenance["projectEvidence"] = {"artifact": "result", "pointer": "#/evidence/provenance/data"}
    return receipt("shared-suite-v1", result["runId"], {"result": digest}, provenance, execution,
                   {"status": "NOT_EVALUATED"}, objectives, capabilities)
