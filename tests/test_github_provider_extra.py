from __future__ import annotations

from collections import deque

import pytest

from pypi_package_changelog_generator._http import (
    HttpRequest,
    HttpResponse,
    HttpTransportError,
)
from pypi_package_changelog_generator.providers.base import (
    ProviderError,
    RepositoryProvider,
)
from pypi_package_changelog_generator.providers.github import (
    GitHubProvider,
    _extract_error_message,
    compute_retry_delay,
    is_rate_limited,
    parse_github_repo,
    resolve_tag_name,
)


def _json_response(
    status: int,
    payload: object,
    headers: dict[str, str] | None = None,
    url: str = "https://api.github.com/test",
) -> HttpResponse:
    return HttpResponse(
        status_code=status,
        headers={key.lower(): value for key, value in (headers or {}).items()},
        content=(__import__("json").dumps(payload)).encode("utf-8"),
        url=url,
    )


def _raw_response(
    status: int,
    payload: bytes,
    headers: dict[str, str] | None = None,
    url: str = "https://api.github.com/test",
) -> HttpResponse:
    return HttpResponse(
        status_code=status,
        headers={key.lower(): value for key, value in (headers or {}).items()},
        content=payload,
        url=url,
    )


def test_provider_base_types_raise_expected_errors() -> None:
    error = ProviderError("boom", "message", retryable=True)
    assert error.code == "boom"
    assert error.message == "message"
    assert error.retryable is True
    with pytest.raises(NotImplementedError):
        RepositoryProvider.compare_versions(object(), "repo", "1", "2")


def test_compare_versions_collects_commits_reviews_and_warning() -> None:
    compare_files = [
        {
            "filename": f"pkg/file-{index}.py",
            "previous_filename": None,
            "status": "modified",
            "additions": 1,
            "deletions": 0,
            "changes": 1,
            "patch": "+1",
        }
        for index in range(300)
    ]
    responses = {
        "/repos/AnnAngela/demo/tags": [
            _json_response(200, [{"name": "v1.0.0"}, {"name": "v2.0.0"}]),
        ],
        "/repos/AnnAngela/demo/compare/v1.0.0...v2.0.0": [
            _json_response(
                200,
                {
                    "html_url": "https://github.com/AnnAngela/demo/compare/v1.0.0...v2.0.0",
                    "commits": [
                        {
                            "sha": "abc",
                            "html_url": "https://github.com/AnnAngela/demo/commit/abc",
                            "commit": {
                                "message": "Subject line\n\nbody",
                                "author": {
                                    "name": "Ann",
                                    "date": "2024-01-01T00:00:00Z",
                                },
                            },
                        }
                    ],
                    "files": compare_files,
                },
            )
        ],
        "/repos/AnnAngela/demo/commits/abc/pulls": [
            _json_response(
                200,
                [
                    {
                        "number": 7,
                        "title": "Improve demo",
                        "html_url": "https://github.com/AnnAngela/demo/pull/7",
                        "state": "closed",
                        "merged_at": "2024-01-02T00:00:00Z",
                    }
                ],
            )
        ],
    }

    def handler(request: HttpRequest) -> HttpResponse:
        queue = responses[request.path]
        return queue.pop(0)

    provider = GitHubProvider(token="secret", transport=handler)
    try:
        result = provider.compare_versions(
            "https://github.com/AnnAngela/demo", "1.0.0", "2.0.0"
        )
    finally:
        provider.close()

    assert provider._client.headers["Authorization"] == "Bearer secret"
    assert result["mode"] == "git"
    assert result["commits"][0]["title"] == "Subject line"
    assert result["reviews"][0]["number"] == 7
    assert result["file_changes"][0]["path"] == "pkg/file-0.py"
    assert result["warnings"][0].code == "github_file_limit"


def test_compare_versions_raises_when_tag_cannot_be_matched() -> None:
    provider = GitHubProvider(
        transport=lambda _: _json_response(200, [{"name": "v1.0.0"}])
    )
    try:
        with pytest.raises(ProviderError, match="Could not match a GitHub tag"):
            provider.compare_versions(
                "https://github.com/AnnAngela/demo", "1.0.0", "2.0.0"
            )
    finally:
        provider.close()


def test_collect_pull_requests_skips_missing_shas_provider_errors_and_duplicates() -> (
    None
):
    provider = GitHubProvider()
    responses = iter(
        [
            ProviderError("boom", "broken"),
            [
                {
                    "number": 1,
                    "title": "One",
                    "html_url": "u1",
                    "state": "open",
                    "merged_at": None,
                },
                {
                    "number": 1,
                    "title": "Duplicate",
                    "html_url": "u1",
                    "state": "open",
                    "merged_at": None,
                },
            ],
        ]
    )

    def fake_get_json(path: str, params: dict[str, object] | None = None) -> object:
        result = next(responses)
        if isinstance(result, Exception):
            raise result
        return result

    provider._get_json = fake_get_json  # type: ignore[method-assign]
    try:
        pulls = provider._collect_pull_requests(
            "AnnAngela",
            "demo",
            [{"sha": None}, {"sha": "bad"}, {"sha": "good"}],
        )
    finally:
        provider.close()

    assert pulls == [
        {"number": 1, "title": "One", "url": "u1", "state": "open", "merged_at": None}
    ]


