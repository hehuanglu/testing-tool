# Audit tĩnh tính liên kết của mcp-zap-repo-operations

Ngày audit: 02/11/2026, giờ Việt Nam. Đối tượng: bản skill tại `.agents/skills/mcp-zap-repo-operations` trong working tree, kể cả file đang sửa và chưa được Git theo dõi. HEAD tham chiếu: `18f17860bad327a18345f949644aac4d40b7fece`; HEAD không đại diện đầy đủ cho nội dung đang audit.

## Kết luận trực tiếp

Skill có một hợp đồng đánh giá v2 khá nhất quán ở cấp trung tâm, và có code thực hiện kiểm tra cấu trúc, liên kết bằng chứng, điều phối journal/lease và xuất ba báo cáo. Tuy nhiên, nó vẫn là **quy trình do agent điều hành, có các thư viện hỗ trợ**, chưa phải một chương trình tự động nhận yêu cầu rồi bảo đảm đánh giá đúng từ đầu đến cuối.

Các cầu nối quan trọng còn phụ thuộc agent: hiểu yêu cầu, khám phá đủ phạm vi, chọn oracle đúng, xác thực nguồn phê duyệt, nối case với executor thật, diễn giải phản hồi thành quan sát, phân loại alert và đồng bộ Google Sheets. Khi agent nhập sai những sự thật này nhưng vẫn tạo dữ liệu hợp lệ, nhiều bộ kiểm tra có thể chấp nhận cấu trúc mà không biết kết luận sai về nghiệp vụ.

Có cả lỗi diễn đạt cục bộ, thiếu thông tin trong packet và giới hạn triển khai. Không được gộp tất cả thành “skill không hoạt động”, cũng không được lấy việc có validator để khẳng định mọi chỉ dẫn được cưỡng chế.

## Phương pháp và giới hạn của lần audit này

- Đọc SKILL.md, agents/openai.yaml và 39 file Markdown trong references, gồm knowledge và lịch sử validation; đối chiếu các điểm nối chính với code v2, CLI, evidence resolver, executor routing và hàm ghi file.
- Kiểm tra 247 đích liên kết Markdown cục bộ trong tập tài liệu trên: không có đích file bị thiếu. Đây là kiểm tra tồn tại file, **không phải kiểm chứng tất cả anchor, nội dung nguồn, hay khả năng chạy**.
- Xem xét thêm các giới hạn runner đã được tài liệu ghi rõ. Không đọc và chứng minh toàn bộ thư viện, mọi adapter, mọi test hay Java scanner checkout bên ngoài.
- Không chạy unit test, scanner, Docker, trình duyệt, request tới sản phẩm, đăng nhập, đọc credential hay ghi Drive. Không dùng web vì đối tượng là tính nhất quán của nguồn cục bộ, không phải xác nhận năng lực ZAP hiện hành.
- Những kết quả test và runtime trong operational-validation-history là **tuyên bố lịch sử được lưu trong tài liệu**, không phải kết quả tôi vừa chạy hoặc xác nhận độc lập.
- Không sửa skill hay code thực thi. Báo cáo này mô tả hành vi được chỉ dẫn và cơ chế có thể nhìn thấy; không bảo đảm một agent tương lai thực sự tuân thủ từng bước.

Trong các bước dưới đây, **[Agent]** nghĩa là quyết định/quan sát do agent chịu trách nhiệm; **[Code]** nghĩa là có kiểm tra hoặc cơ chế tương ứng trong code đã đối chiếu; **[Executor]** nghĩa là tùy đường chạy, deployment và admission; **[Connector]** nghĩa là cần công cụ ngoài thư viện. Một bước có nhiều nhãn vẫn có thể cần agent xác thực ý nghĩa dữ liệu đầu vào.

## 1. Đi qua từng phần của SKILL.md

### Frontmatter và đoạn mở đầu

Mô tả hứa đánh giá tiêu chí đã được chuyên gia duyệt bằng ZAP, hỗ trợ các kỹ thuật anonymous/auth/UI/ownership có điều kiện và hỗ trợ audit skill/tool. Điều này không đồng nghĩa có một executor đa sản phẩm hỗ trợ mọi kỹ thuật. Đoạn mở đầu yêu cầu xác định SKILL_DIR, thư viện assessment và scanner checkout riêng nếu cần source/build. Câu “product-neutral” nói về workflow; các runner bên dưới vẫn có giới hạn và giả định sản phẩm.

### Choose the assessment contract

Đây là bộ định tuyến nghiệp vụ: assessment mới vào v2; continuation đọc RUN trước; legacy giữ nguyên nghĩa cũ. Việc audit hiện tại đi vào nhánh skill-only, nên không kích hoạt hai vòng phê duyệt assessment, traffic hay ba báo cáo sản phẩm. Cơ chế CLI có chặn một số lệnh legacy đối với v2; việc nhận diện nhiệm vụ và lựa chọn đúng RUN vẫn do agent.

### Work from approved criteria

Chuỗi chính là yêu cầu gốc → khám phá tối thiểu → duyệt criteria → khám phá phục vụ test → duyệt plan → thực hiện → đọc lại → kết luận. Các bullet chia trách nhiệm thành khám phá, thiết kế câu hỏi, chọn executor, thực hiện có journal, sửa prerequisite và delegation. Chuỗi này có ý nghĩa, nhưng nhiều mũi tên là thao tác agent phải tự làm; không có pipeline v2 tự nối mọi bước. Delegation là nhánh tùy chọn khi phù hợp, không phải yêu cầu luôn phải tạo worker.

### Evidence and completion

Phần này định nghĩa ranh giới kết quả khá rõ: traffic thật qua ZAP mới hỗ trợ ZAP coverage; source hỗ trợ thiết kế/diễn giải; UI/BOLA/passive không tự thay thế active. `met`, `unmet`, `not_evaluable` là quyết định có điều kiện, còn unfinished thì pending. Reviewer kiểm tra các joins và nghĩa vụ đã khai báo, không tự đọc HTTP để biết đúng/sai, cũng không tự tìm nghĩa vụ bị bỏ quên.

### Deliver results

Cần đồng thời ba JSON, working state riêng và một Google Sheets cho assessment sản phẩm mới. Sheets là giao diện chính cho người dùng, không thay thế journal hay bộ reviewer. Ba JSON có exporter v2; Sheets chưa có exporter trong skill. Skill-only audit không cần dựng ba JSON hay bảng Sheets giả. Có chênh lệch giữa tài liệu đầu ra v2 và một số hướng dẫn kỹ thuật cũ, được liệt kê ở phần phát hiện.

### Read when applicable

Đây là thư viện tham chiếu theo tình huống, không phải danh sách việc buộc phải chạy. Không phải assessment nào cũng đọc hết auth lifecycle, retest, triage, Docker hay repository build. Việc chọn đúng tài liệu do agent; không có bộ nạp tự suy ra mọi phụ thuộc và xung đột phiên bản.

