# configuration-build — Configuration, builds, and dependency declarations

## Intent, applicability, and discovery

Discover actual configuration files, consumers/load paths, defaults/overrides/precedence, environments, CI, manifests/locks, and final build stages. File names and templates do not prove deployment. This track does not automatically include SCA/CVE scanning, runtime provisioning, or secret-validity checks.

## CFG-01 — Which configuration is actually consumed and with what precedence?

Discover loaders/entry points/environment sources/overrides/profiles/CI commands and shared layers. Derive expected configuration from authoritative deployment/product policy or labeled source assumptions. Trace files → consumers → defaults/overrides/precedence and distinguish source declarations from runtime facts. An env template, production filename, README, or unused config does not establish effective deployment. Record missing consumers/includes/overlays and authority/currentness for document-source discrepancies under tester context. Continue feasible source tracing while isolating runtime/policy dependencies.

## CFG-02 — Do runtime/container privileges fit the context?

Discover Docker final USER/stages, Compose users/privileged/capabilities/host mounts/sockets/chmod and actual consumers. Derive necessary privileges from isolation policy/assets rather than imposing one profile. Use bundled Docker/Compose candidates plus alternate-file searches/manual/custom checks. Inspect final versus build user, rootless/user namespaces, cap_drop/seccomp/read-write modes; a :ro Docker socket mount does not make its API read-only. Record declarations/overlays/controls without claiming runtime host compromise. Filtered filenames remain gaps requiring review.

## CFG-03 — Do network, TLS, browser, and server settings fit their context?

Discover TLS clients/servers/proxies/nginx/CORS/CSP/cookies/overrides. Derive transport/origin/content/session requirements from integration policy and cookie purpose/cross-site needs. Inspect actual loaders/options, inheritance, consumers, and precedence with TLS/cookie/nginx/CORS candidates. App/proxy layers, environment overrides, public CORS, and non-sensitive cookies may matter; omitted differs from explicit permissive. Generic nginx patterns do not understand all inheritance. Record configuration/control locations and unobserved headers/TLS; inspect missing shared layers.

## CFG-04 — What dependency declaration and download-source risks are in scope?

Inventory actual manifests/lockfiles/package sources across ecosystems, overrides/workspaces/resolution. Derive trusted/reproducible sourcing from policy; pinned declarations do not establish safe dependencies. Use npm wildcard/remote candidates plus manual integrity/immutability/resolution review. Inspect lock pins/mirrors/immutable Git refs/dev-runtime context/overrides; metadata URLs are not automatically dependencies. Record source/lock/config locations without CVE/reachability/SCA claims. Use appropriate local/custom/manual checks for other ecosystems; retain separately requested CVE capability gaps.

## CFG-05 — Which trust boundaries affect build/install/CI execution and artifacts?

Discover lifecycle/remote-shell/CI commands/build inputs/artifact publication/source maps where relevant. Derive execution trust and visibility from build/release policy; do not run scripts merely to review them. Inspect command construction/provenance/workflow references/publish consumers with shell/lifecycle/Vite candidates. Reviewed pinned downloads/integrity/private artifacts/unpublished maps/unused configs may explain matches. Record command/config/artifact/control locations; enabled source maps alone do not establish public exposure. Find missing scripts/publish configuration without installing/building/uploading.

## CFG-06 — Can sensitive configuration leak or use unintended fallbacks?

Discover credentials/keys in templates/config/defaults/CI and actual consumers/bundle exports/logs. Derive sourcing/retention/exposure policy; literals and secret names need not be real credentials. Inspect consumers/fallbacks/precedence/public-private use/redaction with relevant JWT/Vite candidates. Placeholders/public keys/client IDs/unreachable defaults/runtime injection may explain matches. Record filtered types/locations/consumers, never values; do not test validity. Continue value-independent review while recording runtime/policy gaps.

## Review ledger and completion

Record `{file, consumer_load_path, defaults_overrides, precedence, final_stage_or_inherited_setting, layer, missing_source, locations, question_id, next_step}` in `questions[].result` or manual-review observations. Values describe actually inspected facts; unknowns remain null with specific next steps.

Identify declaration/source versus actual runtime layers. Keep env templates and lockfiles in inventory despite detector filtering. nginx requires exact server/location/include/header scope: parent CSP may not inherit when a child adds headers; inspect add_header_inherit/config/version when supplied, and do not substitute another server or always for actual response context. Resolve Compose file sets/overrides/profiles from consumers/CI. Distinguish bundled build-time FE env from runtime injection and final Docker stages from build stages. Locks show resolution intent rather than installed runtime. Development defaults do not inherit unassigned production policy. supply-chain-config-static.yml covers limited Docker/Compose/nginx/npm/Vite/Node shapes, partly CFG-02…05; CFG-01/06 need substantial manual/custom review. Alternate names such as compose.prod.yaml remain responsibilities, not safe negatives.

Consult the [catalog](../rule-catalog.md) and [rules/triage](../rules-and-triage.md). Missing detectors require applicable local/custom/manual work, rather than N/A or clean results. Close assigned inventory/questions with source-appropriate claims and explicit runtime/policy limitations.
