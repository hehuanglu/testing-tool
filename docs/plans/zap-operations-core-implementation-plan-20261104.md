# Kế hoạch triển khai lõi vận hành MCP ZAP

Ngày: 2026-11-04. Workspace: `/Users/hahoangloc/Working/testing tool`.

**Người thực hiện:** Sol trong context mới. **Loại nhiệm vụ:** sửa skill và thư viện hỗ trợ, kiểm thử offline; không vận hành assessment sản phẩm. **Người nghiệm thu hành vi sau triển khai:** người dùng sẽ giao lại cho agent audit. Sol không tự tuyên bố đã nghiệm thu khả năng vận hành xuyên nhiều chat.

## 0. Mục tiêu và quyết định đã chốt

Triển khai ba phần:

1. Trạng thái chính thức có định danh, snapshot và commit có thể khôi phục; sửa giao dịch lease/journal và retry merge.
2. Chọn việc tiếp theo bằng dữ liệu dependency, block, pending effect, resource và deadline; cung cấp lý do lựa chọn.
3. Ghi nhận sửa công cụ thành nhiệm vụ riêng, có reproduction, phạm vi, verification và điều kiện trở lại assessment.

Đây là kế hoạch triển khai cụ thể. Không mở lại vòng tranh luận kiến trúc, không viết thêm một kế hoạch thay thế, không yêu cầu người dùng quyết định các chi tiết đã chốt bên dưới. Khi source đã thay đổi, đối chiếu bằng hành vi/test và chỉ điều chỉnh điểm tích hợp cần thiết; ghi deviation trong báo cáo cuối. Nếu có xung đột thật làm thay đổi quyền, scope hoặc tính an toàn, giữ phần đó chưa triển khai và hoàn thành các phần độc lập.

**Quyết định kiến trúc:** tiếp tục Python stdlib + JSON + journal hiện có, không thêm database, framework workflow hay daemon. Giữ `criteriaWorkflow.version=2`. Thêm store version 1 và operator-state version 1 nằm ngoài nội dung approval-bound. Giữ executor callback và reviewer hiện hành. Selector chỉ quyết định công việc offline; không tự dispatch, login, mở browser, cài automation hoặc gửi request.

Không tách thành nhiều skill mới trong đợt này. Làm cơ chế chung trước; sửa skill hiện hành để dùng cơ chế đó. Không đổi hai gate, `all_cases`, yêu cầu provenance, no-replay, TTL readback ở nhóm cuối, một Sheets cuối lượt và quyền sharing do user quản lý.

## 1. Context bắt buộc đọc và phạm vi chỉnh sửa

Đường dẫn gốc:

```text
SKILL = /Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations
LIB   = SKILL/lib/zap-product-assessment
SRC   = LIB/src/zap_assessment
TESTS = LIB/tests
AUDIT = /Users/hahoangloc/Working/testing tool/docs/reviews/zap-operations-audit-20261103
PYTHON = /Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python
```

Đọc theo thứ tự:

1. `SKILL/SKILL.md`; các reference `assessment-policy.md`, `retention-stop-and-recovery.md`, `business-work-blocks.md`, `local-remediation-and-continuation.md`, `operational-validation.md`.
2. `AUDIT/recovery-findings.md`, `recovery-repro.py`, `selector-repro.py`; `audit.md` mục F01–F11, F20–F21, F26, F29, F31. Không cần nạp toàn bộ chat evidence vào context.
3. `SRC/criteria_delegation.py`, `journal.py`, `safety_io.py`, `criteria_workflow.py`, `criteria_resume.py`, `product_scope_cli.py`; đọc caller liên quan khi sửa chữ ký.
4. Các tests nêu ở mục 11 trước khi đổi implementation.

Working tree đã dirty và có nhiều file untracked trước nhiệm vụ. Không reset/stash/clean/checkout ghi đè; không xóa lịch sử. HEAD audit là `18f17860bad327a18345f949644aac4d40b7fece`, nhưng đối tượng triển khai là **working-tree bytes hiện hành**. Ghi baseline `git status`, digest các file sắp sửa và kết quả tests trước sửa. Không coi toàn bộ diff hiện có là thành quả của mình. Tìm AGENTS áp dụng từ thư mục cha; nếu có, đọc trước khi sửa.

Không sửa các RUN thật trong `.zap-20261103-4qUdAo`, `.zap-skill-acceptance-20261103-w1`, `.private-zap-runs`, không chọn hộ RUN nào để promote. Không đọc secret raw nếu không cần. Migration/registration chỉ thử bằng fixtures hoặc bản sao sanitized do test tạo. Không Docker restart, không scan, không Drive write, không đồng bộ personal skill installation, không commit/push trong nhiệm vụ này.

## 2. Lỗi nền phải bảo toàn khi sửa

Các reproduction hiện tại chứng minh:

- R1: journal `released` trước khi unlink hết lease; ngắt giữa hai unlink khiến resume và retry đều lỗi.
- R2: lease đã durable nhưng chưa có `leased` journal tạo orphan; API acquire/release/reviewer không khôi phục được.
- R3: append đã ghi nhưng trả lỗi, exception handler xóa lease; journal vẫn coi task active.
- R4: record cuối journal bị ghi dở làm status/review/recovery strict đều thất bại.
- R5: `criteria-merge --output` lặp cùng nội dung bị `FileExistsError`; canonical promotion do operator tự làm.
- Selector: T1 phụ thuộc T2 chưa xong nhưng T1 vẫn được chọn do sort ID.

Giữ các invariants:

- Action có durable intent không được dispatch lại, kể cả thiếu ACK hoặc callback trả lỗi.
- Recovery không tạo permission; plan/source consent/digest/actor/fixture/admission vẫn kiểm tra như cũ.
- ACK không đồng nghĩa terminal, effect đã dừng hoặc evidence đủ.
- Một thao tác `violated` có thể hoàn tất testing dependency; không yêu cầu sản phẩm pass mới được đi tiếp.
- Lease không hết hạn theo worker timeout; không reclaim theo mtime/PID chết.
- Không nới context equality/semantic checks để tests xanh.
- Report projection không trở thành executable RUN.
- Source/config được dùng theo method đã duyệt, nhưng không biến thành ZAP-derived/native alert.

## 3. Bản đồ file sẽ triển khai

Thêm module nhỏ, trách nhiệm tách rõ:

