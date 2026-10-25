# Retention, stop và recovery nhiều lượt

Chỉ dùng khi nhiều attempts khó theo dõi hoặc cần dừng/tiếp tục. Không tự mở fault/HA/repeatability campaign. Đầu ra [ALERTS/RUN](product-assessment-handoff.md), không yêu cầu gói bằng chứng riêng.

## Bàn giao qua chat và trạng thái sống

RUN là điểm tiếp tục: product/môi trường, scope, API/role đã kiểm, thao tác/kết quả, chưa làm và bước tiếp. Dùng journal/status/log đã có để biết producer/resource nào còn sống và request đã ACK hay chưa. Không chạy lại mutation chỉ vì checkpoint chậm; cập nhật tổng hợp từ kết quả terminal phù hợp.

Nếu executor còn checkpoint riêng, chỉ rõ RUN hay checkpoint/revision nào là nơi tiếp tục chính thức. Snapshot attempt cũ giữ nguyên và ghi là lịch sử; không trộn counters/status cũ với operations đã tiến thêm. Sau recovery/finalization, ghi trạng thái tiếp tục nhất quán bằng atomic replace ở executor hỗ trợ; không sửa raw để khớp nhãn complete.

Khi status/count/attempt/binding mâu thuẫn, reconcile với journal ACK/terminal và state hiện tại trước dispatch. Không chọn file có timestamp mới hơn làm nguồn đúng theo suy đoán; session cũ sau cleanup không tự sống lại. Helper [review_open_work.py](operational-knowledge.md#helper-rà-soát-tùy-chọn) có phép so chỉ đọc, không hợp nhất hoặc cập nhật file thay caller.

## Tổng hợp retention từ ledger có sẵn

Ghi dữ liệu test còn giữ hoặc đã cleanup khi liên quan, lý do và điều kiện xử lý. Scanner cleanup khác xóa fixture/product data. Không xóa log/raw/kết quả cũ để đạt bộ output gọn; không prune/down-v/xóa DB hoặc credential ngoài quyền. Native raw chứa secret giữ private, không copy vào ALERTS/RUN.

## Report stop theo event thật

Stop requested, stop ACK và terminal là các trạng thái khác nhau; ghi đúng cái quan sát được, không hứa stop tức thời hoặc không có in-flight khi chưa biết. Dừng đúng operation/job/resource của run, không shared stop-all hoặc dùng tên project làm ownership duy nhất. Mất auth/scope/resource thì dừng nhánh phụ thuộc và giữ kết quả partial.

## Caps và giới hạn

Dùng count/rate/time/resource limit của entry; không nâng caps/hạ reserve để ép completed. Hết deadline workload vẫn cần stop/cleanup đúng quyền. Skill không yêu cầu fault injection, process-kill, ACK-loss hoặc zero-in-flight proof để bàn giao ordinary scan; chỉ thực hiện khi user giao bài kiểm đó hoặc contract executor thực sự yêu cầu.

## Recovery khi outcome chưa rõ

Kiểm operation status, ACK, object state và resources trước retry. Unknown POST/DELETE/start không replay mù. Nếu không thể xác minh trong quyền hiện có, giữ unknown/partial, chỉ rõ tác động và thông tin cần có. Login mới hoặc fresh run thay thế phải ghi là lượt mới, không giả resume cùng phiên. Lỗi cục bộ sửa theo [quy trình](local-remediation-and-continuation.md), tiếp tục nhánh đủ điều kiện.

Đối soát inventory độc lập và thực hiện phần còn thiếu qua [vòng trách nhiệm](responsibility-loop.md); cap/gate/stop của một producer không kết thúc task.
