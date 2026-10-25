# Operations gốc: chọn theo nhu cầu tester

Đọc nhóm liên quan sau [ý định track](track-intents.md), rồi kiểm schema thực trước gọi. Catalog được đối chiếu Java service và delegate tại checkout ngày 25/10/2026: 78 tools. Đây là inventory source, không phải chứng nhận image/runtime. `McpServerApplication.toolCallbackProvider` luôn đăng ký guided/auth/passive/history; expert thêm các nhóm còn lại khi cấu hình bật. Không suy operation không có trong session là repo không hỗ trợ.

Để rà drift, chạy helper chỉ đọc (không kết nối hoặc scan):

```sh
python3 /Users/hahoangloc/.codex/skills/mcp-zap-repo-operations/scripts/inspect_operations.py --repo '/Users/hahoangloc/Working/testing tool/mcp-zap-server' --routing /Users/hahoangloc/.codex/skills/mcp-zap-repo-operations/references/native-operation-routing.md
```

Có thể thêm `--runtime-tools /absolute/shared-tools.json` để so registration và tên tham số source với runtime; thêm `--candidate-tools /absolute/candidate-tools.json` để đối chiếu **hai schema runtime thực**: properties, requiredness, types, constraints và additionalProperties. Source comparison vẫn chỉ so tên; helper không suy type/requiredness source hoặc xác nhận configured auth/session từ description. Không lấy secret/config, không đổi runtime. Name coverage không thay hiểu semantics; operation mới phải đọc service/delegate và bổ sung quyết định routing, không chỉ thêm tên. ToolParam trong source giúp tìm input; schema runtime mới là interface được gọi. Khác checkout/source/image/schema giữ ở trạng thái chưa xác minh.

