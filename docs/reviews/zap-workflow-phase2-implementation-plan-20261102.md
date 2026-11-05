# Kế hoạch implement tiếp: coverage kế thừa, residual và quyết định tiếp tục/dừng

Ngày 02/11/2026. Trạng thái: **thiết kế đã chốt để implement; chưa thực hiện thay đổi code trong lượt lập kế hoạch**.

## 1. Mục tiêu và phạm vi đã chốt

Tiếp tục cải thiện skill project-local `mcp-zap-repo-operations` tại `/Users/hahoangloc/Working/testing tool`. Tập trung làm người vận hành trả lời được ba câu hỏi:

1. Đã biết gì từ assessment cũ, vừa kiểm thử thêm gì, và kết quả nào áp dụng cho context hiện tại?
2. Trong những mục đang ghi partial/unresolved, mục nào thực sự cần kiểm thử tiếp, mục nào chỉ cần đọc lại kết quả, và mục nào là giới hạn phương pháp hoặc dependency thật?
3. Có việc hữu ích trong quyền cần làm ngay không; nếu dừng, dừng vì lý do gì và phạm vi kết luận đến đâu?

Không mở rộng mọi runner. Không viết lại H1–H5 đã hoạt động. Không migrate toàn bộ operation cũ thành evidence mới. Không yêu cầu thêm scan để nghiệm thu thay đổi reporting/planning này.

Deliverables của lượt implement:

- Code, tests và hướng dẫn skill cho coverage presentation, residual review, liên kết next-work và resume inputs.
- Một walkthrough offline dùng assessment 100ms hiện có, xuất **bản preview riêng** để kiểm tra ý nghĩa báo cáo; không sửa hai bundle chính thức cũ.
- Báo cáo ngắn nêu phần đã implement, kiểm tra thực chạy và giới hạn. Không triển khai sản phẩm, chạy traffic, sửa quyền, Docker, personal skill hoặc commit/push.

Kế hoạch này thay thế việc lựa chọn hướng xử lý cho phase 2. Agent sau chủ động quyết định chi tiết coding tương thích source, không yêu cầu user duyệt từng field hoặc mỗi bước thường lệ.

## 2. Baseline và vấn đề đã kiểm chứng

Đọc trước:

- `docs/reviews/zap-workflow-post-implementation-review-20261102.md`.
- Kế hoạch phase 1: `docs/reviews/zap-skill-tester-workflow-implementation-plan-20261102.md`.
- `.agents/skills/mcp-zap-repo-operations/SKILL.md` hiện tại và AGENTS áp dụng.

HEAD khi lập kế hoạch: `18f17860bad327a18345f949644aac4d40b7fece`. Working tree có nhiều thay đổi có trước, gồm implementation mới chưa commit. **Giữ working tree, không khôi phục theo HEAD, không reset/stash/revert.**

Bằng chứng đã xác minh ở lượt review trước:

- Bộ offline 193 tests: 185 pass, 8 skip optional source.
- Runtime 100ms: hai câu hỏi preview JOIN/uncertain JOIN observed; ba pending effects resolved; partial/unknown history vẫn giữ nguyên.
- Ba report cũ byte-identical theo hash charter; bundle mới validate được.
- Report cũ có 19 criterion partial, 25 not-operated, 6 applicability-reviewed. Projection mới có 4 partial, 46 not-performed. Không phải mất dữ liệu: kết quả cũ nằm trong priorAssessment; nhưng nhãn top-level dễ gây hiểu sai.
- `report.py` riêng của acceptance chuyển remainingWork thành question chung `remaining-assigned-requirement-resolved`; có 23 question methodClass unresolved, 22 outside-zap, 2 zap-ui. Không được coi 23 unresolved là 23 test cần chạy.
- Inventory mới có 16 feature groups, nhưng chỉ 2 executable cases; 14 nhóm có no-additional-question và rationale kế thừa.
- `completionSummary.dast.questionIds` chứa cả criterion question và responsibility case tương ứng; không phải số test độc lập.
- RUN compact đã bỏ evidenceRefs. Dùng inventory trong report trực tiếp reconcile bị lỗi provenance; dùng private inputs thì pass. Đây là giới hạn resume cần giải thích và hỗ trợ rõ.

Các điểm sửa nằm chủ yếu ở W05/W06/W07, kèm làm rõ boundary của W01/W02. W03/W04 không cần mở capability mới trong phase này. W08 và unknown-effect safety phải giữ nguyên.

## 3. Nguyên tắc nghiệp vụ

