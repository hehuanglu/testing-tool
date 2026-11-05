# Kế hoạch cải tiến skill ZAP theo nghiệp vụ kiểm thử thực tế

Ngày: 02/11/2026 (Việt Nam). Trạng thái: **đã tái đánh giá và chốt thiết kế để triển khai; chưa implement**.

## 1. Nhiệm vụ của agent nhận bàn giao

Implement kế hoạch này trong `/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations`. Mục tiêu là làm workflow dễ vận hành, tìm đúng việc cần kiểm thử, đọc đúng kết quả và kết thúc đúng phạm vi. Không biến skill thành hệ thống chứng nhận an toàn hay framework quản lý test tổng quát.

Định hướng đã chốt:

1. Giữ inventory kỹ thuật; thêm bản đồ feature/journey độc lập để giảm bỏ sót nghiệp vụ.
2. Chốt câu hỏi và mức quan sát đủ trước khi chọn runner. Dùng mức đại diện có lý do, không sinh mọi tổ hợp.
3. Tách attempt, câu hỏi, finding, phần DAST được giao và toàn assignment/catalog.
4. Giúp agent chọn việc qua helper chỉ đọc; execution vẫn đi qua admission, journal và executor hiện có.
5. Chuẩn hóa readiness và liên kết bằng chứng vừa đủ dùng; không viết engine tự suy luận nghiệp vụ hoặc tự đọc policy thành pass/fail.
6. Giữ rào chắn về quyền, target, unknown effects và provenance. Giảm giấy tờ và vòng qualification không cần thiết.

Chỉ sửa skill, helper, reference và test offline liên quan. Không chạy scan mới, không provision/restart Docker, không sửa sản phẩm, không sửa lại raw/history hoặc ba báo cáo assessment cũ. Không đồng bộ personal skill, commit/push hay tạo chat. Việc implement không cần chờ một đợt audit toàn platform.

## 2. Nền kiểm tra và giới hạn của bản tái đánh giá

Đã đọc bản audit `docs/reviews/zap-skill-business-coverage-gap-analysis-20261102.md`, skill hiện hành, các reference discovery/completion/track/routing/readback/continuation/validation, core helpers và adapter được viện dẫn. Đã đọc các operation liên quan trong `assessment-results/100ms-fresh-20261101/RUN.json` (4.330 operation), kiểm tra source FE chọn lọc để xác nhận pin, spotlight, layout, background và reaction là các hành vi riêng.

Baseline Git HEAD khi kiểm tra: `18f17860bad327a18345f949644aac4d40b7fece`. Working tree có nhiều thay đổi từ trước, gồm chính skill và `security_scope.py` chưa tracked. **Nội dung working tree đã đọc mới là baseline thiết kế, không phải chỉ HEAD**. Agent sau phải giữ những thay đổi có sẵn; không reset/stash/revert hoặc thay nguyên file bằng bản HEAD.

Phương pháp: static source review, đối chiếu reference và readback lịch sử; không tạo traffic. Đã thử import helper để chạy reproduction offline nhưng cả `python3` và `python3.13` sẵn có thiếu `jsonschema`; reproduction chưa chạy được. Không cài dependency trong lượt lập kế hoạch. Không báo các tình huống kiểm tra bên dưới là test đã pass. Bằng chứng lịch sử là dữ liệu đã ghi, chưa phải độc lập tái thực thi toàn bộ assessment. Không có transcript đầy đủ để xác nhận mọi quyết định lịch sử của agent.

Các đường dẫn ngắn trong tài liệu đều tương đối với workspace nêu trên. Dùng các bí danh sau để đọc phần implementation:

- `S = .agents/skills/mcp-zap-repo-operations`
- `L = S/lib/zap-product-assessment`
- `P = L/src/zap_assessment`
- `T = L/tests`
- `R = S/references`

Đây là ký hiệu tài liệu, không phải biến shell đã thiết lập. Trong code/CLI dùng đường dẫn thật hoặc biến được thiết lập rõ.

## 3. Tái đánh giá tám nhận định của audit

### W01 — Thiên về endpoint: xác nhận, cần sửa discovery chứ không thay endpoint inventory

`P/product_scope.py:inventory_from_operations()` chỉ duyệt `doc.operations`, tạo question chung và các unit `technique-decision/result-read`. `.local/100ms-fresh-20261101/session.py:init()` xây inventory từ controller BE. Hai cơ chế này không tự tạo danh sách hành động UI/consumer.

Source sản phẩm minh họa có `fe/src/hooks/useSessionFocus.ts`: pin thay view preference riêng; spotlight gọi API khác và thay trạng thái chung. Có thêm `components/layout/ViewControls.tsx`, `hooks/useBackground.ts`, `hooks/useReactions.ts`. Vì vậy không thể dùng một case preferences thay mọi hành vi; cũng không được suy ra mọi feature cùng đi qua đúng một API.

**Điều chỉnh:** không yêu cầu testcase riêng cho mọi nút và mọi layout. Chỉ tách khi khác ownership, trust boundary, nơi tiêu thụ dữ liệu, side effect hoặc điều kiện closure. Nhóm các biến thể thuần trình bày khi cùng đường xử lý và không có nghĩa vụ riêng từ user.

### W02 — Reconciler không xác nhận discovery: xác nhận giới hạn, không gọi là bug logic

`reconcile()` tin cờ `complete`; `reconcile_responsibilities()` so units trên case đã khai báo. `R/responsibility-loop.md` đã cảnh báo caller labels. Một reconciler không thể phát hiện feature mà cả người gọi lẫn input đều không biết.

**Điều chỉnh:** thêm phép đối chiếu tập feature đã review độc lập với case, cùng danh sách nguồn chưa kiểm tra. Không hứa tự phát hiện mọi journey từ source. Nếu feature bị bỏ khỏi cả hai tập, helper vẫn không biết; phải ghi rõ giới hạn này. Review discovery làm lúc intake, khi xuất hiện dấu hiệu mới và trước kết luận hết việc, không lặp toàn repo mỗi round.

### W03 — Runner hẹp: xác nhận theo lane, giảm phạm vi sửa

`anonymous.py` giới hạn rule 40012/40018 trong lane đó; `fe_authenticated_recipes.prepare()` chỉ có setup adapter cho finalsource; `executor_routing.py` đã có kiểm tra schema/auth và lựa chọn executor. `R/runner-routing.md` đã mô tả khá rõ các giới hạn.

