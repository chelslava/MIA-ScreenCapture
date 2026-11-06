"""
Модуль уведомлений
==================

Кроссплатформенные уведомления (Windows Toast, macOS, Linux)
и звуковые сигналы событий записи (Issue #199).
"""

import base64
import sys
import threading
from pathlib import Path

from logger_config import get_module_logger

logger = get_module_logger(__name__)

# Тоны звуковых сигналов (частота Гц, длительность мс): короткие
# мелодии из системного динамика через winsound — без внешних файлов
_SOUND_TONES: dict[str, tuple[tuple[int, int], ...]] = {
    "start": ((880, 120), (1175, 180)),  # восходящий
    "stop": ((1175, 120), (880, 180)),  # нисходящий
    "paused": ((660, 150),),
    "resumed": ((660, 120), (880, 150)),
    "error": ((440, 260),),
}


def play_event_sound(kind: str) -> bool:
    """
    Проигрывает короткий звуковой сигнал события записи (#199).

    Звук исполняется в фоновом потоке (winsound.Beep блокирует),
    внешние файлы не используются.

    Args:
        kind: Тип события ('start', 'stop', 'paused', 'resumed', 'error').

    Returns:
        True если сигнал поставлен на воспроизведение.
    """
    tones = _SOUND_TONES.get(kind)
    if not tones:
        return False
    thread = threading.Thread(target=_beep_tones, args=(tones,), daemon=True)
    thread.start()
    return True


def _beep_tones(tones: tuple[tuple[int, int], ...]) -> None:
    """Проигрывает последовательность тонов; winsound — только Windows."""
    try:
        import winsound

        for freq, duration_ms in tones:
            winsound.Beep(freq, duration_ms)
    except (ImportError, OSError, RuntimeError) as e:
        # Нет аудио-выхода или не-Windows платформа — звук не критичен
        logger.debug("Не удалось проиграть звук события: %s", e)


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

        # title/message/app_name могут содержать произвольные символы
        # (например, имя файла записи) — base64 исключает любую инъекцию
        # в саму PowerShell-команду (алфавит base64 не содержит кавычек,
        # `$(...)`, обратных кавычек и т.п.). Decode + XML-escape
        # выполняются уже внутри самого PowerShell-скрипта.
        title_b64 = base64.b64encode(title.encode("utf-16-le")).decode("ascii")
        message_b64 = base64.b64encode(message.encode("utf-16-le")).decode(
            "ascii"
        )
        app_name_b64 = base64.b64encode(app_name.encode("utf-16-le")).decode(
            "ascii"
        )

        powershell_script = f'''
        [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
        [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null

        $decodedTitle = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String("{title_b64}"))
        $decodedMessage = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String("{message_b64}"))
        $decodedAppName = [System.Text.Encoding]::Unicode.GetString([System.Convert]::FromBase64String("{app_name_b64}"))
        $escapedTitle = [System.Security.SecurityElement]::Escape($decodedTitle)
        $escapedMessage = [System.Security.SecurityElement]::Escape($decodedMessage)

        $template = @"
        <toast>
            <visual>
                <binding template="ToastText02">
                    <text id="1">$escapedTitle</text>
                    <text id="2">$escapedMessage</text>
                </binding>
            </visual>
        </toast>
"@

        $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
        $xml.LoadXml($template)
        $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($decodedAppName).Show($toast)
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