1. Lịch sử partial là kết quả đã có, không phải “chưa hề kiểm thử”. Kết quả đó cũng không tự thành kết quả current-build.
2. Coverage mới chưa thực hiện không làm coverage cũ biến mất. Kết quả cũ không hợp lệ để kế thừa vẫn được trình bày như historical record.
3. Residual là nội dung cần được phân loại, không mặc định là một test obligation. Một câu prose có thể chứa nhiều ý và phải tách khi chúng dẫn đến next action khác nhau.
4. Phân loại không được trở thành cơ chế giảm scope hoặc chấp nhận rủi ro. Nghĩa vụ gốc, nguyên văn requirement và unresolved effects luôn được bảo toàn.
5. Đã trả lời một câu hỏi với violation có thể kết thúc coverage; finding/remediation có trạng thái riêng.
6. “Không bảo đảm mọi browser/rendering context” không tự mở thêm campaign nếu không phải phạm vi được giao. Ngược lại “all APIs” không được biến thành chọn vài API đại diện bằng nhãn limitation.
7. Đủ để dừng một đợt hữu hạn không có nghĩa toàn catalog complete. Quyết định tiếp tục/dừng phải nêu rõ review universe, chưa review gì và tác động đến kết luận.
8. Không xây scoring engine, policy parser hoặc agent tự chứng minh full discovery. Helpers kiểm tra cấu trúc và ánh xạ; tester chịu trách nhiệm ý nghĩa.

## 4. Kiến trúc thay đổi tối thiểu

Ký hiệu đường dẫn:

- `S = .agents/skills/mcp-zap-repo-operations`
- `P = S/lib/zap-product-assessment/src/zap_assessment`
- `T = S/lib/zap-product-assessment/tests`
- `R = S/references`

Thêm đúng hai module core:

- `P/coverage_presentation.py`: historical/current presentation và work-unit identity.
- `P/residual_review.py`: validation, phân loại có review, nhóm việc tiếp theo và diagnostics.

Mở rộng tại chỗ `security_scope.py`, `product_scope.py`, `product_scope_cli.py`, `work_selection.py`. Resume input validation có thể đặt trong product_scope_cli, không tạo orchestration framework mới. Giữ `workflowVersion: 1`; các extension có version riêng, optional, không đổi nghĩa payload cũ.

Không sửa logic evidence sufficiency của `question_evidence.py` để khớp reporting mới. Nếu gặp defect độc lập, tái hiện bằng test và sửa tối thiểu; không gộp refactor lớn.

## 5. Coverage presentation: không mất tiến độ, không cấp credit giả

### 5.1. Historical record rõ nguồn

Thêm optional `coverageHistory` trong criterion, version 1, chứa `records`:

```json
{
  "version": 1,
  "records": [{
    "id": "prior-assessment:SEC-A01-03",
    "sourceRef": "prior-100ms-report",
    "sourceCriterionId": "SEC-A01-03",
    "sourcePointer": "/criteria/2",
    "coverage": "partial",
    "securityAssessment": "historical source wording",
    "context": {"assessmentId": "...", "environment": "..."},
    "meaning": "historical-only",
    "basis": "Copied from the identified prior report; not a current retest"
  }]
}
```

SourceRef tham chiếu source metadata trong plan/RUN, gồm location và assessment identity. Pointer là vị trí thực tại import, không dùng array index làm stable ID. Coverage/securityAssessment được giữ nguyên chuỗi từ nguồn, không ép vào enum mới. Context unknown giữ unknown, không suy từ context hiện tại.

`meaning` ở phase này chỉ `historical-only`. Nếu tester muốn dùng kết quả cũ làm current credit, đi qua evidenceLinks/context compatibility hiện có, không đổi meaning hoặc gán boolean reviewed để pass.

Historical import:

- Explicit adapter đọc report do caller chỉ định, khớp criterion ID/source identity.
- Không tự chọn report mới nhất, dài nhất hoặc tự tìm nhiều thư mục.
- Không import raw/credentials; chỉ lấy criterion coverage, applicability, interpretation và source references cần thiết.
- Nếu đã có `priorAssessment`, có thể hiển thị fallback `legacy-embedded`; cần báo chưa có source binding đầy đủ. Không tự thay đổi verdict/current coverage.
- Nhiều history record khác build/context không lấy max coverage, không collapse thành “complete”. Trình bày records và trạng thái mixed-history nếu cần.

### 5.2. Derived view cho từng criterion

Thêm `coverageView` version 1 vào criterion output:

- `historical`: records hoặc legacy-embedded fallback, `credit: historical-only`.
- `current`: `{status, questionIds, observedQuestionIds, openQuestionIds}`. Chỉ tính từ question projection hiện hành.
- `applicability`: trạng thái hiện hành đã review.
- `displayStatus`: `not-applicable|user-excluded|current-observed|current-partial|historical-with-current-delta|historical-only|not-performed|unresolved`.
- `displayMeaning`: mô tả ngắn, deterministic; không chép prose dài.