**Điều chỉnh:** vấn đề cần giải quyết là mapping câu hỏi → capability → phần thiếu. Không mở rộng mọi method, protocol, auth hay rule; không xây thêm registry song song thay `executor_routing`. Việc thiếu setup hook không chứng minh toàn ZAP không làm được, cũng không cấp quyền gọi đường thấp hơn để vượt admission.

### W04 — Readiness: xác nhận lỗi adapter và thiếu primitive dùng chung

`fe_authenticated_contract.py:predicate()` có cap 12 giây; đây là giới hạn entry, không phải timeout toàn ZAP. `final_ui_background.mjs` dùng `waitForTimeout(1000)` sau Apply. RUN ghi readiness lúc `22:12:21.128Z`, trước PATCH ACK `22:12:22.523Z`; operation diagnosis nhận diện lỗi này. Followup `final-ui-bg-ready-journey` có readback về background commit/clear.

**Điều chỉnh:** deadline chờ là ngân sách quan sát, không phải SLA sản phẩm. Timeout chưa đủ để tuyên bố vulnerability. Không bắt enum rejection phải có media segment. Không nâng cap toàn hệ thống để che reader sai. Bổ sung primitive polling có identity và observation stage, rồi adapter chọn tầng cần đọc.

### W05 — Trộn attempt với closure: xác nhận hai vấn đề riêng

Adapter `session.py:report()` hardcode `taskCompletion: partial`, suy track từ operation ID. Core `security_scope.project_scope()` dùng `op_open` nếu bất kỳ operation được link không `completed`, và dùng linked case open để giữ question mở. Đây là rủi ro mapping có thật; chưa chứng minh core gây mọi nhãn partial của assessment minh họa.

RUN còn cho thấy chiều ngược lại: `final-ui-focus-journey` có `status: completed` nhưng steps có lỗi Sidebar và cleanup 409; pin/spotlight vẫn có kết quả riêng. `final-ui-background-journey` completed ở cấp operation nhưng processor commit chưa quan sát được. **Completed không đủ để đóng mọi câu hỏi của operation; partial cũng không làm mất mọi quan sát hợp lệ của operation.**

Readback transport ghi 30 dòng 503, trong đó 20 dòng trùng control non503; 10 signature còn thiếu được followup tại version boundary 409. Điều này không chứng minh processing/sink đã được kiểm thử. Không gộp chỉ vì URL/body giống nhau; actor, object, build, state, objective và provenance vẫn phải phù hợp.

**Điều chỉnh:** thêm liên kết bằng chứng ở mức observation unit; tách context/history khỏi support hiện tại. Không sửa status attempt cũ; không bỏ unknown mutation bằng cách chuyển link sang context.

### W06 — Điều kiện đủ: đúng nhưng audit dễ dẫn tới thêm checklist

Skill đã nêu câu hỏi hữu hạn, phân biệt assessment/security/remediation và không cần giải thích mọi failure. Thiếu mẫu intake gọn và cách thể hiện completion theo phần DAST thay vì chỉ partial toàn catalog.

**Điều chỉnh:** dùng một charter ngắn, suy từ yêu cầu hiện có; hỏi chỉ khi khác biệt ảnh hưởng thật đến scope/quyền/kết luận. Không buộc user duyệt test matrix. Chọn mức sâu theo câu hỏi, không mặc định lifecycle end-to-end cho mọi case. Đại diện không tự loại endpoint đã được giao “all APIs”.

### W07 — Chọn việc theo thứ tự: xác nhận, không cần scoring engine

`continue_work()` chọn candidate đầu tiên có handler. Caller có thể sắp đúng nhưng không có giải thích chuẩn khi không tìm được handler. Thiếu handler là việc chuẩn bị hoặc hạn chế capability, không phải hết trách nhiệm.

**Điều chỉnh:** thêm helper đề xuất thứ tự và lý do bỏ qua; cho phép caller giữ thứ tự khi dữ liệu ưu tiên chưa có. Ưu tiên xử lý unknown liên quan, đọc kết quả đã có, gap giá trị cao có readiness, rồi chuẩn bị nhỏ. Không dùng điểm số giả chính xác, không để chỉ chọn việc dễ làm thay việc có tác động cao.

### W08 — Quyền và lịch sử: chủ yếu cần hướng dẫn rõ, không thêm approval engine

Core guidance đã cho phép fixture/repair hợp lệ, allocation mới và tiếp tục độc lập. Một số cấm rộng thuộc prompt riêng của assessment; không có đủ transcript trong lượt này để xác minh đầy đủ các cấm riêng đó.

**Điều chỉnh:** ghi quyền đã có theo nguồn và đối tượng; không yêu cầu tích checkbox cho mọi khả năng hoặc xin lại quyền. Unknown effect phải readback trước replay. Regression được giao trên fixture mới là thao tác khác với replay để làm đẹp nhãn. Không sửa guard safety chỉ vì audit nói cần linh hoạt.

### Hai điểm bổ sung cần xử lý trong cùng phạm vi

1. `continue_work()` hiện union units theo `actorRef/role/state/relation`; không tự kiểm tra origin/object/build/input/objective. Khi thêm evidence links cần ngăn tích lũy sai context cho contract mới. Không được quảng bá helper tự xác minh semantics từ JSON.
2. `review_open_work.py` đang có `workComplete` dựa trên labels và quyết định caller. Giữ cảnh báo trust boundary, thêm nghĩa rõ là hoàn tất xử lý danh sách khai báo, không phải completion của assignment. Không dùng helper này làm nguồn status thứ hai cạnh reconciler.

## 4. Quy tắc nghiệp vụ phải thể hiện trong skill mới

### 4.1. Charter ngắn tại intake

Ghi trong plan/RUN hiện có: đối tượng/môi trường, yêu cầu gốc, tracks/criteria được giao, feature cần xét, độ sâu, sufficient observations, giới hạn phương pháp, quyền fixture/tooling cần dùng. Không tạo deliverable thứ tư.

Độ sâu là mô tả mục tiêu, không phải thang bắt buộc đi từ thấp lên cao:

- `boundary`: đầu vào/quyền bị chặn đúng chỗ và side effect liên quan không xảy ra.
- `processing`: dữ liệu hợp lệ đến đúng xử lý/consumer cần kiểm tra.
- `persistence`: trạng thái sau ghi đọc lại đúng object khi mục tiêu liên quan lưu trữ.
- `delivery`: consumer thực nhận dữ liệu/media/event nếu đó là câu hỏi.
- `recovery`: revoke/stop/retry/reconnect trong phạm vi đã giao.

Ví dụ: câu hỏi enum invalid có thể đóng tại rejection + state liên quan không đổi; câu hỏi recording stop cần đúng recording và downstream trạng thái được chỉ định. Không dùng invalid boundary thay cho active injection processing.

### 4.2. Discovery theo hai hướng

Đi từ spec/use case/UI/source hành động tới API/consumer; đi ngược từ API/auth/state tới tính năng sử dụng. Tận dụng nguồn có sẵn, không bắt buộc vừa spec vừa source vừa UI runtime. Thiếu một nguồn không tự chặn mọi assessment; ghi ảnh hưởng cụ thể đến độ tin cậy/phạm vi khám phá.

Chỉ bổ sung câu hỏi khi có lý do security: actor/owner khác, boundary khác, consumer khác, state transition khác, requirement riêng. Không biến phần DAST thành functional QA toàn sản phẩm.

Mỗi feature được review nhận một disposition: có case, dùng đại diện có căn cứ, không có câu hỏi security bổ sung trong assignment, ngoài assignment theo yêu cầu gốc, hoặc chưa quyết định. “Không có câu hỏi bổ sung” không đồng nghĩa sản phẩm an toàn hay feature không áp dụng về chức năng.

### 4.3. Kết thúc thực tế

- Hết nghĩa vụ được giao với discovery đã đối soát: hoàn thành, kể cả finding còn mở.
- Còn việc hữu ích khả thi trong quyền: tiếp tục.
- Còn công việc nhưng thiếu access/policy/capability thật: handoff partial, chỉ rõ điều kiện tiếp tục; không buộc tạo helper lớn vô hạn để tránh dừng.
- User giao timebox/stop-after-block: tôn trọng, ghi phần chưa làm. Không tự đặt timebox hoặc lấy max_actions làm completion.
- DAST subset đã đủ nhưng catalog còn governance/implementation criteria: báo hai trạng thái riêng; không sinh traffic vô ích.

Không bắt chứng minh absence tuyệt đối, mọi browser, mọi role/state combination; không đặt SLA sau khi nhìn kết quả. Không coi “chưa biết exact root cause của failure cũ” là gap còn test nếu câu hỏi được giao đã có đáp án phù hợp.

## 5. Thiết kế dữ liệu: mở rộng nhỏ, tương thích dữ liệu cũ

### 5.1. Nguyên tắc chung

Giữ các key hiện có: `cases`, `requiredEvidence`, `observations`, `operationIds`, `taskCompletion`, `actionHistory`, `securityScope`. Không đổi nghĩa âm thầm. Thêm contract tùy chọn `workflowVersion: 1` vào responsibility inventory. Dữ liệu mới theo workflow này dùng version 1; dữ liệu cũ vẫn đọc được, không tự migrate history hoặc tự đổi complete thành pass/fail mới.

Validator của contract mới kiểm tra shape, enum, reference và mâu thuẫn cụ thể. Không yêu cầu mọi trường mô tả cho mọi case; lỗi thiếu dữ liệu discovery là diagnostic/open gap, không ngăn lưu checkpoint hoặc chạy phần hợp lệ. ID trùng, reference không tồn tại, kiểu sai là input error.

### 5.2. Các field mới trong inventory

`engagement`: object ngắn, gồm `objective`, `scopeBasis` (nguồn yêu cầu), `methodBoundary`, `authorityNotes` (mảng `{action, scope, basis}`), `limits` (giới hạn user/environment có thật). Không chứa token, không dùng làm authorization bypass. Không tạo boolean “approved everything”.

`discoveryReview`:

- `sources`: `{id, kind, location, reviewedScope, remainingScope?}`. Kind có thể spec, ui-source, api-source, runtime, supplied-inventory.
- `features`: `{id, name, sourceIds, disposition, caseIds, basis?}`.
- `disposition`: `mapped`, `represented`, `no-additional-question`, `outside-assignment`, `unresolved`.
- `represented` cần `caseIds` và basis nêu đường xử lý/boundary dùng chung cùng khác biệt không được bao phủ.
- `no-additional-question` cần basis về assignment/security relevance; không được áp dụng nếu requirement gốc có nghĩa vụ riêng chưa trả lời.
- `outside-assignment` cần scopeBasis cụ thể; thiếu capability không hợp lệ cho disposition này.
- `reviewedCaseIds`: snapshot tập case đã đối chiếu. Thêm case/feature mới sau review phải hiện diagnostics cần đối chiếu delta, không xóa dữ liệu cũ.
- `unresolved`: các khoảng trống thật chưa xác định được, kèm affectedFeatureIds/caseIds nếu có.
- `basis`: lời giải thích ngắn vì sao các nguồn đã đọc đủ cho phạm vi tuyên bố. Không thêm reviewer approval hay chữ ký.

Case giữ ID cũ và thêm tùy chọn:

- `featureIds`, `objectiveDepth`, `expectedBehavior`, `expectationBasis`.
- `coverageContext`: product/environment/origin/build, method/route/inputLocation, actorRef/role/relation, objectRef/state và objective. Chỉ các dimension có nghĩa cho câu hỏi; unknown là unknown, không tự điền từ operation gần nhất.
- `representation`: `{basis, representedVariants, excludedConclusions}` khi dùng test đại diện.
- `priority`: `high|normal|low` và `priorityBasis`; mặc định normal.

`requiredEvidence` tiếp tục là units hiện có, không tạo ngôn ngữ expression mới. Ví dụ feature personal pin có units ui-action, own-preference-read, sibling-preference-read; active API question khác giữ units active riêng. Các unit này chỉ là tên yêu cầu, không tự sinh observations.

Đối với criteria question trong `securityScope.questions`, thêm cùng `objectiveDepth`, `coverageContext` và `methodClass: zap-dast|zap-ui|zap-business-observation|outside-zap|unresolved`. Mapping này do intake xác định; subset `dast` ở §5.4 bao gồm ba nhóm ZAP thuộc assignment, không bao gồm outside-zap. Tên `dast` ở summary là phần đánh giá động qua ZAP, không biến UI/BOLA thành native active credit. Unknown methodClass không được âm thầm bỏ khỏi denominator: nếu có thể thuộc phần ZAP đang được giao, giữ gap mapping. Không cần sinh case/route giả cho outside-zap. Scope-level contract mới dùng `workflowVersion: 1` tương tự inventory; không có inventory track vẫn áp dụng được resolver theo criteria questions.

