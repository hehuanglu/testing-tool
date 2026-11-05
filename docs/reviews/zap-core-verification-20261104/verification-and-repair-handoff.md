# Kiểm tra triển khai MCP ZAP — kết quả và bàn giao sửa cho Sol

Ngày: 2026-11-04. Workspace: `/Users/hahoangloc/Working/testing tool`.

Trong file này, `SRC` là `.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src/zap_assessment` tính từ workspace root.

## Quyết định

**Chưa pass để chuyển sang vận hành nghiệm thu.** Đã chạy lại 172 tests và walkthrough 7 stage đều thành công; `git diff --check` sạch. Kiểm tra độc lập bổ sung phát hiện 2 lỗi P1, 1 lỗi P2 và 1 khoảng trống chẩn đoán P2. Không dùng tổng tests xanh để bỏ qua các reproduction dưới đây.

Đây là vòng sửa và kiểm tra lại, chưa phải hướng dẫn chạy assessment/live migration. Không sửa RUN thật, không gửi traffic, không Docker restart, không ghi Sheets. Sau khi Sol sửa, người dùng sẽ gửi báo cáo lại agent audit để quyết định bước nghiệm thu vận hành tiếp theo.

## Phạm vi đã kiểm tra

- Đối chiếu implementation report/progress/handoff với `docs/plans/zap-operations-core-implementation-plan-20261104.md`.
- Chạy lại đúng 35 core + 132 regression + 5 safety tests theo implementation report: **172 passed trong 9.178 s** ở lần kiểm tra này.
- Chạy walkthrough trong TemporaryDirectory mới: đủ 7 stage, fake effect count 0 sau recovery, 1 sau dispatch/restart/merge, kết thúc `workflow-done`, exit 0.
- Review source selector/operator/CLI/coordinator/store/journal và tests; chạy probes mới với synthetic data, không đọc runtime secrets.
- Bộ store/CLI riêng 12 tests cũng pass; đây là tập con, không cộng thêm vào 172.
- Code không bị sửa trong vòng audit. Chỉ tạo artifacts tại thư mục verification này.

Các phần acquire/release recovery, CAS và workflow wrapper có tiến bộ thực sự. Những giới hạn đã chốt trước (writable journal repair, F31 lock qua callback, chưa live qualification) không bị ghi thành lỗi mới của Sol.

## R01 — P1: ACK làm biến mất pending mutation dù chưa có readback

Nguồn:

- `SRC/question_evidence.py:143–162`, đặc biệt điều kiện ở 157–158.
- `SRC/assessment_store.py:224–238`: giữ original history append-only nhưng chưa giữ invariant unresolved effect khi append ACK.

Repro độc lập: `store-repro.py`, finding S1. Tạo RUN hợp lệ có ca đã có evidence nhưng còn actionHistory mutation intent. Reviewer ban đầu pending=1, `eligibleForCompletion=false`. Commit thêm cùng action ở state `acknowledged`, không thêm operation/readback/resolution. Commit được chấp nhận; reviewer chuyển pending=0 và eligible=true.

**Phân biệt nguồn gốc:** collector có hành vi này từ trước triển khai mới; store mới kế thừa và chưa ngăn được. Repro không có coordinatorState, là đường import/raw history được API cho phép. Coordinator journal có thể bảo vệ tốt hơn trong đường khác; không khẳng định mọi runtime đều bị lỗi này. Nhưng managed state vẫn có đường completion sai, vi phạm invariant ACK != terminal của kế hoạch.

### Sửa yêu cầu

1. Trong collector, mutation/start có durable intent phải còn pending sau `acknowledged`, `accepted`, hoặc bare `reconciled` label. Chỉ contract resolution hiện có với operation/readback/context đúng mới giải quyết uncertainty.
2. Không tự coi row cuối không phải intent là action đã xong. Giữ binding action/case/object/context từ lịch sử, bảo toàn unknown.
3. Reviewer và store dùng cùng cách thu thập pending effective state; đừng thêm một phép đếm riêng chỉ nhằm chặn fixture này. So sánh transition phải xét actionHistory, RUN pending, operation uncertainty và coordinator facts nếu có.
4. Cho phép commit ACK như progress; kết quả phải vẫn pending. Không cần reject mọi ACK commit. Reject hoặc giữ pending nếu candidate cố khai final verdict/delivery không đủ căn cứ.
5. Không tắt no-replay, không sửa lịch sử audit và không bắt mọi RUN import phải có coordinator mới để né bug.

### Tests bắt buộc

