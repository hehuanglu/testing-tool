"""Suite-local launcher for an in-process Spring/JWT authorization contract test."""

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
import time
from uuid import uuid4

from security_framework.evidence import EXIT, fail_run, markdown, put_evidence, start, validate_child
from security_framework.manifest import read_suite

from .assertions.oracle import adjudicate, matrix_plan

DIRECTORY = Path(__file__).resolve().parent
JAVA_TEST = "BusBookingAuthorizationPilotTest"
FIXTURE = DIRECTORY / "fixtures" / f"{JAVA_TEST}.java"
MATRIX = DIRECTORY / "plans/authorization-matrix.txt"
MATRIX_INPUT = "suites/bus_booking/plans/authorization-matrix.txt"
PG_TAG = "postgres:16-alpine"
REVISION = re.compile(r"[0-9a-f]{40}\Z")
DIGEST = re.compile(r"postgres@sha256:[0-9a-f]{64}\Z")
METHODS = {"get", "post", "put", "delete", "patch", "head", "options", "trace"}
HOST_ENV = {
    key: value for key, value in os.environ.items()
    if key in {"HOME", "PATH", "JAVA_HOME", "TMPDIR", "LANG", "LC_ALL", "USERPROFILE", "SYSTEMROOT"}
}


class ExecutionError(Exception):
    """A stable classification whose arguments contain no raw subprocess output."""


