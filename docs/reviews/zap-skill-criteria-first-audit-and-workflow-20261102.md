# Audit skill MCP ZAP và đề xuất workflow theo tiêu chí chuyên gia

Ngày: 02/11/2026. Đối tượng: bản đang có trên working tree của `.agents/skills/mcp-zap-repo-operations`, gồm thay đổi chưa commit. HEAD nền: `18f17860bad327a18345f949644aac4d40b7fece`; HEAD không đại diện đầy đủ cho nội dung được audit.

Đây là audit tĩnh về thiết kế và khả năng vận hành của skill, kèm workflow đề xuất. Không chạy scan sản phẩm, không xác nhận khả năng runtime đa sản phẩm, không sửa skill hoặc helper. Các kết quả test được ghi trong tài liệu cũ chỉ là lịch sử được tài liệu đó báo cáo; lượt audit này không chạy lại chúng.

## 1. Kết luận chính

Skill có nền tảng tốt về tính trung thực của bằng chứng, quyền thao tác, readback, xử lý mutation không rõ kết quả và phân biệt kiểm thử với sửa lỗi sản phẩm. Nó đã yêu cầu câu hỏi hữu hạn, không coi zero alerts là an toàn, và cho phép hoàn tất câu hỏi khi phát hiện vi phạm. Vì vậy, không nên sửa bằng cách thêm một lớp khẩu hiệu “criteria first” lên các lớp cũ.

Vấn đề trung tâm là **đơn vị điều phối chưa thống nhất**: tiêu chí, question, case, route, feature, track, allocation, work session và assessment round đều tham gia quyết định tiếp tục/hoàn tất. Phần lớn điều kiện riêng lẻ hợp lý, nhưng tổ hợp khó vận hành, dễ mang nghĩa vụ inventory/track cũ vào một nhiệm vụ hẹp. Đồng thời, có khoảng cách rõ giữa contract báo cáo mới với helper đang được chỉ dẫn sử dụng.

Đề xuất một contract mới: **đánh giá tập tiêu chí đã được chuyên gia duyệt, bằng kế hoạch đã được duyệt, để kết luận từng tiêu chí là `met`, `unmet` hoặc `not_evaluable`, trong ranh giới bằng chứng đã thống nhất**. Track là lựa chọn kỹ thuật. Discovery chỉ phục vụ tiêu chí và các phụ thuộc cần thiết. Việc sửa lỗ hổng, qualify scanner và mở rộng catalog không nằm trong mặc định hoàn tất.

`completed` mới có nghĩa hoàn tất việc đánh giá; không có nghĩa sản phẩm đạt mọi tiêu chí. `not_evaluable` được phép là kết quả cuối, nhưng phải qua quy tắc chứng minh giới hạn, không phải nhãn thay cho công việc chưa thực hiện.

## 2. Nguồn và giới hạn kiểm tra

Các nguồn chính đã đọc/đối chiếu:

- [S1 — SKILL.md](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/SKILL.md): đặc biệt các mục Work from the current assessment, Assessment-round closure, Recording and final response, Preserve runtime and history.
- [S2 — User security scope](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/user-security-scope.md): Intake, Prepare and assess, Version 1 questions and closure.
- [S3 — Scope and completion](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/assessment-scope-and-completion.md): Assignment completion, Finite closure conditions, Assessment-round lifecycle.
- [S4 — Recovery](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/retention-stop-and-recovery.md): Working-session checkpoints và End-of-session guidance.
- [S5 — Runner routing](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/runner-routing.md), [multi-product](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/multi-product-backend.md), [product discovery](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/product-discovery.md).
- [S6 — Operational validation](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/operational-validation.md): phân biệt source/offline/runtime/agent behavior và các phần lịch sử qualification.
- [S7 — research_product.py](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/research_product.py): dòng 149–153, 286–299.
- [S8 — product_scope.py](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/product_scope.py): `compact_results`, khoảng dòng 350–470, và `compose_completion_summary`.
- [S9 — round_closure.py](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment/round_closure.py): `reviewUniverse`, quyết định tiếp tục/đóng ở khoảng dòng 275–294.
- [S10 — Agent entry prompt](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/agents/openai.yaml), [dispatch](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/operation-dispatch.md), [local remediation](/Users/hahoangloc/Working/testing%20tool/.agents/skills/mcp-zap-repo-operations/references/local-remediation-and-continuation.md).

Đọc trực tiếp các contract điều phối chính, tìm kiếm có mục tiêu trong references và source, kiểm tra một số nhánh implementation để phân biệt mô tả với khả năng thực tế. Không audit từng dòng của toàn bộ thư viện, không kiểm chứng đầy đủ mọi adapter/schema/test. Không có lịch sử tool calls của các lần vận hành trước để đo tần suất agent thật sự yêu cầu đổi window hoặc hỏi lại approval.

## 3. Audit các nhận xét ban đầu

### A1. “Chưa đảm bảo nhiều loại product; còn hardcode” — đúng một phần, cần tách ba lớp

