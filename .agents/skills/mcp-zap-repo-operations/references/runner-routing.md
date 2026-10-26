# Chọn runner từ code đã kiểm

Đây là bản đồ **khả năng và giới hạn code**, không phải chứng nhận runtime. Paths dưới đây tương đối với workspace. Kiểm lại source/help khi checkout đổi; không chọn runner chỉ từ tên. Bộ điều phối cấp skill nằm ở [operation-dispatch](operation-dispatch.md); không nhầm với `product_cli.py` là dispatcher kỹ thuật của một tập executor hữu hạn.

## 1. Operations native trực tiếp và CI runner gốc

Đối với import/crawl/active/report đơn giản trong runtime đã cấu hình, ưu tiên gọi tool hiện có theo [catalog](native-operation-routing.md). Đây là đường orchestration của agent, không cần bọc một research plan chỉ để gọi status hoặc report. Vẫn giữ scope/auth/resource và ghi kết quả thực.

`mcp-zap-server/.github/actions/zap-security-gate/mcp_zap_gate.py` đã đọc nhánh main: optional seed requests → guided auto crawl hoặc expert HTTP spider → optional recursive active → passive wait → findings/snapshot/diff/report. Có transport/parser/report helpers dùng lại được. Nhánh start hiện không truyền authSessionId/context-user; không dùng cả runner làm authenticated DAST chỉ vì seed có token. Recursive scan chỉ phù hợp scope đã cho phép. CI baseline/enforcement khác completion product.

`run-gate.sh`/GitLab wrappers còn provision/cleanup Compose; không chạy wrapper chỉ để lấy collector trên scanner đang dùng. Nếu cần helper, đọc function signature/caller và import đúng module; không dựng argv theo suy đoán. Không lặp collector/exporter native có sẵn.

## 2. Common CLI và discovery backend

Entry `zap-product-assessment/scripts/product_assessment.py` → `src/zap_assessment/product_cli.py`. Đã kiểm dispatch, admission, run branches và `product_workflow.py`.

- `discover`: recipe hoặc reviewed observations → source candidate. Có `--observations` thì đọc source candidate trước và không cần registry; recipe chỉ cần khi chọn executor. Auth khác khuôn bearer được giữ trong `authObservations`, chưa thành runtime support.
- `materialize`: nối source candidate với deployment/binding đã xác minh.
- `status`, `templates`, `plan`: kiểm/compile theo recipe, không thực hiện scan; plan có thể inspect runtime binding.
- `prepare`, `import-actor`, `business-fixtures`: actor/fixture setup trong scope; không tính vào DAST coverage. Actor import cần private file và identity mapping hợp lệ.
- `run`: BE anonymous → AnonymousRun; authenticated → product_native.execute; BOLA → product_bola.execute. FE được dispatch riêng từ đầu.
- `reconcile`, `continue-plan`: finite cases/allocations cũ. `scope reconcile/continue/report` nối inventory độc lập → actions hữu hạn → existing executor → reader → reconciliation; xem [cách chạy](responsibility-loop.md). Agent vẫn phải khám phá/sửa/chuẩn bị và thực hiện phần còn thiếu; đây không là universal scanner.
- `handoff`: composer lineage/evidence cũ, chưa tự là output hai file hiện hành.

Backend registry hiện gồm finalsource-ledger, archive-control. Archive là control. Không thay URL để biến recipe cũ thành product mới. Recipe phù hợp thì dùng; product mới cần đọc source/spec và tạo adapter riêng hoặc orchestration native phù hợp.

Common plan pin cả product modules/recipes/schemas, không chỉ dependency của product. Sửa recipe chung có thể làm plan product khác drift; tránh sửa trong lúc còn run dùng pins đó. Ưu tiên adapter product riêng, ghi ảnh hưởng khi cần đổi core; không regenerate pins để ép plan cũ pass hoặc phát lại mutation.

## 3. BE anonymous executor

`anonymous_runner.py:AnonymousRun` đã kiểm seed, active, bind_baseline, reconcile, stop/export. Seed qua ZAP sendRequest; active bằng native ZAP ascan với method/body/policy; bind SiteNode giữ đúng baseline; MCP dùng passive/report/chunk/summary. Nó **không chỉ gọi guided attack**, nên không đánh đồng lớp này với MCP surface.