- `assessment_store.py`: registry, immutable generations, current pointer, CAS commit, idempotent commit receipt, readback verification. Không import executor.
- `operator_state.py`: schema/validation cho blocks, work items, dependency, repair tasks, delivery receipt và projection. Không suy luận verdict.
- `operation_selection.py`: hàm thuần chọn việc và sinh reason codes từ snapshot + review + coordinator inspection + thời gian được truyền vào.
- `assessment_state_cli.py`: parser/handlers nhóm lệnh `scope state-*`, gọi các module trên. `product_scope_cli.py` route vào đây để tránh nhồi hết logic.

Sửa module có sẵn:

- `criteria_delegation.py`: giao dịch acquire/release, transaction recovery và inspect; giữ entrypoint cũ tương thích.
- `journal.py`: inspect prefix hợp lệ + diagnostic có cấu trúc, giữ strict reader mặc định; không bỏ kiểm tra hash/seq/run/plan.
- `safety_io.py`: thêm primitive replace nhỏ có fsync directory; không đổi no-clobber semantics của `atomic_bytes`.
- `criteria_resume.py`: dùng selection engine, giữ fields tương thích hiện có.
- `product_scope_cli.py`: CLI legacy merge retry, lựa chọn managed store và route lệnh mới.
- `criteria_workflow.py`: chỉ refactor nếu cần tách review thuần và coordinator inspection; không đổi quy tắc verdict/completion.

Tests mới: `test_coordinator_recovery.py`, `test_assessment_store.py`, `test_operator_state.py`, `test_operation_selection.py`, `test_assessment_state_cli.py`. Bổ sung tests cũ theo caller thay đổi.

## 4. WP1 — Giao dịch lease/journal có thể tiếp tục sau ngắt

### 4.1 Lock và event model

Giữ `Coordinator.locked()` theo assessment và reentrant semantics. Thêm lock `resources.lock` tại coordinator root để serialize thay đổi lease dùng chung giữa các assessment. Thứ tự cố định: assessment lock → resources lock. Không bao giờ đảo thứ tự. Chỉ giữ resources lock khi inspect/write/unlink lease; không giữ qua callback/network.

Việc đọc ownership thông thường không được tự repair. Không có quyền sở hữu chỉ từ cùng target URL; tiếp tục dùng resource ID ổn định.

Thêm event kinds, mọi event có transaction ID và binding đầy đủ:

```text
lease_acquire_intent {transactionId, assessmentId, taskId, workerId, packetDigest, resourceIds}
leased               {transactionId, ...binding, resourceIds}  # commit như event cũ
lease_acquire_aborted {transactionId, ...binding, resourceIds, reason}
lease_release_intent {transactionId, ...binding, resourceIds}
released             {transactionId, ...binding, resourceIds}  # commit sau cleanup
```

`transactionId` deterministic theo action kind + binding + resource list; cùng retry dùng cùng ID. Packet task ID không được tái sử dụng sau release cho attempt mới. `leased`/`released` cũ không có transactionId vẫn đọc theo legacy rules.

Không dùng generic “ignore validation error”. Tách validation packet/approval thuần khỏi operational review để recovery của giao dịch chưa hoàn tất không bị chính orphan check chặn. Fresh dispatch vẫn cần full reviewer/admission. Recovery dùng digest packet gốc và durable binding như `_recovery_binding`, cho phép sau stop/revision nhưng không phát effect.

### 4.2 Acquire algorithm bắt buộc

1. Validate current approval, packet và coordinatorState; lấy locks theo thứ tự.
2. Đọc journal strict; kiểm tra retry transaction. Nếu đã commit cùng binding, xác minh lease rồi trả receipt `alreadyApplied=true`.
3. Nếu task đã released/aborted hoặc binding khác: từ chối; không hồi sinh task cũ.
4. Inspect toàn bộ resource trước khi ghi. Foreign binding → trả conflict, không xóa/thay lease của người khác.
5. Append/fsync `lease_acquire_intent` **trước file lease đầu tiên**. Nếu append báo lỗi, dừng; không dispatch và không xóa gì để “rollback”.
6. Tạo các lease còn thiếu bằng no-clobber primitive; file đã tồn tại chỉ được chấp nhận khi full binding khớp. Ghi và verify từng file.
7. Append/fsync `leased`; sau đó mới trả success. Không dispatch nếu commit append thất bại.

Nếu lỗi/kill sau bước 5: giữ durable state. `recover_transactions(packet)` hoàn tất phần lease còn thiếu và commit khi intent có integrity, binding hợp lệ và không có foreign conflict. Recovery này chỉ hoàn tất claim tài nguyên, không phát request. Nếu không thể acquire vì foreign conflict: chỉ rollback lease đúng transaction sau khi chứng minh transaction chưa commit, không có action intent, rồi append `lease_acquire_aborted`; ghi rõ conflict. Không rollback khi journal không đọc chắc được.

R3: append có thể ghi xong rồi raise. Khi retry phải đọc lại durable log để quyết định, không dựa riêng vào exception. Không còn exception handler xóa tất cả `acquired` mù quáng.

### 4.3 Release algorithm bắt buộc

1. Xác minh original packet/durable task binding; không yêu cầu current plan approval chỉ để cleanup. Kiểm tra pending action từ full history; có pending → không release.
2. Append/fsync `lease_release_intent` trước unlink đầu tiên.
3. Với từng resource: nếu file khớp binding thì unlink và fsync parent; nếu đã missing trong transaction release đang mở thì coi bước này đã làm; nếu foreign binding thì giữ nguyên, báo conflict.
4. Khi tất cả lease của transaction đã được xử lý, append/fsync `released`.
5. Retry sau success trả cùng receipt. Không chạy `_check_leases` yêu cầu tất cả file còn tồn tại trên nhánh release retry.

Legacy recovery: có event `released` cũ + còn một phần matching leases thì tiếp tục cleanup matching leftovers; resource missing được phép. Không xóa foreign lease đã được assessment khác acquire. Với legacy active `leased` nhưng lease thiếu, không tự tạo lại vì chưa có acquire-intent chứng minh giao dịch; trả `legacy-lease-inconsistent` có hướng xử lý. Với orphan lease legacy không có task journal, giữ quarantine và báo `orphan-lease-no-intent`; không tự đoán ownership. Các run mới được bảo vệ bằng protocol mới; không fake lịch sử để tự chữa legacy.

### 4.4 Journal inspect và torn-tail

Thêm `Journal.inspect(...)` trả object có `integrity`, `validEvents`, `validPrefixBytes`, `lastValidHash`, `tailBytes`, `tailDigest`, `diagnostics`; không ghi file. Phân biệt `clean`, `incomplete-tail`, `corrupt-record`, `identity-mismatch`. Record thiếu newline nhưng JSON đầy đủ vẫn là uncommitted tail theo contract cũ; không tự nhận là event hợp lệ.

