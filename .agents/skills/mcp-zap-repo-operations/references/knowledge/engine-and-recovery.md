# Cơ chế và recovery cần kiểm tại lượt hiện hành

Tra theo [hướng dẫn kho tri thức](../operational-knowledge.md). Các điểm dưới là hướng dẫn vận hành; repo không đóng gói kết quả hoặc checkpoint của product đã kiểm trước.

## Cùng version nhưng khác schema

So schema actual, requiredness/type và auth/provider của deployment sẽ nhận request. Chọn executor tương thích; không gọi field ngoài schema. Version/tag không attest source-to-image. Exact method/body cần execution/readback hiện hành trước khi ghi observed; không suy authenticated session từ anonymous capability.

## Findings đầy đủ và report representatives

Dùng findings đọc đủ làm totals khi cần, report counts theo đúng semantics samples; giữ native classification/session/origin. Instance IDs không duy nhất xuyên session; không cộng retry thành finding mới. Thiếu paging/filter đủ thì giữ partial và xử lý primitive thiếu, không bịa offset.

Tái dùng `zap_assessment.report_reconciliation` và collector đã có. Truncated preview không parse như full document; theo EOF trước `nextOffset` (có thể null), offsets là code points. Dùng pages đã lưu để resume cùng artifact. Đổi add-on/template/filter/version thì kiểm lại semantics, không mặc định mọi mismatch có cùng nguyên nhân.

## Guard và budget khi producer chạy

Dùng ràng buộc key của runtime thực, kiểm script/containment trước producer và xử lý loss khi chạy. Không hạ guard/cap để ra payload. Baseline/control do engine phát sinh cũng có thể tiêu budget; đọc requests thực theo semantics workload trước sửa allocation. Không coi attempt lỗi là accepted DAST hoặc bắt qualification campaign mới cho mọi scan.

## Recovery và checkpoint nhất quán

Mutation đã ACK nhưng selector/assertion lỗi cần reconcile ACK/journal/state trước tiếp tục. Giữ attempt lỗi và một nơi tiếp tục chính thức, phân biệt attempt/revision; không dùng checkpoint lỗi làm lý do lặp create/delete. Không lấy timestamp mới nhất thay kiểm lineage.

Runtime đổi ephemeral port sau stop/start thì đọc lại mapping và client URL. Login/prepare mới sau cleanup không phải resume session cũ. Scope/identity/binding hiện tại phải kiểm lại.