### Preserve runtime and history

Các bất biến: giữ working tree và lịch sử, actor thật, không lộ secret, không replay effect chưa rõ, không hạ guard, không phá tài nguyên không thuộc quyền. Một số bất biến có code ở coordinator/executor; nhiều lệnh cấm vẫn là chỉ dẫn hành vi. Skill không biến mọi tool/shell call trong môi trường thành call có gate v2.

## 2. Mô tả từng thao tác vận hành

Đây là thứ tự logic và các nhánh điều kiện. Các bước mang điều kiện chỉ xảy ra khi chọn đường tương ứng; không phải 205 thao tác đều phải được thực hiện ở mỗi lần dùng skill. “Nhỏ nhất” ở đây là thao tác ra quyết định, đọc/ghi dữ liệu hay gọi công cụ có thể kiểm toán riêng; không giả định những syscall hoặc API parameter mà runtime chưa được kiểm tra.

### A. Nhận nhiệm vụ, đường dẫn và hiện trạng

1. [Agent] Đọc yêu cầu hiện tại và ràng buộc đã được người dùng đưa trước đó.
2. [Agent] Phân loại: assessment mới, continuation, status/setup, sửa skill hay audit skill/tool.
3. [Agent] Nếu chỉ audit/sửa tài liệu, giữ công việc ở phạm vi đó; không suy ra quyền gửi traffic.
4. [Agent] Xác định thư mục skill từ chính file đang được nạp.
5. [Agent] Gán ASSESSMENT_ROOT tới `lib/zap-product-assessment` trong thư mục skill.
6. [Agent] Đọc AGENTS áp dụng cho vùng sẽ thao tác.
7. [Agent] Đọc HEAD để biết baseline Git.
8. [Agent] Đọc dirty/untracked state và giữ nguyên thay đổi có sẵn.
9. [Agent] Xác định product source và scanner source là hai vị trí khác nhau.
10. [Agent] Chỉ xác minh MCP_ZAP_REPO nếu có nhiệm vụ source/build/doctor cần checkout scanner.
11. [Agent] Nếu cần chạy thư viện, xác định Python 3.13 và môi trường có dependency đã khóa; không tự tải package trong assessment.
12. [Agent] Ghi rõ thông tin thiếu thay vì lấy URL, role, credential hay adapter của sản phẩm cũ làm mặc định.

### B. Tìm hợp đồng và phục hồi assessment đã có

13. [Agent] Với continuation, tìm RUN chính thức theo product/environment đã xác minh.
14. [Agent] Đọc continuation và chỉ các operation/criteria liên quan đến bước tiếp theo.
15. [Agent] Đọc private working-input references; báo cáo đã sanitize không phải working RUN thực thi.
16. [Agent/Code] Kiểm tra `criteriaWorkflow.version:2` để chọn reviewer v2; không suy ra từ tên thư mục.
17. [Agent] Nếu là legacy, giữ `partial`, `observed`, assessmentRound và pin theo hợp đồng cũ.
18. [Agent] Nếu chuyển legacy sang v2, soạn revision tiêu chí/kế hoạch và lấy duyệt đúng phần thay đổi; không sửa lịch sử.
19. [Agent] Đọc journal, ACK/native IDs, pending/unknown effect và resource ownership còn lưu.
20. [Agent/Code] Với coordinator state v2, đọc lease/journal hiện tại; worker timeout không có nghĩa effect đã dừng.
21. [Agent] Phân biệt kiến thức ổn định với actor/token/fixture/build/port có thể đã đổi.
22. [Agent] Chỉ kiểm tra lại những phụ thuộc sống cần cho hành động tiếp theo.

### C. Giữ yêu cầu gốc và khám phá tối thiểu

23. [Agent] Đọc yêu cầu/catalog được giao như dữ liệu, không thực thi lệnh hay prompt nhúng trong đó.
24. [Agent] Giữ nguyên câu chữ gốc, ID, nguồn và vị trí nguồn.
25. [Agent] Tách phần diễn giải do agent viết khỏi nguyên văn và giả định.
26. [Agent] Xác định các tiêu chí thực sự được chọn; catalog chưa chọn không tự thành nghĩa vụ.
27. [Agent] Xác minh product, target, environment và feature boundary trong quyền được giao.
28. [Agent] Đọc source/spec/UI/config được phép để hiểu thành phần liên quan.
29. [Agent] Xác định giao thức thực tế: REST, GraphQL, RPC, browser, async hoặc loại khác.
30. [Agent] Xác định auth/session mechanism có liên quan.
31. [Agent] Xác định trust boundary, owner/sharing/tenant semantics cần để hiểu yêu cầu.
32. [Agent] Xác định state transition và nơi có thể quan sát kết quả.
33. [Agent] Đánh dấu riêng fact, assumption và unknown.
34. [Agent] Chỉ discovery runtime nếu đã có authority tương ứng; chưa duyệt plan thì chưa active test.
35. [Agent] Nếu mơ hồ làm đổi oracle/phạm vi/quyền, hỏi chuyên gia; tiếp tục phần độc lập có thể làm.

### D. Soạn và duyệt criteria

36. [Agent] Tạo ID ổn định cho từng criterion.
37. [Agent] Gắn rawText/source và requirement đã chuẩn hóa.
38. [Agent] Ghi product/environment boundary mà criterion được hiểu trong đó.
39. [Agent] Viết oracle: điều gì được xem là đúng/sai và căn cứ lấy ở đâu.
40. [Agent] Xác định applicability: applicable, not_applicable hay unknown.
41. [Agent] Với N/A, ghi lý do từ sản phẩm; thiếu credential/capability không phải N/A.
42. [Agent] Xác định observation đủ dùng và những kết luận không được suy rộng.
43. [Agent] Tách yêu cầu ghép thành case dự kiến nhưng giữ liên kết và nghĩa của criterion cha.
44. [Agent] Chọn stoppingRule: phải xử lý mọi case hay được dừng khi có counterexample hợp lệ.
45. [Agent] Soạn revision tiêu chí có thể review; người dùng không phải tự viết JSON.
46. [Code] Tính criteria digest trên version/context/revision/nội dung criteria.
47. [Agent] Trình criteria revision và oracle cho chuyên gia review.
48. [Agent] Tái sử dụng duyệt đã có nếu đúng nội dung và phạm vi; nếu thiếu thì chờ duyệt thật.
49. [Agent/Code] Ghi approval kind/revision/digest/source; code chỉ so khớp các trường, agent phải kiểm nguồn duyệt.

### E. Khám phá phục vụ kiểm thử và lập kế hoạch

