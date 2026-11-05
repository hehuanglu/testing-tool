# Phase 3 — Điểm kết thúc và con đường đóng đợt kiểm thử ZAP

Ngày 02/11/2026. Trạng thái: **kế hoạch triển khai và vận hành đã chốt; chưa implement trong lượt lập kế hoạch**.

## 1. Quyết định cốt lõi

**Một đợt kiểm thử phải có thể kết thúc mà không cần chứng minh toàn sản phẩm an toàn hoặc hoàn tất mọi tiêu chí trong catalog.**

Phase 3 bổ sung đường đi đến điểm kết thúc thực tế, không tiếp tục chỉ làm rõ nhãn `partial`. Sau phase này, báo cáo phải trả lời riêng:

1. Đợt kiểm thử đang làm, tạm dừng hay đã kết thúc?
2. Trong phạm vi được giao, đã kiểm thử đủ hay còn thiếu gì?
3. Kết quả bảo mật là gì và finding nào còn mở?
4. Có điều kiện nào cần xảy ra để mở một đợt tiếp theo?

Điểm đích hợp lệ:

- **Hoàn tất đợt kiểm thử:** câu hỏi thuộc đợt đã có kết quả đủ; không còn gap thực thi hoặc discovery ảnh hưởng phạm vi đợt.
- **Kết thúc đợt kiểm thử với giới hạn:** đã xử lý hết công việc hữu ích khả thi trong quyền; các phần không kiểm thử được có căn cứ cụ thể và điều kiện mở lại. Coverage/catalog có thể partial.
- **Chưa thể kết thúc:** còn công việc hữu ích khả thi hoặc còn phần backlog chưa xét có thể thay đổi quyết định.

“Kết thúc với giới hạn” không phải scope exclusion, không phải criterion pass, không phải chấp nhận rủi ro. Không sửa security verdict hay che phần chưa kiểm thử.

Phase 3 phải làm cả hai phần: **có cơ chế closure trong skill và dùng nó đối soát backlog 100ms đã lưu để tiến tới một quyết định kết thúc có căn cứ**. Không chỉ thêm helper rồi chọn vài examples như phase 2.

## 2. Phạm vi, tài liệu và baseline

Workspace: `/Users/hahoangloc/Working/testing tool`.

Đọc:

- `docs/reviews/zap-workflow-phase2-implementation-result-20261102.md`.
- `docs/reviews/zap-workflow-post-implementation-review-20261102.md`.
- Kế hoạch này và skill project-local `.agents/skills/mcp-zap-repo-operations/SKILL.md`.
- Reference completion/residual/recovery theo điểm sửa, không cần audit lại toàn bộ repo.

Baseline phase 2: 235 tests, 227 pass và 8 skip optional source được báo cáo; phase 3 chạy lại bộ liên quan để xác nhận baseline thực tế. HEAD trước đó là `18f17860bad327a18345f949644aac4d40b7fece`, nhưng working tree đã có nhiều implementation chưa commit. Giữ nội dung working tree, không reset/stash/revert về HEAD.

Ký hiệu:

- `S = .agents/skills/mcp-zap-repo-operations`
- `L = S/lib/zap-product-assessment`
- `P = L/src/zap_assessment`
- `T = L/tests`
- `R = S/references`

### Trong scope implement

- Mô hình kết thúc đợt, đường xử lý aggregate và backlog, reporting/CLI/docs/tests.
- Đọc và đối soát toàn bộ residual đã khai trong hai assessment 100ms, tận dụng readback hiện có.
- Chuẩn bị projection/bundle closure riêng từ dữ liệu đã lưu, không ghi đè bundle chính thức cũ.

### Ngoài scope mặc định

- Traffic mới, restart/provision Docker, tạo fixture mới, sửa sản phẩm hoặc deployment.
- Qualification runner/auth/media toàn platform, full rescan hoặc tìm mọi lỗi lịch sử.
- Tự đổi policy/SLA, chấp nhận residual risk, commit/push/sync personal skill.

Nếu đối soát phát hiện một câu hỏi thật cần runtime mới, chuẩn bị chính xác workload/điều kiện thực thi và báo `ready-for-execution` cho phần đó. **Không được dùng giới hạn offline của lượt implement làm bằng chứng rằng bản thân assessment không thể kiểm thử tiếp.** Việc vận hành runtime tiếp theo phải theo assignment/quyền còn hiệu lực tại thời điểm được giao; kế hoạch này không tự phát lệnh scan.

## 3. Vấn đề phase 3 phải sửa dứt điểm

Phase 2 đã giải quyết historical/current presentation, nhưng cố ý chưa thay closure engine. Hệ quả:

