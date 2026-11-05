# Two result files and completion

## Separate status dimensions

Rounds use `completed`, `partial`, `blocked`, `interrupted`. Completed means readable valid output with no error preventing the round's objective; findings do not prevent completion. Partial means meaningful but incomplete work, blocked means no meaningful check could execute, and interrupted means execution was interrupted. Retain native exit/counts/errors separately.

Assessments/tracks use `completed`, `partial`, `blocked`, `stopped`. Completion requires reconciled inventory/scope and assigned triage with no eligible unfinished step. Supported issues do not imply partial status. Required unresolved source/questions/triage mean partial; no meaningful assessment means blocked; user-requested termination means stopped. Continue independent branches.

Questions use `resolved`, `open`, `blocked`, `not-applicable`. Resolution needs a supported answer at the assigned level and may identify an issue. Required needs-review triage keeps questions unresolved. Candidates-only tasks may resolve detector-search questions while explicitly excluding further triage; do not call them completed security audits. N/A needs applicability grounds, rather than missing rules.

## Handoff and versions

New assessments use exactly **ALERTS.json and RUN.json per track** at `<assessment-root>/<track-id>/`, in stable local storage outside targets, preserving history. Under the [sequential workflow](sequential-track-workflow.md), save/review the current pair before executing the next track. Tracks may contain multiple rounds. Exhausted local options with external dependencies permit an honest partial/blocked handoff and independent continuation. User-requested combined execution/reporting retains individual mappings and self-contained assessment references.

Keep raw/log/rules/settings private; do not require evidence folders, archives, hash manifests, EVALUATION files, or canvases. Record self-review in RUN `tracks[].review`; produce a separate evaluation only when requested. Embed [evidence](evidence.md) in ALERTS. Setup/audit/skill maintenance does not authorize product assessments or fabricated result files.

Schemas are `semgrep-tester-alerts-v2` and `semgrep-tester-run-v2`: recording contracts rather than new framework/approval gates. Read v1 as-is and identify missing evidence without inventing or rewriting history. Blocked-before-scan findings may be `[]`, but unknown native counts remain null and status states that no scan occurred. Preserve actual manual observations.

## Shared types

IDs are strings unique within their collections; references resolve to actual records in the same assessment. Evidence IDs are unique across findings. Use timezone-bearing ISO 8601 timestamps when known; null for unknown/unexecuted/synthetic times. Locations are `{path, start, end}`, product-relative with `{line, column}` positions, 1-based when known and null otherwise. Preserve native end positions without invented ranges. Multiple roots need explicit root mappings.

Use `[]` for known empty arrays and null for unobserved fields/counts. Sanitize text; omit tokens/passwords/raw headers/sensitive source. General conclusions do not replace question/operation/finding/evidence links.

## ALERTS.json

Top-level fields: `schema`, `assessment_id`, `status`, `summary`, `findings`.

Summary fields:

- `native_matches_by_round`: actual native result count per round, including inventory-only matches, or null. It need not equal security findings.
- `finding_records`: aggregated observation records, rather than vulnerability count.
- `unique_issues`: nullable until deduplication/triage supports a count; do not count false-positive/needs-review as supported vulnerabilities.
- `by_source`, `by_native_severity`, `by_triage`: finding-record counts. Use real Semgrep severity only; separate manual/null records with `native_severity_null_records`.
- `counting_method`, `deduplication`: units, occurrence grouping, many-to-many mappings, and uncertainty. Historical matches differ from current records/root causes.

Each finding includes:

- `id`, `source` (`semgrep`/`manual-source-review`), `track_ids`, `question_ids`, `round_ids`, `manual_review_ids`.
- `rule_id`, `native_severity`, `native_confidence`, `message`: native facts or null when absent/manual. Put manual claims in triage/evidence, rather than fabricated native messages. Note sensitive-message redactions.
- `locations`; `occurrences` containing `{id, round_id, native_rule_id, location, native_identifier}`. Identifier is nullable; manual findings have no fabricated native occurrence. Preserve actual per-round provenance.
- `related_finding_ids`: known related observations without forced grouping. For multiple-rule aggregates retain per-occurrence IDs; common `rule_id` may be null with explanation.
- `triage`: `{status, rationale, impact, assumptions, next_step}`. Status is `needs-review`, `supported`, `false-positive`, or `not-applicable`; impact/next_step may be null, assumptions an array. Support control rationales with evidence.
- `tester_priority`: null or `{value, rationale}`, separate from native severity; no arbitrary CVSS mapping.
- `evidence` under the [evidence contract](evidence.md), and `evidence_gaps` affecting claims.

## RUN.json

Include:

