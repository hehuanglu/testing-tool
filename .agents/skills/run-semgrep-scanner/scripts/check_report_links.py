#!/usr/bin/env python3
"""Read-only v2 bookkeeping checks, not source/evidence or verdict validation."""
import argparse
import json
from collections import Counter
from pathlib import Path


def check(run, alerts):
    errors = []

    def fail(where, message):
        errors.append(f"{where}: {message}")

    def index(records, where):
        result = {}
        if not isinstance(records, list):
            fail(where, "expected array")
            return result
        for i, record in enumerate(records):
            if not isinstance(record, dict) or not isinstance(record.get("id"), str):
                fail(f"{where}[{i}]", "record requires string id")
                continue
            if record["id"] in result:
                fail(where, f"duplicate id {record['id']}")
            result[record["id"]] = record
        return result

    def refs(record, field, target, where):
        values = record.get(field)
        if not isinstance(values, list):
            fail(f"{where}.{field}", "expected array")
            return []
        known = []
        for value in values:
            if not isinstance(value, str) or value not in target:
                fail(f"{where}.{field}", f"unknown reference {value!r}")
            else:
                known.append(value)
        if len(known) != len(set(known)):
            fail(f"{where}.{field}", "duplicate references")
        return known

    def ref(value, target, where):
        if not isinstance(value, str) or value not in target:
            fail(where, f"unknown reference {value!r}")
            return None
        return target[value]

    if not isinstance(run, dict) or not isinstance(alerts, dict):
        return ["RUN and ALERTS must be JSON objects"]
    for doc, name, schema in ((run, "RUN", "semgrep-tester-run-v2"),
                              (alerts, "ALERTS", "semgrep-tester-alerts-v2")):
        if doc.get("schema") != schema:
            fail(name, f"expected schema {schema}; historical v1 is not rewritten")
        if not isinstance(doc.get("assessment_id"), str):
            fail(name, "assessment_id must be string")
        if doc.get("status") not in ("completed", "partial", "blocked", "stopped"):
            fail(name, "handoff status missing or invalid (draft judgments may still be null)")
    for key in ("assessment_id", "status"):
        if run.get(key) != alerts.get(key):
            fail(key, "RUN and ALERTS differ")
    states = index(run.get("source_states"), "source_states")
    tracks = index(run.get("tracks"), "tracks")
    inventory = index(run.get("inventory"), "inventory")
    questions = index(run.get("questions"), "questions")
    rounds = index(run.get("rounds"), "rounds")
    reviews = index(run.get("manual_reviews"), "manual_reviews")
    findings = index(alerts.get("findings"), "findings")
    evidence_records = []
    occurrence_records = []
    for fid, finding in findings.items():
        for field, dest in (("evidence", evidence_records), ("occurrences", occurrence_records)):
            values = finding.get(field)
            if not isinstance(values, list):
                fail(fid, f"{field} must be array")
            else:
                dest.extend(values)
    evidences = index(evidence_records, "evidence")
    index(occurrence_records, "occurrences")
    native_by_round = {rid: set() for rid in rounds}
    occurrence_count = Counter()
    for fid, finding in findings.items():
        frounds = refs(finding, "round_ids", rounds, fid)
        fmanual = refs(finding, "manual_review_ids", reviews, fid)
        fquestions = refs(finding, "question_ids", questions, fid)
        refs(finding, "track_ids", tracks, fid)
        refs(finding, "related_finding_ids", findings, fid)
        for qid in fquestions:
            if questions[qid].get("track_id") not in finding.get("track_ids", []):
                fail(fid, f"question {qid} track missing from track_ids")
        source = finding.get("source")
        if (finding.get("triage") or {}).get("status") not in (
                "needs-review", "supported", "false-positive", "not-applicable"):
            fail(fid, "triage status missing or invalid")
        if source not in ("semgrep", "manual-source-review"):
            fail(fid, "unknown finding source")
        occurrences = finding.get("occurrences") or []
        if source == "manual-source-review":
            if frounds or occurrences:
                fail(fid, "manual-only finding must not have native rounds/occurrences")
            for field in ("rule_id", "message", "native_severity", "native_confidence"):
                if finding.get(field) is not None:
                    fail(fid, f"manual-only {field} must be null")
        elif source == "semgrep" and not occurrences:
            fail(fid, "Semgrep observation requires native occurrence")
        used_rounds = set()
        for occurrence in occurrences:
            if not isinstance(occurrence, dict):
                continue
            rid = occurrence.get("round_id")
            if ref(rid, rounds, f"{fid}.occurrence.round_id") is not None:
                used_rounds.add(rid)
                native_by_round[rid].add(fid)
                occurrence_count[rid] += 1
                if rid not in frounds:
                    fail(fid, f"occurrence {rid} missing from round_ids")
        if set(frounds) != used_rounds:
            fail(fid, "round_ids must correspond to its native occurrences")
        for mid in fmanual:
            if fid not in reviews[mid].get("finding_ids", []):
                fail(fid, f"manual review {mid} missing backlink")
        for evidence in finding.get("evidence") or []:
            if not isinstance(evidence, dict):
                continue
            eid = evidence.get("id", "evidence")
            provenance = evidence.get("provenance")
            state = evidence.get("source_state_id")
            rid, mid = evidence.get("round_id"), evidence.get("manual_review_id")
            if provenance == "semgrep":
                operation = ref(rid, rounds, f"{eid}.round_id")
                if rid not in frounds or mid is not None or source != "semgrep":
                    fail(eid, "native evidence must belong to this finding's round")
                if evidence.get("kind") not in ("native-match", "native-dataflow", "control-review", "config-review"):
                    fail(eid, "native evidence kind/provenance mismatch")
            elif provenance == "manual-source-review":
                operation = ref(mid, reviews, f"{eid}.manual_review_id")
                if mid not in fmanual or rid is not None:
                    fail(eid, "manual evidence must belong to this finding's manual review")
                if evidence.get("kind") in ("native-match", "native-dataflow"):
                    fail(eid, "manual path cannot be native evidence")
                if operation and eid not in operation.get("evidence_ids", []):
                    fail(eid, "manual review missing evidence backlink")
            elif provenance == "provided-policy":
                operation = None
                if rid is not None or mid is not None or not evidence.get("reference"):
                    fail(eid, "policy evidence needs reference and no execution operation")
            else:
                operation = None
                fail(eid, "unknown evidence provenance")
            if provenance != "provided-policy" or state is not None:
                ref(state, states, f"{eid}.source_state_id")
            if operation and operation.get("source_state_id") != state:
                fail(eid, "evidence source state differs from operation source state")
    for rid, round_record in rounds.items():
        actual = refs(round_record, "finding_ids", findings, rid)
        if set(actual) != native_by_round[rid]:
            fail(rid, "finding_ids must contain only/exactly findings with native occurrences in this round")
        ref(round_record.get("source_state_id"), states, f"{rid}.source_state_id")
        if round_record.get("status") not in ("completed", "partial", "blocked", "interrupted"):
            fail(rid, "round status missing or invalid")
        counts = round_record.get("counts") or {}
        for name, value in counts.items():
            if value is not None and (type(value) is not int or value < 0):
                fail(rid, f"counts.{name} must be nonnegative integer or null")
        count = counts.get("native_matches")
        if type(count) is int and count < occurrence_count[rid]:
            fail(rid, "native match count smaller than retained native occurrences")
        if (round_record.get("status") == "completed" and
                (counts.get("scanned_files") == 0 or round_record.get("errors"))):
            fail(rid, "completed conflicts with zero scanned files or unhandled native errors")
    for mid, review in reviews.items():
        ref(review.get("source_state_id"), states, f"{mid}.source_state_id")
        qids = refs(review, "question_ids", questions, mid)
        for qid in qids:
            if mid not in questions[qid].get("manual_review_ids", []):
                fail(mid, f"question {qid} missing manual review backlink")
        for fid in refs(review, "finding_ids", findings, mid):
            if mid not in findings[fid].get("manual_review_ids", []):
                fail(mid, f"finding {fid} missing manual review backlink")
        for eid in refs(review, "evidence_ids", evidences, mid):
            if evidences[eid].get("manual_review_id") != mid:
                fail(mid, f"evidence {eid} belongs to another operation")
    for iid, item in inventory.items():
        refs(item, "track_ids", tracks, iid)
    for qid, q in questions.items():
        track = ref(q.get("track_id"), tracks, f"{qid}.track_id")
        refs(q, "surface_ids", inventory, qid)
        refs(q, "round_ids", rounds, qid)
        for mid in refs(q, "manual_review_ids", reviews, qid):
            if qid not in reviews[mid].get("question_ids", []):
                fail(qid, f"manual review {mid} missing question backlink")
        if q.get("status") not in ("resolved", "open", "blocked", "not-applicable"):
            fail(qid, "question status missing or invalid")
        base = q.get("base_question_id")
        if track and base is not None and base not in track.get("selected_base_ids", []):
            fail(qid, "base question not selected in track")
        if q.get("introduced_after_round_id") is not None:
            ref(q["introduced_after_round_id"], rounds, f"{qid}.introduced_after_round_id")
    for tid, track in tracks.items():
        if track.get("status") not in ("completed", "partial", "blocked", "stopped"):
            fail(tid, "track status missing or invalid")
        remaining = refs(track, "remaining_question_ids", questions, tid)
        expected = {qid for qid, q in questions.items() if q.get("track_id") == tid
                    and q.get("status") in ("open", "blocked")}
        if set(remaining) != expected:
            fail(tid, "remaining_question_ids differs from open/blocked questions")
        if track.get("status") == "completed" and expected:
            fail(tid, "completed track still has remaining questions")
    coverage = run.get("coverage") or {}
    candidates = index(coverage.get("inventory_candidate_reviews", []), "inventory_candidate_reviews")
    for cid, candidate in candidates.items():
        round_record = ref(candidate.get("round_id"), rounds, f"{cid}.round_id")
        refs(candidate, "question_ids", questions, cid)
        refs(candidate, "manual_review_ids", reviews, cid)
        refs(candidate, "finding_ids", findings, cid)
        n = candidate.get("native_result_index")
        total = (round_record.get("counts") or {}).get("native_matches") if round_record else None
        if n is not None and (type(n) is not int or n < 0 or (type(total) is int and n >= total)):
            fail(cid, "native_result_index outside round results")
    for field in ("resolved_question_ids", "remaining_question_ids", "semgrep_question_ids", "manual_question_ids"):
        if field in coverage:
            refs(coverage, field, questions, "coverage")
    if "remaining_question_ids" in coverage:
        expected = {qid for qid, q in questions.items() if q.get("status") in ("open", "blocked")}
        if set(coverage["remaining_question_ids"]) != expected:
            fail("coverage", "remaining_question_ids mismatch")
    if "untriaged_finding_ids" in coverage:
        refs(coverage, "untriaged_finding_ids", findings, "coverage")
    summary = alerts.get("summary") or {}
    if summary.get("finding_records") != len(findings):
        fail("summary.finding_records", "does not equal finding record count")
    matches = summary.get("native_matches_by_round")
    expected = {rid: (r.get("counts") or {}).get("native_matches") for rid, r in rounds.items()}
    if matches != expected:
        fail("summary.native_matches_by_round", "must preserve all round native counts including null")
    for field, get_value in (("by_source", lambda f: f.get("source")),
                             ("by_native_severity", lambda f: f.get("native_severity")),
                             ("by_triage", lambda f: (f.get("triage") or {}).get("status"))):
        expected = dict(Counter(v for f in findings.values() if (v := get_value(f)) is not None))
        recorded = summary.get(field)
        if not isinstance(recorded, dict) or {k: v for k, v in recorded.items() if v != 0} != expected:
            fail(f"summary.{field}", "does not count finding records by declared unit")
    if summary.get("native_severity_null_records") != sum(f.get("native_severity") is None for f in findings.values()):
        fail("summary.native_severity_null_records", "incorrect null-severity count")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", type=Path)
    parser.add_argument("alerts", type=Path)
    args = parser.parse_args()
    try:
        errors = check(json.loads(args.run.read_text()), json.loads(args.alerts.read_text()))
    except (OSError, ValueError, TypeError, AttributeError):
        parser.exit(2, "Unreadable JSON or malformed record structure; files were not changed.\n")
    if errors:
        for error in errors:
            print(error)
        parser.exit(1)
    print("Bookkeeping links consistent; source evidence and security verdicts were not validated.")


if __name__ == "__main__":
    main()
