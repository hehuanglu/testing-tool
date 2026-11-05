# Phân tích điểm yếu của skill MCP ZAP trong bao quát nghiệp vụ và điều hành assessment

Ngày lập: 02/11/2026, múi giờ Việt Nam.  
Workspace: `/Users/hahoangloc/Working/testing tool`.  
Skill được xem xét: `.agents/skills/mcp-zap-repo-operations/SKILL.md` trên đĩa tại thời điểm lập tài liệu.  
Assessment minh họa: `assessment-results/100ms-fresh-20261101/RUN.json`.

## 1. Mục đích, phạm vi và kết luận chính

Tài liệu trả lời ba câu hỏi:

1. Skill có đang đặt yêu cầu quá cao so với hoạt động testing thực tế không?
2. Tại sao đã có nhiều scan, operation và đối soát nhưng vẫn phát hiện muộn những nghiệp vụ chưa được kiểm thử?
3. Cần điều chỉnh phần mô tả, discovery, runner, helper, reporting và điều phối theo hướng nào?

Đây là phân tích thiết kế workflow và cách vận hành đã ghi nhận, không phải một đợt scan mới, không phải danh sách lỗ hổng mới của sản phẩm, và không phải phê duyệt giảm scope. Việc lập tài liệu không sửa skill, runner, source sản phẩm hay ba báo cáo chính thức.

**Kết luận chính:** yêu cầu về tính trung thực của kết quả nhìn chung hợp lý. Điểm lệch nằm ở chỗ phạm vi bảo đảm được mô tả rộng, trong khi cơ chế lập inventory nghiệp vụ, diễn đạt readiness và điều phối vẫn phụ thuộc nhiều vào agent và adapter viết riêng. Hệ thống có thể kiểm soát rất chặt kết quả của các case đã biết nhưng vẫn bỏ sót cả một journey chưa được đưa vào inventory.

Không thể quy toàn bộ hiện tượng này cho skill. Có bốn lớp nguyên nhân cần phân biệt:

- **Mô tả skill:** đã có nhiều nguyên tắc đúng nhưng chưa chuyển thành thao tác discovery và closure đủ cụ thể.
- **Runner/helper dùng chung:** kiểm tra các đầu vào đã được khai báo; không tự bảo đảm danh sách đó bao quát nghiệp vụ. Một số entry có capability hẹp hoặc giả định theo sản phẩm mẫu.
- **Adapter cục bộ của assessment:** có inventory thiên về controller/API, reporting hardcode và reader bất đồng bộ chưa chính xác.
- **Agent điều hành:** đã có lúc kết luận hết việc khả thi trước khi đối soát đầy đủ FE. Đây là lỗi quyết định của agent, dù tài liệu đã yêu cầu tiếp tục công việc độc lập.

## 2. Cách đọc chứng cứ và mức chắc chắn

Phân tích dựa trên source và reference hiện hành, cùng operation/result đã lưu trong assessment. Không chạy thêm scanner hoặc kiểm thử sản phẩm để lập tài liệu.

Các kết luận được diễn đạt theo ba mức:

- **Xác nhận từ code:** có nhánh, điều kiện hoặc giới hạn cụ thể trong file được viện dẫn.
- **Xác nhận từ operation/readback:** có kết quả đã ghi trong RUN hoặc dữ liệu làm việc được RUN tham chiếu.
- **Suy luận thiết kế:** giải thích hợp lý về cách những hạn chế đó có thể gây bỏ sót hoặc tăng chi phí; không khẳng định đó là nguyên nhân duy nhất.

Code hiện hành cho biết khả năng hiện tại của helper. Nó không chứng minh cùng nội dung này đã tồn tại ở mọi thời điểm trong lịch sử assessment, nhất là khi workspace đang có thay đổi chưa commit. Vì vậy tài liệu không kết luận mọi lỗi lịch sử đều do phiên bản skill hiện hành gây ra.

“Chưa được bao quát” cũng có nhiều nghĩa khác nhau:

- Chưa phát hiện hoặc chưa lập câu hỏi.
- Đã lập câu hỏi nhưng chưa thực thi.
- Đã thực thi nhưng baseline/actor/readiness không hợp lệ hoặc thiếu readback.
- Câu hỏi đã được trả lời, kể cả bằng vi phạm; chỉ còn remediation hoặc giới hạn khái quát hóa.
- Nằm ngoài capability của phương pháp hoặc cần boundary/policy khác.

Không được gộp các trạng thái này thành một backlog scan chung.

## 3. Bản đồ tổng hợp vấn đề

