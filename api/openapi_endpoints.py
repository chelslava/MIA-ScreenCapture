"""Метаданные операций OpenAPI (мигрировано из api/swagger.py)."""

from __future__ import annotations

from typing import Any

# Ключ — «МЕТОД путь» (путь как в OpenAPI, с {параметрами}).
# Поле "request" — имя Pydantic-модели из реестра COMPONENT_MODELS,
# поле "schema" ответа — {"ref": имя} либо {"inline": dict-схема}.
# Источник: рукописная спецификация v1.8.0 (issue #214).
ENDPOINTS: dict[str, dict[str, Any]] = {
    "DELETE /api/v1/profiles/{profile_id}": {
        "summary": "Удалить профиль записи",
        "description": "Удаляет пользовательский профиль (встроенные удалять нельзя)",
        "operation_id": "deleteProfile",
        "responses": {
            "200": {
                "description": "Профиль удален",
            },
            "400": {
                "description": "Нельзя удалить встроенный профиль",
            },
            "404": {
                "description": "Профиль не найден",
            },
        },
    },
    "DELETE /api/v1/schedule/{task_id}": {
        "summary": "Удалить задачу",
        "description": "Удаляет запланированную задачу",
        "operation_id": "deleteSchedule",
        "responses": {
            "200": {
                "description": "Задача удалена",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True}
                        },
                    }
                },
            },
            "404": {
                "description": "Задача не найдена",
                "schema": {"ref": "Error"},
            },
        },
    },
    "GET /api/v1/config": {
        "summary": "Получить конфигурацию",
        "description": "Возвращает текущую конфигурацию приложения",
        "operation_id": "getConfig",
        "responses": {
            "200": {
                "description": "Конфигурация",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {"$ref": "#/components/schemas/Config"},
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/devices": {
        "summary": "Получить аудиоустройства",
        "description": "Возвращает список доступных аудиоустройств",
        "operation_id": "getDevices",
        "responses": {
            "200": {
                "description": "Список устройств",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "input": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/AudioDevice"
                                        },
                                    },
                                    "output": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/AudioDevice"
                                        },
                                    },
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/events/recent": {
        "summary": "Получить недавние события",
        "description": "Возвращает последние real-time события записи",
        "operation_id": "getRecentEvents",
        "responses": {
            "200": {
                "description": "Список событий",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "array",
                                "items": {
                                    "$ref": "#/components/schemas/Event"
                                },
                            },
                        },
                        "required": ["success", "data"],
                    }
                },
            },
            "400": {
                "description": "Некорректный параметр limit",
                "schema": {"ref": "Error"},
            },
            "401": {
                "description": "Не авторизован",
                "schema": {"ref": "Error"},
            },
        },
    },
    "GET /api/v1/events/stats": {
        "summary": "Получить статистику событий",
        "description": "Возвращает статистику real-time event-менеджера",
        "operation_id": "getEventsStats",
        "responses": {
            "200": {
                "description": "Статистика событий",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "$ref": "#/components/schemas/WebSocketStats"
                            },
                        },
                        "required": ["success", "data"],
                    }
                },
            },
            "401": {
                "description": "Не авторизован",
                "schema": {"ref": "Error"},
            },
        },
    },
    "GET /api/v1/observability/baseline": {
        "summary": "Получить baseline SLO",
        "description": "Возвращает baseline и текущие значения эксплуатационных SLO",
        "operation_id": "getObservabilityBaseline",
        "responses": {
            "200": {
                "description": "Baseline SLO",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {"type": "object"},
                        },
                        "required": ["success", "data"],
                    }
                },
            },
            "401": {
                "description": "Не авторизован",
                "schema": {"ref": "Error"},
            },
        },
    },
    "GET /api/v1/observability/metrics": {
        "summary": "Получить эксплуатационные метрики API",
        "description": "Возвращает runtime-метрики API сервера",
        "operation_id": "getObservabilityMetrics",
        "responses": {
            "200": {
                "description": "Снапшот метрик",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {"type": "object"},
                        },
                        "required": ["success", "data"],
                    }
                },
            },
            "401": {
                "description": "Не авторизован",
                "schema": {"ref": "Error"},
            },
        },
    },
    "GET /api/v1/post-processing/config": {
        "summary": "Получить настройки постобработки",
        "description": "Возвращает текущую конфигурацию конвейера постобработки",
        "operation_id": "getPostProcessingConfig",
        "responses": {
            "200": {
                "description": "Конфигурация постобработки",
            },
        },
    },
    "GET /api/v1/post-processing/status": {
        "summary": "Статус постобработки",
        "description": "Возвращает текущий статус активности или результат последнего конвейера",
        "operation_id": "getPostProcessingStatus",
        "responses": {
            "200": {
                "description": "Текущий статус постобработки",
            },
        },
    },
    "GET /api/v1/profiles": {
        "summary": "Список профилей записи",
        "description": "Возвращает список всех доступных профилей настроек записи",
        "operation_id": "getProfiles",
        "responses": {
            "200": {
                "description": "Список профилей",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "array",
                                "items": {"type": "object"},
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/profiles/{profile_id}": {
        "summary": "Получить профиль записи",
        "description": "Возвращает информацию о конкретном профиле",
        "operation_id": "getProfile",
        "responses": {
            "200": {
                "description": "Данные профиля",
            },
            "404": {
                "description": "Профиль не найден",
            },
        },
    },
    "GET /api/v1/recording/finalization-status": {
        "summary": "Получить статус финализации записи",
        "description": "Возвращает прогресс финализации последней записи (объединение видео/аудио, перенос файла): процент, этап, прошедшее время и оценку остатка (#151)",
        "operation_id": "getFinalizationStatus",
        "responses": {
            "200": {
                "description": "Статус финализации записи",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "active": {
                                        "type": "boolean",
                                        "example": True,
                                    },
                                    "percent": {
                                        "type": "number",
                                        "example": 42.5,
                                    },
                                    "stage": {
                                        "type": "string",
                                        "example": "Объединение видео",
                                    },
                                    "elapsed_s": {
                                        "type": "number",
                                        "nullable": True,
                                        "example": 12.3,
                                    },
                                    "eta_s": {
                                        "type": "number",
                                        "nullable": True,
                                        "example": 16.7,
                                    },
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/recording/metrics": {
        "summary": "Получить метрики записи в реальном времени",
        "description": "Возвращает текущий фактический FPS, jitter, количество пропущенных кадров и latency кодирования (#114)",
        "operation_id": "getRecordingMetrics",
        "responses": {
            "200": {
                "description": "Метрики производительности видеозаписи",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "actual_fps": {
                                        "type": "number",
                                        "example": 29.85,
                                    },
                                    "target_fps": {
                                        "type": "integer",
                                        "example": 30,
                                    },
                                    "jitter_ms": {
                                        "type": "number",
                                        "example": 2.34,
                                    },
                                    "frames_dropped": {
                                        "type": "integer",
                                        "example": 0,
                                    },
                                    "encode_latency_ms": {
                                        "type": "number",
                                        "example": 4.12,
                                    },
                                    "buffer_fill_percent": {
                                        "type": "number",
                                        "example": 0.0,
                                    },
                                    "total_frames": {
                                        "type": "integer",
                                        "example": 150,
                                    },
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/recording/{recording_id}/post-processing": {
        "summary": "Статус постобработки записи",
        "description": "Возвращает статус постобработки для указанной записи",
        "operation_id": "getRecordingPostProcessingStatus",
        "responses": {
            "200": {
                "description": "Статус постобработки записи",
            },
        },
    },
    "GET /api/v1/recordings": {
        "summary": "Получить список записей",
        "description": "Возвращает список недавних записей",
        "operation_id": "getRecordings",
        "responses": {
            "200": {
                "description": "Список записей",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "path": {"type": "string"},
                                        "size": {"type": "integer"},
                                        "created": {
                                            "type": "string",
                                            "format": "date-time",
                                        },
                                    },
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/schedule": {
        "summary": "Получить расписание",
        "description": "Возвращает список запланированных задач",
        "operation_id": "getSchedule",
        "responses": {
            "200": {
                "description": "Список задач",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "array",
                                "items": {
                                    "$ref": "#/components/schemas/ScheduleTask"
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /api/v1/status": {
        "summary": "Получить статус записи",
        "description": "Возвращает текущий статус записи экрана",
        "operation_id": "getStatus",
        "responses": {
            "200": {
                "description": "Успешный ответ",
                "schema": {"ref": "Status"},
            },
            "401": {
                "description": "Не авторизован",
                "schema": {"ref": "Error"},
            },
        },
    },
    "GET /api/v1/updates/check": {
        "summary": "Проверить наличие обновлений (GET)",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Результат проверки обновлений",
            },
        },
    },
    "GET /api/v1/updates/config": {
        "summary": "Получить настройки авто-обновлений",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Текущие настройки авто-обновлений",
            },
        },
    },
    "GET /api/v1/updates/status": {
        "summary": "Получить статус подсистемы авто-обновления",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Текущий статус обновлений",
            },
        },
    },
    "GET /api/v1/windows": {
        "summary": "Получить список окон",
        "description": "Возвращает список открытых окон для захвата",
        "operation_id": "getWindows",
        "responses": {
            "200": {
                "description": "Список окон",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "array",
                                "items": {
                                    "$ref": "#/components/schemas/Window"
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "GET /health": {
        "summary": "Проверить состояние сервиса",
        "description": "Возвращает health payload с версией, uptime и состоянием real-time транспорта",
        "operation_id": "getHealth",
        "responses": {
            "200": {
                "description": "Сервис работает",
                "schema": {"ref": "Health"},
            },
        },
    },
    "POST /api/v1/pause": {
        "summary": "Пауза/возобновление записи",
        "description": "Приостанавливает или возобновляет текущую запись",
        "operation_id": "pauseRecording",
        "responses": {
            "200": {
                "description": "Состояние паузы изменено",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "is_paused": {"type": "boolean"}
                                },
                            },
                        },
                    }
                },
            },
        },
    },
    "POST /api/v1/post-processing/run": {
        "summary": "Запустить постобработку",
        "description": "Запускает конвейер постобработки для указанного файла",
        "operation_id": "runPostProcessing",
        "request_inline": {
            "type": "object",
            "required": ["file_path"],
            "properties": {
                "file_path": {"type": "string"},
                "params": {"type": "object"},
            },
        },
        "responses": {
            "200": {
                "description": "Постобработка успешно запущена",
            },
            "400": {
                "description": "Ошибка запуска или файл не найден",
            },
        },
    },
    "POST /api/v1/profiles": {
        "summary": "Создать профиль записи",
        "description": "Создает новый профиль с заданными параметрами",
        "operation_id": "createProfile",
        "request_inline": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string", "example": "Высокое качество"},
                "description": {"type": "string", "example": "60 FPS 1080p"},
                "icon": {"type": "string", "example": "🚀"},
                "video": {"type": "object"},
                "audio": {"type": "object"},
                "capture": {"type": "object"},
                "is_default": {"type": "boolean", "example": False},
            },
        },
        "responses": {
            "201": {
                "description": "Профиль создан",
            },
            "400": {
                "description": "Ошибка валидации",
            },
        },
    },
    "POST /api/v1/profiles/{profile_id}/apply": {
        "summary": "Применить профиль",
        "description": "Применяет настройки профиля к текущей конфигурации приложения",
        "operation_id": "applyProfile",
        "responses": {
            "200": {
                "description": "Профиль успешно применен",
            },
            "404": {
                "description": "Профиль не найден",
            },
        },
    },
    "POST /api/v1/schedule": {
        "summary": "Создать задачу",
        "description": "Создаёт новую запланированную задачу",
        "operation_id": "createSchedule",
        "request": "CreateScheduleRequest",
        "request_examples": {
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
        "responses": {
            "200": {
                "description": "Задача создана",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {"id": {"type": "string"}},
                            },
                        },
                    }
                },
            },
            "400": {
                "description": "Ошибка валидации",
                "schema": {"ref": "ValidationError"},
            },
        },
    },
    "POST /api/v1/schedule/{task_id}/toggle": {
        "summary": "Включить/выключить задачу",
        "description": "Переключает состояние активности задачи",
        "operation_id": "toggleSchedule",
        "request_inline": {
            "type": "object",
            "required": ["enabled"],
            "properties": {"enabled": {"type": "boolean"}},
        },
        "request_examples": {
            "enable": {
                "summary": "Включить задачу",
                "value": {"enabled": True},
            },
            "disable": {
                "summary": "Выключить задачу",
                "value": {"enabled": False},
            },
        },
        "responses": {
            "200": {
                "description": "Состояние изменено",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {"enabled": {"type": "boolean"}},
                            },
                        },
                    }
                },
            },
        },
    },
    "POST /api/v1/start": {
        "summary": "Начать запись",
        "description": "Запускает новую запись экрана с указанными параметрами",
        "operation_id": "startRecording",
        "request": "StartRecordingRequest",
        "request_examples": {
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
        "responses": {
            "200": {
                "description": "Запись начата",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "output_path": {"type": "string"}
                                },
                            },
                        },
                    }
                },
            },
            "400": {
                "description": "Ошибка валидации",
                "schema": {"ref": "ValidationError"},
            },
            "401": {
                "description": "Не авторизован",
                "schema": {"ref": "Error"},
            },
        },
    },
    "POST /api/v1/stop": {
        "summary": "Остановить запись",
        "description": "Останавливает текущую запись",
        "operation_id": "stopRecording",
        "responses": {
            "200": {
                "description": "Запись остановлена",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True},
                            "data": {
                                "type": "object",
                                "properties": {
                                    "output_path": {"type": "string"},
                                    "duration": {"type": "integer"},
                                },
                            },
                        },
                    }
                },
            },
            "400": {
                "description": "Нет активной записи",
                "schema": {"ref": "Error"},
            },
        },
    },
    "POST /api/v1/updates/apply": {
        "summary": "Применить скачанное обновление",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Обновление запущено",
            },
        },
    },
    "POST /api/v1/updates/check": {
        "summary": "Проверить наличие обновлений (POST)",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Результат проверки обновлений",
            },
        },
    },
    "POST /api/v1/updates/download": {
        "summary": "Запустить скачивание обновления",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Скачивание запущено",
            },
        },
    },
    "PUT /api/v1/config": {
        "summary": "Обновить конфигурацию",
        "description": "Обновляет параметры конфигурации",
        "operation_id": "updateConfig",
        "request_inline": {
            "type": "object",
            "properties": {
                "fps": {"type": "integer"},
                "codec": {"type": "string"},
                "bitrate": {"type": "string"},
                "default_path": {"type": "string"},
                "record_mic": {"type": "boolean"},
                "record_system": {"type": "boolean"},
            },
        },
        "request_examples": {
            "video_update": {
                "summary": "Обновить видео-настройки",
                "value": {"fps": 60, "codec": "libx264", "bitrate": "6M"},
            },
            "output_update": {
                "summary": "Обновить путь вывода",
                "value": {"default_path": "C:/Videos/Recordings"},
            },
        },
        "responses": {
            "200": {
                "description": "Конфигурация обновлена",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True}
                        },
                    }
                },
            },
        },
    },
    "PUT /api/v1/post-processing/config": {
        "summary": "Обновить настройки постобработки",
        "description": "Обновляет параметры конвейера постобработки",
        "operation_id": "updatePostProcessingConfig",
        "request_inline": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "transcode_enabled": {"type": "boolean"},
                "transcode_format": {"type": "string"},
                "compress_enabled": {"type": "boolean"},
                "compress_crf": {"type": "integer"},
                "generate_gif_enabled": {"type": "boolean"},
                "copy_enabled": {"type": "boolean"},
                "copy_target_folder": {"type": "string"},
                "open_explorer_on_finish": {"type": "boolean"},
                "webhook_enabled": {"type": "boolean"},
                "webhook_url": {"type": "string"},
            },
        },
        "responses": {
            "200": {
                "description": "Настройки успешно обновлены",
            },
            "400": {
                "description": "Невалидные параметры",
            },
        },
    },
    "PUT /api/v1/profiles/{profile_id}": {
        "summary": "Обновить профиль записи",
        "description": "Обновляет параметры профиля",
        "operation_id": "updateProfile",
        "responses": {
            "200": {
                "description": "Профиль обновлен",
            },
            "400": {
                "description": "Ошибка валидации",
            },
            "404": {
                "description": "Профиль не найден",
            },
        },
    },
    "PUT /api/v1/schedule/{task_id}": {
        "summary": "Обновить задачу",
        "description": "Обновляет параметры запланированной задачи",
        "operation_id": "updateSchedule",
        "request_inline": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "enabled": {"type": "boolean"},
                "time": {"type": "string"},
                "day_of_week": {"type": "string"},
                "params": {
                    "$ref": "#/components/schemas/StartRecordingRequest"
                },
            },
        },
        "request_examples": {
            "rename": {
                "summary": "Переименовать задачу",
                "value": {"name": "Новая задача"},
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
        "responses": {
            "200": {
                "description": "Задача обновлена",
                "schema": {
                    "inline": {
                        "type": "object",
                        "properties": {
                            "success": {"type": "boolean", "example": True}
                        },
                    }
                },
            },
        },
    },
    "PUT /api/v1/updates/config": {
        "summary": "Обновить настройки авто-обновлений",
        "tags": ["Updates"],
        "responses": {
            "200": {
                "description": "Настройки обновлений успешно сохранены",
            },
            "400": {
                "description": "Ошибка валидации",
            },
        },
    },
}