50. [Agent] Từ criteria đã duyệt, xác định inventory cần thiết để đánh giá chúng.
51. [Agent] Nếu phạm vi là “mọi protected API”, giữ đủ các operation thuộc tập đó.
52. [Agent] Phân biệt method/route và business operation dù GraphQL/RPC dùng cùng URL.
53. [Agent] Đi từ feature tới API/consumer và từ API/auth/state ngược về feature khi cần.
54. [Agent] Chỉ gom biến thể nếu cùng security boundary/oracle và ghi excluded conclusions.
55. [Agent/Code] Có thể dùng business discovery helper để kiểm các feature/case/source đã khai báo.
56. [Agent] Tự kiểm lại source coverage; helper không thấy feature bị bỏ khỏi cả hai danh sách.
57. [Agent] Với từng case, ghi objective và expectedBehavior có căn cứ trước khi chạy.
58. [Agent] Ghi target/build/context và actor/role/object/relation/state thực sự cần.
59. [Agent] Ghi baseline/control, input location, requiredEvidence và stage cần quan sát.
60. [Agent] Ghi fixture/auth/prerequisite và phụ thuộc giữa các case.
61. [Agent] Xác định effect read/mutation/start và action descriptor cụ thể nếu dùng coordinator dispatch.
62. [Agent] Chọn executor ứng viên và kiểm schema/auth/request/fixture/reader support.
63. [Agent] Ghi capability theo đúng mức source-reviewed, offline-checked hoặc runtime-observed.
64. [Agent] Ghi resourceIds của scanner/session/fixture dùng chung, không chỉ URL target.
65. [Agent] Ghi cleanup/retention, preparation/fallback được phép và giới hạn nguồn lực.
66. [Agent] Ghi allowedLimitations cùng missing observation và stopping condition có thể chấp nhận.
67. [Agent] Ghi authority source/target/allowedEffects; các trường này ghi lại quyền chứ không tạo quyền.
68. [Agent] Nếu muốn delegation, đưa biên công việc/tài nguyên/hiệu ứng được giao vào plan để duyệt.

### F. Chọn tool và executor thực tế

69. [Agent/Executor] Đọc đầy đủ tools/list của runtime sẽ nhận request, không dựa vào danh mục lịch sử 78 tool.
70. [Agent] Đọc field/type/requiredness/constraint và auth semantics của tool cần dùng.
71. [Agent] Xác định image/JAR/runtime liên quan khi cần; cùng version string không đủ chứng minh đồng nhất.
72. [Code] Có thể so schema hai runtime và kiểm arguments bằng executor_routing.
73. [Code] Field không được khai báo bị coi là thiếu khả năng biểu đạt; không gửi field lạ để thử cho qua.
74. [Agent/Code] Với guided exact method/body, kiểm direct mode và prepared auth thật theo semantics được xác minh.
75. [Agent] Tách browser login khỏi native active-scan authentication.
76. [Agent] Chọn native operation nếu đủ; nếu chưa đủ, xem configuration và helper/adapter có sẵn.
77. [Agent] Chỉ viết adapter/runner tối thiểu khi có khoảng thiếu cụ thể và nằm trong scope cho phép.
78. [Agent] Không đổi anonymous thành bearer, REST thành GraphQL hay UI thành API để vừa runner.
79. [Agent] Giữ case unsupported cùng primitive thiếu và bước chuẩn bị; tiếp tục case độc lập.
80. [Agent] Với common runner, đọc admission/compiler/rule/vector/pin/fixture/cleanup của đúng nhánh.
81. [Agent] Không chọn finalsource/archive adapter chỉ bằng thay URL hoặc tên thư mục.

### G. Duyệt kế hoạch và chuẩn bị thực thi

82. [Code] Tính plan digest gắn cả approved criteria digest và nội dung plan/revision.
83. [Agent] Trình plan cụ thể gồm scope, effect, oracle, resource, fallback và delegation nếu có.
84. [Agent] Nhận hoặc tái sử dụng plan approval đúng nội dung; thời gian trôi qua không thay cho duyệt.
85. [Agent/Code] Ghi nguồn duyệt, revision và digest.
86. [Agent] Khi criteria/oracle đổi đáng kể, quay lại duyệt criteria; khi target/effect/plan đổi đáng kể, duyệt plan.
87. [Agent] Sửa kỹ thuật trong authority/fallback đã duyệt không cần xin lại từng case/fixture/allocation.
88. [Agent] Chọn bước hữu ích tiếp theo: related unknown readback, retained-result readback, ready execution, rồi preparation.
89. [Agent] Nêu mục tiêu work block, observation còn thiếu và điều kiện kết thúc block.
90. [Agent/Executor] Nếu executor cần Docker/browser, xác minh đúng context/daemon/Compose/ownership/health.
91. [Agent/Executor] Đo filesystem/RAM/headroom và áp dụng guard thật của đường chạy, không lấy số cũ làm ngưỡng hiện hành.
92. [Agent] Chuẩn bị legitimate actor/fixture theo quyền đã có; DB không phải mặc định và cần authority cụ thể.
93. [Agent] Khi phải giữ credential/token riêng, thông báo nhu cầu lưu; giữ ngoài argv, prompt worker và báo cáo.

### H. Packet, lease và lần gọi executor

94. [Agent] Có thể tự thực hiện tuần tự; chỉ dùng worker khi phù hợp và nằm trong plan đã duyệt.
95. [Code] Nếu dùng make_packet, kiểm approval hiện tại, user stop/pause và caseIds thuộc plan.
96. [Code] Chọn trường case được allowlist, authority, refs, revision/digest và resourceIds vào packet.
97. [Agent] Bổ sung reference tối thiểu cho executor/secret/working facts; packet hiện không tự mang mọi thông tin plan.
98. [Agent] Nếu dùng worker, cung cấp context chọn lọc; không sao chép full transcript hay secret values.
99. [Code] Persist coordinatorState trước khi acquire resource lease.
100. [Code] Acquire lease với binding assessment/task/worker/packet và ghi leased event vào journal.
101. [Code] File lease mới dùng cơ chế no-clobber; lease cũ không tự hết hạn vì worker chết.
102. [Code] Trước dispatch, xác minh packet hiện tại, lease, action descriptor và effect cho phép.
103. [Code] Kiểm các case prerequisite có evidence execution đủ theo điều kiện đã khai báo.
104. [Code] Chặn action ID đã tiêu thụ, effect liên quan chưa rõ và task còn pending ngoài readback được chỉ định.
105. [Agent/Executor] Ngay trước effect, kiểm target, identity/session, fixture version/state và ownership đang sống.
106. [Code/Executor] Ghi durable intent trước effect; executor thật vẫn phải giữ native ACK/IDs/results riêng.
107. [Code] Gọi callback executor đã admitted; coordinator không tự tạo transport hay import module từ packet.
108. [Code] Nếu callback lỗi, ghi unknown rồi trả lỗi; callback trả về thì ghi acknowledged, chưa coi là terminal.
109. [Agent/Executor] Theo dõi đúng guided operationId/native scanId/queue jobId; giữ ID thật thay vì đoán.
110. [Agent/Executor] Theo dõi auth/resource/scope và dừng producer thuộc quyền khi guard bị vi phạm.

