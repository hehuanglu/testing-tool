"""Materialize reviewed committed sources into an adapter-owned directory."""

import io
from pathlib import Path
import re
import tarfile
from tempfile import TemporaryDirectory

from .execution import ExecutionError


COMMIT = re.compile(r"[0-9a-f]{40}\Z")


def materialize(resources, repository, revision, *, prefix, command):
    working = Path(resources.enter_context(TemporaryDirectory(prefix=prefix)))
    project = working / "app"
    project.mkdir()
    commit = export_project(repository, revision, project, command=command)
    return working, project, commit


def export_project(repository, revision, destination, *, command):
    git = ["git", "-C", str(repository)]
    commit = command([*git, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}"],
                     reason="PROJECT_SOURCE_UNAVAILABLE").decode().strip()
    if not COMMIT.fullmatch(commit):
        raise ExecutionError("PROJECT_SOURCE_UNAVAILABLE")
    archive = command([*git, "archive", "--format=tar", commit], reason="PROJECT_SOURCE_UNAVAILABLE")
    with tarfile.open(fileobj=io.BytesIO(archive)) as snapshot:
        if any(not (member.isfile() or member.isdir()) for member in snapshot):
            raise ExecutionError("UNSUPPORTED_PROJECT_ARCHIVE")
        snapshot.extractall(destination, filter="data")
    return commit
