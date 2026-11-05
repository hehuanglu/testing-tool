# B-CORE-01 · Handoff cho auditor

**`candidate-for-auditor-review`**. Phạm vi cần quyết định là bản sửa thứ tự chọn closure. Bằng chứng cold resume A/B nằm trong episode gốc. Lượt sửa xác nhận lại checkpoint bằng probe chỉ đọc và kiểm tra managed CLI từ pre-closure đến delivery trên fixture riêng. [Implementation report](implementation-report.md) · [Diff](repair.patch)

## Đối chiếu kết quả

- Historical probe trên core cũ trả exit 0 vì assert hành vi lỗi. Regression trước sửa có đúng hai failure. Dùng probe mới làm oracle sau sửa. Cùng checkpoint và giờ giả phải chọn `final-resource-review`, `canConcludeTurn=false`, pending rỗng và 0 dispatch. [Historical argv](historical-probe-before.command.json) · [Historical output](historical-probe-before.stdout) · [Red regression](selector-regression-confirmed-before.stderr) · [Probe sau sửa](checkpoint-probe-after.stdout)
- Trên fixture CLI riêng, selector phải đi theo thứ tự `resource-review` → `verify-final-delivery` → `workflow-done`. Xác minh disposition đã lưu, readback từ tiến trình riêng và digest của receipt. Current, history và coordinator sạch, pending và lease rỗng. [Resource commit](cli-closure-commit.stdout) · [Delivery selection](cli-delivery-next.stdout) · [Readback](cli-delivery-readback.stdout) · [Final recovery](cli-final-recovery.stdout) · [CLI summary](isolated-cli.stdout)
- 226 test offline đạt và walkthrough qua 7 stage. Danh sách và hash của 675 file A/B khớp trước/sau. Action `effect-once` giữ đúng một invocation trong episode gốc. [Lệnh suites](run-offline-suites.zsh) · [Walkthrough](baseline-walkthrough.stdout) · [Hash episode](original-episode-after.sha256) · [Source pins mới](final-source-sha256.txt)

## Chạy lại trên working tree hiện tại

Chạy bằng zsh. Capture và fixture mới nằm trong scratch riêng. Probe chỉ đọc episode A/B qua historical command JSON. Source digest của fixture CLI có thể khác giữa các thư mục scratch vì dữ liệu được băm chứa đường dẫn evidence. Selector, bảng đọc lại và receipt phải cùng digest trong mỗi lần chạy.

```zsh
set -e
review='/Users/hahoangloc/Working/testing tool/docs/reviews/zap-core-closure-repair-20261104T090352+0700'
scratch="$(mktemp -d "${TMPDIR:-/tmp}/zap-closure-audit.XXXXXXXX")"
cp "$review/"{env.zsh,capture.py,checkpoint-probe.py,isolated-cli.py,run-offline-suites.zsh} "$scratch/"
source "$scratch/env.zsh"
cd "$WORKSPACE"

shasum -a 256 -c "$review/final-source-sha256.txt"
shasum -a 256 -c docs/reviews/zap-core-repair-20261104/historical-probes-sha256.txt
"$ZAP_PYTHON" -B "$scratch/checkpoint-probe.py" \
  "$ORIGINAL_EPISODE/evidence/b-repro-closure-selector.command.json"
"$ZAP_PYTHON" -B "$scratch/isolated-cli.py"
zsh "$scratch/run-offline-suites.zsh"
git diff --check

(cd "$ORIGINAL_EPISODE"; find . -type f -print0 | LC_ALL=C sort -z | xargs -0 shasum -a 256) \
  > "$scratch/original-episode.sha256"
cmp "$review/original-episode-before.sha256" "$scratch/original-episode.sha256"
printf 'Audit artifacts at %s\n' "$scratch"
```

Đánh giá riêng B-CORE-01 và các giới hạn đã ghi nhận của A/B. Live scanner, auth/browser, Sheets thật và migration RUN thật vẫn ngoài phạm vi vòng này.
