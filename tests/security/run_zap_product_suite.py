#!/usr/bin/env python3
"""Host-side lifecycle runner for versioned product adapters."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


sys.dont_write_bytecode = True
from byteme_ci_case import ADAPTER as CI_ADAPTER, SHA, validate_case as validate_ci_case


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "product_adapters.json"
IMAGE_PATH = ROOT / "zap-image.txt"
OWNER_LABEL = "io.testing-tool.zap-regression.owner"
ADAPTER_LABEL = "io.testing-tool.zap-regression.adapter"
STATUSES = ("PASS", "REGRESSION", "MISSING_EVIDENCE", "EXECUTION_ERROR")
VARIANTS = ("upstream-original", "fixed-control", "regression-control",
            "anti-csp-none", "anti-no-protection", "anti-report-only",
            "anti-wide-csp-xfo", "anti-malformed")
FAULTS = ("none", "wrong-response", "wrong-status", "wrong-media",
          "startup-failure", "scanner-timeout", "cleanup-failure")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class AdapterError(RuntimeError):
    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


class Cancelled(Exception):
    pass


def cancel(_signum, _frame):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    raise Cancelled("execution interrupted")


def canonical_bytes(value):
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False,
                       allow_nan=False) + "\n").encode("utf-8")


def atomic_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    with temporary.open("wb") as stream:
        stream.write(canonical_bytes(value))
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def sha256_file(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, *, cwd=None, timeout=30, stdout=None, check=True):
    destination = subprocess.PIPE if stdout is None else stdout
    with subprocess.Popen(args, cwd=cwd, stdout=destination,
                          stderr=subprocess.STDOUT if stdout else subprocess.PIPE,
                          text=stdout is None, start_new_session=True) as process:
        try:
            out, err = process.communicate(timeout=timeout)
        except BaseException:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()
            raise
        result = subprocess.CompletedProcess(args, process.returncode, out, err)
        if check:
            result.check_returncode()
        return result


def output(args, *, cwd=None, timeout=30):
    return command(args, cwd=cwd, timeout=timeout).stdout.strip()


def docker_inspect(kind, name, timeout=10):
    result = command(["docker", kind, "inspect", name], timeout=timeout, check=False)
    if result.returncode != 0:
        if (f"No such {kind}:" in result.stderr
                or (kind == "network" and f"network {name} not found" in result.stderr)):
            return None
        raise AdapterError("Docker inspection failed")
    value = json.loads(result.stdout)
    return value[0] if value else None


def labels_of(kind, value):
    if kind == "container":
        return value.get("Config", {}).get("Labels") or {}
    if kind == "network":
        return value.get("Labels") or {}
    if kind == "image":
        return value.get("Config", {}).get("Labels") or {}
    return {}


def validate_case(case, filename):
    if isinstance(case, dict) and case.get("schemaVersion") == 2:
        try:
            return validate_ci_case(case, filename)
        except ValueError as exc:
            raise AdapterError(str(exc), "INVALID_CASE") from exc
    required = {"schemaVersion", "source", "id", "profile", "fixture", "target",
                "requests", "requireResponses", "expect"}
    if not isinstance(case, dict) or set(case) != required:
        raise AdapterError("product case fields are invalid")
    if case["schemaVersion"] != 1 or not SLUG.fullmatch(case["id"]):
        raise AdapterError("product case identity is invalid")
    if filename != case["id"] + ".json":
        raise AdapterError("filename must equal <id>.json")
    if case["source"].get("kind") not in ("product-qualification", "assessment-run-v3"):
        raise AdapterError("product source kind is unsupported")
    if case["profile"] not in ("passive-http-v1", "anti-framing-http-v1") or case["fixture"] != "byteme-v1":
        raise AdapterError("product runner accepts qualified byteme-v1 profiles only")
    target = case["target"]
    if (set(target) != {"adapter", "repository", "commitSha"}
            or target["adapter"] != "byteme-v1"
            or not re.fullmatch(r"[0-9a-f]{40}", target["commitSha"])):
        raise AdapterError("target binding is invalid")
    requests = case["requests"]
    if not isinstance(requests, list) or not requests:
        raise AdapterError("requests are required")
    ids = []
    origins = set()
    for row in requests:
        if (set(row) != {"id", "method", "origin", "path"}
                or not SLUG.fullmatch(row["id"]) or row["method"] != "GET"
                or row["origin"] not in ("product", "detector-control")
                or not isinstance(row["path"], str) or not row["path"].startswith("/")
                or any(token in row["path"] for token in ("?", "#", "\r", "\n", "\\"))
                or any(part in (".", "..") for part in row["path"].split("/"))):
            raise AdapterError("request contract is invalid")
        ids.append(row["id"])
        origins.add(row["origin"])
    required_origins = ({"product", "detector-control"}
                        if case["profile"] == "passive-http-v1" else {"product"})
    if len(ids) != len(set(ids)) or origins != required_origins:
        raise AdapterError("request origins do not match the selected profile")
    expect = case["expect"]
    if not isinstance(expect.get("basis"), str) or not expect["basis"].strip():
        raise AdapterError("expectation basis is invalid")
    if case["profile"] == "passive-http-v1":
        if (set(expect) != {"basis", "alertRef", "presentOn", "absentOn", "requireNonEmptyCspOn"}
                or expect.get("alertRef") != "10038-1"
                or expect.get("presentOn") not in ids or expect.get("absentOn") not in ids
                or expect.get("requireNonEmptyCspOn") not in ids):
            raise AdapterError("CSP expectation contract is invalid")
        if expect["presentOn"] == expect["absentOn"]:
            raise AdapterError("detector control and protected request must differ")
    else:
        if (set(expect) != {"basis", "evaluateOn", "trustedAncestors", "assumption"}
                or expect.get("evaluateOn") not in ids
                or expect.get("trustedAncestors") != ["'self'"]
                or expect.get("assumption") != "modern-user-agent-csp3-html-xfo"):
            raise AdapterError("anti-framing expectation contract is invalid")
    return case


def discover_cases(directory: Path, allow_missing=False):
    if allow_missing and not directory.exists() and not directory.is_symlink():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise AdapterError("cases directory must be a real directory")
    cases = []
    seen = set()
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        if path.is_symlink() or not path.is_file() or path.resolve().parent != directory.resolve():
            raise AdapterError("case path escapes the cases directory")
        try:
            case = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise AdapterError(path.name + " is unreadable: " + type(error).__name__) from None
        validate_case(case, path.name)
        if case["id"] in seen:
            raise AdapterError("duplicate case ID: " + case["id"])
        seen.add(case["id"])
        cases.append(case)
    return cases


def canonical_repository_url(value: str):
    """Normalize only Git's optional .git suffix and trailing slash."""
    normalized = value.rstrip("/")
    if normalized.endswith(".git"):
        normalized = normalized[:-4]
    return normalized


