# Vận hành và tự kiểm từng track

Đây là workflow mặc định cho assessment, không là một chiến dịch đánh giá thêm. Operator dùng Semgrep và đọc source, đồng thời chịu trách nhiệm tự kiểm quy trình và evidence. Không cần senior/agent khác, không tự spawn reviewer; tự kiểm không được gọi là independent evaluation.

## Chọn scope và thứ tự

Chỉ vận hành các track được scope cho phép. Với assessment toàn product, discovery quyết định applicability; ưu tiên be-input → fe-browser → authentication-session → authorization-ownership → configuration-build khi không có phụ thuộc cần đổi thứ tự. Nêu thứ tự/lý do điều chỉnh. Targeted scan, candidates-only và retest giữ đúng phạm vi riêng.

Discovery chung/source state/control đã đọc có thể dùng lại, nhưng phải ghi nguồn và kiểm còn phù hợp với track/source state hiện tại. Mặc định thực thi track hiện tại xong phần local khả thi, đối soát và lưu output rồi mới thực thi track kế tiếp. Không chạy trước cả năm scan rồi mới triage. Một track có thể có nhiều rounds/manual reviews; không cố định một scan hay toàn bộ bundled rules cho mỗi track.

Chỉ gộp execution nhiều track khi user yêu cầu; vẫn đối soát từng question/track và ghi native provenance có thật. References trong mỗi assessment phải khép kín, không trỏ ID của assessment khác như thể record cùng RUN. Khi tái dùng output có thật, giữ command/time/source state và nguồn tái dùng; không dựng round mới đã thực thi.

## Một vòng track

1. **Discovery và tuyên bố:** từ source/spec/config, xác định surfaces/callers, input/identity/object/state hoặc consumer/precedence cần kiểm. Kiểm ignore/path/language và scope; không dùng matches làm inventory. Mỗi entrypoint phải gắn đúng module/class/handler/registration, không lấy decorator đầu file làm routing cho mọi class trong file.
2. **Checkpoint trước execution:** lưu RUN chứa source state, inventory/questions đã biết, expectation/source, closure condition và techniques dự kiến. Chưa biết để null/open. Không prefill round/manual IDs chưa có hoặc viết kết luận trước scan. Nhánh phát sinh ghi thời điểm và `introduced_after_round_id`; đổi mapping/kỹ thuật ghi `changes`.
3. **Chọn và chạy:** đọc local rules, mapping applicability theo từng question; chọn targets và phép kiểm nhỏ nhất phù hợp. Kỹ thuật native và manual tách riêng. Question không có detector phù hợp vẫn giữ trách nhiệm manual/custom-rule, không nhận blanket coverage của YAML.
4. **Thu và đọc output:** mỗi round giữ command/cwd/targets/time/exit, native JSON/stdout/stderr và metadata thực trong private area. Đọc results/errors/timeouts/paths/skipped_rules và logs. Chỉ biết configured thì không điền loaded/executed/actual engine. Đối chiếu requested targets/inventory với native scanned paths: file vắng dù skipped=[] vẫn cần chẩn đoán/review, không biến thành negative pass.
5. **Triage:** giữ từng native result index trong ledger RUN, kể cả inventory-only candidates và observations được đưa vào ALERTS. Đọc source/callers/receiver/controls trước disposition. Tái dùng review cùng control/call path được phép, nhưng giữ từng index/rule/location và lý do grouping; không tự gộp issue vì cùng dòng/rule. Manual findings không có native occurrence giả.
6. **Reconcile scope:** dùng ledger phù hợp track trong question result/manual observations để nối inventory → câu hỏi → kỹ thuật thực → control/use/write → kết quả. Tách nhánh khi control/expectation/consumer khác. Thực hiện bước local còn khả thi theo [responsibility loop](responsibility-loop.md); chỉ giữ external dependency/blocker cụ thể.
7. **Tự kiểm hai chiều:** trả lời hai câu hỏi bên dưới, sửa thiếu sót còn làm được, rồi lưu ALERTS/RUN và status thực. Ghi ngắn kết quả track/phần mở cho user; không chờ xác nhận để tiếp tục track độc lập kế tiếp.

## Quy trình đã đủ cho phát biểu và scope chưa?

Đối chiếu applicability/inventory với mức nhiệm vụ thực được giao, không với số rules hoặc số findings. Ledger cần chỉ ra các operation/nhánh có thể đổi kết luận:

