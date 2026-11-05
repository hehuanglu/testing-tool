# Bundled rule catalog and capability limits

Each entry maps an actual rule to question bases, rather than enumerating vulnerabilities. `inventory-candidate` locates source/controls requiring review; create a security observation only for a describable concern. `security-observation` still requires triage before becoming a supported issue. Mapping one rule to several bases does not multiply counts.

| File | Primary track | Stack | Incomplete bundled coverage |
|---|---|---|---|
| [be-public-static.yml](../rules/be-public-static.yml) | be-input | TS/Nest/Node/TypeORM | Stack-specific templates/archive/deserialization; wrappers/cross-file flows |
| [fe-public-static.yml](../rules/fe-public-static.yml) | fe-browser | TS/React/browser/Vite | Vue/Angular, named handlers/wrappers, UI/server permissions |
| [be-auth-static.yml](../rules/be-auth-static.yml) | authentication-session | TS/Nest/Passport/JWT/bcrypt + generic | Passwordless/SSO, lifecycle/state, varied global guards |
| [authorization-ownership-static.yml](../rules/authorization-ownership-static.yml) | authorization-ownership | TS/Nest/TypeORM shapes | Function permissions, arbitrary persistence/names, relations/lifecycle |
| [supply-chain-config-static.yml](../rules/supply-chain-config-static.yml) | configuration-build | Docker/Compose/nginx/npm/Vite/Node | Precedence, custom filenames, other ecosystems, varied CI/credentials |

## Interpreting coverage

- `bundled-partial`: relevant detectors exist, but discovery/triage/manual work remains. Applies to BE-IN-01…06, FE-BR-01…05, AUTH-01…03/06, AUTHZ-02/03/06, CFG-02…05 when stack/shape matches.
- `manual-review`: starting point for FE-BR-06, AUTH-04/05, AUTHZ-01/04/05, CFG-01/06. Related detectors do not close these bases.
- `custom-rule-needed`: inspect repository/local rules, then useful focused fixtures/rules for unsupported abstractions/languages/paths. Continue feasible manual work. Missing coverage does not imply N/A.

Ownership naming regexes do not cover arbitrary models; TypeORM patterns do not cover every persistence wrapper. Compose recognizes four conventional basenames; Dockerfile/Vite/nginx/npm filters also have limits. Discover alternate files/overrides and preserve mappings. Numeric thresholds require policy interpretation; native severity is not a policy violation. Generic regex differs from structured-language/taint semantics, and local CE flow does not establish cross-file/function coverage. TS zero matches cannot clear Python/Java/Go. Configuration-build does not establish CVE/SCA results or secret validity.

## Individual rules

### be-public-static.yml

File: [rules/be-public-static.yml](../rules/be-public-static.yml); 21 rules. Entries specify language, role, base IDs, and limitations.

- `nestjs-public-dangerous-eval` — language `typescript`; **security-observation**; base `BE-IN-02`. Eval/Function usage; review input trust and actual execution.

- `nestjs-public-child-process-shell` — language `typescript`; **inventory-candidate**; base `BE-IN-02`. Recognized imports/methods and literal shell:true; inspect other wrappers/options.

- `nestjs-public-raw-query-string-construction` — language `typescript`; **security-observation**; base `BE-IN-01`. Local construction into SQL text; external input is not established.

- `nestjs-public-request-body-mass-assignment` — language `typescript`; **inventory-candidate**; base `BE-IN-05,AUTHZ-06`. Body-shaped APIs; create/merge may not write; inspect DTOs/callers.

- `nestjs-public-sensitive-console-output` — language `typescript`; **inventory-candidate**; base `BE-IN-06,AUTH-06`. Expression-name regex without material/redaction semantics.

- `nestjs-public-cors-wildcard` — language `typescript`; **security-observation**; base `CFG-03`. Nest enableCors shapes; inspect credentials, endpoint purpose, and effective overrides.

- `nestjs-public-validation-pipe-without-whitelist` — language `typescript`; **inventory-candidate**; base `BE-IN-05`. Direct pipe options only; runtime validation may exist in another layer.

