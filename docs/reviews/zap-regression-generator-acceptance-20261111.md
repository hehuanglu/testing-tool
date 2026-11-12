# ZAP regression generator — implementation acceptance

Ngày nghiệm thu: 2026-11-12  
Kế hoạch nguồn: `docs/plans/zap-regression-generator-sol-implementation-plan-20261111.md`  
Repo: `hehuanglu/testing-tool`  
Nhánh: `codex/zap-regression-generator`  
PR: [#1 — Add deterministic ZAP regression suite](https://github.com/hehuanglu/testing-tool/pull/1)

## Kết luận

**A core complete.** Cả 20/20 mục nghiệm thu A đạt trên synthetic fixture, gồm generator,
runtime ZAP thật, parser, suite lifecycle, artifact, portable copy và GitHub xanh/đỏ thật.
Stable profile duy nhất là `passive-http-v1`; một case PASS chỉ là kết quả regression test,
không thay verdict hay trạng thái hoàn tất của assessment.

**ByteMe adapter qualification COMPLETE; real assessment transfer PENDING.** Registry đã có
`byteme-v1`, checkout ByteMe ở SHA đầy đủ, dựng database/keys/network disposable, gửi request
qua ZAP và đọc lại history/alerts thật. Case commit mang nhãn `product-qualification`; nó không
được đổi nhãn thành assessment. Ba RUN lịch sử không có `criteriaWorkflow` v3 và không được sửa.
Assessment-to-suite transfer vẫn chờ Gate 2, fresh evidence v3 và một assertion tương thích với
case đã duyệt; không có tuyên bố end-to-end real assessment transfer.

**B/C experiments:** B1, B2, B3, C1 và C3 có script, controls local/GitHub và vẫn ở mức
`experimental`. C2 là `blocked` vì image ghim có Firefox nhưng thiếu `geckodriver`. Async,
OAST, WebSocket, GraphQL và product-specific auth/BOLA vẫn `unsupported`.

## Provenance và bản build được nghiệm thu

- Implementation base: `c954ea870a4180e603fa8ff2926aacb78c74fde7`.
- Core feature: `343301f`; initial PR-head metadata attempt `054eeb8` (superseded by
  `277a675`); portable fix: `c9d17db`.
- Build có core + B/C experiments: `b9a0edb55cd36127eb765ba97e13867e9e641201`.
- Review repair cho fixture lifecycle và commit provenance: `277a6751464f4425367e81272731ddd8470d3bbb`.
- ByteMe adapter implementation: `1c3a022b8d86e6350c9c169a83bd5129a66ed27b`; checkout-origin
  normalization: `bee26723cd54dfc0692dec57e690a0d61580a45c`; Linux key-mount và service
  diagnostics: `19017bfd54abfc5a6ba3c1c219f92352cefc8c6e`; ZAP add-on drift lock:
  `e4ba996c85fb9df4e6be0b82b42421429d3aa7d8`, completed with all `start.*`
  updater gates at `7006f0e69b2e38649a9bd17bba03ae34ff0d3ed1`; nullable evidence
  references for pre-scanner failures: `f8d32d8d47f1e1b10dfef48cb19d229cba5a4131`.
- ByteMe source: `hehuanglu/ByteMe@510f6415b6af535ceec77213f0b0c7d5082123f7`;
  case `byteme-swagger-csp.json`:
  `sha256:ae0ad477dfbc82e4e0108af101d78a7a93673b304173145bbfa8799d08f4d137`.
- Image: `zaproxy/zap-stable@sha256:030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238`
  (ZAP 2.17.0).
- Case `csp-docs.json`: `sha256:7c1bb4924d6e68bdf4346fc6207ee23c07c37f47755f6a86e4a5310594c9aa4f`.
- Runner: `sha256:c926112ac0f699b78bb17b5967868fdb5c8b7b1e953046bd651b7e6a024bc882`.
- Report adapter: `sha256:89fcc0d5242f3a19f07346c5fcb701ac8a4d06358ce090f04addf163eac8b3fb`.
- Exporter: `sha256:9eadefee80f3546d744b12e271dfed7ff2a3c4f394f03a547bb4b80184d43b28`.

## GitHub evidence

| Gate | Run / SHA | Actual | Artifact readback |
|---|---|---|---|
| GH-01 stable green | [43077944312](https://github.com/hehuanglu/testing-tool/actions/runs/43077944312), PR head `277a675` | `success`; tested merge `63cf960`, PR head stored separately as `277a675` | ID `13882309264`, digest `sha256:f87377be2aaa77f2e06fb65eaf798db8e9c85d7869b6096aedccfee9419c1743` |
| GH-02 regression red | [43063128776](https://github.com/hehuanglu/testing-tool/actions/runs/43063128776), `8a7985a` | expected failure: `REGRESSION/PROTECTED_ALERT_PRESENT` | ID `13874930575`, digest `sha256:297146b100485a7c938b0282f19c18cd8d4f040c140dd061bbe2416079a86c39` |
| GH-03 missing traffic red | [43063376011](https://github.com/hehuanglu/testing-tool/actions/runs/43063376011), `84ba24f` | expected failure: `MISSING_EVIDENCE/REQUIRED_RESPONSE_MISSING` | ID `13874761541`, digest `sha256:72681a0dc4add94e1cac1f97c6adb0fe3bd091700a0bec0f23a6bdf6eb0268eb` |
| GH-04 restored final green | [43077934929](https://github.com/hehuanglu/testing-tool/actions/runs/43077934929), push, `277a675` | `PASS`, counts PASS=1 and all failure counts=0; `testedCommitSha` matched branch head and PR head was null | ID `13882184329`, digest `sha256:65af570408bd1d835ac15a2121e5c9559ba39e6916cc56c4450c7fa554e10398` |
| Qualification push | [43077934856](https://github.com/hehuanglu/testing-tool/actions/runs/43077934856), `277a675` | exporter 5/5, runtime 11/11, live records 13/13 | ID `13882014476`, digest `sha256:6de2a9ea21452bd32000f3261b437475a238860b4fdf9ede971484794faa33b0` |
| Qualification PR | [43077944347](https://github.com/hehuanglu/testing-tool/actions/runs/43077944347), PR head `277a675` | 13/13; all nested suites recorded tested merge `63cf960` and PR head `277a675` separately | ID `13883665301`, digest `sha256:71e0137c5ced1dd7fb9b7cc0a0d3807a77453743171e702a587b17ec39a1323d` |
| B/C experiments | [43077934663](https://github.com/hehuanglu/testing-tool/actions/runs/43077934663), `277a675` | all asserted controls completed; C1 records fixed-literal CSRF mode; C2 recorded `BLOCKED` | ID `13883486590`, digest `sha256:526fe0e80cc8999907ed942aa7b460ab4a18e53cd240d59b9e8bec11c5e0afb9` |

Các artifact trên đã được tải vào thư mục local bị ignore `artifacts/downloaded/<run-id>/` và
được parse lại. Push stable chứa đúng `testedCommitSha`; PR stable chứa đúng merge SHA từ
`refs/pull/1/merge` và `pullRequestHeadSha` riêng. Qualification references đều tồn tại;
experiment artifact không chứa hai bearer secret canary.

## ByteMe product adapter qualification

### Source, case và giới hạn claim

- Checkout nghiệm thu là clone sạch riêng của `hehuanglu/ByteMe`, full SHA
  `510f6415b6af535ceec77213f0b0c7d5082123f7`. Adapter ghi lại SHA thực tế, hash
  `Dockerfile`, application config, schema/seed, patch và image identity.
- Case là anonymous `GET /swagger-ui/index.html`, response bắt buộc `200 text/html` và assertion
  CSP ZAP `10038-1`. Căn cứ qualification là report lịch sử `SEC-02` yêu cầu Swagger UI có CSP;
  expected behavior không được học từ response đang quan sát.
- Upstream-original trả `X-Frame-Options: DENY` nhưng thiếu CSP. Vì vậy alert missing-CSP không
  chứng minh tiêu chí anti-framing bị vi phạm. Draft assessment hiện chọn `SEC-A06-06`, Gate 2
  còn pending; transfer thật cần profile kiểm tra cả `frame-ancestors` và XFO cùng fresh v3
  receipt-backed evidence.
- Ba `zap/*/RUN.json` của ByteMe không có `criteriaWorkflow`, approval hay case results v3, và
  còn bind source SHA lịch sử `e163fbb...`. Chúng chỉ dùng để hiểu bối cảnh, không được relabel,
  chỉnh sửa hay export như RUN v3.

Adapter tạo RSA 2048-bit và database password riêng mỗi invocation, không mở public port, dùng
một Docker network có ownership label, và xoá đúng bốn container, network, image cùng key temp.
Health/readiness traffic tách khỏi evidence. Detector control chạy ở loopback origin riêng trong
scanner container và chỉ chứng minh rule `10038-1`, không phải evidence ByteMe.

### GitHub runs và artifact readback

| Control | Run / source | Expected và actual | Artifact readback |
|---|---|---|---|
| Fixed push | [43131931712](https://github.com/hehuanglu/testing-tool/actions/runs/43131931712), `f8d32d8` | `PASS/CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER`; no add-on drift | ID `13905573006`, digest `sha256:09e13865fc3824b3dbd6942eed0181aa4b97a7c2c59711664b2af11e63490fc8` |
| Fixed PR | [43131937975](https://github.com/hehuanglu/testing-tool/actions/runs/43131937975), tested merge `3bdb064`, PR head `f8d32d8` | same PASS; merge SHA và head SHA lưu riêng; no add-on drift | ID `13905771761`, digest `sha256:23be0e5678380ef108a13f243d829fc6cec5549d20801dfefa9e8d0243932eae` |
| Upstream original | [43132022076](https://github.com/hehuanglu/testing-tool/actions/runs/43132022076), no patch | expected red: `REGRESSION/PROTECTED_ALERT_PRESENT` | ID `13906280404`, digest `sha256:acf2d03e70f7697dc38858a1c24aa740872841d93eb8a470d07d814d3b3b869a` |
| Regression control | [43132026812](https://github.com/hehuanglu/testing-tool/actions/runs/43132026812), fixed then reverse patch | expected red: `REGRESSION/PROTECTED_ALERT_PRESENT` | ID `13905033916`, digest `sha256:cb279c35c1260428ac1d51e08a72ae73e4776d2b2fe81d7fb2aef4ceb6910631` |
| Missing request | [43132030948](https://github.com/hehuanglu/testing-tool/actions/runs/43132030948), fixed obligation retained | expected red: `MISSING_EVIDENCE/REQUIRED_RESPONSE_MISSING` | ID `13905587095`, digest `sha256:f80d76d175482ec68f3cadeb33f783316d445df744ea02dc0fd8dfa99bdfe9f0` |
| Full qualification | [43131948517](https://github.com/hehuanglu/testing-tool/actions/runs/43131948517), `f8d32d8` | green harness; expected/actual matched for all 8 scenarios | ID `13906420590`, digest `sha256:35eccd5f878d01d290759de109875d9ea1c9d4b903366a83ebabc408898d2d65` |

Các artifact trên đã được download và parse. Mỗi artifact bind target actual/expected SHA đúng
`510f641...`; response có ZAP message ID, URL/method/status/media/header witness; alert có
`alertId`, `alertRef`, method và URL. Fixed có CSP nonempty và alert `10038-1` chỉ ở control;
original/regression có alert ở cả product và control; missing không có product receipt. Tất cả
references tồn tại, cleanup đủ sáu record, không có `zap-home`, private key, raw RUN, token,
database env hay raw response body. Startup failure không tạo scanner nên lưu `evidencePath: null`
thay vì một locator giả; mọi locator không-null đã được kiểm tra tồn tại. Full qualification không
có add-on install hay port collision trong ZAP logs; cleanup-failure giữ
`preCleanupStatus=PASS` sau khi sáu resource thực đã được xoá.

Hai run full-qualification trung gian đã phát hiện lỗi thay vì bị che: `43087907471` bắt được
add-on auto-update làm network add-on restart/port collision; `43091253537` cho thấy khóa đầu tiên
chưa đủ. Chúng không được dùng làm acceptance cuối. Bản cuối khóa cả `autoupdate.checkOnStart`
và bốn `start.*` updater gates, rồi được chứng minh lại bởi run `43131948517`.

### Reproduction

```bash
PYTHONPATH=.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src \
  python3 -m zap_assessment.cli regression generate \
  --input .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/examples/regression/byteme-csp-qualification-input.json \
  --out-dir tests/security/product-cases

python3 tests/security/product/byteme/run_acceptance.py \
  --product-source /clean/pinned/ByteMe \
  --out artifacts/byteme-qualification \
  --scenario all
```

Exporter unit tests đạt 7/7, runtime tests đạt 18/18. Local live qualification đạt 8/8:
fixed PASS; original và regression-control REGRESSION; omitted request và wrong response
MISSING_EVIDENCE; startup, scanner timeout và cleanup failure EXECUTION_ERROR. Cleanup failure
giữ `preCleanupStatus=PASS`; mọi result do cùng generator/runtime pipeline sinh, không viết tay.

## Acceptance A — 20/20

| Scenario | Mode / command | Expected | Actual | Status / locator |
|---|---|---|---|---|
| GEN-01 | offline, exporter unit + CLI | deterministic canonical bytes, second run `UNCHANGED` | hash ổn định; không timestamp/observed | PASS, qualification run `43077934856` |
| GEN-02 | offline, exporter unit + CLI | changed destination is not overwritten; exit 2 candidate | `REVIEW_REQUIRED`, original hash unchanged | PASS, qualification run `43077934856` |
| GEN-03 | offline, invalid fixture/basis/method/route corpus | specific error; no write/traffic | `INVALID_INPUT` or `UNSUPPORTED_OPERATION` at exact field | PASS, qualification run `43077934856` |
| GEN-04 | offline, synthetic RUN v3 + stale mutations | exact links export; stale revision/operation/path/context/role reject | valid export plus five rejects | PASS, qualification run `43077934856` |
| LIVE-01 | live-github, qualification harness | healthy CSP `PASS` with control and response/header witnesses | `PASS/CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER` | PASS, `qualification-results.json#/scenarios/0` |
| LIVE-02 | live-github, fixture `csp-regression` | docs native alert produces regression; distinct control/docs instances | `REGRESSION/PROTECTED_ALERT_PRESENT` | PASS, `qualification-results.json#/scenarios/1` |
| LIVE-03 | live-github, omit `docs` request only | obligation remains and evidence is missing | `MISSING_EVIDENCE/REQUIRED_RESPONSE_MISSING` | PASS, `qualification-results.json#/scenarios/2` |
| LIVE-04 | live-github, `missing-control` | clean report cannot pass without positive control | `MISSING_EVIDENCE/CONTROL_ALERT_MISSING` | PASS, `qualification-results.json#/scenarios/3` |
| LIVE-05 | live-github, `wrong-status` and `wrong-media` | login/status/media mismatch does not pass | `RESPONSE_STATUS_MISMATCH` and `RESPONSE_MEDIA_TYPE_MISMATCH` | PASS, `qualification-results.json#/scenarios/4-5` |
| LIVE-06 | live-github, deadline `0.01`, then healthy follow-up | `EXECUTION_ERROR/TIMEOUT`, cleanup, next run succeeds | timeout row followed by healthy `PASS` | PASS, `qualification-results.json#/scenarios/6-7` |
| PARSE-01 | offline runtime unit tests | exact origin/method/path/query/alertRef; preserve pointer and optional ID | exact-match and two-instance tests passed | PASS, qualification run `43077934856` |
| PARSE-02 | offline runtime unit tests | malformed/missing/capped native report fails closed | all malformed/capped cases rejected | PASS, qualification run `43077934856` |
| SUITE-01 | live-github lifecycle | add=2, delete=1, empty=0 without manifest/stale output | `PASS(2)`, `PASS(1)`, `EMPTY(0)` | PASS, `qualification-results.json#/scenarios/8-10` |
| SUITE-02 | offline runtime unit tests | duplicate ID, bad filename/schema, symlink fail before traffic; fixture setup/cleanup errors are recorded and later cases continue | all guards passed; injected bind and cleanup failures each produced `EXECUTION_ERROR`, artifacts and a later PASS | PASS, qualification run `43077934856` |
| ART-01 | live-github artifact readback | parseable references; no secret canary/private RUN | references true, canary false | PASS, `qualification-results.json#/scenarios/11` |
| PORT-01 | live-github copied bundle without assessment `PYTHONPATH` | same entrypoint returns one PASS | exit 0, `PASS`, count 1 | PASS, `qualification-results.json#/scenarios/12` |
| GH-01 | live-github PR stable | green with tested merge SHA distinct from PR head | run `43077944312`: tested `63cf960`, PR head `277a675` | PASS |
| GH-02 | live-github deliberate CSP regression commit | red with regression reason; artifact retained | run `43063128776` expected failure, artifact parsed | PASS |
| GH-03 | live-github deliberate missing-traffic commit | red with missing-evidence reason; artifact retained | run `43063376011` expected failure, artifact parsed | PASS |
| GH-04 | live-github repaired implementation build | stable and qualification green; push/PR provenance matches actual checkout | runs `43077934929`, `43077934856`, `43077944312`, and `43077944347` success | PASS |

The negative demonstration commits were reverted with normal history (`cc7213b`, `87026c5`);
no force-push erased their evidence.

## B/C experiment results

All commands use the pinned ZAP image and write a new output directory. Results below come from
GitHub run `43077934663`; local controls were also run before push.

| Capability | Controls and actual result | Status |
|---|---|---|
| B1 `openapi-passive-v1` | good: `PASS/OPENAPI_IMPORTED_AND_ITEMS_REQUEST_WITNESSED`; missing route: `MISSING_EVIDENCE/REQUIRED_ROUTE_NOT_COVERED`; packaged scanner exit 2 (WARN) retained separately | experimental |
| B2 `bearer-passive-v1` | good: `PASS/STATIC_BEARER_ACTOR_AND_MARKER_WITNESSED`; bad: `MISSING_EVIDENCE/AUTH_LOST`; both canaries absent from artifact | experimental |
| B3 `active-xss-v1` | ZAP 2.17.0 rule `40012`; vulnerable: `REGRESSION`; fixed: `PASS`; auth-lost: `MISSING_EVIDENCE`; native instance and active-rule header witness required | experimental |
| C1 `form-cookie-csrf-v1` | Uses one CSRF literal hard-coded in the login body; it does not fetch/extract/rotate a token. Healthy: `PASS/FORM_COOKIE_CSRF_AUTH_WITNESSED`; revoked session: `PASS/SESSION_REFRESH_WITNESSED`; bad fixed literal: `MISSING_EVIDENCE/AUTH_LOST` | experimental |
| C2 `browser-journey-v1` | Firefox found; `geckodriver` missing; no personal browser/spider substituted | blocked |
| C3 `bola-two-actor-v1` | fixed: `PASS`; vulnerable: `REGRESSION/OTHER_ACTOR_READ_OWNER_OBJECT`; auth-lost: `MISSING_EVIDENCE`; read-only post-state unchanged | experimental |

The experiments are deliberately outside `tests/security/cases/` and the stable PR workflow.
A green spike does not promote a profile automatically. Promotion still requires a versioned
stable contract, two independent healthy runs, negative and incomplete controls, clean
artifacts, cleanup proof and GitHub qualification in the target product context.

## Main deliverables and operation

- Generator: `zap-assessment regression generate`, schemas v1, synthetic and RUN v3 adapters.
- Stable case source: `tests/security/cases/csp-docs.json`, generated by the CLI.
- Portable runtime: `tests/security/run_zap_suite.sh`, stdlib Python runner/report adapter,
  isolated fixture/session/output, deadlines and four-state verdict.
- CI: stable, qualification, passive smoke and isolated experiment workflows with pinned action
  SHAs and always-upload artifacts.
- Skill integration: `.agents/skills/mcp-zap-repo-operations/references/ci-regression-suite.md`
  and capability registry.

Typical commands:

```bash
PYTHONPATH=.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/src \
  python3 -m zap_assessment.cli regression generate \
  --input .agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment/examples/regression/csp-reviewed-input.json \
  --out-dir tests/security/cases

bash tests/security/run_zap_suite.sh \
  --cases tests/security/cases \
  --out /tmp/zap-regression-output
```

## Remaining work

1. Hoàn tất Gate 2 cho assessment ByteMe, chạy fresh assessment v3 và review case/result/evidence.
   Nếu giữ `SEC-A06-06`, implement và qualify assertion anti-framing hiểu cả CSP `frame-ancestors`
   và `X-Frame-Options`; sau đó mới export một `assessment-run-v3` case. Case CSP hiện tại chỉ là
   adapter qualification và không được dùng để tuyên bố transfer thật.
2. Pin/package a `geckodriver` version matching the image Firefox, then implement the fixed
   open/click/wait and no-click browser controls through the ZAP proxy.
3. Promote experimental profiles only after their remaining stable-contract gates are met;
   do not infer generic auth, API, active-scan or BOLA support from the synthetic fixtures.