def retained_reference(base: Path, relative: str):
    return relative if (base / relative).is_file() else None


class ByteMeAdapter:
    def __init__(self, case, case_dir: Path, source: Path, variant: str, fault: str,
                 omit_request_id: str | None, deadline: float, run_id: str,
                 retain_native_message: bool = False, expected_product_sha=None,
                 runner_identity=None):
        self.case = case
        self.adapter_id = case["target"]["adapter"]
        self.ci = self.adapter_id == CI_ADAPTER
        self.expected_product_sha = expected_product_sha
        self.runner_identity = runner_identity
        self.actual_sha = None
        self.started = None
        self.timings = {}
        self.case_dir = case_dir
        self.source = source.resolve()
        self.variant = variant
        self.fault = fault
        self.omit_request_id = omit_request_id
        self.deadline = deadline
        self.run_id = run_id
        self.retain_native_message = retain_native_message
        self.short = run_id[:12] + "-" + case["id"][:20]
        self.network = "zap-byteme-" + self.short
        self.db = "zap-byteme-db-" + self.short
        self.backend = "zap-byteme-app-" + self.short
        self.ready = "zap-byteme-ready-" + self.short
        self.scanner = "zap-byteme-scan-" + self.short
        self.image_tag = "testing-tool/byteme-zap:" + self.short
        self.cleanup = []
        self.workspace = None
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["adapters"][self.adapter_id]
        self.zap_image = IMAGE_PATH.read_text(encoding="utf-8").strip()

    def label_args(self):
        return ["--label", OWNER_LABEL + "=" + self.run_id,
                "--label", ADAPTER_LABEL + "=" + self.adapter_id]

    def verify_bindings(self):
        target = self.case["target"]
        if target["repository"] != self.registry["repository"]:
            raise AdapterError("case repository does not match registry", "SOURCE_REPOSITORY_MISMATCH")
        expected = self.expected_product_sha if self.ci else self.registry["commitSha"]
        try:
            root = output(["git", "rev-parse", "--show-toplevel"], cwd=self.source)
            self.actual_sha = output(["git", "rev-parse", "HEAD"], cwd=self.source)
        except (OSError, subprocess.SubprocessError) as exc:
            raise AdapterError("product source must be a Git checkout", "UNSUPPORTED_LAYOUT") from exc
        if Path(root).resolve() != self.source.resolve():
            raise AdapterError("product source must be the Git checkout root", "UNSUPPORTED_LAYOUT")
        if self.actual_sha != expected or (not self.ci and target["commitSha"] != expected):
            raise AdapterError("product checkout does not match expected commit", "SOURCE_SHA_MISMATCH")
        try:
            remote = output(["git", "remote", "get-url", "origin"], cwd=self.source)
        except subprocess.CalledProcessError as exc:
            raise AdapterError("product checkout origin is missing", "SOURCE_REPOSITORY_MISMATCH") from exc
        if canonical_repository_url(remote) != canonical_repository_url(target["repository"]):
            raise AdapterError("product checkout origin does not match target repository",
                               "SOURCE_REPOSITORY_MISMATCH")
        if output(["git", "status", "--porcelain", "--untracked-files=all"], cwd=self.source):
            raise AdapterError("product checkout must be clean", "SOURCE_DIRTY")
        if self.ci:
            for file in self.registry["requiredFiles"]:
                path = self.source / file
                if not path.is_file() or path.resolve() != path:
                    raise AdapterError("required product file is missing or indirect: " + file,
                                       "UNSUPPORTED_LAYOUT")
            if (self.variant != "upstream-original" or self.fault != "none"
                    or self.omit_request_id is not None or self.retain_native_message):
                raise AdapterError("qualification controls are disallowed for event checkout",
                                   "CONTROL_NOT_ALLOWED")
        return self.actual_sha

    def remaining(self, cap):
        if not self.ci:
            return cap
        remaining = self.started + self.deadline - 30 - time.monotonic()
        if remaining <= 0:
            raise TimeoutError("case time budget exhausted")
        return min(cap, remaining)

    def timed(self, stage, action, *args):
        start = time.monotonic()
        try:
            return action(*args)
        finally:
            self.timings[stage] = round(time.monotonic() - start, 3)

    def run_logged(self, filename, args, *, cwd=None, timeout, check=True):
        if not self.ci:
            with (self.case_dir / filename).open("w", encoding="utf-8") as log:
                return command(args, cwd=cwd, timeout=timeout, stdout=log, check=check)
        # PR-controlled build/runtime output can contain arbitrary text. Retain a fixed
        # stage diagnostic and the exit code, never copy subprocess output into CI evidence.
        with (self.case_dir / filename).open("w", encoding="utf-8") as log:
            log.write(f"{filename}: started\n")
            try:
                result = command(args, cwd=cwd, timeout=timeout,
                                 stdout=subprocess.DEVNULL, check=False)
            except subprocess.TimeoutExpired:
                log.write(f"{filename}: deadline exceeded\n")
                raise
            log.write(f"{filename}: exited {result.returncode}\n")
            if check:
                result.check_returncode()
            return result

    def prepare_source(self):
        root = Path(tempfile.mkdtemp(prefix="zap-byteme-adapter-"))
        self.workspace = root / "ByteMe"
        if self.ci:
            files = output(["git", "ls-files", "-z"], cwd=self.source,
                           timeout=self.remaining(30)).split("\0")
            self.workspace.mkdir()
            for name in files:
                if not name:
                    continue
                self.remaining(30)
                source = self.source / name
                destination = self.workspace / name
                if source.is_dir() and not source.is_symlink():
                    raise AdapterError("product submodules are unsupported", "UNSUPPORTED_LAYOUT")
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, destination, follow_symlinks=False)
        else:
            shutil.copytree(self.source, self.workspace, symlinks=True)
        applied = []
        if self.variant in ("fixed-control", "regression-control"):
            fixed = ROOT / self.registry["fixedPatch"]
            command(["git", "apply", "--check", str(fixed)], cwd=self.workspace)
            command(["git", "apply", str(fixed)], cwd=self.workspace)
            applied.append({"path": str(fixed.relative_to(ROOT)), "sha256": sha256_file(fixed)})
        if self.variant == "regression-control":
            regression = ROOT / self.registry["regressionPatch"]
            command(["git", "apply", "--check", str(regression)], cwd=self.workspace)
            command(["git", "apply", str(regression)], cwd=self.workspace)
            applied.append({"path": str(regression.relative_to(ROOT)),
                            "sha256": sha256_file(regression)})
        if self.variant.startswith("anti-"):
            patch_name = self.registry["antiFramingPatches"][self.variant]
            control = ROOT / patch_name
            command(["git", "apply", "--check", str(control)], cwd=self.workspace)
            command(["git", "apply", str(control)], cwd=self.workspace)
            applied.append({"path": str(control.relative_to(ROOT)),
                            "sha256": sha256_file(control)})
        diff = "" if self.ci else output(["git", "diff", "--binary"], cwd=self.workspace)
        key_dir = self.key_dir
        key_dir.mkdir(parents=True, mode=0o755)
        private = key_dir / "private.pem"
        public = key_dir / "public.pem"
        command(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                 "rsa_keygen_bits:2048", "-out", str(private)], timeout=self.remaining(30))
        command(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                timeout=self.remaining(30))
        # The source tree remains below mkdtemp's 0700 parent, while this bind-mounted
        # directory must be traversable by ByteMe's non-host UID (10001) on Linux CI.
        private.chmod(0o444)
        public.chmod(0o644)
        config_files = [
            self.workspace / "Dockerfile",
            self.workspace / "src/main/resources/application.yml",
            self.workspace / "src/main/resources/db/schema.sql",
            self.workspace / "src/main/resources/db/seed.sql",
        ]
        return {
            "appliedPatches": applied,
            "configSha256": {str(path.relative_to(self.workspace)): sha256_file(path)
                             for path in config_files},
            "effectiveDiffSha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
            "generatedKeys": {"algorithm": "RSA", "bits": 2048,
                              "retained": False, "artifactContainsKeyMaterial": False},
        }

    @property
    def key_dir(self):
        if self.ci:
            return self.workspace.parent / "docker-keys"
        return self.workspace / ".local" / "docker-keys"

    def create_network(self):
        args = ["docker", "network", "create", *self.label_args()]
        if self.ci:
            args.append("--internal")
        command([*args, self.network], timeout=self.remaining(30))

    def build_image(self):
        try:
            self.run_logged("build.log",
                            ["docker", "build", *self.label_args(), "--tag", self.image_tag, "."],
                            cwd=self.workspace, timeout=self.remaining(max(600, self.deadline)))
        except subprocess.CalledProcessError as exc:
            raise AdapterError("Docker build exited nonzero", "BUILD_FAILED") from exc
        value = docker_inspect("image", self.image_tag, self.remaining(10))
        if value is None:
            raise AdapterError("built image unavailable", "BUILD_FAILED")
        image = {"id": value["Id"], "repoDigests": value.get("RepoDigests") or []}
        if self.ci:
            base_images = {}
            dockerfile = (self.workspace / "Dockerfile").read_text(encoding="utf-8")
            for reference in re.findall(r"(?im)^FROM\s+([^ \t\r\n]+)", dockerfile):
                if re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_./:@-]+", reference):
                    base = docker_inspect("image", reference, self.remaining(10))
                    if base:
                        base_images[reference] = {"id": base["Id"],
                                                  "repoDigests": base.get("RepoDigests") or []}
            image["locallyObservedBaseImages"] = base_images
        return image

    def start_database(self, password):
        env_file = self.workspace.parent / "mysql.env"
        env_file.write_text("MYSQL_DATABASE=starter\nMYSQL_USER=starter\n"
                            f"MYSQL_PASSWORD={password}\nMYSQL_ROOT_PASSWORD={password}-root\n",
                            encoding="utf-8")
        env_file.chmod(0o600)
        schema = self.workspace / "src/main/resources/db/schema.sql"
        seed = self.workspace / "src/main/resources/db/seed.sql"
        args = ["docker", "run", "-d", "--name", self.db,
                "--network", self.network, "--network-alias", self.registry["databaseAlias"],
                *self.label_args(), "--env-file", str(env_file),
                "--mount", f"type=bind,src={schema},dst=/docker-entrypoint-initdb.d/01-schema.sql,readonly",
                "--mount", f"type=bind,src={seed},dst=/docker-entrypoint-initdb.d/02-seed.sql,readonly",
                "--health-cmd", 'mysqladmin ping -h 127.0.0.1 -uroot -p"$MYSQL_ROOT_PASSWORD" --silent',
                "--health-interval", "2s", "--health-timeout", "5s", "--health-retries", "60",
                "--health-start-period", "10s", self.registry["databaseImage"]]
        output(args, timeout=self.remaining(60))
        deadline = time.monotonic() + self.remaining(min(self.deadline, 180))
        while time.monotonic() < deadline:
            value = docker_inspect("container", self.db, self.remaining(10))
            state = value.get("State", {}) if value else {}
            if state.get("Health", {}).get("Status") == "healthy":
                return
            if state.get("Status") == "exited":
                raise AdapterError("database exited during readiness")
            time.sleep(1)
        raise TimeoutError("database readiness timeout")

    def start_backend(self, password):
        env_file = self.workspace.parent / "backend.env"
        env_file.write_text("DB_URL=jdbc:mysql://mysql:3306/starter\nDB_USERNAME=starter\n"
                            f"DB_PASSWORD={password}\n"
                            "AUTH_JWT_PRIVATE_KEY_FILE=/run/auth/private.pem\n"
                            "AUTH_JWT_PUBLIC_KEY_FILE=/run/auth/public.pem\n",
                            encoding="utf-8")
        env_file.chmod(0o600)
        keys = self.key_dir
        output(["docker", "run", "-d", "--name", self.backend,
                "--network", self.network, "--network-alias", self.registry["backendAlias"],
                *self.label_args(), "--env-file", str(env_file),
                "--mount", f"type=bind,src={keys},dst=/run/auth,readonly", self.image_tag], timeout=self.remaining(60))
        if self.fault == "startup-failure":
            raise AdapterError("INJECTED_STARTUP_FAILURE")
        script = ("import json,time,urllib.request\n"
                  "deadline=time.monotonic()+120\n"
                  "while True:\n"
                  "  try:\n"
                  f"    with urllib.request.urlopen({self.product_origin + self.registry['readinessPath']!r},timeout=3) as r:\n"
                  "      data=json.loads(r.read())\n"
                  "      assert r.status==200 and data.get('status')=='UP'\n"
                  "      break\n"
                  "  except Exception:\n"
                  "    if time.monotonic()>=deadline: raise\n"
                  "    time.sleep(1)\n")
        self.run_logged("readiness.log", [
            "docker", "run", "--name", self.ready, "--network", self.network,
            *self.label_args(), "--entrypoint", "python3", self.zap_image, "-c", script,
        ], timeout=self.remaining(min(self.deadline, 150)))

    @property
    def product_origin(self):
        return f"http://{self.registry['backendAlias']}:{self.registry.get('backendPort', 8080)}"

    def run_scanner(self):
        if (self.retain_native_message
                and self.case["source"]["kind"] != "assessment-run-v3"):
            raise AdapterError("native message retention requires assessment-run-v3 source")
        scan_out = self.case_dir / "scan"
        scan_out.mkdir()
        case_path = self.case_dir / "case.json"
        scanner_deadline = 0.01 if self.fault == "scanner-timeout" else self.remaining(self.deadline)
        if self.ci:
            scanner_deadline = max(0.01, scanner_deadline - 20)
        args = ["docker", "run", "--name", self.scanner, "--network", self.network,
                *self.label_args(), "--user", f"{os.getuid()}:{os.getgid()}",
                "--env", "HOME=/tmp/zap-product-home",
                "--mount", f"type=bind,src={ROOT},dst=/workspace/security,readonly",
                "--mount", f"type=bind,src={case_path},dst=/workspace/case.json,readonly",
                "--mount", f"type=bind,src={scan_out},dst=/zap/wrk/output",
                self.zap_image, "python3",
                "/workspace/security/product/byteme/zap_product_runtime.py",
                "--case", "/workspace/case.json", "--out", "/zap/wrk/output",
                "--product-origin", self.product_origin,
                "--deadline", str(scanner_deadline)]
        if self.omit_request_id:
            args.extend(["--omit-request-id", self.omit_request_id])
        if self.fault in ("wrong-response", "wrong-status", "wrong-media"):
            args.extend(["--fault-mode", self.fault])
        if self.retain_native_message:
            args.append("--retain-native-message")
        try:
            completed = self.run_logged("scanner-container.log", args,
                                        timeout=self.remaining(self.deadline + 60), check=False)
        except subprocess.TimeoutExpired as error:
            raise TimeoutError("scanner container timeout") from error
        result_path = scan_out / "runtime-result.json"
        if not result_path.is_file():
            raise AdapterError("scanner did not retain runtime result")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["containerExit"] = completed.returncode
        return result

    def capture_service_logs(self):
        for name, filename in ((self.db, "database.log"), (self.backend, "backend.log")):
            if docker_inspect("container", name) is None:
                continue
            try:
                with (self.case_dir / filename).open("w", encoding="utf-8") as log:
                    command(["docker", "logs", name], timeout=30, stdout=log, check=False)
            except Exception as exc:
                (self.case_dir / (filename + ".error")).write_text(
                    type(exc).__name__ + ": " + str(exc) + "\n", encoding="utf-8")

    def resolve_image(self, reference):
        value = docker_inspect("image", reference, self.remaining(10))
        if value is None:
            output(["docker", "pull", reference], timeout=self.remaining(300))
            value = docker_inspect("image", reference, self.remaining(10))
        if value is None:
            raise AdapterError("pulled image unavailable")
        return {"id": value["Id"], "repoDigests": value.get("RepoDigests") or [],
                "reference": reference}

    def inventory(self):
        return {
            "owner": self.run_id, "adapter": self.adapter_id,
            "containers": [self.scanner, self.ready, self.backend, self.db],
            "network": self.network, "image": self.image_tag,
        }

    def cleanup_all(self):
        failures = reconcile_inventory(self.inventory(), self.cleanup)
        if self.workspace is not None:
            shutil.rmtree(self.workspace.parent, ignore_errors=False)
        if failures:
            raise AdapterError("owned Docker resources could not be fully reconciled") from failures[0]

    def execute(self):
        case_hash = hashlib.sha256(canonical_bytes(self.case)).hexdigest()
        self.case_dir.mkdir(parents=True, exist_ok=False)
        atomic_json(self.case_dir / "case.json", self.case)
        source_info = None
        image_info = None
        database_info = None
        zap_info = None
        runtime = None
        error = None
        cleanup_error = None
        admitted = False
        self.started = time.monotonic()
        try:
            self.verify_bindings()
            if self.ci:
                atomic_json(self.case_dir / "inventory.json", self.inventory())
            admitted = True
            source_info = self.prepare_source()
            self.create_network()
            image_info = self.timed("build", self.build_image)
            database_info = self.resolve_image(self.registry["databaseImage"])
            if self.ci:
                zap_info = self.resolve_image(self.zap_image)
            password = secrets.token_urlsafe(24)
            self.timed("databaseReadiness", self.start_database, password)
            self.timed("backendReadiness", self.start_backend, password)
            runtime = self.timed("scanner", self.run_scanner)
        except Cancelled:
            error = ("CANCELLED", "execution interrupted")
        except (TimeoutError, subprocess.TimeoutExpired):
            error = ("TIMEOUT", "case time budget exhausted")
        except Exception as exc:
            code = getattr(exc, "code", None)
            error = (code if self.ci and code else "ADAPTER_ERROR:" + type(exc).__name__, str(exc))
            detail = error[0] if self.ci else type(exc).__name__ + ": " + str(exc)
            (self.case_dir / "adapter-error.txt").write_text(detail + "\n", encoding="utf-8")
        finally:
            if admitted:
                if not self.ci:
                    self.capture_service_logs()
                try:
                    self.timed("cleanup", self.cleanup_all)
                except (Exception, Cancelled) as exc:
                    cleanup_error = exc
        if runtime is None:
            runtime = {"status": "EXECUTION_ERROR", "reason": error[0] if error else "UNKNOWN",
                       "nativeExit": None}
        if cleanup_error is not None:
            runtime = {**runtime, "preCleanupStatus": runtime.get("status"),
                       "preCleanupReason": runtime.get("reason"),
                       "status": "EXECUTION_ERROR",
                       "reason": "CLEANUP_ERROR:" + type(cleanup_error).__name__}
        elif self.fault == "cleanup-failure":
            runtime = {**runtime, "preCleanupStatus": runtime.get("status"),
                       "preCleanupReason": runtime.get("reason"),
                       "status": "EXECUTION_ERROR", "reason": "INJECTED_CLEANUP_FAILURE"}
        identity = {
            "adapter": self.adapter_id,
            "adapterRegistrySha256": sha256_file(REGISTRY_PATH),
            "actualCommitSha": self.actual_sha,
            "backendImage": image_info,
            "databaseImage": database_info,
            "expectedCommitSha": self.case["target"].get("commitSha"),
            "repository": self.case["target"]["repository"],
            "sourcePreparation": source_info,
            "variant": self.variant,
        }
        if self.ci:
            del identity["actualCommitSha"], identity["expectedCommitSha"]
            identity.update(testedProductCommitSha=self.actual_sha,
                            expectedProductCommitSha=self.expected_product_sha,
                            reviewedProductCommitSha=self.case["provenance"]["reviewedProductCommitSha"],
                            runnerCommitSha=self.runner_identity["runnerCommitSha"],
                            zapImage=zap_info, databaseImageReference=self.registry["databaseImage"])
        atomic_json(self.case_dir / "target-identity.json", identity)
        atomic_json(self.case_dir / "cleanup.json", {
            "faultInjectedAfterRealCleanup": self.fault == "cleanup-failure",
            "records": self.cleanup,
            "retainedRuntimeSecrets": cleanup_error is not None,
            **({"status": "UNVERIFIED" if cleanup_error else "COMPLETE" if admitted else "NOT_NEEDED"}
               if self.ci else {}),
        })
        result = {
            "adapter": self.adapter_id,
            "caseHash": case_hash,
            "cleanupPath": str((self.case_dir / "cleanup.json").name),
            "evidencePath": retained_reference(self.case_dir, "scan/evidence.json"),
            "id": self.case["id"],
            "reason": runtime["reason"],
            "sourceKind": self.case["source"]["kind"],
            "status": runtime["status"],
            "targetIdentityPath": str((self.case_dir / "target-identity.json").name),
            "variant": self.variant,
            "zapVersion": runtime.get("zapVersion"),
        }
        if self.ci:
            result["reviewedProductCommitSha"] = self.case["provenance"]["reviewedProductCommitSha"]
            result["timingsSeconds"] = {**self.timings,
                                        "total": round(time.monotonic() - self.started, 3)}
        if "preCleanupStatus" in runtime:
            result["preCleanupStatus"] = runtime["preCleanupStatus"]
            result["preCleanupReason"] = runtime.get("preCleanupReason")
        atomic_json(self.case_dir / "result.json", result)
        return result


