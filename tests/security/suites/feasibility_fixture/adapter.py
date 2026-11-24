"""Example adapter for the unchanged, digest-bound feasibility fixture."""

from pathlib import Path
import sys

# The historical PoC uses sibling imports to keep its scripts directly runnable.
sys.path.append(str(Path(__file__).resolve().parents[2] / "feasibility"))

from fixture import fixture as start_fixture

from .assertions.oracles import ORACLES, scanner_identities
from .plans.passive import render as build_plan


def evaluate(case, origin, evidence, profile):
    return ORACLES[case["oracle"]](origin, evidence, profile)


def after_report(path, scenario):
    if scenario == "missing-evidence":
        path.unlink(missing_ok=True)
    elif scenario == "invalid-evidence" and path.is_file():
        path.write_text('{"site": {}}', encoding="utf-8")