- `taskCompletion` phụ thuộc toàn bộ criterion/questions đủ kết quả.
- `retained-aggregate` giữ mở dù đã phân rã và các phần có nghĩa đã có disposition.
- Residual helper có thể nói không còn dynamic action nhưng báo cáo không có trạng thái cuối cho đợt kiểm thử.
- Việc thiếu root cause lịch sử có thể còn được trình bày như blocker của testing, dù không nằm trong câu hỏi được giao.
- Review 8/50 criterion hữu ích để nghiệm thu helper, chưa đủ kết luận về backlog toàn assessment.

Không giải quyết bằng đổi hàng loạt `partial` thành `complete`. Giải quyết bằng **phân biệt lifecycle của đợt với độ đầy đủ của coverage; cho aggregate một đường đóng dựa trên mapping; và thực hiện đối soát hết backlog đã khai**.

## 4. Mô hình trạng thái chốt cho phase 3

### 4.1. Một trạng thái lifecycle chính

Thêm optional `assessmentRound` version 1 vào working RUN và ba report, cùng identity:

- `id`: ID ổn định của đợt; không đổi theo mỗi round CLI, fixture hoặc chat.
- `objective`, `scopeBasis`: mục tiêu và nguồn yêu cầu.
- `assessmentId`, `product`, `environment`.
- `scopeRevision`: revision đang áp dụng.
- `reviewUniverse`: tập criteria, questions/cases, residual sources và route/feature inventories dùng để quyết định đợt kết thúc.
- `status`: `in-progress|checkpointed|completed|completed-with-limitations|stopped-by-user`.
- `closure`: kết quả kiểm tra closure và refs căn cứ, nếu đã finalize.

Không tạo một “đợt” mới chỉ chứa hai case dễ để nói completed khi user đang giao tiếp tục assessment rộng. Với continuation 100ms này, reviewUniverse phải bao phủ assignment tiếp tục và toàn bộ backlog đã biết, giữ phần ngoài phương pháp dưới dạng limitation/obligation chưa trả lời.

### 4.2. Ý nghĩa trạng thái

- `in-progress`: còn action hữu ích, residual cần review, hoặc chưa đủ thông tin để quyết định.
- `checkpointed`: giữ state để tiếp tục vì giới hạn phiên/context/điều kiện tạm thời; không phải kết thúc đợt.
- `completed`: không còn applicable unanswered testing duties trong phạm vi đợt; discovery đã đối soát phù hợp phạm vi; effects/resources đã xử lý.
- `completed-with-limitations`: không còn action hữu ích khả thi cần thực hiện trong quyền/phương pháp của đợt, nhưng có coverage gaps được giải thích và điều kiện mở lại. Có thể còn finding/remediation/catalog obligations.
- `stopped-by-user`: user yêu cầu kết thúc trước điều kiện trên; giữ phần chưa làm. Yêu cầu “pause/tiếp tục sau” dùng checkpointed, không stopped-by-user.

Finding còn mở không bắt buộc completed-with-limitations nếu coverage của đợt thực sự đủ. Violation có đủ observations là kết quả kiểm thử, không phải thiếu coverage.

### 4.3. Giữ tương thích nhưng đổi cách trình bày

Giữ `taskCompletion: complete|partial` và `handoffClosesTask` theo semantics legacy về nghĩa vụ/coverage. Không dùng chúng làm headline duy nhất của sản phẩm mới.

Thêm `taskCompletionMeaning: assigned-obligation-coverage` và `roundClosed: true|false` derived. Không đổi `handoffClosesTask` thành true khi assignment còn partial. Trong completionSummary thêm `round` gồm id/status/closureReason/unansweredObligationIds.

Final response và tài liệu phải dùng:

> Đợt kiểm thử: kết thúc với giới hạn. Coverage phạm vi được giao: partial. Còn: [các gap cụ thể]. Mở lại khi: [điều kiện].

Không chỉ nói “vẫn partial; cần chat tiếp”. Đồng thời không nói “đã hoàn thành toàn assessment” khi chỉ roundClosed true.

Không có dữ liệu assessmentRound trên legacy report: giữ legacy behavior, hiển thị lifecycle chưa xác định, không tự suy closed từ last operation hoặc timestamp.

## 5. Điều kiện closure: hữu hạn và có thể kiểm tra

### 5.1. Điều kiện chung cho completed và completed-with-limitations