| ID | Điểm yếu | Lớp chính | Cơ chế gây ảnh hưởng | Ưu tiên đề xuất |
|---|---|---|---|---|
| W01 | Inventory khởi đầu thiên về endpoint | Discovery, adapter | Nghiệp vụ/UI chưa có case không xuất hiện trong gap list | P0 |
| W02 | Reconciliation chỉ kiểm tra tập đã khai báo | Helper, agent | Queue/case hết việc bị hiểu thành sản phẩm không còn gap | P0 |
| W03 | Capability runner hẹp hơn phạm vi mô tả | Runner, routing | Công sức dồn vào adapter/qualification; chọn việc theo tool sẵn có | P1 |
| W04 | Readiness bất đồng bộ chưa thành contract tái sử dụng | FE helper, adapter | ACK hoặc elapsed time bị dùng thay kết quả xử lý thực | P1 |
| W05 | Trộn trạng thái execution cũ với closure hiện tại | Reporting, aggregation | Nhãn partial dai dẳng hoặc áp lực chạy lại để làm đẹp nhãn | P0 |
| W06 | Chưa vận hành hóa mức sâu và điều kiện đủ của engagement | Mô tả, intake | Mở rộng bảo đảm, truy nguyên failure hoặc duy trì scope mơ hồ | P0 |
| W07 | Scheduler thiếu ưu tiên theo giá trị nghiệp vụ | Điều phối, helper | Nhánh khó và lỗi cũ chiếm phiên; journey độc lập phát hiện muộn | P1 |
| W08 | Phân biệt ràng buộc an toàn với lựa chọn vận hành chưa đủ rõ | Mô tả, recovery, quyền | Hạn chế của một phiên bị hiểu thành cấm thử lại hoặc chuẩn bị fixture nói chung | P1 |

P0 nghĩa là cần xử lý trước khi dựa vào workflow để tuyên bố đã xét hết công việc của một assessment rộng. P1 nghĩa là cần xử lý để vận hành hiệu quả và giảm lỗi lặp. Đây là ưu tiên cải tiến workflow, không phải severity lỗ hổng bảo mật.

## 4. W01 — Inventory khởi đầu thiên về endpoint, chưa bắt buộc có danh sách nghiệp vụ/UI độc lập

### 4.1. Ánh xạ nguồn

- [E01] `product_scope.py`, hàm `inventory_from_operations()`, dòng 29–47: tạo case từ `doc.operations`; mỗi case gắn method/path/input và câu hỏi chung về kỹ thuật, role/state.
- [E02] Helper cục bộ `session.py`, dòng 65–74: inventory ban đầu duyệt `be/src/*controller.ts`, trích decorator method và controller prefix. Trong vòng lặp này không có discovery FE route, form, menu hoặc consumer.
- [E03] `references/product-discovery.md`, phần Preserve inventory: trọng tâm mô tả là method/route/input/role/object/action/relation/state. Skill và các reference FE có yêu cầu journey, nhưng chưa có bước đối chiếu bắt buộc giữa tính năng UI đã tìm thấy và danh sách câu hỏi được cấp phát.

### 4.2. Điểm yếu thực tế

Một endpoint không tương đương một nghiệp vụ. `PATCH preferences` có thể phục vụ device settings, pin, layout, panel, picture-in-picture và virtual background. Kiểm thử body/role của endpoint không chứng minh từng hành động UI và consumer của chúng đã được vận hành.

Ngược lại, một nghiệp vụ có thể trải qua nhiều endpoint và kênh: UI khởi tạo share, API cập nhật domain, signaling tạo peer, receiver phát video, LEAVE thay membership và provider dừng delivery. Danh sách route rời rạc không tự mô tả được quan hệ đó.

### 4.3. Lý do gây bỏ sót

Reconciliation chỉ nhìn thấy những mục discovery đã tạo. Khi inventory ban đầu không chứa “personal pin so với shared spotlight” hoặc “background chỉ commit sau processor readiness”, các luồng này không xuất hiện như pending/eligible. Agent phải tự nhớ và phát hiện lại khi đọc FE sau đó.

### 4.4. Minh họa trong assessment

Trong lượt cuối, sau nhiều operation backend và media, agent mới bổ sung các câu hỏi UI về pin/layout/background/reaction. Các operation sau được tạo để lấp gap:

- `final-ui-focus-journey`.
- `final-ui-background-journey`.
- `final-ui-bg-ready-journey`.
- `final-ui-reaction-journey`.

Đây là các journey có giá trị độc lập, không phải chỉ thêm payload để tăng số lượng. Việc phát hiện chúng muộn xác nhận inventory trước đó chưa phải cơ sở đủ mạnh để nói đã xét hết công việc khả thi.

### 4.5. Hướng xử lý

Dùng các trường inventory/question hiện có để giữ hai góc nhìn:

1. Bề mặt kỹ thuật: method, route, input, auth, object.
2. Nghiệp vụ: actor thực hiện hành động nào, trạng thái đầu/cuối, producer/consumer nào bị ảnh hưởng, điều gì cần quan sát.

Đối soát từ FE router, page/component có hành động, use case/spec được giao và các API liên quan. Mỗi tính năng phát hiện được cần dẫn đến câu hỏi, kết quả kế thừa có căn cứ hoặc gap/disposition cụ thể. Không sinh tích Descartes mọi role × state × input.

### 4.6. Điều kiện đánh giá cải tiến

Với ví dụ preferences, inventory phải phân biệt các câu hỏi pin/layout/background dù dùng cùng API. Có thể kiểm tra bằng walkthrough offline từ source và lịch sử đã lưu, chưa cần traffic mới.

