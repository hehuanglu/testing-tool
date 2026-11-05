# Sửa B-CORE-01 và chuẩn bị nghiệm thu lại

## Phạm vi giao Sol

Workspace `/Users/hahoangloc/Working/testing tool`.

Đọc skill hiện hành và AGENTS áp dụng. Đây là sửa selector offline có phạm vi hẹp, không chạy sản phẩm, ZAP, Docker, Sheets, migration RUN thật hoặc commit/push. Giữ mọi thay đổi working tree có sẵn. Không sửa dữ liệu/history của episode nghiệm thu để khiến test pass.

Episode gốc: `docs/reviews/zap-core-behavioral-acceptance-20261104T083756+0700`.
Core: `.agents/skills/mcp-zap-repo-operations/lib/zap-product-assessment`.
Python: `zap-product-assessment/.venv/bin/python`.

## Kết quả auditor đã xác minh

- Chat B `01a1a43d-2282-7ee1-bbbb-b319dc9df570` là chat mới, chỉ có một turn với prompt theo kế hoạch, không có nhắc tiếp tục xen giữa. A vẫn là chat triển khai cũ.
- Tính lại từ current: generation `a17cac765e5350e2d15a7073f43d12f7405a3450cb3a7bd1d78b401b22f68e66`, 27 generations, current/ancestry sạch; workflow-done; 5 met, 1 unmet; callback effect-once=1, pending=0, leases=0.
- Auditor chạy lại script đọc delivery trong subprocess: đúng 6 hàng, thứ tự/nội dung/sourceDigest. 14 source digests còn khớp baseline.
- Auditor chạy lại nguyên argv trong `evidence/b-repro-closure-selector.command.json`: tái hiện B-CORE-01. Final completion không xóa lỗi dừng sớm đã xảy ra trước đó.

Kết luận: chấp nhận bằng chứng cold resume/no replay và completion synthetic trong episode; **chưa chấp nhận selector tự quyết định dừng**. Lỗi này chặn nghiệm thu lõi vận hành. Live/migration vẫn chưa kiểm chứng.

## Nguyên nhân và thay đổi yêu cầu

File `src/zap_assessment/operation_selection.py`, cuối `select_next`:

1. Work qua admission được phân vào ready / ttl / closure.
2. `final-resource-review` đã qua các gate, nằm trong closure và readyWorkIds.
3. Nhánh `if obligations or wake or ... and not closure` kết luận waiting trước nhánh chọn closure. `not closure` chỉ áp dụng vế cuối, còn obligations/wake vẫn có thể thắng.
4. Obligation T-FINAL chính là công việc resource review đang sẵn sàng giải quyết. Core đánh đồng nghĩa vụ chưa hoàn thành với không có việc khả thi.

Sửa thứ tự quyết định: sau các nhánh ưu tiên hiện hữu (ready, repair/recovery/stop, case handling, TTL đủ hạn, pending-effect reconciliation), chọn closure đã qua admission **trước** nhánh kết luận waiting. Giữ cách chọn `min(closure)` hiện tại. Loại bỏ nhánh closure trùng nếu di chuyển. Làm rõ biểu thức waiting bằng ngoặc/biến nếu cần; không chỉ đổi cờ canConcludeTurn trong khi nextAction vẫn sai.

Không đẩy closure lên trước readback pending hoặc TTL đang ready; không bỏ dependency/resource/notBefore/repair gates; không biến mọi closure thành luôn chạy được. Closure độc lập đã được admission có thể chạy trong khi nghĩa vụ khác chờ thời gian/dependency. Closure có dependency thật phải tiếp tục deferred. Delivery chỉ được chọn sau reviewer đủ điều kiện; không xóa obligation để vượt gate.

Không cần tách skill, thêm agent, thêm schema hoặc viết lại selector. Nếu test chứng minh cần thay semantics ngoài phạm vi này, giữ repro và báo deviation riêng.

## Các bước triển khai

