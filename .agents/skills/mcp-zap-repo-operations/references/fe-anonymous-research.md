# FE anonymous research

Điểm xuất phát nghiệp vụ và scope ở [track intents](track-intents.md); chọn operations/executor theo [dispatcher](operation-dispatch.md). Reference này bổ sung chi tiết của entry hiện có, không mở rộng nhiệm vụ hoặc bắt chạy qualification.

Quy ước hiện hành: [ALERTS/RUN](product-assessment-handoff.md) chỉ ghi thao tác và kết quả, không có phần/folder bằng chứng. Chi tiết proof/pin/qualification dưới đây chỉ áp dụng khi entry code thực sự enforce hoặc user giao qualification đó; không tự thêm chúng vào ordinary assessment hay output.

Profile `fe-anonymous-research/1.0`, plan `fe-anonymous-research-plan/1.0`, journey sidecar `fe-anonymous-journeys/1.0`. Đây là research lane riêng; browser-e2e/canonical-origin strict và ba backend contracts giữ nguyên. Code/controls có thể tồn tại trước runtime qualification: đọc IMPLEMENTATION_STATUS và run proofs hiện tại; không quảng bá capability từ help text.

## Entry và discovery

Dùng Python `.venv` của assessment, từ workspace đã xác minh:

```sh
"$ZAP_PYTHON" ${ASSESSMENT_ROOT}/scripts/product_assessment.py fe-anonymous --help
"$ZAP_PYTHON" ${ASSESSMENT_ROOT}/scripts/fe_anonymous_research.py discover --product /absolute/product --recipe reviewed-fe/1.0 --observations /absolute/observations.json --output /absolute/new-discovery
"$ZAP_PYTHON" ${ASSESSMENT_ROOT}/scripts/fe_anonymous_research.py plan --discovery /absolute/DISCOVERY.json --journeys /absolute/FE_JOURNEYS.json --selection /absolute/selection.json --authority /absolute/authority.json --output /absolute/new-plan.json
"$ZAP_PYTHON" ${ASSESSMENT_ROOT}/scripts/fe_anonymous_research.py run --plan /absolute/plan.json --selection /absolute/selection.json --output /absolute/new-run
"$ZAP_PYTHON" ${ASSESSMENT_ROOT}/scripts/fe_anonymous_research.py verify --run /absolute/run --expected-plan-hash PLAN_SHA256
"$ZAP_PYTHON" ${ASSESSMENT_ROOT}/scripts/fe_anonymous_research.py handoff --lineage /absolute/lineage.json --output /absolute/new-handoff
```

`discover`, `status`, `verify`, `handoff` offline: không start Docker/browser/network. `plan` kiểm selection/deployment, không chạy journey. Unknown recipe không tự chọn product theo folder name. `finalsource-fe/1.0` chỉ là adapter explicit; đọc source/DOM trước dùng, không lấy ví dụ làm discovery product mới. No-source input cần bounded authorized UI discovery rồi observations có provenance; source provider hiện cần observations, không giả source parser chạy được cho mọi framework.

## Admission và phase

Plan khóa source/recipe/implementation hashes, canonical origin, actual frontend Docker relationship/cert/config/build, public request policies, authority, journey IDs/expected UI+network, active vectors, browser/driver/addons/images, resource calibration, retention và stop policy. Không đưa credential vào CLI. Tạo fixture values mới private; fixture success thiếu chỉ chặn nhánh phụ thuộc, validation/failure vẫn thực hiện.

Browser fresh profile từng case, W3C actions hữu hạn và probe code-owned; không thực thi JS từ document/recipe. Cookie có tên/origin/provenance riêng khi cần. Không dùng cookie cleanup đơn lẻ thay fresh storage/IndexedDB/cache/SW proof. Login/register request có thể anonymous; response token/storage đánh dấu terminal transition. Không forward follow-up có identity, không strip token rồi tính đó là hành vi nguyên bản. HTTP200 SPA shell không đủ route oracle. UI validation chặn submit không là API validation.

Canonical HTTPS giữ URL scheme/host/port và upstream Host/SNI. Owned broker decrypt request trước policy, xác minh upstream CA/hostname/fingerprint. Browser tin CA ZAP trong owned profile/runtime; không acceptInsecureCerts, đổi system trust, thay cert product hoặc mirror HTTP. Kernel boundary và management auth phải có controls actual; CONNECT allowlist đơn lẻ không đủ. DNS/IPv6/redirect/WebSocket/SW/third-party bị guard hoặc có gap đúng nhánh; không probe Internet để kiểm deny.

## Native active, lifecycle và evidence

Client Spider/AJAX chỉ bổ sung discovery, không thay scripted journeys. Không `auto` rồi suy HTTP fallback có JS. Native POST anonymous đi qua bounded engine primitive đã có vì guided explicit method/body yêu cầu authSessionId; không fake auth handle. MCP dùng actual tools/list schema cho crawl/status/stop/report/chunk. Rule enabled không là delivered payload; giữ exact rule/version/vector, baseline và response oracle. Không bỏ active vì passive đã ra alerts. DOM execution cần oracle riêng; reflection không là execution. Register dùng finite fresh identities, login caps thấp hơn lockout; không brute force. Body/vector chưa proof giữ gap, không blanket N/A.

Journal start intent/ACK/native ID/terminal; unknown start/POST không replay. Dừng đúng owned producer khi identity/scope/resource/binding breach, settle passive nếu đủ tài nguyên, export partial, cleanup exact IDs. Giữ evidence private 0700/0600. Runtime reserve và browser/TLS calibration theo current measurements; không dùng HTTP calibration để admit. User đã cho phép startup và exact disposable cache/temp cleanup thì thực hiện, không hỏi lại; không blanket prune/DB/evidence/user data deletion.

