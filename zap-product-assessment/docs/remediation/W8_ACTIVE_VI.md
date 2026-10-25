# W8 — active controls trên fixture SQLi và reflected XSS

Contract `w8-owned-active-1` triển khai G9 development trên fixture do run tạo,
anonymous, GET query. Không nhận product URL, credential hay container có sẵn.
Không mở P0/native/delegated/browser/shared mode; các gate W5/W7 và R1/R2 giữ nguyên.
W8 là technical controls qua ZAP API trực tiếp; tích hợp entry point/MCP và liên kết
track thuộc W9, regression sản phẩm A→B thuộc W10.

## Fixture và oracle

- SQLi: rule40018, SQLite thật trong memory; vulnerable nối chuỗi SELECT,
  fixed dùng parameter binding. Baseline đọc đúng một row; witness tautology trả
  hai row ở vulnerable và zero ở fixed. Exception SQLite là kết quả execute thật,
  không nhận diện payload bằng regex hoặc trả alert giả.
- Reflected XSS: rule40012, response `text/html` tại HTML body text; vulnerable
  render input trực tiếp, fixed escape HTML. Oracle độc lập kiểm bytes và parse
  script/event-handler context. Đây là reflected HTML sink proof, không phải
  JavaScript execution/browser/DOM-XSS hay mọi JSON endpoint.
- Fixture data thay theo seed. Mỗi pair giữ cùng seed/vector/baseline, source,
  image/add-ons/policy; build hash kết hợp source và variant nên vulnerable/fixed
  có pin riêng. Hai pair dùng data khác nhau; core không sửa theo IDs.

Policy mỗi scan chỉ bật một rule, strength LOW, threshold MEDIUM. Chỉ GET query
được admit; body/header/cookie/HTTPS/auth vectors không được suy ra support.
Script dynamic SwaggerSecretDetector chỉ được remove trong scanner do run tạo.
Effective inventory trước/sau gồm rule enabled flags, strength/threshold, versions,
add-ons, input options, proxy và hash nội dung ScriptWrapper thực sự trong engine.

## Payload → wire → sink

Tái sử dụng native `TrafficProbe.java` W4, giữ HttpSender delegate hiện có. Rule
identity từ loaded class/stack; không tin caller header. Native request/response,
guard forward-intent/disposition và target arrival khớp request ID, method, URL/body
hash và response hash. Telemetry target giữ input đã decode, SQL statement/parameters,
rows/error hoặc rendered HTML. Verifier replay SQLite riêng và kiểm HTML context;
alert phải trỏ native request cùng rule/input/sink qua actual core message.

Manual seed và manual witness có initiator riêng; không tính thành scanner exercise.
Terminal scanProgress counts phải bằng native rule counts, nhưng Complete không
thay baseline hợp lệ, payload tới sink hay detection oracle. Không tăng strength để
che missing proof. Fixed không có alert vẫn cần actual rule traffic, sink exercise
và witness không tái hiện lỗi; pair comparator đối chiếu policy/seed/build bindings.
Adaptive rule có thể gửi số payload khác nhau giữa vulnerable và fixed.

Seed bị thiếu/duplicate parameter, guard lọc payload, thiếu sink, rule disabled,
Complete với zero native exercise đều block technique claim. Khi witness độc lập
đã chứng minh vulnerability, `securityVerdict=fail` tồn tại dù scanner không detect
và G9 bị block. Missing sink không được suy fail chỉ từ tên variant.

## Runtime và evidence

Image ZAP2.17.0 pin
`sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6`.
Một container network none, không published port/socket, UID1000, read-only root/source/job,
cap-drop ALL, no-new-privileges, core0,1.5GiB/no-swap,2CPU,256PIDs. Home/session,
fixture, captures và temporary files ở tmpfs có cap; chỉ minimized JSON export ra host.
Guard local chỉ forward đúng literal origin/path/query và giữ correlation header.
Network-none chặn external egress; đây không phải shared UID firewall/HA acceptance.

