"""
Клиент GitHub Releases API для проверки и получения информации об обновлениях.
=============================================================================
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import Any

from packaging import version as pkg_version

from core.updater.types import ReleaseAsset, ReleaseInfo, UpdateCheckResult
from logger_config import get_module_logger
from version import get_version

logger = get_module_logger(__name__)

DEFAULT_REPO_OWNER = "chelslava"
DEFAULT_REPO_NAME = "MIA-ScreenCapture"
DEFAULT_API_URL = f"https://api.github.com/repos/{DEFAULT_REPO_OWNER}/{DEFAULT_REPO_NAME}/releases"
DEFAULT_TIMEOUT_SECONDS = 15.0


def normalize_version(ver_str: str) -> str:
    """Удаляет префикс 'v' или пробелы из версии."""
    return re.sub(r"^[vV]", "", ver_str.strip())


def is_version_newer(candidate: str, current: str) -> bool:
    """Сравнивает две версии согласно SemVer / PEP 440."""
    try:
        cand_v = pkg_version.parse(normalize_version(candidate))
        curr_v = pkg_version.parse(normalize_version(current))
        return cand_v > curr_v
    except Exception as e:
        logger.warning(
            "Не удалось сравнить версии '%s' и '%s': %s", candidate, current, e
        )
        return False


class GitHubReleaseClient:
    """Клиент для взаимодействия с GitHub Releases API."""

    def __init__(
        self,
        owner: str = DEFAULT_REPO_OWNER,
        repo: str = DEFAULT_REPO_NAME,
        token: str | None = None,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.owner = owner
        self.repo = repo
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.timeout_seconds = timeout_seconds
        self._api_url = (
            f"https://api.github.com/repos/{self.owner}/{self.repo}/releases"
        )

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MIA-ScreenCapture-Updater/1.0",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    def fetch_releases(self, limit: int = 10) -> list[dict[str, Any]]:
        """Запрашивает список релизов с GitHub API."""
        url = f"{self._api_url}?per_page={limit}"
        req = urllib.request.Request(
            url, headers=self._build_headers(), method="GET"
        )

        try:
            with urllib.request.urlopen(
                req, timeout=self.timeout_seconds
            ) as resp:
                if resp.status != 200:
                    logger.warning("GitHub API вернул статус %d", resp.status)
                    return []
                raw_data = resp.read()
                data = json.loads(raw_data.decode("utf-8"))
                if isinstance(data, list):
                    return data
                return []
        except urllib.error.URLError as e:
            logger.warning(
                "Ошибка сети при обращении к GitHub Releases: %s", e
            )
            return []
        except Exception as e:
            logger.error("Непредвиденная ошибка получения релизов: %s", e)
            return []

    def parse_release_payload(self, data: dict[str, Any]) -> ReleaseInfo:
        """Преобразует JSON-ответ релиза от GitHub в ReleaseInfo."""
        tag_name = data.get("tag_name", "")
        version = normalize_version(tag_name)
        name = data.get("name") or tag_name
        body = data.get("body") or ""
        published_at = data.get("published_at") or data.get("created_at") or ""
        is_prerelease = bool(data.get("prerelease", False))

        raw_assets = data.get("assets", [])
        assets: list[ReleaseAsset] = []
        primary_url: str | None = None
        primary_size: int = 0
        sha256_checksum: str | None = None
        is_delta = False

        # 1. Сначала ищем дельта-патчи (.patch, -delta.zip)
        # 2. Затем полные пакеты (.zip, .exe)
        # 3. Ищем чексуммы (.sha256, sha256sums.txt)
        delta_asset: ReleaseAsset | None = None
        full_asset: ReleaseAsset | None = None

        for a in raw_assets:
            a_name = a.get("name", "")
            a_url = a.get("browser_download_url", "")
            a_size = int(a.get("size", 0))
            a_content_type = a.get("content_type", "application/octet-stream")

            asset_obj = ReleaseAsset(
                name=a_name,
                download_url=a_url,
                size_bytes=a_size,
                content_type=a_content_type,
            )
            assets.append(asset_obj)

            lower_name = a_name.lower()
            if "delta" in lower_name and (
                lower_name.endswith(".zip") or lower_name.endswith(".patch")
            ):
                delta_asset = asset_obj
            elif lower_name.endswith(".zip") or lower_name.endswith(".exe"):
                if not full_asset:
                    full_asset = asset_obj

        # Определяем основной ассет для скачивания (дельта предпочтительнее при наличии)
        if delta_asset:
            primary_url = delta_asset.download_url
            primary_size = delta_asset.size_bytes
            is_delta = True
        elif full_asset:
            primary_url = full_asset.download_url
            primary_size = full_asset.size_bytes
            is_delta = False
        elif data.get("zipball_url"):
            primary_url = data.get("zipball_url")
            primary_size = 0
            is_delta = False

        # Извлечение контрольной суммы SHA-256 из описания релиза (если указана в markdown)
        sha_match = re.search(
            r"(?:sha256|SHA-256|hash)[:\s]+([a-fA-F0-9]{64})",
            body,
            re.IGNORECASE,
        )
        if sha_match:
            sha256_checksum = sha_match.group(1).lower()

        return ReleaseInfo(
            version=version,
            tag_name=tag_name,
            name=name,
            release_notes=body,
            published_at=published_at,
            is_prerelease=is_prerelease,
            assets=assets,
            primary_download_url=primary_url,
            sha256_checksum=sha256_checksum,
            size_bytes=primary_size,
            is_delta=is_delta,
        )

    def get_latest_release(
        self, channel: str = "stable"
    ) -> ReleaseInfo | None:
        """
        Возвращает самый свежий релиз для указанного канала.

        Args:
            channel: Канал обновления ('stable' или 'beta').

        Returns:
            ReleaseInfo или None при отсутствии подходящих релизов.
        """
        releases = self.fetch_releases(limit=10)
        if not releases:
            return None

        for rel in releases:
            if rel.get("draft", False):
                continue
            is_pre = bool(rel.get("prerelease", False))
            if channel == "stable" and is_pre:
                continue
            # Подходящий релиз
            return self.parse_release_payload(rel)

        return None

    def check_for_updates(
        self,
        current_version: str | None = None,
        channel: str = "stable",
        ignored_version: str | None = None,
    ) -> UpdateCheckResult:
        """
        Проверяет наличие новой версии приложения.

        Args:
            current_version: Текущая версия (по умолчанию из version.get_version()).
            channel: Канал ('stable' или 'beta').
            ignored_version: Версия, которую пользователь решил игнорировать.

        Returns:
            UpdateCheckResult с детальной информацией.
        """
        cur_ver = current_version or get_version()
        if cur_ver == "unknown":
            cur_ver = "0.0.0"

        latest = self.get_latest_release(channel=channel)
        if not latest:
            return UpdateCheckResult(
                update_available=False,
                current_version=cur_ver,
                latest_release=None,
                error="Не удалось получить информацию о релизах с GitHub",
            )

        if ignored_version and normalize_version(
            latest.version
        ) == normalize_version(ignored_version):
            return UpdateCheckResult(
                update_available=False,
                current_version=cur_ver,
                latest_release=latest,
                error=None,
            )

        has_update = is_version_newer(latest.version, cur_ver)
        return UpdateCheckResult(
            update_available=has_update,
            current_version=cur_ver,
            latest_release=latest if has_update else None,
            error=None,
        )
