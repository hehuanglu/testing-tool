# Audit và chỉnh sửa mcp-zap-repo-operations — 2026-11-03

## Phạm vi và cách hiểu kết quả

Audit theo yêu cầu về câu chữ thừa/mơ hồ, liên kết hướng dẫn với runner/helper và tính thống nhất workflow. Baseline gồm 467 file trong skill, tại HEAD `18f17860bad327a18345f949644aac4d40b7fece`, kèm nhiều thay đổi tracked/untracked có sẵn. Các thay đổi của lượt này được so với `baseline.json`, không lấy toàn bộ diff so với HEAD làm công việc mới.

Đã kiểm kê toàn bộ cây file, đọc/đối chiếu tài liệu hiện hành, lần theo các entrypoint và phân tích sâu các ranh giới workflow, routing, evidence, journal và report. `coverage.json` ghi mức kiểm tra riêng từng file: đọc sâu, đọc phần liên quan, kiểm tra cấu trúc, tài liệu lịch sử hoặc asset. Kiểm kê toàn bộ không có nghĩa mọi dòng code/test đã được semantic review độc lập.

Đây là audit source và kiểm tra offline. Không có product traffic, scanner provisioning, đăng nhập thật, đọc credential sản phẩm, Drive publishing, đồng bộ personal installation, commit hoặc push. Các lỗi helper bên dưới được tái hiện bằng dữ liệu synthetic; không suy diễn thành sự cố thật của sản phẩm.

## Kết luận theo ba câu hỏi

**Có mô tả thừa hoặc chưa rõ:** có. Một số chính sách counting được lặp lại; một số hướng dẫn discovery/recovery đặt approval gate quá sớm; các từ “all APIs”, “direct” và “v2” trong tài liệu kỹ thuật cũ có thể bị hiểu vượt phạm vi. Đã sửa các chỗ xác nhận được, dùng liên kết tới nguồn chính thay cho lặp lại khi phù hợp. Giữ các nhắc nhở ngắn tại điểm thao tác khi chúng bảo vệ scope, auth hoặc provenance.

**Liên kết với runner/helper:** đã có phần lớn cấu trúc, nhưng còn khoảng trống và sai lệch. Đã bổ sung `references/helper-contract-map.md`, nối từ runner routing, làm rõ input/output/effect của 8 script cấp skill và vendored CI gate. Đã sửa hướng dẫn sai cwd/virtualenv, capability numeric-path lỗi thời và các ví dụ gọi driver không có trong bundle. Các giới hạn còn lại được ghi rõ thay vì giả lập công cụ còn thiếu.

**Workflow thống nhất:** workflow chuẩn vẫn là criteria v2, có hai approval gate, all_cases, verdict độc lập và delivery tách biệt. Đã gỡ các chỉ dẫn hiện hành dẫn người dùng v2 sang legacy completion/residual helpers và đánh dấu rõ tài liệu package/historical. Runner kỹ thuật vẫn giữ contract riêng; không có adapter tự động từ discovery sang live executor, semantic oracle tự động hay Sheets exporter được bổ sung.

## Các lỗi triển khai được sửa

### AUTH-01 — Authenticated request chưa thực sự gắn session

`executor_routing.assess_executor` chấp nhận ordinary authenticated `zap_attack_start` không có `authSessionId` nếu metadata của candidate nói session đã validate. Nay request phải có prepared session thực sự. Đối chứng giữ nguyên lựa chọn anonymous hợp lệ và authenticated có session. Đây là kiểm tra compatibility, chưa phải chứng minh auth runtime.

### EVID-01 — Mapping retained-build hợp lệ bị từ chối

`criteria_workflow.review_workflow` gọi semantic resolver chấp nhận compatibility, rồi lại yêu cầu toàn bộ giá trị context bằng nhau. Nay cho phép finite mapping của dimension cấp case đã được resolver kiểm tra, vẫn đòi operation có context quan sát thực và khớp chính xác mọi dimension trong `criteriaWorkflow.context`. Product/environment hoặc build bound ở workflow không được chuyển qua mapping; placeholder, thiếu context và thay origin vẫn bị chặn. Không sửa operation lịch sử.

### REDACT-01 — Bộ lọc bỏ sót opaque credential fields

`criteria_reporting.sanitize`, `product_scope_cli.safe_review_output` và `readiness.safe_facts` chưa che `setupToken`/`sessionToken` nhất quán với report legacy. Đã đồng nhất normalized sensitive keys và kiểm tra nested structures, đồng thời giữ semantic IDs và prose thông thường. Chỉ dùng token giả trong test.

### REPORT-01 — Report giữ pointer tới evidence đã bị redaction xóa