### I. Các nhánh kỹ thuật và side effect cụ thể

111. [Executor] Nếu cần import spec, dùng OpenAPI/GraphQL/WSDL tương thích; import có thể gửi request và đổi session.
112. [Executor] Nếu cần auth, prepare profile/context/user thật; ZAP user không tự tạo account/role trong sản phẩm.
113. [Executor] Validate session bằng probe/cơ chế phù hợp; login 200 hay decoded JWT không tự chứng minh role.
114. [Executor] Nếu cần crawl, chọn HTTP, Client Spider hoặc AJAX theo mục tiêu; không tự chạy mọi loại.
115. [Executor] Giới hạn context/origin/mutation trước crawl; auto fallback không chứng minh JS coverage.
116. [Executor] Nếu cần active, xem policy/rules/strength/threshold hiện có và workload được cho phép.
117. [Executor] Seed baseline đúng method/body/vector/actor; seed không tự thành active probe.
118. [Executor] Start scan một lần, giữ ACK/ID và poll trạng thái đến observation cần hoặc giới hạn hợp lệ.
119. [Agent/Executor] Đếm payload thực sự thay input và tới application; zero payload giữ thiếu active coverage.
120. [Executor] Với authenticated work, chỉ ghi coverage của khoảng/session/actor thật sự hợp lệ.
121. [Executor] Với FE, dùng browser thực hiện login/click/submit/navigation/reload và kiểm UI/network/post-state đã chọn.
122. [Agent] Không lấy SPA 200, crawl hay direct login/API setup thay cho UI journey thật.
123. [Executor] Với BOLA, chuẩn bị owner-positive và non-owner/cross-role hợp lệ theo policy có căn cứ.
124. [Executor] Gửi comparison qua ZAP sendRequest/proxy nếu muốn ZAP-derived evidence; bypass chỉ có giá trị hỗ trợ riêng.
125. [Agent/Executor] Đọc body/data/side effect trước và sau; 403/404/200 một mình không đủ cho mọi câu hỏi.
126. [Executor] Với collection, dùng dữ liệu phân biệt owner và đọc hết phạm vi/pagination cần thiết.
127. [Agent] Chỉ dùng queue/AF nếu được chọn; queued/ACK/completed plan không tự chứng minh test thành công.
128. [Agent] Chỉ mở natural expiry/revoke/concurrency/retest/triage sâu nếu được giao hoặc cần cho câu hỏi đã duyệt.

### J. Đọc kết quả và chuyển thành bằng chứng

129. [Agent] Xác định result cần đọc thuộc acceptance, boundary, processing, persistence hay consumer/delivery.
130. [Agent] Với 202/job ACK, đọc thêm exact job/object nếu câu hỏi cần processing/persistence/delivery.
131. [Executor] Dùng bounded readiness phù hợp; deadline và timeout không tự tạo product SLA.
132. [Agent] Nếu reader lỗi, đọc retained result/ACK/state trước khi sửa parser; không replay mutation làm parser test.
133. [Agent] Tách validation đúng, auth loss, fixture conflict và handler thực sự được hỏi.
134. [Agent] Tách baseline/calibration/site-tree traffic khỏi selected changed-input probes.
135. [Agent] Lưu sanitized semantic readback trong operation; raw secret-bearing traffic ở vùng private.
136. [Agent] Tạo evidenceLink với operationId, observationUnits, resultPath, resultRead, basis, context và role.
137. [Code] Kiểm operation ID tồn tại, pointer đọc được/nonempty và kiểu link hợp lệ.
138. [Code] Đối chiếu context của question/link/operation và finite compatibility được phép.
139. [Code] Không cho inherited origin/method/route/inputLocation/objective qua compatibility override.
140. [Code] Link role=context giữ lịch sử nhưng không cấp evidence units.
141. [Code] Nếu support contexts xung đột hoặc effect liên quan chưa rõ, giữ thiếu units/diagnostic.
142. [Agent] Tự xác minh readback thật sự chứng minh unit; code không suy ra ý nghĩa từ nội dung HTTP.
143. [Agent] Từ oracle và observation, đề xuất matched, violated hoặc not_evaluable; không copy requirement thành result.
144. [Agent/Code] Với unknown effect, thêm exact action/object/case readback resolution; giữ nguyên history cũ.
145. [Agent/Code] Reconcile coordinator action bằng operation terminal/readback đúng binding rồi mới release lease.

### K. Lỗi, sửa prerequisite và tiếp tục

146. [Agent] Phân loại lỗi ở transport/schema/auth/fixture/reader/resource hay actual product behavior.
147. [Agent] Đọc lịch sử lỗi và knowledge áp dụng trước khi khởi động allocation phụ thuộc tương tự.
148. [Agent] Xác định observation thiếu và điều kiện nào đã đổi trước một lần thử mới.
149. [Agent] Sửa tối thiểu mapping/parser/config/fixture trong authority; không tự sửa vulnerability của sản phẩm.
150. [Agent] Kiểm sửa bằng saved output/offline check hoặc baseline bounded cần thiết, tùy loại sửa.
151. [Agent] Nếu đổi code làm pin drift, tạo allocation mới khi cần; không repin lịch sử để pass.
152. [Agent] Giữ kết quả boundary hợp lệ nhưng không dùng nó đóng nghĩa vụ processing chưa đạt.
153. [Agent] Khi một branch thiếu role/fixture/capability, tiếp tục branch độc lập còn làm được.
154. [Agent] Không lấy max_actions/cap/request count hay xuất report làm lý do assessment đã xong.
155. [Agent] Nếu không thể làm tiếp đúng phạm vi, ghi cause, options, missing evidence và reopen condition cụ thể.
156. [Agent] Giới hạn có thể sửa được chưa làm vẫn là việc còn lại, không tự thành not_evaluable.

### L. Kết luận tiêu chí và completion

157. [Code] Chạy criteria-review trên working RUN hiện tại, không lấy cached status làm bằng chứng.
158. [Code] Kiểm cấu trúc criteria/case reciprocal links, ID, effect và dependency cycle.
159. [Code] Kiểm criteria approval và plan approval đúng revision/digest.
160. [Code] Với matched/violated, resolve evidence rồi kiểm đủ units và support operation context.
161. [Code] Với not_evaluable, kiểm reason nằm trong allowedLimitations và đủ các trường giải thích.
162. [Code] Nếu remainingFeasibleActions không rỗng, giữ case pending và tạo next work.
163. [Code] Applicability unknown để criterion pending; N/A cần product basis và disposition theo hợp đồng.
164. [Code] Tất cả case matched đủ điều kiện mới cho criterion met.
165. [Code] Có violation đủ chứng cứ cho unmet theo stoppingRule; all_cases giữ case còn lại phải được xử lý.
166. [Code] Counterexample chỉ waive case chưa trả lời nếu mọi parent liên quan đều cho phép tương ứng.
167. [Code] Thiếu/stale approval làm final criterion verdict về pending dù có observation ứng viên.
168. [Code] Kiểm resources đã khai báo có disposition/readback đúng, producer đã dừng/được giữ/được containment hợp lệ.
169. [Code] Đọc active coordinator leases và journal pending; chúng có thể chặn completion dù RUN cũ ghi xong.
170. [Agent/Code] Unknown không đọc được chỉ có thể giữ contained limitation với exact state/impact/noReplay/reopen basis.
171. [Agent] Tự kiểm không có nghĩa vụ/producer/resource khả thi bị bỏ khỏi khai báo.
172. [Code] Tính criterion counts, pending work, diagnostic và eligibleForCompletion.
173. [Agent] Diễn giải completed là đã xử lý hợp đồng đánh giá; không phải mọi criterion met hay sản phẩm an toàn.