## 5. W02 — Helper xác nhận tính đầy đủ nội bộ của case, không xác nhận discovery đủ

### 5.1. Ánh xạ nguồn

- [E04] `product_workflow.py`, `reconcile_responsibilities()`, dòng 230–259: duyệt từng case được cung cấp, so required units với observed units và prerequisite.
- [E01] `product_scope.py`, `reconcile()`, dòng 50–80: kiểm tra inventory completeness flag, case/context và observations ngoài inventory. Cờ `complete` vẫn do caller cung cấp.
- [E05] `references/responsibility-loop.md`, phần Reconcile and execute next steps: đã cảnh báo helper tin caller labels và không được sao chép requirements thành evidence units.

### 5.2. Điểm yếu thực tế

Helper có thể trả lời “mọi case trong danh sách đã có quan sát đủ theo contract”. Nó không tự trả lời “danh sách đã chứa mọi nghiệp vụ được giao”. Hai phát biểu này đang dễ bị agent nối thành một.

Đây không nhất thiết là bug của helper: một reconciler hữu hạn cần tin một số đầu vào đã review. Điểm yếu ở cấp workflow là thiếu thao tác review độc lập để bảo đảm đầu vào đó không bỏ tính năng.

### 5.3. Lý do gây bỏ sót

Nếu không có case background, helper không có missing unit background. Nếu action list không còn handler khả thi, vòng tiếp tục không biết cần discovery thêm. Tính nhất quán của JSON, operation references hoặc ba report không thể phát hiện điều không được khai báo.

### 5.4. Trách nhiệm của agent

Agent đã có lúc công bố không còn câu hỏi độc lập khả thi rồi tiếp tục phát hiện FE gaps. Kết luận đó vượt quá những gì helper và inventory chứng minh. Không thể gọi việc thiếu một case chưa được tìm ra là “dependency thật”.

### 5.5. Hướng xử lý

Trước một quyết định dừng, làm một lượt đối chiếu có chủ đích:

- Những tính năng được source/spec/UI cho thấy có nằm trong inventory không?
- Mỗi item có câu hỏi hữu hạn và sufficient observations không?
- Case đã đóng nhờ kết quả thực hay chỉ nhờ nhãn caller?
- “Không có next action” là không còn việc, hay thiếu adapter/handler/mapping?

Kết luận discovery phải có lý do, không chỉ một boolean. Không thể bảo đảm discovery tuyệt đối, nhưng có thể ghi rõ nguồn đã đối soát và phần chưa inspect.

### 5.6. Điều kiện đánh giá cải tiến

Một walkthrough cố ý bỏ journey có trong FE source phải bị phát hiện trong bước review discovery, dù toàn bộ case còn lại đều có đủ observations. Không cần tạo framework tự động suy luận toàn bộ nghiệp vụ.

## 6. W03 — Capability runner hẹp, portability và fixture hooks chưa đồng đều

### 6.1. Ánh xạ nguồn

- [E06] `references/runner-routing.md`, phần Anonymous/Authenticated backend và Frontend: mô tả các lane giới hạn kỹ thuật, method/body/path có điều kiện và các giả định theo sản phẩm.
- [E07] `anonymous.py`, dòng 109–115: entry này chỉ nhận `ruleIds` thuộc `40012/40018` và có ràng buộc request/vector cụ thể.
- [E08] `fe_authenticated_recipes.py`, dòng 15–18: `prepare()` từ chối recipe ngoài `finalsource` với lỗi `no reviewed setup adapter for this recipe`.
- [E09] `SKILL.md`, bước lựa chọn operation/runner: native phù hợp → orchestration → runner/adapter tối thiểu; thiếu adapter không làm mất scope.

### 6.2. Điểm yếu thực tế

Skill nói về nhiều loại sản phẩm và cả BE/FE/BOLA, nhưng không phải entry nào cũng hỗ trợ các bề mặt đó một cách tổng quát. Khả năng nhận reviewed journey không đồng nghĩa tự chuẩn bị được fixture, identity và lifecycle của sản phẩm mới.

Điểm này không có nghĩa ZAP chỉ hỗ trợ hai rule hoặc workflow không có bất kỳ đường nào khác. Giới hạn viện dẫn thuộc các lane cụ thể. Native operations hoặc adapter khác có thể phù hợp nếu được kiểm tra đúng deployment và quyền.

### 6.3. Lý do gây bỏ sót

Khi một lane dễ dùng cho query/body nhưng media lifecycle khó tích hợp, agent dễ phân bổ phần lớn thời gian cho lane có sẵn hoặc sửa phối hợp fixture. Các tính năng chưa có adapter không biến mất khỏi scope, nhưng cũng không tự trở thành action có thể chạy. Khoảng trống giữa “có nghĩa vụ” và “có executor” được lấp bằng script ad hoc.

Đây là nguyên nhân góp phần vào chi phí và thiên lệch lựa chọn công việc; không đủ bằng chứng để quy mọi gap trong assessment cho runner.