V2 report revalidation chưa kiểm tra đầy đủ resource review, resolved effects và contained effects sau sanitization. Có thể xuất report completed dù proof chỉ tồn tại dưới `/raw` đã bị xóa. Nay kiểm tra các references trước khi ghi. Negative control không tạo output directory; cùng proof hợp lệ dưới sanitized `/readback` vẫn publish được.

### JOURNAL-01 — Intent chưa được ghi bền vững trước effect

`ResearchRun.event` chỉ append qua buffer. Nay dùng `write_all`, fsync file và directory trước khi trả quyền dispatch, đồng thời latch công việc mới khi journal IO lỗi. Test kiểm tra sync failure trước effect không dispatch và lỗi lưu ACK sau effect không cho start lại.

### STOP-01 — Lỗi journal/finalization có thể cản stop và cleanup

Nhánh stop dùng chung hàm ghi intent với effect mới; journal lỗi có thể ngăn stop scan đang chạy. Nay stop-only vẫn thử đúng operation đã ACK của run, giữ lỗi journal/ACK best effort và khóa công việc mới. Monitor vẫn đi đến stop khi ghi sự kiện lỗi. `product_native` vẫn chạy cleanup với kiểm tra container ID/ownership khi `finish()` lỗi, giữ kết quả failed/incomplete/block. Test âm giữ nguyên container có ID bị thay. Đây là fault injection offline, không phải qualification sự cố disk/scanner thật.

### EXPORT-01 — Thiếu kiểm tra alert total sau pagination

Hai exporter anonymous/native chỉ đọc tổng alert trước khi phân trang, khác hợp đồng pre/post stable totals. Nay cùng dùng `result_readers.read_native_alerts` để kiểm tra số record từng trang, ID duy nhất và tổng sau đọc trước khi trả dữ liệu complete. Test có tổng ổn định, zero-alert, tăng/giảm total, thiếu và trùng page. Equal totals không chứng minh không có replacement cùng số lượng; điều kiện dừng producer và settle passive vẫn bắt buộc.

## Các nhóm tài liệu đã chỉnh

- Tách reconnaissance/planning trước gate khỏi execution cần approved plan; lưu/reconcile state vẫn có thể cần thiết khi plan dừng hoặc sửa.
- Trỏ completion, residual review, case representation và test guidance hiện hành về v2; giữ legacy cho đọc lịch sử.
- Nêu rõ BOLA cần ZAP sendRequest/proxy để có ZAP-derived coverage; fixture traffic bypass không được nâng thành finding của ZAP.
- Chỉ so sánh nhiều deployment khi thực sự chọn giữa chúng; deployment thứ hai không phải prerequisite mặc định.
- Dùng absolute loaded skill path và external Python environment; không suy `SKILL_DIR` từ cwd hoặc giả định bundle có `.venv`.
- Giữ extension inventory trong assigned questions; không thêm gate ngân sách hoặc giới hạn kích thước adapter tự đặt.
- Giảm lặp counting/native preservation trong alert triage bằng canonical link.
- Nêu rõ CI gate cần API key trên argv, có normalized/suppressed projection và không phải workflow v2; dùng helper phù hợp qua transport riêng thay vì vi phạm secret/provenance contract.
- Bổ sung package documentation index, phân biệt technical contract, milestone history và workflow hiện hành; cập nhật mô tả conditional numeric-path theo compiler.
- Làm rõ recipes README: source-derived assumptions cần đối chiếu catalog, không thêm independent-acceptance gate cho user business knowledge.

## Liên kết từ hướng dẫn đến triển khai

- Criteria/approval/completion: `criteria-driven-workflow.md` → `product_assessment.py scope` → `product_scope_cli` → `criteria_workflow` → semantic evidence resolver → criteria tests/CLI boundary tests.
- Delegation/recovery: `delegation-policy.md` → `criteria_delegation.Coordinator` → packet/lease/journal/merge → criteria integration và lease/recovery tests. Worker summary không tạo verdict.
- Routing: `operation-dispatch.md`/`runner-routing.md` → `map_question_capability` → `choose_executor`/`assess_executor` → inspected schema/auth facts → routing/adapter tests. Compatibility không grant authority.
- Backend: finite common CLI → product compiler/admission → AnonymousRun hoặc product-native/ResearchRun hoặc BOLA lane → readback/journal → internal handoff. V2 coordinator phải gắn approved cases vào executor phù hợp.
- Frontend: common CLI → FE track CLI → contract/compiler → browser/runtime → verify/handoff. Browser journey, actor mapping, fixture hooks và finite predicate cap vẫn theo lane thực tế.
- Publishing: reviewed RUN → `criteria_reporting`/`product_scope` → sanitize/reference validation → RUN/ALERTS/SCOPE_ALERTS. Google Sheets vẫn là bước agent thao tác qua connected tools và readback riêng.
- Skill helpers và vendored gate: xem `references/helper-contract-map.md`; checksum/provenance được kiểm tra riêng, không sửa snapshot vendored.

