# W5 — checkpoint auth lifecycle và canary auditor

Ngày 19/10/2026. Checkpoint: `test-artifacts/mcp-zap-remediation/w5-20261019T052028Z`.
Attempt hiện tại: `synthetic-campaign-v3`; các attempt trước được giữ nguyên.

Continuation mới: [scanner/DB readback và blockers W5](W5_SCANNER_CONTINUATION_VI.md). Kết quả dưới đây giữ nguyên scope lịch sử của checkpoint đầu.

**Trạng thái: development primitives đã kiểm chứng; W5 tổng thể chưa hoàn tất.**
G4 synthetic và auditor text controls đạt expected outcomes. G3 delegated operational,
G4 finalsource product và R1 vẫn blocked. Không có quyền mới được tạo từ registry.

## Thay đổi

`auth_lifecycle.py` chuyển auth state thành một session riêng cho từng actor/run/plan/build.
Mỗi protected request có identity proof khớp subject/role/build trước forwarding;
monitor kiểm identity với poll interval tối đa 5 giây. Mất identity,401,login HTML200,
role/build drift, transport exception hoặc lỗi journal đều bỏ token và latch.
Khóa serialize identity/forward/refresh/loss: sau latch không nhận protected work mới.
Khoảng giữa hai proof và giữa identity đến response vẫn uncertain; không suy rằng
revocation đã được quan sát tức thời. Timeline ghi monotonic timing và in-flight intent.

Refresh phải được contract cho phép, có identity còn sống trước refresh, rồi kiểm lại
identity của token mới trước admission; epoch mới không dùng proof của epoch cũ.
Chưa có refresh sau expiry hoặc refresh-token protocol. Logout latch trước target call;
revoke/logout không có automatic login lại. Restart chọn fail-stop, token không được
serialize/resume. Explicit bootstrap của một session mới phải kiểm identity lại.

Producer stop chạy ở worker riêng để producer đang phát hiện auth-loss có thể thoát
khỏi forwarding lock. Callback phát stop có budget tối đa10s, terminal tối đa120s;
không xác nhận thì `stopUnconfirmed/quarantine`. Worker timeout không có nghĩa callback
đã bị cancel. Lỗi writer giữ trạng thái loss/stop trong memory snapshot, không giả durable
journal đã lưu thành công. Đây chưa thay reserved channel/resource gate G6 trên scanner.

`finalsource_p0_guard.State(..., lifecycle=session)` có seam development dùng lõi mới,
không mở file credentials cũ, không cho actor marker chéo, không nhận business/control
bypass hoặc UI/static transport. `serve()` và P0 CLI vẫn bị chặn trước credential/socket/
Docker theo W3. API injection seam không phải protected runtime admission.

## Bằng chứng thực chạy

Fixture HTTP chỉ bind loopback port động; credential/token canary sinh trong memory.
Server thực thi short TTL, revoke và role change; expiry không phải đổi chuỗi token.
Các case kiểm login failure, invalid token, expiry, live refresh thành công/thất bại,
logout/revoke, wrong actor/role/build,401/login200, secret echo/cookie, exception,
writer failure, cancel, concurrent in-flight loss và stop timeout/exception.

Producer HTTP fixture chạy thật và xác nhận kết thúc. Child process được SIGKILL thật,
restart khi target session còn sống hoặc đã hết hạn đều không resume credential.
`RLIMIT_CORE=0` được đọc lại ở child; đây không chứng minh host swap, OS diagnostics,
scanner dumps hoặc MCP restart. Stop callbacks mặc định ở các case state-machine là
đối chứng fixture; không được gọi là đã stop ZAP operation.

Campaign chạy48 test functions:29 auth/HTTP/process cases,11 auditor cases và8 guard
compatibility cases cũ. Auditor seeded controls phủ13 tên sink ×11 lifecycle ×12 dạng
encoding =1.716 text controls. Raw UTF-8, standard/URL base64 padded/unpadded, percent
upper/lower/mixed, JSON escaping/unicode và các dạng nested được kiểm có giới hạn.
Chỉ giải mã tối đa2 bước,128 candidate chunks/lượt; không claim universal decoding.

