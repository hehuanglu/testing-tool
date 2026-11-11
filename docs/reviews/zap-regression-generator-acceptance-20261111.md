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

**Product-transfer BLOCKED.** Repo không có RUN v3 sản phẩm thật và disposable product fixture
được phép dùng. RUN v3 đã commit chỉ mang nhãn synthetic và chỉ chứng minh contract offline;
không có tuyên bố end-to-end real assessment transfer.

**B/C experiments:** B1, B2, B3, C1 và C3 có script, controls local/GitHub và vẫn ở mức
`experimental`. C2 là `blocked` vì image ghim có Firefox nhưng thiếu `geckodriver`. Async,
OAST, WebSocket, GraphQL và product-specific auth/BOLA vẫn `unsupported`.

## Provenance và bản build được nghiệm thu

- Implementation base: `c954ea870a4180e603fa8ff2926aacb78c74fde7`.
- Core feature: `343301f`; commit binding PR head: `054eeb8`; portable fix: `c9d17db`.
- Build có core + B/C experiments: `b9a0edb55cd36127eb765ba97e13867e9e641201`.
- Image: `zaproxy/zap-stable@sha256:030d3df57735dacbb83464854758e674dd9ad01d79d12a129a8e58b1fd384238`
  (ZAP 2.17.0).
- Case `csp-docs.json`: `sha256:7c1bb4924d6e68bdf4346fc6207ee23c07c37f47755f6a86e4a5310594c9aa4f`.
- Runner: `sha256:9fa073c3e4cfc099ec50cba16399578a99e546f86c2361a2b4601c4806f03fb1`.
- Report adapter: `sha256:89fcc0d5242f3a19f07346c5fcb701ac8a4d06358ce090f04addf163eac8b3fb`.
- Exporter: `sha256:9eadefee80f3546d744b12e271dfed7ff2a3c4f394f03a547bb4b80184d43b28`.

## GitHub evidence

