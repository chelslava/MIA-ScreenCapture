"""
Модуль управления конфигурацией
================================

Обрабатывает настройки приложения, пользовательские предпочтения
и сохранение конфигурации.
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from logger_config import get_module_logger

logger = get_module_logger(__name__)


# Путь к файлу конфигурации
CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_DIR.mkdir(exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class VideoSettings:
    """Настройки видеозаписи."""

    fps: int = 30
    codec: str = "libx264"
    bitrate: str = "2M"
    format: str = "mp4"
    compression: bool = True


@dataclass
class AudioSettings:
    """Настройки аудиозаписи."""

    record_mic: bool = True
    record_system: bool = False
    mic_device: Optional[str] = None
    system_device: Optional[str] = None
    sample_rate: int = 44100
    channels: int = 2


@dataclass
class CaptureSettings:
    """Настройки захвата экрана."""

    area_type: str = "full"  # "full", "window", "rect"
    window_title: Optional[str] = None
    rect_coords: Optional[List[int]] = None  # [x1, y1, x2, y2]


@dataclass
class OutputSettings:
    """Настройки выходного файла."""

    default_path: str = ""
    filename_template: str = "recording_{datetime}"


@dataclass
class APISettings:
    """Настройки API сервера."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 5000


@dataclass
class SchedulerSettings:
    """Настройки планировщика."""

    enabled: bool = True
    persist_tasks: bool = True
    max_concurrent_tasks: int = 1


@dataclass
class AppSettings:
    """Основные настройки приложения."""

    video: VideoSettings = field(default_factory=VideoSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    api: APISettings = field(default_factory=APISettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    minimize_to_tray: bool = True
    show_notifications: bool = True
    language: str = "en"

    # Недавние записи (путь, дата, размер)
    recent_recordings: List[Dict[str, Any]] = field(default_factory=list)
    max_recent_recordings: int = 20


class ConfigManager:
    """
    Менеджер конфигурации для загрузки, сохранения и доступа к настройкам.

    Обеспечивает потокобезопасный доступ к конфигурации приложения
    с автоматическим сохранением в JSON файл.
    """

    def __init__(self, config_path: Optional[Path] = None):
        """
        Инициализация менеджера конфигурации.

        Args:
            config_path: Путь к файлу конфигурации (по умолчанию: CONFIG_FILE)
        """
        self.config_path = config_path or CONFIG_FILE
        self._settings: AppSettings = AppSettings()
        self._load()

    def _load(self) -> None:
        """Загрузка конфигурации из файла или создание значений по умолчанию."""
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    data = json.load(f)
                self._settings = self._dict_to_settings(data)
                logger.info(f"Конфигурация загружена из {self.config_path}")
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {e}")
                self._settings = AppSettings()
        else:
            self._settings = AppSettings()
            logger.info("Создана конфигурация по умолчанию")

    def _dict_to_settings(self, data: Dict[str, Any]) -> AppSettings:
        """
        Преобразование словаря в dataclass AppSettings.

        Args:
            data: Словарь с данными конфигурации

        Returns:
            Экземпляр AppSettings
        """
        try:
            video = VideoSettings(**data.get("video", {}))
            audio = AudioSettings(**data.get("audio", {}))
            capture = CaptureSettings(**data.get("capture", {}))
            output = OutputSettings(**data.get("output", {}))
            api = APISettings(**data.get("api", {}))
            scheduler = SchedulerSettings(**data.get("scheduler", {}))

            return AppSettings(
                video=video,
                audio=audio,
                capture=capture,
                output=output,
                api=api,
                scheduler=scheduler,
                minimize_to_tray=data.get("minimize_to_tray", True),
                show_notifications=data.get("show_notifications", True),
                language=data.get("language", "en"),
                recent_recordings=data.get("recent_recordings", []),
                max_recent_recordings=data.get("max_recent_recordings", 20),
            )
        except Exception as e:
            logger.error(f"Ошибка разбора конфигурации: {e}")
            return AppSettings()

    def save(self) -> bool:
        """
        Сохранение текущей конфигурации в файл.

        Returns:
            True если сохранение успешно, False в противном случае
        """
        try:
            data = asdict(self._settings)
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Конфигурация сохранена в {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False

    @property
    def settings(self) -> AppSettings:
        """Получение текущих настроек."""
        return self._settings

    def update(self, **kwargs) -> None:
        """
        Обновление настроек новыми значениями.

        Args:
            **kwargs: Настройки для обновления (например, video=VideoSettings())
        """
        for key, value in kwargs.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)
        self.save()

    def add_recent_recording(self, path: str, size: int) -> None:
        """
        Добавление записи в список недавних записей.

        Args:
            path: Путь к файлу записи
            size: Размер файла в байтах
        """
        recording = {
            "path": path,
            "date": datetime.now().isoformat(),
            "size": size,
        }

        # Удаление дубликатов
        self._settings.recent_recordings = [
            r
            for r in self._settings.recent_recordings
            if r.get("path") != path
        ]

        # Добавление в начало
        self._settings.recent_recordings.insert(0, recording)

        # Ограничение размера
        if (
            len(self._settings.recent_recordings)
            > self._settings.max_recent_recordings
        ):
            self._settings.recent_recordings = (
                self._settings.recent_recordings[
                    : self._settings.max_recent_recordings
                ]
            )

        self.save()

    def get_output_path(self, filename: Optional[str] = None) -> Path:
        """
        Получение пути вывода для записи.

        Args:
            filename: Опциональное имя файла (будет сгенерировано, если не указано)

        Returns:
            Полный путь к выходному файлу
        """
        base_path = Path(self._settings.output.default_path)

        if not base_path.exists():
            base_path = Path.home() / "Videos" / "Recordings"
            base_path.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            template = self._settings.output.filename_template
            filename = template.replace("{datetime}", timestamp)

        extension = f".{self._settings.video.format}"
        if not filename.endswith(extension):
            filename += extension

        return base_path / filename

    def reset(self) -> None:
        """Сброс конфигурации к значениям по умолчанию."""
        self._settings = AppSettings()
        self.save()
        logger.info("Конфигурация сброшена к значениям по умолчанию")


# Глобальный экземпляр конфигурации
_config: Optional[ConfigManager] = None


def get_config() -> ConfigManager:
    """
    Получение глобального экземпляра менеджера конфигурации.

    Returns:
        Экземпляр ConfigManager
    """
    global _config
    if _config is None:
        _config = ConfigManager()
    return _config


def init_config(config_path: Optional[Path] = None) -> ConfigManager:
    """
    Инициализация глобального менеджера конфигурации.

    Args:
        config_path: Опциональный путь к файлу конфигурации

    Returns:
        Экземпляр ConfigManager
    """
    global _config
    _config = ConfigManager(config_path)
    return _config
