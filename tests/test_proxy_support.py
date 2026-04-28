from __future__ import annotations

from pypi_package_changelog_generator.providers.github import GitHubProvider
from pypi_package_changelog_generator.pypi_client import PypiClient


def test_pypi_client_explicitly_trusts_proxy_environment() -> None:
    client = PypiClient()
    try:
        assert getattr(client._client, "_trust_env") is True
    finally:
        client.close()


def test_github_provider_explicitly_trusts_proxy_environment() -> None:
    provider = GitHubProvider()
    try:
        assert getattr(provider._client, "_trust_env") is True
    finally:
        provider.close()
