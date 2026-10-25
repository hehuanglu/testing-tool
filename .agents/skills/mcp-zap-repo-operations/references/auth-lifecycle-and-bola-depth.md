# Auth lifecycle và BOLA sâu theo mục tiêu

Quy ước hiện hành: [ALERTS/RUN](product-assessment-handoff.md) chỉ ghi thao tác và kết quả, không có phần/folder bằng chứng. Chi tiết proof/pin/qualification dưới đây chỉ áp dụng khi entry code thực sự enforce hoặc user giao qualification đó; không tự thêm chúng vào ordinary assessment hay output.

Đọc phần liên quan theo mục tiêu và discovery. Với BOLA đã giao, object lõi và
collection isolation có căn cứ là trách nhiệm cơ bản theo [hợp đồng phạm vi](assessment-scope-and-completion.md),
không tự thành optional vì fixture khó. Lifecycle và kỹ thuật sâu khác có
applicability riêng. Bàn giao alerts cục bộ theo [handoff](product-assessment-handoff.md#4-điều-kiện-kết-thúc-và-trả-kết-quả)
mà không chạy module này. Đây là hướng dẫn, không là profile/CLI/schema mới hoặc
quyền login, mutation, DB, fault hay automation. Thiếu proof không thành pass.

Tra [auth lifecycle](#chọn-câu-hỏi-auth-lifecycle), [continuity và điểm dừng](#continuity-và-điểm-dừng),
[ownership sâu](#chọn-câu-hỏi-ownership-sâu), [policy provenance](#policy-provenance-và-checker),
[race/tenant](#race-concurrency-và-multi-tenant).

## Chọn câu hỏi auth lifecycle

Chọn đúng câu hỏi thay vì chạy toàn bộ danh sách:

- **Token cũ sau natural expiry:** trước expiry có protected request đúng actor
  với token đó; sau thời điểm expiry thực, quan sát cùng token trên target/binding
  tương thích. Ghi timestamp/timezone, nguồn thời điểm expiry, token reference hoặc
  digest trong vùng private và request/response refs đã giảm secret. JWT claims
  tự decode chỉ là timing diagnostic, không là identity/signature verification.
  Denial của token cũ chỉ hỗ trợ điều kiện đã kiểm; không suy toàn session lifecycle.
- **Relogin:** quan sát login mới và protected subject đúng actor sau đó nếu được
  phép; phân biệt hành động login mới với ZAP auto-relogin, refresh và epoch/session
  continuity. Login success đơn lẻ không khép oracle, direct relogin không chứng
  minh native scanner tự phục hồi phiên.
- **Refresh/revoke/logout:** từ source/spec/UI/traffic trong scope, xác định API
  và semantics thật; frontend xóa storage khác server từ chối token cũ. Không tự
  tạo endpoint hoặc coi tên route là runtime support. Nếu chọn kiểm, nêu expected
  token/session nào còn hoặc mất hiệu lực và quan sát đúng actor trước/sau.
- **Phát hiện mất auth trong scan:** chọn khi cần kiểm monitor/stop của executor,
  giữ protected subject samples, native session/operation refs và phần traffic bị
  gián đoạn. Quan sát direct token bị từ chối không tự chứng minh monitor ZAP đã
  phát hiện/dừng, cũng không là quyền fault injection.

Natural expiry cần phiên/token thật đi qua thời gian hiệu lực vốn có. Synthetic
expired/invalid token, đổi TTL/clock hay owned auth-loss control có giá trị riêng,
không thay natural expiry product. Không đợi TTL, đổi cấu hình hoặc tạo automation
trong task sửa skill; ngay cả scan thường cũng không phải chờ để bàn giao alerts.

## Continuity và điểm dừng

Ghi trong các trường discovery hiện có hoặc technical note: câu hỏi/expected;
product/binding/actor/entry/profile; observation trước/sau với thời điểm/refs;
continuity còn hay mất, có auto-relogin/đổi token/restart không; phần direct và
native; điều đã chứng minh/chưa chứng minh và bước tiếp theo. Không thêm enum.
Theo [auth discovery](auth-capability-discovery.md#quyết-định-coverage) để dùng đúng
availability/verification/disposition; gate của executor vẫn giữ nguyên.

Không còn token hoặc thiếu positive trước đó/cùng binding: ghi không thể thực hiện
cùng-token/same-session observation từ evidence hiện có; câu hỏi chưa kiểm là
not-run/unverified với lý do, continuity chưa biết hoặc đã mất theo sự kiện thật.
Không khôi phục credential từ report chia sẻ hoặc login mới rồi gọi là token cũ.
Run mới có thể kiểm câu hỏi mới khi được giao, không khép retrospective same-session
claim. Mốc hẹn expiry đã qua không là bằng chứng đã quan sát.

Không thấy API revoke/refresh trong inventory chỉ là applicability fact có nguồn
và phạm vi khảo sát; dùng `not_observed_in_scope` khi phù hợp, không runtime pass/
fail. Nếu user muốn kiểm tính năng mà chưa xác định API, ghi câu hỏi/dependency
chưa giải được; không gọi executor unsupported chỉ vì chưa tìm thấy API. Executor
không thực thi được tính năng đã biết là unsupported của đúng entry/vector.

Mất auth trong scan vẫn dừng nhánh phụ thuộc theo contract và giữ partial evidence;
không tính 401/anonymous thành authenticated coverage. Giữ giới hạn sampling/stop
đã quan sát; không suy zero-inflight hoặc chứng nhận mọi thời điểm từ vài samples.
Dừng kiểm sâu khi thiếu token/continuity, budget hết, không thêm thông tin hoặc
cần quyền/capability khác. Handoff thường vẫn trả kết quả đúng phần đã kiểm.

### Giới hạn entry hiện có tại source checkpoint 23/10/2026

`research_product.main` có `check-expiry`, nhưng nhánh này dùng `Product(output)`
với origin finalsource cố định và route `/api/v1/accounts`, đọc actor A từ private
credentials, so thời gian `exp` rồi direct GET. Nhánh này không dùng discovery/
adapter/binding admission của `run`, kể cả parser nhận các flags chung. Nó không
prepare/validate native session hoặc đo monitor reaction. Không quảng bá thành
lệnh expiry generic hay tự chạy với credential lịch sử trên deployment hiện tại.

Nếu mục tiêu cần expiry trên deployment mới hoặc native loss/relogin, xác minh
current authority/binding và executor phù hợp trước; thiếu entry nhận được scope
thì ghi dependency implementation/proof riêng, không wrapper vượt admission.
`ResearchRun` có periodic validate/loss latch/stop theo owned operations trong
source; code support không là proof natural expiry/runtime monitor loss trên product.

## Chọn câu hỏi ownership sâu

Lập đủ object/action/relation/state quan trọng có căn cứ trong trách nhiệm, rồi chọn
workload từng lượt; dùng
[kế hoạch fixture theo case](product-extension-planning.md#fixture-chỉ-cho-case-đã-chọn).
Ghi actor/owner/object/reference ở path/query/body, state cần trước/sau, expected
disclosure/side effect và executor/chi phí. Không mở toàn bộ case space.

- **Populated relation:** empty/null khác có dữ liệu. Receipt null chưa chứng minh
  populated receipt authorization; category/transaction populated proof không
  đóng receipt gap. Nếu chưa có upload/link API trong inventory, ghi chưa kiểm và
  dependency fixture/entry cụ thể; không chèn DB giả kết quả operation đang kiểm,
  dựng endpoint hay ép populate mọi relation.
- **Collection/aggregate/pagination:** giữ trong trách nhiệm BOLA khi contract/discovery
  cho thấy dữ liệu theo owner (ví dụ order list); không đợi user nêu riêng từng list.
  Dữ liệu A/B phải đủ phân biệt disclosure/aggregate theo owner; ghi filter/window/
  pages đã kiểm và completeness theo checker hiện có. Thiếu trang/projection thì
  giữ inconclusive đúng claim, không lấy một list rỗng chứng minh isolation mọi state.
- **Role/object relation:** role chỉ liên quan ownership khi expectation phụ thuộc
  object cụ thể. ADMIN có quyền quản trị chức năng là câu hỏi BFLA riêng nếu không
  phụ thuộc object; không ép ADMIN để đủ BOLA. Shared/tenant chỉ khi có policy/
  inventory thực; không tạo role, grant hay tenant giả để đủ checklist.

## Policy provenance và checker

Với từng expectation có ảnh hưởng kết luận, ghi nguồn: requirement/spec; hành vi
đã thống nhất có reference thật; hoặc source-derived hypothesis. Ghi action/state/
actor relation mà nguồn nói tới và mâu thuẫn còn lại. Source là căn cứ hữu ích để
thiết kế case, nhưng không tự chứng minh đó là yêu cầu nghiệp vụ đúng.

Checker tách code khỏi executor, không import evaluate hoặc có tamper controls
chỉ củng cố tính nhất quán theo expected đã khóa. Nó không làm policy độc lập nếu
expected vẫn lấy cùng source/artifact origin. Tách policy confidence, capture/
state completeness, integrity và outcome; giữ verdict/gate thật của entry.
`policyAcceptanceRefs` không rỗng trong common code không tự là sign-off: không
điền reference giả, lấy checker pass làm acceptance hay đổi locked plan sau run.

Nếu policy chưa rõ, đọc requirement/spec/contract sẵn có trong scope rồi chỉ nêu
câu hỏi thay đổi conclusion, ví dụ “EMPLOYEE được đọc mọi order hay chỉ order được
giao?” hoặc “foreign category reference khi tạo transaction có được phép không?”.
Chỉ hỏi phần không tự giải được khi nó thật sự ảnh hưởng kết luận; không bắt
reviewer sign-off hình thức cho mọi case hoặc coi source vô giá trị. Trong lúc
chưa giải, bàn giao observations và unknown/source-hypothesis đúng mức; không
nâng matched thành security approval, không hạ capture failure thành policy gap.

## Race, concurrency và multi-tenant

Chỉ xem xét khi product/mục tiêu cần và executor có admission/fixture/oracle/proof
tương ứng. Serial ownership cases, pagination và child-kill/lost-response proof
không chứng minh race/concurrent isolation hoặc tenant boundary. Không có evidence
hỗ trợ thì ghi chưa kiểm/unsupported đúng entry hoặc chưa quan sát applicability;
không hứa capability chỉ vì tài liệu nêu candidate. Thêm executor/adapter hoặc
concurrent dispatch là task code riêng, không nằm trong module documentation này.

Historical finalsource auth gaps và BOLA receipt/role/tenant/race gaps chỉ là
[auth snapshot](</Users/hahoangloc/Working/testing tool/test-artifacts/be-authenticated-research-20261020T173556Z/KNOWN_GAPS.md>)
và [BOLA snapshot](</Users/hahoangloc/Working/testing tool/test-artifacts/bola-continuation-20261021T125040Z/KNOWN_GAPS.md>).
Không biến chúng thành status runtime hôm nay hoặc quyền chạy kiểm tiếp.
