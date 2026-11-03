"""Parse BuildKit ``--progress=plain`` logs into build steps."""

from __future__ import annotations

import re
from dataclasses import dataclass

STEP_RE = re.compile(r"^#(\d+)\s+(\[\d+/\d+\]\s+.+)$")
CACHED_RE = re.compile(r"^#(\d+)\s+CACHED\s*$")
DONE_RE = re.compile(r"^#(\d+)\s+DONE\s+([0-9]+(?:\.[0-9]+)?)s\s*$")
ERROR_RE = re.compile(r"^#(\d+)\s+ERROR:?\s*(.*)$")


class LogError(ValueError):
    """Raised when no build steps can be parsed."""


@dataclass
class Step:
    id: int
    description: str
    status: str = "unknown"
    duration_s: float = 0.0

    @property
    def is_cached(self) -> bool:
        return self.status == "cached"

    @property
    def is_executed(self) -> bool:
        return self.status in {"done", "error"}

    @property
    def command(self) -> str:
        return self.description.split("] ", 1)[-1].strip()

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "description": self.description,
            "status": self.status,
            "duration_s": round(self.duration_s, 3),
        }


def parse_build_log(text: str) -> list[Step]:
    steps: dict[int, Step] = {}
    order: list[int] = []

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = STEP_RE.match(stripped)
        if match:
            step_id = int(match.group(1))
            if step_id not in steps:
                order.append(step_id)
                steps[step_id] = Step(step_id, match.group(2).strip())
            continue
        match = CACHED_RE.match(stripped)
        if match:
            step = steps.get(int(match.group(1)))
            if step:
                step.status = "cached"
            continue
        match = DONE_RE.match(stripped)
        if match:
            step = steps.get(int(match.group(1)))
            if step:
                step.status = "done"
                step.duration_s = float(match.group(2))
            continue
        match = ERROR_RE.match(stripped)
        if match:
            step = steps.get(int(match.group(1)))
            if step:
                step.status = "error"
            continue

    result = [steps[step_id] for step_id in order]
    if not result:
        raise LogError("no BuildKit steps found; run with --progress=plain")
    return result