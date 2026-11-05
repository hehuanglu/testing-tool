# Technique questions and verified readers

Read for BE workload planning, adapter/composer changes, zero probes, fixture conflicts, overwritten readback, or misleading metadata. Shared source is `${ASSESSMENT_ROOT}/src/zap_assessment/`; product routes/roles/fields/states remain in adapters. Helpers are not independent semantic oracles.

## Close the selected question

Before start retain the question, meaningful inputs, distinct techniques/rules, and required outcome stage. Do not generate every rule/input combination. Text fields may share reflection questions while numeric/enums need boundary questions. Strength controls workload size; alert threshold affects rule applicability/detection. Inspect actual settings rather than conflating them.

`active_questions.assess_question(question, probes)` reconciles adapter-verified facts:

- Question: `id`, `ruleIds`, `minimumStage` (`boundary/processing/persistence`), optional distinct `fields`, and selection `basis`. N/A needs disposition and sink/context rationale; missing auth/fixtures/capabilities are not N/A.
- Probes: `ruleId`, relevant `field`, `changed`, `application`, `identityValid`, `stage`, `resultRead`, derived from actual app-reaching payloads/session validity/read responses. Enabled rules/ACKs/guard denials/other-field mutations are not equivalent probes.
- Stage: meaningful parsing/validation may establish boundary; reused-fixture conflicts do not establish processing. Matching ACKs may establish processing. Persistence requires the correct object/variant read before overwrite or isolated objects; final snapshots cannot establish all preceding variants.

Results contain `unit`, `evidenceUnits`, `status`, `missingFields`, request counts. Add selected question units to inventory requiredEvidence and only actually returned evidenceUnits to observations/reconcile. SQLi probes do not close zero-probe XSS. Metadata-only rule counts are insufficient. Open results require diagnosis/repair/fixtures/another round, or actual dependency notPerformed/nextSteps at a valid stopping point. Helpers trust normalized facts; do not copy requirements into probes or classify all 400/404/409 alike. Preserve valid boundaries without universal persistence requirements.

## Unit links and attempt history

`question_evidence.resolve_question_evidence(question,observation,operations,pending_effects)` returns `supportedUnits`, `missingUnits`, `contextDiagnostics`, `unresolvedEffectIds`, `supportOperationIds`, `contextOperationIds`; verdict interpretation remains the adapter/tester's responsibility. Version 1 observations carry `evidenceLinks:[{operationId,observationUnits,resultPath,resultRead,basis,context,role}]`. `role` is support or context. Only read support links provide units; top-level evidenceUnits/observationUnits must be subsets of supported units. Attempt completed is insufficient; partial/failed attempts can support valid earlier units. Context/history provides no units and its partial status alone does not block current support. Legacy labels retain their former semantics outside v1.

`context` binds meaningful product/environment/origin/build, method/route/inputLocation, actorRef/role/relation, objectRef/state/objective. Unknown stays unknown. Operation coverageContext, when present, must agree with its link. Inheritance needs `compatibility:{basis,dimensions:{build:{from:"b0",to:"b1"}},operationIds:["old-read"]}` with exact reviewed dimension values; request origin/method/route/input location/objective cannot be inherited. This is a declared finite mapping, not automatic source equivalence or native execution under a new actor.

For v2, support operations must additionally match every `criteriaWorkflow.context` dimension exactly. Explicit compatibility applies only to remaining case-level dimensions. A case-level build can use a reviewed retained-build mapping; a build bound at workflow level, product or environment cannot be changed through that mapping.

### Finite native evidence allocations under an unchanged plan

When existing authority already covers an exact transport alias and complementary requests, the coordinator may record a private `RUN.evidenceAllocations` entry. This is evidence bookkeeping, not an approval or dispatch mechanism. Preserve the approved plan, actual origins/routes/request references and native receipts. The coordinator must interpret original authority and deployment evidence; the helper cannot authenticate permission or infer semantic observations from hashes.

