from __future__ import annotations

from pathlib import Path

from pypi_package_changelog_generator.metadata_analysis import analyze_metadata


def test_metadata_analysis_detects_dependency_and_python_changes(
    tmp_path: Path,
) -> None:
    from_root = tmp_path / "from"
    to_root = tmp_path / "to"
    from_root.mkdir()
    to_root.mkdir()
    (from_root / "pyproject.toml").write_text(
        """
[project]
dependencies = ["requests>=2.31"]
requires-python = ">=3.8"
license = {text = "MIT"}
""".strip(),
        encoding="utf-8",
    )
    (to_root / "pyproject.toml").write_text(
        """
[project]
dependencies = ["httpx>=0.27"]
requires-python = ">=3.10"
license = {text = "MIT"}
""".strip(),
        encoding="utf-8",
    )

    analysis = analyze_metadata(
        {"info": {"requires_python": ">=3.8", "license": "MIT"}},
        {"info": {"requires_python": ">=3.10", "license": "MIT"}},
        from_root=from_root,
        to_root=to_root,
        file_changes=[{"path": "package/api.py", "status": "removed"}],
    )

    dependency_names = {change["name"] for change in analysis["dependency_changes"]}
    assert "requests" in dependency_names
    assert "httpx" in dependency_names
    breaking_kinds = {signal["kind"] for signal in analysis["breaking_signals"]}
    assert "python_floor_raised" in breaking_kinds
    assert "public_module_removed" in breaking_kinds


def test_metadata_analysis_ignores_src_prefix_renames(tmp_path: Path) -> None:
    from_root = tmp_path / "from"
    to_root = tmp_path / "to"
    from_root.mkdir()
    to_root.mkdir()
    analysis = analyze_metadata(
        {"info": {}},
        {"info": {}},
        from_root=from_root,
        to_root=to_root,
        file_changes=[
            {
                "path": "src/demo/api.py",
                "previous_path": "demo/api.py",
                "status": "renamed",
            }
        ],
    )

    breaking_kinds = {signal["kind"] for signal in analysis["breaking_signals"]}
    assert "public_module_removed" not in breaking_kinds
