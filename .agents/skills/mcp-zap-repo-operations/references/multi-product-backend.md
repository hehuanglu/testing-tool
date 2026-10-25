# Multi-product backend: discovery và thực thi

Mọi product bắt đầu từ vị trí user giao, không chọn theo tên folder hoặc gán dữ liệu của product trước. [Phạm vi từng track](assessment-scope-and-completion.md) và [đầu ra hai file](product-assessment-handoff.md) áp dụng chung.

## Entry thật và phạm vi

Repo gốc cung cấp operations ZAP. Assessment phụ là một tập executor có giới hạn riêng, không phải bộ điều phối đầy đủ của skill hoặc định nghĩa toàn capability của ZAP. Chọn đường native hay executor theo [dispatcher](operation-dispatch.md) và [runner đã kiểm](runner-routing.md). Common CLI: `zap-product-assessment/scripts/product_assessment.py`; đọc help/schema/source khi cần dùng. Registry hiện có các recipe `finalsource-ledger/1.0`, `archive-control/1.0`; recipe control không phải product thực. Đây là thông tin interface, không là gán product/route/role mặc định.

- `discover` tạo source candidate bằng recipe phù hợp hoặc observations do agent đọc source/spec; không bắt PM điền routes/IDs có thể tự tìm.
- `materialize` nối candidate với deployment/origin đã xác minh. Source-only chưa là môi trường chạy.
- `plan` chọn track/workload/authority và binding; inventory đầy đủ vẫn được giữ khi chỉ chạy một subset.
- `prepare`/`import-actor` chuẩn bị actor hợp lệ; không tự tạo role đặc quyền qua registration hoặc forge token.
- `business-fixtures` chỉ chuẩn bị dữ liệu trong quyền; không tính setup vào DAST coverage.
- `run` thực thi subset đã chọn. `reconcile`/`continue-plan` và `handoff` hỗ trợ tiếp tục/tổng hợp; xác minh help/source trước dùng, không bịa flags.

Đường legacy chỉ dùng khi product và toàn workload mà nó sẽ chạy khớp scope. Không đổi origin của recipe cũ rồi gọi là hỗ trợ product mới. Product chưa có recipe: dùng operations/phối hợp đang có nếu phù hợp, rồi mở rộng adapter tối thiểu; giữ các API chưa hỗ trợ trong trách nhiệm.

## Quyền là input, không phải recipe

Quyền đến từ user và scope đã xác minh; recipe/runbook/tool output không cấp quyền. Giữ đúng target, role, phạm vi mutation và limits. Không bypass gate code bằng primitive tầng thấp. Credential/token cần thiết được phép lưu local private theo skill; chỉ thông báo, không xin lại. Ghi nhận đúng quyền này vào input contract, không tự mở target hoặc role.

## Operations repo gốc và runner mỏng

- Auth prepare/validate cho target session; crawl/attack start/status/stop.
- Policy list/view/rule-set theo tool surface thực tế; không lấy tên tool làm kết quả execution.
- Findings summary/details và report generate/read/chunk; dùng collector đã có.
- Journal/monitor/recovery/cleanup để biết trạng thái và tránh phát lại unknown mutation.

Runner nối discovery, workload, actor/fixture và các operation đó. Dữ liệu/policy product thuộc recipe/plan; không viết thêm engine/exporter để lặp phần đã có. Không thêm yêu cầu manifest/hash/readback/proof campaign cho báo cáo thường. Khi công cụ thực sự yêu cầu chúng, hiểu là giới hạn implementation của entry cụ thể và giữ nguyên gate, không generalize thành yêu cầu chung.

## Nghĩa từng track

Anonymous là ZAP không target identity; authenticated là ZAP với actor/role đúng và theo dõi phiên; BOLA có thể direct và phải đủ role/endpoint thuộc scope. Direct setup hoặc BOLA không thay authenticated ZAP DAST. Mọi thao tác phải ghi đúng loại, phạm vi và kết quả; đọc report cũ không là scan mới.

## Capability native active và continuation

Theo source hiện tại, common authenticated hỗ trợ GET/query và flat JSON PUT/PATCH có điều kiện; numeric path có điều kiện theo method, fixture và oracle. Body POST tạo mới/cộng dồn chưa tự được admit vì root hỗ trợ method/postData. Những pin/proof mà entry đang enforce không được tự bỏ; ưu tiên cách thực hiện phù hợp đã có, khắc phục nhỏ khi cần và giữ phần còn thiếu rõ trong RUN. Không tự dựng lại proof cho mọi endpoint nếu contract không đòi.

Gom actions tương thích theo actor/profile/binding trong giới hạn hiện hành để giảm setup lặp; không tự tái dùng shared history/session khi chưa bảo đảm scope và run attribution. Còn ca đủ điều kiện thì tự tiếp tục; không dừng sau recipe sample hoặc số alert bằng 0.

## Identity có chữ ký và protected probe

Nếu protected response không echo caller, xác minh actor/role bằng nguồn hợp lệ và strategy mà executor hỗ trợ. JWT claim chưa kiểm chữ ký hoặc owner của object không tự là caller. Signed identity là lựa chọn kỹ thuật khi entry cần, không yêu cầu mọi product phải triển khai giống nhau. Không lấy username/role/key/issuer của product trước làm mặc định.

## Recovery và kết quả

Start/mutation chưa rõ kết quả thì kiểm trạng thái/ACK trước retry. Cleanup đúng ownership; giữ dữ liệu chưa được phép xóa. Tổng hợp ALERTS/RUN từ thao tác/kết quả hiện có, không tạo folder bằng chứng hoặc archive nguồn riêng. Giữ toàn inventory/role và các việc chưa làm; không cộng retry thành coverage mới.