- `nestjs-public-validation-pipe-allows-unknown-fields` — language `typescript`; **inventory-candidate**; base `BE-IN-05`. No recognized literal forbidNonWhitelisted:true; strip/allow policy remains unknown.

- `nestjs-public-internal-exception-disclosure` — language `typescript`; **security-observation**; base `BE-IN-06`. Exception-name regex and response-shaped API; inspect serializer/actual content.

- `nestjs-public-swagger-without-environment-guard` — language `typescript`; **inventory-candidate**; base `CFG-01,CFG-03`. Recognizes some direct guards; enclosing conditions/proxy access are incomplete.

- `nestjs-public-exception-stack-in-http-error` — language `typescript`; **security-observation**; base `BE-IN-06`. Stack in exception construction; inspect error envelopes/runtime context.

- `nestjs-public-querybuilder-dynamic-sql-local` — language `typescript`; **security-observation**; base `BE-IN-01`. Locally constructed clause/Raw/set expression; inspect API identity and bound values.

- `nestjs-public-request-to-sql-text-local` — language `typescript`; **security-observation**; base `BE-IN-01`. Recognized local request/decorators to text/sort; wrappers/allowlists are not established.

- `nestjs-public-sensitive-logger-usage` — language `typescript`; **inventory-candidate**; base `BE-IN-06,AUTH-06`. Logger/method/value naming regex includes literals; distinguish fixed message and actual material, aliases/wrappers and redaction manually.

- `nestjs-public-request-data-to-logger-local` — language `typescript`; **security-observation**; base `BE-IN-06,AUTH-06`. Recognized local request/logger; content sensitivity is not established.

- `nestjs-public-nest-logger-sensitive-argument` — language `typescript`; **inventory-candidate**; base `BE-IN-06,AUTH-06`. Locally constructed/typed Logger shapes and argument text including literals; inspect imports, material, aliases and redaction.

- `nestjs-public-request-to-shell-local` — language `typescript`; **security-observation**; base `BE-IN-02`. Recognized local input to imported command/argv; inspect quoting/mapping.

- `nestjs-public-http-client-usage` — language `typescript`; **inventory-candidate**; base `BE-IN-04`. Recognized fetch/HTTP/axios/HttpService destinations; input trust remains unknown.

- `nestjs-public-request-to-http-local` — language `typescript`; **security-observation**; base `BE-IN-04`. Recognized local input/destination fields; redirects/egress/DNS are not established.

- `nestjs-public-filesystem-path-usage` — language `typescript`; **inventory-candidate**; base `BE-IN-03`. Recognized fs/response paths; inspect source/destination, containment, and symlinks.

- `nestjs-public-request-to-filesystem-local` — language `typescript`; **security-observation**; base `BE-IN-03`. Recognized local request/fs paths; join/normalize is not automatically sanitization.

### fe-public-static.yml

File: [rules/fe-public-static.yml](../rules/fe-public-static.yml); 15 rules. Entries specify language, role, base IDs, and limitations.

- `react-public-dangerously-set-inner-html` — language `typescript`; **inventory-candidate**; base `FE-BR-01`. JSX sink only; neither sanitizer nor untrusted input is established.

- `react-public-direct-dom-html-write` — language `typescript`; **inventory-candidate**; base `FE-BR-01`. HTML assignment/insertion sinks; inspect context and provenance.

- `react-public-dynamic-code-execution` — language `typescript`; **inventory-candidate**; base `FE-BR-02`. eval/Function usage; code provenance and other loaders require review.

- `react-public-document-write` — language `typescript`; **inventory-candidate**; base `FE-BR-01`. document.write only; does not cover every template API.

- `react-public-query-to-location-v2` — language `typescript`; **security-observation**; base `FE-BR-03`. Local query/hash and bound React Router shapes; inspect destination validation.

- `react-public-query-to-window-open-v2` — language `typescript`; **security-observation**; base `FE-BR-03`. Local query/hash to destination; opener access is not established.

- `react-public-window-open-opener-review-v2` — language `typescript`; **inventory-candidate**; base `FE-BR-03`. Options/target regex; review subsequent opener clearing/browser behavior.