Each entry carries `version:1`, `assessmentId`, `caseId`, current `criteriaDigest` and `planDigest` from `approval_digest`, exact `workflowContext`, exact `baseContext` from `bound_context(case, question=True)`, ordered `requiredEvidence`, a review `basis`, nonempty `authorityRefs` and `deploymentRefs`, explicit `originBindings:[{from:approvedOrigin,to:actualOrigin}]`, and a finite `operations` list. Each operation mapping has:

```json
{
  "operationId": "retained-readback-id",
  "observationUnits": ["one-actually-observed-required-unit"],
  "resultPath": "/semanticReadback",
  "context": {"product": "exact actual context; include all dimensions"},
  "provenance": {"transport": "zap-native", "rawRef": "private retained source; copy complete provenance"},
  "receiptDigest": "contracts.digest(operation.zapMessageReceipt)",
  "captureDigest": "contracts.digest(operation.zapCapture)"
}
```

The sample is a field template, not a valid allocation. Populate complete exact contexts/provenance from independently reviewed operations. Mappings require native read receipts bound to case, actor, fixture, request, scanner/session/message ID and request/response hashes. Alias mappings preserve scheme/port and name exact origins; there is no global alias normalization. Workflow dimensions remain exact. Case dimensions other than origin/route/requestRef remain exact. Complementary operations must have identical complete contexts except route/requestRef and the same scanner/session/transport, including actor, fixture and build even when the case omits them. Only exact listed operation/unit/pointer/context combinations may supply units; ordinary compatibility cannot be combined with the allocation.

`review_workflow` validates every allocation against the current approved workflow, including unused entries, then calls the normal `resolve_question_evidence`. Direct resolver use requires `allocation=entry, workflow=currentWorkflow, assessment_id=currentAssessmentId`; it performs the same validation. No allocation preserves existing callers' equality/compatibility rules. Pending effects still withhold units. `outcome:null` observations expose supported/missing units through the reviewer while leaving the case and criterion pending; a pending limitation is retained. Only an independently interpreted matched/violated result with all required units can close a case. Focused synthetic controls are in `tests/test_evidence_allocation.py`.

`resultPath` is an RFC 6901 JSON pointer relative to the linked operation, including context and resolution links. It must survive compact/redaction and contain a result. Raw headers/bodies are removed; use sanitized semantic readback in a new reconciliation operation or working projection with private-source provenance. Preserve old disk data/status/pins. Do not restore raw bodies just to save a pointer.

Pending effects union operation outcomeUnknown/pendingStart with journal/actionHistory mutation/start intent or unknown. Related case/action, declared dependencies and object identity determine affected questions; insufficient binding stays diagnostic/open. Merely moving an unknown attempt to context never resolves it. `resolvedEffects:[{actionId,resolutionOperationId,resultPath,basis}]` must point to actual readback `{actionId,caseId,resolved:true,context:{...}}` for the exact action/object. When object context is unavailable, exact action and case are required. Resolved projection does not modify unknown history or release journal replay gates. Criteria `responsibilityIds` remain required; optional `contextResponsibilityIds` records history without silently reclassifying required cases.

## Bounded readiness at the requested stage

`readiness.wait_for_observation(sample,evaluate,*,context,timeout_seconds,interval_seconds,remaining_seconds,clock,sleep,cancelled)` is async, stdlib-only and read-only. Context names the bound actor/object/operation and required `stage:ack|domain|processing|persistence|consumer`. Sample is reviewed async Python accepting context and remaining transport timeout; propagate that timeout, avoid blocking I/O and honor cancellation. The helper also bounds the awaited sample. Evaluate returns status `ready|pending|terminal-failure|context-mismatch`, stage, sanitized facts and missingConditions. ACK → pending → correct-object consumer is ready only at the last stage when consumer observation was assigned.

Monotonic deadline is min(selected timeout, remaining execution budget); timeout/interval/budget must be positive finite numbers. Sleep and each sample use only remaining time. Results are ready, timeout, terminal-failure, context-mismatch, cancelled or reader-error, with stage/elapsed/missingConditions/sanitized facts and unchanged journal outcomeUnknown. Reader exceptions stop; only explicitly classified transient reads may return pending. No mutation is retried. Context mismatch stops immediately. A timeout is an observation budget result, not a product SLA or vulnerability; a boundary-only question needs no media/decoder/segment.