## Walkthrough và bằng chứng kiểm tra

Các expected outcomes được lấy từ quy trình audit/policy trước khi đánh giá kết quả; không dùng nhãn pass của helper làm semantic oracle.

1. Hai approval gate/content binding: test approval digest, stale approval và CLI finalization; source walkthrough cho drafting trước khi có complete plan.
2. Fixture/reader adjustment trong approved envelope: đối chiếu policy, immutable pins và packet binding; không thay approval cũ bằng digest mới.
3. Scope/authority đổi: stale-revision/worker scope rejection; v2 identity mapping không cho vượt workflow context.
4. Shared observations: mapped alert subset/count tests và walkthrough 403 có sensitive body; verdict cần oracle từng criterion.
5. Violation còn sibling all_cases: pending/required-case tests; không coi finding đã thấy là hoàn thành mọi case.
6. ACK/HTTP 202, zero probes, auth loss: readiness/active-question/readback tests và source walkthrough; không cấp processing/active credit từ nhãn terminal.
7. Reader lỗi hoặc lost ACK: selector ưu tiên retained readback, no-replay/journal tests; lỗi persistence không được tạo start thứ hai.
8. Nhánh phụ thuộc và độc lập: work-selection tests; thiếu fixture không đóng toàn assessment.
9. Missing primitive: routing/schema/auth/reader tests, giới hạn thật khác preparation còn khả thi.
10. Worker stale/unknown/resource overlap: packet/merge/lease tests; lock publication và snapshot consistency.
11. Legacy resume/retest: legacy-v2 rejection, reviewed compatibility và source-pin history; không tự chuyển status thành verdict.
12. Criteria completed nhưng Drive chưa sync: source-only decision walkthrough theo output contract; không có Drive write/runtime test, không scan lại để sửa publishing.
13. Skill-only/explicit stop: source boundary, user-stop và continuation tests; không tạo assessment report sản phẩm.

Kết quả chi tiết và command được lưu cùng báo cáo. Test pass xác nhận các contract đã exercise; không chứng minh chất lượng mọi quyết định tương lai của agent hoặc toàn bộ runtime.

Kết quả cuối: **453 test chạy, 445 pass, 8 skip theo điều kiện optional product source có sẵn, không failure/error** (63,822 giây). Dùng Python 3.13.2 từ environment hiện có với đủ 7 dependency đúng `requirements.lock`; `PYTHONPATH` trỏ tới bundled source/tests. Một số regression dùng HTTP fixture nội bộ, không phải traffic tới sản phẩm/scanner thật. Các nhóm gồm criteria workflow/integration/report/CLI, evidence/readiness/selection, legacy scope/closure/resume, routing, FE contracts, research journal/finalization, report collection, anonymous và common multi-product/edges.

Ngoài ra: 298 local document links/anchors hiện hành hợp lệ; 47 JSON Schema qua metaschema; toàn bộ Python/JSON trong manifest parse được; 8 helper `--help` exit 0 sau khi kiểm tra entrypoint; source inventory nhận diện 78 tool names và khớp routing names, không có runtime call; 3 vendored file hashes đúng provenance; `git diff --check` sạch. Kiểm tra tên tool không chứng minh schema/auth/deployment compatibility.

## Giới hạn còn giữ rõ

- 25 relative Markdown links trong historical remediation documents dẫn tới artifact/continuation files không được đóng gói. Giữ nguyên lịch sử; package README và helper map nêu rõ chúng không phải evidence có thể đọc từ bundle. Không claim campaign lịch sử tái lập được chỉ từ skill.
- Một số campaign driver gốc cũng không có trong package; không tạo driver giả hay chạy lại product effects để lấp khoảng trống.
- Bản cài cá nhân có thể khác repository; lượt này không đồng bộ nó. Plan/admission mới cần nhận diện source-pin drift do code đã sửa, không repin run lịch sử.
- Không xác minh runtime hiện tại, secret retention thực tế, toàn bộ FE/auth/protocol support, Drive layout thực tế hoặc source-to-binary attestation.
- Cần đọc `coverage.json` để phân biệt file được kiểm tra logic với file chỉ được parse/inventory. Không có tuyên bố “skill an toàn toàn diện” hoặc “mọi capability đã pass”.

## Artifact

- `baseline.json`: file hashes/HEAD/dirty baseline trước sửa.
- `coverage.json`: disposition và mức kiểm tra từng file; current hashes và file thay đổi từ baseline.
- `documentation-review.json`, `workflow-review.json`, `runner-review.json`: findings, source traces, controls và giới hạn chi tiết.
- `structural-checks.json`, `schema-environment-checks.json`, `helper-help-checks.json`, `source-tool-inventory.json`: kết quả kiểm tra source/cấu trúc/interface.
- `final-regression-tests.log`: regression sau các sửa đổi tích hợp; log các đợt trước được giữ riêng.
