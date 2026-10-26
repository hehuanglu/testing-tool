# Catalog bundled rules và giới hạn capability

Mỗi entry dưới map rule thật tới base; không là danh sách vulnerabilities. `inventory-candidate` dùng tìm source/control cần đọc; chỉ tạo security observation khi đã mô tả nghi vấn. `security-observation` cũng chưa là supported issue trước triage. Một rule phục vụ nhiều base không nhân counts.

| File | Track nghiệp vụ chính | Stack | Chưa được bundled bao phủ đầy đủ |
|---|---|---|---|
| [be-public-static.yml](../rules/be-public-static.yml) | be-input | TS/Nest/Node/TypeORM | templates/archive/deserialization tùy stack, wrappers/xuyên file |
| [fe-public-static.yml](../rules/fe-public-static.yml) | fe-browser | TS/React/browser/Vite | Vue/Angular, named handlers/wrappers, UI–server permission boundary |
| [be-auth-static.yml](../rules/be-auth-static.yml) | authentication-session | TS/Nest/Passport/JWT/bcrypt + generic | passwordless/SSO, lifecycle/state, global guards đa dạng |
| [authorization-ownership-static.yml](../rules/authorization-ownership-static.yml) | authorization-ownership | TS/Nest/TypeORM shapes | function permissions, arbitrary persistence/names, relation/lifecycle policies |
| [supply-chain-config-static.yml](../rules/supply-chain-config-static.yml) | configuration-build | Docker/Compose/nginx/npm/Vite/Node | precedence, custom filenames, ecosystems khác, CI/credentials đa dạng |

## Cách đọc coverage

- `bundled-partial`: có detector gợi ý cho base, vẫn phải discovery/triage/manual phần thiếu. BE-IN-01…06, FE-BR-01…05, AUTH-01…03/06, AUTHZ-02/03/06, CFG-02…05 nằm nhóm này khi stack/shape phù hợp.
- `manual-review`: điểm khởi đầu cho FE-BR-06, AUTH-04/05, AUTHZ-01/04/05, CFG-01/06. Một số rules dưới hỗ trợ từng phần nhưng không khép base.
- `custom-rule-needed`: khi cần Semgrep nhận abstraction/language/path chưa bundled hỗ trợ; tìm repo/local rules rồi rule nhỏ có fixtures nếu hữu ích. Manual review vẫn làm phần khả thi. Không có bundled coverage không là N/A.

Ownership regex theo tên field không bao phủ mọi tên nghiệp vụ; TypeORM patterns không đại diện mọi persistence API/wrapper. Compose có bốn basenames chuẩn, Dockerfile/Vite/nginx/npm filters cũng hẹp; discovery phải tìm file/override khác và giữ mapping khi review/custom config. Numeric thresholds là heuristic cần policy, native WARNING/ERROR không tự policy violation. Generic regex không có semantics như structured language/taint rule; local CE flow không chứng minh xuyên hàm/file. Không dùng bộ TS để báo Python/Java/Go sạch. Configuration-build không tra CVE/SCA/secret validity.

## Từng rule

### be-public-static.yml

File: [rules/be-public-static.yml](../rules/be-public-static.yml); 21 rules. Mỗi entry ghi language, vai trò, base IDs và giới hạn.

- `nestjs-public-dangerous-eval` — language `typescript`; **security-observation**; base `BE-IN-02`. Eval/Function usage; input trust/actual execution cần review.

- `nestjs-public-child-process-shell` — language `typescript`; **inventory-candidate**; base `BE-IN-02`. Recognized imports/methods và literal shell:true; wrappers/options khác cần đọc.

- `nestjs-public-raw-query-string-construction` — language `typescript`; **security-observation**; base `BE-IN-01`. Local construction tới SQL text; không chứng minh external input.

- `nestjs-public-request-body-mass-assignment` — language `typescript`; **inventory-candidate**; base `BE-IN-05,AUTHZ-06`. Body-shaped APIs; create/merge chưa chắc write, DTO/callers cần đọc.

- `nestjs-public-sensitive-console-output` — language `typescript`; **inventory-candidate**; base `BE-IN-06,AUTH-06`. Regex tên expression, không hiểu sensitive value/redaction.

- `nestjs-public-cors-wildcard` — language `typescript`; **security-observation**; base `CFG-03`. Nest enableCors shapes; credentials/endpoint purpose/effective overrides cần đọc.