- Backend: input → validator/transform → query/execution/resource/disclosure sink → response/write; create/update và parameters/SQL text xét đúng nhánh.
- Browser: route/component → input → render/navigation/storage/API consumer; UI guard khác server enforcement, server chỉ kết luận theo source/control đã đọc.
- Authentication: enrollment, login verification, hash config, issue/verify/principal và lifecycle có thật; threshold heuristic khác policy, client cleanup khác revoke.
- Authorization: actor/action → object/collection/count/reference/state → predicate/check → use/write; xác định receiver và cả referenced resources, không khép collection bằng detail check.
- Config/build: file → consumer/load path → defaults/overrides/precedence → layer/final stage; lockfiles/config bị filter vẫn thuộc inventory khi scope liên quan.

Ghi phần đã trả lời ở mức source và phần thực sự phụ thuộc policy/runtime. Scope source có thể completed dù có supported issue hoặc runtime chưa được kiểm; needs-review còn cần triage theo nhiệm vụ thì question open và track partial. Không đòi mọi policy mới cho phép bàn giao. Thiếu policy không miễn các source steps còn làm được, không tự N/A/false-positive/accepted risk.

## Evidence đã đủ hỗ trợ danh sách observations chưa?

- Đối chiếu **toàn bộ native indexes** của từng round với ledger/disposition và occurrence links nếu được đưa vào ALERTS; không để matches biến mất sau grouping/triage. Native matches, observations, occurrences và unique issues khác đơn vị; không áp một phép cộng khi mapping nhiều–nhiều hoặc chưa biết dedup.
- So rule ID/path/start/end/message/severity/confidence của native records với output thật. Mất field để null, không suy từ tên rule hoặc log summary. Nội dung nhạy cảm được redact có ghi chú, không sửa nghĩa native message.
- Đọc lại vị trí source chứng minh claim/control, không chỉ kiểm file tồn tại hoặc line trong bounds. Một range trỏ closing brace hoặc thiếu đoạn check/use không tự chứng minh claim. Dataflow/call-path cần các bước source đã đọc; manual path luôn manual provenance, native-dataflow chỉ khi output thật có trace đã đọc.
- Kiểm evidence/source state/round/manual review cùng nguồn, IDs và backlinks; checkpoint/questions phát sinh đúng thời điểm. Source đổi thì đánh giá lại phần ảnh hưởng, không bắt hash/snapshot hoặc đọc private-key bytes chỉ để có một nhãn integrity pass.
- False-positive cần implementation/control thực. Supported chỉ theo claim đã viết; discrepancy tài liệu–source phải giữ authority/currentness và permitted claim, không tự thành requirement violation/runtime exploit. Needs-review giữ gaps và next step cụ thể.
- Chạy [checker liên kết](../scripts/check_report_links.py) khi dùng được, rồi kiểm sự thật source/native như trên. Checker pass chỉ là bookkeeping, không thay review ngữ nghĩa hoặc đo recall. Evidence đủ cho records hiện tại không chứng minh danh sách không bỏ sót mọi lỗi.

## Output và chuyển track

Mặc định mỗi track có `<assessment-root>/<track-id>/ALERTS.json` và `RUN.json`, ở ngoài product, không overwrite lịch sử. Raw/log/rules/settings giữ private riêng ngoài targets; ghi rõ nếu working area tạm có thể bị dọn. Tự kiểm nằm trong `tracks[].review` theo [reporting](reporting-and-completion.md), không thêm file giao nộp thứ ba hoặc approval gate.

Có thể chuyển track khi output hiện có đã thu/đọc và phần local khả thi đã xử lý, dù track partial/blocked vì dependency đã ghi. Chưa chạy thì native counts null; output thiếu không gọi zero. Track sau không xóa trách nhiệm/phần còn mở của track trước. Nếu có điều kiện/source/policy mới trong scope cho phép tiếp tục, mở round/review mới và giữ lịch sử.

Nếu user yêu cầu đánh giá skill riêng, tổng hợp hai chiều quy trình/evidence từ các track, tách trạng thái đánh giá với trạng thái assessment. Ghi rõ self-review, senior-assisted hay independent reviewer thực có. Không copy verdict/counts của product trước, không tự thêm oracle campaign, proof run, benchmark hoặc đánh giá độc lập khi chưa được giao.
