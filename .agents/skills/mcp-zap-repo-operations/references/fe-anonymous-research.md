# Anonymous frontend research

Use this technique only within the approved [criteria-driven plan](criteria-driven-workflow.md); it adds no track-wide assignment or alternative workflow. User delivery follows the [Drive table contract](single-table-drive-output.md); JSON/native artifacts below are internal working data.

Start from [track intents](track-intents.md) and select operations/executors through [dispatch](operation-dispatch.md). Entry-specific details do not expand scope or require an additional qualification campaign. Deliver the [Drive assessment table](product-assessment-handoff.md); retain RUN/ALERTS/SCOPE_ALERTS internally, without evidence sections/folders.

Profile `fe-anonymous-research/1.0`, plan `fe-anonymous-research-plan/1.0`, journeys `fe-anonymous-journeys/1.0` form a separate research lane. Existing strict browser-e2e/canonical-origin/backend contracts remain unchanged. Inspect implementation status/current proofs rather than equating available help/controls with runtime qualification.

## Entry and discovery

Use verified assessment Python/dependencies:

```sh
"$ZAP_PYTHON" "$ASSESSMENT_ROOT/scripts/product_assessment.py" fe-anonymous --help
"$ZAP_PYTHON" "$ASSESSMENT_ROOT/scripts/fe_anonymous_research.py" discover --product /absolute/product --recipe reviewed-fe/1.0 --observations /absolute/observations.json --output /absolute/new-discovery
"$ZAP_PYTHON" "$ASSESSMENT_ROOT/scripts/fe_anonymous_research.py" plan --discovery /absolute/DISCOVERY.json --journeys /absolute/FE_JOURNEYS.json --selection /absolute/selection.json --authority /absolute/authority.json --output /absolute/new-plan.json
"$ZAP_PYTHON" "$ASSESSMENT_ROOT/scripts/fe_anonymous_research.py" run --plan /absolute/plan.json --selection /absolute/selection.json --output /absolute/new-run
"$ZAP_PYTHON" "$ASSESSMENT_ROOT/scripts/fe_anonymous_research.py" verify --run /absolute/run --expected-plan-hash PLAN_SHA256
"$ZAP_PYTHON" "$ASSESSMENT_ROOT/scripts/fe_anonymous_research.py" handoff --lineage /absolute/lineage.json --output /absolute/new-handoff
```

Discover/status/verify/handoff are offline and do not start Docker/browser/network; planning checks selection/deployment without journeys. Unknown recipes do not imply folder-based product selection. finalsource-fe/1.0 is explicit and requires actual source/DOM inspection. No-source products need authorized bounded UI discovery and provenance-bearing observations; the current provider is not a universal framework parser.

## Admission and execution

Plans lock source/recipe/implementation, canonical origins, actual frontend Docker/cert/config/build relationship, public request policy, authority, journeys/UI+network predicates, vectors, runtime/browser/images/add-ons, calibration, retention, and stops. Keep credentials off argv and fresh fixture values private; missing success fixtures block dependent branches only.

Use fresh browser profiles per case, bounded W3C actions, and code-owned probes, rather than recipe-supplied executable JS. Anonymous cookies need names/origins/provenance. Cookie deletion alone does not establish clean storage/IndexedDB/cache/SW. Public login/register responses can end anonymity by issuing tokens/storage; stop authenticated follow-ups rather than stripping tokens and claiming original behavior. SPA 200 is not a route oracle; client-blocked submits do not establish API validation.

Canonical HTTPS preserves scheme/host/port and Host/SNI. Owned brokers decrypt before policy and verify upstream CA/hostname/fingerprint. Trust ZAP CA only in owned profiles; no acceptInsecureCerts/system-trust changes/product-cert replacement/HTTP mirrors. Verify actual kernel/management boundaries; CONNECT allowlists alone are insufficient. Guard or explicitly bound DNS/IPv6/redirect/WebSocket/SW/third-party gaps; do not probe public Internet for deny controls.

## Native active and recovery

Client/AJAX crawlers supplement actual journeys; auto fallback does not establish JS coverage. Bounded anonymous POST uses verified native primitives because guided method/body requires prepared auth; never fake handles. Inspect actual MCP schemas. Enabled rules are not payload delivery: retain actual rule/version/vector/baseline/response semantics. Passive alerts do not remove active duties. Reflection differs from DOM execution. Use finite fresh registration identities and login budgets below lockout, without brute force. Unsupported bodies/vectors stay gaps rather than blanket N/A.

