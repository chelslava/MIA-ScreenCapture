"""
Модуль схем валидации API
=========================

Определяет Pydantic модели для валидации входных данных API запросов.
"""

import ipaddress
import re
import socket
from datetime import UTC, datetime
from pathlib import PureWindowsPath
from typing import Any, Literal, Optional
from urllib.parse import urlparse

import tzlocal
from pydantic import BaseModel, Field, field_validator, model_validator


def _is_private_or_reserved_host(hostname: str) -> bool:
    """
    Проверяет, ведёт ли хост на приватную/служебную сеть (защита от SSRF).

    Хост считается небезопасным, если сам является приватным/loopback/
    link-local/reserved/multicast IP-адресом, либо резолвится (любой из
    адресов DNS-ответа) в такой адрес. Хост, который не удалось
    зарезолвить, тоже считается небезопасным (fail closed) — иначе нельзя
    дать гарантию, что итоговый IP не приватный.
    """
    try:
        addresses = [ipaddress.ip_address(hostname)]
    except ValueError:
        try:
            addresses = [
                ipaddress.ip_address(info[4][0])
                for info in socket.getaddrinfo(hostname, None)
            ]
        except (OSError, ValueError):
            return True

    return any(
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_reserved
        or addr.is_multicast
        or addr.is_unspecified
        for addr in addresses
    )


class FilePathRequest(BaseModel):
    """Схема запроса с путём к видеофайлу (#46: verify/repair, #106: path traversal)."""

    file_path: str = Field(..., min_length=1, description="Путь к видеофайлу")

    @field_validator("file_path", mode="after")
    @classmethod
    def validate_file_path(cls, v: str) -> str:
        """Проверяет безопасный синтаксис относительного Windows-пути."""
        path = PureWindowsPath(v)
        invalid_chars = '<>:"|?*'
        has_dot_component = "." in re.split(r"[\\/]", v)
        unsafe_part = any(
            part == ".."
            or part.endswith((" ", "."))
            or any(char in invalid_chars or ord(char) < 32 for char in part)
            or PureWindowsPath(part).is_reserved()
            for part in path.parts
        )

        if path.drive or path.root or has_dot_component or unsafe_part:
            raise ValueError(
                f"Path traversal detected: {v}. "
                "Use a relative path inside the configured output directory"
            )

        return v


class SwitchCaptureSourceRequest(BaseModel):
    """Схема запроса переключения источника захвата записи (#48)."""

    area: Literal["full", "window", "rect"] = Field(
        default="full",
        description="Тип нового источника захвата: full, window или rect",
    )
    window_title: str | None = Field(
        default=None,
        description="Заголовок окна для захвата (требуется если area='window')",
    )
    rect: list[int] | None = Field(
        default=None,
        description="Координаты прямоугольника [x1, y1, x2, y2] (требуется если area='rect')",
        min_length=4,
        max_length=4,
    )

    @field_validator("rect")
    @classmethod
    def validate_rect(cls, v: list[int] | None) -> list[int] | None:
        """Валидация координат прямоугольника."""
        if v is not None:
            if len(v) != 4:
                raise ValueError(
                    "rect должен содержать ровно 4 значения: [x1, y1, x2, y2]"
                )

            x1, y1, x2, y2 = v

            if x2 <= x1 or y2 <= y1:
                raise ValueError(
                    "x2 должен быть больше x1 и y2 должен быть больше y1"
                )

            if any(coord < 0 for coord in v):
                raise ValueError("Координаты не могут быть отрицательными")

        return v


