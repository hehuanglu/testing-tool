# Discovery → questions → techniques → readback → reconciliation

Apply this loop under the [criteria workflow](criteria-workflow.md). Map question IDs to the criteria they answer.

## Discover independently of findings

Verify user-selected source roots. Read applicable AGENTS instructions, architecture/specifications/configuration, and Git revision/dirty state when available. Use the requested commit when specified. Otherwise identify the actual worktree state. Record changed in-scope paths and avoid commit permalinks for locations that differ from the commit. Start with `rg --files`, language extensions, manifests (such as `pom.xml`, `package.json`, `requirements.txt`), and focused searches. Distinguish source, vendor/generated code, tests, and configuration according to scope. Do not install dependencies or build merely for source review.

Inventory HTTP method/routes, GraphQL/RPC operations, jobs/events, libraries, frontend surfaces, and configuration as relevant. Record module/function, locations, discovery source/certainty, track, and scope decision. A single GraphQL URL or several matches do not define complete inventory. Public/protected classifications come from actual routing/guards and carry uncertainty; they are not runtime login tests.

Trace input → processing → sink/response/persistence. Identify principal, object/tenant/relation/state, and controls. Map shared code to in-scope callers; do not multiply one root cause by caller count. Account/organization/workspace/member are examples, not an ownership-name allowlist: inspect actual models/schemas/repositories.

Inspect `.semgrepignore`, `.gitignore`, `nosemgrep`, configurations, rules, and scripts. Existing exclusions are not automatically user-approved scope reductions. Ignored or unsupported in-scope source remains a responsibility.

## Reconcile inventory in both directions

Before execution, walk each selected criterion through its questions to the affected surfaces and conditions. Then walk each discovered surface back to the applicable questions. For a surface without a mapping, record whether it is outside the assignment, inapplicable with a product-grounded reason, or an open discovery gap. Check every question for a link to a selected criterion and the current inventory, including questions omitted from the criterion rows. If a shared control is used to group surfaces, check each caller and split any branch with different behavior or evidence needs.

After readback, compare planned paths and relevant source or configuration inventory with the actual scanned paths and known skips or suppressions. Account for discrepancies by affected question. Distinguish non-code assets, justified exclusions, covered manual reviews and source that still needs work. A path appearing in scan output establishes that the engine scanned the file, while a question-level claim still needs an applicable rule or manual evidence. If readback reveals a new surface, update the inventory and question mapping with the actual discovery time.

For each open question or unmapped in-scope surface, keep its stable ID, known source locations, unresolved fact, and next concrete check or external dependency in RUN so another operator can resume.

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

Save known scope, source state, inventory, and questions in RUN before starting a round. Leave unobserved fields null/open with reasons. Link only actual rounds/reviews. The [record initializer](../scripts/report_records.py) can help; a draft is not a reviewed result. Use the consolidated plan decision for material scope or expectation questions. Incomplete inventory does not block independent discovery/checks.

Record newly discovered branches with their actual time and `introduced_after_round_id`. Record changes as `changes: [{at, after_round_id, field, previous, current, reason}]`. Do not rewrite history to imply every question was planned. Checkpoints need no snapshot/hash requirement.

### Split instances when conclusions may differ

Split when trust source, action, control, persistence/consumer, expectation, or closure condition differs: create/update overwrite order; enrollment/login verification/bcrypt configuration; detail/update/delete, collections/counts, and relation linking. A resolved branch must not hide unresolved work. Group only when shared implementation/control and caller mappings support it. Do not impose six instances per track or a Cartesian product.

Complete the relevant technical ledgers in `questions[].result` objects or `manual_reviews[].observations`, linking inventory/questions/actual work before handoff. Do not defer operation/UI/configuration mappings to another reviewer. Group shared callers with justification, without prescribing row counts or an extra report collection.

## Select and execute

Inspect the [catalog](rule-catalog.md), actual local rules, languages, paths, patterns, engine, and privacy settings. Combine Semgrep inventory/taint/search with manual source review. TS rules cannot clear Python/Java/Go: use applicable local/custom rules with useful fixtures, feasible review, and explicit capability gaps.

Search/inventory matches belong in inventory/questions. Create a security observation only when there is a describable security concern; use needs-review when support is incomplete. Keep custom product mappings outside the core. Use authorized, inspected local rule copies and the planned engine.

Group compatible rounds across criteria and tracks. Split by incompatible targets, filters, rules, engine, or diagnostics. Retain actual question and rule/target mappings. Follow the [CLI guide](semgrep-operations.md) for command, source state, rules, exclusions, and private per-round output outside the product. Temporarily excluding broken source does not remove it from scope.

Map `questions[].techniques` to actual native rule IDs/capabilities/targets and manual reviews, using objects or explicit references. “Scanned YAML” is insufficient for every question. Manual-only questions gain no native coverage from sharing a track; do not attach unrelated round IDs to fill fields. Record post-readback mapping changes rather than backdating them.

## Read and continue

Inspect exit status, JSON, errors/skips/timeouts, and source. Read actual sanitizer/guard/repository imports and implementations, callers, and effective overrides; names such as `sanitize`, `user`, or `verify` do not establish controls. CE has cross-function/file limits: manual review may answer a SAST question but must remain manual provenance.

Reconcile every inventory item/question under the [responsibility loop](responsibility-loop.md), execute feasible open steps, review process and evidence separately under the [criteria workflow](criteria-workflow.md), and persist reviewed [private records](reporting-and-completion.md) for delivery. If specifically requested native execution remains unavailable, preserve it as unexecuted. Retest against diff/ignore/rules/source state; disappearing matches alone do not establish fixes.
