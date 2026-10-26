# configuration-build — Cấu hình, build và dependency declarations

## Ý định, applicability và discovery

Inventory file thực và consumers: manifests, env templates/defaults, overlays, process/container, network/server/browser config, dependency/lockfiles, build/install/CI. Đọc scripts/imports/commands để tìm tên config khác chuẩn, gồm compose override và Dockerfile biến thể. Không yêu cầu Docker nếu product không dùng, không sửa file product để lọt filter. Pattern declarations không là SCA/CVE hoặc secret validity scan.

## CFG-01 — Effective config có thứ tự/default/override nào ảnh hưởng bảo mật?

- **Áp dụng/discovery:** có config/default/env/overlay; tìm loaders, merge order, process args và deployment declarations được cung cấp.
- **Kỳ vọng/nguồn:** effective values phù hợp environment/feature contract, không lấy mẫu development làm production policy.
- **Source/kỹ thuật:** search file references/loaders và manual precedence, interpolation/fallbacks; bundled config patterns hỗ trợ vài consumers, chưa cover precedence toàn hệ thống.
- **Control/giải thích khác:** env override, file không dùng, build-time/runtime injection, inherited config; tên file production chưa chứng minh deployment dùng.
- **Evidence/giới hạn:** config/consumer/precedence locations và nguồn environment, chưa có runtime config thì nói rõ.
- **Khép/bước tiếp:** mô tả effective source config ở mức được cung cấp; tìm overlays/consumers thiếu, giữ assumption/limitation cho runtime chưa biết.

## CFG-02 — Container/process privileges, mounts/capabilities/file permissions có phù hợp không?

- **Áp dụng/discovery:** có container/process declarations; tìm user/group, privileges, caps, host mounts/socket và chmod; không ép Docker tồn tại.
- **Kỳ vọng/nguồn:** quyền cần cho service theo deployment/isolation policy và tài nguyên được bảo vệ, không áp một profile cố định mọi product.
- **Source/kỹ thuật:** bundled Docker/Compose candidates khi path phù hợp; search manifests/tên khác, custom local config/rule có mapping hoặc manual mount/user/cap review.
- **Control/giải thích khác:** multi-stage final user, rootless/user namespaces, cap_drop/seccomp, read/write mode, socket API access; `:ro` chưa làm Docker socket API read-only.
- **Evidence/giới hạn:** declaration/consumer/overlay locations và controls, không suy root/privileged pattern là host compromise runtime.
- **Khép/bước tiếp:** privilege paths được đối chiếu với policy/source context; filename skip giữ gap và review tiếp, không gọi negative semantic pass.

## CFG-03 — Network/TLS/browser/server security config có đúng context không?

- **Áp dụng/discovery:** TLS clients/servers, proxy/nginx, CORS/CSP/cookies và overrides thuộc scope.
- **Kỳ vọng/nguồn:** transport/origin/content/session requirements theo integration/security policy; cookie purpose và cross-site needs có ý nghĩa.
- **Source/kỹ thuật:** bundled TLS/cookie/nginx cùng CORS candidate ở BE file, search actual loaders/options; manual inheritance, effective options và consumers.
- **Control/giải thích khác:** CSP/header ở app/proxy layer khác, environment-only config, public CORS endpoint, cookie không nhạy cảm; omitted flags khác explicit permissive values.
- **Evidence/giới hạn:** source/config/control và precedence locations, runtime headers/TLS chưa được quan sát, generic nginx pattern không hiểu toàn inheritance.
- **Khép/bước tiếp:** claim đúng layer đã đọc và policy áp dụng; tìm shared proxy/app config hoặc giữ gaps runtime có ảnh hưởng.

## CFG-04 — Dependency declarations/lockfiles/nguồn tải có rủi ro nào trong scope?

- **Áp dụng/discovery:** manifest/lockfiles/package sources thực, cả ecosystem ngoài npm; tìm overrides/workspaces/install resolution.
- **Kỳ vọng/nguồn:** reproducible/trusted sourcing theo dependency/build policy; pinned manifest chưa chứng minh dependency an toàn.
- **Source/kỹ thuật:** bundled npm wildcard/remote dependency candidates, search manifests/lockfiles và manual immutability/resolution/integrity declarations.
- **Control/giải thích khác:** lockfile pin, internal mirrors, immutable Git revisions, dev/runtime context và alternate overrides cần đọc, không lấy metadata URL làm dependency.
- **Evidence/giới hạn:** declaration/lock/source locations và config, không suy CVE, graph reachability hay SCA từ pattern.
- **Khép/bước tiếp:** trả lời source/pinning ở mức được giao; ecosystem khác tìm local/custom/manual, yêu cầu CVE riêng giữ capability thiếu rõ ràng.

