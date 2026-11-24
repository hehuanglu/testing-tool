# Bus Booking security test execution report

**SEC-A01-01 · CWE-862.** Tested on 24 November 2026 using the clean Bus Booking security-CI checkout at `56f58a3ed86d22d44bd2007e3a49aeb0c979510f`. The application ran in Spring MockMvc with Java 21.0.13, Maven Wrapper 3.10.2, and PostgreSQL 16.16 on Docker Engine 29.8.1. Each baseline used a fresh database, exported checkout and run ID.

## Application authorization

Both baselines passed all nine application case groups. Their sanitized evidence and case decisions matched. Each run checked 102 protected matrix cells across all 25 protected API operations, plus 10 authentication conditions and 8 role lifecycle or business checks. Of the 50 denied matrix cells, the 48 route-level denials occurred before MVC selected a handler. The two ownership denials were handled by the booking service. All 50 left persisted fixture rows unchanged.

Both privileged roles passed the six administrative reads and eleven administrative writes. In the role-change case, anonymous received 401, USER and ADMIN received 403, and SUPER_ADMIN successfully promoted the eligible target. Before-and-after PostgreSQL checks confirmed the denied states remained unchanged and the allowed change persisted. An already-issued ADMIN JWT lost administrative access after demotion and continued to resolve the same subject with role USER. [First baseline](evidence/baseline-first.json) · [Repeated baseline](evidence/baseline-repeat.json)

## JWT Bearer qualification

Four locally seeded accounts obtained tokens through the real login endpoint. Independent current-user requests matched the four expected subjects and roles, with no session created. Invalid and ineligible authentication conditions returned the expected 401s. The public locations and restored-account controls returned 200. JWT Bearer is qualified for the in-process application lane on this revision and fixture profile. [Authentication evidence](evidence/baseline-first.json)

## Controlled failures and execution errors

Three controls changed one copied observation at a time: status, persistence or MVC handler selection. Each produced FAIL and exit 1. Missing, malformed, wrong-identity and stale evidence produced ERROR and exit 2. A controlled nonzero subprocess and a timed-out subprocess both produced ERROR. Selecting a nonexistent product revision produced a separate exit 2 bundle with `PROJECT_SOURCE_UNAVAILABLE`. [Repeatability and controlled outcomes](evidence/verification.json) · [Invalid revision outcome](evidence/execution-error.json)

The initial application attempt stopped during Maven dependency resolution because the system Maven differed from the product wrapper. A later draft run returned 409 on both positive vehicle update cells because the fixture used a vehicle already assigned to a trip. The final launcher uses the product wrapper cache, and the vehicle-update case uses an unassigned fixture. The final baselines use the same authorization expectations as the draft.

## Blocked capabilities

The unchanged shared launcher returned BLOCKED and exit 3 for scanner JWT transport and active execution. Both receipts recorded `dispatched: false`. Active DAST and the scanner JWT transport remain blocked. [Scanner JWT receipt](evidence/scanner-jwt-blocked.json) · [Active execution receipt](evidence/scanner-active-blocked.json)

## Coverage and handoff

The project-specific executable suite, local run instructions and CI integration instructions are implemented. Hosted CI, live HTTP transport and the other surfaces listed in the coverage report are untested. The result is scoped to the recorded commit and test profile. [Coverage and requirements traceability](specifications/coverage.md) · [Run and CI instructions](README.md)