- `react-public-client-secret-environment-name` — language `typescript`; **inventory-candidate**; base `FE-BR-05,CFG-06`. Vite env-name heuristic; review public identifiers/actual bundle exposure.

- `react-public-auth-session-browser-storage` — language `typescript`; **inventory-candidate**; base `FE-BR-05`. Local Web Storage receiver and key-name regex; neither credentials nor exploits are established.

- `react-public-auth-object-browser-storage` — language `typescript`; **inventory-candidate**; base `FE-BR-05`. JSON.stringify value-name regex; review storage contents/policy.

- `react-public-untrusted-message-to-dom` — language `typescript`; **security-observation**; base `FE-BR-01`. response.data.message shape; actual provenance/encoding is not established.

- `react-public-url-to-html-local` — language `typescript`; **security-observation**; base `FE-BR-01`. Local query/hash to HTML; inspect context/sanitizer implementation.

- `react-public-message-to-sensitive-sink-local` — language `typescript`; **security-observation**; base `FE-BR-01,FE-BR-02,FE-BR-04`. Inline handler shapes; absence of origin/source/payload checks is not established.

- `react-public-message-to-navigation-local` — language `typescript`; **security-observation**; base `FE-BR-03,FE-BR-04`. Inline message to navigation; named handlers/wrappers may fall outside the matcher.

- `react-public-postmessage-wildcard-target` — language `typescript`; **security-observation**; base `FE-BR-04`. Window-like wildcard shape; Worker/public broadcasts need different interpretation.

### be-auth-static.yml

File: [rules/be-auth-static.yml](../rules/be-auth-static.yml); 17 rules. Entries specify language, role, base IDs, and limitations.

- `nestjs-auth-hardcoded-jwt-secret` — language `typescript`; **security-observation**; base `AUTH-03,AUTH-06,CFG-06`. Direct literal/fallback at secret/secretOrKey; strings inside config getters are not literal secrets. Verify JWT identity/effective configuration.

- `nestjs-auth-jwt-expiration-disabled` — language `typescript`; **security-observation**; base `AUTH-02,AUTH-04`. Direct strategy super ignoreExpiration:true; does not cover full expiry lifecycle.

- `nestjs-auth-jwt-from-query-v2` — language `typescript`; **security-observation**; base `AUTH-06`. Query extractor; review transport consumers/logging.

- `nestjs-auth-jwt-from-body-v2` — language `typescript`; **inventory-candidate**; base `AUTH-06`. Body transport contract, rather than query-string disclosure.

- `nestjs-auth-weak-bcrypt-cost` — language `typescript`; **security-observation**; base `AUTH-01`. Literal cost <10 heuristic, rather than default policy; wrappers/runtime cost may differ.

- `nestjs-auth-plaintext-password-comparison` — language `typescript`; **inventory-candidate**; base `AUTH-01`. Credential-named equality; confirmation/hash representation may explain it.

- `nestjs-auth-plaintext-password-persistence` — language `typescript`; **inventory-candidate**; base `AUTH-01`. Credential-name create/save; field may be hashed and create may not write.

- `nestjs-auth-sensitive-logging` — language `typescript`; **inventory-candidate**; base `AUTH-06,BE-IN-06`. Console/value-name regex; inspect sensitivity/redaction/log configuration.

- `nestjs-auth-client-controlled-jwt-subject` — language `typescript`; **inventory-candidate**; base `AUTH-03,AUTH-05`. dto/body/input naming; inspect authenticated provenance.

- `nestjs-auth-password-field-in-response` — language `typescript`; **inventory-candidate**; base `AUTH-06`. Return field-name candidate with TS path filter; inspect HTTP serialization/callers.

- `nestjs-auth-jwt-verification-without-algorithm-allowlist` — language `typescript`; **inventory-candidate**; base `AUTH-02`. Direct super shape missing algorithms; inspect defaults/overrides/actual API.

- `nestjs-auth-password-min-length-under-eight` — language `generic`; **security-observation**; base `AUTH-01`. Generic regex @MinLength 0..7, within 200 chars before field, TS path; map enrollment/change/reset versus login and shared callers, effective validators and policy.