Quy tắc:

1. N/A/user-excluded trình bày riêng, không nhóm với not-performed. Conflicts với observations vẫn giữ ở diagnostics/openWork.
2. Có history, current chưa có observations → historical-only, ví dụ “Historical partial; current mapped questions not performed”.
3. Có history và current observations chưa trả lời toàn nghĩa vụ → historical-with-current-delta.
4. Current đã đủ theo engine hiện hành → current-observed; finding có thể vẫn violation.
5. Không history, không current facts → not-performed hoặc unresolved tùy mapping.

**Giữ field `coverage` hiện tại để backward compatibility**, đồng thời xuất `coverageMeaning: current-question-projection` khi có coverageView. Consumer/docs mới dùng coverageView làm presentation chính, không render `coverage` đơn lẻ như cumulative status. Không đổi enum cũ gây hỏng callers; không gọi current coverage là toàn bộ lịch sử.

`scopeCompletion`, taskCompletion và securityAssessment tiếp tục do engine hiện tại tính. Module presentation tuyệt đối không cấp observation units, không sửa verdict, không đóng criterion bằng history count.

### 5.3. Summary không đếm trùng question/case

Mở rộng `completionSummary.dast` bằng `workUnits`:

- Unit có `id`, `questionIds`, `caseIds`, `coverage`, `countedAs`, `basis`.
- Case là identity chính khi question liên kết responsibilityIds. Question không liên kết case là unit riêng.
- Một case gắn nhiều criteria/questions chỉ đếm một case; nhưng mọi question có thêm observation requirements vẫn được engine kiểm tra độc lập. Không lấy số units để tính completion.
- Question gắn nhiều cases ánh xạ đến các case units tương ứng. Nếu có nghĩa vụ bổ sung không nằm trong linked cases, thêm question unit riêng và ghi basis; không được làm mất requirement.
- Legacy mixed `questionIds` giữ compatibility nhưng có `questionIdsMeaning: references-not-independent-test-count`. Consumers mới dùng workUnits; không đổi tên ID đã lưu.

Thêm summary presentation counts theo coverageView với mẫu số là criteria, không trộn case/operation/finding. N/A/excluded có bucket riêng. Không tính phần trăm “an toàn”.

`selectedTracks` cũ chuyển cách trình bày thành historical selected track labels, giữ nguyên data để truy nguyên. Thêm `trackSummary` derived cho tập mới có coverage data, có `reviewExtent: delta|assigned-track` và source inventory IDs. Không tự upgrade toàn FE từ hai JOIN cases.

## 6. Residual review: phân loại để quyết định, không tạo engine closure thứ hai

### 6.1. Lưu trong input hiện có

Thêm optional `residualReview` version 1 trong scopeAssessment; bản projection giữ summary và các rows đã sanitize trong RUN/SCOPE_ALERTS. Internal working input có thể là một JSON riêng cho CLI, nhưng không tạo deliverable chính thức thứ tư.

Structure:

- `version: 1`, `scopeRevision`.
- `sources`: `{id, location, kind}` với kind retained-report/current-scope/current-run/user-scope.
- `items`: các residual atoms đã tách.
- `reviewExtent`: `{kind: selected-groups|all-declared-residuals, sourceIds, criterionIds, basis}`.
- `unreviewedRefs`: mảng source pointer/criterion còn chưa phân loại; không tự để rỗng vì có vài item.

Mỗi item:

```json
{
  "id": "residual-a01-processing",
  "sourceRef": "prior-report",
  "sourcePointer": "/criteria/0/remainingWork/1",
  "originalText": "Exact source paragraph retained here",
  "selectedText": "The specific clause reviewed",
  "criterionIds": ["SEC-A01-01"],
  "questionIds": [],
  "caseIds": [],
  "kind": "test-gap",
  "basis": "A processing observation remains absent for the assigned input",
  "nextStep": "Read the retained delivery/result for the exact input before deciding on execution",
  "actionClass": "readback",
  "dependency": null
}
```

Item ID stable theo nguồn/criterion/ý nghĩa đã review, không hash wording mỗi lần chỉnh prose. Một paragraph tách nhiều item dùng chung sourcePointer, khác selectedText/ID. Không yêu cầu cắt từng câu nếu toàn đoạn có cùng quyết định.

### 6.2. Các loại và tác động

Chỉ dùng các kind sau:

