# Discover authentication as a tester

Use discovery to support the [criteria-driven intake and planning phases](criteria-driven-workflow.md#intake-and-the-two-approvals). Source-only inspection may precede either approval gate; live discovery needs existing target/effect authority, and active testing waits for plan approval. This reference adds no track-wide assignment. User delivery follows the [Drive table contract](single-table-drive-output.md); JSON/native artifacts below are internal working data.

Use this when internal contracts are absent or actual authentication capabilities are unclear. Inspect permitted source/spec/UI/traffic yourself; do not ask the requester for discoverable documentation/token fields. Source discovery does not wait for Docker/runtime authentication.

Record method/route, source/spec/runtime provenance, and actual observations. Establish login/register, protected requests, and actor/role basics. Explore expiry/refresh/logout/revoke/role changes deeply only when relevant. Reports omit passwords/tokens and need no per-capability hashes/receipts/evidenceRefs.

Select a suitable protected probe/strategy to establish actor/role. Login 200 and unverified JWT claims alone are insufficient. Products need not expose whoami or common token pointers/issuers. Keep unavailable roles in inventory while continuing eligible ones.

Distinguish source-supported but runtime-unverified features; actual actor/route/time-bound results; features not observed; tested incorrect behavior; and missing capability/permission/fixture dependencies. Missing prerequisites do not imply N/A or remove obligations. Do not convert failures to skips or source support to runtime pass.

Local logout does not establish server revocation; new login differs from refresh/resume. Read [lifecycle depth](auth-lifecycle-and-bola-depth.md) for assigned lifecycle questions, rather than waiting for TTL or opening another campaign for routine handoff. Deliver the [Drive assessment table](product-assessment-handoff.md); retain RUN/ALERTS/SCOPE_ALERTS internally; discovery completion is not DAST completion.