1. **Review universe rõ:** đối chiếu scope gốc, inventory hiện có và residual sources. Không còn nhóm chưa review có thể ảnh hưởng kết luận đợt; delta review không đóng round toàn assignment.
2. **Backlog đã được xử lý:** mỗi nghĩa vụ/nhóm đã có kết quả, N/A có căn cứ, limitation/dependency cụ thể, hoặc scope disposition từ user. Không còn item chỉ nói “more testing”, “partial”, “needs investigation” mà chưa xét hành động tiếp theo.
3. **Không còn action hữu ích khả thi chưa làm:** tính cả readback từ dữ liệu đã lưu, preparation/repair nhỏ trong quyền và mapping đang cần hoàn thiện. Thiếu handler, script lỗi hoặc chưa lên lịch không tự thành blocker ngoài quyền.
4. **Effects/resources được kiểm soát:** không còn producer đang chạy không rõ, mutation outcome chưa đọc khi còn đường đọc khả thi, cleanup cần làm trong quyền hoặc fixture đang ảnh hưởng môi trường mà chưa xử lý.
5. **Báo cáo bàn giao đầy đủ:** findings/provenance, coverage, limitations và reopen conditions nhất quán; tham chiếu làm việc cho resume rõ; chưa có dữ liệu không được điền pass.

Đối với unknown effect thật sự không thể reconcile do access/resource đã mất: không coi resolved. Chỉ có thể kết thúc với giới hạn nếu đã ghi exact effect/last-known-state, vì sao readback hiện không khả thi, phạm vi tác động chưa biết, no-replay rule, resource disposition và người/đầu mối có thể xử lý nếu đã biết. Không bịa “đã chuyển giao” cho người chưa nhận. Nếu có khả năng producer còn đang gây tác động và chưa có biện pháp containment trong quyền/đầu mối xử lý, chỉ checkpoint/escalation, không clean closure.

### 5.2. Chọn completed hay completed-with-limitations

- Completed: applicable testing duties thuộc round đều observed hoặc grounded N/A; không còn unanswered assigned testing duty. Finding/policy verdict có thể violation nếu expectation đã rõ.
- Completed-with-limitations: còn unanswered duty, nhưng từng duty có lý do dừng đúng và không còn next action khả thi trong phạm vi; giữ coverage partial.
- Generalization limits không được nâng thành unanswered duty nếu scope không yêu cầu. Nếu chỉ có kiểu giới hạn này và mọi duty đã trả lời, vẫn có thể completed.
- Method limits ở catalog được giao vẫn là unanswered catalog obligation. Round ZAP có thể completed-with-limitations; không certify catalog.

### 5.3. Các lý do dừng hợp lệ

- Access/actor/environment/policy cần thiết thực sự không có, đã xét các nguồn/options hợp lệ.
- Câu hỏi đòi phương pháp ngoài assignment hiện tại.
- Capability thiếu cần thay đổi lớn hoặc boundary/quyền mới; có mô tả primitive còn thiếu, options đã xét và vì sao repair nhỏ không đủ. Không chỉ ghi “khó/tốn thời gian”.
- User giới hạn phạm vi/thời gian cụ thể: ghi đúng nguồn; không tự tạo quota.
- Câu hỏi đã được trả lời, phần còn lại chỉ là khái quát hóa hoặc điều tra nguyên nhân không được giao.

Không cần thử mọi cách, số lần retry cố định, chứng minh impossibility hay exact root cause cho mọi dependency. Cần đủ thông tin để một tester khác hiểu vì sao bước tiếp theo không còn hữu ích/khả thi trong phạm vi.

## 6. Con đường dẫn tới closure — quy trình tester phải thực hiện

### Bước A — Chốt universe một lần, review delta khi có lý do

Dùng original scope, inventories và residual đã lưu để lập danh sách nghĩa vụ đang xử lý. Không lấy số actions hiện có làm universe. Không buộc khám phá lại toàn repo nếu source/scope không đổi và discovery đã có căn cứ.

Đối với 100ms: xét đủ 50 criterion về applicability/method/residual disposition; giữ liên kết 37 route units và feature groups hiện có. Không có nghĩa chạy 50 test hoặc mọi tổ hợp route/role/state.

Mỗi criterion phải có một trong ba mô tả: không có residual testing duty còn mở theo readback; có residual atoms được review; hoặc chưa rõ và cần review cụ thể. Criterion N/A vẫn có basis, không cần tạo test giả.

### Bước B — Dọn backlog bằng kết quả hiện có trước

Với mỗi nhóm partial:

1. Đọc câu hỏi gốc và sufficient observations.
2. Xác định observations đã có, đúng actor/object/build/objective hay không.
3. Xác định thiếu **fact cụ thể nào**, không dùng status của attempt thay fact.
4. Nếu fact đã có: tạo evidence mapping/readback hợp lệ; giữ attempt cũ nguyên trạng.
5. Nếu thiếu fact: ghi câu hỏi hữu hạn và action nhỏ nhất có thể trả lời.
6. Nếu phần còn lại chỉ là giới hạn hoặc causal analysis ngoài assignment: ghi limitation/context, không giữ nó trong executable testing backlog.

Mục tiêu là ít action hơn nhưng đúng nghĩa, không làm đẹp con số coverage. Không lấy 409 stale-version thay processing credit, không lấy UI/passive thay native active khi active đã được giao.

