# Khả năng backend authenticated

Với assessment thường, chọn đường theo [dispatcher](operation-dispatch.md) và [workflow theo mục tiêu](authenticated-dast-goal.md); chỉ dùng [authenticated research](be-authenticated-research.md) khi contract phù hợp. Đích là ZAP DAST thật trên toàn protected API thuộc scope, đúng actor/role và kiểm trạng thái phiên; đầu ra chỉ ALERTS/RUN theo [handoff](product-assessment-handoff.md).

## Phân biệt các lớp

- Client→MCP API key/JWT khác ZAP→target authentication.
- Native prepared auth session khác delegated/header injection; không đổi tên hai cách để báo coverage.
- Guided/expert là registration, direct/queue là execution mode.
- Browser auth dùng Client Spider; browser/AJAX crawl không tự là active authenticated DAST.
- JSON-bearer provider mặc định tắt; chỉ bật deployment/profile được chọn trong quyền. Queue rejection và gate code giữ nguyên.

## Chọn khả năng thực sự dùng được

Đọc help/schema/source của entry và deployment thực khi cần. Root hỗ trợ method/postData không có nghĩa wrapper admit mọi mutation/body. Ưu tiên operation có sẵn, phối hợp/config và adapter tối thiểu trước làm hệ thống mới. Một capability chưa có ở wrapper không là toàn ZAP thiếu.

Xác minh actor/role từ nguồn hợp lệ và protected behavior/strategy phù hợp. Không forge credential, dùng owner field làm caller hoặc coi 401 là đã kiểm authenticated. Giữ token/private raw ngoài hai file chia sẻ; skill cho phép lưu credential/token cần thiết local private, chỉ thông báo và không xin lại.

## Giới hạn assurance

Skill không yêu cầu secret-sink/platform attestation, zero-secret persistence proof, full archive/hash/readback, repeatability/fault campaigns hoặc independent sign-off cho scan thường. Gate đã enforce trong executor vẫn giữ; nếu chọn runner strict thì phải tuân contract của runner đó, nhưng không kéo nó thành dependency mặc định của mọi product.

Chỉ khi user giao qualification/strict audit cụ thể mới tra runbook và implementation-status tương ứng trong assessment hoặc repo gốc. Không dùng kết quả research để đổi verdict strict lịch sử. Với task thông thường, ghi trung thực operations/kết quả/hạn chế và tiếp tục phần scope còn thiếu.
