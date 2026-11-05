# Định hướng đã thống nhất của skill MCP ZAP

Ngày cập nhật: 03/11/2026, Việt Nam. Danh mục 32 mục đã được người dùng định hướng; không còn là questionnaire chờ trả lời. Chính sách vận hành nằm trong [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>). C01–C10 được giao cho coordinator quyết theo từng sản phẩm, không có nghĩa đã có sẵn facts của mọi sản phẩm.

Các mô tả “Trước định hướng” dưới đây giữ bối cảnh của bản rà soát trước; “Định hướng” và “Cách áp dụng” là trạng thái hiện hành. Các đề xuất cũ trái với quyết định người dùng không còn là hướng dẫn. Không thay code executor hay tạo live assessment/Drive file trong lần cập nhật chính sách này.

## Chính sách đã thống nhất

### P01 — Ai có quyền duyệt, bằng hình thức nào?

- **Trước định hướng:** Skill kiểm revision/digest và yêu cầu nguồn duyệt thật; chưa định danh authority mặc định hoặc cách công nhận người duyệt khác.
- **Định hướng đã nhận:** Không thu thập thông tin người phê duyệt.
- **Cách áp dụng:** Giữ message/reference có sẵn để gắn revision/digest; không hỏi tên, chức danh, danh tính hoặc chữ ký.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P02 — Có thể duyệt criteria và plan trong cùng một phản hồi?

- **Trước định hướng:** Hợp đồng có hai loại approval theo nội dung, hiện mô tả theo trình tự criteria rồi plan.
- **Định hướng đã nhận:** Hai gate riêng: approve catalog → lên plan → approve plan.
- **Cách áp dụng:** Không review gộp và không lập kế hoạch kiểm thử chi tiết trước gate catalog; tái sử dụng approval đúng nội dung đã có.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P03 — Nguồn nào quyết định oracle khi có mâu thuẫn?

- **Trước định hướng:** Giữ provenance và hỏi consequential ambiguity đã có; chưa có thứ tự ưu tiên catalog, spec nghiệp vụ, policy và source.
- **Định hướng đã nhận:** Ưu tiên catalog và tri thức nghiệp vụ do người dùng cung cấp.
- **Cách áp dụng:** Người dùng chịu trách nhiệm tính tin cậy của tri thức; source/runtime mô tả implementation, không đổi expected protection của catalog.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [auth-lifecycle-and-bola-depth.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/auth-lifecycle-and-bola-depth.md>).

### P04 — Phủ rộng hay đi sâu trước?

- **Trước định hướng:** Related unknown/retained-result readback được ưu tiên; các ready cases vẫn do coordinator xếp thứ tự.
- **Định hướng đã nhận:** Khảo sát cơ bản để lấy tri thức trước khi đi sâu.
- **Cách áp dụng:** Coordinator chọn reconnaissance phù hợp rồi dùng kiến thức thu được để ưu tiên deep cases.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [tester-context.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/tester-context.md>), [operation-dispatch.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operation-dispatch.md>).

### P05 — Stopping rule mặc định là gì?

- **Trước định hướng:** Code hỗ trợ all_cases và counterexample; plan phải chọn rõ, chưa có default nghiệp vụ.
- **Định hướng đã nhận:** All cases.
- **Cách áp dụng:** Criteria mới dùng all_cases; ghi violation nhưng tiếp tục xử lý sibling obligations. Counterexample chỉ giữ nghĩa lịch sử.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P06 — Được phép kết luận từ mẫu đại diện đến đâu?

- **Trước định hướng:** All APIs không được bỏ operation bằng sampling. Các yêu cầu rộng kiểu bảo đảm an toàn chưa định lượng population/depth.
- **Định hướng đã nhận:** Đồng ý population/sampling basis và giới hạn kết luận.
- **Cách áp dụng:** Định trước tập được đánh giá, observation đủ và excluded conclusions; mẫu đại diện không thành whole-product met.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [product-discovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md>).

### P07 — Thay đổi nào cần duyệt lại?

- **Trước định hướng:** Material criteria/oracle/target/effect change cần duyệt lại; equivalent repair trong fallback không thêm gate. Ranh giới material còn diễn giải.
- **Định hướng đã nhận:** Linh hoạt, tránh duyệt lại nhiều lần tốn chi phí.
- **Cách áp dụng:** Plan bao gồm adaptive testing envelope; tactics/fixtures/reader/adapter/worker không thêm gate. Chỉ thay đổi thực sự catalog meaning/target/effects mới đổi approval scope; giữ đúng digest/pin/gates.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P08 — Ngân sách chung cho assessment được chọn ra sao?

