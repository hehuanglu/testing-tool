# Assess and conclude by criterion

## Plan the first pass

Preserve the criterion ID, wording, and source. Record the product-specific interpretation separately. When the user supplies a catalog, retain its inclusion decisions and reasons. Excluded criteria carry no test obligation. For a goal without a catalog, derive the smallest useful criterion set from the request and relevant product expectations. Use the [question library](track-intents.md) as a starting point.

For each selected criterion, establish:

- The in-scope surfaces and questions, expected behavior, and authority for that expectation. Label source-derived assumptions.
- The evidence that could answer each question. Map candidate rule IDs/configurations and targets, manual checks, or both. Identify questions requiring runtime, policy, or another method, and what they need.
- Applicability, exclusions, and dependencies. An applicable question beyond CE may still be answerable by reading source. A runtime-only question stays open when runtime evidence is needed by the criterion.

Before running Semgrep, review each question against the inventory. For a Semgrep check, name the local rule IDs and target paths, verify language and effective path filters, and state what a match and a zero-match result can establish. For a manual check, name the files, callers or configuration consumers and the control to verify. Split out any question that needs external policy or runtime evidence and identify that evidence. A shared scan can contain many rules, but a mapping to the whole configuration or to “review relevant source” leaves the question unplanned. If running a broad discovery pass, record its purpose and map its observations to questions only after reviewing the actual rule, target and context.

## Prepare and revise plans with a subagent

Assign one preparation subagent for a new criteria assessment. Use the same preparer for scoped reconnaissance, initial drafting, internal Q&A, and follow-up plans. Start with `fork_turns: "none"` and use `gpt-6.1-sol` with `high` reasoning, or `xhigh` if conflicting source or policy materially affects the plan. Give it the assigned criteria and their sources, scoped revision and paths, relevant specs and skill guidance, read-only boundary, and expected handoff. For supplements, also provide the reviewed baseline and precise coverage gaps via scoped, sanitized references. Keep credentials, raw private outputs and unrelated history out of the brief. The preparer returns drafts, source references and dependencies. It has no scan, shared-record write or approval authority.

