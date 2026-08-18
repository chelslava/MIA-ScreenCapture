"""
Unit-тесты клиента GitHub Releases API (core/updater/github_client.py).
======================================================================
"""

from __future__ import annotations

import json
import urllib.error
from unittest.mock import MagicMock, patch

from core.updater.github_client import (
    GitHubReleaseClient,
    is_version_newer,
    normalize_version,
)


class TestGitHubClientVersioning:
    """Тесты утилит версионирования."""

    def test_normalize_version(self) -> None:
        assert normalize_version("v1.2.3") == "1.2.3"
        assert normalize_version("V2.0.0-beta") == "2.0.0-beta"
        assert normalize_version(" 1.0.0 ") == "1.0.0"

    def test_is_version_newer(self) -> None:
        assert is_version_newer("1.2.4", "1.2.3") is True
        assert is_version_newer("2.0.0", "1.9.9") is True
        assert is_version_newer("1.2.3", "1.2.3") is False
        assert is_version_newer("1.2.2", "1.2.3") is False
        assert is_version_newer("invalid", "1.0.0") is False


class TestGitHubReleaseClient:
    """Тесты клиента GitHubReleaseClient."""

    @patch("urllib.request.urlopen")
    def test_fetch_releases_success(self, mock_urlopen: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_data = [
            {
                "tag_name": "v1.5.0",
                "name": "Release 1.5.0",
                "body": "Fixed bugs",
                "prerelease": False,
                "assets": [
                    {
                        "name": "MIA-ScreenCapture-1.5.0.zip",
                        "browser_download_url": "https://github.com/downloads/v1.5.0.zip",
                        "size": 1048576,
                        "content_type": "application/zip",
                    }
                ],
            }
        ]
        mock_response.read.return_value = json.dumps(mock_data).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_response

        client = GitHubReleaseClient()
        releases = client.fetch_releases()

        assert len(releases) == 1
        assert releases[0]["tag_name"] == "v1.5.0"

    @patch("urllib.request.urlopen")
    def test_fetch_releases_network_error_returns_empty(
        self, mock_urlopen: MagicMock
    ) -> None:
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        client = GitHubReleaseClient()
        releases = client.fetch_releases()

        assert releases == []

    def test_parse_release_payload(self) -> None:
        client = GitHubReleaseClient()
        payload = {
            "tag_name": "v2.0.0",
            "name": "Major Update 2.0.0",
            "body": "SHA256: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
            "published_at": "2026-08-18T12:00:00Z",
            "prerelease": False,
            "assets": [
                {
                    "name": "MIA-delta-2.0.0.zip",
                    "browser_download_url": "https://example.com/delta.zip",
                    "size": 524288,
                },
                {
                    "name": "MIA-Full-2.0.0.exe",
                    "browser_download_url": "https://example.com/full.exe",
                    "size": 10485760,
                },
            ],
        }

        info = client.parse_release_payload(payload)

        assert info.version == "2.0.0"
        assert info.is_delta is True
        assert info.primary_download_url == "https://example.com/delta.zip"
        assert (
            info.sha256_checksum
            == "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        )

    @patch.object(GitHubReleaseClient, "fetch_releases")
    def test_check_for_updates_found(self, mock_fetch: MagicMock) -> None:
        mock_fetch.return_value = [
            {
                "tag_name": "v2.0.0",
                "name": "Release 2.0.0",
                "body": "Notes",
                "prerelease": False,
                "assets": [],
            }
        ]

        client = GitHubReleaseClient()
        res = client.check_for_updates(current_version="1.0.0")

        assert res.update_available is True
        assert res.latest_release is not None
        assert res.latest_release.version == "2.0.0"

    @patch.object(GitHubReleaseClient, "fetch_releases")
    def test_check_for_updates_not_available(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.return_value = [
            {
                "tag_name": "v1.0.0",
                "name": "Release 1.0.0",
                "body": "Notes",
                "prerelease": False,
                "assets": [],
            }
        ]

        client = GitHubReleaseClient()
        res = client.check_for_updates(current_version="1.0.0")

        assert res.update_available is False
        assert res.latest_release is None

    @patch.object(GitHubReleaseClient, "fetch_releases")
    def test_check_for_updates_ignored_version(
        self, mock_fetch: MagicMock
    ) -> None:
        mock_fetch.return_value = [
            {
                "tag_name": "v1.5.0",
                "name": "Release 1.5.0",
                "body": "Notes",
                "prerelease": False,
                "assets": [],
            }
        ]

        client = GitHubReleaseClient()
        res = client.check_for_updates(
            current_version="1.0.0", ignored_version="1.5.0"
        )

        assert res.update_available is False