- `test-gap`: câu hỏi được giao còn thiếu observations; phải có questionIds/caseIds hiện hữu hoặc proposedQuestion hữu hạn. Next action execute/prepare/readback phù hợp trạng thái thật.
- `readback-gap`: có kết quả cần đọc/đối chiếu; cần operation/result references cụ thể. Chưa có reader là preparation, không coi đã hết việc.
- `dependency`: thiếu điều kiện thật; cần affected IDs, blockedBy, optionsEvaluated ngắn, resumptionCondition. Không bắt số lần thử cố định.
- `method-limit`: requirement có thật nhưng ngoài ZAP/capability được giao; giữ nghĩa vụ catalog mở, không sinh active scan giả hoặc đổi N/A.
- `generalization-limit`: giới hạn phạm vi kết luận, không phải nghĩa vụ bổ sung từ scope gốc; cần scopeBasis và excludedConclusions. Không được dùng để loại một assigned question còn thiếu units.
- `answered`: câu hỏi hữu hạn đã đủ qua resolver hiện hành, có questionIds và evidence hỗ trợ; không dùng old operation completed hoặc caller text để đóng.
- `remediation`: finding cần sửa theo assignment riêng; có findingIds và assignmentBasis hoặc not-assigned. Không tự biến coverage gap thành remediation.
- `unclassified`: chưa đủ căn cứ; giữ pending review, không dispatch.

`actionClass`: `readback|execute|prepare|investigate|external-dependency|none`.

Không cần actionClass none cho mọi residual ngoài scan nếu vẫn có source/status cần đọc trong quyền. Tester phải phân biệt thiếu quyền/thông tin bên ngoài với chưa điều tra dữ liệu sẵn có.

### 6.3. Validation và derivation

`validate_residual_review(review, scope, reconciliation, operations, findings)`:

- Kiểm tra version/shape/IDs/refs; foreign IDs hoặc duplicate IDs là input error.
- Missing rationale, unreviewed group, thiếu next step là diagnostic khiến review chưa đủ, không chặn lưu checkpoint hoặc kiểm thử nhánh khác.
- OriginalText phải đối chiếu được với source supplied ở import/preparation; core pure function không tự đọc file tùy ý để xác minh prose.
- Answered chỉ được derive nếu linked question observed; unknown effects còn liên quan luôn thắng nhãn answered.
- Dependency phải có nguyên nhân và resumption condition; thiếu handler đơn thuần khi có bước chuẩn bị trong quyền → preparation needed, không tự external blocker.
- Generalization-limit có link tới required question open → conflict diagnostic, không xóa gap. Chỉ tester có scopeBasis cụ thể mới giải thích được giới hạn không phải obligation; helper không suy bằng keyword.
- Method-limit không thay applicability; không mở campaign ngoài assignment.
- Mọi item chưa được review giữ nguyên trong review backlog. Không tự đoán phân loại từ “partial”, “all”, “not proven”, “historical”.

`project_residual_work(...)` trả:

- `actionableReadback`, `actionableExecution`, `preparationNeeded`, `investigationNeeded`.
- `externalDependencies`, `methodLimits`, `conclusionLimits`, `answered`, `remediation`, `unclassified`.
- `reviewDiagnostics`, `unreviewedRefs`, `reviewExtent`.
- `decision`: `continue|review-needed|handoff-with-dependencies|no-further-dynamic-action-in-reviewed-scope`.

Đây là **quyết định công việc trong phạm vi đã review**, không phải taskCompletion, không phải permission và không phải policy acceptance. Không có numeric completion score.

### 6.4. Ưu tiên quyết định

1. User stop/timebox có thật được tôn trọng; lưu next work, không gọi assignment complete.
2. Có unknown liên quan và reader trong quyền → reconcile/readback; chỉ chặn dependency thực.
3. Có kết quả sẵn cần đọc → đọc trước mutation mới.
4. Có executable case/preparation hữu ích → chuyển selector hiện có.
5. Còn unresolved classification ảnh hưởng quyết định hết việc → review-needed; nếu có nhánh độc lập vẫn tiếp tục nhánh đó.
6. Chỉ còn dependency/method limits và review universe rõ → handoff/no-further-dynamic-action trong phạm vi này, assignment có thể partial.

Nếu reviewExtent chỉ selected-groups, không được xuất decision nói hết toàn assignment. Ghi rõ còn unreviewedRefs hoặc phần không thuộc lượt review. Không yêu cầu review toàn history cho một assignment feature hẹp.

## 7. Xử lý các question tổng quát đã tồn tại: giữ scope, không bị kẹt vì compatibility

