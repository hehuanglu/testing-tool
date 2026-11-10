# Inventory → allocation → readback → next action

> Compatibility reference only. Use [criteria-driven workflow](criteria-driven-workflow.md) for all current assessment execution and [Drive table handoff](product-assessment-handoff.md) for delivery. Legacy schema, completion, CLI and three-report delivery descriptions below interpret retained history; they do not authorize a second operating workflow, new legacy dispatch, or extra mandatory user deliverables. Reuse compatible primitives without migrating historical evidence labels.

For new assessments and `criteriaWorkflow.version:3`, use the [criteria-driven coordinator/reviewer](criteria-driven-workflow.md). Cases enter only through the approved plan. This page supplies legacy inventory/reconciliation mechanics and compatible executor/readback primitives; its inventory/round closure rules cannot expand or close v3 assignments. `scope reconcile`, `scope next-work` and `scope continue` remain v1 commands, not criteria-workflow dispatch entrypoints. Packet dispatch is the Python coordinator API with an already-admitted executor callback.

Shared legacy workflow for all five tracks, preserving executor gates and existing cases/observations with optional version 1 semantic evidence links. Code: `${ASSESSMENT_ROOT}/src/zap_assessment/product_scope.py`; CLI: `scripts/product_assessment.py scope` with assessment dependencies/PYTHONPATH.

## Inventory before workload

Begin with [user security criteria](user-security-scope.md) when supplied. Prepare questions from scope + product without requiring the user to author this inventory. Keep non-endpoint questions in the criteria layer; optionally link `responsibilityIds` to track case IDs. Reconcile every assigned criterion and question, rather than only those mapped to runners or findings. Caller-provided observation labels and associations still require tester interpretation of actual results. Inventory can develop over work sessions with gaps explicit; do not require full discovery or every track's prerequisites before useful local work. Every discovered obligation persists across checkpoints independently of the selected work unit.

Keep `responsibilityInventory` in existing plan/discovery/RUN: `productLocation`, `track`, `complete`, `cases`. Completeness is the tester's discovery assessment, not approval; incomplete means continue discovery. Cases retain `caseId`, available `evidenceRefs`, question, `requiredEvidence` observation types, and meaningful actor/role/state/relation. Baseline/passive does not supply `active:query:q` or `result-read`. Avoid infinite rule/field/role/state products.

`inventory_from_operations` starts from all source operations before recipe selection; it does not establish role/UI completeness or techniques. `select_techniques` adds required units/rationale without executing/closing them. Product-reviewed FE/common inventories must include source duties outside recipes; FE `discover --inventory` and common `plan --inventory` consume them. Recipe-free `discover --product ... --observations ... --output ...` is available. Preserve cookie/SSO facts in `authObservations` rather than inventing bearer support.

Before execution encode validation versus processing/create/store objectives and observation conditions in existing `question`/`requiredEvidence`. Split overly broad endpoint/role cases when input/branch conclusions differ while preserving provenance/links/old duties. Active payload labels do not establish creation/persistence. Adapters must verify each unit's actual semantics rather than copying required labels.

