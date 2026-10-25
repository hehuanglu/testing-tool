# Bộ điều phối nghiệp vụ của skill

Đây là **quy trình quyết định và thực thi do agent điều khiển**, đã được nối từ SKILL.md; không phải một binary tự scan toàn product. Dùng operations và executor thật ở [catalog](native-operation-routing.md) và [runner mapping](runner-routing.md). Agent phải hoàn thành từng bước được giao, không chỉ trả kế hoạch. Helper `inspect_operations.py` chỉ rà source/registration và drift của catalog, không dispatch traffic.

## A. Chốt điều cần làm trước khi chọn executor

Đọc [tester context](tester-context.md) và track được giao trong [track intents](track-intents.md). Xác định assessment hay chỉ status/setup/audit/skill edit. Status/audit không tự scan; BE không tự kéo FE/BOLA; generic “authenticated” cần xác định FE/BE từ yêu cầu/context, không đoán khi khác biệt này quyết định UI work.

Giữ một ngữ cảnh công việc gọn trong plan/RUN sẵn có, không bắt schema mới: product + environment + origins, track/scope, inventory độc lập, roles/actors/fixtures cần thiết, trách nhiệm đang mở, thao tác đang chạy/unknown và kết quả đã đọc. Không lấy recipe/tên folder/report cũ làm nguồn quyền hoặc discovery product mới.

Một đơn vị trách nhiệm là câu hỏi cần trả lời cho endpoint/role/input hoặc UI journey/state; BOLA thêm object/action/relation. Nó có prerequisite và tiêu chí quan sát. Một allocation chỉ là lượt thực hiện một phần các đơn vị, không thay inventory đầy đủ. Nếu chưa đủ dữ liệu lập inventory, ghi discovery incomplete và tiếp tục khảo sát trong scope.

Khi nối lượt/chat, tra [tri thức liên quan](operational-knowledge.md) và reconcile checkpoint với journal/ACK/trạng thái hiện tại theo [recovery](retention-stop-and-recovery.md). Bài học và checkpoint không thay discovery hoặc quyền; dùng chúng để tránh lặp lỗi prerequisite đã biết.

## B. Chọn operation trước, runner sau

Với mỗi đơn vị, xác định bốn trạng thái khả năng riêng: **có trong source**, **được expose trong runtime**, **input/auth/vector tương thích**, **đã quan sát execution**. Không dùng một trạng thái thay cả bốn. So cả input properties/schema, không chỉ tool name; helper catalog so tên tham số source và có comparison hai tools/list thực cho requiredness/type/constraints; auth semantics vẫn cần đọc provider/config và kiểm phiên thực.

1. Tìm nhóm operation theo câu hỏi: definition → import; link/JS discovery → crawl; authenticated → profile/context/user; input technique → policy + active; findings → passive/report; recovery → status/history/job; nhiều native jobs phù hợp → AF.
2. Đọc schema actual và những gate liên quan, xác minh target/actor/runtime. Guided đủ thì dùng guided; expert khi cần chức năng khác và đã expose; direct/queue theo topology, không theo sở thích. Không tự bật surface hoặc thay shared scanner nếu việc đó ảnh hưởng run khác.
3. Xem runner đã có cho phần nối: fixture/setup, identity, body seed, BOLA oracle, browser journey, collector, journal. Dùng cả runner khi admission và toàn workload phù hợp; chỉ reuse helper nếu không kéo theo assumptions/gate/side effects không liên quan.
4. Nếu chưa khớp, phân loại gap: cấu hình/registration, input mapping, product fixture/selector/policy, generic mechanism chưa hỗ trợ, hay limitation repo/engine thật. Mỗi loại dẫn tới hành động khác nhau; không gọi tất cả là “blocked by security”.
5. Ưu tiên cấu hình/phối hợp đúng quyền → adapter product tối thiểu → runner bổ sung khi cần → thay capability nền khi thực sự thuộc nhiệm vụ phát triển được giao. Không downgrade kỹ thuật để vừa whitelist và không giả parameter/proof để đi qua gate.

### Chọn deployment theo contract thực