**Bằng chứng:** S1 tuyên bố portable/product-independent; S5 đồng thời nói registry `finalsource-ledger/archive-control` không phải arbitrary-product support. S7 vẫn có CA tại `finalsource/.local-tls/localhost.crt`, origin fallback `https://localhost:8080`, profile mặc định `http://backend:3000`, `/api/auth/login`, `/api/v1/accounts`, token pointer `/data/accessToken`. Nhánh `native_profile` có thể thay profile khi có discovery, nên không thể kết luận mọi lần chạy đều bắt buộc dùng các giá trị này.

Ba lớp cần phân biệt:

1. **Policy chung:** đã yêu cầu không mang route/role của sản phẩm khác vào. Đây là điểm đúng.
2. **Ví dụ/lịch sử sản phẩm:** pin, spotlight, media, recording, JOIN xuất hiện trong references. Có chỗ ghi rõ chỉ là ví dụ. Đây là tải ngữ cảnh và nguy cơ anchoring, chưa tự nó chứng minh lỗi hardcode runtime.
3. **Runner chuyên biệt:** có coupling thực sự với sản phẩm, auth, CA, deployment và recipe. Phải được chọn theo điều kiện tương thích, không coi là executor mặc định cho mọi sản phẩm.

**Ảnh hưởng:** người vận hành có thể hiểu “skill portable” thành “executor đã hỗ trợ sản phẩm này”. Product mới có thể cần mapping/adapter dù instruction cấp cao đúng.

**Ưu tiên:** cao. Tách rõ core, adapter và historical qualification; capability phải được xác nhận cho tổ hợp protocol/auth/request/readback cần dùng. Không yêu cầu mọi runner phải generic, cũng không xóa pin/port của fixture chỉ vì nó là literal.

### A2. “Chưa đặt tiêu chí hoàn thiện trước” — không đúng hoàn toàn với bản hiện tại

**Bằng chứng phản biện:** S1 đã ghi `charter → feature/API map → finite security questions → capability mapping`; yêu cầu “Define finite closure conditions before choosing techniques”. S2 giữ nguyên yêu cầu gốc và tách interpretation. S3 yêu cầu sufficient observations từ intake.

**Khoảng trống thực sự:** chưa có hai artifact được chuyên gia duyệt và khóa revision là **criteria specification** và **test plan**. S1/S3 còn nói không cần routine charter approval. Trình tự feature/API map trước câu hỏi hữu hạn có thể làm discovery quá rộng nếu chưa chốt tập tiêu chí cần đánh giá. Đây là lựa chọn workflow hiện tại, không phải việc agent quên tuân thủ một gate vốn đã tồn tại.

**Đề xuất:** raw criteria → discovery tối thiểu → criteria draft/approval → discovery có mục tiêu + plan/approval → execute. Tiêu chí phải được hiểu trên nền tảng sản phẩm; không chốt oracle kỹ thuật khi chưa biết hệ thống vận hành thế nào.

### A3. “Acceptance completed quá rộng” — đúng về độ phức tạp và trọng tâm, không phải luôn buộc test toàn sản phẩm

**Bằng chứng phản biện:** S2 đã nói narrow feature scope không mở whole-product BE/FE/BOLA; S3 không yêu cầu sửa mọi finding; S1 cho phép answered subset đóng chính subset đó.

**Vấn đề:** S1/S3/S9 còn phối hợp whole-round universe, inventory, residual, aggregate, route/feature obligations và trạng thái legacy. S8 xem track inventory được cung cấp là assigned work và có thể giữ task partial dù criteria projection đã complete. Do đó, việc đưa một inventory rộng vào pipeline có hậu quả về completion; cần phân biệt dữ liệu discovery với nghĩa vụ được giao.

`completed-with-limitations`, `taskCompletion:partial`, `roundClosed`, `handoffClosesTask:false` có thể đồng thời hợp lệ theo thiết kế cũ. Điều này trung thực nhưng khó đọc và khó điều phối cho mục tiêu mới.

**Ưu tiên:** cao. Chuyển completion sang tập criteria/plan được duyệt; không thêm một nhãn mới mà vẫn để toàn bộ closure engine cũ phủ quyết âm thầm. Giữ resource/effect accounting như invariant vận hành, không biến thành một chương trình assurance bổ sung.

### A4. “Còn nhiều thao tác thủ công và đổi window không cần thiết” — có khoảng trống kiến trúc, chưa chứng minh tần suất hành vi

**Bằng chứng phản biện:** S4 đã cấm handoff chỉ vì đổi fixture/vector/role hoặc kết thúc block. S10 yêu cầu tiếp tục mà không hỏi lại cho từng subset. Vì vậy không nên viết thêm cùng quy tắc rồi tuyên bố đã giải quyết.

**Khoảng trống:** khi handoff thực sự xảy ra, S4 vẫn dựa vào người dùng copy prompt và mở chat khi được khuyến nghị. S1 cuối file còn cấm tự spawn subagents. Không có contract task packet/result packet, cơ chế ownership/lease, hoặc quyền kết luận giữa parent và worker. Yêu cầu sub-agent vì vậy cần thay đổi policy và orchestration, không chỉ thay từ “window” bằng “sub-agent”.

