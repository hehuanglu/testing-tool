# ByteMe continuous ZAP regression acceptance

2026-11-13 · **IMPLEMENTED / PR_VALIDATED / DEPLOYED ON MASTER** · **7 of 10 acceptance IDs met**

The workflow is active on ByteMe `master`. The plan reserves `OPERATING_ON_MASTER` for all
ten acceptance IDs. AC-03 uses a simulated response, which leaves the associated live
recovery and cleanup evidence in AC-07 and AC-09 incomplete.

- [testing-tool PR #2](https://github.com/hehuanglu/testing-tool/pull/2) merged as
  `e8197caab2d530287214b0e7b8231a3691e0bba8`. ByteMe pins the independently qualified and
  published runner `54766f0182bbdb32d1401f37383b8c3599586877`. The runtime, workflows and
  assessment skill trees at that pin and the merge commit matched.
- [ByteMe PR #2](https://github.com/hehuanglu/ByteMe/pull/2) merged as
  `e5292c26190de31329dbb77172db8a12164ace76`. The merge adds the workflow, case and operating
  guide. See the [active workflow](https://github.com/hehuanglu/ByteMe/actions/workflows/security-regression.yml)
  and [operating guide](https://github.com/hehuanglu/ByteMe/blob/master/tests/security/README.md).
  [ByteMe PR #7](https://github.com/hehuanglu/ByteMe/pull/7) preserved cancellation evidence and
  merged as `3718e2b8b601cbba5e6c38ed41bde358d21b0f33` with the same runner pin.
- The reviewed v1 case bytes hash to
  `76cbbb12495e1cd9751d24601ef8e5442d0e8e86260305b6c331faad23641d86`. Promotion creates v2
  `77dd8d5efc16e40d7eb3975652f7ac2236acaff2599fe1c0e7788e47c0fc2d94` and repeats byte-identically.
  It carries forward the assessment evidence digests, plan revision, reviewed SHA
  `510f6415b6af535ceec77213f0b0c7d5082123f7`, request and oracle. The basis now uses a
  repository-relative catalog path.

## Acceptance

- **AC-01 met.** Integration push and PR both ran automatically and passed. ZAP 2.17.0 read the
  exact anonymous Swagger GET with HTTP 200, `text/html`, the Swagger document marker, message
  ID `1`, body SHA-256
  `bb9928afd0ea8c12e124c42fef58fb080f36770389684badb2a4dcf548624eeb` and
  `X-Frame-Options: DENY`. Both artifacts record `appliedPatches=[]`.
- **AC-02 met.** Push and manual dispatch both passed on `master` after the original merge
  and after the cancellation fix. Each pair identifies its master commit, the same case and
  the same pinned runner.
- **AC-03 partial.** The unit test classifies a simulated exact 200 HTML Swagger response with
  an empty policy header set as `REGRESSION/ANTI_FRAMING_POLICY_UNPROTECTED`. The live control
  that disables ByteMe's framing protection was excluded. No corresponding ByteMe run exists.
- **AC-04 met.** [PR #3](https://github.com/hehuanglu/ByteMe/pull/3) changed the request path only.
  The PR and push jobs failed as `MISSING_EVIDENCE/RESPONSE_STATUS_MISMATCH`. ZAP read the exact
  new GET response with HTTP 401 and message ID `1`; expected status remained 200.
- **AC-05 met.** [PR #4](https://github.com/hehuanglu/ByteMe/pull/4) introduced a build failure.
  Both jobs failed as `EXECUTION_ERROR/BUILD_FAILED`. The retained build log records Docker
  exiting 1, the evidence locator is null and cleanup is complete.
- **AC-06 met.** Deleting the sole case in [PR #5](https://github.com/hehuanglu/ByteMe/pull/5)
  and breaking its JSON in [PR #6](https://github.com/hehuanglu/ByteMe/pull/6) produced separate
  job failures with `ERROR/EMPTY_SUITE` and `ERROR/INVALID_CASE`. Both had zero cases and no
  runtime inventory. Each artifact contains a suite result, summary and JUnit.
- **AC-07 partial.** Reverting the request-path change on PR #3 automatically triggered a
  new push and PR run. Both passed with the original case hash and runner pin, proving
  recovery after a missing-evidence failure. Recovery after a live framing-policy regression
  remains unverified.
- **AC-08 met.** Local Git fixtures verify different runner and product identities and reject
  wrong SHA, wrong origin, dirty checkout, unsupported layout and forbidden controls before
  resource creation. Hosted artifact provenance agrees with the GitHub run and PR merge
  references.
- **AC-09 partial.** Every hosted artifact listed below was downloaded and checked for schema,
  identity, counts, locators, Markdown/JUnit agreement, allowlisted files and private-material
  markers. Cleanup was verified on success, missing evidence and build error. Local SIGTERM
  returned `CANCELLED` with complete cleanup. The hosted cancellation below also verified
  cleanup. Live regression cleanup remains unverified.
- **AC-10 met.** The pinned runner passed the [push adapter qualification](https://github.com/hehuanglu/testing-tool/actions/runs/43369093646)
  and [PR adapter qualification](https://github.com/hehuanglu/testing-tool/actions/runs/43369327466).
  On testing-tool `main`, the [adapter run](https://github.com/hehuanglu/testing-tool/actions/runs/43369949650),
  [portable qualification](https://github.com/hehuanglu/testing-tool/actions/runs/43369949640) and
  [stable suite](https://github.com/hehuanglu/testing-tool/actions/runs/43369949684) all passed.
  The adapter qualification includes the original anti-framing baseline, omitted-response control,
  fixed CSP control and transferred v1 assessment case. The `main` adapter artifact
  `14012271573` has digest
  `sha256:b1f295e2e897a505272a1d7e8ce69355dded5fb9d5cf8f11d821943405b83009`.
  The fixed CSP scanner-timeout control passed separately in local qualification. Automatic
  qualification selects the original anti-framing, omitted-response and fixed-CSP controls.
  Existing expanded qualification modes remain available for manual invocation. Offline,
  13 exporter/promotion, 28 runtime and six anti-framing tests passed.

The four control PRs were closed after readback. Their branches and commits remain available.

## Hosted cancellation

The initial [cancellation](https://github.com/hehuanglu/ByteMe/actions/runs/43370877046)
on the integrated commit produced `SUITE_EXECUTION=cancelled` in `bootstrap.json` and a
successful fallback cleanup step. Artifact `14012825513` contained the bootstrap diagnostic.
Its ZIP hashes to `sha256:f1799905c071c5d54108610dc7a7354637b3956637e2be762cf6090d3a8bc8c3`.

The repeat [cancellation](https://github.com/hehuanglu/ByteMe/actions/runs/43371087142)
during Docker build used the signal-handling workflow from
[ByteMe PR #7](https://github.com/hehuanglu/ByteMe/pull/7), product SHA
`678e8bd390ded090939279cee63e80b26facb72b`, and the same runner pin. GitHub concluded
`cancelled`. The suite artifact records `EXECUTION_ERROR/CANCELLED` and a null evidence
locator. The runner verified removal of its network and absence of four containers and
the build image. The fallback independently verified all six names absent. Downloaded
artifact `14011569170`, attempt 1, has ZIP SHA-256
`9e1963bce56116d4bcda11fac61f236d51a03da68ec3f1595a0990d9f974e879` and file manifest
SHA-256 `32cd433290595fd675ba6bfcd1e252cee27e792c04349a8b38f475ae2eaaa48b`.

## Downloaded ByteMe evidence

All rows are attempt 1. GitHub names each artifact
`zap-regression-<run ID>-1-zap-regression`. The runner SHA is the pin listed above. For PRs, the
tested product SHA is the generated merge commit. The PR base is the reviewed commit for
the initial integration and the original ByteMe merge commit for subsequent controls. For push and manual runs,
the product SHA is also the event head and PR metadata is null.

`suite-results.json`, `run-metadata.json`, `summary.md` and `junit.xml` were checked in every
artifact. Each executed case also includes `target-identity.json` and `cleanup.json`.
`scan/evidence.json` agrees with `scan/zap-history.json` where ZAP completed a readback.
Readiness, scanner and build diagnostics contain stage exits rather than raw subprocess
output. ZIP hashes below were recomputed from the downloaded archives and checked against
GitHub's digest. Unpacked contents were verified separately. The ZIPs are retained locally
under the ignored `artifacts/byteme-continuous-zap-20261113/` directory in testing-tool.

### AC-01 integration push

- [Run 43369707797 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43369707797) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `dbe4e62409acf339159a30dc3c01b2a14ce59219`
- Artifact `14010989466` · ZIP `sha256:63502e01f360c5efd2fa5f875d777972e773983efb71d6a2235fe0b187c946b9`
- Verified file manifest SHA-256 `193a00ac61605300037b484b5410fb377ff29be10c11d6207643014421f61a7c`
- Build 28.442 s, database readiness 10.359 s, backend readiness 8.696 s, ZAP 16.418 s, total 108.739 s · cleanup `COMPLETE`

### AC-01 integration PR #2

- [Run 43369716348 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43369716348) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `b78c4750f0e3127a888aa67203ede4e30f329a00` · PR head `dbe4e62409acf339159a30dc3c01b2a14ce59219`
- Artifact `14011797609` · ZIP `sha256:145a529c6a4985f40f8300f29b9d3c1e4ac476e82c7916eccd109b53d25e3d50`
- Verified file manifest SHA-256 `45ed8a86054e553432fdf6385c6e2ec48f1e3e79fa714f5f132e86c3a10e0e60`
- Build 21.739 s, database readiness 9.959 s, backend readiness 6.424 s, ZAP 12.246 s, total 75.947 s · cleanup `COMPLETE`

### AC-02 master push

- [Run 43370054111 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43370054111) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `e5292c26190de31329dbb77172db8a12164ace76`
- Artifact `14011788212` · ZIP `sha256:b93e1bf0eb8bf702e43de4d55f1868a1a604e94e59662ee2f2ca4b0773e42634`
- Verified file manifest SHA-256 `274da6ae2188a93c681f6d70887801e3a7ed49b4fe960a1fbfc0aefebef9170f`
- Build 33.545 s, database readiness 10.325 s, backend readiness 7.714 s, ZAP 13.959 s, total 109.513 s · cleanup `COMPLETE`

### AC-02 master manual

- [Run 43370058167 · workflow_dispatch](https://github.com/hehuanglu/ByteMe/actions/runs/43370058167) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `e5292c26190de31329dbb77172db8a12164ace76`
- Artifact `14012102379` · ZIP `sha256:279b37d878c06692892428e7fca9d52e6950297a0b23b1089136ccd7c4309bd0`
- Verified file manifest SHA-256 `5251ff61e9a93a5f8595eb07dfb9997d8ac7c7bfce20054726019fc0ee439241`
- Build 30.703 s, database readiness 10.366 s, backend readiness 9.672 s, ZAP 15.877 s, total 104.567 s · cleanup `COMPLETE`

### AC-04 missing response push

- [Run 43370108773 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43370108773) · `FAIL/RESPONSE_STATUS_MISMATCH` · 1 case(s)
- Product `c0b4cd241c20355afd170d30bcee7a793d8dfa6a`
- Artifact `14012052571` · ZIP `sha256:f475b9146afee3a3490db86e6c9e6df7ca1286899870efe30497a01617b858dc`
- Verified file manifest SHA-256 `19ba555f3c7a72ad10c9d8548172610a75ef48cc2e574e0d6d953d329d187b4b`
- Build 30.925 s, database readiness 10.331 s, backend readiness 7.534 s, ZAP 14.359 s, total 102.858 s · cleanup `COMPLETE`

### AC-04 missing response PR #3

- [Run 43370140953 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43370140953) · `FAIL/RESPONSE_STATUS_MISMATCH` · 1 case(s)
- Product `d45fb2447aa9351e7454a75aa9385caac2e226a6` · PR head `c0b4cd241c20355afd170d30bcee7a793d8dfa6a`
- Artifact `14012606064` · ZIP `sha256:b2c660efe405f963715de9c420a296b80e3341fa463d197a0b466cd300826876`
- Verified file manifest SHA-256 `986cf7515cf554c69134595a651e7175d425d3bea9ae1041f9aa10973815e8df`
- Build 24.993 s, database readiness 10.424 s, backend readiness 9.720 s, ZAP 16.918 s, total 98.492 s · cleanup `COMPLETE`

### AC-05 build error push

- [Run 43370109071 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43370109071) · `FAIL/BUILD_FAILED` · 1 case(s)
- Product `31b58383d2c47e326325af7a09d39575b1219641`
- Artifact `14012485879` · ZIP `sha256:f67d49cb8d97ab1e0477f3a6534fbd723851c457293646f83d1f69db81bbb27a`
- Verified file manifest SHA-256 `03a494802058a766c96d228679aee68be2a920b93b4e9735056875c0e9fa9f9f`
- Build 5.678 s, total 6.039 s · cleanup `COMPLETE`

### AC-05 build error PR #4

- [Run 43370147802 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43370147802) · `FAIL/BUILD_FAILED` · 1 case(s)
- Product `d2b6902254cd2fde6f38f33158aecb0122aa85a7` · PR head `31b58383d2c47e326325af7a09d39575b1219641`
- Artifact `14012630342` · ZIP `sha256:131bcd3cf269753a9c636dfe19b539451fc50b44c04c2bfae9e0172e1faa6d8d`
- Verified file manifest SHA-256 `58d7d38f066d25eba9f98fe052cee4ad588b0a05bfa93b764780638a2426da30`
- Build 7.035 s, total 7.484 s · cleanup `COMPLETE`

### AC-06 empty push

- [Run 43370108969 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43370108969) · `ERROR/EMPTY_SUITE` · 0 case(s)
- Product `c37f55f710be41c1452fe4aeaedc66db5b87f176`
- Artifact `14012460777` · ZIP `sha256:6be8e79c745e0a819aa1156c2b8306fdb109d7cab53957e02dd37fb403d15a15`
- Verified file manifest SHA-256 `b71c12d2acb9759e50b9fcc340567cfda8725ed14a4cc59d88b700726cd3c033`
- Fallback cleanup `NO_INVENTORY`

### AC-06 empty PR #5

- [Run 43370154693 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43370154693) · `ERROR/EMPTY_SUITE` · 0 case(s)
- Product `b4540fad4564ac0737ce7149202c5b411a407254` · PR head `c37f55f710be41c1452fe4aeaedc66db5b87f176`
- Artifact `14011708223` · ZIP `sha256:e023855681c3c90e9084e8a48eaba7617ba451b0584b472c058fa35b8dca382b`
- Verified file manifest SHA-256 `896327570762814fff6822f78e4944d4a242ca47a13a25478bcb65e08fe3bff6`
- Fallback cleanup `NO_INVENTORY`

### AC-06 invalid push

- [Run 43370108744 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43370108744) · `ERROR/INVALID_CASE` · 0 case(s)
- Product `edd4126bd552a960d5744a28630e470e061165b7`
- Artifact `14012391024` · ZIP `sha256:27947dc5d20bf4daee41462b88ada18434ba82c83bf4232c220b1d1de89a61b1`
- Verified file manifest SHA-256 `eb50d99c326c3508e8dbbc2d177366c469976d9d076691adecf09f82160afbd6`
- Fallback cleanup `NO_INVENTORY`

### AC-06 invalid PR #6

- [Run 43370160643 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43370160643) · `ERROR/INVALID_CASE` · 0 case(s)
- Product `6b1b962e39841eee0d498d21adf0559c7f4da75e` · PR head `edd4126bd552a960d5744a28630e470e061165b7`
- Artifact `14012421102` · ZIP `sha256:4ea345daaeb99ccead180833a44c4e13c72a9fdd2099c918aa1e4aa5f051707f`
- Verified file manifest SHA-256 `cbc27675e280adb0ef445de0d27608c45a56cd243f93417b5aa9f6bfb1123e51`
- Fallback cleanup `NO_INVENTORY`

### AC-07 substitute recovery push

- [Run 43370480501 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43370480501) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `f9ae24a21b979dc6345819283ee116551e36c7a3`
- Artifact `14011772959` · ZIP `sha256:c371a787fe6281190a67bd16cc1a9f06b39f284d79789e61d0b66bf74342b9f3`
- Verified file manifest SHA-256 `68d2aa874e982a63e73dd7d07be7fc11f06f485ccda3452ebded11c311e431a7`
- Build 28.882 s, database readiness 10.355 s, backend readiness 8.586 s, ZAP 15.374 s, total 99.934 s · cleanup `COMPLETE`

### AC-07 substitute recovery PR #3

- [Run 43370486009 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43370486009) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `9a8f6692dce186036a25211c8ec4d0a9a9c1b78e` · PR head `f9ae24a21b979dc6345819283ee116551e36c7a3`
- Artifact `14011783964` · ZIP `sha256:929b7a91040b0d5a5115cfd6012ea838e3e18d8e9216d5cb684ad1e952495a54`
- Verified file manifest SHA-256 `8e41d0f44c4d7f9e6d339106623b9024ead95784b7cd5a4a3491176b32b66f4a`
- Build 32.696 s, database readiness 10.385 s, backend readiness 8.700 s, ZAP 15.863 s, total 105.256 s · cleanup `COMPLETE`

### Cancellation fix push

- [Run 43371313083 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43371313083) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `2d32d7d4b9d253c2cca8771d337c183cf52775ca`
- Artifact `14012383537` · ZIP `sha256:2e9902844b119e08792118418ece43f7eaa16170f9a2106e8f5fc684f7dfe3cc`
- Verified file manifest SHA-256 `8e14d85136cbd407aac16bb885f3b56c8b6e865edd241e0740fe09a37e68f920`
- Build 28.486 s, database readiness 10.354 s, backend readiness 8.643 s, ZAP 15.363 s, total 105.916 s · cleanup `COMPLETE`

### Cancellation fix PR #7

- [Run 43371318275 · pull_request](https://github.com/hehuanglu/ByteMe/actions/runs/43371318275) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `11002a960f7e825df770ebd782ccb284a4b09c06` · PR head `2d32d7d4b9d253c2cca8771d337c183cf52775ca`
- Artifact `14012517788` · ZIP `sha256:0f7ccc74b308ec3d629b7911a5dc1b4b0d3a16466f1cc336816501c80739c92d`
- Verified file manifest SHA-256 `95ee9aef8df28f1371bfb57d6396e4090c1733a318880adbb886f3fcdd9942f3`
- Build 25.780 s, database readiness 10.382 s, backend readiness 8.634 s, ZAP 15.859 s, total 96.554 s · cleanup `COMPLETE`

### Latest master push

- [Run 43371579165 · push](https://github.com/hehuanglu/ByteMe/actions/runs/43371579165) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `3718e2b8b601cbba5e6c38ed41bde358d21b0f33`
- Artifact `14011878953` · ZIP `sha256:7d1004aae0558e83440c8aebc02660b067d69607672bf0ce0bd23788fa9da7a7`
- Verified file manifest SHA-256 `8adf00c83262268fb6f97f4c49b477009569cdd5b5a1975e659ac2dc158922c8`
- Build 25.624 s, database readiness 10.332 s, backend readiness 6.514 s, ZAP 13.347 s, total 93.589 s · cleanup `COMPLETE`

### Latest master manual

- [Run 43371583156 · workflow_dispatch](https://github.com/hehuanglu/ByteMe/actions/runs/43371583156) · `PASS/ANTI_FRAMING_POLICY_PROTECTED` · 1 case(s)
- Product `3718e2b8b601cbba5e6c38ed41bde358d21b0f33`
- Artifact `14013095395` · ZIP `sha256:0213afa166ed2f565008b200b97e1b1d3a4256790e666626dff07acff051bfbb`
- Verified file manifest SHA-256 `bfd99032a76f2384f36f313124ca22fdd24c9a2b3ee255f81b0c990ab3639b59`
- Build 23.181 s, database readiness 10.396 s, backend readiness 8.692 s, ZAP 15.368 s, total 93.915 s · cleanup `COMPLETE`