Chỉ prefix trước lỗi được dùng cho forensic hints. Bất kỳ corruption/hash mismatch giữa file không được silently skip. Không thay mặc định strict của constructors đang dùng cho dispatch.

`Coordinator.inspect_recovery()` phải hoạt động read-only dù journal có tail; trả pending/lease facts đọc được, mức chắc chắn và `effectsAllowed=false`. Không trả `pendingEffects=[]` như thể chắc chắn không còn effect khi tail chưa rõ.

**Ranh giới triển khai đã chốt:** đợt này không tự truncate, sửa hash-chain, replay event hay mở khóa dispatch khi có tail/corruption chưa đối soát. Hoàn thành đường inspect/degraded selection để tiếp tục source/file review độc lập và chuẩn bị recovery. Tạo repair task `journal-integrity` với raw path/hash/last valid event. Fresh effect, lease changes và final completion vẫn bị khóa. Việc phục hồi writable journal sau hỏng thật cần evidence executor và quyết định riêng; Sol phải báo giới hạn này rõ, không gọi đây là fully automatic journal repair.

### 4.5 Lock callback F31

Không tách callback khỏi assessment lock trong đợt này: thay đổi đó cần protocol writer-in-flight/fencing riêng và không cần để sửa các crash windows R1–R3. Ghi rõ F31 còn tồn tại; không thêm timeout có thể giải phóng lease khi effect còn chạy. Source work offline không cần gọi callback để tiến triển. Tách lock callback là work item hậu nghiệm thu, không âm thầm mở thêm scope.

## 5. WP2 — Registry và immutable working generations

### 5.1 Layout và định danh

Registry root do CLI cung cấp rõ bằng `--registry-dir`. Không scan toàn máy, không tự lấy file mới nhất/lớn nhất. Một file registry entry cho mỗi SHA-256 assessment ID:

```text
<registry-dir>/registry.lock
<registry-dir>/<sha256(assessmentId)>.json
<state-dir>/store.lock
<state-dir>/current.json
<state-dir>/generations/<generation-id>/RUN.json
<state-dir>/generations/<generation-id>/OPERATOR.json
<state-dir>/generations/<generation-id>/manifest.json
<state-dir>/projections/<generation-id>/checklist.md
<state-dir>/projections/<generation-id>/CONTINUE-PROMPT.md
```

Registry entry: `{version:1, assessmentId, storePath, registrationId, sourceRunPath, sourceRunSha256}`. Một assessment chỉ có một storePath trong registry. Register cùng entry idempotent; khác storePath trả conflict. Đợt này không có CLI tự replace registry entry hoặc tự chuyển quyền active store. Sau này relocation cần thao tác explicit riêng.

Current pointer: `{version:1, assessmentId, generationId, manifestSha256}`. Manifest chứa `version`, `assessmentId`, `generationId`, `parentGenerationId`, `commitId`, `requestDigest`, `expectedGenerationId`, hashes/bytes của RUN và OPERATOR, timestamp UTC, source provenance. Không đặt secrets vào pointer/manifest/stdout.

Source provenance bắt buộc có `sourceRunPath`, `sourceRunSha256`, `artifactBaseDir` là thư mục của RUN nhập ban đầu. Các relative evidence paths lịch sử tiếp tục resolve theo `artifactBaseDir`, không theo generation folder. Không sửa hàng loạt nội dung raw/approved paths để biến chúng thành absolute. Với reference mới do store tạo, dùng absolute private reference hoặc structured `{path, baseDir}` được validator hỗ trợ; không diễn giải URI private minh họa thành đường dẫn tự tồn tại. Loader phải có một hàm resolve reference chung truyền explicit base vào reader, không đổi cwd process.

Generations immutable; chỉ `current.json` replace atomically. Một snapshot được commit **khi current pointer durable và đọc lại trùng**, không phải khi mới có folder generation.

Không thêm state metadata vào approved plan. Giữ RUN là JSON theo schema hiện hành để reviewer/executor vẫn đọc được. OPERATOR lưu scheduling/repairs ngoài approval digest. Không thay `coordinatorState.directory` để move resources khi register.

### 5.2 Python API

```python
register_store(registry_dir, state_dir, source_run, operator_state, *, registration_id)
resolve_store(registry_dir, assessment_id)
load_current(state_dir) -> Snapshot
commit_snapshot(state_dir, *, expected_generation, commit_id, run, operator_state) -> CommitReceipt
inspect_store(state_dir) -> Inspection
render_projections(snapshot, decision) -> dict[str, str]
```

Snapshot chứa run, operator, generation ID và file refs; không trả copy có thể bị coi là canonical sau sửa mà chưa commit. `commit_id` là idempotency key do caller chọn và giữ qua retry. `requestDigest` tính từ **logical payload** + expected parent; không chứa timestamp/UUID ngẫu nhiên sinh trong mỗi retry. Generation ID dùng SHA-256 commit ID; manifest giữ full commit ID để phát hiện collision/misuse.

Quy tắc digest request theo command: state-commit dùng canonical run+operator+expectedGeneration; state-merge dùng packet digest+canonical result+expectedGeneration; repair command dùng canonical input repair+expectedGeneration. Store nhận thêm `request_kind` và `request_payload_digest` nội bộ từ typed handler, lưu cả hai trong manifest. Không nhận digest tùy ý từ CLI để bỏ qua so sánh payload. Retry handler tra manifest theo commitId trước khi merge trên current; như vậy retry merge cũ sau một commit khác không vô tình tạo payload mới từ RUN đã tiến lên.

### 5.3 Commit protocol

Thứ tự locks khi RUN có coordinatorState: coordinator assessment lock → store lock. Registry lock chỉ dùng registration/lookup, không giữ qua coordinator callback; không code nào giữ store lock rồi lấy coordinator lock. Pure `load_current` không tạo missing directory hoặc coordinator.

