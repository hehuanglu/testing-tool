# Security testing framework

The framework runs reviewed regression cases against owned fixtures. A suite supplies objectives, cases, authentication profiles and oracles. Its project adapter acquires the fixtures. The selected engine executes within its reviewed scope, and the evidence layer validates and records the decision for each case.

The runner carries forward the feasibility PoC's native validation, fresh ZAP homes, bounded subprocesses, ordered job receipts and scoped report checks. It shares the original ZAP report parser. The example reuses the original fixture, Requestor plan steps and application oracles directly. The digest-bound feasibility source and evidence are preserved. [Feasibility report](../security-testing-feasibility.md) · [Qualification evidence](../security-testing-feasibility-evidence.json) · [CI verdict contract](../ci-verdict-contract.md)

## Repository layout

```text
tests/security/
  security_framework/
    manifest.py                  input and traceability checks
    execution.py                 project adapter, engine admission and resource scope
    project.py                   immutable Git materialization
    engine.py                    ZAP Automation Framework execution
    evidence.py                  v1 evidence validation, verdict and Markdown report
    receipt.py, ci.py            v2 compatibility receipts and CI entry point
    run.py                       synthetic fixture host launcher and isolated worker
    schemas/                     input and evidence JSON schemas
    templates/                   test specification template
  suites/<suite>/
    suite.json                   ordered case groups and implementation inputs
    objectives/objectives.json   stable security objective IDs and CWE mappings
    specifications/              test design and reviewable expected behavior
    cases/cases.json              executable case registry
    plans/                       reviewed native plan builders
    authentication/profiles.json authentication configuration and expected actors
    fixtures/                    fixture implementation or referenced fixture
    assertions/                  application-owned evidence and oracles
    adapter.py                   suite runtime entry point
  zap-image.txt                  pinned standalone scanner image
artifacts/security-suite/<suite>/<scenario>/<run>/
  result.json                    machine-readable evidence and verdict
  report.md                      human-readable report for the same run
.github/workflows/
  security-suite-framework.yml   standalone hosted workflow
```

The output directory must be new. A v1 result is the original evidence and exit contract. A v2 receipt references those original bytes by SHA-256 and records execution, objective acceptance and capability qualification independently. [Suite input schema](../tests/security/security_framework/schemas/suite-inputs.schema.json) · [Result schema](../tests/security/security_framework/schemas/result.schema.json) · [Receipt schema](../tests/security/security_framework/schemas/receipt.schema.json)

## Project adapter contract

`ProjectAdapter.prepare(resources)` materializes the intended source, checks configuration and dependencies, builds and starts the fixture, and registers cleanup with the provided `ExitStack` as resources are acquired. The adapter returns the fixture shape the selected engine already needs. The fixture can contain an owned origin, provisioning or observation functions, build and runtime identities, or a local in-process test target. Checks that require the engine's isolated network namespace remain with the reviewed lane at its first use of the fixture. Register cleanup before advancing to the next acquisition wherever partial startup can leave resources behind. Adjudicate and publish after the stack has unwound. [Adapter contract](../tests/security/security_framework/execution.py)

The synthetic adapter wraps the qualified fixture and supplies its event observer. Both Bus Booking pilot adapters reuse committed-source export, copied-matrix validation and API inventory checks. Bus Booking retains the Spring build, PostgreSQL and Mailpit lifecycle, account provisioning and identities, SQL fixture, application assertions and readback. The native product suite owns a separate fixture and continues to run through its own entry point. The shared framework validates its filtered evidence through a versioned compatibility adapter. ByteMe and the historical feasibility launcher keep their existing workflow and formats. [Bus Booking adapter](../tests/security/suites/bus_booking/adapter.py) · [Live adapter](../tests/security/suites/bus_booking/live/run.py) · [Native evidence adapter](../tests/security/suites/bus_booking/native_evidence.py)

## Engine contract

An `Engine` declares a capability and the suite methods it accepts. Admission rejects unsupported methods and applies authentication and Active DAST restrictions before any project preparation. The engine validates its own scope and prerequisites before dispatch. It returns an observation or a stable classification to the suite adjudicator. Project cleanup belongs to the adapter. Engine-owned processes, reports, temporary homes and captures live within the engine's existing bounded execution or the adapter's resource scope. [Engine contract](../tests/security/security_framework/execution.py)

- **MockMvc** invokes the reviewed in-process fixture. Its observations include controller selection and persisted state.
- **Live HTTP** uses the synthetic fixture or the packaged Bus Booking backend. It verifies application session identity and response and state expectations. The live Bus Booking pilot compares these observations with MockMvc.
- **Native ZAP passive** validates a fixed, loopback-only plan, runs native validation and passive processing, and checks the fresh report and independent identity witnesses. Form/cookie and bounded native JWT retain their respective reviewed profiles.
- **HAR passive** runs in the native product workflow with networking disabled and request sending disabled. The evidence engine validates the resulting HAR reconciliation, source identity, teardown and release gate. It consumes the filtered product bundle.

Future engines can use the same adapter lifecycle and supply their own prerequisites, admission rules, evidence producer and reviewed case methods. Source analysis and runtime inspection can use immutable local inputs. Browser evidence and log assertions need fixture-owned scope and independently verifiable observations. Adding a case method requires an explicit manifest, validation and test change.

## Execution and evidence

