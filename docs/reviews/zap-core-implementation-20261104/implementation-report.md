# Báo cáo triển khai lõi vận hành MCP ZAP

Ngày 2026-11-04. Đối tượng triển khai là working-tree bytes hiện hành tại workspace `testing tool`. Baseline gồm `baseline-status.txt`, `baseline-sha256.txt` và `baseline-tests.txt`. Bộ baseline 77 test qua trước khi chỉnh. Các thay đổi đã có trong workspace được giữ lại. Historical repro và audit giữ nguyên để đối chiếu.

## Các gói triển khai

- **WP1** — `criteria_delegation.py` và `journal.py` thêm acquire/release intent bền vững, khóa shared resource, retry theo binding, recovery có packet gốc, chẩn đoán legacy và forensic prefix. Quyền readback sau revision hoặc stop lấy từ descriptor read-only trong packet đã được giữ lease và từ action đang pending của chính task đó. `criteria_native_read.py` tái sử dụng kiểm tra này trước khi khởi tạo transport. Full reviewer, callback admission, fixture và no-replay tiếp tục áp dụng ở các điểm dispatch tương ứng.
- **WP2** — `assessment_store.py` thêm registry tường minh, immutable generations, manifest hashes và ancestry, CAS, retry receipt và kiểm tra transition của RUN. Commit point là con trỏ được công bố và đọc lại. Snapshot giữ artifact base của source RUN. `assessment_state_cli.py` bổ sung typed commit và managed merge. `product_scope_cli.py` bổ sung lựa chọn `--state-dir` và retry cùng output cho legacy merge.
- **WP3** — `operator_state.py` và `operation_selection.py` kiểm tra schedule version 1 ngoài approval digest, chọn việc theo dependency, tài nguyên, pending effects, block, repair và TTL. `criteria_resume.py` dùng chung selector với raw RUN. Review v2 vẫn quyết định closure. Delivery receipt verified được kiểm tra với digest của reviewed report content và điều kiện hoàn tất.
- **WP4** — Hai lệnh repair ghi proposal và transition vào OPERATOR qua CAS. Repair revision, fingerprint, history, reproduction, verification và resume work đều nằm trong working state. Repair mở chặn đúng nhánh đã gắn binding. Readback sau repair tiếp tục dùng action và lease gốc.
- **WP5** — `state-render` tạo checklist và prompt từ generation cùng journal facts. `SKILL.md` và các reference về recovery, blocks, remediation, workflow, delegation, helper, setup, policy và validation mô tả entrypoint managed. `examples/state_recovery_walkthrough.py` chạy qua CLI và các tiến trình con chỉ bằng fixture.

## Kết quả và ánh xạ kiểm thử

`core-tests.txt` chứa tên đầy đủ của từng method, mã scenario và kết quả. Một số method thực hiện nhiều tình huống với fixture riêng hoặc subtest.

- **A01–A05** — `test_coordinator_recovery.TransactionTests` kiểm tra chronology acquire, process exit trước lease đầu và sau từng lease, cùng ambiguous append đã persist.
- **A06–A09, A13–A15** — Cùng module kiểm tra torn lease commit, release process exit, retry sau resource được cấp lại, cấm hồi sinh task, tail prefix và corruption/identity.
- **A10–A12, A16** — Cùng module kiểm tra pending lease retention, readback sau stop/revision, hai process cạnh tranh, abort khi có foreign claim và legacy leftovers/orphan.
- **B01–B11, B14–B15** — `test_assessment_store.StoreTests` kiểm tra registration, staged/committed retry, CAS, tamper và path safety, projection failure, approval/operation/action history và degraded commit.
- **B12–B13** — `test_assessment_state_cli.CliTests` kiểm tra managed merge retry sau generation mới, historical conflict, legacy output và input.
- **C01, C03–C18** — `test_operation_selection.SelectorTests` kiểm tra reviewer dependency, reader/resource ordering, block, evidence hints, TTL, stop, stale plan, receipt, determinism và recovery-only.
- **C02, D01–D06** — `test_operator_state.OperatorTests` kiểm tra DAG, dedup, repair isolation, verification, original readback, scope và stale revision.
- **D07, D09–D11** — `test_assessment_state_cli.CliTests` kiểm tra process mới, structured errors, canary, stale packet và prompt. Managed reconcile/release qua CLI cũng có trong stage 6 của walkthrough.
- **D08** — `test_assessment_store.StoreTests.test_B09_D08_tampering_missing_symlink_escape` và các test raw `--run` trong hồi quy.