1. Load current dưới lock; validate pointer/hash/schema/assessment identity.
2. Check idempotency **trước CAS**: nếu commit ID hiện nằm trong committed ancestry và requestDigest trùng, trả receipt cũ + current generation (`alreadyApplied=true`); không rewind pointer. Cùng ID payload khác → conflict.
3. Parent expected không khớp current → `stale-generation`; không write.
4. Validate run: không reportProjection; đúng assessment; validate_workflow và evidence bằng reviewer khi coordinator clean. Operator validation chống thay authority qua scheduling.
5. Trong chế độ journal degraded, chỉ được commit OPERATOR/repair metadata; RUN phải byte-equivalent theo canonical digest với current RUN. Không tự chốt verdict, không thêm operation để bỏ qua reviewer đang lỗi.
6. Ghi immutable RUN, OPERATOR, manifest bằng no-clobber atomic primitives; fsync files/directory/generations parent. File đã tồn tại trong retry phải có hash trùng; conflict không overwrite.
7. Ghi temporary pointer rồi `os.replace`, fsync state-dir; đọc lại pointer + manifest + file hashes. Đây là commit point.
8. Sinh projections sau commit. Lỗi projection không rollback state; trả `projectionsPending=true`, có thể render lại offline.

Validation transition giữa hai snapshot: assessment ID và coordinatorState không được đổi qua ordinary commit; operation IDs cũ không được xóa hoặc sửa nội dung, chỉ append operation mới. CaseResults/resourceReview/resolutions có thể cập nhật qua coordinator review và được lưu history bằng generation cũ; không coi worker merge là quyền overwrite conflicting result. Plan/criteria có thể có revision mới khi cần nhưng approval phải được reviewer đánh giá theo digest mới, không copy nhãn approved. Scheduling không thể thay evidence. Không nhận một candidate RUN rỗng làm cách clear unknown history: bảo toàn actionHistory/pending bindings; resolutions chỉ có giá trị khi đi qua contract hiện hành. Thêm negative tests cho delete operation, clear actionHistory và đổi coordinator root.

Manifest retry sau crash phải reuse timestamp/provenance đã durable nếu generation có một phần file; không sinh timestamp khác rồi báo conflict giả. Nếu generation chưa có manifest, timestamp/provenance tạo khi hoàn tất manifest và chỉ requestDigest dùng cho idempotency. Không đưa newly sampled timestamp vào RUN/OPERATOR payload của retry tự động.

Crash trước pointer → generation staged, không tự chọn làm current. Retry đúng commit ID/parent có thể hoàn tất publication. Crash sau pointer trước stdout → retry trả receipt, không tạo generation mới. Crash khi current đang được replace → hoặc pointer cũ hợp lệ hoặc pointer mới hợp lệ; không dùng mtime làm fallback. Pointer/hash hỏng thật → inspect và explicit recovery; không chọn generation ngầm.

Initial register: tạo genesis store trước, registry publish sau. Ngắt trước registry thì source/registration ID cho phép retry chính xác store đó. Có registry entry nhưng store mất/hỏng → error có cấu trúc; không bootstrap assessment mới. Private directory 0700, file 0600; reject symlink final destinations, path traversal và nonregular files theo primitives hiện có.

### 5.4 CLI mới và hợp đồng lỗi

Thêm dưới `python -m zap_assessment.product_cli scope`:

```text
state-init --run PATH --operator PATH --state-dir DIR --registry-dir DIR --registration-id ID
state-resolve --registry-dir DIR --assessment-id ID
state-inspect --state-dir DIR
state-commit --state-dir DIR --expected-generation ID --commit-id ID --run PATH --operator PATH
state-merge --state-dir DIR --expected-generation ID --commit-id ID --packet PATH --result PATH
state-next --state-dir DIR [--evidence-index PATH] [--now RFC3339]
state-render --state-dir DIR
state-inspect-recovery --state-dir DIR
state-recover-leases --state-dir DIR --packet PATH
state-repair-open --state-dir DIR --expected-generation ID --commit-id ID --repair PATH
state-repair-update --state-dir DIR --expected-generation ID --commit-id ID --repair PATH
```

`state-next` và inspect read-only, không sửa stale checkpoint. `--now` phục vụ tests/offline scheduling, không được dùng bypass live token/executor checks. `state-recover-leases` chỉ metadata/resource lease protocol, không native stop/replay; có receipt riêng journal, không nhất thiết tạo generation nếu RUN/OPERATOR không đổi. Lệnh này cần coordinatorState hiện có, không tự tạo root mới.

Mutation stdout chỉ receipt/status/IDs/refs cần thiết, không dump RUN, token, callback bodies hoặc credentials. Exit code: 0 = command thành công kể cả decision waiting; 2 = invalid input/schema; 3 = conflict/stale generation; 4 = integrity/recovery required; 5 = IO/unavailable dependency. Diagnostic có stable `code`, `message`, `refs`, không parse string exception trong scheduler. Các lệnh legacy giữ exit semantics cũ.

`state-merge`: load current, gọi `merge_result` dưới lock, commit run mới + operator hiện tại bằng CAS. Giữ worker không được sửa arbitrary OPERATOR hay verdict trực tiếp. Case result conflict vẫn cần coordinator reconciliation, không biến thành overwrite.

Legacy `criteria-merge --run --output`: nếu output đã có, đọc regular file và so logical JSON result. Trùng hoàn toàn → success `alreadyApplied=true`; khác → conflict. Không overwrite input, không tự promote canonical. Không thay `atomic_bytes` thành overwrite chung.

### 5.5 Tích hợp consumer

Với CLI v2 hiện có, thêm lựa chọn `--state-dir` mutually exclusive với `--run` cho `criteria-review`, `criteria-digest`, `criteria-packet`, `criteria-native-read`, `criteria-reconcile-action`, `criteria-release-task`, `resume-next`; state-dir resolve current snapshot. Không đổi legacy scope v1 commands.

Lệnh effect/readback dùng state-dir phải reload current dưới coordinator lock ngay trước admission; packet binding phải match current approved plan. Raw `--run` vẫn hỗ trợ legacy. Trong managed workflow, skill yêu cầu đi qua state-dir, không sửa generation RUN trực tiếp. Store hashes phát hiện accidental direct edit; đợt này không tuyên bố chặn mọi caller Python cố ý bypass protocol.

`criteria-merge` raw giữ file API cũ; managed merge dùng `state-merge`. Report exporter có thể nhận resolved immutable RUN nhưng output vẫn là projection; không thay exporter thành canonical store. Không bắt buộc rewrite mọi runner trong đợt này; ghi supported managed entrypoints trong tài liệu và tests.

## 6. WP3 — Operator state và selection engine

### 6.1 Schema operator v1

Tất cả key dưới đây là top-level trong OPERATOR.json, không trong `criteriaWorkflow.plan`:

