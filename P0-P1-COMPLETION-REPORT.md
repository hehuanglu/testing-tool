# Security testing framework P0 and P1 completion

24 November 2026, ICT

## Closure summary

- **Engineering completion.** The bounded native JWT and passive scanner integration and the Active DAST admission contract are committed. The product suite adds a PostgreSQL rollback test to the existing OTP integration tests. The Bus Booking production source, build and deployment files match the prior revision.
- **Local runtime qualification.** **VERIFIED** for the requested permitted lanes. Native JWT, scanner identity, passive processing and the paired HTTP comparison passed. The wrong-password control and all 16 synthetic scenarios matched their expected outcomes. Bus Booking's final full and long runs passed. Fixture teardown is verified.
- **Bus Booking security acceptance.** **MISSING**. The matrix has 18 PASS, eight REVIEW and two MISSING. Open release gates also include a compatible approved passive baseline, 12 reviewed API contract discrepancies and authenticated Active DAST qualification. [Product acceptance review](/Users/hahoangloc/Working/UET/bus-booking-security-ci/docs/security-acceptance-p0-p1.md)
- **Authenticated Active DAST.** **BLOCKED** at shared admission and **MISSING** as a product capability and qualification claim. The local proof is the no-dispatch receipt. [Execution contract](ci-verdict-contract.md#authenticated-active-dast)

## Final committed revisions

| Repository | Qualified input |
| --- | --- |
| Shared framework, `codex/security-framework-p0-p1` | `cc1d753ba3d57fb00b8535a7c26b7bc375d7b803`. Suite tree at the verification input `becd9313ed7d4881d6cdadf49efedd7e59b5a972` and workflow blob `4bd52ec7d2dedb7a007718ea8a6acf289c63a4f1`. The integration landed in `0117bc0defc891d3eb4644c53635e7e547daa5ca`. The final input commit repairs Docker API failure classification. The report and evidence supplement that source pin. |
| Bus Booking, `codex/bus-booking-security-p0-p1` | `b8de73f2cd35461fdce7564b1f0ce0a539fbaa24`. Production tree `922135afab8cc622ee47092350192ab465b4b347`, identical to `ca45f3a90c453b2db3818c1389e13c4ff788db1e`. The final commit changes the OTP integration test and suite traceability. The earlier `9059a1b0942191a8b23ebdc98873dc36213ffd49` production fix already checks affected rows. |

The evidence index binds receipts to source revisions, file and plan SHA-256 digests, the application JAR, runtime versions, and immutable image identities where applicable. Each lane retains its own observed verdict and shell exit. The scanner receipts retain phase, status and identity predicates. Credentials, JWT values, raw scanner reports and HAR traffic were transient. [Final evidence index](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

The shared live launcher builds a Git export and places the application, Mailpit and ZAP on the database container's disconnected loopback namespace with zero published ports. The product-native runner uses its own loopback fixture to capture HTTP and sends the archive to a disconnected ZAP container for passive analysis. [Shared live lane](tests/security/suites/bus_booking/specifications/native-jwt-passive.md) · [Product HAR plan](/Users/hahoangloc/Working/UET/bus-booking-security-ci/tests/security/zap.yaml)

Historical comparisons remain tied to their original inputs. The committed baseline is `a5401a16568bc852e53dd7eaaf92e96a0fcf1041`. The first measured native integration is `546cce391d08a67b0a88f1fbde34c7fd60352d66` with product `56f58a3ed86d22d44bd2007e3a49aeb0c979510f`. Hosted PR #20 measured product head `56f58a3` and merge snapshot `ff5c9e606697ea87a387f60403ef5408fb5bdcb8`. Hosted execution for the final revisions remains unmeasured. [Previous verification index](tests/security/suites/bus_booking/evidence/p0-p1/verification.json) · [Hosted artifact](https://github.com/maaL6/bus-booking-system-phase-2/actions/runs/45236299340/artifacts/14848308972)

## Final-revision runtime and regression results

### Native JWT authentication

**PASS, exit 0.** ZAP performed native JSON login after the disposable USER was registered and email-verified. The backend returned 200 and issued the Bearer token. The independent anonymous control returned 401 and a Bearer challenge. [Positive receipt](tests/security/suites/bus_booking/evidence/p0-p1/final-native-jwt.json)

### Wrong-password negative control

**Expected ERROR, exit 2, `AUTHENTICATION_FAILURE`.** The backend rejected both login attempts with 401. Every poll and named request returned 401 and failed the issued-token and principal checks. The receipt contains no accepted identity or passive report and records completed teardown. [Wrong-password receipt](tests/security/suites/bus_booking/evidence/p0-p1/final-native-jwt-bad-password.json)

### Scanner identity

**PASS.** The poll and named Requestor both received 200. The backend response matched the fixture account ID, email, verified state and USER role. The relay correlated the Bearer token on both requests with the token issued by the backend during native login. The measured scope was one USER and `GET /api/auth/me`. [Backend identity witnesses](tests/security/suites/bus_booking/evidence/p0-p1/final-native-jwt.json)

### Authenticated passive processing

**PASS.** Native plan preflight exited 0 with zero traffic. Both Requestor jobs finished, followed by the passive wait and report jobs. The scoped report recorded positive detector `10038-1` on the synthetic HTML and rules `10111` and `10112` on the login operation. The verified profile emitted no report row in this run. [Passive execution and report receipt](tests/security/suites/bus_booking/evidence/p0-p1/final-native-jwt.json)

### Paired HTTP pilot

**PASS.** Both packaged HTTP runs and the MockMvc run matched for 102 authorization cells across 25 operations and 18 authentication and role conditions. Response, persisted state and identity observations matched. MockMvc supplied the handler witness. The independent anonymous proxy/passive lane passed its product read and detector control. The comparator rejected a missing HTTP cell, a state mismatch and a missing ZAP report with their expected classifications. [Four-run comparison](tests/security/suites/bus_booking/evidence/p0-p1/final-http-comparison.json) · [Lane receipt hashes and provenance](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

### Synthetic regression scenarios

**16/16 matched** on the final framework revision. The earlier post-change attempt matched 8/16. The fresh receipts match verdicts, reason codes and native exits where applicable. The Docker-unavailable control pointed only the test client at an absent socket. Docker Desktop exited 1 before starting a worker. The initial runner classified that as `MISSING_EVIDENCE`. The final runner classifies the connection failure as `INFRASTRUCTURE_FAILURE` and preserves the missing-evidence assertion for worker exits without a receipt. [Scenario receipts and expectations](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

- Baseline, baseline repeat, application-only and anonymous-only passed with exit 0.
- Public and private CSP and the authorization regression each returned the expected FAIL with exit 1.
- Bad password, scanner warning, invalid plan, incomplete execution, missing report, invalid report and Docker unavailable each returned the expected ERROR with exit 2.
- Active DAST and generic JWT admission controls returned the expected BLOCKED with exit 3 and recorded zero dispatch.

### Bus Booking suite

**Full and long execution PASS, release acceptance MISSING.** The clean full run passed 324 Maven tests, 100/100 HTTP situations on 32/32 operations, 12/12 ownership situations and 133/133 reconciled offline HAR exchanges. The clean long run passed 324 Maven tests, 101/101 HTTP situations and 179/179 reconciled HAR exchanges. It covered the 12 seat race invariants, JWT expiry and fresh-login control, quota recovery, and OTP expiry and retry. The new PostgreSQL rollback test passed in both modes. The framework Python suite passed 47 tests. The product Python suite passed 11 tests, and manifest validation found 28 criteria, 32 operations and seven exclusions. [Product and offline evidence](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

### Container and temporary-resource teardown

**PASS.** Final pilot labels and synthetic worker names were absent in Docker after the runs. Both product runs reported container, process and temporary-file cleanup, and independent Docker readback confirmed the two product database volumes were absent. The host temporary parents and the isolated product verification checkout were removed. [Final teardown evidence](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

The earlier interrupted runs had six exited Bus Booking containers. The retained run manifests, exact container names, pinned images and mount inspection identified three Mailpit containers and three PostgreSQL containers. The PostgreSQL mounts were anonymous and attached to their corresponding fixture alone. Exact-name removal and readback confirmed absence of the six containers and the three volumes. The host's prior fixture-temp prefixes were also absent. Docker recovered before this pass began. [Final teardown evidence](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

## Bus Booking security acceptance

The matrix preserves the product's existing release criteria. PASS is scoped to the mapped witnesses. REVIEW requires a recorded technical or product decision. MISSING identifies an unresolved required evidence dependency. The product-native gate evaluates both coverage and release acceptance. [Scope and assertions](/Users/hahoangloc/Working/UET/bus-booking-security-ci/tests/security/scope.json) · [Product acceptance rules](/Users/hahoangloc/Working/UET/bus-booking-security-ci/docs/security-acceptance-p0-p1.md) · [Review gates](/Users/hahoangloc/Working/UET/bus-booking-security-ci/tests/security/assessment.py)

| Objective | CWE | Status | Evidence and remaining work |
| --- | --- | --- | --- |
| SEC-A01-01 | CWE-862 | PASS | MockMvc exercises the actual security chain. The HTTP matrix checks anonymous rejection, USER/ADMIN/SUPER_ADMIN decisions and persisted role changes. Reuse of a prior token after demotion proves that authorization uses the effective backend role. |
| SEC-A01-02 | CWE-639 | PASS | Independent owner and second USER cover detail, history and cancel. Both admin roles supply the permitted controls. The booking suite checks owner isolation and restored seats in persisted state. |
| SEC-A01-07 | CWE-276 | PASS | Registration defaults to USER and rejects privilege fields. Lower-privileged role changes and an unlisted method are denied. |
| SEC-A02-04 | CWE-260 | PASS | The checked production and development password properties resolve through environment variables. The test profile contains a fixture default. This source acceptance covers the repository configuration. |
| SEC-A02-05 | CWE-547 | REVIEW | **Missing product policy and deployment evidence.** JWT and OTP keys resolve through environment configuration, and invalid rate limits are rejected. OTP lifetime (10 minutes), resend cooldown (60 seconds), maximum failed attempts (5), and BCrypt cost (10) are fixed in source. **Bus Booking** must approve the effective release values, document the allowed overrides and secret source, and confirm the test profile is excluded. **Framework** must record that disposition against the effective release configuration. |
| SEC-A03-01 | CWE-1329 | PASS | Maven-managed or explicit dependency versions and Docker image references can be replaced. The requirement evaluates updateability of the in-scope software components. |
| SEC-A04-05 | CWE-759 | PASS | The unit and runtime checks validate randomized BCrypt salts for equal passwords and successful hash verification. |
| SEC-A04-06 | CWE-916 | PASS | Runtime BCrypt hashes meet the work factor specified in the suite. The reviewed condition is the algorithm and cost configured for this application. |
| SEC-A05-01 | CWE-89 | REVIEW | **Missing recorded review evidence.** The final-source trace below covers all 32 operations, and the quoted-name and optional-filter controls cover the declared runtime witnesses. The release gate still requires a disposition for `parameter-binding-review`. **Framework** must reconcile the trace against the effective data-access implementation and record the decision. **Bus Booking** must identify any release-only data-access extension and confirm intended matching semantics for vehicle filters. |
| SEC-A05-04 | CWE-93 | PASS | Registration and resend reject CR/LF-containing recipient input. Mailpit records no delivery from these cases and verified registration supplies the successful control. |
| SEC-A06-01 | CWE-598 | PASS | Auth capture traces login and email verification fields in JSON and JWT in the Bearer header. The contract check finds no credential query parameter, and offline HAR reconciles the captured requests. |
| SEC-A06-03 | CWE-525 | MISSING | **Missing frontend dependency, browser test implementation and evidence.** Backend login, profile and booking cases supply `no-store` evidence. **Bus Booking** must supply the pinned frontend, reproducible start command and fixture access. **Framework** must drive the sensitive views in that build and capture cache, Back navigation and post-logout revisit behavior with a successful navigation control. |
| SEC-A06-05 | CWE-602 | MISSING | **Missing frontend dependency, browser test implementation and evidence.** Backend coverage exercises authorization, trip state, capacity, pricing and persisted state. **Bus Booking** must supply the pinned frontend and a reproducible bookable and ineligible-trip fixture. **Framework** must drive the paired real booking journeys and correlate UI result, backend decision and resulting booking/seat state. |
| SEC-A07-01 | CWE-613 | PASS | The product tests cover invalid Bearer input, valid identity and exact JWT expiry at the service boundary. Application-client expiry coverage is independent of scanner session expiry. |
| SEC-A07-03 | CWE-307 | PASS | Live login throttling and OTP single-use run with accepted-credential controls. Unit and HTTP regressions cover quota boundary, concurrency, reset, and forwarded-header handling. |
| SEC-A07-05 | CWE-259 | PASS | The bootstrap path uses an external password and explicit opt-in. Disabled bootstrap needs no credential. The backend fixture tests successful bootstrap and failed password verification. |
| SEC-A08-02 | CWE-427 | REVIEW | **Missing release artifact and deployment evidence.** The committed entrypoint resolves `java` through PATH, and the supplied Dockerfile and Compose file inherit the base image user and PATH. The pinned local Temurin base resolves it to `/opt/java/openjdk/bin/java`. The default UID is 0, and every PATH directory reported writable under that UID. **Bus Booking** must provide the deployed image digest, effective user, PATH, mounts and filesystem/security settings and decide whether the observed ownership is acceptable. **Framework** must confirm ordered resolution and directory writability in that specific deployment. The result establishes the pinned base-image defaults. [PATH probe](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json) |
| SEC-A08-03 | CWE-502 | REVIEW | **Missing release mapper and signing-key evidence.** Existing controls exercise incorrect DTO types, unexpected fields, HS256 enforcement, wrong issuer/key and malformed claims. The committed source review found no global polymorphic-typing declaration. **Bus Booking** must provide the effective mapper modules/configuration and key ownership, issuance and rotation policy. **Framework** must verify the deployment configuration and repeat the approved DTO/JWT controls there. |
| SEC-A08-05 | CWE-915 | PASS | Profile and role APIs reject unexpected or privileged fields. DB checks confirm rejected mutations leave state intact and allowed updates touch the intended fields. |
| SEC-A09-01 | CWE-117 | REVIEW | **Missing sink dependency, sink-specific test implementation and evidence.** The fixture exercised the CR/LF cases and checked its application log for a forged record. The observed application log and source inventory leave connector, access, exception and downstream sink framing open. **Bus Booking** must identify each enabled sink and relevant request field. **Framework** must establish marker reachability, then verify that each sink preserves one correctly framed record with a benign control. |
| SEC-A09-02 | CWE-532 | REVIEW | **Missing deployment evidence and sink coverage.** The fixture marker scan and redaction tests cover the exercised application paths. **Bus Booking** must provide effective log levels, exception/connector outputs, and the ingestion and retention configuration. **Framework** must verify each configured sink against correlated synthetic credentials, JWTs, OTPs and PII on the relevant success and failure paths. |
| SEC-A09-03 | CWE-778 | REVIEW | **Observed fixture evidence gap and possible product defect.** The fixture exercised all four events. Its captured application log contains no matching named login, access-denied, rate-limited or role-changed records. **Bus Booking** must identify the event producer and sink, or implement those events if the release has no producer. **Framework** must verify sanitized records against each corresponding action and actor in the effective sink. |
| SEC-A10-01 | CWE-252 | REVIEW | **Missing final write/lock review evidence.** The seven row-count controls cover booking status, role update and OTP create, update, consume, failure count and replacement. The final PostgreSQL test adds rollback and retry evidence for a zero-row challenge delete after the account update. **Framework** must record the remaining `unchecked-update-review` disposition against role, OTP, booking and seat writes and their lock/transaction boundaries. **Bus Booking** must identify any deployment-specific writers or transaction differences before release acceptance. |
| SEC-A10-02 | CWE-478 | PASS | Error dispatch, quota mapping and unlisted methods have exercised defaults. Missing and invalid original status return the generic server response. |
| SEC-A10-03 | CWE-484 | PASS | Scoped dispatch uses arrow switch rules. Error routing, unknown methods and invalid fields exercise separate branches with their expected outcomes. |
| SEC-A10-04 | CWE-460 | PASS | The JWT filter clears its security context after a downstream exception. Integration controls verify rollback of seat reservations and an already flushed trip update. |
| SEC-A10-05 | CWE-215 | PASS | Production and development debug settings and redacted representations are checked. Runtime canaries locate no monitored fixture secrets in logs. |
| SEC-A10-06 | CWE-550 | PASS | MockMvc exercises infrastructure exceptions with generic output. The HTTP suite tests scoped conflict and validation errors, and production configuration excludes exception details. |

### SQL binding trace

The trace covers the 32 method/path pairs in the final manifest. In the inspected source, JDBC operations use fixed statements with positional values. Spring Data uses typed entity operations or fixed JPQL/SQL with named bindings. Pagination uses typed page number and size plus fixed repository ordering. [Controllers](/Users/hahoangloc/Working/UET/bus-booking-security-ci/src/main/java/com/example/busbooking/api/controller) · [Repositories](/Users/hahoangloc/Working/UET/bus-booking-security-ci/src/main/java/com/example/busbooking/data/repository) · [Adapters](/Users/hahoangloc/Working/UET/bus-booking-security-ci/src/main/java/com/example/busbooking/data/adapter)

| Scoped operations | Controller input to persistence |
| --- | --- |
| `POST /api/auth/{register,login,verify-email,resend-verification}`, `GET /api/auth/me` | Canonical email goes to declared user lookups or the fixed OTP JDBC account lock. OTP writes bind numeric ID, digest and timestamps. JWT subject is converted to a typed user ID. Other auth fields flow to hashing, verification and mapped writes. |
| `GET/PUT /api/users/me`, `PUT /api/admin/users/{userId}/role` | The resolved subject and role target are typed IDs. Profile JPQL binds name, phone, ID and active status. Role JDBC binds actor and target IDs, enum-derived role name and resolved role ID. |
| `POST /api/bookings`, `GET/DELETE /api/bookings/{bookingId}`, `GET /api/users/me/bookings` | Booking form values map to typed domain fields and saved entities. Booking and trip locks, seat delta, status and ownership/history reads use typed, bound IDs and values. History ordering is fixed. |
| `GET /api/admin/bookings` | Optional user ID, trip ID and enum status become bound predicates and skip flags in fixed content and count queries. `page` and `size` feed `PageRequest`. |
| `GET /api/locations`, `GET/POST /api/admin/locations`, `PUT /api/admin/locations/{locationId}` | Bound search text feeds fixed `position()` expressions over name, province and address. Bound text and a typed excluded ID serve duplicate checks. Mapped fields flow through entity persistence. |
| `GET/POST /api/admin/operators`, `PUT /api/admin/operators/{operatorId}` | Operator search uses bound query and status in fixed SQL. Duplicate/reference checks and write locks bind typed IDs and normalized form fields. Writes use mapped entities. |
| `GET/POST /api/admin/vehicles`, `PUT /api/admin/vehicles/{vehicleId}` | Fixed JPQL binds text into the `LIKE` value, with optional typed operator ID and enum status. Input wildcards can affect text matching within that bound value. Reference and update paths bind typed IDs and persist mapped entities. |
| `GET/POST /api/admin/routes`, `PUT /api/admin/routes/{routeId}` | Fixed list predicates bind nullable origin/destination IDs and enum status. Reference lookup, duplicate and active-trip checks use typed IDs in fixed queries. Writes map the body to the entity. |
| `GET /api/trips`, `GET /api/trips/{tripId}` | Fixed list/count queries bind optional origin/destination IDs, temporal bounds, skip flags and a departure cutoff. Detail binds the typed trip ID. Pagination enters `PageRequest`. |
| `GET/POST /api/admin/trips`, `PUT/DELETE /api/admin/trips/{tripId}` | Fixed list/count queries bind optional route, status and date bounds. Create/update/cancel resolve route, vehicle and trip using typed IDs. Writes use mapped fields and fixed locking/status/seat operations. |

### Transaction review for SEC-A10-01

- Role updates lock actor and target accounts, recheck eligibility and require one affected row for an actual role change. The existing PostgreSQL integration and HTTP tests cover the role recheck and effective-role transition.
- OTP operations lock the account before reading the challenge. The existing integration tests cover concurrent verification, resend and registration rollback. The new PostgreSQL test makes the second write affect zero rows, checks that the first write rolled back and that the challenge survives, then removes the fixture and verifies a normal retry.
- Booking creation and cancellation run in transactions. Cancellation checks booking ownership/status under a write lock, locks the trip before restoring seats and requires one booking status update. Seat updates guard against underflow and require one affected row. Existing PostgreSQL tests verify rollback after a seat reservation and the final long run exercises the concurrent seat invariants.

[Role and OTP persistence](/Users/hahoangloc/Working/UET/bus-booking-security-ci/src/main/java/com/example/busbooking/data/adapter) · [Booking transaction](/Users/hahoangloc/Working/UET/bus-booking-security-ci/src/main/java/com/example/busbooking/business/service/BookingService.java) · [OTP integration tests](/Users/hahoangloc/Working/UET/bus-booking-security-ci/src/test/java/com/example/busbooking/integration/AuthServiceIntegrationTest.java)

### Release baseline and API contracts

Two informational login observations are retained as expected behavior. Rule 10111 identifies the login operation. Rule 10112 identifies issuance of the Bearer session token. Count and confidence remain part of baseline review. The older reviewed ARM64 baseline's OpenAPI digest is `fbea8ee16547777a7e190ae2386401404cdda7df50f450216cb2aaf2d9119ffa`. The final full runtime reports `adb60fb6effef029039fa039bae32f902330b8a380516d532cf145f4c40dfb72`. The existing comparator also found a changed suite manifest digest and returned `MISSING / baseline_incompatible`. The final full receipt supplies a candidate for Bus Booking to approve by operation, rule, count and confidence. [Product baseline and dispositions](/Users/hahoangloc/Working/UET/bus-booking-security-ci/docs/security-acceptance-p0-p1.md)

All 12 API contract observations remain REVIEW. Bus Booking API owners must reconcile checked-in design/OpenAPI and runtime behavior, or record an explicit decision for each recognized difference. The framework must revalidate the revised contract. [Operation-by-operation dispositions](/Users/hahoangloc/Working/UET/bus-booking-security-ci/docs/security-acceptance-p0-p1.md#api-contract-drift)

## Authenticated Active DAST

| Dimension | Status | Evidence and remaining work |
| --- | --- | --- |
| Implementation | **MISSING** | The shared framework has a case method, schema, admission rule and CI assertion. The passive engine admits fixed Requestor, passive wait and report jobs. Bus Booking's product workflow imports HAR in an offline scanner and has no active adapter. |
| Integration readiness | **PARTIAL** | The isolated product fixture, approved single-USER native passive profile, passive reporting and cleanup are measured. Integration still requires a reviewed active method and a product-specific scope, identity, lifecycle and results contract. The active component's own session handling is unmeasured. |
| Execution restriction | **BLOCKED** | Existing admission returned exit 3 and a single case-bound receipt with `dispatched: false` for the product and synthetic selections. The execution restriction remains in force. |
| Qualification evidence | **MISSING** | Qualification requires an authorized run, exact source/image/configuration and scope, active-component backend identity, dispatch/readback, terminal results and verified teardown. Scanner-owned expiry, re-login and additional roles also require separate evidence where in scope. |

[Active execution contract](ci-verdict-contract.md#authenticated-active-dast) · [Local no-dispatch evidence](tests/security/suites/bus_booking/evidence/p0-p1/final-runtime.json)

## P0/P1 Definition of Done

### Engineering completion

- [x] Commit and bind the bounded native JWT and passive scanner implementation.
- [x] Verify offline result, authentication, scope and Active DAST admission contracts. Preserve separate infrastructure and missing-evidence classifications.
- [x] Review the 28 product objectives, all 12 API drift records and the two informational login findings.
- [x] Implement the additional OTP row-count controls and the PostgreSQL rollback regression in the existing suite.

### Runtime qualification

- [x] Verify native JWT, wrong-password rejection, backend identity and authenticated passive processing on final inputs.
- [x] Complete two packaged HTTP runs, MockMvc and anonymous passive processing, and reconcile the four receipts.
- [x] Check all 16 synthetic scenarios against their existing exit and reason expectations, including teardown.
- [x] Verify final fixture teardown and reconcile the interrupted Docker runs.
- [x] Verify the new PostgreSQL regression and final product-native suite locally.
- [ ] Obtain hosted workflow evidence for these final revisions.

### Product security acceptance

- [ ] Resolve eight REVIEW and two MISSING objectives using the evidence and ownership described above.
- [ ] Approve a compatible passive baseline and close the 12 API contract dispositions.
- [x] Reconfirm the Active DAST admission restriction and the no-dispatch evidence.
- [ ] Qualify Authenticated Active DAST through an authorized implementation and execution.

## Reproduction

Use the pinned revisions and dependencies in the evidence index. Run the shared unittest contract, the 16 existing synthetic scenarios, the four documented live lanes and the MockMvc adapter and comparator. For the product-native suite use the validated Bus Booking manifest and its long mode. [Shared live commands](tests/security/suites/bus_booking/live/README.md) · [Synthetic suite commands](tests/security/suites/feasibility_fixture/README.md) · [Product runbook](/Users/hahoangloc/Working/UET/bus-booking-security-ci/docs/security-runbook.md)
