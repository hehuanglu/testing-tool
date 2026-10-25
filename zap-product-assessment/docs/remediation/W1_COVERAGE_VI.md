# W1 — Coverage có binding và oracle

Ngày 18/10/2026. Tiếp tục qua G0 theo yêu cầu người dùng và dừng ở **G1**. Phạm vi implementation: predicate reusable cho direct API, collector pilot bảo thủ, regression và reevaluation offline. Không đổi BOLA v1.4, legacy verifier, root Java/CI, target hay runtime scanner.

## Predicate dùng chung

`src/zap_assessment/coverage.py:evaluate(assertion, evidence)` trả riêng `observed`, `requested`, `targetRequested`, `techniqueExecuted`, `responseSource`, `oracleResult`, `reasonCodes`. Các boolean là **proof đã có**, false không chứng minh không có traffic. Oracle không đọc `verified`/`oracleResult` tự khai trong input. `pass` chỉ là kết quả của assertion cụ thể, không phải release/security approval.

Contract in-memory `schemaVersion=2.0` khóa đủ binding: assessmentId, planHash, targetBinding, buildRef, actorRef, resourceRef, operation, techniqueId, phaseId, oracleVersion. `request` chứa method/path/body mong đợi; concrete path phải khớp operation template. `primaryRef` chọn exchange chính. Mỗi support spec chứa `ref`, full `binding`, exact `request`, `statuses`. Control không được đổi assessment/plan/target/build/phase/oracle; owner/identity có actor/resource/technique riêng đã khai báo.

Evidence có `exchanges`, `boundaries` theo cùng ref và `phases` theo phaseId. Exchange ghi binding/request/response, requestId, responseId, authEpoch, clockId và monotonic `at`. Response gồm status, contentType và raw JSON body dạng string. Boundary phải có cùng binding/IDs/clock/time/auth mode/epoch và SHA-256 request/response; chỉ sau correlation mới tin `source=target|guard|infrastructure`. Không suy source từ body marker. Mất correlation => unknown/inconclusive, không claim target-request proof.

Hash ở W1 là **canonical normalized JSON** (sorted keys, compact separators, UTF-8, không NaN), không phải raw HTTP wire bytes. Boundary thực phải tạo record từ transport mà nó quan sát; caller tự viết hai record khớp nhau không phải independent attestation. W4/W5 phải nối producer thật; W2 phải kiểm artifact/semantics độc lập. Legacy guard chỉ ghi method/path/status/bytes, không đủ để tạo correlation này, nên không được backfill target proof từ time window hay marker.

`identities[actor]` khai subject/role, JSON pointers và proof spec của identity response. Primary, owner-positive và state controls phải có identity đúng actor/role và cùng auth epoch, clock; proof đi trước request, tuổi tối đa 5s như contract W0. Khoảng freshness này không chứng minh natural expiry/revocation/refresh; G4 vẫn chưa chạy. Anonymous phải là actor explicit với authMode/epoch anonymous, không fallback từ protected actor.

`resource` khóa logical resourceRef, wireId, ownerActorRef/ownerSubject và id/owner pointers. Owner-positive phải có response ứng dụng đúng resource/owner, identity đúng owner và timestamp trước request chính. Supporting resource metadata không được lấy lại từ response để hợp thức actual. Resource IDs có thể là chuỗi/UUID; route matcher ưu tiên static route trước template.

## Oracle và state

Các oracle hỗ trợ tại G1: `resource-read`, `denial`, `validation`, `state-transition`. `oracle.statuses` lấy từ contract, không có global status whitelist. `responseEquals` chứa các JSON pointer/value assertions; read còn tự kiểm ID/owner theo resource binding. Denial yêu cầu forbiddenPointers để kiểm disclosure. Owner-positive bắt buộc cho phạm vi resource ownership này. Login/health, browser và active-sink chưa có adapter oracle trong module này; không suy coverage từ chúng.

Writes và validation/state-transition cần preState/postState specs, statePointer và expectedPreState. Raw state phải đúng resource/owner; ordering là pre < request < post trên cùng clock và identity/epoch còn hợp lệ. Denial/validation đòi post không đổi; state-transition đòi expectedPostState. JSON numeric comparison không dùng binary float cho decimal; boolean không được bằng numeric ID. Duplicate JSON keys và body HTML/login không được pass. Cố định decimal transition theo business adapter/arithmetic thuộc W6, chưa được suy từ balance bất kỳ.

403/404 có thể pass denial đúng contract với owner-positive/no disclosure/post-state; 400 có thể pass validation đúng contract và state không đổi. Denial mà disclosure hoặc state đổi vẫn fail. Confirmed violation không bị biến thành inconclusive khi proof phụ về sau thiếu/lỗi.

Request đã tới target vẫn giữ `targetRequested/techniqueExecuted` khi status/oracle không đạt. `techniqueExecuted` hiện chỉ chứng minh direct API exercise; SQLi/XSS vẫn blocked `unsupported_technique_or_sink_unproven`. Scanner lifecycle Complete là một dimension riêng, không là payload/sink proof.

## Evidence từ phase lỗi

Mặc định phase khác completed không pass. Chỉ assertion có `reusePolicy=completed-before-phase-failure` cùng explicit `reuseRecords[assertionId]` mới được xét reuse. Record khóa binding, clock, authEpochs từng actor, exchangeRefs đầy đủ, stateBeforeRef/stateAfterRef, completedAt và recordRef. Phase có failedAt/clockId; mọi required exchange/control phải hoàn tất ≤ completedAt < failedAt. Các state/auth/resource/oracle checks ở trên vẫn bắt buộc, kể cả read phải có state continuity khi reuse. Sai epoch, thiếu post-state, lỗi xảy ra trước completion hoặc foreign phase => inconclusive. Kết quả assertion không sửa phase failed thành completed và không bù required track khác.

## Collector và CLI

`scripts/finalsource_p0_coverage.py` gọi predicate chung khi đọc observations cũ. Vì legacy không đủ binding/provenance/oracle nên kết quả candidate giữ `inconclusive`/`not_run`, không phát `verified` theo status. Body/query/credential values không được copy vào candidate; chỉ metadata, evidence refs và input hashes được ghi. Phase failed hoặc policy-deviating vẫn giữ observations để điều tra, không bị âm thầm loại rồi báo pass. Active lifecycle được ghi riêng và technique proof vẫn false.

Tái đánh giá bundle đã publish phải chỉ định thư mục mới ngoài source; collector từ chối output đã tồn tại, output bên trong source và ghi đè coverage/manifest đã có. Bundle cũ, legacy status và historical verifier không đổi. Candidate ghi `legacyBundleUpgraded=false`; không được đưa candidate vào manifest cũ. Output có coverage.json, input-index.json và reevaluation-diff.json nếu source có coverage lịch sử.

Từ package root:

```sh
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p '*coverage*.py' -v
.venv/bin/python scripts/finalsource_p0.py coverage \
  /absolute/historical-bundle --output /absolute/fresh-candidate
```

Nhánh `coverage` của pilot tái dùng collector, không cần receipt/credentials hoặc khởi tạo Pilot. Các mode scan cũ không tự bật trong W1. Readback 1.991 artifact bằng verifier legacy chỉ chứng minh consistency lịch sử; W2 mới triển khai semantic verifier độc lập/version dispatch, không gọi lại builder để quyết định cùng oracle. Source/image/plan pins, tests/actual outcomes, reason diff, preservation và điểm dừng được lưu ở checkpoint W1 ngoài package.