```json
{
  "version": 1,
  "assessmentId": "fixture-assessment",
  "planDigest": "digest-from-approved-plan",
  "activeBlockId": "B1",
  "blocks": [
    {"id": "B1", "caseIds": ["T1", "T2"], "order": 0, "exitCondition": "review all selected cases"}
  ],
  "workItems": [
    {
      "id": "inspect-T1", "caseIds": ["T1"], "blockId": "B1",
      "kind": "source-review", "mode": "offline",
      "phase": "execution", "order": 0,
      "dependsOnWorkIds": [], "resourceIds": [],
      "state": "ready", "basisRefs": ["private://approved-case/T1"],
      "nextStep": "Inspect the pinned source path from case T1",
      "actionRef": null, "readbackOf": null, "notBefore": null,
      "completionRefs": [], "waiting": null
    }
  ],
  "repairs": [],
  "delivery": null,
  "stopRecord": null
}
```

Enums work kind: `source-review|evidence-review|prepare|dispatch|readback|resource-review|delivery`. Mode: `offline|runtime`. Phase: `execution|ttl-readback|closure`. State: `ready|in_progress|waiting|done`. Không có `passed`, `met`, `not_applicable` trong operator task status.

`actionRef` khi runtime trỏ đúng `{caseId, actionId}` trong approved action descriptors; không chứa Python import, shell command, tool callback hoặc payload thay thế. `readbackOf` phải khớp descriptor gốc. Nếu chưa có executable action, dùng prepare task; không invent action từ oracle. Runtime resource set phải bao gồm effective plan+case resource set giống make_packet; nếu empty dùng target fallback cùng helper. Không cho operator resourceIds rỗng giả vờ độc lập.

Validator:

- IDs unique, refs nonempty, case IDs tồn tại, block map không nhân đôi case giữa các block. Mỗi plan case nằm đúng một block; nếu khởi tạo không có lịch thì tạo một default block chứa toàn bộ case, không suy luận nghiệp vụ.
- Work dependencies là DAG; plan `dependsOnCases` vẫn là dependency riêng. Worker/output không được tự khai done cho case verdict.
- `done` work cần completionRefs/basis; chỉ giải quyết work-item dependency. Case closure luôn lấy review_workflow. Nếu case còn pending mà tất cả work items done, sinh `prepare` fallback với reason `case-obligation-without-ready-work`; không biến case thành hoàn tất.
- Waiting record `{reason, basisRefs, reopenCondition, missingEvidence, nextStep}`; tự hết waiting chỉ khi deadline rõ đã qua, repair đã verified hoặc dependency hoàn tất bằng data. Không diễn giải văn xuôi reopenCondition thành executable logic.
- planDigest khác hiện tại → operator stale, trả preparation/rebase metadata task. Không tự sửa approval digest hoặc packet. Plan mới giữ lịch cũ historical; rebase đòi explicit new OPERATOR input và diff mapping.
- Không có lịch/draft đầy đủ trước Gate 2: raw legacy resume vẫn trả approval actions. Managed state-init trong đợt này yêu cầu v2 RUN có plan structure hợp lệ, cho phép approvals còn thiếu; không bắt user tạo plan trước Gate 1 chỉ để dùng store.

### 6.2 API và output

```python
select_next(run, operator, review, coordinator_inspection, *, evidence_index=(), now) -> Decision
```

Hàm thuần, không read files/network/sleep, không gọi callback, không đổi input. `now` datetime aware UTC; UI/handoff mới format sang timezone user nếu dữ liệu có. Wrapper load store/reviewer/coordinator và đưa snapshot vào hàm. Tests inject review/time, không mock semantic truth thành product qualification.

Decision output giữ trường cũ của resume (`assessmentStatus`, `criterionCounts`, `pendingActionIds`, `nextAction`) và thêm:

```text
decisionVersion=1
generationId / planDigest
mode = normal | recovery-only | stopped
readyWorkIds
deferred [{workId/caseId, reasonCode, dependsOn, refs, earliestAt}]
nextAction {kind, workId?, caseId?, blockId?, actionId?, missingUnits?, reasonCode, refs, nextStep}
nextWakeAt (nullable; chỉ timestamp, không claim đã đặt monitor)
canConcludeTurn (bool)
conclusionReason (nullable)
```

Không dùng `canConcludeTurn=true` như verdict/completion. Đây là điều kiện operator có thể bàn giao, khác assessment completed. Có thể false dù nextAction null nếu binding sai cần repair/clarification chưa biểu diễn; phải có diagnostic concrete.

### 6.3 Thứ tự lựa chọn cố định

Thực hiện filtering trước scoring:

1. Actual user stop/pause: chặn fresh assessment work; vẫn trả owned readback/resource disposition cần thiết theo quyền đã có nếu có. Không tự bỏ userRequest vì user gửi status question. `canConcludeTurn` chỉ true sau khi đã nêu pending supervision/resource condition hoặc không có việc cleanup khả thi.
2. Journal/store integrity: `mode=recovery-only`; không fresh runtime effects. Cho phép inspect-recovery, tạo repair và work offline source/evidence collection độc lập; không derive verdict mới nếu reviewer không đủ integrity.
3. Approval thiếu/stale: trả approval/preparation action như hiện tại; không dispatch. Không bắt dừng mọi source preparation vốn được phép, nhưng không gán execution credit từ draft.
4. Pending effects: ưu tiên readback **đã có descriptor/authority** của action liên quan. Nếu không có reader thì prepare-reader/repair; ghi unknown giữ nguyên. Khi reader thực sự unavailable, không để một placeholder readback lặp vô hạn chặn mọi việc độc lập.
5. Retained ACK/evidence chưa reconcile: evidence-review/readback trước fresh dispatch khi compatible. Evidence index là hint; không tự đóng unit.
6. Ready work trong active block; nếu active block waiting/reconciled thì chọn block ready có order nhỏ nhất. Case dependency chỉ thỏa khi reviewer outcome `matched|violated`; pending/N/A parent không tự thỏa dependency action. Explicit readbackOf dùng để reconcile effect đang mở không bị ordinary forward case dependency chặn vô lý; vẫn phải qua recovery admission gốc.
7. Repairs đã có scope, repro và ready để sửa; independent preparation/source; dùng deterministic tie-break dưới đây.
8. TTL: subject/control refs + timezone-aware `notBefore` bắt buộc; chỉ xét runtime TTL sau deadline và sau khi không còn execution-phase work khả thi (non-TTL blocked không bắt chờ vô hạn). Trước dispatch revalidate same token/control bằng executor; clock eligibility không chứng minh live validity.
9. Sau obligations: resource review, rồi delivery theo final-only. Nếu assessment pending mà hết ready thì review-dependencies với exact deps; không giả complete. Delivery interim chỉ khi user boundary/authority cho phép.

