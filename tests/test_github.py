from __future__ import annotations

from pypi_package_changelog_generator.providers.github import (
    compute_retry_delay,
    resolve_tag_name,
)


def test_compute_retry_delay_prefers_retry_after() -> None:
    delay = compute_retry_delay(
        {"retry-after": "7", "x-ratelimit-remaining": "0"}, 0, now=0
    )
    assert delay == 7.0


def test_compute_retry_delay_uses_reset_header() -> None:
    delay = compute_retry_delay(
        {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "105"}, 0, now=100
    )
    assert delay == 6.0


def test_resolve_tag_name_matches_common_prefixes() -> None:
    tags = ["v1.2.0", "release-1.3.0"]
    assert resolve_tag_name(tags, "1.2.0") == "v1.2.0"
    assert resolve_tag_name(tags, "1.3.0") == "release-1.3.0"