**Giới hạn kết luận:** tài liệu không đủ để chứng minh agent thường xuyên hỏi lại hoặc đổi window sai. Cần transcript quan sát cho kết luận hành vi. Lượt này chỉ xác nhận mô hình recovery chưa cung cấp cơ chế delegation theo yêu cầu mới.

### A5. “Mô tả có dễ vận hành, phân chia, điều phối không?” — mạnh về invariants, yếu về đường đi mặc định

**Điểm tốt:** phân biệt native alert/observed issue; không lấy status code, exit 0 hoặc labels làm bằng chứng; đọc effect trước replay; giữ scope và lịch sử; phát hiện lỗi không buộc sửa sản phẩm. Đây là nền tảng nên giữ.

**Điểm yếu:** cùng một quyết định tiếp tục/đóng được mô tả ở SKILL, scope/completion, security scope, dispatch, responsibility loop, recovery, prompt entry và helper. SKILL cùng references cấp một có tổng 2.033 dòng tại thời điểm kiểm tra; số dòng không tự chứng minh chất lượng kém, nhưng việc phân tán owner của quyết định làm tăng tải đọc. Tài liệu validation còn trộn hướng dẫn chung với nhật ký qualification của sản phẩm cụ thể.

**Đề xuất:** một state machine chuẩn và một nguồn định nghĩa completion/verdict. Các tài liệu khác chỉ tham chiếu. Một worker chỉ đọc contract chung ngắn, packet và reference của executor được chọn.

### A6. Lệch contract đầu ra và implementation — vấn đề cụ thể cần sửa trước khi gọi là tự động

**Bằng chứng:** S1 yêu cầu `SCOPE_ALERTS` là danh sách alert mapped, đồng thời thừa nhận generic reporting helpers vẫn xuất mixed-record/criterion-first. S5 vẫn chỉ đến `product_scope.compact_results/scope report` để có ba file. S8 tạo `projection` theo criteria, rồi `compact_scope=compact(projection)`.

**Ảnh hưởng:** theo đúng một hướng dẫn có thể vẫn nhận đầu ra không đúng contract khác. Agent phải tự bù mapping/trình bày; tạo thêm cơ hội đếm sai hoặc mô tả sai trạng thái.

**Ưu tiên:** cao. Làm một exporter thực thi contract, có kiểm tra mapping và provenance. Criteria verdict thuộc RUN; SCOPE_ALERTS không bị biến trở lại thành bảng tiêu chí. Không thay đổi lịch sử hoặc tuyên bố helper cũ đã được migrate.

## 4. Contract workflow đề xuất

### 4.1 Mục tiêu và ranh giới

Đầu vào nghiệp vụ: sản phẩm/environment được phép đánh giá và tiêu chí raw của chuyên gia. Đầu ra: kết luận có căn cứ cho **từng tiêu chí trong revision đã duyệt**, kèm các kiểm thử thực hiện, bằng chứng, giới hạn và alert liên quan.

Discovery có thể đọc thành phần phụ thuộc ngoài feature được nêu để hiểu đường xử lý, nhưng không tự mở active testing ở target/feature đó. Mọi test thực thi phải truy về criterion ID hoặc prerequisite cụ thể của test đã duyệt. Finding ngoài tiêu chí tình cờ thấy trong traffic hợp lệ được ghi nhận, không tự mở campaign mới.

Nếu raw requirement là “mọi API”, inventory của mọi API trong ranh giới đã giao vẫn cần được đối chiếu. Không lấy “criteria first” làm lý do test một endpoint đại diện rồi kết luận cho toàn bộ.

### 4.2 Ba điểm tương tác chính với chuyên gia

1. **Input gate — chuyên gia cung cấp raw criteria:** có thể là văn bản ngắn, file, policy hoặc phần được chọn từ catalog. Đây là cung cấp ý định, không phải bắt người dùng viết JSON/actor matrix. Nếu đã cung cấp thì tái sử dụng, không hỏi lại.
2. **Criteria approval — chuyên gia duyệt bản agent chuẩn hóa:** duyệt nội dung, phạm vi, oracle, các giả định và tiêu chí chưa thể đánh giá. Lưu nguồn xác nhận gắn với revision cụ thể.
3. **Plan approval — chuyên gia duyệt kế hoạch thực thi:** duyệt test cases, target/environment, actors, tác động, phạm vi chuẩn bị/khôi phục và cách xử lý giới hạn. Sau đó agent tự chạy các bước nằm trong kế hoạch.

Không xin duyệt theo mỗi case, actor, fixture, allocation, token refresh, readback hoặc kết thúc block khi chúng đã nằm trong quyền được duyệt. Approval có sẵn trong session vẫn có hiệu lực đúng phạm vi.

Ba điểm này là đường đi thông thường, không phải lời hứa tuyệt đối không bao giờ cần hỏi thêm. Thay đổi material về tiêu chí/oracle, target, mutation impact, quyền truy cập hoặc phạm vi là **revision quay lại gate tương ứng**, không phải tạo thêm một gate tùy hứng. Thiếu bí mật/điều kiện môi trường có thể cần input; không gọi việc xin dữ liệu đó là approval. Trong lúc chờ, tiếp tục các nhánh độc lập đã có quyền.

### 4.3 Phân biệt kết quả và tiến độ