`normalize_scope()` hiện giữ question cũ và cấm đổi semantics cùng ID; không được sửa guard này thành cho phép xóa obligation. Phase 2 **không tự đóng hoặc xóa** các question `retained-scope-*` khi residual được phân loại.

Quyết định implementation:

- Residual review là planning/presentation layer; question engine vẫn giữ các placeholder nghĩa vụ cũ mở nếu chưa có mapping đủ.
- Thêm `questionRole: executable|retained-aggregate` optional, default executable. Retained-aggregate vẫn thuộc completion/openWork, nhưng nextSteps phải là review-decomposition thay vì execute/retry campaign. Không mặc định requiredEvidence chung là input chạy scanner.
- Khi cần test cụ thể, thêm question mới với ID mới, link `refinesQuestionId` tới aggregate cũ, giữ aggregate nguyên trạng và scope revision mới. Validator kiểm tra cùng criterion/boundary, không cycle.
- Trong phase 2, không tự đóng aggregate chỉ vì một child observed. Summary phải nói “đã xử lý các câu hỏi được map; aggregate còn chưa đối soát đầy đủ”. Không tạo gate buộc migrate tất cả aggregate để dùng residual helper.
- Nếu cần hoàn tất toàn criterion sau này, đó là bước review mapping đầy đủ các nghĩa vụ và evidence, không đổi nhãn aggregate thành N/A. Phase 2 không hứa tự chứng minh full coverage bằng child count.

Thiết kế này có chủ đích giữ taskCompletion bảo thủ mà vẫn cho tester dừng đúng khi không còn hành động động hữu ích. **Thành công của phase 2 là backlog rõ và report đúng nghĩa, không phải làm mọi partial biến mất.**

## 8. Tích hợp next-work và discovery extent

### 8.1. Không tạo scheduler song song

`select_next_work()` tiếp tục là selector duy nhất cho executable actions. Residual helper cung cấp planning candidates và affected case IDs; không tự chạy handler hoặc tạo argv.

Mở rộng output next-work bằng:

- `executionProposal`: giữ output selector hiện tại.
- `planningProposal`: residual review/preparation/investigation không có executor.
- `reviewedScopeDecision`: quyết định §6, extent và reasons.

Giữ các top-level keys cũ để compatibility. Action có handler, requires và safety hợp lệ mới được selector chọn. Một planning proposal `prepare-adapter` chưa thể execute phải hiện ra, không bị nhầm thành hết việc.

Default runtime không bắt buộc có residualReview. Thiếu dữ liệu này trên legacy run → `residualReviewStatus: not-supplied`, không đổi completion hoặc tự cấm execution. Nhưng khi caller xin kết luận hết toàn backlog, helper phải báo giới hạn chưa review, không cung cấp assurance đó.

### 8.2. Discovery summary đúng phạm vi

Thêm optional discoveryReview.extent `{kind: delta|assigned-scope, featureIds, caseIds, basis}`. Legacy thiếu extent hiển thị declared-inventory, không đoán whole-product.

Summary discovery gồm extent và số feature groups đã review, nhưng không gọi là tỷ lệ feature coverage. Với 100ms acceptance, extent là delta; 16 groups reviewed không đồng nghĩa 16 groups mới được retest. Giữ riêng mapped/no-additional-question counts; không gán no-additional-question là observation.

### 8.3. CLI

Thêm command chỉ đọc:

`scope review-residuals --security-scope SCOPE --scope-assessment ASSESSMENT --run WORKING_RUN [--reconciliation REC] [--alerts ALERTS]`

- Review lấy từ ASSESSMENT.residualReview; không tự trích prose thành decisions.
- Stdout JSON compact với IDs/categories/next steps đã sanitize, không raw data.
- Valid input có open items exit 0. Malformed/unresolved foreign refs exit nonzero.
- Không cần output directory, không mutation, không import code.

Mở rộng `scope next-work` bằng optional `--security-scope`, `--scope-assessment`, `--run` để cung cấp residual context. Nếu supplied phải kiểm tra product/environment/scope revision khớp inventory. Tránh load working history hai lần; dùng shared loader hiện có. Không tự dispatch ngoài allowlist.

`scope report` tích hợp projection mới từ scopeAssessment, không thêm mandatory flag cho callers cũ.

## 9. Resume inputs: báo cáo compact không phải executable input

Không đưa lại raw/evidenceRefs/private credentials vào report công khai để làm report trở thành plan.

Thêm optional RUN `continuation.workingInputs` version 1:

- `inventory`, `observations`, `prerequisites`, `operations`, `history`: path tới retained private input hoặc pointer đã định nghĩa vào working RUN.
- `assessmentId`, `product`, `environment`, `scopeRevision`.
- `purpose: executable-working-inputs`, `reportIsProjection: true`.

