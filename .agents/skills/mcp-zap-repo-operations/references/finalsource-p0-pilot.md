# Finalsource P0 pilot — 18/10/2026

Quy ước hiện hành: [ALERTS/RUN](product-assessment-handoff.md) chỉ ghi thao tác và kết quả, không có phần/folder bằng chứng. Chi tiết proof/pin/qualification dưới đây chỉ áp dụng khi entry code thực sự enforce hoặc user giao qualification đó; không tự thêm chúng vào ordinary assessment hay output.

Runbook chuẩn trong workspace:
[finalsource-p0-runbook.md](</Users/hahoangloc/Working/testing tool/zap-product-assessment/docs/finalsource-p0-runbook.md>).
Evidence mới:
[PM_REPORT_VI.md](</Users/hahoangloc/Working/testing tool/test-artifacts/finalsource-p0-20261018T101545Z/PM_REPORT_VI.md>),
`acceptance.json`, `coverage.json` và verifier `scripts/verify_finalsource_p0.py`.
Đọc status thực và verify bundle; không lấy reference này làm quyền chạy tương lai.

Để thực thi authenticated DAST mới, dùng [workflow theo mục tiêu](authenticated-dast-goal.md)
và [be-authenticated](be-authenticated.md). P0 là evidence lịch sử; các entry legacy P0
có admission cố định trong `capabilities.require_p0_mode`. Xác minh source thật;
không chạy lại lệnh pilot cũ, bỏ guard hoặc repin registry để biến snapshot thành
executor được admit. Native secret failure không tự chặn một delegated contract
khác đã được nghiệm thu, nhưng delegated hiện có cũng cần proof riêng.

- Root full Docker suite mới106/106,12 suites,0 fail/skip; unit1260/1260. Baseline13
  failures vẫn giữ nguyên. Sửa test isolation và native Java listener fixture, không
  giảm assertions hoặc xóa test. Không đồng nhất release scanner với dirty root build.
- Firefox8 journeys + Client Spider thực chạy trong `native-browser-a6`, full report
  chunks/hash. Native browser auth functional nhưng password/JWT có trong history/
  report: secret gate vẫn **fail**. Không quảng bá native JSON/form/browser auth là
  secret-safe chỉ từ functional success hoặc quyền giữ credential giả lập riêng.
- `delegated-a4`/`delegated-b3`: scanner riêng từng actor, JWT chỉ nằm ở private guard
  và được inject ở hop cuối. Đây là adapter-assisted mirror, không phải gateway
  bearer-reference scaffold hoặc experimental JSON bearer đã hoạt động. Identity,
  owner/cross-user, invalid-token live stop, egress và history/report audits có proof.
- 11 controls account/goal +10 transaction controls,12 final post-state assertions.
  Category helper chỉ INSERT hai dòng mới cho đúng fixture actors khi user cho phép
  dữ liệu test; không reset/update user/đụng row cũ. Credentials DB chỉ trong memory/
  stdin. Dùng manifest IDs thực; helper post-state hiện pin IDs của pilot này.
- Rule10116 kiểm phiên bản scanner gọi internet ngoài scope và giữ passive threads
  60s/response: tắt riêng rule này, pin inventory; giữ app passive rules. SSE parser
  phải dùng LF/CRLF, không Unicode splitlines: report thật chứa NEL/U+0085.
- Dynamic active rule100043 vẫn gửi request khi policy và script wrapper disabled.
  Gỡ active script khỏi đúng scanner do run sở hữu; kiểm actual scanProgress chỉ
  40012/40018 và Complete. Giữ các failed/policy-deviating phases; không coi readback
  enabled=false là proof actual rule traffic.

Mirror đổi browser origin/transport; không chứng minh canonical TLS/CORS.19 operations
×3 actor states có cả not tested; bills chưa có populated object-ownership fixture,
race/upload/fraud logic chưa chạy. Snapshot regression qua build, queue durability
và release/security approval không thuộc acceptance này. Không tự đánh dấu M4/GA.

User trong phiên này cho phép private evidence chứa credential giả lập, Docker
Desktop restart sau ENOSPC và dọn cache tái tạo được. Đó là quyền theo phiên, không
phải quyền prune volumes/DB hoặc restart target chung cho các yêu cầu vận hành sau.