**Trạng thái công việc:** `draft`, `awaiting_criteria_approval`, `planning`, `awaiting_plan_approval`, `executing`, `waiting_dependency`, `completed`, `stopped_by_user`. Checkpoint là dữ liệu phục hồi trong trạng thái hiện tại, không bắt buộc là kết thúc chat hoặc một kết quả kiểm thử.

**Kết quả criterion:** chỉ xuất `met | unmet | not_evaluable` khi có quyết định cuối. Khi còn đang thực hiện, verdict để trống; không ép case chưa chạy thành `not_evaluable`.

- `met`: mọi nghĩa vụ bằng chứng cần để thỏa tiêu chí trong plan đã có, đúng context và phù hợp oracle. Phải trình bày phạm vi kết luận; “không tìm thấy SQLi trong các test đã duyệt” không chứng minh “mọi query dùng parameter binding”.
- `unmet`: có bằng chứng đủ để vi phạm oracle đã duyệt. Với yêu cầu phổ quát, một phản ví dụ hợp lệ có thể đủ; có dừng các test còn lại hay không theo stopping rule đã duyệt. Nếu plan yêu cầu đánh giá mọi route hoặc đo mức độ ảnh hưởng thì phải tiếp tục phần đó.
- `not_evaluable`: không đủ cơ sở kết luận trong phương pháp/quyền/điều kiện đã duyệt, sau khi xử lý các prerequisite hợp lý còn khả thi. Ghi reason code, phần đã biết/chưa biết, phương án đã thử hoặc loại trừ, ảnh hưởng và điều kiện mở lại.

`not_applicable` là thuộc tính applicability, không phải bằng chứng pass. Để giữ đúng ba verdict, tiêu chí không áp dụng được giữ với `verdict:not_evaluable`, `reason:not_applicable`, product basis riêng, đếm tách với thiếu quyền/capability. Chuyên gia duyệt semantics này ở criteria gate. Tiêu chí bị chuyên gia loại khỏi phạm vi ở revision mới được giữ trong lịch sử với disposition excluded, không còn trong mẫu số active; agent không tự loại.

Không có phép ánh xạ cơ học `legacy partial → not_evaluable`, `observed → met` hoặc `zero alerts → met`.

## 5. Quy trình chi tiết

### Bước 0 — Tiếp nhận ý định và lưu nguyên văn

Coordinator lưu nguồn tiêu chí raw, product/environment được chỉ định và authority hiện có. Nếu chỉ có yêu cầu chung, giúp soạn lựa chọn tiêu chí để chuyên gia quyết định; không tự lấy toàn bộ catalog làm assignment. Không yêu cầu chuẩn bị endpoint matrix, actor matrix, runner arguments.

**Đầu ra:** raw source và phạm vi ban đầu; danh sách câu hỏi thật sự ảnh hưởng ý định/authority. Chỉ bước phụ thuộc câu trả lời mới chờ.

### Bước 1 — Discovery tối thiểu và draft tiêu chí

Đọc spec/source/config hoặc observations sẵn có để hiểu thành phần, protocol, auth, trust boundaries, object ownership và dữ liệu cần thiết cho raw criteria. Gắn nguồn cho từng fact; phân biệt fact, assumption, unknown. Không chạy active scan để “khám phá tất cả”. Traffic discovery mới chỉ thực hiện nếu quyền hiện có cho phép, nếu chưa có thì để trong kế hoạch.

Mỗi tiêu chí có: stable ID; raw text/source; normalized requirement; feature/environment boundary; oracle và nguồn; applicability; sufficient evidence; điều kiện `met/unmet/not_evaluable`; giới hạn suy rộng; vấn đề cần chuyên gia quyết định. Tiêu chí ghép có thể tách thành các câu hỏi con nhưng giữ nguyên cha và logic kết hợp.

Ví dụ: “A không đọc được tài liệu riêng của B” phải làm rõ loại tài liệu, quyền chia sẻ và role thực tế. Không tự áp dụng owner model nếu sản phẩm dùng public/shared resources.

**Exit:** gửi bản criteria có thể review. Chờ approval cho revision; chỉ tiếp tục discovery read-only độc lập trong khi chờ. Không coi im lặng hoặc thời gian chờ là đồng ý.

### Bước 2 — Lập kế hoạch dựa trên nền tảng sản phẩm

Từ criteria đã duyệt, tìm inventory tối thiểu đủ và những dependency có liên quan. Với từng nghĩa vụ, chọn kỹ thuật và executor dựa trên khả năng hiện tại: tool schema, auth/session support, request body/protocol, fixture, observation/readback. Ghi mức xác minh `source-reviewed`, `offline-checked`, `runtime-observed`; không đánh đồng chúng.

Mỗi test case phải có:

- `caseId`, criterion/question links, objective và evidence obligation được phục vụ.
- Target/build/environment; API operation hoặc UI journey cụ thể; actor/role/object/state; fixture prerequisites.
- Expected result và oracle; baseline/positive/negative controls cần thiết; observation/readback đủ để kết luận.
- Executor/technique và lý do chọn; giới hạn khả năng; provenance qua ZAP nếu claim là ZAP-derived.
- Mutations, cleanup/retention, auth refresh, khả năng rollback/containment; quyền đã có.
- Dependency, scanner/session/resource cần dùng, điều kiện retry an toàn, stopping rule, deadline/rate/budget khi cần kiểm soát tác động.
- Fallback được phép và terminal reason dự kiến nếu phương pháp không đánh giá được.