- **Trước định hướng:** Không tự bịa quota/token cap để đóng sớm; executor guards vẫn có hiệu lực. Chưa có effort/time/cost envelope mặc định.
- **Định hướng đã nhận:** Không thêm quan tâm ngân sách; phù hợp thì dùng subagent.
- **Cách áp dụng:** Coordinator tự chia việc theo ích lợi thực tế, không thêm cost-justification gate hoặc quota tự đặt; giữ resource/rate guards thật và giới hạn người dùng đã có.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [operation-dispatch.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operation-dispatch.md>), [resource-preflight.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/resource-preflight.md>).

### P09 — Được tự sửa adapter đến mức nào?

- **Trước định hướng:** Sửa prerequisite tối thiểu được phép trong scope; framework/phát triển lớn là nhiệm vụ riêng. Small/minimal chưa có ranh giới phân loại cụ thể.
- **Định hướng đã nhận:** Adapter linh hoạt theo nghiệp vụ.
- **Cách áp dụng:** Được sửa/extend testing adapter theo câu hỏi; không giới hạn bằng số dòng code, vẫn giữ authority/history/admission và kiểm boundary đã sửa.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [local-remediation-and-continuation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P10 — Thang severity của observed alerts

- **Trước định hướng:** Native rating giữ nguyên, tester rating phải ghi nguồn; chưa chọn CVSS hay rubric định tính và cách so hai scale.
- **Định hướng đã nhận:** Native giữ nguyên ZAP; observed do tester đánh giá rủi ro từ evidence.
- **Cách áp dụng:** Giữ native grouping/severity/confidence/triage; tester rating có basis và provenance. Không ép người dùng chọn CVSS/rubric mới.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>), [zap-result-boundary.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md>), [alert-triage.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/alert-triage.md>).

### P11 — False-positive và lịch sử có đẩy Mức độ lên không?

- **Trước định hướng:** Native alerts/triage/history được giữ; cột severity nói highest recorded severity mà chưa chốt bộ finding hiện hành dùng để tính.
- **Định hướng đã nhận:** Native giữ nguyên report ZAP, kể cả triage.
- **Cách áp dụng:** Không tự bỏ hoặc giảm native false-positive/informational; cột severity thể hiện rating/triage thật. Observed giữ tester risk assessment tách nguồn.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>), [alert-triage.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/alert-triage.md>).

### P12 — Định danh và gộp một vấn đề bảo mật

- **Trước định hướng:** Không nhân alert theo occurrence/mapping/retry đã rõ; chưa có convention root-cause grouping giữa session/build và native+observed.
- **Định hướng đã nhận:** Giao agent quyết định dedup/identity.
- **Cách áp dụng:** Giữ native session/source ID và grouping, dedup việc đọc/export lặp lại; observed gom khi cùng issue/boundary/context có căn cứ. Native/observed có thể trùng thì cross-reference, không âm thầm sửa native counts; count là alert records, không khẳng định unique root causes.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [zap-result-boundary.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md>), [product-assessment-handoff.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md>).

### P13 — Mức triage tối thiểu cho suspected issue

- **Trước định hướng:** Concrete signal/credible suspicion có thể là alert, không cần exploit hoàn chỉnh; chưa có rubric đủ rõ về noise và baseline.
- **Định hướng đã nhận:** Agent là tester có nghiệp vụ để xác định alert và mức độ.
- **Cách áp dụng:** Triage từ actual signal/observations và business-risk reasoning; không thêm expert signature, user rubric hay exploit campaign bắt buộc.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [alert-triage.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/alert-triage.md>), [zap-result-boundary.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md>).

### P14 — Ai được đọc dữ liệu trên Drive?

- **Trước định hướng:** Không public sharing, giữ quyền hiện hữu và sanitize đã rõ; chưa có audience/data-classification policy.
- **Định hướng đã nhận:** Đã kết nối Drive; người dùng tự chia sẻ.
- **Cách áp dụng:** Dùng connected tools và quyền hiện hữu, không share/change permissions hoặc thêm permission workflow.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>), [product-assessment-handoff.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md>).

### P15 — Human edits có thẩm quyền tới đâu?

- **Trước định hướng:** Giữ và reconcile human edits đã được yêu cầu; chưa có ownership theo cột hoặc quy tắc conflict.
- **Định hướng đã nhận:** Human-edit handling ngoài phạm vi; theo thiết kế gốc.
- **Cách áp dụng:** Tạo/update assessment-managed range từ snapshot theo đúng bảy cột; không bidirectional sync hoặc conflict workflow, không thêm cột/tab/gate.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P16 — TTL và người chịu trách nhiệm retention/cleanup

