# authentication-session — Danh tính, credential và session

## Ý định, applicability và discovery

Tìm login/passwordless/SSO, credential stores, token/session issuance/verification, guards/middleware, reset/refresh/revoke/logout và serializers/logs trong scope. Track này không quét toàn bộ protected business code. Không cần token thật để đọc source; feature không tồn tại có thể N/A có căn cứ, thiếu bundled rule thì không.

## AUTH-01 — Credential acquisition/storage/transformation có phù hợp flow không?

- **Áp dụng/discovery:** password registration/login/change hoặc alternative passwordless credential; tìm handlers, hash/compare/imports và persistence hooks.
- **Kỳ vọng/nguồn:** credential không lưu/so sánh plaintext ngoài contract; salt/cost/algorithm theo policy áp dụng và implementation. Passwordless cần đọc nonce/key/assertion flow thay vì ép password policy.
- **Source/kỹ thuật:** bundled persistence/comparison/local taint và threshold candidates; manual input → transformations → storage/verification, wrappers/hooks và callers.
- **Control/giải thích khác:** password confirmation không là verification, field có thể đã hash; kiểm hash implementation/salt/cost thực. Bcrypt <10 và MinLength 0..7 là detector heuristic, không chuẩn bắt buộc mọi product.
- **Evidence/giới hạn:** credential representation/control locations, policy hoặc giả định source, không giá trị thật. Static chưa xác nhận runtime cost, migrations hoặc store content.
- **Khép/bước tiếp:** flow thực được giải thích đủ, threshold chỉ kết luận theo policy đã biết; thiếu policy giữ gap phụ thuộc, tiếp tục review transformation.

## AUTH-02 — Token/identity có được verify trước khi tin không?

- **Áp dụng/discovery:** JWT/SSO/assertions/API tokens; tìm decode/verify/strategy và nơi dùng kết quả làm identity.
- **Kỳ vọng/nguồn:** signature, issuer, audience, algorithm và token purpose theo issuer/consumer contract; decode chỉ parse.
- **Source/kỹ thuật:** bundled decoded-identity/algorithm/expiration candidates; search actual verifier/import/config, manual caller path token → verify → claims → trusted principal.
- **Control/giải thích khác:** verify cùng token có thể ở guard trước decode; tên `verified`, `user`, `jwtService` không đủ. Đọc defaults, key resolution và bypass/error paths.
- **Evidence/giới hạn:** source/config/principal binding và control locations, expectation source; native match không chứng minh verifier toàn hệ thống vắng, không xác nhận token validity runtime.
- **Khép/bước tiếp:** identity sink và verification/binding đúng path có căn cứ; đọc upstream guard/caller hoặc ghi thiếu provider config/source.

## AUTH-03 — Session/token issuance và cookie configuration có đúng contract không?

- **Áp dụng/discovery:** sign/signAsync, session create, Set-Cookie/response, defaults/env overrides và subject assignment.
- **Kỳ vọng/nguồn:** authenticated subject, token lifetime/purpose và cookie Secure/HttpOnly/SameSite theo session/cross-site/HTTPS policy.
- **Source/kỹ thuật:** bundled hardcoded secret/subject cùng config cookie rules; manual principal → claims → issuance, config precedence và consumers.
- **Control/giải thích khác:** literals có thể demo/non-JWT, fallback không reachable, body ID có thể đã bound server-side; cookie dùng preference có kỳ vọng khác session. Thiếu flag khác explicit false.
- **Evidence/giới hạn:** issuance/options/config/control locations đã lọc, runtime env/proxy override chưa biết ghi rõ; không kiểm secret validity.
- **Khép/bước tiếp:** issuance và effective source config đã đối chiếu; runtime override thiếu không ngăn mô tả static fact, giữ giới hạn tương ứng.

## AUTH-04 — Reset/refresh/revoke/logout/expiry có bảo vệ lifecycle state không?