### 5.3. Evidence links cho closure mới

Thêm module `P/question_evidence.py` dùng chung cho responsibility và criteria projection. Contract mới của observation có `evidenceLinks`, mỗi link:

- `operationId`: attempt chứa kết quả, luôn kiểm tra tồn tại.
- `observationUnits`: units thực được hỗ trợ.
- `resultPath`: JSON Pointer đến readback đã giữ trong operation/result (pointer hợp lệ, không chỉ trỏ status tổng).
- `resultRead: true`, `basis`: diễn giải fact → unit; không dùng prose làm chứng minh tự động.
- `context`: dimension liên quan; phải khớp case/question hoặc có mapping tương thích được ghi cụ thể.
- `role`: `support` hoặc `context`. Context không cung cấp units.

Thêm `compatibility` tùy chọn khi kế thừa qua fixture/actor/build: `{basis, dimensions, operationIds}`. Phải giữ các dimension bắt buộc của câu hỏi, không chỉ `compatible:true`. Không cho URL/method/input khác được gộp bằng lý do chung chung. Nếu chưa xác minh tương thích, giữ quan sát riêng và gap mở. Không tự so semantic source code để chứng minh equivalence.

Thêm `resolvedEffects` cho unknown effect có readback: `{actionId, resolutionOperationId, resultPath, basis}`. Resolution phải liên kết đúng action/object và có kết quả đọc được. History unknown vẫn giữ nguyên; current pending-effect projection mới đánh dấu đã reconcile. Operation link đổi sang context không phải resolution.

Nguồn `pending_effects` là phép hợp của intent/unknown trong actionHistory/journal và operation có outcomeUnknown/pendingStart của RUN/continuation, trừ resolution hợp lệ. Không lấy riêng danh sách operation support của câu hỏi vì sẽ bỏ lọt unknown được chuyển sang context. Gắn dependency qua caseId, actionId, dependsOnCases và object context hiện có; không chặn toàn assignment vì unknown ở object độc lập. Nếu thiếu dữ liệu để xác định ảnh hưởng, trả diagnostic cần reconcile cho phần liên quan chưa xác định, không tự cho là unrelated. Giữ journal là nguồn authoritative cho việc cấm replay; resolver/report không được cấp quyền replay.

Các resultPath là pointer tương đối với operation được link. Pointer phải còn trỏ được trong report sau compact: nếu readback cần thiết nằm trong raw field bị loại, adapter tạo sanitized semantic readback tóm tắt bên trong operation mới/working projection, dẫn nguồn về raw private. Không đưa lại raw request/response/token vào report để giữ pointer. Không sửa operation lịch sử trên đĩa; dùng projection hoặc operation reconciliation mới để giữ nguồn gốc. Resolver kiểm tra cấu trúc/link, còn tính đúng của facts và interpretation vẫn do checker/tester xác minh.

Quy tắc resolver:

1. Với observation legacy không có `evidenceLinks`, giữ hành vi cũ, không dùng migration để tự đóng thêm.
2. Với evidenceLinks, chỉ union units từ support links đã đọc, context phù hợp, pointer có kết quả, không có unknown liên quan chưa reconcile. `observationUnits/evidenceUnits` caller khai phải là subset các units được links hỗ trợ; không tự copy requirements.
3. Attempt completed không tự cung cấp units. Attempt failed/partial có thể hỗ trợ units đã đọc trước lỗi; phải trỏ đúng phần readback, không dùng toàn attempt để suy đủ.
4. Required `responsibilityIds` vẫn là nghĩa vụ bắt buộc. Thêm `contextResponsibilityIds` nếu cần history; không tự chuyển linked case mở sang context. Case hiện tại chỉ đóng khi units đủ.
5. Không gộp outcome violated từ context/build cũ vào current retest. Trong cùng câu hỏi/context hiện hành, có violated được hỗ trợ thì giữ violation; original finding không bị xóa khi retest mới matched.
6. Policy chưa rõ: đủ factual observation có thể được ghi, nhưng security conclusion vẫn inconclusive nếu kỳ vọng bắt buộc chưa xác định. Không đóng câu hỏi compliance bằng factual observation đơn thuần.

`resolve_question_evidence(question, observation, operations, pending_effects)` trả `supportedUnits`, `missingUnits`, `contextDiagnostics`, `unresolvedEffectIds`, `supportOperationIds`, `contextOperationIds`; không tự đặt verdict. Caller reconciler/projection dùng kết quả này; không tạo engine status thứ hai.

### 5.4. Trạng thái hiển thị

Giữ `taskCompletion` chỉ `complete|partial` cho toàn assignment hiện hành. Thêm derived `completionSummary` trong RUN gồm:

- `assignment`: status và unresolved IDs.
- `dast`: status `complete|partial|not-assigned`, question IDs thuộc phần DAST đã được giao và gaps.
- `discovery`: `reviewed|gaps|legacy-unreviewed`, scope của review.
- `securityOutcome`: các finding/uncertainty hiện có, không đổi native severity/confidence.
- `remediation`: `not-assigned` trừ khi có assignment riêng; kế hoạch này không thực hiện remediation.

Subset DAST phải lấy từ mapping đã review lúc intake theo question method/scope, không chọn lại sau kết quả để được complete. Ngoài ZAP giữ unassessed của catalog, không N/A giả. Ba report giữ cùng taskCompletion và bundle lineage; summary không thay status gốc của attempts.

## 6. Helper cần implement và điểm tích hợp

### H1 — Đối soát feature với inventory

Tạo `P/business_discovery.py`:

- `validate_discovery_review(inventory)`: validate contract tùy chọn.
- `review_business_coverage(inventory)`: trả `unmappedFeatures`, `unreviewedCases`, `unresolvedSources`, `diagnostics`, `reviewStatus`. Pure function, không network/filesystem scan.
- Mapping nhiều feature → một case hoặc một feature → nhiều case đều hợp lệ; represented không được tính như execution mới.
- Với workflowVersion 1, gaps thật của H1 đi vào `reconcile().inventoryGaps`; complete boolean không được ghi đè chúng. Với legacy, diagnostic thiếu review hiển thị rõ nhưng giữ semantics legacy, không cưỡng bức migrate mọi run.
- Nguồn chưa review nhưng không liên quan assignment chỉ là limitation có basis; nguồn có ảnh hưởng đến phạm vi đang tuyên bố là gap. Không bắt read toàn repo.

