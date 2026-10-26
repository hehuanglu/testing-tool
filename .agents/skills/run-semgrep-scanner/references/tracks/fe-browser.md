# fe-browser — Frontend và browser trust boundaries

## Ý định, applicability và discovery

Kiểm browser source thuộc scope: router/views, URL/API/storage/user content, render/template APIs, script loaders, navigation và messaging. Xác định framework/wrappers thực, public/protected UI là context source. Không yêu cầu browser/journey runtime, không gọi match là DOM execution. React rules không đại diện Vue/Angular hoặc toàn bộ JS.

## FE-BR-01 — Untrusted content tới HTML/DOM/template có control đúng context không?

- **Áp dụng/discovery:** tìm rich text, server message, HTML render, template/direct DOM và nguồn URL/API/storage/user content.
- **Kỳ vọng/nguồn:** render text hoặc sanitize/encode theo HTML/attribute/URL context của feature; đọc renderer contract và content policy.
- **Source/kỹ thuật:** HTML sinks/URL taint bundled, search framework-specific directives, manual provenance và sanitizer implementation/config.
- **Control/giải thích khác:** trusted constant, sanitizer đúng context/version/config, framework text escaping; tên `safeHtml` hoặc parsing URL không chứng minh sanitization.
- **Evidence/giới hạn:** locations source/transform/sink/control, call path đúng provenance. Sink-only rule không chứng minh attacker control hay JavaScript execution/CSP runtime.
- **Khép/bước tiếp:** hiểu render contexts và controls trên surfaces chọn; đọc wrapper/sanitizer hoặc custom local rule cho framework khác, giữ gaps chưa rõ.

## FE-BR-02 — Dynamic code/script execution nhận nội dung từ đâu?

- **Áp dụng/discovery:** eval/Function, script injection/loaders, expression/template engines; tìm import và API thực.
- **Kỳ vọng/nguồn:** chỉ code/provenance được tin cậy theo plugin/script contract và build policy; không suy trust từ tên biến.
- **Source/kỹ thuật:** bundled dynamic-code candidate, search script URLs/constructors/loaders và manual flow tới execution API.
- **Control/giải thích khác:** fixed build assets, signed/integrity-controlled resources, test/dead code có căn cứ; CSP source declarations chưa chứng minh runtime enforcement.
- **Evidence/giới hạn:** nguồn URL/code, validation/integrity và sink locations; ghi config/runtime chưa biết, không báo đã thực thi trong browser.
- **Khép/bước tiếp:** provenance/control đã được đối chiếu đủ claim; đọc loader/caller hoặc giữ open nơi source bên ngoài chưa cung cấp.

## FE-BR-03 — Navigation/window.open/redirect có giới hạn destination và opener phù hợp không?

- **Áp dụng/discovery:** return URL, deep link, location/router navigate, window.open, user link fields.
- **Kỳ vọng/nguồn:** scheme/origin/destination và opener policy theo redirect/link contract; nội bộ, external và SSO có kỳ vọng khác nhau.
- **Source/kỹ thuật:** query/hash navigation/open taint và opener candidates bundled; search wrapper/router, manual destination canonicalization và browser context.
- **Control/giải thích khác:** allowlist/mapping cố định, relative paths, scheme validation, noopener/noreferrer hoặc subsequent opener clearing; tên route không chứng minh đích nội bộ.
- **Evidence/giới hạn:** source/check/navigation options locations và policy; static không chứng minh final URL, opener access hay browser version behavior.
- **Khép/bước tiếp:** destination policy và controls trên paths chọn đủ căn cứ; kiểm wrapper/SSO mapping còn thiếu trước verdict.

## FE-BR-04 — postMessage input/output có ràng buộc sender/recipient/payload đúng không?

