# Progress B-CORE-01

- Baseline saved before edits. Original episode treated as read-only. Scope is the admitted closure selection branch and offline verification.

- Historical probe ran with its original argv and reproduced the premature stop (exit 0).

- Before changing core, the final 14-test selector set failed exactly the two early-wait cases. Moved admitted closure ahead of waiting and re-ran all 14 successfully.

- Read-only corrected probe selected final-resource-review on the exact historical inputs and injected time.

- Isolated CLI selected closure, persisted the resource disposition, independently verified the local table, then reached workflow-done with zero dispatches. Baseline offline suites and walkthrough passed.
- Compared all 675 original episode file hashes and paths before/after. Tracked diff preserved.

- Completed implementation report and auditor handoff after resuming the interrupted reporting turn.

- Verified every report and handoff link. Re-ran the handoff command block from a clean scratch directory with exit 0, including the read-only probe, isolated CLI, all 226 tests, walkthrough and original episode hash comparison.