### M. Alert, mapping và ba JSON

174. [Agent/Executor] Đọc actual native findings cho đúng target/session; settle passive và xử lý truncation/page/EOF khi cần.
175. [Agent] Giữ native rule/identity/severity/confidence/provenance; không đổi tester observation thành native alert.
176. [Agent] Với observed alert, ghi concrete security signal, expected/observed, policy basis và suspected/confirmed/needs-review.
177. [Agent] Để healthy control, fixture error và bare uncertainty trong RUN.
178. [Agent/Code] Triage mixed legacy records thành loại rõ ràng; exporter không tự hiểu nghĩa của nhãn cũ.
179. [Agent] Thiết lập stable alert identity và grouping/deduplication có căn cứ.
180. [Code] Kiểm alert kind, ZAP transport, identity và operation refs bắt buộc tùy loại.
181. [Agent] Chọn mapping alert tới original criterion bằng lý do ngữ nghĩa, không chỉ cùng OWASP category.
182. [Code] Kiểm mapping IDs/rationale và current criteria approval; tạo SCOPE_ALERTS đúng subset của ALERTS.
183. [Code] Tính distinct alerts, native/observed, mapped/unmapped, mapping count và occurrence count riêng.
184. [Code] Review lại khi publish; nếu yêu cầu finalize mà chưa eligible thì từ chối trước khi ghi bundle.
185. [Code] Tạo RUN projection có verdict/status hiện tại, controls, operations và private continuation references.
186. [Code] Sanitize raw fields/secret keys/known secret variants rồi kiểm lại liên kết và tính nhất quán bundle.
187. [Agent] Tự soát sensitive content còn lại; sanitization không tự biết mọi secret/PII được nhúng tùy ý.
188. [Code] Ghi ba file trong vùng staging; destination mới được publish bằng rename.
189. [Code] Nếu overwrite được yêu cầu, chỉ chấp nhận destination report phù hợp và thay từng file; crash có thể làm bundle lệch generation.
190. [Agent] Giữ raw/journal/pin/private working state và historical bundles; recomposition không phải retest.

### N. Google Sheets và bàn giao

191. [Agent/Connector] Chỉ với assessment sản phẩm mới: nạp kỹ năng Drive/Sheets và chọn connected tools thực tế.
192. [Agent/Connector] Tạo một native Sheets file, một worksheet, một assessment table sớm trong run; không đổi quyền chia sẻ.
193. [Agent] Lưu ngay file ID, URL, worksheet identity, run association và sync state vào private working state.
194. [Agent/Connector] Viết metadata và bảy cột: Mã; Tiêu chí bảo mật; Phạm vi / Cách kiểm tra; Trạng thái / Kết luận; Quan sát / Căn cứ; Mức độ; Việc tiếp theo.
195. [Agent] Giữ một hàng mỗi criterion; tách planned/performed, suspected/confirmed và N/A/method limit trong nội dung.
196. [Agent/Connector] Update theo stable criterion ID ở các mốc; hòa giải human edits thay vì append/ghi đè mù.
197. [Agent] Chỉ đưa severity của finding liên quan; không tự tạo severity cho tiến độ criterion.
198. [Agent/Connector] Read back run identity, headers, row count/IDs, verdict và nội dung quan trọng so với snapshot đã review.
199. [Agent] Kiểm evidence links dùng được với người nhận; local path không tự thành link Drive truy cập được.
200. [Agent/Connector] Nếu tạo/write chưa rõ kết quả, tìm lại file ID/metadata; không tự tạo file mới hoặc rerun test để sửa export.
201. [Agent] Nếu sync thất bại, giữ local assessment và báo Sheets pending/outdated, kèm bước publish còn thiếu.
202. [Agent] Handoff bắt đầu bằng assessment status/verdict, actual work, alert counts, exact limits; kèm ba JSON và URL Sheets đã xác minh khi áp dụng.
203. [Agent] Nếu chưa xong và phải checkpoint, ghi lý do thực, next action, pending effects và resource disposition; không giả cơ chế monitor nền.
204. [Agent] Khi resume, đọc lại working state/leases và kiểm live dependency chọn lọc trước effects, không reset hoặc replay do đổi chat.
205. [Agent] Nếu đã hoàn tất phạm vi audit/assessment, kết thúc với giới hạn/reopen trigger thực; không tạo thêm việc hay yêu cầu người dùng “continue” vô cớ.

## 3. Các điểm liên kết đáng nghi, theo mức ảnh hưởng

### F01 — Cầu nối v2 từ discovery sang thực thi chưa được tự động hóa

**Loại:** giới hạn triển khai được tài liệu thừa nhận; ảnh hưởng cao nếu hiểu skill như pipeline tự động. [operational-validation.md:75](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md:75>) nói rõ không có automatic v2 discovery-to-live-executor adapter. [product_scope_cli.py:14](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope_cli.py:14>) cung cấp criteria-review/digest/packet/merge; [criteria_delegation.py:334](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:334>) dispatch một callback đã admitted chứ không chọn hoặc dựng executor.

**Hệ quả:** agent phải tự nối approved case/action → executor → ACK/result storage → operation/readback/evidenceLinks. Gọi criteria-review hoặc tạo packet không tự chạy test. Dùng scope continue legacy để “lấp cầu nối” không mặc nhiên có hợp đồng v2.

**Đề nghị:** diễn đạt ngay ở đầu skill rằng agent orchestrates bằng các executor có điều kiện; chỉ thêm adapter thật khi được giao triển khai và đã xác định use case.

### F02 — Quy tắc ALERTS trong BOLA còn mâu thuẫn với hợp đồng trung tâm

**Loại:** xung đột tài liệu xác định được. [bola-research.md:15](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/bola-research.md:15>) cho ALERTS giữ meaningful outcomes gồm matched và inconclusive; [zap-result-boundary.md:24](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md:24>) và [alert-triage.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/alert-triage.md>) yêu cầu healthy controls/bare uncertainty nằm trong RUN. V2 exporter yêu cầu kind rõ và securitySignal cho observed alert ([criteria_reporting.py:71](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_reporting.py:71>)).

