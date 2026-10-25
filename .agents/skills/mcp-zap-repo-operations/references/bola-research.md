# BOLA: đủ role và quyền trên object

Điểm xuất phát nghiệp vụ và scope ở [track intents](track-intents.md); chọn operations/executor theo [dispatcher](operation-dispatch.md). Reference này bổ sung chi tiết của entry hiện có, không mở rộng nhiệm vụ hoặc bắt chạy qualification.

BOLA là nhánh riêng khi được user giao/chọn; không thay hai track DAST BE. Dùng [discovery](product-discovery.md), [multi-product](multi-product-backend.md) và [scope](assessment-scope-and-completion.md); output [ALERTS/RUN](product-assessment-handoff.md).

## Chọn ownership cases và đọc kết quả

Lập matrix tất cả endpoint–role thuộc scope; xét đủ role đã discovery, role đặc quyền và anonymous khi liên quan. Với từng mục, xác định object/action, owner/relation/state, ID ở path/query/body và kết quả kỳ vọng từ policy/spec/source hiện có. Không hardcode role/route/ID/state/số ca của product mẫu.

- Object có owner: owner-positive, non-owner/cross-owner và role được cấp quyền hoặc bị cấm; dữ liệu trả về và thay đổi trạng thái liên quan.
- Create/update/delete và business action: kiểm kết quả thực tế, object/owner và side effect cần thiết; ID tài nguyên mới lấy từ ACK/readback, không chọn ID để pass.
- List/filter/pagination: kiểm isolation và role scope; không dùng collection rỗng thay populated case khi cần kiểm dữ liệu.
- Role có quyền xử lý object của nhiều owner khác shared/public catalog; tách function-level access với object ownership.

Thiếu tài khoản/fixture/policy là mục còn mở theo endpoint–role, không N/A. Không bắt mọi tổ hợp tenant/race/state vô hạn; giữ những relation/state làm thay đổi quyền. Không chỉ làm owner-positive hoặc một role rồi gọi track complete. Xem [ownership sâu](auth-lifecycle-and-bola-depth.md#chọn-câu-hỏi-ownership-sâu) khi nhiệm vụ cần.

## Đường thực thi policy, identity và state

Direct-client đúng scope được dùng; ghi nguồn direct, không giả native ZAP alert. Common CLI có compile_cases/execute/checker; borrowed legacy v1.4 read-only vẫn read-only. Kiểm capability thực trước chọn entry và không đổi origin của adapter cũ cho product khác.

Xác minh account/role từ nguồn hợp lệ, không forge quyền hoặc lấy owner làm caller. Expected được xác định trước thao tác từ policy/spec hoặc giả định source đã nêu, không sửa theo observed response để khớp. Policy suy từ chính source chưa là xác nhận policy nghiệp vụ đúng; kết quả matched phải diễn giải trong giới hạn đó.

## Thực thi theo entry đã chọn

Chuẩn bị fixture hợp lệ trong scope, ghi object/owner/state cần dùng, chạy case, đọc response và trạng thái liên quan, đối soát matrix rồi tiếp tục phần thiếu. Unknown mutation cần xác minh trước retry; không replay để sửa checkpoint. Dùng lại identity/transport/journal/checker có sẵn, sửa mapping/orchestration tối thiểu nếu cần, không tạo engine mới hoặc checker trả pass cố định.

Không bắt bộ policy receipts, source archive, manifest/hash, independent checker campaign hoặc report ZAP cho BOLA direct. Gate đang có trong entry vẫn thực hiện; đó không là lý do để thêm các gate assurance của skill cho toàn nhiệm vụ. Đọc help/source của `scripts/product_assessment.py` hoặc `scripts/bola_research.py` trước chọn đường legacy; không bịa flags.

## Kết quả và tiếp tục

RUN chứa matrix endpoint–role đầy đủ, cases/thao tác thực tế và response/state/kết quả, giả định policy, hạn chế và phần chưa làm. ALERTS chứa discrepancy/finding nguồn direct với mức độ xác nhận trung thực; không biến no discrepancy thành product an toàn. Không có phần/folder evidence trong bộ kết quả. Còn role/API quan trọng chưa chạy thì nhiệm vụ partial; tự tiếp tục phần đủ điều kiện.