class StartRecordingRequest(BaseModel):
    """Схема запроса для начала записи."""

    area: Literal["full", "window", "rect"] = Field(
        default="full",
        description="Тип области захвата: full, window или rect",
    )
    window_title: str | None = Field(
        default=None,
        description="Заголовок окна для захвата (требуется если area='window')",
    )
    rect: list[int] | None = Field(
        default=None,
        description="Координаты прямоугольника [x1, y1, x2, y2] (требуется если area='rect')",
        min_length=4,
        max_length=4,
    )
    audio: Literal["mic", "system", "none", "both"] = Field(
        default="none",
        description="Источник аудио: mic, system, none или both",
    )
    output_path: str | None = Field(
        default=None, description="Путь для сохранения файла записи"
    )
    fps: int = Field(
        default=30, ge=1, le=120, description="Кадров в секунду (1-120)"
    )
    codec: str = Field(default="libx264", description="Видеокодек")
    bitrate: str = Field(
        default="2M", description="Битрейт видео (например: 2M, 5000K)"
    )
    duration: int | None = Field(
        default=None, ge=1, description="Длительность записи в секундах"
    )
    mic_device: int | None = Field(
        default=None, description="Индекс устройства микрофона"
    )
    profile_id: str | None = Field(
        default=None, description="ID профиля для применения настроек"
    )

    @field_validator("rect")
    @classmethod
    def validate_rect(cls, v: list[int] | None) -> list[int] | None:
        """Валидация координат прямоугольника."""
        if v is not None:
            if len(v) != 4:
                raise ValueError(
                    "rect должен содержать ровно 4 значения: [x1, y1, x2, y2]"
                )

            x1, y1, x2, y2 = v

            if x2 <= x1 or y2 <= y1:
                raise ValueError(
                    "x2 должен быть больше x1 и y2 должен быть больше y1"
                )

            if any(coord < 0 for coord in v):
                raise ValueError("Координаты не могут быть отрицательными")

        return v

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str) -> str:
        """Валидация формата битрейта."""
        if not re.match(r"^\d+[KMk]?$", v):
            raise ValueError(
                "Битрейт должен быть в формате: число + опционально K/M (например: 2M, 5000K, 2000000)"
            )
        return v

    @model_validator(mode="after")
    def validate_area_requirements(self) -> "StartRecordingRequest":
        """Проверка требований для выбранного типа области."""
        if self.area == "window" and not self.window_title:
            raise ValueError('window_title обязателен когда area="window"')

        if self.area == "rect" and not self.rect:
            raise ValueError('rect обязателен когда area="rect"')

        return self


class MultiCaptureSourceRequest(BaseModel):
    """Схема одного источника мультиисточниковой записи (#51)."""

    label: str = Field(
        ..., min_length=1, description="Уникальная метка источника"
    )
    area: Literal["full", "window", "rect"] = Field(
        default="full",
        description="Тип области захвата: full, window или rect",
    )
    monitor_index: int = Field(
        default=0,
        ge=0,
        description="Индекс монитора для захвата (при area='full')",
    )
    window_title: str | None = Field(
        default=None,
        description="Заголовок окна для захвата (требуется если area='window')",
    )
    rect: list[int] | None = Field(
        default=None,
        description="Координаты прямоугольника [x1, y1, x2, y2] (требуется если area='rect')",
        min_length=4,
        max_length=4,
    )

    @field_validator("rect")
    @classmethod
    def validate_rect(cls, v: list[int] | None) -> list[int] | None:
        """Валидация координат прямоугольника."""
        if v is not None:
            if len(v) != 4:
                raise ValueError(
                    "rect должен содержать ровно 4 значения: [x1, y1, x2, y2]"
                )

            x1, y1, x2, y2 = v

            if x2 <= x1 or y2 <= y1:
                raise ValueError(
                    "x2 должен быть больше x1 и y2 должен быть больше y1"
                )

            if any(coord < 0 for coord in v):
                raise ValueError("Координаты не могут быть отрицательными")

        return v

    @model_validator(mode="after")
    def validate_area_requirements(self) -> "MultiCaptureSourceRequest":
        """Проверка требований для выбранного типа области."""
        if self.area == "window" and not self.window_title:
            raise ValueError('window_title обязателен когда area="window"')

        if self.area == "rect" and not self.rect:
            raise ValueError('rect обязателен когда area="rect"')

        return self


class StartMultiRecordingRequest(BaseModel):
    """Схема запроса для начала мультиисточниковой записи (#51)."""

    sources: list[MultiCaptureSourceRequest] = Field(
        ...,
        min_length=2,
        description="Источники захвата для одновременной записи (минимум 2)",
    )
    output_path: str | None = Field(
        default=None,
        description="Базовый путь вывода (каждый источник получит свой файл)",
    )
    fps: int = Field(
        default=30, ge=1, le=120, description="Кадров в секунду (1-120)"
    )
    codec: str = Field(default="libx264", description="Видеокодек")
    bitrate: str = Field(
        default="2M", description="Битрейт видео (например: 2M, 5000K)"
    )
    duration: int | None = Field(
        default=None, ge=1, description="Длительность записи в секундах"
    )
    audio_type: str = Field(
        default="none",
        description='Тип записи аудио: "none", "mic", "system", "both" (по умолчанию: "none")',
    )

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str) -> str:
        """Валидация формата битрейта."""
        if not re.match(r"^\d+[KMk]?$", v):
            raise ValueError(
                "Битрейт должен быть в формате: число + опционально K/M (например: 2M, 5000K, 2000000)"
            )
        return v

    @field_validator("sources")
    @classmethod
    def validate_unique_labels(
        cls, v: list[MultiCaptureSourceRequest]
    ) -> list[MultiCaptureSourceRequest]:
        """Проверка уникальности меток источников."""
        labels = [source.label for source in v]
        if len(labels) != len(set(labels)):
            raise ValueError(
                "Метки источников (label) должны быть уникальными"
            )
        return v