The synthetic [adapter example](../lib/zap-product-assessment/examples/question_adapter.py) demonstrates reuse with injected transport. It does not repair historical JS background readiness or add generic FE media support. The FE finite predicate cap remains 12 seconds; changing that lane requires its own schema/worker/pins change, never bypass through this helper.

## Stable reading and recomposition

- `result_readers.read_jsonl(path)` splits LF records; U+2028/U+2029 inside strings do not split records. Invalid outer JSON reports its line; malformed HTTP-body strings remain intact. Do not silently drop bad records to claim completion.
- `result_readers.collect_alerts(fetch, total, page_size=100)` collects actual native IDs, permits identical boundary overlap, and rejects no-progress pages/changed-ID content/missing counts. Advance by actual returned rows. Stop producers, settle passive, and check stable totals before/after. Representative samples are not all instances.
- `result_readers.read_native_alerts(engine, origin, page_size=100)` is the bounded native-ID reader used by anonymous/native exporters. It reuses `collect_alerts` for identical boundary overlap, changed-content and no-progress checks, then checks pre/post totals, including zero alerts. Request full bounded pages rather than reducing the last request to the remaining unique count: a repeated boundary record otherwise leaves the final record unread. Equal totals alone cannot detect every same-count replacement; producer isolation and passive settling remain required.
- `transport.Scanner(..., chunk_size=100000).chunk` respects exposed schema and caller byte/resource caps. `evidence.collect_report/read_report` handles EOF, code-point offsets, stable artifacts, and saved-page resume. Reader repairs do not require rescans.
- `product_checks.check_pages(..., terminal=True)` requires an observed empty terminal page. Total zero makes page 0 terminal; populated collections need all data pages plus the following terminal. Ownership/total/order/missing/duplicate IDs still matter.

## IDs, secrets, and outputs

Keep baseline/campaign/actual request IDs and case links distinct. `operationIds` retain exact operation IDs; pagination groups retain group labels and real child requests rather than invented prefix operations.

`product_scope.compact_results(..., secrets=...)` redacts sensitive fields/auth assignments/JWTs/known secret values without treating `Token:CUSTOMER` or “password validation” as credentials. Verify unique IDs/resolved references after redaction and handle collisions while still protecting real secrets.

Prefer new destinations. Use `overwrite=True` only when replacement was requested; ensure the destination contains only regular RUN/ALERTS/SCOPE_ALERTS report files (legacy pairs are accepted) and prepare/validate all three before replacement. Overwrite is per-file atomic, not crash-atomic across the bundle. Preserve raw/journal/pins/historical audits. Rerendering existing data is not retesting. [User security scope](criteria-driven-workflow.md) defines criterion/question/finding joins and revision handling.

Budget fixtures from actual questions/request estimates and observed objects. Reuse valid quota/state-compatible actors/fixtures without cached attack responses or replacing new-create mutations with duplicates to reduce accounts. Missing cleanup APIs require accurate authorized retention rather than arbitrary object-count pass limits.

Focused tests: `tests/test_operational_readback.py`; scope/continuation tests: `tests/test_pm_scope.py`; legacy criteria/report contracts: `tests/test_security_scope.py`; current v2 verdict/export contracts: `tests/test_criteria_workflow.py`, `tests/test_criteria_integration.py` and `tests/test_criteria_reporting_boundary.py`. Unit tests qualify mechanisms rather than all runtime tracks.

### Resolutions returned by continuation readers

`continue_work` validates incoming and prior links with the actual pending-effect set before merging them. During a mutation handler's readback its own intent is still durable and pending until ACK is written: preserve a fact-backed outcome label at this stage, while the resolver still withholds units for unresolved effects. Neither the temporary label nor a completed handler releases replay gates. An exact reader resolution can close the current question after reconciliation; wrong object/objective remains blocked. The regression in `test_work_selection` covers incoming resolvedEffects and both wrong-object and wrong-objective controls.