Tích hợp `P/product_scope.py:validate_inventory/reconcile/apply_completion/compact_results`. Tránh lưu bản sao inventory riêng trong nhiều file. Bản đồ feature nằm trong inventory mà RUN đã mang theo; report compact phải giữ semantic references hữu ích sau redaction.

Thêm `scope review-business --inventory FILE` vào `product_scope_cli.py`, stdout JSON chỉ chứa diagnostic/ID và summary, exit 0 khi dữ liệu hợp lệ dù còn gap; input invalid exit nonzero. Không dispatch, không tạo bundle, không sửa file. Không thêm auto-crawler hay regex extractor đa framework trong đợt này.

### H2 — Chọn việc tiếp theo và giải thích thiếu executor

Tạo `P/work_selection.py:select_next_work(inventory, reconciliation, prerequisites, attempts, available_action_ids)`.

Tái sử dụng filtering của continue_work làm nguồn duy nhất cho eligibility: unknown effects, requires, dependsOnCases, seen actions, user stop vẫn giữ nguyên. Refactor filtering thành hàm dùng chung nếu cần, không copy ra hai implementation.

Trả `orderedCandidates`, `deferred`, `missingHandlers`, `reasonCodes`, `selectedActionId`. Mỗi candidate có caseId/actionId/kind và lý do. Không tạo handlers từ text, không import code hoặc chạy argv từ inventory.

Thứ tự mặc định khi có workflowVersion 1:

1. Reconcile unknown liên quan có reader sẵn; nếu reader unavailable chỉ chặn nhánh phụ thuộc.
2. Readback kết quả đã có có thể đóng gap (đánh dấu action metadata `usesExistingResult: true`; không coi mọi read là readback).
3. Execute khả thi, theo priority high → normal → low.
4. Prepare/repair được giao, có bước cụ thể và dependency có thể mở; tác động high có thể lên trước execute low nếu ghi `unblocksCaseIds` hợp lệ.
5. Tie-break giữ thứ tự case/action cũ để ổn định và tái sử dụng fixture. Không đoán cost từ tên action.

Các action metadata mới chỉ gồm `usesExistingResult`, `unblocksCaseIds`, `selectionBasis`; optional. Khi thiếu metadata dùng thứ tự ổn định hiện tại. Không tự vòng lặp retry action failed với ID mới. Khi phải allocation mới cần thay đổi prerequisite/cause được ghi và safety gates hiện hành.

Tích hợp continue_work dùng selector, ghi decision vào kết quả continuation (không giả operation). Nếu còn gap nhưng không có handler, trả missingHandlers và next step prepare-adapter rõ; không break rồi kết luận hết việc. Helper đề xuất này không tạo approval hoặc thay đổi max_actions.

Thêm `scope next-work` nhận cùng inventory/observations/prerequisites và tùy chọn actions/previous phù hợp CLI hiện có, chỉ đọc. Phải dùng chung loader/history handling với continue để không đánh rơi pending intents. Nếu --actions thiếu, trả đề xuất ở mức case và capability-gap; không giả có executor.

### H3 — Mapping capability và hợp đồng adapter tối thiểu

Mở rộng `executor_routing.py` bằng `map_question_capability(question, candidates)` ở mức dữ liệu review. Tái sử dụng classify_workload/choose_executor cho phần request/schema/auth; các dữ kiện UI/fixture/readback do adapter/operator khai với basis.

Output cần có questionId, selected executor hoặc null, support đã xác minh (transport/auth/request/fixture/readback), missingPrimitive, nextPreparation, verificationLevel (`source-reviewed|offline-checked|runtime-observed`) và deployment context nếu có. Không đồng nhất schema-compatible với runtime-qualified.

Đưa một mẫu adapter vào `L/examples/question_adapter.py` dùng dữ liệu giả, không nhúng route/role/token sản phẩm. Mẫu tách các hàm prepare, identity, execute, readback, cleanup; prepare trả fixture refs và ownership facts; execute journal intent trước dispatch, giữ ACK; readback gọi H4 và xuất evidenceLinks; cleanup chỉ thao tác tài nguyên sở hữu đã được phép. Mẫu sử dụng dependency injection cho transport, không dựng client bỏ qua ZAP/admission. CLI continue hiện chỉ dispatch entry được allowlist: không mở arbitrary plugin loading vì mẫu này.

Cần một test tích hợp adapter mẫu bằng fake transport vào reconciliation để chứng minh có đường sử dụng thực; không chỉ thêm interface bỏ trống. Không sửa finalsource-only recipe thành “generic” bằng return thành công. Các sản phẩm mới vẫn cần mapping có thật.

### H4 — Readiness nhiều tầng, gắn đúng object

Tạo `P/readiness.py`, chỉ stdlib, có API:

`wait_for_observation(sample, evaluate, *, context, timeout_seconds, interval_seconds, remaining_seconds, clock, sleep, cancelled)`.

- sample là callback read-only do code adapter đã review cung cấp; không nhận code string từ JSON. evaluate trả `ready|pending|terminal-failure|context-mismatch` và facts đã sanitize.
- context chỉ định object/operation/actor liên quan, stage cần chờ: ack/domain/processing/persistence/consumer. Stage không được tự suy từ HTTP200.
- Dùng monotonic clock; deadline hiệu lực là min(timeout được chọn, execution remaining). Số dương hữu hạn; interval > 0; sleep không vượt remaining. Một lần sample cũng phải nhận/cưỡng chế timeout transport còn lại từ adapter, không để callback treo vượt deadline.
- Trả `ready|timeout|terminal-failure|context-mismatch|cancelled|reader-error`, stage, elapsed, missing conditions và facts cuối đã lọc. Giữ `outcomeUnknown` theo mutation journal; timeout không tự biến unknown thành failed/no-effect.
- Reader lỗi không retry mutation. Context mismatch dừng đọc theo binding sai, không đợi đủ timeout rồi pass.
- Không catch mọi exception rồi sleep; transient read errors chỉ được retry khi adapter phân loại rõ, có budget và context không đổi. Không log request/header/token/raw exception.
- Nếu callback trả ACK nhưng câu hỏi cần consumer: tiếp tục. Với boundary-only question, không đợi media/segment ngoài yêu cầu.

