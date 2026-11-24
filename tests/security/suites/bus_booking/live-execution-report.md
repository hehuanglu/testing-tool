# SEC-A01-01 live HTTP execution report

**Verified locally on 24 November 2026.** Bus Booking commit `56f58a3ed86d22d44bd2007e3a49aeb0c979510f` was packaged with its Maven wrapper and run on Java 21 in Docker. PostgreSQL, the packaged application and the selected test client shared a disconnected loopback namespace with zero published ports. Each run used a new database. The application checkout and shared framework code were preserved.

## Authorization and JWT

The MockMvc rerun and two independent live HTTP runs each passed all nine application case groups. The comparison verified identical observed and expected statuses, JSON and database predicates, and identity witnesses for **102 protected authorization cells across 25 operations**, plus 18 authentication and role conditions.

Four test identities obtained JWTs from the actual login endpoint and independently resolved their expected accounts and roles through `GET /api/auth/me`. Login and current-user responses issued no JSESSIONID. Missing, malformed, expired, duplicate and ineligible credentials returned the expected 401 responses. The 50 denied matrix cells preserved persisted state. The real application allowed SUPER_ADMIN to change roles, rejected role changes from ADMIN, and denied administrative access on an already-issued token immediately after demotion. [First live HTTP result](evidence/live/http-first.json) · [Repeated live HTTP result](evidence/live/http-repeat.json) · [MockMvc rerun](evidence/live/mockmvc.json) · [Cross-lane comparison](evidence/live/comparison.json)

## Comparison of the two application lanes

| Surface | In-process Spring | Packaged application over HTTP |
| --- | --- | --- |
| Entry point and clock | MockMvc with Spring test profile and fixed clock | Spring Boot JAR with default profile, HTTP/1.1 and the system clock |
| Authorization evidence | HTTP-shaped response and PostgreSQL state, with MVC handler-selection evidence | Actual servlet transport, on-wire status and JSON, and the same PostgreSQL predicates |
| Authentication evidence | Actual app login and effective identities from MockMvc, with internal session check | Actual app login and effective identities over the loopback socket, with an externally observable JSESSIONID check |
| Pre-controller boundary | Handler-selection witness on all 48 route-level denials | Denial responses and unchanged state. Handler selection is outside the HTTP receipt. |

Both entry points use the original contract matrix and the same fixture and response oracles. The JAR contains the application's production classes. The HTTP test client is a separate process. [Live specification](specifications/live-http.md) · [Traceability and coverage](specifications/coverage.md)

## ZAP proxy and passive evidence

ZAP 2.17.0 forwarded one anonymous `GET /api/locations` through the allowlisted relay. The proxy response matched the direct HTTP 200 response body, and the relay independently witnessed the app request. The proxy used a disposable Safe-mode home with the API disabled. [ZAP proxy command line](https://www.zaproxy.org/docs/desktop/addons/network/cmdline/) · [ZAP Safe mode](https://www.zaproxy.org/docs/desktop/start/features/modes/)

Separate native phase receipts showed zero relay requests during plan validation, then an ordered Requestor, passive drain and report. The report was fresh and uncapped. It projected zero rule instances on the one public Bus Booking route and three on the synthetic HTML control, including the required CSP rule `10038-1`. The report describes this bounded observation through a relay that preserves end-to-end headers and omits cookies and connection framing. The passive PASS means the proxy, collection and detector-control requirements held. Authorization verdicts come from the application lanes. [Sanitized ZAP result](evidence/live/passive.json) · [Native Automation Framework](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)

## Failure handling and qualification boundaries

| Capability or control | Verified result |
| --- | --- |
| Application HTTP matrix and independent effective identities | **PASS (0)** in both isolated runs |
| Anonymous ZAP proxy and passive report | **PASS (0)** in its own isolated run |
| Copied application observation with a wrong state predicate | **FAIL (1)** |
| Missing application cell or missing native report in copied evidence | **ERROR (2)** |
| Requested source revision unavailable | **ERROR (2)** |
| Shared scanner JWT and Active DAST | **BLOCKED (3)** with no dispatch |
| TLS, external ingress, full Compose and SMTP behavior, hosted GitHub Actions | **Untested** |

The first development scanner process stopped before producing evidence and exited 2. The corrected worker passed proxy and passive evidence verification. The copied-observation controls exercised the verdict path without changing application authorization. [Comparison controls](evidence/live/comparison.json) · [Invalid revision](evidence/live/execution-error.json) · [JWT restriction](evidence/live/scanner-jwt-blocked.json) · [Active restriction](evidence/live/scanner-active-blocked.json)

The executable workflows and [local Docker and GitHub Actions instructions](live/README.md) are available in the suite.