**Hệ quả:** agent chỉ đọc guide BOLA có thể tăng alert count bằng những test bình thường hoặc chưa rõ kết quả. Code chặn nhãn legacy mơ hồ nhưng vẫn phụ thuộc agent phân loại có đúng nghĩa không.

**Đề nghị:** sửa câu BOLA thành quan sát bình thường vào RUN, chỉ issue/suspicion có security signal mới vào observed alerts. Trong audit này chưa sửa.

### F03 — Packet tối thiểu chưa mang đầy đủ hợp đồng worker được mô tả

**Loại:** chênh lệch mô tả–triển khai. Canonical workflow mô tả worker nhận objective/oracle, relevant facts, limitations/resource obligations. [criteria_delegation.py:103](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_delegation.py:103>) chỉ copy các trường id/criterionIds/objective/expectedBehavior/expectationBasis/requiredEvidence/coverageContext/effects/actions/dependsOnCases. Packet có authority/resources/refs, nhưng không tự copy criterion oracle/raw/source, allowedLimitations, fixture, cleanup/retention hay fallback tùy ý trong case/plan.

**Hệ quả:** expectedBehavior truyền được phần oracle ở cấp case; không phải hoàn toàn không có kỳ vọng. Tuy nhiên, worker không mặc nhiên có đủ approved limit/fallback/cleanup context. Coordinator phải cung cấp reference phù hợp và worker phải đọc nó. Không nên coi helper đã tạo packet là đủ ngữ nghĩa.

**Đề nghị:** định nghĩa rõ trường bắt buộc trong packet hoặc bắt buộc reference chọn lọc tới approved case details; giữ nguyên quyền coordinator quyết định verdict.

### F04 — Duyệt, evidence và khả thi vẫn dựa vào sự thật do agent nhập

**Loại:** trust boundary, phần lớn đã được tài liệu thừa nhận. [criteria_workflow.py:162](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_workflow.py:162>) kiểm approval bằng kind/revision/digest; source chỉ phải có text. Evidence resolver kiểm pointer/context/units; reviewer nhận matched/violated từ case result. Limitation không có remainingFeasibleActions mới terminal, nhưng code không tự khám phá action bị bỏ khỏi danh sách.

**Hệ quả:** source approval giả nhưng nonempty, semantic readback sai hoặc missing work bị bỏ khai báo không thể được phát hiện chỉ nhờ digest/schema. Đây không tự động là vulnerability sản phẩm hay bằng chứng agent sẽ làm sai; đây là giới hạn thật của lời hứa “evidence-backed”.

**Đề nghị:** mô tả rõ mỗi trust boundary; review trực tiếp approval source, raw/semantic correspondence và discovery extent. Không viết thêm test khớp câu chữ để giả lập semantic assurance.

### F05 — Google Sheets là nghĩa vụ bắt buộc nhưng chưa tích hợp vào completion code

**Loại:** khoảng trống integration có chủ ý. SKILL.md:43 và single-table-drive-output yêu cầu file + verified URL; tài liệu nói rõ chưa có automatic exporter. Reviewer/publisher v2 đã đọc không kiểm spreadsheet ID, sync status, bảy cột hay remote readback.

**Hệ quả:** assessment evidence có thể completed và JSON xuất thành công trong khi user-facing delivery còn thiếu/outdated. Chính tài liệu tách publication failure khỏi assessment completion, nên đây không phải mâu thuẫn verdict; nhưng agent phải báo thêm delivery status, không được nói “đã giao đầy đủ” dựa vào completed.

**Đề nghị:** chuẩn hóa delivery state riêng và handoff checklist phù hợp; không trộn Drive failure thành not_evaluable của security criterion.

### F06 — Một số tài liệu kỹ thuật vẫn nói như generic exporter chưa có nhánh v2

**Loại:** hướng dẫn cũ thiếu qualification theo phiên bản. [operations-and-results.md:23](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operations-and-results.md:23>) nói generic compact_results còn xuất kiểu cũ và chỉ dùng nội bộ; phần lifecycle phía cuối hướng tới review-closure/assessmentRound. Trong khi [product_scope.py:324](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope.py:324>) đã route criteriaWorkflow sang criteria_reporting; product-assessment-handoff có đoạn v2 đúng và rào rõ legacy phía dưới.

**Hệ quả:** đọc guide kỹ thuật ngoài bối cảnh có thể chọn nhầm command hoặc tưởng v2 chưa có exporter. SKILL/canonical hiện ưu tiên v2 nên có cách giải xung đột; điều đó không xóa độ khó đọc và nguy cơ chọn sai nhánh.

**Đề nghị:** đặt version boundary ngay đầu operations-and-results và chỉ qualify cảnh báo “unadapted legacy composer”; không xóa legacy history.

### F07 — Tập hợp resource thật vẫn cần được khai báo đầy đủ; lease không bao phủ mọi đường gọi

**Loại:** giới hạn bảo đảm. [criteria_workflow.py:184](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_workflow.py:184>) kiểm union của run.resources và resourceIds đã khai báo, cộng journal/lease khi có coordinatorState. `coordinator_lock` không tạo lock nếu không có state. make_packet fallback theo target khi thiếu resourceIds; tài liệu đã nhắc shared scanner phải có resource ID thật.

**Hệ quả:** cùng scanner ở hai URL khác nhau hoặc coordinator directory khác nhau không được tự nhận diện là cùng resource. Gọi native tool ngoài coordinator cũng không bị thư viện này tự bọc lease. Đây là điều kiện sử dụng phải đúng, chưa phải bằng chứng có actual overlap trên runtime.

**Đề nghị:** ghi rõ phạm vi enforcement: cùng coordinator state và consistent scanner/session/fixture identity; executor path nào không đi qua coordinator phải giữ admission/journal tương đương.

### F08 — Sanitization có cơ chế thật nhưng không phải bảo đảm mọi dữ liệu chia sẻ đã sạch

**Loại:** giới hạn bảo vệ thông tin. [criteria_reporting.py:161](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/criteria_reporting.py:161>) loại raw fields, che secret keys, dùng known secret variants và cleaner. Không thể tự biết mọi credential/PII nằm trong basis, rawText, arbitrary semantic fields hoặc encoding lạ. CLI report không có đối số secrets tương đương Python API trong đoạn interface đã đọc.

**Hệ quả:** bước agent tạo semantic projection và triage input vẫn quan trọng; upload supporting material lên Drive cần soát riêng. Không có cơ sở từ audit tĩnh này để nói đã có leak thực tế.

**Đề nghị:** giữ dữ liệu thực thi private; kiểm nội dung sẽ chia sẻ, không chỉ kiểm schema; nêu rõ caller phải cung cấp known secrets khi dùng API tương ứng.

### F09 — Workflow trung lập còn sót bối cảnh “50 tiêu chí”