- `nestjs-auth-unsigned-jwt-algorithm` — language `generic`; **security-observation**; base `AUTH-02,AUTH-03`. Generic none-config regex in TS; inspect actual consumer/purpose.

- `nestjs-auth-request-credential-to-persistence-local` — language `typescript`; **security-observation**; base `AUTH-01`. Recognized local request/hash sanitizers/persistence; inspect wrappers/hooks and algorithm policy.

- `nestjs-auth-decoded-jwt-identity-local` — language `typescript`; **security-observation**; base `AUTH-02,AUTH-05`. Recognized JWT names/decode identity sinks; inspect upstream verification of the same token.

- `nestjs-auth-sensitive-field-to-http-local` — language `typescript`; **security-observation**; base `AUTH-06,BE-IN-06`. Field/response regex and local flow; inspect serializer/actual values.

- `nestjs-auth-sensitive-entity-response-review` — language `typescript`; **inventory-candidate**; base `AUTH-06,BE-IN-06`. Local sensitive-field selection/assignment then return/send; internal return is not automatically HTTP exposure.

### authorization-ownership-static.yml

File: [rules/authorization-ownership-static.yml](../rules/authorization-ownership-static.yml); 12 rules. Entries specify language, role, base IDs, and limitations.

- `nestjs-ownership-client-user-id-to-service` — language `typescript`; **inventory-candidate**; base `AUTHZ-06`. user/owner/principal-field regex; review request origin/principal authority.

- `nestjs-ownership-user-id-field-in-dto` — language `typescript`; **inventory-candidate**; base `AUTHZ-06`. DTO suffix and field regex; input/output/shared/inherited usage requires caller and serializer mapping, not class-name exclusions.

- `nestjs-ownership-id-only-find-one` — language `typescript`; **inventory-candidate**; base `AUTHZ-02`. TypeORM-like ID/key lookup including tested id+owner/id+status shapes with overlap; prior guard still matches, missing match does not prove authorization.

- `nestjs-ownership-unscoped-update-delete` — language `typescript`; **inventory-candidate**; base `AUTHZ-02`. ID criteria shapes; inspect prior checks/transactions/persistence identity.

- `nestjs-ownership-client-user-id-persistence` — language `typescript`; **inventory-candidate**; base `AUTHZ-06`. Ownership-name copy/create; input may be server-trusted and other names fall outside regex.

- `nestjs-ownership-request-body-mass-assignment` — language `typescript`; **inventory-candidate**; base `AUTHZ-06,BE-IN-05`. Body-shaped construction/persistence; inspect DTO/hooks/overwrite order.

- `nestjs-ownership-scalar-mutation-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-02`. Scalar variable name ID/ref/key; Map/Set, service, repository, manager and aliases may match; resolve receiver/write and prior authorization manually.

- `nestjs-ownership-bulk-criteria-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-03`. In/Any/list mutation shapes and identifier regex; each element still needs policy review.

- `nestjs-ownership-request-key-to-criteria-local` — language `typescript`; **inventory-candidate**; base `AUTHZ-02,AUTHZ-03,AUTHZ-04`. Local request key-name regex to criteria; full predicates/principal binding are not established.

- `nestjs-ownership-dto-spread-persistence-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-06,BE-IN-05`. dto/input/body naming taint to method shapes; establish receiver provenance and actual write as well as input trust/allowlist.

- `nestjs-ownership-object-assign-write-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-06,BE-IN-05`. Locally assigned then saved; inspect field allowlist/order/callers.

- `nestjs-ownership-additional-criteria-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-02,AUTHZ-05`. Extra criteria may be status/type or owner; correct authority is not established.

### supply-chain-config-static.yml

File: [rules/supply-chain-config-static.yml](../rules/supply-chain-config-static.yml); 20 rules. Entries specify language, role, base IDs, and limitations.

- `config-docker-latest-tag` — language `generic`; **security-observation**; base `CFG-04`. Generic Dockerfile/YAML latest-image regex; inspect lock/digest/deployment policy.

- `config-docker-root-user` — language `generic`; **security-observation**; base `CFG-02`. Generic exact Dockerfile basename, explicit USER root/0; omitted user/final-stage semantics are not covered.

