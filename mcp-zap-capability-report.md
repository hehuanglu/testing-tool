# MCP ZAP capability audit

## Executive summary

The connected MCP server supports a reproducible passive security check against a local fixture. It can run and monitor a traditional crawl, import OpenAPI from a URL or an engine-readable file, wait for passive analysis, retrieve findings, and export integrity-checked JSON and HTML reports. This deployment lacks the interfaces needed to author and run a complete advanced security regression suite through MCP. In particular, its guided surface has no context and user administration, general request and assertion interface, script management, or Automation Framework plan lifecycle.

The matrix classifies 114 capabilities. 14 BLOCKED, 1 EXPOSED_UNTESTED, 18 INDIRECT, 13 PARTIAL, 48 UNSUPPORTED, 20 VERIFIED. A verified row is limited to the behavior demonstrated by its experiment. The [sanitized evidence bundle](mcp-zap-capability-evidence.json) contains the full discovered schemas, trial records, and projected results. The [gap analysis](mcp-zap-gap-analysis.md) lists the owner and CI effect of each open capability.

## Environment

- Audit date 2026-11-24, Vietnam time. Fixture calls ran from 11:28:18 to 11:33:03 ICT.
- Server `mcp-zap-server` 0.16.0, as returned by MCP initialization. Streamable HTTP at `http://127.0.0.1:7456/mcp`, negotiated protocol version `2025-03-26`.
- ZAP 2.17.0, independently shown in the downloaded ZAP JSON report and corroborated by the running Docker image label. Successful crawl, import, passive and report operations confirmed engine connectivity.
- Both existing containers reported healthy. Docker exposed ZAP and MCP on loopback. The audit fixture was on the private Docker network with no published port.
- The host chat tool registry had no ZAP namespace. The configured header helper exited unsuccessfully. An unauthenticated MCP initialization returned HTTP 401. The audit used a separate MCP protocol client with the deployment's documented client credential from its matching local configuration. It preserved the same endpoint and authentication boundary. Credential values, headers, opaque MCP and operation handles, and internal report paths were omitted from the evidence.
- ZAP's persisted runnable add-on inventory lists 49 entries. That inventory came from a read-only engine file, an indirect mechanism. The full inventory is in experiment M03. Relevant versions include Automation Framework 0.62.0, Authentication Helper 0.44.0, OpenAPI 58.0.0, Spider 0.20.0, AJAX Spider 23.33.0, Client Side Integration 0.35.0, passive rules 79.0.0, active rules 84.0.0, Reports 0.46.0, Script Console 45.20.0, Alert Filters 29.0.0, Sequence 10.0.0, Replacer 22.0.0, Requester 7.10.0 and Fuzzer 13.17.0. Archive directories also contained other versions. Access Control Testing did not appear in the persisted runnable inventory.
- Source cross-check used the bundled server at workspace commit `e8197caab2d530287214b0e7b8231a3691e0bba8`. Its expert registration branch explains capabilities present in source that were unavailable on the connected surface. The live MCP responses govern the classification.

## MCP tool inventory

Discovery returned 21 tools, zero resources, zero resource templates, and zero prompts. Each tool supplied an input schema. No tool advertised an output schema. The [evidence bundle](mcp-zap-capability-evidence.json) preserves the exact protocol input schemas and descriptions. Required fields are marked below.

- `zap_attack_start` accepts targetUrl (string, required), recurse (string), policy (string), idempotencyKey (string), authSessionId (string).
- `zap_attack_status` accepts operationId (string, required).
- `zap_attack_stop` accepts operationId (string, required).
- `zap_auth_session_prepare` accepts profileId (string, required), targetUrl (string, required).
- `zap_auth_session_validate` accepts sessionId (string, required).
- `zap_crawl_start` accepts targetUrl (string, required), strategy (string), idempotencyKey (string), authSessionId (string).
- `zap_crawl_status` accepts operationId (string, required).
- `zap_crawl_stop` accepts operationId (string, required).
- `zap_findings_details` accepts baseUrl (string, required), pluginId (string), alertName (string), includeInstances (boolean), limit (integer).
- `zap_findings_summary` accepts baseUrl (string, required).
- `zap_passive_scan_status` accepts no parameters.
- `zap_passive_scan_wait` accepts timeoutSeconds (integer), pollIntervalMs (integer).
- `zap_report_generate` accepts baseUrl (string), format (string), theme (string).
- `zap_report_read` accepts reportPath (string, required), maxChars (integer).
- `zap_report_read_chunk` accepts reportPath (string, required), offset (integer), maxChars (integer), expectedSha256 (string).
- `zap_scan_history_customer_handoff` accepts handoffName (string), target (string), limit (integer).
- `zap_scan_history_export` accepts evidenceType (string), status (string), target (string), limit (integer).
- `zap_scan_history_get` accepts entryId (string, required).
- `zap_scan_history_list` accepts evidenceType (string), status (string), target (string), limit (integer).
- `zap_scan_history_release_evidence` accepts releaseName (string), target (string), limit (integer).
- `zap_target_import` accepts definitionType (string, required), sourceKind (string, required), source (string, required), endpointUrl (string), hostOverride (string).

