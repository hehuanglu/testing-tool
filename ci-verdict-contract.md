# Security framework CI verdict contract

The gate exits zero only when every required assertion has valid evidence and evaluates to PASS. ZAP process exit, plan completion and a report each establish part of the evidence needed for a security verdict.

The v2 compatibility receipt preserves the original exit in `execution.exitCode` and distinguishes completed assertions, incomplete execution and admission restrictions. A completed run can contain a failed test. Shared suite tests leave release `acceptance` unevaluated. The Bus Booking product reader preserves its separate execution gate, criterion decisions, baseline review, drift review and Active DAST evidence dependency. Capability qualification remains independently recorded. [Receipt and migration guide](docs/security-test-p2-migration.md)

## Exit codes

| Gate exit | Verdict | Meaning and evidence |
| --- | --- | --- |
| 0 | PASS | Native preflight and execution succeeded, all expected jobs finished in order, exact fixture witnesses and a fresh scoped report are valid, and every required security assertion held. |
| 1 | FAIL | A valid observation contradicted an assertion. The controls exercise CSP regression, omission of a required API link, and a role decision with incorrect application state. |
| 2 | ERROR | The gate could not establish a complete, trustworthy result. The reason identifies the failed prerequisite or evidence check. |
| 3 | BLOCKED | The execution boundary prohibits the workflow. The active status case records the policy decision and carries no scanner execution. |

## ERROR reasons

| Reason | Gate input |
| --- | --- |
| `INFRASTRUCTURE_FAILURE` | Docker startup, pinned-image availability, subprocess launch or another infrastructure dependency failed. |
| `PLAN_VALIDATION_FAILURE` | Native `-autocheck` exited nonzero or the supposedly validation-only process contacted the fixture. |
| `SCANNER_FAILURE` | The plan process exited abnormally or returned an execution error. Qualification terminates the disposable scanner after a fixture request. |
| `SCANNER_WARNING` | Native execution returned 2 without a known authentication failure. Qualification expects HTTP 204 from a fixture route returning 200. |
| `AUTHENTICATION_FAILURE` | The fixture recorded a rejected named login or an authenticated witness had the wrong effective identity. A named user, valid session handle or login indicator alone cannot establish identity. |
| `INCOMPLETE_EXECUTION`, `CONTAINER_TIMEOUT` | A required job receipt or fixture witness is absent, or the run reaches a deadline. Qualification omits an expected GET from an otherwise completed plan. |
| `MISSING_EVIDENCE`, `INVALID_EVIDENCE` | A required report or container result is absent, stale, malformed, truncated, inconsistent or in the wrong scope. Qualification removes or corrupts the generated report before ingestion. |
| `DETECTOR_CONTROL_MISSING` | The deliberately missing CSP header lacks the expected in-scope rule instance, so the absence of a finding on the subject has no detector control. |
| `APPLICATION_EVIDENCE_FAILURE`, `EVIDENCE_WRITE_FAILURE` | The application state witness cannot be read or the host cannot write the result. The latter may be available only through the nonzero process exit and stderr. |

For the qualified workload, enforcement follows the order of acquisition. The runner checks validation, process state, identity when a usable run exists, warnings, completion, report integrity and security assertions. Failures discovered after evidence acquisition remain visible in their check results. Aggregate precedence is ERROR, BLOCKED, FAIL, then PASS. If the project intentionally excludes active DAST from the required suite, record that decision separately from the required-check list. A requested active DAST check exits 3.

## Evidence and verification

- The result uses schema version 1 and includes the scenario, per-check verdicts and reason codes, aggregate verdict, exit code and the decisive check reasons. Qualification separately records the actual shell exit and the expected outcome for each control.
- Each native run uses fresh scanner homes, a fresh fixture and session store, a unique container and a read-only source mount. The standalone Docker network is disabled and host ports are never published. Both the validator and executor have time limits. The wrapper checks that the child's exit and JSON verdict agree and that every expected check is present.
- The generated plan digest, native exits, job transitions, fixture-side effective actor and status, report digest and allowlisted alert rows, and application response and post-state witnesses are retained when available. The complete native plan, logs, report, credentials, cookies and session identifiers stay private. The projected report pointers refer to the transient native report.
- Native exit 0 must be backed by the expected ordered job receipts, a terminal success marker, complete fixture witnesses and a fresh uncapped ZAP report containing the exact fixture origin. The receipt parser is tied to the tested ZAP image. A changed console format fails closed.
- An intentional regression still exits 1 from `run.py`. The qualification driver exits 0 when the regression was correctly detected and all verdicts match across the two clean runs. A downstream CI gate should invoke `run.py baseline` or its reviewed product equivalent, then retain the result artifact on both success and failure. If a job is killed outside the wrapper, a missing result is a failed job.
- Native CLI codes are engine telemetry. With the pinned Automation Framework CLI, 0 means no reported warnings or errors, 1 indicates errors, and 2 indicates warnings. The fixtures use no `exitStatus` override. [ZAP Automation Framework CLI](https://www.zaproxy.org/docs/desktop/addons/automation-framework/)

The reusable entry points are in [tests/security/feasibility](tests/security/feasibility/README.md). The measured results are in [security-testing-feasibility-evidence.json](security-testing-feasibility-evidence.json).


## Authenticated Active DAST

The framework accepts `authenticated-active-dast` as a case method for traceability. Its sole receipt is
`BLOCKED / ACTIVE_EXECUTION_RESTRICTED` with exit 3 for a fully blocked selection and a single case-bound
`capability-boundary` observation containing `dispatched: false` and the same reason. The result schema,
admission and result validator enforce that contract. CI checks the receipt without starting a scanner.
The shared native JWT Requestor evidence qualifies only its specific passive lane. Product-native Active DAST
has status `MISSING`.

An independent qualification, if authorized, needs a separately reviewed interface and approval for the exact
owned environment, operation scope, actors and data boundaries. Its evidence record would need a source and
configuration identity, fixture and scanner image identity, admitted scope and exclusions, verified backend
principal and effective role, correlated dispatch and terminal completion, checked scope and outcome evidence,
and cleanup. Separate configuration review, missing evidence, and any execution outcome. Product integration
and authorized qualification of the active component's own session behavior remain open.
