# Standalone security test suite framework

The framework runs reviewed regression cases against disposable loopback fixtures in a network-disabled ZAP container. A suite supplies its objectives, cases, authentication, fixtures, plan and application oracles. The framework owns process isolation, plan admission, evidence and CI exit status.

The runner carries forward the feasibility PoC's native validation, fresh ZAP homes, bounded subprocesses, ordered job receipts and scoped report checks. It shares the original ZAP report parser. The example reuses the original fixture, Requestor plan steps and application oracles directly. The digest-bound feasibility source and evidence are preserved. [Feasibility report](../security-testing-feasibility.md) · [Qualification evidence](../security-testing-feasibility-evidence.json) · [CI verdict contract](../ci-verdict-contract.md)

## Repository layout

```text
tests/security/
  security_framework/
    manifest.py                  input and traceability checks
    engine.py                    native Automation Framework execution
    evidence.py                  evidence validation, verdict and Markdown report
    run.py                       host launcher and isolated worker
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

The output directory must be new. The workflow uses a fresh checkout and its baseline directory represents one execution. The receipt schema is specific to this framework and uses the exit codes from the existing CI contract. [Suite input schema](../tests/security/security_framework/schemas/suite-inputs.schema.json) · [Evidence schema](../tests/security/security_framework/schemas/result.schema.json)

## Execution and evidence

1. The host resolves the chosen scenario to a nonempty ordered set of cases. Each case must resolve to an objective, CWE mapping, specification and auth profile. The host and child independently hash the registries, specifications, framework modules and declared implementation inputs.
2. Active and unqualified JWT cases produce BLOCKED with a no-dispatch receipt. The launcher starts no container when every selected case is blocked. Other cases run in a unique Docker container with a read-only source mount, disabled networking and a bounded lifetime. Each run provisions a fresh fixture bound to `127.0.0.1`.
3. Scanner cases use an admitted native plan. The tested plan has one or more literal GET Requestor jobs, passive drain and a scoped traditional JSON report. Validation and execution run separately, with no fixture contacts permitted during validation. The runner checks native exit, expected job transitions, completion marker, freshness, scanner version, report scope and the report's truncation marker. [ZAP Automation Framework CLI](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)
4. The suite projects fixture and application observations. For authenticated scanner cases, the runner checks the fixture-resolved actor after login. For authenticated application assertions, it checks actor and status from the application's independent responses. Application-only cases can execute without starting ZAP. The example preserves state by reading its initial revision before executing its mutation checks.
5. Each case receipt includes its case ID, objective ID, CWE IDs, method, specification, expected predicate, auth profile, reason code, verdict and JSON evidence pointers. Input digests bind the executable sources. The scanner evidence records the generated plan digest and the report digest. Artifact pointers within projected alert rows locate entries in the transient native report. Console logs, unprojected reports, materialized plans, cookies and credentials are private to execution. Suite adapters must supply allowlisted observations.
6. The launcher checks the child exit, unique run ID, input digests, full case inventory, referenced observations and available native and identity evidence before accepting a result. ERROR takes precedence over BLOCKED, then FAIL, then PASS. A failed teardown invalidates evidence-backed earlier assertions for the run. A missing result, unresolved reference, incomplete job sequence, unverified identity or infrastructure failure precludes PASS.

## Authentication and capability status

Profiles live under the suite. The framework checks the expected actor aliases and observed HTTP status. The suite knows how to establish sessions and obtain independent application evidence of the effective actor. The example supports anonymous and form-and-cookie profiles. Its credentials belong to the disposable fixture. A new product adapter should read known fixture credentials at runtime, avoid publishing them, and test anonymous access, wrong credentials and actor separation against the actual product authentication path.

JWT Bearer has its own unqualified profile kind. Selecting it returns `BLOCKED / AUTH_PROFILE_UNQUALIFIED`. It needs an independently exercised token acquisition and replay path, effective subject and role evidence, and defined negative and lifecycle controls before admission. Authenticated Active DAST remains `BLOCKED / ACTIVE_EXECUTION_RESTRICTED`; the admission layer rejects active and other unsupported ZAP jobs. Expert Mode remains useful for fixture development within its released surface. The standalone workflow calls no MCP tools and changes no MCP server code. [Expert audit](../mcp-zap-expert-capability-report.md) · [Expert evidence B01](../mcp-zap-expert-capability-evidence.json)

## Local run and GitHub Actions

From the repository root, use Python 3.10 or newer and the pinned Docker image.

```sh
docker pull "$(cat tests/security/zap-image.txt)"
PYTHONPATH=tests/security python3 -m security_framework.run \
  --suite feasibility_fixture --scenario baseline \
  --out artifacts/security-suite/feasibility_fixture/baseline/local-01
```

The GitHub Actions workflow prepares the same baseline gate with read-only repository permissions and retains projected evidence when a run bundle exists. Its gate propagates the runner exit. A failed scanner image pull or missing output also fails the job. The pin and retained evidence support comparison between local and hosted runs. [GitHub Actions workflow](../.github/workflows/security-suite-framework.yml) · [GitHub artifact documentation](https://docs.github.com/en/actions/tutorials/store-and-share-data)

**Implemented.** The framework, schemas, reporting, example adapter and GitHub Actions workflow use Python's standard library and the existing pinned scanner image.

**Verified locally.** On Docker Engine 29.8.1 with a Linux ARM64 container, all 16 invocations matched their expected verdicts. Two clean baselines agreed, and the application-only and anonymous-only lanes passed. The three intentional CSP and authorization regressions exited 1 while ZAP exited 0. Authentication, evidence and infrastructure controls exited 2. Active and JWT selections exited 3 without dispatch. Nine framework contract tests passed and all emitted results validated against the evidence schema.

**Unqualified.** The workflow definition and shell commands were checked locally. Hosted GitHub Actions execution, JWT Bearer, Active DAST, browser and API exploration, external targets, and new project adapters remain unqualified for this framework.

[Implementation guidelines](security-test-implementation.md) · [Specification template](../tests/security/security_framework/templates/security-test-specification.md) · [Example suite](../tests/security/suites/feasibility_fixture/README.md)