### 6.4. Hướng xử lý

Sau discovery, lập mapping capability cho từng câu hỏi: operation nào, transport nào, actor nào, fixture nào, readback nào. Nếu thiếu primitive, chỉ bổ sung phần đó vào adapter sản phẩm, tái sử dụng transport/auth/journal/report có sẵn.

Không mở rộng mọi runner đồng loạt và không bắt assessment phải hoàn thành một chương trình qualification toàn hệ thống. Chỉ cần verification tương xứng với boundary vừa thay đổi và câu hỏi được chọn.

### 6.5. Điều kiện đánh giá cải tiến

Một nghiệp vụ chưa có hook phải hiện thành “cần chuẩn bị adapter cho câu hỏi X”, không bị bỏ khỏi inventory và cũng không bị mô tả là ZAP không thể kiểm thử nếu chưa điều tra native primitive phù hợp.

## 7. W04 — Readiness bất đồng bộ và post-state còn dựa quá nhiều vào adapter riêng

### 7.1. Ánh xạ nguồn

- [E10] `fe_authenticated_contract.py`, dòng 10–11 và 26–29: tập action/predicate hữu hạn; predicate có giới hạn thời gian tối đa 12 giây trong entry này.
- [E11] `references/operational-readback.md`, phần Close the selected question: yêu cầu adapter phân biệt boundary/processing/persistence và xác minh actual application-reaching probes.
- [E12] Adapter `final_ui_background.mjs`, dòng 17: chờ cố định một giây sau Apply, sau đó suy ra có thể tiếp tục.
- [E13] RUN operation `final-background-prerequisite-diagnosis`: reader ghi device applied lúc `22:12:21.128Z`, trong khi PATCH thực ACK lúc `22:12:22.523Z`.

### 7.2. Điểm yếu thực tế

Các predicate DOM thông thường hữu ích nhưng chưa biểu đạt trực tiếp readiness nhiều tầng: command ACK, domain trạng thái đúng, sender RTP tăng, receiver decode và recorder có segment. Giới hạn 12 giây cũng không mặc nhiên phù hợp mọi tác vụ bất đồng bộ.

Tuy nhiên, lỗi chờ một giây là lỗi adapter/agent, không phải do contract bắt buộc dùng sleep. Tài liệu hiện hành đã yêu cầu actual readiness; phần thực thi đã không tuân thủ đủ.

### 7.3. Lý do gây bỏ sót hoặc diễn giải sai

Một reader dùng elapsed time làm readiness có thể tạo false blocker: hệ thống còn xử lý bình thường nhưng input kế tiếp được gửi quá sớm. Chiều ngược lại, chỉ thấy 200/READY hoặc outbound frames có thể tạo false coverage dù chưa có LIVE/RECORDING/segment cần thiết.

Nếu readiness logic được viết lại trong nhiều script, sửa một script không bảo đảm các caller khác kế thừa sửa đó.

### 7.4. Hướng xử lý

Cho adapter biểu đạt predicate có deadline và sampling phù hợp câu hỏi, gắn đúng object/operation. Ví dụ:

- Background: dialog Apply hoàn tất, track live/enabled và video decode, rồi mới chọn effect.
- Recording: đúng recordingId ở RECORDING và có RTP/segment khi mục tiêu yêu cầu.
- Revocation: đúng peer/counter sau LEFT/END; so sánh cùng tập đối tượng.

Không nâng mọi timeout hoặc buộc mọi test đều có segment. Readiness phải phục vụ đúng mục tiêu: kiểm tra enum bị từ chối không mặc định cần toàn bộ media pipeline nếu contract không yêu cầu nó.

### 7.5. Điều kiện đánh giá cải tiến

Fixture chậm nhưng hợp lệ không bị kết luận thất bại do sleep ngắn. ACK có trước kết quả không bị tính thành processing complete. Reader chỉ chạy lại phần quan sát còn thiếu sau khi outcome mutation đã được đối soát.

## 8. W05 — Reporting trộn lịch sử execution, câu hỏi hiện hành và completion của đợt đánh giá

### 8.1. Ánh xạ nguồn

- [E02] Helper cục bộ `session.py`, dòng 107–111: hardcode `taskCompletion: partial`; nhãn track dựa một phần vào operation ID có tồn tại hay không, FE có chuỗi remaining duties chung.
- [E14] `security_scope.py`, dòng 198–213: question sufficiency phụ thuộc observation units, linked case trạng thái, linked operation trạng thái và unknown/blockers.
- [E15] RUN operations `final-transport-offline-reconciliation`, `final-historical-native-input-reconciliation`, `final-missing-transport-readback`.
- [E16] `references/assessment-scope-and-completion.md`: đã yêu cầu tách assessment, security và remediation; không giữ mọi route partial mãi một cách máy móc.

### 8.2. Điểm yếu thực tế

Reporting cục bộ không tự tính closure của toàn track từ từng câu hỏi. Vì vậy các nhãn track là tuyên bố bảo thủ cần agent diễn giải, không phải kết quả coverage engine đủ chi tiết.

