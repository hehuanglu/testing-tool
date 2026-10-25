# Explicit multi-product backend workflow

The common entry is `scripts/product_assessment.py` (use the package `.venv/bin/python`). It accepts product location, discovery, explicit recipe and track; legacy CLIs retain their original finalsource scope. No product/deployment changes are needed to author/test a recipe. The scanner engine, native JSON bearer provider, queue, strict gates and historical readers have not been replaced.

Source trees can use `--observations`: an agent reads source/spec and supplies pinned source facts; this is source-assisted discovery, not automatic multilingual parsing. `product_discovery.py validate` still only validates existing discovery. Candidate schema `product-source-candidate/1.0` intentionally has unresolved environment/binding/origins. `status` and `templates` require no network/deployment for this stage.

`materialize --candidate FILE --deployment FILE --output NEW.json` requires environment provenance and independently checked Docker backend selection. Selection contains `transport=docker-http/1.0`, container/environment/network/port and expectedBinding. Backend origins include observed aliases; host direct origins come from published IPv4 loopback ports. No frontend/proxy/cert requirement. TLS/proxy/remote transport requires its own proven inspector; current unsupported messages do not disable trust checks.

`plan --product PATH --discovery FILE --recipe ID --track TRACK --selection FILE --authority FILE --workload FILE --run-id RUN --output NEW.json` freezes recipe, implementation, source, authority and origins. Every workload allocation must be in the selected operation subset and actual authority. Inventory gaps remain visible. Unknown recipes stop before inspection/setup. The authority record points to current explicit user instructions and binds product/environment/deployment/operations/expiry; it does not grant permission by itself.

`prepare --plan FILE --selection FILE --output NEW_DIR` creates only the register role of that recipe, validates independently registered subjects through protected JSON, and writes private actor files and immutable ledger revisions. `business-fixtures` additionally requires actors/catalog with current dedicated ownership/authority and a recipe-owned DAG. Actor/order retention remains explicit when APIs cannot remove them.

`run --plan FILE --selection FILE --output NEW_DIR` reuses AnonymousRun, ResearchRun or DirectClient/Journal observation lane. Auth accepts a private single actor (`--actors`, not dumped into logs), `--jar`, and `--jar-pin`; BOLA accepts private actor map. The native pin includes JAR hash, provider/source refs and compatibility evidence; current-source pin alone does not prove a binary rebuild. Common native mutations require locked direct post-state assertions, separate from ZAP coverage. Plain read-only/native active subsets remain usable when business fixtures/privileged roles are unavailable.

Recipe registry:

- `finalsource-ledger/1.0`: finite source/fixture compatibility, existing finance mapping. Legacy extended preparation, BOLA continuation and historical evidence remain their own versions. The new common subset does not inherit historical runtime qualification.
- `archive-control/1.0`: owned nonfinancial HTTP fixture; different routes/methods/envelopes/string IDs/201/204/pagination/soft-delete. It proves the common path, not a third product scan.

Policy for BOLA observations is locked before traffic. The independent checker reads expected values and observations, never executor `evaluate` or its pass flags. Missing policy acceptance, unknown projection, incomplete pages and missing denial post-state remain inconclusive. Shared catalog references and employee reads are distinct from forbidden cross-owner access. New observation schema is `product-bola-observations/1.0`; legacy research/BOLA readers are unchanged.

Runtime control runner: `scripts/multi_product_control.py --track be-authenticated|be-anonymous --kind fresh|interrupted --output NEW_DIR`. It creates an owned archive backend/network, uses the same plan/prepare/run CLI, retains private evidence, then removes only exact owned control/scanner resources. It never logs in to example/finalsource. Native artifact/resource gates use the existing bounded Docker HTTP research profile, with topology qualification still separate.

Current proof, commands, failures and dependencies are in `test-artifacts/multi-product-20261021T135734Z/`. Source/compiler/control/runtime states are separate. No new product runtime qualification is implied. Handoff uses existing `pm-alerts/1.0`; raw native files remain private. Never manufacture product ALERTS.json when product traffic was not run.

The common native active boundary includes GET/query and conditional
`native-flat-json-update/1.0`: PUT/PATCH, a flat JSON object, one recipe-mapped
mutable scalar, fixed references, exact owned object and transition oracle. Product
workloads must supply a current hashed controlled-native proof (`nativeBodyProof`).
`nativeControl` requires fixture ownership independently observed from Docker labels;
it is not an escape flag for a product. Nested/array shapes, active POST/DELETE,
path/header, queue and strict remain separate boundaries. Native seeds and direct
oracles are not active body coverage. Read actual wire/rule attribution and accepted/
rejected state evidence rather than interpreting enabled rules as exercise.

Private `import-actor` uses pinned independent subject/role evidence plus a recipe
`protected-json-subject-role/1.0` mapping. It checks protected identity, anonymous and
invalid-session controls; native monitoring also checks the role. A product without
a suitable protected subject/role strategy remains blocked for that actor. Login,
JWT claims and public200 do not replace protected identity.

`reconcile` selects missing evidence per reviewed case and its own prerequisites;
`continue-plan` freezes a selected next allocation. Unknown outcomes require state/
allocation reconciliation. `handoff --lineage FILE --output NEW_DIR` composes pinned
retained and continuation handoffs with unique obligation units; retry units cannot
be counted twice. Raw run status tuples remain in the lineage. This does not close
task coverage or accept source-hypothesis policy. See the latest resume evidence
under `test-artifacts/assessment-resume-20261023T085641Z/` for commands, proofs and limits.

The optional `signed-jwt-protected-probe/1.0` identity strategy is for explicitly
reviewed research recipes. Freeze `actorRole`, independent subject/role evidence,
deployment-bound public-key provenance, issuer/audience/role claim and protected
probe marker/status. Import verifies the signature and actual protected response
plus anonymous/invalid401 controls; native Java and Python monitor the actual wire
token. Status403 is authenticated denial only with this compound proof, never
business success. Status0 history records are retained as no-response/unproved
coverage. Unknown mappings, keys, claims or source drift reject execution.
Research-plan2.1 adds only an optional versioned identityStrategy field; old2.0/2.1
readers/default protected JSON behavior keep their existing meaning. Queue and
strict/native secret-safe gates are unchanged. See the identity continuation
evidence under `test-artifacts/assessment-identity-20261023T094019Z/`.
