# W9 — normalized orchestration và stop-only recovery

Contract `w9-owned-unified-diagnostic-1` bổ sung một entry point `prepare → run →
verify`, cùng `recover` chỉ dừng tài nguyên. Chỉ owned synthetic, không product URL,
credential input, borrowed mutation, shared scanner hoặc native/delegated admission.

## Plan và các track bắt buộc

Plan khóa assessment ID, source pins, seed/adapter, container/image identities,
fixture/actor/resource scope hash, required graph và epoch policy. Required tracks
luôn gồm session spike, API business/BOLA, UI thật, active vulnerable, active fixed,
post-state và independent verification. Không có cờ bỏ browser sau khi chạy.

Child W6/W7/W8 runners nhận optional binding gồm parent plan hash, assessment ID,
phase, child run ID, fixture/scope hash và `fresh-memory-only-stop-on-restart`.
Worker echo binding vào observations khi thực thi; không gắn nhãn parent hồi tố
lên bundle cũ. Target request IDs gắn child run và các verifier hiện có kiểm actual
actor/resource/response/state. W9 kiểm liên kết cả hai chiều và child source/image.
Session spike của chính assessment phải precede UI; không reuse spike run khác.

API và UI là **phase-isolated fixture clones**, dùng chung logical actors/resource
IDs/initial state từ seed, có run/provenance riêng. Post-state kiểm từng state branch
bằng independent W6 replay, không giả rằng API và UI đã dùng cùng live product DB.
Active SQLi/XSS là fixture riêng với anonymous scope; không được suy auth A/B sang
active track. Mô hình này kiểm plumbing, dependency và evidence aggregation; single
live product workflow/MCP end-to-end vẫn chưa chứng minh.

## Aggregation và evidence

Hash-chained journal khóa plan → preflight → từng track intent/record → post-state →
verifying. Intent giữ exact name/image/run/volume trước create. Dependency/order,
required coverage, source drift và output mới được enforce ở entry point.

Parent bundle giữ bản sao đầy đủ các child bundles, plan, journal, track matrix,
active pair, post-state và summary. Publication atomic sau readback. Verifier dùng
safe bounded BundleReader, external parent pin, đọc và replay **mọi** child; không tin
summary, child exit code hoặc phase khác để bù missing/failed track. Tamper kể cả
recomputed hashes/child metadata/rechained journal vẫn phải qua semantic checks.

Functional verdict, evidence completeness, observed security failure và operational
gate tách riêng. W7 persistent-canary failure được giữ ở session/UI và toàn assessment.
Diagnostic continuation chỉ thu thập synthetic evidence; không biến failure thành
skip/pass. Orchestration có thể verified khi các functional controls đủ, trong khi
`securityVerdict=fail`, `gateDecision=block`, `G10Operational=blocked`, R1/R2 không admit.
UI functional error không được active/API pass che đi; child development expectation
không phải aggregate acceptance.

## Gián đoạn và recovery

Không có resume/replay login hay scan trên plan cũ. Restart cần assessment/plan mới,
fresh in-memory canaries/session và fixture IDs mới, hoặc stop. `recover` không gọi
target API/ZAP start/auth. Nó đọc original plan/journal bằng external pin; stop/remove
chỉ exact owned ID/name/image và đủ run/assessment/phase/plan labels. Creation ACK
được reconcile nếu có; lost ACK không phát start lần hai.

Browser profile volume cần đúng mounted volume và ownership trước đọc/retention.
Raw profile giữ private ngoài workspace,0600/0700 và indexed hashes trước remove.
Volume thiếu reader/container có thể quarantine, không xóa rồi báo clean. Active
captures nếu còn đọc được chỉ là partial prefix, không được tính coverage/Complete.
Recovery ghi journal/result **mới**, kiểm journal gốc nguyên bytes, giữ observed
findings, execution interrupted/evidence incomplete/gate block. Không seal bundle
complete thay cho run đã gián đoạn. Daemon outage/shared failover không được suy ra
từ SIGKILL controller.

## Resource và vận hành

Các child giữ resource/isolation contracts W6–W8. Parent preflight giữ
`2×192MiB + 2GiB reserve`; không hạ floor. Child chạy tuần tự; chỉ private UI profile
và minimized bundles tồn tại trên host. Đây chưa phải G6 calibration/SLO mới cho
mọi workload. Controller interruption không cho quyền dọn tài nguyên borrowed.

