# End-to-end security testing feasibility

**Decision as of 24 November 2026 (ICT)**

Start project-specific suite development using Expert Mode for fixture setup, exploratory checks and evidence inspection, and standalone Automation Framework plus application-owned assertions for CI. **The supported development path requires no MCP implementation changes.** Authenticated Active DAST remains **NO-GO** under the existing execution restriction.

The proof used the supplied [Guided capability report](mcp-zap-capability-report.md), [gap analysis](mcp-zap-gap-analysis.md), [extensibility report](mcp-zap-extensibility-report.md), [deployment provenance](mcp-zap-deployment-provenance.md), [Expert Mode report](mcp-zap-expert-capability-report.md), [Guided versus Expert comparison](mcp-zap-guided-vs-expert.md), and their evidence bundles. It exercised six named workflows with disposable fixtures. It draws runtime conclusions from the published MCP v0.16.0 release identified in the provenance report. The bundled Java checkout and its experimental auth provider were outside the execution path.

## Decisions by methodology

| Methodology | Decision | Qualified scope |
| --- | --- | --- |
| Passive DAST | **GO** | Fixed anonymous GETs with a positive detector control, a healthy subject and an intentional CSP regression. |
| Authenticated passive DAST | **GO** | Native form login and cookie replay with application-side identity witnesses and a protected CSP control. |
| Authenticated API exploration | **CONDITIONAL-GO** | Two verified users and read-only, HTML-linked JSON APIs with declared expected coverage. The result is specific to the discovery mechanism and fixture. |
| Deterministic authorization | **GO** | Application-owned identity, HTTP decisions, response semantics and post-state assertions for named fixture roles. |
| Authenticated Active DAST | **NO-GO** | Execution remains restricted. Prior discovery and policy readback establish tool exposure and configuration only. |
| Standalone Automation Framework CI | **GO** | Pinned local Docker qualification with native preflight, bounded execution and a fail-closed repository-owned gate. Hosted runner qualification remains open. |

## 1. Passive DAST with positive and negative controls

**Requirements and development path.** ZAP's CSP detector, Automation Framework Requestor and passive drain jobs, JSON Reports and an exact fixture witness. A fresh Expert instance ran the bounded passive subset and listed its report. The prior runtime audit also repeated both controls at a fresh site. The reusable local plan and fixture run without MCP. [Expert evidence F01–F03, F05 and X02](mcp-zap-expert-capability-evidence.json) · [ZAP rule 10038-1](https://www.zaproxy.org/docs/alerts/10038-1/)

**Expected and observed.** Both anonymous pages returned 200. The detector-positive `/public/control` omitted CSP and produced `10038-1`. The healthy `/public/subject` supplied CSP and produced no matching finding. Removing CSP from the subject produced the scoped finding and `FAIL / CSP_REGRESSION` with native exit 0. Both results retained exact method, application status, actor, header-presence witness and report rule instances.

## 2. Authenticated passive DAST

**Requirements and development path.** Form authentication, cookie session handling, dedicated users, protected pages, a passive detector and independent target-side identity evidence. Expert's native user/context operations and the fixture witnesses from its prior authenticated Spider audit support development. In the new Expert development run, Requestor established reader and editor sessions, reached the protected pages as reader, and produced both CSP controls. The standalone plan repeats those protected requests and verifies guest rejection and both identities. [Expert evidence A01–A06 and X01](mcp-zap-expert-capability-evidence.json) · [ZAP environment configuration](https://www.zaproxy.org/docs/desktop/addons/automation-framework/environment/)

**Expected and observed.** The reader's exact protected GETs returned 200 under the reader identity, the editor identity returned editor, and the guest probe returned 401. Only `/private/control` triggered `10038-1` in the baseline protected pair. Removing CSP from `/private/subject` gave `FAIL / CSP_REGRESSION` while the scanner exited 0. Wrong reader credentials returned 401 and gave `ERROR / AUTHENTICATION_FAILURE`. A login indicator was corroborated by the fixture's authenticated response witnesses.

## 3. Authenticated API exploration using multiple identities

