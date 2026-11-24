"""Run the Bus Booking contract and passive ZAP checks in a disconnected Docker namespace."""

import argparse
from contextlib import contextmanager
import base64
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import tarfile
import time
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from security_framework.evidence import (
    EXIT, add_check, fail_run, finish, markdown, outcome, put_evidence, start, validate_child,
)
from security_framework.execution import APPLICATION, PASSIVE, Engine, run_project
from security_framework.manifest import ROOT, read_suite
from security_framework.run import IMAGE_PIN

from ..adapter import (
    FIXTURE, HOST_ENV, PG_TAG, ExecutionError, cached_maven, command, prepare_source, sha256,
)
from ..assertions.oracle import adjudicate
from .scanner import verify_witnesses

DIRECTORY = Path(__file__).resolve().parent
HTTP_CLIENT = DIRECTORY / "BusBookingLiveHttp.java"
JAVA_TAG = "eclipse-temurin:21-jre"
CASE_ID = "BB-LIVE-PASSIVE"
NATIVE_CASE_ID = "BB-LIVE-JWT-PASSIVE"
NATIVE_LANES = ("authenticated-passive", "authenticated-passive-bad-password")
MAILPIT_TAG = "axllent/mailpit:v1.27.8"


def pinned_local_image(tag, repository):
    pins = json.loads(command(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", tag],
                              reason="RUNTIME_IMAGE_UNAVAILABLE"))
    pattern = re.compile(re.escape(repository) + r"@sha256:[0-9a-f]{64}\Z")
    for pin in pins or ():
        if pattern.fullmatch(pin):
            return pin
    raise ExecutionError("RUNTIME_IMAGE_UNAVAILABLE")


def build_revision(project, working, java_client):
    try:
        release = (Path(HOST_ENV["JAVA_HOME"]) / "release").read_text(encoding="utf-8")
    except (KeyError, OSError):
        raise ExecutionError("JAVA_21_REQUIRED") from None
    java = re.search(r'^JAVA_VERSION="(21\.[0-9.]+)"$', release, re.MULTILINE)
    if not java:
        raise ExecutionError("JAVA_21_REQUIRED")
    maven, version = cached_maven(project)
    if java_client:
        package = project / "src/test/java/com/example/busbooking/api"
        for file in (FIXTURE, HTTP_CLIENT):
            target = package / file.name
            if target.exists():
                raise ExecutionError("FIXTURE_PATH_CONFLICT")
            shutil.copyfile(file, target)
    command([str(maven), "-o", "-B", "-q", "-DskipTests", "package"], cwd=project, timeout=180,
            reason="APPLICATION_BUILD_FAILURE")
    target = project / "target"
    jars = list(target.glob("busbooking-*.jar"))
    if len(jars) != 1:
        raise ExecutionError("APPLICATION_JAR_MISSING")
    runtime = working / "runtime"
    runtime.mkdir()
    jar = runtime / "app.jar"
    shutil.copyfile(jars[0], jar)
    fixture_hashes = {}
    with ZipFile(jar) as archive:
        names = archive.namelist()
        dependencies = [name for name in names if re.fullmatch(r"BOOT-INF/lib/[^/]+\.jar", name)]
        if not dependencies or any("BusBookingAuthorizationContract" in name or "BusBookingLiveHttp" in name
                                   for name in names):
            raise ExecutionError("APPLICATION_JAR_LAYOUT_INVALID")
        if java_client:
            archive.extractall(runtime, members=dependencies)
    if java_client:
        shutil.copytree(target / "classes", runtime / "classes")
        fixture_classes = runtime / "contract/com/example/busbooking/api"
        fixture_classes.mkdir(parents=True)
        classes = target / "test-classes/com/example/busbooking/api"
        for prefix in ("BusBookingAuthorizationContract", "BusBookingLiveHttp"):
            for compiled in classes.glob(prefix + "*.class"):
                shutil.copyfile(compiled, fixture_classes / compiled.name)
        fixture_hashes = {
            "authorizationFixtureSha256": sha256(package / FIXTURE.name),
            "httpClientSha256": sha256(package / HTTP_CLIENT.name),
        }
    return runtime, {"javaBuildVersion": java[1], "mavenWrapperVersion": version,
                     "applicationJarSha256": sha256(jar), **fixture_hashes}