The exposed tools map to selected ZAP capabilities. The mappings below describe the server interfaces and associated engine components. They do not imply access to those components' other operations. [ZAP API Reference](https://www.zaproxy.org/docs/api/), [ZAP exploration guidance](https://www.zaproxy.org/docs/getting-further/automation/exploring-your-app/), [ZAP OpenAPI support](https://www.zaproxy.org/docs/desktop/addons/openapi-support/), [ZAP passive scanner](https://www.zaproxy.org/docs/desktop/addons/passive-scanner/), [ZAP report generation](https://www.zaproxy.org/docs/desktop/addons/report-generation/), [ZAP Client Spider API](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/spider-api/)

- Discovery writes to the Sites Tree and HTTP History through traditional Spider, AJAX Spider, Client Spider and selected `openapi`, `graphql` and `soap` imports. Traditional Spider and OpenAPI imports were verified. Browser coverage remains partial.
- `zap_passive_scan_status` and `zap_passive_scan_wait` read passive scanner state. Rule management and context scope settings are absent. The wait concerns the engine backlog.
- The guided attack tools expose a target, recursion flag, optional prepared policy name and authentication session reference, with operation status and stop. The live audit exercised no active scan.
- Auth session tools reference operator-managed profiles for HTTP form or Client Spider browser workflows. They expose no profile authoring, ZAP user management, or target identity response readback.
- Guided findings and reports read ZAP alerts and report artifacts. `zap_scan_history_*` reads or projects the MCP scan and artifact ledger. Native HTTP History is a separate ZAP capability.
- No generic native API dispatcher, arbitrary file interface, script registration path, or Automation Framework tool was published. Read-only negative probes for context list, automation status and a direct version tool returned JSON-RPC -32602.

## Experiment methodology

All target traffic was scoped to a disposable static NGINX fixture. The fixture served a two-link homepage, two CSP test pages, a self-contained OpenAPI document and a read-only API response. It had no external links or application credentials. A file-import variant used a separately staged copy with its own query parameter. Docker was used for provisioning, a read-only add-on inventory, and independent fixture logs. All ZAP operations used MCP Streamable HTTP. The first fixture start failed on a PID-path permission issue and was repaired in the temporary fixture configuration. The fixture and staged definition were removed after the experiments. Audit-related history and generated reports remain in the current engine and MCP workspaces.

Runtime proof combines the MCP response, independent fixture access logs, and result readback. Where possible, the process checked a start, status transition, terminal response, fixture effect and repeat run. For findings, the downloaded JSON was parsed and reconciled to the fixture controls. For reports, pages were reconstructed, full SHA-256 was checked, and the fixture and format were inspected. A wrong-digest control verified that inconsistent pages are rejected. Source and official documentation are evidence of design or native support. Only successful current-runtime operations earn `VERIFIED`. An unavailable route means `UNSUPPORTED` for the currently exposed surface when discovery or a negative probe establishes absence. `BLOCKED` means the route was available or documented but an execution or fixture dependency prevented proof. `INDIRECT` identifies a capability outside the available MCP path.

## Runtime results

