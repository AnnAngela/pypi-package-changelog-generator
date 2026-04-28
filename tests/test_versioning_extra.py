from __future__ import annotations

import pytest

from pypi_package_changelog_generator.versioning import (
    VersionCandidate,
    VersionResolutionError,
    _legacy_sort_key,
    _looks_like_prerelease,
    build_candidates,
    build_tag_candidates,
    normalize_version,
    resolve_version_pair,
)


def test_version_candidate_helpers_cover_sorting_and_normalization() -> None:
    valid = VersionCandidate("1.0.0", None, ("a",), False)
    parsed = build_candidates({"1.0.0": [], "legacy-beta": [], "1.1.0rc1": []})

    assert normalize_version(" V1.0.0 ") == "1.0.0"
    assert parsed[0].raw == "1.0.0"
    assert parsed[-1].raw == "legacy-beta"
    assert parsed[1].is_prerelease is True
    assert valid.normalized == "1.0.0"
    assert VersionCandidate("1.0.0", parsed[0].parsed, (), False) < VersionCandidate("2.0.0", parsed[0].parsed.__class__("2.0.0"), (), False)
    assert VersionCandidate("1.0.0", parsed[0].parsed, (), False) < VersionCandidate("legacy", None, ("z",), False)
    assert VersionCandidate("legacy", None, ("a",), False) < VersionCandidate("legacy", None, ("z",), False)
    assert VersionCandidate("legacy", None, ("a",), False).__lt__(object()) is NotImplemented


def test_version_resolution_errors_and_helpers() -> None:
    with pytest.raises(VersionResolutionError, match="No releases were returned"):
        resolve_version_pair({}, from_version="1.0.0", to_version="2.0.0", version_range=None)

    with pytest.raises(VersionResolutionError, match="was not found"):
        resolve_version_pair({"1.0.0": []}, from_version="2.0.0", to_version="1.0.0", version_range=None)

    with pytest.raises(VersionResolutionError, match="does not have enough matching versions"):
        resolve_version_pair(
            {"1.0.0": [], "2.0.0": []},
            from_version=None,
            to_version=None,
            version_range="latest-0",
        )

    with pytest.raises(VersionResolutionError, match="Unsupported version range"):
        resolve_version_pair(
            {"1.0.0": [], "2.0.0": []},
            from_version=None,
            to_version=None,
            version_range="not-a-specifier",
        )

    assert build_tag_candidates("v1.2.3") == [
        "v1.2.3",
        "1.2.3",
        "release-1.2.3",
        "release/1.2.3",
        "python-v1.2.3",
    ]
    assert _looks_like_prerelease("1.0.0-preview1") is True
    assert _legacy_sort_key("1.0.0-beta1") == ((0, 1), (0, 0), (1, "beta", 1))