Không áp ma trận Cartesian criterion × route × role × payload. Grouping chỉ hợp lệ nếu chung security boundary và oracle, với excluded conclusions rõ. Nếu tiêu chí yêu cầu đủ mọi route/role thì plan vẫn phải giữ đủ nghĩa vụ đó.

Giới hạn request/time của executor chia công việc thành allocation; hết allocation không tự hoàn tất assessment. Budget do người dùng duyệt có thể khiến kết quả `not_evaluable:budget_exhausted` nếu policy đã chấp nhận; không tự đặt quota để dừng sớm.

**Exit:** plan revision được chuyên gia duyệt, gồm quyền delegation trong cùng assessment và tác động cho phép. Capability gap được trình bày trước, không che đi để plan trông khả thi.

### Bước 3 — Chuẩn bị execution và giao việc

Coordinator xác nhận runtime binding trước traffic; kiểm tra các actor/fixture cần ngay lúc này. Tạo task packet cho work unit có mục tiêu hữu hạn, không chia máy móc theo mỗi endpoint hoặc toàn bộ một track. Chuẩn bị chỉ những fixture cần cho nhóm test sắp chạy.

Một agent có thể tự làm work unit đơn giản. Dùng sub-agent khi có lợi về context hoặc có nhánh độc lập rõ ràng. Mô hình không bắt buộc spawn worker cho từng case.

**Exit:** worker nhận packet đúng revision; quyền, prerequisites, resource ownership và đường ghi kết quả rõ ràng. Nếu thiếu executor phù hợp, coordinator chọn fallback đã duyệt hoặc giữ nhánh chờ với bước chuẩn bị cụ thể.

### Bước 4 — Execute → readback → reconcile liên tục

Vòng lặp của mỗi work unit:

1. Kiểm tra current plan revision, target, auth, fixture và quyền resource cần dùng; không đọc lại toàn bộ tài liệu.
2. Ghi durable intent trước effect, thực hiện một lần, lưu ID/ACK hoặc unknown outcome.
3. Đọc result đúng actor/object/build và observation stage. ACK/HTTP 202 không thay terminal processing nếu criterion cần processing.
4. Khi lỗi: phân loại transport/auth/fixture/executor/product behavior; ưu tiên đọc kết quả đã có trước retry. Không sửa product để có kết quả pass.
5. Khi prerequisite có thể sửa trong phạm vi: sửa tối thiểu, kiểm tra boundary vừa sửa, rồi tiếp tục. Không biến một thiếu adapter thành dự án phát triển framework vô hạn.
6. Trả observations, evidence refs, đề xuất verdict, pending effects và next action. Coordinator kiểm tra và merge.
7. Chọn nhánh hữu ích tiếp theo; lưu checkpoint tự động mà không yêu cầu người dùng “continue”.

Nếu mất ACK, worker chỉ được readback/reconcile; không replay mutation theo timeout. Nếu token hết hạn, chỉ các observation không chứng minh được session hợp lệ bị ảnh hưởng; không tự phủ nhận toàn bộ kết quả trước đó.

### Bước 5 — Quyết định verdict và xử lý giới hạn

Coordinator đối chiếu bằng chứng với oracle đã duyệt, không với câu tóm tắt của worker. Kiểm tra identity/context/provenance, đủ units, positive controls khi cần và mọi nghĩa vụ trong plan. Khi evidence mâu thuẫn, giữ verdict pending và chọn readback/test phân biệt trong phạm vi; không bỏ phiếu theo số worker.

Với tiêu chí ghép, áp logic đã duyệt. Nếu yêu cầu là conjunction, một nhánh vi phạm đủ làm criterion `unmet`; các nhánh còn lại chưa đánh giá vẫn phải hiện rõ. Nếu yêu cầu là đo toàn bộ coverage, phần việc còn lại chỉ được bỏ khi stopping rule cho phép.

Muốn kết luận `not_evaluable`, phải trả lời đủ:

1. Chính xác evidence nào còn thiếu và tại sao nó cần cho oracle?
2. Đã thử những bước nào; bước nào bị loại và có căn cứ gì?
3. Có readback, fixture repair, auth renewal hoặc fallback đã duyệt nào vẫn khả thi không? Nếu có, tiếp tục.
4. Giới hạn là method, access, policy, capability, environment, budget hay applicability? Không gọi missing handler là external blocker nếu còn sửa tối thiểu được trong plan.
5. Điều kiện cụ thể nào cho phép mở lại? Không dùng “cần test thêm” làm lý do.

Nếu sửa adapter vượt quyền/chi phí đã duyệt, giữ dependency hoặc terminal limitation theo plan; không xin mở rộng chỉ để làm mọi criterion thành evaluable. Có thể hoàn tất assessment với tiêu chí ngoài ZAP là `not_evaluable:method_boundary`, không tự mở Semgrep hoặc source audit khác.