1. **Traditional Spider and monitoring.** Both crawl runs reached 100%. The second was sampled at 25% before completion. Fixture logs showed two successful visits to each linked page, along with the expected root and discovery requests. The scan ledger kept both direct starts as `started`, so the ledger alone would not establish completion.
2. **OpenAPI imports.** URL import caused a `GET /audit-spec` and a `GET /audit-api-check?sample=audit`, both HTTP 200. File import caused a second request with `source=file`. Inline import returned an explicit disabled-staging error. The one tested operation does not establish complete Sites Tree or Params inspection.
3. **Browser crawls and stop.** AJAX status showed running, followed by stopped after a stop request. A subsequent start received a busy error despite the earlier stopped status. A later poll showed stopped with one discovered URL. Client Spider had one run with zero progress and no matching fixture request, and a repeat with a matching request and zero progress before cooperative stop. Both Client Spider runs exposed 100% after stop. That return value leaves successful coverage unconfirmed. Browser-specific completion and repeatability remain partial.
4. **Passive execution and detection.** The engine reported a drained queue and zero active tasks. The missing-CSP page produced rule 10038, alert reference 10038-1, CWE-693. The page with a CSP header was fetched and excluded from the missing-header results. The JSON report also confirmed presence and absence of the header in the respective fixture responses. The same missing-header result appeared after a second traditional crawl. Evidence covers this passive detector only. [ZAP passive rule 10038-1](https://www.zaproxy.org/docs/alerts/10038-1/)
5. **Findings and reports.** The bounded rule drilldown returned four recorded instances, and a limit of one returned a single instance. The JSON report identified the sole fixture site and contained seven alert groups, with affected headers such as `x-frame-options` reported as parameters. The JSON artifact contained request and response fields for alert-associated messages. These fields were projected to allowlisted properties for this audit. Automatic redaction and retrieval of arbitrary messages remain unverified. JSON and HTML artifacts were reconstructed in nine and five pages respectively and their SHA-256 digests matched. The JSON included the engine version, rule, CWE and fixture endpoint. HTML contained the expected finding and endpoint.
6. **Ledger and handoff.** A scoped scan ledger export returned two reports and two direct crawl starts for the initial window. A listed entry could be retrieved by handle, and both a release evidence export and a customer handoff were returned. The handoff reported `CAVEAT` and carries no fixture verdict by itself.
7. **Authentication and plans.** Guided authentication rejected an unconfigured synthetic profile and an invalid session handle. These are input controls independent of target login, actor identity, expiry and reauthentication. Automation Framework status was rejected as an absent tool. No plan was executed, and YAML materialization alone would not be execution evidence.

## Capability matrix

Evidence IDs resolve to experiments or official documentation in the evidence bundle. Browser experiment prefixes refer to all start, status and stop records in that trial.

| ID | Capability | Native ZAP support | MCP tool | Status | Evidence | CI/CD feasibility |
|---|---|---|---|---|---|---|
| M01 | MCP transport, tools, schemas, resources and prompts | MCP protocol | MCP initialize and discovery | VERIFIED | M01 M02 | Build discovery into runner startup |
| M02 | ZAP version and engine connectivity | core.version | zap_report_generate / read_chunk | VERIFIED | I08 | Record live report version |
| M03 | Installed or runnable add-ons and versions | autoupdate | None | INDIRECT | M03 M02 | Use engine inventory outside MCP |
| M04 | Arbitrary ZAP API invocation | ZAP component APIs | None | UNSUPPORTED | M02 X02 | Use typed interfaces |
| M05 | Asynchronous start, monitoring and stop | Spider and scanner component APIs | zap_crawl_start / status / stop | VERIFIED | C02 C04 C06 C07 | Use operation status and fixture evidence |
| M06 | File and artifact handling | Importer, exports and reports | zap_target_import / zap_report_read_chunk | PARTIAL | C05 C10 I08 M02 | Artifact retrieval works; general file management absent |
| M07 | Script management | script API and Automation Framework script job | None | UNSUPPORTED | M02 H01 | No managed lifecycle |
| A01 | Create contexts | context API | None | UNSUPPORTED | M02 X01 | Pre-provisioning or a typed context interface |
| A02 | Retrieve contexts | context API | None | UNSUPPORTED | M02 X01 | No context readback |
| A03 | Update contexts | context API | None | UNSUPPORTED | M02 X01 | No context update |
| A04 | Remove contexts | context API | None | UNSUPPORTED | M02 X01 | No managed cleanup |
| A05 | Include URLs | context include rules | None | UNSUPPORTED | M02 | Explicit fixture boundaries needed |
| A06 | Exclude URLs | context exclusion rules | None | UNSUPPORTED | M02 | No caller-managed exclusions |
| A07 | Restrict to selected API operations | Context URLs and scanner targeting support some cases | zap_crawl_start / zap_attack_start | PARTIAL | M02 C05 | Target URL available; method-and-operation allowlist absent |
| A08 | Configure and verify ZAP scope | context.setContextInScope and context readback | None | UNSUPPORTED | M02 P01 | Shared scanner scope cannot be managed |
| A09 | Isolated ZAP session lifecycle | core new, load and save session | None | UNSUPPORTED | M02 | Provision separate engine instances externally |
| B01 | JSON-based authentication | Native JSON-based authentication | None | UNSUPPORTED | M02 B01 | Guided schema documents form and browser profiles |
| B02 | Form-based authentication | Native form-based authentication | zap_auth_session_prepare / validate | BLOCKED | B01 B02 M02 | Needs preconfigured local fixture profile and identity check |
| B03 | Script-based authentication | Script Console and authentication component | None | UNSUPPORTED | M02 H01 | No script or context binding |
| B04 | Browser-based authentication | Authentication Helper and a browser | zap_auth_session_prepare / validate; client strategy | BLOCKED | B01 B02 M02 | Needs configured browser profile and effective identity check |
| B05 | JWT Bearer authentication to target | Header session management and app-specific token acquisition | None | UNSUPPORTED | M02 | MCP client API-key auth is independent |
| B06 | Cookie-based session management | Native cookie session management | zap_auth_session_prepare / validate | PARTIAL | M02 B01 B02 | Documented form profile route; no cookie configuration or identity proof |
| B07 | Header-based session management | Authentication Helper headers session management | None | UNSUPPORTED | M02 | No target-header lifecycle interface |
| B08 | Multiple users and roles in a context | ZAP users; app assigns roles | zap_auth_session_prepare | PARTIAL | M02 B01 X01 | Separate operator profiles can be referenced; no user or role management |
| B09 | Automatic authentication | ZAP authentication and verification | zap_auth_session_prepare / validate | BLOCKED | B01 B02 | No configured fixture profile |
| B10 | Automatic reauthentication | ZAP verification and reauthentication | zap_auth_session_prepare / validate | BLOCKED | B01 B02 | No expired-session and recovery observation |
| B11 | Authentication verification | ZAP verification strategies | zap_auth_session_validate | BLOCKED | B01 B02 | Unknown-session control only |
| B12 | Target authentication failure detection | Logged-out marker, poll or app identity endpoint | zap_auth_session_validate | BLOCKED | B02 | Handle rejection gives no app-layer proof |
| B13 | Reuse authenticated state across tool calls | ZAP user and context session handling | zap_crawl_start / zap_attack_start authSessionId | BLOCKED | M02 B01 B02 | Needs identity readback across multiple requests |
| C01 | OpenAPI URL import | openapi importer | zap_target_import | VERIFIED | C05 F01 | API operation and query observed |
| C02 | OpenAPI import from file | openapi importer | zap_target_import | VERIFIED | C11 F01 | ZAP-readable file supplied by runner; operation and parameter observed |
| C03 | OpenAPI import from inline content | openapi importer plus MCP staging | zap_target_import | BLOCKED | C10 | Dedicated shared staging disabled |
| C04 | Traditional Spider | spider add-on | zap_crawl_start / status | VERIFIED | C01 C02 C03 C04 F01 | Repeated completed crawl with independent access logs |
| C05 | AJAX Spider | spiderAjax add-on | zap_crawl_start / status / stop | PARTIAL | C06 C09 F01 | Observed fixture traffic and lifecycle; coverage/results interface limited |
| C06 | Client Spider | clientSpider add-on | zap_crawl_start / status / stop | PARTIAL | C07 C08 F01 | Observed lifecycle; readiness and coverage require independent evidence |
| C07 | Authenticated exploration | User-specific spiders | zap_auth_session_prepare / zap_crawl_start | BLOCKED | M02 B01 B02 | No authenticated identity sample |
| C08 | Register or send selected manual HTTP requests | core.sendRequest or Automation Framework requestor | None | UNSUPPORTED | M02 H01 | No deterministic HTTP transport for custom cases |
| C09 | Inspect Sites Tree | core sites and URLs; import/export add-on | None | UNSUPPORTED | M02 | Report evidence shows a subset |
| C10 | Inspect HTTP History | core.messages and message | zap_scan_history_list / get | PARTIAL | M02 I07 I10 I08 | Scan ledger plus report messages; no arbitrary HTTP history |
| C11 | Verify discovered operations and parameters | Sites Tree, HTTP History and Params add-on | zap_target_import; limited report evidence | PARTIAL | C05 F01 I08 | Independent fixture log confirms one operation and parameter; no full MCP inventory |
| C12 | GraphQL and SOAP import | graphql and soap add-ons | zap_target_import | EXPOSED_UNTESTED | M02 M03 | Requires dedicated fixtures |
| D01 | Configure passive scanners | pscan and passiveScan-config | None | UNSUPPORTED | M02 P01 | Operator defaults only |
| D02 | Enable or disable individual passive rules | pscan and passiveScan-config | None | UNSUPPORTED | M02 | No per-rule control |
| D03 | Set passive alert thresholds | pscan and passiveScan-config | None | UNSUPPORTED | M02 | No threshold management |
| D04 | Monitor passive queue | pscan recordsToScan and tasks | zap_passive_scan_status | VERIFIED | P01 P02 P04 | Reports remaining work and active tasks |
| D05 | Wait for passive completion | pscan and passiveScan-wait | zap_passive_scan_wait | VERIFIED | P02 P03 P04 I02 I03 | Repeatable bounded wait; queue is shared |
| D06 | Retrieve structured passive results | alert API and report add-on | zap_findings_details / zap_report_generate / read_chunk | VERIFIED | I02 I03 I08 | Machine-readable JSON report |
| D07 | Detect a known passive condition with controls | Passive rule 10038 | Crawl, wait and findings tools | VERIFIED | F01 I02 I03 I08 | Missing-CSP predicate reproduced |
| E01 | Create custom active scan policies | ascan policy operations and activeScan-policy | None | UNSUPPORTED | M02 | Only a named policy selector is exposed |
| E02 | Select individual active rules | ascan scanners and policy controls | zap_attack_start policy | PARTIAL | M02 | Can reference prepared policy; cannot select rules through it |
| E03 | Configure active rule strength | ascan scanner controls | None | UNSUPPORTED | M02 | No caller-set strength |
| E04 | Configure active rule thresholds | ascan scanner controls | None | UNSUPPORTED | M02 | No caller-set alert threshold |
| E05 | Restrict active scan to specific context | ascan context and scope options | zap_attack_start | PARTIAL | M02 | Target and recursion controls; no explicit context argument |
| E06 | Restrict active scan by API method or operation | Partial native URL and parameter restrictions | zap_attack_start | PARTIAL | M02 | Target URL and recursion cannot express an operation manifest |
| E07 | Authenticated Active Scan | ascan and authentication | zap_attack_start with authSessionId | BLOCKED | M02 B01 | No runtime active or authenticated proof |
| E08 | User-specific Active Scan | ascan scanAsUser | zap_attack_start with authSessionId | BLOCKED | M02 B01 | Operator profile reference is documented; no runtime actor proof |
| E09 | Parameter-specific active scanning | ascan input vectors, exclusions and policies | None | UNSUPPORTED | M02 | No parameter selector |
| E10 | Configure duration and resource limits at runtime | ascan duration, concurrency and related options | None | UNSUPPORTED | M02 | Server defaults are deployment controls |
| E11 | Start or monitor active scan | ascan scan and status | zap_attack_start / status | BLOCKED | M02 | Active execution restricted for this audit |
| E12 | Stop running active scan | ascan stop | zap_attack_stop | BLOCKED | M02 | Active execution restricted for this audit |
| E13 | Retrieve active findings with HTTP evidence | alert, core messages and reports | zap_findings_details / zap_report_generate | BLOCKED | I08 M02 | HTTP evidence proved for passive findings |
| F01 | Role-based access-control cases | Access Control add-on, app-defined rules | None | INDIRECT | M02 R04 | Needs explicit role verdict criteria |
| F02 | Horizontal authorization cases | Partial Access Control support; app ownership semantics | None | INDIRECT | M02 R04 | Needs per-actor ownership assertions |
| F03 | Vertical authorization cases | Partial Access Control support; app privilege semantics | None | INDIRECT | M02 R04 | Needs privilege-level assertions |
| F04 | Object-level authorization / BOLA | Partial URL rules; app object oracle | None | INDIRECT | M02 R04 | Needs identity and object ownership evidence |
| F05 | Function-level authorization / BFLA | Partial URL rules; app function and method oracle | None | INDIRECT | M02 R04 | Needs method-specific role assertions |
| F06 | Unauthenticated access restrictions | Access Control can include anonymous user | None | INDIRECT | M02 R04 | Needs positive and anonymous controls |
| F07 | Session isolation tests | App-specific oracle over ZAP traffic | None | INDIRECT | M02 B02 | Needs independent sessions and identity verification |
| F08 | Multi-user request workflows | Automation Framework requestor and application fixtures | None | INDIRECT | M02 H01 | Requires deterministic actor-aware orchestration |
| F09 | Expected HTTP status assertions | Automation Framework requestor responseCode | None | INDIRECT | M02 H01 R04 | Status alone gives limited business evidence |
| F10 | Response content assertions | Custom script or application test harness | None | INDIRECT | M02 R04 | Needs stable semantic response assertions |
| F11 | Application state verification | App-specific readback or fixture oracle | None | INDIRECT | M02 R04 | Requires app-owned reset and state access |
| G01 | HTTP Sender scripts | Script Console HTTP Sender | None | UNSUPPORTED | M02 H01 | No registration, execution or inspection |
| G02 | Authentication scripts | Script Console authentication | None | UNSUPPORTED | M02 H01 | No registration, execution or inspection |
| G03 | Session management scripts | Script Console session management | None | UNSUPPORTED | M02 H01 | No registration, execution or inspection |
| G04 | Active scanner scripts | Script Console active rules | None | UNSUPPORTED | M02 H01 | No registration, execution or inspection |
| G05 | Passive scanner scripts | Script Console passive rules | None | UNSUPPORTED | M02 H01 | No registration, execution or inspection |
| G06 | Standalone scripts | Script Console standalone type | None | UNSUPPORTED | M02 H01 | No registration, execution or inspection |
| G07 | Requestor or Requester | Automation Framework requestor and Requester add-on | None | UNSUPPORTED | M02 H01 | No configure, execute or inspect interface |
| G08 | Replacer | Replacer add-on and Automation Framework job | None | UNSUPPORTED | M02 | No configure, execute or inspect interface |
| G09 | Fuzzer | Fuzzer add-on, primarily desktop | None | UNSUPPORTED | M02 M03 | No MCP control demonstrated |
| G10 | Request sequence management | Sequence add-on, HAR import, sequence script | None | UNSUPPORTED | M02 | No configure, execute or inspect interface |
| G11 | Custom input vectors | Script Console variant scripts | None | UNSUPPORTED | M02 H01 | No lifecycle interface |
| G12 | Dynamic extraction and reuse | Scripts or external harness | None | INDIRECT | M02 R04 | Requires a typed data-flow and assertion runner |
| G13 | Conditional execution | Ordered jobs and alwaysRun; richer behavior via scripts or runner | None | INDIRECT | M02 H01 | No MCP branching semantics |
| G14 | Custom security assertions | Built-in Automation Framework tests and custom assertions outside them | None | INDIRECT | M02 H01 R04 | Needs app-owned assertions |
| H01 | Create an Automation Framework YAML plan | Automation Framework templates, GUI or file authoring | None | INDIRECT | M02 H01 R05 | YAML authoring can live in source control |
| H02 | Import Automation Framework plans | Automation Framework file input and API | None | UNSUPPORTED | M02 H01 | Expert source has file or inline submission |
| H03 | Export or round-trip Automation Framework plans | Automation Framework file/GUI handling | None | UNSUPPORTED | M02 H01 | Versioned source remains external |
| H04 | Validate Automation Framework configuration | Automation Framework CLI validation | None | UNSUPPORTED | M02 H01 R05 | No validation-only MCP path |
| H05 | Execute Automation Framework plans | automation.runPlan | None | UNSUPPORTED | M02 H01 | Expert run tool absent in live surface |
| H06 | Monitor individual job execution | Automation Framework progress, output and job tests | None | UNSUPPORTED | M02 H01 | No per-job MCP telemetry |
| H07 | Configure dependencies and ordering | Ordered jobs, enabled and alwaysRun flags; no general DAG | None | UNSUPPORTED | M02 H01 R05 | Runner owns dependency graph |
| H08 | Configure alert tests | Automation Framework alert test | None | UNSUPPORTED | M02 H01 R05 | No plan submission |
| H09 | Configure statistics tests | Automation Framework stats test | None | UNSUPPORTED | M02 H01 R05 | No plan submission |
| H10 | Configure monitor tests | Automation Framework monitor test | None | UNSUPPORTED | M02 H01 R05 | No plan submission |
| H11 | Configure URL tests | Automation Framework URL presence test | None | UNSUPPORTED | M02 H01 R05 | No plan submission |
| H12 | Configure execution failure conditions | Automation Framework exitStatus and test failure controls | None | UNSUPPORTED | M02 H01 R05 | External runner must derive exit verdict |
| H13 | Generate machine-readable reports | Reports add-on and report job | zap_report_generate / read_chunk | VERIFIED | I08 | Structured standalone report; AF report job unverified |
| H14 | Run a reproducible noninteractive workflow | Headless engine and API or Automation Framework | MCP crawl, passive wait and report tools | PARTIAL | C02 C04 I08 I09 | Repeatable passive subset; plan and assertion pipeline unavailable |
| H15 | Headless and Docker execution | Official ZAP Docker images | Current Streamable HTTP deployment | VERIFIED | M01 M03 C04 I08 | Local container deployment observed |
| H16 | GitHub Actions compatibility | ZAP Docker and published GitHub Actions | Streamable HTTP accessible from a runner in principle | INDIRECT | M01 R06 | No Actions job or end-to-end qualification |
| H17 | Stop Automation Framework plan and inspect its artifacts | automation.stopPlan and report filesystem | None | UNSUPPORTED | M02 H01 R05 | Expert source only lists artifact previews; no stop tool found |
| I01 | Retrieve alerts | alert API and reports | zap_findings_summary / details | VERIFIED | I01 I02 | Grouped and instance evidence |
| I02 | Retrieve CWE identifiers | alert fields and report cweid | zap_findings_details / zap_report_read_chunk | VERIFIED | I02 I08 | CWE-693 confirmed |
| I03 | Retrieve scan rule identifiers | alert plugin ID and alert reference | zap_findings_details / zap_report_read_chunk | VERIFIED | I02 I08 | Plugin 10038 and alert 10038-1 |
| I04 | Retrieve affected endpoints and parameters | alert instances and report fields | zap_findings_details / zap_report_read_chunk | VERIFIED | I02 I08 | JSON included affected routes and header parameters |
| I05 | Retrieve sanitized HTTP requests and responses | core.messages and HTTP-inclusive report templates | zap_report_generate / read_chunk | PARTIAL | I08 I09 | Raw fixture HTTP demonstrated; redaction and arbitrary message retrieval unverified |
| I06 | Filter and group findings | alert query and summary views | zap_findings_summary / details | VERIFIED | I01 I02 I13 | Scope, plugin and limit exercised |
| I07 | Configure alert filters | alertFilter add-on and alertFilter job | None | UNSUPPORTED | M02 M03 | Post-processing filters are separate from ZAP alert rules |
| I08 | Generate and retrieve JSON report | Report Generation add-on | zap_report_generate / read / read_chunk | VERIFIED | I04 I08 I14 | Parsed and digest-checked |
| I09 | Generate and retrieve HTML report | Report Generation add-on | zap_report_generate / read / read_chunk | VERIFIED | I05 I09 | Fixture markers and digest checked |
| I10 | Export evidence and handoff | ZAP reports plus MCP ledger | zap_scan_history_list / get / export / release_evidence / customer_handoff | VERIFIED | I06 I07 I10 I11 I12 | Evidence export works; started ledger rows remain started |
| I11 | Map findings to objectives and case IDs | CWE and tags; external objective taxonomy | Findings and reports as inputs | INDIRECT | I02 I08 R04 | Join in a versioned evidence mapper |

## Limitations and missing capabilities

The current guided surface cannot manage contexts, users, session isolation, ZAP scope, passive rule settings, active policy authoring, arbitrary HTTP messages, scripts, alert filters, or Automation Framework plans. Authenticated coverage remains blocked by the lack of configured fixture profiles. Active DAST was capability-reviewed without running active rules, generating payloads or qualifying exploit detection. The passive backlog and ZAP session were engine-wide although reported findings were fixture-scoped. No GitHub Actions run was executed. The gap analysis distinguishes absent guided tools from existing expert-source methods and native ZAP support.

## Recommendations

1. Use the verified passive subset as a CI smoke check isolated to a dedicated scanner workspace and fixture. Compare a scoped positive and negative result, drain passive work, capture the engine version, and validate the report digest before deriving a verdict.
2. Before relying on authenticated observations, configure approved fixture profiles through deployment administration and prove effective identity and session lifecycle on a dedicated test instance. Document the same proof for each actor.
3. For governance and evidence, prioritize typed context lifecycle, configuration readback, documented result schemas, and a redacted HTTP evidence interface. Treat the source-only expert features as a separate deployment qualification. An unbounded native API pass-through would weaken the audit boundary.
4. Keep product-specific assertions, fixtures, data reset, workflow composition, and case-to-objective mapping with the application test suite. Qualify the CI environment and artifact policy before using report data as a merge gate.

## Final assessment

1. **Advanced authenticated DAST** is unverified and operationally insufficient on this deployment. Guided form and browser session references exist. Effective identity, authenticated crawl and active execution were unproved.
2. **Multiple authenticated users and roles** cannot be managed through the current MCP surface. Existing profiles can be referenced by ID. Application roles and per-actor authorization expectations reside in the test environment.
3. **Deterministic authorization and business logic** require an application test harness. ZAP's Access Control Testing add-on supports URL/user rules where installed and configured, while business outcomes require actor, resource, method and post-state oracles. [ZAP Access Control Testing](https://www.zaproxy.org/docs/desktop/addons/access-control-testing/), [ZAP requestor job](https://www.zaproxy.org/docs/desktop/addons/automation-framework/job-requestor/)
4. **Advanced scripts** cannot be configured, executed or inspected on the current MCP surface. Native ZAP scripting depends on the script type, script engine and add-on. [ZAP script types](https://www.zaproxy.org/docs/getting-further/scripting/script-types/), [ZAP script job](https://www.zaproxy.org/docs/desktop/addons/script-console/automation/)
5. **Reusable Automation Framework plans** cannot be created, validated and executed end to end through the current surface. The bundled source contains expert-mode run/status/artifact methods for a restricted plan subset. Native validation and execution are documented independently. [ZAP Automation Framework CLI and API](https://www.zaproxy.org/docs/desktop/addons/automation-framework/), [ZAP Framework jobs](https://www.zaproxy.org/docs/automate/automation-framework/)
6. **Evidence for security objective evaluation** is sufficient for the tested passive header objective with an external oracle. General objective evaluation needs application-specific assertions and a stable case-to-evidence mapping. HTTP evidence redaction remains unqualified.
7. **Fully automated security regression on GitHub Actions** is unqualified. Docker-hosted, noninteractive MCP calls worked locally, so a passive check is plausible for a runner with its own authorized stack. No current-surface proof covers the requested advanced workflow or Actions execution. [ZAP automation options and GitHub Actions](https://www.zaproxy.org/docs/getting-further/automation/automation-options/), [ZAP Docker documentation](https://www.zaproxy.org/docs/docker/)
8. **MCP changes** are needed for missing typed lifecycle or evidence operations such as full context/scope management, configuration readback, passive rule controls, sanitized message export and plan validation/job inspection. Some basic context, user and plan operations already appear behind an expert registration branch in bundled source. Deployment exposure and runtime proof would still be needed.
9. **Mechanisms outside ZAP** are needed for product-owned authorization and business assertions, fixture reset and post-state checks, stable objective/test-ID mapping, and CI orchestration, secrets and artifact handling.

## Official OWASP ZAP references

- R01 [ZAP API Reference](https://www.zaproxy.org/docs/api/)
- R02 [ZAP authentication concepts](https://www.zaproxy.org/docs/getting-further/authentication/concepts/)
- R03 [ZAP session handling](https://www.zaproxy.org/docs/authentication/session-handling/)
- R04 [ZAP Access Control Testing](https://www.zaproxy.org/docs/desktop/addons/access-control-testing/)
- R05 [ZAP Automation Framework CLI and API](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)
- R06 [ZAP automation options and GitHub Actions](https://www.zaproxy.org/docs/getting-further/automation/automation-options/)
- R07 [ZAP exploration guidance](https://www.zaproxy.org/docs/getting-further/automation/exploring-your-app/)
- R08 [ZAP OpenAPI support](https://www.zaproxy.org/docs/desktop/addons/openapi-support/)
- R09 [ZAP passive scanner](https://www.zaproxy.org/docs/desktop/addons/passive-scanner/)
- R10 [ZAP passive rule 10038-1](https://www.zaproxy.org/docs/alerts/10038-1/)
- R11 [ZAP script types](https://www.zaproxy.org/docs/getting-further/scripting/script-types/)
- R12 [ZAP script job](https://www.zaproxy.org/docs/desktop/addons/script-console/automation/)
- R13 [ZAP requestor job](https://www.zaproxy.org/docs/desktop/addons/automation-framework/job-requestor/)
- R14 [ZAP Replacer](https://www.zaproxy.org/docs/desktop/addons/replacer/)
- R15 [ZAP Framework jobs](https://www.zaproxy.org/docs/automate/automation-framework/)
- R16 [ZAP report generation](https://www.zaproxy.org/docs/desktop/addons/report-generation/)
- R17 [ZAP Alert Filters](https://www.zaproxy.org/docs/desktop/addons/alert-filters/)
- R18 [ZAP Docker documentation](https://www.zaproxy.org/docs/docker/)
- R19 [ZAP Client Spider API](https://www.zaproxy.org/docs/desktop/addons/client-side-integration/spider-api/)
- R20 [ZAP authentication methods](https://www.zaproxy.org/docs/desktop/start/features/authmethods/)
