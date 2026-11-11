# Private assessment records and completion

## Separate status dimensions

Rounds use `completed`, `partial`, `blocked`, `interrupted`. Completed means readable valid output with no error preventing the round's objective; findings do not prevent completion. Partial means meaningful but incomplete work, blocked means no meaningful check could execute, and interrupted means execution was interrupted. Retain native exit/counts/errors separately.

Assessments and technical groupings use `completed`, `partial`, `blocked`, `stopped`. Completion requires reconciled inventory/scope and assigned triage with no eligible unfinished step. Supported issues do not imply partial status. Required unresolved source/questions/triage mean partial; no meaningful assessment means blocked; user-requested termination means stopped. Continue independent branches.

Questions use `resolved`, `open`, `blocked`, `not-applicable`. Resolution needs a supported answer at the assigned level and may identify an issue. Required needs-review triage keeps questions unresolved. Candidates-only tasks may resolve detector-search questions while explicitly excluding further triage; do not call them completed security audits. N/A needs applicability grounds, rather than missing rules.

## Storage and versions

Maintain one **RUN.json and ALERTS.json** pair for the assessment at a stable private location outside source targets. Preserve earlier assessment records and original round evidence on retest. Produce the [Google Sheets handoff](sheets-delivery.md) from reviewed records. Technical tracks may share rounds and source reviews.

Keep raw/log/rules/settings private; do not require evidence folders, archives, hash manifests, EVALUATION files, or canvases. Record self-review in RUN `review` for criteria assessments; produce a separate evaluation only when requested. Embed [evidence](evidence.md) in ALERTS. Setup/audit/skill maintenance does not authorize product assessments or fabricated result files.

Schemas are `semgrep-tester-alerts-v2` and `semgrep-tester-run-v2`: recording contracts rather than new framework/approval gates. The criterion fields below extend v2 records. Read historical v1/v2 and per-track pairs as-is. Identify missing evidence without rewriting history. Verify compatibility and retain original provenance before reusing observations. Blocked-before-scan findings may be `[]`, but unknown native counts remain null and status states that no scan occurred. Preserve actual manual observations.

## Criterion records

In RUN, keep the plan and its reviewed results together:

- `plan` records the scope/expectation decision, its source and timestamp, and any material changes with reasons. For a broad assessment, record the main challenges raised in plan review, how they were resolved, and open dependencies by criterion or question ID. Link the source state and keep planned methods distinct from actual round/review IDs.
- Record the exact initial plan revision and its approval state in `plan`. Retain [follow-up revisions](criteria-workflow.md#plan-the-next-pass-from-coverage-gaps) in `plan.follow_up_revisions`. Each revision has a stable ID, baseline review and source-state references, work items and dependencies mapped to criterion/question IDs, approval state, the user approval for that exact revision when received, and execution state. Preserve earlier revisions and actual results. Pending or approved work does not increase coverage until readback supports it. Historical records may omit this field.
- `criteria[]` holds `id`, `wording`, `source`, `interpretation`, `selected`, `selection_reason`, `applicability`, `applicability_reason`, `question_ids`, `coverage`, `conclusion`, `finding_ids`, `evidence_ids`, `remaining_question_ids`, `gaps`, and `next_step`. Coverage records `level`, checked questions/surfaces, methods and limits. Use the [four criterion decisions](criteria-workflow.md#conclude-independently). Reevaluate historical conclusions from retained evidence when projecting to the Sheet and preserve the original records. A historical bounded negative is insufficient for Pass without full evidence. Criterion links may share questions and evidence when the mapping supports each claim.
- `review` records actual operator self-review for the assessment. `delivery` records the spreadsheet ID/URL when known, the status of the latest write/readback and when it was verified.
- In ALERTS, give every supported finding an `issue_id` stable within the assessment. Use the same issue ID for records that support the same confirmed issue. Preserve distinct finding IDs and occurrences. Keep `issue_id` null until supported and grouped, and record tester confidence with rationale when assessed separately from native confidence.

Resolve criterion questions against RUN and finding/evidence IDs against ALERTS. Check that each linked observation answers a mapped question. Reconcile remaining questions against actual readback and required triage. For assessment completion use assigned criteria and obligations, including any required native execution.

In a RUN with criteria, each supported or needs-review finding must link to at least one selected criterion. The link checker flags missing links so the Sheet projection cannot silently drop reportable findings. Historical RUN records without criteria retain their existing checks.

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
- `reviewed_risk`: for a supported Semgrep-detected issue, record `{level, rationale, evidence_ids}` with level `critical`, `high`, `medium`, `low` or `unrated`. The rationale explains impact, prerequisites and any material assumptions or missing context. Evidence IDs resolve to retained evidence supporting that issue. Keep one consistent rating per Semgrep-detected issue ID. Use null for agent-only issues and other dispositions. If a historical Semgrep-detected issue has no rating, surface the rating gap in Notes until reviewed. Exclude any historical agent-only rating from the Sheet risk counts. Preserve the original record.
- `tester_priority`: null or `{value, rationale}`, separate from native severity; no arbitrary CVSS mapping.
- `evidence` under the [evidence contract](evidence.md), and `evidence_gaps` affecting claims.

## RUN.json

Include:

- `schema`, `assessment_id`, `status`, `started_at`, `finished_at`, `product` (paths/roots/languages/frameworks/known revision), `scope` (request/source, triage depth, exclusions).
- `source_states`: `{id, roots, observed_at, revision, dirty, notes}`. Unknown/no-Git revision/dirty are null. Record changes without mandatory snapshots/hashes.
- `tracks`: `{id, scope, selected_base_ids, applicability, status, remaining_question_ids, rationale}` for the technical groupings referenced by questions. Historical records may also include track-level `review`. Use assessment-level self-review for new criteria assessments.
- `inventory`: `{id, kind, name, locations, discovery_source, certainty, track_ids, scope_decision}`, adding protocol/entrypoint/input where useful. Findings/rule allowlists do not define inventory.
- `questions`: `{id, question, base_question_id, track_id, surface_ids, expectation, expectation_source, techniques, round_ids, manual_review_ids, result, status, next_step}` plus `closure_condition`, `recorded_at`, `introduced_after_round_id`, `changes` under [checkpointing](tester-workflow.md). Base is nullable for new questions. Distinguish supplied policy from source hypotheses and planned from executed techniques. Results may be objects separating source facts, dependencies, and feasible steps. Do not backfill historical reports to imply prior observations.
- `rounds`: `{id, purpose, started_at, finished_at, command, cwd, targets, source_state_id, engine, version, rules_selection, exclusions, privacy, exit_code, errors, skips, timeouts, counts, status, finding_ids}`. Redact argv. Record rule origin/files/IDs and configured versus actual capability. Privacy reflects actual settings/guard; metrics off does not establish blocked networking. Show exclusions/suppressions/missing source. Unreadable errors/skips remain null.
- Round `counts`: `native_matches`, `rules_configured`, `rules_loaded`, `rules_executed`, `candidate_files`, `scanned_files`, `skipped_files`, `excluded_binary_files`, each actual or null. YAML/`time.rules` do not establish loaded/executed counts; do not subtract incompatible units.
- `manual_reviews`: `{id, question_ids, source_state_id, locations, call_paths, observations, controls, expectation, finding_ids, evidence_ids}`. Record actual implementation reviews and source state separately from native execution.
- `coverage`: answered questions/source, skips/unsupported/unread/untriaged scope and effects, with explicit units. Files scanned do not establish endpoint/role/runtime coverage. Use `coverage.inventory_candidate_reviews` for candidate accounting rather than inventing inventory surfaces for every match.
- `limitations`, `unperformed`, `next_steps`: affected scope, reasons, attempted remedies, and resumption conditions. Preserve remaining question IDs and execute feasible steps before handoff.

## Operator self-review

RUN `review` records actual `reviewed_at` and `reviewer_mode` (`operator-self-review`, or the real requested reviewer), `process_assessment`, `evidence_assessment`, `remaining_dependencies`, and `next_steps`.

Process assessment evaluates scope/claims/triage against the criterion plan, inventory, questions, rounds, manual work, and specific gaps. Evidence assessment evaluates native accounting, claims/controls, source locations/provenance, and support for current observations separately from bookkeeping checks. Link policy/runtime/source/capability dependencies to questions. Route feasible new work through follow-up planning and proceed with approved work when execution is assigned. Empty arrays mean genuinely none.

These assessments differ from status: supported issues do not imply a poor process; evidence sufficient for a needs-review record does not resolve required triage. No numeric score, oracle, hashes, or second reviewer is required. Do not fabricate historical self-reviews.

## Candidate ledger and reconciliation

Each `coverage.inventory_candidate_reviews` record contains `id`, `round_id`, `native_result_index` (0-based, null if unrecoverable), `rule_id`, `location`, `question_ids`, `manual_review_ids`, `candidate_kind`, `context_read`, `disposition`, `finding_ids`, `next_step`.

Account for every `(round_id, native_result_index)`, both inventory-only and security observations, retaining genuine many-to-many links. Missing output requires an accounting gap/status rather than fabricated rows. Tester dispositions may be open, inventory-only-closed, promoted-to-observation, or a specific description; they are not automated vulnerability verdicts. Non-promoted candidates retain context/responsibility. Native counts include **all** results. Shared-location detectors may share review while retaining each native index/rule/message; the tester determines common root causes.

For a RUN containing `criteria`, the link checker flags missing indexes per round when the native count is known, including on interim reports. An open triage item can still have a ledger row if its actual index is available. A row with an unknown index does not satisfy a known count. Keep genuine gaps visible if the underlying output cannot be recovered. Historical reports without `criteria` retain their existing link checks.

`report_records.py` creates drafts/questions without decisions; `record_round.py` collects private output without triage; `check_report_links.py RUN.json ALERTS.json` checks IDs/references/known counts/provenance without editing or certifying source evidence/verdicts. See [operations](semgrep-operations.md) and [tests](../tests/README.md). They create no third handoff file or approval gate.

Check assessment/status agreement, reciprocal IDs, occurrence→round, evidence→source state/operation, manual review→evidence/finding, question→inventory/base/track, remaining questions, and declared count units. Re-read/retest affected source changes or retain explicit limits. Retest against actual diff/rules/paths/ignores/engine; disappearing matches from suppressions/filter changes do not establish fixes. Preserve historical output/verdicts and identify unretested scope.

Use [synthetic examples](../examples/README.md) and [validation](validation.md) with their limits. Final responses give the verified Sheet link for criteria assessments, actual assessment and delivery statuses, and remaining work or blockers. Skill maintenance reports changes and validation.