- **Trước định hướng:** Private retention cần thiết được phép có thông báo; không có TTL chung hay cleanup owner sau assessment.
- **Định hướng đã nhận:** Theo source lifecycle: còn hiệu lực giữ, hết hiệu lực xóa.
- **Cách áp dụng:** Kiểm validity/expiry thật cho task-owned live credential/session material; expired thì owned cleanup được phép. Không tự đặt TTL, không xem unknown là expired; giữ history/ACK/unknown-effect bindings, không suy quyền xóa database/raw reports.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [retention-stop-and-recovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md>), [operational-readback.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md>), [local-remediation-and-continuation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md>).

### P17 — Ranh giới continuation và một đợt retest mới

- **Trước định hướng:** Continuation giữ Sheet; separately assigned retest tạo file mới. Build thay giữa assessment dở hoặc retest hẹp chưa có rule episode chi tiết.
- **Định hướng đã nhận:** Ưu tiên sửa cục bộ để continue, tránh retest toàn bộ lãng phí.
- **Cách áp dụng:** Reuse compatible facts/results/fixtures, chỉ chạy missing/affected work; full retest cần lý do scope/dependency thật hoặc assignment riêng. Local continuation giữ cùng run/Sheet.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>), [retest-and-version-comparison.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retest-and-version-comparison.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### P18 — Thông báo ngay khi gặp phát hiện nghiêm trọng

- **Trước định hướng:** Có milestones và stop theo auth/scope/resource breach; chưa định nghĩa escalation severity trong assessment.
- **Định hướng đã nhận:** Không cần báo động ngay; làm report tổng hợp.
- **Cách áp dụng:** Không thêm severity-triggered notification/escalation; operational stop theo actual auth/scope/resource breach vẫn giữ.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [alert-triage.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/alert-triage.md>), [product-assessment-handoff.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>).

## Theo project — coordinator quyết

### C01 — Target/environment/origin khi chỉ có repository

- **Trước định hướng:** Binding và origin selection đã có guard, nhưng không thể suy authorized target chỉ từ source.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Khám phá thông tin được phép; nếu target còn consequential unknown thì hỏi target cụ thể, tiếp tục source-only; không đoán production hoặc cổng đầu tiên.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [product-discovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md>), [discovery-origin-selection.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/discovery-origin-selection.md>).

### C02 — Bằng cách nào biết discovery đã đủ?

- **Trước định hướng:** Helper chỉ so các feature/case/source đã khai báo; feature bị bỏ cả hai tập thì vô hình.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Broad criterion đối chiếu hai chiều feature→API và API→feature; ghi extent và unknown cụ thể, không yêu cầu archive/hash mọi source.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [product-discovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### C03 — Observation phải đạt stage nào?

- **Trước định hướng:** Boundary/processing/persistence/consumer có ngữ nghĩa khác; không có depth chung cho mọi criterion.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Derive stage từ requirement/asset/threat trước chạy; ghi đủ observation và excluded conclusions. Không bắt DB cho mọi denial và không dùng 409 thay processing.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [operational-readback.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### C04 — Role/state/vector nào cần case riêng?

- **Trước định hướng:** Không Cartesian product vô hạn; gom cùng boundary có basis, all APIs vẫn phải đủ operation.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Tách theo security reason; reuse/gom biến thể tương đương có căn cứ. Không coi cùng role là cùng actor hoặc cùng URL là cùng business operation.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [track-intents.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/track-intents.md>), [product-discovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md>), [product-extension-planning.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-extension-planning.md>).

### C05 — Rule/rate/impact budget và lượng fixture

- **Trước định hướng:** Không mặc định mọi rule hay chỉ 40012/40018 cho mọi product; executor có caps riêng.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Theo input/sink/risk và actual capability; tính cả baseline/control vào budget, không tự mở brute force/lockout để phủ catalog.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [native-operation-routing.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/native-operation-routing.md>), [fe-anonymous-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/fe-anonymous-research.md>), [operational-readback.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md>).

### C06 — Polling/readiness deadline của async/media

- **Trước định hướng:** Helper có deadline mechanics và FE lane có cap; không có product SLA toàn cục.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Chọn theo documented lifecycle/measured baseline trong guard; timeout là thiếu observation nếu chưa có SLA oracle. Không bypass cap.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [operational-readback.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md>), [auth-lifecycle-and-bola-depth.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/auth-lifecycle-and-bola-depth.md>).

### C07 — Khi nào bằng chứng cũ còn dùng được?

- **Trước định hướng:** Có context/finite compatibility và selective live checks, chưa thể có universal TTL cho mọi fact.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Theo exact context và change dependencies; volatile identity/fixture kiểm ngay trước use. Tuổi snapshot không tự chứng minh live hoặc hủy mọi evidence cũ.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [operational-readback.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md>), [retention-stop-and-recovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md>), [retest-and-version-comparison.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retest-and-version-comparison.md>).

### C08 — Resource identity và isolation thực tế

- **Trước định hướng:** Delegation hiện yêu cầu common coordinator state, actual shared IDs và serialize nếu chưa isolated; tool không tự suy map này.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Ghi actual stable IDs/bindings; chỉ parallel effects khi target/session/fixture/attribution đã isolated. Không phải policy chọn lại việc cho replay hay bỏ lease.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [delegation-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/delegation-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [fe-authenticated-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/fe-authenticated-research.md>).

### C09 — Quyền tạo fixture/DB setup/cleanup cụ thể

- **Trước định hướng:** Scope nguồn không tự cấp quyền login/DB; DB setup cần đúng binding/tables/budget/authority.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Chuẩn bị legitimate fixtures trong plan; DB chỉ khi quyền cụ thể; không biết DELETE thì giữ có lý do, không giả cleanup thành công.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [product-extension-planning.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-extension-planning.md>), [fe-authenticated-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/fe-authenticated-research.md>), [local-remediation-and-continuation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md>).

### C10 — Lúc nào waiting thành terminal not_evaluable?

- **Trước định hướng:** Các trường limitation/stopping đã được kiểm; việc còn feasible alternatives hay không vẫn do agent xác thực.
- **Định hướng đã nhận:** Giao toàn quyền lựa chọn chuyên môn cho coordinator khi quan sát sản phẩm trong project/target/effects đã thống nhất; không hỏi lại người dùng từng mục.
- **Cách áp dụng:** Coordinator quyết định dựa vào knowledge thu được và nghiệp vụ testing. Chỉ terminal khi cause/missingEvidence/options/reopen đủ và hết approved feasible required action; không đóng bằng nhãn capability chung. Không cần hỏi lại người dùng cho mỗi case.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>).

## Phạm vi triển khai đã thống nhất

### I01 — Pipeline end-to-end chưa tự động

- **Trước định hướng:** Discovery→approved executor mapping→semantic evidence→Drive vẫn agent-operated; có helper nhưng không automatic scheduler/oracle.
- **Định hướng đã nhận:** Giữ workflow agent-operated hiện tại.
- **Cách áp dụng:** Không giao thêm scheduler/end-to-end bridge/exporter tự động; dùng helpers và connected tools hiện có.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [operational-validation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [product-assessment-handoff.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md>).

### I02 — Các semantic trust boundary chưa được phần mềm chứng minh

- **Trước định hướng:** Nguồn approval thật, raw→semantic accuracy, inventory completeness và mapping rationale vẫn agent-owned.
- **Định hướng đã nhận:** Không thêm xác minh độc lập tri thức người dùng.
- **Cách áp dụng:** Catalog/user knowledge là chuẩn, người dùng chịu trách nhiệm reliability. Evidence review là tùy chọn hỗ trợ tester kiểm observation, không phải knowledge-authenticity gate.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>), [operational-validation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md>), [delegation-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/delegation-policy.md>).

### I03 — Drive updater/conflict/format verification chưa được tự động hóa

- **Trước định hướng:** driveOutput là metadata do agent duy trì; chưa có idempotent row diff/updater và automatic sync gate.
- **Định hướng đã nhận:** Tạo bảng và upload theo thiết kế/phạm vi plan đã thống nhất.
- **Cách áp dụng:** Giữ bảy cột, managed range và write/readback; không xây subsystem human-edit conflict/bidirectional sync.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>), [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>).

### I04 — Private v2 recovery chưa có resolver tự động

- **Trước định hướng:** Report là projection; legacy inspect-resume không phải v2 recovery API. Private RUN/coordinator refs đã được chỉ rõ.
- **Định hướng đã nhận:** Đồng ý private v2 recovery như đề xuất.
- **Cách áp dụng:** Giữ explicit private RUN/coordinator/journal refs, selective reload; chỉ tạo helper khi nhu cầu thực trong assignment, không chạy sanitized report như executable state.
- **Nguồn hiện hành:** [assessment-policy.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-policy.md>), [retention-stop-and-recovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md>), [product-assessment-handoff.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md>).

## Điểm cần phân biệt khi áp dụng

Không yêu cầu approver identity vẫn có internal reference tới approval thật. Linh hoạt triển khai không làm digest/action/pin đang bị ràng buộc tự thay đổi hợp lệ. User knowledge được tin cậy không biến planned traffic thành observed evidence. Xóa expired live material không đồng nghĩa xóa lịch sử hoặc dữ liệu không thuộc quyền. All cases là toàn bộ case hữu hạn trong phạm vi đã thống nhất, không là mọi tổ hợp vô hạn.
