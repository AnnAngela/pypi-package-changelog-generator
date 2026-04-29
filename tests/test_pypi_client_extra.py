from __future__ import annotations

import pytest

from pypi_package_changelog_generator._http import (
    HttpRequest,
    HttpResponse,
    HttpTransportError,
)
from pypi_package_changelog_generator.pypi_client import (
    PypiClient,
    PypiClientError,
    iter_project_urls,
    normalize_repository_url,
)


def _json_response(
    status: int,
    payload: object,
    *,
    headers: dict[str, str] | None = None,
    url: str = "https://example.test",
) -> HttpResponse:
    return HttpResponse(
        status_code=status,
        headers={key.lower(): value for key, value in (headers or {}).items()},
        content=(__import__("json").dumps(payload)).encode("utf-8"),
        url=url,
    )


def _bytes_response(
    status: int,
    payload: bytes,
    *,
    headers: dict[str, str] | None = None,
    url: str = "https://example.test",
) -> HttpResponse:
    return HttpResponse(
        status_code=status,
        headers={key.lower(): value for key, value in (headers or {}).items()},
        content=payload,
        url=url,
    )


def test_pypi_client_methods_use_expected_endpoints_and_extract_values() -> None:
    seen: list[str] = []

    def handler(request: HttpRequest) -> HttpResponse:
        seen.append(request.url)
        if request.path.endswith("/demo/json"):
            return _json_response(
                200,
                {
                    "urls": [
                        {"packagetype": "bdist"},
                        {
                            "packagetype": "sdist",
                            "url": "https://files/demo.tar.gz",
                        },
                    ]
                },
                url=request.url,
            )
        if request.path.endswith("/demo/1.0.0/json"):
            return _json_response(
                200,
                {
                    "info": {
                        "project_urls": {
                            "Source": "https://example.com/demo",
                            "Code": "https://github.com/AnnAngela/demo",
                        },
                        "home_page": "https://github.com/AnnAngela/demo-home",
                    }
                },
                url=request.url,
            )
        raise AssertionError(f"unexpected url: {request.url}")

    client = PypiClient(transport=handler)
    try:
        assert (
            client.get_project("demo")["urls"][1]["url"] == "https://files/demo.tar.gz"
        )
        release = client.get_release("demo", "1.0.0")
        assert client.find_sdist_url({"urls": [{"packagetype": "bdist"}]}) is None
        assert (
            client.find_sdist_url(client.get_project("demo"))
            == "https://files/demo.tar.gz"
        )
        assert (
            client.extract_repository_url(
                {"info": {"project_urls": {"Docs": "https://example.com/demo"}}},
                release,
            )
            == "https://github.com/AnnAngela/demo"
        )
        assert (
            client.extract_repository_url(
                {"info": {"project_urls": {"Docs": "https://example.com/demo"}}}
            )
            is None
        )
    finally:
        client.close()

    assert seen


def test_pypi_client_download_bytes_success_and_errors() -> None:
    payload = b"archive"

    def ok_handler(_: HttpRequest) -> HttpResponse:
        return _bytes_response(200, payload)

    client = PypiClient(transport=ok_handler)
    try:
        assert client.download_bytes("https://files.example/demo.tar.gz") == payload
    finally:
        client.close()

    def failing_handler(_: HttpRequest) -> HttpResponse:
        raise HttpTransportError("boom")

    client = PypiClient(transport=failing_handler)
    try:
        with pytest.raises(PypiClientError, match="Failed to download source archive"):
            client.download_bytes("https://files.example/demo.tar.gz")
    finally:
        client.close()

    def status_handler(_: HttpRequest) -> HttpResponse:
        return _bytes_response(404, b"missing")

    client = PypiClient(transport=status_handler)
    try:
        with pytest.raises(PypiClientError) as exc_info:
            client.download_bytes("https://files.example/demo.tar.gz")
        assert exc_info.value.code == "pypi_download_failed"
        assert exc_info.value.retryable is True
    finally:
        client.close()


def test_pypi_client_wraps_http_errors() -> None:
    def status_handler(_: HttpRequest) -> HttpResponse:
        return _json_response(503, {"detail": "down"})

    client = PypiClient(transport=status_handler)
    try:
        with pytest.raises(PypiClientError) as exc_info:
            client.get_project("demo")
        assert exc_info.value.code == "pypi_http_503"
        assert exc_info.value.retryable is True
    finally:
        client.close()

    def transport_error(_: HttpRequest) -> HttpResponse:
        raise HttpTransportError("timeout")

    client = PypiClient(transport=transport_error)
    try:
        with pytest.raises(PypiClientError) as exc_info:
            client.get_project("demo")
        assert exc_info.value.code == "pypi_http_error"
        assert exc_info.value.retryable is True
    finally:
        client.close()


@pytest.mark.parametrize(
    ("candidate", "expected"),
    [
        (None, None),
        ("ssh://github.com/AnnAngela/demo", None),
        ("https://example.com/AnnAngela/demo", None),
        ("https://github.com/AnnAngela", None),
        ("git@github.com:AnnAngela/demo.git", "https://github.com/AnnAngela/demo"),
        (
            " https://github.com/AnnAngela/demo.git ",
            "https://github.com/AnnAngela/demo",
        ),
    ],
)
def test_normalize_repository_url(candidate: str | None, expected: str | None) -> None:
    assert normalize_repository_url(candidate) == expected


def test_iter_project_urls_collects_project_urls_and_home_pages() -> None:
    urls = iter_project_urls(
        [
            {"info": {"project_urls": {"Code": "https://github.com/AnnAngela/demo"}}},
            {"info": {"home_page": "https://example.com/home"}},
        ]
    )

    assert urls == ["https://github.com/AnnAngela/demo", "https://example.com/home"]