Trong common projection, nếu câu hỏi mới được liên kết cả với execution cũ failed/partial, cơ chế `op_open` hoặc linked case open có thể giữ câu hỏi mở. Cơ chế đó hợp lý khi phần failed chính là quan sát còn thiếu, nhưng cần chọn liên kết đúng: operation tham khảo lịch sử không nhất thiết là điều kiện bắt buộc của closure hiện tại.

Đây là rủi ro thiết kế/mapping cần xử lý, không phải kết luận rằng common helper chắc chắn đã làm sai mọi nhãn partial của RUN này. Assessment đang dùng cả adapter reporting riêng.

### 8.3. Lý do gây khó kết thúc

Một request cuối không có fixture hợp lệ có thể là control trùng hệt request đã có kết quả. Nếu backlog chỉ nói “allocation partial”, người vận hành dễ tưởng phải tạo thêm fixture để làm lần execution cũ trở thành thành công, trong khi lịch sử đó không thể và không cần bị sửa.

Readback cuối cho thấy:

- 30 request transport503 gồm 20 dòng trùng control đã có kết quả không503.
- Chỉ còn 10 signature input riêng cần followup; chúng được vận hành riêng và nhận409 ở version boundary, state không đổi.
- Bốn control content/recording/STAGE khác cũng trùng request đã được thực thi.

Điều này không hoàn tất các mục tiêu xử lý sâu hơn một cách tự động. Nó chỉ cho thấy phải xét **câu hỏi còn thiếu**, không lấy số execution failed làm số nghiệp vụ chưa kiểm thử.

### 8.4. Hướng xử lý

Giữ riêng bốn lớp trong dữ liệu hiện có:

1. Execution attempt: kết quả lần chạy, không sửa lịch sử.
2. Question: quan sát nào là đủ và còn thiếu gì.
3. Finding/security outcome: matched, vi phạm hoặc inconclusive.
4. Engagement/track completion: tổng hợp những câu hỏi thực sự được giao.

Followup trả lời đủ có thể đóng câu hỏi hiện tại; original allocation vẫn partial. Việc liên kết history với question nên chỉ rõ là context hay bằng chứng bắt buộc. Không lấy native plugin completion hoặc manual boundary followup thay mục tiêu sink/processing đã được giao.

### 8.5. Điều kiện đánh giá cải tiến

Có thể thể hiện đồng thời “attempt cũ thất bại”, “câu hỏi hữu hạn đã trả lời bằng followup hợp lệ”, “finding còn mở” và “toàn catalog vẫn partial”, không mâu thuẫn và không ép replay để cải thiện nhãn.

## 9. W06 — Mức sâu và điều kiện đủ của engagement chưa được chuyển thành thao tác intake nhất quán

### 9.1. Ánh xạ nguồn

- [E09] `SKILL.md`, dòng 18–25 và các bước 35–40: scope do user, every assigned API cần DAST, câu hỏi hữu hạn và sufficient observations.
- [E16] `references/assessment-scope-and-completion.md`, phần Assignment completion/Finite closure conditions: đã nói không cần sửa mọi finding hoặc giải thích mọi failure lịch sử.
- [E17] `references/track-intents.md`: định nghĩa track, nhưng mức đại diện và độ sâu vẫn phụ thuộc discovery/planning của từng assessment.

### 9.2. Điểm yếu thực tế

Không phải skill yêu cầu vô hạn. Ngược lại, nó đã cấm tạo mọi tổ hợp và có nguyên tắc finite closure. Hạn chế là workflow chưa buộc chuyển các nguyên tắc đó thành một danh sách câu hỏi đủ cụ thể và mức sâu hợp lý ngay từ đầu.

“Đánh giá cả project theo 50 tiêu chí” rộng hơn “DAST các luồng được giao”. Một số tiêu chí là assurance về implementation/governance; dù DAST đã đủ cho câu hỏi động, toàn catalog vẫn không thể complete chỉ bằng ZAP.

### 9.3. Lý do tạo cảm giác yêu cầu quá cao

- Trộn full-catalog completion với completion của đợt DAST.
- Trộn câu hỏi hành vi đã có đáp án với nguyên nhân sâu của lỗi cũ.
- Giữ các giới hạn khái quát như “không bảo đảm mọi browser/SLA” như thể đó luôn là nhiệm vụ test tiếp.
- Không ghi rõ vì sao một role/transport có thể dùng kết quả đại diện của đường xử lý chung.

### 9.4. Hướng xử lý

Ngay intake, ghi trong RUN/plan hiện có:

- Đối tượng và môi trường được đánh giá.
- Tính năng/câu hỏi và mức sâu: boundary, processing, persistence, actual media hay recovery.
- Kỹ thuật phù hợp, actor khác biệt có ý nghĩa và lý do dùng đại diện nếu có.
- Sufficient observations để đóng câu hỏi.
- Phần không thể kết luận bằng phương pháp và điều kiện để thay đổi kế hoạch.