class CreateScheduleRequest(BaseModel):
    """Схема запроса для создания запланированной задачи."""

    name: str = Field(
        min_length=1, max_length=100, description="Название задачи"
    )
    trigger: Literal["once", "daily", "weekly", "interval", "cron"] = Field(
        description="Тип расписания: once, daily, weekly, interval или cron"
    )

    # Поля для разовой задачи
    datetime: str | None = Field(
        default=None,
        description="Дата и время выполнения (ISO формат) для trigger='once'",
    )

    # Поля для daily/weekly
    time: str | None = Field(
        default=None,
        description="Время выполнения в формате HH:MM для daily/weekly",
    )

    # Поля для weekly
    day_of_week: str | None = Field(
        default=None,
        description="Дни недели через запятую (0=Пн, 6=Вс) для weekly. Пример: '0,2,4'",
    )

    # Поля для interval
    hours: int | None = Field(
        default=None,
        ge=0,
        le=168,
        description="Интервал в часах для interval (0-168)",
    )
    minutes: int | None = Field(
        default=None,
        ge=0,
        le=59,
        description="Интервал в минутах для interval (0-59)",
    )

    # Поле для cron
    cron_expression: str | None = Field(
        default=None,
        description="Cron-выражение для trigger='cron'. Пример: '0 9 * * 1-5' (каждый будний день в 9:00)",
    )

    # Параметры записи
    params: StartRecordingRequest | None = Field(
        default=None, description="Параметры записи"
    )

    @field_validator("datetime")
    @classmethod
    def validate_datetime(cls, v: str | None) -> str | None:
        """Валидация формата datetime."""
        if v is not None:
            try:
                dt = datetime.fromisoformat(v)
                # Нормализуем к UTC для корректного сравнения
                if dt.tzinfo is None:
                    # Если часовой пояс не указан, считаем локальным временем
                    local_tz = tzlocal.get_localzone()
                    dt = dt.replace(tzinfo=local_tz)
                # Сравниваем с текущим временем в той же timezone
                now_utc = datetime.now(UTC)
                dt_utc = dt.astimezone(UTC)
                if dt_utc < now_utc:
                    raise ValueError("datetime должен быть в будущем")
            except ValueError as e:
                raise ValueError(f"Некорректный формат datetime: {e}")  # noqa: B904
        return v

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str | None) -> str | None:
        """Валидация формата времени."""
        if v is not None:  # noqa: SIM102
            if not re.match(r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$", v):
                raise ValueError(
                    "time должен быть в формате HH:MM (например: 14:30)"
                )
        return v

    @field_validator("day_of_week")
    @classmethod
    def validate_day_of_week(cls, v: str | None) -> str | None:
        """Валидация дней недели."""
        if v is not None:
            try:
                days = [int(d.strip()) for d in v.split(",")]
                for day in days:
                    if not 0 <= day <= 6:
                        raise ValueError(
                            "Дни недели должны быть от 0 (Пн) до 6 (Вс)"
                        )
            except ValueError as e:
                raise ValueError(
                    f"Некорректный формат дней недели: {e}"
                ) from e
        return v

    @field_validator("cron_expression")
    @classmethod
    def validate_cron_expression(cls, v: str | None) -> str | None:
        """Валидация cron-выражения."""
        if v is not None:
            # Стандартное cron-выражение имеет 5 полей:
            # минута час день_месяца месяц день_недели
            # Пример: "0 9 * * 1-5" - каждый будний день в 9:00
            parts = v.strip().split()
            if len(parts) != 5:
                raise ValueError(
                    "cron_expression должен содержать 5 полей: "
                    "минута час день_месяца месяц день_недели. "
                    'Пример: "0 9 * * 1-5"'
                )
            # Базовая проверка каждого поля
            for i, part in enumerate(parts):
                if not re.match(r"^[\d*/-]+$", part) and part != "*":
                    raise ValueError(
                        f'Некорректное cron-выражение: поле {i + 1} "{part}" '
                        "должно содержать только цифры, *, / или -"
                    )
        return v

    @model_validator(mode="after")
    def validate_trigger_requirements(self) -> "CreateScheduleRequest":
        """Проверка обязательных полей для каждого типа расписания."""
        if self.trigger == "once" and not self.datetime:
            raise ValueError('datetime обязателен когда trigger="once"')

        if self.trigger in ("daily", "weekly") and not self.time:
            raise ValueError(f'time обязателен когда trigger="{self.trigger}"')

        if self.trigger == "weekly" and not self.day_of_week:
            raise ValueError('day_of_week обязателен когда trigger="weekly"')

        if self.trigger == "interval":
            if self.hours is None and self.minutes is None:
                raise ValueError(
                    'hours или minutes обязательны когда trigger="interval"'
                )
            if self.hours == 0 and self.minutes == 0:
                raise ValueError("Интервал должен быть больше 0")

        if self.trigger == "cron" and not self.cron_expression:
            raise ValueError('cron_expression обязателен когда trigger="cron"')

        return self


class UpdateScheduleRequest(BaseModel):
    """Схема запроса для обновления запланированной задачи."""

    id: str = Field(min_length=1, description="ID задачи")
    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Название задачи",
    )
    enabled: bool | None = Field(
        default=None, description="Включена ли задача"
    )
    params: StartRecordingRequest | None = Field(
        default=None, description="Параметры записи"
    )
    time: str | None = Field(default=None, description="Время выполнения")
    day_of_week: str | None = Field(default=None, description="Дни недели")

    @field_validator("time")
    @classmethod
    def validate_time(cls, v: str | None) -> str | None:
        """Валидация формата времени."""
        if v is not None and not re.match(
            r"^([01]?[0-9]|2[0-3]):([0-5][0-9])$", v
        ):
            raise ValueError("time должен быть в формате HH:MM")
        return v


