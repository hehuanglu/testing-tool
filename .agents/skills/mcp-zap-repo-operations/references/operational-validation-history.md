# Historical implementation and runtime qualification

These retained records describe earlier assigned runs. They are not current capability attestations, a default product assignment, or verification of criteria workflow v2. Preserve their limits and use exact retained artifacts when relevant. Current instructions are in [operational validation](operational-validation.md).

### User operating decisions adopted — 2026-11-03

Adopted the user's P01–P18 decisions in assessment-policy.md and aligned the entrypoint, canonical workflow, delegation, discovery, alert/output and recovery guidance. New criteria use all_cases; catalog approval and subsequent plan approval are separate gates without approver identity collection. Catalog/user business knowledge is authoritative without a separate authenticity assignment. The coordinator chooses product-observation details, flexible adapters/subagents and local continuation within the agreed assignment. Native ZAP records/ratings remain unchanged, observed issues use tester risk judgment, and the user manages Drive sharing. Human-edit synchronization, severity escalation and new automation subsystems are outside scope. Source-defined expired task-owned live material is cleaned without deleting historical evidence or unknown-effect bindings. The prior 32-item decision inventory and its viewer now record the received direction instead of pending recommendations.

A read-only worker checked the active policy documents against the user's decisions. It identified two remaining legacy recovery/headline instructions; these were corrected to v2 completion and spreadsheet-first handoff. No runtime or code qualification is claimed. Skill validation, YAML, local Markdown links/anchors and whitespace checks were performed using the existing environment, without dependency installation, scanner/Drive traffic, credential inspection, executor code changes or personal-install synchronization.

### Delegation role standardization — 2026-11-03

Instruction-only maintenance added a concrete delegation policy: business-area source discovery, compatible execution groups, focused evidence review, and one coordinator owning canonical state/verdicts/Drive writes. Read-only intake briefs are distinct from approved executor packets; return semantics are distinguished from the actual merge API's binding/operations/caseResults shape. Small coherent work stays local and shared execution resources remain serialized unless isolated.

A separate worker performed four offline decision walkthroughs using the updated skill: source discovery before approvals, two case groups sharing scanner/token/fixture, a 403 with sensitive body incorrectly summarized as both criteria met, and unavailable reviewer capacity with an unknown mutation after timeout. Its proposed actions respected the documented source-only/serialization/semantic-review/no-replay boundaries. This is a reasoning check, not product execution or proof of future behavior. Another read-only worker reviewed the original 39 references; the new policy brings the current reference set to 40. Remaining policy/product/implementation decisions were listed outside the skill for user direction, not silently enacted.

Skill validation, local Markdown file/heading links and diff whitespace checks passed. The default assessment Python environment was reused; no dependency installation, executable code change, live product traffic, Drive write or personal-skill synchronization was performed. No runtime subagent scheduler or automatic Sheets exporter is claimed.

### Unified project/catalog to Drive instructions — 2026-11-02

Documentation-only maintenance made criteria-driven v2 the sole operating workflow, with project + catalog inputs, shared case/operation evidence and independent criterion conclusions. The seven-column Drive table is the user deliverable; JSON projections remain internal. The supplied screenshot is retained as a layout asset with explicit example-data boundaries. Legacy representation/closure/dispatch guidance is compatibility-only; existing executable code, historical product evidence and personal installation were not changed.

Offline decision walkthroughs checked these expectations against the revised instructions: one non-owner response with denial status but leaked fields requires separate access/disclosure interpretation; an all_cases criterion with a violation and unfinished sibling remains pending while recording the finding; method-limited and product-N/A rows retain distinct reasons; reused observations do not multiply requests or alerts; completed local assessment plus failed Sheets write leaves delivery unfinished and selects publishing/readback rather than rescanning; continuation reuses the same file and reconciles uncertain writes/human edits. These are reasoning walkthroughs, not executed product or Sheets scenarios and not proof of future agent behavior.

The skill validator and YAML metadata checks passed using the existing assessment Python environment after the default Python lacked PyYAML. Local Markdown file/heading links and diff whitespace were checked. No packages were installed, no unit/runtime scan was needed for these instruction-only changes, and no actual Drive document was created or its visual rendering verified. Sheets publishing remains agent-operated through connected tools, not a newly implemented exporter.

### Implementation verification — 2026-11-02