### Bước C — Phân biệt root cause với missing observation

Nếu câu hỏi là “STOP có chấm dứt recording trong điều kiện đã chọn không?”, quan sát recording tiếp tục có thể trả lời bằng violation/inconclusive tùy policy. Không bắt tìm exact cause để công nhận đã quan sát hành vi.

Nếu câu hỏi là “payload đến processing path nào?”, fixture hỏng trước path đó vẫn là missing observation; cần baseline/fixture/reader phù hợp, không đổi thành limitation chỉ vì khó.

Nếu root cause là assignment riêng hoặc cần thiết để khôi phục phép thử còn thiếu, giữ trong preparation/investigation. Nếu chỉ giải thích lịch sử sau khi câu hỏi đã có đáp án, ghi optional follow-up, không chặn closure.

Cụ thể `a06-historical-cause` của preview phase 2 phải được kiểm tra theo quy tắc này; không kế thừa nhãn external dependency máy móc.

### Bước D — Làm nốt action hữu ích

Dùng selector hiện có; ưu tiên reconcile unknown → đọc kết quả đã có → executable gap → preparation nhỏ có tác động. Nhánh blocked không giữ toàn round nếu còn nhánh độc lập.

Trước một repair/attempt mới, nêu: thiếu fact nào, điều kiện nào đã thay đổi, kết quả nào sẽ đóng câu hỏi hoặc chứng minh dependency. Không chạy lại vì nhãn cũ partial.

Nếu cùng blocker lặp lại và không có prerequisite/reader/options mới, không tạo allocation đổi tên để thử lại. Ghi dependency cụ thể và chuyển nhánh. Không đặt số retry cố định; quyết định dựa trên thông tin mới và giá trị test.

### Bước E — Đối soát aggregate và review closure

Sau khi các atoms được xử lý, resolve aggregate theo §7. Chạy review closure trên universe của round, không chỉ inventory của block mới.

Nếu output là continue: thực hiện action được đề xuất khi có quyền; nếu chỉ review-needed: hoàn thiện mapping/phân loại bằng nguồn sẵn có. Nếu action cần runtime ngoài lượt implementation: chuẩn bị execution handoff cụ thể, giữ round in-progress/checkpointed, không fabricate limitation.

### Bước F — Finalize một lần khi đủ điều kiện

Ghi round status, kết luận coverage và security outcome, limitations/reopen conditions, state tài nguyên và bundle refs. Không tạo prompt “tiếp tục” chung chung khi đã closed.

Mở lại khi có trigger cụ thể: quyền/actor/policy mới; fixture/capability mới khắc phục dependency; build thay đổi ảnh hưởng câu hỏi; phát hiện feature thuộc scope bị thiếu; user giao phương pháp hoặc remediation mới. Không mở lại chỉ vì overall coverage vẫn partial.

## 7. Aggregate phải có đường đóng, không thành nghĩa vụ bất tử

Phase 3 thay quy tắc phase 2 “retained aggregate luôn mở” bằng **aggregate accounting có review**, không tự drop parent.

### 7.1. Contract

Thêm `aggregateReviews` version 1 vào scopeAssessment, mỗi row:

- `aggregateQuestionId`, `scopeRevision`.
- `sourceRefs`: original requirement/remainingWork locations đã review.
- `obligationAtoms`: mảng `{id, text, basis, questionIds, residualItemIds, disposition}`.
- `disposition`: `tested-question|grounded-na|external-or-method-limit|conclusion-limit|separate-remediation|unresolved`.
- `coverageBasis`: giải thích vì sao atoms biểu đạt đầy đủ nghĩa vụ parent trong scope hiện tại.
- `unmappedClauses`: các phần chưa map; không tự rỗng do có vài children.

Giữ parent ID/question/closureCondition và original requiredObservations trong history/normalized scope. Review là current projection có revision, không sửa meaning cũ trên đĩa.

### 7.2. Derived trạng thái

Aggregate có hai field tách biệt:

- `accountingStatus: pending|accounted`: đã map và xử lý quyết định cho mọi phần hay chưa.
- `coverage`: derived từ testing obligations, không từ số atom.

Quy tắc:

1. Thiếu clauses, unknown child, ref sai hoặc disposition chưa đủ basis → accounting pending; không đóng round dựa vào parent này.
2. Test obligation linked child observed/grounded N/A → đủ coverage của atom đó, kể cả violated.
3. External/method limit → accounting có thể accounted, coverage vẫn partial; nghĩa vụ chưa trả lời còn trong report.
4. Conclusion limit phải chứng minh không phải yêu cầu chưa test; không được dùng để hạ một child required open. Remediation tách khỏi test coverage chỉ khi test question đã đủ hoặc obligation vốn là remediation riêng.
5. Mọi applicable test atom đã đủ, không còn unanswered obligation → aggregate coverage observed hoặc applicability-only phù hợp; **không đòi evidence unit giả `remaining-assigned-requirement-resolved`**.
6. Aggregate có coverage partial nhưng accounting accounted, không còn action khả thi → có thể kết thúc round với giới hạn. Scope/catalog vẫn partial.