### Bước 6 — Đóng assessment và báo cáo

`assessmentStatus:completed` chỉ khi:

- Mọi criterion active trong criteria revision đã duyệt có verdict cuối hợp lệ và basis.
- Mọi plan obligation được hoàn tất hoặc có disposition theo stopping/limitation rule đã duyệt; không còn công việc khả thi cần thiết bị bỏ chỉ vì đã có nhãn verdict.
- Không có scope/oracle revision ngầm, evidence conflict chưa xử lý, hoặc criterion bị mất khỏi mẫu số.
- Pending effects/resources được reconcile hoặc có containment thực tế và hạn chế ghi rõ; không còn producer không được kiểm soát. Không yêu cầu xóa mọi fixture nếu retention được phép.
- Báo cáo phản ánh đúng revision và nguồn kết quả, không dùng record lịch sử như current credit.

Có `unmet` hoặc `not_evaluable` vẫn có thể completed. Nếu người dùng dừng trước khi đủ disposition, trạng thái là stopped_by_user và các verdict chưa biết vẫn pending; không lấp chúng bằng `not_evaluable` để làm đẹp tỷ lệ hoàn tất.

Mở lại khi một điều kiện cụ thể thay đổi: build, scope/oracle, actor, capability hoặc fixture giải quyết đúng limitation. Không quét lại chỉ vì catalog còn tiêu chí chưa đạt hoặc finding chưa được sửa.

## 6. Contract sub-agent với context tối thiểu

Đây là thiết kế đề xuất, chưa có trong skill hiện tại. Lượt audit này không cần spawn worker để thay đổi session vận hành hay chạy sản phẩm.

### Vai trò

- **Coordinator:** giữ criteria/plan approvals, registry work units, quyền scope, tài nguyên và bản RUN chính. Có quyền ra verdict sau khi review evidence, không tự thay oracle.
- **Discovery/planning worker:** đọc nguồn được giao, trả facts/candidates và uncertainties; không scan hoặc tự phê duyệt criterion.
- **Execution worker:** chỉ thực hiện work unit trong packet; ghi journal và evidence của mình, không finalize assessment hoặc ghi đè report chính.
- **Readback/review worker:** có thể đọc kết quả độc lập hoặc kết quả phức tạp; là tùy chọn, không biến thành approval gate mỗi lần test.

### Task packet tối thiểu

```yaml
taskId: W-014
assessmentId: A-001
criteriaRevision: C-2
planRevision: P-3
criterionIds: [C-04]
caseIds: [T-04-1, T-04-2]
objective: Evaluate the approved cross-owner read rule
oracleRef: private-plan-reference-to-C-04
requiredEvidence: [owner-control, other-owner-result, bound-object-identity]
productFactsRef: selected-facts-for-this-work-unit
authorityRef: approved-plan-scope-and-effects
executorRef: selected-executor-contract
resourceLeaseRef: coordinator-owned-lease
workingStateRef: current-fixtures-and-operation-journal
pendingEffectsRef: relevant-pending-effects-only
secretRefs: [private-actor-session-reference]
allowedActions: [read-current-state, run-approved-cases]
forbiddenActions: [expand-scope, replay-unknown-mutation, finalize-assessment]
returnTo: coordinator
```

Packet là dữ liệu, không phải quyền mới. Không chứa token, password, full transcript, toàn bộ catalog hay raw logs không liên quan. Worker nhận context mới (`fork_turns:none` khi công cụ hỗ trợ); đọc những reference được chỉ định và instruction áp dụng. Context sạch không có nghĩa bỏ qua invariant an toàn hoặc trạng thái shared resource.

### Result packet tối thiểu

Trả `taskId/revisions`, trạng thái execution, actual operations và ACK IDs, evidence refs có context, observation đạt/chưa đạt, proposed verdict + rationale, blocker/preparation, mutation/resource disposition và exact next action. Không chỉ trả “pass” hay một đoạn summary.

Coordinator đối chiếu revisions trước merge. Kết quả từ revision cũ được giữ historical hoặc reuse có lý do tương thích; không tự cấp current credit. Một canonical writer cập nhật RUN; worker không cùng ghi vào file đó.

### Quy tắc concurrency và phục hồi

Shared scanner/session hoặc fixture có thể ảnh hưởng nhau phải thực thi tuần tự. Chỉ chạy song song khi target objects, sessions, attribution và resources thật sự độc lập; lease phải được kiểm tra tại dispatch, không chỉ là lời hứa trong prompt. Read-only discovery có thể chạy độc lập.

Worker chết hoặc mất phản hồi không chứng minh operation đã dừng. Thu hồi quyền dispatch mới, đọc journal/ACK/native state, rồi mới cấp lease cho worker tiếp theo. Đổi worker không cấp quyền replay. Worker không tự giao việc xuống nhiều tầng nếu coordinator chưa cấp quyền đó.

Coordinator giữ compact state và giao work unit kế tiếp cho worker mới khi có lợi; người dùng không phải copy context. Nếu công cụ không hỗ trợ sub-agent hoặc không có isolation cần thiết, coordinator thực hiện tuần tự với cùng packet. Chỉ khuyến nghị chat mới khi có khó khăn context/host cụ thể mà checkpoint và selective loading không giải quyết được; không hứa có thể tự kéo dài session vô hạn.