def command(args, *, cwd=None, env=None, timeout=20, reason="INFRASTRUCTURE_FAILURE"):
    try:
        with subprocess.Popen(args, cwd=cwd, env=HOST_ENV if env is None else env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True) as process:
            try:
                stdout, _ = process.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.communicate()
                raise ExecutionError("PROCESS_TIMEOUT") from None
            if process.returncode:
                raise ExecutionError(reason)
            return stdout
    except OSError:
        raise ExecutionError(reason) from None


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_project(repository, revision, destination):
    git = ["git", "-C", str(repository)]
    rev = command([*git, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"],
                  reason="PROJECT_SOURCE_UNAVAILABLE").decode().strip()
    if not REVISION.fullmatch(rev):
        raise ExecutionError("PROJECT_SOURCE_UNAVAILABLE")
    archive = command([*git, "archive", "--format=tar", rev], reason="PROJECT_SOURCE_UNAVAILABLE")
    with tarfile.open(fileobj=io.BytesIO(archive)) as snapshot:
        if any(not (member.isfile() or member.isdir()) for member in snapshot):
            raise ExecutionError("UNSUPPORTED_PROJECT_ARCHIVE")
        snapshot.extractall(destination, filter="data")
    return rev


def verify_contract(project, matrix):
    openapi = project / "docs/openapi.json"
    design = project / "docs/04-api-design.md"
    pom = project / "pom.xml"
    try:
        document = json.loads(openapi.read_text(encoding="utf-8"))
        published = {(method.upper(), path) for path, item in document["paths"].items()
                     if path.startswith("/api/") for method in item if method in METHODS}
        if matrix != published or not design.is_file() or not pom.is_file():
            raise ExecutionError("CONTRACT_INVENTORY_MISMATCH")
        return {"openApiSha256": sha256(openapi), "designSha256": sha256(design), "pomSha256": sha256(pom)}
    except (OSError, ValueError, KeyError, TypeError):
        raise ExecutionError("PROJECT_CONTRACT_UNAVAILABLE") from None


@contextmanager
def database(run_id):
    entries = command(["docker", "image", "inspect", "--format", "{{json .RepoDigests}}", PG_TAG],
                      reason="DATABASE_IMAGE_UNAVAILABLE")
    pins = [item for item in json.loads(entries) if DIGEST.fullmatch(item)]
    if not pins:
        raise ExecutionError("DATABASE_IMAGE_UNAVAILABLE")
    image = pins[0]
    name = "bus-booking-pilot-" + run_id
    password = secrets.token_hex(24)
    env = {**HOST_ENV, "POSTGRES_PASSWORD": password}
    try:
        command(["docker", "run", "-d", "--name", name, "--label", "bus-booking-pilot=" + run_id,
                 "--pull", "never", "--publish", "127.0.0.1::5432", "--tmpfs", "/var/lib/postgresql/data",
                 "--env", "POSTGRES_PASSWORD", "--env", "POSTGRES_DB=bus_pilot", image], env=env,
                timeout=30, reason="DATABASE_START_FAILURE")
        endpoint = command(["docker", "port", name, "5432/tcp"]).decode().strip()
        if not re.fullmatch(r"127\.0\.0\.1:[0-9]{1,5}", endpoint):
            raise ExecutionError("DATABASE_ISOLATION_FAILURE")
        deadline = time.monotonic() + 35
        while True:
            try:
                command(["docker", "exec", name, "pg_isready", "-q", "-h", "127.0.0.1", "-U", "postgres",
                         "-d", "bus_pilot"], timeout=3, reason="DATABASE_NOT_READY")
                break
            except ExecutionError:
                if time.monotonic() >= deadline:
                    raise ExecutionError("DATABASE_NOT_READY") from None
                time.sleep(0.5)
        version = command(["docker", "exec", name, "postgres", "--version"]).decode().strip()
        if not re.fullmatch(r"postgres \(PostgreSQL\) [0-9.]+", version):
            raise ExecutionError("DATABASE_VERSION_UNAVAILABLE")
        yield image, version, {
            "TEST_DB_URL": f"jdbc:postgresql://{endpoint}/bus_pilot",
            "TEST_DB_USERNAME": "postgres",
            "TEST_DB_PASSWORD": password,
        }
    finally:
        # A failed start can still leave a container. Remove only this invocation's labeled fixture.
        listed = command(["docker", "ps", "-aq", "--filter", "label=bus-booking-pilot=" + run_id],
                         reason="DATABASE_TEARDOWN_FAILURE").decode().strip()
        if listed:
            if not re.fullmatch(r"[0-9a-f]{12,64}", listed):
                raise ExecutionError("DATABASE_TEARDOWN_FAILURE")
            command(["docker", "rm", "-f", "-v", listed], reason="DATABASE_TEARDOWN_FAILURE")


def cached_maven(project):
    properties = (project / ".mvn/wrapper/maven-wrapper.properties").read_text(encoding="utf-8")
    distribution = re.search(
        r"^distributionUrl=(https://repo\.maven\.apache\.org/maven2/org/apache/maven/apache-maven/"
        r"[0-9.]+/(apache-maven-([0-9.]+))-bin\.zip)$", properties, re.MULTILINE,
    )
    if not distribution:
        raise ExecutionError("MAVEN_WRAPPER_UNSUPPORTED")
    root = Path.home() / ".m2/wrapper/dists" / distribution[2]
    for marker in sorted(root.glob("*/mvnw.url")):
        binary = marker.parent / "bin/mvn"
        if binary.is_file() and marker.read_text(encoding="utf-8").strip() == distribution[1]:
            return binary, distribution[3]
    raise ExecutionError("MAVEN_WRAPPER_CACHE_UNAVAILABLE")


def read_application(project, working, result, database_env, maven, matrix):
    dest = project / "src/test/java/com/example/busbooking/api" / FIXTURE.name
    if dest.exists():
        raise ExecutionError("FIXTURE_PATH_CONFLICT")
    dest.write_bytes((working / FIXTURE.name).read_bytes())
    receipt = working / "application-receipt.json"
    env = {**HOST_ENV, **database_env, "BUS_PILOT_MATRIX": str(matrix),
           "BUS_PILOT_RECEIPT": str(receipt), "BUS_PILOT_RUN_ID": result["runId"]}
    command([str(maven), "-o", "-B", "-q", "-Dtest=" + JAVA_TEST, "test"], cwd=project, env=env,
            timeout=180, reason="APPLICATION_TEST_PROCESS_FAILURE")
    if not receipt.is_file():
        raise ExecutionError("MISSING_EVIDENCE")
    try:
        return json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ExecutionError("INVALID_EVIDENCE") from None


def run_application(suite, result, repository, revision):
    try:
        with TemporaryDirectory(prefix="bus-booking-pilot-") as temporary:
            working = Path(temporary)
            project = working / "app"
            project.mkdir()
            source = export_project(repository, revision, project)
            matrix = working / MATRIX.name
            shutil.copyfile(MATRIX, matrix)
            if sha256(matrix) != suite.inputs[MATRIX_INPUT]:
                raise ExecutionError("MATRIX_INPUT_CHANGED")
            fixture = working / FIXTURE.name
            shutil.copyfile(FIXTURE, fixture)
            inventory, expected = matrix_plan(matrix)
            contract = verify_contract(project, inventory)
            if not HOST_ENV.get("JAVA_HOME"):
                raise ExecutionError("JAVA_HOME_REQUIRED")
            release = Path(HOST_ENV["JAVA_HOME"]) / "release"
            java_version = re.search(r'^JAVA_VERSION="([0-9.]+)"$', release.read_text(), re.MULTILINE)
            if not java_version or not java_version.group(1).startswith("21."):
                raise ExecutionError("JAVA_21_REQUIRED")
            maven, maven_version = cached_maven(project)
            with database(result["runId"]) as (image, database_version, env):
                put_evidence(result, "provenance", "runner", {
                    **contract, "projectCommit": source, "authorizationFixtureSha256": sha256(fixture),
                    "javaVersion": java_version.group(1), "mavenWrapperVersion": maven_version, "postgresImage": image,
                    "postgresVersion": database_version, "applicationTransport": "mockmvc-in-process",
                    "databaseBinding": "ephemeral-loopback", "scannerDispatched": False,
                })
                observation = read_application(project, working, result, env, maven, matrix)
            return adjudicate(result, suite, observation, expected)
    except ExecutionError as error:
        return fail_run(result, suite, error.args[0])
    except (OSError, ValueError, TypeError, KeyError, tarfile.TarError):
        return fail_run(result, suite, "SUITE_EXECUTION_FAILURE")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path, help="local Bus Booking Git checkout")
    parser.add_argument("--revision", default="HEAD", help="committed application revision")
    parser.add_argument("--out", type=Path, required=True, help="new evidence directory")
    args = parser.parse_args()
    if args.out.exists():
        parser.error("--out must name a new directory")
    try:
        suite = read_suite("bus_booking", "baseline")
        result = run_application(suite, start(suite, uuid4().hex), args.project, args.revision)
        validate_child(result, suite, result["runId"], result["exitCode"])
        result["executionEnvironment"] = "github-actions" if os.environ.get("GITHUB_ACTIONS") == "true" else "local"
        args.out.mkdir(parents=True)
        (args.out / "report.md").write_text(markdown(result), encoding="utf-8")
        (args.out / "result.json").write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    except (OSError, ValueError, TypeError, KeyError):
        print("ERROR SUITE_EVIDENCE_FAILURE", file=sys.stderr)
        return EXIT["ERROR"]
    print(f'{result["verdict"]} {args.out / "result.json"}')
    return result["exitCode"]


if __name__ == "__main__":
    sys.exit(main())