Tên sink gắn cho file text seeded không biến file đó thành ZAP history/session DB
hoặc browser/crash artifact thật. Auditor từ chối missing pair, duplicate, unreadable,
symlink parent/file, hardlink, FIFO, traversal, oversized, invalid UTF-8 và decoder DB
chưa có. Binary/compressed database cần decoder và access proof riêng. `auditStatus`
clear không thể tự tạo G3 pass; thiếu sink vẫn blocked.

Attempt đầu lỗi child import vì CLI được gọi không có `PYTHONPATH`; source được sửa
để truyền module path rõ ràng vào owned child. Attempt v2 đã pass; v3 bổ sung containment
UI/static và xử lý writer failure trong stop worker, sau đó chạy/readback lại. Không sửa
failure cũ. Không coi ba attempt là ba lần acceptance độc lập trên cùng source.

## Chạy và đọc lại

Từ package root, dùng work directory mới. Lưu hash trả về ở bước prepare bên ngoài plan:

```sh
.venv/bin/python scripts/remediation_w5_campaign.py prepare --work-dir /absolute/fresh-w5
.venv/bin/python scripts/remediation_w5_campaign.py run --work-dir /absolute/fresh-w5 --expect-plan-sha256 HASH_FROM_PREPARE
.venv/bin/python scripts/remediation_w5_campaign.py verify --work-dir /absolute/fresh-w5 --expect-plan-sha256 HASH_FROM_PREPARE
PYTHONPATH=src:tests .venv/bin/python -m unittest test_auth_lifecycle test_secret_audit test_w5_campaign test_finalsource_p0_guard -q
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
```

CLI không nhận target/credentials/Docker flags. Plan lock pin implementation, tests,
schema và expected cases trước mở fixture. Một attempt không được chạy lần hai; source
drift yêu cầu fresh prepare. Readback kiểm SHA, external lock, case inventory, event
bindings, epoch và target arrivals sau latch mà không gọi lại `ActorSession`. Test tamper
sửa artifact rồi recompute checksum vẫn bị từ chối. Đây là consistency verifier của
development harness, không thay semantic verifier assessment G2 hoặc operational G3.
Readback không cần network; exit0 giữ `gateDecision=block`, security=inconclusive.

## Phần còn thiếu và reforecast

1. Nối candidate vào scanner riêng có G5/G6, contract actor/epoch và producer ownership
   thật; không mở P0 credential-copy provision path. Chạy canary login/crawl/active,
   expiry/refresh-failure/exception/cancel/restart/crash/cleanup trên pipeline đó.
2. Xác minh13 operational sinks và decoder thực tế, process argv/tool envelopes, ZAP
   history/session DB, logs/report/export, browser/profile (hoặc absence proof đã khóa),
   crash artifacts. Hiện cả143 sink/lifecycle pairs được ghi missing proof, không loại
   khỏi mẫu số. Không dùng text controls hoặc kiểm report để bù phần còn thiếu.
3. Chốt adapter finalsource identity/role/TTL/refresh/logout/revoke contract và authority
   runtime còn hiệu lực trước product proof. Unsupported endpoint phải ghi đúng scope;
   synthetic không thay product acceptance. Không cần credential thật để làm hai bước đầu.
4. Chỉ sau G3/G4 operational pass mới xem xét admission R1; độc lập human/security review
   vẫn pending. Native/browser/canonical/shared không kế thừa synthetic outcome này.

Reforecast W5: lượt này làm generic primitive, fixture, auditor, schema/campaign/readback
và regressions; timestamps/commands lưu ở checkpoint, không đổi elapsed thành ngày công.
Ước lượng còn lại cho W5 khoảng2–4 ngày công, phụ thuộc access/decoder ZAP DB/dumps và
khả năng ghép scanner G5/G6; product endpoint/authority chưa chốt có thể tăng forecast.
W6–W11 vẫn khoảng14–22 ngày công theo kế hoạch; N/C/H tính riêng. R2 đầy đủ vẫn giữ UI
required; không đổi gate, threshold hoặc release scope để vượt blocker.

Rollback chỉ các file mới/đã sửa được liệt kê trong checkpoint change-index; snapshot
source-before nằm trong `.baseline/w5-20261019T052028Z`. Giữ evidence/failures và root
dirty JSON-bearer spike; không reset/stash, xóa secret evidence hoặc publish/merge.
