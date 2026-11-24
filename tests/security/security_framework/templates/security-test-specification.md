# Security test specification

## Objective and traceability

- Objective ID and security requirement.
- Applicable CWE IDs and why they apply to this behavior.
- Scope, authorized fixture, and test owner.
- Implementation revision and relevant dependency versions.

## Test design

- Threat or misuse in scope and the expected protection.
- Method and supported runner capability.
- Actors, fixture state, scope, and allowed operations.
- Authentication profile and independent effective-identity proof.
- Independent application and scanner observations.
- Positive control that proves the observation mechanism works.
- Regression control that changes the expected security outcome.
- Cleanup, time limits, and reproducibility conditions.

## Test cases

For each case, state its stable ID, objective ID, and method. Record the initial state, exact requests and actor, expected status and response fields, expected or forbidden side effects, and final state readback. Link the case registry entry, authentication profile, adapter, plan, fixtures and assertion implementation. Name each required evidence key. State how the oracle distinguishes a security violation from missing evidence, wrong identity, and an execution failure.

## Execution, evidence and verdict

Record the suite, scenario, source and scanner pin, and where CI retains the run bundle. Describe what each evidence group proves and how it is sanitized. Define the exact conditions for PASS, FAIL, ERROR and BLOCKED. Review one baseline and the intentional regression control on clean fixtures before adding the case to a gate.
