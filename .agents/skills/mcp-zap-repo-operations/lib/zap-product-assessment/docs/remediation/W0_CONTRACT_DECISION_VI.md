# W0 — Khóa contract và dừng tại G0

Ngày quyết định: 18/10/2026 (Asia/Ho_Chi_Minh). Phạm vi được giao: thực hiện kế hoạch remediation và **dừng khi chạm gate**. Điểm dừng đầu tiên là G0, sau khi có đầu ra W0 để kiểm tra. Không có quyết định review/approval được ghi thay con người.

## Contract đã chọn cho implementation tiếp theo

Namespace mới là `remediation/2.0`. Coverage assertion, gate result và normalized remediation plan sử dụng version `2.0`; W0 chỉ cung cấp schema cho **kế hoạch phát triển offline**. Schema assertion và verifier ngữ nghĩa được triển khai tại W1/W2, chưa tồn tại ở W0. Không đăng ký `2.0` vào legacy dispatcher trước khi reader/writer tương ứng có implementation và compatibility tests. `contracts.py` và BOLA read-only v1.4 giữ nguyên.

Normalized plan trong checkpoint là JSON canonical UTF-8 (sorted keys, compact separators); `planHash` là SHA-256 của byte chính xác, lưu ở contract lock bên ngoài để tránh self-reference. Lock còn pin schema, runtime metadata, source inventory, case index, endpoint inventory và baseline index. Thay bất kỳ pin nào phải tạo attempt/lock mới, giữ attempt cũ. Hash là kiểm toàn vẹn so với checkpoint tin cậy, chưa chống việc kẻ tấn công thay đồng thời mọi lock; semantic tamper với recomputed hash thuộc G2.

Release đích giữ **R2 đầy đủ**: API ownership/business, selected active SQLi/reflected-XSS tại sink phù hợp, browser business E2E, evidence verification, regression và alternate product đều required. R0/R1 là mức bàn giao trung gian. Nếu browser blocked thì chỉ có thể báo R2-API theo quyết định scope riêng; R2 đầy đủ vẫn chưa đạt. Native, canonical và shared/HA là các nhánh acceptance riêng. Mọi mode mới là candidate/blocked/unverified đến khi có proof đúng mode; W0 không bật mode nào.

Mẫu số operation được đối chiếu từ OpenAPI đã lưu và controller source hiện tại, không fetch schema mới. Mỗi operation × anonymous/A/B tạo một required row với trạng thái `unknown`. Đây là mẫu số discovery/operation cần được phân rã thành assertions, **không phải 57 security assertions đã có oracle**. W1/W6 phải tạo assertion IDs và resource/phase/technique bindings; không được bỏ hàng chưa đủ fixture như bills hoặc tự coi register là tested. Các technique có mẫu số riêng, không suy rằng mọi operation đều có sink SQLi/XSS. Endpoint khác semantics, thiếu route hoặc thay OpenAPI phải chặn/live-plan amendment trước run.

Assertion key bắt buộc: `assessmentId, planHash, targetBinding, buildRef, actorRef, resourceRef, operation, techniqueId, phaseId, oracleVersion`. `observed`, `requested`, `techniqueExecuted`, `oracleResult` là các field độc lập. `responseSource` là `target|guard|infrastructure|unknown`; target source cần boundary correlation với request/response, không suy từ body marker hay status. Oracle states: `pass|fail|inconclusive|not_run|not_applicable`; N/A cần rationale được khóa trước run. Unknown/missing/unsupported required proof không được vào tử số pass.

Oracle references đã chọn (định nghĩa contract, chưa claim implementation):

- `identity-binding/2.0`: actor/role proof, target/build/resource mapping và auth epoch hợp lệ tại protected request; anonymous là explicit actor, không phải fallback.
- `adapter-health/2.0`: đúng target/build binding và response body theo health contract của adapter; không suy từ HTTP 200 hoặc dùng health để bù protected coverage.
- `ownership-no-disclosure/2.0`: owner-positive trước cross-user/anonymous denial; kiểm data disclosure và post-state cho writes. Status 403/404 chỉ có ý nghĩa trong product contract; denial mà state đổi là fail.
- `business-transition/2.0`: valid pre-state, expected decimal transition, actual post-state và reload/persistence; 400 chỉ pass khi đúng validation oracle và state không đổi.
- `browser-business/2.0`: login A → create account → create expense → balance → reload → B denied read/write → A unchanged. API fixture setup không phải UI submit.
- `active-sink/2.0`: valid seed/input vector, payload correlation, sink reachability, vulnerable/fixed oracle; scanner Complete không đủ.
- `remediation-equivalence/2.0`: giữ logical scope, fixture semantics, auth/policy/input/oracle và scanner comparability giữa A/B; chỉ fix được exercise tương đương mới `remediationVerified`.

Không có danh sách status code tự cấp application-pass. Guard-only 403, auth-loss 401, login-page 200, wrong binding, thiếu positive/post-state và sai phase đều phải bị regression tests W1/W2 chặn. Counterexample lịch sử được pin trong baseline, chưa được sửa ở W0.