Để giữ phạm vi implement nhỏ: **không thay schema/predicate cap 12 giây của FE research lane trong đợt này**. H4 là primitive cho adapter Python có reader nhiều tầng; runner finite hiện tại giữ giới hạn công khai. Tích hợp adapter mẫu H3 và một reader fake async dùng H4, chứng minh reuse; JS product-local cũ không bị viết lại. Reference phải nói rõ đây chưa phải sửa runtime background đã lưu hay hỗ trợ generic media trong FE runner. Nếu sau này chọn FE finite lane để chạy case cần timeout khác, đó là thay đổi schema/worker/pins riêng, không bypass cap qua H4.

### H5 — Question closure và reporting

Implement resolver ở §5.3 trước khi sửa projection. Tích hợp vào `security_scope.project_scope` và contract mới của product_scope; core vẫn hỗ trợ legacy.

- Với version mới, op status chỉ mô tả attempt; unit-level readback quyết định đủ hay thiếu. Required case còn mở vẫn chặn phần liên quan.
- Context link không chặn chỉ vì attempt partial; unknown effect liên quan vẫn chặn cho đến khi có resolution hợp lệ.
- `continue_work` không union evidenceLinks qua context khác; kết quả khác context giữ riêng cho review hoặc trả diagnostic, không trộn units và outcome. Legacy path giữ hành vi đã document, thêm diagnostic khi có thông tin context xung đột.
- Validate pointer/operation/context trước projection. Resolver không tự diễn giải raw HTTP thành matched/violated; adapter chịu trách nhiệm semantics, tests cần fixtures có expectation độc lập.
- `compact_results` xuất completionSummary và các gaps nhất quán. Extend `validate_result_ids`/`security_scope.validate_bundle` để kiểm tra reference mới cả support/context/resolution sau sanitization; không làm mất history chỉ để validator qua.
- Không sửa `.local/.../session.py` hay report 100ms. Viết fixture synthetic mô phỏng hardcode và test composer mới từ reconciliation. Ghi cách adapter tương lai gọi composer thay hardcode trong reference.
- `review_open_work.py` giữ compatibility key `workComplete`, thêm `declaredListHandled` cùng giá trị và cảnh báo đây không phải assignment completion. Không buộc script optional này import library thiếu dependency; không triển khai logic completion mới lần thứ ba.

## 7. Sửa tài liệu điều hướng, không thêm tầng quy định trùng lặp

Giữ SKILL.md ngắn. Mở đầu workflow mới: charter → feature/API map → finite questions → capability mapping → execute/readback → reconcile/choose next → scoped conclusion. Một đường đọc theo quyết định, không bắt tải mọi reference.

Sửa tại chỗ:

1. `SKILL.md`: thêm bước đối chiếu feature trước khi nói hết việc; chỉ rõ assessment có thể kết thúc với findings và catalog limitations. Giữ các boundary hiện có.
2. `R/product-discovery.md`: hướng dẫn hai chiều, H1, cách nhóm đại diện, ví dụ pin/spotlight/background/reaction dùng làm minh họa chứ không default checklist.
3. `R/assessment-scope-and-completion.md`: charter, depth, completionSummary, phân biệt coverage gap với giới hạn khái quát; không lặp lại toàn guide khác.
4. `R/responsibility-loop.md`: H1/H2/H5, sample input/output ngắn, cách unknown và missing handler ảnh hưởng nhánh nào.
5. `R/operational-readback.md`: H4, stage và identity, ví dụ ACK trước terminal, timeout khác SLA; unit links cho attempt partial.
6. `R/runner-routing.md`: giới hạn helper mới, mapping capability và lựa chọn adapter; không claim mở rộng FE recipe/body/auth support.
7. `R/local-remediation-and-continuation.md`: phân biệt safety invariant với restriction phiên; tiến hành fixture/regression đã được giao, đánh giá effort sửa helper tương xứng; không vòng diagnosis vô hạn.
8. `R/user-security-scope.md`, `R/product-assessment-handoff.md`, `R/operations-and-results.md`: contract links/completion mới, legacy path và báo hai tầng DAST/catalog.
9. `R/operational-validation.md`: thêm các scenario §9; nêu offline checks không chứng minh future agent behavior/runtime.
10. `agents/openai.yaml`: prompt ngắn hướng feature/question/next useful work, không thêm lời hứa full assurance.

Chỉ chỉnh `track-intents.md`, `retention-stop-and-recovery.md`, `operational-knowledge.md` nếu có câu trực tiếp mâu thuẫn với thiết kế này; không rewrite cả bộ reference. Kiểm tra link sau sửa. Quyền đã có tiếp tục hiệu lực, không có gate user duyệt charter thường lệ.

## 8. Trình tự implement cụ thể

### Bước 0 — Chuẩn bị baseline

Đọc AGENTS áp dụng, SKILL hiện tại, kế hoạch này; git status/diff để nhận diện thay đổi có trước. Đọc các hàm nêu trên thay vì audit lại toàn repo. Nếu working tree có thay đổi mới làm lệch contract, giữ intent và điều chỉnh điểm tích hợp, ghi rõ khác biệt; chỉ hỏi khi thay đổi scope/quyền không thể tự suy.

Dùng Python 3.13 và requirements.lock. Tìm interpreter/dependency environment hiện có; nếu chưa có, trong nhiệm vụ implement được phép tạo venv riêng ngoài thư mục skill/product và cài đúng lock. Không cài global, không copy venv vào skill, không khởi động scanner để chạy test offline. Ghi interpreter đã dùng. Kế hoạch không phụ thuộc source hoặc credentials của sản phẩm 100ms để test.

### Bước 1 — Contracts và discovery

Implement H1 và validator optional fields; thêm fixtures nhỏ và CLI review-business; tích hợp inventoryGaps cho workflowVersion 1. Dữ liệu legacy không đổi semantics. Xác minh thêm feature chưa map làm new workflow partial nhưng vẫn cho phép chạy case độc lập.

### Bước 2 — Evidence resolver và projection

Implement H5/§5.3, positive/negative tests trước khi sửa composer. Tích hợp product_scope, security_scope, continuation merge và report validator. Đây là thay đổi nhạy cảm nhất: không có đường completed-only, không được dùng context để giấu unknown, không làm mất missing units khi copy/compact.

