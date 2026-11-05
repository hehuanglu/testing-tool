# Assignment scope and completion contract

> Compatibility reference only. Use [criteria-driven workflow](criteria-driven-workflow.md) for all current assessment execution and [Drive table handoff](product-assessment-handoff.md) for delivery. Legacy schema, completion, CLI and three-report delivery descriptions below interpret retained history; they do not authorize a second operating workflow, new legacy dispatch, or extra mandatory user deliverables. Reuse compatible primitives without migrating historical evidence labels.

Apply the [ZAP result boundary](zap-result-boundary.md): native alerts and ZAP-derived observations are distinct; external-tool/source-only findings do not enter this skill’s ALERTS output.

For retained v1 reports, use the legacy format notes in [internal state and handoff](product-assessment-handoff.md). For current delivery, use the [single Google Sheets table](single-table-drive-output.md). Honest operations/results suffice for reporting without an additional assurance package. Actual target authorization, resource limits, and executor gates remain in force.

## Keep four layers separate

For a supplied policy/catalog/text, use the [user criteria layer](user-security-scope.md) above track inventory. Applicability, execution coverage, security assessment and assignment completion are separate. Product-grounded N/A differs from missing actor/source/capability; supported violations may coexist with partial coverage. Scope completion cannot close new/unresolved criteria through old track completion or finding counts.

1. Complete source/spec/route/available-runtime inventory: method/route/input/role/object/action/relation/state, including uncertainty.
2. User-assigned scope and in-track discovery. Keep narrow assignments narrow; do not shrink whole-track assignments to recipes/easy cases.
3. Bounded admitted workloads under actual capabilities/resources. Unselected items remain responsibilities.
4. Actual operations/results/errors/unperformed work. Available tools, imports, tests, and output files do not establish full scanning.

## Assignment completion and security outcome

At intake, use the user's existing request to state product/environment, assigned tracks or criteria, finite questions, sufficient observations, and known method limits in the existing plan/RUN. Prepare technical mappings yourself; ask only about material unresolved scope or expectations, without a routine approval gate. Refine discovery with reasons rather than moving closure conditions to fit results. Preserve requirements beyond ZAP as unassessed; completing the full catalog needs a suitable additional assignment/method or an explicit user scope revision.

Keep round lifecycle separate from legacy obligation coverage: `taskCompletion:complete` means all assigned applicable questions have sufficient results/readback and discovery is reconciled; security outcome records compliance, violations or uncertainty; remediation completion concerns separately assigned product fixes and their acceptance/retests. A demonstrated violation can close its answered question while the finding remains open. Neither fixing every finding nor explaining every historical failure is a prerequisite unless the assignment requires it. Missing intended processing, unknown mutation outcomes or unresolved expectations still leave the affected question open.

Use the reconciled inventory to decide what follows:

- All assigned duties are answered or grounded N/A, with no unresolved discovery/coverage duties: finish the assignment and report findings and limits. Do not add variants or require a repair merely to avoid ending with a violation.
- A concrete unanswered duty has a useful authorized next action: execute it, including feasible preparation or local repair. A generic partial label alone does not select more traffic.
- Remaining duties depend on actual unavailable access, policy, capability or conditions: hand off with the affected scope still partial and specific resumption conditions. Reporting the gaps does not complete them. Only the user may reduce scope; do not turn a blocked assessment into an unsolicited remediation/design or external-method campaign.

## Short charter and observation depth

Keep the charter in the existing plan/RUN, not a fourth deliverable. `engagement` records `objective`, `scopeBasis`, `methodBoundary`, `authorityNotes:[{action,scope,basis}]` and genuine user/environment `limits`. Authority notes document existing permission and grant nothing. Infer routine details from the request and available context; ask only when a difference materially changes scope, authority or conclusions.

Case/question fields `objectiveDepth`, `expectedBehavior`, `expectationBasis` and `coverageContext` describe the finite objective. Depth is a choice, not a mandatory ladder: `boundary` (rejection and relevant no-effect), `processing` (correct handler/consumer), `persistence` (same-object readback), `delivery` (consumer actually receives), or `recovery` (assigned revoke/stop/retry/reconnect). Invalid enum rejection may finish at boundary without media segments. A recording-stop question needs the named recording/downstream state. Boundary observations do not replace an assigned injection-processing question. When a compliance question requires a known expectation, retain unresolved policy or set `expectationRequired:true`; factual readback alone cannot establish compliance.

