# W3 — Registry, chặn mode và chuẩn bị secret gate

Ngày 18/10/2026 (Asia/Ho_Chi_Minh). Tiếp tục từ G0–G2 development checkpoints, phạm vi W3 offline. Registry được đọc máy, kiểm schema và hash/link; đây là containment và G3 readiness, chưa phải G3 pass hoặc acceptance R1/R2/G12. Không có campaign, credential resolution hay Docker lifecycle mới.

## Nguồn chuẩn và cách đọc

`profiles/capability-registry.json` (`capability-registry/1.0`) ghi chín capability với evidence level, execution policy, contract, scope, limitations, known failures, source/image provenance và reference metadata có SHA-256. Các mức source-supported, pilot-verified, blocked/unverified không đồng nghĩa nhau. Historical pilot và readback giữ đúng thời điểm/source; không suy thành current runtime. G2 source manifest là pin trước W3; source W3 cuối được pin tại checkpoint mới. Image inventory G0 là metadata lịch sử, không phải attestation image được build từ dirty source.

[Summary được sinh từ registry](CAPABILITIES_GENERATED.md) được kiểm byte-for-byte cùng metadata refs. Không chỉnh summary bằng tay. [Capability matrix M2](../capability-matrix.md) giữ các mục cũ dưới nhãn historical. [Implementation status](../implementation-status.md) và [P0 runbook](../finalsource-p0-runbook.md) trỏ đến trạng thái W3 thay cho lời claim cũ. Artifact/gate record W0–W2 và evidence pilot không bị viết lại.

Registry không cấp quyền. `existing-contract` chỉ định đường v1.0/v1.1 anonymous hoặc direct-client BOLA v1.2–v1.4 đã có planner/authority/binding/source/fixture checks riêng. Evidence runtime của các đường đó là historical; W3 không bỏ qua source drift, kế thừa authority cũ hoặc chạy lại để cấp fresh acceptance. Không thêm writes vào BOLA read-only v1.4. `verification-v2` chỉ offline, publisher v2 vẫn blocked.

## Admission cho P0

`capabilities.require_p0_mode` áp execution ceiling cố định cho native, delegated và business. CLI trả exit2 cùng not_started / incomplete / inconclusive / clean / block trước đọc receipt, credential hoặc tạo output. `Pilot.__init__` chặn trước metadata/Docker; `provision` và `execute` kiểm lại; standalone guard `serve` chặn trước `State` đọc credential và mở listener. Unknown mode cũng block. Không có cờ force/diagnostic bypass. `coverage` vẫn là nhánh offline không khởi tạo Pilot.

Đổi registry thành pass không tạo runtime attestor hoặc mở mode. W4/W5 phải triển khai contract/gate cụ thể rồi sửa admission bằng code và tests có proof trước khi mở delegated; native cần G12-N riêng. Đây là guard cho các entry point của assessment, không phải sandbox ngăn người sửa/chạy Python tùy ý hoặc khóa toàn bộ chức năng auth của upstream. Root Java experimental JSON bearer giữ nguyên default-off trong source, không được bật bởi W3. Anonymous public ZAP không bị nhầm với native authenticated diagnostic.

Lý do cụ thể:

- Native: audit lịch sử ghi password/JWT trong history, generated UI script, tool chunk responses và report. Chưa sửa secret persistence.
- Delegated: audit scanner hẹp không thấy match, nhưng bỏ qua private/source/controls/guard; zap.log được ghi sau audit; chưa có seeded auditor controls hoặc lifecycle đầy đủ. `provision` còn copy credential source vào `run/private/credentials.json`, trái invariant mới dù permission0600. W3 chặn đường đó, không xóa file lịch sử.
- Business P0: đi qua cùng provision chứa credential copy và scanner startup; không được mượn acceptance read-only BOLA để bật writes.
- Browser, canonical và shared/HA: thiếu proof đúng mode. Mirror, TLS không xác minh hoặc việc tools có mặt không là acceptance.