Handoff theo [hai file kết quả](product-assessment-handoff.md#3-bộ-bàn-giao-bắt-buộc): ALERTS.json và RUN.json. Giữ native severity/confidence, browser-only observations riêng và ghi đúng UI/route/kỹ thuật đã chạy, kết quả/lỗi, coverage, hạn chế, phần chưa làm. Không có folder/mục bằng chứng, không yêu cầu pins, raw refs hoặc checksum trong báo cáo. Runner vẫn giữ controls/gate nội bộ; không tự mở qualification hai fresh runs/interrupted run cho ordinary assessment.

## Lưu ý đã kiểm từ implementation

Rule `40012` là reflected XSS; `40018` là SQL Injection. Không suy tên rule từ tên campaign. Recipe phải nói đúng độ sâu: payload tới validation/credential-error không chứng minh đã tới SQL sink. Native history đọc từng message khi response JS lớn; không tăng transport cap để che mất capture. Driver của Client Spider cần loopback ports trong namespace owned, vẫn giữ management auth và deny direct/IPv6/external egress.

Đọc [runbook trong assessment](../lib/zap-product-assessment/docs/fe-anonymous-research.md) khi chuẩn bị selection/authority hoặc tái hiện. Verifier nối browser/broker với native history và kiểm DOM đã capture; các giá trị pass do producer báo riêng không đủ. Handoff có optional triage ref với hash; raw vẫn private và native classification không đổi.

ZAP Selenium mặc định có thể yêu cầu `acceptInsecureCerts=true`. FE runtime dùng `fe_anonymous_geckodriver.py` cho browser phụ Client Spider: ép W3C session sang false, kiểm capability trả về và fail closed nếu không đúng. Đọc `CLIENT_BROWSER_CAPABILITIES.json`; chỉ broker TLS pass không thay proof browser capability. Nếu chat/controller mất, không replay start/POST; stop/export theo Journal/owned IDs và giữ interrupted/partial. Lượt fresh thay thế dùng run ID/profile/fixture mới, không gộp alert lặp.


## Semantics sau independent review F1–F4

Evidence mới dùng `fe-anonymous-evidence/2.0`, broker `fe-broker/2.0`.
Plan/journey 1.0 vẫn đọc được vì facts workload nằm trong frozen plan và implementation pins.
Reader hiện hành trả `semanticsVersion=independent/2.0`: đọc được bundle 1.0 nhưng
không kế thừa claim complete cũ. Reverify vào namespace mới; giữ reader/pins/verdict
lịch sử và raw/index nguyên bytes. Discrepancy lịch sử không là traffic rerun.

Broker ghi request intent và append-only events bằng fsync trước send, rồi chuyển
`sent` → `response-headers` → `response-observed`. `sent` nghĩa có thể đã gửi;
chỉ response hoàn chỉnh mới có forwarded=true. Lỗi sau điểm gửi là unknown,
forwarded=null, giữ allocation/case/campaign/request hash và status đã nhận.
Chỉ `not-sent` có cơ sở trước send mới là forwarded=false do transport.
Unknown mutation latch producer, không replay, giữ reconciliation/retention obligation;
đọc `UNKNOWN_MUTATIONS.json`, durable broker events và private fixture ledger.
Readback hữu hạn chỉ đúng owned identity/resource; không retry POST để tìm kết quả.

Admission derive theo selected journey, campaign và setup hook. Browser/passive/read
không tự cần active/public-mutation. POST read-like phải có effect provenance;
mutation và fixture setup vẫn cần quyền thật. `ADMISSION.json` giữ nhánh thiếu quyền;
not-run/gap giữ task partial, inventory không bị bỏ. Broker cũng enforce quyền,
không chỉ controller. Prerequisite thiếu chỉ chặn nhánh phụ thuộc.

Verifier tính delivery từ final broker responses + native messages + native baseline:
method/path/rule header, payload đổi đúng vector, sibling giữ baseline, verified app
TLS. Header rule với body không đổi là control request, không là delivered payload.
Re-read sau terminal/passive settle; so counters với OPERATIONS; raw start/status/stop
và hai passive observations ổn định trước report export là bắt buộc. Cờ producer
không thay kiểm độc lập. Terminal/stopped chỉ nghĩa không còn chạy; không là mọi
payload kỹ thuật đã chạy hết. Unknown mutation hoặc nghĩa vụ áp dụng chưa xử lý
không được complete.

Reconcile public inputs với DTO/service/UI và runtime trước chọn kỹ thuật. Valid
baseline giữ sibling fields hợp lệ; không dùng invalid email để né persistence rồi
đóng active public forms. Password vào bcrypt khác email vào parameterized query.
Giữ validation/error controls nhưng claim đúng độ sâu. Quote/markup trên register
cần fresh finite identity, thành công/transition, persistence readback và retention;
DOM text/element observations không tự chứng minh mọi stored/DOM XSS vector.
N/A cần input/sink provenance, nhánh áp dụng chưa kiểm giữ gap. Không fuzz mọi
field × mọi rule hoặc tự thu hẹp nhiệm vụ cho vừa capability.

Cap login tính cả baseline và native control body không đổi; cap changed payload riêng không bảo đảm dưới lockout. Final UI counters/network claims được tính lại sau stop, journal ACK ban đầu giữ nguyên.

Owned controls cũng cần readback độc lập: đối chiếu `HOST_SAMPLES.json` với reserve, raw native detector outcomes, broker/app arrival và pins. Producer `transport-boundary-pass` không đủ nếu late sample đã chạm reserve; giữ raw verdict, tạo disposition từ chối và chạy lại control ở namespace mới sau khi đủ headroom. Không lấy control có resource breach làm qualification; không sửa raw để pass.
