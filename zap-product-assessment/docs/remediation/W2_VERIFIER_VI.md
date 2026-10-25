# W2 — Verifier v2 độc lập; điểm dừng G2

Thực hiện theo kế hoạch remediation và yêu cầu tiếp tục W2. Phạm vi: schema/version dispatch, read-only artifact verifier, independent oracle replay, fixture binding, summary agreement và corpus adversarial offline. Sau G2 dừng; không chạy W3 hoặc campaign sản phẩm.

## Đường đọc và trust anchor

`evidence.verify_bundle(root, expected_plan_hash=...)` dispatch schema v2 sang `verification.py`. CLI tương ứng:

```sh
PYTHONPATH=src .venv/bin/python -m zap_assessment.cli verify \
  /absolute/v2-bundle --expect-plan-hash 'externally-pinned-sha256'
```

V2 bắt buộc plan hash giữ **bên ngoài bundle**. SHA lấy từ manifest đang bị kiểm không phải trust anchor. Manifest, file bytes/hash, canonical plan và fixture pin được kiểm riêng. Nếu thay plan cùng toàn bộ internal hashes mà external pin không đổi, verifier từ chối. Nếu operator cố ý khóa một plan mới hợp lệ thì đó là scope mới, không phải approval của plan cũ.

Schema nằm tại `schemas/v2.0/bundle.schema.json`. `contracts.validate` chọn version/kind minh thị; unknown version không fallback sang v1. Legacy v1.0–v1.4 dùng reader/schema hiện hữu, không tự đổi verdict/meaning. Historical P0 vẫn dùng `scripts/verify_finalsource_p0.py`; không biến reevaluation W1 thành bundle v2 hay viết vào bundle cũ. Publisher v2 bị chặn trước ghi file: W2 chỉ triển khai verifier, chưa qua secret/runtime gates để bật publication.

Plan có schemaVersion2.0, planKind coverage-verification, verificationOnly true; fixtureHash, assessment/target/build, assertions, phases, reports và đầy đủ required tracks/gates theo R2. Trong plan template, `binding.planHash` dùng literal `$self` để tránh vòng hash; chỉ binding ở các vị trí đã định nghĩa được materialize thành hash byte canonical plan. Evidence phải dùng hash thực. Không thay literal trong business request/body tùy ý.

Manifest chỉ định đường dẫn document theo role (plan, fixture, observations, coverage, summary) và report/chunk refs; không pin ID/thư mục pilot. Mỗi artifact phải được kê khai đúng một lần, có byte count/SHA-256 và được một role sử dụng. Physical inventory phải khớp chính xác, không extra/unlisted/unreferenced file, alias hai role hoặc duplicate claim/ID/request/response.

## Kiểm filesystem và report

Reader giữ directory FD, mở từng ancestor/file bằng no-follow, chỉ đọc regular file; từ chối traversal, absolute/backslash/ambiguous paths, symlink file/directory/root, hardlink và special files. Header manifest cũng đọc có giới hạn/no-follow/nonblocking để FIFO không treo quá trình. Budgets hiện tại: file16MiB, bundle64MiB,4096 artifacts, depth32; quá budget block, không tự truncate rồi coi complete. Chuỗi JSON duplicate keys, nonfinite numbers hoặc mixed document version bị từ chối. Không echo response body/value trong lỗi.

Reader kiểm inode/size/timestamps khi đọc và inventory cuối. Đây là readback nhất quán tại thời điểm quan sát, không phải cơ chế filesystem immutable chống mọi thay đổi tương lai. Path phải là POSIX relative canonical NFC; đây là implementation POSIX, không hứa filesystem/OS chưa kiểm.

Native report chunks được dựng bằng Unicode codepoint offsets, continuity, source reportPath, byte hash và EOF; thứ tự file/manifest không phải thứ tự content. Missing/duplicate/orphan/noncontiguous chunks, sai SHA/total/EOF/Unicode offset bị từ chối. Bytes dựng lại phải đúng nguyên artifact. JSON report được parse; HTML chỉ kiểm UTF-8/bytes, không render/execute. Report readback dùng helper serialization sẵn có; không dùng report tồn tại để quyết định application oracle.

## Oracle độc lập và binding fixture

`oracle_verification.py:IndependentAudit` không import/call `coverage.evaluate`, collector hay helper application oracle W1. Tests làm builder throw/trả pass giả và vẫn yêu cầu verifier tự tìm fail. Shared schemas/canonical JSON và native chunk reader không quyết định nghiệp vụ.

