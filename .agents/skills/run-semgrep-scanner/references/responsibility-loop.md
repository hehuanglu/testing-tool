# Responsibility loop

Keep product inventory and questions independent of findings and selected workload. For each assigned track, reconcile inventory → question → actual technique → readback → disposition → next step. Follow the [sequential workflow](sequential-track-workflow.md) and [reporting contract](reporting-and-completion.md).

For each open item, decide whether to execute, repair a local issue, prepare input/source context, use another authorized technique, mark a genuinely inapplicable dimension, or document a specific external dependency. A decision is not execution: perform feasible next steps before handoff.

Read actual native JSON, stdout/stderr, errors, timeouts, skips, scanned paths, and source controls. An exit code, match count, or helper success does not establish coverage. Check ignored/unsupported files against the inventory; missing paths remain unresolved until explained or reviewed. Native counts are null when execution/output is unavailable, rather than zero.

When CLI execution fails, diagnose the smallest affected layer: engine/flags, rules, targets/ignore filters, parsing, output collection, or source context. Make minimal authorized corrections and run a focused check. Continue independent questions. Do not retry unchanged conditions, download remote rules, change engines, modify product code, or expand scope merely to obtain a passing run.

Manual review can answer a source question where suitable, with manual provenance. If the user specifically required Semgrep execution, retain that unmet requirement separately. A missing rule/policy does not erase feasible source work or automatically mean N/A, false-positive, or accepted risk.

Before closing a track, reconcile all native result indexes with the RUN ledger, dispositions, and ALERTS occurrences; review process sufficiency and evidence support separately. Preserve historical source states and results. Retest affected work when new source/policy/capability makes progress possible.

Stop only when assigned scope/triage is addressed, the user requests it, or a diagnosed blocker leaves no authorized feasible step. Record affected questions, attempted remedies, and resumption conditions. Partial/blocked work may be handed off without claiming whole-scope completion; continue independent subsequent tracks without an approval checkpoint.
