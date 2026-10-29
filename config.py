"""
Модуль управления конфигурацией
================================

Обрабатывает настройки приложения, пользовательские предпочтения
и сохранение конфигурации.
"""

import json
import threading
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from logger_config import get_module_logger
from utils import atomic_write_json

logger = get_module_logger(__name__)
_RECENT_RECORDINGS_SAVE_DEBOUNCE_SECONDS = 0.75


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
    verify_on_complete: bool = Field(default=True)
    auto_repair_corrupted: bool = Field(default=False)

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


class RecordingTunablesSchema(BaseModel):
    """Схема тонких параметров записи (#155).

    Значения по умолчанию идентичны прежнему поведению: до этого
    параметры были доступны только через конструкторы writer'ов.
    """

    enable_frame_skip: bool = Field(default=False)
    max_recovery_attempts: int = Field(default=3, ge=1, le=10)
    disk_warning_mb: float = Field(default=1024.0, ge=0, le=2_000_000)
    disk_critical_mb: float = Field(default=100.0, ge=0, le=2_000_000)
    disk_check_interval_s: float = Field(default=30.0, ge=1, le=600)
    # None — лимит сегментов отключён (прежнее поведение)
    max_segment_size_mb: float | None = Field(default=None, ge=1)
    max_segment_duration_s: float | None = Field(default=None, ge=1)
    health_check_interval_s: float = Field(default=1.0, ge=0.1, le=60)
    audio_max_recovery_attempts: int = Field(default=3, ge=1, le=10)

    @model_validator(mode="after")
    def validate_disk_thresholds(self) -> "RecordingTunablesSchema":
        """Критический порог диска не должен превышать warning."""
        if self.disk_critical_mb > self.disk_warning_mb:
            raise ValueError(
                "disk_critical_mb не может быть больше disk_warning_mb"
            )
        return self


class RateLimitSettingsSchema(BaseModel):
    """Схема валидации настроек rate limiting API (#152)."""

    enabled: bool = Field(default=True)
    requests_per_minute: int = Field(default=60, ge=1, le=100_000)
    requests_per_hour: int = Field(default=1000, ge=1, le=1_000_000)
    burst_limit: int = Field(default=10, ge=1, le=1000)
    block_duration: int = Field(default=10, ge=1, le=3600)
    # IP-адреса без ограничений
    whitelist: list[str] = Field(default_factory=list)
    # Лимитер неудачных аутентификаций
    auth_max_attempts: int = Field(default=5, ge=1, le=100)
    auth_base_delay: int = Field(default=60, ge=0, le=3600)


class APISettingsSchema(BaseModel):
    """Схема валидации настроек API."""

    enabled: bool = Field(default=True)
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=5000, ge=1, le=65535)
    server_threads: int = Field(default=4, ge=1, le=32)
    api_key: str | None = Field(default=None)
    webhook_url: str | None = Field(default=None)
    webhook_secret: str | None = Field(default=None)
    webhook_enabled: bool = Field(default=False)
    # Доверять X-Forwarded-For/X-Real-IP только за доверенным reverse-proxy
    trust_proxy_headers: bool = Field(default=False)
    # Использовать структурированные JSON-логи для API
    structured_logs: bool = Field(default=False)
    rate_limit: RateLimitSettingsSchema = Field(
        default_factory=RateLimitSettingsSchema
    )

    @field_validator("api_key", mode="before")
    @classmethod
    def validate_api_key(cls, value: Any) -> str | None:
        """Нормализует токен API."""
        if value is None:
            return None

        api_key = str(value).strip()
        return api_key or None

    @field_validator("webhook_url", "webhook_secret", mode="before")
    @classmethod
    def validate_webhook_str_fields(cls, value: Any) -> str | None:
        """Нормализует строковые поля webhook (пустая строка -> None)."""
        if value is None:
            return None

        normalized = str(value).strip()
        return normalized or None


class SchedulerSettingsSchema(BaseModel):
    """Схема валидации настроек планировщика."""

    enabled: bool = Field(default=True)
    persist_tasks: bool = Field(default=True)
    max_concurrent_tasks: int = Field(default=1, ge=1, le=10)


