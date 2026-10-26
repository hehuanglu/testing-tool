# BE-authenticated — broker và diagnostic ngày 20/10/2026

**Partial implementation; operational/product admission vẫn blocked.**

Lượt private HSQL reader mới:
[ghi chú triển khai](../../../test-artifacts/be-authenticated-db-20261020T083344Z/IMPLEMENTATION_NOTES_VI.md),
[tiến độ](../../../test-artifacts/be-authenticated-db-20261020T083344Z/PROGRESS_VI.md),
[tái lập](../../../test-artifacts/be-authenticated-db-20261020T083344Z/REPRODUCE_VI.md).
Plan1.2 chỉ opt-in với `--source-mode private-file --private-db-controls` ở prepare.
Holder audit actual private-source control và saved-session qua private socket/child
pipes; raw source/typed cells không đi qua controller. Control là separate actual
HSQL file DB,5encodings×TEXT/BINARY, không thay seed live ZAP sink. Verifier giữ
G3/product G4 blocked; checkpoint mới ghi kết quả A/B/fault khi đã xác minh.

Kế hoạch: [BE-00–BE-09](../../../QUY_TRINH_HOAN_THIEN_BE_AUTHENTICATED_2026-10-20.md).
Checkpoint: [nhật ký](../../../test-artifacts/be-authenticated-20261020T065558Z/PROGRESS_VI.md),
[work items](../../../test-artifacts/be-authenticated-20261020T065558Z/work-items.json),
[native/platform ADR](../../../test-artifacts/be-authenticated-20261020T065558Z/NATIVE_AND_PLATFORM_ADR_VI.md).

Lượt tiếp tục source-reference và monitor:
[bàn giao](../../../test-artifacts/be-authenticated-source-20261020T073718Z/HANDOFF_VI.md),
[nhật ký mới](../../../test-artifacts/be-authenticated-source-20261020T073718Z/PROGRESS_VI.md),
[contract nguồn](../../../test-artifacts/be-authenticated-source-20261020T073718Z/SOURCE_REFERENCE_CONTRACT_VI.md).
Checkpoint cũ giữ nguyên; source pins của từng bundle quyết định current/historical.
Fresh A4/B2 cùng source cuối: mỗi run15cases,16receipts nguồn và14resolutions;
full offline readback pass, cleanup clean. Hai current-readiness outputs và các
attempt failed/historical được giữ ngoài sealed bundles. Xem
[phần việc còn lại](../../../test-artifacts/be-authenticated-source-20261020T073718Z/REMAINING_WORK_VI.md)
cho dependencies chưa được nghiệm thu.

External fault mới có native state RUNNING, initiator2/rule40012 và correlated
protected target arrival trước SIGKILL đúng holder ID. Sau confirmed stop, target
journal không đổi; interrupted bundle vẫn blocked/partial, complete verifier từ
chối, recovery stop-only/no-replay. Controller v1 lỗi no-clobber final receipt được
giữ nguyên; chỉ v2 có đủ durable intent/final receipt. Full regression cuối507/507.

## Source và phạm vi

- `src/zap_assessment/credential_broker.py`: private external source/reference,
  generated holder source, actor/run/plan/build/deadline binding và operation scope.
  Dùng lại ActorSession cho identity/epoch/latch/stop; public methods không trả token,
  password hoặc public real-password fingerprints. Object phải ở vùng secret cô lập.
- `src/zap_assessment/w5_scanner_fixture.py`: owned boundary protected dispatch đi
  qua broker. Adapter/egress guard là trusted code; origin metadata không thay actual
  independent wire proof. Không thêm product URL/credential input hoặc P0 bypass.
- `src/zap_assessment/private_source.py`: source zone thật trong holder tmpfs,
  directory0700/file0600, no-follow/single-link, immutable metadata; resolve journal
  gắn đúng actor/run/plan và target login. Metadata không xuất source values/content
  hashes. Đây là nguồn synthetic W5, chưa là operator-provided product source.
