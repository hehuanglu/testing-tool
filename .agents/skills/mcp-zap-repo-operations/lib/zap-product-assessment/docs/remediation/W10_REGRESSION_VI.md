# W10 — regression A→B và CI exit mapping

`assessment_regression/v1` là contract mới, độc lập với root scanner diff
`ci_gate_findings_diff/v3`. Field `resolved` lịch sử giữ nghĩa cũ. Comparator W10
không dùng `resolved`, không auto baseline, không tự suppress và không cấp R1/R2.

## Inputs và comparability

`w10_regression.py prepare` khóa request canonical bằng external SHA: hai bundle
paths, hai external plan pins, hai input manifest hashes, kind, enforce/seed, required SQLi/XSS, versioned scope
amendments và verifier source pins. Manifest không được thay sau prepare, kể cả khi
artifact hashes đã tính lại. Compare kiểm pin trước đọc evidence, rồi replay
W8 hoặc toàn W9 bằng BundleReader bounded/no-follow và independent oracle.
Không nhận normalized views/result summary do caller cung cấp. Corrupt evidence
không xuất complete comparison. Source đổi phải prepare request mới; không sửa
request cũ rồi coi cùng source.

Scanner version/image và full installed add-on ID/version/status phải matching;
unknown/legacy inventory không comparable. Inventory order không tạo drift giả.
Scope/routes/method/parameters/sinks, required verified coverage, auth continuity,
effective rules/scripts/proxy/vectors, fixture semantics và oracle version/source
được so riêng. A/B target build hashes giữ riêng: build change là biến chủ định,
không đòi cùng build. Hai run IDs phải khác. Fresh tagged fixture values được map
sang cùng logical vectors/business seed semantics; không so raw resource IDs.

Kind `active` chỉ hỗ trợ owned anonymous GET query SQLite SQLi40018/HTML body
XSS40012 của W8. Auth ở đây explicit N/A, không phải proof login/refresh của product.
Target implementation fixture có cùng source và variant build khác nhau. Target
source đổi ngoài fixture contract này conservative incomparable; chưa có product
regression adapter. Kind `unified` replay toàn required W9 tracks và bindings trước
so active-vulnerable A với active-fixed B. Không dùng API/active pass che UI/auth gap.
Business adapter/required graph/state model/epoch policy phải equivalent; parent
browser secret failures và operational-unverified blocker giữ nguyên.

`observedRemoved` chỉ nói scanner observation đã biến mất. `remediationVerified`
chỉ liệt kê **selected anonymous active techniques** khi cả A/B có equivalent valid
exercise, A có scanner detection + independent vulnerable witness, B không alert
và independent fixed oracle. B vẫn vulnerable thì security fail dù scanner silent.
Missing route/login/rule/sink hoặc fixture/oracle/policy drift không thành fix.
Versioned `scope_amendment/v1` có technique/disposition/reason ghi retirement riêng,
luôn review/block, không biến thành retested remediation.

W9 có thể ghi local active remediation nhưng toàn assessment vẫn security fail và
block. `G11Synthetic=pass` chỉ khi bounded active comparison exit0; không full G11
product/operational acceptance, G3/G4/G8/G10/R1/R2 hoặc independent approval.

## Exit contract và wrapper

- Assessment compare exit0: equivalent A→B fixed trong scope synthetic đã khai báo.
- Exit1: current vulnerability/observed security failure, kể cả đồng thời có gap.
- Exit2: invalid, missing/incomparable proof, source drift, same-run reuse hoặc
  incomplete remediation. Corrupt input không xuất result complete.
- Exit3: seed review candidate; không enforce-pass, không approve baseline.
- Verify exit0 chỉ result khớp replay, kể cả result exit1/2/3; không dùng verify làm CI gate.

Root `mcp_zap_gate.py assessment-regression` gọi comparator thực, map assessment0→0
và mọi nonzero/signal/execution error→1. Wrapper `run-assessment-regression.sh` dùng
`exec`, không Docker/login/start/cleanup. Existing `run-gate.sh`, action.yml và GitLab
scanner flow giữ contract cũ. Operator chọn explicit offline wrapper cho W10;
không tự gửi traffic hoặc dùng result JSON như chứng nhận pass.

New comparator không hỗ trợ suppressions; supplied suppression args bị từ chối.
Legacy suppression expiry vẫn được root tests kiểm theo contract cũ. Seed review
không tự copy candidate thành baseline. Route retirement cần request mới có amendment,
không tự drop technique khỏi required set.

## Command sequence

Từ `zap-product-assessment`, lấy plan pins từ receipt ngoài bundle; output phải mới:

```sh
PYTHONPATH=src .venv/bin/python scripts/w10_regression.py prepare --baseline /absolute/A/bundle --baseline-plan-sha PLAN_A_SHA --current /absolute/B/bundle --current-plan-sha PLAN_B_SHA --kind active --output /absolute/new-request.json
PYTHONPATH=src .venv/bin/python scripts/w10_regression.py compare --request /absolute/new-request.json --expect-request-sha REQUEST_SHA --output /absolute/new-comparison
PYTHONPATH=src .venv/bin/python scripts/w10_regression.py verify --request /absolute/new-request.json --expect-request-sha REQUEST_SHA --result /absolute/new-comparison/result.json
bash ../mcp-zap-server/.github/actions/zap-security-gate/run-assessment-regression.sh --assessment-root "$PWD" --assessment-python "$PWD/.venv/bin/python" --request /absolute/new-request.json --expect-request-sha REQUEST_SHA --output-dir /absolute/new-root-comparison
PYTHONPATH=src .venv/bin/python scripts/w10_regression_controls.py --w8-evidence /absolute/w8/accepted --w9-current /absolute/w9/current --output /absolute/new-controls
PYTHONPATH=src:tests .venv/bin/python -m unittest test_regression -q
PYTHONPATH=src:tests .venv/bin/python -m unittest discover -s tests -q
```

Root tests từ `mcp-zap-server`: `python3 -m unittest discover -s tests/python -p
'test_mcp_zap_gate.py' -q`. Chỉ Python/docs thay đổi: không cần Java/image rebuild
hoặc native campaign mới. Exact argv/exit, original input pins và output hashes nằm
trong checkpoint; matrix là **offline replay/tamper controls trên actual historical
evidence**, không mới chạy login/route-failure runtime hay quét product.

## Giới hạn và rollback

W5 G3/G4 operational, W7 secret persistence, W9 phase-clone/single-live-DB/MCP gaps
và independent review vẫn mở. Suppression không dùng ở new gate. Thay đổi không
đưa credential thật vào runner. Không sửa bundle W8/W9 hoặc dirty Java/auth spike.
Rollback gỡ W10 module/scripts/tests/wrapper/docs, bỏ root subcommand và restore
registry/generated summary/plan từ baseline-source; giữ evidence và DB/container cũ.

Checkpoint: [W10 handoff](../../../test-artifacts/mcp-zap-remediation/w10-regression-20261019T155107Z/HANDOFF_VI.md).