- `schema`, `assessment_id`, `status`, `started_at`, `finished_at`, `product` (paths/roots/languages/frameworks/known revision), `scope` (request/source, triage depth, exclusions).
- `source_states`: `{id, roots, observed_at, revision, dirty, notes}`. Unknown/no-Git revision/dirty are null. Record changes without mandatory snapshots/hashes.
- `tracks`: `{id, scope, selected_base_ids, applicability, status, remaining_question_ids, rationale, review}`. Applicability states facts/sources/limits. Inapplicable tracks may be completed with rationale, rather than inventing an N/A assessment status. Do not default review to pass from exit/checker results.
- `inventory`: `{id, kind, name, locations, discovery_source, certainty, track_ids, scope_decision}`, adding protocol/entrypoint/input where useful. Findings/rule allowlists do not define inventory.
- `questions`: `{id, question, base_question_id, track_id, surface_ids, expectation, expectation_source, techniques, round_ids, manual_review_ids, result, status, next_step}` plus `closure_condition`, `recorded_at`, `introduced_after_round_id`, `changes` under [checkpointing](tester-workflow.md). Base is nullable for new questions. Distinguish supplied policy from source hypotheses and planned from executed techniques. Results may be objects separating source facts, dependencies, and feasible steps. Do not backfill historical reports to imply prior observations.
- `rounds`: `{id, purpose, started_at, finished_at, command, cwd, targets, source_state_id, engine, version, rules_selection, exclusions, privacy, exit_code, errors, skips, timeouts, counts, status, finding_ids}`. Redact argv. Record rule origin/files/IDs and configured versus actual capability. Privacy reflects actual settings/guard; metrics off does not establish blocked networking. Show exclusions/suppressions/missing source. Unreadable errors/skips remain null.
- Round `counts`: `native_matches`, `rules_configured`, `rules_loaded`, `rules_executed`, `candidate_files`, `scanned_files`, `skipped_files`, `excluded_binary_files`, each actual or null. YAML/`time.rules` do not establish loaded/executed counts; do not subtract incompatible units.
- `manual_reviews`: `{id, question_ids, source_state_id, locations, call_paths, observations, controls, expectation, finding_ids, evidence_ids}`. Record actual implementation reviews and source state separately from native execution.
- `coverage`: answered questions/source, skips/unsupported/unread/untriaged scope and effects, with explicit units. Files scanned do not establish endpoint/role/runtime coverage. Use `coverage.inventory_candidate_reviews` for candidate accounting rather than inventing inventory surfaces for every match.
- `limitations`, `unperformed`, `next_steps`: affected scope, reasons, attempted remedies, and resumption conditions. Preserve remaining question IDs and execute feasible steps before handoff.

## Operator self-review

Each new `tracks[].review` records actual `reviewed_at` and `reviewer_mode` (`operator-self-review`, or the real requested reviewer), `process_assessment`, `evidence_assessment`, `remaining_dependencies`, and `next_steps`.

Process assessment evaluates scope/claims/triage against inventory/questions/rounds/manual work and specific gaps. Evidence assessment evaluates native accounting, claims/controls, source locations/provenance, and support for current observations separately from bookkeeping checks. Link policy/runtime/source/capability dependencies to questions. Do not leave feasible source steps merely recorded before moving on. Empty arrays mean genuinely none.

These assessments differ from status: supported issues do not imply a poor process; evidence sufficient for a needs-review record does not resolve required triage. No numeric score, oracle, hashes, or second reviewer is required. Do not fabricate historical self-reviews.

## Candidate ledger and reconciliation

Each `coverage.inventory_candidate_reviews` record contains `id`, `round_id`, `native_result_index` (0-based, null if unrecoverable), `rule_id`, `location`, `question_ids`, `manual_review_ids`, `candidate_kind`, `context_read`, `disposition`, `finding_ids`, `next_step`.

Account for every `(round_id, native_result_index)`, both inventory-only and security observations, retaining genuine many-to-many links. Missing output requires an accounting gap/status rather than fabricated rows. Tester dispositions may be open, inventory-only-closed, promoted-to-observation, or a specific description; they are not automated vulnerability verdicts. Non-promoted candidates retain context/responsibility. Native counts include **all** results. Shared-location detectors may share review while retaining each native index/rule/message; the tester determines common root causes.

`report_records.py` creates drafts/questions without decisions; `record_round.py` collects private output without triage; `check_report_links.py RUN.json ALERTS.json` checks IDs/references/known counts/provenance without editing or certifying source evidence/verdicts. See [operations](semgrep-operations.md) and [tests](../tests/README.md). They create no third handoff file or approval gate.

Check assessment/status agreement, reciprocal IDs, occurrence→round, evidence→source state/operation, manual review→evidence/finding, question→inventory/base/track, remaining questions, and declared count units. Re-read/retest affected source changes or retain explicit limits. Retest against actual diff/rules/paths/ignores/engine; disappearing matches from suppressions/filter changes do not establish fixes. Preserve historical output/verdicts and identify unretested scope.

Use [synthetic examples](../examples/README.md) and [validation](validation.md) with their limits. Final responses use **Operations** and **Limitations**, with actual work, per-track completion, both file links, unfinished work/remedies/resumption conditions, and claim limits. Skill maintenance reports changes/validation without fabricating product assessments.
