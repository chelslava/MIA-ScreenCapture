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
from typing import Any

from pydantic import BaseModel, Field, field_validator

from logger_config import get_module_logger
from utils import atomic_write_json

logger = get_module_logger(__name__)


# ============================================================================
# Pydantic модели для валидации
# ============================================================================


class VideoSettingsSchema(BaseModel):
    """Схема валидации настроек видео."""

    fps: int = Field(default=30, ge=1, le=120)
    codec: str = Field(default="libx264")
    bitrate: str = Field(default="2M")
    format: str = Field(default="mp4")
    compression: bool = Field(default=True)
    preset: str = Field(default="medium")

    @field_validator("preset")
    @classmethod
    def validate_preset(cls, v: str) -> str:
        valid_presets = (
            "ultrafast",
            "superfast",
            "veryfast",
            "faster",
            "fast",
            "medium",
            "slow",
            "slower",
            "veryslow",
        )
        if v not in valid_presets:
            raise ValueError(f"preset должен быть одним из: {valid_presets}")
        return v

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str) -> str:
        valid_suffixes = ("K", "M", "G", "k", "m", "g")
        if not any(v.endswith(s) for s in valid_suffixes) and not v.isdigit():
            raise ValueError(
                "bitrate должен быть числом или числом с суффиксом K/M/G"
            )
        return v


class AudioSettingsSchema(BaseModel):
    """Схема валидации настроек аудио."""

    record_mic: bool = Field(default=True)
    record_system: bool = Field(default=False)
    mic_device: str | None = Field(default=None)
    system_device: str | None = Field(default=None)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    channels: int = Field(default=2, ge=1, le=8)


class CaptureSettingsSchema(BaseModel):
    """Схема валидации настроек захвата."""

    area_type: str = Field(default="full")
    window_title: str | None = Field(default=None)
    rect_coords: list[int] | None = Field(default=None)

    @field_validator("area_type")
    @classmethod
    def validate_area_type(cls, v: str) -> str:
        if v not in ("full", "window", "rect"):
            raise ValueError(
                "area_type должен быть 'full', 'window' или 'rect'"
            )
        return v

    @field_validator("rect_coords")
    @classmethod
    def validate_rect_coords(cls, v: list[int] | None) -> list[int] | None:
        if v is not None and len(v) != 4:
            raise ValueError(
                "rect_coords должен содержать 4 элемента [x1, y1, x2, y2]"
            )
        return v


class OutputSettingsSchema(BaseModel):
    """Схема валидации настроек вывода."""

    default_path: str = Field(default="")
    filename_template: str = Field(default="recording_{datetime}")


class APISettingsSchema(BaseModel):
    """Схема валидации настроек API."""

    enabled: bool = Field(default=True)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000, ge=1, le=65535)
    api_key: str | None = Field(default=None)

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, value: Any) -> str | None:
        """Нормализует токен API."""
        if value is None:
            return None

        api_key = str(value).strip()
        return api_key or None


class SchedulerSettingsSchema(BaseModel):
    """Схема валидации настроек планировщика."""

    enabled: bool = Field(default=True)
    persist_tasks: bool = Field(default=True)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=10)


class AppSettingsSchema(BaseModel):
    """Схема валидации основных настроек приложения."""

    video: VideoSettingsSchema = Field(default_factory=VideoSettingsSchema)
    audio: AudioSettingsSchema = Field(default_factory=AudioSettingsSchema)
    capture: CaptureSettingsSchema = Field(
        default_factory=CaptureSettingsSchema
    )
    output: OutputSettingsSchema = Field(default_factory=OutputSettingsSchema)
    api: APISettingsSchema = Field(default_factory=APISettingsSchema)
    scheduler: SchedulerSettingsSchema = Field(
        default_factory=SchedulerSettingsSchema
    )
    minimize_to_tray: bool = Field(default=True)
    show_notifications: bool = Field(default=True)
    language: str = Field(default="en")
    recent_recordings: list[dict[str, Any]] = Field(default_factory=list)
    max_recent_recordings: int = Field(default=20, ge=1, le=100)


# ============================================================================
# Dataclass модели (для совместимости)
# ============================================================================


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
    preset: str = "medium"


@dataclass
class AudioSettings:
    """Настройки аудиозаписи."""

    record_mic: bool = True
    record_system: bool = False
    mic_device: str | None = None
    system_device: str | None = None
    sample_rate: int = 44100
    channels: int = 2


@dataclass
class CaptureSettings:
    """Настройки захвата экрана."""

    area_type: str = "full"  # "full", "window", "rect"
    window_title: str | None = None
    rect_coords: list[int] | None = None  # [x1, y1, x2, y2]


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
    api_key: str | None = None


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
    recent_recordings: list[dict[str, Any]] = field(default_factory=list)
    max_recent_recordings: int = 20


class ConfigManager:
    """
    Менеджер конфигурации для загрузки, сохранения и доступа к настройкам.

    Обеспечивает потокобезопасный доступ к конфигурации приложения
    с автоматическим сохранением в JSON файл.
    """

    def __init__(self, config_path: Path | None = None):
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
                # Валидация через Pydantic
                validated = AppSettingsSchema.model_validate(data)
                self._settings = self._dict_to_settings(validated.model_dump())
                logger.info(f"Конфигурация загружена из {self.config_path}")
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {e}")
                self._settings = AppSettings()
        else:
            self._settings = AppSettings()
            logger.info("Создана конфигурация по умолчанию")

    def _dict_to_settings(self, data: dict[str, Any]) -> AppSettings:
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
            AppSettingsSchema.model_validate(data)
            result = atomic_write_json(self.config_path, data)
            if result:
                logger.info(f"Конфигурация сохранена в {self.config_path}")
            return result
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}")
            return False

    def validate_settings(self) -> tuple[bool, list[str]]:
        """
        Валидация текущих настроек.

        Returns:
            Кортеж (валидно, список ошибок)
        """
        try:
            data = asdict(self._settings)
            AppSettingsSchema.model_validate(data)
            return True, []
        except Exception as e:
            errors = [str(e)]
            return False, errors

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

    def clear_recent_recordings(self) -> None:
        """Очистка списка недавних записей."""
        self._settings.recent_recordings = []
        self.save()

    def get_output_path(self, filename: str | None = None) -> Path:
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
_config: ConfigManager | None = None


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


def init_config(config_path: Path | None = None) -> ConfigManager:
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