Trong cùng priority class: active block trước → block.order → work.order → stable ID. Thứ tự ID không được vượt dependency/readiness. Resource conflicts lấy từ retained leases + effective resource map; cùng task có pending action thì chỉ readback đúng action được phép; different case ID không tạo isolation. Source offline không chiếm scanner chỉ vì plan có shared resource, nhưng không được dùng nhãn offline cho thao tác HTTP.

Nếu thiếu resource map đủ để chứng minh runtime độc lập, trả prepare admission, không assume ready. Descriptor có thể đủ để chọn `dispatch` candidate nhưng executor vẫn quyết định admission live.

`resume_next(run, evidence_index=())` legacy wrapper: dùng minimal operator mặc định và chung selection core; phải sửa dependency T1→T2 ngay cả khi không có managed store. Giữ tests cũ cho retained ACK/case closure; output thêm fields được phép. Với unknown effect T1 và independent T2, vẫn cho T2 nếu readback không ready và tài nguyên được chứng minh độc lập; fixture test hiện tại có thể cần làm rõ resource map thay vì blanket assumption.

### 6.4 Delivery và stopping

Delivery receipt nằm operator: `{fileId, worksheetId, status, sourceDigest, verifiedAt, readbackRefs}`. `sourceDigest` tính từ reviewed report projection gồm run identity/criteria/row content; loại timestamp riêng của verification, scheduler và receipt để tránh digest tự thay đổi sau mỗi verify. Reuse projection logic của `criteria_reporting.py` nếu phù hợp, không tạo security verdict thứ hai.

Agent nhập receipt từ connected readback; store chỉ kiểm tra structure/binding, không tự chứng minh Google Sheets còn đúng. Không thêm exporter. Final decision `workflow-done` chỉ khi reviewer eligible, resources reconciled và receipt verified cho đúng sourceDigest. Raw legacy RUN thiếu receipt → `verify-final-delivery`, không suy ra done.

`canConcludeTurn=false` nếu còn next action khả thi. True khi workflow done, explicit user boundary đã xử lý tài nguyên, hoặc tất cả work còn lại có dependency cụ thể/TTL future. `host-interruption`/`context-handoff` là stopRecord có user/host source và reason, không do selector tự đoán. Skill không được tự bịa stop reason từ số case/độ dài chat. Module không thể cưỡng chế model không final; chỉ cung cấp quyết định có kiểm chứng để nghiệm thu sau này.

## 7. WP4 — Nhiệm vụ sửa công cụ có vòng đời riêng

Repair nằm OPERATOR.repairs, không thành criterion hay plan obligation mới:

```json
{
  "id": "repair-reader-001",
  "kind": "reader",
  "status": "open",
  "affectedCaseIds": ["T1"],
  "affectedWorkIds": ["read-T1"],
  "affectedResourceIds": [],
  "symptom": "Captured response shape rejected by existing parser",
  "reproductionRefs": ["private://captured-result/sanitized"],
  "expectedBehavior": "Read retained receipt without another effect",
  "authorityRef": "private://approved-testing-adapter-scope",
  "allowedPaths": ["relative/module.py"],
  "prohibitedEffects": ["product-traffic", "replay", "product-remediation"],
  "acceptanceChecks": ["captured valid response accepted", "invalid response rejected"],
  "verificationRefs": [],
  "resumeWorkIds": ["read-T1"],
  "dependency": null,
  "history": []
}
```

Kinds: `reader|adapter|fixture-preparation|binding|journal-integrity|store-integrity|executor-capability`. `fixture-preparation` có thể cần effect; repair task chỉ mô tả việc chuẩn bị, effect vẫn cần existing action/admission. `allowedPaths` là scope cho agent, không sandbox hay code execution permission.

States: `open → reproducing → implementing → verifying → verified`; từ trạng thái đang làm có thể sang `waiting_dependency`; từ waiting quay lại bước đã lưu khi dependency được đối soát; `superseded` cần replacement ID. Không mark verified chỉ vì worker nói pass.

Verified cần reproduction outcome, changed file/digest refs, positive+negative check refs, kết quả verification và next original work. Lưu verificationLevel `offline-checked|runtime-observed`; không tự nâng offline fix thành runtime-qualified. Không cần user duyệt lại sửa kỹ thuật trong authority có sẵn.

Dedup bằng `kind + affected work + normalized symptom + reproduction digest` do code tính; cùng lỗi lặp lại append occurrence vào history, không tạo repair mới vô hạn. Symptom giống nhưng context/build khác giữ riêng hoặc explicit linked repair, không tự dùng kết quả cũ.

Scheduler chặn đúng affectedWorkIds và dependent work, vẫn chọn việc độc lập. Repair verified chỉ mở lại work bị ảnh hưởng; không tự sửa outcome, xóa pending effects, repin plan hoặc replay action. Quay về `readback` nếu effect cũ có intent/ACK; chỉ fresh action khác khi plan/admission thật cho phép.

CLI repair-open/update dùng CAS commit OPERATOR; update phải giữ history append-only, không thay original symptom/repro để làm sửa trông thành công. Lưu record version/revision; stale update báo conflict. Có validated payload từ agent là cần thiết; không triển khai arbitrary text-to-code repair engine.

## 8. WP5 — Checklist, prompt và cập nhật skill

`state-render` tạo projection theo committed generation + journal snapshot diagnostic. Header ghi assessment ID, generation, plan digest và timestamp quan sát journal. Checklist không là authority; khi journal thay đổi, render lại thay vì cập nhật checklist bằng tay. `state-next` luôn tính lại journal live, không tin cached nextAction trong projection.

Prompt phải ngắn và chỉ có:

- Skill absolute path; registry-dir + assessment ID hoặc state-dir chính thức.
- Lệnh inspect/next; first action + reason; pending effect reconciliation; whole remaining approved workflow.
- Không chứa secret/raw transcript, shell command lấy từ artifact không tin cậy, hay “kết thúc khi xong một lane”.
- Ghi rõ next step là ưu tiên, không thu hẹp assignment. Chỉ handoff khi stop rule thật đáp ứng. Không tự tạo chat/automation.

Không ép chạy `state-render` sau mọi effect như một điều kiện để checkpoint tồn tại. Snapshot/journal mới là durable authority; projection có thể khôi phục sau ngắt không có final message.

Sửa các reference cụ thể:

1. `SKILL.md`: managed state entrypoint, inspect→recover→select→execute→persist→repeat; không tự khởi tạo assessment khác khi thiếu pointer.
2. `retention-stop-and-recovery.md`: thay checklist-as-authority bằng generated projection; documented transaction recovery; degraded tail; CLI; legacy compatibility.
3. `business-work-blocks.md`: schema operator blocks, active block và TTL scheduling; không phải mỗi block một chat.
4. `local-remediation-and-continuation.md`: repair task state machine và quay lại original work.
5. `criteria-driven-workflow.md`: không thay approvals; mô tả store bên ngoài content binding, managed merge và revision mismatch.
6. `delegation-policy.md`: worker chỉ ghi result/draft/repair proposal; coordinator commit canonical; runtime resources vẫn sequential trừ isolation thật.
7. `helper-contract-map.md`, `setup.md`: command paths, interpreter, return semantics và giới hạn.
8. `assessment-policy.md`: cập nhật câu cũ “no new ... scheduler” cho đúng scope mới đã được user giao: deterministic offline selector + durable store được triển khai; không background executor/automatic Sheets exporter.
9. `operational-validation.md`: thêm fault tests và phân biệt implementation verified với behavioral acceptance pending.

Sửa resume template đang nói `exclude external-tool/source-only findings`: làm rõ chỉ không nhập chúng vào ZAP-derived/native alerts; source evidence theo approved method vẫn là công việc hợp lệ.

## 9. Thứ tự triển khai và checkpoints của Sol

Làm tuần tự các WP để tránh sửa interfaces khi caller chưa thống nhất:

1. Baseline + port reproduction thành regression assertions (không chỉ assert error cũ).
2. WP1: durable lease transactions + inspection. Chạy focused recovery/caller tests.
3. WP2: store + CAS + idempotence + registry; tests độc lập fixture.
4. WP3: operator schema + selection engine; legacy wrapper và state CLI.
5. WP4: repair task lifecycle + scheduling integration.
6. WP5: projections/docs, full selected regression, offline CLI walkthrough.

Sau mỗi WP lưu `docs/reviews/zap-core-implementation-20261104/progress.md`: WP đã xong, files thay đổi, command+test results, outstanding issue, exact next step. Đây là checkpoint cho **nhiệm vụ implementation**, không phải product RUN mới. Nếu bị ngắt, đọc progress và current diff rồi tiếp tục WP đang mở. Không dừng tự nguyện sau mỗi WP để xin “tiếp tục”.

Không bắt buộc subagent. Nếu skill maintenance delegation được dùng, chỉ giao phần độc lập với file ownership rõ; main agent nhận và review trước merge. Không giao hai worker sửa chung coordinator/store/CLI. Profile theo delegation-policy hiện hành; không biến availability của worker thành điều kiện bắt buộc của implementation.

## 10. Kiểm thử bắt buộc — expected behavior đã chốt

Mọi tests dùng TemporaryDirectory, fake executor có bộ đếm, fixtures sanitized. Không host product requests. Fault injection ở đúng boundary sau durable write; ít nhất một test subprocess interruption thật cho acquire/release để tránh chỉ kiểm tra Python exception rollback. POSIX/macOS là môi trường hiện hành; skip có lý do trên host không hỗ trợ, không claim cross-platform qualification.

### A. Coordinator transactions

- A01 acquire normal → durable intent trước lease và commit; fresh Coordinator đọc lại được.
- A02 kill sau acquire-intent trước lease → recover tạo đúng lease, không callback.
- A03 kill sau lease đầu trong hai lease → recover hoàn tất, không orphan.
- A04 kill sau lease cuối trước leased commit → recover commit, cùng packet idempotent.
- A05 append leased đã persist rồi raise → retry không xóa lease và không duplicate grant.
- A06 lỗi write trước đủ record → inspect báo incomplete/corrupt, fresh dispatch bị chặn; không rollback mất ownership.
- A07 release kill sau release-intent → retry cleanup hết.
- A08 release kill sau unlink đầu → retry chịu missing file, cleanup phần còn lại, commit.
- A09 release success mất stdout → retry success, không unlink resource mới của task khác.
- A10 pending action → release/recovery không được xóa lease; unknown không được replay.
- A11 cùng resource, hai assessments/process → chỉ một acquire commit; không delete foreign lease.
- A12 legacy released + matching leftover → cleanup được; legacy orphan không journal → diagnostic/quarantine.
- A13 task ID đã released không được acquire lại thành attempt mới.
- A14 valid prefix + torn tail → inspect trả prefix/unknown; strict dispatch vẫn lỗi, không false zero pending.
- A15 corrupt middle/hash/identity → fail closed, không bỏ record.
- A16 stop/plan revision không chặn original lease readback/release đã có quyền; fresh dispatch vẫn bị chặn.

### B. Store và merge

- B01 register + resolve deterministic assessment ID; registration retry idempotent.
- B02 hai directory cùng assessment ID trong registry → conflict; không chọn newest.
- B03 genesis crash trước registry publish → explicit registration retry chỉ adopt đúng store.
- B04 crash giữa RUN/OPERATOR/manifest trước pointer → current cũ còn nguyên.
- B05 crash sau pointer trước receipt → cùng commit ID trả alreadyApplied.
- B06 retry commit cũ sau một commit mới → receipt cũ, pointer không rewind.
- B07 same commit ID different payload → conflict; stale expected generation → conflict.
- B08 hai writers expected cùng parent → một thắng, một stale; không mất update.
- B09 bad hash/missing file/symlink/path escape → diagnostic, không guessed fallback.
- B10 projection write fail → committed snapshot vẫn load được; render lại được.
- B11 operator-only change giữ nguyên approval digests; attempted plan change không được tự kế thừa approvals.
- B12 state-merge identical retry idempotent; conflicting historical operation/result vẫn reject.
- B13 legacy merge same output same JSON success; different output JSON conflict; input không overwrite.
- B14 registration không sửa source RUN/journal/coordinatorState; relative artifact refs giữ base gốc hoặc normalize bằng explicit source base, không resolve nhầm sang generations directory.
- B15 degraded journal cho phép operator repair metadata commit nhưng reject thay RUN/verdict.

### C. Scheduler