def verify_namespace(name, expected):
    mode, ports = command(["docker", "inspect", "--format",
                           "{{.HostConfig.NetworkMode}} {{len .HostConfig.PortBindings}}", name],
                          reason="DOCKER_ISOLATION_FAILURE").decode().split()
    if mode != expected or ports != "0":
        raise ExecutionError("DOCKER_ISOLATION_FAILURE")


def bind(path, destination, *, writable=False):
    return f"type=bind,src={path.resolve()},dst={destination}" + ("" if writable else ",readonly")


def docker_args(name, run_id, namespace):
    return ["docker", "run", "--name", name, "--label", f"bus-booking-live={run_id}",
            "--network", namespace, "--pull", "never"]


@contextmanager
def deployed(run_id, runtime, *, mail=False):
    db_name = f"bus-live-{run_id}-db"
    app_name = f"bus-live-{run_id}-app"
    label = f"bus-booking-live={run_id}"
    postgres = pinned_local_image(PG_TAG, "postgres")
    mail_image = pinned_local_image(MAILPIT_TAG, "axllent/mailpit") if mail else None
    java = pinned_local_image(JAVA_TAG, "eclipse-temurin")
    password = secrets.token_hex(24)
    jwt_key = base64.b64encode(secrets.token_bytes(32)).decode()
    app_env = {
        "DB_URL": "jdbc:postgresql://127.0.0.1:5432/bus_pilot", "DB_USERNAME": "postgres",
        "DB_PASSWORD": password, "JWT_SECRET": jwt_key,
        "EMAIL_OTP_SECRET": base64.b64encode(secrets.token_bytes(32)).decode(),
        "BOOTSTRAP_SUPER_ADMIN_ENABLED": "false", "API_DOCS_ENABLED": "false",
        "SERVER_ADDRESS": "127.0.0.1", "JAVA_TOOL_OPTIONS": "-Duser.timezone=Asia/Ho_Chi_Minh",
    }
    if mail:
        app_env.update(SMTP_HOST="127.0.0.1", SMTP_PORT="1025", SMTP_AUTH="false", SMTP_STARTTLS="false")
    try:
        database = command([*docker_args(db_name, run_id, "none"), "-d",
                            "--tmpfs", "/var/lib/postgresql/data", "--env", "POSTGRES_PASSWORD",
                            "--env", "POSTGRES_DB=bus_pilot", postgres],
                           env={**HOST_ENV, "POSTGRES_PASSWORD": password},
                           timeout=30, reason="DATABASE_START_FAILURE").decode().strip()
        if not re.fullmatch(r"[a-f0-9]{64}", database):
            raise ExecutionError("DOCKER_ISOLATION_FAILURE")
        verify_namespace(db_name, "none")
        deadline = time.monotonic() + 35
        while True:
            try:
                command(["docker", "exec", db_name, "pg_isready", "-q", "-h", "127.0.0.1",
                         "-U", "postgres", "-d", "bus_pilot"], timeout=3, reason="DATABASE_NOT_READY")
                break
            except ExecutionError:
                if time.monotonic() >= deadline:
                    raise ExecutionError("DATABASE_NOT_READY") from None
                time.sleep(0.5)

        namespace = "container:" + database
        if mail_image:
            mail_name = f"bus-live-{run_id}-mail"
            command([*docker_args(mail_name, run_id, namespace), "-d", "--cap-drop", "ALL",
                     "--security-opt", "no-new-privileges", mail_image], timeout=30,
                    reason="MAIL_FIXTURE_START_FAILURE")
            verify_namespace(mail_name, namespace)
        command([*docker_args(app_name, run_id, namespace), "-d", "--cap-drop", "ALL",
                 "--security-opt", "no-new-privileges", "--mount", bind(runtime / "app.jar", "/app/app.jar"),
                 *[f"--env={key}" for key in app_env], "--entrypoint", "java", java, "-jar", "/app/app.jar"],
                env={**HOST_ENV, **app_env}, timeout=30, reason="APPLICATION_START_FAILURE")
        verify_namespace(app_name, namespace)
        yield namespace, java, {"DB_PASSWORD": password, "JWT_SECRET": jwt_key}, {
            "javaRuntimeImage": java, "postgresImage": postgres, "namespace": "disconnected-docker-loopback",
            "publishedPorts": 0, "springProfile": "default", "applicationTransport": "http-1.1",
            **({"mailpitImage": mail_image} if mail_image else {}),
        }
    finally:
        # Remove dependants first, including an attached client that exceeded its host deadline.
        listed = command(["docker", "ps", "-a", "--filter", f"label={label}", "--format", "{{.Names}}"],
                         reason="DOCKER_TEARDOWN_FAILURE").decode().splitlines()
        allowed = [f"bus-live-{run_id}-{suffix}" for suffix in ("client", "zap", "app", "mail", "db")]
        if set(listed) - set(allowed):
            raise ExecutionError("DOCKER_TEARDOWN_FAILURE")
        for name in allowed:
            if name in listed:
                command(["docker", "rm", "-f", "-v", name], reason="DOCKER_TEARDOWN_FAILURE")
        if command(["docker", "ps", "-a", "--filter", f"label={label}", "--format", "{{.Names}}"],
                   reason="DOCKER_TEARDOWN_FAILURE").strip():
            raise ExecutionError("DOCKER_TEARDOWN_FAILURE")