## Secret sink inventory

`profiles/secret-sink-inventory.json` (`secret-sink-readiness/1.0`) khởi tạo 13 loại sink, bốn mode native/delegated/browser/business, 11 lifecycle cases và năm nhóm encoding. Mỗi sink có vị trí cần kiểm, cách truy cập dự kiến, quan sát lịch sử, proof tiếp theo và trạng thái access/control/lifecycle chưa chứng minh. Thiếu sink, encoding, mode hoặc lifecycle bắt buộc bị từ chối; không dùng N/A sau run để bỏ required proof.

Vùng cho phép là credential source bên ngoài repo/bundle bằng reference và bộ nhớ runtime cô lập có lifecycle/dump proof. Persistent browser storage chưa được chấp nhận; tmpfs cần kiểm scope persistence/crash trước khi dùng. Vùng cấm gồm prompt/tool output, argv, repo, journal, profile browser, history/session DB, logs, reports/exports, bundle, credential copy và artifacts crash/restart. Canary seeded vào từng loại sink phải được auditor W5/N phát hiện100%; run thật đòi zero matches. Unreadable hoặc omitted sink dẫn đến blocked.

Encoding inventory dự kiến gồm UTF-8 raw, standard/URL base64 có/không padding, percent encoding và JSON escapes. W5/N phải khóa biến thể/decoder bounded và bổ sung encoding/compression/DB format thực tế có trong pipeline. W3 chưa triển khai hay chạy auditor; không hứa mọi encoding đều được phát hiện. `check_readiness` chỉ xác nhận inventory đủ cấu trúc, luôn trả `g3Status=blocked`, không cấp secret-pass. Không đọc source credential để làm kiểm tra readiness.

Khi gate thật thất bại: dừng/quarantine đúng resource owned, giữ restricted evidence và chặn export public. Không tự xóa evidence rò rỉ lịch sử, đổi credential thật, restart target hoặc prune scanner chung.

## Lệnh đã chuẩn bị để tái kiểm

Từ `zap-product-assessment`:

```sh
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities summary
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_capabilities.py' -v
```

Exit0 của `capabilities check` chỉ là registry/links/hash/generated-docs/inventory nhất quán. Kết quả cùng lúc giữ G3 blocked và securityApproval false. Khi sửa source metadata được pin, cập nhật reference hash sau review thay đổi và sinh lại summary; không repin artifact lịch sử để che drift. Registry runtime attestation luôn false.

## Reforecast W3 và điểm bàn giao

Không đổi required R2/browser tracks, thresholds, oracle hoặc exit semantics của W0–W2. W3 chưa mở capability runtime mới. Sáu capability P0/browser/canonical/shared vẫn execution blocked; hai existing-contract được giữ nguyên và một capability verification offline. Native có failure đã biết; delegated cần loại credential copy, full sink access/seeded controls/encoding coverage và lifecycle proof trước mọi fresh admission. Runtime provenance và independent human acceptance vẫn pending.

Theo effort trong kế hoạch, W4–W11 còn khoảng19–30 ngày công cho một kỹ sư; đây là forecast, không suy từ wall-clock của lượt agent. N/C/H và thời gian chờ quyền/môi trường tính riêng. Browser secret path là dependency critical cho R2 đầy đủ, feasibility cần chốt đầu W7. R0 containment/registry đã được chuẩn bị, không tự cấp release/security sign-off. Checkpoint W3 ghi thời điểm bắt đầu/kết thúc, pin source, actual commands/exits, tests, preservation và reviewer pending; không giả lập ngày công đã tiêu hay approval.

Bước tiếp theo là W4 effective policy/resource preflight/partial evidence/stop trên runtime sẵn có. W5 mới đóng G3/G4 delegated. Rollback theo change-index/snapshot W3, giữ evidence; không bật lại mode credential-leaking để chữa lỗi và không reset/stash dirty upstream.
