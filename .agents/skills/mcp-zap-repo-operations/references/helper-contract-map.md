# Bundled helper contracts

This map covers the skill-level `scripts/` and vendored CI helpers. The [runner map](runner-routing.md) covers assessment-library executors. These are technical tools selected within the [criteria workflow](criteria-driven-workflow.md), not additional assessment workflows or mandatory acceptance gates. Inspect the selected entrypoint before use; a helper name does not establish compatibility or authorize its effects.

## Read-only and local maintenance helpers

- `scripts/inspect_operations.py`: reads `--repo` Java `@Tool` sources. Optional `--routing` checks exact tool-name coverage; `--runtime-tools` compares a saved complete tools/list with source registration and parameter names; `--candidate-tools` compares two saved runtime schemas and requires `--runtime-tools`. It never discovers a live MCP session. Source parsing does not attest requiredness, auth or deployed image. Routing errors exit 2; reported source/runtime drift still needs interpretation and does not itself make the exit nonzero.
- `scripts/review_open_work.py`: `work` reviews caller-declared responsibilities; `checkpoint` compares supplied snapshots; `session` reviews legacy continuation data and rejects v2. It reads JSON and prints diagnostics, without dispatch or state writes. Its declared-list/checkpoint flags are not assessment completion. Use `scope criteria-review` for v2 decisions. Exit 1 means attention/next actions, and 2 means invalid input; dependency-based partial handoff still requires reading the structured result.
- `scripts/install_skill.py`: `check` compares packaged files with a selected installation, without synchronization. `install` copies the complete skill; `--update` replaces a divergent installation while retaining a backup. Installation writes require that setup assignment; repository edits do not automatically authorize personal-install synchronization. It installs no Python dependencies and does not configure a scanner.
- `scripts/verify_saved_evidence.py`: reads historical campaign indexes and bundles under an explicit `--assessment-root`, compares recorded statuses and source pins, then writes a new `--output` outside that package. It expects historical indexes/runs that are not bundled with this skill. An installed skill alone cannot supply those artifacts. Its integrity/consistency checks are not a retest or semantic security verdict; no campaign is replayed.

## Product-specific operational helpers

The following scripts retain the fixed `finalsource-zap-test` environment, routes and evidence contracts. They are not defaults for a different project, an automatic v2 adapter or a linked end-to-end assessment pipeline. Their local receipt checks are necessary technical gates, not substitutes for actual user authority and the Gate 2 plan approval where applicable.

- `scripts/prepare_finalsource_fixture.py`: creates dedicated actors and an owned account, writes private generated credentials, intent/journal and BOLA preparation artifacts. It creates an isolated Docker client and retains product fixtures for authorized retesting; `--run-bola` additionally executes the prepared legacy BOLA lane. This is effectful setup/execution, not a status command. Its direct fixture API traffic does not itself establish ZAP-derived findings.
- `scripts/probe_finalsource_auth.py`: consumes prepared fixture/config/credentials, performs bounded direct auth controls and may create one weak-password test actor. It records sanitized responses and private credentials separately and cleans its owned Docker client. Direct auth observations require their actual provenance; they are not native ZAP active coverage.
- `scripts/run_finalsource_native.py`: `run` creates a fresh owned scanner namespace, uses anonymous crawl/selected GET active traffic and a backend guard, then exports tool transcripts/reports and a manifest. `guard` is its internal serving mode. `verify` reads a bundle's manifest and hashes only. Completion is the wrapper's finite technical chain, not all-case v2 completion; terminal scan status does not establish payload sufficiency. It does not establish authenticated DAST or a real UI journey.
- `scripts/verify_finalsource_delivery.py`: verifies a specifically assembled historical delivery layout, including `native-r3`, `bola-bundle`, `fixture`, `auth-probes`, `operator-sources` and `repo-checks`. These are caller-assembled inputs, not a layout emitted by one preceding script. In particular `auth-probes/login-failure-normalized-comparison.json` is additional retained interpretation; the auth probe itself records its comparison in `result.json`. Do not fabricate missing artifacts or rerun effects to satisfy this verifier. Its output is bundle-integrity/recorded-observation readback, not verification of the current Google Sheets delivery.

## Vendored CI gate