Không tự giảm scope gốc. Nếu user đã giao cả catalog thì vẫn giữ mục chưa đánh giá, nhưng báo riêng đợt DAST đã hoàn tất đến đâu. Không tự bịa timebox, SLA hoặc residual-risk acceptance.

### 9.5. Điều kiện đánh giá cải tiến

Hai tình huống phải được xử lý đúng: một vi phạm có đủ quan sát được đóng về coverage dù chưa sửa; một tiêu chí governance chưa đánh giá vẫn mở nhưng không tự sinh thêm DAST traffic vô ích.

## 10. W07 — Scheduler chưa ưu tiên theo giá trị và còn dựa thứ tự action/handler

### 10.1. Ánh xạ nguồn

- [E01] `continue_work()`, dòng 103–116: gom candidate theo thứ tự case/action rồi chọn candidate đầu tiên có handler.
- [E05] Responsibility loop: yêu cầu tự tiếp tục công việc hữu ích, nhưng mapping action/handler và việc chọn nhánh vẫn do caller thiết lập.
- [E18] `references/local-remediation-and-continuation.md`: yêu cầu một dependency chỉ chặn phần phụ thuộc và phải tiếp tục nhánh độc lập.

### 10.2. Điểm yếu thực tế

Hàm không có cơ chế nội tại so sánh giá trị nghiệp vụ, khả năng đóng câu hỏi, chi phí fixture, prerequisite đã sẵn sàng hoặc mức giảm bất định. Có handler là điều kiện thực thi, không phải bằng chứng đó là việc đáng làm nhất.

Điều này không khiến scheduler tự động sai: caller có thể sắp thứ tự đúng. Nhưng nó khiến chất lượng phụ thuộc nhiều vào agent, nhất là sau nhiều phiên recovery.

### 10.3. Lý do gây bỏ sót

Lỗi gần nhất và script đang làm dở dễ trở thành trọng tâm. Các nhánh recording/STOP503/trace có thể chiếm phần lớn thời gian, trong khi journey độc lập rẻ hơn chưa được lập action. Continuation dài tiếp tục mang các nextActions cũ, khiến lựa chọn bị neo vào lịch sử thay vì câu hỏi hiện tại.

### 10.4. Hướng xử lý

Chọn theo thứ tự thực dụng, có thể làm thủ công trong plan hiện có:

1. Kết quả đã đủ, chỉ cần readback/đóng câu hỏi.
2. Gap có điều kiện đóng rõ, prerequisite hiện có.
3. Gap cần chuẩn bị/sửa vận hành nhỏ trong quyền.
4. Dependency thật, giữ điều kiện mở lại.
5. Phần ngoài phương pháp, không cố chạy để tạo traffic.

Trong cùng nhóm, ưu tiên tác động bảo mật và giá trị của quan sát mới, sau đó chi phí/setup. Không cần xây một scoring engine trước khi cải thiện hành vi điều hành.

### 10.5. Điều kiện đánh giá cải tiến

Khi recording readiness bị chặn, một journey UI độc lập vẫn được chọn và thực hiện. Khi code có action nhưng không có handler, trạng thái phải là thiếu khả năng thực thi/chuẩn bị, không được suy ra hết việc.

## 11. W08 — Ràng buộc an toàn, lịch sử và quyền vận hành dễ bị nhập làm một

### 11.1. Ánh xạ nguồn

- [E09] Skill yêu cầu giữ history, không replay unknown mutations, không đổi binds/TLS/auth và không giảm gate để pass.
- [E18] Local remediation cho phép sửa orchestration/adapters và chuẩn bị fixture trong quyền; nói rõ giữ dữ liệu cũ không cấm tạo fixture mới được phép.
- [E05] Responsibility loop cho phép allocation mới sau sửa prerequisite, phải loại effect đã ACK/unknown khỏi replay không kiểm soát.
- Prompt vận hành riêng của assessment này cấm rộng hơn: không replay phần đã đạt chỉ để đổi nhãn, không reset quota/history, không sửa product/header/cutoff hoặc rebuild chỉ vì đổi block.

### 11.2. Điểm yếu thực tế

Những quy tắc này có mục đích khác nhau:

- Không replay effect unknown: bảo đảm an toàn và đúng outcome.
- Không ghi đè raw/history: bảo đảm tính trung thực.
- Không tự đổi scope/auth/TLS: bảo đảm đúng quyền và đúng target.
- Không chạy lại phần đã đạt chỉ vì nhãn: tránh lãng phí trong phiên cụ thể.
- Không reset fixture/quota: có thể là yêu cầu bảo toàn dữ liệu của môi trường hiện tại, không phải chuẩn cấm mọi test environment.

Nếu không phân loại, agent có thể hiểu rằng “giữ history” đồng nghĩa không được regression trên fixture mới, hoặc không được thay đổi điều kiện test dù đã có quyền.

### 11.3. Hướng xử lý

Intake cần phân biệt quyền đã cấp cho target và quyền trên fixture/tooling: có được tạo mới, cleanup, reset test-only data, đổi pacing, instrument, rebuild isolated helper, hoặc thực hiện regression không. Quyền nào chưa cấp thì giữ dependency; quyền đã cấp thì dùng, không hỏi lại.

