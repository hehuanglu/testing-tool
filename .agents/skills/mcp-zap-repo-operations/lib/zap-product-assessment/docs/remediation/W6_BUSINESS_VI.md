# W6 — fixture động và oracle business/BOLA

Contract `w6-owned-business-1` chỉ dành cho owned synthetic API fixtures. Implementation
và kiểm chứng W6 được phép tiến hành độc lập phần operational W5; protected product
execution vẫn phải qua authority, G3/G4 và các gate của mode. Native/JSON bearer,
P0 business và R1 không được mở. Borrowed BOLA v1.4 vẫn chỉ đọc, không thêm writes.

`business.py` khóa manifest, ownership/provenance, inputs và expected state bằng
initial state + transitions. Tất cả tiền là integer minor units ở scale4; decimal
string chỉ được đổi chính xác, quá precision/range hoặc float input bị từ chối.
Manifest chứa ID được seed/cấp riêng cho run, kể cả reserved create IDs của fixture;
không tái sử dụng ID hoặc số dư pilot. Product create thật sẽ cần capture actual ID
và provenance trong bước preparation được cấp quyền; chưa có product runtime trong
entry này. Không lấy reserved synthetic IDs làm dữ kiện của sản phẩm.

`product_adapter.py` ánh xạ source-derived finalsource routes, DTO/envelopes và
alternate ledger (`PATCH`, `/vault/wallets`, `/journal`, integer units, string keys,
`result.value`). Cùng `business_verification.py` replay cả hai. Double HTTP trong
`business_fixture.py` không import adapter/oracle, chỉ parse request thực; không đọc
transitions/expected outcomes. Driver dùng bounded transport `bola_http.exchange`.
Server ghi arrival/actor/request/response và hash state trước/sau. Driver đọc file
state độc lập API sau từng operation. Offline verifier đối chiếu cả hai với replay,
reusing `BundleReader`, strict JSON, canonical hashing và atomic publication hiện có.
Đây là independent implementation/readback trên synthetic, không signed wire/DB
attestation cho finalsource.

Mỗi operation có owner identity và resource-specific owner GET/list trước request,
rồi identity A/B/anonymous thực nhận tại fixture. Mỗi rejection còn cần một prior
successful same-operation positive. Delete dùng sibling disposable cùng owner cho
positive destructive (đã xóa thì không dùng làm live negative target); target của
negative vẫn có fresh owner detail. Create có implicit authenticated owner nên
positive sibling và owner list xác nhận absence cho anonymous-create. Account
read/update, goal update, expense/revenue negatives dùng đúng resource đã positive.
Cross-account dùng account của người khác nhưng category của requester; cross-category
dùng account của requester và category của người khác, tránh hai lỗi bị lẫn nhau.

Denial phải có safe error envelope và toàn state unchanged, kể cả GET, anonymous và
validation400. List so exact membership/values/duplicate count, có populated transactions
trước delete và cascade readback sau delete. Positive thiếu/lỗi → inconclusive; state
violation/disclosure đã quan sát vẫn fail. Không đổi failed assertion thành skipped.

Bills populated là skipped vì nguồn đọc được chỉ có GET và chưa có authorized fixture
create; không thêm DB mutation. Category product preparation cũng có gap (GET options
không phải create), synthetic seed chỉ chứng minh core. Cross-owner account-create
unsupported vì DTO không có owner input; A/B own-create và anonymous denial vẫn chạy.
Finalsource runtime, auth/identity oracle/lifecycle và G3/G4 không được suy từ header
identity endpoint synthetic.

Từ package, chạy owned fixture mới (không nhận product URL hoặc credentials):

```sh
PYTHONPATH=src .venv/bin/python scripts/w6_business_campaign.py --output /absolute/new-run --seed 619
PYTHONPATH=src .venv/bin/python scripts/w6_business_campaign.py --output /absolute/another-run --seed 8831 --reverse
PYTHONPATH=src .venv/bin/python scripts/w6_business_campaign.py --output /absolute/alternate --seed 1507 --adapter alternate-ledger
PYTHONPATH=src .venv/bin/python scripts/verify_finalsource_fixture_state.py --bundle /absolute/new-run/bundle --expect-plan-sha EXTERNAL_PLAN_SHA256
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -p 'test_business.py' -v
```

Container image pin lấy từ runtime-baseline; network none, không published port,
read-only root/source/manifest, no capabilities, no-new-privileges, bounded
CPU/memory/no-swap/PIDs và16MiB tmpfs; chỉ đúng ID+run label+image được stop/remove.
Host preflight `2×32MiB+2GiB` reserve cho workload nhỏ này; không dùng làm scanner
calibration. Readback verifier không gọi Docker/HTTP/credential source. Exit0 nghĩa
bundle nhất quán; securityVerdict vẫn inconclusive vì gaps, hoặc fail khi fixture
vulnerable. `syntheticContractStatus=pass` không là product/security approval.

Script post-state cũ được thay bằng entry offline có external plan pin, không còn
hardcoded ID/balance hoặc implicit finalsource connection. Historical pilot có bản
script đã pin trong delivery-source, giữ nguyên. CLI mới không đọc legacy bundle.
Runbook P0 phía trên vẫn historical và blocked theo registry.
