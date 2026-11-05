# SAST evidence embedded in ALERTS

Evidence supports a specific claim; it is not a proof campaign. Prefer locations and sanitized descriptions. Include short code only when necessary, non-sensitive, and authorized for sharing. Do not require copied source/secrets, evidence folders, raw pointers, snapshots, or hash manifests.

## Record

Each `findings[].evidence` includes these fields, with meaningful nulls for unknowns:

- `id`: unique across the assessment, including different findings.
- `kind`: `native-match`, `native-dataflow`, `source-review`, `control-review`, `policy-reference`, or `config-review`.
- `provenance`: `semgrep`, `manual-source-review`, or `provided-policy`.
- `claim`: the supported claim; `observation`: observed facts separated from hypotheses.
- `locations`: [reporting-contract](reporting-and-completion.md) locations; external policy may have none.
- `source_state_id`: RUN source-state ID for source-based evidence, otherwise null.
- `round_id`, `manual_review_id`: actual relevant RUN operations, nullable. Policy may use `reference` instead.
- `reference`: existing document/section/policy description, nullable; no mandatory raw-file/hash pointer.
- `flow_steps`: `{order, location, observation}` for actual inspected dataflow/call paths, otherwise `[]`. Order follows the path; do not invent locations.
- `limitations`: uncertainties that materially limit the claim.

## Kind, provenance, and operations

`native-match` requires Semgrep provenance, actual source state, and round; it establishes a pattern match. `native-dataflow` additionally requires actual inspected native trace output, which may still omit callers/files. Manual call paths always use source-review/manual-source-review with a manual review ID. Control/configuration reviews retain their actual observation provenance. Provided-policy references identify their authority; expectations inferred from source use manual provenance and an assumption label.

Source evidence must agree with its linked round/manual review's source state. Manual review may support a Semgrep finding while native rounds/occurrences retain their provenance. Maintain reciprocal manual-review/evidence/finding links. Enabling a trace flag alone does not establish native dataflow.

## Claims and triage

- `supported`: support fits the written claim and inspected controls/assumptions. Native matches alone cannot support claims beyond their patterns; dynamic exploitation is unnecessary.
- `false-positive`: actual pattern error or effective control on the inspected path; names and accepted risk are insufficient.
- `not-applicable`: retain scope/applicability rationale. Missing rules/timeouts/policy do not establish N/A.
- `needs-review`: a native match may be the only evidence. Record gaps/next steps without fabricating controls/traces; execute feasible steps under the [responsibility loop](responsibility-loop.md).

Missing native traces do not invalidate findings. Missing controls in a small snippet do not establish system-wide absence. Record deployment/runtime/policy assumptions in the appropriate gaps/limitations. File counts do not establish role/endpoint/runtime coverage.

## Review and examples

Before moving tracks, perform [evidence self-review](sequential-track-workflow.md#does-evidence-support-the-observations): compare native records to actual output, then re-read the source ranges/controls supporting claims. Existing files, in-bounds ranges, and a passing checker do not establish semantic support. Retain non-promoted candidates in RUN; fewer observations do not measure correctness or recall.

The [synthetic JSON pair](../examples/README.md) illustrates native-match/manual controls, needs-review, false-positive, and manual findings. It contains no real Semgrep output/trace. Check IDs, locations, source states, operations, and counts; never rewrite v1 history to invent missing evidence.
