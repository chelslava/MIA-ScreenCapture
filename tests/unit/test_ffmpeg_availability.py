"""
Unit тесты для check_ffmpeg() — graceful degradation при недоступности FFmpeg.
"""

import subprocess
from unittest.mock import MagicMock, patch

from recorder.utils import FFmpegStatus, check_ffmpeg


class TestFFmpegStatusDataclass:
    """Проверка структуры FFmpegStatus."""

    def test_available_defaults(self) -> None:
        s = FFmpegStatus(available=True, version="6.1", path="/usr/bin/ffmpeg")
        assert s.available is True
        assert s.error is None
        assert s.recommendation is None

    def test_unavailable_with_error(self) -> None:
        s = FFmpegStatus(
            available=False, error="не найден", recommendation="установите"
        )
        assert s.available is False
        assert s.version is None
        assert s.path is None


class TestCheckFfmpegNotInPath:
    """Сценарий 1: FFmpeg не установлен / не в PATH."""

    def test_returns_unavailable(self) -> None:
        with patch("recorder.utils.get_ffmpeg_path", return_value=None):
            result = check_ffmpeg()

        assert isinstance(result, FFmpegStatus)
        assert result.available is False
        assert result.version is None
        assert result.path is None
        assert result.error is not None
        assert result.recommendation is not None

    def test_recommendation_mentions_download(self) -> None:
        with patch("recorder.utils.get_ffmpeg_path", return_value=None):
            result = check_ffmpeg()

        assert (
            "ffmpeg" in result.recommendation.lower()
            or "path" in result.recommendation.lower()
        )


class TestCheckFfmpegFoundButNotExecutable:
    """Сценарий 2: FFmpeg в PATH, но не запускается (FileNotFoundError)."""

    def test_returns_unavailable_with_path(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                side_effect=FileNotFoundError("не найден"),
            ),
        ):
            result = check_ffmpeg()

        assert result.available is False
        assert result.path == "/usr/bin/ffmpeg"
        assert result.error is not None
        assert result.recommendation is not None

    def test_recommendation_mentions_permissions(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                side_effect=FileNotFoundError,
            ),
        ):
            result = check_ffmpeg()

        rec_lower = result.recommendation.lower()
        assert any(
            word in rec_lower for word in ["permissions", "reinstall", "check"]
        )


class TestCheckFfmpegTimeout:
    """Сценарий 2b: FFmpeg зависает при вызове -version."""

    def test_returns_unavailable_on_timeout(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="ffmpeg", timeout=10
                ),
            ),
        ):
            result = check_ffmpeg()

        assert result.available is False
        assert result.error is not None

    def test_recommendation_on_timeout(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                side_effect=subprocess.TimeoutExpired(
                    cmd="ffmpeg", timeout=10
                ),
            ),
        ):
            result = check_ffmpeg()

        assert result.recommendation is not None


class TestCheckFfmpegAvailableCurrentVersion:
    """Сценарий: FFmpeg доступен, версия актуальная (>= 4.0.0)."""

    def _make_run_result(self, version_line: str) -> MagicMock:
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = f"{version_line}\nsome other output\n"
        return mock

    def test_returns_available(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                return_value=self._make_run_result(
                    "ffmpeg version 6.1.1 Copyright"
                ),
            ),
        ):
            result = check_ffmpeg()

        assert result.available is True
        assert result.version == "6.1.1"
        assert result.path == "/usr/bin/ffmpeg"
        assert result.error is None

    def test_no_recommendation_for_current_version(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                return_value=self._make_run_result(
                    "ffmpeg version 5.0 Copyright"
                ),
            ),
        ):
            result = check_ffmpeg()

        assert result.recommendation is None


class TestCheckFfmpegOutdatedVersion:
    """Сценарий 3: FFmpeg найден, но версия устарела (< 4.0.0)."""

    def _make_run_result(self, version_line: str) -> MagicMock:
        mock = MagicMock()
        mock.returncode = 0
        mock.stdout = f"{version_line}\n"
        return mock

    def test_available_but_has_recommendation(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                return_value=self._make_run_result(
                    "ffmpeg version 3.4.8 Copyright"
                ),
            ),
        ):
            result = check_ffmpeg()

        assert result.available is True
        assert result.recommendation is not None
        assert (
            "outdated" in result.recommendation.lower()
            or "older" in result.recommendation.lower()
        )

    def test_recommendation_mentions_min_version(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                return_value=self._make_run_result(
                    "ffmpeg version 2.8 Copyright"
                ),
            ),
        ):
            result = check_ffmpeg()

        assert "4.0" in result.recommendation

    def test_version_extracted_correctly(self) -> None:
        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch(
                "recorder.utils.subprocess.run",
                return_value=self._make_run_result(
                    "ffmpeg version 3.4.8 Copyright"
                ),
            ),
        ):
            result = check_ffmpeg()

        assert result.version == "3.4.8"


class TestCheckFfmpegNonZeroReturnCode:
    """FFmpeg запустился, но вернул ненулевой код."""

    def test_returns_unavailable(self) -> None:
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with (
            patch(
                "recorder.utils.get_ffmpeg_path",
                return_value="/usr/bin/ffmpeg",
            ),
            patch("recorder.utils.subprocess.run", return_value=mock_result),
        ):
            result = check_ffmpeg()

        assert result.available is False
        assert result.path == "/usr/bin/ffmpeg"
        assert result.error is not None