1. Tạo thư mục mới `docs/reviews/zap-core-closure-repair-<timestamp>/`; ghi baseline git status, source hashes và progress.md. Dùng tên mới, không overwrite lần chạy trước.
2. Đọc repro, RUN/OPERATOR bất biến và snapshots được command JSON chỉ định. Chạy lại repro trước sửa, lưu stdout/stderr/exit trong thư mục mới. Repro gốc có assert hành vi lỗi nên exit 0 trước sửa là đúng.
3. Thêm regression tự chứa vào tests selector theo fixture conventions có sẵn, không phụ thuộc absolute path episode. Trước sửa regression phải fail vì nextAction sai. Dùng reviewer thật cho ca chính: T-FINAL còn thiếu evidence, closure resource review liên kết T-FINAL, không pending/lease; không fake `eligibleForCompletion=true`.
4. Sửa nhánh selection theo yêu cầu ở trên. Không sửa historical probe để hợp với kết quả mới.
5. Thêm probe mới trong thư mục review: dùng chính input và fake time từ command JSON lịch sử, gọi select_next; assert workId=final-resource-review, canConcludeTurn=false, pendingActionIds=[], không dispatch. Lưu output và source hashes. Sau sửa không dùng việc probe lịch sử exit nonzero làm kết luận regression: probe ấy cố ý assert lỗi cũ; probe mới là oracle đã sửa.
6. Kiểm tra đường managed CLI trên bản sao fixture cô lập. Dùng bản sao generations/commit history cần thiết, registry/coordinator riêng và rebind các absolute locator hợp lệ bằng helper nếu cần; không trỏ mutation về episode gốc. Nếu copy/rebind làm thay semantics thì chỉ dùng managed fixture mới tái tạo cùng trạng thái tối thiểu và ghi rõ. `state-next` phải chọn resource review. Thực hiện resource observation/merge/commit synthetic, review, delivery local/readback/receipt tới workflow-done. Không dispatch lại effect-once; checkpoint nguyên bản chỉ đọc.
7. Chạy targeted tests trước, rồi bộ offline liên quan bằng lệnh baseline report hiện có, và git diff --check. Ghi số test/skip thực tế; không mặc định phải giữ đúng 220 khi thêm test.
8. Ghi implementation-report.md và acceptance-handoff.md, links tới diff, test outputs, probe cũ trước sửa/probe mới sau sửa, CLI progression, các digests và giới hạn. Dừng với candidate-for-auditor-review; user sẽ đưa auditor kiểm tra.

## Ma trận regression bắt buộc

| Ca | Kỳ vọng |
| --- | --- |
| T-FINAL obligation, closure resource review ready, không việc khác | Chọn đúng closure, canConcludeTurn=false |
| Closure độc lập ready, một work khác đang notBefore | Chọn closure, giữ deferred/nextWakeAt của work kia |
| Closure có dependsOn work/case chưa đủ | Không chọn closure; giữ dependency cụ thể, không giả completed |
| Closure ready cùng readback pending effect | Readback/reconciliation giữ ưu tiên; không kết luận done |
| Closure ready cùng TTL đã đến hạn, control hợp lệ | Giữ thứ tự TTL trước closure theo contract hiện tại |
| Closure bị repair/resource gate | Không bypass gate; chọn repair/recovery/việc độc lập thích hợp |
| Sau closure, reviewer đủ nhưng delivery thiếu/stale | verify-final-delivery, canConcludeTurn=false |
| Reviewer đủ, receipt đúng digest | workflow-done, canConcludeTurn=true |
| Explicit stop và degraded journal | Giữ semantics hiện hữu; chạy lại test có sẵn, không thêm policy mới |

Không thêm assert toàn cục rằng readyWorkIds khác rỗng luôn cấm conclude: stop/recovery có semantics riêng. Regression trọng tâm là mode normal, approved plan hiện hành, admitted executable closure.

## Bảo toàn bằng chứng

Trước/sau sửa so SHA-256 của toàn bộ file đã tồn tại trong episode gốc. Không viết vào current pointer, manifest, journal, callback log, generations, report hoặc historical probe. Evidence vòng sửa nằm hoàn toàn ngoài episode. Không dùng deepcopy state rồi tiếp tục coordinator gốc.

User không cần mở lại A/B hay nhắc tiếp tục từng bước. Lượt sửa phải hoàn tất toàn bộ công việc khả thi trong cùng lượt, với progress lưu đủ để tự resume nếu bị ngắt.