Giới hạn: `anonymous.py` whitelist rule 40012/40018; runtime/guard, pins, caps và evidence contract riêng. Stop duyệt scans trong engine của runtime: chỉ dùng khi engine là owned isolated như contract, không lắp nguyên executor vào scanner chung. `transport.py:MCP` có TOOLS whitelist và endpoint docker-exec cố định; không phải client tùy ý cho 78 operations.

`scripts/be_anonymous_research.py` có product-run/setup/cleanup finalsource và cả `run` bị giới hạn environment finalsource-zap-test trong entry hiện tại. Common CLI có đường khác vào AnonymousRun. Chọn đường đúng, không lấy tên “anonymous research” làm generic capability.

Tái dùng khi workload/guard/runtime khớp; mở adapter tối thiểu cho input còn thiếu sau khi đã chọn kỹ thuật theo nghiệp vụ. Không giới hạn nhiệm vụ vào hai rules để vừa executor.

## 4. BE authenticated executor

`product_native.py:execute` → validate workflow/actor → compile_track → owned runtime/profile/guard → `research.py:ResearchRun`. Đã kiểm prepare/validate, monitor loss, start/wait/stop và report readback. Có native identity callback; auth mất thì latch, stop owned operations; unknown start ghi trạng thái không retry mù.

Common path cần actor, JAR/pin, binding và recipe; chủ yếu GET/query, conditional flat PUT/PATCH và numeric path theo proof/method/oracle. Chỉ chọn 40012/40018 hiện tại. ResearchRun admit legacy plan có finalsource assumptions; dùng common compiled version đúng, không truyền một dict tùy ý vào để vượt gate.

`scripts/be_authenticated_research.py` là entry finalsource-specific; không mặc định cho product khác. `product_prepare.py`/`product_identity.py` hỗ trợ chuẩn bị/import actor và mapping theo recipe, nên ưu tiên chúng khi tương thích trước viết login/identity mới. Không hứa auth bearer/cookie/SSO bất kỳ từ việc đã có một research profile.

Đường native tools có profile phù hợp có thể tránh dependency qualification không liên quan của research executor; đây là chọn entry đáp ứng nghiệp vụ ngay từ đầu, không bypass enforcement của run đang dùng. Khi capability chưa có, adapter mới phải giữ actor/session/state cần thiết và gọi primitive hiện có.

### Fallback khi shared thiếu method/body

Đường `research_product.provision` + `ResearchRun.prepare/start/wait` + `seed_as_user` hỗ trợ orchestration native trên scanner riêng; schema và auth/direct semantics phải lấy từ đúng candidate. Cho tác vụ implementation/validation được giao, adapter product hữu hạn có thể reuse các helpers này với plan/admission thật, owned fixture, scope guard, auth monitor, journal và state readback; không giả body proof để gọi common CLI đang enforce proof.

Exact method/body phải được kiểm trên deployment hiện hành trước khi ghi observed. Các method/body/vector chưa kiểm giữ not-operated. Workload anonymous cần lane có semantics phù hợp, không gắn phiên authenticated để vượt gate.

## 5. BOLA executor

`product_bola.py:compile_cases/execute` cùng `product_checks.py`, `bola_research.py:DirectClient`, `bola_http.py`: đã kiểm expected từ recipe trước request, relation/owner binding, identity per actor, positive control, before/after/related state, collection/pagination và reconcile unknown mutation. Tái dùng checker/transport/journal khi semantics đúng.

Input vẫn là explicit workload/actor/resource/cases. Compiler không tự chứng minh đủ mọi role. `reconcile_responsibilities` chỉ biết cases caller đưa vào; list rỗng trả partial, không được dùng đóng track. Dispatcher phải join với inventory độc lập.