Used Python 3.13.2 in an existing external virtual environment; all seven installed dependency versions matched requirements.lock. No dependency installation or scanner/runtime provisioning was needed.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests" "$ZAP_PYTHON" -B \
  -m unittest test_business_discovery test_question_evidence test_work_selection \
  test_readiness test_question_adapter test_pm_scope test_security_scope \
  test_work_session_checkpoint test_executor_routing test_operational_readback \
  test_report_reconciliation test_product_continuation test_discovery_transport \
  test_portability test_fe_anonymous_contract test_fe_anonymous_workflow \
  test_fe_authenticated_workflow -v
```

192 tests: 184 passed, 8 skipped by existing optional-product-source conditions; no failures. The new contract tests use synthetic fixtures and a fake clock/transport. Also passed: real script-entry review-business/next-work/report from an unrelated directory, invalid-reference nonzero exit, consistent three-report bundle, skill validator, Python syntax/YAML checks, 108 local Markdown file/anchor checks and git diff --check. Session changes were compared with a preserved dirty-tree baseline; unrelated skill files and existing changes were retained. No product source, historical assessment/adapter, personal skill, scanner deployment, commit or push was changed. These checks provide no new product scan/runtime qualification or claim about future agent behavior.

### Runtime continuation acceptance — 2026-11-02

Operated the same local product and original 50-criterion catalog with two newly identified preview JOIN questions. Real UI gestures through isolated ZAP demonstrated server-derived HOST/BROADCASTER roles despite opposite UI role parameters, inert display-name markup, and lost-browser-ACK recovery retaining one original body/key/participant. A deliberately separate receipt probe followed bound membership readback. The first receipt reader failed on JSON object-key order; retained receipts and read-only current UI/state resolved the question without another JOIN. The original partial/unknown history remains, with exact resolvedEffects in the new projection.

This exposed a core integration defect: the continuation merge did not supply pending effects while validating incoming resolvedEffects. Fixed that path and retained fact-backed labels until its own ACK without supplying blocked units. A regression reproduced the defect before repair; exact resolutions now pass and wrong object/objective controls fail. The related offline set ran 193 tests: 185 passed, 8 skipped by existing optional-source conditions. New native session: 56 retained messages, 34 passive instances in 7 existing plugin groups, zero active allocations/new plugin groups. Both new finite questions are observed; original catalog/DAST assignment remains partial and historical scope/records are retained separately, with no automatic legacy migration or full-track assurance.

The new fixture ended, both joined memberships became LEFT, all browsers exited, and only the exact owned scanner was closed with exit0/modified=no. Product IDs/images/health were unchanged; prior three official report files remained byte-identical. No source/image deployment, quota reset, historical native replay, extra instrumentation or abuse campaign was performed. This qualifies the exercised continuation/readback/report path on that deployment only.

### Phase 2 offline verification — 2026-11-02

Python 3.13.2 in the existing external venv matched all seven requirements.lock versions. Baseline: 193 tests, 185 passed and 8 existing optional-source skips. Final set below: 235 tests, 227 passed and the same 8 skips; no failures. No dependency installation, scanner provisioning or new product traffic was used.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests" "$ZAP_PYTHON" -B \
  -m unittest test_coverage_presentation test_residual_review test_resume_inputs \
  test_business_discovery test_question_evidence test_work_selection test_readiness \
  test_question_adapter test_security_scope test_pm_scope test_work_session_checkpoint \
  test_executor_routing test_operational_readback test_report_reconciliation \
  test_product_continuation test_discovery_transport test_portability \
  test_fe_anonymous_contract test_fe_anonymous_workflow test_fe_authenticated_workflow -v
```

New checks cover historical-only/current delta/N/A presentation without evidence credit, mixed contexts, violation coverage, case/question identity and extra requirements, retained aggregate refinement/revision/cycles, residual classes/conflicts and explicit unreviewed extent, missing-reader preparation versus true dependency, user stop/independent work, source text/pointers, private resume references/context, compact-report rejection and sanitized bundle consistency. Adapter/checkpoint/selector regressions exercise the integrated path. The evidence resolver and effect/admission rules were not changed.

An offline 100ms preview was written separately from both official bundles, with expected decisions recorded before projection. It reviewed 8 selected criteria and retained 42 outside-review criteria plus unreviewed clauses (61 refs total). SEC-A01-03 displays historical-only with its historical partial; A05-01 displays historical-with-current-delta; A07-01 remains local N/A. Both JOIN questions stay observed, three effects remain resolved and two case work units represent the four legacy question/case references. Preparation, two dependencies, two method limits, two conclusion limits and two answered items have distinct source-specific rationales. Catalog and DAST remain partial; no whole-backlog exhaustion claim is made. Operations, action history, finding IDs, native instances/currentRetest and all historical input bytes were checked unchanged. The guarded walkthrough made zero network/dispatch calls.