Trong project_scope, parent được tính một lần qua review; children vẫn kiểm tra evidence độc lập. Không nhân đôi cùng duty ở parent và child; không xóa child gap khỏi criterion. Graph refinesQuestionId giữ cycle/criterion/boundary guards. Một child observed không đủ nếu parent mapping chưa đầy đủ.

Đây là điểm khác chủ yếu so với phase 2: **có review đầy đủ thì parent được kết luận theo các nghĩa vụ đã phân rã, không bắt nó tồn tại như open testcase trùng lặp mãi mãi**.

## 8. Thiết kế helper và tích hợp

### 8.1. Tối đa một module mới

Thêm `P/round_closure.py`, tái sử dụng business_discovery, residual_review, evidence resolver và work_selection. Không thêm scheduler hoặc generic workflow engine.

API pure functions:

- `review_aggregate_obligations(scope, assessment, question_projection, residual_projection)` → aggregate states, unresolved atoms, diagnostics.
- `review_round_closure(round_definition, scope_projection, reconciliation, residual_projection, work_selection, resource_state)` → eligibleStatus hoặc null, decision, exact next work, blockers/limitations, reopen conditions và review extent.

Decision enum: `continue|review-needed|checkpoint-required|ready-to-close|stopped-by-user`. `eligibleStatus` chỉ completed/completed-with-limitations khi conditions §5 đủ. Helper không tự mutate report hoặc dispatch.

### 8.2. Dữ liệu input không phình thành checklist mới

Dùng existing engagement, residualReview, discoveryReview, actions, operations, pendingEffects và continuation.resourceDisposition. Chỉ thêm dữ liệu thật còn thiếu cho round/aggregate; không bắt tester nhập lại một fact ở ba nơi.

`reviewUniverse` tham chiếu sources/criterionIds/questionIds/caseIds/inventoryRefs đã có; helper so set để phát hiện omission. Không bắt snapshot toàn source hoặc hash mọi file. Broad criterion chưa có finite mapping vẫn phải visible trong review-needed hoặc method-limit có basis.

Resource_state dùng existing owned resource refs, pending operations và cleanup facts. Trạng thái `stopped` phải có readback nếu có producer được khởi chạy, không lấy câu prose trong final làm evidence. Không có resource do round tạo → not-required, không buộc tạo cleanup checklist rỗng.

### 8.3. Evidence/review lineage

Review closure không được dùng legacy historical-only record để tự cấp observed. Mapping kết quả cũ vào câu hỏi hiện tại dùng resolver hiện có, context compatibility rõ. Existing historical finding/currentRetest giữ nguyên.

Round finalize phải ghi scopeRevision và IDs của inputs/projections dùng để quyết định, thời điểm và lý do. Không cần hash manifest bắt buộc. Nếu scope/results/unknown state thay đổi sau review, tính lại closure; không tin ready-to-close cũ từ JSON caller gửi.

### 8.4. CLI

Thêm:

`scope review-closure --run WORKING_RUN --security-scope SCOPE --scope-assessment ASSESSMENT [--inventory INV --observations OBS --prerequisites PRE]`

- Read-only; dùng same loaders/resolvers như report và next-work.
- Nếu round_definition chưa có: trả missing-round-definition, không suy từ latest action.
- JSON stdout chỉ sanitized IDs/status/reasons/next steps; valid open review exit 0, invalid refs/shape exit nonzero.
- Có whole assignment scope thì không bỏ qua missing inventory do caller không truyền; lấy retained working inputs hoặc trả diagnostic.

Mở rộng `scope report --finalize-round`:

- Recompute closure từ current inputs; không chấp nhận caller set status completed.
- Nếu chưa eligible: không xuất bundle giả closed; trả closure diagnostics. Người dùng vẫn có thể xuất checkpoint/report không finalize bằng command hiện có.
- Nếu eligible: dùng staging và validate_bundle hiện có, ghi assessmentRound cùng completionSummary.round và roundClosed vào cả ba report.
- Finalization là offline report operation, không kill runtime, không cleanup, không cấp quyền replay.
- Chỉ đánh dấu finalized sau khi bộ report staged đã validate; báo write failure như failure, không tuyên bố closed đã bàn giao. Giữ bundleId để phát hiện overwrite bị gián đoạn.

Không có catalog được giao thì API vẫn dùng được cho track/feature-only round; không tạo catalog giả để có closure.

### 8.5. Điểm sửa code

