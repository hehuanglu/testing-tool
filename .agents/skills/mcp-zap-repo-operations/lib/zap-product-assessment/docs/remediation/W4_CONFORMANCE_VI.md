# W4 continuation — transport denial, policy containment và runtime faults

> Tài liệu này ghi checkpoint lịch sử. Trạng thái implementation hiện tại và các
> acceptance đã bổ sung được mô tả tại [W4_COMPLETION_VI.md](W4_COMPLETION_VI.md).

Ngày19/10/2026, Asia/Ho_Chi_Minh. Checkpoint mới nằm tại
`test-artifacts/mcp-zap-remediation/w4-conformance-20261018T200856Z`.
Đây là implementation/conformance trên fixture anonymous riêng. Full W4, R1/R2 và protected W5 chưa được chấp nhận; independent review vẫn pending. Không gửi traffic vào finalsource, dùng credential, sửa root Java/CI hoặc đổi shared stack.

## Source và ranh giới transport

`TrafficProbe.java` giữ HttpSenderListener và bổ sung decorator quan sát exception từ chính sender đã có. Không thay transport/retry/redirect implementation. Hook đọc field `HttpSender.impl` trên ZAP2.17/network0.31 đã pin; inventory kiểm hook không bị thay thế. Đây là integration riêng cho fixture, chưa đăng ký cho borrowed/P0/native/protected mode.

Một số HTTPS background requests dùng `notifyListeners=false`. Collector quan sát **entry của sender**, ghi `capturePoint=sender-entry-listeners-disabled`, không gọi đó là engine listener callback. Chỉ các lần thử TLS không có listener được tuần tự hóa trước khi ghi để guard không chọn đoán giữa hai request cùng authority. Nếu sender trả về mà không có terminal callback hợp lệ, capture vẫn incomplete.

Guard không mở CONNECT tunnel. Một CONNECT denial cần khớp một native request đang chờ đúng authority, native I/O failure và không có forwarding/target arrival. Thiếu hoặc mơ hồ thì latch/block. Disposition là `unsupported_https_connect`, không tạo HTTP response giả, không xác nhận HTTPS application oracle, TLS/cookie/CORS/CSRF fidelity hoặc active technique. Giữ URL/body dưới dạng hash; không log raw header/body/exception message.

Rule identity dùng class reference của plugin thực sự được load và stack tại thời điểm gửi. `x-zap-scan-id` không cấp rule identity. Unknown/ambiguous/disabled active producer bị block kể cả guard đã chứa được request. Workflow `active=false` còn chặn active producer từ rule enabled; enabled inventory không phải quyền thực thi active.

Sau cleanup, runtime đọc lại cả ba durable logs. Có request đến muộn hoặc capture khác snapshot đã đưa vào evidence thì từ chối publication. Bundle thành công có `traffic-closure.json` pin SHA của snapshot sau khi owned resources đã dừng. Fault trước terminal không được tạo closure hoặc complete manifest.

## Proof hiện có

Calibration7 hoàn tất full redirect workload qua cùng Executor/LiveScanner, ResourceGate và SafetySupervisor trên image release đã pin. Source/product/workflow/image/growth bindings giữ nguyên; không tái dùng calibration HTTP-only cũ. Calibration-only vẫn cố ý block publication.

Lượt normal3 có **execution completed, evidence complete, cleanup clean**; bundle đã verify. Gate ứng dụng là **review_required**, security **inconclusive**, exit3: fixture có CSP directive/anti-clickjacking findings cần review. Harness development không đòi application pass và không bỏ findings để tạo allow.

Lượt này đối chiếu29 sender requests:16 HTTP responses,13 transport failures và13 CONNECT denials;13 independent target arrivals, zero forbidden target requests. Background được audit riêng với crawl/manual; số background requests thay đổi theo thời điểm, không phải acceptance denominator. Completed resource sampling gap lớn nhất khoảng2,881s. Traffic closure sau cleanup khớp exact snapshot. Các con số này chỉ thuộc workload đã đo.

Các ca negative và fault cùng source pin được ghi riêng trong `gate-results.json` và `runtime-readback.json`. Ca rule990001 là plugin fixture cố ý phát request dù disabled; không phải phát hiện defect ở built-in rule. Unknown producer chạy từ class/thread không đăng ký và gửi rule header giả để kiểm header không thay native identity. Một phase bị dừng có thể giữ receipt đã hoàn tất trước latch; pending phần còn lại vẫn incomplete, không biến cả run thành complete.

Kernel ENOSPC/EROFS/EFBIG dùng tmpfs8MiB/root read-only trong container riêng. Controller journal ENOSPC là fault injection ở I/O boundary, không giả thành host disk thật đã đầy. Lost start ACK bỏ return của start thật, không gửi start lần hai. SIGKILL và Docker API transport outage có recovery record mới, giữ journal gốc và original failure. API outage chỉ ngắt relay UNIX0600 của child controller; không restart hay làm lỗi shared daemon. Stop không xác nhận phải quarantine trước khi phục hồi transport và stop-only recovery.

## Kiểm chứng và chạy lại

Từ package root:

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
.venv/bin/python scripts/remediation_w4_runtime.py --output /absolute/new-calibration-report.json --work-dir /absolute/new-calibration-work
.venv/bin/python scripts/remediation_w4_conformance.py prepare --work-dir /absolute/new-case --calibration-report /absolute/new-calibration-report.json --case normal
```

Bước prepare tạo `input-lock.json`, plan và safety contract trước thực thi. Run dùng SHA từ lock đã đọc riêng:

```sh
.venv/bin/python scripts/remediation_w4_conformance.py run --work-dir /absolute/new-case --output /absolute/new-case-report.json --expect-safety-hash EXTERNAL_LOCKED_HASH
```

Các case khác: `disabled-rule`, `unknown-active`, `inventory-drift`, `journal-enospc`, `lost-start-ack`, `interrupt`. Harness và Java fault fixture có hash riêng trong lock; đây không là independent reviewer approval. Output/work-dir luôn mới. Scripts SIGKILL/API outage và exact command receipts nằm trong checkpoint; không áp dụng chúng vào product/shared namespace.

## Còn thiếu và rollback

Full G5 chưa có acceptance cho expected enabled built-in active set/forwarding, vectors header/body/cookie hoặc policy theo từng active phase. Passive/background classification ngoài initiator đã quan sát chưa được generalize. Full G6 còn thiếu các workload/mode/topology khác; monitor sampling kết thúc trước cleanup, cleanup dùng bounded stop/reserved channel và traffic closure riêng. API transport loss không chứng minh daemon restart/state loss. Không coi calibration nhỏ là RAM SLO cho mọi scanner/browser.

G3/G4 delegated lifecycle/secret campaign còn thiếu, nên không mở protected W5/P0/native/browser/shared. Source-supported candidate và development pass không cấp mode authority hoặc release/security sign-off.

Rollback theo `source-before.json` + private snapshot + `change-index.json`, chỉ khôi phục đúng file thuộc lượt này; không reset/stash root dirty spike. Giữ failure history, quarantine và backup/archive trước đó. Không rollback coverage đã biết sai hoặc xóa evidence để đổi gate.