class ToggleScheduleRequest(BaseModel):
    """Схема запроса для включения/выключения задачи."""

    enabled: bool = Field(
        description="Включить (true) или выключить (false) задачу"
    )


class ConfigureWebhookRequest(BaseModel):
    """Схема запроса настройки webhook-уведомлений."""

    url: str | None = Field(default=None, description="URL получателя webhook")
    secret: str | None = Field(
        default=None,
        description="Секрет для HMAC-подписи; не передавайте, чтобы "
        "оставить текущий секрет или сгенерировать новый автоматически",
    )
    enabled: bool = Field(
        default=False, description="Включить отправку webhook-уведомлений"
    )
    allow_private_network: bool = Field(
        default=False,
        description="Разрешить приватные/internal-адреса в URL webhook "
        "(локальная разработка/тесты); по умолчанию запрещено из-за "
        "риска SSRF",
    )

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        """Проверяет, что URL начинается с http:// или https://."""
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not normalized.startswith(("http://", "https://")):
            raise ValueError("URL должен начинаться с http:// или https://")
        return normalized

    @model_validator(mode="after")
    def validate_url_not_private(self) -> "ConfigureWebhookRequest":
        """Запрещает приватные/internal-адреса в URL webhook (SSRF, #73)."""
        if self.url is None or self.allow_private_network:
            return self

        hostname = urlparse(self.url).hostname
        if hostname and _is_private_or_reserved_host(hostname):
            raise ValueError(
                "URL webhook не может указывать на приватный/internal "
                "адрес (риск SSRF); для локальной разработки передайте "
                "allow_private_network=true"
            )
        return self


