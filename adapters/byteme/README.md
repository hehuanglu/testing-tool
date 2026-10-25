# Adapter ByteMe

Mã vận hành được giữ từ các lượt ByteMe gần nhất, không chứa token, actor, fixture ID, plan hay kết quả của lượt cũ.

- `anonymous/`: runner, guard, active rule kiểm tra phone và bộ tổng hợp kết quả.
- `authenticated/`: runner, guard, reader và bộ tổng hợp kết quả.
- `ownership/`: adapter kiểm tra role/ownership bằng transport và checker chung.

Các adapter này dành riêng cho source `/Users/hahoangloc/Working/UET/SA/ByteMe` và deployment Docker local ByteMe trên `127.0.0.1:8081`. Mỗi lượt cần discovery và xác minh binding hiện tại; không dùng bằng cách chỉ đổi URL sang sản phẩm khác.

Mặc định, working data được tạo riêng tại:

```text
operations/byteme/anonymous
operations/byteme/authenticated
operations/byteme/ownership
```

Đặt `BYTEME_ANON_ROOT`, `BYTEME_AUTH_ROOT`, `BYTEME_BOLA_ROOT` để dùng thư mục mới cho một lượt mới. Reader và composer dùng cùng biến tương ứng. Chỉ resume một working directory còn nguyên trạng; không tái tạo state từ kết quả cũ.

Authenticated runner dùng JAR tại `mcp-zap-server/build/libs/mcp-zap-server-0.16.0.jar`; giữ bản build hiện tại và xác minh capability khi allocation mới. Script guard và phone rule được mount từ source adapter, không từ working data.

Các continuation/audit script chỉ phục vụ trạng thái của lượt cũ đã được bỏ. Dùng workflow runner và reader hiện tại để chuẩn bị, chạy, đọc kết quả, cleanup và tổng hợp `ALERTS.json` + `RUN.json`.
