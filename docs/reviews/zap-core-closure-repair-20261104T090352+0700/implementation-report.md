# B-CORE-01 · Báo cáo triển khai

**`candidate-for-auditor-review`**. Bản sửa selector và kiểm tra offline đã hoàn tất. Baseline HEAD `18f17860bad327a18345f949644aac4d40b7fece`. Hai file thay đổi đã có trong working tree dưới dạng untracked trước lượt sửa. Diff so trực tiếp với bản trước sửa của hai file. [Diff](repair.patch) · [Git status trước](git-status-before.txt) · [Git status sau](git-status-after.txt)

## Thay đổi selector

`select_next` chọn `min(closure)` ngay sau nhánh TTL đến hạn và đối soát pending effect. Kết luận chờ nằm sau lựa chọn đó. Một resource review đã qua admission có thể xử lý obligation của chính nó hoặc tiến hành trong khi work độc lập chờ hạn. Các gate dependency, lease/resource, repair, explicit stop và degraded journal vẫn đi qua các nhánh cũ. Reviewer và receipt đúng digest tiếp tục là điều kiện để kết thúc delivery. [Diff](repair.patch)

## Repro và regression

- Trước sửa, chạy nguyên argv của historical probe. Exit 0 xác nhận hành vi lỗi ở generation `7d1791ca8de43ecc26c8fc5983211a288fd75f915647d483086b363267090edf`. Selector trả `review-dependencies` và `canConcludeTurn=true` dù `final-resource-review` đã ready. [Lệnh](historical-probe-before.command.json) · [Kết quả](historical-probe-before.stdout)
- Sau khi hiệu chỉnh cấu hình ca thử resource gate cho đúng schema runtime, chạy lại bộ selector 14 test trên core cũ. Hai ca lỗi đúng kỳ vọng, gồm closure tự xử lý obligation `T-FINAL` và closure độc lập trong lúc work khác còn `notBefore`. Sau sửa, cả 14 test đạt. [Lần chuẩn bị regression](selector-regression-before.stderr) · [Red trước sửa](selector-regression-confirmed-before.stderr) · [Green sau sửa](selector-after.stderr)
- Sáu test mới bao phủ obligation, lịch chờ, dependency theo work/case, readback và reconciliation pending, TTL đã đến hạn, repair và foreign lease. Test delivery hiện hữu kiểm tra cả thiếu receipt, stale digest và digest đúng, cùng cờ `canConcludeTurn`. Test explicit stop và degraded journal cũng được chạy lại. [Diff regression](repair.patch) · [Kết quả selector](selector-after.stderr)
- Probe mới đọc chính RUN/OPERATOR bất biến, recovery/review snapshots và mốc giờ giả `2026-11-05T00:00:00Z` từ historical command. Kết quả là `resource-review`, work `final-resource-review`, `canConcludeTurn=false`, pending rỗng và 0 dispatch. [Probe mới](checkpoint-probe.py) · [Output](checkpoint-probe-after.stdout)

## Managed CLI và delivery synthetic

Dùng fixture tối thiểu mới trong thư mục review, với assessment ID `synthetic-closure-selector-repair` và state, registry, coordinator riêng. Cách này tái tạo trạng thái quyết định cần đo mà tránh đổi các locator tuyệt đối đã được giữ trong history episode A/B. Probe chỉ đọc ở trên kiểm tra riêng checkpoint lịch sử với đầy đủ input gốc. [Fixture runner](isolated-cli.py) · [Resolve](cli-resolve.stdout) · [Reviewer trước closure](cli-pre-closure-review.stdout) · [Recovery trước closure](cli-pre-closure-recovery.stdout)

1. `state-next` chọn `final-resource-review` khi reviewer còn obligation `T-FINAL`. Fixture đọc trạng thái resource giả và kiểm tra thư mục lease rỗng. [Selector](cli-pre-closure-next.stdout) · [Observation](isolated-cli-fixture/resource-observation.json)
2. `state-merge` lưu evidence và case result, rồi `state-commit` lưu resource disposition và work đã hoàn tất. Reviewer xác nhận đủ điều kiện. Selector yêu cầu `verify-final-delivery` với `canConcludeTurn=false`. [Merge](cli-merge.stdout) · [Commit](cli-closure-commit.stdout) · [Reviewer](cli-delivery-source.stdout) · [Selector](cli-delivery-next.stdout)
3. Một tiến trình riêng đọc bảng JSON, đối chiếu ID, thứ tự, nội dung và source digest với reviewer rồi mới commit receipt. Selector trả `workflow-done`, `canConcludeTurn=true`. Final generation `a5f6082c233ed6e427e62d9082dabd6c649f93134df432e32fb4480ce3b40e9f` có 4 committed generations, current/history/coordinator sạch, 0 pending, 0 lease và 0 dispatch. [Readback](cli-delivery-readback.stdout) · [Receipt commit](cli-delivery-commit.stdout) · [Final selector](cli-final-next.stdout) · [Integrity](cli-final-inspect.stdout) · [Recovery](cli-final-recovery.stdout)

## Kiểm tra và bảo toàn bằng chứng

- **226 test offline đạt, 0 lỗi, 0 skip.** Gồm 41 core, 132 regression, 5 safety và 48 repair. 14 test selector đã nằm trong tổng 226. Walkthrough baseline đạt cả 7 stage trên fixture riêng, với action synthetic riêng `effect`. [Core](core-suite.stderr) · [Regression](regression-suite.stderr) · [Safety](safety-suite.stderr) · [Repair](repair-suite.stderr) · [Walkthrough](baseline-walkthrough.stdout)
- `git diff --check` và kiểm tra reverse-apply của patch đều thành công. Tracked diff trước và sau khớp byte. So theo hai file trực tiếp đã lưu hash trước và sau. Bộ pin mới gồm 14 mục lịch sử và test selector, tổng 15 mục. Các pin của historical probes vẫn khớp. [Diff check](diff-check.command.json) · [Patch check](repair-diff-check.command.json) · [Tracked diff](tracked-diff-integrity.txt) · [Hash trước](changed-files-before.sha256) · [Hash sau](changed-files-after.sha256) · [Pin mới](final-source-sha256.txt) · [Historical probe hashes](historical-pins-after.stdout)
- Danh sách và SHA-256 của toàn bộ 675 file episode gốc khớp trước/sau, gồm current pointer, manifest, journal, callback log, generations và historical probe. Counter gốc giữ một entry `effect-once`, sequence 1. [Integrity](episode-integrity.txt) · [Hash episode trước](original-episode-before.sha256) · [Hash episode sau](original-episode-after.sha256)

Phạm vi là selector, checkpoint chỉ đọc và fixture offline. Sản phẩm, ZAP/Docker, auth/browser live, Sheets thật và migration RUN thật nằm ngoài phạm vi. [Handoff và lệnh chạy lại](acceptance-handoff.md)