Theo chỉ đạo user chỉ có dự án này, cleanup W9 chỉ dọn dependency/build output có
thể tái tạo: docs/packaging node_modules, Astro/dist, compiled classes/resources/tmp,
unpacked/bundle staging. Giữ jars/MCPB, test XML/reports, source/DB/backup/evidence,
19 container identities và runtime cache Codex đang dùng; không Docker prune.
`storage-cleanup.json` ghi đúng trước/sau và paths; biến động free space khác không
được cộng thành bytes do cleanup giải phóng.

## Commands

Từ package root, output phải mới; copy plan SHA từ prepare receipt ngoài bundle:

```sh
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py prepare --output /absolute/new-plan.json --seed 9101
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py run --plan /absolute/new-plan.json --expect-plan-sha EXTERNAL_PLAN_SHA --output /absolute/new-run
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py verify --bundle /absolute/new-run/bundle --expect-plan-sha EXTERNAL_PLAN_SHA
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py recover --run-path /absolute/interrupted-run --expect-plan-sha EXTERNAL_PLAN_SHA --output /absolute/new-recovery
PYTHONPATH=src .venv/bin/python scripts/w9_unified_controls.py --bundle /absolute/run-a/bundle --expect-plan-sha PLAN_A_SHA --other-bundle /absolute/run-b/bundle --other-plan-sha PLAN_B_SHA --output /absolute/new-controls
PYTHONPATH=src:tests .venv/bin/python -m unittest test_unified test_ui test_business test_active -q
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
```

`prepare --adapter alternate-ledger --reverse` kiểm fixture khác route/envelope/ID shape.
`--fault-ui wrong-balance` hoặc API fault là explicit diagnostic controls, không product
mutation. Run exit0 chỉ orchestration diagnostic verified; completed functional failure
exit1; missing/invalid/partial execution exit2. Verify exit0 là consistency, kể cả gate
blocked/security fail. Recovery exit0 chỉ confirmed stop/cleanup, không nâng verdict.

## Compatibility và giới hạn

Optional child binding giữ standalone W6/W7/W8 entry points và historical verifier
contracts. UI schema thêm optional field, không đòi historical bundles phải có W9
linkage. W9 chỉ nhận current linked children, không nâng historical corpus thành fresh
run. W5 operational, W7 secret failure, N/C, product build/auth/DB continuity, all143
sink/lifecycle pairs và independent/security approval vẫn là dependencies riêng.

Rollback tắt entry point W9, gỡ module/controls/tests mới và restore các modified child
files/schema/plan/registry từ checkpoint baseline-source. Giữ toàn bộ journals,
private retention và evidence; không reset root dirty spike hoặc DB/container cũ.

Checkpoint: [HANDOFF_VI.md](../../../test-artifacts/mcp-zap-remediation/w9-unified-20261019T145432Z/HANDOFF_VI.md).

## Các hardening trong integration

Fixture browser dùng bounded threaded HTTP server: idle preconnect không được chặn
request document/fetch khác. Regression loopback tái hiện server cũ bị chặn; không
lấy kiểm tra server này thay browser flow. Một số startup attempts còn báo `no such
window / browsing-context-discarded`, được giữ nguyên với private profile retention.
Driver mới đợi initial document ready và tạo/chọn một tab riêng **một lần** trước target
navigation; không retry toàn flow, không retry mutation để che lỗi UI. Với custom
profile, fixed Marionette port theo [Geckodriver Profiles](https://firefox-source-docs.mozilla.org/testing/geckodriver/Profiles.html);
context creation dùng [WebDriver New Window](https://developer.mozilla.org/en-US/docs/Web/WebDriver/Reference/Classic/Commands/NewWindow).
Chỉ categorical error/stage và cgroup counters được export; không raw command/error
messages hoặc credential values. Đây không phải proof SLO/stability của Firefox.

Normal publication và recovery đều đọc namespace closure bằng Docker API khỏe.
Container/volume inspection failure không được mặc định thành absence. Volume chỉ
absent khi listing thành công xác nhận; namespace còn resource hoặc Docker state
unknown thì blocked/quarantined. Unknown/foreign resources không được auto-delete.

Checkpoint current:2 fresh complete assessments,1 actual functional-failure control,1 real controller SIGKILL + stop-only recovery.25 unified unit tests,443 full-suite tests và25 offline controls đạt. Browser functional/secret statuses vẫn riêng; G10 operational blocked. Root current source snapshot và exact commands ở handoff.
