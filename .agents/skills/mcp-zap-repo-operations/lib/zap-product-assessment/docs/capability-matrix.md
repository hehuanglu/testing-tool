# W4 admission update

The [W4 runtime contract](remediation/W4_RUNTIME_VI.md) adds mandatory pinned
safety/calibration preflight at the anonymous live entry. Missing proof blocks
before provisioning; incomplete egress attribution blocks before producer work.
The generated registry remains the current claim index; historical pilot evidence
does not satisfy G5/G6 operational acceptance. Planning, readback and stop-only
recovery remain available. BOLA is still a separate narrow direct-client contract.

# Current routing — W3

Use the [generated capability registry summary](remediation/CAPABILITIES_GENERATED.md)
for current claims, scope, known failures and hashed evidence links. See the
[W3 contract](remediation/W3_REGISTRY_VI.md) for fail-closed mode guards and secret
sink readiness. Native/delegated/business P0 is blocked; v2 is offline-only. Existing
anonymous and direct-client BOLA contracts keep their own admission checks.

Everything below is the **historical M2/M3 snapshot**, including old product
unverified/metadata-only statements and fixed counts. Later bounded product proof
is recorded in implementation-status.md and the registry; no current IP, authority
or runtime acceptance is inferred from this historical matrix.

# M2 capability matrix — separate observation levels

Current M3 extension: account-read BOLA supports owned synthetic v1.3 and borrowed Docker v1.4 login/read through an isolated client, independently verified with9 borrowed cases/34 focused tests. Follow `m3-borrowed-runbook.md`; the M2 unsupported/auth and metadata paragraphs below are historical for the ZAP path, not a claim that the separate BOLA entry is missing. No ZAP credential path or general authenticated DAST was enabled; actual finalsource BOLA remains unverified pending real inputs/authority.

Pinned clean source reference: upstream v0.16.0 commit0ebe11c3ae4c17de59fde0654e19b3e35e42ca20. Dirty JSON/Bearer checkout excluded and preserved. Observed binary version/image digest and source tag are separate provenance; no source-to-binary attestation is claimed. See runtime-baseline.json and per-run manifests for exact pins, actual tools/list and add-ons. Historical evidence `evidence/integration-campaign.json` stays immutable; continuation evidence is under `evidence/m2-binding/`.

## Synthetic baseline — verified

- Guided/direct HTTP crawl/start/status/stop, JSON string envelope decoding, empty session readback. Direct idempotency key is ignored upstream; interruption/lost ACK reconciles by stopping the dedicated engine, no replay.
- Self-contained OpenAPI3 JSON URL import to isolated fixture; exact hostOverride. Required GETs are separately exercised/asserted through ZAP sendRequest; import alone is not coverage. OpenAPI add-on58.0.0 observed.
- Passive settle requires two stable Completed=yes/backlog0 observations. Timeouts block. Scoped JSON report add-on0.46.0, Unicode-codepoint chunks + UTF8/full hash/length checks, atomic bundle publication. Corrupt/truncated data cannot become complete evidence.
- Mandatory proxy readback, network add-on0.31.0 rate readback and guard rate enforce1–2rps. Scanner UID can reach only guard; direct target/control/metadata/external/IPv6 sockets fail. Exact origin/Host/scheme/CONNECT denials; forbidden target counter zero. DNS has no permitted network path.
- Unique namespace/container/session/workspace + intent/ACK journal + owner identity. Two historical clean runs and real interrupted/lost ACK cases verified; old bundles still verify under v1.0 schema. Medium findings retain review_required, not a product/security pass.

## Existing-target binding — implemented; independent integration evidence

- Registered `docker-existing-http-v1` takes its binding and guard configuration from validated immutable v1.1 plan. Borrowed target container/image/StartedAt/network/IP checked via read-only sideplane before setup and at phase/poll boundaries; health oracle checked before crawl. Container mount identity for products is unsupported and rejected.
- A separate synthetic application is provisioned by tests/support/borrowed_target.py before executor. It is not the legacy fixture module and executor never provisions it. Clean integration evidence is in `evidence/m2-binding/binding-acceptance.json` (only allAssertionsPassed=true is a complete campaign); additional development complete run rd82045d73b81441d8c61209ab685b96e is retained separately.
- Content import semantics were source-described first, then exercised with real pinned MCP/ZAP: `zap_target_import(sourceKind=content)` uses a dedicated POSIX shared volume and exact success envelope. UID1001 named principal + writer lock/mode0750; ZAP group1000 read-only mount. URL, content and file capability claims are distinct: URL legacy verified, content existing adapter verified by bundle, arbitrary file import unsupported.
- Independent campaign covers two fresh sessions, target identity/build mismatch before crawl, exact-path egress/credential refusal, target preservation after scanner cleanup, interruption/lost ACK and real report hash/truncation faults. Final campaign allAssertionsPassed=true, all10 cases passed; verification.json confirms readback. A separate health-only-binding.json also passed and observed only GET /api/health reaching its independent synthetic target, including nested health assertions. Kernel/guard proofs and full chunk readback are required by v1.1 verifier. Guard refuses credential requests/responses before forwarding; this is anonymous safety, not authenticated secret-gate coverage.
- Supplemental MCP findings lookup requires a crawl-covered URL prefix; requesting root after path-only crawl is rejected upstream. Summary uses approved crawlPath; full JSON report determines verdict for all declared seeds. Guard-generated Server/Date headers are a report provenance limitation.
- Owned scanner anchor, guard, ZAP, MCP and content staging volume are cleaned; borrowed container/network/volumes are never stopped, removed, reset or exec'd by runtime. Anchor attaches to approved bridge with inert sleep PID1; DROP rules precede scanner/MCP/guard startup. No host ports or Docker socket exposed. INPUT and IPv6 also DROP for this binding.

## Unsupported or unverified

HTTPS/hostname/DNS/IPv6-capable existing adapter, browser/JS/dependency traffic, authentication/credential resolver, JSON/Bearer experimental, active execution, GraphQL/SOAP/Swagger2, queue/PostgreSQL/shared history, Linux CI, wheel distribution and independent operator/reviewer acceptance. Tools being exposed is not operational verification. M3–M7 remain deferred; no automation, publish, merge or shared service deployment.