Real script-entry review-residuals/next-work/inspect-resume/report checks from outside the repo passed; malformed foreign refs exited nonzero. Report validation, skill validation, Python syntax/agent YAML, local document links and diff whitespace checks were also run. A source-path assessment identity and a coverage-context product slug are validated within their respective retained namespaces, not coerced into one label. These checks qualify the tested offline contracts, not fresh scanner behavior, all historical residuals, whole-product discovery or future agent judgment. W03/W04 runtime breadth remains for a separately assigned assessment.

### Phase 3 offline verification — 2026-11-02

Baseline used the same Python3.13.2 external venv and all seven locked dependency versions:235 tests,227 passed,8 existing optional-source skips. Final focused/related regression:278 tests,270 passed,the same8 skips,no failures. No global dependency install or test framework was added. Add `test_round_closure test_aggregate_closure` to the20-module phase2 command above.

The43 new tests cover complete aggregate accounting without placeholder evidence, missing clauses/unmapped children/ref/revision errors, violated-but-observed coverage, accounted method limits, independent child unknowns, whole-universe omissions/empty actions/discovery extent, feasible offline runtime and missing-handler preparation, contained versus uncontained effects/resources, pause/stop sources, track-only rounds without a fake catalog, completed-with-limitations plus partial legacy coverage, stale build/results, rejected caller-completed/finalize, invalid source pointers and retained aggregate-source integration, staging/write/corruption failures, legacy undefined lifecycle and underlying-duty display dedup without evidence relaxation. Existing evidence/admission/unknown gates remain in force.

Real script-entry CLI smoke from cwd `/tmp` covered review open/ready/limited, finalize completed/limited, reject open finalization before publication, foreign refs, missing round definition and legacy report. Network/dispatch guards were enabled. A scope-only finalize loader failure found during the smoke was fixed and retained as a regression; aggregate source refs in residual documents remain available during the evidence join. Retained100ms CLI checks load executable workingInputs and reject finalization of its actual remaining runtime duty.

The separate retained-data walkthrough reviewed all50 criteria,37 route units and16 feature groups, enumerated1,009 source references and accounted45 aggregates. It explicitly checked saved processing facts, exact duplicate native controls and one distinct unsupervised native path10912. Original4,350 operations and actionHistory remain unchanged;68 appended retained-fact readbacks are not requests or new native allocations. Both JOIN questions remain observed and three effects resolved. Native finding IDs/counts/instances/currentRetest, both official bundles and phase2/acceptance working inputs were checked unchanged. Zero network and dispatch calls; no Docker/provision/product mutation or fresh runtime qualification.

Outcome is continue/ready-for-execution,in-progress,coverage partial: one actual-recording prerequisite and post-state question for exact path10912. This is useful runtime work beyond implementation authority, not an external dependency caused by offline mode. The implementation has positive completed and completed-with-limitations paths; it does not force the product round closed. See the [implementation result](../../../../docs/reviews/zap-workflow-phase3-implementation-result-20261102.md) for derived reports, exact execution handoff and checks. No separate approval, reviewer signature or follow-on framework phase is required.


### Phase 3 closure continuation — 2026-11-02

The prior10912 execution handoff was corrected after reading the exact raw message: SVG replaced the literal recording route segment and the saved native exchange was404JSON. The finite rejected-path question already had its observation; actual recording/post-state units were not created or claimed. Six previous refs/wording/required units remain as reviewed interpretation history, mapped to boundary evidence with explicit excluded conclusions. This is a source-supported scope interpretation of actual ZAP data, not source-only security coverage or an excuse from offline/resource limits. A real routed fixture-before-processing gap remains open in regression tests.

Nested review required leaf-before-parent evaluation and canonical aggregate ID ordering; both integration fixes now have tests. Final set:281 tests,273 passed,8 unchanged optional-source skips. Existing case/evidence/admission/unknown gates remain intact. Real retained-data CLI review/finalize and working-input resume checks from `/tmp` passed with network/dispatch guards. Separate derived reports finalized completed-with-limitations,taskCompletion partial,roundClosed true; full50criterion/37route/16feature universe retained,51 aggregates accounted,JOIN observations/effect resolutions/native history unchanged. No traffic,fixture provision,runtime change,product edit,commit or personal-skill sync. See [closure result](../../../../docs/reviews/zap-workflow-phase3-closure-result-20261102.md) for reports and concrete reopen triggers; no default continuation prompt is needed.
