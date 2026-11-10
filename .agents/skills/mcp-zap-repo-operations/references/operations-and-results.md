# Record operations and read results

Use the [canonical criteria workflow](criteria-driven-workflow.md) for all execution and verdicts. This page describes observation/report primitives; legacy examples are readback compatibility only.

Apply the [ZAP result boundary](zap-result-boundary.md): native alerts and ZAP-derived observations are distinct; external-tool/source-only findings do not enter this skill’s ALERTS output.

The goal is accurate work/results, rather than an additional proof package. Deliver the [Drive assessment table](product-assessment-handoff.md#required-deliverables); keep three JSON projections internal, without mandatory extra proof packages.

## Native workflow

Use actual schemas: optional import → suitable crawl/seed → assigned active scan → terminal/error status → alerts/report → operation/result recording → gap reconciliation. Do not invent parameters or confuse scan/job IDs with guided operation IDs. Running producers remain running rather than completed.

Distinguish HTTP versus browser/JS crawling and imports versus coverage. Both BE tracks require actual ZAP execution; direct BOLA/requests, health checks, unit tests, and tools/list do not replace DAST. Record actual method/route/role/input/techniques without mandatory request archives/wire attribution/proof files.

## Read enough to report accurately

Use findings summary/details or reports for the correct target/run. Retrieve truncated data through available interfaces or state unread portions. Existing chunk helpers may handle offsets/EOF/hashes; do not create an extra full-readback/manifest campaign. Checksums do not establish security.

Triage actual native severity/confidence/routes/parameters/descriptions/available responses without mandatory new exploit proof/raw retention per alert. State unconfirmed interpretations and exclude secrets from outputs.

## Alert reporting contract

Use [alert inclusion/counting](zap-result-boundary.md): RUN records all actual operations/observations truthfully, ALERTS lists native and observed security alerts with details, SCOPE_ALERTS lists only alerts with at least one defensible original-criterion mapping plus the same details and mapped criteria/rationale. Count alerts, not all mixed finding/observation records. Ordinary successful controls, matched denials and uncertainty without a concrete security concern stay in RUN. An observed BOLA issue is a valid alert with explicit tester provenance; do not require a native alert ID.

Total/native/observed counts must match alert rows. Mapped/unmapped counts refer to the same total; mappingCount and instanceCount are separate. Full per-criterion coverage, including criteria with no alerts, belongs in RUN. For v2/v3, compact_results routes to criteria_reporting and validates alert-only/subset projections. Only the legacy v1 branch emits the older criterion-first/mixed-record model; do not use it for new workflow conclusions or delivery.

## Operation journal

Use stable operation IDs and criterion/question references when known. [User scope reporting](criteria-driven-workflow.md) maps native and observed security alerts to criteria; normal business observations and coverage stay in RUN; source/config reads remain support in RUN. Keep proposed actions separate from actual operations; pending/ACK/unknown operations remain unfinished. All three reports share sanitized context/completion and canonical finding identity, without forcing mappings for incidental alerts.

Record operation type/time where known, method/route/scope, actor/role, technique, result/error, and separate unexecuted work/reasons. Distinguish setup/login/identity, seed/crawl, passive/active/BOLA, source/spec versus runtime, and historical versus new scans.

Open duties need [handling decisions](local-remediation-and-continuation.md#decisions-for-open-work) and executed outcomes, rather than state labels. Keep execution/coverage/policy confidence separate: missing policy approval does not erase actual execution; a fixture plan does not establish execution.

## Unit-level support and completion

Version 1 inventories/scopes use [semantic evidenceLinks](operational-readback.md#unit-links-and-attempt-history). Preserve attempt status separately from question closure: partial attempts may contain useful read units and completed attempts may lack them. Context links retain history without credit; related pending effects from journal/RUN remain open until exact action/object resolution. Required responsibility cases remain binding. Do not aggregate units or old violations across different origin/build/object/input/objective without explicit finite compatibility; keep unretested findings.

For internal legacy scope work, compose completion through `product_scope.compact_results`, using actual reconciliation rather than hardcoded partial or operation-ID track heuristics. RUN `completionSummary` reports assignment, reviewed assigned ZAP subset, discovery, security outcome and remediation separately. notPerformed and nextSteps must agree with actual remaining gaps. RUN/ALERTS/SCOPE_ALERTS retain identical taskCompletion/context/bundle lineage. The summary changes no native classification, history or authorization. [Scope/depth](assessment-scope-and-completion.md#short-charter-and-observation-depth) owns the meaning of those statuses.

## Keep coverage summaries consistent with actual operations

Use criterion `coverageView` to show historical records alongside current question observations. A current not-performed projection does not mean historical tests never ran; history alone supplies no current credit. N/A/excluded criteria are separate from not-performed. Use `dast.workUnits` for independent case/question identities; the old mixed reference list is not a test count. Coverage, operation attempts, findings and separately assigned remediation retain distinct meanings.

For v3 (and retained v2), review remaining approved cases and limitations under the [canonical execution rules](criteria-driven-workflow.md#execute-and-reconcile) before choosing more traffic. For retained v1 state only, use [residual review](user-security-scope.md#residual-review-and-finite-refinement) within an explicit extent. Read available results before mutation, prepare missing semantic readers, and retain real dependencies/method/conclusion limits separately. Exact source paragraphs, atom IDs and semantic result pointers survive report sanitization; raw bodies/credentials do not. A selected-groups decision cannot declare the whole backlog exhausted, and classification alone closes no unresolved aggregate or unknown effect; full aggregateReviews can account for parent clauses without changing independent child evidence.

When reconciling a route or closing a question, update its actor/role and technique summaries from the linked actual operations/readback alongside coverage, remainingWork and role responsibilities. Do not leave discovery defaults such as anonymous/sendRequest as the sole observed summary when authenticated native work was actually executed. Operation IDs and nativeInputSubsets remain authoritative detail; aggregate only compatible product/build/route observations. Never copy planned roles or required techniques into observed summaries. Equivalent role behavior can justify reuse with a product-grounded rationale, but does not mean native payloads ran under every role.

Separate selected plugin payloads from engine calibration/site-tree probes, and successful baseline controls from changed-input probes. Cached paths or expired/unknown actors in auxiliary requests provide no selected-actor or sibling-route coverage. Retain their diagnostic results without adding them to tested-role/input summaries. Distinguish passive-only operations from active execution and name the roles actually used. A corrected zero-payload allocation must not erase the original not-exercised outcome.

Use existing saved data to repair contradictory derived metadata before handing off. This is report reconciliation, not a rescan or permission to rewrite raw history. If attribution cannot be recovered, record the uncertainty and retain the affected coverage gap instead of inventing actor/technique labels. No extra manifest, evidence package or schema migration is needed.

## Failures, internal data, and attribution

Before retry identify the failed layer, dispatch/ACK state, and affected scope. Use existing diagnostics without a new forensic package. Follow [remediation](local-remediation-and-continuation.md); unknown causes stay unknown rather than inferred from exception types. Add sanitized local diagnostics only where necessary.

Keep runner logs/native reports/private data at working locations. Preserve old data/verdicts rather than copying/deleting to simplify output. Saved-bundle/checksum/qualification helpers apply to assigned audits/retests, rather than ordinary handoff gates.

For new-finding claims in shared sessions, compare valid before/after detail/snapshots where available. Existing IDs/instances remain existing; absent baseline means first-seen unknown. Do not reset sessions for attractive counts. New reports do not make all included alerts new.

Tool Next Actions suggesting release-evidence/customer-handoff are suggestions, rather than authorization. Follow the approved criteria plan and Drive delivery; additional bundles need an assignment or real entry requirement. [Operational validation](operational-validation.md) separates health/passive smoke from active/auth/FE/BOLA acceptance. Reconcile independent inventory under the [responsibility loop](responsibility-loop.md); one producer's cap/gate/stop does not end the task.

## Assessment finalization and table synchronization

Use scope criteria-review for current v3 (or retained v2) working state and scope report --finalize-round only when eligible for an internal finalized snapshot. Preserve operations, evidence, resource review and private continuation. These commands do not execute tests, stop resources or write Sheets. Then synchronize and read back the same Drive table; final user delivery remains unfinished if its snapshot is outdated or unverified.

Legacy assessmentRound/roundClosed and scope review-closure describe retained historical states only. Never use them to override v2/v3 criteria conclusions. A completed criterion may retain a finding; an unfinished all_cases criterion retains known violations and exact missing work. Use the [handoff contract](product-assessment-handoff.md) for the user response and real checkpoints.
