# Agent-controlled operation dispatch

For new `criteriaWorkflow.version:3` assessments, [criteria-driven workflow](criteria-driven-workflow.md) owns intake, approval, assigned cases and completion. Historical version 2 retains its original approval contract. Use the operation/executor/readback primitives below within the approved plan. Legacy inventory/round duties and the v1 CLI continuation path cannot add scope, authorize dispatch or override the criteria reviewer.

This is a decision/execution workflow linked from SKILL.md, rather than an automatic whole-product scanner. Use actual [operations](native-operation-routing.md) and [runners](runner-routing.md), completing assigned actions instead of returning only plans. `inspect_operations.py` inspects source/registration/catalog drift without dispatching traffic.

## Define the task before selecting an executor

For user criteria, follow [security scope intake](criteria-driven-workflow.md): source + product → applicability/questions → suitable techniques → bounded execution/readback → criterion reconciliation. Scope is independent of track admission; source/config/document reads may support applicability, expectations and fixtures under the ZAP result boundary, not create source-only findings or close criteria beyond observable ZAP capabilities. Do not let runner availability redefine the requirement or catalog content expand target authority.

Use [context](tester-context.md)/[track intents](track-intents.md) for new or uncertain scope. Read the sections relevant to the current decision and reuse understood, unchanged guidance across blocks. Reopen references when their content, selected path or interpretation changes; do not batch-read the same reference bundle after each round. Live dependency checks remain necessary. Distinguish assessment from status/setup/audit/skill edits; the latter do not automatically scan. BE does not open FE/BOLA. Resolve FE versus BE when “authenticated” would materially change UI work.

