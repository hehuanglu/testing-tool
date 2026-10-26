# Discovery → câu hỏi → kỹ thuật → readback → reconcile

Thực hiện vòng này cho từng track theo [workflow tuần tự và tự kiểm](sequential-track-workflow.md). Nhiều track trong scope không là lý do chạy tất cả scans trước rồi mới đọc/triage output; thu và tự kiểm cặp ALERTS/RUN của track hiện tại trước khi chuyển tiếp.

## Discovery độc lập findings

Xác minh source roots user chọn; đọc AGENTS, kiến trúc/spec/config sẵn có và Git revision/dirty nếu có. Dùng `rg --files` rồi search có mục đích; phân biệt source, vendor/generated/tests/config theo nhiệm vụ. Không cài dependencies hoặc build chỉ để đọc source.

Inventory gồm HTTP handlers (method–route), GraphQL/RPC operations, jobs/event handlers, libraries, FE surfaces và config khi liên quan. Ghi module/function, locations, discovery source/certainty, track và scope decision. Không lấy một URL GraphQL hoặc vài matches làm toàn inventory. Public/protected lấy từ routing/guards có thật và ghi độ chắc chắn; không là runtime login test.

Theo luồng input → xử lý → sink/response/persistence; xác định principal, object/tenant/relation/state và controls. Shared code map về surfaces/callers thuộc scope, một root cause không nhân thành nhiều bugs chỉ vì nhiều callers. Discovery owner như account/organization/workspace/member chỉ là ví dụ; tìm model/schema và repository implementation thực, không giới hạn theo whitelist tên.

Đọc `.semgrepignore`, `.gitignore`, `nosemgrep`, config/rules/scripts trước dùng. Exclusions có sẵn không tự là scope user chấp nhận. Inventory source bị ignore/unsupported vẫn giữ trách nhiệm cần xử lý.

## Question instances

Đọc [base được chọn](track-intents.md); mỗi instance ghi trong RUN:

- `id`, `base_question_id` (null cho câu hỏi phát sinh), `track_id`, `surface_ids` nối inventory.
- Câu hỏi cụ thể bằng chức năng/source: ví dụ “download invoice dùng tên file từ job payload có thoát thư mục export không?”, không chỉ “path traversal”.
- `expectation` và `expectation_source`: policy/spec/config được cung cấp, hoặc giả định từ source có nhãn rõ.
- `techniques`, rule selection/search/manual review, giới hạn; `round_ids`, `manual_review_ids` khi đã làm.
- `result`, `status`, `next_step`: điều đã quan sát, kết luận ở mức giao và bước cần thực hiện tiếp.
- `closure_condition`: điều kiện đủ trả lời đúng claim, không chỉ exit 0/zero matches; `recorded_at`, `introduced_after_round_id` (null khi trước lượt), `changes` ghi thời điểm/lý do đổi câu hỏi hoặc kỹ thuật.

Không copy base nhãn thành câu trả lời. Applicability từ feature/surface; thiếu rule hoặc policy không tự N/A. Không cần tích mọi field × rule × actor × state nếu không thay đổi câu hỏi.

### Checkpoint local trước execution

Lưu phần scope, source state, inventory và questions đã biết trong RUN trước khi bắt đầu round. Fields chưa quan sát để null hoặc trạng thái open có lý do do tester chọn. `round_ids`/`manual_review_ids` chỉ liên kết thao tác có thật, không invent một round tương lai. Có thể dùng [khởi tạo bản ghi](../scripts/report_records.py); draft còn null không là handoff đã hoàn tất. Không thêm file giao nộp hoặc checkpoint xin phép. Chưa biết hết inventory không cản discovery/phép kiểm độc lập.

Khi readback làm phát sinh nhánh mới, tạo instance với `introduced_after_round_id` và thời điểm thật; khi đổi kỹ thuật/expectation ghi `changes: [{at, after_round_id, field, previous, current, reason}]`. Không sửa lịch sử thành mọi câu hỏi đều đã dự kiến. Không bắt snapshot/hash để xác nhận checkpoint.