## 7. Đầu ra và dữ liệu tối thiểu

Giữ ba file handoff hiện có để tránh thêm gánh nặng cho người dùng:

- **RUN.json:** raw criteria/source refs, approved criteria và plan revisions, approval refs, criterion verdicts/basis, actual operations, observations/evidence refs, limitations, resource/effect state và continuation khi cần.
- **ALERTS.json:** native alerts và tester-observed security issues, provenance và grouping rõ. `not_evaluable` tự nó không phải alert.
- **SCOPE_ALERTS.json:** chỉ alert có mapping hợp lệ đến tiêu chí trong scope, giữ rationale; không phải bản sao bảng criteria.

Journal/worker packets/private secrets là working state nội bộ theo nhu cầu; không buộc thêm deliverable hay bắt user thao tác chúng. RUN có thể tham chiếu working state thay vì chép raw logs hoặc secrets.

Kết quả người dùng thấy mở đầu bằng: assessment đã hoàn tất hay chưa; bao nhiêu criteria `met/unmet/not_evaluable/pending`; từng criterion có kết luận và căn cứ gì. Alert counts là thông tin hỗ trợ, không phải mẫu số completion. Không đưa “safety percentage” từ tỷ lệ met.

Ví dụ schema logic mới, chưa phải schema được CLI hiện tại hỗ trợ:

```json
{
  "workflowVersion": 2,
  "assessmentStatus": "completed",
  "criteriaRevision": "C-2",
  "planRevision": "P-3",
  "criterionResults": [
    {"criterionId":"C-01","verdict":"met","evidenceRefs":["read-01"],"basis":"All approved observation duties satisfied"},
    {"criterionId":"C-02","verdict":"unmet","evidenceRefs":["read-02"],"basis":"Approved oracle contradicted by the bound-object read"},
    {"criterionId":"C-03","verdict":"not_evaluable","reason":"method_boundary","basis":"Approved dynamic method cannot establish the required source property","reopenCondition":"Expert assigns an appropriate source-review method"}
  ]
}
```

Mẫu chỉ minh họa logic verdict; chưa đủ fields để dispatch hoặc chứng minh completion. Evidence refs/basis phải trỏ tới dữ liệu thật, approval revisions phải truy xuất được. Không cho helper hiện tại đọc mẫu này như một workflow đã được triển khai.

## 8. Chỉnh sửa skill và implementation theo thứ tự

### Giai đoạn 1 — Chốt semantics, chưa đụng executor

Viết một contract `criteria-driven-workflow` làm nguồn duy nhất cho scope, approvals, verdict và completion. Chốt cách xử lý N/A, criterion ghép, stop-on-counterexample và terminal limitations. Sửa SKILL + agent prompt đồng bộ: đường đi mặc định ngắn, track chỉ là kỹ thuật, không tự mở full-track assignment từ discovery inventory.

Thay câu cấm blanket subagent bằng delegation trong plan đã duyệt, packet tối thiểu và resource ownership. Giữ cấm tự tạo chat, tự cấp authority hoặc nhắn người khác ngoài phạm vi.

**Acceptance:** walkthrough hẹp không mở full product; vi phạm không buộc sửa; pending không biến thành not_evaluable; criteria và plan có revision/approval có thể review.

### Giai đoạn 2 — Tách adapter và capability facts

Đưa product-named runbooks, setup/auth/readback/cleanup assumptions vào adapter/reference riêng. Core chỉ mô tả interface và cách chọn. Discovery schema ghi protocol/auth/object/state/oracle; capability registry phân biệt supported, conditional, unavailable cùng verification basis. Không hứa hỗ trợ mọi sản phẩm hay mọi protocol.

Di chuyển nhật ký qualification trong operational-validation sang lịch sử riêng; phần hướng dẫn chung giữ link khi cần. Không xóa các giới hạn hoặc bằng chứng lịch sử.

**Acceptance:** product không khớp adapter không bị gán origin/role/route mặc định; cookie/SSO hoặc protocol chưa hỗ trợ được báo đúng, không ép thành bearer/REST.

### Giai đoạn 3 — Runtime state và coordinator

Thêm cấu trúc plan revisions, work packets/results, assignment ownership và resource leases vào working state hiện có hoặc module nhỏ có boundary rõ. Ưu tiên nối lại auth/journal/readback/cleanup primitives, không viết lại scanner. Chỉ coordinator cập nhật kết quả canonical. Approval refs được kiểm tra với actual scope, không tin trường `approved:true` do worker tự khai.

Tách discovered inventory khỏi assigned obligations trong reconciliation. Có criterion map thì obligation được nhận vào từ approved plan; inventory hỗ trợ không tự trở thành nhiệm vụ. Giao broad track vẫn giữ đầy đủ nghĩa vụ broad track đã duyệt.

**Acceptance:** worker stale/dead không replay; shared scanner không chạy xung đột; independent branch tiếp tục khi một dependency bị thiếu; context packet không chứa secrets/full transcript.

### Giai đoạn 4 — Verdict engine và exporter

