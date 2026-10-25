# W4 — effective policy, resource gate và partial/stop evidence

Checkpoint hiện tại: `test-artifacts/mcp-zap-remediation/w4-completion-20261019T032146Z`.
Kết quả và readback cuối nằm trong `gate-results.json`, `runtime-readback.json`,
`preservation-final.json` và `HANDOFF_VI.md` tại checkpoint đó. Checkpoint conformance
trước được giữ nguyên, bao gồm các acceptance từng còn thiếu.

## Phạm vi implementation

W4 triển khai G5/G6 trên runtime Docker riêng, anonymous, với hai workload: fixture
redirect/background và fixture GET query chạy built-in rule 40012. Đây là development
acceptance cho primitive policy/resource/stop; không cấp product security approval,
independent reviewer approval hoặc mở protected mode. W5 chịu trách nhiệm G3/G4 auth và
secret lifecycle; browser thuộc W7; vulnerable/fixed controls, full vector/sink proof
thuộc W8; shared/native daemon restart và state-loss acceptance thuộc các track riêng.

`w4-owned-active-conformance` chỉ nhận fixture synthetic loopback cố định và
`/api/echo?q=baseline`. Registered product adapters từ chối workflow này; Executor yêu
cầu observed runtime riêng. Bật boolean active trên workflow V1 thường vẫn bị block.
Không gửi traffic vào finalsource, dùng credential hoặc sửa root Java/CI/shared stack.

## Policy và fidelity

Inventory trước/trong/sau run pin add-on versions, rule IDs/enabled flags, input-vector
options và SHA256 nội dung ScriptWrapper thực sự đang nằm trong engine. Active policy
riêng `w4-query-only` chỉ bật 40012. Script động `SwaggerSecretDetector.js` của image có
hành vi tự enable khi active scan bắt đầu; workload tối thiểu loại script đó khỏi
scanner **thuộc run** trước khi chốt inventory. Không gỡ script trên shared scanner.

Native collector giữ sender delegate sẵn có. Rule identity dựa vào class reference của
plugin được load và stack tại request, không dựa vào `x-zap-scan-id`. Request chuẩn bị
của native Analyser được phân loại riêng là `active-control`; không tính vào số request
của active rule. Unknown/ambiguous/disabled rule vẫn latch dù boundary đã chặn request.

Executor cập nhật phase bằng atomic file replacement trước operation intent. Collector
chụp phase tại request; guard chỉ nhận active producer trong phase active, và controller
kiểm lại ngay cả với request đã bị chứa. Enabled inventory không tự cấp quyền chạy
active ngoài workflow/phase. Final policy đòi observed forwarded rule set bằng expected
set; campaign đối chiếu thêm terminal scanProgress request counts với native receipts.

Wire URL/body hashes phải khớp sender, boundary và independent target arrival. Query
được giữ nguyên; header/body/cookie fuzzing chưa được admit và được công bố unsupported.
Guard không mở CONNECT tunnel. HTTPS refusal cần native I/O failure và authority-bound
CONNECT denial, không được tạo HTTP application response giả. Passive/background được
audit riêng; scanProgress không được dùng làm bằng chứng cho toàn bộ egress.

Sau cleanup, cả ba durable traffic logs được đọc lại. Snapshot thay đổi, request đến
muộn, receipt thiếu hoặc forbidden canary arrival đều ngăn publication. Bundle thành
công có traffic closure pin SHA của snapshot sau khi mọi producer đã dừng.

## Resource và cleanup

Không có fixed floor 8GiB theo chỉ định user. Preflight kiểm host và Docker storage
riêng theo `2 × estimatedRunGrowth + 2 GiB reserve`; chưa có growth thì phải calibrate
synthetic trước. Candidate RAM headroom vẫn 4GiB, completed sampling gap tối đa 5 giây.
Calibration pin source/image/product/workflow; active metadata dùng version 1.2 với
phase active thật, metadata non-active 1.1 giữ nguyên ý nghĩa cũ.