Paths phải là reference, không inline secrets. Không bắt mọi assessment tạo thêm file mới nếu một working RUN đã chứa đủ inputs. Khi xuất report chia sẻ ngoài workspace, có thể redact location; phải ghi unavailable để không giả resume được.

Thêm `scope inspect-resume --run REPORT` chỉ đọc:

1. Kiểm tra references hiện hữu theo quyền local, regular files, expected schema/context.
2. Không tự thực thi command hoặc load Python module từ input.
3. Nếu workingInputs thiếu, đọc privateWorkingDirectory chỉ như gợi ý; trả missing-inputs và hướng tìm retained state, không tự đoán tên file rồi resume.
4. Nếu RUN compact thiếu evidenceRefs, trả diagnostic `report-projection-not-executable`, không exception mơ hồ.
5. Không trả token/raw/contents; stdout chỉ path/status/context conflicts.
6. Hash/version liveness không được suy từ existence; trước execution vẫn phải revalidate dependency liên quan. Không thêm mandatory hash manifest.

Không cho `--previous` âm thầm nhận report compact như internal continuation RUN. Loader phát hiện shape và chỉ ra `inspect-resume`; không migrate tự động hoặc bịa evidenceRefs từ prose.

## 10. Walkthrough trên dữ liệu 100ms: offline, không rewrite report cũ

Input chỉ đọc:

- `assessment-results/100ms-fresh-20261101/{RUN,ALERTS,SCOPE_ALERTS}.json`.
- `assessment-results/100ms-workflow-acceptance-20261102/{RUN,ALERTS,SCOPE_ALERTS}.json`.
- `.local/100ms-workflow-acceptance-20261102/` cho inventory/observations/prerequisites/operations/actionHistory và charter cần thiết; không đọc hoặc in credentials không liên quan.

Output preview: thư mục mới `.local/zap-workflow-phase2-preview-<unique>/reports/` với ba file chuẩn. Internal reviewed mapping nằm cùng thư mục làm việc bên ngoài skill. Không đổi officialRunPath hoặc copy preview thành official assessment khi user chưa giao việc đó. Nếu input không có tại môi trường implement, dùng synthetic fixtures và báo không chạy historical walkthrough; không cần user cung cấp secret.

Review các nhóm đủ khác nhau để kiểm tra quyết định:

1. SEC-A01-03: historical partial + giới hạn khái quát, không có test mới trong delta.
2. SEC-A05-01: historical DOM observations + current JOIN name observation + giới hạn rendering context. Tách phần đã quan sát khỏi absence tuyệt đối.
3. SEC-A01-05: tenant policy/model chưa xác định — dependency thật, không gán N/A.
4. SEC-A06-02 hoặc A06-03: processing/readiness cũ và receipt đã trả lời; tách các ý khác next action.
5. SEC-A07-01: applicability N/A ở local product, upstream ngoài target; không hiển thị như password test còn phải chạy trong local scope.
6. Một criterion ngoài ZAP trong nhóm implementation/governance — giữ catalog obligation mở, không sinh traffic.
7. Hai JOIN questions hiện tại — vẫn observed; original partial attempt và exact resolutions giữ nguyên.

Không yêu cầu phân loại hết 50 criterion để nghiệm thu helper. Output selected-groups phải liệt kê phần chưa review; không được tuyên bố whole-assignment no work remaining. Với mỗi residual atom đã chọn, agent implement đọc đúng source/ref và ghi rationale cụ thể, không thay toàn bộ bằng cùng template.

Preview phải chứng minh:

- Người đọc thấy coverage lịch sử và delta cạnh nhau, không hiểu test cũ chưa làm.
- Các nguyên nhân partial khác nhau dẫn tới nextStep khác nhau.
- Không có execution/mutation phát sinh từ review/report.
- Hai question mới vẫn đóng, findings cũ/attempts/statuses không thay đổi.
- DAST/full catalog vẫn partial nếu nghĩa vụ chưa đủ; không đặt target “phải complete”.

## 11. Thứ tự implement và điểm sửa

### Bước 0 — Baseline

Đọc kế hoạch, skill và AGENTS; kiểm tra dirty state. Dùng Python 3.13 với lock trong môi trường có sẵn. Interpreter từng dùng là `/tmp/zap-skill-audit-20261102-venv/bin/python`, nhưng phải kiểm tra còn tồn tại/dependencies đúng; không coi path này là dependency permanent. Nếu thiếu, tạo venv riêng ngoài skill/product và cài lock trong phạm vi implementation, không cài global.

Chạy các tests liên quan baseline trước sửa; lưu log ngoài skill. Không cần full suite có runtime/Docker.

