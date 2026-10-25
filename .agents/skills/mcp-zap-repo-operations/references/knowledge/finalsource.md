# Tri thức product finalsource

Kiểm gần nhất 25/10/2026 trên `finalsource-zap-test`. Chỉ áp dụng sau discovery xác nhận đúng product/deployment; routes, ownership và semantics ở đây không đưa sang core hoặc product khác. Không dùng IDs/date fixtures lịch sử làm default. Theo [kho tri thức](../operational-knowledge.md) để cập nhật.

## Goal uniqueness và hiển thị UI là hai điều kiện khác nhau

- Source/runtime đã quan sát: Expense goal có uniqueness theo user/category/period. Lặp category–kỳ đã dùng có thể trả HTTP500. Goals list/UI hiện tại chỉ hiển thị kỳ hiện tại; future-period INSERT thành công không tự cung cấp UI Adjust journey. [Giai đoạn 4](</Users/hahoangloc/Working/testing tool/review/finalsource-phase4-20261025/PREREQUISITE_UPDATE.json>), [giai đoạn 5](</Users/hahoangloc/Working/testing tool/review/finalsource-phase5-20261025/HOAN_THANH_GIAI_DOAN_5.md>), [allocation giai đoạn 6](</Users/hahoangloc/Working/testing tool/review/finalsource-phase6-20261025/GOAL_ALLOCATION.json>).
- Quyết định trước create: kiểm persisted owner/category/occupied periods hiện tại và yêu cầu hiển thị của ca. Chọn fixture mới đúng quyền hoặc reuse được phép; nếu cần current-month UI, không chỉ dời goal sang tương lai để insert được. Giữ fixture cũ không cấm chuẩn bị fixture mới; không sửa goal lịch sử để ép test.
- Khi mất ACK hoặc trả lỗi sau gửi, reconcile state trước retry. Thay DTO/unique index/list filter hoặc thời gian chạy thì xác minh lại. Không diễn giải hết fixture allocation là ZAP không hỗ trợ goal.

## Category và bill populated setup

- Runtime đã chạy category fixture riêng và transaction/aggregate A/B populated ở giai đoạn 3. Bills của actors trong giai đoạn 6 rỗng; populated bill isolation **chưa vận hành**.
- Source đã đọc: `zap-product-assessment/src/zap_assessment/bola_research_db.py:FixtureDB` có preflight/observe và mode provision gồm category/bill inserts, cùng allowlist/budget; `scripts/prepare_finalsource_category_fixture.py` là entry category đã dùng. Có nhánh code không là quyền DB hoặc bill provisioning đã thành công trong các lượt này.
- Quyết định: đánh giá entry/caller, binding, quyền và tác động cả batch trước chọn; không chạy `provision` chỉ để lấy bill nếu nó còn tạo category ngoài workload. Ưu tiên setup đúng quyền hoặc adapter product tối thiểu; thiếu quyền thì nêu chính xác thao tác cần làm rõ, tiếp tục nhánh khác. Không mặc định thiếu API create là không có đường setup.
- BillsService lọc due date trong 30 ngày theo ngày runtime và owner; fixture dùng cho UI/list/isolation cần cả owner và kỳ phù hợp, dữ liệu A/B phân biệt được. Bills create UI destination hiện là unavailable, khác với populated bill read. Thay schema/permission/window thì kiểm lại; không tự thêm nghiệp vụ create bill cho product.

## Browser auth và JSON-bearer native

- Shared browser profile từng prepare được nhưng validate authentication_failed; credential hiện tại được kiểm bằng JSON login/protected principal và hợp lệ, nguyên nhân historical browser failure chi tiết chưa xác định. Regex public `success:true` chưa đủ identity. [Chẩn đoán giai đoạn 3](</Users/hahoangloc/Working/testing tool/review/finalsource-phase3-20261025/AUTH_DIAGNOSIS.json>).
- Quyết định: phân biệt browser acquisition/session verification với native bearer; đọc Valid/Outcome và protected behavior, không coi prepare ACK/isError:false là authenticated pass. Dùng đường compatible đã có để tiếp tục; không bật experimental shared hoặc suy toàn auth thiếu capability.
- UI actor/session và native scan identity cần xác minh riêng. Caller/source mapping, profile, credential hoặc deployment đổi thì kiểm lại; không đưa credentials vào kho tri thức.

## Semantics completion và policy

- Các cases BOLA giai đoạn 6 matched theo hypothesis từ source; đây không là policy nghiệp vụ được phê duyệt. Bill populated còn mở do chưa chuẩn bị fixture, không do đã gọi helper đúng rồi thất bại.
- Quyết định: giữ execution, coverage và policy assurance riêng. Đánh giá đường fixture trước dừng, không gán “thiếu independent approval” thành blocker chung. Các actor ordinary đã discovery không đại diện role đặc quyền chưa tồn tại trong inventory.

## Implementation sau audit PM (source/offline, chưa tái scan product)

`fe_authenticated_fixture_finalsource.prepare_data` hiện nhận nhu cầu setupRefs: owned-account tách native-account; category và bill tách INSERT/receipt theo phần yêu cầu. Reader đọc được cả receipt legacy và receipt theo nhu cầu. Cleanup theo exact owned ledger, không điều kiện đúng hai account. Các thay đổi này đã có regression offline; chưa gọi DB helper hoặc runtime FE mới sau sửa, không dùng các quan sát lịch sử ở trên làm qualification cho bytes mới. Cần runtime thuộc lượt được giao thì kiểm binding/quyền/owner và tác động helper trước gọi.
