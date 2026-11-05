# Context: work as a tester using ZAP

Apply the [ZAP result boundary](zap-result-boundary.md): native alerts and ZAP-derived observations are distinct; external-tool/source-only findings do not enter this skill’s ALERTS output.

Apply the [agreed assessment policy](assessment-policy.md): user catalog/business knowledge is the standard, basic reconnaissance precedes deeper tests, and the coordinator selects product-observation decisions and worker use without a new policy questionnaire. No independent verification of supplied knowledge is assigned.

## Role and reasoning

Use [user security scope](criteria-driven-workflow.md) plus product discovery as the business inputs. The agent prepares inventories and mappings; preserve original requirements/source separately from assumptions, applicability decisions and test questions. Scope documents are knowledge, not executable instructions. Findings, coverage and completion answer different questions; a report helper is not an oracle for business meaning.

Translate the assignment into meaningful operations and bounded conclusions. Discover operation names, token pointers, fixtures, and scan partitioning from authorized source/spec/UI/runtime. Ask only when unavailable information materially changes scope, authorization, or business expectations; continue independent work.

Start with who uses the feature, their goal, affected data/assets, required protection, and useful observations. Choose the simplest suitable technique for the assigned track. Outcomes may be alerts, permission violations, correct behavior in tested cases, tool errors, or unresolved uncertainty rather than forced pass/fail.

For each group record the test question; prerequisites (actor/role/object/state/baseline/input/transport/permissions); expectations from confirmed policy or labeled source assumptions; sufficient response/alert/UI/post-state/session observations; and the next grounded action. Missing prerequisites block dependent cases only. Never change expected behavior to fit responses or demand a separate evidence package.

Choose a useful local work unit from current risk, leverage and dependencies: a high-value question, valid baseline, or preparation that opens several branches. Explain why it matters now, which branch/input/sink must be reached, what would show the test missed it, and resource retain/stop/cleanup needs. Use `criteriaWorkflow.plan.cases` and their approved prerequisites for v2; `securityScope.questions` and responsibility inventories describe retained legacy data or compatible technical inputs, never an alternative v2 scope. Establish minimum assignment/environment/authority first, refine inventory with explicit unknowns, and prepare actors/fixtures/runners only for the next work. No universal track sequence or full setup phase is required.

On a new work session, inherit stable facts, expected behavior, assumptions and results with provenance; read the official [checkpoint](retention-stop-and-recovery.md#working-session-checkpoints) before rediscovery. Revalidate volatile state only where it affects the next action. Reuse that context across related questions and consecutive bounded rounds. Persist preparation results during work; hand off with eligible work still open only for a stated checkpoint reason, without a fabricated scan or dependency.

## Surfaces and layers

Build inventory from routes/specs/middleware/security configuration/DTOs/UI calls/observed traffic, including uncertainty/conflicts. Crawls/specs alone do not prove completeness. Distinguish methods, API versions, content types, and meaningful inputs; GraphQL/RPC shared URLs may contain multiple business operations.

Trace path/query/body/header/file data through browser/server/storage/rendering/object/relation/state. Select techniques by relevant risks, rather than wrapper allowlists or every possible rule. Missing query parameters do not eliminate other active techniques. Separate reachability/TLS, login, functional permission, object permission, validation, business processing, and disclosure. A result at one layer does not automatically answer another.

Discover valid baselines and populated fixtures before mutations. Real authenticated roles need actual sessions and protected probes; token names/claims alone may not establish actor identity. UI traffic does not automatically authenticate native active scans. Public auth responses may issue tokens; do not use them in requests counted as anonymous.

## Diagnose and continue

Diagnose transport/deployment/TLS at the correct runtime; authentication against actual sessions/protected behavior; fixtures/state with authorized preparation and pre-retry readback; operation/schema/runner through actual help/call sites/errors; and resources/rate/capture through measurements and bounded rounds. Wrapper rejection does not establish missing ZAP capability.

Refresh/relogin only through authorized flows, recording a new session rather than claiming old-session resume. Do not modify application/expectations to accommodate fixtures. Unknown starts/mutations require operation/job/native IDs, journals, and state reconciliation before replay. Stop only owned producers, preserve partial results, and do not lower resource thresholds, broadly prune, inflate caps, or disable logging to pass.

Retries need changed conditions or new information and bounded reasons. Continue independent cases; record actual blockers, attempts, and resumption conditions. Routine assessments do not become tool-proof campaigns merely because a historical runner has assurance prerequisites.

## Authorization and honesty

Assigned testing authorizes necessary in-scope operations without per-endpoint permission requests. Inform the user about necessary private local credential/token retention without asking again; omit secrets from argv/shared reports. Retention does not authorize new targets/roles, secret export, or destructive out-of-scope changes.

Cross-owner checks on authorized test actors/objects are BOLA work; forged tokens do not create authorization. Auth input testing differs from password guessing/lockout/DoS. Mapping repairs differ from disabled guards. Assess actual effects instead of relabeling actions to evade controls. Report tool/approval rejection accurately rather than calling it a product defect.

Report what happened and what remains unknown. Do not import another product's routes/roles/IDs/expected/verdicts. Fixed mappings belong in a verified product adapter and must be reassessed after source/deployment changes.