Trước dispatch, so đúng hai deployment bằng tools/list còn đầy đủ pages, image/JAR thực và các input workload cần. `zap_assessment.executor_routing.choose_executor` là helper compatibility chỉ đọc; không cấp scope, không thay admission của runner, không gọi traffic. Descriptor auth phải từ provider/config/runtime đã kiểm, không suy từ một field `authSessionId` hoặc version giống nhau.

- Shared biểu đạt đủ input và auth phù hợp → chọn operation shared trong scope. Thiếu field dù tool có expose là `schema-field-missing`, giữ workload `not-operated`; không gửi thử field ngoài schema.
- Shared thiếu contract → chọn runtime riêng tương thích đã có. Tool không đăng ký là `not-exposed`; required/type/constraint sai là `input-error`; auth kind/config/phiên chưa hợp lệ là `configuration-error`; đã dispatch rồi fail mới ghi `execution-failed`.
- Candidate cũng chưa đủ → ghi primitive/mapping thiếu theo workload; tiếp tục nhánh khác. Không tự bật expert, JSON-bearer experimental hoặc migrate shared để làm selection pass.

Exact method/body cần đọc semantics riêng: candidate hiện yêu cầu **direct + prepared form/json-bearer hợp lệ**, không phải generic anonymous body chỉ vì schema có `method/postData`. Chỉ nghiệm thu capability đã có seed baseline thật, request method/body readback, response/post-state và terminal; field tồn tại hoặc ACK không chứng minh delivery. PUT flat JSON đã kiểm không đại diện POST/PATCH/DELETE, path vector, toàn bộ field/rule hoặc UI.

Không cố gọi tất cả operations; catalog đầy đủ giúp chọn đúng. Snapshot/diff, queue, AF, release evidence là conditional, không phải stage bắt buộc cho mọi assessment.

## C. Các đường thực thi

**Native orchestration:** tool calls trực tiếp trên deployment đã cấu hình: import/seed phù hợp → auth nếu cần → crawl/active có mục tiêu → status → passive → findings/report. Agent ghi RUN và giữ các ID trả về. Seed direct/proxy, UI và fixture phải ghi đúng loại; không có generic seed MCP tool trong catalog hiện tại. Dùng helper có sẵn hoặc adapter đã kiểm để seed qua ZAP khi cần. Không gửi token qua CLI hoặc tool field chứa raw credential không phù hợp.

**Backend common executor:** dùng product_assessment discover/materialize/plan/prepare hoặc import-actor/run khi recipe/input/runtime hợp lệ. Đọc giới hạn rule/vector/proof trước chọn; không tự gọi legacy product-run vì common entry reject. Có thể chia native workload và direct BOLA thành các allocation riêng trong scope đã giao, giữ attribution.

**FE executor:** dùng FE CLI đúng track, reviewed observations hoặc adapter product được xác minh. Browser UI là producer bắt buộc của FE; crawler bổ sung discovery, native attack thực hiện nghĩa vụ active đang áp dụng trên API/input liên quan. Chọn kỹ thuật theo câu hỏi product; UI/passive không thay active. Các producers phối hợp. Setup/auth/native/browser phải giữ mapping actor/origin. Thiếu setup hook chỉ chặn journey phụ thuộc; viết hook riêng đúng product khi cần.

**BOLA executor:** compile expected từ policy đã xác định, prepare actor/object, execute positive và cross-owner/role cases, kiểm response/state rồi reconcile. Direct client hợp lệ được ưu tiên khi native scan không diễn đạt nghiệp vụ; không trình bày kết quả như native alert.

**Product-local extension:** đặt runner/adapter tại khu vực làm việc riêng của product, ngoài folder final report. Runner nhận input explicit product/environment/selection, không tự tìm target từ tên container hay default product cũ. Chỉ gọi primitive đã có; tự viết phần thiếu như fixture mapping/UI action/post-state. Nếu phải sửa core dùng chung, phân tích caller và plan pins, tránh tác động run khác; không cập nhật hash để ép run lịch sử tiếp tục.

## D. Hợp đồng tối thiểu khi viết runner phụ

