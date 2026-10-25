# Chọn phần kiểm tiếp theo theo product

Áp dụng [scope](assessment-scope-and-completion.md): nghiệp vụ/API/role thuộc nhiệm vụ chưa làm vẫn là trách nhiệm, không thành optional vì khó. Chọn thêm kỹ thuật ngoài nhiệm vụ chỉ khi có giá trị và trong quyền/budget.

## Chọn câu hỏi và phần tiếp theo

Từ mục tiêu, source/spec và kết quả đã có, chọn input/risk/role/state cần kiểm; map vào operation sẵn có và baseline/fixture cần thiết. Ghi giới hạn và kết quả nào đủ trả lời; không đặt risk score hoặc số lượng request/rule để gọi đủ. Không đòi một proof campaign mới cho mỗi lựa chọn.

## Anonymous

Giữ toàn public API, kể cả public auth. Ưu tiên input/validation có nghĩa; tách xử lý credential khỏi input bị validation chặn sớm. Public token trả về không tự truyền tiếp. Không tự mở lockout/DoS/all-rules chỉ để tăng coverage. Request mẫu/passive không thay active phù hợp trong mục tiêu DAST.

## Authenticated

Giữ toàn protected API và role có hành vi khác biệt. Chọn query/body/path/header theo input thực; header nghiệp vụ khác credential. Seed chứa ID không tự là active path fuzz. Mutation dùng dữ liệu hợp lệ và kiểm trạng thái liên quan, không gán scope query thành body hoặc DELETE seed thành active DELETE. Chọn entry phù hợp trước tạo fixture; giữ dependency còn thiếu rõ trong RUN.

## BOLA

Khi được giao, xét tất cả endpoint–role và đủ role discovery. Owner-positive/cross-owner, quyền chức năng, collection isolation và state/relation quan trọng phải được xử lý; không chọn object dễ rồi bỏ nghiệp vụ lõi. Không dựng tenant/shared/role mà product không có. Relation rỗng khác populated; kết quả relation này không đại diện relation kia. Findings nguồn direct giữ riêng với ZAP.

## Fixture chỉ cho case đã chọn

Tìm API chuẩn bị/readback hợp lệ, owner/state, payload và quyền. Tái dùng fixture còn phù hợp nếu entry cho phép; nếu cần fresh thì tạo trong scope, không mượn ID lịch sử theo suy đoán. Kiểm kết quả mutation ở mức đủ biết thao tác thực tế và side effect quan trọng. DB không phải prerequisite mặc định và không thay API/ZAP coverage; không tự sửa DB/product.

Chuẩn bị dữ liệu sau khi biết đường thực thi phù hợp để tránh tạo fixture rồi bỏ vì capability không hỗ trợ. Phần chưa làm vẫn giữ dependency và bước tiếp. Cleanup chỉ bằng quyền/resource thực có, không hứa xóa dữ liệu khi API không hỗ trợ.

## Điểm dừng

Sau mỗi lượt ghi thao tác/kết quả, đối soát inventory/role rồi tự tiếp tục ca đủ điều kiện. Không mở kỹ thuật/lifecycle ngoài mục tiêu để xóa mọi unknown. Đến blocker thật sau khắc phục trong quyền/tài nguyên thì báo partial và điều kiện tiếp tục, không coi blocker là hoàn tất.