- W5 supervisor tách resource và policy workers; cả hai completed-read timelines
  vẫn tối đa5giây. Resource worker chạy tiếp qua final policy/cleanup. Policy quá
  hạn cũng latch owned stop dù resource còn fresh; sampler timing chỉ là telemetry.
- `scanner_secret_audit.py`: seeded HSQL control phải có distinct TEXT/BINARY SQL
  families; cell table binding/duplicate tables/post-terminal records bị kiểm.
  Counterexamples trước fix được giữ, không chỉnh artifact để làm xanh.
- `scripts/be_authenticated_preflight.py`: offline W5 verifier + 143-pair missing
  proof inventory. Partial observations không được promote; helper không là product
  operational attestor và không có execution/admission override. Nó đối chiếu đầy
  đủ source pins hiện tại để phân biệt current-source và historical-source readback.

## Commands đã dùng và cách tái lập

Từ package root, dùng output mới theo [W5 runbook](W5_SCANNER_CONTINUATION_VI.md) và
resource profile source thực. Không tái chạy output directory của checkpoint:

```sh
PYTHONPATH=src:tests .venv/bin/python -m unittest test_credential_broker test_scanner_secret_audit test_be_authenticated_preflight -q
.venv/bin/python scripts/remediation_w5_scanner.py --help
.venv/bin/python scripts/be_authenticated_preflight.py --help
.venv/bin/python scripts/remediation_w5_scanner.py prepare --work-dir FRESH_ABSOLUTE_DIR --actor A --resource-profile bounded-fixture --source-mode private-file
```

External locks và exact argv/exit nằm trong `scanner-A-external-lock.json`,
`scanner-B-external-lock.json` và các `*-command-receipt.json` ở checkpoint.
A/B dùng cùng source pins, actors/run/plan khác nhau. Verifier chỉ đọc bundle,
không Docker/HTTP; readiness output phải mới và ngoài sealed bundle. Exit0 của
diagnostic/readback không là security pass hoặc product admission.

Controller interruption dùng đúng PID process do lượt chạy tạo. Guard fault có
external fault-plan hash trước execution, kiểm exact creation ACK/container ID/image/
run label rồi mới SIGKILL. Post-confirmed-stop target journal không đổi; khoảng từ
fault request đến confirmed stop không được gọi zero-in-flight. Recovery giữ journal
gốc, không replay start/login/refresh/mutation. Failed attempts đều giữ nguyên.

## Điểm còn thiếu

Generic broker có primitive và private-file child HTTP proof. W5 plan1.1 đã có
owned private-file reference đi qua MCP/scanner; plan1.0/generated vẫn là contract
riêng. Không suy nguồn operator/product hoặc platform acceptance từ W5 family.
G3 cần actual private-source seeded access/decoder/
lifecycle proof theo sink, cùng platform swap/dumps/transport acceptance. No-swap
container hoặc core limit0 không tự giải quyết host virtualization memory persistence.
HSQL TEXT/BINARY positive control hiện là public DB control; không thay private
source seeded control ở từng sink/lifecycle. Ma trận143cặp chưa có full acceptance.

Source discovery có 19 operations, global prefix `/api`; accounts list có `user_id`
từ authenticated principal, candidate subject oracle. Cần fresh runtime envelope,
independent expected actor/binding và auth epoch trước product continuity claim.
Không giả product role, không lấy membership/JWT claims riêng lẻ thay identity proof.

Product authenticated passive/active DAST, business mutation/post-state, operational
attestor và authenticated fixed-build regression chưa được chạy/admit. Owned selected
active rule requests không chứng minh vulnerable/fixed detection hoặc product G9.
Native giữ known persistence blocker; independent/security acceptance pending.

## Rollback và bảo toàn

Checkpoint `source-before/` giữ bản trước của các file sửa; `baseline-index.json`
giữ hashes và `scanner-before.diff` giữ upstream dirty diff. Rollback chỉ diff của
lượt này và file mới trong change index; giữ evidence, failed attempts, private-source
boundaries và raw report readback. Không reset/stash, prune, down-v hay sửa target DB.
Installer staging cleanup là hành động riêng theo quyền user và có receipt riêng;
không coi xóa cache staging là thay đổi product/scanner deployment.
