"""Command line entry point for sysopt-buildcache."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from .analyze import Report, analyze
from .logparse import LogError, parse_build_log


def _render_text(report: Report, shown, top: int) -> str:
    lines = [
        (
            f"build: {len(report.steps)} steps, {report.cached} cached, "
            f"{report.executed} executed, {report.failed} failed"
        ),
        f"cache hit rate: {report.hit_rate:.1%} (target {report.min_hit_rate:.0%})",
        f"executed time: {report.executed_time:.1f}s",
        "",
    ]
    if shown:
        lines.append("findings:")
        for finding in shown:
            step = f"#{finding.step_id}" if finding.step_id is not None else "-"
            lines.append(
                f"  {finding.severity:<7} {finding.rule:<20} {step:<5} {finding.description}"
            )
            lines.append(f"          {finding.message}")
            lines.append(f"          -> {finding.suggestion}")
    else:
        lines.append("findings: none")

    executed = sorted(
        (step for step in report.steps if step.is_executed),
        key=lambda step: (-step.duration_s, step.id),
    )[:top]
    if executed:
        lines.append("")
        lines.append("slowest executed steps:")
        for step in executed:
            lines.append(f"  {step.duration_s:7.1f}s  #{step.id} {step.description}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sysopt-buildcache",
        description="Measure BuildKit cache reuse and flag Dockerfile steps that bust it.",
    )
    parser.add_argument("log", help="BuildKit log from `docker build --progress=plain`")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--min-hit-rate",
        type=float,
        default=0.5,
        help="cache hit rate considered healthy (default: 0.5)",
    )
    parser.add_argument(
        "--slow-step-s",
        type=float,
        default=30.0,
        help="executed step duration that counts as slow (default: 30)",
    )
    parser.add_argument(
        "--min-severity",
        choices=("info", "warning", "error"),
        default="info",
        help="only show findings at or above this severity",
    )
    parser.add_argument("--top", type=int, default=5, help="slow steps to list")
    parser.add_argument(
        "--fail-on-low-cache",
        action="store_true",
        help="exit 1 when the cache hit rate is below --min-hit-rate",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        text = Path(args.log).read_text(encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot read {args.log}: {exc}", file=sys.stderr)
        return 2
    try:
        steps = parse_build_log(text)
    except LogError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    report = analyze(steps, min_hit_rate=args.min_hit_rate, slow_step_s=args.slow_step_s)
    shown = report.at_least(args.min_severity)
    if args.format == "json":
        payload = report.to_dict()
        payload["findings"] = [finding.to_dict() for finding in shown]
        print(json.dumps(payload, indent=2))
    else:
        print(_render_text(report, shown, args.top))

    if args.fail_on_low_cache and report.hit_rate < args.min_hit_rate:
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())