Monitor bắt đầu từ preflight, bao phủ startup, producer/report work và cleanup.
Stop/remove từng container được đồng bộ với sampler để không đọc cgroup vừa biến mất
hoặc quan sát khoảng giữa removal và ACK; có forced samples xen kẽ. Sau khi container
dừng, metric ghi lại cgroup peak cuối đã quan sát, không giả thành một peak mới đo sau
khi cgroup mất. Calibration không phải RAM SLO cho mọi topology/browser.

Chỉ khi mọi workload đã remove, monitor mới ghi seal và lấy mẫu cuối. Measurement helper
được stop/remove riêng trong cửa sổ tối đa 5 giây; quá hạn, latch hoặc writer failure
vẫn block publication. `runtime-safety.json` và manifest chứa timeline cuối; snapshot
trước cleanup được giữ riêng. Atomic publication và reserved stop channel xử lý các lỗi
mà polling không thể ngăn kịp. Không có complete manifest giả khi fault xảy ra.

Cleanup xác minh creation intent, exact container ID, pinned image ID và ownership label.
Missing/mismatched ownership không cho phép stop/remove. Không confirmed stop thì
quarantine, không reuse. Recovery tạo journal mới, giữ journal gốc và chỉ stop; không
replay start/mutation hoặc nâng verdict của lượt lỗi thành pass.

## Phân loại bằng chứng

Hai positive runs giữ `execution=completed`, `evidence=complete`, `cleanup=clean`, nhưng
application gate vẫn `review_required`, security `inconclusive` do findings của fixture.
Development acceptance không yêu cầu bỏ findings để đổi gate thành allow. Rule 40012
proof là policy/fidelity proof, không phải vulnerability detection/sink acceptance.

Fault campaign phân biệt rõ: disabled native fixture rule/unknown emitter và policy
mutation có chủ đích; persistent journal ENOSPC injection tại I/O boundary; kernel
ENOSPC/EROFS/EFBIG trong tmpfs 8MiB/root read-only; SIGKILL controller thật sau crawl ACK;
và cắt UNIX Docker API transport riêng của child controller. API outage kiểm unavailable
và unknown-stop/quarantine/recovery protocol; daemon chung không bị crash/restart, không
claim daemon database/state-loss proof. Ownership negatives dùng container riêng; fixture
thiếu label tự hết hạn theo policy khai báo, runtime bị từ chối không xóa nó.

Các calibration/integration attempts thất bại được giữ nguyên. Gap 5,55 giây và race
sampler/remove từng bị phát hiện đã dẫn tới incomplete/quarantine rồi fresh stop-only
recovery; chúng không được đổi thành historical pass. Một startup sample unavailable
cũng được giữ cùng failure journal và cleanup outcome. Early-failure report của harness
được sửa để không phụ thuộc scanner đã khởi tạo hay chưa.

## Chạy lại

Từ package root, luôn dùng output/work directory mới:

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
.venv/bin/python scripts/remediation_w4_runtime.py --active --output /absolute/new-active-cal.json --work-dir /absolute/new-active-cal
.venv/bin/python scripts/remediation_w4_conformance.py prepare --work-dir /absolute/new-normal --calibration-report /absolute/new-active-cal.json --case normal
.venv/bin/python scripts/remediation_w4_conformance.py run --work-dir /absolute/new-normal --output /absolute/new-normal.json --expect-safety-hash EXTERNAL_LOCKED_HASH
```

Không có `--active` khi đo redirect/background workload. `phase-deviation` dùng active
calibration; các ca disabled-rule, unknown-active, inventory-drift, addon-drift,
journal-enospc và lost-start-ack dùng workload phù hợp đã pin. Input lock giữ hash của
harness/fault fixture riêng. Scripts SIGKILL/API outage, ownership và exact command
receipts nằm tại checkpoint; không áp dụng vào shared/product namespace.

Rollback dùng source-before snapshot và change-index của đúng checkpoint, chỉ khôi phục
file thuộc lượt này; không reset/stash dirty root spike, xóa evidence, backup hoặc archive.
