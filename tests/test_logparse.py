from __future__ import annotations

import pytest

from sysopt_buildcache.logparse import LogError, parse_build_log


def test_parses_user_steps_and_ignores_internal(build_log):
    steps = parse_build_log(build_log)

    assert [step.id for step in steps] == [2, 3, 4, 5, 6, 7]
    assert all("[internal]" not in step.description for step in steps)


def test_statuses_and_durations(build_log):
    steps = {step.id: step for step in parse_build_log(build_log)}

    assert steps[2].status == "cached"
    assert steps[2].is_cached is True
    assert steps[3].status == "done"
    assert steps[3].duration_s == 4.2
    assert steps[3].is_executed is True


def test_command_strips_the_stage_prefix(build_log):
    steps = {step.id: step for step in parse_build_log(build_log)}

    assert steps[4].command == "COPY . ."
    assert steps[6].command.startswith("RUN curl")


def test_error_status():
    log = "#1 [1/1] RUN false\n#1 ERROR: exit code 1\n"

    step = parse_build_log(log)[0]

    assert step.status == "error"
    assert step.is_executed is True


def test_empty_log_is_rejected():
    with pytest.raises(LogError, match="progress=plain"):
        parse_build_log("")