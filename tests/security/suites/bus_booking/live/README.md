# Live HTTP execution and CI integration

Use the [live specification](../specifications/live-http.md) for scope and the [comparison report](../live-execution-report.md) for the validated revision and results.

## Local Docker execution

On Linux or macOS, use Python 3.12+, Git, a Java 21 JDK, and Docker with Linux containers. Use a trusted Bus Booking checkout and a reviewed committed revision. The launcher builds an exported commit in a temporary directory. It uses the wrapper distribution and Maven dependencies already cached in the normal Maven home.

From the framework root, prepare the selected checkout and the runtime images. Pull ZAP only if exercising the optional passive lane.

```sh
export BUS_PROJECT=/absolute/path/to/bus-booking-security-ci
export JAVA_HOME=/absolute/path/to/java-21
export BUS_REV=56f58a3ed86d22d44bd2007e3a49aeb0c979510f

(cd "$BUS_PROJECT" && ./mvnw -B -DskipTests package)
docker pull postgres:16-alpine
docker pull eclipse-temurin:21-jre
docker pull "$(cat tests/security/zap-image.txt)"
```

Run the HTTP authorization gate and, separately, the anonymous ZAP evidence check. Use a new evidence path for each run.

```sh
export PYTHONPATH=tests/security
export BUS_OUT=artifacts/security-suite/bus_booking/live-local

python3 -m suites.bus_booking.live.run --lane http \
  --project "$BUS_PROJECT" --revision "$BUS_REV" --out "$BUS_OUT/http"
python3 -m suites.bus_booking.live.run --lane passive \
  --project "$BUS_PROJECT" --revision "$BUS_REV" --out "$BUS_OUT/passive"
```

The standalone runner pins the locally cached image digests, uses Maven offline, and publishes no container port to the host. It removes the containers and temporary files after execution. For the application-only gate, prepare PostgreSQL and Java and run the HTTP command. The authenticated matrix sends its requests directly to the application.

To reproduce the comparison, rerun the HTTP lane to `$BUS_OUT/http-repeat` and run the unchanged MockMvc entry point.

```sh
python3 -m suites.bus_booking.adapter \
  --project "$BUS_PROJECT" --revision "$BUS_REV" --out "$BUS_OUT/mockmvc"

python3 -m suites.bus_booking.live.compare \
  "$BUS_OUT/mockmvc/result.json" "$BUS_OUT/http/result.json" \
  "$BUS_OUT/http-repeat/result.json" "$BUS_OUT/passive/result.json" \
  --out "$BUS_OUT/comparison.json"
```

The comparison consumes current-source receipts and verifies the response, state and identity results. The original in-process report retains its historical artifacts.

## Scanner-owned JWT passive analysis

Use the same project revision, local Java and Docker setup. Also cache the recorded Mailpit image with
`docker pull axllent/mailpit:v1.27.8`. The launcher resolves its immutable local digest.

```sh
python3 -m suites.bus_booking.live.run --lane authenticated-passive \
  --project "$BUS_PROJECT" --revision "$BUS_REV" --out "$BUS_OUT/native-jwt"
```

The negative control is `--lane authenticated-passive-bad-password` with a distinct output directory.
Expect exit 2, `AUTHENTICATION_FAILURE`, and a cleanup receipt. Native ZAP fetches a fixture-local login
page, submits the JSON login to the scoped relay and sends a verified profile poll and named request.
Provisioning uses registration and Mailpit. The relay forwards the login and the exact protected GET
to the real backend. There are zero published ports and the database owns a disconnected Docker loopback
namespace. The suite's generic launcher reports `PRODUCT_FIXTURE_REQUIRED` for this case because the
product launcher provides the isolated packaged runtime. [Specification](../specifications/native-jwt-passive.md)

## GitHub Actions integration

On an Ubuntu runner with Docker, install Java 21 and Python 3.12+ and cache Maven dependencies using the application's POM. Check out the target application commit into `bus-booking` and a fixed, reviewed framework revision containing this suite into `security-framework`. Set `permissions: contents: read` and use separate required steps or jobs for application gates. The following is the live HTTP job's shell step.

```sh
set -eu
(cd bus-booking && ./mvnw -B -DskipTests package)
docker pull postgres:16-alpine
docker pull eclipse-temurin:21-jre
revision=$(git -C bus-booking rev-parse HEAD)
PYTHONPATH=security-framework/tests/security python3 -m suites.bus_booking.live.run \
  --lane http --project bus-booking --revision "$revision" --out pilot-evidence/http
```

Keep the [in-process gate](../README.md#ci-integration) in its own step or job. For a separate passive evidence job, also pull the existing scanner image from `security-framework/tests/security/zap-image.txt` during setup and invoke `--lane passive --out pilot-evidence/passive` with the same application revision. Use an artifact upload step that runs on failure and retains only `pilot-evidence/**/result.json` and `pilot-evidence/**/report.md`. Preserve the launcher status and require a receipt for each enabled gate. Use the existing [artifact upload pattern](../../../../../.github/workflows/security-suite-framework.yml). To qualify the scanner-owned passive profile, cache Mailpit too and use the lane above in its own job. Use the shared CLI for the generic JWT and Active DAST no-dispatch controls, with exit 3 expected.

The CI integration instructions were prepared from the local workflow. Hosted GitHub Actions execution remains unverified.