Keep product/environment/origins, track/scope, independent inventory, roles/actors/fixtures, open duties, running/unknown operations, and read results in existing plan/RUN without a new schema. Establish [v2 verdict and completion conditions](criteria-driven-workflow.md#verdicts-and-completion) before selecting work blocks; distinguish them from a block objective or product remediation. Recipes/folder names/history do not establish new-product authority. A responsibility is a test question for endpoint/role/input or UI journey/state, with object/action/relation for BOLA and meaningful prerequisites/observations. Allocations execute subsets rather than replace inventory. Incomplete inventory requires continued discovery.

For intake continuation, use the [private progress checklist](retention-stop-and-recovery.md#operator-schedule-and-crash-checkpoint). For execution continuation, start at official RUN/continuation and its relevant scope/operation records; reconcile pending/unknown journal/ACK/state before dependent effects. Reuse stable facts/results, selectively revalidate the next action's live dependencies, then choose useful preparation or execution under [checkpoint/resume](retention-stop-and-recovery.md#working-session-checkpoints). Consult relevant [knowledge](operational-knowledge.md), which does not replace run state or authorization. A new context does not require whole-product rediscovery, every actor/fixture, or a new login.

## Select operations before runners

Distinguish source presence, runtime exposure, compatible input/auth/vector, and observed execution. Inspect actual input properties/types/requiredness/constraints and auth provider/configuration/session semantics rather than names alone.

Map definitions→import; links/JS→crawl; authentication→profiles/context/users; input techniques→policy/active; findings→passive/report; recovery→status/history/jobs; multiple native jobs→AF where appropriate. Use guided when sufficient, exposed expert when needed, and direct/queue according to topology. Do not enable new surfaces/change shared scanners automatically.

Reuse whole runners only when admission/workload/assumptions/side effects fit; otherwise reuse suitable fixture/identity/seed/oracle/browser/collector/journal helpers. Classify gaps as registration/configuration, input mapping, product fixtures/selectors/policy, generic mechanisms, or actual repository/engine limits. Prefer authorized configuration/orchestration → minimal product adapters → justified runners → underlying capability changes only within assigned development scope. Do not downgrade techniques to allowlists or fabricate parameters/proofs.

### Compare actual deployment contracts

Inspect the selected deployment's complete tools/list pages, actual image/JAR, required workload fields and verified auth semantics. When choosing between deployments, compare those contracts for each candidate; a second deployment is not a prerequisite for ordinary dispatch. `executor_routing.choose_executor` is read-only compatibility, not authorization/admission/qualification. `authSessionId` or matching versions do not establish authentication compatibility. Authenticated starts must actually attach a nonempty prepared `authSessionId`; session-validation metadata alone does not attach it (`prepared-auth-session-missing`).

Compatible shared operations may be selected. Missing required schema fields mean `schema-field-missing`/not-operated, rather than sending unsupported fields. Consider an existing compatible dedicated runtime when shared is insufficient. Distinguish `not-exposed`, `input-error` for types/constraints, `configuration-error` for auth kind/config/session, and `execution-failed` only after dispatch. If no candidate fits, preserve the missing primitive/mapping and continue independent work. Do not enable expert/experimental JSON bearer or migrate shared deployments merely to pass selection.

Exact method/body semantics need separate inspection: the candidate currently needs **direct + valid prepared form/json-bearer**, rather than generic anonymous body support inferred from method/postData fields. Qualification needs actual seed baseline, method/body readback, response/post-state, and terminal status. Verified flat JSON PUT does not establish POST/PATCH/DELETE/path/all-input/UI support. Queue/AF/snapshot/release features are conditional, not mandatory stages.

## Execution paths

**Native orchestration:** suitable import/seed → auth if needed → purposeful crawl/active → status → passive → findings/report. Preserve returned IDs and operation types. No generic MCP seed tool exists in the current catalog; use verified proxy/direct/UI/fixture adapters with correct provenance. Avoid inappropriate raw credential fields/argv.

**Common backend:** discover/materialize/plan/prepare or import-actor/run only when recipes/inputs/runtime fit. Inspect vector/rule/proof limits. Common rejection does not authorize legacy product-run fallback. Native DAST/direct BOLA may use separate authorized allocations with attribution.

**Frontend:** select the track CLI/reviewed observations/verified product adapter. Real browser UI is required; crawlers support discovery, and applicable active work addresses related APIs/inputs. Preserve actor/origin mapping across setup/auth/native/browser. Missing hooks block dependent journeys only; add product-specific hooks where needed.

**BOLA:** compile policy-derived expectations, prepare legitimate actors/objects, run positive and cross-owner/role cases, inspect response/state, and reconcile. Send reportable comparisons through ZAP sendRequest or a verified ZAP proxy. Direct clients bypassing ZAP support fixture setup only; they supply no ZAP-derived coverage or alerts. Tester-observed issues remain distinct from native detector alerts.

**Product-local extension:** place adapters/runners in private product working areas outside final reports. Require explicit product/environment/selection; do not infer targets from containers or old defaults. Reuse scoped primitives and implement only missing fixture/UI/post-state mappings. Shared-core repairs require caller/plan-pin impact analysis and preservation of old hashes/runs.

## Minimal additional-runner contract

Create only for a demonstrated gap after inspecting existing runners. Accept current discovery-derived selection/actors/fixtures and verified origins/roles, without credential argv/shared logs. Distinguish read/setup/mutation/crawl/active/UI/direct, journal intent before side effects and IDs/ACK/outcomes afterward. Bound rounds/rates, monitor sessions/status, stop only owned producers, and reconcile unknown outcomes before retry.

Return actual results/errors/unperformed work to collectors without deriving security pass/completion from exit 0. Cleanup only authorized run-owned resources; retain with reasons when deletion is unavailable. Verify meaningful new request/actor/failure/unknown/parser/state behavior, rather than fixed expected verdict assertions or whole-platform qualification. Product-specific verified routes/selectors are allowed; hardcoded verdicts/fake responses/arbitrary passing owners/foreign policies are not. Generic mechanisms still isolate product configuration/state.

## Plan a work block across bounded rounds

State the opening chat objective and its closure conditions in a short commentary before substantive work, including why it advances assessment completion. Reuse `continuation.currentFocus` or existing plan/RUN fields for objective, linked questions, closure conditions, progress and final objective outcome; these describe the chat, not a new executor gate. Legacy RUNs without this detail remain usable: recover it selectively. A preparation/diagnosis objective is valid when it resolves a concrete prerequisite, rather than promising an ungrounded scan count.

Group related valuable questions that share actors, fixtures, runtime, baselines and knowledge. Size the block by dependencies, risk, readback and usable context, without fixed request/round/token quotas. A block may include preparation, multiple separately bounded scans/mutations, readback and repair; it does not enlarge scope or executor budgets. Avoid repeated sessions that each perform a few checks and repeat setup/handoff. Do not add low-value tests merely to consume context.

Maintain intent/ACK/pending state in existing journals as execution proceeds. Reuse valid discovery, documents, tokens, fixtures and results; recheck only changed/uncertain dependencies and the live prerequisites required by the next action. Keep intermediate reconciliation private, but synchronize and verify the Sheets table at final delivery or whenever the user asks to update progress, check status, view the table or receive its link. Persisting recovery state does not end the turn.

After each meaningful readback, compare actual results with the selected closure conditions. Mark answered questions as such; keep specific missing observations open. Choose the next action for its contribution to closing an assigned question or removing a dependency, and reuse current knowledge where useful. Do not select work merely because another header/path/rule can be run or because the latest runner suggests it. If the opening objective is met, say so in commentary and select the next objective within scope. If it is blocked, retain it and continue useful independent work. A changed fixture/vector/role does not itself end the chat; assess whether the current understanding still supports that block safely.

## Execute, diagnose, and continue

Check case-specific deployment/identity/fixture/state/auth/vector/resource prerequisites and meaningful baseline. If the intended handler is not reached, repair fixtures/inputs or bound claims. Track guided operationId, native scanId, queue jobId, auth sessionId, AF planId/planPath correctly. Starts/timeouts/lost ACKs differ; reconcile owned status before retry. Guided direct idempotencyKey is not guaranteed duplicate prevention.

Diagnose actual local failures, repair minimally, verify purposefully, and continue independent actors/fixtures. Resource breaches stop affected producers. Preserve gates/pins; identify specific implementation dependencies rather than forging receipts or opening unlimited qualification. Existing adapter-owned native APIs follow their contracts; raw ZAP is not a default bypass for MCP destination/auth/policy rejection.

## Reconcile independently of runners

Check all inventory method/routes/protocol operations, actual differing roles, owner/non-owner applicability, genuine UI actions, correct authenticated sessions, input techniques/outcomes, validation/guard/fixture blocks, unknown side effects, and cleanup. Crawled routes, existing roles, and traffic labels do not substitute for missing responsibilities. Retries add no new coverage; historical unretested findings remain labeled.

For v3 (and retained v2), reconcile approved cases with `scope criteria-review` and retained coordinator/journal state. Legacy `reconcile_responsibilities`/continuation helpers cover supplied cases only and cannot establish criteria-workflow completion; validate the relevant inventory yourself. Keep unsupported responsibilities with reasons/next steps and execute eligible work without per-subset approval. Distinguish ended rounds, grounded open-work decisions, and completed assignments. Baseline/passive or a non-not-operated row does not close applicable active/UI/relation duties. Follow [open-work decisions](local-remediation-and-continuation.md#decisions-for-open-work).

`review_open_work.py` optionally checks caller-defined responsibility decisions/checkpoints read-only; it does not discover inventory/dispatch/authorize or replace reconciliation. See [knowledge](operational-knowledge.md#optional-review-helper). Tool Next Actions do not authorize other tracks/release bundles. [Validation](operational-validation.md) distinguishes smoke from full acceptance.

## Close and report

Deliver the [Drive assessment table](product-assessment-handoff.md) from reviewed results, filtering secrets and retaining RUN/ALERTS/SCOPE_ALERTS and technical artifacts internally. Apply the [v2 verdict and completion rules](criteria-driven-workflow.md#verdicts-and-completion) after reconciliation: finish answered scope, execute useful feasible open work, or preserve partial scope at an actual [checkpoint](retention-stop-and-recovery.md#working-session-checkpoints). A completed small round is not a handoff reason. Save recovery state during work; at a checkpoint preserve open duties and specific next actions. No exhausted-options proof or fabricated blocker is needed. A user stop or diagnosed absence of valid continuation permits ending work, not labeling unresolved scope complete; use blocked only for actual dependencies. Tests/runtime success/zero alerts do not establish product safety.
