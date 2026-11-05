# Vòng sửa R01–R04 của lõi vận hành MCP ZAP

Ngày 2026-11-04. Workspace `/Users/hahoangloc/Working/testing tool`. Phạm vi là implementation và xác minh fixture offline. Baseline working tree nằm trong `baseline-status.txt`. Digest của toàn bộ file code, test và reference được sửa trong vòng này nằm trong `final-source-sha256.txt`.

## R01 — ACK và pending mutation/start

`question_evidence.py` chuẩn hóa plain history và journal envelope trong cùng collector. Một durable mutation/start intent vẫn sinh pending sau ACK, accepted hoặc bare reconciled label. Collector hợp nhất uncertainty từ history, operation, RUN/continuation và coordinator theo action ID, đồng thời kiểm tra các trường identity và coverage context không xung đột. `criteria_workflow.py` dùng collector đó trước khi chạy semantic resolution hiện hành. `assessment_store.py` dùng cùng dữ liệu trước resolution để kiểm tra transition, cho phép lưu ACK và từ chối verified delivery khi reviewer còn pending.

- `PendingHistoryTests.test_R01_plain_envelope_mixed_unknown_and_bare_labels` kiểm tra plain, envelope, mixed, unknown rồi ACK, accepted và reconciled label.
- `PendingHistoryTests.test_R01_exact_resolution_closes_and_wrong_binding_rejects` kiểm tra positive control và sai action, case, object hoặc environment.
- `PendingHistoryTests.test_R01_coordinator_run_history_and_operation_are_deduplicated` đưa cùng action qua coordinator journal, history, RUN pending và operation uncertainty.
- `RepairCliTests.test_R01_managed_ack_commit_succeeds_and_verified_delivery_rejects` kiểm tra ACK commit, từ chối delivery sớm và mở bước verify delivery sau resolution hợp lệ.
- Hai test hiện hữu `QuestionEvidenceTests.test_unknown_intent_union_and_independent_object` và `WorkSelectionTests.test_stop_and_durable_intent_ordering` cập nhật kỳ vọng ACK vẫn giữ pending. Các test positive/negative resolution hiện hữu tiếp tục chạy.

## R02 — Tiếp tục đúng packet sau acquire

`operator_state.py` thêm `executionBinding` tùy chọn vào runtime work của OPERATOR v1. `criteria_delegation.py` cung cấp durable lease facts cho wrapper. `assessment_state_cli.py` giải packet path từ artifact base, xác minh digest và authority, kiểm tra membership của action/case và đối chiếu full claim với lease files. `operation_selection.py` chỉ dùng binding facts đã kiểm tra để nhận diện lease của work, giữ filter pending/consumed và trả một bước preparation khi có thể đối soát binding tại chỗ. Binding hợp lệ được lưu trước acquire có thể dẫn đến `prepare/acquire-execution-lease`. Sau acquire hoặc recovery, cùng work có thể được chọn dispatch nếu chưa dùng và các điều kiện khác đạt. Executor tiếp tục kiểm tra admission khi dispatch.

- `RepairCliTests.test_R02_cold_selection_after_acquire_and_consumed_action` kiểm tra preparation trước acquire, cold CLI sau acquire và cấm chọn lại action đã dùng.
- `test_R02_cold_selection_after_partial_acquire_recovery` dùng process exit sau lease đầu, chạy recover qua CLI, rồi chạy cold `state-next`.
- `test_R02_missing_binding_prepares_and_forged_digest_conflicts` kiểm tra bước đối soát local, refs và `canConcludeTurn=false`, cùng forged digest.
- `test_R02_other_task_foreign_assessment_and_missing_resource` và `test_R02_same_task_with_different_valid_packet_digest_conflicts` kiểm tra các binding/resource không đủ.
- `test_R02_pending_effect_in_another_case_of_same_packet` chứng minh cùng task với effect pending ở case khác chỉ chọn reader phù hợp.
- Walkthrough stage 2 chạy `state-next` từ process mới sau recover và xác nhận chọn `dispatch` cho `effect`, `canConcludeTurn=false`, fake count 0. Stage 4 kiểm tra action đã consumed. Stage 7 xác nhận fake count vẫn là 1.

## R03 — Mở lại repair khi tái diễn

`operator_state.py` phân biệt occurrence mới và retry bằng proposal ID cùng payload digest. Recurrence sau verified với fingerprint trùng chuyển repair về open, lưu `reopened-after-verification` cùng verification trước và reproduction refs mới. Current verification được xóa và lần verify sau cần ref kiểm tra dương, âm và record mới. `operation_selection.py` dùng trạng thái mở để chặn lại công việc liên quan. Typed repair APIs vẫn là đường ghi lifecycle.