Với guided exact method/body: `method/postData` trong candidate chỉ áp dụng prepared auth/direct theo provider/service đã đọc; không suy generic body support hoặc anonymous compatibility. Trước dispatch dùng quyết định tại [operation-dispatch](operation-dispatch.md#chọn-deployment-theo-contract-thực). Cùng version nhưng khác JAR có thể có schema khác; cần ghi image/JAR thực, giữ source-to-image provenance unknown nếu chưa có attestation.

## 1. Import surface API — trước scan khi có definition

- `zap_target_import`: facade guided chọn OpenAPI/GraphQL/SOAP và nguồn URL/file/content. Content chỉ OpenAPI, cần shared staging bật và full hostOverride; file phải ZAP đọc được, không mặc nhiên là path trên máy agent.
- `zap_import_openapi_spec_url`, `zap_import_openapi_spec_file`: import OpenAPI từ URL/file, có hostOverride theo policy.
- `zap_import_graphql_schema_url`, `zap_import_graphql_schema_file`: import schema cho endpoint GraphQL chỉ định.
- `zap_import_soap_wsdl_url`, `zap_import_soap_wsdl_file`: import WSDL URL/file.

Chọn guided mặc định nếu đủ input; expert khi cần surface tương ứng đã expose. Kiểm definition/add-on, target servers/refs, origin và warning. Import thay đổi ZAP session và có thể gửi request, không phải offline parse hoặc active coverage. Có spec chưa chắc đủ API; đối soát source/runtime. Thiếu spec thì seed/crawl/adapter từ inventory, không tự bỏ endpoint.

Nguồn: `GuidedSecurityToolsService`, `ExpertImportMcpToolsService` → `OpenApiService`/import services.

## 2. Auth chuẩn bị và xác minh — trước protected work

- `zap_auth_session_prepare`: profile operator-managed + targetUrl → prepared session/context/user; không phải tool tự đọc password từ chat hay tạo role.
- `zap_auth_session_validate`: kiểm prepared session qua sessionId trước và trong protected workload khi cần.
- `zap_contexts_list`: xem context có sẵn; `zap_context_upsert`: tạo/cập nhật include/exclude/in-scope cho đúng target.
- `zap_users_list`: xem users theo context; `zap_user_upsert`: tạo/cập nhật ZAP user/credential config/enabled, không tạo tài khoản ứng dụng.
- `zap_context_auth_configure`: đặt auth method/config và logged-in/out indicators cho context.
- `zap_auth_test_user`: kiểm auth của contextId/userId đã cấu hình; kết quả này không tự là toàn protected scan hoặc role coverage.

Dùng prepared session khi profile phù hợp; expert context/user khi cần kiểm/cấu hình luồng được repo hỗ trợ. Credential resolution/private files theo runner/deployment thật, không truyền secret qua args/prompt. Chấp nhận local retention của skill được phản ánh vào input contract, không xin lại.

Browser profile dùng Client Spider (`strategy=client`); form/JSON bearer dùng http/auto và active theo allowedKinds. AJAX `strategy=browser` từ chối authSessionId. JSON bearer cần bật đúng deployment, validated, direct; browser session không tự dùng cho active. Không đoán mọi loại auth (header/SSO/MFA) có thể dùng trong mọi operation: đọc `GuidedScanWorkflowService.resolvePreparedSession` và profile provider.

Nguồn: `GuidedAuthSessionMcpToolsService` → `GuidedAuthSessionService`; `ExpertAuthMcpToolsService` → `ContextUserService`.

## 3. Crawl — discovery/traffic, không thay UI journeys

- `zap_crawl_start`: guided `http` (link/server), `client` (JS/Client Spider), `browser` (AJAX), `auto` (HTTP rồi fallback AJAX chỉ khi unauth direct HTTP start lỗi). Auto không tự đo coverage JS.
- `zap_crawl_status`, `zap_crawl_stop`: theo dõi/dừng bằng **guided operationId** trả về.
- `zap_spider_start`, `zap_spider_as_user`: HTTP Spider anonymous hoặc contextId/userId; `zap_spider_status`, `zap_spider_stop`: dùng native scanId.
- `zap_client_spider_start`: Client Spider, maxDepth và cặp contextName/userName khi auth; `zap_client_spider_status`, `zap_client_spider_stop`: scanId. Tên context/user khác numeric IDs và khác credential đăng nhập.
- `zap_ajax_spider`: start AJAX; `zap_ajax_spider_status`, `zap_ajax_spider_stop`, `zap_ajax_spider_results`: status/stop/results của AJAX session. Các view/action này không nhận scanId như HTTP Spider; kiểm ownership/singleton trước dùng scanner chung.

Client cần add-on/Firefox/runtime phù hợp. Chọn kỹ thuật theo ứng dụng; không khởi tạo cả ba crawler tự động. FE vẫn cần real browser actions/assertions riêng. Crawl có thể đi link/mutation ngoài dự kiến: scope context và runtime phải đúng trước chạy.

Nguồn: guided workflow → SpiderScanService/ClientSpiderService/AjaxSpiderService; expert direct facade.

## 4. Policy và active — chọn kỹ thuật theo input/rủi ro

- `zap_scan_policies_list`: lấy tên policy thực có.
- `zap_scan_policy_view`: đọc rule/category/filter/limit để hiểu rule đang bật.
- `zap_scan_policy_rule_set`: enable/disable, strength, threshold theo rule IDs của named policy; thay đổi cấu hình thật. Dùng policy owned/được phép sửa, không chỉnh policy chung của run khác.
- `zap_attack_start`: guided active target/recurse/policy, optional authSessionId. Explicit method/postData chỉ direct + prepared auth, body phải gắn request đã seed đúng. Đọc schema/version đang chạy.
- `zap_attack_status`, `zap_attack_stop`: guided operationId, không dùng native scanId/jobId thay thế.
- `zap_active_scan_start`: expert direct active URL/recurse/policy; `zap_active_scan_as_user`: cùng chức năng với contextId/userId.
- `zap_active_scan_status`, `zap_active_scan_stop`: expert native scanId.

List/view trước chọn rule thay vì gán cố định 40012/40018 cho mọi product. Không bật mọi rule để tăng count. Expert direct start hiện không expose method/postData như guided extension; đổi surface không tự giải quyết mọi body case. Native anonymous explicit body hiện đi qua adapter riêng, không fake auth handle. Nếu wrapper không admit, phân biệt capability và gate rồi chọn đường phù hợp hoặc sửa adapter có kiểm tra; không dùng raw API để né enforcement target/auth.

Nguồn: `ExpertDirectScanMcpToolsService` → `ActiveScanService`; guided workflow → engine scan execution. Repo không expose mọi ZAP action thành MCP; đọc native gateway/adapter khi có gap cụ thể.

## 5. Passive và đọc findings/report — sau traffic hoặc khi triage

- `zap_passive_scan_status`: backlog/current completion; `zap_passive_scan_wait`: chờ với timeout/poll. Timeout là chưa settle, không phải zero alerts.
- `zap_findings_summary`, `zap_get_findings_summary`: guided/expert first-pass summary theo baseUrl.
- `zap_findings_details`: guided drill-down group/instances theo schema; `zap_alert_details`: expert alert family details; `zap_alert_instances`: occurrences với limit. Limit không phải toàn bộ instances.
- `zap_alerts`: legacy core alerts list theo base URL; dùng summary/details hoặc report khi cần cấu trúc/group đầy đủ.
- `zap_report_generate`: guided HTML/JSON; `zap_generate_report`: expert template/theme/sites; `zap_view_templates`: xem template trước chọn.
- `zap_report_read`: preview; `zap_report_read_chunk`: bounded pagination theo offset/nextOffset/EOF, expected hash khi interface yêu cầu. Truncated preview không là đã đọc hết report.
- `zap_findings_snapshot`: export snapshot để lưu baseline/retest khi cần; `zap_findings_diff`: so với baseline và maxGroups, kiểm tương thích version/add-ons/phạm vi trước diễn giải new/resolved.

Không tự scan lại để sửa aggregation. Báo cáo native có thể tích lũy trong session: xác định attribution run/target và trạng thái historical; thiếu thì nêu giới hạn. Tái dùng collector đã có khi format phù hợp; hash nội bộ không thành yêu cầu gói evidence của đầu ra. Handoff cuối vẫn đúng hai file của skill, không phải mọi artifact generator sinh ra.

Nguồn: GuidedSecurityToolsService, ExpertResultsMcpToolsService → FindingsService/ReportService; PassiveScanService; core inventory.

## 6. Inventory ZAP — đối soát discovery

- `zap_hosts`: hosts ZAP đã thấy; `zap_sites`: site roots; `zap_urls`: URLs, optional baseUrl filter.

Đối chiếu với inventory source/spec/UI, phát hiện surface hoặc origin ngoài dự kiến. Những URL này không chứng minh mọi method, role, body hoặc endpoint đã scan. Không tự thăm host ngoài scope chỉ vì nó có trong session. Guided không có tương đương inventory đầy đủ; dùng tool khi exposed hoặc nguồn đã quan sát khác, không bịa calls.

Nguồn: ExpertInventoryMcpToolsService → CoreService.

## 7. Queue/jobs — chỉ khi topology/workload cần

- `zap_queue_active_scan`, `zap_queue_active_scan_as_user`: queue active anonymous/as-user.
- `zap_queue_spider_scan`, `zap_queue_spider_scan_as_user`: queue HTTP crawl anonymous/as-user.
- `zap_queue_client_spider_scan`: queue Client Spider, context/user names khi dùng.
- `zap_queue_ajax_spider`: queue AJAX crawl.
- `zap_scan_job_status`, `zap_scan_job_list`: kiểm job theo ID hoặc status filter.
- `zap_scan_job_cancel`: hủy job cụ thể.
- `zap_scan_job_retry`: retry job theo contract; `zap_scan_job_dead_letter_list`: xem dead-letter; `zap_scan_job_dead_letter_requeue`: đưa job dead-letter trở lại queue.

Queue start trả job identity; dùng job lifecycle, không diễn giải queued là đã scan. Idempotency key giúp dedup khi queue hỗ trợ; guided direct bỏ qua key nên không bảo đảm retry an toàn. Retry/requeue có thể tạo traffic mới: reconcile unknown trước, kiểm target/auth/fixture/scope hiện tại. Không tự chuyển JSON bearer direct sang queue để né giới hạn hoặc bật HA vì có queue tools.

Nguồn: ExpertQueueMcpToolsService → ScanJobQueueService; GuidedExecutionModeResolver. Native ID, guided operationId và jobId là ba loại khác nhau.

## 8. Automation Framework — phối hợp native jobs khi phù hợp

- `zap_automation_plan_run`: chạy YAML file/inline theo workspace/policy đã kiểm; không chỉ import offline.
- `zap_automation_plan_status`: đọc running/messages/errors; completed không tự là successful hoặc passive drained.
- `zap_automation_plan_artifacts`: list/preview artifact theo normalized planPath, có giới hạn số/size.

Chọn khi supported jobs của repo giải được chuỗi công việc và giảm wrapper lặp. Đọc `AutomationPlanService`/`AutomationPlanTargetPolicy` trước tạo plan: script/import/browser jobs, proxy/config override và variable destinations bị giới hạn theo contract. maxDuration là cooperative budget khi capability hỗ trợ, không phải network cutoff. AF không thay UI journeys/BOLA policy oracle, không dùng để né gate của operation khác.

## 9. History và policy diagnostics — phục hồi/điều tra, không scan mới

- `zap_scan_history_list`: tìm entries theo type/status/target/limit; `zap_scan_history_get`: đọc entryId cụ thể.
- `zap_scan_history_export`: inline JSON history có filter/limit.
- `zap_scan_history_customer_handoff`: customer-safe Markdown summary từ history; không đủ thay ALERTS/RUN theo inventory của skill.
- `zap_scan_history_release_evidence`: bundle release/pilot; chỉ dùng khi tác vụ đó cần, không mặc định assessment.
- `zap_policy_dry_run`: preview allow/deny của **MCP Policy Bundle** theo tool/target/time. Không phải ZAP scan policy, cũng không phải app BOLA policy; preview không cấp quyền và không sửa enforcement.

Dùng history để nối operation/report cũ hoặc reconcile, nhưng entry “started” không thay kiểm terminal. Không coi history retention đầy đủ hoặc khôi phục được mọi engine session sau restart. Export không đưa raw secret vào báo cáo.

Nguồn: ScanHistoryMcpToolsService → ScanHistoryLedgerService; ExpertPolicyMcpToolsService → service/policy/PolicyDryRunService.

## Các nhu cầu phải phối hợp runner

Không thấy native MCP tool chuyên trách generic UI click/assertion, fixture nghiệp vụ/ownership oracle, full endpoint–role closure hoặc hợp đồng hai file của skill. Dùng [runner mapping](runner-routing.md) và [dispatcher](operation-dispatch.md) để bổ sung đúng chỗ. Bản thân việc thiếu tool chuyên dụng không chứng minh mọi primitive ZAP đều thiếu; kiểm gateway/runner đang có trước viết mới.