Chỉ tạo khi có gap cụ thể và đã đọc runner hiện có. Không bắt viết runner cho mỗi endpoint hoặc mỗi lần gọi tool.

- Nhận selection/actor/fixture từ discovery của product hiện tại; xác minh origin và role cần thiết. Không mang credential trong args/log chia sẻ.
- Phân biệt read/setup/mutation/crawl/active/UI/direct; ghi intent trước side effect, ID/ACK và outcome sau. Không cần bộ hash/proof mới để ghi thao tác.
- Có giới hạn lượt/rate theo workload; theo dõi status/session và cách dừng đúng owned producer. Unknown mutation/start chuyển sang reconcile, không retry mù.
- Trả dữ liệu kết quả/lỗi và phần chưa thực hiện để collector đang có/agent tổng hợp. Không tự đặt security pass hoặc task complete từ exit0.
- Cleanup chỉ object/resource thuộc lượt chạy và được phép; retention nếu không có cách xóa hợp lệ. Không sửa dữ liệu product để che lỗi test.
- Kiểm tra có mục đích: request/actor binding, failure/unknown handling hoặc parser/state semantics vừa thêm. Không test bằng assert kết quả mong muốn cố định, không cần qualification toàn platform cho helper nhỏ.

Adapter product được phép chứa route/selector mapping đã kiểm; không được hardcode verdict, response giả, owner ID tùy chọn để pass hoặc policy của product khác. Generic primitive thiếu thực sự có thể thành helper dùng chung, nhưng configuration/state vẫn cô lập theo product.

## E. Execution, lỗi và tiếp tục

Trước lượt chạy, kiểm prerequisite đúng ca (deployment, identity, fixture/state, operation/auth/vector, resources). Bắt đầu bằng baseline có nghĩa; khi baseline không tới handler cần kiểm thì sửa input/fixture hoặc ghi giới hạn, không ghi DAST sâu hơn đã quan sát.

Theo dõi ID đúng loại: guided operationId; expert/native scanId; queue jobId; auth sessionId; AF planId/planPath. Start/timeout/lost ACK khác nhau. Đọc status/owned state trước retry; nếu unknown không giải được thì latch nhánh đó và làm nhánh độc lập. `idempotencyKey` của guided direct không bảo đảm chống lặp.

Lỗi công cụ cục bộ: đọc nguyên nhân thực → sửa nhỏ → kiểm focused → tiếp tục. Lỗi actor chỉ chặn actor; lỗi fixture chỉ chặn dependent cases; resource breach dừng producer liên quan. Nếu contract executor chặn proof/pin thì chọn đường nghiệp vụ phù hợp đã hỗ trợ hoặc xác định sửa contract cần thiết; không hạ gate, forge receipt hoặc mở một qualification campaign vô hạn.

Native API trong adapter owned hiện có được dùng theo contract của adapter. Không coi raw ZAP là đường fallback mặc định để vượt MCP destination/auth/policy rejection. Khi root thật sự thiếu primitive, thêm hỗ trợ rõ ràng với scope controls thay vì bypass.

## F. Reconcile độc lập với runner

Sau mỗi lượt, đối soát inventory gốc với các quan sát:

- Method–route và protocol operation thuộc scope còn mục nào chưa có kết quả/chưa chạy? Route xuất hiện trong crawl không đủ.
- Role nào có hành vi khác chưa được thực hiện đúng actor? BOLA có đủ discovered roles và owner/non-owner/applicability? Không dùng role hiện có đại diện role thiếu.
- FE có thực sự thao tác UI cho journey không, hay mới API setup/crawler? Authenticated traffic có phiên đúng tại thời điểm được tính không?
- Kỹ thuật input nào đã chạy, bị chặn validation/guard/mất auth hoặc chưa đọc đủ kết quả? N/A phải có lý do nghiệp vụ, không vì wrapper thiếu.
- Unknown side effect hoặc cleanup obligation còn gì? Retry không cộng coverage mới; retained historical finding chưa retest giữ nhãn riêng.

