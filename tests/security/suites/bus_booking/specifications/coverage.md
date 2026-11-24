# Coverage and requirements traceability

The [matrix](../plans/authorization-matrix.txt) contains 32 operation pairs. The baseline executes all 25 protected pairs with anonymous, USER, ADMIN and SUPER_ADMIN credentials, plus the second USER on both booking-by-ID operations. This yields 102 protected status/handler/response/state cells. Two of the same USER bookings are also checked for ownership as a boundary of SEC-A01-01. That sample does not qualify the broader ownership objective SEC-A01-02.

| SEC-A01-01 / CWE-862 requirement | Case IDs | Evidence predicate |
| --- | --- | --- |
| Effective authentication precedes protected operations | BB-AUTH and all protected matrix cases | Real login, independent current-user witness, rejection and absent MVC handler for authentication failures |
| Ordinary users can perform only their contract operations | BB-PROFILE, BB-USER, BB-BOOKING | Per-role results, ownership boundary, response identity and readback |
| Administrative resources require ADMIN or SUPER_ADMIN | BB-ADMIN-READ, BB-ADMIN-WRITE | Each role and operation, authorized positive controls, denied persistence and pre-controller rejection |
| Only SUPER_ADMIN can change roles | BB-ROLE, BB-ROLE-LIFECYCLE, BB-ROLE-RULES | Verified principal, stored role changed only when allowed, sole root, next-request demotion |
| Existing execution restrictions remain enforced | BB-SCANNER-JWT, BB-ACTIVE | Separate no-dispatch receipts and blocked exit |

There are also 10 authentication condition rows and 8 role lifecycle/business rows. Four independent login and current-user witnesses gate the application cases. Reported evidence shows request outcomes and row-level persistence. It does not capture network traffic, in-memory or external side effects, or the contents of database rows.

The contract has seven public operations. Login is exercised with valid and wrong passwords. Anonymous locations and its invalid-Bearer control are exercised. Public trips, public trip detail, registration, verification and resend flows are untested here. For the JWT failure variants, coverage is representative rather than every route/token combination.

Surfaces outside the initial MockMvc qualification include live HTTP transport, proxy and TLS behavior, CORS, unknown paths and method permutations, mail delivery, arbitrary date or resource states, token signing-key rotation, concurrent role changes, hosted CI and deployment configuration. The in-process application lane qualifies login-issued JWT Bearer and current-role resolution for this test profile. Shared JWT scanner transport and Active DAST remain blocked. No passive scanner check is needed for the authorization oracle.

## Live HTTP requirements traceability

| Requirement | Existing case IDs | MockMvc evidence | Live HTTP evidence |
| --- | --- | --- | --- |
| Authenticate protected requests | BB-AUTH, BB-PROFILE and all protected groups | Current-user proof, response, security denial before MVC handler selection | Current-user proof from real HTTP, response, and database snapshot |
| Enforce role and ownership boundaries | BB-USER, BB-BOOKING, BB-ADMIN-READ, BB-ADMIN-WRITE | All matrix cells with MVC handler, response and state witnesses | The same matrix cells with HTTP status and JSON, and independent database state |
| Limit role changes to SUPER_ADMIN and apply the new role on the next request | BB-ROLE, BB-ROLE-LIFECYCLE, BB-ROLE-RULES | Response and stored roles, same-JWT demotion and rule cases | The same response, stored role and same-JWT checks through the packaged application |
| Preserve scanner boundaries and retain applicable evidence | BB-LIVE-PASSIVE, BB-SCANNER-JWT, BB-ACTIVE | Existing JWT and active no-dispatch controls | Anonymous request through ZAP, fresh report and synthetic detector control. Shared JWT and active no-dispatch controls retain their separate BLOCKED verdicts. |

The live HTTP lane reuses the 102 protected cells and all 18 supplemental conditions. It qualifies the packaged application's loopback HTTP/1.1 interface for this committed revision and fixture configuration. The in-process gate still observes MVC handler selection. The live suite leaves TLS, ingress and reverse-proxy policy, full Compose and SMTP flows, and hosted CI untested. See the [comparative execution report](../live-execution-report.md).
