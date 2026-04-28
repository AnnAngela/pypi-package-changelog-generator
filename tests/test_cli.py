from __future__ import annotations

import json

import pytest

from pypi_package_changelog_generator.cli import execute_analysis, main
from pypi_package_changelog_generator.models import ChangelogResult


def test_cli_outputs_json(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fake_execute_analysis(args: object) -> ChangelogResult:
        return ChangelogResult(
            package="requests",
            resolved_versions={"from": "2.31.0", "to": "2.32.0", "range": None},
            mode="git",
        )

    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.execute_analysis", fake_execute_analysis
    )

    exit_code = main(
        [
            "--package",
            "requests",
            "--from-version",
            "2.31.0",
            "--to-version",
            "2.32.0",
        ]
    )
    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["package"] == "requests"
    assert payload["resolved_versions"]["from"] == "2.31.0"
    assert payload["resolved_versions"]["to"] == "2.32.0"
    assert payload["mode"] == "git"


def test_cli_rejects_mixed_version_inputs() -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "--package",
                "requests",
                "--from-version",
                "2.31.0",
                "--to-version",
                "2.32.0",
                "--version-range",
                ">=2.0,<3.0",
            ]
        )


def test_execute_analysis_handles_version_resolution_failure() -> None:
    result = execute_analysis(
        type(
            "Args",
            (),
            {
                "package": "missing-package-example-do-not-use",
                "from_version": "1.0.0",
                "to_version": "2.0.0",
                "version_range": None,
                "github_token": None,
                "json_indent": 2,
            },
        )()
    )
    assert result.mode == "error"
    assert result.errors