## Status và evidence reuse

Giữ riêng `executionStatus`, `evidenceStatus`, `securityVerdict`, `cleanupStatus`, `gateDecision`. Development gate states giữ `not_run|pass|fail|blocked|not_applicable`. Existing legacy enum không đổi ngầm. Phase failed không được đổi completed vì một assertion đã pass. Confirmed violation vẫn fail dù phase khác incomplete. Assessment exit 0/1/2/3 và root CI exit 0/1 giữ original result; mapper ở W10 cần tests trước khi enforce.

Evidence từ phase failed chỉ được tái dùng cho assertion hoàn tất **trước lỗi**, có cùng assessment/plan/target/build/actor/resource/technique/oracle, có request correlation, valid auth epoch bao phủ request, state continuity và explicit reuse record. Không tái dùng xuyên run hoặc bù required track khác; thiếu proof => inconclusive. Bundle legacy đọc historical/unknown bằng legacy dispatch; `resolved` cũ vẫn là no-longer-observed. Không tự nâng bundle lịch sử lên schema mới. W1 reevaluation phải ghi đầu ra mới.

## Thresholds khóa trước campaign

Theo kế hoạch gốc: identity poll ≤5s, request timeout ≤8s, stop producer ≤10s sau phát hiện, terminal ≤120s. Sau guard latch authLost: zero protected forwarding mới trong fixture; không suy zero traffic từ thời điểm server revocation chưa được quan sát. Sampling resource 5s; disk preflight `max(8 GiB, 2×estimatedGrowth+2 GiB)` riêng host/Docker, reserve 2 GiB; RAM 4 GiB là candidate phải calibrate W4. Unknown growth chặn live preflight cho đến calibration. Không phải SLO runtime đã chứng minh.

G3 yêu cầu zero canary matches trên sink inventory đầy đủ và 100% seeded canary controls được phát hiện; thiếu/unreadable sink blocked. Raw và encoding phải ghi inventory cụ thể ở W3/W5; W0 không claim scanner đã qua secret gate. G10 cần hai fresh runs và một interrupted run; G11/G12 cần comparator/alternate-product proof. Không thay các ngưỡng/required cases sau run để đạt.

## Baseline và authority

Source trước W0, dirty diff và untracked source được snapshot vào `.baseline/w0-…/` hạn chế quyền đọc; checkpoint chỉ giữ reference/hash. Historical artifacts được hash tại chỗ, không copy raw secret/native evidence vào bundle mới. Source snapshot loại `.env`, `.zap-auth`, runtime/runs, generated output và historical evidence; `.env.example` là source template. Raw Git diff không được đưa vào báo cáo chung.

Inventory Docker chỉ đọc các trường container/image/state và Compose ownership labels theo allowlist. Nó không chứng minh image được build từ dirty source, add-on inventory hiện hành hoặc identity target ở lớp ứng dụng. Registry pin trong `profiles/runtime-baseline.json` chỉ là candidate lịch sử; add-on inventory đã lưu được phân loại historical. Runtime campaign phải lấy pin trước/trong/sau theo G5.

W0 không có live authority record, credential reference hay target execution binding được chấp nhận. `remediation_w0.py --live` luôn trả blocked trước đọc bundle hoặc tạo process/socket. Natural expiry/authority-binding runtime negatives thuộc live entry/campaign sau G0; chưa chạy và không được đánh pass bằng kiểm tra hash. Không chuyển authorization lịch sử thành quyền mới. Scope công việc hiện tại cho phép chỉnh source/contract và offline tests; chưa chạy login, mutation, crawl, active hay Docker lifecycle.

## Gate, reforecast và tiếp tục

Checkpoint G0 báo riêng offline development readiness và live readiness. Dù offline checks pass, dừng tại G0 theo yêu cầu người dùng; W1–W11 chưa chạy. Independent review pending là trạng thái thực, không giả lập approval. Khi tiếp tục, đọc lại pins; drift tạo checkpoint mới trước bước phụ thuộc.

Reforecast sau W0: chưa có thay đổi scope R2 hay gate acceptance. W1–W11 vẫn còn khoảng 24–38 ngày công theo tổng ước lượng trong kế hoạch; đó là forecast cho một kỹ sư, không suy từ thời gian chạy script. Native/canonical/shared và thời gian chờ quyền/môi trường tính riêng. W0 mới chuẩn bị contract và kiểm chứng offline, chưa có campaign feasibility/auth/secret/product proof; phải reforecast lại ở W3/W5 và ngày đầu W7. Chi phí thực của lượt này được ghi bằng timestamp checkpoint, không biến elapsed time thành ngày công chuẩn.

Lệnh tái kiểm tại package root: `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_remediation_w0.py'`; sau đó `.venv/bin/python scripts/remediation_w0.py /absolute/checkpoint`. Các lệnh chỉ đọc checkpoint, không ghi vào bundle lịch sử. Rollback W0: bỏ các file W0 mới khỏi checkout nếu cần; baseline giữ lại. Không reset/stash dirty changes hoặc rollback về predicate coverage sai để allow.