- Plain actionHistory: intent → ACK giữ pending và completion false.
- Journal envelope equivalent: cùng kết quả; mixed historical representation không mất uncertainty.
- intent → unknown → ACK vẫn pending.
- Bare `state=reconciled` không có terminal evidence không đóng.
- Đúng readback/resolution đúng action/case/context đóng được; wrong action/object/context không đóng.
- Có và không có coordinatorState đều kiểm tra; không double count cùng action từ nhiều nguồn.
- Managed state commit ACK thành công nhưng `state-next` không `workflow-done`; verified delivery không được bind kết luận sai.
- Các regression resolution trước đây vẫn qua; không làm pending tồn tại vĩnh viễn sau resolution hợp lệ.

## R02 — P1: lease hợp lệ của chính task bị coi là resource-conflict

Nguồn:

- `SRC/operation_selection.py:147–152`: chỉ miễn occupied lease cho readback có pending original action.
- `SRC/operator_state.py`: work item chưa có binding đủ để nhận diện packet đã acquire nhưng chưa dispatch.

Repro: `selector-repair-probes.py`, V01 (qua CLI `state-next`). Một work có approved action và resource scanner. Coordinator acquire đúng packet của task, chưa có action intent. Cold CLI selector trả:

```json
{
  "nextAction": {"kind": "review-dependencies", "reasonCode": "remaining-dependencies"},
  "deferred": [{"workId": "fresh", "reasonCode": "resource-conflict", "dependsOn": ["scanner"]}],
  "canConcludeTurn": true
}
```

Cùng RUN/packet/lease đó, `Coordinator.dispatch` vẫn admit và gọi fake callback đúng một lần. Đây là tình huống ngắt sau acquire trước dispatch rất bình thường. Selector đang cho phép dừng dù vẫn có bước khả thi, chính là loại lỗi vận hành cần khắc phục.

### Sửa yêu cầu

1. Bổ sung binding optional cho runtime work trong OPERATOR, ví dụ `executionBinding:{taskId, workerId, packetDigest, packetRef}`. Ghi binding trước acquire và giữ qua restart. Schema thay đổi additive trong operator v1; legacy work không có binding vẫn đọc được.
2. `packetRef` là đường dẫn private, không phải permission. Wrapper load/verify exact packet, digest, case/action membership, current approval hoặc recovery authority, original durable lease record. Selector nhận verified binding facts, không tin metadata tự khai.
3. Fresh action được candidate tiếp tục nếu toàn bộ effective resources thuộc đúng assessment+task+worker+packet digest đã xác minh, action chưa consumed và không có pending shared-task effect. Gate dispatch vẫn kiểm tra live admission.
4. Không miễn mọi lease cùng assessment; packet/task khác cùng assessment vẫn là conflict. Không release/reacquire chỉ để làm selector chạy được.
5. Nếu lease có vẻ task-owned nhưng work thiếu binding, trả công việc `prepare/resolve-execution-binding` với refs và `canConcludeTurn=false` khi còn bước đối soát local khả thi. Không kết luận external dependency từ việc thiếu metadata.
6. Sau acquire/recovery, cold `state-next` phải đưa ra được đường tiếp tục mà không cần người dùng biết để bypass selector.

### Tests bắt buộc

- Acquire xong trước intent, process mới state-next chọn fresh work đúng binding hoặc bước đối soát binding khả thi; không dừng chờ.
- Recover partial acquire xong rồi cold state-next có kết quả tương tự.
- Foreign assessment, different task, different packet digest, resource thiếu đều không dispatch candidate tự tin.
- Cùng task nhưng pending effect khác → chỉ original readback đúng authority.
- Action consumed → không được dispatch lại dù lease hợp lệ.
- Binding thiếu → concrete preparation, không claim unsafe ready; binding forged → reject/conflict.
- Scenario đã qua hết ca độc lập và chỉ còn task-owned pre-dispatch work phải có `canConcludeTurn=false`.
- Thêm scenario vào walkthrough; walkthrough cũ gọi dispatch trực tiếp sau recovery nên bỏ qua lỗi selector này.

## R03 — P2: báo lỗi tái diễn nhưng repair vẫn verified

Nguồn: `SRC/operator_state.py:229–234`; selector loại repair `verified` khỏi blockers.

Repro: V02. Repair đã đi đủ open→reproducing→implementing→verifying→verified. Gọi repair-open với proposal ID mới, cùng fingerprint và evidence lỗi tái diễn. Code chỉ append `occurrence`, tăng revision; trạng thái vẫn verified. Nhánh phụ thuộc không bị chặn lại để điều tra.

### Sửa yêu cầu

