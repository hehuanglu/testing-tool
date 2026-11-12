#!/usr/bin/env python3
"""Host-side lifecycle runner for versioned product adapters."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / "product_adapters.json"
IMAGE_PATH = ROOT / "zap-image.txt"
OWNER_LABEL = "io.testing-tool.zap-regression.owner"
ADAPTER_LABEL = "io.testing-tool.zap-regression.adapter"
STATUSES = ("PASS", "REGRESSION", "MISSING_EVIDENCE", "EXECUTION_ERROR")
VARIANTS = ("upstream-original", "fixed-control", "regression-control")
FAULTS = ("none", "wrong-response", "startup-failure", "scanner-timeout", "cleanup-failure")
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


class AdapterError(RuntimeError):
    pass


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
    return subprocess.run(args, cwd=cwd, timeout=timeout, stdout=destination,
                          stderr=subprocess.STDOUT if stdout else subprocess.PIPE,
                          text=stdout is None, check=check)


def output(args, *, cwd=None, timeout=30):
    return command(args, cwd=cwd, timeout=timeout).stdout.strip()


def docker_inspect(kind, name):
    result = subprocess.run(["docker", kind, "inspect", name], capture_output=True, text=True)
    if result.returncode != 0:
        return None
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
    if case["profile"] != "passive-http-v1" or case["fixture"] != "byteme-v1":
        raise AdapterError("product runner accepts byteme-v1 passive-http-v1 only")
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
    if len(ids) != len(set(ids)) or origins != {"product", "detector-control"}:
        raise AdapterError("unique product and detector-control requests are required")
    expect = case["expect"]
    if (expect.get("alertRef") != "10038-1"
            or expect.get("presentOn") not in ids or expect.get("absentOn") not in ids
            or expect.get("requireNonEmptyCspOn") not in ids
            or not isinstance(expect.get("basis"), str) or not expect["basis"].strip()):
        raise AdapterError("expectation contract is invalid")
    if expect["presentOn"] == expect["absentOn"]:
        raise AdapterError("detector control and protected request must differ")
    return case


def discover_cases(directory: Path):
    if directory.is_symlink() or not directory.is_dir():
        raise AdapterError("cases directory must be a real directory")
    cases = []
    seen = set()
    for path in sorted(directory.glob("*.json"), key=lambda item: item.name):
        if path.is_symlink() or path.resolve().parent != directory.resolve():
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
                 omit_request_id: str | None, deadline: float, run_id: str):
        self.case = case
        self.case_dir = case_dir
        self.source = source
        self.variant = variant
        self.fault = fault
        self.omit_request_id = omit_request_id
        self.deadline = deadline
        self.run_id = run_id
        self.short = run_id[:12] + "-" + case["id"][:20]
        self.network = "zap-byteme-" + self.short
        self.db = "zap-byteme-db-" + self.short
        self.backend = "zap-byteme-app-" + self.short
        self.ready = "zap-byteme-ready-" + self.short
        self.scanner = "zap-byteme-scan-" + self.short
        self.image_tag = "testing-tool/byteme-zap:" + self.short
        self.resources = []
        self.cleanup = []
        self.workspace = None
        self.registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))["adapters"]["byteme-v1"]
        self.zap_image = IMAGE_PATH.read_text(encoding="utf-8").strip()

    def label_args(self):
        return ["--label", OWNER_LABEL + "=" + self.run_id,
                "--label", ADAPTER_LABEL + "=byteme-v1"]

    def verify_bindings(self):
        target = self.case["target"]
        if (target["repository"] != self.registry["repository"]
                or target["commitSha"] != self.registry["commitSha"]
                or target["adapter"] != "byteme-v1"):
            raise AdapterError("case target does not match the controlled adapter registry")
        actual = output(["git", "rev-parse", "HEAD"], cwd=self.source)
        dirty = output(["git", "status", "--porcelain"], cwd=self.source)
        remote = output(["git", "remote", "get-url", "origin"], cwd=self.source)
        if actual != target["commitSha"]:
            raise AdapterError("product checkout does not match pinned commit")
        if dirty:
            raise AdapterError("product checkout must be clean")
        if canonical_repository_url(remote) != canonical_repository_url(target["repository"]):
            raise AdapterError("product checkout origin does not match target repository")
        return actual

    def prepare_source(self):
        root = Path(tempfile.mkdtemp(prefix="zap-byteme-adapter-"))
        self.workspace = root / "ByteMe"
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
        diff = output(["git", "diff", "--binary"], cwd=self.workspace)
        key_dir = self.workspace / ".local" / "docker-keys"
        key_dir.mkdir(parents=True, mode=0o755)
        private = key_dir / "private.pem"
        public = key_dir / "public.pem"
        command(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt",
                 "rsa_keygen_bits:2048", "-out", str(private)], timeout=30)
        command(["openssl", "pkey", "-in", str(private), "-pubout", "-out", str(public)],
                timeout=30)
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

    def create_network(self):
        command(["docker", "network", "create", *self.label_args(), self.network])
        self.resources.append({"kind": "network", "name": self.network})

    def build_image(self):
        with (self.case_dir / "build.log").open("w", encoding="utf-8") as log:
            command(["docker", "build", *self.label_args(), "--tag", self.image_tag, "."],
                    cwd=self.workspace, timeout=max(600, self.deadline), stdout=log)
        self.resources.append({"kind": "image", "name": self.image_tag})
        value = docker_inspect("image", self.image_tag)
        return {"id": value["Id"], "repoDigests": value.get("RepoDigests") or []}

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
        output(args, timeout=60)
        self.resources.append({"kind": "container", "name": self.db})
        deadline = time.monotonic() + min(self.deadline, 180)
        while time.monotonic() < deadline:
            value = docker_inspect("container", self.db)
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
        keys = self.workspace / ".local" / "docker-keys"
        output(["docker", "run", "-d", "--name", self.backend,
                "--network", self.network, "--network-alias", self.registry["backendAlias"],
                *self.label_args(), "--env-file", str(env_file),
                "--mount", f"type=bind,src={keys},dst=/run/auth,readonly", self.image_tag], timeout=60)
        self.resources.append({"kind": "container", "name": self.backend})
        if self.fault == "startup-failure":
            raise AdapterError("INJECTED_STARTUP_FAILURE")
        script = ("import json,time,urllib.request\n"
                  "deadline=time.monotonic()+120\n"
                  "while True:\n"
                  "  try:\n"
                  "    with urllib.request.urlopen('http://byteme-backend:8080/actuator/health',timeout=3) as r:\n"
                  "      data=json.loads(r.read())\n"
                  "      assert r.status==200 and data.get('status')=='UP'\n"
                  "      break\n"
                  "  except Exception:\n"
                  "    if time.monotonic()>=deadline: raise\n"
                  "    time.sleep(1)\n")
        with (self.case_dir / "readiness.log").open("w", encoding="utf-8") as log:
            command(["docker", "run", "--name", self.ready, "--network", self.network,
                     *self.label_args(), "--entrypoint", "python3", self.zap_image,
                     "-c", script], timeout=min(self.deadline, 150), stdout=log)
        self.resources.append({"kind": "container", "name": self.ready})

    def run_scanner(self):
        scan_out = self.case_dir / "scan"
        scan_out.mkdir()
        case_path = self.case_dir / "case.json"
        scanner_deadline = 0.01 if self.fault == "scanner-timeout" else self.deadline
        args = ["docker", "run", "--name", self.scanner, "--network", self.network,
                *self.label_args(), "--user", f"{os.getuid()}:{os.getgid()}",
                "--env", "HOME=/tmp/zap-product-home",
                "--mount", f"type=bind,src={ROOT},dst=/workspace/security,readonly",
                "--mount", f"type=bind,src={case_path},dst=/workspace/case.json,readonly",
                "--mount", f"type=bind,src={scan_out},dst=/zap/wrk/output",
                self.zap_image, "python3",
                "/workspace/security/product/byteme/zap_product_runtime.py",
                "--case", "/workspace/case.json", "--out", "/zap/wrk/output",
                "--product-origin", "http://byteme-backend:8080",
                "--deadline", str(scanner_deadline)]
        if self.omit_request_id:
            args.extend(["--omit-request-id", self.omit_request_id])
        if self.fault == "wrong-response":
            args.extend(["--fault-mode", "wrong-response"])
        with (self.case_dir / "scanner-container.log").open("w", encoding="utf-8") as log:
            try:
                completed = command(args, timeout=self.deadline + 60, stdout=log, check=False)
            except subprocess.TimeoutExpired as error:
                raise TimeoutError("scanner container timeout") from error
        self.resources.append({"kind": "container", "name": self.scanner})
        result_path = scan_out / "runtime-result.json"
        if not result_path.is_file():
            raise AdapterError("scanner did not retain runtime result")
        result = json.loads(result_path.read_text(encoding="utf-8"))
        result["containerExit"] = completed.returncode
        return result

    def cleanup_resource(self, kind, name):
        value = docker_inspect(kind, name)
        if value is None:
            self.cleanup.append({"kind": kind, "name": name, "state": "absent"})
            return
        if labels_of(kind, value).get(OWNER_LABEL) != self.run_id:
            raise AdapterError("refusing to remove resource without invocation ownership: " + name)
        if kind == "container":
            command(["docker", "rm", "-f", name], timeout=30)
        elif kind == "network":
            command(["docker", "network", "rm", name], timeout=30)
        elif kind == "image":
            command(["docker", "image", "rm", name], timeout=60)
        self.cleanup.append({"kind": kind, "name": name, "state": "removed"})

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

    def cleanup_all(self):
        for name in (self.scanner, self.ready, self.backend, self.db):
            self.cleanup_resource("container", name)
        self.cleanup_resource("network", self.network)
        self.cleanup_resource("image", self.image_tag)
        if self.workspace is not None:
            shutil.rmtree(self.workspace.parent, ignore_errors=False)

    def execute(self):
        case_hash = hashlib.sha256(canonical_bytes(self.case)).hexdigest()
        self.case_dir.mkdir(parents=True, exist_ok=False)
        atomic_json(self.case_dir / "case.json", self.case)
        actual_sha = None
        source_info = None
        image_info = None
        database_info = None
        runtime = None
        error = None
        cleanup_error = None
        try:
            actual_sha = self.verify_bindings()
            source_info = self.prepare_source()
            self.create_network()
            image_info = self.build_image()
            database_value = docker_inspect("image", self.registry["databaseImage"])
            if database_value is None:
                output(["docker", "pull", self.registry["databaseImage"]], timeout=300)
                database_value = docker_inspect("image", self.registry["databaseImage"])
            database_info = {"id": database_value["Id"],
                             "repoDigests": database_value.get("RepoDigests") or []}
            password = secrets.token_urlsafe(24)
            self.start_database(password)
            self.start_backend(password)
            runtime = self.run_scanner()
        except TimeoutError as exc:
            error = ("TIMEOUT", str(exc))
        except Exception as exc:
            error = ("ADAPTER_ERROR:" + type(exc).__name__, str(exc))
            (self.case_dir / "adapter-error.txt").write_text(type(exc).__name__ + ": " + str(exc) + "\n",
                                                              encoding="utf-8")
        finally:
            self.capture_service_logs()
            try:
                self.cleanup_all()
            except Exception as exc:
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
            "adapter": "byteme-v1",
            "adapterRegistrySha256": sha256_file(REGISTRY_PATH),
            "actualCommitSha": actual_sha,
            "backendImage": image_info,
            "databaseImage": database_info,
            "expectedCommitSha": self.case["target"]["commitSha"],
            "repository": self.case["target"]["repository"],
            "sourcePreparation": source_info,
            "variant": self.variant,
        }
        atomic_json(self.case_dir / "target-identity.json", identity)
        atomic_json(self.case_dir / "cleanup.json", {
            "faultInjectedAfterRealCleanup": self.fault == "cleanup-failure",
            "records": self.cleanup,
            "retainedRuntimeSecrets": False,
        })
        result = {
            "adapter": "byteme-v1",
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
        if "preCleanupStatus" in runtime:
            result["preCleanupStatus"] = runtime["preCleanupStatus"]
            result["preCleanupReason"] = runtime.get("preCleanupReason")
        atomic_json(self.case_dir / "result.json", result)
        return result


def suite_result(run_id, cases, suite_error=None):
    counts = {status: 0 for status in STATUSES}
    for case in cases:
        counts[case["status"]] += 1
    value = {
        "caseCount": len(cases),
        "cases": cases,
        "counts": counts,
        "imageDigest": IMAGE_PATH.read_text(encoding="utf-8").strip().split("@", 1)[-1],
        "pullRequestHeadSha": os.environ.get("PULL_REQUEST_HEAD_SHA") or None,
        "runId": run_id,
        "schemaVersion": 1,
        "status": ("ERROR" if suite_error else "EMPTY" if not cases else
                   "PASS" if counts["PASS"] == len(cases) else "FAIL"),
        "testedCommitSha": os.environ.get("TESTED_COMMIT_SHA", "local"),
    }
    if suite_error:
        value["suiteError"] = suite_error
    return value


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--product-source", required=True)
    parser.add_argument("--variant", choices=VARIANTS, default="fixed-control")
    parser.add_argument("--fault-mode", choices=FAULTS, default="none")
    parser.add_argument("--omit-request-id")
    parser.add_argument("--deadline", type=float, default=240.0)
    args = parser.parse_args(argv)
    out_dir = Path(args.out).resolve()
    if out_dir.exists() and any(out_dir.iterdir()):
        print("output directory must be new or empty", file=sys.stderr)
        return 2
    out_dir.mkdir(parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    results = []
    try:
        cases = discover_cases(Path(args.cases).resolve())
        for case in cases:
            adapter = ByteMeAdapter(case, out_dir / case["id"], Path(args.product_source).resolve(),
                                    args.variant, args.fault_mode, args.omit_request_id,
                                    args.deadline, run_id + "-" + uuid.uuid4().hex[:8])
            results.append(adapter.execute())
        suite = suite_result(run_id, results)
    except Exception as error:
        suite = suite_result(run_id, results, str(error))
    atomic_json(out_dir / "suite-results.json", suite)
    atomic_json(out_dir / "run-metadata.json", {
        "adapterRegistrySha256": sha256_file(REGISTRY_PATH),
        "runnerSha256": sha256_file(Path(__file__)),
        "runId": run_id,
    })
    return 0 if suite["status"] in ("PASS", "EMPTY") else 1


if __name__ == "__main__":
    raise SystemExit(main())