Host preflight `2×32MiB+2GiB reserve`, during reserve2GiB; Docker free và RAM
được quan sát trong worker, RAM floor4GiB. Cgroup current/peak/events và Docker
free/RAM sample mỗi1s, verifier yêu cầu gap≤5s, zero OOM. Startup→scanner/fixture
shutdown được lấy mẫu; outer controller kiểm host disk, ownership, stopped/OOM và
exact ID/image trước remove. Đây là bounded tmpfs diagnostic, không cấp calibration
G6 mới, daemon crash recovery hoặc resource SLO. W4/W5 fault/recovery contract giữ riêng.

Creation intent trước Docker, lost ACK chỉ reconcile exact name/label/image, không
start lại. API sendRequest cập nhật Sites bất đồng bộ: chờ exact seed có mặt trước
single scan start. Worker failure giữ partial captures/log và cleanup; không seal bundle.
Complete bundle chỉ publish atomic sau safe reader, external locked plan hash,
checksums, semantic recomputation và cleanup. Local receipts không phải signed remote
attestation. Lịch sử attempts/failures được giữ, không sửa lại bằng verifier mới.

## Chạy lại

Từ package root, dùng output mới. Plan SHA lấy từ output/locked plan đã giữ ngoài bundle.

```sh
PYTHONPATH=src .venv/bin/python scripts/w8_active_campaign.py run --output /absolute/new-vulnerable --seed 8101 --variant vulnerable
PYTHONPATH=src .venv/bin/python scripts/w8_active_campaign.py run --output /absolute/new-fixed --seed 8101 --variant fixed
PYTHONPATH=src .venv/bin/python scripts/w8_active_campaign.py compare --vulnerable /absolute/new-vulnerable/bundle --vulnerable-plan-sha VULNERABLE_PLAN_SHA --fixed /absolute/new-fixed/bundle --fixed-plan-sha FIXED_PLAN_SHA --output /absolute/new-pair.json
PYTHONPATH=src .venv/bin/python scripts/w8_active_campaign.py verify --bundle /absolute/new-fixed/bundle --expect-plan-sha FIXED_PLAN_SHA
PYTHONPATH=src .venv/bin/python scripts/w8_active_controls.py --vulnerable /absolute/new-vulnerable/bundle --vulnerable-plan-sha VULNERABLE_PLAN_SHA --fixed /absolute/new-fixed/bundle --fixed-plan-sha FIXED_PLAN_SHA --output /absolute/new-offline-controls
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
```

Các fault CLI: `invalid-seed`, `missing-parameter`, `guard-filter`, `missing-sink`,
`disabled-rule` với `--variant vulnerable --fault CASE`. Exit0 của fault runner
nghĩa expected blocked outcome, không có nghĩa technique pass hay security approval.
Verify exit0 chỉ consistency; đọc từng status field.

Checkpoint và commands thực:
[HANDOFF_VI.md](../../../test-artifacts/mcp-zap-remediation/w8-active-20261019T135325Z/HANDOFF_VI.md).
Compatibility: không sửa dispatcher/schema cũ1.0–1.4/v2, product, root Java/CI hoặc
shared scanner. W8 pre-final candidate attempts pin source riêng; không tự đổi chúng
thành current acceptance. Rollback gỡ/tắt entry point W8 và các file W8, khôi phục
plan/registry/docs từ baseline-source của checkpoint; giữ evidence và dirty changes cũ.

Nguồn rule upstream: [SQLi40018](https://www.zaproxy.org/docs/alerts/40018/) và [Active Scan Rules / reflected XSS40012](https://www.zaproxy.org/docs/desktop/addons/active-scan-rules/). Runtime receipts của checkpoint mới là bằng chứng cho image đã pin.

Checkpoint cuối:9 native campaigns (4 positive variants/2 pairs,5 faults),19 focused tests,418 full-suite tests,25 offline controls. Max sampling gap 1.015s; cgroup peak 656916480 bytes. G9 synthetic pass; product unverified; independent review và R1/R2 vẫn chưa admit. Failed intermediate sampling/setup/counterexamples được giữ, chỉ namespace `accepted` là final-source acceptance.