- **Áp dụng/discovery:** Window/iframe/worker messaging; tìm handlers, senders, message types và receivers.
- **Kỳ vọng/nguồn:** origin/source window/payload validation và targetOrigin theo integration contract; Worker API và public broadcast có ngữ nghĩa riêng.
- **Source/kỹ thuật:** bundled inline message taint/wildcard target; search named handlers/wrappers, manual origin/source comparisons, schema and sinks.
- **Control/giải thích khác:** origin chính xác khác suffix/substring; source window binding, early returns đúng đường, payload allowlist; wildcard public data chưa tự sensitive disclosure.
- **Evidence/giới hạn:** locations send/handler/check/sink và loại API; manual call path không native trace, không suy controls vắng toàn app từ handler nhỏ.
- **Khép/bước tiếp:** kiểm cả chiều input/output thuộc scope; đọc shared handler hoặc parent contract chưa có, giữ gaps cụ thể.

## FE-BR-05 — Credential/session material có nằm trong storage/bundle/config/logging không?

- **Áp dụng/discovery:** auth state persistence, client env exports, telemetry/console và bundles/config được cung cấp.
- **Kỳ vọng/nguồn:** session/secret handling theo product policy và threat model; token lưu browser không tự là exploit đã xác nhận.
- **Source/kỹ thuật:** bundled Web Storage/auth-name/Vite-env candidates; search custom storage, logger/build exports; manual giá trị thực và lifecycle/redaction.
- **Control/giải thích khác:** public identifiers/keys, synthetic placeholders, storage wrappers, runtime injection, log stripping và session purpose; tên `token` chưa chứng minh credential.
- **Evidence/giới hạn:** locations/types/provenance/consumer đã lọc, không secret values. Static không xác nhận validity, attacker script presence hoặc runtime bundle exposure chưa cung cấp.
- **Khép/bước tiếp:** mô tả đúng material và exposure có căn cứ; cần policy thì giữ phần kết luận phụ thuộc mở, tiếp tục dataflow khả thi.

## FE-BR-06 — UI permissions có bị coi thành API authorization không?

- **Áp dụng/discovery:** menu/client guards/role checks và calls tới API cho actions nhạy cảm.
- **Kỳ vọng/nguồn:** server là trust boundary theo API authorization contract; UI chỉ điều khiển trải nghiệm, không thay server checks.
- **Source/kỹ thuật:** search UI guards/routes/API clients, manual principal/action/payload mapping; đọc server handler/control liên quan chỉ khi source nằm trong scope/quyền. Bundled không có detector đầy đủ cho câu hỏi này.
- **Control/giải thích khác:** server middleware/service authorization có thể đã enforce; menu ẩn/hiện không chứng minh server allow/deny. Không tự mở assessment toàn server.
- **Evidence/giới hạn:** UI/API reference và server locations nếu đã đọc, ghi server source ngoài scope hoặc thiếu; không tạo finding “server thiếu authz” chỉ từ client.
- **Khép/bước tiếp:** trả lời boundary ở mức được giao; đủ source thì review control, thiếu thì ghi limitation/điều kiện tiếp tục cho phần phụ thuộc.

## Mẫu ledger UI → API → server boundary

Mỗi action/data flow ghi `{route_component, action_or_data, input_source, transform, sink_context, api_consumer, token_storage_material, token_storage_consumer, server_handler_control_read, outside_scope, question_id, manual_review_id}` trong result/review. Nối locations thật ở từng đoạn; trường chưa đọc để null và next step cụ thể.

Với FE-BR-05 truy storage key → loại material → writers/readers → HTTP consumers → remember-me/login/register/logout khi có. Không gọi mọi token-shaped key là credential. Với FE-BR-06 ghi UI guard/button disabled tại layer UI; API enforcement chỉ kết luận sau đọc server control thuộc scope, không suy từ UI. Navigation/message/HTML cần transform và sink context thực (URL/origin/attribute/HTML), không chỉ tên component.

## Mapping, thích nghi và khép track

[Catalog](../rule-catalog.md): `fe-public-static.yml`, TS/React/browser/Vite, bundled-partial FE-BR-01…05; FE-BR-06 và frameworks/wrappers khác manual-review/custom-rule-needed. Đọc source trước nhận sanitizer, không thêm exemption dựa tên. Khép từng surface/question ở mức SAST, không bắt runtime.

Ví dụ rich-text preview dùng shared HTML component: sink match vẫn có thể false-positive cho claim untrusted injection khi renderer/control đã đọc đủ; FE text render là ca không match, chưa chứng nhận toàn trang safe.