**Requirements and development path.** The Traditional Spider, one bounded exploration context per actor, form login and cookie replay, actor-specific entry points and an expected route manifest. Expert previously demonstrated `zap_spider_as_user` with both users and independent role witnesses. The new Expert run used the same fixture with actor-specific native contexts. Both direct Spiders completed at 100%, and the fixture saw each actor fetch their linked profile API. The standalone plan assigns each actor their own start URL and scope. [Expert evidence A06 and X01](mcp-zap-expert-capability-evidence.json) · [ZAP Spider Automation Framework](https://www.zaproxy.org/docs/desktop/addons/spider/automation/)

**Expected and observed.** Reader and editor each reached their linked `/explore/<actor>/profile` JSON endpoint with HTTP 200 and the matching application-side subject. The coverage control hid the editor link while the editor remained authenticated and the job completed. The gate returned `FAIL / API_LINK_MISSING` with native exit 0. A declared link without a corresponding observed visit is an incomplete execution. Evidence is the exact actor, route, status and emitted link set, backed by ordered job receipts. Schema import with per-user traffic, browser discovery and token renewal remain unqualified here.

## 4. Deterministic authorization with application-owned assertions

**Requirements and development path.** Known role policy, isolated application state, independent cookie jars and a before/after state oracle. Expert helps confirm identities and observe role-specific traffic. The application test owns the decision, response and state checks, and runs as ordinary fixture requests outside scanner transport. [Expert evidence A06 and X01](mcp-zap-expert-capability-evidence.json) · [Application assertions](tests/security/feasibility/app_assertions.py)

**Expected and observed.** The anonymous write returned 401 and the reader write returned 403, both retaining revision 0. The editor write returned 200 with an allowed response and changed revision to 1. The regression fixture incorrectly denied the editor and left revision 0, producing `FAIL / AUTHORIZATION_ASSERTION_VIOLATED` even though the scanner exited 0. The evidence records each returned actor, decision, status and post-state against the versioned expected matrix.

## 5. Authenticated Active DAST

**Exact cause of the previous BLOCKED verdict.** Expert experiment **B01** records that the audit's execution restrictions excluded active DAST. The extensibility report identifies that restriction as the prior AI execution boundary. The older Guided run also lacked a bound authentication profile, a dependency the Expert run addressed for passive transport. Discovery **D01** exposed user-specific active tools and **P01–P04** proved policy inspection and a rule-state change. The audit never submitted an active request. The retained record therefore establishes an execution boundary, with no observed dispatch error, auth failure or rule outcome. No active test was submitted through MCP, standalone Automation Framework, or the repository's experimental active runner during this validation. [Expert evidence B01, D01 and P01–P04](mcp-zap-expert-capability-evidence.json) · [Extensibility report, section 3](mcp-zap-extensibility-report.md#3-authenticated-active-dast-and-execution-restrictions)

**Requirements, expected evidence and result.** Qualification would require a permitted execution route, a bounded active policy and fixture, proof of the effective actor during the active run, independent completion and a valid detection/control oracle. The prior authenticated Spider only establishes identity on that transport. The status artifact returned `BLOCKED / ACTIVE_EXECUTION_RESTRICTED` on both clean invocations and retained `dispatched: false`. Active security behavior and detection repeatability remain unmeasured.

## 6. Standalone Automation Framework and CI verdicts

**Requirements and development path.** Python 3, Docker, the pinned ZAP image, Automation Framework, Requestor, form and Spider support, passive rules, and Reports. The released Expert API has useful plan and artifact tooling. Its finished plan status was `Successful: unknown` in both the prior audit and the new passive subset run. The new run reported zero warnings and errors, and its report was read from the isolated shared workspace. The full standalone plan also uses regex-scoped contexts. The released Expert plan policy rejected its nonempty `env.contexts[0].includePaths` at submission. The standalone runner uses ZAP CLI `-autocheck` and `-autorun` in separate fresh scanner homes. [Expert evidence F01–F06](mcp-zap-expert-capability-evidence.json) · [ZAP Automation Framework CLI](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)

**Expected and observed.** A passing native process needed job receipts, fixture-side role and traffic evidence, a fresh scoped report with the positive controls, and satisfied application assertions. Four intentional objective regressions exited 1 even with native exit 0. An invalid plan, forced scanner termination, wrong credentials, a native warning, an omitted required request, a missing report and a malformed report each exited 2 with their corresponding reason. Two supplemental invocations without a Docker command also exited 2 with `INFRASTRUCTURE_FAILURE`. The active status case exited 3. Each scenario ran twice in a fresh container with networking disabled. Verdicts matched between runs, and the normalized security witnesses matched for the native-exit-0 scenarios. The two full rounds give 26 scenario results. Docker Engine 29.8.1 on Linux ARM64 supplied the execution environment. The separate Expert check used a fixture-only host allowlist, an internal Docker network with no published ports, and a newly provisioned shared workspace. Hosted CI, other image architectures and add-on upgrades were outside this qualification. [CI verdict contract](ci-verdict-contract.md)

## Implementation decision

The tested architecture gives the repository control over plans, fixture and identity setup, test data, application assertions and CI exit codes. Expert can continue to support development within its plan and tooling limits. The full plan's MCP validation rejection does not block the standalone execution path. An MCP-only requirement would reopen questions about plan validation and cancellation, context/user cleanup, and typed per-job verdicts and redacted HTTP evidence. The active execution restriction is independent of those interface gaps.

[Reusable local proof of concept](tests/security/feasibility/README.md) · [Machine-readable evidence](security-testing-feasibility-evidence.json)
