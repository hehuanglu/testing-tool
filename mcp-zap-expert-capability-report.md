# MCP ZAP Expert Mode runtime capability audit

Expert Mode on the published release **verified context and scope management, effective form-authenticated identity for two users, policy inspection and rule disable, direct and queued Spider lifecycle, passive Automation Framework execution, and structured findings and artifacts**. It is sufficient to develop and validate a local passive regression suite with application-owned identity assertions. An MCP-only advanced security regression gate still needs lifecycle and verdict interfaces. Authenticated Active DAST remains **BLOCKED** for runtime verification.

The [deployment provenance](mcp-zap-deployment-provenance.md) establishes the running revision. The [sanitized evidence bundle](mcp-zap-expert-capability-evidence.json) contains the exact tool schemas, per-call projections, fixture totals, resolved engine inventory and report digests. The [comparative assessment](mcp-zap-guided-vs-expert.md) lists outstanding changes. The targeted trials address gaps identified in the [Guided capability report](mcp-zap-capability-report.md), [Guided gap analysis](mcp-zap-gap-analysis.md), and [implementation audit](mcp-zap-extensibility-report.md).

## Runtime design and controls

The original Guided endpoint was rediscovered read-only. The isolated Expert endpoint used the same release JAR, a dedicated ZAP sidecar and an internal network with no public ports. Fixtures supplied synthetic credentials and emitted only method, path, HTTP status and resolved fixture subject. A separate hostname was used to replicate passive detection without relying on earlier alerts for that site. Docker handled provisioning, fixture log readback and staged plan inputs. All scanner operations and Automation Framework actions used the temporary Expert MCP endpoint. The audit preserved and subsequently checked the original deployments. [Evidence D01, D02, X01 and X02](mcp-zap-expert-capability-evidence.json)

Configuration was evaluated through MCP response and readback. Execution required a terminal observation and, where relevant, independent fixture access logs. Passive detection required a matched positive and negative control in the report. A completed job, auth boolean or report by itself was insufficient to establish a security outcome. The local run exercised ordinary form login and benign requests. Active execution was blocked by the audit boundary, and no exploit detection claim is made.

## Results

### Context and actor controls