def http_receipt(result, namespace, java, credentials, runtime, matrix, working):
    run_id = result["runId"]
    output = working / "receipt"
    output.mkdir()
    env = {**credentials, "BUS_PILOT_MATRIX": "/matrix.txt", "BUS_PILOT_RECEIPT": "/receipt/result.json",
           "BUS_PILOT_RUN_ID": run_id, "JAVA_TOOL_OPTIONS": "-Duser.timezone=Asia/Ho_Chi_Minh"}
    command([*docker_args(f"bus-live-{run_id}-client", run_id, namespace), "--cap-drop", "ALL",
             "--security-opt", "no-new-privileges", "--mount", bind(runtime, "/runtime"),
             "--mount", bind(matrix, "/matrix.txt"), "--mount", bind(output, "/receipt", writable=True),
             *[f"--env={key}" for key in env], "--entrypoint", "java", java,
             "-cp", "/runtime/contract:/runtime/classes:/runtime/BOOT-INF/lib/*",
             "com.example.busbooking.api.BusBookingLiveHttp"], env={**HOST_ENV, **env}, timeout=150,
            reason="LIVE_APPLICATION_PROCESS_FAILURE")
    receipt = output / "result.json"
    if not receipt.is_file():
        raise ExecutionError("MISSING_EVIDENCE")
    return json.loads(receipt.read_text(encoding="utf-8"))