- `security_scope.py:normalize_scope/project_scope/validate_bundle`: aggregate reviews và projection, không phá history/revision guards.
- `product_scope.py:compact_results/compose_completion_summary`: lifecycle report, không đánh đồng taskCompletion với roundClosed.
- `product_scope_cli.py`: review-closure, finalize và reuse inspect-resume/load_work_state.
- `residual_review.py`: dùng accounted aggregate states; causal investigation ngoài duty không giữ testing queue sau khi review có basis.
- `work_selection.py`: chỉ đổi integration/returned reason, không đổi eligibility/unknown gate.
- `coverage_presentation.py`: display round outcome rõ, historical/current view giữ nguyên.

## 9. Workstream 100ms bắt buộc: từ backlog thực tới kết luận

### 9.1. Inputs và output riêng

Đọc hai bundle:

- `assessment-results/100ms-fresh-20261101/`
- `assessment-results/100ms-workflow-acceptance-20261102/`

Tận dụng preview phase 2 `.local/zap-workflow-phase2-preview-84f1dd0a78/` và workingInputs được chỉ ra. Không import/chạy adapter cũ có side effects, không in token/raw secrets.

Tạo working directory mới `.local/zap-workflow-phase3-closure-<unique>/`. Reports derived nằm trong `reports/` gồm đúng RUN/ALERTS/SCOPE_ALERTS. Không ghi đè official bundles, không đổi official pointer cũ. Nếu derived round đã eligible, có thể finalize projection riêng; mô tả rõ đây là kết luận mới từ retained-data review, không fresh rescan hoặc kiểm tra live liveness.

Nếu dữ liệu working quan trọng không còn, ghi đúng records cần phục hồi; không bịa provenance. Synthetic tests vẫn kiểm tra code nhưng không thay nghiệm thu backlog sản phẩm.

### 9.2. Thực hiện đầy đủ theo nhóm, không theo 4.330 operation

1. Lập universe 50 criterion và danh sách residual gốc, đối chiếu route/feature inventories đã biết.
2. Nhóm các residual trùng underlying duty: một processing obligation có thể liên quan nhiều criterion. Dùng một atom với nhiều criterion refs; không đọc/chạy lại cùng việc vì nhiều mappings.
3. Review tất cả groups để không còn unreviewedRef ảnh hưởng closure của đợt. Đọc sâu operations chỉ cho group cần giải quyết, không migrate mọi operation.
4. Xử lý `a06-processing-readback` bằng reader/mapping trên kết quả đã lưu. Mỗi unit chỉ được ghi khi actual facts/context hỗ trợ; giữ phần thiếu thật.
5. Xét lại `a06-historical-cause`: nếu exact cause không phải testing requirement và hành vi đã được quan sát đủ, chuyển sang historical uncertainty/optional separate investigation. Nếu thiếu cause khiến không đánh giá được phép thử thật, giữ gap với next action cụ thể.
6. Đối chiếu generalization limits A01/A05 để không biến “mọi browser/mọi rendering context” thành campaign mới ngoài scope.
7. Tenant/upstream/production/log governance: giữ policy/method obligations theo căn cứ. Không gán N/A vì ZAP không hỗ trợ; local password N/A đã grounded giữ đúng.
8. Hoàn tất aggregateReviews cho groups liên quan, tính current coverage/round closure bằng helper.
9. So sánh before/after theo câu hỏi, không theo số request hay số labels đã chuyển.

### 9.3. Kết quả được phép ở cuối workstream

- **Ready-to-close completed-with-limitations:** mọi residual đã accounted, không còn action hữu ích khả thi; còn method/policy/access limitations cụ thể. Finalize derived bundle, đưa reopen conditions. Không yêu cầu hết partial catalog.
- **Ready-to-close completed:** chỉ nếu applicable testing obligations thực sự đủ trong scope đợt; không đặt đây là target bắt buộc.
- **Continue/ready-for-execution:** còn question cần traffic thật, có quyền/capability/fixture feasible. Bàn giao execution plan chính xác, không đánh dấu closed hoặc gọi đây là external dependency chỉ vì lượt hiện tại offline.
- **Checkpoint-required:** unresolved operational uncertainty/resources còn cần xử lý mà chưa đủ containment; chỉ rõ owner/next step, không tự clean close.

Implementation có thể hoàn thành trong khi assessment round chưa eligible. Khi đó báo **đúng một danh sách việc thực chất còn thiếu để kết thúc**, không dùng “cần tiếp tục assessment” chung chung và không đề xuất phase framework tiếp theo nếu chỉ còn vận hành.

## 10. Tài liệu phải cập nhật đồng bộ

`SKILL.md` và `R/assessment-scope-and-completion.md`:

