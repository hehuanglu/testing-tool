#!/usr/bin/env python3
"""Initialize draft v2 records; judgments stay null until the tester supplies them."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def question(question_id, track_id=None, base_id=None):
    return dict(id=question_id, question=None, base_question_id=base_id,
                track_id=track_id, surface_ids=[], expectation=None,
                expectation_source=None, techniques=[], closure_condition=None,
                recorded_at=now(), introduced_after_round_id=None, changes=[],
                round_ids=[], manual_review_ids=[], result=None, status=None,
                next_step=None)


def draft(assessment_id):
    run = dict(schema="semgrep-tester-run-v2", assessment_id=assessment_id,
               status=None, started_at=now(), finished_at=None, product=None,
               scope=None, source_states=[], tracks=[], inventory=[], questions=[],
               rounds=[], manual_reviews=[], coverage=dict(
                   unit=None, inventory_candidate_reviews=[]),
               limitations=[], unperformed=[], next_steps=[])
    alerts = dict(schema="semgrep-tester-alerts-v2", assessment_id=assessment_id,
                  status=None, summary=dict(native_matches_by_round={},
                  finding_records=0, unique_issues=None, by_source={},
                  by_native_severity={}, by_triage={}, native_severity_null_records=0,
                  counting_method=None, deduplication=None), findings=[])
    return run, alerts


def write_new(path, value):
    # Exclusive creation preserves existing assessment history.
    with Path(path).open("x", encoding="utf-8") as stream:
        Path(path).chmod(0o600)
        json.dump(value, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    init = sub.add_parser("init")
    init.add_argument("directory", type=Path)
    init.add_argument("--assessment-id", required=True)
    q = sub.add_parser("question")
    q.add_argument("id")
    q.add_argument("--track-id")
    q.add_argument("--base-id")
    args = parser.parse_args()
    if args.mode == "question":
        print(json.dumps(question(args.id, args.track_id, args.base_id),
                         indent=2, ensure_ascii=False))
    else:
        args.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        paths = [args.directory / name for name in ("RUN.json", "ALERTS.json")]
        if any(path.exists() for path in paths):
            parser.error("RUN.json or ALERTS.json already exists; choose a new directory")
        for path, value in zip(paths, draft(args.assessment_id)):
            write_new(path, value)


if __name__ == "__main__":
    main()
