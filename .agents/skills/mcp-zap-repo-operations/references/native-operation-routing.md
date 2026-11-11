# Native operations: select by testing need

Read relevant [track intents](track-intents.md), then inspect actual runtime schemas. Source inventory does not qualify deployed images or runtimes. McpServerApplication.toolCallbackProvider always registers guided/auth/passive/history; expert configuration adds other groups. Missing session registration does not establish missing repository support.

Read-only drift inspection:

```sh
python3 "$SKILL_DIR/scripts/inspect_operations.py" --repo "$MCP_ZAP_REPO" --routing "$SKILL_DIR"/references/native-operation-routing.md
```

Add `--runtime-tools /absolute/shared-tools.json` for registration/source parameter-name comparison and `--candidate-tools /absolute/candidate-tools.json` to compare two actual runtime schemas, including properties/requiredness/types/constraints/additionalProperties. Source comparison checks names only, not source types/requiredness or configured auth/session semantics. It does not access secrets/change runtimes. Read actual services/delegates for new operations. Runtime schemas are the callable interface; source/image/schema differences remain unverified until checked.

Candidate guided method/postData requires prepared auth/direct under actual provider/service semantics, rather than generic/anonymous body support. Follow [deployment selection](operation-dispatch.md#compare-actual-deployment-contracts). Same versions may have different JAR schemas; record actual image/JAR and unknown source-to-image provenance where applicable.

## 1. Import API definitions

- `zap_target_import`: guided OpenAPI/GraphQL/SOAP URL/file/content facade. Content supports OpenAPI only, requires enabled shared staging/full hostOverride; files must be readable by ZAP, not merely agent-local.
- `zap_import_openapi_spec_url`, `zap_import_openapi_spec_file`: OpenAPI import with policy-governed hostOverride.
- `zap_import_graphql_schema_url`, `zap_import_graphql_schema_file`: schema import for a specified GraphQL endpoint.
- `zap_import_soap_wsdl_url`, `zap_import_soap_wsdl_file`: WSDL import.

Prefer guided when sufficient, exposed expert when needed. Inspect definitions/add-ons/servers/refs/origins/warnings. Imports mutate sessions and may send requests; they are neither offline parsing nor active coverage. Reconcile specifications against source/runtime; missing definitions require suitable seed/crawl/adapters rather than dropped endpoints. Sources: GuidedSecurityToolsService/ExpertImportMcpToolsService and import services.

## 2. Prepare and validate authentication

- `zap_auth_session_prepare`: operator-managed profile + targetUrl → session/context/user; does not read chat passwords or create application roles.
- `zap_auth_session_validate`: sessionId validation before/during protected work.
- `zap_contexts_list`, `zap_context_upsert`: inspect/update target-specific include/exclude/in-scope contexts.
- `zap_users_list`, `zap_user_upsert`: inspect/update ZAP user credentials/config/enabled state, not application accounts.
- `zap_context_auth_configure`: auth method/configuration and login/logout indicators.
- `zap_auth_test_user`: configured contextId/userId check, rather than complete protected/role coverage.

Use suitable prepared profiles or supported expert context/user configuration. Resolve credentials privately under actual deployment/runner contracts, without secret argv/prompts; reflect authorized retention without asking again. Browser profiles use Client Spider strategy=client. Form/JSON bearer use http/auto and permitted active allowedKinds. AJAX strategy=browser rejects authSessionId. JSON bearer needs enabled/validated direct deployment; browser sessions do not automatically support active. Inspect GuidedScanWorkflowService.resolvePreparedSession/providers for actual auth kinds rather than assuming header/SSO/MFA compatibility. Sources: GuidedAuthSessionMcpToolsService/GuidedAuthSessionService; ExpertAuthMcpToolsService/ContextUserService.

## 3. Crawl for discovery and traffic

- `zap_crawl_start`: guided http (server links), client (JS/Client Spider), browser (AJAX), auto (HTTP with AJAX fallback only for failed unauthenticated direct HTTP start). Auto does not measure JS coverage.
- `zap_crawl_status`, `zap_crawl_stop`: guided operationId.
- `zap_spider_start`, `zap_spider_as_user`: HTTP anonymous/contextId+userId; `zap_spider_status`, `zap_spider_stop`: native scanId.
- `zap_client_spider_start`: maxDepth and optional contextName/userName (names differ from numeric IDs/login credentials); `zap_client_spider_status`, `zap_client_spider_stop`: scanId.
- `zap_ajax_spider`, `zap_ajax_spider_status`, `zap_ajax_spider_stop`, `zap_ajax_spider_results`: AJAX session lifecycle/results, rather than HTTP-style scanId. Check singleton ownership on shared scanners.

Verify Client add-on/Firefox/runtime. Choose suitable crawlers instead of starting all automatically. FE still requires actual UI actions/assertions. Constrain contexts/runtime before crawls that may follow unexpected links/mutations. Sources: guided workflow and SpiderScanService/ClientSpiderService/AjaxSpiderService; expert facades.

## 4. Policies and active techniques

- `zap_scan_policies_list`: actual policies.
- `zap_scan_policy_view`: rules/categories/filters/limits.
- `zap_scan_policy_rule_set`: real enable/disable/strength/threshold changes to an owned/authorized policy, rather than another run's shared policy.
- `zap_attack_start`: guided target/recurse/policy/optional authSessionId. Explicit method/postData requires direct/prepared auth and correctly seeded request bodies under actual schemas.
- `zap_attack_status`, `zap_attack_stop`: guided operationId.
- `zap_active_scan_start`, `zap_active_scan_as_user`: expert direct URL/recurse/policy, optionally contextId/userId.
- `zap_active_scan_status`, `zap_active_scan_stop`: native scanId.

Inspect actual policy/rules rather than fixing 40012/40018 for all products or enabling everything for counts. Expert direct currently lacks guided method/postData extension; surface changes do not solve all body cases. Anonymous explicit bodies use verified adapters, not fake auth handles. Separate wrapper admission/capability/gates, repair suitably, and do not bypass target/auth enforcement through raw APIs. Sources: ExpertDirectScanMcpToolsService/ActiveScanService; guided workflow/engine execution. MCP does not expose every native action.

## 5. Passive analysis and findings/reports

- `zap_passive_scan_status`, `zap_passive_scan_wait`: backlog/settling with timeout/poll; timeout is not zero alerts.
- `zap_findings_summary`, `zap_get_findings_summary`: guided/expert baseUrl summaries.
- `zap_findings_details`, `zap_alert_details`, `zap_alert_instances`: group/family/occurrence details under actual schemas/limits; limited samples are not all instances.
- `zap_alerts`: legacy base-URL list; use details/reports for suitable complete structure.
- `zap_report_generate`, `zap_generate_report`, `zap_view_templates`: guided HTML/JSON or expert template/theme/sites generation and template discovery.
- `zap_report_read`, `zap_report_read_chunk`: preview versus bounded offset/nextOffset/EOF reading, expected hash where required. Truncated previews do not establish full reading.
- `zap_findings_snapshot`, `zap_findings_diff`: conditional baselines/retests with maxGroups and version/add-on/scope compatibility checks before new/resolved claims.

Do not rescan to fix aggregation. Sessions may accumulate findings: establish target/run/historical attribution or state its limits. Reuse suitable collectors without turning internal hashes into mandatory handoff proof. Deliver the Drive assessment table; retain selected native outputs and three JSON projections internally rather than exporting every generator artifact. Sources: GuidedSecurityToolsService/ExpertResultsMcpToolsService, FindingsService/ReportService/PassiveScanService/core.

## 6. ZAP inventory

- `zap_hosts`, `zap_sites`, `zap_urls`: observed hosts/site roots/URLs, with optional baseUrl filtering where supported.

Reconcile with source/spec/UI, including unexpected origins. URLs do not establish every method/role/body scan. Session hosts do not authorize visits. Use exposed inventory or other actual observations; do not invent guided equivalents. Source: ExpertInventoryMcpToolsService/CoreService.

## 7. Queue and jobs

- `zap_queue_active_scan`, `zap_queue_active_scan_as_user`: anonymous/as-user active jobs.
- `zap_queue_spider_scan`, `zap_queue_spider_scan_as_user`: HTTP crawl jobs.
- `zap_queue_client_spider_scan`, `zap_queue_ajax_spider`: client/AJAX jobs with appropriate names/context.
- `zap_scan_job_status`, `zap_scan_job_list`, `zap_scan_job_cancel`: job lifecycle/filters/scoped cancellation.
- `zap_scan_job_retry`, `zap_scan_job_dead_letter_list`, `zap_scan_job_dead_letter_requeue`: retry/dead-letter operations under current contracts.

Queued is not executed. Queue idempotency may deduplicate; guided direct ignores the key and does not guarantee safe replay. Retry/requeue creates potential traffic: reconcile unknown outcomes/current targets/auth/fixtures/scope. Do not move direct JSON bearer into queue to evade limits or infer HA from tool presence. Sources: ExpertQueueMcpToolsService/ScanJobQueueService/GuidedExecutionModeResolver. Native scanId, guided operationId, and jobId differ.

## 8. Automation Framework

- `zap_automation_plan_run`: executes reviewed YAML file/inline under workspace/policy, rather than offline import.
- `zap_automation_plan_status`: running/messages/errors; completed does not automatically mean successful/passive-settled.
- `zap_automation_plan_artifacts`: bounded count/size previews under normalized planPath.

Use when supported native jobs fit orchestration. Inspect AutomationPlanService/AutomationPlanTargetPolicy for restrictions on scripts/import/browser jobs/proxy/config/variable destinations. maxDuration is a cooperative budget where supported, rather than network cutoff. AF does not replace UI journeys/BOLA or bypass other gates.

## 9. History and policy diagnostics

- `zap_scan_history_list`, `zap_scan_history_get`: filtered entries and specific entryId.
- `zap_scan_history_export`: filtered/limited inline JSON.
- `zap_scan_history_customer_handoff`: customer-safe Markdown, rather than full inventory-based RUN/ALERTS/SCOPE_ALERTS.
- `zap_scan_history_release_evidence`: conditional release/pilot bundle, not routine assessment output.
- `zap_policy_dry_run`: MCP Policy Bundle allow/deny preview by tool/target/time; differs from ZAP scan policy and application BOLA policy. Preview neither authorizes nor changes enforcement.

History supports continuation/reconciliation but “started” is not terminal. Do not assume complete retention/session recovery after restart. Omit raw secrets from exports. Sources: ScanHistoryMcpToolsService/ScanHistoryLedgerService; ExpertPolicyMcpToolsService/PolicyDryRunService.

## Needs requiring runner orchestration

No dedicated native MCP tools provide generic UI clicks/assertions, business fixtures/ownership oracles, full endpoint/role closure, or generation of the internal RUN, ALERTS and SCOPE_ALERTS projections. Use [runners](runner-routing.md)/[dispatch](operation-dispatch.md) for those gaps. Missing dedicated tools does not establish missing underlying primitives; inspect existing gateways/adapters before writing new ones.
