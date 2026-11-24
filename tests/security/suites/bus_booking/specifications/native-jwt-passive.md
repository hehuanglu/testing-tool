# Native JWT passive acceptance

`BB-LIVE-JWT-PASSIVE` supplies authenticated scanner transport evidence for SEC-A01-01 (CWE-862).
The product adapter registers a disposable USER and verifies its email with Mailpit. No outside client
logs in. Native ZAP JSON authentication performs the login and maps the returned token to Bearer
session state. Its anonymous Requestor control receives 401 and a Bearer challenge. Its named
Requestor and authenticated poll must receive 200 and resolve to the fixture account's ID, email,
verified status and USER role. The loopback relay verifies that both requests carry the backend-issued
token and answers ZAP’s preliminary login-page GET locally and forwards only the reviewed login POST and profile GET. Evidence retains predicates and status
codes. Fixture credentials, token values, response bodies and raw scanner output are transient.

Native preflight has zero contacts. The admitted plan consists of two fixed Requestor jobs, passive
drain and the report job. A separate synthetic HTML response must produce rule 10038-1. Report rows
are attributed by method and path, so this detector is distinguishable from product findings. A
missing or contradictory witness, scanner warning, incomplete job, out-of-scope report or failed
cleanup prevents a PASS. The bad-password scenario expects an execution ERROR with an authentication
failure and completed fixture cleanup. The positive receipt covers a single USER and `GET /api/auth/me`.
Session expiry, renewal and session ownership by other ZAP components require separate evidence.
