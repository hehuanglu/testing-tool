# Prepare fixed CI regression cases

Use this workflow only when the user wants to retain a reviewed security behavior as a CI
regression. Do not export every catalog criterion automatically. An exported test does not
replace Gate 2, an assessment verdict, retained evidence, or the Drive deliverable.

## Inputs and output

Select one valuable case with a current plan binding, a reviewed `matched` or `violated`
result, exact support evidence links, and a stable expectation derived from the requirement.
Prepare a separate CI mapping with a disposable fixture, exact request and response witness,
positive control, and assertion. Never learn the expectation from the observed alert count.

The supported profile registry is:

| Status | Profile | Boundary | Qualification |
|---|---|---|---|
| supported | `passive-http-v1` | Anonymous literal GET, CSP missing rule `10038-1`, fixed response/control witnesses; synthetic `csp-demo` and registry-bound ByteMe v1 product lane | `tests/security/qualification/run_acceptance.py` LIVE-01 through LIVE-06; `tests/security/product/byteme/run_acceptance.py` |
| qualification-pending | `anti-framing-http-v1` | ByteMe v1 exact anonymous GET HTML response; ZAP-derived semantics for enforcing CSP `frame-ancestors` and XFO, with unsupported complexity failing closed | `tests/security/product/byteme/run_acceptance.py --profile anti-framing`; promote after local and GitHub artifact readback |
| experimental | `openapi-passive-v1` | OpenAPI import and passive API transport only | `tests/security/experiments/openapi-passive/` |
| experimental | `bearer-passive-v1` | Static bearer injection and auth witness only | `tests/security/experiments/bearer-passive/` |
| experimental | `active-xss-v1` | One selected native active XSS rule on disposable fixture | `tests/security/experiments/active-xss/` |
| experimental | `form-cookie-csrf-v1` | Synthetic form auth, cookie session and refresh witness with one fixed CSRF literal embedded in the login body; no token extraction or rotation | `tests/security/experiments/form-cookie-csrf/` |
| experimental | `bola-two-actor-v1` | Read-only two-actor ownership oracle with exact object/actor witness | `tests/security/experiments/bola-two-actor/` |
| blocked | `browser-journey-v1` | Pinned Firefox exists but matching `geckodriver` is absent | `tests/security/experiments/browser-journey/` |
| unsupported | async/OAST/WebSocket/GraphQL and product-specific auth/BOLA | No stable profile | A named experiment or product adapter must first satisfy its qualification gates |

ZAP exposing a feature or add-on does not make it supported by this skill.

## Export and review

For a synthetic contract fixture:

```sh
zap-assessment regression generate --input reviewed-input.json --out-dir tests/security/cases
```

For an assessment RUN v3:

```sh
zap-assessment regression generate \
  --input ci-mapping.json \
  --run /private/RUN.json \
  --case-id CASE_ID \
  --out-dir tests/security/cases
```

The exporter validates the current plan revision and digest, the exact case/context, support
readback links and profile boundary. It projects only stable provenance digests. It does not
read files named by the RUN, send traffic, or commit raw responses and secrets. Missing data
returns a field-specific `MISSING_PREREQUISITE`; an operation outside the profile returns
`UNSUPPORTED_OPERATION`.

The runtime registry accepts synthetic `csp-demo` and versioned product adapter `byteme-v1`.
The product adapter pins `hehuanglu/ByteMe` at a full SHA, builds an isolated target with private
database/keys, gives ZAP/backend/database one owned network without public ports, and reads the
response and alerts back from ZAP history. Its detector control uses a separate origin and is not
product evidence. The committed ByteMe case is `product-qualification`: it qualifies the adapter
and CSP assertion without pretending the legacy RUN is v3.

The separate anti-framing candidate does not require native alert `10038-1`. It reads the exact
ZAP message and projects only the framing-policy header allowlist. An enforcing CSP
`frame-ancestors` directive takes precedence over XFO; Report-Only, `default-src`, and
`frame-src` do not provide inbound anti-framing. The profile never claims a browser framing
attempt. Complex or unsupported syntax returns missing evidence rather than PASS.

Keep every ZAP updater gate disabled in this pinned lane (`autoupdate.checkOnStart` plus the
`start.*` check/download/install flags); otherwise a downloaded network add-on can change the
effective scanner and restart its listener. Every non-null result locator must resolve inside the
retained artifact. If setup fails before the scanner exists, record `evidencePath: null` rather
than manufacturing evidence or pointing at a missing file.

A real RUN v3 can produce the same product case shape only when its current approved case has
reviewed support links and an expectation basis compatible with the CSP assertion. Do not turn a
historical missing-CSP alert into an anti-framing verdict: an effective `X-Frame-Options` policy
may satisfy the catalog criterion even while rule `10038-1` fires. Keep adapter qualification and
assessment-to-suite transfer as separate claims.

Review a newly created file or the exit-2 candidate diff. A byte-identical existing case is
`UNCHANGED`; a different existing file is never overwritten. After review, run the portable
suite locally and in the target repository workflow. Add a case by adding one JSON file;
delete it by deleting that file; update it by explicitly accepting the reviewed candidate.

Keep assessment history, product traffic authority, CI fixture data and regression outcomes
separate. Export itself is offline. Product traffic still requires the approved assessment
scope; disposable CI fixtures may be exercised by their repository workflow. A future target,
auth protocol or business oracle requires a newly qualified adapter rather than relabeling a
generic ZAP operation.

For ByteMe adapter qualification, run:

```sh
python3 tests/security/product/byteme/run_acceptance.py \
  --product-source /clean/pinned/ByteMe \
  --out artifacts/byteme-qualification \
  --scenario all

python3 tests/security/product/byteme/run_acceptance.py \
  --profile anti-framing \
  --product-source /clean/pinned/ByteMe \
  --out artifacts/byteme-anti-framing-qualification \
  --scenario all
```

The harness distinguishes upstream-original, fixed-control and regression-control, plus missing
request, wrong response, startup, scanner-timeout and cleanup failures. Fixed/regression patches
are versioned in testing-tool and must never be reported as upstream ByteMe behavior.
