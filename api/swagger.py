"""
Модуль Swagger документации API
================================

Предоставляет OpenAPI/Swagger спецификацию для REST API.
"""

from typing import Any

# OpenAPI спецификация для API MIA-ScreenCapture
SWAGGER_SPEC: dict[str, Any] = {
    "openapi": "3.0.3",
    "info": {
        "title": "MIA-ScreenCapture API",
        "description": "REST API для управления записью экрана",
        "version": "1.2.0",
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
    "security": [
        {
            "ApiKeyAuth": []
        }
    ],
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
                        "type": "string",
                        "example": "Описание ошибки",
                    },
                },
                "required": ["success", "error"],
            },
            "ValidationError": {
                "type": "object",
                "properties": {
                    "success": {
                        "type": "boolean",
                        "example": False,
                    },
                    "error": {
                        "type": "string",
                        "example": "Ошибка валидации данных",
                    },
                    "validation_errors": {
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
                        },
                    },
                },
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
                            "output_path": {
                                "type": "string",
                                "example": "C:/Videos/recording_20260320.mp4",
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
                        "enum": ["once", "daily", "weekly", "interval", "cron"],
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
                        "enum": ["once", "daily", "weekly", "interval", "cron"],
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
                    "cron": {
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
                                    "bitrate": {
                                        "type": "string",
                                    },
                                    "output_directory": {
                                        "type": "string",
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
        Словарь с OpenAPI спецификацией
    """
    return SWAGGER_SPEC


def register_swagger_routes(app) -> None:
    """
    Регистрирует маршруты для Swagger документации.

    Args:
        app: Экземпляр Flask приложения
    """
    from flask import jsonify

    @app.route("/api/swagger.json", methods=["GET"])
    def get_swagger_json():
        """Возвращает OpenAPI спецификацию в формате JSON."""
        return jsonify(SWAGGER_SPEC)

    @app.route("/api/docs", methods=["GET"])
    def swagger_ui():
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
                displayOperationId: false,
                defaultModelsExpandDepth: 1,
                defaultModelExpandDepth: 1,
            });
        }
    </script>
</body>
</html>
        """