`completionSummary`, derived by the report composer, separates:

- `assignment`: `complete|partial`, unresolved IDs and gaps, consistent with `taskCompletion`.
- `dast`: `complete|partial|not-assigned`, reviewed assigned ZAP question IDs/gaps. Includes zap-dast, zap-ui and zap-business-observation without converting UI/BOLA to native-active credit. Unmapped methods remain gaps; outside-zap questions remain catalog work.
- `discovery`: `reviewed|gaps|legacy-unreviewed` and reviewed scope.
- `securityOutcome`: finding IDs, violated questions and uncertainty; native severity/confidence remain unchanged.
- `remediation`: `not-assigned` here; product fixes require a separate assignment.

A missing assigned observation is a coverage gap. A limit on extrapolating beyond tested browsers/representative variants is a conclusion limit, not automatically another assigned test. Honor an explicit user timebox/stop-after-block and retain unperformed work. Do not invent a timebox, SLA or completion from max_actions. Do not repeat traffic for catalog criteria outside ZAP when the assigned dynamic subset is answered. A real unavailable access/policy/capability can end work with partial handoff; proportional helper repair does not require developing a large framework indefinitely.

## Reviewed residual decisions

Before concluding no useful dynamic work remains, review the relevant residual universe using [the residual contract](user-security-scope.md#residual-review-and-finite-refinement). Partial prose can mix an answered finite question, missing processing readback, a policy dependency and limits on extrapolation; split atoms only when their next actions differ. Read existing outcomes first. Missing handlers with useful preparation do not establish external blockage. Unknown effects retain priority, and independent branches remain eligible.

`residualWork.decision` concerns only its explicit reviewExtent; selected-groups keeps outside/unreviewed refs visible. It changes neither taskCompletion nor applicability/evidence rules and accepts no residual risk. A stopped finite dynamic review can coexist with partial catalog coverage, real dependencies or outside-method requirements. Retained aggregate questions require full clause accounting; observed children alone cannot close an unmapped parent. A reviewed parent can be accounted with observed coverage or with explicitly unanswered method/access atoms. Do not demand another scan to make historical partial disappear, or use generalization-limit to remove an assigned “all APIs” duty.

Use criterion `coverageView` to distinguish historical progress from current projection. DAST `workUnits` deduplicate case identity without relaxing any linked question's extra requirements. Discovery extent and trackSummary bound current work; a few delta observations cannot establish an entire FE/BE track retest.

## Backend and BOLA scope

BE anonymous requires actual ZAP DAST across every in-scope public API without logged-in identity, including public login/register. Record seeding/validation/passive separately; sample requests/passive-only do not replace active objectives. Protected-denial is additional.

BE authenticated requires actual ZAP DAST across every in-scope protected API with correct role/actor and valid session. Map fixtures/inputs/techniques/results and behaviorally different roles. Missing roles remain unexecuted; 401/auth loss is not authenticated coverage. Public APIs reconcile to anonymous scope.

BOLA requires applicability/results or explicit untested status for every in-scope endpoint/role, including discovered privileged/anonymous roles where relevant. Check owner-positive/non-owner/cross-owner, functional versus ownership permission, meaningful relations/states/collections/filters/pagination. ZAP-proxied clients or ZAP sendRequest provide observation provenance and do not replace authenticated DAST.

“All APIs” means every in-scope method/route, rather than infinite input/rule/role/state combinations. A technique dimension may be grounded N/A while the API still needs handling. Missing token/fixture/capability is open work, not N/A. Never prefill pass or change expectations to match responses.

## Frontend scope

Use [track intents](track-intents.md). Anonymous FE needs real unauthenticated browser journeys/actions on public UI and related network surfaces; API/crawlers do not replace UI. Authenticated FE needs actual UI login/protected journeys with correct role/session and UI/network/post-state. API/DB setup is supplementary; browser authentication does not prove native active authentication.

Reconcile UI responsibilities and security questions for every related API/input. Applicable active testing needs separate execution/readback; UI/browser/passive traffic cannot replace it. Ground technique N/A in product facts and keep missing capabilities open. Do not expand to unrelated backend scope. Preserve meaningful GraphQL/RPC operations inside shared endpoints.

## Bounded planning and coverage

Record discovered → request sent → appropriate technique executed → result read separately in RUN without mandatory evidence files/manifests. Operate intake → inventory → security/role/object questions → operation mapping → bounded rounds → execution → readback → reconciliation → focused remediation → continuation.

Choose techniques from actual input/risk before checking wrapper capabilities: relevant query/body/path/header/protocol, validation, and returned data. Do not restrict to XSS/SQLi because of an allowlist or enable every rule to inflate counts. Missing query/body does not eliminate all active work. Planned techniques are not executed techniques.

Before execution reconcile recipes/tools with independent inventory/roles. Prefer native operations → configuration/orchestration → minimal existing adapter extension → justified runner → minimal underlying capability. Attach deployment/actor/fixture/state/operation/post-mutation/cleanup prerequisites only where needed. Caps split rounds; elapsed time is not completion. Existing pin/proof gates are specific implementation dependencies, rather than ZAP impossibility or permission to bypass.

Missing deployment blocks traffic but not source discovery; missing one role blocks that role only. Prepare legitimate objects instead of dropping core features. Read enough post-mutation state to know success/denial without requiring independent proof campaigns. Object ownership persists even when a privileged actor can act across owners. Shared catalogs differ from personal objects. Derive semantics from current product/policy, labeling source assumptions.

## Finite closure conditions

For each relevant question in the existing inventory, record the specific route/input/role/state or journey, expected behavior and basis, sufficient observations, and what would remain open. A closure condition answers a security question; it is not a target count of successful requests, alerts, rules or rounds. Define it before technique selection and retain it during readback. Refine newly discovered branches with a reason, without redefining the question to fit results or expanding user scope.

Reconcile actual results into: answered with sufficient observations (including observed violations), grounded N/A at the applicable dimension, not yet tested, tested but insufficient/unknown, or blocked by a real dependency. Keep execution coverage separate from security assessment: a tested violation can have complete coverage; an inconclusive policy interpretation can remain explicitly unresolved without repeating the same traffic. Missing actors/fixtures remain open. An answered subset closes only that subset, not its route or track.

A route/role/journey closes when all its assigned applicable questions have sufficient results and readback, with grounded N/A dimensions accounted for and no unresolved discovery/coverage duties. Keep that closure visible when other routes remain partial. Do not mechanically mark every route partial forever, or promote it merely because a scanner ended. For broad assignments discovery must still reconcile the full in-scope inventory.

For each open item, replace generic text such as “more role/input/state testing” with the unanswered question, why current observations are insufficient, and the next action plus its closure/resumption condition. Reuse existing question, remainingWork and nextActions fields; the additive workflow fields stay in existing reports; no extra file is required. If the same item stays open across sessions, use retained results to identify the missing observation, repair or actual policy/authority dependency before selecting more work. Do not keep adding vectors after the assigned questions are answered. New duties need a product/scope basis, not a desire for more coverage or context consumption.

## Continuation and reconciliation

Keep journals/pending state current; update RUN/ALERTS/SCOPE_ALERTS at meaningful milestones and autonomously continue eligible subsets across bounded rounds without per-subset permission requests. Save recovery state without ending the turn; [hand off for another work session](retention-stop-and-recovery.md#working-session-checkpoints) only for a stated checkpoint reason, never merely because a small round ended. A checkpoint with eligible work is partial, not blocked, and does not close the task. Diagnose/fix/test local issues purposefully; documentation/aggregation changes do not require full rescans. Unknown starts/mutations need state readback before retry. Only the user may exclude/reduce assigned scope.

Join full inventory/roles/journeys with workloads/results under the [responsibility loop](responsibility-loop.md). `reconcile_responsibilities` checks only supplied cases; empty or fully observed selected cases do not establish whole-track completion. State incomplete discovery explicitly.

### Per-input result meaning

Derive the question and closure condition from the feature/input/sink before workload selection, rather than whichever branch a payload happened to reach. Distinguish validation/lookup/processing/create/store/response/state transitions when meaningful. Do not replace an assigned processing/create/store objective with duplicate/validation-only checks. A successful baseline and duplicate campaign are separate observations, rather than active coverage of the creation branch. Not every input must reach storage: assess technique/product applicability.

- Allocated active input needs actual application-reaching variation and question-specific readback. Null baselines, skipped fields, or traffic on sibling inputs do not close it. Prepare valid seeds/techniques or ground dimension-specific N/A.
- Classify actual responses: contractual boundary validation, expected denial, auth loss, unintended fixture/sibling blocking, or intended processing. Status/terminal scan/request counts alone cannot establish this; use content/readback/source/spec as needed. Unknown processing remains open.
- Boundary/denial may close its own question. If uniqueness/siblings/state block an assigned processing/create/store question, retain the boundary observation and continue the unmet objective. Not every payload needs acceptance, 2xx, or DB access; 400/409 is not automatically missing coverage.
- Baseline validity can change during active scanning. Prepare uniqueness/dependent fields/objects/state within authorization and inspect relevant mutation outcomes. PUT does not replace POST or another business branch. Reconcile ACK/state before retries without weakening guards or modifying the product.

Login pages, HTTP-200 business errors, and guard responses do not substitute for intended handler results. For asynchronous work, HTTP 202/job ACK establishes acceptance only; processing questions may need the same job/object's state/result through available interfaces. Read pending status and continue independent work without replaying mutations. No universal DB trace/readback format is required.

### Whole-track conclusion

Every in-scope method/route needs actual work/results or explicit unperformed reasons. Both BE tracks still require real ZAP DAST; BOLA still requires endpoint/role/ownership/state reconciliation. Open API/role/input/technique responsibilities prevent full completion. Recorded errors alone do not close work; continue eligible branches and local remediation.

When execution is sufficient but exploit/policy confirmation is absent, bound conclusions without opening an unassigned assurance campaign. Zero alerts, technical pass, existing reports, and three files are not safety/release approval.

Before assignment closure, reconcile all obligations including those outside selected workloads. A decision to run/repair/prepare is unfinished work. At a session checkpoint, preserve useful progress, remaining obligations, unknowns and concrete next actions even if eligible work remains; no fabricated blocker or exhaustive diagnosis is required. An incomplete/emergency checkpoint records recovery needs rather than discarding state. Dependency-based assignment handoff still requires actual diagnosis/options/resumption conditions under [open-work decisions](local-remediation-and-continuation.md#decisions-for-open-work). Neither kind of handoff makes incomplete coverage complete.

## Assessment-round lifecycle and closure

`assessmentRound` version 1 stores `id`, `objective`, `scopeBasis`, `assessmentId`, `product`, `environment`, `scopeRevision`, `reviewUniverse` and `status`. Keep the ID stable across executor allocations and chats. Status is `in-progress|checkpointed|completed|completed-with-limitations|stopped-by-user`. A pause/context handoff is checkpointed; an explicit user stop has a `userRequest:{kind:"stop",source:...}`. A pause uses kind pause. Do not infer either request from a timestamp or a partial result.

Closure requires the whole declared assignment universe reconciled with original requirements and all known inventories/residual sources, no unreviewed group affecting the decision, every backlog item answered/grounded N/A/limited with basis, no useful feasible readback/execution/preparation left, controlled effects/resources and a consistent handoff. Completed requires no applicable unanswered testing duty. Completed-with-limitations retains every unanswered duty, exact access/policy/method reason and concrete reopen condition. An observed violation is an answer, not a coverage deficit or mandatory remediation. Generalization beyond the assignment does not create a new testing duty.

Keep `taskCompletion:complete|partial` and `handoffClosesTask` under their legacy assigned-obligation coverage meaning. All reports add `taskCompletionMeaning:assigned-obligation-coverage`, derived `roundClosed` and `roundOutcome` as the lifecycle headline. `completionSummary.round` contains id/status/closureReason/unansweredObligationIds. A closed round may have partial coverage and handoffClosesTask false. Legacy missing round definitions remain undefined, never automatically closed.

Use [aggregate accounting](user-security-scope.md#aggregate-accounting-and-round-review) instead of the placeholder `remaining-assigned-requirement-resolved`. The parent's original question/required units remain historical; reviewed child obligations drive its current projection, without manufacturing evidence for the placeholder or duplicating child testing duties.

If useful runtime work is feasible but outside an implementation-only turn, return continue with an exact ready-for-execution handoff. Offline implementation is not an external dependency. If an effect reader is available, reconcile first; independent cases stay eligible. Uncontained producers prohibit clean closure. For a truly unreadable effect, retain exact effect/last-known-state, unavailable-reader reason/options, unknown impact, no-replay rule, containment/resource readback and reopen condition; do not mark it resolved or invent a receiving owner.

Finalize only from current inputs. Reopen on scope/build/result/known-duty/resource changes, new actor/policy, a capability/fixture resolving a named dependency, a newly found in-scope feature or an explicit new method/remediation assignment. Partial catalog coverage alone is not a reopen trigger. No reviewer signature, risk acceptance or routine permission to conclude is required.
