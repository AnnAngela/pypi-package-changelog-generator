from __future__ import annotations

import argparse
import runpy
import sys

import pytest

from pypi_package_changelog_generator.archive_diff import ArchiveDiffError
from pypi_package_changelog_generator.cli import build_parser, execute_analysis, main, validate_args
from pypi_package_changelog_generator.models import ChangelogResult
from pypi_package_changelog_generator.providers.base import ProviderError
from pypi_package_changelog_generator.pypi_client import PypiClientError
from pypi_package_changelog_generator.versioning import VersionResolutionError


class _Args:
    package = "demo"
    from_version = "1.0.0"
    to_version = "2.0.0"
    version_range = None
    github_token = None
    json_indent = 2


def test_build_parser_and_validate_args_error_paths() -> None:
    parser = build_parser()
    args = parser.parse_args(["--package", "demo", "--version-range", "latest-1"])
    assert args.json_indent == 2
    validate_args(parser, args)

    with pytest.raises(SystemExit):
        validate_args(
            parser,
            argparse.Namespace(
                package="demo",
                from_version=None,
                to_version=None,
                version_range=None,
            ),
        )


def test_execute_analysis_uses_github_and_cleans_up_archive(monkeypatch: pytest.MonkeyPatch) -> None:
    cleanup_called = {"value": False}
    budget_called = {"value": False}

    class FakeArchive:
        from_archive = type("Archive", (), {"root": "from-root"})()
        to_archive = type("Archive", (), {"root": "to-root"})()
        file_changes = [{"path": "pkg/module.py", "status": "modified"}]

        def cleanup(self) -> None:
            cleanup_called["value"] = True

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get_project(self, package: str) -> dict[str, object]:
            return {"releases": {"1.0.0": [], "2.0.0": []}}

        def get_release(self, package: str, version: str) -> dict[str, object]:
            return {"info": {"license": "MIT", "requires_python": ">=3.12"}}

        def extract_repository_url(self, *payloads: dict[str, object]) -> str | None:
            return "https://github.com/AnnAngela/demo"

    class FakeProvider:
        def __init__(self, token: str | None = None) -> None:
            assert token == "env-token"

        def compare_versions(self, repo_url: str, from_version: str, to_version: str) -> dict[str, object]:
            return {
                "mode": "git",
                "source": {
                    "provider": "github",
                    "repository_url": repo_url,
                    "compare_url": "https://compare",
                },
                "commits": [{"sha": "abc"}],
                "reviews": [{"number": 1}],
                "file_changes": [{"path": "pkg/module.py", "status": "modified"}],
                "warnings": [],
            }

        def close(self) -> None:
            return None

    monkeypatch.setattr("pypi_package_changelog_generator.cli.os.getenv", lambda key: "env-token")
    monkeypatch.setattr("pypi_package_changelog_generator.cli.PypiClient", FakeClient)
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.resolve_version_pair",
        lambda releases, **kwargs: type("Selection", (), {"from_version": "1.0.0", "to_version": "2.0.0", "range_expression": None})(),
    )
    monkeypatch.setattr("pypi_package_changelog_generator.cli.GitHubProvider", FakeProvider)
    monkeypatch.setattr("pypi_package_changelog_generator.cli.compare_release_archives", lambda client, fr, tr: FakeArchive())
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.analyze_metadata",
        lambda *args, **kwargs: {
            "metadata_changes": [{"field": "license"}],
            "dependency_changes": [{"name": "httpx"}],
            "breaking_signals": [{"kind": "signal"}],
        },
    )
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.apply_budget",
        lambda result: budget_called.__setitem__("value", True),
    )

    result = execute_analysis(_Args())

    assert result.mode == "git"
    assert result.auth.token_provided is True
    assert result.auth.provider == "github"
    assert result.source.compare_url == "https://compare"
    assert result.metadata_changes == [{"field": "license"}]
    assert cleanup_called["value"] is True
    assert budget_called["value"] is True


