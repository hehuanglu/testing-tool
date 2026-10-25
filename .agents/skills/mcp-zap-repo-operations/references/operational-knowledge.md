# Tri thức vận hành dùng lại

Nơi lưu bài học đã kiểm từ các lượt vận hành, để thay đổi quyết định ở lượt sau. Đây là reference của skill, không phải nhật ký scan, nguồn quyền, policy nghiệp vụ hay trạng thái sống của product. Không thêm bước vào chuỗi vận hành; tra khi chọn executor, chuẩn bị fixture, recovery hoặc nối checkpoint.

## Tra theo vấn đề

- Schema/source/image khác nhau, exact body, native report samples, script guard, chunk/EOF và checkpoint: [cơ chế và recovery](knowledge/engine-and-recovery.md).
- Product **đã xác minh là finalsource**: category/bill setup, goal uniqueness và current-month UI, profile browser/JSON-bearer: [finalsource](knowledge/finalsource.md).
- Chọn operation/entry vẫn theo [dispatcher](operation-dispatch.md) và [runner mapping](runner-routing.md). Tri thức chỉ gợi ý đường cần kiểm, không thay contract/admission hiện tại.

Tìm theo triệu chứng và product; chỉ đọc entry liên quan. Kiểm lại origin/binding/version/source và điều kiện của entry trước dùng. Thông tin đúng ở một deployment không đại diện mọi deployment; tên/version giống nhau chưa bảo đảm cùng schema.

## Cách cập nhật sau vận hành

Mỗi bài học giữ ngắn: **điều kiện áp dụng → quan sát và mức xác nhận → quyết định dùng lại → kiểm lại khi nào → nguồn đã có**. Ghi ngày kiểm gần nhất và giới hạn chưa biết. Kết luận từ source, runtime và giả thuyết phải phân biệt; không nâng source-supported thành execution-confirmed.

Sửa/bổ sung entry đang có thay vì chép thành nhật ký mỗi phase. Khi cơ chế không còn đúng, ghi entry bị thay thế và điều kiện mới; không xóa kết quả/raw lịch sử. Bài học chưa có execution có thể lưu như giả thuyết cần kiểm, nhưng phải gắn nhãn đó. Chỉ tách entry/product mới khi có kiến thức thực sự ảnh hưởng quyết định.

Không lưu credential/token/cookie, dữ liệu cá nhân, full request/response hoặc object ID/session ID làm default. Chỉ dẫn source/working result đã có khi hữu ích; không đòi proof/hash bundle mới. Owner/role/expected của product ở entry product; cơ chế dùng chung không chứa giả định finalsource. Khả năng setup không tự cấp quyền mutation/DB hoặc quyền sang target khác.

Trạng thái hiện tại và phần còn mở vẫn ở RUN/journal được chỉ định; kho này không thay checkpoint. Không bắt mỗi run phải tạo một entry hoặc chạy helper dưới đây.

## Helper rà soát tùy chọn

`../scripts/review_open_work.py` chỉ đọc JSON caller ánh xạ từ inventory/plan/RUN đã có; không đổi schema executor hoặc bộ đầu ra hai file. Dùng khi cần kiểm quyết định/tiếp tục một cách lặp lại, không là gate bắt buộc:

```sh
python3 .agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py work --input /absolute/work-review.json
python3 .agents/skills/mcp-zap-repo-operations/scripts/review_open_work.py checkpoint --checkpoint /absolute/checkpoint.json --current /absolute/current-state.json
```

Input `work`: `responsibilities` là inventory trách nhiệm độc lập, mỗi mục có `id`, `requiredObservations` (các loại quan sát thực sự cần, không phải mọi kỹ thuật). `observations` map ID sang danh sách loại đã quan sát, hoặc `{completed: [...], outcomeUnknown: true}`. `decisions` map ID sang `{action, basis, nextStep}` cho `execute/repair/prepare-fixture/reconcile`; `dependency` cần thêm `diagnosis`, `optionsEvaluated` (mỗi option có `option`, `basis`) và `blockedBy`. `not-applicable` cần `applicability`; `user-excluded/outside-assignment` cần `scopeBasis`. Chỉ đưa dữ liệu đã lọc secret, không đưa raw native report vào helper.

Helper chỉ review; [vòng có execution/readback](responsibility-loop.md) xử lý action trước bàn giao. Helper trả `unresolved`, `nextActions`, `openWorkWithDecisions`, `workComplete`, `allOpenWorkHasGroundedDecision` và `canHandOffPartial`. Kế hoạch execute/repair chưa làm vẫn ở `nextActions`, không trở thành work complete hoặc điểm bàn giao. Quyết định chỉ có lý do chung chung hoặc thiếu diagnostic cần bổ sung. Outcome unknown cần `reconcile`; nếu đã chẩn đoán không thể reconcile trong quyền hiện có, `dependency` phải giữ `unknownOutcomeRetained:true`, nguyên nhân và điều kiện tiếp tục, không cho phép replay. Một inventory rỗng trả chưa đủ dữ liệu, không pass. Helper kiểm cấu trúc/logic của dữ liệu đã khai báo, **không xác nhận tính đúng của căn cứ, đầy đủ inventory, policy hay quyền**; agent phải đối chiếu thực tế. Exit 1 khi còn unresolved/next actions hoặc checkpoint cần reconcile; exit 2 cho input không đọc/parse được; exit 0 không tự là nghiệm thu hay quyền chạy.

Input `checkpoint/current` là hai snapshot cùng run caller cần so: `product`, `environment`, optional `runId/attemptId/origin`, `operations`, optional `requestCount/executionStatus/finishedAt`. Count/status/binding/operation lineage khác hoặc outcome unknown yêu cầu reconcile; không chọn bản nhiều requests hơn làm bản đúng. Helper không merge, sửa file, cập nhật checkpoint, chạy tiếp hay cho phép replay. `requiresReconciliation:false` chỉ là không phát hiện mâu thuẫn trong fields đã so, không phải trạng thái sống hoặc quyền dispatch.
