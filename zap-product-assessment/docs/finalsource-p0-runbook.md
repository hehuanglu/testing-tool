# W3 admission — P0 execution blocked

See the [W3 registry/secret readiness contract](remediation/W3_REGISTRY_VI.md) and
[generated current capability summary](remediation/CAPABILITIES_GENERATED.md).
`finalsource_p0.py --mode native|delegated|business` now returns exit2/block before
reading receipt/credentials or creating resources. Constructor, provision, execute
and standalone guard serve also reject. There is no diagnostic override. The
historical commands below are retained as procedure history and will be refused
until a future contract-specific runtime gate attestor is implemented and proven.
BOLA v1.4 read-only is a separate entry with its existing checks; it does not enable
P0 writes. Historical pilot secret audits do not satisfy expanded G3.

The offline coverage subcommand and historical verification remain usable; v2
readback continues to require an external plan pin and cannot publish or allow.

# Local finalsource P0 pilot

W2 adds a separate externally pinned v2 evidence verifier; see
[the W2 verifier contract](remediation/W2_VERIFIER_VI.md). Historical P0 bundles
continue to use `verify_finalsource_p0.py`; they are not silently upgraded to v2.

Remediation W1 adds an offline `coverage` subcommand and conservative v2
candidate output; see [the W1 coverage contract](remediation/W1_COVERAGE_VI.md).
Reevaluate published bundles into a fresh external directory. Legacy `verified`
coverage labels remain historical and are not v2 application-oracle-pass. The
scan examples below document the earlier pilot; W1 does not grant live authority
or enable a mode past its auth/secret/policy gates.

This pilot extends product evidence separately from the existing borrowed v1.4
read-only account BOLA adapter. It does not change that adapter's contract. Use
only on the explicitly authorized `finalsource-zap-test` deployment with dedicated
fixture actors and a fresh output directory. The script inspects the current
frontend/backend container IDs, image IDs, StartedAt, network ID and addresses.
Target drift aborts the run. It never execs into target containers or reads the DB.

Use the package Python runtime. `--receipt` must identify this test environment,
the actual user request and fixture authority when using `--business`. Credentials
are supplied by a private file, never shell values. Reuse actual fixture actors;
the pilot assumes the separately preserved A-owned baseline account1 exists.

```sh
.venv/bin/python scripts/finalsource_p0.py \
  --output /absolute/new-run/native-A \
  --credentials /absolute/private/test-credentials.json \
  --receipt /absolute/user-authorization.json \
  --mode native --actor A --business

.venv/bin/python scripts/finalsource_p0.py \
  --output /absolute/new-run/delegated-A \
  --credentials /absolute/private/test-credentials.json \
  --receipt /absolute/user-authorization.json \
  --mode delegated --actor A
```

Run actor B in another fresh directory with `--actor B`. Execute these sequentially
when host disk/memory is constrained. Preserve each output, including failures.
The private credential schema is the existing fixture schema: `actors.A/B` contain
email, password and expected userId; optional W is the previously created weak
password test user. This is test-only data, not a real user's credentials.

The completed pilot uses `--accounts 1,4,5` for read-only scanner phases. Use actual
IDs from the fixture manifest on future runs. When categories are absent and data
preparation is explicitly authorized, `prepare_finalsource_category_fixture.py`
transactionally inserts exactly two new categories for the test actors, verifies
identity/ownership and updates/deletes no old row. Required DB credentials stay in
memory/stdin; a one-shot client can reach only the test DB IP:3306. It never execs
into a borrowed target. Then `--mode business --category-fixture /absolute/result.json`
creates dedicated accounts and runs transaction balance/ownership controls. Final
read-only data checks used the historical pinned copy of `verify_finalsource_fixture_state.py`.
The current script is the offline W6 manifest/transition verifier with an external
plan pin; see [W6](remediation/W6_BUSINESS_VI.md). It sends no product requests and
does not reinterpret legacy pilot bundles.

## Boundaries and interpretation