### Khi nào tách instance

Tách nếu trust source, action, control, persistence/consumer, expectation hoặc điều kiện khép khác nhau và có thể thay đổi kết luận. Ví dụ create/update có overwrite order khác; enrollment, login verification và bcrypt configuration; detail/update/delete, collections/counts và relation linking. Một nhánh resolved không che nhánh còn thiếu review. Có thể gộp khi cùng implementation/control và ghi mapping callers đủ chứng minh tính dùng chung. Không mặc định sáu instances/track hoặc sinh tích Descartes.

Các track có mẫu ledger riêng; operator hoàn thiện trong `questions[].result` dạng object hoặc `manual_reviews[].observations` trước bàn giao track, nối inventory/question/thao tác có thật. Không để tới một lượt senior khác mới bổ sung operation/UI/config mapping. Ledger có thể nhóm callers dùng chung control khi có căn cứ; không bắt một khuôn số hàng hoặc thêm collection báo cáo ngoài RUN.

## Chọn và thực thi

Xem [catalog](rule-catalog.md), inspect repo/local rules, đọc language/path/pattern/engine/privacy trước chạy. Có thể dùng Semgrep inventory, taint, search và manual source review phối hợp. Với Python/Java/Go không báo sạch từ TS rules: tìm local rules phù hợp, viết rule nhỏ có fixtures khi hữu ích, đọc source phần làm được, giữ gaps cần capability khác.

Search/inventory match ghi inventory/câu hỏi; chỉ tạo security observation khi mô tả được nghi vấn bảo mật. Khi chưa đủ căn cứ thì needs-review, không ép thành vulnerability. Custom mapping nằm ngoài core; không tải remote rules hoặc đổi engine để khép track.

Chia rounds trong track theo targets/câu hỏi/tài nguyên; mặc định track nào thu/triage/tự kiểm xong output track đó. Chỉ gộp execution nhiều track khi user yêu cầu cách vận hành đó, giữ mapping question/track và provenance thực. [CLI](semgrep-operations.md) ghi command, source state, rules, exclusions và dữ liệu thực, output mỗi round private riêng ngoài product. Tạm tách source lỗi không bỏ nó khỏi scope.

Đối soát `questions[].techniques` theo phép kiểm thực: native rule IDs/capability/targets và manual review tương ứng; có thể ghi dạng object trong mảng hoặc text có references đủ rõ. Không dùng cùng mô tả “đã scan YAML” cho mọi question. Manual-only question không được nhận native coverage chỉ vì cùng track; `round_ids` chỉ giữ thao tác native thực liên quan, không gắn hàng loạt để lấp fields. Sửa mapping sau readback thì ghi `changes`, không biến nó thành kế hoạch trước lượt.

## Đọc và tiếp tục

Đọc exit, JSON, errors/skips/timeouts và code, không chỉ summary matches. Triage đọc import/implementation của sanitizer/guard/repository, callers và effective overrides; tên `sanitize`, `user`, `verify` chưa chứng minh control. CE có giới hạn xuyên hàm/file: manual review có thể trả lời câu hỏi SAST nhưng phải ghi nguồn riêng, không cộng Semgrep coverage.

Đối chiếu mọi inventory/question với kỹ thuật thực đã làm theo [responsibility loop](responsibility-loop.md); thực hiện bước khả thi còn mở, tự kiểm riêng quy trình và evidence theo [workflow theo track](sequential-track-workflow.md), rồi bàn giao [hai file](reporting-and-completion.md) của track. Nếu user yêu cầu Semgrep thực thi cụ thể mà chỉ manual được, giữ phần yêu cầu chưa thực thi riêng. Retest xem diff/ignore/rules/source state, không sửa lịch sử hoặc gọi mất match là fixed.