- `nestjs-public-validation-pipe-without-whitelist` — language `typescript`; **inventory-candidate**; base `BE-IN-05`. Direct pipe options only; runtime validation có thể ở layer khác.

- `nestjs-public-validation-pipe-allows-unknown-fields` — language `typescript`; **inventory-candidate**; base `BE-IN-05`. Không thấy literal forbidNonWhitelisted:true; strip/allow policy chưa xác định.

- `nestjs-public-internal-exception-disclosure` — language `typescript`; **security-observation**; base `BE-IN-06`. Exception-name regex và response-shaped API; serializer/actual content cần đọc.

- `nestjs-public-swagger-without-environment-guard` — language `typescript`; **inventory-candidate**; base `CFG-01,CFG-03`. Một số direct guards được nhận; enclosing conditions/proxy access chưa hiểu đầy đủ.

- `nestjs-public-exception-stack-in-http-error` — language `typescript`; **security-observation**; base `BE-IN-06`. Stack trong exception construction; error envelope/runtime còn cần đọc.

- `nestjs-public-querybuilder-dynamic-sql-local` — language `typescript`; **security-observation**; base `BE-IN-01`. Local constructed clause/Raw/set expression; API identity và bound values cần đọc.

- `nestjs-public-request-to-sql-text-local` — language `typescript`; **security-observation**; base `BE-IN-01`. Recognized request/decorators local tới text/sort; wrappers/allowlist không được chứng minh.

- `nestjs-public-sensitive-logger-usage` — language `typescript`; **inventory-candidate**; base `BE-IN-06,AUTH-06`. Logger/method/value naming regex includes literals; distinguish fixed message and actual material, aliases/wrappers and redaction manually.

- `nestjs-public-request-data-to-logger-local` — language `typescript`; **security-observation**; base `BE-IN-06,AUTH-06`. Local recognized request/logger; content sensitivity chưa chứng minh.

- `nestjs-public-nest-logger-sensitive-argument` — language `typescript`; **inventory-candidate**; base `BE-IN-06,AUTH-06`. Locally constructed/typed Logger shapes and argument text including literals; inspect imports, material, aliases and redaction.

- `nestjs-public-request-to-shell-local` — language `typescript`; **security-observation**; base `BE-IN-02`. Local recognized input tới imported command/argv slot; quoting/mapping cần đọc.

- `nestjs-public-http-client-usage` — language `typescript`; **inventory-candidate**; base `BE-IN-04`. Recognized fetch/HTTP/axios/HttpService destinations; không xác định input trust.

- `nestjs-public-request-to-http-local` — language `typescript`; **security-observation**; base `BE-IN-04`. Local recognized input/destination fields; redirects/egress/DNS chưa được chứng minh.

- `nestjs-public-filesystem-path-usage` — language `typescript`; **inventory-candidate**; base `BE-IN-03`. Recognized fs/response paths; source/destination, containment/symlinks cần đọc.

- `nestjs-public-request-to-filesystem-local` — language `typescript`; **security-observation**; base `BE-IN-03`. Local recognized request/fs path; join/normalize không tự sanitizer.

### fe-public-static.yml

File: [rules/fe-public-static.yml](../rules/fe-public-static.yml); 15 rules. Mỗi entry ghi language, vai trò, base IDs và giới hạn.

- `react-public-dangerously-set-inner-html` — language `typescript`; **inventory-candidate**; base `FE-BR-01`. JSX sink only; không nhận sanitizer hay chứng minh untrusted input.

- `react-public-direct-dom-html-write` — language `typescript`; **inventory-candidate**; base `FE-BR-01`. HTML assignment/insertion sinks; context và provenance cần đọc.

- `react-public-dynamic-code-execution` — language `typescript`; **inventory-candidate**; base `FE-BR-02`. eval/Function usage; chưa hiểu code provenance hoặc script loaders khác.

- `react-public-document-write` — language `typescript`; **inventory-candidate**; base `FE-BR-01`. document.write only; không cover mọi template API.

- `react-public-query-to-location-v2` — language `typescript`; **security-observation**; base `FE-BR-03`. Local query/hash và bound React Router shapes; destination validation cần đọc.

- `react-public-query-to-window-open-v2` — language `typescript`; **security-observation**; base `FE-BR-03`. Local query/hash tới destination; không chứng minh opener access.

- `react-public-window-open-opener-review-v2` — language `typescript`; **inventory-candidate**; base `FE-BR-03`. Options/target regex; subsequent opener clearing/browser behavior cần review.