- C01 T1 dependsOn T2 unfinished → T2 trước; T2 violated với đủ evidence cũng mở T1.
- C02 dependency cycle/unknown ID → reject schema.
- C03 unknown effect T1, ready admitted reader → readback trước fresh effect; không replay.
- C04 reader unavailable, T2 offline độc lập → T2; unknown T1 giữ lại.
- C05 hai case cùng scanner/task pending → không xem different case ID là isolation.
- C06 active block còn ready → ở lại; block waiting → chọn block independent.
- C07 retained evidence hint không tự đóng case; compatible review candidate ưu tiên.
- C08 toàn bộ task done nhưng reviewer còn missing units → prepare missing work, không done assessment.
- C09 TTL trước deadline → deferred + earliestAt; còn independent work thì tiếp tục.
- C10 TTL qua deadline nhưng control không đủ → prepare/revalidate; không tự declare result.
- C11 TTL chỉ còn cùng non-TTL blocked → có thể chọn TTL khi live prerequisites đủ; không starvation.
- C12 user stop/pause → không fresh work; pending resource disposition vẫn hiển thị.
- C13 operator stale planDigest → reconcile schedule, không sửa approval.
- C14 workflow review complete, delivery missing/stale → verify delivery; đúng receipt → workflow-done.
- C15 chỉ thay verification timestamp không làm projection sourceDigest thay đổi.
- C16 cùng snapshot/now → cùng decision/order; input không bị mutate.
- C17 malformed journal → recovery-only + offline independent task; không final completion.
- C18 ready work còn → canConcludeTurn false; không nhầm một block done thành workflow done.

### D. Repair lifecycle và CLI integration

- D01 cùng repro/context → append occurrence, không duplicate repair.
- D02 repair mở chỉ chặn affected/dependent work; independent source vẫn ready.
- D03 verified thiếu checks/refs → reject; offline-checked không tự thành runtime-observed.
- D04 verified repair → original readback được chọn, action cũ không được dispatch lại.
- D05 worker proposal không thể sửa oracle/approval/verdict/registry.
- D06 stale repair update/CAS → conflict; history cũ giữ nguyên.
- D07 fresh subprocess: state-resolve → inspect → next → synthetic merge → next tiến tới ca kế; không cần biến Python/context cũ.
- D08 immutable-generation tamper detected; legacy raw --run APIs vẫn chạy tests cũ.
- D09 CLI error codes/JSON schema đúng; stdout không chứa fixture secret canaries.
- D10 managed native read/reconcile/release reload current; stale packet reject.
- D11 generated prompt có whole remaining workflow + exact locator; không tạo stop-after-lane. Kiểm tra dữ liệu contract và walkthrough, không dùng prose test làm bằng chứng agent thực thi tốt.

## 11. Lệnh kiểm tra và bộ hồi quy

Từ workspace root:

```sh
export ZAP_PYTHON='/Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python'
export ASSESSMENT_ROOT='/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment'
export PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests"
"$ZAP_PYTHON" -B -m unittest test_criteria_resume test_criteria_workflow test_criteria_cli_boundary test_criteria_native_read test_criteria_integration test_criteria_reporting_boundary -q
```

Sau khi thêm modules/tests:

```sh
"$ZAP_PYTHON" -B -m unittest test_coordinator_recovery test_assessment_store test_operator_state test_operation_selection test_assessment_state_cli -q
"$ZAP_PYTHON" -B -m unittest test_evidence_allocation test_role_object_matrix test_resume_inputs test_work_session_checkpoint -q
git diff --check
```

Kiểm tra runtime_safety tests trước khi chạy để bảo đảm chỉ fixture/local offline; chạy phần liên quan journal/safety IO khi sửa chúng. Không chạy một suite có live effects chỉ vì tên “regression”. Nếu interpreter thiếu dependencies, tìm environment đã có theo setup; không tự tải/cài toàn bộ môi trường ngoài assignment. Ghi blocker môi trường cụ thể và tiếp tục code/source work độc lập.

Các repro audit cũ cố ý assert lỗi cũ; sau fix chúng có thể không còn trả lỗi. Giữ nguyên chúng làm historical evidence. Regression mới phải assert behavior mong đợi, không sửa file audit để che thay đổi kết quả. Lưu transcript mới kèm test IDs ở thư mục implementation.

## 12. Offline walkthrough để bàn giao cho người nghiệm thu

Thêm script `LIB/examples/state_recovery_walkthrough.py`, chỉ fixture, chạy một lần tạo output temp được chỉ định và không network. Script tạo hai case phụ thuộc + một case independent, một fake effect counter, một repair và một TTL task. Các stage:

1. Khởi tạo store và coordinator, commit approval fixture; ghi rằng approval chỉ là synthetic test.
2. Acquire hai resources; inject interruption; process mới recover lease, fake effect count vẫn 0.
3. Dispatch fake effect đúng một lần; lưu receipt, ngắt trước merge.
4. Process mới readback receipt và merge; assert fake effect count vẫn 1.
5. Chặn reader của một case bằng repair; chọn independent case; verified fix quay lại readback.
6. Future TTL trả nextWakeAt; advance injected clock, chọn TTL khi execution work khác xong hoặc blocked có căn cứ.
7. Reviewer completed nhưng delivery thiếu → verify-final-delivery; nhập synthetic receipt đúng digest → done.

Walkthrough chỉ chứng minh liên kết code/CLI qua process boundary. Không gọi đây là nghiệm thu agent qua context thật, Google Sheets thật hay scanner thật. Chuẩn bị entrypoint và artifacts để người dùng gửi lại agent audit.

## 13. Definition of done của Sol

Sol kết thúc implementation khi:

- WP1–WP5 hoàn tất trong scope đã chốt; CLI/API/docs khớp nhau.
- Tests A–D có mapping rõ tới test method và kết quả, kể cả tests ghép nhiều scenario.
- Positive controls và negative controls đều chạy; legacy no-replay/approval/evidence regressions vẫn giữ.
- Walkthrough process restart chạy được; có checkpoint/runnable commands cho người nghiệm thu.
- Không chạm product RUN thật, scanner, Docker, Sheets, permissions hoặc historical audit artifacts.
- Báo rõ giới hạn còn lại: journal corruption chưa có automatic writable repair, callback lock F31, chưa behavioral acceptance, chưa live migration/real runtime qualification.

Deliverables:

1. Code + focused tests + skill/reference updates trong working tree.
2. `docs/reviews/zap-core-implementation-20261104/implementation-report.md`: changes theo WP, files, contract decisions đã thực hiện, test mapping/results, deviations, residual risks, exact audit commands.
3. `docs/reviews/zap-core-implementation-20261104/progress.md`: final implementation status và remaining work nếu thực sự blocked.
4. `docs/reviews/zap-core-implementation-20261104/acceptance-handoff.md`: một prompt copy được cho agent nghiệm thu, trỏ plan này, implementation report, walkthrough và tests. Không tự yêu cầu user resume từng WP.

Final response của Sol nêu implementation status, tests, report/handoff links và giới hạn; không nói assessment sản phẩm đã hoàn tất hoặc skill đã được nghiệm thu toàn bộ.