`lib/mcp-zap-server/.github/actions/zap-security-gate/mcp_zap_gate.py` is a pinned vendored snapshot; `lib/vendor-provenance.json` records its hashes. Its normal CLI sends seed/crawl/optional active/passive/report traffic. It has its own CI baseline/suppression/exit contract and does not implement v2 Gate 2 plan approval, per-case semantic evidence, recovery or Drive publishing. Reuse suitable parsers/collectors only after checking callers and signatures.

The normal CLI requires `--api-key`; this is not a safe path for a private credential under the skill's no-secrets-in-argv rule. Use the configured connector or an inspected compatible private in-process transport instead of putting a secret on the command line. Token-bearing seeds do not authenticate the later scan starts. CI snapshot normalization and suppression projections do not replace retained native records, IDs, ratings or raw reports in assessment reporting.

`run-assessment-regression.sh` delegates to the Python gate's `assessment-regression` branch, which invokes the selected assessment package's `scripts/w10_regression.py compare`. This replays finite retained evidence offline and maps every nonzero assessment exit to root exit 1. It can write comparison outputs and requires its historical request/artifacts; it does not run v2 criteria review or grant product scan authority.

## Historical documentation and absent artifacts

`lib/zap-product-assessment/docs/remediation/` retains historical decisions and qualification results. Some relative links point to external `test-artifacts/` or omitted continuation documents. Missing linked files are unavailable evidence in the portable package, not instructions to recreate history or claims that the corresponding capability passed today. Current workflow and acceptance guidance remain [criteria workflow](criteria-driven-workflow.md) and [operational validation](operational-validation.md).

## Managed state commands

Use `python -m zap_assessment.product_cli scope` with the bundled library on
`PYTHONPATH`. Use explicit private paths for the store and registry. The
following arguments are required unless shown in brackets.

```text
state-init --run PATH --operator PATH --state-dir DIR --registry-dir DIR --registration-id ID
state-resolve --registry-dir DIR --assessment-id ID
state-inspect --state-dir DIR
state-commit --state-dir DIR --expected-generation ID --commit-id ID --run PATH --operator PATH
state-merge --state-dir DIR --expected-generation ID --commit-id ID --packet PATH --result PATH
state-next --state-dir DIR [--evidence-index PATH] [--now RFC3339]
state-render --state-dir DIR
state-inspect-recovery --state-dir DIR
state-recover-leases --state-dir DIR --packet PATH
state-repair-open --state-dir DIR --expected-generation ID --commit-id ID --repair PATH
state-repair-update --state-dir DIR --expected-generation ID --commit-id ID --repair PATH
```

Use an empty JSON object at registration for a default block, then record
explicit work items as needed. Store snapshots retain the original artifact
base for relative references. Managed mutations return receipt metadata. An
identical retry keeps the commit ID and expected parent, even after a newer
generation advances the pointer. A failed projection can be rerendered.

State commands return 0 for success including waiting, 2 for invalid input,
3 for conflicts, 4 for integrity or recovery, and 5 for IO or unavailable
dependencies. Structured diagnostics include code, message and refs.
`--now` controls offline selection and is separate from runtime checks.

Managed `criteria-review`, `criteria-digest`, `criteria-packet`,
`criteria-native-read`, `criteria-reconcile-action`, `criteria-release-task`
and `resume-next` accept `--state-dir` in place of `--run`. Effect and cleanup
consumers reload the snapshot under the assessment lock. Other runners retain
their existing entrypoints. Use `state-merge` for a managed result. Raw
`criteria-merge` can retry an identical existing output and preserves its input.

### Retained execution bindings and inspection

Before acquiring a managed runtime packet, save it privately and commit the
optional work-item field
`executionBinding: {taskId, workerId, packetDigest, packetRef}`. An absolute
private path or a relative path under the original artifact base locates the
packet. On resume, the wrapper verifies the packet digest and authority against
the current approval or original readback binding, then checks the durable
claim and every packet resource. An acquired packet can become a dispatch
candidate only while its action is unused and its task is clear of conflicting
pending effects. Executor admission still applies. An existing own-assessment
lease without a work binding can lead to `prepare/resolve-execution-binding`.
Resolve it against the retained packet and coordinator journal.

`state-inspect` checks the current generation and its hash-linked committed
ancestry. Exit 4 with `committed-history-integrity` means the current snapshot
verified and its ancestry requires recovery. Use the reported refs to locate
the failing link. Staged generations outside the ancestry do not affect this
result.