- `react-public-client-secret-environment-name` — language `typescript`; **inventory-candidate**; base `FE-BR-05,CFG-06`. Vite env-name heuristic; public identifiers/actual bundle exposure cần review.

- `react-public-auth-session-browser-storage` — language `typescript`; **inventory-candidate**; base `FE-BR-05`. Local Web Storage receiver và key-name regex; không chứng minh credential hay exploit.

- `react-public-auth-object-browser-storage` — language `typescript`; **inventory-candidate**; base `FE-BR-05`. JSON.stringify value-name regex; storage contents/policy cần review.

- `react-public-untrusted-message-to-dom` — language `typescript`; **security-observation**; base `FE-BR-01`. response.data.message shape; actual provenance/encoding chưa chứng minh.

- `react-public-url-to-html-local` — language `typescript`; **security-observation**; base `FE-BR-01`. Local query/hash tới HTML; context/sanitizer implementation cần đọc.

- `react-public-message-to-sensitive-sink-local` — language `typescript`; **security-observation**; base `FE-BR-01,FE-BR-02,FE-BR-04`. Inline handler shapes; origin/source/payload checks không được xác nhận vắng.

- `react-public-message-to-navigation-local` — language `typescript`; **security-observation**; base `FE-BR-03,FE-BR-04`. Inline message tới navigation; named handlers/wrappers có thể ngoài matcher.

- `react-public-postmessage-wildcard-target` — language `typescript`; **security-observation**; base `FE-BR-04`. Window-like wildcard shape; Worker/public broadcast cần interpretation khác.

### be-auth-static.yml

File: [rules/be-auth-static.yml](../rules/be-auth-static.yml); 17 rules. Mỗi entry ghi language, vai trò, base IDs và giới hạn.

- `nestjs-auth-hardcoded-jwt-secret` — language `typescript`; **security-observation**; base `AUTH-03,AUTH-06,CFG-06`. Direct literal/literal fallback tại secret/secretOrKey; chuỗi bên trong config getter không phải literal value. JWT identity/effective config chưa chắc.

- `nestjs-auth-jwt-expiration-disabled` — language `typescript`; **security-observation**; base `AUTH-02,AUTH-04`. Direct strategy super ignoreExpiration:true; không cover full expiry lifecycle.

- `nestjs-auth-jwt-from-query-v2` — language `typescript`; **security-observation**; base `AUTH-06`. Extractor query use; transport consumers/logging cần review.

- `nestjs-auth-jwt-from-body-v2` — language `typescript`; **inventory-candidate**; base `AUTH-06`. Body transport contract, không phải query-string disclosure.

- `nestjs-auth-weak-bcrypt-cost` — language `typescript`; **security-observation**; base `AUTH-01`. Literal cost <10 heuristic, không policy mặc định; wrappers/runtime cost có thể khác.

- `nestjs-auth-plaintext-password-comparison` — language `typescript`; **inventory-candidate**; base `AUTH-01`. Credential-named equality; confirmation/hash representation có thể hợp lệ.

- `nestjs-auth-plaintext-password-persistence` — language `typescript`; **inventory-candidate**; base `AUTH-01`. Credential-name create/save; field có thể hash, create chưa write.

- `nestjs-auth-sensitive-logging` — language `typescript`; **inventory-candidate**; base `AUTH-06,BE-IN-06`. Console/value name regex; sensitivity/redaction/log configuration chưa hiểu.

- `nestjs-auth-client-controlled-jwt-subject` — language `typescript`; **inventory-candidate**; base `AUTH-03,AUTH-05`. dto/body/input naming; authenticated provenance cần đọc.

- `nestjs-auth-password-field-in-response` — language `typescript`; **inventory-candidate**; base `AUTH-06`. Return field-name candidate, TS path filter; HTTP serialization/callers cần đọc.

- `nestjs-auth-jwt-verification-without-algorithm-allowlist` — language `typescript`; **inventory-candidate**; base `AUTH-02`. Direct super shape missing algorithms; defaults/overrides/actual API cần đọc.

- `nestjs-auth-password-min-length-under-eight` — language `generic`; **security-observation**; base `AUTH-01`. Generic regex @MinLength 0..7, within 200 chars before field, TS path; map enrollment/change/reset versus login and shared callers, effective validators and policy.

