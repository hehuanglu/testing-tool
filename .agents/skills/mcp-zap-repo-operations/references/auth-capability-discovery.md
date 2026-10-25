# Khảo sát auth theo góc nhìn tester

Dùng khi chưa có contract nội bộ hoặc cần biết auth thực sự hỗ trợ gì. Tự đọc source/spec/UI/traffic được phép; không yêu cầu PM cung cấp tài liệu hoặc token field đã tìm được. Discovery source không cần chờ Docker/auth runtime.

## Thu thập khả năng có thể quan sát

Ghi method–route, loại thông tin source/spec/runtime và kết quả thật. Login/register, protected business request và account/role là cơ bản; expiry/refresh/logout/revoke/role change chỉ khảo sát sâu khi liên quan mục tiêu. Không lưu password/token trong báo cáo. Không cần hash/receipt hoặc field evidenceRefs cho từng capability ở output.

Chọn protected probe/strategy phù hợp để xác định đúng actor và role; login200 hay JWT claim chưa kiểm không tự là đủ. Không bắt mọi product có `whoami` hoặc cùng token pointer/issuer. Giữ các role chưa có account trong danh sách trách nhiệm, tiếp tục role đủ điều kiện.

## Quyết định coverage

- Source/spec có tính năng nhưng chưa chạy: ghi chưa xác minh runtime và điều kiện cần.
- Thao tác đã chạy: ghi kết quả đúng actor/route/thời điểm và giới hạn; không lấy source-supported thành pass.
- Chưa thấy trong phạm vi khảo sát: ghi chưa quan sát, không khẳng định toàn product không có.
- Đã kiểm và sai: ghi kết quả sai, không đổi thành skip.
- Thiếu capability/quyền/fixture: ghi dependency đúng case, không tự N/A hoặc loại khỏi nhiệm vụ.

Local logout không chứng minh server revoke; login mới khác refresh/resume. Đọc [lifecycle](auth-lifecycle-and-bola-depth.md) khi câu hỏi đó được giao, không đợi TTL hoặc mở campaign mới chỉ để bàn giao scan thường. Kết quả theo [ALERTS/RUN](product-assessment-handoff.md); hoàn tất khảo sát không nghĩa hoàn tất DAST.
