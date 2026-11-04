"""Захват веб-камеры через FFmpeg/DirectShow (#165).

Запускает отдельный FFmpeg-процесс, пишущий видео камеры в файл,
параллельно основной записи. Остановка — graceful (stdin 'q') с
fallback на terminate/kill.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from logger_config import get_module_logger
from recorder.utils import get_subprocess_creationflags

logger = get_module_logger(__name__)

FFMPEG_BINARY = "ffmpeg"
CAMERA_STOP_TIMEOUT_SECONDS = 10.0
DEVICE_LIST_TIMEOUT_SECONDS = 15.0
_CAMERA_START_WAIT_SECONDS = 2.0


@dataclass(frozen=True)
class CameraDeviceInfo:
    """Найденное устройство захвата видео (веб-камера)."""

    name: str


def parse_ffmpeg_device_list(output: str) -> list[CameraDeviceInfo]:
    """Разобрать вывод `ffmpeg -list_devices` в список камер (#165).

    Args:
        output: Полный stderr-вывод FFmpeg.

    Returns:
        Список видеоустройств (секция «DirectShow video devices»
        до секции аудио); пустой список, если устройства не найдены.
    """
    devices: list[CameraDeviceInfo] = []
    in_video_section = False
    for line in output.splitlines():
        stripped = line.strip()
        lowered = stripped.lower()
        if "directshow video devices" in lowered:
            in_video_section = True
            continue
        if "directshow audio devices" in lowered:
            in_video_section = False
            continue
        # Строки устройств начинаются с префикса лога "[dshow @ ...]"
        if "]" in stripped:
            stripped = stripped.split("]", 1)[1].strip()
        if not in_video_section or not stripped.startswith('"'):
            continue
        name = stripped.strip('"')
        # Альтернативные имена устройства (после "Alternative name")
        if name.startswith("Alternative name"):
            continue
        if name:
            devices.append(CameraDeviceInfo(name=name))
    return devices


def list_cameras() -> list[CameraDeviceInfo]:
    """Перечислить веб-камеры через FFmpeg/DirectShow (#165).

    Returns:
        Найденные устройства; при недоступности FFmpeg — пустой список.
    """
    cmd = [
        FFMPEG_BINARY,
        "-hide_banner",
        "-list_devices",
        "true",
        "-f",
        "dshow",
        "-i",
        "dummy",
    ]
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=DEVICE_LIST_TIMEOUT_SECONDS,
            creationflags=get_subprocess_creationflags(),
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        logger.warning("Не удалось перечислить камеры: %s", e)
        return []
    # FFmpeg выводит список устройств в stderr
    return parse_ffmpeg_device_list(result.stderr or "")


class CameraRecorder:
    """Запись веб-камеры в файл отдельным FFmpeg-процессом (#165).

    Lifecycle: `start()` → `stop()`. Повторный `start()` без `stop()`
    отклоняется. Остановка сначала пытается завершить FFmpeg корректно
    (stdin 'q'), затем термирует процесс.
    """

    def __init__(
        self,
        device_name: str = "",
        fps: int = 30,
        ffmpeg_binary: str = FFMPEG_BINARY,
    ) -> None:
        """
        Инициализировать рекордер камеры.

        Args:
            device_name: Имя устройства DirectShow; пустая строка —
                первое найденное устройство.
            fps: Кадров в секунду для камеры.
            ffmpeg_binary: Путь к FFmpeg (для тестов).
        """
        self._device_name = device_name
        self._fps = max(1, int(fps))
        self._ffmpeg_binary = ffmpeg_binary
        self._process: subprocess.Popen[bytes] | None = None
        self._output_path: Path | None = None

    @property
    def is_running(self) -> bool:
        """Запущен ли процесс записи камеры."""
        return self._process is not None and self._process.poll() is None

    def _resolve_device_arg(self) -> str | None:
        """Определить аргумент `-i` для камеры.

        Returns:
            `video=<имя>` или `None`, если устройство не найдено.
        """
        if self._device_name:
            return f"video={self._device_name}"
        cameras = list_cameras()
        if not cameras:
            logger.warning("Веб-камеры не найдены")
            return None
        logger.info("Камера не указана, используется: %s", cameras[0].name)
        return f"video={cameras[0].name}"

    def start(self, output_path: Path) -> bool:
        """Запустить запись камеры в файл.

        Args:
            output_path: Путь к выходному файлу камеры.

        Returns:
            `True`, если процесс запущен и файл начал создаваться.
        """
        if self.is_running:
            logger.warning("Запись камеры уже активна")
            return False

        device_arg = self._resolve_device_arg()
        if device_arg is None:
            return False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = [
            self._ffmpeg_binary,
            "-hide_banner",
            "-f",
            "dshow",
            "-framerate",
            str(self._fps),
            "-i",
            device_arg,
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-pix_fmt",
            "yuv420p",
            "-y",
            str(output_path),
        ]
        try:
            self._process = subprocess.Popen(  # noqa: S603
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=get_subprocess_creationflags(),
            )
        except OSError as e:
            logger.error("Не удалось запустить FFmpeg для камеры: %s", e)
            self._process = None
            return False

        self._output_path = output_path
        logger.info("Запись камеры начата: %s", output_path)
        return True

    def stop(self) -> bool:
        """Остановить запись камеры и дождаться финализации файла.

        Returns:
            `True`, если процесс завершился и файл существует.
        """
        process = self._process
        if process is None:
            return False
        self._process = None

        try:
            if process.stdin is not None:
                try:
                    process.stdin.write(b"q\n")
                    process.stdin.flush()
                except OSError:
                    logger.debug("stdin камеры уже закрыт")
            try:
                process.wait(timeout=CAMERA_STOP_TIMEOUT_SECONDS)
            except subprocess.TimeoutExpired:
                logger.warning(
                    "FFmpeg камеры не завершился за %s сек — terminate",
                    CAMERA_STOP_TIMEOUT_SECONDS,
                )
                process.terminate()
                try:
                    process.wait(timeout=5.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5.0)
        except OSError as e:
            logger.warning("Ошибка остановки записи камеры: %s", e)

        output_path = self._output_path
        self._output_path = None
        if output_path is None or not output_path.exists():
            logger.warning("Файл камеры не создан")
            return False
        return True
