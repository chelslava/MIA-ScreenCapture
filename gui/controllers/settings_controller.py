"""
Контроллер настроек
===================

Управляет загрузкой и сохранением настроек приложения.
Отделяет работу с конфигурацией от UI.
"""

from pathlib import Path
from typing import TYPE_CHECKING, cast

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

    def get_output_path(self) -> Path:
        """
        Получить путь к выходному файлу.

        Returns:
            Путь к выходному файлу
        """
        filename = cast(str, self._state.get_output_filename())
        if self._state.output.output_path:
            output_path = Path(self._state.output.output_path)
            if output_path.exists() and output_path.is_dir():
                return output_path / filename
            if output_path.suffix == "":
                return output_path.with_suffix(f".{self._state.video.format}")
            return output_path

        # Генерация пути по умолчанию
        default_path = self._state.output.default_path
        if default_path:
            return Path(default_path) / filename
        return Path(filename)