class UpdateConfigRequest(BaseModel):
    """Схема запроса для обновления конфигурации."""

    video: Optional["UpdateConfigVideoRequest"] = Field(
        default=None, description="Видео настройки"
    )
    audio: Optional["UpdateConfigAudioRequest"] = Field(
        default=None, description="Аудио настройки"
    )
    output: Optional["UpdateConfigOutputRequest"] = Field(
        default=None, description="Настройки вывода"
    )
    app: Optional["UpdateConfigAppRequest"] = Field(
        default=None, description="Настройки приложения"
    )

    # Видео настройки
    fps: int | None = Field(
        default=None, ge=1, le=120, description="Кадров в секунду"
    )
    codec: str | None = Field(default=None, description="Видеокодек")
    bitrate: str | None = Field(default=None, description="Битрейт видео")

    # Аудио настройки
    record_mic: bool | None = Field(
        default=None, description="Записывать микрофон"
    )
    record_system: bool | None = Field(
        default=None, description="Записывать системное аудио"
    )

    # Настройки вывода
    default_path: str | None = Field(
        default=None, description="Путь для сохранения записей по умолчанию"
    )
    filename_template: str | None = Field(
        default=None, description="Шаблон имени файла"
    )

    # Настройки приложения
    minimize_to_tray: bool | None = Field(
        default=None, description="Сворачивать в трей"
    )
    show_notifications: bool | None = Field(
        default=None, description="Показывать уведомления"
    )
    language: str | None = Field(default=None, description="Язык интерфейса")

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Валидация формата битрейта."""
        if v is not None and not re.match(r"^\d+[KMk]?$", v):
            raise ValueError(
                "Битрейт должен быть в формате: число + опционально K/M"
            )
        return v

    @model_validator(mode="after")
    def sync_nested_sections(self) -> "UpdateConfigRequest":
        """Заполняет flat-поля значениями из nested-полей для совместимости."""
        if self.video is not None:
            if self.fps is None and self.video.fps is not None:
                self.fps = self.video.fps
            if self.codec is None and self.video.codec is not None:
                self.codec = self.video.codec
            if self.bitrate is None and self.video.bitrate is not None:
                self.bitrate = self.video.bitrate

        if self.audio is not None:
            if self.record_mic is None and self.audio.record_mic is not None:
                self.record_mic = self.audio.record_mic
            if (
                self.record_system is None
                and self.audio.record_system is not None
            ):
                self.record_system = self.audio.record_system

        if self.output is not None:
            if (
                self.default_path is None
                and self.output.default_path is not None
            ):
                self.default_path = self.output.default_path
            if (
                self.filename_template is None
                and self.output.filename_template is not None
            ):
                self.filename_template = self.output.filename_template

        if self.app is not None:
            if (
                self.minimize_to_tray is None
                and self.app.minimize_to_tray is not None
            ):
                self.minimize_to_tray = self.app.minimize_to_tray
            if (
                self.show_notifications is None
                and self.app.show_notifications is not None
            ):
                self.show_notifications = self.app.show_notifications
            if self.language is None and self.app.language is not None:
                self.language = self.app.language

        return self


class UpdateConfigVideoRequest(BaseModel):
    """Вложенная схема видео-настроек."""

    fps: int | None = Field(
        default=None, ge=1, le=120, description="Кадров в секунду"
    )
    codec: str | None = Field(default=None, description="Видеокодек")
    bitrate: str | None = Field(default=None, description="Битрейт видео")

    @field_validator("bitrate")
    @classmethod
    def validate_bitrate(cls, v: str | None) -> str | None:
        """Валидация формата битрейта."""
        if v is not None and not re.match(r"^\d+[KMk]?$", v):
            raise ValueError(
                "Битрейт должен быть в формате: число + опционально K/M"
            )
        return v


class UpdateConfigAudioRequest(BaseModel):
    """Вложенная схема аудио-настроек."""

    record_mic: bool | None = Field(
        default=None, description="Записывать микрофон"
    )
    record_system: bool | None = Field(
        default=None, description="Записывать системное аудио"
    )


class UpdateConfigOutputRequest(BaseModel):
    """Вложенная схема настроек вывода."""

    default_path: str | None = Field(
        default=None, description="Путь для сохранения записей по умолчанию"
    )
    filename_template: str | None = Field(
        default=None, description="Шаблон имени файла"
    )


class UpdateConfigAppRequest(BaseModel):
    """Вложенная схема настроек приложения."""

    minimize_to_tray: bool | None = Field(
        default=None, description="Сворачивать в трей"
    )
    show_notifications: bool | None = Field(
        default=None, description="Показывать уведомления"
    )
    language: str | None = Field(default=None, description="Язык интерфейса")


UpdateConfigRequest.model_rebuild()


# Модели ответов API


class APIResponse(BaseModel):
    """Базовая модель ответа API."""

    success: bool = Field(description="Успешность операции")
    data: dict | None = Field(default=None, description="Данные ответа")
    error: str | None = Field(default=None, description="Сообщение об ошибке")


class StatusResponse(BaseModel):
    """Модель ответа статуса записи."""

    is_recording: bool = Field(description="Идёт ли запись")
    is_paused: bool = Field(description="На паузе ли запись")
    elapsed_time: float = Field(description="Прошедшее время в секундах")
    current_file: str | None = Field(
        default=None, description="Текущий файл записи"
    )
    frame_count: int | None = Field(
        default=None, description="Количество записанных кадров"
    )


class DeviceInfo(BaseModel):
    """Модель информации об устройстве."""

    name: str = Field(description="Название устройства")
    index: int = Field(description="Индекс устройства")
    channels: int = Field(description="Количество каналов")


class WindowInfo(BaseModel):
    """Модель информации об окне."""

    title: str = Field(description="Заголовок окна")
    x: int = Field(description="Координата X")
    y: int = Field(description="Координата Y")
    width: int = Field(description="Ширина окна")
    height: int = Field(description="Высота окна")


# Схемы профилей записи (Issue #117)


class ProfileVideoSettingsSchema(BaseModel):
    """Схема настроек видео в профиле."""

    fps: int = Field(default=30, ge=1, le=120)
    codec: str = Field(default="libx264")
    bitrate: str = Field(default="2M")
    format: str = Field(default="mp4")
    preset: str = Field(default="medium")
    compression: bool = Field(default=True)
    verify_on_complete: bool = Field(default=True)
    auto_repair_corrupted: bool = Field(default=False)


class ProfileAudioSettingsSchema(BaseModel):
    """Схема настроек аудио в профиле."""

    record_mic: bool = Field(default=True)
    record_system: bool = Field(default=False)
    mic_device: str | None = Field(default=None)
    system_device: str | None = Field(default=None)
    sample_rate: int = Field(default=44100, ge=8000, le=192000)
    channels: int = Field(default=2, ge=1, le=8)


class ProfileCaptureSettingsSchema(BaseModel):
    """Схема настроек захвата в профиле."""

    area_type: Literal["full", "window", "rect"] = Field(default="full")
    window_title: str | None = Field(default=None)
    rect_coords: list[int] | None = Field(default=None)


class CreateProfileRequest(BaseModel):
    """Схема запроса создания профиля записи."""

    name: str = Field(
        ..., min_length=1, max_length=100, description="Название профиля"
    )
    description: str = Field(
        default="", max_length=500, description="Описание профиля"
    )
    icon: str = Field(
        default="⚙️", max_length=10, description="Иконка или эмодзи"
    )
    video: ProfileVideoSettingsSchema | None = Field(
        default=None, description="Настройки видео"
    )
    audio: ProfileAudioSettingsSchema | None = Field(
        default=None, description="Настройки аудио"
    )
    capture: ProfileCaptureSettingsSchema | None = Field(
        default=None, description="Настройки захвата"
    )
    is_default: bool = Field(
        default=False, description="Установить профилем по умолчанию"
    )


class UpdateProfileRequest(BaseModel):
    """Схема запроса обновления профиля записи."""

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        description="Новое название профиля",
    )
    description: str | None = Field(
        default=None, max_length=500, description="Новое описание"
    )
    icon: str | None = Field(
        default=None, max_length=10, description="Новая иконка"
    )
    video: ProfileVideoSettingsSchema | None = Field(
        default=None, description="Новые настройки видео"
    )
    audio: ProfileAudioSettingsSchema | None = Field(
        default=None, description="Новые настройки аудио"
    )
    capture: ProfileCaptureSettingsSchema | None = Field(
        default=None, description="Новые настройки захвата"
    )
    is_default: bool | None = Field(
        default=None, description="Сделать профилем по умолчанию"
    )


class ImportProfileRequest(BaseModel):
    """Схема импорта профиля из JSON."""

    schema_version: str | None = Field(
        default=None, alias="schema", description="Версия схемы"
    )
    profile: dict | None = Field(default=None, description="Данные профиля")
    name: str | None = Field(
        default=None, description="Название профиля (при прямом импорте)"
    )
    description: str | None = Field(default=None)
    icon: str | None = Field(default=None)
    video: dict | None = Field(default=None)
    audio: dict | None = Field(default=None)
    capture: dict | None = Field(default=None)


class RecordingMetricsData(BaseModel):
    """Данные метрик производительности видеозаписи (#114)."""

    actual_fps: float = Field(default=0.0, description="Фактический FPS")
    target_fps: int = Field(default=30, description="Целевой FPS")
    jitter_ms: float = Field(
        default=0.0, description="Дрожание межкадровых интервалов в мс"
    )
    frames_dropped: int = Field(
        default=0, description="Количество пропущенных кадров"
    )
    encode_latency_ms: float = Field(
        default=0.0, description="Средняя задержка записи кадра в мс"
    )
    buffer_fill_percent: float = Field(
        default=0.0, description="Заполнение буфера кадров в %"
    )
    total_frames: int = Field(default=0, description="Всего записанных кадров")


class RecordingMetricsResponse(BaseModel):
    """Схема ответа на запрос метрик записи (#114)."""

    success: bool = True
    data: RecordingMetricsData


class PostProcessingConfigData(BaseModel):
    """Данные настроек конвейера постобработки (#118)."""

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


class PostProcessingConfigResponse(BaseModel):
    """Схема ответа с настройками постобработки."""

    success: bool = True
    data: PostProcessingConfigData


class UpdatePostProcessingConfigRequest(BaseModel):
    """Схема запроса на обновление настроек постобработки."""

    enabled: bool | None = None
    transcode_enabled: bool | None = None
    transcode_format: str | None = None
    transcode_codec: str | None = None
    compress_enabled: bool | None = None
    compress_crf: int | None = Field(default=None, ge=0, le=51)
    trim_silence_enabled: bool | None = None
    trim_silence_threshold_db: int | None = Field(default=None, le=0)
    generate_gif_enabled: bool | None = None
    gif_duration_seconds: int | None = Field(default=None, ge=1, le=60)
    gif_fps: int | None = Field(default=None, ge=1, le=30)
    copy_enabled: bool | None = None
    copy_target_folder: str | None = None
    open_explorer_on_finish: bool | None = None
    webhook_enabled: bool | None = None
    webhook_url: str | None = None
    transcription_enabled: bool | None = None
    transcription_mode: str | None = None
    transcription_model: str | None = None
    transcription_output_format: str | None = None
    transcription_language: str | None = None
    transcription_api_key: str | None = None
    transcription_api_base: str | None = None
    step_timeout_seconds: int | None = Field(default=None, ge=10, le=3600)


class PostProcessingStatusData(BaseModel):
    """Данные текущего статуса постобработки."""

    is_running: bool = False
    last_result: dict[str, Any] | None = None


class PostProcessingStatusResponse(BaseModel):
    """Схема ответа со статусом постобработки."""

    success: bool = True
    data: PostProcessingStatusData


class RunPostProcessingRequest(BaseModel):
    """Схема запроса запуска постобработки для файла."""

    file_path: str = Field(description="Путь к видеофайлу для постобработки")
    params: dict[str, Any] | None = Field(
        default=None,
        description="Параметры переопределения шагов постобработки",
    )


# === Схемы авто-обновления приложения (#128) ===


class UpdateAppConfigRequest(BaseModel):
    """Схема запроса обновления конфигурации авто-обновлений."""

    check_on_startup: bool | None = None
    auto_download: bool | None = None
    channel: str | None = None
    check_interval_hours: int | None = Field(default=None, ge=1, le=720)
    ignored_version: str | None = None


class UpdateAppConfigData(BaseModel):
    """Данные конфигурации авто-обновлений."""

    check_on_startup: bool = True
    auto_download: bool = False
    channel: str = "stable"
    check_interval_hours: int = 24
    last_checked_at: str | None = None
    ignored_version: str | None = None


class UpdateAppConfigResponse(BaseModel):
    """Схема ответа с настройками авто-обновлений."""

    success: bool = True
    data: UpdateAppConfigData


class CheckUpdateApiRequest(BaseModel):
    """Схема запроса проверки обновлений."""

    force: bool = False
    channel: str = "stable"


class CheckUpdateApiResponse(BaseModel):
    """Схема ответа проверки обновлений."""

    success: bool = True
    data: dict[str, Any]


class DownloadUpdateApiRequest(BaseModel):
    """Схема запроса скачивания обновления."""

    version: str | None = None


class DownloadUpdateApiResponse(BaseModel):
    """Схема ответа скачивания обновления."""

    success: bool = True
    data: dict[str, Any]


class ApplyUpdateApiResponse(BaseModel):
    """Схема ответа применения обновления."""

    success: bool = True
    data: dict[str, Any]


class UpdateStatusApiResponse(BaseModel):
    """Схема ответа со статусом подсистемы обновлений."""

    success: bool = True
    data: dict[str, Any]
