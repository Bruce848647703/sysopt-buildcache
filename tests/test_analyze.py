from __future__ import annotations

from sysopt_buildcache.analyze import analyze
from sysopt_buildcache.logparse import parse_build_log


def rules(report) -> set[str]:
    return {finding.rule for finding in report.findings}


def test_cache_hit_rate(build_log):
    report = analyze(parse_build_log(build_log))

    assert report.cached == 2
    assert report.executed == 4
    assert report.hit_rate == 2 / 6
    assert report.executed_time == 4.2 + 0.1 + 12.0 + 1.0


def test_low_cache_hit_is_flagged(build_log):
    report = analyze(parse_build_log(build_log), min_hit_rate=0.5)

    finding = next(f for f in report.findings if f.rule == "low-cache-hit")
    assert finding.severity == "warning"
    assert "33.3%" in finding.message


def test_cache_busting_copy(build_log):
    report = analyze(parse_build_log(build_log))

    finding = next(f for f in report.findings if f.rule == "cache-busting-copy")
    assert finding.step_id == 4
    assert "COPY the lockfile" in finding.suggestion


def test_unpinned_apt(build_log):
    report = analyze(parse_build_log(build_log))

    finding = next(f for f in report.findings if f.rule == "unpinned-apt")
    assert finding.step_id == 3


def test_download_execute_is_an_error(build_log):
    report = analyze(parse_build_log(build_log))

    finding = next(f for f in report.findings if f.rule == "download-execute")
    assert finding.step_id == 6
    assert finding.severity == "error"


def test_add_url(build_log):
    report = analyze(parse_build_log(build_log))

    finding = next(f for f in report.findings if f.rule == "add-url")
    assert finding.step_id == 7


def test_slow_step_threshold(build_log):
    report = analyze(parse_build_log(build_log), slow_step_s=10.0)

    slow = [f for f in report.findings if f.rule == "slow-step"]
    assert [finding.step_id for finding in slow] == [5]


def test_severity_filter_keeps_errors(build_log):
    report = analyze(parse_build_log(build_log))

    shown = report.at_least("error")
    assert shown
    assert all(finding.severity == "error" for finding in shown)


def test_healthy_build_has_no_warnings():
    log = "#1 [1/2] FROM alpine\n#1 CACHED\n#2 [2/2] RUN true\n#2 CACHED\n"
    report = analyze(parse_build_log(log))

    assert report.hit_rate == 1.0
    assert rules(report) == set()