1. The host resolves the chosen scenario to a nonempty ordered set of cases. Each case must resolve to an objective, CWE mapping, specification and auth profile. The host and child independently hash the registries, specifications, framework modules and declared implementation inputs.
2. Active and unqualified JWT cases produce BLOCKED with a no-dispatch receipt. The launcher starts no container when every selected case is blocked. Other cases run in a unique Docker container with a read-only source mount, disabled networking and a bounded lifetime. Each run provisions a fresh fixture bound to `127.0.0.1`.
3. Scanner cases use an admitted native plan. The tested plan has one or more literal GET Requestor jobs, passive drain and a scoped traditional JSON report. Validation and execution run separately, with no fixture contacts permitted during validation. The runner checks native exit, expected job transitions, completion marker, freshness, scanner version, report scope and the report's truncation marker. [ZAP Automation Framework CLI](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)
4. The suite projects fixture and application observations. For authenticated scanner cases, the runner checks the fixture-resolved actor after login. For authenticated application assertions, it checks actor and status from the application's independent responses. Application-only cases can execute without starting ZAP. The example preserves state by reading its initial revision before executing its mutation checks.
5. Each case receipt includes its case ID, objective ID, CWE IDs, method, specification, expected predicate, auth profile, reason code, verdict and JSON evidence pointers. Input digests bind the executable sources. The scanner evidence records the generated plan digest and the report digest. Artifact pointers within projected alert rows locate entries in the transient native report. Console logs, unprojected reports, materialized plans, cookies and credentials are private to execution. Suite adapters must supply allowlisted observations.
6. The launcher checks the child exit, unique run ID, input digests, full case inventory, referenced observations and available native and identity evidence before accepting a result. ERROR takes precedence over BLOCKED, then FAIL, then PASS. A failed teardown invalidates evidence-backed earlier assertions for the run. A missing result, unresolved reference, incomplete job sequence, unverified identity or infrastructure failure precludes PASS.

## Authentication and capability status

Profiles live under the suite. The framework checks the expected actor aliases and observed HTTP status. The suite knows how to establish sessions and obtain independent application evidence of the effective actor. The example supports anonymous and form-and-cookie profiles. Its credentials belong to the disposable fixture. A new product adapter should read known fixture credentials at runtime, avoid publishing them, and test anonymous access, wrong credentials and actor separation against the actual product authentication path.

The reviewed Bus Booking live profile uses native ZAP JSON login, extraction of the login response token into
header-based session state, and an authenticated poll plus a named Requestor profile read for one USER.
The separate application client still owns authentication for the 102-case authorization pilot. The generic
`jwt-bearer` profile remains unqualified and returns `BLOCKED / AUTH_PROFILE_UNQUALIFIED`.
The `native-jwt-requestor` kind is admitted only for authenticated passive cases using the product fixture entry point.
[Native authentication specification](../tests/security/suites/bus_booking/specifications/native-jwt-passive.md) ·
[ZAP header session management](https://www.zaproxy.org/docs/desktop/addons/authentication-helper/session-header/)

Two passive modes have different evidence. Bus Booking product CI imports authenticated application-client HAR with request
sending disabled in an offline ZAP container. The shared pilot's native JWT lane has the scanner generate the login and
authenticated traffic on a disconnected loopback namespace. The backend-resolved identity, native passive drain and report
detector are required. The lab session check informed the native profile and evidence but is outside the shared CI entry point.
[Bus Booking live runbook](../tests/security/suites/bus_booking/live/README.md)

Authenticated Active DAST returns `BLOCKED / ACTIVE_EXECUTION_RESTRICTED`. The engine admits only its bounded passive plans.
The CI definition checks the no-dispatch receipt. Product-native scanner qualification remains missing. See the execution
and evidence boundary in the [CI verdict contract](../ci-verdict-contract.md#authenticated-active-dast).

## Local run and GitHub Actions

From the repository root, use Python 3.13.2 and the pinned Docker image. Git source materialization requires Python 3.12 or later for filtered archive extraction.

```sh
docker pull "$(cat tests/security/zap-image.txt)"
PYTHONPATH=tests/security python3 -m security_framework.run \
  --suite feasibility_fixture --scenario baseline \
  --out artifacts/security-suite/feasibility_fixture/baseline/local-01
```

The GitHub Actions workflow pins the checkout to the triggering SHA and validates it before publication. It records Python, Docker, image and platform identity, checks the execution gate and owned-container teardown, and stages the original projected evidence with its normalized receipt. The product workflow can pass its filtered bundle to the same verifier while retaining its independent acceptance gate. [GitHub Actions workflow](../.github/workflows/security-suite-framework.yml) · [P2 migration guide](security-test-p2-migration.md)

**Implemented.** The framework, schemas, reporting, example adapter and GitHub Actions workflow use Python's standard library and the existing pinned scanner image.

**Historical baseline.** On Docker Engine 29.8.1 with a Linux ARM64 container, all 16 invocations matched their expected verdicts. Two clean baselines agreed, and the application-only and anonymous-only lanes passed. The three intentional CSP and authorization regressions exited 1 while ZAP exited 0. Authentication, evidence and infrastructure controls exited 2. Active and JWT selections exited 3 without dispatch. Nine framework contract tests passed and all emitted results validated against the evidence schema.

**Current qualification.** See the [P2 completion report](../P2-COMPLETION-REPORT.md) and the [P0 and P1 evidence and reproduction record](../P0-P1-COMPLETION-REPORT.md).

[Implementation guidelines](security-test-implementation.md) · [Specification template](../tests/security/security_framework/templates/security-test-specification.md) · [Example suite](../tests/security/suites/feasibility_fixture/README.md)
