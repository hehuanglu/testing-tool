# Discovery → questions → techniques → readback → reconciliation

Apply this loop per track under the [sequential workflow and self-review](sequential-track-workflow.md). Collect, triage, and review the current track's ALERTS/RUN before executing the next track.

## Discover independently of findings

Verify user-selected source roots. Read applicable AGENTS instructions, architecture/specifications/configuration, and Git revision/dirty state when available. Start with `rg --files` and focused searches. Distinguish source, vendor/generated code, tests, and configuration according to scope. Do not install dependencies or build merely for source review.

Inventory HTTP method/routes, GraphQL/RPC operations, jobs/events, libraries, frontend surfaces, and configuration as relevant. Record module/function, locations, discovery source/certainty, track, and scope decision. A single GraphQL URL or several matches do not define complete inventory. Public/protected classifications come from actual routing/guards and carry uncertainty; they are not runtime login tests.

Trace input → processing → sink/response/persistence. Identify principal, object/tenant/relation/state, and controls. Map shared code to in-scope callers; do not multiply one root cause by caller count. Account/organization/workspace/member are examples, not an ownership-name allowlist: inspect actual models/schemas/repositories.

Inspect `.semgrepignore`, `.gitignore`, `nosemgrep`, configurations, rules, and scripts. Existing exclusions are not automatically user-approved scope reductions. Ignored or unsupported in-scope source remains a responsibility.

## Question instances

From the selected [bases](track-intents.md), record each instance in RUN:

- `id`, `base_question_id` (null for new questions), `track_id`, and inventory-linked `surface_ids`.
- A functional source question, such as whether an invoice filename from a job payload can escape its export directory, rather than only “path traversal.”
- `expectation` and `expectation_source`: supplied policy/spec/configuration or a labeled source assumption.
- `techniques`, rule selection/search/manual review, limitations, and actual `round_ids`/`manual_review_ids`.
- `result`, `status`, `next_step`: observations, conclusions at the assigned level, and remaining action.
- `closure_condition`, `recorded_at`, `introduced_after_round_id` (null before a round), and timestamped/reasoned `changes`.

Base labels do not replace answers. Missing rules/policy do not automatically imply N/A. Do not generate every field × rule × actor × state combination when it cannot change the question.

### Local checkpoint before execution

Save known scope, source state, inventory, and questions in RUN before starting a round. Leave unobserved fields null/open with reasons. Link only actual rounds/reviews. The [record initializer](../scripts/report_records.py) can help; a draft is not a completed handoff. Do not add another handoff file or permission checkpoint. Incomplete inventory does not block independent discovery/checks.

Record newly discovered branches with their actual time and `introduced_after_round_id`. Record changes as `changes: [{at, after_round_id, field, previous, current, reason}]`. Do not rewrite history to imply every question was planned. Checkpoints need no snapshot/hash requirement.

### Split instances when conclusions may differ

Split when trust source, action, control, persistence/consumer, expectation, or closure condition differs: create/update overwrite order; enrollment/login verification/bcrypt configuration; detail/update/delete, collections/counts, and relation linking. A resolved branch must not hide unresolved work. Group only when shared implementation/control and caller mappings support it. Do not impose six instances per track or a Cartesian product.

Complete track-specific ledgers in `questions[].result` objects or `manual_reviews[].observations`, linking inventory/questions/actual work before handoff. Do not defer operation/UI/configuration mappings to another reviewer. Group shared callers with justification, without prescribing row counts or an extra report collection.

## Select and execute

Inspect the [catalog](rule-catalog.md), actual local rules, languages, paths, patterns, engine, and privacy settings. Combine Semgrep inventory/taint/search with manual source review. TS rules cannot clear Python/Java/Go: use applicable local/custom rules with useful fixtures, feasible review, and explicit capability gaps.

Search/inventory matches belong in inventory/questions. Create a security observation only when there is a describable security concern; use needs-review when support is incomplete. Keep custom product mappings outside the core. Do not fetch remote rules or change engines to close a track.

Split rounds by targets/questions/resources. Combine cross-track execution only at the user's request, retaining actual question/track provenance. Follow the [CLI guide](semgrep-operations.md) for command, source state, rules, exclusions, and private per-round output outside the product. Temporarily excluding broken source does not remove it from scope.

Map `questions[].techniques` to actual native rule IDs/capabilities/targets and manual reviews, using objects or explicit references. “Scanned YAML” is insufficient for every question. Manual-only questions gain no native coverage from sharing a track; do not attach unrelated round IDs to fill fields. Record post-readback mapping changes rather than backdating them.

## Read and continue

Inspect exit status, JSON, errors/skips/timeouts, and source. Read actual sanitizer/guard/repository imports and implementations, callers, and effective overrides; names such as `sanitize`, `user`, or `verify` do not establish controls. CE has cross-function/file limits: manual review may answer a SAST question but must remain manual provenance.

Reconcile every inventory item/question under the [responsibility loop](responsibility-loop.md), execute feasible open steps, review process/evidence separately under the [track workflow](sequential-track-workflow.md), and deliver that track's [two files](reporting-and-completion.md). If specifically requested native execution remains unavailable, preserve it as unexecuted. Retest against diff/ignore/rules/source state; disappearing matches alone do not establish fixes.