Có thể dùng `reconcile_responsibilities`/continue-plan cho allocation đã mô tả, nhưng trước đó phải kiểm cases không bỏ sót inventory/roles. List rỗng hoặc observed toàn selected cases không chứng minh full track. Giữ mục chưa thể chạy trong trách nhiệm, có lý do và bước tiếp. Còn ca đủ điều kiện thì tự tiếp tục, không hỏi PM “chạy tiếp không” sau mỗi subset.

Tách **lượt thực thi xong**, **quyết định cho phần còn mở đã có căn cứ**, và **phạm vi được giao đã hoàn tất**. Một route có baseline/passive hoặc một row khác `not-operated` chưa khép trách nhiệm active/UI/relation đang áp dụng. Với gap, chọn bước [khắc phục](local-remediation-and-continuation.md#quyết-định-cho-phần-việc-còn-mở), thực hiện bước đủ điều kiện; không chỉ thêm limitations rồi đóng lượt. Không ép mọi input/rule kết hợp; kỹ thuật không áp dụng cần lý do theo câu hỏi kiểm thử.

Helper tùy chọn `scripts/review_open_work.py` rà quyết định trên inventory trách nhiệm caller đã lập và so checkpoint/current chỉ đọc. Nó không thay `reconcile_responsibilities`, không tự khám phá inventory, chạy traffic hay cấp quyền; xem [cách dùng](operational-knowledge.md#helper-rà-soát-tùy-chọn).

Gợi ý `Next Actions` từ tool chỉ là đề xuất: không tự tạo release-evidence hoặc mở active/track khác ngoài scope. Với audit/nghiệm thu, áp dụng [operational validation](operational-validation.md), không gọi smoke pass là full skill acceptance.

## G. Kết quả và đóng nhiệm vụ

Đầu ra assessment chỉ ALERTS.json và RUN.json trong một folder ổn định. Tái dùng alert/report data; lọc credential và giảm fields nội bộ khi cần. Các handoff legacy còn sinh technical/evidence là working artifacts, không gửi thành package cuối. Agent tổng hợp hai file theo [hợp đồng](product-assessment-handoff.md); không bắt thêm schema/version, references/hash/evidence hoặc chạy verifier để báo kết quả đã quan sát.

Đóng khi đã xử lý toàn scope, user yêu cầu dừng, hoặc đã chẩn đoán/khắc phục trong quyền mà không còn nhánh hợp lệ chạy được. Nếu inventory/role/journey còn mở thì báo partial/blocked, kèm thao tác đã thử và điều kiện tiếp tục. Runtime success, tests pass hoặc zero alerts không là chứng nhận product an toàn.

Một kế hoạch `execute/repair/prepare/reconcile` chưa thực hiện không đủ để bàn giao nếu bước đó còn làm được trong nhiệm vụ. User chỉ giao một giai đoạn thì kết thúc đúng ranh giới đó, ghi phần ngoài giai đoạn là bước sau; không tự triển khai giai đoạn chưa được giao. Nghiệm thu điểm dừng bằng câu hỏi trong SKILL, không bằng số cases đã pass.

## Những ví dụ ra quyết định, không phải recipe product

- Có OpenAPI public, scanner guided sẵn: import đúng target rồi đối soát inventory, native scan/policy phù hợp; không provision research runtime chỉ để import.
- Protected JSON POST chưa được common runner admit: giữ endpoint mở; kiểm root method/postData và auth, seed/fixture/state; dùng đường tương thích hoặc adapter product. Không đổi POST thành GET hoặc gọi BOLA direct là DAST.
- UI authenticated đọc được nhưng journey tạo object thiếu fixture: tiếp tục read journeys; chuẩn bị fixture đúng quyền/hook riêng rồi thực hiện UI mutation, không thay bằng DB insert và báo UI pass.
- BOLA user thường đã xong nhưng role đặc quyền chưa có account: giữ role trong matrix, làm các ca đủ actor và tìm nguồn account hợp lệ. Không forge role và không đóng track theo số cases đã pass.
- Tool start mất ACK: reconcile ID/status/state, không gọi start lần hai chỉ để có output đẹp; tránh hủy scan người khác.