- **Áp dụng/discovery:** chỉ features có trong scope: reset links/codes, refresh rotation, revocation stores, logout và expiry checks.
- **Kỳ vọng/nguồn:** one-time use, binding, invalidation/rotation/expiry theo feature/session policy; không áp một flow cho mọi hệ thống.
- **Source/kỹ thuật:** search handlers, token stores, transactions, TTL/clock comparisons và client consumers; manual call paths/state transitions. Bundled expiration chỉ một phần nhỏ, không cover lifecycle đầy đủ.
- **Control/giải thích khác:** stateless logout có semantics khác revoke; upstream provider hoặc store layer có thể enforce. Đọc error/reuse paths và transaction order, không chỉ tên `revoke`.
- **Evidence/giới hạn:** locations state/check/write, policy và assumptions; code không chứng minh thời gian thực, concurrency hoặc provider behavior chưa cung cấp.
- **Khép/bước tiếp:** giải thích state/invalidation cho feature được giao ở mức static; tìm provider/config thiếu hoặc ghi blocker cụ thể, không tự gửi traffic.

## AUTH-05 — Guards/middleware có bypass hoặc mất principal binding không?

- **Áp dụng/discovery:** protected surfaces, global/local guard, decorators/exemptions, middleware order và principal propagation.
- **Kỳ vọng/nguồn:** chỉ exception paths theo routing/auth contract được bỏ identity checks; trusted principal có provenance và binding đúng request.
- **Source/kỹ thuật:** search bootstrap/module config, registration/decorators và services; manual global → local → handler/caller path, verify thực cùng token. Bundled decoded-identity/subject chỉ hỗ trợ từng hình dạng.
- **Control/giải thích khác:** inherited/global guards, reverse provider trust được cung cấp và service checks; decorator có tên public không tự là bypass, tên `user` không tự trusted.
- **Evidence/giới hạn:** registration/order/exemption/principal-use locations; source thiếu một layer chưa chứng minh bypass runtime.
- **Khép/bước tiếp:** paths thuộc scope có binding/control đủ đọc; tìm missing registration/callers, giữ open phần không xác định được.

## AUTH-06 — Credential/session material có rò qua response/log/config không?

- **Áp dụng/discovery:** credential fields, token transport/query/body, entity responses, logging/config declarations.
- **Kỳ vọng/nguồn:** disclosure/transport/redaction theo data/session policy và consumer contract, không suy mọi token là secret.
- **Source/kỹ thuật:** bundled logging/HTTP/entity/query extraction/hardcoded config candidates; manual actual values, serializer, callers, redaction và config precedence.
- **Control/giải thích khác:** internal return, hashed/public values, effective serializer, test placeholders hoặc disabled sink; đọc implementation trước false-positive.
- **Evidence/giới hạn:** locations và loại material đã lọc, không secret values hoặc raw headers. Static chưa xác nhận logs/HTTP runtime hoặc credential còn dùng được.
- **Khép/bước tiếp:** claim exposure phù hợp đường đã đọc và controls; source/serialization chưa rõ thì needs-review có gaps và đọc tiếp khi khả thi.

## Mẫu credential/token lifecycle

Chọn các đoạn có feature thật: `acquisition/enrollment → transform/store → compare/verify → issue → principal propagation → expiry/logout/revoke`. Mỗi đoạn ghi `{feature, input_provenance, implementation_locations, config_consumer, control, output_consumer, question_id, limitations}` trong result/review; đoạn không có ghi discovery fact thay vì dựng flow.

Tách enrollment/change/reset policy khỏi credential input tại login và bcrypt config. `MinLength` ở login không chứng minh enrollment yếu; shared DTO cần caller/validator mapping, không exempt theo tên LoginDto. Đọc validators effective và trường có thật là credential; không đổi ngưỡng heuristic thành policy. Client cleanup chỉ là client cleanup, chưa là server revocation. Docs mô tả guard/strategy không thay đọc implementation, registration và caller; dùng mẫu mâu thuẫn tài liệu–source ở tester context khi cần.

Return credential-named object cần phân loại internal config/factory, controller response hoặc helper qua callers và serializer. Broad detector vẫn là inventory; ưu tiên review controller/HTTP caller đã nhận diện từ source, không loại config/factory theo path hoặc cho false-positive tự động.

## Mapping, thích nghi và khép track

[Catalog](../rule-catalog.md): `be-auth-static.yml` chủ yếu TS/Nest/Passport/JWT/bcrypt, generic regex cho một số syntax TS; cookie config ở configuration file. AUTH-04/05 phần lớn manual-review/custom-rule-needed; không có password flow có thể N/A AUTH-01 phần password sau discovery, không loại cả track.

Ví dụ strategy decode token rồi gán principal: đọc global guard xem verify cùng token và issuer/audience trước; match vẫn cần triage, không tin `decoded.userId`. Khép theo câu hỏi/flow đã giao, phân biệt source hypothesis với policy xác nhận.
