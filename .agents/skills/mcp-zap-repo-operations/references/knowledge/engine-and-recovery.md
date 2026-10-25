# Bài học cơ chế và recovery

Kiểm gần nhất 25/10/2026. Tra theo [hướng dẫn kho tri thức](../operational-knowledge.md). Source/artifact hiện tại có thể đổi; kiểm lại trước dispatch.

## Cùng version nhưng khác schema

- Quan sát runtime/artifact: shared finalsource scanner version `0.16.0` không có `method/postData`; candidate có chúng và đã thực hiện PUT JSON body. Căn cứ: [kết quả giai đoạn 2](</Users/hahoangloc/Working/testing tool/review/finalsource-phase2-20261025/EXACT_BODY_RESULT.json>).
- Quyết định: so schema actual, requiredness/type và auth/provider của deployment sẽ nhận request. Chọn executor tương thích; không gọi field ngoài schema hoặc thêm lại Java input đã có trong source.
- Giới hạn: exact PUT đã chạy không nghiệm thu mọi body/method; candidate exact body cần auth/direct semantics phù hợp. Không giả authenticated session cho anonymous. Build/registration thay đổi thì so lại; version/tag không attest source-to-image.

## Findings đầy đủ và report representatives

- Quan sát trên ZAP 2.17.0: reproduction scanner network-none cho 8 findings → 5 report samples; full findings trước/sau không đổi. [Reproduction giai đoạn 1](</Users/hahoangloc/Working/testing tool/review/finalsource-phase1-20261025/REPRODUCTION.json>). Đây là cơ chế sampling/grouping đã kiểm ở workload/version này, không chứng minh mọi report mismatch có cùng nguyên nhân; lineage report-only ID cũ vẫn chưa rõ.
- Quyết định: dùng findings đọc đủ làm totals khi cần, report counts theo đúng semantics samples; giữ native classification/session/origin. Instance IDs không duy nhất xuyên session; không cộng retry thành finding mới. Thiếu paging/filter đủ thì giữ partial và xử lý primitive thiếu, không bịa offset.
- Tái dùng `zap_assessment.report_reconciliation` và collector đã có; không chép lại parser. Truncated preview không parse như full document; theo EOF trước `nextOffset` (có thể null), offsets là code points. Dùng pages đã lưu để resume cùng artifact, không scan lại để sửa parsing. Đổi add-on/template/filter/version thì kiểm lại semantics.

## Guard và budget phải khỏe khi producer chạy

- Quan sát giai đoạn 4: ScriptVars key quá dài gây native script error và sibling drift; một lần reload còn có containment probe chưa áp dụng. Attempt lỗi không được tính accepted selected-field DAST. [Checkpoint giai đoạn 4](</Users/hahoangloc/Working/testing tool/review/finalsource-phase4-20261025/HOAN_THANH_GIAI_DOAN_4.md>).
- Quyết định: dùng ràng buộc key của runtime thực, kiểm script/containment trước producer và xử lý loss khi chạy; script cố định + config cập nhật là phương án đã dùng trong adapter đó. Không hạ guard/cap để ra payload. Baseline/control do engine phát sinh cũng có thể tiêu budget; đọc requests thực theo semantics workload trước sửa allocation.
- Giới hạn: không quy mọi lỗi thành reload race; không bắt qualification campaign hoặc generic guard mới cho mọi scan. Kiểm phần thay đổi trong entry hiện có.

## Rule có 0 request và điều kiện áp dụng

- ByteMe, ZAP 2.17.0/ascanrules 84.0.0: PUT trước đó chọn reflected-XSS 40012 với threshold MEDIUM có 0 request; lượt mới dùng LOW alert threshold có 25 application requests từ rule đó. [Source rule](https://github.com/zaproxy/zap-extensions/blob/main/addOns/ascanrules/src/main/java/org/zaproxy/zap/extension/ascanrules/CrossSiteScriptingScanRule.java) có nhánh return cho PUT nếu threshold không LOW. Source hiện hành và kết quả runtime cùng hỗ trợ chẩn đoán này; kiểm lại khi version/config thay đổi.
- Quyết định: phân biệt strength với alert threshold, kiểm điều kiện rule trước gọi là lỗi engine hoặc N/A toàn PUT. Unit của câu hỏi XSS phải đi qua reconciliation riêng. JSON reflection mức Low không chứng minh browser execution. Đường dùng helper/reader ở [operational readback](../operational-readback.md); không lấy kết quả SQLi để cấp unit XSS.

## Recovery không replay và checkpoint nhất quán

- Quan sát: UI mutation đã ACK nhưng selector/assertion hỏng được reconcile rồi tiếp tục; checkpoint giai đoạn 6 có status/count cũ lẫn operations mới. [Đối soát chỉ đọc](</Users/hahoangloc/Working/testing tool/review/finalsource-operating-responsibility-audit-20261025/READBACK_CHECK.json>).
- Quyết định: giữ attempt lỗi, reconcile ACK/journal/state; ghi một nơi tiếp tục chính thức nhất quán, phân biệt attempt/revision. Không dùng failed checkpoint làm lý do lặp create/delete. Không lấy timestamp mới nhất thay kiểm lineage.
- Runtime riêng đổi ephemeral port sau stop/start: đọc lại port mapping và tạo client URL mới; login/prepare mới sau cleanup không phải resume session cũ. Scope/identity/binding hiện tại phải kiểm lại.