The coordinator independently checks the draft against the source and criterion authority, including [inventory reconciliation](tester-workflow.md#reconcile-inventory-in-both-directions). Ask product-specific questions about missing callers or branches, unsupported rule/target pairs, assumptions about controls, and what evidence would settle each disputed question. Send gaps to the same preparer, which answers with source references and revises the mapping or records a precise dependency. Recheck the revision and repeat until the draft is ready to present. Retain the reviewed draft and material questions, answers and decisions in private working state. This internal review establishes readiness for the plan approval gate. The coordinator owns the final plan, execution, canonical records and delivery.

Reuse the reviewed draft on resume. If the preparer cannot continue, resume or replace that role using the retained draft and feedback. If subagents are unavailable, record the limitation and perform the same preparation and review locally. Focused targeted scans and retests can be planned locally. Optional delegation is limited to bounded read-only tasks, with the same context boundaries and coordinator verification. Status, delivery refresh and skill maintenance need no assessment preparer.

## Plan approval gate

After internal review, save the plan and source state in private RUN. Present one consolidated revision to the user with the scope, planned work, dependencies and closure conditions. Record the revision ID and pending status, request explicit approval of that revision, and end the turn. Apply this same gate to the initial plan, focused scan or retest plans, and each follow-up plan. Scope clarification and internal review are preparation steps.

Resume execution only when the user has explicitly approved the exact presented revision. Record the approval and its scope. On resume, reuse recorded approval for the same revision. A general assignment, standing authorization, or delegated decision does not approve a new plan. If the user requests changes, revise the plan, review it, and present the new revision at the same gate. A planning-only request ends with the reviewed plan and its approval state.

## Execute by compatible work

Group questions sharing the same source state, applicable targets, effective filters, rule behavior, and engine requirements. A round can serve several questions, criteria, and tracks. Split rounds when filters, source state, engine, or diagnosis require it. A rule ID alone does not map a finding to a criterion. Record the actual rule/target/question mapping and evidence that supports each link. Shared source or control reviews also retain precise caller and surface mappings.

Work through every feasible item in the approved revision before returning to planning. Diagnose and retry routine failures within that revision and work on independent approved items when another item has a dependency. Record blocked items and their resumption conditions. Collect and read back each round before using it to drive follow-up or conclusions. Reuse compatible observations from Semgrep and manual source reviews with their original command, source state, and provenance. Verify any changes in source, rules, engine, or ignores before relying on old evidence. Keep each criterion's own closure conditions and unresolved questions. Record runtime-only checks as dependencies outside this skill's evidence boundary.

## Plan the next pass from coverage gaps

At the end of an execution pass, compare actual evidence against each selected criterion and the current inventory. The first plan can be incomplete. Identify which surface, branch, or required observation it missed, which planned checks ran incompletely, and which gaps reflect policy, effective deployment, source access, or tool limits. Include every still-open question, even on criteria with a supported issue or a bounded negative conclusion. Add newly discovered in-scope questions with stable IDs and a reason.

1. **Build a reviewable revision.** For each gap record the criterion/question IDs, prior evidence or its absence, cause, next check, concrete targets, expected evidence and closure condition. Use separate work items when a question has both feasible local work and an external dependency. Name the exact artifact, decision, or capability needed for each dependent item. Review whether a local source check can advance the question before marking it dependent. Map shared work to every question it serves and carry forward any compatible evidence.
2. **Review the supplement.** Return the reviewed baseline and gaps to the preparation subagent for a draft and product-specific Q&A. Check that every open question maps to a work item or a specific dependency, and that each item maps to an assigned criterion.
3. **Present and stop.** Save the reviewed revision with its baseline source and evidence, then apply the same [plan approval gate](#plan-approval-gate). Resume the new work only after the user approves that exact revision. If readback exposes another gap requiring new work, repeat this loop.

When only external dependencies remain, report the exact inputs and resumption conditions. Keep the assessment partial while required questions remain open.

## Conclude independently

For each selected criterion record these fields in the [private reporting records](reporting-and-completion.md):

- **Applicability** is `applicable`, `not-applicable`, or `undetermined`, with a reason grounded in the product or a specific missing fact. Track selection/exclusion separately. Missing rules, source access, policy, or runtime evidence do not establish inapplicability.
- **Coverage** is `full` when all required in-scope questions have sufficient checked evidence, `partial` when some have meaningful evidence and gaps remain, and `none` when none has usable evidence. Use null where coverage is inapplicable, undetermined, or not yet assessed. Identify the checked and unchecked surfaces/questions and the methods used. Record the reason for gaps, such as unsupported language, scope excluded, parse failure, or runtime evidence required. A bounded static scope may be fully covered while runtime behavior remains untested.
- **Conclusion** uses exactly four criterion statuses:
  - **Out of scope** (`out-of-scope`) — The user excluded the criterion from the initial assessment scope.
  - **Fail** (`fail`) — Admitted Semgrep evidence or agent source review establishes a violation of the criterion. A verified violation can establish Fail with partial coverage.
  - **Pass** (`pass`) — Reviewed evidence from the applicable methods covers all required in-scope questions and supports the expected behavior.
  - **Not evaluable** (`not-evaluable`) — The criterion is in scope and neither Semgrep nor agent review provides sufficient evidence to decide it. Record why, including grounded non-applicability, missing evidence or work still pending. Partial observations can be retained even when neither method can settle the criterion.

A zero count or exit 0 supplies no conclusion on its own. Keep unchecked obligations open. On interim reports show progress and dependencies in Next steps or Notes. Required needs-review items stay open even when another issue is confirmed. A report can be verified and delivered while the assessment remains partial or blocked. Complete the assessment when all assigned obligations are addressed, with any agreed exclusions or grounded inapplicability explicit.

## Review the process and evidence

Compare actual inventory and checked obligations to the plan. Use relevant [track guides](track-intents.md) to review trust boundaries, controls, write paths, and configuration consumers. Follow the [responsibility loop](responsibility-loop.md) to address feasible gaps.

- Account for every native result index, including inventory-only, false-positive, and unresolved matches. Keep occurrences linked through deduplication. Compare actual rule ID, location, severity, confidence, and message where present. Redact sensitive text and note the redaction.
- Re-read source supporting findings and controls. Verify inspected dataflow/call steps and the source state. A native trace requires actual trace output. An inferred call path remains manual evidence. A policy discrepancy needs a source of authority before it becomes a verified policy violation.
- Check criterion-to-question-to-evidence links, scope gaps, counts, and source consistency. Record self-review of process sufficiency and evidence support separately. The [v2 link checker](../scripts/check_report_links.py) checks record structure. Review criterion links and the Sheet projection explicitly.

Persist reviewed state before delivery or pausing. When resuming, identify the prior scope, source state, pending questions, and Sheet binding. Continue feasible independent work after resolving any source or evidence incompatibility.
