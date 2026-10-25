# Đưa mục tiêu authenticated DAST đến execution

Đích là ZAP thực sự kiểm API protected với actor/role đúng và phiên hợp lệ. BOLA direct, anonymous report, health, token login hoặc chỉ sửa skill không hoàn thành đích này. Toàn inventory protected thuộc scope phải được xử lý, không chỉ recipe sample.

## Auth thật và local retention

Authenticated dùng token/session thật. Skill cho phép lưu credential/token cần thiết local private, chỉ thông báo; nếu dùng `be-authenticated-research/1.0` thì phản ánh quyền này vào field retention của contract, không hỏi lại. Chọn profile/deployment tương thích theo [dispatcher](operation-dispatch.md), không tự bật experimental trên shared scanner hoặc đưa secret vào output chia sẻ.

## 1. Chọn đường thực thi

Discovery → API/role/input/fixture → operation/entry thực → workload hữu hạn → ZAP auth prepare/validate/crawl/attack/status → đọc kết quả. Chọn native operations hoặc executor theo [dispatcher](operation-dispatch.md); [multi-product](multi-product-backend.md) và [research authenticated](be-authenticated-research.md) là hướng dẫn khi entry tương ứng phù hợp, không là bắt buộc cho mọi scan. Root có method/body khác việc wrapper đã hỗ trợ shape đó.

Không mặc định quay về runner strict lịch sử hoặc product adapter khác. Không dựng capability-proof, strict secret-safe/platform qualification hoặc hash bundle mới chỉ để có kết quả assessment trung thực. Entry đang bắt proof/pin thì chẩn đoán dependency đó, không bỏ gate hay giả kết quả.

## 2. Chọn blocker cần đóng

Thiếu actor, fixture, input mapping, method/vector, runtime hay báo cáo là những lỗi khác nhau. Dùng operations sẵn có, cấu hình/phối hợp, rồi sửa runner/adapter tối thiểu theo [vòng khắc phục](local-remediation-and-continuation.md). Giữ scope đầy đủ và các nhánh độc lập; không coi bị wrapper reject là product fail hoặc ZAP không làm được.

## 3. Quy trình chỉnh sửa skill

Khi chỉ được giao sửa skill: đọc baseline và giới hạn user; sửa routing/quy trình, kiểm validator/link và walkthrough offline. Không quét product để chứng minh tài liệu đã sửa; không thay schema/implementation ngoài scope. Kết quả sửa skill tách khỏi kết quả assessment.

## 4. Thực thi và đối soát

Chạy ZAP thật trong quyền, theo dõi terminal/mất auth, đọc findings/report có sẵn và kiểm kết quả mutation liên quan. Ghi method–route, role, kỹ thuật và kết quả/lỗi; seed không ghi thành active, mất phiên không ghi coverage. Đối chiếu toàn protected inventory và role sau mỗi lượt rồi tự tiếp tục phần đủ điều kiện.

## 5. Bàn giao khi đích chưa đạt

Dùng [ALERTS/RUN](product-assessment-handoff.md), không folder/mục bằng chứng. Nêu đã làm, kết quả, API/role chưa chạy, blocker và bước tiếp. Trả alerts sớm nhưng không gọi toàn mục tiêu hoàn tất khi còn nghĩa vụ. Chỉ dừng theo điểm dừng hợp lệ; không tự mở lifecycle/qualification ngoài mục tiêu.
