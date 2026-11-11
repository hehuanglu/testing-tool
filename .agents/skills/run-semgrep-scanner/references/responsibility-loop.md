# Responsibility loop

Keep product inventory and questions independent of findings and selected workload. For each assigned criterion, reconcile inventory → question → actual technique → readback → disposition → next step. Follow the [criteria workflow](criteria-workflow.md) and [reporting contract](reporting-and-completion.md).

For each open item, decide whether to execute, repair a local issue, prepare input/source context, use another authorized technique, mark a genuinely inapplicable dimension, or document a specific external dependency. A decision is not execution: perform feasible next steps before handoff.

Complete all feasible work in the approved revision, including independent items and routine recovery, before preparing a supplement. After readback and review, use the [follow-up planning loop](criteria-workflow.md#plan-the-next-pass-from-coverage-gaps) for gaps requiring new work. Present the reviewed supplement at the [plan approval gate](criteria-workflow.md#plan-approval-gate) and end the turn.

Read actual native JSON, stdout/stderr, errors, timeouts, skips, scanned paths, and source controls. An exit code, match count, or helper success does not establish coverage. Check ignored/unsupported files against the inventory; missing paths remain unresolved until explained or reviewed. Native counts are null when execution/output is unavailable, rather than zero.

Repeat [inventory reconciliation](tester-workflow.md#reconcile-inventory-in-both-directions) after each relevant readback. When closing a group of matches with a shared rationale, identify the actual common control and confirm it applies to every occurrence. Split out any caller or branch whose disposition differs or remains uncertain.

When CLI execution fails, diagnose the smallest affected layer: engine/flags, rules, targets/ignore filters, parsing, output collection, or source context. Make minimal authorized corrections and run a focused check. Continue independent questions. Do not retry unchanged conditions, download remote rules, change engines, modify product code, or expand scope merely to obtain a passing run.

Manual review can answer a source question where suitable, with manual provenance. If the user specifically required Semgrep execution, retain that unmet requirement separately. A missing rule/policy does not erase feasible source work or automatically mean N/A, false-positive, or accepted risk.

Before concluding the relevant criteria, reconcile all native result indexes with the RUN ledger, dispositions, and ALERTS occurrences; review process sufficiency and evidence support separately. Preserve historical source states and results. Retest affected work when new source/policy/capability makes progress possible.

Stop when a reviewed plan is presented for approval, the assigned outcome is delivered, the user requests it, or a diagnosed blocker leaves no authorized feasible step. Record affected questions, attempted remedies, and resumption conditions. Keep questions open while plan approval or required external evidence is pending.