- `RepairCliTests.test_R03_typed_recurrence_reopens_once_and_requires_new_checks` kiểm tra lịch sử verification, retry cùng commit, dedup cùng occurrence, independent work, chống ordinary overwrite, yêu cầu check mới và quay về reader mà không chọn replay.
- `OperatorTests.test_D01_deduplicate_normalized_symptom_by_context_and_repro` giữ đối chứng active duplicate và context khác.

## R04 — Phân biệt current và committed history

`assessment_store.py` dùng chung trình duyệt ancestry cho inspection và receipt lookup. `state-inspect` trả `currentIntegrity` và `historyIntegrity` khi cả hai sạch. Nếu current xác minh được nhưng parent chain lỗi, CLI trả exit 4 với `committed-history-integrity` và refs. Staged generation ngoài ancestry không tham gia phép kiểm tra.

- `RepairCliTests.test_R04_inspect_intact_history_ignores_staged_generation` xác nhận intact chain và staged non-ancestor.
- `test_R04_missing_and_tampered_parent_reject_inspect` kiểm tra missing/tampered parent trong khi current còn đọc được.
- `test_R04_self_cycle_is_not_a_clean_store` kiểm tra cycle.

## Kết quả thực chạy

| Suite | Pass | Fail / error | Skip |
|---|---:|---:|---:|
| Core gốc | 35 | 0 | 0 |
| Regression gốc | 132 | 0 | 0 |
| Safety gốc | 5 | 0 | 0 |
| Repair và hồi quy collector/selector dùng chung | 48 | 0 | 0 |

Tổng **220 test**, gồm 14 test mới và 34 test hồi quy bổ sung ngoài bộ 172 gốc. Xem `core-tests.txt`, `regression-tests.txt`, `safety-tests.txt` và `repair-tests.txt` cho kết quả theo method. Walkthrough qua đủ 7 stage trong `walkthrough-transcript.jsonl`. `git diff --check` qua.

Hai historical probe giữ nguyên SHA-256. Bản `*-before.txt` ghi behavior đã tái hiện. Sau sửa, selector probe trả bước preparation cho legacy work thiếu binding và repair chuyển về open. Store probe dừng ở assertion cũ của S1, vốn đòi ACK xóa pending. Các test R04 riêng kiểm tra S2 bằng expected behavior mới.

## Giới hạn và lựa chọn tích hợp

- Managed wrapper dùng packet content digest, case/action membership và durable coordinator facts. Selector chỉ đưa ra candidate từ trạng thái đã quan sát. Executor kiểm tra lại authority, resource và no-replay khi vận hành.
- Pending mutation/start trong các caller legacy dùng chung collector tiếp tục chờ evidence sau ACK. Hai kỳ vọng test cũ được sửa theo invariant này.
- Writable journal repair và F31 assessment lock qua callback giữ giới hạn của kế hoạch gốc. Behavioral acceptance qua chat, migration RUN thật và qualification runtime live vẫn chờ audit riêng.
- Mọi bài chạy dùng fixture offline. Không thực hiện product traffic, scan, Docker restart, sửa RUN thật, ghi Sheets, đổi permissions, commit hoặc push.

## Lệnh chạy lại

Từ workspace root:

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
"$ZAP_PYTHON" -B -m unittest test_verification_repairs test_question_evidence test_work_selection -v

fixture_parent=$(mktemp -d)
"$ZAP_PYTHON" -B "$ASSESSMENT_ROOT/examples/state_recovery_walkthrough.py" "$fixture_parent/fixture"
shasum -a 256 -c docs/reviews/zap-core-repair-20261104/final-source-sha256.txt
shasum -a 256 -c docs/reviews/zap-core-repair-20261104/historical-probes-sha256.txt
git diff --check
```

## Prompt cho agent audit

```text
Kiểm tra lại R01–R04 trong workspace /Users/hahoangloc/Working/testing tool. Đọc docs/reviews/zap-core-verification-20261104/verification-and-repair-handoff.md, store-findings.md và hai probe cùng thư mục. Đối chiếu docs/plans/zap-operations-core-implementation-plan-20261104.md và docs/reviews/zap-core-repair-20261104/implementation-report.md. Xác minh source digests, chạy lại đúng các lệnh offline trong report và dùng fixture tạm mới.

Kiểm tra riêng ACK-only history qua state-commit và positive control có resolution, cold state-next sau acquire/recover với exact binding và đối chứng foreign/same task khác digest, recurrence sau verified với retry idempotent, cùng ancestry hỏng với current còn đọc được. Kiểm tra walkthrough chọn effect qua state-next sau recovery trước callback, rồi giữ no-replay. Historical probes giữ assertion cũ, dùng test mới để đánh giá expected behavior.

Báo kết quả offline và quyết định có đủ điều kiện chuyển sang behavioral acceptance hay không. Giữ dirty changes. Trong lượt kiểm tra này chỉ dùng fixtures, giữ nguyên RUN thật, scanner, Docker, Sheets và permissions.
```