Fixture registry pin logical actor/resource, subject/role, identity resourceRef, wire ID, owner và response pointers. Owner phải liên kết đúng actor registry. Assertion, support controls và mọi exchange/boundary phải cùng assessment/plan/target/build/phase/oracle context đã khóa. Request method/path/body phải khớp contract; route template không suy ID từ tên file hoặc numeric-only path. Identity/raw response, owner-positive, auth epoch/freshness, body oracle, disclosure và pre/post-state được tái dựng từ data, không tin verified flag tự khai.

W2 hỗ trợ JSON direct API resource-read, denial, validation và state-transition theo contract W1; fixture có thể đổi actor/resource IDs, route, envelope, filesystem layout/order và số assertion mà không sửa verifier. Data/report không tạo authority. Unsupported technique, thiếu proof, auth gap, guard/infrastructure response hoặc phase không đủ proof => inconclusive, không pass bằng status code.

Explicit reuse chỉ hợp lệ khi assertion đã hoàn tất trước failedAt, có đủ state/identity/epoch/clock/ref/binding proof và record được khai báo. Assertion pass riêng không đổi phase failed thành completed. Disclosure/state violation đã xác nhận vẫn fail nếu proof khác về sau thiếu; verifier ghi `proofComplete=false` khi cần, không đánh mất failure.

`coverage` chỉ là declaration để đối chiếu với oracle tái tính. Summary counts/track states/execution/cleanup/verdict phải khớp kết quả độc lập. V2 hiện là **verification-only** với required runtime gates chưa có proof: `evidenceStatus=incomplete`, `gateDecision=block`, `securityVerdict=inconclusive` nếu chưa có violation; confirmed violation giữ `securityVerdict=fail`. `coverageEvidenceStatus` tách độ đầy đủ của proof coverage khỏi trạng thái toàn assessment. Ngay cả khi tất cả oracle trong fixture pass, không có security-pass/allow được cấp cho sản phẩm.

CLI verify exit0 nghĩa bundle nhất quán, bao gồm fail/blocked. Kết quả còn giữ `assessmentExitCode=1` khi confirmed fail, hoặc2 khi bị block/inconclusive. Root CI0/1 và legacy assessment0/1/2/3 không bị đổi nghĩa. Không tạo security/release approval hoặc reviewer reference.

## Corpus, compatibility và giới hạn

`tests/support/verification_fixture.py` tạo bundle synthetic động, không import builder/verifier để đặt expectations. `verification_corpus.py` khai expected accept/reject trước run: corrupt/hash/missing-response, duplicate/traversal/symlink/hardlink, wrong binding/identity/resource/phase, self-declared pass, native chunks và summary. Các ca semantic tamper cập nhật cả raw content, boundary hashes và manifest checksums; chúng vẫn phải bị oracle/contract/summary checks từ chối. Cũng có invalid contract mới được external-pin để chứng minh trusted hash không bỏ qua logical fixture/duplicate/phase checks.

Harness có thể chạy lại, không phát network/Docker:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_verification_v2.py' -v
.venv/bin/python scripts/remediation_w2_campaign.py \
  --output /absolute/fresh-g2-results.json \
  --work-dir /absolute/fresh-private-fixture-directory
```

Raw negative bundles cố ý có unsafe links/metadata được giữ trong work dir riêng0700/files0600; checkpoint chỉ trỏ ref và kết quả. Không đưa chúng vào namespace bundle đã publish hoặc sửa historical evidence. Compatibility readback dùng verifier cũ trên bundles v1.0–v1.4 và P0, ghi output mới ngoài package.

**Trust limit:** checksum không chứng minh transport/controller nói thật. Nếu toàn bộ raw records đều được bịa nhất quán với một trusted plan, không có signature/independent attestation để tự phát hiện nguồn giả. W2 không claim giải được điều đó; runtime/secret/policy/source-to-image proof vẫn required và gate luôn block. G2 chứng minh các tamper vi phạm binding/oracle/summary bắt buộc và không false-allow trong corpus, không chứng minh ứng dụng hoặc runtime đã an toàn. Independent implementation khác independent human review; review thật vẫn pending.

Source/image/plan pins, expected/observed, commands/exits, preservation, attempt history và kết quả cụ thể được lưu ở checkpoint W2. Điểm tiếp tục sau G2 là W3 registry/mode guards/secret sink readiness; chưa chạy trong W2.