Use [finite closure conditions](assessment-scope-and-completion.md#finite-closure-conditions) to make the inventory an actionable route to completion. At meaningful milestones, update which questions were answered, which exact observations remain missing, and why the next action reduces that gap. Do not leave every route with a copied generic partial reason. A chat may complete its selected objective while the assignment remains partial; neither status replaces the other. If no new coverage was achieved, record whether diagnosis/preparation resolved a prerequisite or left the same dependency unchanged.

## Choose executable options

Use `executor_routing.classify_workload` for nested JSON/content type/auth/roles, then `choose_executor` against real tools/list/auth semantics. Compatibility is not qualification/traffic authorization. Do not send extra-schema fields or alter product bodies/IDs/roles to pass gates. Unsupported duties remain inventory; add authorized minimal mappings/primitives, verify, and allocate anew where suitable.

FE guards support scalar paths with exact ownership; readback `idFormat` selects integer/uuid/slug. Request-policy `jsonSchema` expresses bounded nested input without external references. This does not imply nested native campaigns, cookie FE research, or arbitrary protocols; use suitable verified executors/adapters for other needs.

## Reconcile and execute next steps

For technique-specific results use [question-level readback](operational-readback.md#close-the-selected-question), retaining question units before start and joining actual results into reconciliation. `active_questions` prevents another rule's mutations from closing zero-probe questions; adapters still interpret actual HTTP/fixtures.

`scope reconcile --inventory TASK.json --observations OBS.json --prerequisites PRE.json --output NEW_DIRECTORY` returns all supplied responsibilities, rather than selected workloads only. Observations map case IDs to `matched/violated`, `evidenceUnits`, `resultRead:true`, and required actor/role/state/relation. A violation is still tested when observations suffice. Unknown outcomes remain unknown despite ACK/status. Empty inventory does not establish completion.

Derive observations from actual request/results and [input closure conditions](assessment-scope-and-completion.md#per-input-result-meaning). Never copy requiredEvidence to evidenceUnits or blanket matched/resultRead merely to satisfy helpers. Helpers trust caller labels; verify actual target-input changes, correct identity, processing branch, and readback. Keep unmet units open even when a composer says complete. Do not hide zero probes, auth loss, other-field traffic, or terminal-only scans behind metadata.

Missing work must affect reconciliation input, rather than only limitations prose: retain requirements, omit unobserved units, or split cases. Preserve valid boundary observations for their own questions. Reconcile corrected inputs, then compare `taskCompletion`, `notPerformed`, `nextSteps` against all open duties. Complete plus an untested note and empty gaps is a derived error to repair. Preserve raw results and explain corrected conclusions without presenting retests.

### Match observations to questions

Bind requests/results to actual product/environment, method/route, content type, precise input location, objective, and relevant actor/object/state. Same-named fields in different JSON branches differ. Do not join object A's active work with object B's outcomes or old build data without compatibility review. Same role does not imply same actor/fixture. The legacy `continue_work` path unions by actorRef/role/state/relation and emits a diagnostic for supplied conflicting coverage contexts. Version 1 accumulates links only within equal full declared support contexts; conflicts retain separate `contextHistory` and current missing units. Reviewed per-link compatibility can support a finite inherited observation, not erase an older finding. Callers still verify semantics.

Compare actual app-reaching mutations against effective baselines. Uniqueness setup/session refresh/JSON reordering does not establish variation of an unchanged target field. If guards/mappings replace payloads with seeds, repair mappings without weakening guards. Correct application normalization/sanitization still counts as meaningful processing; raw persistence/exploitation is not universally required.

Valid pre/post sessions do not authenticate redirected/login/denied requests in between. Inspect actual identity/response conditions, retain valid earlier coverage, refresh legitimately, and continue missing work. Later expiry does not erase valid prior observations. Unknown intervals remain open.

Technique N/A stays at its dimension. Helper `disposition: not-applicable` excludes the whole case, so do not apply it to aggregated endpoints with unresolved duties. Split/retain applicable requirements, then reconcile. Missing auth/fixtures/capabilities remain open. Phase/workload labels do not redefine user assignment boundaries.

## Version 1 evidence and work proposals

Legacy responsibility inventories tagged `workflowVersion:1` use feature review from [discovery](product-discovery.md#review-feature-and-api-coverage-in-both-directions), and the [evidence link contract](operational-readback.md#unit-links-and-attempt-history). Python `reconcile(..., operations=existing_operations, attempts=action_history)` validates pointers/context and resolves units; version 1 observations without links supply no units. Do not convert a legacy run into v1 merely to promote old labels.

For example, an operation `{"id":"read-a","status":"partial","readback":{"pin":{"ownerChanged":true}}}` can support `{"operationId":"read-a","observationUnits":["own-read"],"resultPath":"/readback/pin","resultRead":true,"basis":"Read owner preference","context":{"objectRef":"fixture-a"},"role":"support"}` for a matching question. The reconciliation exposes `supportedUnits:["own-read"]` and retains any missing sibling unit; the later attempt failure remains partial.

`work_selection.select_next_work(inventory,reconciliation,prerequisites,attempts,available_action_ids)` shares eligibility with `continue_work`: requires/dependencies, seen actions, relevant unknowns and explicit user stop. It returns `orderedCandidates`, `deferred`, `missingHandlers`, `reasonCodes`, `selectedActionId` and `nextPreparation`. Read-only preview:

```sh
PYTHONPATH="$ASSESSMENT_ROOT/src" "$ZAP_PYTHON" -B \
  "$ASSESSMENT_ROOT/scripts/product_assessment.py" scope next-work \
  --inventory TASK.json --observations OBS.json --prerequisites PRE.json \
  --operations OPERATIONS.json --actions ACTIONS.json --previous PRIOR_DIRECTORY
```

`--actions` and `--previous` are optional for preview; no actions means no claimed executor. Preview has no `--output` and writes nothing. Continue/reconcile accept the same optional `--operations` file. Continue and preview share the previous-history loader, retaining pending intent and operation context. `--stop` means user stop. A proposal is not admission or an operation.

Version 1 order is related state reconciliation with a reader, `usesExistingResult:true` readback, ready execution by `priority:high|normal|low`, then concrete preparation. An action with reviewed `unblocksCaseIds` and `selectionBasis` can prepare a high-impact dependency before low-priority execution. Ties and legacy inputs preserve input order; missing handlers remain visible preparation work, never completion. Unknown on an independent object does not block ready work elsewhere. `max_actions` bounds one invocation only.

### Residual planning alongside execution

For retained partial prose, use [residual atoms and aggregate refinement](user-security-scope.md#residual-review-and-finite-refinement). Do not interpret a generic retained requirement as scanner input. `retained-aggregate` questions without full clause accounting keep completion open; [aggregateReviews](user-security-scope.md#aggregate-accounting-and-round-review) can derive accounted coverage from independently checked children and explicit unanswered limitations. A finite reviewed scope can have no further useful dynamic action while catalog/aggregate work remains partial.

`scope next-work` optionally accepts `--security-scope SCOPE --scope-assessment ASSESSMENT --run WORKING_RUN` together. Product/environment/revision must match the inventory; add explicit inventory `scopeRevision` and identity metadata for this path. Optional `--alerts ALERTS` is needed for finding-referencing residuals. Existing callers need none of these flags. Output keeps old keys and adds `executionProposal` (the existing selector), `planningProposal` (residual readback/preparation/investigation and missing adapters) and `reviewedScopeDecision` with extent/unreviewed refs. No residual helper chooses argv, imports handlers or creates a second scheduler. Missing residualReview is reported as not-supplied without blocking legacy execution; it cannot justify a whole-backlog no-work claim.

Read/reconcile related unknown effects and available results first. A missing reader with useful preparation remains preparationNeeded; another independent ready branch stays eligible. Explicit stop prevents dispatch while retaining next work. A planning proposal has no executor until an existing eligible action/handler passes the shared selector and its admission gates.

## Execute continuation actions

Use `scope continue` with the same three inputs and `--actions ACTIONS.json --output NEW_DIRECTORY`. Ordered case actions have `id`, `kind` (`execute/prepare-fixture/repair/reconcile-state`), `effect` (`read/mutation/start`), `requires`, and optional `dependsOnCases`. Preparation satisfies prerequisites rather than active/UI results. Blocked execution is not dispatched; perform valid fixture/repair steps first.

ACTIONS maps IDs to argv `arguments` for existing product_assessment entries (run/prepare/import-actor/business-fixtures), without shell execution or input-imported code. Preserve original admission and new per-allocation plans/selection/actors/output. `resultBindings` maps checker/native campaign/attack indexes and actual units; UI/direct supplies no active units. `prerequisiteBindings` maps keys to independently verified actorRefs. Adapter `continue_work(...handlers=..., persist=...)` still requires real execution/readback; callback 0 is not coverage.

Journal intent before dispatch and ACK/failure after readback. `--previous PREVIOUS_DIRECTORY` restores observations/prerequisites/actionHistory with scope reconciliation and unknowns retained. `_attempts` recovers journal events when RUN lagged. Do not redispatch prior intent/ACK/unknown actions. Unknowns allow reconcile-state only until state is read. Local exceptions leave cases open while independent actions continue. Round caps/max_actions mean another bounded batch, not inflated caps/lowered reserves.

Persist journal/pending state at round/action boundaries and continue the next valuable feasible block after readback/reconciliation. A cap or returned CLI result ends only that bounded invocation; select another admitted allocation as needed, without raising caps or requiring a user prompt. Hand off at a safe persisted boundary only for the stated [checkpoint reasons](retention-stop-and-recovery.md#working-session-checkpoints), without changing `stop` or `continuationStoppedByUser`: those still mean an actual user stop, not a context handoff. Retain the existing journal and `continuation` references. Pending/unknown state may be saved before it is fully reconciled; readback gates dispatch on resume, not persistence of the checkpoint.

## Repair and allocate anew

Stop only owned producers, inspect IDs/ACK/state/fixtures, preserve old pins/plans/raw, verify fixes for new allocations, and use `remaining_actions` to exclude prior intent/ACK/unknown effects. An ACKed mutation with a failed selector needs remaining readback/UI, rather than another object. Recovery stop/export/cleanup does not end independent task duties.

Follow actual setupRefs and fixture ledgers; one fixture kind does not implicitly create another. Never recreate ACKed IDs. Cleanup exact ledger-owned objects; retain those without authorized DELETE with reasons. Missing permission is a dependency, not N/A; do not re-request existing authorization.

## Handoff

The [single Google Sheets table](single-table-drive-output.md) is the current user-facing deliverable. The commands below describe internal legacy report projections. For the current internal RUN, ALERTS and SCOPE_ALERTS formats, see the [result boundary](zap-result-boundary.md#three-file-result-contract).

`scope report --inventory ... --observations ... --prerequisites ... --run WORKING_RUN.json --alerts EXISTING_ALERTS.json --output NEW_DIRECTORY` uses `compact_results` to write RUN/ALERTS/SCOPE_ALERTS without scanning, reattributing, or granting completion by format. Preserve open duties/actions regardless of exit0/journey counts/scan100%/zero alerts. Legacy workloadCompletion is limited to known cases; actual sufficient observations may also exceed a runner's conservative partial label.

Add `--security-scope NORMALIZED.json --scope-assessment REVIEWED.json` for criterion-level reporting; [examples and revision handling](user-security-scope.md#reporting-and-compatibility). The track input triple is optional for scope-only review. `scope reconcile/continue` remain internal RUN/journal commands, not handoff bundles. Recomposition requires no new traffic; prior unknown mutations remain subject to existing journal/state gates.

Continue feasible actions by default. Only when a checkpoint reason applies, leave them explicitly in `nextActions` under [session handoff](retention-stop-and-recovery.md#working-session-checkpoints). This is a normal partial assessment with `handoffClosesTask:false`, not a dependency-based assignment closure. On resume, recover unknowns/revalidate affected state before choosing the next action. Source-hypothesis BOLA is not policy approval. Keep sampled/truncated counts accurate and read remaining data through available interfaces. Offline tests qualify only tested mechanisms, rather than every product/runtime.

## From useful work to a finite round conclusion

A. Establish the universe from original scope, existing inventories and all declared residual sources. Review discovery deltas only when source/scope/new evidence warrants them; do not narrow a broad continuation to two cases.

B. Read each residual's original question and sufficient observations, then actual retained facts in the right actor/object/build/objective context. Missing fact, rather than attempt status, selects the next work. Map valid followups without changing failed history.

C. Separate old causal uncertainty from unanswered behavior. A valid STOP followed by continued recording can answer the assigned behavior as a violation or policy-inconclusive result; exact root cause is optional unless assigned or needed to restore a missing experiment. A fixture failing before the intended processing path still leaves that fact missing. A stale-version409 is boundary evidence, never processing credit.

D. Do useful feasible work in order: related unknown readback, existing-result readback, executable gap, small preparation/repair. Before a new attempt name the missing fact, changed prerequisite and result that will answer it. No renamed allocation retries without new information; blocked branches do not stop independent ones. Missing handlers remain preparation, not closure.

E. Map every parent clause to finite children, grounded N/A, method/access limits, justified conclusion limits or separate remediation. Preserve original source/history. Review closure over the whole round; selected groups or empty action files are insufficient. Complete review-needed mapping with available data. A runtime fact outside the implementation turn gets an exact ready-for-execution handoff and an unfinished round.

F. Finalize once eligible; lead with lifecycle, then obligation coverage and security findings. A completed-with-limitations round keeps method/catalog duties partial, concrete reopen conditions and no default "continue" prompt. Finding repair is separate unless assigned. Unknown effect with feasible reader means reconcile; unknown live producer without containment means checkpoint/escalate. User pause means checkpointed; user stop means stopped-by-user.