Một lần chạy lại có mục đích khác hoặc sau sửa lỗi, được phép và ghi provenance đúng, là regression/retest hợp lệ. Nó không làm execution cũ thành thành công. Ngược lại, replay một mutation chưa rõ outcome để thử parser vẫn không hợp lệ.

### 11.4. Điều kiện đánh giá cải tiến

Agent giải thích được mỗi giới hạn đến từ user, scope, safety invariant hay implementation gate; không gán tất cả cho “skill yêu cầu”. Trong assessment hiện tại, các quyền bị user hạn chế không được tự mở lại từ tài liệu này.

## 12. Chuỗi nguyên nhân tổng thể

Chuỗi góp phần dẫn tới bỏ sót trong case này có thể mô tả như sau:

1. Inventory khởi đầu lấy API làm trục chính.
2. Những nghiệp vụ dùng chung endpoint chưa có danh sách UI/action/consumer độc lập.
3. Runner phổ thông không khớp đầy đủ media/lifecycle, cần nhiều adapter cục bộ.
4. Debug fixture/readiness tiêu tốn sự chú ý; reader mới lại phát sinh lỗi riêng.
5. Reconciler kiểm tra đúng tập case đã nhập nhưng không tìm journey chưa nhập.
6. Reporting giữ partial tổng quát và nhiều failure lịch sử, chưa tách tốt phần đã trả lời.
7. Agent kết luận hết công việc khả thi dựa trên backlog hiện có, trước khi kiểm tra discovery lần nữa.
8. Khi đọc FE có chủ đích, các journey còn thiếu mới xuất hiện và được vận hành.

Không cần hạ chuẩn auth/readback để sửa chuỗi này. Cần sửa chất lượng inventory, ánh xạ câu hỏi và quyết định chọn/đóng công việc.

## 13. Phân biệt phần hợp lý, phần quá rộng và phần không được bỏ qua

### 13.1. Nên giữ

- Đúng actor/role/session và target runtime cho câu hỏi đang kiểm tra.
- Native alerts tách khỏi tester observations; direct support tách khỏi ZAP coverage.
- ACK không thay terminal/result; unknown effects phải readback trước retry.
- Không dùng zero alerts hoặc native Complete để tuyên bố sản phẩm an toàn.
- Finding gốc, currentRetest và build phải có provenance riêng.
- Không tự giảm scope hoặc chấp nhận residual risk.

### 13.2. Cần diễn đạt và điều hành thực tế hơn

- Mọi route cần được xử lý trong scope không có nghĩa mọi rule phải chạy trên mọi role/state.
- Đủ kết quả cho câu hỏi không có nghĩa phải tìm exact root cause mọi lỗi lịch sử.
- Một giới hạn khái quát hóa không mặc định là một test case còn thiếu.
- Bảo toàn lịch sử không có nghĩa cấm tạo fixture hoặc regression hợp lệ trong quyền.
- Không có handler/recipe không có nghĩa câu hỏi ngoài khả năng ZAP.
- Kết thúc đợt DAST có giới hạn không có nghĩa hoàn tất assurance toàn catalog.

### 13.3. Không giải quyết bằng đổi nhãn

Media/recording tiếp tục trong adapter outage đã được quan sát. Có thể chốt câu hỏi về hành vi đó với kết quả có giới hạn hoặc vi phạm theo policy áp dụng. Muốn khắc phục cần assignment riêng; muốn chấp nhận cần quyết định của chủ thể có thẩm quyền. Không thể tự đặt SLA sau khi thấy số đo để làm test pass.

Tenant/upstream auth/production policy chưa xác định và assurance ngoài ZAP cũng không thể được coi N/A chỉ để hoàn thành báo cáo.

## 14. Lộ trình cải tiến đề xuất

### Bước 1 — Sửa discovery và cách đóng câu hỏi trước

Áp dụng W01, W02, W05, W06. Dùng trường hiện có để ghi business journeys, sufficient observations, current gap và quan hệ với attempts/history. Bỏ hardcode completion khỏi composer cục bộ khi triển khai thay đổi được giao; completion phải dựa reconciliation đúng nghĩa.

Không sửa các nhãn hiện có sang complete hàng loạt. Trước tiên xác định câu hỏi nào thực sự còn mở và vì sao.

### Bước 2 — Cải thiện lựa chọn công việc và quyền chuẩn bị

Áp dụng W07, W08. Đưa công việc dễ/giá trị cao/prerequisite sẵn lên trước; không để một nhánh khó chặn nhánh độc lập. Ghi rõ fixture/tooling authority và điều kiện allocation mới, không tạo approval flow lặp lại.

### Bước 3 — Chỉ bổ sung runner primitive theo nhu cầu đã xác định

Áp dụng W03, W04. Ưu tiên các readiness/readback có thể tái sử dụng cho tác vụ bất đồng bộ, rồi fixture hooks cần thiết cho sản phẩm. Không refactor mọi runner hoặc nâng mọi cap/timeout.

