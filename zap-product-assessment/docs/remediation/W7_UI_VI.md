# W7 — browser session spike và UI E2E diagnostic

Contract `w7-owned-ui-diagnostic-1` là owned synthetic, không nhận product URL hoặc
credential input, không khởi động ZAP, không mở native/JSON bearer/P0 protected mode.
Nguồn chuẩn W7/G8 là `MCP_ZAP_REMEDIATION_PLAN_VI.md`; tài liệu long-term chỉ đối chiếu.
Theo yêu cầu tiếp tục W7, implementation/contract work được làm độc lập phần operational
W5. Không suy W7/G8 pass từ API, unit test hoặc verifier exit0.

## Candidate đã triển khai

- Browser worker chạy Firefox thật qua W3C WebDriver trong image ZAP đã pin sẵn, chỉ
  lấy binary Firefox và geckodriver addon; không chạy Java/ZAP/MCP. Client protocol
  stdlib không thêm Selenium/Playwright dependency. Driver version/hash và browser
  capabilities được readback khi session thực sự chạy.
- Target UI owned source-derived có semantic labels/test IDs và submit handlers thật.
  Login A → create account → owner detail → expense → balance → browser refresh →
  logout A/login B → deny read/write → logout B/login A → final unchanged state.
  Có13 required steps, dynamic IDs/ownership từ W6 manifest, scale4 integer money.
- W6 independent Product double, ProductAdapter, transition oracle, BundleReader,
  opaque canary auditor, atomic writer và journal được tái sử dụng. API seed chỉ là
  preparation; không thay UI click/submit. Driver chỉ dùng fill/click/refresh và
  read-only DOM snapshots; business requests xuất phát từ HTML submit handlers.
- Target arrival có actor/auth epoch, Firefox User-Agent, exact method/path/body,
  response và pre/post-state hashes. Worker đọc file state độc lập API trước/sau
  từng UI action. Verifier replay W6 state, so DOM với response/resource/balance,
  owner-positive trước B negatives, account render/disclosure và state unchanged.
- Locator/test-id và wait có deadline trên completion/request correlation; polling
  delay không là oracle. Không retry toàn flow. Nonempty alert, sai rendered balance,
  missing submit, sai actor/resource/correlation/reload không tạo functional-pass.
- Screenshot chỉ crop summary element sau reload, không login/password form;
  ≤256KiB/PNG, pin hash/length. Khi browser chưa chạy thì không có screenshot thật.
- Full flow yêu cầu session-spike bundle trước, external plan SHA, actual-webdriver
  evidence và current session source/image pins. Spike-only không được tính là UI
  business completion. `unit-contract-corpus` có generated DOM/command observations
  chỉ kiểm oracle; `functionalVerdict=not_run`, `browserRuntimeVerified=false`.

## Session/secret path và ranh giới

Nguồn finalsource AuthContext/LoginForm/httpClient dùng localStorage/sessionStorage,
rememberMe mặc định true. Candidate mô phỏng localStorage path bằng canary sinh trong
container memory; host chỉ nhận fingerprint/length metadata. Actual Firefox session spike đã phát hiện canary còn trong
`w7-profile/storage/default/http+++127.0.0.1+18080/ls/data.sqlite` sau khi browser đóng.
Raw/readonly SQLite reader cùng xác nhận; đây là secret failure, không phải skip.
`startupCache/scriptCache.bin` vượt8MiB reader budget vẫn là coverage gap.

Driver log không lưu command values. Login request/response được minimize trước
arrival persistence; bearer/password không vào bundle. Auditor raw/SQLite readonly
cells (UTF-8/UTF-16LE) có seeded unit controls. Unsupported compressed/WAL/dump
formats vẫn ghi gap; không suy raw-scan zero là complete decoder proof.

Nếu profile có canary: giữ security fail, G3/G8 blocked; raw owned profile phải được
copy private ngoài workspace, file0600/dir0700 và pin inventory trước khi xóa đúng
container/volume. Không export raw profile. Full143 sink×lifecycle operational
pairs chưa được chứng minh; UI diagnostic không cấp R1/R2 hay product acceptance.
Client logout chỉ chứng minh actor switch/UI token removal, không server revocation.

Fidelity luôn `owned-synthetic-source-derived-ui`; không phải actual finalsource UI,
canonical origin, TLS/CORS/cookie/CSRF proof. Product runtime vẫn không được phép.
Native-style credential path cần N/C hoặc đường khác có G3 proof trước operational.

