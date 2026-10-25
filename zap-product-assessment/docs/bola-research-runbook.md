# BOLA research direct-client — 21/10/2026

Entry mới `scripts/bola_research.py` dùng contract `bola-research/1.0`, độc lập với borrowed v1.4 read-only và W6 owned synthetic. Core hiểu actor/object/policy và ID path/query/body; product adapter hiện chỉ finalsource local test. Product khác chưa được admit tự động. Không gọi BE-auth compiler, không cần ZAP session, native report hay active scan.

Quyền triển khai không tự là quyền product execution. Trong lượt ngày 21/10, prompt BOLA revision 2 mục 2 cho login, fresh API-only fixtures A/B, bounded read/mutation/poststate/cleanup trên deployment test đã xác minh từ checkout. Không có quyền DB helper, ID cũ, active ZAP, production, rebuild/restart target hoặc sửa product. Receipt ghi lại chỉ thị, không reviewer approval. Luôn xác minh lại binding và deadline; mỗi run mới có fixtures và credentials mới.

Từ workspace `/Users/hahoangloc/Working/testing tool`:

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

Latest evidence/progress: [BOLA implementation](../../test-artifacts/bola-research-20261021T070245Z/PROGRESS_VI.md). Transaction/category/Expense-goal/bills populated coverage cần fixture API hiện không có; related empty transactions không chứng minh populated cascade. Fixed selected product build, natural expiry/refresh và independent review vẫn phải báo riêng. Zero findings không kết luận toàn product an toàn hoặc toàn track complete.

Latest verified checkpoint 21/10/2026: final-source product-D/product-E,36cases each; product-interrupted stops after2cases with confirmed account cleanup. Regression132/132 and9owned controls pass expected outcomes. See [progress](</Users/hahoangloc/Working/testing tool/test-artifacts/bola-research-20261021T070245Z/PROGRESS_VI.md>) and [tester handoff](</Users/hahoangloc/Working/testing tool/test-artifacts/bola-research-20261021T070245Z/technical/TESTER_REPORT_VI.md>). Zero findings in executed scope; populated fixtures/fixed build/natural expiry pending. No mutation replay or reuse of prior credentials.


## Branch/populated continuation (explicit DB prerequisite authority)

`bola-inventory/1.1` adds branches with operationRef, branchRef, predicate, reference locations, policy/evidence refs, fixture dependencies and applicability disposition. `bola_research_branches.coverage` only accepts executed proof references; candidate alone is never tested. Historical inventory1.0 and implicit legacy inventories retain their old readback semantics.

Use `scripts/bola_continuation.py run --discovery DISCOVERY --inventory INVENTORY --receipt RECEIPT --output NEW_RUN [--failure]` only with the explicit local-test DB prerequisite/fault scope. Discovery remains `scripts/bola_research.py discover`. Never reuse historical credentials or fixture IDs. DB is independently bound before 4 bounded inserts; APIs under test still create transactions/goals and exercise ownership. Fresh target/unrelated/disposable accounts carry real relations; real transaction pages use limit2 and source-supported type/offset. Owner injection names come from DTO/entity/persistence mappings.

Offline verification: `scripts/bola_continuation.py verify --output RUN`; legacy `bola_research.py verify --run OLD_RUN` remains separate. Selected state checker has no evaluate import; same repository and shared artifact origin limit independence. Fault mode preserves proxy forwarding proof, journal and readbacks without request replay; surviving controller credentials are not whole-session recovery proof. Retain goals/users/categories with exact ledger; API cascade and exact bill cleanup are verified separately.


## Verified continuation checkpoint — 21/10/2026 (supersedes historical coverage above)

Current proof: [continuation progress](</Users/hahoangloc/Working/testing tool/test-artifacts/bola-continuation-20261021T125040Z/PROGRESS_VI.md>) and [tester handoff](</Users/hahoangloc/Working/testing tool/test-artifacts/bola-continuation-20261021T125040Z/technical/TESTER_REPORT_VI.md>). Fresh product-A/B use the same frozen source/build/logical cases with distinct IDs:150 cases/398requests each,16/22 operations and22/22 relevant branches;6 operations not applicable. Actual product-failure has150 cases/407requests plus3 in-flight fault controls. Earlier derisk03 had144 cases and source had already advanced before resume; do not relabel it as the final pair.

POST56 cases/run: transactions32,goals16,accounts8, including foreign references, anonymous/nonexistent and property whitelist controls. Populated account PUT/DELETE, Saving/Expense goal PUT, collection/aggregate reads and14 transaction pages (limit2) use fresh related transactions/categories/bills. Category/bill DB provisioning stays4 prerequisite inserts after independent binding/schema/FK checks; it is not API coverage. Fault proof reconciles exactly one successful create for lost-response and SIGKILL child, denied0, no replay. Surviving controller memory is not whole-session recovery.

Current independent checker also corroborates fault intent/no ACK, exact forwarded request/actor/count/status/created ID and selected readback state; source receipt binds productLocation and explicit owned-client-fault permission.141 focused compatibility tests pass. Accounts/transactions/bills cleanup verified; retained users/goals/categories have exact ledger. No findings in this executed scope; source BOLA/direct-client/property authorization, not native ZAP or whole-product safe. Natural JWT expiry TTL3600s, fixed-build remediation and populated receipt relations remain unproved. Do not wait for expiry or require a fixed build to hand off current findings. See ALERTS.json, KNOWN_GAPS, REPEATABILITY and VERIFICATION in this namespace.
