"""
Модуль уведомлений
==================

Кроссплатформенные уведомления (Windows Toast, macOS, Linux).
"""

import sys
from pathlib import Path

from logger_config import get_module_logger

logger = get_module_logger(__name__)


def send_notification(
    title: str,
    message: str,
    app_name: str = "MIA-ScreenCapture",
    icon_path: Path | None = None,
) -> bool:
    """
    Отправка системного уведомления.

    Args:
        title: Заголовок уведомления
        message: Текст уведомления
        app_name: Имя приложения
        icon_path: Путь к иконке

    Returns:
        True если уведомление отправлено успешно
    """
    try:
        if sys.platform == "win32":
            return _send_windows_toast(title, message, app_name, icon_path)
        elif sys.platform == "darwin":
            return _send_macos_notification(title, message)
        else:
            return _send_linux_notification(title, message)
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления: {e}")
        return False


def _send_windows_toast(
    title: str,
    message: str,
    app_name: str,
    icon_path: Path | None = None,
) -> bool:
    """
    Отправка Windows Toast уведомления.

    Использует win10toast или winotify.
    """
    try:
        from winotify import Notification, audio

        notification = Notification(
            app_id=app_name,
            title=title,
            msg=message,
            duration="short",
        )
        notification.set_audio(audio.Default, loop=False)
        notification.show()
        return True
    except ImportError:
        pass

    try:
        from win10toast import ToastNotifier

        toaster = ToastNotifier()
        toaster.show_toast(
            title,
            message,
            duration=3,
            threaded=True,
        )
        return True
    except ImportError:
        pass

    try:
        import subprocess

        powershell_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">{title}</text>
                    <text id="2">{message}</text>
                </binding>
            </visual>
        </toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("{app_name}").Show($toast)
        '''

        subprocess.run(
            ["powershell", "-Command", powershell_script],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception as e:
        logger.debug(f"PowerShell toast failed: {e}")
        return False


def _send_macos_notification(title: str, message: str) -> bool:
    """Отправка уведомления на macOS."""
    try:
        import subprocess

        subprocess.run(
            [
                "osascript",
                "-e",
                f'display notification "{message}" with title "{title}"',
            ],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False


def _send_linux_notification(title: str, message: str) -> bool:
    """Отправка уведомления на Linux через notify-send."""
    try:
        import subprocess

        subprocess.run(
            ["notify-send", title, message],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception:
        return False
