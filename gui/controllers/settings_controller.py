"""
Контроллер настроек
===================

Управляет загрузкой и сохранением настроек приложения.
Отделяет работу с конфигурацией от UI.
"""

from pathlib import Path
from typing import TYPE_CHECKING

from config import ConfigManager, get_config
from gui.models.recording_state import (
    AudioType,
    CaptureType,
    RecordingState,
)
from logger_config import get_module_logger

if TYPE_CHECKING:
    pass

logger = get_module_logger(__name__)


class SettingsController:
    """
    Контроллер для управления настройками.

    Отвечает за:
    - Загрузку настроек из конфигурации
    - Сохранение настроек в конфигурацию
    - Синхронизацию между моделью и конфигурацией
    """

    def __init__(
        self,
        state: RecordingState | None = None,
        config: ConfigManager | None = None,
    ):
        """
        Инициализация контроллера.

        Args:
            state: Модель состояния записи
            config: Менеджер конфигурации
        """
        self._state = state or RecordingState()
        self._config = config or get_config()

    @property
    def state(self) -> RecordingState:
        """Получить текущее состояние."""
        return self._state

    def load_settings(self) -> None:
        """Загрузить настройки из конфигурации в модель."""
        settings = self._config.settings

        # Настройки видео
        self._state.video.fps = settings.video.fps
        self._state.video.codec = settings.video.codec
        self._state.video.bitrate = settings.video.bitrate
        self._state.video.format = settings.video.format

        capture_type_map = {
            "full": CaptureType.FULL,
            "window": CaptureType.WINDOW,
            "rect": CaptureType.RECT,
        }
        self._state.capture.capture_type = capture_type_map.get(
            settings.capture.area_type,
            CaptureType.FULL,
        )
        self._state.capture.window_title = settings.capture.window_title or ""
        if (
            settings.capture.rect_coords
            and len(settings.capture.rect_coords) == 4
        ):
            x1, y1, x2, y2 = settings.capture.rect_coords
            self._state.capture.rect_coords = (
                int(x1),
                int(y1),
                int(x2),
                int(y2),
            )

        # Путь вывода
        if settings.output.default_path:
            self._state.output.default_path = settings.output.default_path

        # Недавние записи
        self._state.recent_recordings.clear()
        for rec in settings.recent_recordings:
            path = Path(rec["path"])
            if path.exists():
                from gui.models.recording_state import RecentRecording

                recording = RecentRecording(
                    path=path,
                    size=rec.get("size", path.stat().st_size),
                    date=rec.get("date", ""),
                )
                self._state.recent_recordings.append(recording)

        logger.debug("Настройки загружены")

    def save_settings(self) -> None:
        """Сохранить настройки из модели в конфигурацию."""
        settings = self._config.settings

        # Настройки видео
        settings.video.fps = self._state.video.fps
        settings.video.codec = self._state.video.codec
        settings.video.bitrate = self._state.video.bitrate
        settings.video.format = self._state.video.format

        settings.capture.area_type = self._state.capture.capture_type.value
        settings.capture.window_title = (
            self._state.capture.window_title or None
        )
        if self._state.capture.capture_type == CaptureType.RECT:
            settings.capture.rect_coords = list(
                self._state.capture.rect_coords
            )
        else:
            settings.capture.rect_coords = None

        # Путь вывода
        if self._state.output.default_path:
            settings.output.default_path = self._state.output.default_path

        self._config.save()
        logger.debug("Настройки сохранены")

    def update_video_settings(
        self,
        fps: int | None = None,
        codec: str | None = None,
        bitrate: str | None = None,
        format: str | None = None,
    ) -> None:
        """
        Обновить настройки видео.

        Args:
            fps: Кадров в секунду
            codec: Видеокодек
            bitrate: Битрейт
            format: Формат файла
        """
        if fps is not None:
            self._state.video.fps = fps
        if codec is not None:
            self._state.video.codec = codec
        if bitrate is not None:
            self._state.video.bitrate = bitrate
        if format is not None:
            self._state.video.format = format

    def update_capture_settings(
        self,
        capture_type: CaptureType | None = None,
        window_title: str | None = None,
        rect_coords: tuple[int, int, int, int] | None = None,
    ) -> None:
        """
        Обновить настройки области захвата.

        Args:
            capture_type: Тип области захвата
            window_title: Заголовок окна
            rect_coords: Координаты прямоугольника
        """
        if capture_type is not None:
            self._state.capture.capture_type = capture_type
        if window_title is not None:
            self._state.capture.window_title = window_title
        if rect_coords is not None:
            self._state.capture.rect_coords = rect_coords

    def update_audio_settings(
        self,
        audio_type: AudioType | None = None,
        mic_device_index: int | None = None,
        mic_device_name: str | None = None,
    ) -> None:
        """
        Обновить настройки аудио.

        Args:
            audio_type: Тип источника аудио
            mic_device_index: Индекс устройства микрофона
            mic_device_name: Имя устройства микрофона
        """
        if audio_type is not None:
            self._state.audio.audio_type = audio_type
        if mic_device_index is not None:
            self._state.audio.mic_device_index = mic_device_index
        if mic_device_name is not None:
            self._state.audio.mic_device_name = mic_device_name

    def update_output_settings(
        self,
        output_path: str | None = None,
        default_path: str | None = None,
    ) -> None:
        """
        Обновить настройки вывода.

        Args:
            output_path: Путь к выходному файлу
            default_path: Путь по умолчанию
        """
        if output_path is not None:
            self._state.output.output_path = output_path
        if default_path is not None:
            self._state.output.default_path = default_path

    def add_recent_recording(self, path: Path, size: int) -> None:
        """
        Добавить недавнюю запись.

        Args:
            path: Путь к файлу записи
            size: Размер файла в байтах
        """
        self._state.add_recent_recording(path, size)
        self._config.add_recent_recording(str(path), size)

    def clear_recent_recordings(self) -> None:
        """Очистить недавние записи в модели и конфигурации."""
        self._state.recent_recordings.clear()
        self._config.clear_recent_recordings()

    def get_theme_mode(self) -> str:
        """
        Получить текущий режим темы из конфигурации.

        Returns:
            `"system"`, `"light"` или `"dark"`.
        """
        return str(self._config.settings.theme)

    def set_theme_mode(self, mode: str) -> None:
        """
        Установить и немедленно сохранить режим темы.

        В отличие от video/audio-настроек, тема сохраняется на диск сразу,
        а не только при закрытии окна — это UI-preference, а не часть
        сессии записи.

        Args:
            mode: `"system"`, `"light"` или `"dark"`.
        """
        self._config.settings.theme = mode
        self._config.save()

    def get_output_path(self) -> Path:
        """
        Получить путь к выходному файлу.

        Returns:
            Путь к выходному файлу
        """
        filename = self._state.get_output_filename()
        if self._state.output.output_path:
            output_path = Path(self._state.output.output_path)
            if output_path.exists() and output_path.is_dir():
                return Path(output_path, filename)
            if output_path.suffix == "":
                return Path(
                    str(
                        output_path.with_suffix(f".{self._state.video.format}")
                    )
                )
            return Path(str(output_path))

        # Генерация пути по умолчанию
        default_path = self._state.output.default_path
        if default_path:
            return Path(default_path, filename)
        return Path(filename)