Kết quả cuối gồm **35 test lõi**, **132 test hồi quy**, **5 test journal/safety** và **7 stage walkthrough**. `git diff --check` qua. Walkthrough giữ fake effect count ở 0 qua recovery và ở 1 sau dispatch, merge, repair, TTL và synthetic delivery. TTL dùng đồng hồ truyền vào. `walkthrough-transcript.jsonl` ghi locator của fixture tạm và projection được tạo.

## Điểm tích hợp theo source hiện hành

- Các reader v2 hiện hành dùng JSON pointer trong operation hoặc đường dẫn receipt do coordinator tạo. Store giữ nguyên các reference lịch sử và cung cấp `Snapshot.resolve_reference` với base gốc cho artifact path, không đổi cwd. Các runner bên ngoài danh sách managed giữ entrypoint hiện hành.
- Journal hỏng trả gợi ý repair `journal-integrity` với path, tail digest và last valid hash. Coordinator mở repair qua `state-repair-open` để cung cấp authority và acceptance checks thật. `state-next` chỉ đọc.
- Delivery digest dùng identity, approved criteria/plan content, reviewed case/criterion rows và retained operation content. Source hiện hành có report projections nhưng không có builder riêng cho dòng Sheets cuối. Agent vẫn phải đối chiếu các dòng Sheets thực tế qua connected readback trước khi ghi receipt.
- F20 và F21 là bối cảnh audit. Handoff dùng interpreter sẵn có và không mở rộng sang doctor cho live runtime hoặc thay pin lịch sử.

## Giới hạn nghiệm thu

Torn-tail và corruption hỗ trợ đọc chẩn đoán. Writable journal recovery cần đối soát evidence và quyết định riêng. F31 còn tồn tại vì assessment lock được giữ qua callback. Các fault tests kiểm tra tiến trình và fixture trên môi trường POSIX hiện hành. Chúng không đại diện cho thử nghiệm mất điện. Behavioral acceptance qua nhiều chat, migration RUN thật và live runtime qualification thuộc lượt nghiệm thu sau. Nhiệm vụ này dùng fixture offline và không thực hiện sản phẩm, scan, Docker restart, Sheets, sharing, commit hoặc push.

## Lệnh chạy lại

Từ workspace root, chạy các lệnh sau với interpreter đã có.

```sh
export ZAP_PYTHON="$PWD/zap-product-assessment/.venv/bin/python"
export ASSESSMENT_ROOT="$PWD/.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment"
export PYTHONPATH="$ASSESSMENT_ROOT/src:$ASSESSMENT_ROOT/tests"

"$ZAP_PYTHON" -B -m unittest test_coordinator_recovery test_assessment_store test_operator_state test_operation_selection test_assessment_state_cli -v
"$ZAP_PYTHON" -B -m unittest test_criteria_resume test_criteria_workflow test_criteria_cli_boundary test_criteria_native_read test_criteria_integration test_criteria_reporting_boundary test_evidence_allocation test_role_object_matrix test_resume_inputs test_work_session_checkpoint -v
"$ZAP_PYTHON" -B -m unittest \
  test_runtime_safety.SafetyTests.test_atomic_short_write_never_exposes_final_name \
  test_runtime_safety.SafetyTests.test_truncated_journal_recovery_preserves_original \
  test_runtime_safety.SafetyTests.test_journal_middle_corruption_never_recovered_as_partial_tail \
  test_runtime_safety.SafetyTests.test_permanent_journal_fault_still_stops_and_records_out_of_band \
  test_runtime_safety.SafetyTests.test_reserved_channel_survives_writer_fault_and_rejects_torn_slot -v

fixture_parent=$(mktemp -d)
"$ZAP_PYTHON" -B "$ASSESSMENT_ROOT/examples/state_recovery_walkthrough.py" "$fixture_parent/fixture"
git diff --check
```
