# Finalsource: từ yêu cầu PM đến alert và evidence

Quy ước hiện hành: [ALERTS/RUN](product-assessment-handoff.md) chỉ ghi thao tác và kết quả, không có phần/folder bằng chứng. Chi tiết proof/pin/qualification dưới đây chỉ áp dụng khi entry code thực sự enforce hoặc user giao qualification đó; không tự thêm chúng vào ordinary assessment hay output.

Nguồn chuẩn vẫn là tool schema/runtime và code/runbook của repo. Đây là workflow
trên máy này, không là quyền mặc định quét một production target.

Các helper dưới đây giữ legacy public/borrowed scopes; không mở rộng contract của
chúng. Với nhiệm vụ assessment rộng hơn, reconcile theo [hợp đồng phạm vi](assessment-scope-and-completion.md),
giữ phần helper không chạy là nghĩa vụ/gap, không coi helper xong là track xong. Chọn lượt theo
[workload và triage hiện hành](product-assessment-handoff.md#2-chọn-workload-và-thực-thi-trong-phạm-vi);
không tự mở fixture/BOLA/auth probe chỉ vì yêu cầu ZAP. BOLA chỉ thực hiện khi
được yêu cầu/chọn; nếu user yêu cầu cả ba track thì xử lý BOLA hoặc báo blocked.

## Chọn scope và input

Xác nhận bằng Docker labels đúng project `finalsource-zap-test`, container/image/
StartedAt/network/IP hiện tại; không dùng lại địa chỉ trong báo cáo cũ. Ghi yêu cầu
thực của người dùng vào receipt cùng cách hiểu scope và môi trường. Tài liệu/receipt
do agent ghi chỉ là bản ghi yêu cầu đó, không phải chữ ký hoặc reviewer approval.

Nếu phần đã chọn cần fixture/credential và references còn hợp lệ, dùng lại chúng.
Nếu chưa có và người dùng cho phép tạo tài khoản/dữ liệu giả lập trên test, chuẩn bị fixture qua
API trước. Không mặc định bắt người dùng cung cấp sẵn hai tài khoản. Quyền scan
không tự cấp quyền sửa dữ liệu cũ, đăng ký user trên production hoặc DB reset.

## Tạo fixture trước, kiểm tra BOLA sau

Helper `../scripts/prepare_finalsource_fixture.py` có input `--receipt` và một
`--output` mới. Receipt cần `environment=finalsource-zap-test`, owner, nội dung
`userRequest`, `fixtureRequest` thực và `fixtureCreationAuthorized=true` được suy
ra từ chính chỉ thị người dùng. `--run-bola` thực hiện thêm runner hiện có:

```sh
'/Users/hahoangloc/Working/testing tool/zap-product-assessment/.venv/bin/python' \
  '/Users/hahoangloc/Working/testing tool/.agents/skills/mcp-zap-repo-operations/scripts/prepare_finalsource_fixture.py' \
  --receipt /absolute/run/user-authorization.json --output /absolute/run/fixture --run-bola
```

Helper tạo một client tạm có firewall, GET health, đăng ký đúng hai user mới với
email unique, tạo một account thuộc A bằng token đăng ký. Không retry POST hoặc
đổi payload sau ACK không rõ. Credentials được ghi vào file riêng0600 trước
mutation để có thể đối chiếu nếu mất ACK. Nó không exec/restart target hoặc sửa
DB; chỉ tạo dữ liệu test mới qua contract ứng dụng. Fixture được giữ để retest,
khác cleanup client. Nếu cần xóa fixture, chọn đúng IDs đã tạo và kiểm tra lại
ownership; không xóa user/account cũ để làm sạch kết quả.

Output: creation journal, actor IDs/email, actual account ownership manifest,
private `test-credentials.json`, config/authority/locked plan của borrowed BOLA,
preflight và result/verification. Hai credential references được truyền trong
process memory cho runner, không đi qua ZAP. Kiểm tra BOLA vẫn là hai login và
chín GET controls/reads; fixture creation không bị ghi giả thành read-only BOLA.

Credentials giả lập có thể bàn giao theo yêu cầu người dùng; link file riêng
thay vì chép token vào bản alert chia sẻ rộng. Không đổi hành vi credential logging
của engine hoặc bật JSON-bearer spike để có authenticated DAST.

Khi auth-policy probe được chọn và scope security test/fixture creation đã được phép, helper riêng
`../scripts/probe_finalsource_auth.py --fixture FIXTUREDIR --receipt RECEIPT
--output NEWDIR` kiểm7 requests có giới hạn: anonymous/tampered-JWT/invalid-ID
controls, một đăng ký password1 ký tự và login, known/unknown wrong-password.
Nó có thể tạo thêm đúng một user test để đo password policy; không retry mutation.
So lỗi login bằng semantic fields, không so timestamp động hoặc suy timing leak
từ một lần đo. Ghi rõ user probe cũng được giữ để retest.

## Public native scan, report và handoff

Helper `../scripts/run_finalsource_native.py run --receipt RECEIPT --output NEWDIR`
dùng Python `.venv` trên. Nó tạo scanner riêng từ pinned release images, không
trộn shared ZAP history hoặc build dirty source. Backend qua proxy chỉ GET, exact
origin/path và 2rps; frontend chỉ HTTP Spider/GET trên đúng IP:8443. HTTP form POST
tắt. Firewall chặn backend bypass, host khác, metadata và IPv6; không mở host port.

Workflow: discovery → crawl/GET frontend/assets → crawl backend → public OpenAPI
GET-only subset import → active bounded, nonrecursive trên health/docs-json →
passive settle hai observations → native summaries/snapshots/self-diff → JSON và
HTML report full chunk/hash readback → release evidence/customer handoff/history
→ cleanup đúng scanner → borrowed target binding readback → manifest/detached hash.

`verify NEWDIR` kiểm các artifact của helper. Raw native files và warnings phải
giữ nguyên; manifest checksum không phải source-to-binary attestation/chữ ký.
Same-run self-diff chỉ kiểm contract, không chứng minh regression hay remediation.

Với bộ bàn giao có `manifest.json`/`manifest.sha256`, helper
`../scripts/verify_finalsource_delivery.py BUNDLE` kiểm offline cả raw tool
transcripts/schema, operation terminal/passive observations, full chunk content,
scope guard, standard BOLA verifier và auth probe proof. Exit0 là evidence
consistency, không phải security pass. Output Markdown mẫu có giá trị thực tế ở
`/Users/hahoangloc/Working/testing tool/test-artifacts/finalsource-security-2026-10-18/PM_REPORT_VI.md`;
đó là snapshot của một run, không là quyền chạy lại trong tương lai.

Giới hạn quan trọng: frontend chưa có browser/Client Spider coverage; native scan
không có credential; backend guard làm hẹp active method/path coverage; responses
guard-generated không là app alerts. Report của direct/in-memory deployment vẫn
có caveat về terminal queue evidence. BOLA pass cho một account không mở rộng
thành auth DAST, business logic, quyền update/delete hoặc whole-repo acceptance.

## Bàn giao cho PM

Dùng [hai file kết quả](product-assessment-handoff.md#3-bộ-bàn-giao-bắt-buộc): ALERTS.json và RUN.json. Ghi target/thời gian/scope, các thao tác thực tế và kết quả, toàn coverage, hạn chế và phần chưa làm. Giữ native severity/confidence, phân biệt nhóm/instances và nguồn direct/ZAP. Không có folder/mục bằng chứng hoặc yêu cầu sao chép raw/hash vào đầu ra. Các file runner sinh giữ tại chỗ làm việc, không xóa hoặc sửa kết quả lịch sử.

## Entry anonymous nghiên cứu mới

Phần public native scan phía trên mô tả **legacy bounded GET helper**. Với public
login/register JSON POST, protected denial matrix và qualification mới, dùng
[be-anonymous-research](be-anonymous-research.md), entry assessment riêng. Không
coi hạn chế legacy là toàn bộ capability của track.