1. Phân biệt retry cùng occurrence với báo cáo occurrence mới. Giữ commit ID idempotence cho retry; proposal/occurrence ID mới sau verified là sự kiện cần xem xét lại.
2. Chốt policy vòng này: cùng fingerprint nhưng occurrence mới sau verified → reopen repair về `open`, tăng revision, append `reopened-after-verification` với snapshot verification cũ và new reproduction refs.
3. Giữ nguyên original symptom/scope và historical verification; clear current verification fields để không kế thừa pass cho lần mới. Có thể lưu verification cũ trong history event có dữ liệu đầy đủ.
4. Retry cùng occurrence không reopen lần nữa, không nhân duplicate. Current open/reproducing vẫn dedup bằng append occurrence như cũ.
5. Selector chặn lại affected work; công việc độc lập tiếp tục. Không replay old effect sau sửa lần hai.
6. Update validation/store transition/docs để hỗ trợ reopen chính thức qua typed repair API; không cho ordinary state-commit thay repair tùy ý.

### Tests bắt buộc

- New occurrence sau verified → open, old verification preserved historical.
- Same occurrence/commit retry → idempotent.
- Active repair duplicate → không tạo repair mới vô hạn.
- Different context/build fingerprint → giữ riêng như hiện tại.
- Reopened repair chặn affected work và cho independent work tiếp tục; re-verification phải cung cấp evidence mới.

## R04 — P2: state-inspect báo clean khi parent history hỏng

Nguồn: `SRC/assessment_store.py:load_current`, `inspect_store`, ancestry traversal trong `find_receipt`.

Probe S2 sửa fixture parent manifest sau khi tạo generation con. `state-inspect` vẫn báo `integrity=clean`; commit tiếp theo lại từ chối `generation-integrity` khi duyệt ancestry. Current snapshot có thể vẫn nguyên vẹn; đây là khoảng trống chẩn đoán/history, không phải bằng chứng current bytes bị corrupt hoặc unsafe replay.

### Sửa yêu cầu

- `state-inspect` phải phân biệt current snapshot integrity và committed history integrity; không gọi whole store clean khi chỉ kiểm tra current.
- Duyệt ancestry bằng parent hash liên kết đã có, detect missing/corrupt parent và cycle; không chọn newest file, không tự sửa pointer.
- Có thể giữ `load_current` nhẹ cho caller rõ scope, nhưng inspect trả `integrity=clean` chỉ khi các phần nó tuyên bố đã verify thực sự clean. History lỗi trả structured code/refs để operator biết bước tiếp theo trước khi ghi.
- Thêm tests deleted parent, tampered parent, intact chain và staged non-ancestor generation. Staged orphan không được tự nhập vào history/được coi là committed corruption.

## Lệnh tái hiện audit

Từ workspace root, dùng interpreter đã có:

```sh
zap-product-assessment/.venv/bin/python -B docs/reviews/zap-core-verification-20261104/selector-repair-probes.py
zap-product-assessment/.venv/bin/python -B docs/reviews/zap-core-verification-20261104/store-repro.py
```

Hai probe là evidence cho **behavior trước sửa**, không phải regression expectations mới. Không chỉnh chúng để báo pass. Chuyển scenarios vào test modules phù hợp với expected behavior yêu cầu ở trên. Sau fix probe có thể không còn in kết quả cũ hoặc dừng ở assertion audit cũ; giải thích bằng tests mới và transcript.

Xem `selector-repair-results.json` và `store-findings.md` cùng thư mục để đối chiếu chi tiết. Các fixtures được xóa khi script kết thúc; report giữ kết quả sanitized, không chứa product secrets.

## Phạm vi và Definition of done vòng sửa

- Đọc lại kế hoạch gốc để giữ invariants; không refactor thêm toàn bộ workflow.
- Fix R01–R04, cập nhật tests/docs/managed binding contract tương ứng. Nếu phát hiện buộc phải mở rộng scope, ghi cụ thể thay vì silently bypass.
- Giữ mọi dirty edits trước nhiệm vụ, không commit/push/reset, không sửa historical audits/product RUN.
- Chạy tests mới, 172-test command gốc và walkthrough mới. Số lượng test có thể tăng; báo đầy đủ số pass/fail/skip theo suite và exact command.
- Report chỉ là implementation verified offline. Không tự chạy assessment live, migrate RUN thật hoặc tuyên bố behavioral acceptance qua chat.
- Bàn giao `docs/reviews/zap-core-repair-20261104/implementation-report.md` gồm từng R01–R04 → files → test methods → actual result; source digest cuối; residual risks; prompt cho agent audit kiểm tra lại.
