# be-input — Backend input và xử lý dữ liệu

## Ý định, applicability và discovery

Kiểm dữ liệu do bên không tin cậy kiểm soát đi tới xử lý/tiết lộ gì. Chọn public/protected HTTP/GraphQL/RPC entrypoints trong scope, cùng jobs/events/files/library input khi liên quan. Tìm routing/handlers, schemas, services, repository wrappers, sinks, responses và logs độc lập matches. Không tự mở authentication/authorization assessment chỉ vì đọc principal để hiểu flow.

## BE-IN-01 — Input có tham gia SQL/query construction không an toàn không?

- **Áp dụng/discovery:** có persistence/query; tìm raw SQL, ORM builders, sort/filter/dynamic identifiers và wrappers gọi chúng.
- **Kỳ vọng/nguồn:** tách bound values khỏi SQL text; identifiers theo mapping/allowlist phù hợp API. Đọc query contract, schema và coding policy; chưa có policy thì ghi giả định.
- **Source/kỹ thuật:** theo handler/job → service → wrapper → query; bundled SQL taint/construction cho TS, search sinks và manual callers/bindings khi xuyên file.
- **Control/giải thích khác:** hằng số/constant folding, SQL parameter placeholders, allowlist identifiers thực, ORM escaping. Có mảng parameters chưa chứng minh text an toàn; sort direction cũng cần đọc.
- **Evidence/giới hạn:** locations nguồn, construction, sink và binding/control, source state/thao tác; manual path là source-review. Static không chứng minh DB runtime hoặc exploit.
- **Khép/bước tiếp:** trả lời cho query paths trong scope sau đọc provenance và controls; thiếu wrapper thì tìm/đọc nó, thiếu source thì giữ gap cụ thể. Zero matches không khép inventory queries.

## BE-IN-02 — Input tới shell/process/eval/template execution như thế nào?

- **Áp dụng/discovery:** tìm process launch, eval/new Function, template compile/render hoặc expression interpreter trong flow được giao.
- **Kỳ vọng/nguồn:** command/code và template trust theo feature contract; input không thành cú pháp thực thi ngoài ý định. Tìm job spec, command mapping và template policy.
- **Source/kỹ thuật:** đọc imports/API, command/argv/options, caller và engine; shell/eval bundled, search template wrappers, manual execution path.
- **Control/giải thích khác:** argv không qua shell khác command string; `shell:true`, shell interpreter argv, quoting, fixed command mapping, trusted templates và sandbox semantics cần kiểm thật.
- **Evidence/giới hạn:** ghi execution API/options, nguồn và transformations/controls đã đọc, không gọi mọi process use là injection. Không chạy payload hay process product để chứng minh.
- **Khép/bước tiếp:** giải thích được cái gì thực được thực thi và input ảnh hưởng ra sao; đọc wrapper/options còn thiếu hoặc bổ sung local rule/fixture phù hợp.

## BE-IN-03 — Input tới filesystem/upload/archive có giữ đúng boundary không?

- **Áp dụng/discovery:** tìm upload/download, extract/archive, path từ request/job và mọi điểm đọc/ghi/rename/copy/link.
- **Kỳ vọng/nguồn:** thao tác trong base directory/tài nguyên được phép; tên file, archive entries và symlinks theo storage/feature policy.
- **Source/kỹ thuật:** bundled filesystem usage/taint cho API TS được nhận diện; search upload/archive libs, đọc normalization → containment → actual read/write và callers.
- **Control/giải thích khác:** `join`/normalize không tự containment; kiểm canonicalization, separator/prefix, symlink/TOCTOU và generated filename. Với copy/rename đọc cả source/destination.
- **Evidence/giới hạn:** locations input/base/check/sink, hướng đọc/ghi và giả định filesystem/runtime; không invent effective permissions.
- **Khép/bước tiếp:** đã đối chiếu paths/entries và controls liên quan câu hỏi; thư viện extract hoặc storage wrapper chưa đọc thì đọc tiếp, không lấy không match làm safe.

## BE-IN-04 — Input điều khiển outbound network destination ra sao?

