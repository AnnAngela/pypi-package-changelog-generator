from __future__ import annotations

import ast
from pathlib import Path

from packaging.version import Version

from pypi_package_changelog_generator.metadata_analysis import (
    ParsedProjectMetadata,
    _append_change,
    _extract_min_python,
    _find_shallowest,
    _literal_list,
    _literal_scalar,
    _literal_value,
    _looks_public_python_module,
    _module_qualname,
    _normalize_dependencies,
    _parse_pkg_info,
    _parse_pyproject,
    _parse_setup_cfg,
    _parse_setup_py,
    _split_multiline,
    analyze_metadata,
    compare_dependencies,
    compare_python_floor,
    parse_project_metadata,
)


def test_parse_project_metadata_prefers_shallowest_supported_files(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    nested = root / "nested"
    nested.mkdir()
    (nested / "pyproject.toml").write_text("[project]\nlicense = {file = 'LICENSE'}\n", encoding="utf-8")
    (root / "setup.cfg").write_text(
        """
[metadata]
license = MIT
classifiers =
    Programming Language :: Python

[options]
python_requires = >=3.9
install_requires =
    requests>=2

[options.extras_require]
dev =
    pytest>=8
""".strip(),
        encoding="utf-8",
    )

    metadata = parse_project_metadata(root)

    assert metadata.source == "nested/pyproject.toml"
    assert metadata.license == "LICENSE"
    setup_cfg = _parse_setup_cfg(root / "setup.cfg")
    assert setup_cfg.dependencies == {
        "requests": "requests>=2",
        "extra:dev:pytest": "pytest>=8",
    }
    assert setup_cfg.classifiers == ["Programming Language :: Python"]
    assert setup_cfg.requires_python == ">=3.9"
    assert metadata.dependencies == {}
    assert _find_shallowest(root, "missing.toml") is None


def test_parse_project_metadata_supports_pyproject_pkg_info_and_absent_files(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject"
    pyproject.mkdir()
    (pyproject / "pyproject.toml").write_text(
        """
[project]
dependencies = ["requests>=2", "not a req"]
requires-python = ">=3.10"
license = {file = "LICENSE"}
classifiers = ["Framework :: Pytest"]

[project.optional-dependencies]
docs = ["mkdocs>=1"]
""".strip(),
        encoding="utf-8",
    )
    parsed_pyproject = _parse_pyproject(pyproject / "pyproject.toml")
    assert parsed_pyproject.dependencies["requests"] == "requests>=2"
    assert parsed_pyproject.dependencies["not a req"] == "not a req"
    assert parsed_pyproject.dependencies["extra:docs:mkdocs"] == "mkdocs>=1"
    assert parsed_pyproject.license == "LICENSE"

    pkg_info = tmp_path / "pkginfo"
    pkg_info.mkdir()
    (pkg_info / "PKG-INFO").write_text(
        """
Metadata-Version: 2.1
Name: demo
Requires-Python: >=3.8
License: Apache-2.0
Classifier: Programming Language :: Python :: 3
Requires-Dist: httpx>=0.27
""".strip(),
        encoding="utf-8",
    )
    parsed_pkg = _parse_pkg_info(pkg_info / "PKG-INFO")
    assert parsed_pkg.dependencies == {"httpx": "httpx>=0.27"}
    empty = tmp_path / "empty"
    empty.mkdir()
    assert parse_project_metadata(empty) == ParsedProjectMetadata()
    assert parse_project_metadata(None) == ParsedProjectMetadata()


def test_parse_setup_py_supports_setup_and_setuptools_setup(tmp_path: Path) -> None:
    setup_py = tmp_path / "setup.py"
    setup_py.write_text(
        """
from setuptools import setup

setup(
    install_requires=["requests>=2"],
    extras_require={"dev": ["pytest>=8"], "bad": "not-a-list"},
    classifiers=["A", 1],
    license="MIT",
    python_requires=">=3.11",
)
""".strip(),
        encoding="utf-8",
    )
    parsed = _parse_setup_py(setup_py)
    assert parsed.dependencies == {
        "requests": "requests>=2",
        "extra:dev:pytest": "pytest>=8",
    }
    assert parsed.classifiers == ["A"]

    attr_setup_py = tmp_path / "attr_setup.py"
    attr_setup_py.write_text(
        """
import setuptools

setuptools.setup()
""".strip(),
        encoding="utf-8",
    )
    assert _parse_setup_py(attr_setup_py) == ParsedProjectMetadata()

    no_setup = tmp_path / "no_setup.py"
    no_setup.write_text("value = 1\n", encoding="utf-8")
    assert _parse_setup_py(no_setup) == ParsedProjectMetadata()


def test_metadata_helpers_cover_edge_cases(tmp_path: Path) -> None:
    assert compare_dependencies({"a": "a>=1", "b": "b>=1", "c": "c>=1"}, {"b": "b>=2", "c": "c>=1", "d": "d>=1"}) == [
        {"kind": "removed", "name": "a", "before": "a>=1", "after": None},
        {"kind": "added", "name": "d", "before": None, "after": "d>=1"},
        {"kind": "changed", "name": "b", "before": "b>=1", "after": "b>=2"},
    ]
    assert compare_python_floor(">=3.8", ">=3.8") is None
    assert compare_python_floor(">=3.8", ">=3.10") == {
        "kind": "python_floor_raised",
        "severity": "high",
        "message": "Python requirement increased from 3.8 to 3.10.",
        "evidence": {"before": ">=3.8", "after": ">=3.10"},
    }
    assert _normalize_dependencies(["", "requests>=2", "not a req"]) == [
        ("requests", "requests>=2"),
        ("not a req", "not a req"),
    ]
    assert _split_multiline(" one \n\n two ") == ["one", "two"]
    literal_list = ast.parse("['x']").body[0].value
    literal_scalar = ast.parse("'x'").body[0].value
    non_literal = ast.parse("value").body[0].value
    assert _literal_list(literal_list) == ["x"]
    assert _literal_list(non_literal) == []
    assert _literal_scalar(literal_scalar) == "x"
    assert _literal_scalar(literal_list) is None
    assert _literal_value(None) is None
    assert _literal_value(non_literal) is None

    changes: list[dict[str, object]] = []
    _append_change(changes, field="license", before="", after=None, source=None)
    _append_change(changes, field="license", before="MIT", after="Apache-2.0", source="setup.cfg")
    assert changes == [
        {"field": "license", "before": "MIT", "after": "Apache-2.0", "source": "setup.cfg"}
    ]
    assert _extract_min_python(None) is None
    assert _extract_min_python(">=3.8, ==3.9, >3..1") == Version("3.9")
    assert _looks_public_python_module("pkg/module.py") is True
    assert _looks_public_python_module("docs/conf.py") is False
    assert _module_qualname(None) is None
    assert _module_qualname("README.md") is None
    assert _module_qualname("./src/pkg/__init__.py") == "pkg"
    assert _module_qualname("/__init__.py") is None
    assert _module_qualname("tests/test_demo.py") is None
    assert _module_qualname("pkg/module.py") == "pkg.module"


def test_analyze_metadata_captures_classifier_and_rename_breaking_signals(tmp_path: Path) -> None:
    from_root = tmp_path / "from"
    to_root = tmp_path / "to"
    from_root.mkdir()
    to_root.mkdir()
    (from_root / "PKG-INFO").write_text(
        """
Metadata-Version: 2.1
Classifier: Old
Requires-Dist: old>=1
Requires-Python: >=3.8
""".strip(),
        encoding="utf-8",
    )
    (to_root / "pyproject.toml").write_text(
        """
[project]
dependencies = ["new>=1"]
requires-python = ">=3.9"
classifiers = ["New"]
license = {text = "MIT"}
""".strip(),
        encoding="utf-8",
    )

    analysis = analyze_metadata(
        {"info": {"requires_python": ">=3.8", "license": "BSD"}},
        {"info": {"requires_python": ">=3.9", "license": "MIT"}},
        from_root=from_root,
        to_root=to_root,
        file_changes=[
            {"path": "pkg/keep.txt", "status": "modified"},
            {
                "path": "pkg/renamed.py",
                "previous_path": "pkg/original.py",
                "status": "renamed",
            }
        ],
    )

    assert any(change["field"] == "classifiers" for change in analysis["metadata_changes"])
    kinds = {signal["kind"] for signal in analysis["breaking_signals"]}
    assert kinds == {"python_floor_raised", "dependency_removed", "public_module_removed"}
