# FE anonymous research lane

`fe-anonymous-research/1.0` is a separate research contract. `product_assessment.py fe-anonymous` dispatches to `fe_anonymous_cli`; the backend `TRACKS` tuple, strict browser/canonical-origin capabilities and legacy diagnostic runner retain their contracts. Qualification evidence and unresolved obligations are recorded in the workspace's `review/fe-anonymous-audit-2026-10-23/IMPLEMENTATION_STATUS.md`.

## Commands

Use the assessment virtualenv and `scripts/product_assessment.py fe-anonymous --help` or `scripts/fe_anonymous_research.py --help`. Both support:

- `discover --product PATH --recipe ID [--observations FILE] --output NEW_DIRECTORY`: source-only; no deployment is invented. The explicit `finalsource-fe/1.0` recipe verifies supported source facts. `reviewed-fe/1.0` accepts independently reviewed source/DOM observations, with hashes and provenance, for other products.
- `plan --discovery FILE --journeys FILE --selection FILE --authority FILE --run-id ID --output NEW_FILE`: inspect deployment and freeze recipe, responsibilities, selection, authority, request policies, vectors, source/runtime and implementation pins.
- `run --plan FILE --selection FILE --output NEW_DIRECTORY [--interrupt-after COUNT]`: owned Firefox/WebDriver journeys, native Client Spider, selected native active scans and complete native reports. The interruption option is a controlled checkpoint before a selected journey; it does not emulate controller hard-kill recovery.
- `verify --run DIRECTORY --expected-plan-hash SHA256`: offline readback of artifact integrity and selected semantics. It sends no target traffic. An interrupted/partial bundle may pass integrity verification.
- `handoff --lineage FILE --output NEW_DIRECTORY`: select one retained run, with `run` and its independently recorded `planHash`. Optional `triage: {path, sha256}` supplies separately authored, evidence-based assessments matching each native rule/name group. A handoff never changes the native classification or source bundle.
- `status --discovery FILE`: offline source stage and obligation count.

The common backend handoff composer also accepts an explicit `tracks: ["fe-anonymous"]`; omitting `tracks` preserves the original three-backend requirement. Duplicate lineage units are rejected. Historical backend evidence does not become fresh execution when composed with FE results.

## Binding, identity and native execution

The selection identifies the current frontend container/image/start/network/address, canonical published HTTPS origin, ordered Compose files, source/config hashes, public certificate SHA256/DER fingerprint, source-matched scanner JAR and immutable runtime images. Certificates are trusted only within owned runtime/profile material. System trust and the product certificate are unchanged. A broker verifies upstream CA, hostname/SNI and fingerprint on every forwarded exchange. Kernel rules allow only the broker to connect to the pinned target. Browser access to ZAP management requires authentication; ZAP's browser children have loopback driver ports, with MCP management excluded. IPv6 and external/direct target egress stay denied.

Every journey creates and closes its own Firefox profile. It captures initial storage/cache/IndexedDB/service-worker/cookie state, UI assertions and bounded DOM facts/screenshots, then inventories and disposes the closed profile. Cookies require name/provenance admission. Credential headers, non-admitted cookie/query/body authority and unplanned identity transitions fail closed. Public registration/login responses remain anonymous request evidence; receipt/storage of identity ends that case's anonymous phase. Follow-up traffic is blocked without stripping credentials. Authenticated API fixture setup is a separate lane and is excluded from FE anonymous coverage; its exact intent/ACK/ownership/cleanup ledger is retained.

Native rules are identified by their installed name and ID. Rule 40012 is reflected XSS; 40018 is SQL Injection. The finalsource recipe retains validation/error controls and adds bounded email-query 40018 probes with a valid baseline, successful quote/markup registration, login persistence readback, and length boundaries. It does not claim SQL sink coverage, stored-XSS execution or exhaustive input coverage. Login uses a fresh owned unknown email, a baseline and at most two changed active probes and four total app requests including native unchanged controls/baseline, below the inspected lockout threshold. The broker enforces the campaign cap before delivery. Guard denials are not application payload exercise. Native stop/status and rule delivery are retained separately from successful technique coverage.

## Evidence and operation

Runtime preflight uses measured browser/TLS growth plus the existing 2 GiB reserve, Docker free storage and RAM; execution is sequential. Runtime sampling stops producers on reserve/cap/binding/identity breaches. Use exact owned disposable cleanup when already authorized; retain raw evidence and product data. Start/POST lost ACK is reconciled without replay. Do not use broad prune or change TLS to repair a failure.

Native history uses bounded one-message pages because bundles can contain large JS responses. Fixture evidence paths belong to the recipe. Captured app exchanges join to native history using method, canonical URL, request hash, status and text response hash. Binary assets explicitly record when the native decoded representation prevents a byte hash match. Independently re-evaluated DOM facts, fresh native session evidence, rule delivery, passive settling and JSON/HTML chunk EOF/hash readback support claims. Resource samples and missed cgroup reads remain visible.

PM output is `ALERTS.json` plus `fe-anonymous/`. Native alerts retain severity/confidence; browser observations are separately attributed. Response policies are grouped by document/assets/API/error response. Native raw, fixture credentials and screenshots remain private; the handoff references these external local artifacts and is not a self-contained portable archive. A finite scan is not a safety verdict or reviewer approval. Unrun/failed obligations keep task completion partial.

Native Client Spider uses the owned W3C driver wrapper because ZAP Selenium requests insecure certificate acceptance by default. `CLIENT_BROWSER_CAPABILITIES.json` records the requested and actual values; actual must be false. The wrapper leaves target requests/DOM unchanged and preserves ZAP/browser isolation. A controller-loss recovery is stop/export only; retained interrupted evidence is separate from any fresh replacement run.


Evidence 2.0 uses durable broker 2.0 request intents/events and independent semantics 2.0.
Historical 1.0 bundles remain immutable and readable; current semantic rejection is
recorded separately from their historical verifier result. A rule header without a
changed vector is a control request, never active payload delivery. Final counts are
refreshed after producer terminal/passive settle and independently checked against
native messages, baseline, exact operation start/status/stop and stable passive
observations before export. Stopped/terminal does not imply an exhaustive technique.

Branch admission requires base network/browser/private retention only; selected
active, mutation and setup branches add their permissions. Missing permissions keep
those branches not-run and task partial while independent branches continue. POST
read-like classification requires source provenance; the broker preserves the
mutation gate. Unknown mutation states (sent/response-headers/unknown) retain
correlation and a reconciliation/retention obligation, latch further producer
traffic and never replay. Only a proved pre-send error means not-sent.

Finalsource public input coverage combines valid sibling fields, the source input
map, browser validation/boundaries, native payloads and bounded owned persistence
checks. SQLi on bcrypt password and dynamic SQL in ORM save are not inferred from
rule names; N/A reasoning lives in responsibilities with source provenance. Markup
must remain DOM text with no injected element and be read back through a fresh login;
these are separate browser/API observations, not native exploit alerts. Successful
identities without a supported public DELETE remain in the private retention ledger.

Final UI transport counters/network claims are refreshed from final broker records after producer stop; journal ACK snapshots remain historical. Caps include unchanged native control requests as well as changed payloads.

Native control qualification also independently checks every host sample against reserve, raw detector outcomes and broker/app arrivals. A producer pass with a late sub-reserve sample is rejected in a separate disposition; retain raw and rerun into a fresh namespace only after sufficient headroom. The final resource-qualified pair and supersession are indexed by the current acceptance artifact.
