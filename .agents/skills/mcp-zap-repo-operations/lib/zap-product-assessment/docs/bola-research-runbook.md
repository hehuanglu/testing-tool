# BOLA research direct-client — 21/10/2026

Entry mới `scripts/bola_research.py` dùng contract `bola-research/1.0`, độc lập với borrowed v1.4 read-only và W6 owned synthetic. Core hiểu actor/object/policy và ID path/query/body; product adapter hiện chỉ finalsource local test. Product khác chưa được admit tự động. Không gọi BE-auth compiler, không cần ZAP session, native report hay active scan.

Quyền triển khai không tự là quyền product execution. Xác minh quyền hiện hành, binding và deadline; mỗi run có fixtures và credentials riêng.

Từ thư mục assessment được đóng gói trong skill (`$ASSESSMENT_ROOT`):

```sh
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py --help
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py discover --output NEW_DISCOVERY_DIRECTORY
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py product-run --discovery NEW_DISCOVERY_DIRECTORY/BOLA_DISCOVERY.json --inventory NEW_DISCOVERY_DIRECTORY/BOLA_INVENTORY.json --receipt AUTHORITY_RECEIPT.json --output NEW_RUN_DIRECTORY
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py verify --run NEW_RUN_DIRECTORY
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research.py compare --before FIRST_RUN_DIRECTORY --after SECOND_RUN_DIRECTORY
```

Receipt JSON cần `environment=finalsource-zap-test`, `productLocation` là absolute checkout finalsource, `source` trỏ tới yêu cầu thật, `permissions=["setup","read","mutation","poststate","cleanup","login"]`. Agent tự ghi receipt từ scope người dùng đã giao. Không tự điền quyền chưa có; đây không phải file PM phải chuẩn bị. Mode mới dùng owner-positive write trên sibling riêng nên cần tất cả quyền trên; nếu chỉ có borrowed-read-only authority, dùng v1.4 với actor/fixture provenance thật.

Discovery dùng source + live Swagger + immutable Docker binding và proxy config. Swagger hiện không khai transaction query DTO: adapter bổ sung type/limit/offset từ DTO đã hash, ghi provenance/gap rồi kiểm runtime. Inventory có disposition cho từng operation. Trước setup kiểm source, finite surface, static related read, test Compose working directory, target/proxy binding và resource reserve. Giữ mọi failed attempt, không nới gate để chạy.

Executor tạo A/B riêng, kiểm registration/login subject rồi protected `/data/user_id`. Lists còn dùng membership; không chỉ lấy membership làm identity. Tokens/password/email chỉ trong bộ nhớ, actor slots immutable; register/login response bị bỏ trừ subject. Request/response chỉ lưu dữ liệu fixture cần cho oracle, các credential fields/canaries được giảm dữ liệu. Không có cookies, redirect, proxy từ env hay retry. Không claim target wire/source-to-image attestation. Deadline900s,500requests,2rps,5s/request,64KiB/response,32MiB artifacts,2GiB host reserve. Product adapter dùng CA local có hostname verification; không bỏ TLS.

Account detail/list/options và Saving-goal list kiểm hai chiều A/B và anonymous. Account PUT/DELETE, goal PUT chỉ nhắm target fresh thuộc run; owner positive dùng sibling riêng. Mỗi case có protected identities trước/sau, owner before/after, related readbacks; tiền dùng recipe exact integers và `business.minor`. Missing/unknown response hoặc auth loss là inconclusive. Lost ACK ghi unknown outcome rồi readback; không replay mutation. BOLA finding giữ nguồn direct-client, native ZAP ID null và classification authority do agent.

`--interrupt-after N` dừng trước case tiếp theo sau N cases; poststate/cleanup vẫn chạy trong budget và binding hiện tại. SIGINT/SIGTERM trong case loop bật stop latch; không resume. Hard kill/power loss không có restart credential recovery vì credential chỉ trong memory: giữ journal/fixture events, ghi cleanup chưa xác nhận, không tự đăng nhập lại hay phát lại mutation. Không dùng legacy Docker cleanup cho mode host direct.

Cleanup chỉ account IDs đã ack trong ledger và đúng actor identity, sau đó đọc404. User/goal không có DELETE API: giữ và liệt kê retention; không SQL/reset. Thất bại setup giữ FAILURE + journal + cleanup, không là BOLA finding hay full bundle. Run đủ plan có PLAN/hash, cases, HTTP/actions/journal, RESULTS, COVERAGE, ALERTS, cleanup và EVIDENCE_INDEX; verify replay policy/oracle và evidence references, không ký chứng nhận an toàn. Hash index local không là trust anchor độc lập. Không sửa bytes của run đã seal.

Owned HTTP qualification có route/schema cargo độc lập, secure/vulnerable, shared read, later-page disclosure, denied mutation side effect, lost ACK và auth-loss controls:

```sh
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research_qualification.py --help
zap-product-assessment/.venv/bin/python zap-product-assessment/scripts/bola_research_qualification.py --output NEW_OWNED_DIRECTORY
```

Test harness mock pacing waits để fault corpus chạy nhanh; target HTTP/server state thật, không là product throughput proof. Product runs giữ pacing thật. Focused regression dùng `.venv/bin/python -m unittest` với `PYTHONPATH=src:tests` từ assessment. Historical BE-auth/anonymous proofs chỉ chuyển recipe/mechanics, không chuyển verdict hoặc authority.

## Branch/populated continuation (explicit DB prerequisite authority)

`bola-inventory/1.1` adds branches with operationRef, branchRef, predicate, reference locations, policy/evidence refs, fixture dependencies and applicability disposition. `bola_research_branches.coverage` only accepts executed proof references; candidate alone is never tested. Historical inventory1.0 and implicit legacy inventories retain their old readback semantics.

Use `scripts/bola_continuation.py run --discovery DISCOVERY --inventory INVENTORY --receipt RECEIPT --output NEW_RUN [--failure]` only with the explicit local-test DB prerequisite/fault scope. Discovery remains `scripts/bola_research.py discover`. Never reuse historical credentials or fixture IDs. DB is independently bound before 4 bounded inserts; APIs under test still create transactions/goals and exercise ownership. Fresh target/unrelated/disposable accounts carry real relations; real transaction pages use limit2 and source-supported type/offset. Owner injection names come from DTO/entity/persistence mappings.

Offline verification: `scripts/bola_continuation.py verify --output RUN`; legacy `bola_research.py verify --run OLD_RUN` remains separate. Selected state checker has no evaluate import; same repository and shared artifact origin limit independence. Fault mode preserves proxy forwarding proof, journal and readbacks without request replay; surviving controller credentials are not whole-session recovery proof. Retain goals/users/categories with exact ledger; API cascade and exact bill cleanup are verified separately.
