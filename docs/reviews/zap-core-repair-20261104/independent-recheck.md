# Kiểm tra độc lập sau sửa R01–R04

Ngày 2026-11-04. Kết luận: **pass vòng kiểm tra implementation offline đã chọn; đủ điều kiện vào behavioral acceptance fixture**. Không phải nghiệm thu toàn skill, live migration hoặc runtime.

## Thực chạy

- Chạy đúng các module core/regression/safety/repair của implementation-report trong một invocation unittest: 220 tests, 17.983 s, OK, không skip.
- `shasum -a 256 -c final-source-sha256.txt`: tất cả 14 file khớp.
- `shasum -a 256 -c historical-probes-sha256.txt`: cả hai probe audit nguyên vẹn.
- `git diff --check`: exit 0.
- Walkthrough trong TemporaryDirectory mới: exit 0, đủ 7 stage. Stage 2: dispatch/effect, canConcludeTurn=false, counter 0. Stage 3/4/7 counter 1; stage 7 workflow-done.
- Chạy lại historical selector/repair probe nguyên bản: work chưa có executionBinding trả prepare/resolve-execution-binding, canConcludeTurn=false; recurrence chuyển open với previousVerification giữ trong history.
- Probe độc lập store bằng fixture mới: register RUN có mutation intent, commit ACK-only; pending còn 1 và eligibleForCompletion=false. Sau đó làm hỏng ancestor fixture: inspect trả committed-history-integrity.
- Review source các sửa collector/binding/repair recurrence/ancestry. Positive controls resolution, valid exact task binding sau acquire/recovery và negative controls được kiểm tra trong suite test_verification_repairs; không chỉ dựa probe âm.

## Đánh giá R01–R04

- R01: ACK không còn xóa unresolved mutation/start trong các đường đã kiểm tra; resolution đúng vẫn được tests kiểm chứng.
- R02: đường exact packet trong walkthrough cold-process chọn dispatch sau recovery; work legacy thiếu binding có bước preparation thay vì tự kết luận dừng chờ.
- R03: occurrence mới sau verified mở lại repair, giữ verification trước; typed retry/dedup và fresh checks có tests.
- R04: inspection phân biệt current snapshot và committed ancestry, báo lỗi parent hỏng.

Không phát hiện blocker mới trong phạm vi source/test vừa kiểm tra. Không kết luận không còn mọi bug. Writable journal repair và lock callback F31 giữ giới hạn đã thống nhất. Không sửa core/source/product state khi kiểm tra này.

## Bước tiếp theo

Dùng `docs/plans/zap-core-behavioral-acceptance-sol-20261104.md`. Lượt A vận hành fixture qua nhiều block tới checkpoint được chỉ định; lượt B trong chat mới hoàn tất từ locator. Chỉ sau khi có report và evidence A/B mới đánh giá khả năng agent vận hành liên tục qua context. Không dùng subprocess restart làm bằng chứng chat restart hoặc báo synthetic delivery là Sheets thật.