Triển khai ba verdict với bằng chứng và limitation validation. Engine kiểm tra structural consistency và references; vẫn cần agent hiểu semantics/oracle, không giả vờ validator tự hiểu mọi security property. Sửa exporter theo RUN/ALERTS/SCOPE_ALERTS mới, thay hướng dẫn gọi helper legacy không tương thích.

Thêm version mới thay vì đổi nghĩa `taskCompletion`/`completed` của hồ sơ cũ. Các run cũ đọc với semantics cũ; assessment mới dùng contract mới. Muốn tiếp tục run cũ theo contract mới phải dựng criteria/plan revision rõ và duyệt phần thay đổi; không cần yêu cầu lại quyền đã có nếu không đổi phạm vi. Không repin hoặc sửa lịch sử.

**Acceptance:** completed có not_evaluable được trình bày rõ; pending và resources uncontained chặn closure; report counts và criterion mapping nhất quán; exporter không tạo criteria-first SCOPE_ALERTS.

## 9. Kiểm chứng workflow sau khi triển khai

Không dùng kiểm tra khớp câu chữ làm bằng chứng agent vận hành đúng. Có thể bắt đầu bằng scenario/offline tests rồi kiểm chứng một số phiên agent được cấp quyền:

1. **REST/bearer, một feature:** raw chỉ chọn owner-read; inventory có nhiều API khác. Kỳ vọng chỉ chạy case liên quan và prerequisite; không mở SQLi/full authenticated track mặc định.
2. **Web session-cookie/SSO:** không dùng profile bearer của sản phẩm mẫu. Nếu executor không hỗ trợ, thể hiện capability gap đúng, thử fallback đã duyệt hoặc not_evaluable có căn cứ.
3. **GraphQL/RPC:** hai operation chung URL vẫn giữ nghĩa vụ khác nhau khi boundary khác; một URL được scan không tự đóng mọi operation.
4. **Async/job/stream:** ACK không đủ nếu oracle cần terminal delivery; reader lỗi phải dùng retained result trước khi tạo job mới.
5. **Sản phẩm không có source:** đánh giá phần black-box được giao; không block toàn bộ chỉ vì thiếu source, cũng không kết luận source property từ zero alerts.
6. **Vi phạm rõ:** kết luận unmet, dừng theo stopping rule; không tự sửa sản phẩm hay xin approval cho từng next case còn được giao.
7. **Fixture hỏng nhưng sửa được:** tiếp tục preparation, không not_evaluable sớm. Nếu sửa vượt quyền đã duyệt, giữ giới hạn cụ thể.
8. **Worker mất sau mutation:** reconcile ACK/effect trước thay worker; không chạy lần hai. Shared scanner chỉ có một writer/dispatcher được cấp lease.
9. **Scope drift:** phát hiện feature mới ngoài criteria chỉ ghi candidate. Oracle/target thay đổi cần revision; cùng target và kỹ thuật fallback đã duyệt không hỏi lại.
10. **Completion và reporting:** criteria có met/unmet/not_evaluable nhưng không pending, mọi disposition hợp lệ và resources controlled → completed; missing evidence, stale approval hoặc uncontained producer → chưa completed.
11. **N/A và điều kiện dừng:** product fact chứng minh không áp dụng được đếm riêng; user stop giữa chừng giữ pending, không biến thành “đã đánh giá hết”.
12. **Run cũ và contract mới:** giữ nguyên lịch sử, không chuyển partial thành not_evaluable hoặc đổi finding count thành alert count mà thiếu mapping.

Các case offline chứng minh semantics/contract được mô phỏng, không chứng minh mọi product được hỗ trợ. Với phiên vận hành thật, đo: số câu hỏi approval ngoài hai approval gate và lý do; số lần yêu cầu đổi chat; test nào không truy được approved criterion; verdict thiếu evidence; retry mutation khi unknown; khả năng tiếp tục nhánh độc lập. Muốn kết luận workflow vận hành tốt phải đọc trace quyết định, không chỉ đếm test passed.

## 10. Quyết định thiết kế được khuyến nghị

Nên giữ hệ thống bằng chứng và recovery hiện có, nhưng thay tầng điều phối bằng một workflow theo criteria/plan revision đã duyệt. Không thu hẹp bằng cách bỏ unknown-effect checks hoặc tự coi mọi blocked item đã hoàn tất. Thu hẹp bằng cách xác định đúng nhiệm vụ từ đầu và không biến discovery, track templates, adapter gaps hay catalog chưa được chọn thành assignment mới.

Ưu tiên sửa ba điểm trước: **một định nghĩa completion duy nhất**, **hai approval artifact rõ ràng**, và **exporter khớp contract**. Sau đó thêm delegation có task/result packet và resource ownership. Chỉ thêm sub-agent trước khi giải quyết ba điểm đó sẽ phân tán sự mơ hồ sang nhiều context thay vì giảm nó.

Audit và bản đề xuất này đã hoàn tất ở phạm vi tài liệu/source đã nêu. Workflow mới chưa được triển khai hoặc kiểm chứng runtime; không có kết luận sản phẩm nào đạt/không đạt tiêu chí bảo mật từ lượt audit này.
