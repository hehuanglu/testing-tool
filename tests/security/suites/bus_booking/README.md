# Bus Booking authorization pilot

This suite applies SEC-A01-01 and CWE-862 to the Bus Booking backend. It reuses the shared case manifest, the effective-identity checker, evidence records, validator, aggregation, reports and blocked-capability policy. The suite-local launcher runs the application’s test context and owns its JWT fixture. The shared runner checks the two scanner restriction scenarios directly.

- [Specification](specifications/sec-a01-01.md)
- [Authorization matrix](plans/authorization-matrix.txt)
- [Execution report](execution-report.md)
- [Requirements traceability and coverage](specifications/coverage.md)
- [Sanitized evidence](evidence/)

## Local execution

On Linux or macOS, use Python 3.12 or newer, Git, Java 21, Docker and a local Bus Booking Git checkout. A committed revision is required because the launcher uses `git archive` and ignores working-tree edits. It reserves a new output directory and launches a fresh database per invocation. No running Bus Booking deployment is required.

Set `BUS_PROJECT` to the authorized local checkout. Set `JAVA_HOME` to the installed Java 21 home. Prepare the checked-out revision's exact Maven wrapper and dependencies separately. The selected product unit test exercises Surefire dependency resolution without a database. Run the following from the framework repository root.

```sh
export BUS_PROJECT=/absolute/path/to/bus-booking-security-ci
export JAVA_HOME=/absolute/path/to/java-21
(cd "$BUS_PROJECT" && ./mvnw -B -Dtest=JwtServiceTest test)
docker pull postgres:16-alpine

PYTHONPATH=tests/security python3 -m suites.bus_booking.adapter \
  --project "$BUS_PROJECT" \
  --revision 56f58a3ed86d22d44bd2007e3a49aeb0c979510f \
  --out artifacts/security-suite/bus_booking/baseline/local-01
```

Repeat with a new output directory. The launch uses the Maven binary in the product wrapper cache and Maven offline mode, verifies the contract inventory, and starts the local PostgreSQL image by its digest with image pulling disabled. MockMvc runs the real Spring MVC and Spring Security chain without creating an application listener. The runner projects sanitized `result.json` and `report.md`. Exit 0 is PASS, 1 FAIL, 2 ERROR and 3 BLOCKED. Maven failures are classified without forwarding raw test output.

Run the two capability checks using the unchanged shared launch command. Each is expected to exit 3.

```sh
PYTHONPATH=tests/security python3 -m security_framework.run \
  --suite bus_booking --scenario jwt-blocked \
  --out artifacts/security-suite/bus_booking/jwt-blocked/local-01

PYTHONPATH=tests/security python3 -m security_framework.run \
  --suite bus_booking --scenario active-blocked \
  --out artifacts/security-suite/bus_booking/active-blocked/local-01
```

Compare two clean baselines, verify controls from copied observations, and check nonzero process exit and timeout handling.

```sh
PYTHONPATH=tests/security python3 -m suites.bus_booking.assertions.verify \
  artifacts/security-suite/bus_booking/baseline/local-01/result.json \
  artifacts/security-suite/bus_booking/baseline/local-02/result.json \
  --out artifacts/security-suite/bus_booking/baseline-verification.json
```

## CI integration

Run the baseline in the Bus Booking PR job on a Docker-capable runner with Java 21 and Python 3.12 or newer. Check out the Bus Booking revision being tested and a reviewed, fixed revision of the framework in separate directories. The framework revision must include the shared modules and this suite. Cache Maven dependencies and bootstrap the wrapper from the product checkout. The same job can pull the approved PostgreSQL 16 image as a setup step. Record the digest from the resulting provenance. Example commands for checkout directories named `bus-booking` and `security-framework` are below.

```sh
set -eu
(cd bus-booking && ./mvnw -B -Dtest=JwtServiceTest test)
docker pull postgres:16-alpine
revision=$(git -C bus-booking rev-parse HEAD)
PYTHONPATH=security-framework/tests/security python3 -m suites.bus_booking.adapter \
  --project bus-booking --revision "$revision" --out pilot-evidence
```

Use a separate artifact upload step with `if: always()` for `pilot-evidence/result.json` and `pilot-evidence/report.md`. Preserve the runner exit as the job result. A missing receipt or failed prerequisite fails the job. Store scanner restriction checks in a separate verification step that explicitly asserts exit 3 and the expected no-dispatch evidence. Hosted execution status is recorded in the execution report.

## Live HTTP companion

The [live specification](specifications/live-http.md) applies the same 102 protected matrix cells to the packaged application in Docker. See [local Docker and GitHub Actions instructions](live/README.md) and the [comparative execution report](live-execution-report.md). The application-level MockMvc entry point remains the baseline described above.
