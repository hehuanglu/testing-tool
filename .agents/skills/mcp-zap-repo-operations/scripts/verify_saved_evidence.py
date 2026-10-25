#!/usr/bin/env python3
"""Read saved assessment bundles without traffic, campaigns or historical rewrites.

Run with zap-product-assessment/.venv/bin/python. Exit 0 means readback
consistent, not security approval. Source drift is reported separately.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone

INDEXES = {
    "integration-campaign.json": 4,
    "m2-binding/binding-acceptance.json": 10,
    "m2-binding/synthetic-regression.json": 4,
    "m2-binding/health-only-binding.json": 1,
    "m3-bola/synthetic-campaign-final.json": 11,
    "m3-operational/pilot-final.json": 2,
    "m3-borrowed/pilot-final.json": 9,
}
STATUS = ("executionStatus", "evidenceStatus", "securityVerdict", "cleanupStatus", "gateDecision")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assessment-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New file outside historical evidence")
    args = parser.parse_args()
    root = args.assessment_root.resolve()
    output = args.output.absolute()
    if output.exists() or output.is_symlink():
        parser.error("output must be a new file")
    if output.resolve().is_relative_to(root):
        parser.error("write audit outside the assessment package to preserve its evidence")
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(root / "src"))
    from zap_assessment.evidence import verify_bundle
    from zap_assessment.executor import implementation_digest
    from zap_assessment.bola import source_digest
    current = {"anonymous": implementation_digest(), "bola": source_digest()}
    fingerprints = {}

    def remember(path):
        if path.is_file():
            fingerprints[str(path)] = sha(path)

    for folder in ("src", "schemas", "docs/evidence"):
        for p in (root / folder).rglob("*"):
            if p.is_file() and "__pycache__" not in p.parts:
                remember(p)

    def readback(path):
        path = path if path.is_absolute() else root / path
        resolved = path.resolve()
        if not resolved.is_relative_to(root / "runs") or path.is_symlink():
            raise ValueError("bundle outside retained runs")
        for p in path.iterdir():
            remember(p)
        m = verify_bundle(path)
        pin = m["sourceRefs"]["orchestrator"]
        family = "bola" if m["schemaVersion"] in ("1.2", "1.3", "1.4") else "anonymous"
        return {"bundle": str(path), "verified": True, "runId": m["runId"],
                "schemaVersion": m["schemaVersion"], "manifestSha256": sha(path / "manifest.json"),
                "sourcePin": pin, "sourceMatchesCurrent": pin == current[family],
                "statuses": {k: m[k] for k in STATUS}}

    groups = []
    for name, expected_count in INDEXES.items():
        path = root / "docs/evidence" / name
        group = {"index": str(path), "expectedCaseCount": expected_count, "cases": []}
        try:
            data = json.loads(path.read_bytes())
            group["indexSha256"] = sha(path)
            group["recordedCampaignPassed"] = data.get("allAssertionsPassed", data.get("passed")) is True
            cases = data.get("runs", data.get("cases", []))
            for case in cases:
                row = {"case": case.get("case", case.get("variant"))}
                try:
                    result = case["result"]
                    if result.get("bundle"):
                        row.update(readback(Path(result["bundle"])))
                        row["matchesIndexStatuses"] = row["statuses"] == {k: result[k] for k in STATUS}
                        row["matchesExpectedVerdict"] = "expected" not in case or row["statuses"]["securityVerdict"] == case["expected"]
                        row["consistent"] = row["matchesIndexStatuses"] and row["matchesExpectedVerdict"]
                    else:
                        rid = result["runId"]
                        if Path(rid).name != rid or rid in (".", ".."):
                            raise ValueError("invalid run ID")
                        row.update(runId=rid, verified=False, statuses={k: result[k] for k in STATUS},
                                   noPublishedBundle=not (root / "runs" / rid / "bundle").exists())
                        row["consistent"] = row["noPublishedBundle"] and result["gateDecision"] == "block" and result["evidenceStatus"] in ("incomplete", "invalid")
                        row["classification"] = "recorded blocked case; no bundle to verify"
                    assertions = case.get("assertions")
                    if assertions is not None:
                        row["recordedHarnessAssertionsPassed"] = bool(assertions) and all(v is True for v in assertions.values())
                        row["consistent"] &= row["recordedHarnessAssertionsPassed"]
                except Exception as exc:
                    row.update(consistent=False, errorType=type(exc).__name__)
                group["cases"].append(row)
            group["consistent"] = (group["recordedCampaignPassed"] and len(cases) == expected_count
                                   and all(c["consistent"] for c in group["cases"]))
        except Exception as exc:
            group.update(consistent=False, errorType=type(exc).__name__)
        groups.append(group)

    # This later real health-only smoke supersedes earlier blocked product candidates.
    try:
        smoke = readback(root / "runs/rb7477f7ba9bc48a4a110998dae795d97/bundle")
    except Exception as exc:
        smoke = {"verified": False, "errorType": type(exc).__name__}
    changed = [p for p, digest in fingerprints.items() if not Path(p).is_file() or sha(Path(p)) != digest]
    rows = [c for g in groups for c in g["cases"]]
    verified_rows = [c for c in rows if c.get("verified")]
    ok = all(g["consistent"] for g in groups) and smoke["verified"] and not changed
    report = {
        "schema": "mcp-zap-local-evidence-readback/v1",
        "observedAt": datetime.now(timezone.utc).isoformat(),
        "assessmentRoot": str(root), "readbackConsistent": ok,
        "currentSourceDigests": current,
        "campaignCaseCount": len(rows), "verifiedCampaignBundles": len(verified_rows),
        "campaignCasesWithoutBundle": len(rows) - len(verified_rows),
        "campaignBundlesMatchingCurrentSource": sum(c["sourceMatchesCurrent"] for c in verified_rows),
        "campaigns": groups, "finalsourceHealthSmoke": smoke,
        "preservation": {"filesChecked": len(fingerprints), "changedFiles": changed},
        "limits": ["No campaign rerun or target HTTP", "Harness assertions read, not re-observed",
                   "Historical source mismatch does not invalidate a valid old bundle",
                   "No signature, source-to-binary attestation or reviewer approval",
                   "No current Docker resource cleanup check", "No finalsource BOLA/authenticated DAST proof"],
    }
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("readbackConsistent", "campaignCaseCount", "verifiedCampaignBundles",
                                            "campaignCasesWithoutBundle", "campaignBundlesMatchingCurrentSource")}))
    print(json.dumps({"healthSmokeVerified": smoke["verified"], "preservedFiles": len(fingerprints), "output": str(output)}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