**Loại:** nhiễu tài liệu, ảnh hưởng thấp hơn. [zap-result-boundary.md:13](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md:13>) nói “50 criteria in the current assessment” trong reference tái sử dụng. Những câu “không chèn 50 rows” có thể chỉ là ví dụ; câu “current assessment” dễ bị đọc thành bối cảnh chung hiện hành.

**Hệ quả:** không tìm thấy hardcode số 50 trong reviewer v2 đã đọc, nên không kết luận code ép đủ 50 tiêu chí. Nguy cơ là agent mang scope cũ vào nhiệm vụ mới.

**Đề nghị:** chuyển bối cảnh mẫu thành ví dụ có nhãn hoặc bỏ số cố định khỏi hợp đồng chung.

### F10 — “State progression” là mô tả lifecycle, chưa phải state machine đầy đủ trong reviewer

**Loại:** độ chính xác mô tả. Canonical workflow có draft → awaiting criteria → planning → awaiting plan → executing → completed. `review_workflow` thực tế đòi cấu trúc plan ngay để validate và tính status từ approval/results; không emit riêng draft/planning. waiting_dependency xuất khi userRequest pause; dependency thông thường chưa đủ tự đổi status.

**Hệ quả:** agent vẫn có thể lập draft trong hội thoại/private artifacts, nhưng không nên quảng bá reviewer như orchestrator quản lý toàn bộ lifecycle state và tự biết đang chờ dependency. Không có workflow scheduler tự chuyển từ intake sang execution.

**Đề nghị:** phân biệt authoring phase với computed assessmentStatus; giữ pending work/diagnostic cụ thể trong giao diện.

## 4. Những đoạn có liên kết kỹ thuật thực sự tốt

- Duyệt plan gắn criteria digest, nên đổi tiêu chí làm stale plan approval; không chỉ kiểm một boolean approved.
- Reviewer không dùng số alert hay status completed của attempt làm đủ bằng chứng. Link context, observation units, pending effects và resource review ảnh hưởng conclusion.
- Hợp đồng counterexample được xử lý cả khi case có nhiều parent; không vô tình bỏ nghĩa vụ all_cases của parent khác.
- Report projection không được dùng như executable working RUN. CLI/report tách v2 khỏi lệnh closure/inventory legacy và không âm thầm migrate history.
- V2 alert publisher có exact mapped subset, giữ original criterion text/source, tách alert/mapping/occurrence counts và kiểm bundle sau sanitization.
- Coordinator có intent-before-callback, consumed action IDs, exact lease binding và reconcile trước release. Điều này bảo vệ đường chạy qua coordinator, không tự bao trùm mọi tool call ngoài nó.
- Hàm atomic_bytes thực sự dùng `os.link` no-clobber, file fsync và directory fsync. Nhận định ban đầu rằng lease acquire có thể ghi đè file lease của assessment khác đã bị loại bỏ sau khi đọc callee; không ghi nó thành finding.
- Overwrite ba report không crash-atomic được tài liệu thừa nhận; generation ID cho phép phát hiện lệch bundle, không giả vờ có transaction toàn bộ.

## 5. Vai trò và liên kết của đủ 39 tài liệu tham chiếu

Danh mục này mô tả mỗi tài liệu tham gia bước nào; không nói rằng phải nạp tất cả ở mọi assessment.

- [criteria-driven-workflow.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/criteria-driven-workflow.md>): thẩm quyền v2 về intake, hai approval, verdict, completion, delegation và reopening. Là nơi ưu tiên khi tài liệu cũ khác nghĩa.
- [assessment-scope-and-completion.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/assessment-scope-and-completion.md>): hợp đồng coverage/round closure cũ và nguyên tắc kỹ thuật; không tự áp whole-track/all-round vào v2.
- [user-security-scope.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/user-security-scope.md>): representation legacy securityScope/questions, historical/current projection, residual và aggregate review. Không phải parser chính sách tùy ý hay schema criteriaWorkflow v2.
- [product-discovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md>): discovery theo criteria, inventory hai chiều feature/API và giới hạn helper chỉ thấy dữ liệu đã khai báo.
- [tester-context.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/tester-context.md>): cách suy luận của tester, prerequisite, observation depth và authority. Chủ yếu là chỉ dẫn cho agent.
- [track-intents.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/track-intents.md>): các câu hỏi gợi ý cho năm track; có rào scope nhưng các câu “every endpoint/role” cần luôn được hiểu trong approved criterion/plan.
- [multi-product-backend.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/multi-product-backend.md>): common CLI/recipe/origin/auth và giới hạn multi-product; không xác nhận arbitrary-product runtime.
- [discovery-origin-selection.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/discovery-origin-selection.md>): giữ aliases và kiểm authorized/bindingVerified candidates, selection/pin drift; không tự chọn production.
- [auth-capability-discovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/auth-capability-discovery.md>): khám phá login/session/role, tách source support và actor runtime observation.
- [be-authenticated.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/be-authenticated.md>): phân biệt client→MCP và ZAP→target auth, browser versus active, guarded executor capability.
- [authenticated-dast-goal.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/authenticated-dast-goal.md>): nhấn mạnh protected API DAST thực sự và continuation; không thay bởi setup/BOLA.
- [be-anonymous-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/be-anonymous-research.md>): anonymous actual DAST và public auth flows; không dùng token trả về để tính anonymous coverage.
- [be-authenticated-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/be-authenticated-research.md>): actors/sessions/vector/pin/readback theo research lane; không hỗ trợ mọi body bằng root schema.
- [bola-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/bola-research.md>): policy/owner/relation/matrix qua ZAP; có câu ALERTS lỗi thời ở F02.
- [fe-anonymous-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/fe-anonymous-research.md>): browser/TLS/broker/native payload semantics, unknown mutations và independent verifier; có admission/runtime cụ thể, không phải generic crawler.
- [fe-authenticated-research.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/fe-authenticated-research.md>): UI login/protected journeys, browser/native identities và bearer-limited research; hook/DB/native admission có điều kiện.
- [native-operation-routing.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/native-operation-routing.md>): chín nhóm import/auth/crawl/active/results/inventory/queue/AF/history; inventory lịch sử không phải tools/list live.
- [runner-routing.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md>): mapping code/entry/compiler/execution/cleanup và conditional support; nêu rõ synthetic adapter không phải plugin runtime tự đăng ký.
- [operation-dispatch.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operation-dispatch.md>): quyết định chọn operation trước runner, work block, compare deployment, diagnose/continue; cần đọc rào v2 đầu trang.
- [responsibility-loop.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/responsibility-loop.md>): reconcile/next-work/continue/report legacy, và primitive có thể tái sử dụng; nói rõ v2 dispatch qua Python coordinator callback.
- [operational-readback.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-readback.md>): required units, evidenceLinks, context compatibility, pending resolution, bounded readiness, result readers và redaction links; helper không là oracle độc lập.
- [operations-and-results.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operations-and-results.md>): ghi operation/đọc đủ/report counts/provenance; cần qualifier v2 rõ hơn như F06.
- [local-remediation-and-continuation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md>): chẩn đoán–sửa prerequisite–verify–tiếp tục, giữ authority/pin/history; không tự sửa product vulnerability.
- [retention-stop-and-recovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md>): checkpoint/private working state, selective resume, no replay và producer supervision; helper inspect-resume vẫn legacy.
- [resource-preflight.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/resource-preflight.md>): đo đúng host/VM/disk/RAM, reserve, remedy theo ownership; không tạo quyền cleanup từ một số “reclaimable”.
- [local-runtime.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/local-runtime.md>): inspect/start/stop đúng cài đặt và exact Compose; không tự rebuild/mở expert/đổi auth để pass.
- [repo-map.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/repo-map.md>): bản đồ scanner checkout/build/test/package/CI có điều kiện; không thay thế xác minh checkout hay attestation runtime.
- [setup.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/setup.md>): cài/copy skill và môi trường dependencies; install không tự configure MCP hay scanner. Không được suy ra quyền sync personal copy từ repo maintenance.
- [product-extension-planning.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-extension-planning.md>): thêm kỹ thuật/fixture theo câu hỏi được giao; không mở rộng scope hoặc mọi combination.
- [auth-lifecycle-and-bola-depth.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/auth-lifecycle-and-bola-depth.md>): expiry/relogin/revoke/deeper owner/race/tenant khi có assignment; có checkpoint source-specific không dùng làm generic support.
- [retest-and-version-comparison.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/retest-and-version-comparison.md>): present/not-reobserved/inconclusive trong retest được giao; preserve findings chưa retest.
- [alert-triage.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/alert-triage.md>): security signal và provenance; owner success/non-owner denial ở RUN, suspected issue có thể là observed alert.
- [zap-result-boundary.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/zap-result-boundary.md>): ranh giới ZAP-derived, alert-only/subset/counting; v2 override và cảnh báo legacy; còn sót “50 current criteria”.
- [product-assessment-handoff.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/product-assessment-handoff.md>): ba JSON, v2 exporter/CLI trước rồi legacy sections; authority rõ hơn các guide cũ.
- [single-table-drive-output.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/single-table-drive-output.md>): một Sheets/run, bảy cột, sync/readback/human edits/evidence link; chưa là implemented exporter và không áp skill-only audit.
- [operational-validation.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md>): acceptance theo khả năng, scenario offline và giới hạn test/runtime; đây là reference áp dụng cho audit này.
- [operational-validation-history.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation-history.md>): các tuyên bố kiểm tra cũ, bao gồm số test và runtime continuation; không attestation v2 hiện tại.
- [operational-knowledge.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/operational-knowledge.md>): lesson có điều kiện và optional legacy bookkeeping helper; không phải authorization hay live run state.
- [knowledge/engine-and-recovery.md](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/knowledge/engine-and-recovery.md>): các pitfall/schema/readback/media/script/GET thực địa theo deployment cũ; chỉ chọn dùng sau khi kiểm applicability.

