"""Plain data objects shared by every module."""
from dataclasses import dataclass, field
from typing import Optional

SEVERITIES = ("ERROR", "WARNING")


@dataclass(frozen=True)
class Check:
    """One declared data-quality test (built from a YAML entry)."""
    name: str
    type: str
    table: str
    severity: str = "ERROR"
    params: dict = field(default_factory=dict)
    source: str = ""  # which YAML file / generator it came from


@dataclass
class Result:
    check: Check
    passed: bool
    violations: Optional[int]  # None when the check could not run
    error: Optional[str] = None  # exception class name only, never data


class PipelineHalted(Exception):
    """Raised when at least one ERROR-severity check failed."""


@dataclass
class RunReport:
    results: list

    @property
    def failed_errors(self):
        return [r for r in self.results if not r.passed and r.check.severity == "ERROR"]

    @property
    def failed_warnings(self):
        return [r for r in self.results if not r.passed and r.check.severity == "WARNING"]

    @property
    def should_halt(self):
        return bool(self.failed_errors)

    def raise_if_halt(self):
        if self.should_halt:
            names = ", ".join(r.check.name for r in self.failed_errors)
            raise PipelineHalted(f"{len(self.failed_errors)} ERROR check(s) failed: {names}")