### Bước 3 — Next-work và capability

Refactor eligibility chung, implement H2, CLI chỉ đọc, tích hợp continue_work. Thêm H3 mapping reuse executor_routing. Kiểm tra missing handler vẫn visible, stop user được tôn trọng, state unknown chỉ chặn dependency thực. Không thay đổi admission/journal ordering.

### Bước 4 — Readiness và adapter mẫu

Implement H4 và adapter fake tích hợp; dùng fake clock/sleep, không sleep thật để test chậm. Test actor/object mismatch, reader error, cancellation và deadline bao sample. Không mở rộng protocol của FE finite runner. Mẫu adapter phải xuất observations được H5 tiêu thụ, không tự đạt requiredEvidence.

### Bước 5 — Reporting và hướng dẫn vận hành

Hoàn thiện completionSummary, CLI/report compatibility, optional review helper. Viết docs theo §7, bỏ lời lặp không cần thiết. Mẫu charter và cách gọi CLI phải khớp code đã implement, không dùng flag tưởng tượng. Không thay status các assessment lịch sử để demo.

### Bước 6 — Kiểm tra và bàn giao

Chạy tests mới và các regression offline liên quan ở §9; kiểm tra diff chỉ có thay đổi cần thiết, links/docs không mâu thuẫn. Báo files sửa, checks thực chạy và giới hạn chưa kiểm chứng. Dừng khi implementation scope đạt; không tiếp tục scan sản phẩm để làm đẹp acceptance.

## 9. Acceptance và kiểm tra hồi quy

### 9.1. Scenario bắt buộc của implementation

Các scenario dưới đây là test cho helpers, không trở thành checklist bắt buộc mỗi product assessment. Dùng synthetic data; không sao chép raw/token/media lịch sử vào skill.

1. **Bỏ sót feature đã review:** inventory có pin đủ units, discoveryReview có background chưa map → inventory gap background; không complete. Thêm case tương ứng hoặc disposition có basis phù hợp mới giải quyết gap. Omit khỏi cả hai tập → helper không phát hiện; ghi giới hạn bằng walkthrough, không viết test khẳng định tìm được.
2. **Đại diện hợp lý:** hai biến thể cùng boundary dùng chung case, basis và excluded conclusions rõ → không bắt chạy mỗi biến thể. Thay khác owner/consumer → phải có câu hỏi/quan sát bổ sung, không blanket đại diện.
3. **Không mở rộng functional scope:** layout decoration không có nghĩa vụ security riêng được `no-additional-question` có basis; vẫn giữ related API security question nếu đã giao.
4. **Partial attempt, unit đủ:** attempt A lỗi ở bước sau pin; pin support pointer/context hợp lệ → pin observed; background chưa có units → mở. Không dựa status completed.
5. **Followup hợp lệ:** A partial là context, B đọc đủ units đúng câu hỏi → question observed, A vẫn partial. Case required còn open → không được đóng criterion chỉ vì B tồn tại.
6. **Unknown không bị giấu:** đổi operation A unknown sang context → affected question vẫn mở; resolution readback đúng action/object mới gỡ. Unrelated independent question vẫn eligible.
7. **Sai context:** cùng actor/role nhưng object/build/origin/input khác → không union mặc định. Compatible inheritance có basis và đúng dimensions chỉ hỗ trợ câu hỏi hữu hạn được review, không làm biến mất finding cũ.
8. **Boundary không thay processing:** followup 409 đúng stale-version chỉ cho boundary units, thiếu sink/processing vẫn mở. Required units không được copy từ plan.
9. **Violation là tested:** đủ units và violated → coverage complete, finding còn open, remediation not-assigned. Catalog có governance chưa đánh giá → assignment partial, DAST subset complete nếu thực sự đã đủ.
10. **ACK trước result:** fake samples ACK → pending → đúng object ready → chỉ đóng ở sample cuối. Fixture chậm trong deadline hợp lệ không false fail.
11. **Timeout/read error/cancel:** trả đúng trạng thái, không repeat execute; deadline hợp lệ, không sleep/sample vượt remaining theo contract; no unbounded retry. Không gọi timeout là policy violation khi không có SLA.
12. **Boundary không cần media:** question boundary-only hoàn thành qua observations đúng mà không yêu cầu decoder/segment.
13. **Chọn nhánh độc lập:** media prerequisite blocked, reaction ready → chọn reaction; prep high-impact có unblocksCaseIds được cân nhắc trước execute low. Thiếu handler → missingHandlers/nextPreparation, không complete.
14. **Giữ safety:** prior intent/ACK/unknown không redispatch; user stop không chạy action; effect read không được trá hình compiled mutation; journal intent luôn trước effect.
15. **Không có capability:** source-compatible nhưng runtime chưa kiểm tra → verificationLevel không bị nâng. Request schema/auth không phù hợp vẫn bị executor_routing từ chối; không biến thành ngoài scope.
16. **Legacy và report:** old inputs giữ semantics; new fields survives compact/redaction, mọi ID/pointer/reference hợp lệ; ba reports đồng nhất completion/bundle, notPerformed/nextSteps khớp gaps; invalid refs bị từ chối trước ghi.
17. **Quyền/regression:** walkthrough docs: fixture mới/regression đã được giao được dùng; unknown mutation vẫn phải reconcile; không xin lại quyền thường lệ, không coi source-read audit này là quyền scan mới.
18. **Không làm mới history:** snapshot synthetic old attempt/pins/findings trước/sau recomposition không đổi; chỉ derived report mới thay đổi. Không ghi đè assessment 100ms để kiểm tra.

### 9.2. Tập test và cách chạy

Thêm `test_business_discovery.py`, `test_question_evidence.py`, `test_work_selection.py`, `test_readiness.py`, `test_question_adapter.py`; mở rộng test_security_scope/test_pm_scope/test_work_session_checkpoint khi sửa đường tương ứng. Dùng unittest theo repo; không thêm framework mới.

Regression ưu tiên: `test_pm_scope`, `test_security_scope`, `test_work_session_checkpoint`, `test_executor_routing`, `test_operational_readback`, `test_report_reconciliation`, `test_product_continuation`, `test_discovery_transport`, `test_portability`. Đọc setup của từng file trước chạy: chỉ chạy phần offline; test cần Docker/target/dependency ngoài scope phải được ghi skipped/not-run có lý do, không mock để giả pass runtime.

