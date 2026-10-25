# Ghi thao tác và đọc kết quả

Đích là biết đã làm gì và kết quả nào, không phải tạo bộ chứng minh chặt. Đầu ra theo [hai file kết quả](product-assessment-handoff.md#3-bộ-bàn-giao-bắt-buộc), không có phần/folder evidence.

## Native scan workflow

Dùng schema thực của tools: optional import → crawl/seed khi phù hợp → active đã được giao → theo dõi status đến kết thúc hoặc lỗi → đọc alerts/report → ghi thao tác/kết quả → đối soát phần thiếu. Không bịa tham số hoặc đổi scan ID/job ID thành guided operation ID. Producer chưa kết thúc thì ghi đang chạy, không kết luận completed.

Phân biệt HTTP crawl với browser/JS; import không là coverage. Anonymous và authenticated phải có ZAP thực sự chạy; direct request/BOLA, health, unit test và danh sách tools không thay DAST. Ghi method–route, role, input/kỹ thuật thực kiểm; không cần request archive, wire attribution hoặc proof file riêng cho từng dòng.

## Đọc kết quả đủ để báo đúng

Dùng findings summary/details hoặc report đúng target và lượt chạy. Nếu output bị truncate, lấy phần còn lại bằng API có sẵn hoặc ghi rõ chưa đọc đủ; không giả summary toàn bộ từ một preview. Chunk API/helper hiện có có thể xử lý offset/EOF/hash tự động; skill không bắt tạo chiến dịch full-readback/manifest/hash bổ sung. Không lấy checksum pass làm security pass.

Triage từ nội dung đã có: native severity/confidence, route/parameter, mô tả và phản hồi liên quan nếu sẵn. Không yêu cầu lưu raw hoặc chứng minh exploit mới cho mọi nhóm. Khi thiếu thông tin ảnh hưởng nhận định thì ghi chưa xác nhận. Không đưa secret vào ALERTS/RUN.

## Nhật ký thao tác

Mỗi việc ghi loại thao tác, thời gian khi biết, method–route/phạm vi, actor/role, kỹ thuật, kết quả hoặc lỗi. Setup/login/identity, seed/crawl, passive, active và BOLA là các loại khác nhau. Ghi riêng mục chưa chạy cùng lý do. Thông tin từ source/spec khác kết quả runtime; report lịch sử khác scan vừa chạy.

Phần còn mở cần [quyết định xử lý](local-remediation-and-continuation.md#quyết-định-cho-phần-việc-còn-mở) và outcome của bước đã làm, không chỉ một nhãn trạng thái. Giữ execution, coverage và mức xác nhận policy riêng: thiếu policy approval không biến case đã chạy thành chưa chạy; case chưa có fixture vẫn là chưa chạy dù đã có hướng xử lý.

## Lỗi và tiếp tục

Biết bước lỗi, đã dispatch/ACK hay chưa và phần bị ảnh hưởng trước retry. Tận dụng log/status sẵn có; không yêu cầu một gói forensic mới. Lỗi cục bộ sửa theo [workflow](local-remediation-and-continuation.md), rồi tiếp tục. Nếu công cụ chỉ báo type thiếu nguyên nhân thì nói chưa xác định; có thể bổ sung diagnostic đã lọc ở đúng chỗ trong scope sửa, không in raw credential.

## Dữ liệu nội bộ và audit riêng

Log/report/private artifact runner sinh vẫn ở vị trí làm việc; không bắt copy vào bộ bàn giao. Giữ dữ liệu cũ, không chỉnh verdict hoặc xóa để làm output gọn. Helper kiểm checksum/saved bundles hoặc qualification chỉ dùng khi user yêu cầu audit/retest cụ thể; không chạy chúng như gate mặc định mỗi assessment và không tự mở campaign mới.

## Attribution và gợi ý từ native tools

Trong shared session, nếu cần kết luận finding mới thì so details/snapshot trước và sau khi có visibility hợp lệ. Alert ID/instance đã có giữ nhãn tồn tại; không có baseline thì nêu không xác định first-seen, không reset session để có số đẹp. Một report mới không làm mọi alert trong report thành mới.

`Next Actions` gợi ý release-evidence/customer-handoff không là yêu cầu của assessment. Theo scope và hợp đồng hai file; chỉ tạo bundle nếu user yêu cầu hoặc entry thực sự bắt buộc. Kiểm định capability dùng [operational validation](operational-validation.md); smoke health/passive không thay active/auth/FE/BOLA acceptance.

Đối soát inventory độc lập và thực hiện phần còn thiếu qua [vòng trách nhiệm](responsibility-loop.md); cap/gate/stop của một producer không kết thúc task.