`agents/openai.yaml` đồng thuận định hướng v2 và nhắc journal/lease/no replay. Default prompt không tự nạp approved plan, khởi tạo adapter, cấp quyền hay bảo đảm Drive output; các phần đó vẫn nằm trong workflow cần agent thực hiện.

## 6. Mô phỏng suy luận tĩnh để thấy các ranh giới

Các tình huống sau là walkthrough trên mô tả/code, **không phải test vừa chạy**.

1. **Yêu cầu “mọi API protected đều chặn non-owner”:** agent phải khám phá đủ API/owner boundary, duyệt oracle/case plan, chọn actor thật, chạy comparison qua ZAP và đọc data/effects. Nếu agent bỏ một API khỏi plan, v2 reviewer không tự phát hiện API đó; đây là discovery trust boundary.
2. **Scan terminal nhưng payload bằng 0:** terminal chỉ đóng operation, không tạo evidence units active. Agent cần kiểm seed/config/fixture để chạy phần thiếu hoặc giữ pending/justified limit; không đổi requiredEvidence để vừa kết quả.
3. **Owner 200, non-owner 403 và readback không đổi:** nếu đủ observation của case, có thể matched/met theo plan; kết quả kiểm soát bình thường vào RUN, không tự thành alert. Đây là đường mà câu cũ BOLA có thể gây nhầm.
4. **Có non-owner access thật nhưng plan all_cases còn case khác:** observation là violated và có thể observed alert; criterion còn pending cho tới disposition đủ case còn lại. Nếu stoppingRule đã duyệt counterexample thì có thể unmet sớm nhưng vẫn xử lý effect/resource state.
5. **Mutation đã chạy, parser đọc receipt lỗi:** không chạy mutation lại. Đọc ACK/native/state đã lưu, sửa parser với captured output, thêm exact resolution và tiếp tục phần readback còn thiếu.
6. **Bộ JSON đủ điều kiện completed nhưng Sheets write lỗi:** security assessment có thể completed, delivery vẫn pending/outdated. Không rerun scan, không tạo URL giả và không nói đã bàn giao đầy đủ.
7. **Worker mất kết nối sau intent:** lease không tự hết hạn; đọc journal/ACK/native state, reconcile đúng action rồi release/reassign. Không tự timed takeover hoặc replay bằng task ID khác.
8. **Audit tĩnh chính skill như nhiệm vụ này:** chỉ đọc nguồn và tạo kết quả audit. Không cần user cấp criteria/plan approval của assessment, không có alert count sản phẩm, không phát minh RUN/ALERTS/SCOPE_ALERTS hay tạo Sheets.

## 7. Thứ tự cải thiện nếu giao sửa ở bước sau

1. Sửa xung đột ALERTS của BOLA và thêm version qualifier cho operations-and-results; đây là việc nhỏ, có căn cứ trực tiếp.
2. Làm rõ ở SKILL mức tự động hóa thực tế, cầu nối executor và trust boundaries; không hứa oracle hay discovery completeness mà code không có.
3. Khớp packet contract với dữ liệu worker thực sự nhận, đặc biệt limitation/fallback/cleanup/criterion context cần thiết.
4. Tách assessment completion và delivery sync state trong handoff; giữ Sheets là projection và xử lý thiếu connector/write riêng.
5. Giảm bối cảnh sản phẩm/cố định số 50 trong reference chung, giữ lịch sử ở history/knowledge có nhãn.
6. Chỉ khi có assignment triển khai cụ thể mới xây adapter v2→executor hoặc exporter Sheets; đánh giá từng deployment/actor/protocol bằng execution được phép, không dùng sửa tài liệu làm chứng minh runtime.

Audit tĩnh này hoàn tất trong phạm vi đã nêu. Chưa có sửa skill, kiểm thử runtime mới hay xác nhận sản phẩm an toàn.
