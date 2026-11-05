# Đánh giá sau implementation và nghiệm thu workflow ZAP

Ngày 02/11/2026. Đối chiếu chat **Implement ZAP tester workflow plan** (`01a19a25-b29d-7f12-8961-06850aa1e860`), working tree hiện tại, dữ liệu nghiệm thu trên sản phẩm 100ms và kế hoạch W01–W08.

## Kết luận

**Cải tiến có tác dụng thực, đặc biệt ở closure theo câu hỏi, readback sau lỗi và kiểm soát unknown effects. Đã nghiệm thu được một đường vận hành thật; chưa nghiệm thu toàn bộ khả năng điều hành assessment rộng.**

Không nên đánh giá “đã sửa hết tám điểm yếu”, cũng không nên xem lượt nghiệm thu là chỉ thêm tài liệu. Core mới thực sự được dùng, phát hiện một lỗi tích hợp mà tests ban đầu chưa bắt được, được sửa rồi vận hành tiếp từ dữ liệu đã giữ. Hai câu hỏi UI mới có kết quả hợp lệ mà không cần đổi lịch sử lỗi thành pass.

Phần khắc phục mạnh nhất: W05 ở cấp câu hỏi mới và W08 ở cách recovery trong quyền. W01/W02/W04 đã có bằng chứng thực tế nhưng giới hạn ở lượt bổ sung. W03 vẫn chỉ cải thiện routing và khả năng nối adapter. W06/W07 chưa đủ bằng chứng để kết luận backlog toàn assessment đã được điều hành tới điểm dừng tốt nhất.

Đây là đánh giá mức trưởng thành dựa trên bằng chứng, không dùng phần trăm vì chưa có mẫu số đại diện cho mọi loại sản phẩm, phương pháp và tình huống vận hành.

## 1. Phạm vi kiểm tra độc lập lần này

- Đọc hai turn implementation và runtime acceptance của chat, chọn các command/output liên quan discovery, execution, reader failure, sửa helper, reporting và validation; không chỉ dựa final summary.
- Đọc skill, helpers business_discovery/question_evidence/work_selection/readiness, điểm tích hợp product_scope, adapter và report composer riêng của lượt nghiệm thu.
- Đối chiếu RUN/ALERTS/SCOPE_ALERTS của `100ms-workflow-acceptance-20261102` với báo cáo cũ `100ms-fresh-20261101`.
- Chạy lại bộ offline gồm 17 module đã dùng nghiệm thu: **193 tests chạy, 185 pass, 8 skip** theo điều kiện optional product source. Không có failure.
- Chạy `validate_bundle` trên ba report mới: pass.
- Tính lại reconciliation bằng inventory/observations/prerequisites/operations/actionHistory trong thư mục private: **2 case observed/matched; 3 pending effects resolved**.
- Kiểm tra hash ba report cũ theo charter của lượt nghiệm thu: vẫn byte-identical.

Không chạy traffic mới, không khởi động scanner, không sửa skill hoặc sản phẩm trong lần review này. Kết quả runtime là readback đã lưu và lịch sử thao tác, không phải tôi vừa chạy lại UI. Offline tests chứng minh contract được kiểm tra, không chứng minh agent luôn lập inventory đúng.

Lưu ý kỹ thuật: RUN công khai là bản compact, đã bỏ evidenceRefs. Đưa trực tiếp responsibilityInventory trong report vào reconciler bị từ chối vì thiếu provenance. Dùng input private được RUN dẫn tới thì reconciliation thành công. Đây là giới hạn khả năng tái tính từ report một mình; không phải hai câu hỏi bị mất coverage. Handoff tiếp theo cần chỉ rõ input làm việc, không ngầm coi report compact là executable plan.

## 2. Lượt nghiệm thu đã làm gì và chất lượng quyết định

### Discovery và lựa chọn công việc