Khi runner báo blocked/eligible, agent còn phải chọn và thực hiện bước [khắc phục](local-remediation-and-continuation.md#quyết-định-cho-phần-việc-còn-mở); status không tự là quyết định dừng. Helper tùy chọn [review_open_work.py](operational-knowledge.md#helper-rà-soát-tùy-chọn) kiểm phần quyết định caller ánh xạ, không đổi admission/pins của common CLI hoặc kết quả lịch sử.

Legacy bola/borrowed/operational runners là những contract hữu hạn (có read-only/account-read/synthetic lanes), không nâng thành full ownership chỉ từ tên. `scripts/bola_research.py` và product adapters lịch sử phải đọc branch tương ứng khi cần; common lane là ứng viên ưu tiên cho nhiều action nhưng vẫn phụ thuộc recipe/identity/oracle. Không nới expected/status để ép phù hợp.

## 6. FE executors

`fe_anonymous_cli.py` → `fe_anonymous_discovery.py`, contract, `fe_anonymous_runner.py:FERun`, browser/runtime/transport. Đã kiểm: reviewed-fe observation provider tồn tại ngoài finalsource registry; Client Spider bổ sung; browser worker/journey; native body dùng ZAP API và tái dùng AnonymousRun.bind_baseline; passive/report collector.

`fe_authenticated_cli.py` → reviewed/finalsource discovery, contract, `fe_authenticated_runner.py:AuthenticatedRun`. Đã kiểm browser worker session groups và UI/native checkpoints, auth prepare/validate/active, stop và export. `fe_authenticated_recipes.prepare` hiện chỉ có setup adapter finalsource; core còn finalsource cleanup branch. Generic reviewed journeys không tự có mọi fixture hook.

Cả hai cần browser thật, selection/binding/TLS/runtime/caps và contract qualification hiện hữu; không chạy `controls` mặc định vì CLI có lệnh đó. Chọn runner khi journey predicates và auth thực sự biểu đạt được product. Thiếu selector/state/setup thì viết adapter product hoặc mở primitive nhỏ; không thay UI bằng API request hay mặc định acceptInsecureCerts.

## 7. Collector, handoff và helpers lịch sử

Reader và composer dùng lại: [operational readback](operational-readback.md) mô tả `result_readers`, `active_questions`, chunk size theo schema và kiểm ID sau redaction. Đọc call contract trước dùng; normalized probes vẫn cần predicate product, không là nhãn do caller tự chứng nhận.

`product_native.report_readback`, `transport.read_report`, FE export dùng chunk/EOF và report data: tái dùng khi interface và size cap phù hợp. Lỗi truncate cần đọc tiếp hoặc ghi thiếu, không tự tăng cap vô hạn.

`product_handoff.py`, `fe_anonymous_handoff.py`, `fe_authenticated_handoff.py` còn tạo technical/evidence/lineage/pins. Không coi output của chúng là final package hiện hành. Nếu entry tự gọi chúng, giữ ở working directory; agent lấy kết quả đã có và tổng hợp **ALERTS.json + RUN.json** ở folder bàn giao riêng. Không gọi thêm verifier chỉ để có handoff. Dùng `product_scope.compact_results`/`scope report`: hai file từ dữ liệu đã đọc, giữ reconciliation và attribution. Legacy technical output vẫn là working artifacts; không tự tạo composer theo counts của recipe.

`capabilities.py`, `verify_saved_evidence.py`, `verify_finalsource_delivery.py`, P0/fault/qualification scripts: chỉ chọn khi audit công cụ hoặc contract cụ thể cần. Registry P0 always-block không có nghĩa mọi research lane bị chặn. Không lẫn assurance status với task completion hoặc product security verdict.

Các scripts finalsource trong skill (`prepare_finalsource_fixture.py`, `probe_finalsource_auth.py`, `run_finalsource_native.py`) là helper product legacy, có route/container/environment cố định. Chỉ khi product/mode khớp và đã đọc nhánh được gọi. Không dùng làm mặc định hoặc nhân bản cho product khác mà chưa bỏ assumptions.

## Quyết định tái sử dụng

Với từng runner ứng viên, đọc entry → compiler/admission → executor → cleanup/output; xác nhận input, tác động, target/actor và giới hạn. Ghi ngắn vì sao dùng cả runner, chỉ dùng helper hay cần adapter. “Code có”, “unit test pass”, “đã chạy trước đây” và “đang chạy được với product này” là bốn điều khác nhau.

Tra [tri thức vận hành](operational-knowledge.md) để dùng lại recovery/fixture đã kiểm thay vì copy script theo phase. Giữ source của cơ chế dùng chung và mapping product ở đúng nơi; recipe/selector/fixture phải kiểm lại trên deployment hiện tại. Không gọi mode provision chỉ vì nó tồn tại nếu batch còn side effects ngoài workload/quyền.

Không cần chạy toàn bộ runner để chọn; help/offline tests và đọc code đủ cho quyết định thiết kế, còn claim runtime chỉ sau execution thật. Không tự khởi động fixture/control campaigns trong một tác vụ chỉ sửa skill.
