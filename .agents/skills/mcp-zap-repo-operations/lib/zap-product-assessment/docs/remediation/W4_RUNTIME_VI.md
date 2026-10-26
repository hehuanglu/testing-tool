# W4 — Policy, resource preflight và evidence partial

**Historical checkpoint:** floor8GiB và giới hạn live nêu dưới đây thuộc lượt trước. User đã bỏ floor8GiB ngày19/10/2026; xem [trạng thái live hiện tại](W4_LIVE_CONTINUATION_VI.md). Giữ kết quả cũ theo source/time, không đổi raw evidence.

Tiếp tục từ W3. Phạm vi implementation và kiểm chứng development: tái sử dụng executor/runtime/journal/egress, không tạo executor hay engine thứ hai. P0 native/delegated/business vẫn bị chặn, v2 publisher vẫn verification-only. W4 không chạy HTTP/login/scan/write vào finalsource hoặc thay contract read-only BOLA.

## Policy gate

`runtime_safety.EffectivePolicy` khóa đầy đủ add-on/version, active-rule IDs/enabled, script name/type/enabled/content SHA và input vectors. So sánh inventory trước/trong/sau run; thiếu field, duplicate ID, drift hoặc thiếu snapshot không được pass. Rule disabled nhưng vẫn phát traffic là violation nếu không thuộc expected enabled set, kể cả scanProgress báo Complete. Passive/background/crawl/import/seed/control được đếm riêng. Unknown attribution, thiếu boundary correlation, forwarding sai scope/credential hoặc vector bị guard biến đổi mà chưa có proof tương đương đều block. Không dùng rule count hoặc enabled=false làm proof không có traffic.

`SafetySupervisor` kết nối gate với executor hiện có. Trước producer work phải có inventory và complete egress capture; watchdog yêu cầu khoảng cách mẫu hoàn tất không quá5s (bắt đầu sớm1s để dành thời gian đo), latch lỗi và phát một bounded stop đúng runtime. Sau latch không chạy intent mới. Finalization đòi inventory/traffic cuối trước cleanup và publication. `provenance.runtimeSafety` giữ contract hash và audit trong bundle v1 của fixture đã có đủ proof. Kết quả policy không tự cấp technique-verified hoặc security approval; active-sink assertion thuộc W8.

**Giới hạn integration hiện tại:** `DockerRuntime.policy_inventory` đọc API thật, không bịa script source hash nếu engine không cung cấp; thiếu hash dẫn đến blocked. `policy_traffic` hiện trả complete=false vì guard legacy thiếu independent producer/rule correlation. Do đó runtime thật bị chặn trước producer mới; controller fixture có capture riêng chỉ chứng minh logic gate. G5 operational chưa đạt. Cần collector/hook runtime có source proof đúng mode trước khi mở execution, không điền boolean correlation từ lời tự khai của scanner. Một tập data giả nhưng nhất quán với trusted contract vẫn không có independent signed wire attestation.