- `nestjs-auth-unsigned-jwt-algorithm` — language `generic`; **security-observation**; base `AUTH-02,AUTH-03`. Generic regex none config shape in TS; actual consumer/purpose cần đọc.

- `nestjs-auth-request-credential-to-persistence-local` — language `typescript`; **security-observation**; base `AUTH-01`. Local recognized request/hash sanitizers/persistence; wrappers/hooks và algorithm policy cần đọc.

- `nestjs-auth-decoded-jwt-identity-local` — language `typescript`; **security-observation**; base `AUTH-02,AUTH-05`. Recognized JWT names/decode identity sinks; verification cùng token upstream cần đọc.

- `nestjs-auth-sensitive-field-to-http-local` — language `typescript`; **security-observation**; base `AUTH-06,BE-IN-06`. Field/response regex và local flow; serializer/actual values cần đọc.

- `nestjs-auth-sensitive-entity-response-review` — language `typescript`; **inventory-candidate**; base `AUTH-06,BE-IN-06`. Select/assignment sensitive field then return/send locally; internal return chưa HTTP exposure.

### authorization-ownership-static.yml

File: [rules/authorization-ownership-static.yml](../rules/authorization-ownership-static.yml); 12 rules. Mỗi entry ghi language, vai trò, base IDs và giới hạn.

- `nestjs-ownership-client-user-id-to-service` — language `typescript`; **inventory-candidate**; base `AUTHZ-06`. user/owner/principal field regex; request origin/principal authority cần review.

- `nestjs-ownership-user-id-field-in-dto` — language `typescript`; **inventory-candidate**; base `AUTHZ-06`. DTO suffix và field regex; input/output/shared/inherited usage requires caller and serializer mapping, not class-name exclusions.

- `nestjs-ownership-id-only-find-one` — language `typescript`; **inventory-candidate**; base `AUTHZ-02`. TypeORM-like ID/key lookup including tested id+owner/id+status shapes with overlap; prior guard still matches, missing match does not prove authorization.

- `nestjs-ownership-unscoped-update-delete` — language `typescript`; **inventory-candidate**; base `AUTHZ-02`. ID criteria shapes; prior checks/transaction/persistence identity cần đọc.

- `nestjs-ownership-client-user-id-persistence` — language `typescript`; **inventory-candidate**; base `AUTHZ-06`. Ownership-name copy/create; INPUT có thể server-trusted, tên khác ngoài regex.

- `nestjs-ownership-request-body-mass-assignment` — language `typescript`; **inventory-candidate**; base `AUTHZ-06,BE-IN-05`. Body-shaped construction/persistence; DTO/hook/overwrite order cần đọc.

- `nestjs-ownership-scalar-mutation-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-02`. Scalar variable name ID/ref/key; Map/Set, service, repository, manager and aliases may match; resolve receiver/write and prior authorization manually.

- `nestjs-ownership-bulk-criteria-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-03`. In/Any/list mutation shapes và identifier regex; từng element vẫn cần policy.

- `nestjs-ownership-request-key-to-criteria-local` — language `typescript`; **inventory-candidate**; base `AUTHZ-02,AUTHZ-03,AUTHZ-04`. Local request key-name regex tới criteria; không xác nhận full predicates/principal binding.

- `nestjs-ownership-dto-spread-persistence-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-06,BE-IN-05`. dto/input/body naming taint to method shapes; establish receiver provenance and actual write as well as input trust/allowlist.

- `nestjs-ownership-object-assign-write-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-06,BE-IN-05`. Locally assigned then saved; field allowlist/order/callers cần đọc.

- `nestjs-ownership-additional-criteria-review` — language `typescript`; **inventory-candidate**; base `AUTHZ-02,AUTHZ-05`. Extra criteria có thể status/type hoặc owner; không chứng minh authority đúng.

### supply-chain-config-static.yml

File: [rules/supply-chain-config-static.yml](../rules/supply-chain-config-static.yml); 20 rules. Mỗi entry ghi language, vai trò, base IDs và giới hạn.

- `config-docker-latest-tag` — language `generic`; **security-observation**; base `CFG-04`. Generic Dockerfile/YAML image latest regex; lock/digest/deployment policy cần đọc.

- `config-docker-root-user` — language `generic`; **security-observation**; base `CFG-02`. Generic exact Dockerfile basename, explicit USER root/0; không phát hiện omitted user/final-stage semantics.

- `config-docker-remote-shell-install-v2` — language `generic`; **security-observation**; base `CFG-05`. Generic Dockerfile curl/wget pipe sh/bash; provenance/integrity/policy cần đọc.