### Bước 4 — Kiểm tra hành vi bằng lịch sử có sẵn

Các kịch bản cần kiểm tra khi triển khai cải tiến:

1. Endpoint đủ traffic nhưng thiếu một UI journey: phải phát hiện trước kết luận hết việc.
2. Một request cũ thất bại nhưng control tương đương đã có: giữ failure, đánh giá đúng gap hiện tại, không replay cả scan.
3. Câu hỏi có đủ quan sát vi phạm: coverage được đóng, remediation còn mở.
4. Async ACK sớm, result muộn: reader chờ đúng điều kiện, không lấy sleep làm readiness.
5. Một dependency chặn media: vẫn chọn được journey độc lập.
6. Catalog có mục ngoài ZAP: giữ unassessed, không tạo traffic giả hoặc tự giảm scope.
7. Regression được cấp quyền và effect unknown chưa được đối soát: cho phép trường hợp đầu, chặn trường hợp sau.

Các kiểm tra này có thể bắt đầu bằng walkthrough/offline với artifact hiện có. Chỉ thực thi traffic mới khi cần xác minh primitive thay đổi và nằm trong assignment phù hợp. Unit test/validator không chứng minh agent tương lai sẽ luôn lập inventory đúng.

## 15. Nguồn tham chiếu cục bộ

Các số dòng trong nội dung là vị trí khi lập tài liệu; có thể dịch chuyển khi source thay đổi. Function/section name là điểm định vị ổn định hơn.

- **E01:** [product_scope.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope.py) — `inventory_from_operations`, `reconcile`, `continue_work`.
- **E02:** [session.py của assessment](../../.local/100ms-fresh-20261101/session.py) — inventory controller và report composer. Đây là adapter cục bộ, không phải core skill dùng chung.
- **E03:** [product-discovery.md](../../.agents/skills/mcp-zap-repo-operations/references/product-discovery.md).
- **E04:** [product_workflow.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_workflow.py) — `reconcile_responsibilities`.
- **E05:** [responsibility-loop.md](../../.agents/skills/mcp-zap-repo-operations/references/responsibility-loop.md).
- **E06:** [runner-routing.md](../../.agents/skills/mcp-zap-repo-operations/references/runner-routing.md).
- **E07:** [anonymous.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/anonymous.py) — campaign admission.
- **E08:** [fe_authenticated_recipes.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/fe_authenticated_recipes.py) — `prepare`.
- **E09:** [SKILL.md](../../.agents/skills/mcp-zap-repo-operations/SKILL.md).
- **E10:** [fe_authenticated_contract.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/fe_authenticated_contract.py) — actions/predicates và validation.
- **E11:** [operational-readback.md](../../.agents/skills/mcp-zap-repo-operations/references/operational-readback.md); [active_questions.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/active_questions.py).
- **E12:** [final_ui_background.mjs](../../.local/100ms-fresh-20261101/final_ui_background.mjs) — prefix readiness chưa đúng, được giữ nguyên lịch sử.
- **E13:** [RUN.json](../../assessment-results/100ms-fresh-20261101/RUN.json) — operation `final-background-prerequisite-diagnosis` và các journey cuối; [ALERTS.json](../../assessment-results/100ms-fresh-20261101/ALERTS.json) — findings với prefix `100ms-fresh-20261101-final-`.
- **E14:** [security_scope.py](../../.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/security_scope.py) — `project_scope`.
- **E15:** [RUN.json](../../assessment-results/100ms-fresh-20261101/RUN.json) — operations `final-transport-offline-reconciliation`, `final-historical-native-input-reconciliation`, `final-missing-transport-readback`.
- **E16:** [assessment-scope-and-completion.md](../../.agents/skills/mcp-zap-repo-operations/references/assessment-scope-and-completion.md).
- **E17:** [track-intents.md](../../.agents/skills/mcp-zap-repo-operations/references/track-intents.md).
- **E18:** [local-remediation-and-continuation.md](../../.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md).
- **E19:** [operational-validation.md](../../.agents/skills/mcp-zap-repo-operations/references/operational-validation.md) — hướng dẫn kiểm tra hành vi bằng lịch sử/offline, phân biệt structural validation với runtime và agent behavior.

Không có credential/token/raw media được sao chép vào tài liệu. Các tham chiếu private chỉ phục vụ truy nguyên tại workspace hiện tại; người nhận ngoài môi trường này cần bản đã chọn lọc và làm sạch nếu được giao chia sẻ.

## 16. Trạng thái hoàn thành tài liệu

Đã lập một tài liệu Markdown duy nhất, ánh xạ tám điểm yếu với mô tả/source/operation liên quan, giải thích cơ chế và lý do ảnh hưởng, phân biệt trách nhiệm và đề xuất điều kiện đánh giá cải tiến.

Đây là định hướng cải tiến, chưa phải implementation hay acceptance của skill mới. Không thay đổi scope hoặc kết luận bảo mật của assessment hiện hành.