def cleanup_resource(inventory, records, kind, name, remaining):
    value = docker_inspect(kind, name, remaining())
    if value is None:
        records.append({"kind": kind, "name": name, "state": "absent"})
        return
    labels = labels_of(kind, value)
    if labels.get(OWNER_LABEL) != inventory["owner"] or labels.get(ADAPTER_LABEL) != inventory["adapter"]:
        raise AdapterError("refusing to remove resource without invocation ownership: " + name)
    if kind == "container":
        command(["docker", "rm", "-fv", name], timeout=remaining())
    elif kind == "network":
        command(["docker", "network", "rm", name], timeout=remaining())
    elif kind == "image":
        command(["docker", "image", "rm", name], timeout=remaining())
    if docker_inspect(kind, name, remaining()) is not None:
        raise AdapterError("Docker resource still exists after removal")
    records.append({"kind": kind, "name": name, "state": "removed"})



def reconcile_inventory(inventory, records):
    deadline = time.monotonic() + 25

    def remaining():
        budget = deadline - time.monotonic()
        if budget <= 0:
            raise TimeoutError("cleanup deadline exceeded")
        return min(5, budget)

    failures = []
    for kind, names in (("container", inventory["containers"]),
                        ("network", [inventory["network"]]), ("image", [inventory["image"]])):
        for name in names:
            try:
                cleanup_resource(inventory, records, kind, name, remaining)
            except Exception as exc:
                records.append({"kind": kind, "name": name, "state": "unverified"})
                failures.append(exc)
    return failures