Agent đọc lại source UI và các journey đã lưu, nhận ra trước đây thường dùng actor đã JOIN. Nó xác định hai câu hỏi chưa được trả lời rõ: JOIN thật từ preview và phục hồi khi browser không nhận ACK JOIN. Đây là gap nghiệp vụ độc lập, có giá trị; không phải chạy thêm payload để tăng số lượng.

Inventory mới có 16 feature groups: 2 mapped vào case mới, 14 `no-additional-question` dẫn về kết quả cũ. Cách làm này giúp tránh replay các phần đã biết. Tuy nhiên đây là review bổ sung trên một sản phẩm quen thuộc; chưa chứng minh discovery từ đầu trên sản phẩm mới hoặc toàn bộ 14 disposition đều được phân loại sâu bằng helper.

### Runtime và kết quả

- Thực hiện JOIN qua browser thật/ZAP với hai actor trên fixture mới.
- Server xác định HOST/BROADCASTER dù UI query khai role ngược lại; tên có markup được hiển thị dạng text trong consumer đã kiểm tra.
- Với mất ACK, UI giữ draft và key/body ban đầu; sau state readback, thực hiện một thao tác lấy lại receipt có chủ đích.
- Tổng 3 JOIN requests gồm 2 JOIN ban đầu và 1 receipt retrieval; tạo 2 membership. Không nên mô tả là “không có request JOIN lặp nào”: đúng hơn là **không có replay vận hành mù để sửa lỗi reader**, còn probe idempotency được thực hiện sau khi đã đọc state.
- Native session giữ 56 messages, 34 passive instances thuộc 7 plugin groups đã biết; **0 native active allocations**, không có nhóm alert mới.
- Hai matched observations mới được thêm; không biến chúng thành native vulnerabilities hay full-criterion pass.

### Recovery: cải tiến rõ nhất

Reader so sánh receipt bằng JSON.stringify nên thất bại khi thứ tự key khác nhau. Agent đọc receipt đã giữ và current membership/UI, xác minh semantic equality và không gửi thêm JOIN để sửa nhãn.

Tiếp đó continuation gặp lỗi tích hợp: validate resolvedEffects không nhận pending effects hiện tại. Agent tạo regression tái hiện failure, sửa core và kiểm tra lại. Một candidate resolution có objective khác bị từ chối; resolution khớp exact action/object/objective mới được dùng.

Kết quả cuối giữ `wf-member-first-attempt` là partial/unknown trong history, nhưng current projection resolve đủ ba effects. Đây là bằng chứng mạnh cho việc tách execution history khỏi question closure; cũng là bằng chứng rằng 184 tests pass ở lượt implementation đầu chưa đủ nghiệm thu runtime integration.

### Điểm dừng

Fixture được END, hai membership LEFT, browser thoát, scanner sở hữu được đóng theo readback đã lưu. Không có dấu hiệu từ các artifact đã kiểm tra cho thấy sản phẩm bị sửa/deploy lại trong lượt này. Agent không cần user nhắc “tiếp tục” giữa các bước và không xin lại quyền thao tác thường lệ.

**Điểm dừng phù hợp cho nghiệm thu hai câu hỏi và recovery path.** Nhưng câu “không còn phần việc độc lập khả thi của toàn assessment” cần căn cứ khác: inventory thực thi mới chỉ có hai case, còn old blockers được copy và các residual được giữ ở mức tổng quát. Không bắt buộc scan thêm để chứng minh điểm dừng; cần phân loại rõ phần việc cũ bằng bằng chứng đã có.

## 3. W01–W08 đã khắc phục đến mức nào?

### W01 — Inventory thiên endpoint: cải thiện khá, đã thấy hiệu quả trên sản phẩm

Có charter, feature/API map và H1 business discovery. Runtime phát hiện hai UI JOIN questions mà inventory/journey cũ chưa bao quát rõ, rồi thực thi đúng chúng. Điều này giải quyết một biểu hiện thực của điểm yếu cũ.

Giới hạn: 14 feature groups còn lại dùng disposition có lời giải thích, không được chuyển thành đầy đủ question/evidence mapping mới. Điều đó hợp lý cho continuation có giới hạn; không đủ để tuyên bố feature inventory toàn sản phẩm đã đầy đủ. Không yêu cầu một case cho mỗi nút UI hay tự động khám phá mọi feature.

