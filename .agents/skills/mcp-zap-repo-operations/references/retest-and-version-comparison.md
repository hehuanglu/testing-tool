# Retest and compare versions

Use this technique only within the approved [criteria-driven plan](criteria-driven-workflow.md); it adds no track-wide assignment or alternative workflow. User delivery follows the [Drive table contract](single-table-drive-output.md); JSON/native artifacts below are internal working data.

Use when assigned finding retests/build comparisons, rather than requiring two fresh runs/fixed builds/source-image attestations for routine assessments. Deliver the [Drive assessment table](product-assessment-handoff.md); retain RUN/ALERTS/SCOPE_ALERTS internally.

Identify findings/APIs/roles/inputs/techniques, environments/versions, and known changes. Same routes with different roles/states/builds may differ; state unknowns. Source/old-report review is not runtime retesting and report deltas do not establish fixes.

Default to local repair and selective continuation under the [agreed policy](assessment-policy.md#flexible-execution-within-the-approved-assignment). Determine which observations/dependencies actually became incompatible; reuse unaffected facts, fixtures and results, revalidate the next action's live prerequisites and execute missing/affected cases only. Do not automatically run the whole catalog or rebuild all actors after a parser/adapter failure, new chat or build change. A full retest needs a concrete scope/dependency reason or explicit new assignment; a local repair remains the same run and Drive table.

Execute suitable scoped operations/fixtures/workloads to determine present/not-reobserved/inconclusive outcomes. Preserve native severity/confidence without changing suppressions/expectations/raw to remove alerts. Reconcile unknown prior mutations before replay.

Record actual retest work/times/builds in RUN and honest current findings in ALERTS. Historical unretested issues remain labeled. Narrow retests do not replace whole baselines; retries do not create new bugs or require claim/hash/lineage packages.

`compare_research_runs.py`, `bola_research.py compare`, and regression entries accept specific contracts: inspect help/source. Same-build comparison is not automatically an A→B retest. Label manual comparison honestly; checksums/test success are not security approval.