def suite_result(run_id, cases, suite_error=None, identity=None, tested_sha=None):
    counts = {status: 0 for status in STATUSES}
    for case in cases:
        counts[case["status"]] += 1
    value = {
        "caseCount": len(cases),
        "cases": cases,
        "counts": counts,
        "imageDigest": IMAGE_PATH.read_text(encoding="utf-8").strip().split("@", 1)[-1],
        "runId": run_id,
        "schemaVersion": 1,
        "status": ("ERROR" if suite_error else "EMPTY" if not cases else
                   "PASS" if counts["PASS"] == len(cases) else "FAIL"),
    }
    if suite_error:
        value["suiteError"] = suite_error
    if identity is not None:
        value.update(identity, schemaVersion=2, testedProductCommitSha=tested_sha)
    else:
        value.update(testedCommitSha=tested_sha or "local",
                     pullRequestHeadSha=os.environ.get("REGRESSION_PR_HEAD_SHA")
                     or os.environ.get("PULL_REQUEST_HEAD_SHA") or None)
    return value


def git_head(path):
    try:
        return output(["git", "rev-parse", "HEAD"], cwd=path)
    except (OSError, subprocess.SubprocessError):
        return None


def runner_identity(expected_sha):
    runner_sha = git_head(ROOT)
    return {
        "expectedProductCommitSha": expected_sha,
        "runnerCommitSha": runner_sha,
        "pullRequestHeadSha": os.environ.get("REGRESSION_PR_HEAD_SHA") or None,
        "pullRequestBaseSha": os.environ.get("REGRESSION_PR_BASE_SHA") or None,
        "github": {
            "repository": os.environ.get("GITHUB_REPOSITORY") or None,
            "runId": os.environ.get("GITHUB_RUN_ID") or None,
            "runAttempt": os.environ.get("GITHUB_RUN_ATTEMPT") or None,
            "event": os.environ.get("GITHUB_EVENT_NAME") or None,
        },
        "adapterRegistrySha256": sha256_file(REGISTRY_PATH),
        "runnerSha256": sha256_file(Path(__file__)),
    }


