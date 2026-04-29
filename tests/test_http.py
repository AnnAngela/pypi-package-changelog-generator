from __future__ import annotations

from io import BytesIO
from urllib.error import URLError
from urllib.error import HTTPError

import pytest

from pypi_package_changelog_generator._http import (
    HttpClient,
    HttpTransportError,
    _append_query,
    _normalize_headers,
    _resolve_url,
)


class _OpenedResponse:
    def __init__(
        self,
        *,
        status: int,
        headers: dict[str, str],
        content: bytes,
        url: str,
    ) -> None:
        self.status = status
        self.headers = headers
        self._content = content
        self._url = url

    def __enter__(self) -> "_OpenedResponse":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._content

    def geturl(self) -> str:
        return self._url


def test_http_client_uses_opener_when_no_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = HttpClient(
        base_url="https://example.test/api",
        headers={"Accept": "application/json"},
        timeout=12.5,
        trust_env=False,
    )

    seen: dict[str, object] = {}

    def fake_open(request, timeout: float) -> _OpenedResponse:  # type: ignore[no-untyped-def]
        seen["url"] = request.full_url
        seen["timeout"] = timeout
        seen["headers"] = dict(request.header_items())
        seen["method"] = request.get_method()
        return _OpenedResponse(
            status=200,
            headers={"Content-Type": "application/json", "X-Test": "ok"},
            content=b'{"ok": true}',
            url="https://example.test/final",
        )

    monkeypatch.setattr(client._opener, "open", fake_open)

    response = client.get("projects", params={"page": 2}, headers={"X-Extra": "1"})

    assert client._trust_env is False
    assert seen == {
        "url": "https://example.test/api/projects?page=2",
        "timeout": 12.5,
        "headers": {
            "Accept": "application/json",
            "X-extra": "1",
        },
        "method": "GET",
    }
    assert response.status_code == 200
    assert response.headers == {"content-type": "application/json", "x-test": "ok"}
    assert response.content == b'{"ok": true}'
    assert response.url == "https://example.test/final"
    assert response.json() == {"ok": True}


def test_http_client_wraps_url_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    client = HttpClient(base_url="https://example.test")

    def fake_open(*_args: object, **_kwargs: object) -> None:
        raise URLError("network down")

    monkeypatch.setattr(client._opener, "open", fake_open)

    with pytest.raises(HttpTransportError, match="network down"):
        client.get("/ping")


def test_http_client_converts_http_error_to_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = HttpClient(base_url="https://example.test")

    def fake_open(*_args: object, **_kwargs: object) -> None:
        raise HTTPError(
            url="https://example.test/missing",
            code=404,
            msg="missing",
            hdrs={"Content-Type": "application/json"},
            fp=BytesIO(b'{"error": "missing"}'),
        )

    monkeypatch.setattr(client._opener, "open", fake_open)

    response = client.get("/missing")

    assert response.status_code == 404
    assert response.headers == {"content-type": "application/json"}
    assert response.content == b'{"error": "missing"}'
    assert response.url == "https://example.test/missing"


def test_http_helper_functions_cover_absolute_relative_query_and_headers() -> None:
    assert (
        _resolve_url("https://example.test/api", "https://other.test/path")
        == "https://other.test/path"
    )
    assert (
        _resolve_url("https://example.test/api", "/projects")
        == "https://example.test/api/projects"
    )
    assert (
        _resolve_url("https://example.test/api", "projects")
        == "https://example.test/api/projects"
    )

    assert (
        _append_query(
            "https://example.test/api?existing=1",
            {
                "skip": None,
                "tag": ["a", "b"],
                "state": ("open", "closed"),
                "page": 2,
            },
        )
        == "https://example.test/api?existing=1&tag=a&tag=b&state=open&state=closed&page=2"
    )
    assert _append_query("https://example.test/api", None) == "https://example.test/api"

    assert _normalize_headers(
        [("X-Test", 1), ("content-type", "application/json")]
    ) == {
        "x-test": "1",
        "content-type": "application/json",
    }