- Đổi câu “assessment completion nghĩa là mọi assigned question đủ” thành phân biệt lifecycle closure và obligation coverage.
- Giữ criterion/track complete yêu cầu đủ evidence; bổ sung round completed-with-limitations.
- Có đường xử lý aggregate và đoạn “khi nào kết thúc, khi nào mở lại”.

`R/responsibility-loop.md`, `R/user-security-scope.md`:

- Hướng dẫn A–F, aggregateReviews, review universe toàn đợt, finite child closure.
- Ví dụ failed historical attempt + valid followup; answered violation; method-limit; no useful action; unknown effect còn sống.

`R/product-assessment-handoff.md`, `R/operations-and-results.md`, `R/retention-stop-and-recovery.md`:

- Round lifecycle là dòng trạng thái đầu trong final; coverage/security/remediation theo sau.
- Phân biệt round closure với chat checkpoint và user stop.
- Round closed không có prompt tiếp tục mặc định; chỉ reopen triggers cụ thể.
- Working inputs và native state history vẫn giữ, không replay nếu mở lại.

`R/operational-validation.md`, `agents/openai.yaml`:

- Tests/checks thực chạy, giới hạn offline/runtime.
- Không còn instruction mâu thuẫn “phải tiếp tục vì taskCompletion partial” khi round đã kết thúc đúng với limitations.

Không thêm assurance package, dashboard, mandatory approval hoặc reviewer signature. Tester có thể quyết định closure trong scope đã được giao; chỉ hỏi về policy/quyền thực sự thiếu, không hỏi “cho phép kết thúc?” thường lệ.

## 11. Thứ tự implement

### 0 — Baseline

Đọc applicable AGENTS/skill/plan; giữ dirty tree. Dùng Python 3.13 và locked dependencies ở env riêng hiện có. Không cài global. Ghi baseline tests, chọn source files cần sửa.

### 1 — Aggregate closure trước

Implement aggregateReviews validation/projection, tests positive/negative. Chứng minh parent có thể accounted và coverage đủ khi các nghĩa vụ thật đủ; child observed không tự đóng parent thiếu mapping. Đây là bước gỡ nguyên nhân open nghĩa vụ trùng lặp.

### 2 — Round state và closure reviewer

Implement round_closure pure functions, lifecycle/coverage separation và resource/unknown conditions. Không dùng “không có handler” làm ready-to-close. Không đổi admission hay evidence semantics.

### 3 — Reporting, CLI, compatibility

Nối summary/report/validator và review-closure/finalize. Legacy report không tự được upgraded. Test fail trong finalize không ghi bundle closed; read-only commands không dispatch.

### 4 — Đóng backlog trên retained 100ms data

Thực hiện toàn §9. Ghi expected disposition cho từng group trước chạy projection; nếu facts không đủ, giữ gap đúng. Không chỉ test 8 criterion hoặc dừng ở helper pass.

### 5 — Tài liệu và validation cuối

Sửa docs theo §10, chạy focused/related tests, syntax/links/diff. Kiểm tra official bundles/working history không bị thay đổi. Bàn giao round decision, coverage, exact remaining actions hoặc reopen triggers và derived report links.

## 12. Acceptance — chứng minh có lối ra và không đóng nhầm

### Closure cases bắt buộc

1. Mọi finite duty observed, có violation finding mở → round completed, finding vẫn open, không buộc remediation.
2. Đủ dynamic observations, catalog governance ngoài phương pháp chưa đánh giá → round completed-with-limitations nếu toàn universe đã review; catalog/taskCompletion partial.
3. History attempt failed, followup evidence đủ → question/aggregate đóng đúng, history không đổi.
4. Root cause lịch sử chưa biết, không assigned và không cản interpretation → limitation không chặn round; không đổi unknown thành known.
5. Fixture hỏng trước intended processing → test gap còn mở; không dùng case 4 để đóng nhầm.
6. Parent aggregate map đủ children đủ evidence → coverage observed/accounted; không bắt unit placeholder chung.
7. Parent thiếu clause, child observed → review-needed; không close.
8. Parent map đủ có method-limit → accounted nhưng partial; round có thể closed-with-limitations.
9. Generalization-limit gán cho assigned API/input chưa test → diagnostic; continue/review-needed.
10. Missing handler/reader mà có preparation hữu ích → continue, không ready-to-close.
11. Runtime case feasible nhưng phase implementation offline → ready-for-execution, không external blocker/closed.
12. Unknown effect có reader khả thi → reconcile; case độc lập vẫn chạy được.
13. Unknown effect reader unavailable nhưng resource đã contained, uncertainty và no-replay/resumption đầy đủ → có thể completed-with-limitations; evidence vẫn unknown.
14. Producer có thể còn chạy, tác động chưa contained → checkpoint-required, không clean closure.
15. User pause → checkpointed; user stop → stopped-by-user; không tự completed.
16. Review selected groups không đủ universe round → review-needed; không dùng hai JOIN cases để đóng all-project round.
17. No next action vì actions file rỗng trong khi obligations chưa review → review-needed, không close.
18. Round closed sau đó scope/build/known duty thay đổi → closure re-evaluated, reopen basis rõ; không auto replay old effects.