def test_fetch_tags_paginates_until_short_page() -> None:
    provider = GitHubProvider()
    pages = iter(
        [
            [{"name": f"tag-{index}"} for index in range(100)],
            [{"name": "tag-100"}],
        ]
    )
    provider._get_json = lambda path, params=None: next(pages)  # type: ignore[method-assign]
    try:
        tags = provider._fetch_tags("AnnAngela", "demo")
    finally:
        provider.close()
    assert tags[0] == "tag-0"
    assert tags[-1] == "tag-100"


def test_fetch_tags_stops_on_empty_payload() -> None:
    provider = GitHubProvider()
    provider._get_json = lambda path, params=None: []  # type: ignore[method-assign]
    try:
        assert provider._fetch_tags("AnnAngela", "demo") == []
    finally:
        provider.close()


def test_get_json_retries_http_errors_and_wraps_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pypi_package_changelog_generator.providers.github.time.sleep", lambda _: None
    )
    attempts = {"count": 0}

    def flaky_handler(_: HttpRequest) -> HttpResponse:
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise HttpTransportError("temporary")
        return _json_response(200, {"ok": True})

    provider = GitHubProvider(max_retries=1, transport=flaky_handler)
    try:
        assert provider._get_json("/demo") == {"ok": True}
    finally:
        provider.close()

    def always_fail(_: HttpRequest) -> HttpResponse:
        raise HttpTransportError("broken")

    provider = GitHubProvider(max_retries=0, transport=always_fail)
    try:
        with pytest.raises(ProviderError) as exc_info:
            provider._get_json("/demo")
        assert exc_info.value.code == "github_http_error"
        assert exc_info.value.retryable is True
    finally:
        provider.close()


def test_get_json_handles_retryable_and_final_http_statuses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "pypi_package_changelog_generator.providers.github.time.sleep", lambda _: None
    )
    queued = deque(
        [
            _json_response(503, {"message": "retry me"}),
            _json_response(200, {"ok": True}),
        ]
    )

    provider = GitHubProvider(max_retries=1, transport=lambda _: queued.popleft())
    try:
        assert provider._get_json("/demo") == {"ok": True}
    finally:
        provider.close()

    provider = GitHubProvider(max_retries=-1)
    try:
        with pytest.raises(ProviderError) as exc_info:
            provider._get_json("/demo")
        assert exc_info.value.code == "github_retry_exhausted"
    finally:
        provider.close()

    provider = GitHubProvider(
        max_retries=0,
        transport=lambda _: _json_response(
            403,
            {"message": "API rate limit exceeded"},
            headers={"x-ratelimit-remaining": "0"},
        ),
    )
    try:
        with pytest.raises(ProviderError) as exc_info:
            provider._get_json("/demo")
        assert exc_info.value.code == "github_rate_limited"
        assert exc_info.value.retryable is True
    finally:
        provider.close()

    provider = GitHubProvider(
        max_retries=0,
        transport=lambda _: _json_response(404, {"message": "missing"}),
    )
    try:
        with pytest.raises(ProviderError) as exc_info:
            provider._get_json("/demo")
        assert exc_info.value.code == "github_http_404"
        assert exc_info.value.message == "missing"
    finally:
        provider.close()


@pytest.mark.parametrize(
    ("repo_url", "expected"),
    [
        ("https://github.com/AnnAngela/demo", ("AnnAngela", "demo")),
    ],
)
def test_parse_github_repo_success(repo_url: str, expected: tuple[str, str]) -> None:
    assert parse_github_repo(repo_url) == expected


@pytest.mark.parametrize(
    "repo_url",
    ["https://example.com/AnnAngela/demo", "https://github.com/AnnAngela"],
)
def test_parse_github_repo_rejects_invalid_urls(repo_url: str) -> None:
    with pytest.raises(ProviderError):
        parse_github_repo(repo_url)


def test_resolve_tag_name_and_rate_limit_helpers() -> None:
    assert resolve_tag_name(["V1.0.0"], "1.0.0") == "V1.0.0"
    assert resolve_tag_name(["tag-1"], "1.0.0") is None

    response = _raw_response(403, b"{}", headers={"retry-after": "1"})
    assert is_rate_limited(response) is True
    response = _raw_response(403, b"{}", headers={"x-ratelimit-remaining": "0"})
    assert is_rate_limited(response) is True
    response = _raw_response(403, b"not-json")
    assert is_rate_limited(response) is False
    response = _json_response(403, {"message": "secondary rate limit"})
    assert is_rate_limited(response) is True


def test_retry_delay_and_error_message_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "pypi_package_changelog_generator.providers.github.time.time", lambda: 10.0
    )
    assert compute_retry_delay({"retry-after": "bad"}, 0) is None
    assert (
        compute_retry_delay(
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "bad"}, 0
        )
        is None
    )
    assert (
        compute_retry_delay(
            {"x-ratelimit-remaining": "0", "x-ratelimit-reset": "12"}, 0
        )
        == 3.0
    )
    assert compute_retry_delay({}, 2) == 240.0

    json_response = _json_response(500, {})
    assert (
        _extract_error_message(json_response) == "GitHub request failed with HTTP 500."
    )

    raw_response = _raw_response(500, b"not-json")
    assert (
        _extract_error_message(raw_response) == "GitHub request failed with HTTP 500."
    )
