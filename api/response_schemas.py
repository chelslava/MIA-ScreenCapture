"""Pydantic-модели компонентов OpenAPI, не покрытых api/schemas.py.

Источник истины для компонентов спецификации (issue #214): модели
запросов живут в api/schemas.py, модели ответов — здесь. Реестр
COMPONENT_MODELS сопоставляет имена компонентов спеки с классами;
генератор api/openapi.py строит из него components.schemas.

OpenAPI `example` на поле задаётся статическим словарём в
json_schema_extra — Pydantic сливает его со схемой поля.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from api.schemas import CreateScheduleRequest, StartRecordingRequest


def _example(value: Any) -> dict[str, Any]:
    """Единый способ задать OpenAPI `example` в схеме поля."""
    return {"example": value}


class ApiErrorBody(BaseModel):
    """Тело ошибки: код, сообщение и произвольные детали."""

    code: str = Field(json_schema_extra=_example("bad_request"))
    message: str = Field(json_schema_extra=_example("Ошибка запроса"))
    # Детали произвольной формы: сервер присылает список, объект,
    # строку или число в зависимости от источника ошибки
    details: list[Any] | dict[str, Any] | str | int | float | bool = Field(
        json_schema_extra=_example([])
    )


class FieldErrorItem(BaseModel):
    """Один элемент детализации ошибки валидации."""

    field: str = Field(json_schema_extra=_example("fps"))
    message: str = Field(
        json_schema_extra=_example("Значение должно быть от 1 до 120")
    )
    type: str = Field(json_schema_extra=_example("value_error"))


class ValidationErrorBody(BaseModel):
    """Тело ошибки валидации с массивом details."""

    code: str = Field(json_schema_extra=_example("validation_error"))
    message: str = Field(json_schema_extra=_example("Ошибка валидации данных"))
    details: list[FieldErrorItem]


class ApiError(BaseModel):
    """Конверт ошибки: success=False + тело ошибки + trace_id."""

    success: bool = Field(json_schema_extra=_example(False))
    error: ApiErrorBody
    trace_id: str = Field(json_schema_extra=_example("req_1234567890abcdef"))


class ApiValidationError(BaseModel):
    """Конверт ошибки валидации: details — массив FieldErrorItem."""

    success: bool = Field(json_schema_extra=_example(False))
    error: ValidationErrorBody
    trace_id: str = Field(json_schema_extra=_example("req_1234567890abcdef"))


class StatusData(BaseModel):
    """Состояние записи в конверте /status."""

    is_recording: bool = Field(json_schema_extra=_example(True))
    is_paused: bool = Field(json_schema_extra=_example(False))
    elapsed_time: int = Field(
        json_schema_extra={
            **_example(120),
            "description": "Время записи в секундах",
        },
    )
    current_file: str | None = Field(
        json_schema_extra=_example("C:/Videos/recording_20260320.mp4"),
    )
    output_path: str | None = Field(
        json_schema_extra=_example("C:/Videos/recording_20260320.mp4"),
    )


class Status(BaseModel):
    """Конверт ответа /status: success + data."""

    success: bool = Field(json_schema_extra=_example(True))
    data: StatusData


class WebSocketStats(BaseModel):
    """Статистика транспорта WebSocket (вложение в Health)."""

    buffered_events: int | None = Field(
        default=None, ge=0, json_schema_extra=_example(1)
    )
    events_published_total: int | None = Field(
        default=None, ge=0, json_schema_extra=_example(1)
    )
    transport_ready: bool = Field(json_schema_extra=_example(True))
    attached_to_event_bus: bool | None = Field(
        default=None, json_schema_extra=_example(False)
    )


class Health(BaseModel):
    """Ответ /health: состояние сервера и WebSocket-транспорта."""

    status: str = Field(json_schema_extra=_example("ok"))
    timestamp: str = Field(
        json_schema_extra=_example("2026-03-23T12:00:00+00:00")
    )
    version: str = Field(json_schema_extra=_example("1.8.0"))
    uptime_seconds: float = Field(json_schema_extra=_example(12.345))
    websocket: WebSocketStats


class Event(BaseModel):
    """Событие шины: тип, время и произвольные данные."""

    type: str = Field(json_schema_extra=_example("started"))
    timestamp: str = Field(
        json_schema_extra=_example("2026-03-23T12:00:00+00:00")
    )
    data: dict[str, Any] = Field(
        json_schema_extra={"additionalProperties": True}
    )


class ScheduleTask(BaseModel):
    """Задача планировщика в ответах /schedule."""

    id: str = Field(json_schema_extra=_example("task_123"))
    name: str = Field(json_schema_extra=_example("Ежедневная запись"))
    trigger: str = Field(json_schema_extra=_example("daily"))
    enabled: bool = Field(json_schema_extra=_example(True))
    next_run: str | None = Field(
        default=None, json_schema_extra=_example("2026-03-21T10:00:00")
    )
    params: dict[str, Any] = Field(
        json_schema_extra={"description": "Параметры записи"}
    )


class Window(BaseModel):
    """Информация об окне для захвата."""

    title: str = Field(json_schema_extra=_example("Visual Studio Code"))
    rect: list[int] = Field(json_schema_extra=_example([100, 100, 1920, 1080]))


class AudioDevice(BaseModel):
    """Информация об аудиоустройстве."""

    id: int = Field(json_schema_extra=_example(1))
    name: str = Field(json_schema_extra=_example("Микрофон (Realtek Audio)"))
    channels: int = Field(json_schema_extra=_example(2))
    sample_rate: int = Field(json_schema_extra=_example(44100))


class ConfigVideo(BaseModel):
    """Видео-секция Config."""

    fps: int = Field(json_schema_extra=_example(30))
    codec: str = Field(json_schema_extra=_example("libx264"))
    bitrate: str = Field(json_schema_extra=_example("5M"))


class ConfigAudio(BaseModel):
    """Аудио-секция Config."""

    sample_rate: int = Field(json_schema_extra=_example(44100))
    channels: int = Field(json_schema_extra=_example(2))


class ConfigOutput(BaseModel):
    """Секция вывода Config."""

    directory: str = Field(json_schema_extra=_example("C:/Videos"))
    filename_pattern: str = Field(
        json_schema_extra=_example("recording_{date}_{time}")
    )


class Config(BaseModel):
    """Конфигурация записи в ответах /config."""

    video: ConfigVideo
    audio: ConfigAudio
    output: ConfigOutput


# Реестр компонентов спеки: имя в components.schemas -> Pydantic-класс.
# Модели с вложенными классами (Error/ValidationError) инлайнятся
# генератором целиком; остальные вложения ($defs) поднимаются
# в отдельные компоненты по имени класса.
COMPONENT_MODELS: dict[str, type[BaseModel]] = {
    "Error": ApiError,
    "ValidationError": ApiValidationError,
    "Status": Status,
    "Health": Health,
    "Event": Event,
    "WebSocketStats": WebSocketStats,
    "ScheduleTask": ScheduleTask,
    "Window": Window,
    "AudioDevice": AudioDevice,
    "Config": Config,
    "StartRecordingRequest": StartRecordingRequest,
    "CreateScheduleRequest": CreateScheduleRequest,
}

# Компоненты, у которых вложенные модели инлайнятся вместо $ref
# (структурно совместимо с рукописной спецификацией).
INLINE_NESTED_COMPONENTS: frozenset[str] = frozenset(
    {"Error", "ValidationError"}
)
