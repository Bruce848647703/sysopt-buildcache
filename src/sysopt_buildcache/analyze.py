"""Cache reuse metrics and Dockerfile anti-pattern detection."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .logparse import Step

INSTALL_MARKERS = (
    "npm install",
    "npm ci",
    "yarn install",
    "pnpm install",
    "pip install",
    "poetry install",
    "apt-get install",
    "apt install",
    "cargo build",
    "go mod download",
    "bundle install",
    "mvn ",
    "gradle ",
)

SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


@dataclass(frozen=True)
class Finding:
    rule: str
    severity: str
    step_id: int | None
    description: str
    message: str
    suggestion: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule": self.rule,
            "severity": self.severity,
            "step_id": self.step_id,
            "description": self.description,
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class Report:
    steps: list[Step]
    findings: list[Finding] = field(default_factory=list)
    min_hit_rate: float = 0.5
    slow_step_s: float = 30.0

    @property
    def cached(self) -> int:
        return sum(1 for step in self.steps if step.is_cached)

    @property
    def executed(self) -> int:
        return sum(1 for step in self.steps if step.is_executed)

    @property
    def failed(self) -> int:
        return sum(1 for step in self.steps if step.status == "error")

    @property
    def hit_rate(self) -> float:
        total = self.cached + self.executed
        return self.cached / total if total else 0.0

    @property
    def executed_time(self) -> float:
        return sum(step.duration_s for step in self.steps if step.is_executed)

    def at_least(self, severity: str) -> list[Finding]:
        limit = SEVERITY_RANK[severity]
        return [finding for finding in self.findings if SEVERITY_RANK[finding.severity] >= limit]

    def to_dict(self) -> dict[str, Any]:
        return {
            "steps": [step.to_dict() for step in self.steps],
            "cached": self.cached,
            "executed": self.executed,
            "failed": self.failed,
            "cache_hit_rate": round(self.hit_rate, 6),
            "executed_time_s": round(self.executed_time, 3),
            "findings": [finding.to_dict() for finding in self.findings],
        }


def _command_parts(step: Step) -> list[str]:
    return step.command.split()


def _is_broad_copy(step: Step) -> bool:
    parts = _command_parts(step)
    if not parts or parts[0].upper() != "COPY" or len(parts) < 2:
        return False
    source = parts[1]
    return source in {".", "./"} or source.startswith("./")


def _is_install_step(step: Step) -> bool:
    command = step.command.lower()
    return any(marker in command for marker in INSTALL_MARKERS)


def analyze(steps: list[Step], min_hit_rate: float = 0.5, slow_step_s: float = 30.0) -> Report:
    report = Report(steps=steps, min_hit_rate=min_hit_rate, slow_step_s=slow_step_s)

    if report.hit_rate < min_hit_rate:
        report.findings.append(
            Finding(
                rule="low-cache-hit",
                severity="warning",
                step_id=None,
                description="build cache",
                message=(
                    f"only {report.hit_rate:.1%} of steps came from cache "
                    f"(target {min_hit_rate:.0%})"
                ),
                suggestion=(
                    "copy lockfiles and install dependencies before copying the rest "
                    "of the build context"
                ),
            )
        )

    for index, step in enumerate(steps):
        command = step.command
        lowered = command.lower()

        if _is_broad_copy(step) and any(_is_install_step(later) for later in steps[index + 1 :]):
            report.findings.append(
                Finding(
                    rule="cache-busting-copy",
                    severity="warning",
                    step_id=step.id,
                    description=step.description,
                    message=(
                        "the whole build context is copied before dependency installation, "
                        "so every source edit invalidates the dependency cache"
                    ),
                    suggestion=(
                        "COPY the lockfile(s) first, RUN the install, then COPY the source"
                    ),
                )
            )

        if "apt-get update" in lowered and "rm -rf /var/lib/apt/lists" not in lowered:
            report.findings.append(
                Finding(
                    rule="unpinned-apt",
                    severity="warning",
                    step_id=step.id,
                    description=step.description,
                    message="apt lists are left in the layer and the package set is not pinned",
                    suggestion=(
                        "combine update+install and end with "
                        "`rm -rf /var/lib/apt/lists/*` in the same RUN"
                    ),
                )
            )

        if ("curl " in lowered or "wget " in lowered) and (
            "| sh" in lowered or "| bash" in lowered
        ):
            report.findings.append(
                Finding(
                    rule="download-execute",
                    severity="error",
                    step_id=step.id,
                    description=step.description,
                    message="a network download is piped straight into a shell",
                    suggestion="download, verify a checksum, then execute a pinned artifact",
                )
            )

        if command.upper().startswith("ADD HTTP"):
            report.findings.append(
                Finding(
                    rule="add-url",
                    severity="warning",
                    step_id=step.id,
                    description=step.description,
                    message="ADD from a URL is not cacheable and cannot be verified",
                    suggestion="use RUN curl with a checksum, or vendor the artifact",
                )
            )

        if step.is_executed and step.duration_s >= slow_step_s:
            report.findings.append(
                Finding(
                    rule="slow-step",
                    severity="info",
                    step_id=step.id,
                    description=step.description,
                    message=f"step took {step.duration_s:.1f}s",
                    suggestion="move it earlier so it is cached more often, or split it",
                )
            )

    report.findings.sort(
        key=lambda f: (
            -SEVERITY_RANK[f.severity],
            f.step_id if f.step_id is not None else -1,
            f.rule,
        )
    )
    return report