### Bước 1 — Presentation

Implement coverage_presentation, optional historical record validation và coverageView. Tích hợp project_scope sau khi coverage/security verdict đã tính. Thêm tests SEC-A01-03 synthetic, N/A, mixed history, current observed violation. Kiểm tra historical-only không làm scopeCompletion thay đổi.

### Bước 2 — Residual contract

Implement residual_review pure functions; tests categories/conflicts/unreviewed extent. Extend scopeAssessment validation/projection. Không chạm evidence resolver để hợp thức hóa labels. Thêm retained-aggregate/refinesQuestionId với revision/cycle guards, giữ obligations như §7.

### Bước 3 — Selector và summary

Nối residual planning vào next-work, giữ shared executable eligibility. Implement workUnits identity và discovery extent. Kiểm tra all-declared/selected-groups decisions đúng, missing handler không biến mất. Giữ count không chi phối completion.

### Bước 4 — Resume/CLI/report

Implement review-residuals, inspect-resume và flags optional. Kiểm tra script-entry từ cwd ngoài repo. Report sanitizer giữ semantic refs cần thiết và loại private fields. Extend validate_bundle kiểm tra coverageView/reference/version và summary consistency; không coi coverageHistory là support evidence.

### Bước 5 — Walkthrough và tài liệu

Tạo preview mới và mapping thực cho các nhóm §10. Không sửa `report.py` hay bundles của acceptance cũ; adapter preview mới gọi core functions, không hardcode completion để demo.

Cập nhật tại chỗ:

- SKILL.md: trước “hết việc”, phân loại residual trong extent được review; report historical/current.
- product-assessment-handoff.md, operations-and-results.md, user-security-scope.md: coverageView, evidence boundary, workUnits.
- responsibility-loop.md, assessment-scope-and-completion.md: residual không đồng nghĩa testcase, stop partial hợp lệ, aggregate mapping.
- retention-stop-and-recovery.md: workingInputs và inspect-resume; không biến missing metadata thành cấm lưu checkpoint.
- product-discovery.md: delta vs assigned-scope review.
- operational-validation.md: checks thực chạy và limits, không ghi trước số pass.

Không rewrite mọi reference; không thêm guide dài trùng lặp. Ví dụ CLI phải chạy được với code thật, không chỉ documentation mock.

### Bước 6 — Final verification

Tests mới + related regression; diff check, link check các tài liệu sửa; xác minh history inputs byte-identical trước/sau walkthrough. Bàn giao kết quả và dừng, không tự mở runtime scan để nâng mức nghiệm thu.

## 12. Acceptance cụ thể

### A. Historical/current presentation

1. Historical partial + current not-performed → coverageView historical-only; legacy coverage vẫn current-question-projection; overall không tự complete.
2. Historical partial + JOIN delta observed → historical-with-current-delta nếu criterion còn gap; không tự criterion pass.
3. Current sufficient violated → current observed, violation giữ, remediation không tự assigned.
4. N/A có basis → bucket N/A, không nằm trong dynamic execution queue; conflict evidence vẫn diagnostic.
5. Hai historical contexts khác nhau → không max/union credit tự động.
6. Embedded priorAssessment không source binding → visible legacy-embedded, không đủ để current credit.
7. Một case gắn nhiều criteria → workUnits không đếm case lặp; extra question requirements không mất.

### B. Residual decisions

8. Đoạn trộn fixture failure và all-browser limitation → tách atoms, next action khác nhau; original text vẫn giữ.
9. Câu hỏi assigned open bị gán generalization-limit → conflict, không đóng obligation.
10. Claim answered nhưng question thiếu units/unknown → giữ open, không kế thừa từ operation completed.
11. Governance ngoài ZAP → method-limit, catalog partial, không create active action.
12. Missing handler nhưng có preparation cụ thể → preparationNeeded; không external blocker chỉ vì chưa viết handler.
13. Dependency có blockedBy/resumption hợp lệ → giữ dependency; không yêu cầu thử đường biết không phù hợp để đủ attempt count.
14. Partial review selected-groups → không xuất whole-assignment no-work claim; unreviewedRefs visible.
15. User stop → không dispatch; next work vẫn giữ.
16. Có unknown dependent và case độc lập sẵn → reconcile nhánh liên quan, không blanket block case độc lập.
17. Retained aggregate được refine → original obligation không mất; child observed không tự close toàn aggregate.
18. Không residualReview → legacy execution vẫn hoạt động; giới hạn review hiển thị khi hỏi điểm dừng.

### C. Resume/report/integration

