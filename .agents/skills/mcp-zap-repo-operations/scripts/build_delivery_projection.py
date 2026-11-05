#!/usr/bin/env python3
"""Build a sanitized, reviewable Drive-delivery projection from retained v2 evidence.

The review spec supplies tester judgment (mappings, triage, observed alerts).  The
script verifies that the complete native-alert population is accounted for and
derives criterion risk counts from alert identities rather than narrative text.
It does not write Google Drive or mutate the retained assessment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit


SKILL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL_DIR / "lib/zap-product-assessment/src"))

from zap_assessment.criteria_workflow import review_workflow  # noqa: E402


RISK_KEYS = {
    "High": "high",
    "Medium": "medium",
    "Low": "low",
    "Informational": "informational",
}
STATUS = {
    "met": "Đáp ứng",
    "unmet": "Không đáp ứng",
    "not_evaluable": "Không áp dụng",
    None: "Đang kiểm tra",
}
UUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F-]{27,}\b")
LONG_ID_RE = re.compile(r"\b[0-9a-fA-F]{24,}\b")


def load(path: Path):
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def clean_route(raw_url: str) -> str:
    parts = urlsplit(raw_url)
    path = UUID_RE.sub("{id}", parts.path)
    path = LONG_ID_RE.sub("{id}", path)
    return path + ("?{query}" if parts.query else "")


def compact_ids(values: list[str], limit: int = 12) -> str:
    if len(values) <= limit:
        return ", ".join(values)
    return ", ".join(values[:limit]) + f", … (+{len(values) - limit})"


def validate_review(run: dict, native_rows: list[dict], spec: dict) -> tuple[dict, dict]:
    criteria = {row["id"]: row for row in run["criteriaWorkflow"]["criteria"]}
    operations = {row["id"]: row for row in run.get("operations", [])}
    plugin_rules = {}
    for row in spec.get("nativeRules", []):
        plugin = str(row["pluginId"])
        if plugin in plugin_rules:
            raise ValueError(f"duplicate native rule review: {plugin}")
        mapped = row.get("criterionIds", [])
        if bool(mapped) == bool(row.get("unmappedReason")):
            raise ValueError(f"native rule {plugin} needs mappings xor unmappedReason")
        if any(criterion not in criteria for criterion in mapped):
            raise ValueError(f"native rule {plugin} references unknown criterion")
        if mapped and not str(row.get("rationale", "")).strip():
            raise ValueError(f"native rule {plugin} mapping rationale required")
        plugin_rules[plugin] = row

    native_ids = [str(row["id"]) for row in native_rows]
    if len(native_ids) != len(set(native_ids)):
        raise ValueError("duplicate native alert identity")
    missing_plugins = sorted({str(row["pluginId"]) for row in native_rows} - plugin_rules.keys())
    extra_plugins = sorted(plugin_rules.keys() - {str(row["pluginId"]) for row in native_rows})
    if missing_plugins or extra_plugins:
        raise ValueError(f"native review mismatch missing={missing_plugins} extra={extra_plugins}")

    observed = {}
    for row in spec.get("observedAlerts", []):
        finding = row["findingId"]
        if finding in observed:
            raise ValueError(f"duplicate observed alert {finding}")
        criterion_ids = row.get("criterionIds")
        if criterion_ids is None:
            criterion_ids = [row.get("criterionId")]
        if not criterion_ids or any(criterion not in criteria for criterion in criterion_ids):
            raise ValueError(f"observed alert {finding} references unknown criterion")
        if row.get("severity") not in RISK_KEYS:
            raise ValueError(f"observed alert {finding} needs supported tester severity")
        if row.get("nativeMatchState") not in ("matched", "possible", "none-established"):
            raise ValueError(f"observed alert {finding} needs nativeMatchState")
        refs = row.get("operationIds", [])
        if not refs or any(ref not in operations for ref in refs):
            raise ValueError(f"observed alert {finding} has unresolved operation IDs")
        evidence_origin = row.get("evidenceOrigin", "zap-derived-observation")
        if evidence_origin not in ("zap-derived-observation", "source-config-runtime"):
            raise ValueError(f"observed alert {finding} has unsupported evidenceOrigin")
        for ref in refs:
            provenance = operations[ref].get("provenance", {})
            has_capture = isinstance(operations[ref].get("zapCapture"), dict)
            if evidence_origin == "zap-derived-observation":
                if "zap" not in str(provenance.get("transport", "")).lower() and not has_capture:
                    raise ValueError(f"observed alert {finding} operation {ref} lacks ZAP provenance")
            elif not provenance.get("sourceOperationId"):
                raise ValueError(f"observed alert {finding} operation {ref} lacks source/config/runtime provenance")
        for required in ("ratingBasis", "securitySignal", "triage", "rationale"):
            if not str(row.get(required, "")).strip():
                raise ValueError(f"observed alert {finding} missing {required}")
        observed[finding] = {**row, "criterionIds": criterion_ids, "evidenceOrigin": evidence_origin}
    return plugin_rules, observed


def build(run: dict, native_doc: dict, spec: dict, native_url: str | None):
    native_rows = native_doc.get("alerts")
    if not isinstance(native_rows, list):
        raise ValueError("native alert document must contain alerts[]")
    rules, observed = validate_review(run, native_rows, spec)
    review = review_workflow(run)
    results = {row["criterionId"]: row for row in review["criterionResults"]}
    cases = {row["caseId"]: row for row in run["criteriaWorkflow"].get("caseResults", [])}
    criteria = run["criteriaWorkflow"]["criteria"]

    mapped = defaultdict(list)
    unmapped = []
    for alert in native_rows:
        rule = rules[str(alert["pluginId"])]
        item = {
            "findingId": f"ZAP-{alert['id']}",
            "recordKind": "native-zap-alert",
            "nativeAlertId": str(alert["id"]),
            "nativeRuleId": str(alert["pluginId"]),
            "name": alert.get("name") or alert.get("alert"),
            "severity": alert.get("risk"),
            "confidence": alert.get("confidence"),
            "messageId": str(alert.get("sourceMessageId") or alert.get("messageId")),
            "method": alert.get("method"),
            "route": clean_route(alert.get("url", "")),
            "triage": rule.get("triage", "reviewed"),
            "rationale": rule.get("rationale"),
        }
        if item["severity"] not in RISK_KEYS:
            raise ValueError(f"unsupported native severity for {item['findingId']}: {item['severity']}")
        if rule.get("criterionIds"):
            for criterion in rule["criterionIds"]:
                mapped[criterion].append(item)
        else:
            item["unmappedReason"] = rule["unmappedReason"]
            unmapped.append(item)

    for item in observed.values():
        for criterion_id in item["criterionIds"]:
            mapped[criterion_id].append({
                **item,
                "criterionId": criterion_id,
                "recordKind": (
                    "observed-security-finding"
                    if item["evidenceOrigin"] == "source-config-runtime"
                    else "observed-security-alert"
                ),
                "severitySource": "tester",
            })

    rows = []
    for criterion in criteria:
        cid = criterion["id"]
        result = results[cid]
        alerts = mapped.get(cid, [])
        # D:G are reserved for native ZAP risk ratings. Tester-assigned ratings
        # for Only observed findings remain descriptive evidence in the note and
        # supporting index; they never enter the four ZAP risk columns.
        counts = Counter(
            RISK_KEYS[item["severity"]]
            for item in alerts
            if item["recordKind"] == "native-zap-alert"
        )
        only_observed = sum(
            item["recordKind"] in ("observed-security-alert", "observed-security-finding")
            and item["nativeMatchState"] == "none-established"
            for item in alerts
        )
        case_rows = [cases[case_id] for case_id in criterion.get("caseIds", []) if case_id in cases]
        case_index = [f"{row['caseId']}:{row['outcome']}" for row in case_rows]
        alert_index = [item["findingId"] for item in alerts]
        observed_items = [
            item for item in alerts
            if item["recordKind"] in ("observed-security-alert", "observed-security-finding")
            and item["nativeMatchState"] == "none-established"
        ]
        observed_severity = Counter(item["severity"] for item in observed_items)
        observed_origin = Counter(item["evidenceOrigin"] for item in observed_items)
        note_parts = []
        if observed_items:
            severity_text = ", ".join(
                f"{severity} {observed_severity[severity]}"
                for severity in ("High", "Medium", "Low", "Informational")
                if observed_severity[severity]
            )
            origin_text = ", ".join(
                f"{origin} {count}" for origin, count in sorted(observed_origin.items())
            )
            note_parts.append(
                f"Only observed = {len(observed_items)}; mức tester chỉ để mô tả: {severity_text}; "
                f"nguồn: {origin_text}; IDs {compact_ids([item['findingId'] for item in observed_items], 7)}. "
                "Các mức này không được tính vào bốn cột risk level của ZAP."
            )
        if spec.get("criterionNotes", {}).get(cid):
            note_parts.append(spec["criterionNotes"][cid])
        rows.append({
            "criterionId": cid,
            "criterion": criterion["rawText"],
            "status": STATUS[result["verdict"]],
            "counts": {
                "high": counts["high"],
                "medium": counts["medium"],
                "low": counts["low"],
                "informational": counts["informational"],
                "onlyObserved": only_observed,
            },
            "caseIndex": case_index,
            "alertIndex": alert_index,
            "evidenceLabel": (
                f"Cases {compact_ids(case_index, 7) if case_index else 'N/A'}"
                + (f" • Alerts {compact_ids(alert_index, 7)}" if alert_index else " • 0 alert mapped")
                + " • Hồ sơ chứng cứ"
            ),
            "verdictBasis": result.get("basis"),
            "note": " ".join(note_parts),
            "caseEvidence": [
                {"caseId": row["caseId"], "outcome": row["outcome"], "basis": row.get("basis"),
                 "operationIds": row.get("operationIds", []),
                 "evidenceOperationIds": [link.get("operationId") for link in row.get("evidenceLinks", [])]}
                for row in case_rows
            ],
            "alerts": alerts,
        })

    projection = {
        "version": 1,
        "assessmentId": run.get("assessmentId"),
        "sourceGeneration": spec["sourceGeneration"],
        "mappingReviewComplete": True,
        "criteriaCount": len(rows),
        "nativeAlertCount": len(native_rows),
        "observedAlertCount": len(observed),
        "observedCriterionMappingCount": sum(len(row["criterionIds"]) for row in observed.values()),
        "mappedNativeAlertCount": sum(1 for row in native_rows if rules[str(row["pluginId"])].get("criterionIds")),
        "unmappedNativeAlertCount": len(unmapped),
        "nativeRiskTotals": dict(Counter(row["risk"] for row in native_rows)),
        "nativeIndexUrl": native_url,
        "rows": rows,
        "unmappedNativeAlerts": unmapped,
    }
    return projection


def write_native_index(path: Path, projection: dict, source_sha: str):
    lines = [
        "# Chỉ mục native alert ZAP — Clicon",
        "",
        f"- Assessment: `{projection['assessmentId']}`",
        f"- Generation: `{projection['sourceGeneration']}`",
        f"- SHA-256 nguồn native: `{source_sha}`",
        f"- Tổng native alert records: **{projection['nativeAlertCount']}**",
        f"- Phân bố native: `{json.dumps(projection['nativeRiskTotals'], ensure_ascii=False)}`",
        f"- Đã map: **{projection['mappedNativeAlertCount']}**; chưa map có lý do: **{projection['unmappedNativeAlertCount']}**",
        "",
        "Tài liệu này là projection đã làm sạch. Route đã bỏ origin, UUID và giá trị query; không chứa cookie, token hay raw traffic.",
        "",
    ]
    grouped = defaultdict(list)
    for row in projection["rows"]:
        for alert in row["alerts"]:
            if alert["recordKind"] == "native-zap-alert":
                grouped[(alert["nativeRuleId"], alert["name"], alert["severity"], alert["confidence"], row["criterionId"], alert["triage"], alert["rationale"])].append(alert)
    for key, alerts in sorted(grouped.items()):
        plugin, name, risk, confidence, criterion, triage, rationale = key
        lines.extend([
            f"## ZAP {plugin} — {name}", "",
            f"- Tiêu chí: `{criterion}`",
            f"- Mức native / confidence: **{risk} / {confidence}**",
            f"- Triage: {triage}",
            f"- Lý do mapping: {rationale}",
            f"- Alert records: **{len(alerts)}**", "",
            "| Alert ID | Message ID | Method | Route |", "|---|---|---|---|",
        ])
        for alert in alerts:
            lines.append(f"| {alert['nativeAlertId']} | {alert['messageId']} | {alert['method']} | `{alert['route']}` |")
        lines.append("")
    if projection["unmappedNativeAlerts"]:
        lines.extend(["## Native alerts chưa map vào catalog", ""])
        by_rule = defaultdict(list)
        for alert in projection["unmappedNativeAlerts"]:
            by_rule[(alert["nativeRuleId"], alert["name"], alert["severity"], alert["unmappedReason"])].append(alert)
        for key, alerts in sorted(by_rule.items()):
            plugin, name, risk, reason = key
            lines.extend([f"### ZAP {plugin} — {name}", "", f"- Mức native: **{risk}**", f"- Lý do chưa map: {reason}", f"- Alert records: **{len(alerts)}**", ""])
    path.write_text("\n".join(lines), encoding="utf-8")


def write_criterion_index(path: Path, projection: dict):
    lines = [
        "# Chỉ mục chứng cứ theo tiêu chí — Clicon",
        "",
        f"- Assessment: `{projection['assessmentId']}`",
        f"- Generation: `{projection['sourceGeneration']}`",
        f"- Tiêu chí: **{projection['criteriaCount']}**",
        f"- Native alerts: **{projection['nativeAlertCount']}**; Only observed findings do tester ghi nhận: **{projection['observedAlertCount']}** unique / **{projection['observedCriterionMappingCount']}** ánh xạ tiêu chí",
        f"- Chỉ mục native alert: {projection.get('nativeIndexUrl') or 'chưa gắn URL Drive'}",
        "",
        "Đây là chỉ mục đã làm sạch của kết quả vận hành. Only observed gồm finding do tester xác nhận từ ZAP hoặc source/config/runtime khi chưa có native ZAP detection tương ứng. Mỗi finding giữ ID, mức độ, nguồn quan sát, căn cứ rating và operation truy vết; bằng chứng thô, secret và đường dẫn cục bộ không được công bố.",
        "",
    ]
    for row in projection["rows"]:
        c = row["counts"]
        lines.extend([
            f"## {row['criterionId']} — {row['status']}", "",
            row["criterion"], "",
            f"- Native ZAP risk counts: Cao {c['high']} · Trung bình {c['medium']} · Thấp {c['low']} · Thông tin {c['informational']}",
            f"- Only observed count: {c['onlyObserved']} (mức tester chỉ mô tả trong Ghi chú/Alerts, không tính vào bốn mức native ZAP)",
            f"- Căn cứ kết luận: {row.get('verdictBasis') or 'Còn case hoặc applicability chưa khép.'}",
        ])
        if row.get("note"):
            lines.append(f"- Ghi chú diễn giải: {row['note']}")
        if row["caseEvidence"]:
            lines.extend(["", "### Cases", ""])
            for case in row["caseEvidence"]:
                refs = case["operationIds"] or case["evidenceOperationIds"]
                suffix = f"; operations `{compact_ids(refs, 10)}`" if refs else ""
                lines.append(f"- `{case['caseId']}` — **{case['outcome']}**: {case.get('basis') or 'Không có basis'}{suffix}")
        if row["alerts"]:
            lines.extend(["", "### Alerts", ""])
            for alert in row["alerts"]:
                if alert["recordKind"] == "native-zap-alert":
                    triage = alert["triage"].rstrip(".; ")
                    lines.append(f"- `{alert['findingId']}` — native **{alert['severity']}**, ZAP {alert['nativeRuleId']}, message {alert['messageId']}, `{alert['method']} {alert['route']}`; {triage}.")
                else:
                    triage = alert["triage"].rstrip(".; ")
                    lines.append(
                        f"- `{alert['findingId']}` — Only observed **{alert['severity']}** (tester); "
                        f"nguồn `{alert['evidenceOrigin']}`; {triage}; "
                        f"native-match `{alert['nativeMatchState']}`; operations `{compact_ids(alert['operationIds'], 10)}`. "
                        f"Quan sát: {alert['securitySignal']} Căn cứ mức độ: {alert['ratingBasis']} "
                        f"Lý do ánh xạ: {alert['rationale']}"
                    )
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--native-alerts", type=Path, required=True)
    parser.add_argument("--review-spec", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--native-index-url")
    args = parser.parse_args()
    run, native, spec = load(args.run), load(args.native_alerts), load(args.review_spec)
    projection = build(run, native, spec, args.native_index_url)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    projection_path = args.output_dir / "delivery-projection.json"
    native_path = args.output_dir / "native-alert-index.md"
    criterion_path = args.output_dir / "criterion-evidence-index.md"
    projection_path.write_text(json.dumps(projection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_native_index(native_path, projection, digest(args.native_alerts))
    write_criterion_index(criterion_path, projection)
    print(json.dumps({"projection": str(projection_path), "nativeIndex": str(native_path), "criterionIndex": str(criterion_path), "criteria": projection["criteriaCount"], "native": projection["nativeAlertCount"], "observed": projection["observedAlertCount"], "mappedNative": projection["mappedNativeAlertCount"], "unmappedNative": projection["unmappedNativeAlertCount"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
