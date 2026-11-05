# Execute and self-review each track

This is the default assessment workflow, rather than an additional evaluation campaign. The operator performs Semgrep/source review and takes responsibility for process and evidence self-review. Do not automatically spawn another reviewer or describe self-review as independent evaluation.

## Scope and order

Run only authorized tracks. For a whole-product assessment, discover applicability and prefer be-input → fe-browser → authentication-session → authorization-ownership → configuration-build unless dependencies justify another order. State ordering changes. Preserve the narrower scope of targeted scans, candidates-only tasks, and retests.

Reuse discovery/source-state/control reviews only with provenance and current applicability. Finish feasible local work, reconcile, and save the current track before executing the next. Do not run all five scans before triage. A track may need multiple rounds/manual reviews; neither one scan nor all bundled rules are mandatory.

Combine cross-track execution only at the user's request, retaining question/track mappings and real native provenance. References must resolve within each assessment, rather than treating IDs from another RUN as local. Reused output retains its original command/time/source state and reuse provenance; do not invent an executed round.

## Track cycle

1. **Discover and announce:** identify surfaces/callers, input/identity/object/state or consumers/precedence from source/spec/config. Inspect ignores, paths, languages, and scope independently of matches. Bind each entry point to the correct module/class/handler/registration; the first decorator in a file does not route every class.
2. **Checkpoint:** save known source state, inventory/questions, expectations/sources, closure conditions, and planned techniques in RUN. Unknowns remain null/open. Do not prefill future round/review IDs or conclusions. Timestamp new branches with `introduced_after_round_id`; record mapping/technique changes in `changes`.
3. **Select and execute:** inspect local rules and question-specific applicability; select the smallest suitable target/check. Keep native and manual techniques distinct. Questions without detectors retain manual/custom-rule responsibility.
4. **Collect/read:** retain command/cwd/targets/time/exit, native JSON/stdout/stderr, and actual metadata privately per round. Read results/errors/timeouts/paths/skipped_rules/logs. Configured does not establish loaded/executed/actual engine. Compare requested inventory against scanned paths; absent files need diagnosis/review even when skipped=[] and cannot become negative passes.
5. **Triage:** keep every native result index in the RUN ledger, including inventory-only candidates and ALERTS observations. Inspect source/callers/receivers/controls. Reuse shared-control review with every index/rule/location and grouping rationale. Same line/rule alone does not imply the same issue. Manual findings have no fabricated native occurrences.
6. **Reconcile:** link inventory → question → actual technique → control/use/write → result in the track ledger. Split differing controls/expectations/consumers. Perform feasible local steps under the [responsibility loop](responsibility-loop.md); retain specific external dependencies/blockers.
7. **Self-review:** answer the two questions below, repair feasible gaps, and save ALERTS/RUN with actual status. Briefly report track results/open work and continue independent tracks without waiting for confirmation.

## Is the process sufficient for the scope and claims?

Compare applicability/inventory with the actual assignment, rather than rule/finding counts. Include branches that could change conclusions:

- Backend: input → validator/transform → query/execution/resource/disclosure sink → response/write; distinguish create/update and query parameters/SQL text.
- Browser: route/component → input → render/navigation/storage/API consumer. UI guards differ from server enforcement; limit server claims to inspected controls.
- Authentication: actual enrollment, login verification, hash configuration, issue/verify/principal, and lifecycle. Heuristic thresholds differ from policy; client cleanup differs from revocation.
- Authorization: actor/action → object/collection/count/reference/state → predicate/check → use/write. Identify receivers and referenced resources; detail checks do not close collections.
- Configuration/build: file → consumer/load path → defaults/overrides/precedence → layer/final stage. Filtered lockfiles/config remain inventory when in scope.

Separate answered source questions from genuine policy/runtime dependencies. Source scope may be completed with supported issues and untested runtime behavior. Unfinished assigned triage keeps a question open and track partial. Do not demand new policy for every handoff; missing policy does not excuse feasible source work or imply N/A/false-positive/accepted risk.

## Does evidence support the observations?

- Reconcile **every native index** per round with ledger/disposition and ALERTS occurrences where applicable. Grouping must not discard matches. Native matches, observations, occurrences, and unique issues are different units; do not assume additive counts for many-to-many mappings or unknown deduplication.
- Compare native rule ID/path/start/end/message/severity/confidence with actual output. Unknown fields stay null; do not infer from names or summary logs. Redact sensitive content with a note without changing message meaning.
- Re-read source locations supporting claims/controls. Existing files and in-bounds lines are insufficient: a closing brace or missing check/use does not establish the claim. Dataflow/call paths need inspected steps. Manual traces remain manual; native dataflow requires actual inspected output traces.
- Check source/round/review provenance, IDs/backlinks, and checkpoint timing. Reassess affected work after source changes. Do not require hashes/snapshots or read private-key bytes merely to obtain an integrity label.
- False-positive requires a real inspected control. Supported applies only to the stated claim. Documentation/source discrepancies retain authority/currentness and permitted-claim limits, rather than becoming requirement violations/runtime exploits. Needs-review retains specific gaps/next steps.
- Run the [link checker](../scripts/check_report_links.py) where available, then review source/native truth. Passing bookkeeping does not replace semantic review or measure recall. Adequate evidence for recorded observations does not establish absence of missed defects.

## Output and transition

By default use `<assessment-root>/<track-id>/ALERTS.json` and `RUN.json` outside the product, preserving history. Keep raw/log/rules/settings privately outside targets; state if a temporary working area may be cleaned. Store self-review in `tracks[].review` under [reporting](reporting-and-completion.md), without a third file or approval gate.

Move on when available output has been collected/read and feasible local work is addressed, even if documented dependencies leave partial/blocked status. Unexecuted native counts are null, not zero. Later tracks do not erase earlier open work. New in-scope source/policy/conditions may justify another round/review while retaining history.

For a separately requested skill evaluation, aggregate process and evidence reviews while separating evaluation status from product assessment status. Identify actual self-review, senior assistance, or independent review. Do not copy another product's verdict/counts or add oracle campaigns, proof runs, benchmarks, or independent evaluation without an assignment.