19. Compact report thiếu evidenceRefs → inspect-resume báo projection-not-executable; working input hợp lệ vẫn load được.
20. WorkingInputs thiếu file/sai product/environment/revision → diagnostic cụ thể, không tự fallback sang assessment khác.
21. Path/input chứa command hoặc module string → chỉ data, không execute/import.
22. Semantic refs survives sanitization; token/raw không lọt output. Bundle consistent, không thêm deliverable thứ tư.
23. Offline end-to-end: legacy history + current evidence + residual review → next-work proposal → preview bundle; 0 network/dispatch calls.
24. History source byte-identical; finding IDs/native counts/currentRetest và pending journal không đổi.

### D. Nghiệm thu trên 100ms

Có preview với các nhóm §10, expected decisions viết trước khi chạy projection; exact values đối chiếu input sau đó. Không chỉ assert “bundle valid” hoặc “exit 0”. SEC-A01-03 phải hiện lịch sử partial; SEC-A07-01 không trở thành password test local; hai JOIN observed không bị mở lại; phần chưa review không được che mất.

### Test files và lệnh

Thêm `test_coverage_presentation.py`, `test_residual_review.py`, `test_resume_inputs.py`. Mở rộng test_security_scope, test_work_selection, test_work_session_checkpoint và test_question_adapter cho đường tích hợp liên quan; không thêm framework.

```sh
cd '/Users/hahoangloc/Working/testing tool'
ZAP_PHASE2_ROOT="$PWD/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment"
ZAP_PHASE2_PYTHON='/absolute/path/to/python-with-locked-dependencies'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$ZAP_PHASE2_ROOT/src:$ZAP_PHASE2_ROOT/tests" \
  "$ZAP_PHASE2_PYTHON" -B -m unittest \
  test_coverage_presentation test_residual_review test_resume_inputs \
  test_business_discovery test_question_evidence test_work_selection \
  test_readiness test_question_adapter test_security_scope test_pm_scope \
  test_work_session_checkpoint test_executor_routing test_report_reconciliation -v
```

Ba module phase 2 chưa tồn tại khi lập kế hoạch. Sau focused checks, chạy bộ 17 modules đã dùng baseline nếu không có blocker; không tăng test scope sang runtime chỉ để tăng số lượng. Skip có sẵn ghi rõ; không sửa guard/lower reserve để pass.

## 13. Điều kiện hoàn thành implement và phần không thuộc scope

Hoàn thành khi:

- Presentation phân biệt lịch sử/current/N/A đúng và không thay completion bằng nhãn mới.
- Residual được phân loại thành next actions hữu hạn; engine không cho chuyển unknown/assigned gap thành limitation bằng label.
- Selector/report/resume dùng được qua CLI, giữ compatibility và safety.
- Preview 100ms hoặc synthetic fallback được kiểm tra theo nghĩa nghiệp vụ, không ghi đè official reports.
- Tests liên quan pass, docs khớp CLI, nêu giới hạn chưa runtime-qualified.

Không yêu cầu:

- Whole 50-criterion catalog complete, tất cả legacy questions được migrate, hoặc mọi historical failure được giải thích root cause.
- Fresh active scan, media consumer campaign, auth/cookie/SSO qualification hoặc sản phẩm thứ hai.
- Xây universal crawler, SLA mới, risk acceptance, approval engine hoặc dashboard.

W03/W04 có thể được nghiệm thu sâu hơn ở assignment runtime thực tiếp theo; đó là việc riêng, không phải nợ implementation phase 2. Không tự tạo obligation “phải thêm sản phẩm để pass”.

## 14. Prompt bàn giao window sạch

> Implement `/Users/hahoangloc/Working/testing tool/docs/reviews/zap-workflow-phase2-implementation-plan-20261102.md`. Hướng xử lý đã chốt: historical/current coverage presentation, residual review để quyết định tiếp tục/dừng, liên kết selector và working inputs cho resume. Đọc working tree hiện tại và giữ mọi thay đổi có trước; không khôi phục về HEAD. Thực hiện các bước 0–6, tests và walkthrough offline trên dữ liệu 100ms nếu sẵn có. Không scan/provision/restart runtime, không sửa sản phẩm, hai bundle chính thức hoặc adapter lịch sử; không sync personal skill/commit/push. Giữ evidence resolver và unknown-effect safety; không đổi partial thành complete để đạt nghiệm thu. Tự xử lý chi tiết coding thường lệ, chỉ hỏi nếu phát sinh thay đổi scope/quyền thực sự. Bàn giao files sửa, kết quả checks, preview và giới hạn.

Lượt lập kế hoạch hiện tại dừng khi file này hoàn thiện; chưa implement các extension nêu trên.
