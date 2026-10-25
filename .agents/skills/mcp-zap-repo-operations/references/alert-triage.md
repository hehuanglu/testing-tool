# Triage alert theo kết quả đã có

Dùng khi alert cần giải nghĩa sâu hơn [triage cơ bản](product-assessment-handoff.md#triage-alert-theo-kết-quả). Đọc nội dung đã trả về, giữ native severity/confidence, ghi nhận định và giới hạn; không bắt lưu raw/HTTP archive/hash hay chứng minh exploit cho mọi alert. Không tự mở một campaign mới chỉ để bàn giao kết quả.

## Injection

Đọc route/parameter/vector, baseline/input và phản hồi mà rule viện dẫn nếu có. Phân biệt payload bị validation/guard chặn, reflection và hành vi khai thác đã quan sát. Native alert có thể giữ nguyên cùng nhận định chưa xác nhận impact; HTTP200 hoặc không tái hiện một lần không đủ gọi false positive. Thiếu thông tin thì ghi rõ thay vì dựng proof.

## Security headers và cấu hình

Xác định response thuộc app, tài liệu hoặc proxy/guard nếu thông tin có sẵn; nhận xét theo context. Thiếu header không tự chứng minh exploit. Giữ severity native và mô tả điều quan sát, không áp kết luận một product mẫu cho product mới.

## Auth/session Informational

Công cụ nhận diện token/session mechanism không đồng nghĩa token leak hoặc lỗi phiên. Chỉ kết luận disclosure khi có kết quả cho thấy bên không được phép nhận được dữ liệu. Không copy giá trị token vào report; không đợi expiry hoặc mở lifecycle để giải thích Informational.

## Error/disclosure

Đọc nội dung lỗi/dữ liệu đã trả về; phân biệt generic error với stacktrace, secret hoặc dữ liệu có ảnh hưởng. Không gán impact vượt điều quan sát được. Bảo vệ dữ liệu nhạy cảm trong báo cáo chia sẻ, không publish raw theo suy đoán đã sanitize.

## Direct BOLA/business

Đọc actor/role, owner/object/relation/state và expected policy/spec/source hiện có; kết quả response và trạng thái sau thao tác nếu đã kiểm. Tách policy chưa rõ khỏi lỗi thực tế đã thấy. Status deny đơn lẻ không chứng minh mọi side effect; nêu giới hạn phần đã đọc. Không đổi expected theo observed để matched.

Findings direct không phải ZAP alerts; severity do tester đánh giá phải ghi đúng nguồn và mức chắc chắn. Đủ bàn giao observation không đồng nghĩa đã kiểm đủ role/API: phần còn thiếu vẫn nằm trong RUN theo [scope](assessment-scope-and-completion.md).
