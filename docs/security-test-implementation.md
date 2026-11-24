# Security test implementation guidelines

Follow this sequence for each case.

1. **Security objective.** Assign a stable ID in `objectives/objectives.json`. Describe the protection and map relevant CWE IDs. Make the expected behavior reviewable without reading runner output.
2. **Test design.** Use the specification template. Define the disposable fixture, exact allowed traffic, initial state, actors, independent witnesses and controls. Separate the application's decision from the scanner's observation. Establish the expected rule or state before executing the case.
3. **Test cases.** Register IDs, objectives, specification paths, methodology, auth profile, oracle and required evidence keys in `cases/cases.json`. List required cases in the appropriate `suite.json` scenario. Order state-dependent cases explicitly and reset the fixture per run.
4. **Test implementation.** Put plans, fixture, auth configuration and application assertions in the suite. Bind all reused and suite-owned files through the manifest's `sources`. Keep runner policy and verdict aggregation in the framework.
5. **Execution.** Run the baseline and a deliberately changed control in clean isolated runs. Check the actual process exit and meaningful observations. Include the auth failure case for authenticated suites. Read a fresh scoped report only after the native plan completes and passive work drains.
6. **Evidence.** Emit only the fields needed to explain the result, such as fixture route and status, stable actor IDs, a native alert reference or state revision. Keep test data and credentials out of report artifacts. Preserve the projected result and report together. Include enough state to prove denied operations had no side effect.
7. **Verdict.** A security mismatch with usable evidence returns FAIL. Evidence, identity, process or infrastructure failures return ERROR. An unavailable method returns BLOCKED. Confirm healthy controls return PASS and deliberate regressions return the expected nonzero exit before enabling a gate.

## Implementing an adapter

A reviewed `suites/<suite>/adapter.py` provides the following hooks.

- `start_fixture(scenario)` returns a context manager yielding the owned fixture and an `http://127.0.0.1:<port>` origin. The fixture's `events` list contains sanitized requests served by the application.
- `build_plan(origin, directory, scenario, profiles)` creates the bounded Automation Framework definition for scanner cases. The passed profiles are those required for that scanner execution. Application-only suites can omit the hook. Keep plan report output at `<directory>/zap-report.json` and use a fixed positive detector control.
- `scanner_identities(events, profile)` returns an application witness per required actor in the form `{actor: {"actor": effective_actor, "status": response_status}}`. A rejected login may report 401 with a null effective actor. For a verified session, use a protected request witness independent of the login marker.
- `evaluate(case, origin, evidence, profile)` returns a verdict, a mapping of named projected observations, and application identity witnesses in the same shape. The framework adds native evidence requirements to scanner cases and verifies identity for authenticated cases. Make each oracle check the expected objective semantics. Report ERROR on absent or malformed evidence rather than substituting a default.
- The example's optional `after_report(path, scenario)` is a fixture qualification hook used to prove missing and malformed report handling. Normal suites can omit it.

Only trusted, reviewed suite code should run in this framework. The fixture adapter owns its operations and data contract. The standard runner mounts the test tree read-only and uses Docker networking mode `none`. Passive plan admission supports fixed GET requests, form login, passive drain and a ZAP report. State writes in the example belong to the deterministic application test against its own synthetic revision endpoint.

For branch and CI decisions, inspect the exact `checks` record for a case and its `evidenceRefs`. The generated Markdown report is a projection of the JSON result. An empty or absent result and an unsuccessful workflow step are both non-passing. [Architecture and schemas](security-test-framework.md) · [CI contract](../ci-verdict-contract.md)