## CFG-05 — Build/install/CI execution và artifact exposure có boundary nào?

- **Áp dụng/discovery:** lifecycle scripts, remote shell install, CI commands, build inputs, artifact publishing/source maps khi liên quan.
- **Kỳ vọng/nguồn:** trust của code thực thi và artifact visibility theo build/release policy, không chạy script chỉ để đọc.
- **Source/kỹ thuật:** bundled remote-shell/lifecycle/Vite sourcemap candidates, search workflow/script refs, manual command construction, provenance và upload/artifact declarations.
- **Control/giải thích khác:** reviewed pinned download, integrity checks, private artifacts, maps không published, unused config; đọc downstream CI consumer/override.
- **Evidence/giới hạn:** script/config/artifact/control locations; source-map enabled chưa chứng minh public disclosure, không execute install/build hoặc upload.
- **Khép/bước tiếp:** execution/artifact path được đối chiếu đủ claim; tìm referenced script/publish config hoặc ghi source/capability thiếu.

## CFG-06 — Sensitive config/credential declarations có exposure/fallback ngoài ý định không?

- **Áp dụng/discovery:** credential/keys trong env templates/config/defaults/CI references; tìm actual consumers, bundle/export và logging.
- **Kỳ vọng/nguồn:** secret sourcing/retention/exposure theo config/data policy; không coi mọi giá trị literal hoặc secret-named field là credential thật.
- **Source/kỹ thuật:** search cấu trúc và consumers, bundled hardcoded JWT/Vite patterns khi phù hợp; manual fallback/precedence, public/private use và redaction.
- **Control/giải thích khác:** synthetic placeholders, public key/client identifier, unreachable default, runtime injection; không thử credential validity.
- **Evidence/giới hạn:** vị trí/loại/consumer đã lọc, tuyệt đối không giá trị thật; static detection không là Secrets validity check.
- **Khép/bước tiếp:** exposure/fallback claim có context/control đủ đọc, phần thiếu runtime/policy ghi riêng; tiếp tục review không phụ thuộc secret value.

## Mẫu file → consumer → precedence → layer

Trong result/review ghi `{file, consumer_load_path, defaults_overrides, precedence, final_stage_or_inherited_setting, layer, missing_source, locations, question_id, next_step}`. `layer` nêu declaration/source hay runtime evidence thực có; source-only không tự kết luận effective runtime absence. Inventory cả env templates và lockfiles dù detector không nhận path/language; không gọi dependency declaration là CVE/SCA.

- nginx: đọc đúng server/location, include và header scope. Parent có CSP chưa chứng minh child inherited nếu child có add_header riêng; ghi add_header_inherit/config/version nếu source cung cấp. CSP ở server khác không bảo vệ server đang xét. Include source thiếu giữ gap, `always` không tự trả lời mọi response/runtime context.
- Compose: từ command/CI consumer tìm files/overrides/profiles thực, merge/env sources theo source có sẵn; basename production không chứng minh được deploy.
- FE: phân biệt build-time env được bundle với runtime injection, tìm consumer/publish stage; env template không tự là giá trị production.
- Docker/locks: final stage và inherited USER/config khác stage build; package/lock declarations cho resolution intent, không xác nhận runtime installation. Research/development defaults không bị chấm bằng production policy chưa được giao.

## Mapping, thích nghi và khép track

[Catalog](../rule-catalog.md): `supply-chain-config-static.yml`, Docker/Compose/nginx/npm/Vite/Node shapes, bundled-partial CFG-02…05. CFG-01/06 phần lớn manual-review/custom-rule-needed, có rules liên quan ở BE/AUTH/FE. Compose chỉ bốn basename chuẩn, Docker/Vite/nginx/npm cũng có path/shape limits. Discovery file khác tên cần review hoặc rule/config local riêng, giữ mapping nguồn và không gọi file skip là safe.

Ví dụ CI nạp `compose.prod.yaml`: discovery giữ file đó trong inventory; nếu rule chỉ include `compose.yaml` thì ghi filter limitation, đọc `privileged`/overrides hoặc tạo rule local phù hợp. Khép theo config/questions đã giao; không mở SCA/CVE hoặc runtime provisioning.
