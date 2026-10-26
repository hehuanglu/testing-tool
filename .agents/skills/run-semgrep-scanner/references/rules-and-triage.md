# Chọn rules, bổ sung phép kiểm và triage

## Thư viện local khởi đầu

Đọc [catalog](rule-catalog.md): năm YAML bundled giữ IDs/severity/confidence và có giới hạn TypeScript/NestJS/TypeORM, React/browser, Docker/Compose/nginx/npm. Không đại diện thư viện đa ngôn ngữ hoặc policy mặc định. Ngưỡng bcrypt <10 và MinLength 0..7 là heuristic cần policy; regex tên field và path filters có blind spots.

Chọn theo [base nghiệp vụ](track-intents.md) và source thực, đọc languages/paths/pattern/taint/engine trước dùng. Không ép Python/Java/Go qua bộ TS rồi báo sạch: inspect repo/local rules → kiểm applicability → custom rule có fixtures khi hữu ích → manual source review phần khả thi → đối soát gaps. Thiếu rule không là N/A. Generic regex không có cùng ý nghĩa phân tích với structured language/taint rules.

## Chọn hoặc tạo rule theo câu hỏi

1. Xem config/rules repo đã có và local library sẵn có; đọc remote references, autofix, engine requirements, filters và suppressions trước dùng.
2. Chọn rule security cho giả thuyết cụ thể, hoặc search rule để inventory sinks/call sites. Inventory match không tự trở thành vulnerability alert; ghi mục đích riêng.
3. Nếu abstraction product chưa được nhận diện, đọc implementation trước khi viết source/sink/sanitizer. Lưu mapping riêng của product ngoài core/thư viện chung. Không mang tên route/role/ID từ product trước sang.
4. Với custom rule, dùng cấu trúc code/metavariables để diễn đạt điều cần tìm; regex có thể phù hợp config/text, nhưng không tự cho parser/semantic coverage như language rule. Không loại findings dựa trên tên biến “safe” hoặc hàm “sanitize” chưa đọc semantics.
5. Thử rule mới/sửa trên ca positive và negative đại diện trước khi dùng để kết luận. Với taint, có ca dữ liệu không tin cậy tới sink và ca kiểm soát đúng ngữ cảnh; ca literal cũng cần nếu muốn phân biệt. Chạy lại trên source thật và triage; test synthetic chỉ kiểm hành vi rule trên các ca đó.

Thư viện local có thể được mở rộng khi nhiệm vụ yêu cầu. Không tải Registry, dùng Playground với source private hoặc nâng engine tự động. Có thể nghiên cứu tài liệu/public rule khi phù hợp; tải rules vào assessment và thực thi remote config là hành động khác, phải nằm trong quyền đã giao. Khi được phép dùng nguồn bổ sung, ghi xuất xứ và engine, không gọi đó là bộ bundled đã kiểm.

## Triage một match

Đọc vị trí finding, đoạn code đầy đủ và đường gọi đủ để giải quyết nghi vấn:

- Input thực đến từ đâu, ai kiểm soát, có hằng số hoặc server-generated value không?
- Sink/context nào gây tác động: SQL, shell, HTML, path, outbound network, credential hoặc persistence?
- Validation/sanitization/encoding/authz có áp dụng trên đúng đường gọi và dữ liệu không? Control đúng một ngữ cảnh chưa đủ cho ngữ cảnh khác.
- Policy owner/tenant/role lấy từ đâu? Guards/global middleware/repository có thêm constraints không? Có đường gọi khác bypass không?
- Source có phải implementation dùng cho chức năng trong scope, hay fixture/dead/generated/sample? Không kết luận dead chỉ vì không tìm thấy caller một lần.
- Engine/rule theo được đoạn nào, tester đọc bổ sung đoạn nào, phần nào còn chưa biết?

Giữ native ID/path/line/severity/confidence và thông điệp cần thiết. Nếu message chứa dữ liệu nhạy cảm thì redact ở bản bàn giao, không làm sai ý nghĩa finding. Không đưa matched source hoặc giá trị secret vào báo cáo theo mặc định.

Dùng triage trạng thái có nghĩa:

- `needs-review`: chưa đọc đủ hoặc còn thông tin ảnh hưởng kết luận; nêu bước tiếp.
- `supported`: có căn cứ từ source cho vấn đề/rủi ro đã mô tả; ghi mức xác nhận và giả định, không mặc định đã khai thác runtime.
- `false-positive`: mẫu bắt sai hoặc kiểm soát có hiệu lực trên đường gọi đã được xác định; ghi lý do cụ thể.
- `not-applicable`: có căn cứ không thuộc chức năng/phạm vi đang kiểm; giữ record cùng lý do, không xoá lặng lẽ.

Rủi ro được chấp nhận khác false positive; chỉ ghi accepted risk khi có quyết định từ người có thẩm quyền đã được cung cấp. Không tự accept vì severity thấp. Không bắt xác định mọi alert thành supported/false-positive; needs-review hợp lệ nhưng phải phản ánh vào mức hoàn tất nếu nhiệm vụ bao gồm triage phần đó.

## Findings do đọc source thủ công

Nếu phát hiện vấn đề khi đọc callers/controls mà Semgrep chưa báo, vẫn ghi finding nếu có cơ sở, với nguồn `manual-source-review`, rule_id null và native severity/confidence null. Nhận định tester đặt riêng; không bịa Semgrep trace/rule hoặc đổi nguồn để tăng scan coverage.

Nếu Semgrep và manual review cùng hỗ trợ một vấn đề, liên kết hai observations thay vì đếm thành hai vấn đề độc lập. Giữ occurrences gốc để người nhận xem scanner thực sự báo ở đâu.

## Đếm và retest

Inventory candidate reviews có một chỗ trong `RUN.coverage.inventory_candidate_reviews` theo [contract](reporting-and-completion.md). Ghi round/rule/location/index, question/manual review, candidate kind, context, disposition và next step cả khi không tạo ALERT. `record_round.py` có thể gợi ý nhóm theo native location, giữ từng occurrence và reference về native message; caller/control grouping sau đọc context do tester ghi. Không suy cùng issue/root cause từ cùng dòng/rule hoặc tự đổi false-positive theo receiver/path. Một control review có thể hỗ trợ nhiều candidates/observations.

Tách native matches/occurrences, findings sau triage và nhóm vấn đề khi gộp. Một finding bị nhiều rules/lượt phát hiện không tự là nhiều vulnerability. Ghi cách gộp, không cộng lại tất cả results qua các lượt như số lỗi hiện hành. Không gộp chỉ vì cùng rule nếu có root cause khác.

Giữ native severity; priority/impact của tester là field riêng và cần lý do. Không chuyển WARNING thành CVSS hoặc severity khác bằng mapping tuỳ ý. Retest chỉ ghi đã xử lý khi đã đối chiếu thay đổi và scan/readback phù hợp; alert biến mất do exclusions/rule change chưa là fixed.

Evidence từng claim theo [evidence contract](evidence.md); output v2 theo [reporting](reporting-and-completion.md). Manual call-path là source-review, chỉ ghi native-dataflow khi native output thật có trace và đã đọc.