| Gate | Run / SHA | Actual | Artifact readback |
|---|---|---|---|
| GH-01 stable green | [43072912094](https://github.com/hehuanglu/testing-tool/actions/runs/43072912094), PR, `b9a0edb` | `success` | Same case/runner as downloaded push artifact below |
| GH-02 regression red | [43063128776](https://github.com/hehuanglu/testing-tool/actions/runs/43063128776), `8a7985a` | expected failure: `REGRESSION/PROTECTED_ALERT_PRESENT` | ID `13874930575`, digest `sha256:297146b100485a7c938b0282f19c18cd8d4f040c140dd061bbe2416079a86c39` |
| GH-03 missing traffic red | [43063376011](https://github.com/hehuanglu/testing-tool/actions/runs/43063376011), `84ba24f` | expected failure: `MISSING_EVIDENCE/REQUIRED_RESPONSE_MISSING` | ID `13874761541`, digest `sha256:72681a0dc4add94e1cac1f97c6adb0fe3bd091700a0bec0f23a6bdf6eb0268eb` |
| GH-04 restored final green | [43072903955](https://github.com/hehuanglu/testing-tool/actions/runs/43072903955), push, `b9a0edb` | `PASS`, counts PASS=1 and all failure counts=0; `commitSha` matched | ID `13878813369`, digest `sha256:9109f13460595216e895440ca88814ecff1461975a26a7e497bcd3e76487fde0` |
| Qualification | [43072903802](https://github.com/hehuanglu/testing-tool/actions/runs/43072903802), `b9a0edb` | exporter 5/5, runtime 8/8, live records 13/13 | ID `13879901358`, digest `sha256:f78e28fe9b3a3a85c6d663370b443b4e6ba71e5c7f45a5ca043a9af9dcf49663` |
| B/C experiments | [43072904017](https://github.com/hehuanglu/testing-tool/actions/runs/43072904017), `b9a0edb` | all asserted controls completed; C2 recorded `BLOCKED` | ID `13878128794`, digest `sha256:3d9d63585286859dc0365a2d994c960bf5ce5d9abdb7eeed2f16159eca83cd97` |

Các artifact trên đã được tải vào thư mục local bị ignore `artifacts/downloaded/<run-id>/` và
được parse lại. Stable `suite-results.json` chứa đúng full head SHA; qualification references
đều tồn tại; experiment artifact không chứa hai bearer secret canary.

## Acceptance A — 20/20

| Scenario | Mode / command | Expected | Actual | Status / locator |
|---|---|---|---|---|
| GEN-01 | offline, exporter unit + CLI | deterministic canonical bytes, second run `UNCHANGED` | hash ổn định; không timestamp/observed | PASS, qualification run `43072903802` |
| GEN-02 | offline, exporter unit + CLI | changed destination is not overwritten; exit 2 candidate | `REVIEW_REQUIRED`, original hash unchanged | PASS, qualification run `43072903802` |
| GEN-03 | offline, invalid fixture/basis/method/route corpus | specific error; no write/traffic | `INVALID_INPUT` or `UNSUPPORTED_OPERATION` at exact field | PASS, qualification run `43072903802` |
| GEN-04 | offline, synthetic RUN v3 + stale mutations | exact links export; stale revision/operation/path/context/role reject | valid export plus five rejects | PASS, qualification run `43072903802` |
| LIVE-01 | live-github, qualification harness | healthy CSP `PASS` with control and response/header witnesses | `PASS/CSP_MISSING_ALERT_ABSENT_WITH_CONTROL_AND_NONEMPTY_HEADER` | PASS, `qualification-results.json#/scenarios/0` |
| LIVE-02 | live-github, fixture `csp-regression` | docs native alert produces regression; distinct control/docs instances | `REGRESSION/PROTECTED_ALERT_PRESENT` | PASS, `qualification-results.json#/scenarios/1` |
| LIVE-03 | live-github, omit `docs` request only | obligation remains and evidence is missing | `MISSING_EVIDENCE/REQUIRED_RESPONSE_MISSING` | PASS, `qualification-results.json#/scenarios/2` |
| LIVE-04 | live-github, `missing-control` | clean report cannot pass without positive control | `MISSING_EVIDENCE/CONTROL_ALERT_MISSING` | PASS, `qualification-results.json#/scenarios/3` |
| LIVE-05 | live-github, `wrong-status` and `wrong-media` | login/status/media mismatch does not pass | `RESPONSE_STATUS_MISMATCH` and `RESPONSE_MEDIA_TYPE_MISMATCH` | PASS, `qualification-results.json#/scenarios/4-5` |
| LIVE-06 | live-github, deadline `0.01`, then healthy follow-up | `EXECUTION_ERROR/TIMEOUT`, cleanup, next run succeeds | timeout row followed by healthy `PASS` | PASS, `qualification-results.json#/scenarios/6-7` |
| PARSE-01 | offline runtime unit tests | exact origin/method/path/query/alertRef; preserve pointer and optional ID | exact-match and two-instance tests passed | PASS, qualification run `43072903802` |
| PARSE-02 | offline runtime unit tests | malformed/missing/capped native report fails closed | all malformed/capped cases rejected | PASS, qualification run `43072903802` |
| SUITE-01 | live-github lifecycle | add=2, delete=1, empty=0 without manifest/stale output | `PASS(2)`, `PASS(1)`, `EMPTY(0)` | PASS, `qualification-results.json#/scenarios/8-10` |
| SUITE-02 | offline runtime unit tests | duplicate ID, bad filename/schema, symlink fail before traffic; continue after one runtime error | all guards passed; later case result preserved | PASS, qualification run `43072903802` |
| ART-01 | live-github artifact readback | parseable references; no secret canary/private RUN | references true, canary false | PASS, `qualification-results.json#/scenarios/11` |
| PORT-01 | live-github copied bundle without assessment `PYTHONPATH` | same entrypoint returns one PASS | exit 0, `PASS`, count 1 | PASS, `qualification-results.json#/scenarios/12` |
| GH-01 | live-github PR stable | green at intended head | run `43072912094` success at `b9a0edb` | PASS |
| GH-02 | live-github deliberate CSP regression commit | red with regression reason; artifact retained | run `43063128776` expected failure, artifact parsed | PASS |
| GH-03 | live-github deliberate missing-traffic commit | red with missing-evidence reason; artifact retained | run `43063376011` expected failure, artifact parsed | PASS |
| GH-04 | live-github restored final implementation build | stable and qualification green; artifact SHA matches | runs `43072903955`, `43072903802`, and PR run `43072912094` success | PASS |

The negative demonstration commits were reverted with normal history (`cc7213b`, `87026c5`);
no force-push erased their evidence.

## B/C experiment results

All commands use the pinned ZAP image and write a new output directory. Results below come from
GitHub run `43072904017`; local controls were also run before push.

| Capability | Controls and actual result | Status |
|---|---|---|
| B1 `openapi-passive-v1` | good: `PASS/OPENAPI_IMPORTED_AND_ITEMS_REQUEST_WITNESSED`; missing route: `MISSING_EVIDENCE/REQUIRED_ROUTE_NOT_COVERED`; packaged scanner exit 2 (WARN) retained separately | experimental |
| B2 `bearer-passive-v1` | good: `PASS/STATIC_BEARER_ACTOR_AND_MARKER_WITNESSED`; bad: `MISSING_EVIDENCE/AUTH_LOST`; both canaries absent from artifact | experimental |
| B3 `active-xss-v1` | ZAP 2.17.0 rule `40012`; vulnerable: `REGRESSION`; fixed: `PASS`; auth-lost: `MISSING_EVIDENCE`; native instance and active-rule header witness required | experimental |
| C1 `form-cookie-csrf-v1` | healthy: `PASS/FORM_COOKIE_CSRF_AUTH_WITNESSED`; revoked session: `PASS/SESSION_REFRESH_WITNESSED`; bad CSRF: `MISSING_EVIDENCE/AUTH_LOST` | experimental |
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

1. Supply an authorized real RUN v3, reviewed passive-header mapping and disposable product
   fixture to qualify product-transfer without committing private assessment data.
2. Pin/package a `geckodriver` version matching the image Firefox, then implement the fixed
   open/click/wait and no-click browser controls through the ZAP proxy.
3. Promote experimental profiles only after their remaining stable-contract gates are met;
   do not infer generic auth, API, active-scan or BOLA support from the synthetic fixtures.

