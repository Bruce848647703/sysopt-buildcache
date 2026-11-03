from __future__ import annotations

import json
from pathlib import Path

from sysopt_buildcache.cli import main


def write(tmp_path: Path, text: str) -> str:
    path = tmp_path / "build.log"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_text_output(tmp_path, build_log, capsys):
    code = main([write(tmp_path, build_log)])

    output = capsys.readouterr().out
    assert code == 0
    assert "cache hit rate: 33.3%" in output
    assert "cache-busting-copy" in output
    assert "slowest executed steps:" in output


def test_json_output(tmp_path, build_log, capsys):
    code = main([write(tmp_path, build_log), "--format", "json"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert payload["cached"] == 2
    assert payload["executed"] == 4
    assert any(f["rule"] == "download-execute" for f in payload["findings"])


def test_fail_on_low_cache(tmp_path, build_log):
    assert main([write(tmp_path, build_log), "--fail-on-low-cache"]) == 1


def test_high_threshold_can_be_satisfied(tmp_path, build_log):
    assert main([write(tmp_path, build_log), "--min-hit-rate", "0.1", "--fail-on-low-cache"]) == 0


def test_min_severity_filters(tmp_path, build_log, capsys):
    code = main([write(tmp_path, build_log), "--format", "json", "--min-severity", "error"])

    payload = json.loads(capsys.readouterr().out)
    assert code == 0
    assert {finding["severity"] for finding in payload["findings"]} == {"error"}


def test_invalid_log_returns_two(tmp_path, capsys):
    code = main([write(tmp_path, "not a build log\n")])

    assert code == 2
    assert "progress=plain" in capsys.readouterr().err


def test_missing_file_returns_two(tmp_path, capsys):
    code = main([str(tmp_path / "missing.log")])

    assert code == 2
    assert "cannot read" in capsys.readouterr().err