- `config-docker-remote-shell-install-v2` — language `generic`; **security-observation**; base `CFG-05`. Generic Dockerfile curl/wget piped to sh/bash; inspect provenance/integrity/policy.

- `config-docker-world-writable-permissions-v2` — language `generic`; **security-observation**; base `CFG-02`. Generic Dockerfile chmod 777 regex; inspect resources/effective permissions.

- `config-compose-privileged` — language `generic`; **security-observation**; base `CFG-02`. Generic literal true, four Compose basenames; overlays/runtime remain unknown.

- `config-compose-host-network` — language `generic`; **security-observation**; base `CFG-02,CFG-03`. Generic literal host, four Compose basenames; inspect effective topology.

- `config-compose-docker-socket` — language `yaml`; **security-observation**; base `CFG-02`. YAML service volumes and conventional socket paths; permissions/daemon access remain unknown.

- `config-nginx-server-tokens-on` — language `generic`; **security-observation**; base `CFG-03`. Generic *.conf explicit server_tokens on; inspect includes/effective scope.

- `config-nginx-directory-listing-enabled-v2` — language `generic`; **security-observation**; base `CFG-03`. Generic *.conf explicit autoindex on; inspect location/access restrictions.

- `config-nginx-csp-scope-review-v2` — language `generic`; **inventory-candidate**; base `CFG-03`. Generic server/header/include lines in *.conf; resolve block scope, add_header inheritance/version, includes and runtime consumers manually; no absence claim.

- `config-vite-production-sourcemap` — language `generic`; **security-observation**; base `CFG-05`. Generic vite.config.ts/js literal true; overrides/publication remain unknown.

- `config-package-unpinned-wildcard-dependency` — language `json`; **security-observation**; base `CFG-04`. JSON package.json dependency-field wildcards; inspect lockfile/resolution.

- `config-package-remote-code-dependency` — language `json`; **security-observation**; base `CFG-04`. JSON package.json Git/HTTP dependency fields; inspect immutability/install behavior.

- `config-package-install-lifecycle-script` — language `generic`; **inventory-candidate**; base `CFG-05`. Generic package.json script-key regex; command safety/actual installation are not established.

- `config-node-tls-verification-disabled` — language `typescript`; **security-observation**; base `CFG-03`. Recognized Node/TypeORM/undici config/API/import shapes; inspect effective consumers/environment.

- `config-cookie-secure-disabled` — language `typescript`; **security-observation**; base `CFG-03,AUTH-03`. Recognized response/session explicit false; inspect cookie purpose/overrides; omitted flags are not covered.

- `config-cookie-httponly-disabled` — language `typescript`; **security-observation**; base `CFG-03,AUTH-03`. Recognized response/session explicit false; inspect cookie purpose/overrides.

- `config-cookie-samesite-disabled` — language `typescript`; **security-observation**; base `CFG-03,AUTH-03`. Explicit false/none; inspect cross-site requirements/effective secure context.

- `config-compose-added-capability-review` — language `yaml`; **inventory-candidate**; base `CFG-02`. YAML conventional basenames and capability lists; inspect cap_drop/rootless/seccomp/policy.

- `config-compose-sensitive-host-bind-review` — language `yaml`; **inventory-candidate**; base `CFG-02`. YAML conventional names and root/etc/proc/sys/dev binds; inspect permissions/modes/isolation.

## Machine-readable projection and ID history

[select_rules.py](../scripts/select_rules.py) produces JSON suggestions with repeatable `--base AUTHZ-02`. This catalog is canonical for role/base/manual follow-up; YAML is canonical for languages/paths/options/engine/matchers. The helper reads both directly, without a second catalog or inferred coverage. Null means no declaration, rather than unlimited engine support. Five YAML files do not mandate five scans.

The historical `config-nginx-missing-content-security-policy` was replaced by `config-nginx-csp-scope-review-v2` on 2026-10-26. The new detector inventories server/header/include declarations instead of asserting absence from generic blocks; counts/meaning are not equivalent. Preserve historical IDs/results; retesting with the new ID does not automatically establish a fix. Logger/receiver/DTO/lifecycle changes affected messages/guidance while preserving matchers/native severity/confidence. See [validation](validation.md).