- **Context setup and scope verified.** One native context was created, listed, set out of scope, restored and read back. Its exclusion prevented a linked route from appearing in fixture traffic. Removing the exclusion and rerunning produced one HTTP 200 request to that route. Context removal was absent and an attempted removal by the candidate tool name returned JSON-RPC -32602. [C01–C08, N01 and X01](mcp-zap-expert-capability-evidence.json)
- **Native form login and cookie replay verified for expert Spider.** Native auth configuration set positive and negative indicators. ZAP listed two enabled valid users and a third synthetic wrong-password control. Auth test returned true for the valid users and false for the wrong-password case. The fixture independently saw a login 401 for the wrong password, protected identity 200 for each correct actor, anonymous identity 401, and role-check results of reader 403 and editor 200. Browser login, session expiry, automatic renewal and packaged Guided auth handles remain unqualified. The prepared-profile tool rejected an unconfigured profile. [A01–A07 and X01](mcp-zap-expert-capability-evidence.json) · [ZAP authentication concepts](https://www.zaproxy.org/docs/getting-further/authentication/concepts/)
- **Application role evidence was verified independently.** The fixture owned the identity and role decision. MCP provided the native user-specific transport and status. General response, object, method and state assertions remain application responsibilities. [A06 and X01](mcp-zap-expert-capability-evidence.json)

### Policy and lifecycle

- **Policy configuration verified.** Expert listed and inspected policies. One enabled rule was disabled in the disposable Default Policy. Independent policy readback showed `enabled=no` and threshold `OFF`, with 52 enabled rules after 53 in the prior view. This is configuration proof. No active scan or detector execution was performed. Dedicated policy creation and deletion tools were absent. [P01–P04](mcp-zap-expert-capability-evidence.json)
- **Passive exploration lifecycle verified.** Direct Spider and user-specific Spider reached terminal progress with fixture traffic. An in-memory queued Spider moved from `RUNNING` to `SUCCEEDED`. A separate running job was cancelled and independently read back as `CANCELLED` with 60% progress. This proves queue cancellation state. The audit did not independently measure all traffic after cancellation or test durable PostgreSQL recovery. [A04, A06, E10, Q01 and Q02](mcp-zap-expert-capability-evidence.json)
- **Active and script limits.** Expert published active direct and queued tool schemas. Authenticated active execution and detection are **BLOCKED**. The engine inventory contained Script Console, while discovery contained no script-management tool. A candidate script-list method was rejected and a script job was rejected during plan submission. [D01, B01, N02, F04 and X03](mcp-zap-expert-capability-evidence.json)

### Automation Framework and evidence

- **Submission validation verified.** An unknown job type and a script job were rejected before dispatch. The separate validation-only method was absent. Inline plans and a workspace-file plan were accepted. The file-based plan produced the expected unique HTTP 404 fixture request. [F00, F04, F06, N03 and X02](mcp-zap-expert-capability-evidence.json)
- **Plan execution verified.** Two inline plans ran Requestor, passive wait and report in the expected order. A further run repeated the experiment at a fresh fixture site. Fixture logs and per-job progress corroborated execution. The three expected-status runs produced zero warnings. A fourth inline plan deliberately expected 204 for a route that returned 200 and recorded one warning. The wrapper reported `Successful: unknown` for all completed plans. A scanner-independent CI verdict is still needed. [F01–F03, F05 and X02](mcp-zap-expert-capability-evidence.json) · [ZAP Automation Framework](https://www.zaproxy.org/docs/desktop/addons/automation-framework/) · [ZAP Requestor](https://www.zaproxy.org/docs/desktop/addons/automation-framework/job-requestor/)
- **Passive detection and report retrieval verified.** Four report artifacts were discovered, paged through MCP and validated against their full SHA-256 digests. In every report, rule 10038 with CWE-693 identified only the planned missing-CSP route. The page with a CSP header was fetched and excluded from this alert family. The fresh-site run had its own request log and scoped artifact. [F01–F03, F05 and X02](mcp-zap-expert-capability-evidence.json) · [ZAP CSP rule 10038-1](https://www.zaproxy.org/docs/alerts/10038-1/)
- **Structured findings verified.** Expert returned v3 snapshots and a complete 49-add-on engine inventory. The same-inventory diff reported 18 unchanged findings and zero new or resolved findings. Rule-filtered alert instances and URL inventory worked after registering a crawl at the target origin. Earlier origin-wide reads were refused when only a narrower scan existed. Schema controls rejected incorrectly typed limits until corrected. Scanner provenance fields for MCP revision and image digest were null in the exported snapshot and were joined externally from verified deployment metadata. [E03–E07, E10–E18 and X03](mcp-zap-expert-capability-evidence.json)

## Discovered tool inventory

Expert published 78 tools. All 21 Guided tools remained available with identical input schemas, and 57 Expert-only tools were added. Both surfaces returned zero MCP resources, templates and prompts. The complete input schemas and descriptions are in the [evidence bundle](mcp-zap-expert-capability-evidence.json). Inventory establishes exposure. The experiment IDs above establish behavior.

- `zap_active_scan_as_user` with `contextId`, `userId`, `targetUrl`, `recurse`, `policy`
- `zap_active_scan_start` with `targetUrl`, `recurse`, `policy`
- `zap_active_scan_status` with `scanId`
- `zap_active_scan_stop` with `scanId`
- `zap_ajax_spider` with `targetUrl`
- `zap_ajax_spider_results` with no inputs
- `zap_ajax_spider_status` with no inputs
- `zap_ajax_spider_stop` with no inputs
- `zap_alert_details` with `baseUrl`, `pluginId`, `alertName`
- `zap_alert_instances` with `baseUrl`, `pluginId`, `alertName`, `limit`
- `zap_alerts` with `baseUrl`
- `zap_auth_test_user` with `contextId`, `userId`
- `zap_automation_plan_artifacts` with `planPath`, `maxArtifacts`, `maxChars`
- `zap_automation_plan_run` with `planPath`, `planYaml`, `planFileName`
- `zap_automation_plan_status` with `planId`, `maxMessages`
- `zap_client_spider_start` with `targetUrl`, `maxDepth`, `contextName`, `userName`
- `zap_client_spider_status` with `scanId`
- `zap_client_spider_stop` with `scanId`
- `zap_context_auth_configure` with `contextId`, `authMethodName`, `authMethodConfigParams`, `loggedInIndicatorRegex`, `loggedOutIndicatorRegex`
- `zap_context_upsert` with `contextName`, `includeRegexes`, `excludeRegexes`, `inScope`
- `zap_contexts_list` with no inputs
- `zap_findings_diff` with `baseUrl`, `baselineSnapshot`, `maxGroups`
- `zap_findings_snapshot` with `baseUrl`
- `zap_generate_report` with `reportTemplate`, `theme`, `sites`
- `zap_get_findings_summary` with `baseUrl`
- `zap_hosts` with no inputs
- `zap_import_graphql_schema_file` with `endpointUrl`, `filePath`
- `zap_import_graphql_schema_url` with `endpointUrl`, `schemaUrl`
- `zap_import_openapi_spec_file` with `filePath`, `hostOverride`
- `zap_import_openapi_spec_url` with `apiUrl`, `hostOverride`
- `zap_import_soap_wsdl_file` with `filePath`
- `zap_import_soap_wsdl_url` with `wsdlUrl`
- `zap_policy_dry_run` with `policyBundle`, `toolName`, `target`, `evaluatedAt`
- `zap_queue_active_scan` with `targetUrl`, `recurse`, `policy`, `idempotencyKey`
- `zap_queue_active_scan_as_user` with `contextId`, `userId`, `targetUrl`, `recurse`, `policy`, `idempotencyKey`
- `zap_queue_ajax_spider` with `targetUrl`, `idempotencyKey`
- `zap_queue_client_spider_scan` with `targetUrl`, `maxDepth`, `contextName`, `userName`, `idempotencyKey`
- `zap_queue_spider_scan` with `targetUrl`, `idempotencyKey`
- `zap_queue_spider_scan_as_user` with `contextId`, `userId`, `targetUrl`, `maxChildren`, `recurse`, `subtreeOnly`, `idempotencyKey`
- `zap_scan_job_cancel` with `jobId`
- `zap_scan_job_dead_letter_list` with no inputs
- `zap_scan_job_dead_letter_requeue` with `jobId`
- `zap_scan_job_list` with `statusFilter`
- `zap_scan_job_retry` with `jobId`
- `zap_scan_job_status` with `jobId`
- `zap_scan_policies_list` with no inputs
- `zap_scan_policy_rule_set` with `scanPolicyName`, `ruleIds`, `enabled`, `attackStrength`, `alertThreshold`
- `zap_scan_policy_view` with `scanPolicyName`, `ruleFilter`, `limit`
- `zap_sites` with no inputs
- `zap_spider_as_user` with `contextId`, `userId`, `targetUrl`, `maxChildren`, `recurse`, `subtreeOnly`
- `zap_spider_start` with `targetUrl`
- `zap_spider_status` with `scanId`
- `zap_spider_stop` with `scanId`
- `zap_urls` with `baseUrl`
- `zap_user_upsert` with `contextId`, `userName`, `authCredentialsConfigParams`, `enabled`
- `zap_users_list` with `contextId`
- `zap_view_templates` with no inputs

## Conclusion

Use the released Expert surface for local context/auth setup, passive suite validation and evidence inspection. It already covers these workflows and requires deployment configuration and application-specific fixtures. A self-contained MCP pipeline still needs, where required, separate plan validation and stop, a reliable per-job verdict, scoped context/user cleanup, and a redacted message contract. An independent CI runner can own plan validation, process exit, test data and deterministic application assertions. GitHub Actions and active DAST execution remain unqualified.