- **Áp dụng/discovery:** callback/webhook/import/proxy/fetch từ input; tìm HTTP clients, URL/options/baseURL và redirects.
- **Kỳ vọng/nguồn:** destination/protocol/redirect policy theo chức năng; đọc integration spec, allowlists, proxy/egress config được cung cấp.
- **Source/kỹ thuật:** bundled HTTP usage/request taint cho local TS, search client factories; manual URL assembly, parser và redirect/caller options.
- **Control/giải thích khác:** fixed server destinations, host/scheme allowlist áp dụng sau parsing, redirect validation và effective consumer. URL parsing không tự chống SSRF; network runtime có thể hạn chế nhưng chưa biết phải ghi rõ.
- **Evidence/giới hạn:** nguồn, destination fields, checks và redirect/config locations; không khẳng định reachability/DNS behavior chưa quan sát.
- **Khép/bước tiếp:** kết luận ở mức source cho destinations thuộc scope; config/egress chưa cung cấp giữ limitation, tiếp tục review không phụ thuộc runtime.

## BE-IN-05 — Binding/deserialization/mass assignment có cho sửa protected fields không?

- **Áp dụng/discovery:** DTO/entity binding, deserialize, object spread/assign/merge/create/save; tìm fields user được phép sửa và fields server quản lý.
- **Kỳ vọng/nguồn:** field allowlist và validation theo API/schema/policy; tenant/owner/role/state có authoritative source rõ.
- **Source/kỹ thuật:** bundled body/ValidationPipe candidates; search serializers/binders và manual validation invocation, merge order tới điểm persistence.
- **Control/giải thích khác:** TS types không là runtime filter; DTO declarations chưa chứng minh pipe chạy; create/merge có thể chưa ghi DB. Đọc hooks, wrappers, overwrite order và caller trust.
- **Evidence/giới hạn:** locations binding/validator/write, fields mô tả đã lọc và policy/control đã đọc; không copy sensitive payload hoặc suy mọi field writable.
- **Khép/bước tiếp:** xác định fields thực tới write và control có hiệu lực; thiếu policy giữ expectation giả định/open phần phụ thuộc, vẫn đọc path khả thi.

## BE-IN-06 — Sensitive data có tới response/log/error ngoài ý định không?

- **Áp dụng/discovery:** tìm dữ liệu cá nhân/credential/tài sản theo chức năng, serializers, error envelope và logger sinks.
- **Kỳ vọng/nguồn:** disclosure/redaction theo API/data classification/logging policy; implementation chỉ là hypothesis nếu policy chưa có.
- **Source/kỹ thuật:** bundled sensitive names/logger/error/HTTP candidates, search actual models và manual flow tới response/log handler, serialization và config.
- **Control/giải thích khác:** tên token có thể là public identifier; hashing/redaction, disabled log level, serializer exclusion và internal return cần đọc. Không tin tên `redact` trước implementation.
- **Evidence/giới hạn:** ghi vị trí/loại dữ liệu, sink và control, không ghi secret values. Static chưa chứng minh log access, response runtime hay dữ liệu thật.
- **Khép/bước tiếp:** đã hiểu data representation/exposure trên paths chọn; đọc logger/serializer/caller còn thiếu; needs-review giữ gaps nếu chưa thể phân định.

## Mẫu ghi đường dữ liệu theo nhánh

Trong `questions[].result` hoặc manual review, ghi `{entrypoint_input, trust_source, transform_validator, sink, control, response_or_write, callers, locations, limitations}`. Mỗi giá trị là facts đã đọc; chưa biết để null. Ghi public/protected theo routing/guard source, không mô tả đã thử session runtime. Supporting library/module ghi vai trò hỗ trợ và callers, không gán là input entrypoint.

Ví dụ synthetic: create account dùng allowlist trước persistence nhưng update spread body rồi override owner; tách hai instances BE-IN-05 vì control/overwrite order khác. Ghi validation implementation, thứ tự transformations và writer thực cho từng nhánh. Không mở toàn AUTH/AUTHZ chỉ vì đọc principal. N/A filesystem cần discovery fact không có file operations trong scope, không từ zero matches.

## Mapping, thích nghi và khép track

[Catalog](../rule-catalog.md) map `be-public-static.yml` (TS/Nest/Node/TypeORM, bundled-partial), cùng rules liên quan ở AUTH/ownership/config khi câu hỏi cần. Templates/archive/deserialization tùy stack thường manual-review hoặc custom-rule-needed. Không coi tên public là giới hạn chỉ anonymous source. Ngoài stack thì tìm repo/local rules, custom rule có fixtures khi hữu ích, manual review và giữ phần chưa làm.

Khép theo inventory/questions đã chọn, không theo đủ 21 rules. Ví dụ export invoice được API và worker gọi: cùng helper nối filename chỉ thành một root cause, evidence liên kết cả callers khi đã đọc; runtime file access chưa được chứng minh.