The Linux namespace has a default-deny IPv4/IPv6 output firewall. Only guard UID1003
can reach the exact borrowed frontend IP:8443. Scanner UID1000 can reach loopback
for ZAP and browser/driver traffic, with explicit rejection of the private control
port18081 and MCP7456. The guard binds only loopback. No host ports are published.
Allowed UI/assets and API GET paths are explicit; scanner writes are denied except
an exact fixture login in native mode. Private API controls accept account writes
only on newly registered fixture IDs, refuse writes to the old baseline account1,
and require a run prefix for new accounts. Saving goals are tracked by returned ID.
Requests are bounded at2rps and the guard expires after40minutes. No redirects are
followed upstream and no upstream cookie is replayed. No automatic login retry.

The mirror serves the actual frontend/assets/API responses under a loopback HTTP
origin. It uses the local target's self-signed TLS connection without changing
system trust. Report URLs must be mapped back to the recorded canonical frontend.
Mirror transport/CORS/TLS/cache/header alerts are not automatically app findings.
This mode does not test the canonical browser TLS origin, SNI, deployment CORS,
external dependencies or production egress configuration.

Native mode executes the real login form and eight UI journeys in Firefox through
ZAP, then starts the supported browser-authenticated Client Spider context. It is
a diagnostic of native auth/history, not permission to call a leaking mode safe.
Credentials, script source, history and reports remain under the restricted run
directory. Never publish them as a public customer report. Preserve any secret-gate
failure and distinguish it from functional success.

Delegated mode uses a separately logged-in, identity-checked actor token in the
private guard process. ZAP uses its ordinary HTTP crawl/active APIs through this
per-actor authenticating mirror. Real JWTs are injected only on the final target
hop; they never enter the ZAP request model. This is an adapter-assisted path, not
native ZAP JSON-bearer support or an operationalized experimental provider. Actor
A/B use different guard processes, tokens and entire scanner namespaces. Protected
response identity is checked from the actual server response, not just token claims.
The script runs one bounded XSS/SQLi policy on two parameterized business GETs,
then injects an invalid token during a separate live producer, latches a real401,
stops that exact operation and confirms terminal state. It does not refresh a token
or silently count anonymous responses as authenticated coverage.

The final run removes the dynamic `SwaggerSecretDetector.js` script from its own
scanner: disabling the generic script rule alone did not prevent rule100043 from
sending requests. Earlier policy-deviating phases remain excluded. Actual final
scanProgress must show only40012/40018 with nonzero requests and Complete status.
Passive rule10116 (scanner update check) is disabled because its internet lookup
cannot complete behind the intentional egress deny. App passive rules stay enabled.

## Business fixture changes

`--business` creates two run-prefixed accounts, validates cross-user/anonymous
update/delete with owner post-state controls, updates the A account as owner and
deletes only that new A account. It retains the new B account for isolation proof.
It creates two saving goals, verifies cross-user/anonymous denial and an effective
owner update. Goals remain retained because no DELETE route exists. All attempts,
including denied writes, are in the mutation journal and the final state inventory.
Existing users/account1 are never modified. Transactions require an owned category. Do not invent an ID or use another user's
category for a positive control. Preserve initial empty-option evidence; use the
separately authorized fixture helper above, or keep this workflow blocked.

## Completion and recovery

Record separate execution/evidence/cleanup/acceptance statuses. Producer completion
must be observed; then collect two passive-zero observations, messages, URLs, JSON
and HTML reports and full hash-pinned report chunks. Audit real credential/JWT
occurrence and validate actor identity, controls and scope before acceptance.
Do not use report generation, import success or an HTTP401 as authenticated proof.

On lost ACK, do not repeat a start or mutation. Reconcile the recorded operation or
stop only the run-owned scanner namespace. Container cleanup verifies both the exact
ID and `zpa.run` label. Borrowed targets are never removed by recovery. A daemon
outage leaves cleanup unconfirmed until later metadata readback. Docker Desktop
restart affects targets and needs the user's scope or explicit approval. Keep
interrupted evidence immutable and put later recovery observations in a new file.

For a published delivery manifest, offline readback is:

```sh
.venv/bin/python scripts/verify_finalsource_p0.py /absolute/delivery
```

The verifier does not send traffic, rerun tests or approve security/release. A
consistent bundle may correctly contain blocked or failed P0 acceptance.