def event_admission(args, cases, source, out_dir, identity):
    pins = [sha for sha in (args.expected_product_sha, os.environ.get("EXPECTED_PRODUCT_SHA"),
                             os.environ.get("REGRESSION_TESTED_COMMIT_SHA"),
                             os.environ.get("GITHUB_SHA")) if sha is not None]
    if (not args.expected_product_sha or not SHA.fullmatch(args.expected_product_sha)
            or len(set(pins)) != 1):
        raise AdapterError("explicit product SHA is required and must agree with event metadata",
                           "SOURCE_SHA_MISMATCH")
    runner_pin = os.environ.get("EXPECTED_RUNNER_SHA")
    if (runner_pin is not None and (not SHA.fullmatch(runner_pin)
                                   or identity["runnerCommitSha"] != runner_pin)):
        raise AdapterError("runtime checkout does not match workflow pin", "RUNNER_SHA_MISMATCH")
    if not identity["runnerCommitSha"]:
        raise AdapterError("runtime Git checkout is required", "UNSUPPORTED_LAYOUT")
    if runner_pin is not None and output(["git", "status", "--porcelain"], cwd=ROOT):
        raise AdapterError("runtime Git checkout must be clean", "RUNNER_DIRTY")
    runner_root = Path(output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT)).resolve()
    if (out_dir.is_relative_to(source) or out_dir.is_relative_to(runner_root)
            or runner_root.is_relative_to(source) or source.is_relative_to(runner_root)):
        raise AdapterError("product and runner must be separate with output outside both",
                           "UNSUPPORTED_LAYOUT")
    if any(case["schemaVersion"] != 2 for case in cases):
        raise AdapterError("event checkout requires v2 cases", "INVALID_CASE")
    if not math.isfinite(args.deadline) or args.deadline <= 30:
        raise AdapterError("case deadline must include the 30-second cleanup reserve",
                           "INVALID_DEADLINE")


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--product-source", required=True)
    parser.add_argument("--expected-product-sha")
    parser.add_argument("--require-cases", action="store_true")
    parser.add_argument("--variant", choices=VARIANTS, default="upstream-original")
    parser.add_argument("--fault-mode", choices=FAULTS, default="none")
    parser.add_argument("--omit-request-id")
    parser.add_argument("--retain-native-message", action="store_true")
    parser.add_argument("--deadline", type=float, default=240.0)
    args = parser.parse_args(argv)
    signal.signal(signal.SIGTERM, cancel)
    signal.signal(signal.SIGINT, cancel)
    source = Path(args.product_source).resolve()
    cases_dir = Path(args.cases).absolute()
    out_dir = Path(args.out).resolve()
    ci = args.expected_product_sha is not None or "EXPECTED_PRODUCT_SHA" in os.environ
    if ci:
        runner_root = Path(output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT)).resolve()
        if out_dir.is_relative_to(source) or out_dir.is_relative_to(runner_root):
            print("event-checkout output must be outside both checkouts", file=sys.stderr)
            return 2
    if out_dir.exists() and (not out_dir.is_dir() or any(out_dir.iterdir())):
        print("output directory must be new or empty", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    results = []
    suite_error = None
    identity = runner_identity(args.expected_product_sha)
    tested_sha = git_head(source)
    try:
        try:
            cases = discover_cases(cases_dir, allow_missing=ci and args.require_cases)
        except (AdapterError, TypeError, ValueError, AttributeError) as exc:
            raise AdapterError("invalid case discovery or case contract", "INVALID_CASE") from exc
        ci = ci or any(case["schemaVersion"] == 2 for case in cases)
        if args.require_cases and not cases:
            raise AdapterError("no regression cases found", "EMPTY_SUITE")
        if ci:
            event_admission(args, cases, source, out_dir, identity)
        for case in cases:
            adapter = ByteMeAdapter(case, out_dir / case["id"], source,
                                    args.variant, args.fault_mode, args.omit_request_id,
                                    args.deadline, run_id + "-" + uuid.uuid4().hex[:8],
                                    args.retain_native_message, args.expected_product_sha, identity)
            results.append(adapter.execute())
            if ci and adapter.actual_sha is not None:
                tested_sha = adapter.actual_sha
            if results[-1]["reason"] == "CANCELLED":
                break
    except (Exception, Cancelled) as error:
        suite_error = ({"code": getattr(error, "code", None) or "EXECUTION_ERROR"}
                       if ci or args.require_cases else str(error))
    suite = suite_result(run_id, results, suite_error, identity if ci else None, tested_sha)
    atomic_json(out_dir / "suite-results.json", suite)
    atomic_json(out_dir / "run-metadata.json", {
        **(identity if ci else {k: identity[k] for k in ("adapterRegistrySha256", "runnerSha256")}),
        "runId": run_id,
    })
    return 0 if suite["status"] in ("PASS", "EMPTY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