def test_execute_analysis_falls_back_to_archive_and_records_warnings(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeArchive:
        from_archive = type("Archive", (), {"root": None})()
        to_archive = type("Archive", (), {"root": None})()
        file_changes = [{"path": "pkg/new.py", "status": "added"}]

        def cleanup(self) -> None:
            return None

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get_project(self, package: str) -> dict[str, object]:
            return {"releases": {"1.0.0": [], "2.0.0": []}}

        def get_release(self, package: str, version: str) -> dict[str, object]:
            return {"info": {}}

        def extract_repository_url(self, *payloads: dict[str, object]) -> str | None:
            return "https://github.com/AnnAngela/demo"

    class BrokenProvider:
        def __init__(self, token: str | None = None) -> None:
            return None

        def compare_versions(self, repo_url: str, from_version: str, to_version: str) -> dict[str, object]:
            raise ProviderError("github_broken", "boom")

        def close(self) -> None:
            return None

    monkeypatch.setattr("pypi_package_changelog_generator.cli.PypiClient", FakeClient)
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.resolve_version_pair",
        lambda releases, **kwargs: type("Selection", (), {"from_version": "1.0.0", "to_version": "2.0.0", "range_expression": None})(),
    )
    monkeypatch.setattr("pypi_package_changelog_generator.cli.GitHubProvider", BrokenProvider)
    monkeypatch.setattr("pypi_package_changelog_generator.cli.compare_release_archives", lambda client, fr, tr: FakeArchive())
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.analyze_metadata",
        lambda *args, **kwargs: {
            "metadata_changes": [],
            "dependency_changes": [],
            "breaking_signals": [],
        },
    )
    monkeypatch.setattr("pypi_package_changelog_generator.cli.apply_budget", lambda result: None)

    result = execute_analysis(_Args())

    assert result.mode == "archive"
    assert result.source.provider == "archive"
    assert result.file_changes == [{"path": "pkg/new.py", "status": "added"}]
    assert result.warnings[0].code == "github_broken"


def test_execute_analysis_reports_repository_missing_and_unavailable_analysis(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get_project(self, package: str) -> dict[str, object]:
            return {"releases": {"1.0.0": [], "2.0.0": []}}

        def get_release(self, package: str, version: str) -> dict[str, object]:
            return {"info": {}}

        def extract_repository_url(self, *payloads: dict[str, object]) -> str | None:
            return None

    monkeypatch.setattr("pypi_package_changelog_generator.cli.PypiClient", FakeClient)
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.resolve_version_pair",
        lambda releases, **kwargs: type("Selection", (), {"from_version": "1.0.0", "to_version": "2.0.0", "range_expression": "latest-1"})(),
    )
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.compare_release_archives",
        lambda client, fr, tr: (_ for _ in ()).throw(ArchiveDiffError("sdist_missing", "missing")),
    )
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.analyze_metadata",
        lambda *args, **kwargs: {
            "metadata_changes": [],
            "dependency_changes": [],
            "breaking_signals": [],
        },
    )
    monkeypatch.setattr("pypi_package_changelog_generator.cli.apply_budget", lambda result: None)

    result = execute_analysis(_Args())

    assert result.mode == "error"
    assert [warning.code for warning in result.warnings] == ["repository_missing", "sdist_missing"]
    assert result.errors[0].code == "analysis_unavailable"


@pytest.mark.parametrize(
    "error",
    [
        PypiClientError("pypi_http_404", "missing", retryable=False),
        VersionResolutionError("bad range"),
    ],
)
def test_execute_analysis_wraps_top_level_errors(
    monkeypatch: pytest.MonkeyPatch, error: Exception
) -> None:
    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get_project(self, package: str) -> dict[str, object]:
            raise error

    monkeypatch.setattr("pypi_package_changelog_generator.cli.PypiClient", FakeClient)

    result = execute_analysis(_Args())

    assert result.mode == "error"
    assert result.errors[0].message == str(error)


def test_main_returns_zero_on_broken_pipe(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.execute_analysis",
        lambda args: ChangelogResult(
            package="demo",
            resolved_versions={"from": "1.0.0", "to": "2.0.0", "range": None},
            mode="git",
        ),
    )
    monkeypatch.setattr(
        "pypi_package_changelog_generator.cli.json.dumps",
        lambda *args, **kwargs: (_ for _ in ()).throw(BrokenPipeError()),
    )

    assert main(["--package", "demo", "--from-version", "1.0.0", "--to-version", "2.0.0"]) == 0


def test_module_main_entrypoint_raises_system_exit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "argparse.ArgumentParser.parse_args",
        lambda self, argv=None: argparse.Namespace(
            package="demo",
            from_version="1.0.0",
            to_version="2.0.0",
            version_range=None,
            github_token=None,
            json_indent=2,
        ),
    )

    class FakeClient:
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def get_project(self, package: str) -> dict[str, object]:
            raise PypiClientError("pypi_http_error", "failed")

    monkeypatch.setattr("pypi_package_changelog_generator.pypi_client.PypiClient", FakeClient)
    existing = sys.modules.pop("pypi_package_changelog_generator.cli", None)

    try:
        with pytest.raises(SystemExit) as exc_info:
            runpy.run_module("pypi_package_changelog_generator.cli", run_name="__main__")
    finally:
        if existing is not None:
            sys.modules["pypi_package_changelog_generator.cli"] = existing

    assert exc_info.value.code == 0
