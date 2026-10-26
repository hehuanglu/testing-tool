# W5 — resource profile đo được và canary source cô lập

Ngày19/10/2026. [Checkpoint](../../../test-artifacts/mcp-zap-remediation/w5-resource-20261019T084619Z/HANDOFF_VI.md). Đây là continuation của W5 scanner; W5/R1 operational vẫn blocked khi còn thiếu G3/G4. Không đổi acceptance thành all-pass từ fixture hoặc independent approval.

## RAM và storage

ResourceGate mặc định vẫn yêu cầu4GiB khả dụng. Method `required_ram(preflight)` cho phép W5 calibration subclass riêng; chỉ profile owned-synthetic được dùng3GiB preflight và1,5GiB during-run. Sampling5s, disk reserve2GiB và terminal120s không đổi. Đây là candidate cần đo theo workload, không áp vào production/borrowed/browser.

Hai run calibration A/B đầu có115 readings/run từ startup tới cleanup. Peak riêng lẻ của các workloads cộng lại khoảng787MiB/785MiB; max concurrent `memory.current` quan sát khoảng668MiB/671MiB. Đây là cgroup charges có thể gồm file cache, không phải host RSS hoặc peak toàn VM; measurement helper32MiB không nằm trong tổng này. Native runs vẫn còn trên4GiB VM MemAvailable, nên không được coi là stress test tại ngưỡng1,5GiB.

Persist `memory.current`, `memory.peak`, `memory.events`, immutable container ID, limit, OOMKilled và stopped/removed cache. Sampler dừng khi Docker ghi OOM/oom_kill. Verifier đối chiếu metric với gate sample, RAM threshold đã khóa, creation ACK, peak monotonic, ownership và artifact budget; thiếu OOM fields hoặc sửa số rồi tính lại checksum vẫn phải block. Negative container64MiB/no-swap cấp phát512MiB bị kernel kill137 và sampler block; cleanup chỉ namespace đó.

Profile v1 dùng cap368MiB từ retained snapshots với margin; nó không claim lịch sử đã đo peak. Profile v2 pin hai gate-results A/B cùng115 raw readings, max host artifact logical growth190.052.439 bytes/190.008.091 bytes. Lấy125% maximum, làm tròn lên64MiB => **256MiB cap**. Preflight giữ công thức `2×growth +2GiB reserve`, nên host cần **2,5GiB**, Docker storage vẫn theo estimate1GiB+reserve. Cap logical artifact được enforce trong run. Schema v1 vẫn đọc được với budget cũ; không sửa historical gates hay giảm disk reserve.

## Cache clone giữ evidence

Một thử nghiệm clone các static library copies trong completed/stopped W5 artifacts giữ nguyên bytes/SHA/path và regular files nlink1, có CoW control.75 files với468.674.085 logical duplicate bytes được thay bằng APFS clone; filesystem free không tăng đáng kể tại lúc đo. Không coi con số logical này là reclaimed disk. Không prune Docker/APFS snapshots hoặc xóa evidence. Receipt đầu do host Python không có os.listxattr được giữ; dùng native xattr comparison trước atomic replacement.

Để tránh phát sinh thêm bản vật lý trong run mới, profile v2 preseed **chỉ94 pinned image library/driver files (~162MiB logical)** vào fresh owned ZAP home bằng clonefile. Mỗi source file phải có exact SHA trong precredential image-cache baseline và được hash lại; không clone session DB, preferences, keys, logs hoặc credential. Clone là inode riêng có CoW, không dùng hardlink/symlink. Artifact audits vẫn đọc/hash bytes bình thường. OS thiếu clonefile hoặc cache hash đổi thì blocked, không fallback âm thầm sang storage assumption khác. Resource budget vẫn tính logical bytes, hostFree đo vật lý thực; không bảo đảm ngăn mọi ENOSPC bằng sampling.

## Private canary source

Guard sinh hex64 seed trong runtime128MiB có memory-swap bằng memory, core limit0, readonly root và UID-private socket tmpfs. Host không tạo/gửi seed/password/token qua Docker exec stdin. `auditor-bind` chỉ trả204 SHA256/length comparisons cho67 private canaries và một public JDBC control. Binding có runId/planHash/hash của inventory trong auth-source.jsonl; bind lần hai và boot nhận seed do host cung cấp đều bị từ chối. Token minting bị giới hạn64 để không có token nằm ngoài comparison inventory.

`OpaqueCanaryAuditor` chỉ nhận hashes/lengths. Nó reuse2 decoding steps, tối đa128 decoded views/step, và matcher cho đúng family hex64/W5-canary-HMAC.816 source-internal controls gồm raw, base64 standard/URL/padded/unpadded, mixed percent, JSON escapes và embedded/nested examples phải detect100%. Không serialize source values trong controls. Comparator không có `_secrets` chứa raw values.

Đây là family high-entropy synthetic canary, **không phải generic real-password/JWT resolver hoặc production broker**. Không xuất hash của password thật để thay source isolation; real credential routing/auditing vẫn cần private broker/source-reference contract. Report/envelope có private canary phải fail/quarantine; không xuất value vào summary. JDBC TEXT/BINARY positive control hiện là public test value, không được tính thành actual private source control cho mọi sink.

## Kiểm chứng và giới hạn

Private-source diagnostic chạy container riêng network=none: real loopback login/identity, refresh epoch, reject host seed, revoke, natural TTL, SIGKILL và readback filesystem/log/argv/env/mounts sau stop bằng comparison hashes. Nó không chứng minh ZAP/MCP protected forwarding. Native opaque A/B campaign riêng phải pin fresh source/plan và chạy lại đủ15 cases; readback yêu cầu source binding, controls, traffic/actor/epoch, resource và DB receipts. Native crash vẫn chỉ kill credential holder sau producers terminal.

Full suite mới327 tests; receipts và native outcomes cuối xem handoff. Tests cũng kiểm metadata không chứa source values, arbitrary secret family/inventory bị từ chối, embedded/nested forms và compression reader dùng opaque comparator.

G3 operational vẫn thiếu generic production source/broker và actual seeded controls/access/decoder/lifecycle đầy đủ13sinks×11lifecycle. Source controls và zero matches trong các sink đã đọc không tự thay đủ matrix. Independent review/R1 chưa được cấp.

## Amendment scope tester theo người dùng

Người dùng xác nhận không có contract nội bộ và cho phép bỏ nghiệp vụ không thể kiểm của sản phẩm. Skill đã có [auth discovery](</Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/references/auth-capability-discovery.md>): tự khảo sát API/UI/nguồn có sẵn trong quyền hiện tại, chọn business probe và phân biệt local logout với server invalidation. Không yêu cầu contract làm điều kiện bắt đầu discovery; không bắt buộc endpoint tên whoami nếu có identity oracle độc lập tương đương.

Auth discovery must preserve source-supported and runtime-unverified states separately. Do not reuse prior product discovery or credentials as current evidence.

Khảo sát và luồng skill trong scope tester đã hoàn tất. Full product G4 chưa được chứng minh; skip tính năng sản phẩm không bỏ prerequisite secret của mode. Native/delegated protected operational admission và R1 vẫn blocked bởi G3. Không sửa sản phẩm để tạo tính năng cho checklist, không bỏ assertion đã quan sát thất bại.
