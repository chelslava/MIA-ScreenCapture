"""
Модуль Swagger документации API
================================

Предоставляет OpenAPI/Swagger спецификацию для REST API.
"""

from copy import deepcopy
from typing import Any

# OpenAPI спецификация для API MIA-ScreenCapture
SWAGGER_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "MIA-ScreenCapture API",
        "description": "REST API для управления записью экрана",
        "version": "1.4.6.dev0",
        "contact": {
            "name": "MIA Development Team",
        },
        "license": {
            "name": "MIT",
        },
    },
    "servers": [
        {
            "url": "http://localhost:5000",
            "description": "Локальный сервер разработки",
        }
    ],
    "security": [{"ApiKeyAuth": []}],
    "components": {
        "securitySchemes": {
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API ключ для аутентификации",
            }
        },
        "schemas": {
            "Error": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": False,
                    },
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "example": "bad_request",
                            },
                            "message": {
                                "type": "string",
                                "example": "Ошибка запроса",
                            },
                            "details": {
                                "nullable": True,
                                "oneOf": [
                                    {
                                        "type": "array",
                                    },
                                    {
                                        "type": "object",
                                    },
                                    {
                                        "type": "string",
                                    },
                                    {
                                        "type": "integer",
                                    },
                                    {
                                        "type": "number",
                                    },
                                    {
                                        "type": "boolean",
                                    },
                                ],
                            },
                        },
                        "required": ["code", "message", "details"],
                    },
                    "trace_id": {
                        "type": "string",
                        "example": "req_1234567890abcdef",
                    },
                },
                "required": ["success", "error", "trace_id"],
            },
            "ValidationError": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": False,
                    },
                    "error": {
                        "type": "object",
                        "properties": {
                            "code": {
                                "type": "string",
                                "example": "validation_error",
                            },
                            "message": {
                                "type": "string",
                                "example": "Ошибка валидации данных",
                            },
                            "details": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "field": {
                                            "type": "string",
                                            "example": "fps",
                                        },
                                        "message": {
                                            "type": "string",
                                            "example": "Значение должно быть от 1 до 120",
                                        },
                                        "type": {
                                            "type": "string",
                                            "example": "value_error",
                                        },
                                    },
                                    "required": [
                                        "field",
                                        "message",
                                        "type",
                                    ],
                                },
                            },
                        },
                        "required": ["code", "message", "details"],
                    },
                    "trace_id": {
                        "type": "string",
                        "example": "req_1234567890abcdef",
                    },
                },
                "required": ["success", "error", "trace_id"],
            },
            "Event": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "example": "started",
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-03-23T12:00:00+00:00",
                    },
                    "data": {
                        "type": "object",
                        "additionalProperties": True,
                    },
                },
                "required": ["type", "timestamp", "data"],
            },
            "WebSocketStats": {
                "type": "object",
                "properties": {
                    "buffered_events": {
                        "type": "integer",
                        "minimum": 0,
                        "example": 1,
                    },
                    "events_published_total": {
                        "type": "integer",
                        "minimum": 0,
                        "example": 1,
                    },
                    "transport_ready": {
                        "type": "boolean",
                        "example": True,
                    },
                    "attached_to_event_bus": {
                        "type": "boolean",
                        "example": False,
                    },
                },
                "required": ["transport_ready"],
            },
            "Health": {
                "type": "object",
                "properties": {
                    "status": {
                        "type": "string",
                        "example": "ok",
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-03-23T12:00:00+00:00",
                    },
                    "version": {
                        "type": "string",
                        "example": "1.4.6.dev0",
                    },
                    "uptime_seconds": {
                        "type": "number",
                        "example": 12.345,
                    },
                    "websocket": {
                        "$ref": "#/components/schemas/WebSocketStats",
                    },
                },
                "required": [
                    "status",
                    "timestamp",
                    "version",
                    "uptime_seconds",
                    "websocket",
                ],
            },
            "Status": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": True,
                    },
                    "data": {
                        "type": "object",
                        "properties": {
                            "is_recording": {
                                "type": "boolean",
                                "example": True,
                            },
                            "is_paused": {
                                "type": "boolean",
                                "example": False,
                            },
                            "elapsed_time": {
                                "type": "integer",
                                "example": 120,
                                "description": "Время записи в секундах",
                            },
                            "current_file": {
                                "type": "string",
                                "nullable": True,
                                "example": "C:/Videos/recording_20260320.mp4",
                            },
                            "output_path": {
                                "type": "string",
                                "example": "C:/Videos/recording_20260320.mp4",
                                "nullable": True,
                            },
                        },
                    },
                },
            },
            "StartRecordingRequest": {
                "type": "object",
                "properties": {
                    "area": {
                        "type": "string",
                        "enum": ["full", "window", "rect"],
                        "default": "full",
                        "description": "Область захвата",
                    },
                    "window_title": {
                        "type": "string",
                        "description": "Заголовок окна (для area=window)",
                    },
                    "rect": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                        },
                        "minItems": 4,
                        "maxItems": 4,
                        "example": [0, 0, 1920, 1080],
                        "description": "Координаты [x1, y1, x2, y2] (для area=rect)",
                    },
                    "audio": {
                        "type": "string",
                        "enum": ["mic", "system", "none", "both"],
                        "default": "none",
                        "description": "Источник аудио",
                    },
                    "output_path": {
                        "type": "string",
                        "description": "Путь к выходному файлу",
                    },
                    "fps": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 120,
                        "default": 30,
                        "description": "Кадров в секунду",
                    },
                    "codec": {
                        "type": "string",
                        "default": "libx264",
                        "description": "Видеокодек",
                    },
                    "bitrate": {
                        "type": "string",
                        "pattern": r"^\d+[KM]?$",
                        "example": "5M",
                        "description": "Битрейт (например: 5M, 5000K)",
                    },
                    "duration": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "Максимальная длительность в секундах",
                    },
                },
            },
            "ScheduleTask": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "example": "task_123",
                    },
                    "name": {
                        "type": "string",
                        "example": "Ежедневная запись",
                    },
                    "trigger": {
                        "type": "string",
                        "enum": [
                            "once",
                            "daily",
                            "weekly",
                            "interval",
                            "cron",
                        ],
                    },
                    "enabled": {
                        "type": "boolean",
                        "example": True,
                    },
                    "next_run": {
                        "type": "string",
                        "format": "date-time",
                        "example": "2026-03-21T10:00:00",
                    },
                    "params": {
                        "type": "object",
                        "description": "Параметры записи",
                    },
                },
            },
            "CreateScheduleRequest": {
                "type": "object",
                "required": ["name", "trigger"],
                "properties": {
                    "name": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 100,
                        "example": "Ежедневная запись",
                    },
                    "trigger": {
                        "type": "string",
                        "enum": [
                            "once",
                            "daily",
                            "weekly",
                            "interval",
                            "cron",
                        ],
                    },
                    "datetime": {
                        "type": "string",
                        "format": "date-time",
                        "description": "Дата и время (для trigger=once)",
                    },
                    "time": {
                        "type": "string",
                        "pattern": r"^[0-2][0-9]:[0-5][0-9]$",
                        "example": "10:00",
                        "description": "Время (для trigger=daily/weekly)",
                    },
                    "day_of_week": {
                        "type": "string",
                        "example": "0,1,2,3,4",
                        "description": "Дни недели (0=Пн, для trigger=weekly)",
                    },
                    "hours": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Часы (для trigger=interval)",
                    },
                    "minutes": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Минуты (для trigger=interval)",
                    },
                    "cron_expression": {
                        "type": "string",
                        "example": "0 10 * * 1-5",
                        "description": "Cron выражение (для trigger=cron)",
                    },
                    "params": {
                        "type": "object",
                        "description": "Параметры записи",
                    },
                },
            },
            "AudioDevice": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "integer",
                        "example": 1,
                    },
                    "name": {
                        "type": "string",
                        "example": "Микрофон (Realtek Audio)",
                    },
                    "channels": {
                        "type": "integer",
                        "example": 2,
                    },
                    "sample_rate": {
                        "type": "integer",
                        "example": 44100,
                    },
                },
            },
            "Window": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "example": "Visual Studio Code",
                    },
                    "rect": {
                        "type": "array",
                        "items": {
                            "type": "integer",
                        },
                        "example": [100, 100, 1920, 1080],
                    },
                },
            },
            "Config": {
                "type": "object",
                "properties": {
                    "video": {
                        "type": "object",
                        "properties": {
                            "fps": {
                                "type": "integer",
                                "example": 30,
                            },
                            "codec": {
                                "type": "string",
                                "example": "libx264",
                            },
                            "bitrate": {
                                "type": "string",
                                "example": "5M",
                            },
                        },
                    },
                    "audio": {
                        "type": "object",
                        "properties": {
                            "sample_rate": {
                                "type": "integer",
                                "example": 44100,
                            },
                            "channels": {
                                "type": "integer",
                                "example": 2,
                            },
                        },
                    },
                    "output": {
                        "type": "object",
                        "properties": {
                            "directory": {
                                "type": "string",
                                "example": "C:/Videos",
                            },
                            "filename_pattern": {
                                "type": "string",
                                "example": "recording_{date}_{time}",
                            },
                        },
                    },
                },
            },
        },
    },
    "paths": {
        "/api/status": {
            "get": {
                "summary": "Получить статус записи",
                "description": "Возвращает текущий статус записи экрана",
                "operationId": "getStatus",
                "responses": {
                    "200": {
                        "description": "Успешный ответ",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Status",
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Не авторизован",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/health": {
            "get": {
                "summary": "Проверить состояние сервиса",
                "description": "Возвращает health payload с версией, uptime и состоянием real-time транспорта",
                "operationId": "getHealth",
                "security": [],
                "responses": {
                    "200": {
                        "description": "Сервис работает",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Health",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/start": {
            "post": {
                "summary": "Начать запись",
                "description": "Запускает новую запись экрана с указанными параметрами",
                "operationId": "startRecording",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/StartRecordingRequest",
                            },
                            "examples": {
                                "full_screen": {
                                    "summary": "Полный экран (валидный минимум)",
                                    "value": {
                                        "area": "full",
                                        "audio": "mic",
                                        "fps": 30,
                                        "codec": "libx264",
                                        "bitrate": "5M",
                                    },
                                },
                                "window_capture": {
                                    "summary": "Захват окна",
                                    "value": {
                                        "area": "window",
                                        "window_title": "Visual Studio Code",
                                        "audio": "none",
                                        "fps": 30,
                                        "codec": "libx264",
                                        "bitrate": "3M",
                                        "duration": 60,
                                    },
                                },
                                "rect_capture": {
                                    "summary": "Захват области",
                                    "value": {
                                        "area": "rect",
                                        "rect": [100, 100, 1600, 900],
                                        "audio": "system",
                                        "fps": 60,
                                        "codec": "libx264",
                                        "bitrate": "8M",
                                    },
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Запись начата",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "output_path": {
                                                    "type": "string",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Ошибка валидации",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ValidationError",
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Не авторизован",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/stop": {
            "post": {
                "summary": "Остановить запись",
                "description": "Останавливает текущую запись",
                "operationId": "stopRecording",
                "responses": {
                    "200": {
                        "description": "Запись остановлена",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "output_path": {
                                                    "type": "string",
                                                },
                                                "duration": {
                                                    "type": "integer",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Нет активной записи",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/pause": {
            "post": {
                "summary": "Пауза/возобновление записи",
                "description": "Приостанавливает или возобновляет текущую запись",
                "operationId": "pauseRecording",
                "responses": {
                    "200": {
                        "description": "Состояние паузы изменено",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "is_paused": {
                                                    "type": "boolean",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/recordings": {
            "get": {
                "summary": "Получить список записей",
                "description": "Возвращает список недавних записей",
                "operationId": "getRecordings",
                "responses": {
                    "200": {
                        "description": "Список записей",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "path": {
                                                        "type": "string",
                                                    },
                                                    "size": {
                                                        "type": "integer",
                                                    },
                                                    "created": {
                                                        "type": "string",
                                                        "format": "date-time",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/events/recent": {
            "get": {
                "summary": "Получить недавние события",
                "description": "Возвращает последние real-time события записи",
                "operationId": "getRecentEvents",
                "parameters": [
                    {
                        "name": "limit",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "integer",
                            "default": 50,
                            "minimum": 1,
                            "maximum": 500,
                        },
                        "description": "Количество событий в ответе",
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Список событий",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/Event",
                                            },
                                        },
                                    },
                                    "required": ["success", "data"],
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Некорректный параметр limit",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Не авторизован",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/events/stats": {
            "get": {
                "summary": "Получить статистику событий",
                "description": "Возвращает статистику real-time event-менеджера",
                "operationId": "getEventsStats",
                "responses": {
                    "200": {
                        "description": "Статистика событий",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "$ref": "#/components/schemas/WebSocketStats",
                                        },
                                    },
                                    "required": ["success", "data"],
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Не авторизован",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/observability/metrics": {
            "get": {
                "summary": "Получить эксплуатационные метрики API",
                "description": "Возвращает runtime-метрики API сервера",
                "operationId": "getObservabilityMetrics",
                "responses": {
                    "200": {
                        "description": "Снапшот метрик",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                        },
                                    },
                                    "required": ["success", "data"],
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Не авторизован",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/observability/baseline": {
            "get": {
                "summary": "Получить baseline SLO",
                "description": "Возвращает baseline и текущие значения эксплуатационных SLO",
                "operationId": "getObservabilityBaseline",
                "responses": {
                    "200": {
                        "description": "Baseline SLO",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                        },
                                    },
                                    "required": ["success", "data"],
                                },
                            },
                        },
                    },
                    "401": {
                        "description": "Не авторизован",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/schedule": {
            "get": {
                "summary": "Получить расписание",
                "description": "Возвращает список запланированных задач",
                "operationId": "getSchedule",
                "responses": {
                    "200": {
                        "description": "Список задач",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/ScheduleTask",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "post": {
                "summary": "Создать задачу",
                "description": "Создаёт новую запланированную задачу",
                "operationId": "createSchedule",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "$ref": "#/components/schemas/CreateScheduleRequest",
                            },
                            "examples": {
                                "once": {
                                    "summary": "Разовый запуск",
                                    "value": {
                                        "name": "Разовая запись",
                                        "trigger": "once",
                                        "datetime": "2099-01-01T10:00:00+03:00",
                                        "params": {},
                                    },
                                },
                                "daily": {
                                    "summary": "Ежедневно",
                                    "value": {
                                        "name": "Ежедневная запись",
                                        "trigger": "daily",
                                        "time": "10:00",
                                        "params": {},
                                    },
                                },
                                "weekly": {
                                    "summary": "По будням",
                                    "value": {
                                        "name": "Запись по будням",
                                        "trigger": "weekly",
                                        "time": "10:00",
                                        "day_of_week": "0,1,2,3,4",
                                        "params": {},
                                    },
                                },
                                "interval": {
                                    "summary": "Интервал",
                                    "value": {
                                        "name": "Запись каждые 30 минут",
                                        "trigger": "interval",
                                        "hours": 0,
                                        "minutes": 30,
                                        "params": {},
                                    },
                                },
                                "cron": {
                                    "summary": "Cron",
                                    "value": {
                                        "name": "Cron запись",
                                        "trigger": "cron",
                                        "cron_expression": "0 10 * * 1-5",
                                        "params": {},
                                    },
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Задача создана",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "id": {
                                                    "type": "string",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "400": {
                        "description": "Ошибка валидации",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ValidationError",
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/schedule/{task_id}": {
            "delete": {
                "summary": "Удалить задачу",
                "description": "Удаляет запланированную задачу",
                "operationId": "deleteSchedule",
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                        },
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Задача удалена",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                    },
                                },
                            },
                        },
                    },
                    "404": {
                        "description": "Задача не найдена",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/Error",
                                },
                            },
                        },
                    },
                },
            },
            "put": {
                "summary": "Обновить задачу",
                "description": "Обновляет параметры запланированной задачи",
                "operationId": "updateSchedule",
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                        },
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                    },
                                    "enabled": {
                                        "type": "boolean",
                                    },
                                    "time": {
                                        "type": "string",
                                    },
                                    "day_of_week": {
                                        "type": "string",
                                    },
                                    "params": {
                                        "$ref": "#/components/schemas/StartRecordingRequest",
                                    },
                                },
                            },
                            "examples": {
                                "rename": {
                                    "summary": "Переименовать задачу",
                                    "value": {
                                        "name": "Новая задача",
                                    },
                                },
                                "update_weekly_time": {
                                    "summary": "Изменить время и дни",
                                    "value": {
                                        "time": "11:30",
                                        "day_of_week": "0,1,2,3,4",
                                        "enabled": True,
                                    },
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Задача обновлена",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/schedule/{task_id}/toggle": {
            "post": {
                "summary": "Включить/выключить задачу",
                "description": "Переключает состояние активности задачи",
                "operationId": "toggleSchedule",
                "parameters": [
                    {
                        "name": "task_id",
                        "in": "path",
                        "required": True,
                        "schema": {
                            "type": "string",
                        },
                    }
                ],
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "required": ["enabled"],
                                "properties": {
                                    "enabled": {
                                        "type": "boolean",
                                    },
                                },
                            },
                            "examples": {
                                "enable": {
                                    "summary": "Включить задачу",
                                    "value": {"enabled": True},
                                },
                                "disable": {
                                    "summary": "Выключить задачу",
                                    "value": {"enabled": False},
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Состояние изменено",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "enabled": {
                                                    "type": "boolean",
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/devices": {
            "get": {
                "summary": "Получить аудиоустройства",
                "description": "Возвращает список доступных аудиоустройств",
                "operationId": "getDevices",
                "responses": {
                    "200": {
                        "description": "Список устройств",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "object",
                                            "properties": {
                                                "input": {
                                                    "type": "array",
                                                    "items": {
                                                        "$ref": "#/components/schemas/AudioDevice",
                                                    },
                                                },
                                                "output": {
                                                    "type": "array",
                                                    "items": {
                                                        "$ref": "#/components/schemas/AudioDevice",
                                                    },
                                                },
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/windows": {
            "get": {
                "summary": "Получить список окон",
                "description": "Возвращает список открытых окон для захвата",
                "operationId": "getWindows",
                "responses": {
                    "200": {
                        "description": "Список окон",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "type": "array",
                                            "items": {
                                                "$ref": "#/components/schemas/Window",
                                            },
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
        "/api/config": {
            "get": {
                "summary": "Получить конфигурацию",
                "description": "Возвращает текущую конфигурацию приложения",
                "operationId": "getConfig",
                "responses": {
                    "200": {
                        "description": "Конфигурация",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                        "data": {
                                            "$ref": "#/components/schemas/Config",
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
            "put": {
                "summary": "Обновить конфигурацию",
                "description": "Обновляет параметры конфигурации",
                "operationId": "updateConfig",
                "requestBody": {
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "fps": {
                                        "type": "integer",
                                    },
                                    "codec": {
                                        "type": "string",
                                    },
                                    "bitrate": {
                                        "type": "string",
                                    },
                                    "default_path": {
                                        "type": "string",
                                    },
                                    "record_mic": {
                                        "type": "boolean",
                                    },
                                    "record_system": {
                                        "type": "boolean",
                                    },
                                },
                            },
                            "examples": {
                                "video_update": {
                                    "summary": "Обновить видео-настройки",
                                    "value": {
                                        "fps": 60,
                                        "codec": "libx264",
                                        "bitrate": "6M",
                                    },
                                },
                                "output_update": {
                                    "summary": "Обновить путь вывода",
                                    "value": {
                                        "default_path": "C:/Videos/Recordings",
                                    },
                                },
                            },
                        },
                    },
                },
                "responses": {
                    "200": {
                        "description": "Конфигурация обновлена",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "success": {
                                            "type": "boolean",
                                            "example": True,
                                        },
                                    },
                                },
                            },
                        },
                    },
                },
            },
        },
    },
}


def get_swagger_spec() -> dict[str, Any]:
    """
    Возвращает OpenAPI спецификацию.

    Returns:
        Копия словаря с OpenAPI спецификацией
    """
    spec = deepcopy(SWAGGER_SPEC)

    # В спецификации используем versioned API как основной контракт.
    # Это убирает путаницу между legacy /api/* и актуальным /api/v1/*.
    remapped_paths: dict[str, Any] = {}
    for path, path_spec in spec.get("paths", {}).items():
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            remapped_paths[f"/api/v1/{path.removeprefix('/api/')}"] = path_spec
        else:
            remapped_paths[path] = path_spec
    spec["paths"] = remapped_paths

    # Добавляем поддержку идемпотентности для write-endpoints.
    idempotency_header = {
        "name": "Idempotency-Key",
        "in": "header",
        "required": False,
        "schema": {
            "type": "string",
            "maxLength": 128,
        },
        "description": (
            "Идемпотентный ключ для безопасных ретраев write-запросов. "
            "Одинаковый ключ + одинаковый payload вернёт cached-ответ."
        ),
    }
    for path_spec in spec.get("paths", {}).values():
        if not isinstance(path_spec, dict):
            continue
        for method_name, operation in path_spec.items():
            if method_name not in {"post", "put", "patch", "delete"}:
                continue
            if not isinstance(operation, dict):
                continue
            parameters = operation.setdefault("parameters", [])
            has_header = any(
                isinstance(item, dict)
                and item.get("in") == "header"
                and item.get("name") == "Idempotency-Key"
                for item in parameters
            )
            if not has_header:
                parameters.append(deepcopy(idempotency_header))

    # Относительный server URL автоматически подхватывает текущий хост/порт.
    spec["servers"] = [
        {
            "url": "/",
            "description": "Текущий API сервер",
        }
    ]

    return spec


def register_swagger_routes(app: Any) -> None:
    """
    Регистрирует маршруты для Swagger документации.

    Args:
        app: Экземпляр Flask приложения
    """
    from flask import jsonify, request

    @app.route("/api/swagger.json", methods=["GET"])
    def get_swagger_json() -> Any:
        """Возвращает OpenAPI спецификацию в формате JSON."""
        spec = get_swagger_spec()
        # Для удобства в UI показываем абсолютный URL текущего хоста/порта.
        spec["servers"] = [
            {
                "url": request.host_url.rstrip("/"),
                "description": "Текущий API сервер",
            }
        ]
        return jsonify(spec)

    @app.route("/api/docs", methods=["GET"])
    def swagger_ui() -> Any:
        """Возвращает Swagger UI страницу."""
        return """
<!DOCTYPE html>
<html>
<head>
    <title>MIA-ScreenCapture API Documentation</title>
    <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
    <style>
        body { margin: 0; padding: 0; }
    </style>
</head>
<body>
    <div id="swagger-ui"></div>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
    <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js"></script>
    <script>
        window.onload = function() {
            const ui = SwaggerUIBundle({
                url: "/api/swagger.json",
                dom_id: '#swagger-ui',
                presets: [
                    SwaggerUIBundle.presets.apis,
                    SwaggerUIStandalonePreset
                ],
                layout: "StandaloneLayout",
                deepLinking: true,
                persistAuthorization: true,
                displayRequestDuration: true,
                tryItOutEnabled: true,
                displayOperationId: false,
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
            });
        }
    </script>
</body>
</html>
        """