**Mức nghiệm thu:** discovery bổ sung cho cùng sản phẩm đã chứng minh; discovery rộng trên sản phẩm mới chưa chứng minh.

### W02 — Reconcile chỉ biết tập đã khai: đã bổ sung cơ chế đúng, coverage review vẫn do tester

H1 kiểm tra feature chưa map, case chưa review, nguồn còn thiếu, rationale và mapping hai chiều. `workflowVersion: 1` đưa discovery gaps vào reconciliation. Runtime thực sự chạy review và selector trước execution; không chỉ thêm reference.

Giới hạn: `reviewStatus: reviewed` nghĩa là tập khai báo đã được đối chiếu, không phải tự chứng minh toàn source/spec không còn feature. Hai case observed chỉ chứng minh hai case; không chứng minh toàn backlog cũ đã hết việc. Kết quả summary hiện ghi scope FE/môi trường tương đối rộng, nên người đọc cần thấy rõ đây là delta review.

**Mức nghiệm thu:** tốt ở kiểm tra tính đầy đủ nội bộ và discipline review; chưa loại bỏ sự phụ thuộc vào discovery của tester, và không cần đặt mục tiêu bất khả thi đó.

### W03 — Capability/runner hẹp: khắc phục một phần

Có `map_question_capability`, tái dùng executor_routing; có adapter mẫu và fake integration tests. Trong runtime, agent nhận diện connector thiếu primitives cần thiết, tái dùng transport/adapter sản phẩm và native ZAP sở hữu trong quyền. Missing wrapper không bị coi là toàn ZAP không thể làm.

Giới hạn: vẫn phải viết nhiều script product-local cho browser, fixture, receipt, reconcile và report. Chưa thấy bằng chứng runtime sử dụng `map_question_capability` để tự điều phối câu hỏi này; quyết định routing chủ yếu do agent/source review. Chưa mở rộng generic FE fixture setup, cookie/SSO, method/body/rules; lượt này không có native active campaign.

**Mức nghiệm thu:** routing và contract hỗ trợ tốt hơn; portability/capability thực tế vẫn hẹp. Đây đúng với scope kế hoạch, không phải thiếu yêu cầu phải mở mọi runner.

### W04 — Readiness bất đồng bộ: cải thiện khá ở primitive, nghiệm thu runtime còn hẹp

H4 có stage, context, deadline, remaining budget, cancellation và reader-error; tests kiểm tra ACK/pending/result, timeout và mismatch. Runtime dùng helper cho scanner readiness, membership persistence và passive queue.

Giới hạn: membership readback đạt ready nhanh; chưa có runtime chậm nhiều tầng processor/consumer/media/segment qua H4. Browser still dùng product-local Playwright waits; FE finite predicate cap 12 giây được giữ đúng kế hoạch. Không có bằng chứng rằng lỗi background cũ đã được sửa runtime bằng helper mới.

**Mức nghiệm thu:** primitive và vài reader thật đã chứng minh; chưa nghiệm thu generic asynchronous media pipeline. Không cần bắt mọi boundary test đợi segment.

### W05 — Trộn attempt/closure/report: mạnh ở câu hỏi mới, chưa tốt ở tổng hợp lịch sử

EvidenceLinks/resolvedEffects được dùng thật; partial attempt vẫn giữ nguyên trong khi current question observed. Regression runtime đã sửa đúng thiếu pending effects. Bundle validation và việc bảo toàn báo cáo cũ đều được kiểm tra lại.

Vấn đề còn lại có bằng chứng cụ thể: báo cáo cũ có 19 criterion partial, 25 not-operated, 6 applicability-reviewed; projection mới có 4 partial, 46 not-performed. Ví dụ SEC-A01-03 từ partial chuyển thành top-level not-performed, trong khi priorAssessment.coverage vẫn partial. Các trạng thái này không cùng nghĩa và không nên so như tỷ lệ tiến độ; nhưng đây chính là điểm gây khó đọc của presentation hiện tại.

