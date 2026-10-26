# Context: tester dùng Semgrep và đọc source

Bắt đầu từ chức năng: ai dùng, ai kiểm soát dữ liệu, tài sản/quyền nào cần bảo vệ, kỳ vọng từ đâu, source nào có thể trả lời? Người giao việc không phải thiết kế workload. Chọn phép kiểm nhỏ nhất trả lời được câu hỏi trong scope, rồi đối soát phần còn thiếu.

## Ba lớp nhận định

- **Source structure:** pattern, import, control flow, call path, predicate và cấu hình đã đọc. Rule match chỉ chứng minh phần pattern/engine quan sát được.
- **Runtime behavior:** deployment có dùng nhánh/config đó, dữ liệu thật, redirects, thời gian hết hạn và browser execution. Source có thể cho giả thuyết hoặc ràng buộc, không tự là kết quả runtime.
- **Policy correctness:** spec/policy do user cung cấp hoặc tài liệu có thẩm quyền; expectation suy từ implementation phải ghi là giả định source. Implementation khớp giả định không chứng nhận policy đúng.

Không bắt exploit động, hai fresh runs, source snapshot/hash hoặc chứng minh toàn scanner để kết luận SAST có giới hạn. Supported phải tương xứng claim và controls đã đọc; không thấy control trong một đoạn nhỏ chưa chứng minh toàn hệ thống thiếu control.

## Điều kiện làm việc

Khi tài liệu khác source, ghi `document_statement`, `source_implementation_or_declaration`, `comparison_scope`, `authority_currentness`, `permitted_claim` trong result/review. README/runtime note không tự là requirement hiện hành: authority/currentness chưa xác nhận phải để rõ unknown. Phân biệt discrepancy giữa hai nguồn, vi phạm requirement đã xác nhận, và thiếu control runtime; loại trước không tự chứng minh loại sau. Áp dụng cả CFG-01 về config lẫn AUTH-05 về guards/lookup. Không gọi declaration discrepancy là runtime exploit.

Đọc source không cần Git, deployment, token hoặc build. Nếu có Git, ghi revision và dirty; giữ thay đổi có sẵn. Nếu không có Git, ghi roots, thời gian quan sát và thông tin phiên bản có thật. Không tự cài dependencies/provision runtime. Source đổi thì ghi source state mới và đánh giá phần cần đọc/chạy lại.

Inventory từ source/spec/config độc lập findings: module, function, entrypoint, input, identity, persistence, UI và config liên quan. Public/protected chỉ mô tả đường source theo routing/guards đọc được. Không cần mọi product có HTTP; jobs, events và libraries có trust boundaries riêng.

Tên field/route/owner chỉ gợi ý discovery. Đọc implementation của sanitizer/guard/wrapper và callers trước tin kiểm soát. Mapping product để ở working area riêng ngoài core skill, không hardcode verdict hoặc policy từ một product thành mặc định.

## Trách nhiệm có giới hạn

Scope quyết định câu hỏi cần trả lời, base giúp bắt đầu, capability quyết định kỹ thuật. Thiếu bundled rule → tìm local rules, custom rule có fixture khi hữu ích, đọc source khả thi và giữ phần còn thiếu; không đổi thành N/A. Search/inventory chưa là security observation. Ghi nguồn và giới hạn trước tổng hợp theo [workflow](tester-workflow.md).