def scanner_receipt(result, namespace, lane):
    run_id = result["runId"]
    image = (ROOT / "zap-image.txt").read_text(encoding="utf-8").strip()
    if not IMAGE_PIN.fullmatch(image):
        raise ExecutionError("SCANNER_IMAGE_UNAVAILABLE")
    result["scannerImage"] = image
    name = f"bus-live-{run_id}-zap"
    # The same disconnected namespace is also verified at the database and backend.
    raw = command([*docker_args(name, run_id, namespace), "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--mount", bind(ROOT, "/suite"),
                   "--env", "PYTHONPATH=/suite", "--entrypoint", "python3", image,
                   "-m", "suites.bus_booking.live.scanner", run_id, lane], timeout=260, reason="SCANNER_PROCESS_FAILURE")
    verify_namespace(name, namespace)
    child = json.loads(raw)
    if (not isinstance(child, dict) or set(child) != {"runId", "reason", "evidence"}
            or child["runId"] != run_id or not isinstance(child["evidence"], dict)
            or (child["reason"] is not None and not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", child["reason"]))):
        raise ExecutionError("INVALID_EVIDENCE")
    for key, record in child["evidence"].items():
        put_evidence(result, key, record["producer"], record["data"])
    if child["reason"]:
        return child["reason"]
    if lane in NATIVE_LANES:
        from .authenticated import verify
        return verify(result)
    return verify_witnesses(result["evidence"])


class LiveAdapter:
    def __init__(self, result, suite, args):
        self.result, self.suite, self.args = result, suite, args

    def prepare(self, resources):
        lane = self.args.lane
        working, project, matrix, expected, provenance = prepare_source(
            resources, self.suite, self.args.project, self.args.revision, prefix="bus-booking-live-")
        runtime, build = build_revision(project, working, lane == "http")
        namespace, java, credentials, deployment = resources.enter_context(
            deployed(self.result["runId"], runtime, mail=lane in NATIVE_LANES))
        put_evidence(self.result, "provenance", "runner", {
            **provenance, **build, **deployment, "testLane": lane,
        })
        return LiveFixture(self.result, lane, working, namespace, java, credentials, runtime, matrix, expected)


@dataclass(frozen=True)
class LiveFixture:
    result: dict
    lane: str
    working: Path
    namespace: str
    java: str
    credentials: dict
    runtime: Path
    matrix: Path
    expected: dict


def observe_http(fixture):
    observation = http_receipt(fixture.result, fixture.namespace, fixture.java, fixture.credentials,
                               fixture.runtime, fixture.matrix, fixture.working)
    return observation, fixture.expected


def observe_passive(fixture):
    return scanner_receipt(fixture.result, fixture.namespace, fixture.lane), fixture.working


LIVE_HTTP = Engine("live-http", APPLICATION, observe_http)
ZAP_PASSIVE = Engine("zap-passive", PASSIVE, observe_passive)


def execute(result, suite, args):
    native = args.lane in NATIVE_LANES
    try:
        adapter = LiveAdapter(result, suite, args)
        if args.lane == "http":
            observed, expected = run_project(suite, LIVE_HTTP, adapter)
            return adjudicate(result, suite, observed, expected, observe_handler=False)
        reason, working = run_project(suite, ZAP_PASSIVE, adapter)
        case_id = NATIVE_CASE_ID if native else CASE_ID
        if native:
            put_evidence(result, "runtimeCleanup", "runner",
                         {"containersRemoved": True, "temporaryDirectoryRemoved": not working.exists()})
        status = (outcome("ERROR", reason) if reason else
                  outcome("PASS", "NATIVE_JWT_PASSIVE_VERIFIED" if native else "PASSIVE_TRANSPORT_VERIFIED"))
        refs = set(suite.cases[case_id]["requiredEvidence"]) & result["evidence"].keys()
        add_check(result, suite, case_id, status, sorted(refs))
        return finish(result)
    except ExecutionError as error:
        return fail_run(result, suite, error.args[0])
    except (OSError, ValueError, TypeError, KeyError, AttributeError, tarfile.TarError, BadZipFile):
        return fail_run(result, suite, "LIVE_EXECUTION_FAILURE")


def checked_result(result, suite):
    try:
        return validate_child(result, suite, result["runId"], result["exitCode"])
    except (ValueError, KeyError, TypeError, AttributeError):
        return fail_run(start(suite, result["runId"]), suite, "INVALID_EVIDENCE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--revision", default="HEAD")
    parser.add_argument("--lane", choices=("http", "passive", *NATIVE_LANES), default="http")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must name a new directory")
    try:
        suite = read_suite("bus_booking", "live-" + args.lane)
        result = checked_result(execute(start(suite, uuid4().hex), suite, args), suite)
        result["executionEnvironment"] = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
        args.out.mkdir(parents=True)
        (args.out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (args.out / "report.md").write_text(markdown(result), encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError):
        print("ERROR SUITE_EVIDENCE_FAILURE", file=sys.stderr)
        return EXIT["ERROR"]
    print(f'{result["verdict"]} {args.out / "result.json"}')
    return result["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