Không mất dữ liệu hoặc tự kết luận an toàn: lịch sử được giữ lồng bên trong. Tuy vậy người đọc top-level dễ hiểu rằng test cũ chưa diễn ra. `selectedTracks` cũng được copy từ report cũ, chưa phải trạng thái track tính lại từ toàn question model mới. CompletionSummary DAST liệt kê cả criterion question IDs và case IDs cho cùng hai câu hỏi, nên không dùng độ dài list làm số test độc lập.

**Mức nghiệm thu:** closure engine cho câu hỏi mới tốt; báo cáo cumulative/legacy còn một phần đáng kể cần hoàn thiện.

### W06 — Điều kiện đủ và mức sâu: tốt cho block mới, yếu hơn ở residual toàn assignment

Charter và required units được đặt trước execution. Agent kết thúc hai câu hỏi bằng factual readback, không sửa sản phẩm hay replay campaign để làm hết partial. Overall assignment/catalog vẫn partial, tách khỏi finite acceptance complete. Đây là cải thiện quan trọng.

Nhưng `report.py` chuyển remainingWork cũ thành question chung `remaining-assigned-requirement-resolved`, prerequisite chung `original-requirement-specific-policy-access-or-method`. Scope có 23 questions methodClass unresolved, 22 outside-zap, 2 zap-ui; một unresolved thuộc criterion N/A nên không nằm trong 22 DAST mapping gaps. “Unresolved” ở đây không tương đương 23 test thật sự còn cần chạy.

Nhiều remainingWork trộn hạn chế khái quát như không chứng minh mọi rendering context với failure fixture/processing cũ và câu hỏi policy cụ thể. Đây chính là nguồn làm assessment partial dai dẳng trong audit gốc. Giữ nguyên chúng tránh giảm scope sai, nhưng chưa giải quyết được cách chọn việc hữu ích tiếp theo.

**Mức nghiệm thu:** finite objective mới rõ và đủ; closure/disposition của backlog cũ chưa được chuẩn hóa đủ để đánh giá toàn assignment.

### W07 — Scheduler theo giá trị: có implementation và một đường chạy thật, chưa đủ bằng chứng ưu tiên toàn backlog

H2 chia ready/readback/reconcile/preparation, giữ missingHandlers và reasons; shared selector được dùng bởi continue_work. Runtime chọn HOST case priority high trước member, sau lỗi chuyển sang reconcile-state từ kết quả đã giữ. Có tests cho nhánh độc lập khi media blocked và preparation mở việc high-impact.

Giới hạn: runtime selection pool chỉ có hai case và recovery actions; chưa có một nhóm gồm journey độc lập, media blocked, missing handler và chuẩn bị high-impact cạnh tranh thực tế. Không thể từ việc chọn đúng giữa hai case suy ra scheduler đã giải quyết thiên lệch phân bổ công sức của assessment rộng.

**Mức nghiệm thu:** cơ chế tốt hơn, runtime cơ bản đã có; prioritization đa nhánh chủ yếu còn bằng chứng offline.

### W08 — Quyền, fixture và history: cải thiện tốt trong phạm vi lượt này

Agent tự dùng quyền hiện có để tạo fixture mới, không sửa fixture cũ/history để pass; thông báo private credentials, đọc state trước receipt probe, dừng đúng tài nguyên sở hữu. Hash ba report cũ vẫn khớp charter. Tách được deliberately assigned idempotency probe khỏi automatic unknown replay.

Giới hạn: đây là một môi trường local với quyền đã biết, chưa phải kiểm chứng mọi loại reset/instrumentation/production boundary. Không cần tạo thêm approval checklist để giải quyết giới hạn này.

**Mức nghiệm thu:** đủ mạnh để chấp nhận hành vi recovery/fixture/history đã quan sát; không suy rộng mọi môi trường.

## 4. Ba phần cần ưu tiên tiếp theo

