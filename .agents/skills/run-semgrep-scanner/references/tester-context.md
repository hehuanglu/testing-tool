# Context: testing with Semgrep and source review

Start with functionality: who uses it, who controls the data, which assets/permissions matter, where expectations come from, and which source can answer the question. The requester need not design the workload. Choose the smallest useful check, then reconcile remaining scope.

## Three kinds of claims

- **Source structure:** inspected patterns, imports, control flow, call paths, predicates, and configuration. A match establishes only what that pattern/engine observed.
- **Runtime behavior:** deployed branches/configuration, actual data, redirects, expiry timing, and browser execution. Source supports hypotheses or constraints, rather than automatically establishing runtime results.
- **Policy correctness:** user-provided specifications/policies or authoritative documentation. Label expectations inferred from implementation as source assumptions; matching implementation does not certify the policy.

A bounded SAST conclusion does not require dynamic exploitation, two fresh runs, snapshots/hashes, or qualification of the entire scanner. Support must match the claim and inspected controls. A missing control in a small snippet does not establish system-wide absence.

## Working conditions

When documentation differs from source, record `document_statement`, `source_implementation_or_declaration`, `comparison_scope`, `authority_currentness`, and `permitted_claim` in the result/review. README/runtime notes are not automatically current requirements; leave authority/currentness unknown when unverified. Distinguish source/document discrepancies, violations of verified requirements, and missing runtime controls. Apply this to CFG-01 configuration and AUTH-05 guards/lookups. A declaration discrepancy is not a runtime exploit.

Source review does not require Git, deployment, tokens, or a build. When Git exists, record revision/dirty state and preserve existing changes. Otherwise record roots, observation time, and available version information. Do not provision a runtime or install dependencies merely to read source. Record changed source state and reassess affected work.

Inventory source/specifications/configuration independently of findings: modules, functions, entry points, input, identity, persistence, UI, and configuration. Public/protected describes inspected routing/guards. Jobs, events, and libraries also have trust boundaries; products need not expose HTTP.

Field/route/owner names are discovery hints. Inspect sanitizer/guard/wrapper implementations and callers before relying on them. Keep product mappings in a separate working area, outside the core skill; do not generalize one product's policy or verdict.

## Bounded responsibility

Scope defines questions; bases provide starting points; capabilities determine techniques. Missing bundled rules require consideration of local/custom rules with useful fixtures and feasible manual review, rather than N/A. Searches/inventory are not security observations. Record provenance and limits before reporting under the [workflow](tester-workflow.md).
