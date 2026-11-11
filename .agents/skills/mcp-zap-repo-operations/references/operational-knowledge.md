# Reusable operational knowledge

Store verified lessons that change later decisions. This reference is not a scan journal, authorization source, business policy, or live product state. Consult it for executor selection, fixtures, recovery, and checkpoint continuation without adding mandatory stages.

Current user [security requirements](criteria-driven-workflow.md) take precedence over historical business assumptions. Recheck each lesson's applicability to the product/environment/question; do not import catalog IDs, role policies, route mappings or verdicts into the common criteria layer.

## Find relevant lessons

For schema/source/image drift, exact body, report samples, guards/chunks/EOF/checkpoints, read [engine and recovery](knowledge/engine-and-recovery.md). Choose operations/entries under [dispatch](operation-dispatch.md)/[runner routing](runner-routing.md); lessons do not replace current contracts/admission.

Search by symptom/product and read only relevant entries. Recheck origin/binding/version/source/applicability; matching names/versions do not establish identical deployment schemas.

## Update verified lessons

Keep entries short: applicability → observation/verification level → reusable decision → recheck conditions → existing sources. Record last verification date and unknowns, separating source support/runtime execution/hypotheses. Update existing entries rather than logging every phase. Mark superseded mechanisms and conditions without deleting historical raw results. Unexecuted hypotheses must be labeled.

Omit credentials/tokens/cookies/personal data/full requests/responses and default object/session IDs. Existing source/result references may help without new proof/hash bundles. Product roles/owners/expectations stay product-specific; generic mechanisms avoid those assumptions. Setup capability does not authorize DB/mutations/other targets. Current state/open work stays in official RUN/journals rather than this knowledge base. Entries/helpers are not mandatory for every run.

## Optional review helper

`../scripts/review_open_work.py` reads caller-mapped JSON from existing inventory/plans/RUN without changing executor schemas/three-file outputs. It is optional bookkeeping:

```sh
python3 .agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py work --input /absolute/work-review.json
python3 .agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py checkpoint --checkpoint /absolute/checkpoint.json --current /absolute/current-state.json
python3 .agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py session --run /absolute/RUN.json --current /absolute/current-state.json --alerts /absolute/ALERTS.json --scope-alerts /absolute/SCOPE_ALERTS.json
```

Work input: `responsibilities` with `id`/actually required `requiredObservations`; `observations` mapping IDs to observed units or `{completed: [...], outcomeUnknown: true}`; `decisions` with `{action, basis, nextStep}` for execute/repair/prepare-fixture/reconcile. Dependency additionally needs `diagnosis`, `optionsEvaluated` entries `{option,basis}`, and `blockedBy`; N/A needs `applicability`; user-excluded/outside-assignment needs `scopeBasis`. Sanitize inputs rather than passing raw native reports.

Outputs: `unresolved`, `nextActions`, `openWorkWithDecisions`, `workComplete`, `allOpenWorkHasGroundedDecision`, `canHandOffPartial`. Planned actions remain unfinished. Generic rationales/missing diagnosis need correction. Unknown outcomes require reconcile or grounded dependency retaining `unknownOutcomeRetained:true`, causes, and resumption conditions without replay authorization. Empty inventory is insufficient. The helper checks declared structure/logic, not truth/inventory completeness/policy/permissions. Exit 1 means unresolved/next/reconciliation work; 2 means unreadable/invalid input; 0 is neither acceptance nor dispatch authority. Use the [execution loop](responsibility-loop.md) to act.

`canHandOffPartial` keeps its original dependency-based meaning: grounded dependencies and no eligible actions. It is **not** the gate for a context checkpoint. `session` separately reviews RUN [continuation metadata](retention-stop-and-recovery.md#working-session-checkpoints), accepting preparation progress and feasible next actions without inventing a dependency. It returns `checkpointReady` (data structure only, never a reason to end the session), `missingInformation`, `requiresReconciliation`, `nextActionCount`, `revalidationRequired` and ordered `resumeSteps`. It never sets completion, dispatches, reads credential/private-reference contents or writes state. Missing metadata remains saveable best-effort; recover it before dependent work. Pending/unknown operations can have a usable checkpoint while still requiring reconciliation before execution. For `status:checkpointed`, it checks the guidance recommendation and nonempty reason/userAction/resumePrompt; it cannot verify their meaning, the official path or whether stopping is justified. In-progress recovery saves need no user prompt. Neither readiness nor exit 0 proves facts, authority, coverage or liveness.

For `session`, only `--run` is required. `--current` optionally compares supplied snapshots using the checkpoint rules; it does not fetch runtime state. Supply both other reports to check context/completion and available generation IDs after an interrupted overwrite. New reports share `reportGeneration.bundleId`; mismatches need reconciliation, never newest-file selection. Legacy reports without IDs remain readable, without proving coherent publication. Diagnostics use field paths/codes, not checkpoint prose; sanitize source data before using it elsewhere. Exit 1 means missing data or pending reconciliation, not prohibition on saving a checkpoint.

Checkpoint/current snapshots identify `product`, `environment`, optional runId/attemptId/origin/targetBinding/runtimeBinding/image/build/schemaRevision/scopeRevision, `operations`, optional requestCount/executionStatus/finishedAt. Session review also accepts identity from `assessmentContext`. Binding/count/status/lineage differences or unknown outcomes need reconciliation; newer timestamps/larger counters do not establish truth. The helper does not merge/update/continue/replay. No detected discrepancy is not verified live state or authorization. Reusable lessons stay here; live fixture/session state stays in RUN/journals.

## Lost UI acknowledgement and receipt-reader errors

If an acknowledgement is lost, reconcile the existing receipt and authoritative state before retrying. Compare JSON according to its contract, including whether object key order is meaningful. Bind a resolution to the original action, object and objective, and retain unresolved effects in the journal until supported readback closes them.