class PostProcessingSettingsSchema(BaseModel):
    """Схема валидации настроек постобработки записей."""

    enabled: bool = Field(default=False)
    transcode_enabled: bool = Field(default=False)
    transcode_format: str = Field(default="webm")
    transcode_codec: str = Field(default="libvpx-vp9")
    compress_enabled: bool = Field(default=False)
    compress_crf: int = Field(default=28, ge=0, le=51)
    trim_silence_enabled: bool = Field(default=False)
    trim_silence_threshold_db: int = Field(default=-50, le=0)
    generate_gif_enabled: bool = Field(default=False)
    gif_duration_seconds: int = Field(default=5, ge=1, le=60)
    gif_fps: int = Field(default=10, ge=1, le=30)
    copy_enabled: bool = Field(default=False)
    copy_target_folder: str = Field(default="")
    open_explorer_on_finish: bool = Field(default=False)
    webhook_enabled: bool = Field(default=False)
    webhook_url: str | None = Field(default=None)
    transcription_enabled: bool = Field(default=False)
    transcription_mode: str = Field(default="local")
    transcription_model: str = Field(default="base")
    transcription_output_format: str = Field(default="srt")
    transcription_language: str | None = Field(default=None)
    transcription_api_key: str | None = Field(default=None)
    transcription_api_base: str | None = Field(default=None)
    step_timeout_seconds: int = Field(default=300, ge=10, le=3600)

    @field_validator("webhook_url", mode="before")
    @classmethod
    def validate_webhook_url(cls, value: Any) -> str | None:
        if value is None:
            return None
        normalized = str(value).strip()
        return normalized or None


class UpdateSettingsSchema(BaseModel):
    """Схема валидации настроек автоматического обновления."""

    check_on_startup: bool = Field(default=True)
    auto_download: bool = Field(default=False)
    channel: str = Field(default="stable")
    check_interval_hours: int = Field(default=24, ge=1, le=720)
    last_checked_at: str | None = Field(default=None)
    ignored_version: str | None = Field(default=None)


# Держать в синхроне с gui.styles.theme.VALID_THEME_MODES (core/config не
# импортирует gui-слой с PyQt6, поэтому список продублирован буквально).
_VALID_THEME_MODES = ("system", "light", "blue", "dark", "dark_contrast")


