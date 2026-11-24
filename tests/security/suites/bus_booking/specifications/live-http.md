# Live HTTP security test specification

## Objective and traceability

**SEC-A01-01 · CWE-862 — Missing Authorization.** Protected operations require authentication and the role authorized by the API contract. ADMIN and SUPER_ADMIN may use administrative resources. Changing an account role requires SUPER_ADMIN.

The live suite uses the same nine application case groups, [authorization matrix](../plans/authorization-matrix.txt) and [case registry](../cases/cases.json) as the qualified [in-process suite](sec-a01-01.md). The matrix defines 102 protected cells across 25 operations. Its role and status expectations come from the original contract analysis. The runner reconciles method-and-path inventory with the committed OpenAPI before starting the application. The [updated requirements traceability](coverage.md) identifies the evidence for each lane.

## Test design

- **Target.** Package the committed Bus Booking revision with its own Maven wrapper. Run the resulting production Spring Boot JAR on the Java 21 runtime used by the product Dockerfile. PostgreSQL starts in a fresh Docker `none` network namespace. The application and its test client join that same stack and communicate on loopback. There are zero published ports. Dependency resolution and image pulls belong to setup. [Docker container networking](https://docs.docker.com/engine/network/#container-networks)
- **Application contract.** The [shared Java fixture and assertions](../fixtures/BusBookingAuthorizationPilotTest.java) provide seed state, fixed request bodies and PostgreSQL readback. The [live client](../live/BusBookingLiveHttp.java) sends HTTP/1.1 to the packaged application. The fixture selects dates relative to the Vietnam calendar in this lane so scheduled trips are open for booking when the application uses its normal clock.
- **Identity.** Four preverified, independently seeded fixture accounts obtain access tokens through the real `POST /api/auth/login`. Each token must resolve the matching account ID and persisted role through `GET /api/auth/me`, with no `JSESSIONID` issued. The fixture includes an eligible role target, a pending account, a known expired token signed with the disposable fixture key, and the original missing, malformed, duplicate-header, invalid-public-Bearer, ineligible-account and wrong-password controls.
- **Expected result.** Test each applicable actor using the same matrix requests and status codes. Denials must have the expected JSON fields and unchanged persisted state. Successful reads must identify the fixture resource or principal. Successful writes must persist the intended change. The lifecycle case also checks that the same issued ADMIN token loses admin access immediately after the role change while the account ID remains the same. MVC handler selection remains an in-process evidence field.
- **Optional ZAP evidence lane.** A separate fresh application instance exposes one reviewed anonymous GET via a loopback relay. A local client uses the ZAP proxy with Safe mode and the API disabled. Compare its HTTP response to a direct request and require one upstream witness. In a separate session, the shared native runner validates and executes a two-request plan, drains passive work and creates a scoped JSON report. The second request is a synthetic HTML control and must produce CSP rule `10038-1`. The relay forwards only `GET /api/locations` to the app and serves the synthetic control itself. [ZAP modes](https://www.zaproxy.org/docs/desktop/start/features/modes/) · [ZAP proxy controls](https://www.zaproxy.org/docs/desktop/addons/network/cmdline/) · [ZAP Automation Framework](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)
- **Isolation and cleanup.** All application test credentials and signing material are generated per invocation. The ZAP worker receives no authentication fixture. Docker containers, PostgreSQL tmpfs, raw application and scanner output, and temporary build and ZAP homes are disposable. The launcher bounds package build, application readiness, client process, native scanner phases, and container cleanup.

## Test cases

| Case IDs | Live evidence and expectations |
| --- | --- |
| BB-AUTH | Login and independent current-user proof over HTTP. Preserve the ten authentication conditions and their expected response and state. |
| BB-PROFILE, BB-USER, BB-BOOKING | Preserve the original actor, method, route, status, response and persistence expectations, including the second user's booking denial. |
| BB-ADMIN-READ, BB-ADMIN-WRITE | Preserve all six administrative reads and eleven writes with all four matrix actors. |
| BB-ROLE, BB-ROLE-LIFECYCLE, BB-ROLE-RULES | Preserve positive role change, denial and unchanged state, replay after demotion, sole role invariant and pending-account boundary. |
| BB-LIVE-PASSIVE | Anonymous proxy observation, ready product witness, zero relay requests during native validation, ordered completed passive plan, fresh scoped report and synthetic detector control. Auxiliary evidence for the pilot; the authorization verdict comes from the application lane. |
| BB-SCANNER-JWT, BB-ACTIVE | Existing capability receipts yield BLOCKED and record no dispatch. These are separate scenarios. |

## Execution, evidence and verdict

The [suite launcher](../live/run.py) publishes allowlisted `result.json` and `report.md`. Application evidence keys are `provenance`, `jwtAcquisition`, `jwtIdentity`, and the case ID. Provenance records the product commit, build and container inputs, and loopback transport. Case evidence contains expected and observed statuses, response and state predicates, operation IDs and actor aliases. Live evidence contains no MVC handler claims. The passive lane has `proxyWitness`, `scannerEvents`, `scannerExecution` and `zapReport`. Its projected report retains the scanner version, digest, rule IDs and transient report pointers. The case evidence omits request payloads, credentials, database rows and raw scanner sessions.

**PASS (0)** requires evidence-backed expectations for the selected lane. **FAIL (1)** is an authorization assertion contradicted by complete usable evidence. **ERROR (2)** includes incomplete observations, failed identity, process or teardown, invalid evidence, or missing required native scan and detector evidence. **BLOCKED (3)** records a prohibited shared capability with no dispatch. See [local and CI execution](../live/README.md) and the [comparison report](../live-execution-report.md).