- `config-docker-world-writable-permissions-v2` — language `generic`; **security-observation**; base `CFG-02`. Generic Dockerfile chmod 777 regex; resource/effective permissions cần đọc.

- `config-compose-privileged` — language `generic`; **security-observation**; base `CFG-02`. Generic literal true, bốn Compose basenames; overlays/runtime chưa xác định.

- `config-compose-host-network` — language `generic`; **security-observation**; base `CFG-02,CFG-03`. Generic literal host, bốn Compose basenames; effective topology cần đọc.

- `config-compose-docker-socket` — language `yaml`; **security-observation**; base `CFG-02`. YAML service volume và conventional socket paths; permissions/daemon access chưa biết.

- `config-nginx-server-tokens-on` — language `generic`; **security-observation**; base `CFG-03`. Generic *.conf explicit server_tokens on; includes/effective scope cần đọc.

- `config-nginx-directory-listing-enabled-v2` — language `generic`; **security-observation**; base `CFG-03`. Generic *.conf explicit autoindex on; location/access restrictions cần đọc.

- `config-nginx-csp-scope-review-v2` — language `generic`; **inventory-candidate**; base `CFG-03`. Generic server/header/include lines in *.conf; resolve block scope, add_header inheritance/version, includes and runtime consumers manually; no absence claim.

- `config-vite-production-sourcemap` — language `generic`; **security-observation**; base `CFG-05`. Generic vite.config.ts/js literal true; overrides/publication chưa biết.

- `config-package-unpinned-wildcard-dependency` — language `json`; **security-observation**; base `CFG-04`. JSON package.json dependency fields wildcard only; lockfile/resolution cần đọc.

- `config-package-remote-code-dependency` — language `json`; **security-observation**; base `CFG-04`. JSON package.json Git/HTTP dependency fields; immutability/install behavior cần đọc.

- `config-package-install-lifecycle-script` — language `generic`; **inventory-candidate**; base `CFG-05`. Generic package.json script-key regex; không hiểu command safety hay actual install.

- `config-node-tls-verification-disabled` — language `typescript`; **security-observation**; base `CFG-03`. Recognized Node/TypeORM/undici config/API/import shapes; effective consumers/env cần đọc.

- `config-cookie-secure-disabled` — language `typescript`; **security-observation**; base `CFG-03,AUTH-03`. Recognized response/session explicit false; cookie purpose/override, không nhận omitted flag.

- `config-cookie-httponly-disabled` — language `typescript`; **security-observation**; base `CFG-03,AUTH-03`. Recognized response/session explicit false; cookie purpose/override cần đọc.

- `config-cookie-samesite-disabled` — language `typescript`; **security-observation**; base `CFG-03,AUTH-03`. Explicit false/none; cross-site needs và effective secure context cần đọc.

- `config-compose-added-capability-review` — language `yaml`; **inventory-candidate**; base `CFG-02`. YAML conventional basenames và capability list; cap_drop/rootless/seccomp/policy cần đọc.

- `config-compose-sensitive-host-bind-review` — language `yaml`; **inventory-candidate**; base `CFG-02`. YAML conventional names, root/etc/proc/sys/dev bind paths; permissions/mode/isolation cần đọc.

## Projection machine-readable và lịch sử ID

[select_rules.py](../scripts/select_rules.py) xuất JSON gợi ý theo `--base AUTHZ-02` (có thể lặp). Catalog này là canonical cho role/base/manual follow-up; YAML là canonical cho language/path/options/engine và matcher. Helper đọc trực tiếp hai nguồn, không giữ catalog thứ hai hoặc tự kết luận coverage. Path/language/options fragments giữ nguyên để operator đọc; null nghĩa không có declaration đó, không hứa engine không có giới hạn. Không mặc định năm YAML là năm scans.

`config-nginx-missing-content-security-policy` là ID lịch sử, được thay bằng `config-nginx-csp-scope-review-v2` trong lượt cải thiện 2026-10-26. ID mới inventory server/header/include declarations thay vì negative generic block matcher; match counts và ý nghĩa không tương đương. Giữ kết quả/rule ID cũ trong assessment lịch sử, retest bằng ID mới không tự là fixed. Các rules logger/receiver/DTO/lifecycle chỉ đổi message/guidance, giữ matcher và native severity/confidence. Xem fixtures và giới hạn trong [validation](validation.md).