Input-vector options dùng các API `optionTargetParamsInjectable`, `optionTargetParamsEnabledRPC`, `optionAddQueryParam` theo [ZAP API reference](https://www.zaproxy.org/docs/api/). Script hash không chứng minh chỉ từ tên/file path; W4 không gỡ scripts trên scanner dùng chung. Không có scanProgress-only fallback.

`egress.policy_target` tái sử dụng origin/Host/anonymous/method guard và exact allowed-path policy của bound guard. Redirect được trả về cho caller; hop tiếp theo phải qua guard, không tự follow. Guard writer fsync và latch lỗi ghi; request mới sau latch bị từ chối trước forwarding. Log không ghi URL/header/credential values. Requests đang in-flight trước phát hiện vẫn là khoảng không chắc chắn, không claim zero traffic hồi tố.

## Resource contract và preflight

`runtime-safety/1.0` là sidecar được pin bằng SHA canonical JSON bên ngoài. Nó khóa planHash, sourceDigest, runtime image pins, growth/calibration, policy, sampling5s, reserve2GiB, candidate RAM4GiB và stop budget≤120s. Không thay schema/version/meaning của bundle/plan v1.0–v1.4; v2 runtime chưa được bật.

Preflight đòi riêng host artifact filesystem và Docker storage: free≥max(8GiB,2×estimatedGrowth+2GiB). Trong run, free≤2GiB hoặc Docker unavailable/missing measurement/RAM dưới candidate gây latch, block work mới và stop có giới hạn. Equality8GiB ở preflight được chấp nhận; equality2GiB trong run bị chặn. Sampling là cơ chế giám sát, không ngăn được ENOSPC xảy ra giữa hai mẫu; timestamps thực được journal giữ và chưa có SLO đầy đủ cho engine.

Không chấp nhận growth số dương chỉ kèm một checksum tự khai. Calibration reference phải là absolute canonical regular metadata file, không symlink/hardlink,≤1MiB và đúng byte hash. Kiểm source/image/workflow binding, scanner-topology measurement kind, startup/crawl/settle/report/cleanup, timeline tăng, estimate bao phủ quan sát và measured peak phù hợp candidate4GiB. Hash vẫn cần trust anchor thực của operator; không xác nhận nguồn đo chỉ từ metadata. Test metadata fictitious được giữ trong fixture riêng, không dùng để mở live mode.

`DockerRuntime.resource_sample` đo host bằng statvfs; Docker filesystem/VM MemAvailable bằng helper image đã pin, network=none, read-only root, memory32MiB/pids32. Probe không tạo scanner hoặc gửi traffic; intent/name/image pin được lưu trước tạo, kết thúc được xác nhận và lost ACK chỉ reconcile stop, không replay. Một probe đo kernel của Docker Desktop không phải đầy đủ calibration growth của ZAP/browser. Read-only metadata không đổi Docker context/topology.

**Kết quả thật W4:** kernel fault fixture trong tmpfs8MiB qua ENOSPC, root read-only qua EROFS, RLIMIT_FSIZE tạo short-write/EFBIG; reserved stop frame còn đọc được sau ENOSPC và không có final artifact name giả. Resource sample/peak của fixture nhỏ được ghi riêng. Đây chưa là full scanner workload/RAM calibration; không đổi candidate4GiB thành threshold đã chứng minh cho mọi topology. G6 operational còn blocked cho đến khi đủ calibration và runtime fault matrix đúng mode.

## Journal, atomic writer và kênh dự phòng

`safety_io.atomic_bytes` lặp đến khi ghi đủ, chặn zero-progress, fsync, đọc lại exact bytes trước no-clobber link vào final name và fsync directory. Failure giữ staging/partial, không tạo final file từ bytes chưa đủ. `evidence.write_file` dùng primitive này cho các version hiện hữu. Publication vẫn verify bundle trước rename. Nếu lỗi sau rename, executor thử chuyển sang quarantined-publication và giữ block; storage failure ngăn cả quarantine được ghi publicationStatus=quarantine-unconfirmed, không tự cấp allow/reuse.

`ReservedStop` cấp trước64KiB với hai slot độc lập có seq/hash, identity run/plan và trạng thái tối thiểu, không phải manifest complete. Khi filesystem đầy, có thể overwrite vùng đã cấp; torn slot mới nhất còn slot trước để đọc. Nếu storage/dump hoàn toàn unavailable, kênh này cũng có thể mất khả năng ghi; kết quả phải unconfirmed, không hứa durability trước mọi lỗi thiết bị. Không có secret hoặc raw exception trong frame.

Journal append được khóa giữa controller/watchdog, ghi đủ bytes+fsync, latch io_failed; lỗi kéo dài không được ngăn stop. Executor bắt lỗi cả trong nhánh cleanup và dùng reserved frame ghi clean/incomplete/secretIntegrity. Partial nằm ở `partial-evidence/status.json` và journal-prefix, không có complete manifest. Thiếu khả năng lưu partial vẫn có reserved frame đã cấp trước nếu storage còn hỗ trợ overwrite. EROFS chặn cả overwrite được giữ incomplete/unconfirmed.

## Ownership, stop và recovery

Container cần đúng run label, creation intent, container ID sau ACK, immutable expected image ID; mất ACK mà thiếu image proof không được suy ownership chỉ từ tên. Auxiliary measurement/fault containers cũng phải được stop. Missing label, changed ID/image hoặc thiếu identity thì từ chối delete. Borrowed content volume cần creation ACK/timestamp đúng; lost volume ACK thiếu pin được giữ lại, không xóa đoán. Deadline được truyền xuống Docker inspect/stop/remove và không tự restart/prune daemon.

Recovery dùng executor.recover hiện có, **stop-only**. Chỉ cho bỏ dòng cuối không có newline trong bản journal recovery; corrupt middle/hash/envelope không được bỏ qua. Original journal/bundle giữ nguyên. Recovery tạo file `recovery-journal-<id>.jsonl` mới từ verified prefix, ghi original hash/partial-tail disposition rồi stop exact owned resources; không reissue scan/import/mutation. Thiếu intent sau torn write vẫn block ownership. Secret-integrity quarantine kiểm cả journal và reserved frame, không được generic recovery xóa. Recovery record mới không sửa thất bại hoặc evidenceStatus của run gốc.

## Entry point và cách tái kiểm

Live anonymous Executor bây giờ bắt buộc safety contract+external pin; thiếu calibration block trước Docker provisioning. Product pilot có `--safety-contract` và `--expect-safety-hash`, ngoài authority/plan pin sẵn có. Contract hợp lệ chưa đủ: missing script pin/egress capture cũng block trước producer. Không có override. Planning, verification và stop-only recovery không đòi safety contract mới để làm việc đọc/dừng an toàn. BOLA entry riêng giữ admission riêng; shared atomic writer được harden và có regression, không thêm writes hay ZAP vào BOLA.

Từ package root:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_runtime_safety.py' -v
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/remediation_w4_campaign.py --output /absolute/fresh-result.json --work-dir /absolute/fresh-private-workdir
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
```

Campaign cần image boundary đã có; không pull/build/restart shared service, target HTTP=0. Controller policy/daemon-loss records là simulated; kernel storage faults là thật. Shared container ID/image/StartedAt trước/sau và absence của owned resources được kiểm. Một lần development tìm ra auxiliary container chưa được stop; đã sửa, thêm regression và reconcile đúng resource rồi giữ attempt cũ.

Gate record/checkpoint W4 ghi tests, actual commands/exit, source/image/calibration limits, preservation và reviewer pending. Development pass không đồng nghĩa G5/G6 runtime acceptance. Còn thiếu production-grade runtime correlation, full scanner calibration/fault matrix và G3/G4; không mở delegated/native chỉ vì unit/fault fixture đạt. Tiếp theo là nối collector đúng mode và W5 auth/secret lifecycle trên runtime đã qua các prerequisite. Scope R2/browser và thresholds W0 không thay đổi.
