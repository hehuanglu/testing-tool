# Chọn base nghiệp vụ

Chọn theo nhiệm vụ và discovery, không theo tên YAML. Mỗi base có sáu câu hỏi để cụ thể hóa, không bắt chạy tất cả vô điều kiện.

- [be-input](tracks/be-input.md): BE-IN-01…06; public/protected backend input và shared processing.
- [fe-browser](tracks/fe-browser.md): FE-BR-01…06; browser data/code/message/navigation boundaries.
- [authentication-session](tracks/authentication-session.md): AUTH-01…06; credential, verification, issuance/lifecycle, principal propagation và leakage.
- [authorization-ownership](tracks/authorization-ownership.md): AUTHZ-01…06; chức năng, object/tenant, collection, relation, lifecycle và protected fields.
- [configuration-build](tracks/configuration-build.md): CFG-01…06; effective config, privileges, network/TLS, dependency declarations, build/CI và credentials.

Chỉ giao một track thì không tự mở bốn track còn lại. Shared code cần đọc để hiểu câu hỏi không tự mở assessment service khác. Scope hẹp thì ghi selected_base_ids và lý do phần base không chọn; phân biệt ngoài scope với không áp dụng. Nhiều track dùng chung một lượt được, giữ mapping câu hỏi và không đếm trùng root cause.

Tên rules giữ ổn định để nhận diện; `public`/`auth` trong tên không xác định surface. Xem [catalog đầy đủ](rule-catalog.md) để biết file, stack và giới hạn. Không có rule không là không có rủi ro; Python/Java/Go hoặc wrapper khác cần local/custom/manual phù hợp theo [rules và triage](rules-and-triage.md).