### Ưu tiên 1 — Báo đúng tiến độ kế thừa

Hiển thị rõ `historicalCoverage`, `currentDeltaCoverage`, và câu hỏi nào đã đủ theo context tương thích; không bắt tự động nâng legacy thành new verified evidence. Khi chưa migrate, dùng “historical partial; current delta not assessed” thay vì một nhãn not-performed có vẻ bao trùm tất cả. Giữ applicability N/A riêng khỏi chưa chạy.

Không cần chạy lại sản phẩm. Có thể kiểm tra bằng SEC-A01-03, một criterion có observation mới, và một criterion N/A trên report hiện có. Không đổi overall partial chỉ vì presentation rõ hơn.

### Ưu tiên 2 — Phân loại residual trước khi mở thêm traffic

Với từng nhóm remainingWork có tác động đến việc chọn next action, xác định: câu hỏi động còn thiếu; dữ liệu đã có cần readback; dependency thật; ngoài phương pháp; giới hạn khái quát không phải nghĩa vụ mới; hoặc remediation đã được giao riêng. Chỉ tạo closure units cụ thể cho câu hỏi thật sự chưa trả lời.

Không cần migrate toàn bộ 4.330 operation cũ hoặc mọi criterion để bắt đầu. Làm theo nhóm có thể thay đổi quyết định tiếp tục/dừng trước. Nếu số việc khả thi bằng không sau review này, kết thúc partial là đúng; không cần scan thêm để “chứng minh có cố gắng”.

### Ưu tiên 3 — Nghiệm thu có chủ đích khi có task thực tiếp theo

Chọn scenario phù hợp assignment thật: một nhánh bất đồng bộ chậm, một journey độc lập, một missing primitive/handler; quan sát helper có chọn đúng, đọc đúng và giữ gap không. Native active/cookie/SSO chỉ kiểm tra khi được giao và cần cho sản phẩm, không bắt qualify toàn platform.

Đây là bước nâng độ tin cậy vận hành, không phải điều kiện phủ nhận hai câu hỏi đã nghiệm thu xong.

## 5. Kết luận về mức nghiệm thu

- **Chấp nhận:** implementation nền workflow và đường runtime preview JOIN → lost ACK → readback → exact effect resolution → report, với regression đã sửa.
- **Chấp nhận có giới hạn:** feature review, capability routing và readiness cho những reader đã chạy.
- **Chưa đủ căn cứ chấp nhận rộng:** discovery hoàn chỉnh toàn sản phẩm, scheduler tối ưu toàn backlog, generic runner/media support, hoặc tuyên bố không còn việc độc lập khả thi trong assignment cũ.
- **Vấn đề thực cần cải thiện:** presentation legacy/current và residual questions còn quá tổng quát. Đây là phần gần nhất với cảm giác “partial mãi” của người vận hành; nên sửa nó trước khi đầu tư thêm scan hoặc framework.

## Nguồn truy nguyên

Đường dẫn tương đối với `/Users/hahoangloc/Working/testing tool`:

- Kế hoạch: `docs/reviews/zap-skill-tester-workflow-implementation-plan-20261102.md`.
- Report hiện tại: `assessment-results/100ms-workflow-acceptance-20261102/{RUN,ALERTS,SCOPE_ALERTS}.json`.
- Report gốc: `assessment-results/100ms-fresh-20261101/{RUN,ALERTS,SCOPE_ALERTS}.json`.
- Adapter/report hiện tại: `.local/100ms-workflow-acceptance-20261102/{report.py,run_questions.py,preview_join.mjs,inventory.json,reconciliation.json}`; private inputs chỉ đọc tại workspace, không sao chép credential/raw vào tài liệu này.
- Helpers: `.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/{business_discovery.py,question_evidence.py,work_selection.py,readiness.py,product_scope.py}`.
- Test và mô tả nghiệm thu: `.agents/skills/mcp-zap-repo-operations/references/operational-validation.md`.

Không có sửa skill hoặc report assessment trong lượt review này.