Journal intent/ACK/native IDs/terminal; reconcile unknown starts/POSTs without replay. Stop owned producers on identity/scope/resource/binding breach, settle passive if feasible, export partial, and clean exact authorized resources. Private data uses 0700/0600. Current browser/TLS calibration and reserves apply; HTTP calibration does not admit different workloads. Existing startup/exact-disposable-cleanup authority persists without renewed requests; no broad prune/DB/evidence/user-data deletion.

Rule 40012 is reflected XSS; 40018 is SQLi, regardless of campaign names. Validation/credential-error arrival does not establish SQL sinks. Read individual native messages where JS responses are large, rather than hiding capture gaps by increasing transport caps. Client Spider drivers need owned namespace loopback while preserving management auth/direct/IPv6/external egress restrictions.

Read the [bundled executable runbook](../lib/zap-product-assessment/docs/fe-anonymous-research.md) for selection/authority/reproduction. Verifiers correlate browser/broker/native history and captured DOM rather than trusting producer pass flags. Optional triage hashes remain internal, with native classification unchanged. The geckodriver adapter forces W3C acceptInsecureCerts=false and verifies returned capabilities; inspect CLIENT_BROWSER_CAPABILITIES.json. Broker TLS alone does not establish browser capability. Controller loss requires journal/owned-ID stop/export and interrupted/partial; replacement runs use new IDs/profiles/fixtures and do not duplicate findings.

## Independent semantics F1–F4

New evidence uses fe-anonymous-evidence/2.0 and fe-broker/2.0; frozen plan/journey 1.0 remains readable. Readers return semanticsVersion=independent/2.0 without inheriting old completion claims. Reverify in new namespaces, preserving historical readers/pins/verdicts/raw/index bytes; corrections are not traffic reruns.

Broker fsyncs intent/append-only events before send, then sent → response-headers → response-observed. Sent means possibly transmitted; only complete responses establish forwarded=true. Post-send failures remain unknown/forwarded=null with allocation/case/campaign/request/status. Only grounded pre-send not-sent establishes false. Unknown mutations latch producers and require reconciliation/retention through UNKNOWN_MUTATIONS.json/durable events/private fixtures, without replaying POSTs to discover outcomes.

Admission derives from selected journeys/campaigns/hooks. Browser/passive/read need no automatic active/public-mutation authority; POST read-like needs effect provenance. Mutations/setup need actual permission enforced by broker as well as controller. Preserve missing-authority branches in ADMISSION.json/inventory with partial status.

Delivery requires final broker responses, native messages/baselines, exact method/path/rule headers, changed target vectors, stable siblings, and verified application TLS. Rule headers on unchanged bodies are controls rather than delivered payloads. Re-read after terminal/passive settling; compare counters/OPERATIONS and raw start/status/stop with two stable passive observations before export where enforced. Producer flags are insufficient; stopped/terminal does not mean all techniques delivered. Unknown/unresolved applicable duties prevent completion.

Reconcile public inputs against DTO/service/UI/runtime before techniques. Valid baselines keep siblings valid; invalid emails must not be used to avoid persistence then close public-form active scope. Password bcrypt differs from parameterized email SQL. Retain boundary/error controls at their actual depth. Register quote/markup questions may need finite fresh identity/success transition/persistence/retention; DOM text/element observations do not establish all stored/DOM vectors. N/A needs input/sink provenance, without exhaustive field×rule products or capability-driven scope reduction.

Login caps include baselines/unchanged controls, not only changed payloads. Recompute final UI/network counters after stop while preserving original ACK journal. Owned controls also need independent HOST_SAMPLES/reserve/native/broker/app/pin readback. A producer boundary-pass does not override late reserve breaches; preserve raw verdicts, reject qualification, and rerun only appropriate controls in a new namespace once headroom exists.

Internal report projections still contain actual RUN/ALERTS/SCOPE_ALERTS, with separate browser provenance/full gaps, rather than mandatory raw/hash packages or two-fresh/interrupted qualification for ordinary assessments.
