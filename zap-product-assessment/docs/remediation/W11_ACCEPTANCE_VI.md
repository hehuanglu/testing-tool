# W11 — alternate conformance, compatibility và handoff

Contract `w11-conformance-handoff/v1` chuẩn bị nghiệm thu trong scope owned synthetic.
**G7 synthetic generalization có proof; G12-D reproducibility prepared; operational
G12-D/R1/R2 blocked và independent acceptance pending.** Không có reviewer approval
tự sinh. Browser secret persistence vẫn observed failure, không skip hoặc pass.

## Alternate product và core dùng chung

Ba business runs mới dùng cùng W6 core/state replay/verifier/source pins: primary
finalsource-shaped với numeric IDs và envelope `data`; alternate-ledger với string
IDs, `PATCH /vault/wallets`, `/journal/*`, integer units và envelope `result.value`.
Hai alternate runs khác IDs/order; một là API child của unified assessment mới.
Actual request/response/arrival và direct-file post-state được replay độc lập.
Mỗi run giữ đủ66 assertions cùng actor/operation/resource/positive-control shape,
không sửa core theo fixture ID hoặc adapter name.

`w11_acceptance.py` chỉ nhận actual W6/W9 evidence đã được independent verifiers
đọc lại. Nó kiểm freshness/disjoint IDs, ID types, routes/methods và successful
response envelopes thực nhận. Chỉ đổi tên adapter không đủ; core/source/required
assertions/gap inventory đổi, reused IDs hoặc thiếu repeat sẽ blocked. Envelope và
route logic chỉ nằm trong conformance checker, không thêm product branch vào core.

Fresh unified alternate run giữ session → API → actual UI → active vulnerable/fixed
→ post-state → verification. Parent/API child linkage và final source pins phải khớp.
Không dùng business HTTP/unit corpus thay actual browser. Existing explicit phase
clones vẫn là các DB branches riêng; chưa single live product DB/MCP workflow.

W10 regression CLI/root wrapper đọc fresh active pair của chính unified run này.
SQLi/XSS có equivalent fixed oracle thì local remediationVerified; browser secret
failure vẫn giữ whole-assessment security fail/gate block. Không mở protected/native,
JSON bearer, canonical hoặc shared/HA execution.

## Locked request và exit semantics

Prepare khóa primary/alternate/repeat/unified plan pins và manifest hashes, current
verifier/entry source, W10 request/result hashes. External request SHA kiểm trước
readback; nguồn hoặc input đổi phải prepare request mới. Output phải là namespace
mới. Result chỉ publish sau replay; verify so canonical recomputation, không tin
saved summary hoặc candidate approval fields. Symlink/unsafe/oversize artifact bị
existing BundleReader từ chối.

Run exit0 chỉ diagnostic conformance complete; run exit1 là conformance blocked;
invalid evidence/request exit2. **Mọi result vẫn gateDecision=block**, G12DOperational
blocked và independentAcceptance pending. Verify exit0 chỉ consistency, kể cả fail.
Không dùng exit0 này làm production release gate. Root W10 wrapper giữ contract
0/1 riêng; không gọi W11 verify để cho CI pass.

## Reproducible sequence

Fresh runtime commands đã chạy từ package root; output phải mới khi rerun:

```sh
PYTHONPATH=src .venv/bin/python scripts/w6_business_campaign.py --output /absolute/new-primary --seed 11101
PYTHONPATH=src .venv/bin/python scripts/w6_business_campaign.py --output /absolute/new-alternate-repeat --seed 11102 --adapter alternate-ledger --reverse
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py prepare --output /absolute/new-plans/unified.json --seed 11103 --adapter alternate-ledger --reverse
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py run --plan /absolute/new-plans/unified.json --expect-plan-sha EXTERNAL_UNIFIED_SHA --output /absolute/new-unified
PYTHONPATH=src .venv/bin/python scripts/w9_unified_campaign.py verify --bundle /absolute/new-unified/bundle --expect-plan-sha EXTERNAL_UNIFIED_SHA
```

Dùng plan pins từ receipts ngoài bundle, không tự chấp nhận baseline. Chuỗi thực tế
W10 prepare→compare→root wrapper và W11 prepare→run→verify có exact argv/exit ở
[sequence receipts](../../../test-artifacts/mcp-zap-remediation/w11-acceptance-20261019T160915Z/sequence-command-receipts.json).
W11 `prepare --help` liệt kê bốn cặp `--ROLE-bundle/--ROLE-plan-sha` cho primary,
alternate, repeat, unified; thêm `--regression-request`, `--regression-request-sha`,
`--regression-result`, `--output`. Alternate input chính là verified unified API
child, không bundle tự gắn nhãn parent hồi tố.

Offline rerun/verify với external acceptance request SHA:

```sh
PYTHONPATH=src .venv/bin/python scripts/w11_acceptance.py run --request /absolute/acceptance.json --expect-request-sha EXTERNAL_REQUEST_SHA --output /absolute/new-acceptance
PYTHONPATH=src .venv/bin/python scripts/w11_acceptance.py verify --request /absolute/acceptance.json --expect-request-sha EXTERNAL_REQUEST_SHA --result /absolute/new-acceptance/result.json
PYTHONPATH=src .venv/bin/python scripts/w11_acceptance_controls.py --request /absolute/acceptance.json --expect-request-sha EXTERNAL_REQUEST_SHA --output /absolute/new-controls
PYTHONPATH=src:tests .venv/bin/python -m unittest test_acceptance test_binding test_verification_v2 test_bola test_bola_operational test_bola_borrowed test_business test_ui test_active test_unified test_regression -q
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -q
PYTHONPATH=src .venv/bin/python -m zap_assessment.capabilities check
```

Request/source/input paths là local absolute paths. Chuyển máy/checkout cần prepare
request mới và external pin mới, không sửa core/IDs để khớp bundle cũ. Một operator
khác còn phải thực chạy offline sequence cùng fresh authorized run và ghi review
record thật; prepared instructions không phải independent acceptance.

## Compatibility, operational limits và next action

Focused tests kiểm contracts legacy anonymous/binding, BOLA1.2–1.4 read-only, v2
verifier/tamper, W6–W10. Readback helper giữ historical source mismatch phân loại
riêng, không biến legacy evidence thành current capability. Root Python suite giữ
scanner v3, suppression expiry, seed/enforce và wrapper behavior. Không sửa root
Java/auth/queue hoặc packaging; Java/Docker integration và artifact build cũ không
được gọi current-source acceptance của lượt này. Assessment Markdown links,
generated registry summary và evidence references được kiểm; public Astro docs và
packaging source không đổi nên không build/install lại node dependencies.

Coverage gaps populated bills/category provisioning/cross-owner create/product
runtime vẫn giữ nguyên và không cộng vào pass. Production broker/per-sink lifecycle
G3/G4, browser secret-safe N/C path, canonical fidelity, product/MCP/live-DB G10,
product regression G11, shared/HA và independent/security approval vẫn mở.

W0–W11 diagnostic implementation có thể bàn giao; full R2 chưa đạt. Bước kế tiếp
là xử lý các operational dependencies hoặc người độc lập chạy prepared sequence;
không tự mở N/C/H hoặc approve baseline/release. Rollback gỡ W11 scripts/tests/docs,
restore registry/status/skill summary từ checkpoint baseline-source và regenerate
capabilities; giữ fresh evidence, private browser profiles và existing containers/DB.

Checkpoint: [W11 handoff](../../../test-artifacts/mcp-zap-remediation/w11-acceptance-20261019T160915Z/HANDOFF_VI.md).