## Resource và thực thi

Image interpreter/browser: `sha256:5ccfff9a411743ab2615136a2edd7416bec9ce41572fa94e935df38c14adb2b6`.
Network none, no published ports/host socket, read-only root/source/job, user1000,
cap-drop ALL/no-new-privileges/core0,768MiB/no-swap,1CPU,256PIDs, private work/tmp tmpfs.
`/work` cho phép exec để chạy geckodriver đã pin; `/tmp` giữ noexec mặc định.
Export tmpfs dùng exact registered paths và bounded read (result4MiB, screenshot256KiB),
vì Docker archive/cp không truy cập tmpfs trong runtime này. Profile là owned persistent volume để kiểm persistence có chủ đích, không borrowed
browser profile. Chỉ đúng run label/container ID/image/volume name được cleanup;
intent được journal trước create, uncertain ACK không start lại mù.

Host disk preflight giữ `2×32MiB + 2GiB reserve` = **2.0625GiB**. Không hạ ngưỡng để
chạy UI, không prune/reset shared resources. Đây không phải scanner G6 calibration.

Từ package, output phải là directory mới:

```sh
PYTHONPATH=src .venv/bin/python scripts/w7_ui_campaign.py --output /absolute/new-session-spike --seed 7101 --spike-only
PYTHONPATH=src .venv/bin/python scripts/w7_ui_campaign.py --output /absolute/new-ui-run --seed 7201 --session-spike /absolute/new-session-spike/bundle --expect-spike-plan-sha EXTERNAL_SPIKE_PLAN_SHA
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_ui.py' -v
PYTHONPATH=src .venv/bin/python scripts/w7_ui_controls.py --output /absolute/new-unit-controls
```

`verify_ui_bundle(path, external_plan_sha)` là readback offline, không Docker/HTTP.
Unit controls có14 cases và được ghi rõ không browser runs; actual-bundle offline
controls có15 cases. Runtime checkpoint có9 final browser campaigns (1 session spike,
3 fixed flows13/13,5 faults),42 UI tests và399 full-suite tests đạt. W6 old evidence giữ
bytes; source-current helper W6 có thể thấy intentional registry/docs/source drift.

## Runtime continuation19/10/2026

[Checkpoint runtime mới](../../../test-artifacts/mcp-zap-remediation/w7-runtime-20261019T130900Z/HANDOFF_VI.md)
ghi browser campaigns thực tế, command receipts, canary failure, private retention,
cleanup và readback. Firefox153.5.0/geckodriver0.37.1 chạy trong image đã pin.
Flow reload có hai request identity→account read; verifier kiểm cùng actor/subject/epoch,
state không đổi qua identity và balance/resource sau read. Contract corpus cũng
bắt buộc hai request này, không dùng generated DOM để thay browser runtime.

Dùng thêm controls trên actual bundle (offline, không thêm browser/product requests):

```sh
PYTHONPATH=src .venv/bin/python scripts/w7_ui_controls.py --output /absolute/new-actual-controls --actual-bundle /absolute/fixed-run/bundle --expect-plan-sha EXTERNAL_FIXED_PLAN_SHA
```

W7 implementation và synthetic functional diagnostic có thể bàn giao theo nhánh
negative-evidence của kế hoạch. G3/G8 operational vẫn blocked do persistent canary;
N/C là dependency tiếp theo cho session path secret-safe và canonical fidelity.
Không tự mở rộng W7 sang N/C, W8–W11 hoặc bỏ UI required track. Operational secret
proof143 pairs, product runtime, TLS/CORS/cookie/CSRF và server revocation chưa kiểm.

## Checkpoint candidate lịch sử

[Handoff W7](../../../test-artifacts/mcp-zap-remediation/w7-ui-20261019T124203Z/HANDOFF_VI.md)
chứa actual receipts. Session attempt đầu bị block trước volume/container/canary vì
host free900.861.952 bytes <2.214.592.512 bytes. Prerequisite probes đã thấy Firefox
153.5.0esr và geckodriver trong pinned addon, không là browser session/functional proof.
38 focused tests và14 generated-evidence controls đã đạt; actual browser functional,
session persistence, screenshots và crash/cleanup runtime còn chưa kiểm chứng.
Không có G8 operational pass hoặc R1/R2 admission. Sau khi host có đủ free space,
chạy fresh session spike trước, rồi mới quyết định candidate UI diagnostic campaign.

Protocol reference: [W3C WebDriver](https://www.w3.org/TR/webdriver2/).
