"""
Тесты модуля уведомлений
========================

Тестирует кроссплатформенные уведомления (Windows Toast, macOS, Linux).
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gui.notifications import send_notification


class TestSendNotification:
    """Тесты основной функции send_notification."""

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_windows_platform(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест вызова Windows функции на Windows."""
        mock_windows.return_value = True
        result = send_notification("Title", "Message")
        assert result is True
        mock_windows.assert_called_once()

    @patch("gui.notifications.sys.platform", "darwin")
    @patch("gui.notifications._send_macos_notification")
    def test_macos_platform(
        self,
        mock_macos: MagicMock,
    ) -> None:
        """Тест вызова macOS функции на macOS."""
        mock_macos.return_value = True
        result = send_notification("Title", "Message")
        assert result is True
        mock_macos.assert_called_once_with("Title", "Message")

    @patch("gui.notifications.sys.platform", "linux")
    @patch("gui.notifications._send_linux_notification")
    def test_linux_platform(
        self,
        mock_linux: MagicMock,
    ) -> None:
        """Тест вызова Linux функции на Linux."""
        mock_linux.return_value = True
        result = send_notification("Title", "Message")
        assert result is True
        mock_linux.assert_called_once_with("Title", "Message")

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_with_icon_path(
        self,
        mock_windows: MagicMock,
        tmp_path: Path,
    ) -> None:
        """Тест передачи пути к иконке."""
        icon_path = tmp_path / "icon.png"
        icon_path.touch()
        mock_windows.return_value = True
        result = send_notification("Title", "Message", icon_path=icon_path)
        assert result is True
        mock_windows.assert_called_once()

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_custom_app_name(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест передачи имени приложения."""
        mock_windows.return_value = True
        result = send_notification("Title", "Message", app_name="CustomApp")
        assert result is True
        call_args = mock_windows.call_args
        assert call_args[0][2] == "CustomApp"

    @patch("gui.notifications.sys.platform", "win32")
    @patch(
        "gui.notifications._send_windows_toast", side_effect=Exception("Error")
    )
    def test_exception_handling(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест обработки исключений."""
        result = send_notification("Title", "Message")
        assert result is False


class TestSendWindowsToast:
    """Тесты Windows Toast уведомлений."""

    @pytest.mark.skip(reason="Требует сложного мокирования импортов")
    def test_winotify_success(self) -> None:
        """Тест успешной отправки через winotify."""
        pass

    @pytest.mark.skip(reason="Требует сложного мокирования импортов")
    def test_fallback_to_win10toast(self) -> None:
        """Тест fallback на win10toast при ImportError winotify."""
        pass


class TestPowerShellFallbackSafety:
    """Проверки защиты PowerShell-fallback от инъекции спецсимволов."""

    @staticmethod
    def _decode_b64_unicode(value: str) -> str:
        """Декодировать base64(utf-16-le)-строку, как это делает PowerShell."""
        import base64

        return base64.b64decode(value).decode("utf-16-le")

    @staticmethod
    def _extract_script(mock_run: MagicMock) -> str:
        """Достать переданный PowerShell-скрипт из вызова subprocess.run."""
        call_args = mock_run.call_args
        command = call_args[0][0]
        return str(command[2])

    def test_quotes_and_subexpression_are_base64_encoded(self) -> None:
        """Кавычки и $(...) не должны попадать в скрипт буквально."""
        from gui.notifications import _send_windows_toast

        malicious_title = 'rec"; Remove-Item C:\\; $(calc) `whoami`'
        malicious_message = "запись.mp4"

        with patch.dict("sys.modules", {"winotify": None, "win10toast": None}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = _send_windows_toast(
                    malicious_title, malicious_message, "MIA-ScreenCapture"
                )

        assert result is True
        script = self._extract_script(mock_run)

        # Опасные символы не должны встречаться буквально в скрипте —
        # они существуют только внутри base64-блоба.
        assert malicious_title not in script
        assert '"; Remove-Item' not in script
        assert "$(calc)" not in script
        assert "`whoami`" not in script

        # Но base64-блоб при декодировании восстанавливает оригинал —
        # фикс не теряет данные, только обезвреживает их.
        title_b64 = script.split('FromBase64String("')[1].split('"')[0]
        assert self._decode_b64_unicode(title_b64) == malicious_title

    def test_unicode_title_round_trips(self) -> None:
        """Кириллица/эмодзи в имени файла должны сохраняться без потерь."""
        from gui.notifications import _send_windows_toast

        title = "Запись остановлена: запись_2026-06-24.mp4 🎬"

        with patch.dict("sys.modules", {"winotify": None, "win10toast": None}):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                _send_windows_toast(title, "ok", "MIA-ScreenCapture")

        script = self._extract_script(mock_run)
        title_b64 = script.split('FromBase64String("')[1].split('"')[0]
        assert self._decode_b64_unicode(title_b64) == title


class TestSendMacosNotification:
    """Тесты macOS уведомлений."""

    def test_success(self) -> None:
        """Тест успешной отправки на macOS."""
        mock_run = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_run):
            from gui.notifications import _send_macos_notification

            result = _send_macos_notification("Title", "Message")
            assert result is True

    def test_exception(self) -> None:
        """Тест обработки исключения."""
        with patch("subprocess.run", side_effect=Exception("osascript error")):
            from gui.notifications import _send_macos_notification

            result = _send_macos_notification("Title", "Message")
            assert result is False


class TestSendLinuxNotification:
    """Тесты Linux уведомлений."""

    def test_success(self) -> None:
        """Тест успешной отправки на Linux."""
        mock_run = MagicMock(returncode=0)
        with patch("subprocess.run", return_value=mock_run):
            from gui.notifications import _send_linux_notification

            result = _send_linux_notification("Title", "Message")
            assert result is True

    def test_exception(self) -> None:
        """Тест обработки исключения."""
        with patch(
            "subprocess.run", side_effect=Exception("notify-send error")
        ):
            from gui.notifications import _send_linux_notification

            result = _send_linux_notification("Title", "Message")
            assert result is False


class TestEdgeCases:
    """Тесты граничных случаев."""

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_empty_title(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест с пустым заголовком."""
        mock_windows.return_value = True
        result = send_notification("", "Message")
        assert result is True

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_empty_message(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест с пустым сообщением."""
        mock_windows.return_value = True
        result = send_notification("Title", "")
        assert result is True

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_long_text(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест с длинным текстом."""
        mock_windows.return_value = True
        long_text = "A" * 500
        result = send_notification(long_text, long_text)
        assert result is True

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_none_icon_path(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест с None в качестве пути к иконке."""
        mock_windows.return_value = True
        result = send_notification("Title", "Message", icon_path=None)
        assert result is True

    @patch("gui.notifications.sys.platform", "win32")
    @patch("gui.notifications._send_windows_toast")
    def test_nonexistent_icon_path(
        self,
        mock_windows: MagicMock,
    ) -> None:
        """Тест с несуществующим путём к иконке."""
        mock_windows.return_value = True
        result = send_notification(
            "Title",
            "Message",
            icon_path=Path("/nonexistent/icon.png"),
        )
        assert result is True
