---
name: run-semgrep-scanner
description: >-
  Assess source security against assigned criteria using local Semgrep and
  manual source review. Plan checks from product behavior, share compatible
  scans, triage evidence, and report criterion-level coverage and conclusions
  in one concise Google Sheets table with Semgrep risk counts, agent observations
  and evidence. Leave Next steps and Notes empty unless they contain a material
  action, dependency, limitation, skip or warning. Also supports targeted scans,
  custom rules, and retests.
---

# Run Semgrep Scanner

Work as a tester in the user's language. Use the assigned criteria to decide what to check, the product to identify relevant surfaces, and the available static evidence to decide what can be concluded. Read [tester context](references/tester-context.md) for source, runtime, and policy claim boundaries.

Operate this assessment independently. Base findings, coverage and conclusions on local Semgrep output and manual review of the assigned source and versioned configuration. A scope from another assessment may supply criterion IDs and selection decisions. Exclude ZAP and other scanner or runtime results from the evidence, counts and conclusions, including during follow-up and delivery. Keep claims requiring effective deployment or runtime observations open.

Resolve references from this skill directory. The repository's complete skill tree is the maintained source. See [setup and synchronization](references/setup.md) for portable installations.

## Assessment workflow

1. **Intake and discovery.** Determine the requested criteria or goal, source snapshot, roots, included/excluded paths, stack, and triage depth. Follow [discovery and question design](references/tester-workflow.md). Read the source and available specs before asking the user about unresolved scope or policy.
2. **Prepare and review the plan.** For a new criteria assessment, assign one [preparation subagent](references/criteria-workflow.md#prepare-and-revise-plans-with-a-subagent) to scoped discovery and drafting. Review the draft against the source and send concrete questions back to the same preparer for revision. Follow the [criteria workflow](references/criteria-workflow.md) for question IDs, expectations, surfaces, methods, targets and closure evidence.
3. **Present the plan and stop for approval.** Apply the [single plan approval gate](references/criteria-workflow.md#plan-approval-gate) after each reviewed plan, including targeted scans, retests and follow-up plans. Persist and present the exact revision, then end the turn until the user explicitly approves it.
4. **Execute the approved plan in full.** Complete all feasible work in the approved revision, including readback, triage and self-review. Select inspected local rule IDs and target paths with the [catalog](references/rule-catalog.md) and [CLI guide](references/semgrep-operations.md). Combine compatible work across criteria and tracks with explicit rule/target/question mappings. Use focused [custom rules with fixtures](references/rules-and-triage.md) or manual review where they answer a question.
5. **Reconcile coverage and replan as needed.** Compare actual evidence, errors, skips, timeouts and suppressions against the plan and inventory. If new work is needed, return to [follow-up planning](references/criteria-workflow.md#plan-the-next-pass-from-coverage-gaps), have the preparer draft and revise the supplement, then present it at the same gate and stop.
6. **Conclude and deliver.** Record applicability, coverage, conclusion, and remaining work per criterion. Maintain a private [RUN/ALERTS pair](references/reporting-and-completion.md) and deliver [one Google Sheets table](references/sheets-delivery.md) with one row per criterion, four criterion statuses (Pass, Fail, Not evaluable, Out of scope), four risk counts for Semgrep-detected issues, an Only observed count for agent-only observations, and linked evidence. Keep Next steps and Notes blank when there is no material row-specific content; do not fill them with generic retest advice, repeated method text or statements that no gap exists. Apply the [risk rubric](references/rules-and-triage.md#assign-reviewed-risk) to supported Semgrep detections after triage. For targeted or setup-only requests, follow the requested scope and output.

## Question and technique library

Use the [track index](references/track-intents.md) to find relevant questions and source-review guidance for backend input, browser, authentication/session, authorization/ownership, and configuration/build. Tracks organize techniques. They add no scope, execution order, or reporting requirement. For a goal without a supplied catalog, derive a bounded set of criteria from the goal and product, recording their source. A focused retest or candidates-only request can use only the relevant questions.

## Routing and boundaries

- **New criteria assessment:** plan, execute and self-review against the assigned criteria, then verify Sheets delivery.
- **Continue a criteria assessment:** recover the reviewed RUN/ALERTS and Sheet binding. Resume the exact approved revision from its first unfinished work item. For a pending revision, wait for its approval. For gaps requiring new work, prepare a supplement and stop at the plan gate. Read back the results and update the authorized summary from the reviewed evidence. A planning-only request ends with the reviewed plan and its approval state.
- **Targeted scan or candidates:** keep the plan bounded to the requested detector scope, triage depth, and output. Claim only the work actually performed.
- **Retest:** compare source, rule, ignore, path, and engine changes with retained evidence. Reuse compatible evidence and preserve prior results.
- **Status or delivery refresh:** use reviewed retained state. A status request does not assign a new scan. Update the bound Sheet when the user asks for a refresh or the latest table.
- **Setup, audit of the skill, or maintenance:** use [validation](references/validation.md) for the assigned work.

Use local Semgrep OSS/CE, inspected local rules, isolated settings, disabled metrics/version checks, and private output outside the target. Record the actual engine/version. Verify isolation when offline execution is required. Use already-inspected, versioned local copies of any authorized Registry rules. Keep product code and suppressions intact. Local review and scan authorization covers the identified source and scope. Login, rule downloads, uploads outside the agreed report, dependency changes, runtime probing, and product remediation require separate scope.

Finish feasible assigned work and retain precise blockers, remedies attempted, and resumption conditions. Report assessment status and verified delivery status separately. Return the Sheet link for a criteria assessment when available and state any unfinished work. Report maintenance and validation directly for skill-only work.