Ví dụ lệnh sau khi chọn được interpreter có dependencies (thay đường dẫn interpreter thật):

```sh
cd '/Users/hahoangloc/Working/testing tool'
ZAP_ASSESSMENT_ROOT="$PWD/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment"
ZAP_TEST_PYTHON='/absolute/path/to/venv/bin/python'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ZAP_ASSESSMENT_ROOT/src:$ZAP_ASSESSMENT_ROOT/tests" \
  "$ZAP_TEST_PYTHON" -B -m unittest \
  test_business_discovery test_question_evidence test_work_selection \
  test_readiness test_question_adapter test_security_scope test_pm_scope \
  test_work_session_checkpoint test_executor_routing -v
```

Các tên test mới là deliverables sẽ tạo, chưa tồn tại tại thời điểm kế hoạch. Không chạy discovery toàn suite vô điều kiện nếu có integration tests khởi tạo runtime. Lỗi baseline có sẵn phải tách khỏi regression của thay đổi; sửa trong phạm vi nếu liên quan, không che bằng skip mới tùy tiện.

### 9.3. Điều kiện đủ để bàn giao implementation

- Workflow mới đi trọn đường từ feature map qua finite question tới capability, fake adapter/readiness, evidence reconciliation và report bằng test offline.
- Các scenario quan trọng về false closure, valid closure, unknown, missing handler và legacy pass trong môi trường dependency đúng; nêu rõ phần chưa chạy.
- Không làm yếu admission, resource reserve, TLS/auth, target binding, immutable history; không sinh source-only findings vào ZAP report.
- Docs và CLI thực tế thống nhất, không ép thêm approval/checklist/qualification toàn platform.
- Diff được review và giữ các thay đổi có trước. Không yêu cầu hai fresh product runs hoặc đóng hết catalog để nghiệm thu cải tiến skill.

Không tuyên bố đã chứng minh agent tương lai luôn discovery đủ, helper tự hiểu policy, hoặc mọi product/auth/media lane đã được qualify. Các kết luận đó cần assessment thực được giao sau này.

## 10. Các quyết định không mở lại trong window implement

- Không tạo universal business crawler, AST extractor nhiều framework, graph database hoặc scoring engine.
- Không tạo UI/canvas/dashboard, không thêm bundle bàn giao ngoài RUN/ALERTS/SCOPE_ALERTS cho product assessment.
- Không sửa historical adapter/report 100ms; chỉ dùng làm căn cứ và mô hình hóa synthetic scenarios.
- Không mở rộng toàn bộ FE/BE runner, không nâng timeout/cap hàng loạt, không sửa global guard để kế hoạch dễ pass.
- Không coi mọi UI feature là scope security mới; giữ quyền tester nhóm biến thể hợp lý và ghi rationale ngắn.
- Không coi unresolved criteria ngoài phương pháp là DAST cần chạy tiếp vô hạn; giữ overall partial với partial completion rõ phạm vi.
- Không dùng việc thiếu metadata mới để vô hiệu hóa mọi dữ liệu legacy hoặc ép migrate tất cả trước khi làm việc.
- Không giao việc thiết kế lại cho user: contract, helper và thứ tự ở trên đã là hướng triển khai. Agent sau chỉ cần chọn chi tiết coding tương thích source thực tế.

## 11. Điểm định vị source để agent implement đọc nhanh

Audit gốc: `docs/reviews/zap-skill-business-coverage-gap-analysis-20261102.md`.

Đường code chính:

- `P/product_scope.py`: validate_inventory, inventory_from_operations, reconcile, continue_work, apply_completion, compact_results, validate_result_ids.
- `P/product_workflow.py`: reconcile_responsibilities.
- `P/security_scope.py`: normalize_scope, project_scope, validate_bundle.
- `P/product_scope_cli.py`: main, read_action_result và history loading.
- `P/executor_routing.py`: classify_workload, assess_executor, choose_executor.
- `P/fe_authenticated_contract.py`: predicate, pins; `P/fe_authenticated_recipes.py`: prepare.
- `P/fe_authenticated_browser.py`: AuthenticatedBrowser và worker; `P/ui_webdriver.py`: wait_for/transport timeouts. Chỉ đọc để hiểu boundary H4, chưa giao thay finite worker.
- `S/scripts/review_open_work.py`: review_work/review_checkpoint/review_session.

Minh họa lịch sử chỉ đọc:

- `.local/100ms-fresh-20261101/session.py`: init/report.
- `.local/100ms-fresh-20261101/final_ui_background.mjs`: readiness sau device Apply.
- `assessment-results/100ms-fresh-20261101/RUN.json`: final-ui-focus-journey, final-ui-background-journey, final-background-prerequisite-diagnosis, final-ui-bg-ready-journey, final-ui-reaction-journey, final-transport-offline-reconciliation, final-missing-transport-readback, final-historical-native-input-reconciliation.

Source sản phẩm minh họa: `/Users/hahoangloc/Working/100ms-Video-Conferencing-and-Live-Streaming-sol-full/finalsource/fe/src/`. Chỉ cần nếu muốn xem lại mapping; implementation/test skill không phụ thuộc thư mục này và không được sửa nó.

## 12. Prompt giao việc cho window sạch

> Đọc và implement `/Users/hahoangloc/Working/testing tool/docs/reviews/zap-skill-tester-workflow-implementation-plan-20261102.md`. Đây là kế hoạch đã chốt hướng sau tái audit theo nghiệp vụ tester. Làm trong skill project-local mcp-zap-repo-operations, giữ working tree có trước, thực hiện các bước 0–6 và acceptance offline. Tập trung implementation, tương thích legacy, không cần audit lại toàn bộ hay hỏi lựa chọn thiết kế thường lệ. Không scan/provision runtime, không sửa sản phẩm hoặc dữ liệu assessment lịch sử, không sync personal skill/commit/push. Nếu source hiện tại có drift, thích ứng điểm tích hợp nhưng giữ các invariants của kế hoạch. Báo thay đổi, kiểm tra thực chạy và giới hạn khi hoàn thành.

Bản kế hoạch này là sản phẩm cuối của lượt tái đánh giá. Chưa thay skill/helper hoặc kết luận bảo mật của assessment; quy trình hiện tại dừng tại đây.
