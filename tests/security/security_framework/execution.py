"""Project resource ownership and bounded execution engine dispatch."""

from contextlib import ExitStack
from dataclasses import dataclass
from typing import Callable, Generic, Protocol, TypeVar

from .manifest import APP_METHODS, SCANNER_METHODS, restriction_reason


Fixture = TypeVar("Fixture", covariant=True)
Input = TypeVar("Input")
Output = TypeVar("Output")


class ProjectAdapter(Protocol[Fixture]):
    def prepare(self, resources: ExitStack) -> Fixture:
        """Return a fixture ready for this lane and register all owned resources."""


class ExecutionError(Exception):
    """An execution classification without raw output, credentials or exception text."""


@dataclass(frozen=True)
class Engine(Generic[Input, Output]):
    capability: str
    methods: frozenset[str]
    execute: Callable[[Input], Output]

    def admit(self, suite, cases):
        for case in cases:
            kind = suite.profiles[case["authProfile"]]["kind"]
            reason = restriction_reason(case["method"], kind)
            if reason:
                raise ExecutionError(reason)
            if case["method"] not in self.methods:
                raise ExecutionError("ENGINE_CAPABILITY_MISMATCH")

    def run(self, suite, cases, request: Input) -> Output:
        self.admit(suite, cases)
        return self.execute(request)


def run_project(suite, engine: Engine[Input, Output], adapter: ProjectAdapter[Input]) -> Output:
    """Admit before acquisition and return only after registered teardown succeeds."""
    cases = tuple(suite.cases.values())
    engine.admit(suite, cases)
    with ExitStack() as resources:
        return engine.execute(adapter.prepare(resources))


APPLICATION = frozenset(APP_METHODS)
PASSIVE = frozenset(SCANNER_METHODS)