class AppSettingsSchema(BaseModel):
    """Схема валидации основных настроек приложения."""

    video: VideoSettingsSchema = Field(default_factory=VideoSettingsSchema)
    audio: AudioSettingsSchema = Field(default_factory=AudioSettingsSchema)
    recording_tunables: RecordingTunablesSchema = Field(
        default_factory=RecordingTunablesSchema
    )
    capture: CaptureSettingsSchema = Field(
        default_factory=CaptureSettingsSchema
    )
    output: OutputSettingsSchema = Field(default_factory=OutputSettingsSchema)
    api: APISettingsSchema = Field(default_factory=APISettingsSchema)
    scheduler: SchedulerSettingsSchema = Field(
        default_factory=SchedulerSettingsSchema
    )
    post_processing: PostProcessingSettingsSchema = Field(
        default_factory=PostProcessingSettingsSchema
    )
    updates: UpdateSettingsSchema = Field(default_factory=UpdateSettingsSchema)
    minimize_to_tray: bool = Field(default=True)
    show_notifications: bool = Field(default=True)
    language: str = Field(default="en")
    theme: str = Field(default="system")
    sidebar_width: int = Field(default=110, ge=44, le=400)
    recent_recordings: list[dict[str, Any]] = Field(default_factory=list)
    max_recent_recordings: int = Field(default=20, ge=1, le=100)

    @field_validator("theme")
    @classmethod
    def validate_theme(cls, v: str) -> str:
        if v not in _VALID_THEME_MODES:
            raise ValueError(
                f"theme должен быть одним из {_VALID_THEME_MODES}"
            )
        return v

    @field_validator("language")
    @classmethod
    def validate_language(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if cleaned in ("auto", "en", "ru", "de", "fr", "es", "zh", "ja"):
            return cleaned
        return "en"


# ============================================================================
# Dataclass модели (для совместимости)
# ============================================================================


# Путь к файлу конфигурации
CONFIG_DIR = Path(__file__).parent / "config"
CONFIG_DIR.mkdir(exist_ok=True)
CONFIG_FILE = CONFIG_DIR / "config.json"


@dataclass
class RecordingTunables:
    """Тонкие параметры записи (#155).

    Настраиваются в config.json (`recording_tunables`) и в GUI
    (вкладка настроек). Дефолты идентичны прежнему поведению
    конструкторов рекордеров.
    """

    enable_frame_skip: bool = False
    max_recovery_attempts: int = 3
    disk_warning_mb: float = 1024.0
    disk_critical_mb: float = 100.0
    disk_check_interval_s: float = 30.0
    max_segment_size_mb: float | None = None
    max_segment_duration_s: float | None = None
    health_check_interval_s: float = 1.0
    audio_max_recovery_attempts: int = 3


@dataclass
class VideoSettings:
    """Настройки видеозаписи."""

    fps: int = 30
    codec: str = "libx264"
    bitrate: str = "2M"
    format: str = "mp4"
    compression: bool = True
    preset: str = "medium"
    verify_on_complete: bool = True
    auto_repair_corrupted: bool = False


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
class RateLimitSettings:
    """Настройки rate limiting API (#152)."""

    enabled: bool = True
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    block_duration: int = 10
    whitelist: list[str] = field(default_factory=list)
    auth_max_attempts: int = 5
    auth_base_delay: int = 60


@dataclass
class APISettings:
    """Настройки API сервера."""

    enabled: bool = True
    host: str = "127.0.0.1"
    port: int = 5000
    server_threads: int = 4
    api_key: str | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None
    webhook_enabled: bool = False
    trust_proxy_headers: bool = False
    structured_logs: bool = False
    rate_limit: RateLimitSettings = field(default_factory=RateLimitSettings)


@dataclass
class SchedulerSettings:
    """Настройки планировщика."""

    enabled: bool = True
    persist_tasks: bool = True
    max_concurrent_tasks: int = 1


@dataclass
class PostProcessingSettings:
    """Настройки постобработки записей."""

    enabled: bool = False
    transcode_enabled: bool = False
    transcode_format: str = "webm"
    transcode_codec: str = "libvpx-vp9"
    compress_enabled: bool = False
    compress_crf: int = 28
    trim_silence_enabled: bool = False
    trim_silence_threshold_db: int = -50
    generate_gif_enabled: bool = False
    gif_duration_seconds: int = 5
    gif_fps: int = 10
    copy_enabled: bool = False
    copy_target_folder: str = ""
    open_explorer_on_finish: bool = False
    webhook_enabled: bool = False
    webhook_url: str | None = None
    transcription_enabled: bool = False
    transcription_mode: str = "local"
    transcription_model: str = "base"
    transcription_output_format: str = "srt"
    transcription_language: str | None = None
    transcription_api_key: str | None = None
    transcription_api_base: str | None = None
    step_timeout_seconds: int = 300


@dataclass
class UpdateSettings:
    """Настройки автоматического обновления приложения."""

    check_on_startup: bool = True
    auto_download: bool = False
    channel: str = "stable"
    check_interval_hours: int = 24
    last_checked_at: str | None = None
    ignored_version: str | None = None


@dataclass
class AppSettings:
    """Основные настройки приложения."""

    video: VideoSettings = field(default_factory=VideoSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    recording_tunables: RecordingTunables = field(
        default_factory=RecordingTunables
    )
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    output: OutputSettings = field(default_factory=OutputSettings)
    api: APISettings = field(default_factory=APISettings)
    scheduler: SchedulerSettings = field(default_factory=SchedulerSettings)
    post_processing: PostProcessingSettings = field(
        default_factory=PostProcessingSettings
    )
    updates: UpdateSettings = field(default_factory=UpdateSettings)
    minimize_to_tray: bool = True
    show_notifications: bool = True
    language: str = "en"
    theme: str = "system"
    sidebar_width: int = 110

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
        self._settings_lock = threading.RLock()
        self._save_lock = threading.Lock()
        self._recent_save_timer: threading.Timer | None = None
        self._load()

    def _load(self) -> None:
        """Загрузка конфигурации из файла или создание значений по умолчанию."""
        if self.config_path.exists():
            try:
                with open(self.config_path, encoding="utf-8") as f:
                    data = json.load(f)
                # Валидация через Pydantic
                validated = AppSettingsSchema.model_validate(data)
                with self._settings_lock:
                    self._settings = self._dict_to_settings(
                        validated.model_dump()
                    )
                logger.info(f"Конфигурация загружена из {self.config_path}")
            except Exception as e:
                logger.error(f"Ошибка загрузки конфигурации: {e}")
                if "data" in locals():
                    logger.debug(
                        "Проблемная структура конфигурации: %s",
                        json.dumps(data, ensure_ascii=False, indent=2)[:2000],
                    )
                else:
                    try:
                        raw = self.config_path.read_text(encoding="utf-8")
                        logger.debug(
                            "Raw-содержимое конфигурационного файла: %s",
                            raw[:2000],
                        )
                    except Exception:
                        pass
                with self._settings_lock:
                    self._settings = AppSettings()
        else:
            with self._settings_lock:
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
            # Вложенные секции приходят из Pydantic model_dump() словарями —
            # разворачиваем в dataclass вручную (#152, #155)
            tunables_data = data.get("recording_tunables")
            recording_tunables = (
                RecordingTunables(**tunables_data)
                if isinstance(tunables_data, dict)
                else RecordingTunables()
            )
            capture = CaptureSettings(**data.get("capture", {}))
            output = OutputSettings(**data.get("output", {}))
            api_data = dict(data.get("api", {}))
            # rate_limit приходит из Pydantic model_dump() как словарь —
            # разворачиваем в dataclass вручную (#152)
            rate_limit_data = api_data.get("rate_limit")
            api_data["rate_limit"] = (
                RateLimitSettings(**rate_limit_data)
                if isinstance(rate_limit_data, dict)
                else RateLimitSettings()
            )
            api = APISettings(**api_data)
            scheduler = SchedulerSettings(**data.get("scheduler", {}))
            post_processing = PostProcessingSettings(
                **data.get("post_processing", {})
            )
            updates = UpdateSettings(**data.get("updates", {}))

            return AppSettings(
                video=video,
                audio=audio,
                recording_tunables=recording_tunables,
                capture=capture,
                output=output,
                api=api,
                scheduler=scheduler,
                post_processing=post_processing,
                updates=updates,
                minimize_to_tray=data.get("minimize_to_tray", True),
                show_notifications=data.get("show_notifications", True),
                language=data.get("language", "en"),
                theme=data.get("theme", "system"),
                sidebar_width=data.get("sidebar_width", 110),
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
            with self._settings_lock:
                data = asdict(self._settings)
            AppSettingsSchema.model_validate(data)
        except Exception as e:
            logger.error(
                f"Ошибка валидации конфигурации перед сохранением: {e}"
            )
            return False

        with self._save_lock:
            self._cancel_recent_save_timer_locked()
            try:
                result = atomic_write_json(self.config_path, data, mode=0o600)
                if result:
                    logger.info(f"Конфигурация сохранена в {self.config_path}")
                return bool(result)
            except Exception as e:
                logger.error(f"Ошибка сохранения конфигурации: {e}")
                return False

    def _save_recent_recordings_debounced(self) -> None:
        """
        Планирует отложенное сохранение конфига для hot-path recent записей.

        Несколько быстрых обновлений recent списка объединяются в один I/O.
        """
        with self._save_lock:
            self._cancel_recent_save_timer_locked()
            timer = threading.Timer(
                _RECENT_RECORDINGS_SAVE_DEBOUNCE_SECONDS,
                self._flush_recent_recordings_save,
            )
            timer.daemon = True
            self._recent_save_timer = timer
            timer.start()

    def _flush_recent_recordings_save(self) -> None:
        """Фоновая запись конфига после debounce окна."""
        try:
            with self._settings_lock:
                data = asdict(self._settings)
            AppSettingsSchema.model_validate(data)
        except Exception as e:
            logger.error(f"Ошибка валидации debounce-конфигурации: {e}")
            return

        with self._save_lock:
            self._recent_save_timer = None
            try:
                result = atomic_write_json(self.config_path, data, mode=0o600)
                if result:
                    logger.debug(
                        "Конфигурация сохранена (debounce recent_recordings)"
                    )
            except Exception as e:
                logger.error(f"Ошибка debounce-сохранения конфигурации: {e}")

    def _cancel_recent_save_timer_locked(self) -> None:
        """Отменяет отложенный таймер сохранения под захваченным lock."""
        if self._recent_save_timer is None:
            return
        self._recent_save_timer.cancel()
        self._recent_save_timer = None

    def flush_debounced_saves(self) -> bool:
        """
        Немедленно выполнить отложенное сохранение (для shutdown).

        Returns:
            True если сохранение успешно или нет отложенных сохранений
        """
        with self._save_lock:
            if self._recent_save_timer is None:
                return True
            self._cancel_recent_save_timer_locked()

        # Выполняем flush вне lock
        self._flush_recent_recordings_save()
        return True

    def validate_settings(self) -> tuple[bool, list[str]]:
        """
        Валидация текущих настроек.

        Returns:
            Кортеж (валидно, список ошибок)
        """
        try:
            with self._settings_lock:
                data = asdict(self._settings)
            AppSettingsSchema.model_validate(data)
            return True, []
        except Exception as e:
            errors = [str(e)]
            return False, errors

    @property
    def settings(self) -> AppSettings:
        """
        Получение текущих настроек.

        Возвращается общий объект настроек для обратной совместимости.
        Для фоновых потоков безопаснее использовать snapshot_settings().
        """
        with self._settings_lock:
            return self._settings

    def snapshot_settings(self) -> AppSettings:
        """
        Возвращает снимок настроек для безопасного чтения вне lock.

        Returns:
            Полная копия текущих настроек.
        """
        with self._settings_lock:
            return deepcopy(self._settings)

    def update(self, **kwargs: Any) -> None:
        """
        Обновление настроек новыми значениями.

        Args:
            **kwargs: Настройки для обновления (например, video=VideoSettings())
        """
        with self._settings_lock:
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

        with self._settings_lock:
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

        self._save_recent_recordings_debounced()

    def clear_recent_recordings(self) -> None:
        """Очистка списка недавних записей."""
        with self._settings_lock:
            self._settings.recent_recordings = []
        self.save()

    def remove_recent_recordings(self, paths: list[str]) -> int:
        """
        Массовое удаление записей из списка недавних (#160).

        Args:
            paths: Пути записей для удаления.

        Returns:
            Количество фактически удалённых элементов.
        """
        path_set = {str(p) for p in paths}
        with self._settings_lock:
            before = len(self._settings.recent_recordings)
            self._settings.recent_recordings = [
                r
                for r in self._settings.recent_recordings
                if r.get("path") not in path_set
            ]
            removed = before - len(self._settings.recent_recordings)

        if removed:
            self._save_recent_recordings_debounced()
        return removed

    def get_output_path(self, filename: str | None = None) -> Path:
        """
        Получение пути вывода для записи.

        Args:
            filename: Опциональное имя файла (будет сгенерировано, если не указано)

        Returns:
            Полный путь к выходному файлу
        """
        with self._settings_lock:
            output_path = self._settings.output.default_path
            filename_template = self._settings.output.filename_template
            extension = f".{self._settings.video.format}"

        base_path = Path(output_path)

        if not base_path.exists():
            base_path = Path.home() / "Videos" / "Recordings"
            base_path.mkdir(parents=True, exist_ok=True)

        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = filename_template.replace("{datetime}", timestamp)

        if not filename.endswith(extension):
            filename += extension

        return base_path / filename

    def reset(self) -> None:
        """Сброс конфигурации к значениям по умолчанию."""
        with self._settings_lock:
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