### Reporting và backward compatibility

19. taskCompletion partial + round completed-with-limitations được validate, ba report cùng state; headline đúng nghĩa.
20. No assessmentRound legacy → không suy lifecycle; legacy callers vẫn chạy.
21. Caller set status completed nhưng review còn action → finalize từ chối, không ghi report closed.
22. Required refs/pointers sai, scopeRevision cũ, graph cycle → input error trước publication.
23. Writing/staging fail → không báo bàn giao closure thành công; prior bundle giữ nguyên.
24. Native alerts/counts/findings/currentRetest không đổi khi chỉ recomposition; outside-ZAP source review không thành ZAP finding.

### Nghiệm thu 100ms

- Universe đủ 50 criterion về disposition, không nhất thiết coverage đủ 50 criterion.
- 37 route units/feature groups hiện có được giữ hoặc có reasoned mapping; không biến selected workload thành toàn scope.
- Tất cả residual có ảnh hưởng closure đã reviewed hoặc explicit unresolved; không che số lượng bằng grouping.
- Hai JOIN questions vẫn observed; three effects resolved; original attempts/history giữ nguyên.
- Có kết luận rõ một trong các outcomes §9.3 và danh sách next work/reopen triggers tương ứng.
- Không yêu cầu kết quả bắt buộc completed: **yêu cầu đường đến kết thúc cụ thể, kiểm chứng được, không sinh thêm obligation tùy ý**.

### Tests

Thêm `T/test_round_closure.py`, `T/test_aggregate_closure.py`; mở rộng security_scope, residual_review, work_selection, coverage_presentation, checkpoint và adapter integration theo code thay đổi. Dùng unittest, fake resources/clock/transport; không framework mới.

Chạy focused checks rồi bộ regression phase 2 và relevant legacy tests. Đọc setup trước chạy để không khởi tạo Docker/target. Không hạ guards/reserves để pass; ghi skip/failure baseline chính xác.

Smoke CLI từ cwd ngoài repo: review-closure open, review ready, finalize ready, finalize rejected, report legacy. Dùng temporary output/private fixture synthetic; kiểm tra 0 network/dispatch trên review/report.

## 13. Điều kiện hoàn thành phase 3

Phase 3 hoàn thành khi:

1. Skill có trạng thái kết thúc đợt đúng nghĩa và không đánh đồng coverage partial với công việc chưa thể kết thúc.
2. Aggregate có đường derive conclusion từ nghĩa vụ thật; không tồn tại như testcase trùng lặp vĩnh viễn.
3. Quy trình A–F dẫn đến action hoặc closure rõ ràng, có safeguards against false closure.
4. Backlog 100ms đã được đối soát toàn review universe ở mức disposition bằng dữ liệu có sẵn, không chỉ vài examples; phần cần runtime được chỉ rõ.
5. Tests/CLI/docs thống nhất, history được giữ, báo cáo nêu chính xác outcome.

Không kết thúc phase bằng câu “đã thêm helper, assessment vẫn partial” mà không giải thích **còn chính xác việc gì để round đóng và tại sao**. Không đề nghị thêm phase 4 chỉ để thực hiện mapping/readback/vận hành đã xác định trong phase này.

## 14. Prompt cho window implement sạch

> Đọc và implement `/Users/hahoangloc/Working/testing tool/docs/reviews/zap-workflow-phase3-closure-plan-20261102.md`. Mục tiêu phase 3 là có điểm kết thúc đợt kiểm thử và con đường đạt tới đó, không chỉ thêm nhãn reporting. Implement aggregate accounting/closure, round lifecycle tách khỏi obligation coverage, closure reviewer/CLI/docs/tests. Sau đó đối soát toàn backlog 100ms đã khai bằng retained data theo §9, không chỉ chọn vài examples. Giữ working tree có trước và historical bundles/attempts. Không scan/provision/restart Docker hoặc sửa sản phẩm trong nhiệm vụ implementation này. Nếu còn test runtime hữu ích khả thi, chuẩn bị exact execution handoff và giữ round chưa đóng; không gọi giới hạn offline là external blocker. Nếu đủ điều kiện, finalize derived bundle riêng với status completed hoặc completed-with-limitations đúng căn cứ; không tự chấp nhận rủi ro hoặc ép taskCompletion complete. Báo checks thực chạy, round outcome, coverage và exact next actions/reopen triggers. Không commit/push/sync personal skill.

Lượt hiện tại chỉ tạo kế hoạch này và dừng; các thay đổi code và review backlog đầy đủ được thực hiện ở lượt implement phase 3.
