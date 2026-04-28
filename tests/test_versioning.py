from __future__ import annotations

import pytest

from pypi_package_changelog_generator.versioning import (
    VersionResolutionError,
    resolve_version_pair,
)


def test_resolve_explicit_versions() -> None:
    releases = {"1.0.0": [], "1.1.0": [], "1.2.0": []}
    selection = resolve_version_pair(
        releases,
        from_version="1.0.0",
        to_version="1.2.0",
        version_range=None,
    )
    assert selection.from_version == "1.0.0"
    assert selection.to_version == "1.2.0"


def test_resolve_specifier_range() -> None:
    releases = {"1.0.0": [], "1.1.0": [], "1.2.0": [], "2.0.0": []}
    selection = resolve_version_pair(
        releases,
        from_version=None,
        to_version=None,
        version_range=">=1.0,<2.0",
    )
    assert selection.from_version == "1.0.0"
    assert selection.to_version == "1.2.0"


def test_resolve_latest_offset_range() -> None:
    releases = {"1.0.0": [], "1.1.0": [], "1.2.0": [], "1.3.0": []}
    selection = resolve_version_pair(
        releases,
        from_version=None,
        to_version=None,
        version_range="latest-1",
    )
    assert selection.from_version == "1.2.0"
    assert selection.to_version == "1.3.0"


def test_reject_range_with_single_match() -> None:
    releases = {"1.0.0": [], "2.0.0": []}
    with pytest.raises(VersionResolutionError):
        resolve_version_pair(
            releases,
            from_version=None,
            to_version=None,
            version_range="==2.0.0",
        )
