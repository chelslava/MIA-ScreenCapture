# Changelog

## [Unreleased]

### Planned for 1.4.5
- Длинный smoke-run API-вкладки (30+ минут) и финальная стабилизация
  live-логов.

### Added
- Улучшен UX блока `Последние записи`:
  - фильтрация списка по имени файла и дате;
  - кнопка быстрого открытия последней записи;
  - кнопка очистки списка записей.
- Добавлена поддержка `Idempotency-Key` для write-endpoints API:
  повтор с тем же ключом и тем же payload возвращает cached-ответ.
- Добавлено TTL-хранилище идемпотентных результатов API
  с фоновым cleanup потоком.
- Расширены тесты для идемпотентности:
  `tests/integration/test_api.py::TestAPIIdempotency` и
  `tests/unit/test_api_server.py::TestAPIIdempotencyStore`.
- Добавлено безопасное хранение API токена в Windows Credential Manager
  с fallback на переменную окружения `MIA_API_KEY`.

### Changed
- Синхронизирована версия `1.4.5` в `pyproject.toml`, `README.md`,
  `api/swagger.py` и roadmap ближайшего релиза.
- Добавлен release preflight-чеклист `plans/release-preflight-v1.4.5.md`
  с quality gates, smoke evidence и проверкой артефактов.
- Добавлены автопроверки консистентности версии между
  `pyproject.toml`, `README.md`, `/health` и `/api/swagger.json`.
- Подготовлен регрессионный сценарий API-вкладки GUI
  (`plans/gui-api-tab-regression-v1.4.5.md`) для `start/stop/restart`
  при открытом live-логе.
- В `release.yml` добавлен smoke-test собранного Windows EXE:
  запуск в `--headless`, проверка `/health`, корректная остановка процесса.
- Блокирующий integration-step в CI расширен:
  добавлен `tests/integration/test_api.py`.
- Интеграционные тесты `tests/integration/test_api.py` приведены
  к актуальному v1-контракту (`/api/v1/*`) и стабилизированы по rate-limit.
- Блокирующий `mypy`-scope в CI расширен на `api/swagger.py`.
- Убрано искусственное ограничение таймаута GUI для API `stop`:
  остановка записи теперь ожидает завершение без `TimeoutError`.
- Обновлён unit-тест runtime API (`tests/unit/test_main_api_runtime.py`)
  для проверки сценария stop без таймаута GUI.
- Добавлена синхронная очистка `recent recordings` в GUI-модели и конфиге.
- Расширены unit-тесты для фильтра записей и очистки списка.
- Выполнен headless smoke-run API runtime: `start/stop/restart`, смена порта
  и токена, восстановление логов после truncate.
- Оптимизирована запись `recent_recordings`:
  частые обновления объединяются через debounce, что снижает I/O.
- Удалён неиспользуемый техдолг в `VideoRecorder`:
  поля `_frame_queue` и `_write_thread`.
- Дневная ротация логов переведена на стабильный формат файлов
  `mia_YYYY-MM-DD.log` и `api_YYYY-MM-DD.log` с автопереключением в полночь.
- Добавлены unit-тесты `tests/unit/test_logger_config.py` для API-фильтра,
  переключения дня и очистки устаревших лог-файлов.
- Подготовлен технический дизайн WebSocket transport для `v1.5.0`
  (`plans/websocket-transport-v1.5.0.md`).
- Зафиксированы quality gates для затронутых модулей:
  `ruff check`, `ruff format --check`, `mypy`.
- Swagger/OpenAPI дополнен заголовком `Idempotency-Key`
  для mutating endpoints.
- Добавлены автопроверки консистентности версии в `tests/unit/test_swagger.py`:
  синхронизация `pyproject.toml`, `README.md`, Swagger и runtime `/health`.
- Runtime API-token в `main.py` переведён на постоянное хранилище
  (Credential Manager/env), с миграцией legacy токена из config.
- Аудиозапись переведена на неблокирующую модель:
  запись WAV вынесена из callback в отдельный writer-thread
  с bounded-queue и защитой от переполнения чанков.
- Для `AudioRecorder` добавлены unit-тесты очереди записи:
  переполнение буфера и запись чанков из writer-потока.
- `ConfigManager` сделан потокобезопасным для внутренних мутаций
  `_settings/recent_recordings`:
  - добавлен `RLock` для конкурентных update/save/add_recent_recording;
  - добавлен безопасный `snapshot_settings()` для фонового чтения;
  - добавлен unit-тест на конкурентное добавление `recent_recordings`.
- Планировщик задач теперь применяет
  `config.scheduler.max_concurrent_tasks` как реальный лимит
  `ThreadPoolExecutor(max_workers=...)`.
- Добавлены unit-тесты на применение/нормализацию лимита
  параллельных задач в `TaskScheduler` и прокидку лимита из `main.py`.
- API обработка входного JSON ужесточена:
  - malformed JSON теперь возвращает `400 bad_request` вместо `500`;
  - добавлено ограничение размера запроса (`MAX_CONTENT_LENGTH=1 MiB`);
  - oversized payload возвращает `413 payload_too_large`.
- `APIServer.start()` теперь делает fail-fast проверку bind host/port
  перед запуском waitress и возвращает `False` при занятом порте.
- Добавлен unit-тест на fail-fast сценарий старта API при ошибке bind.
- Устранена гонка в observability latency-метриках:
  чтение latency samples теперь выполняется под lock.
- Декоратор `rate_limit` нормализует tuple-ответы через `make_response`
  и стабильно добавляет `X-RateLimit-*` заголовки.
- Добавлены unit-тесты на потокобезопасное чтение latency и на
  `X-RateLimit-*` заголовки для tuple-ответов.
- Полностью переписан `tests/unit/test_scheduler_tab.py`:
  вместо синтетических проверок добавлены реальные поведенческие сценарии
  create/edit/delete/toggle, обновление кнопок и проверка payload диалога.
- Убрано хардкод-значение `threads=4` для waitress:
  параметр `server_threads` добавлен в API-конфигурацию и прокинут
  в `APIServer`/`main.py`.
- Добавлены unit-тесты на применение `server_threads` в runtime
  и при создании waitress-сервера.
- Добавлена защита от невыполнимых scheduler-задач:
  - `TaskScheduler` отклоняет weekly без дней и interval с нулевым шагом;
  - `TaskDialog` валидирует weekly/interval перед `accept()`.
- Добавлены unit-тесты для backend/UI-валидации scheduler-задач
  (`tests/unit/test_scheduler.py`, `tests/unit/test_scheduler_tab.py`).
- Добавлены интеграционные тесты API:
  - lifecycle сервера (`tests/integration/test_api_server_lifecycle.py`);
  - health/observability (`tests/integration/test_api_health_metrics.py`);
  - обработка внутренних ошибок (`tests/integration/test_api_error_handling.py`);
  - маршруты записи `start/stop/pause`
    (`tests/integration/test_api_recording_routes.py`).
- Добавлены unit-тесты устойчивости рекордера:
  `tests/unit/test_encoder.py`, `tests/unit/test_video_recorder.py`,
  `tests/unit/test_audio_recorder.py`.
- Стабилизированы pytest-временные фикстуры для sandbox-окружения:
  `tmp_path` и `temp_dir` в `tests/conftest.py` переведены на локальный
  temp-root, устранены `PermissionError` в выборочных прогонах recorder/
  scheduler тестов.

## [1.4.3] - 2026-03-28

### Added
- **Новая вкладка API в GUI**:
  - Настройка порта API сервера
  - Настройка API токена
  - Кнопки управления сервером: `Запустить`, `Остановить`, `Перезапустить`
  - Кнопка сохранения настроек API
  - Кнопка открытия папки логов API
- **Окно логов API в реальном времени** на вкладке API
- **API токен в конфигурации** (`config/config.json`) с поддержкой
  загрузки/сохранения
- **Отдельная папка логов API**: `logs/api/` с ротацией по дням
  (`api_YYYY-MM-DD.log`)

### Changed
- Обновлена интеграция GUI и backend для runtime-управления API сервером
- Улучшен lifecycle API сервера при перезапуске из GUI

## [1.4.0] - 2026-03-27

### Added
- **API Versioning**: все endpoints доступны с префиксом `/api/v1/`
- **Package entry point**: команда `mia-capture` после `pip install`
- **Pydantic валидация конфигурации**: автоматическая валидация настроек
- **GUI диагностика**: вкладка для проверки состояния системы
  - Проверка FFmpeg
  - Проверка аудиоустройств
  - Проверка API сервера
  - Проверка папки вывода
- **Thread safety**: RecordingState теперь потокобезопасен с RLock
- **Rate limiter cleanup**: автоматическая очистка неактивных клиентов

### Changed
- **Консолидация типов**: CaptureMode/CaptureType и AudioMode/AudioType объединены
- **Динамическая версия**: версия читается из package metadata
- **monitor_index**: исправлена индексация для windows-capture (0-based → 1-based)
- **Конфигурация**: полная реализация `_update_config` с поддержкой секций
- **CI workflow**: обновлён для Python 3.11/3.12, добавлен coverage

### Fixed
- Остановка записи из состояния паузы
- Ошибки mypy в основных модулях
- Legacy API endpoints для обратной совместимости

### Security
- Rate limiter теперь очищает неактивных клиентов (TTL 2 часа)

## [1.3.2] - 2026-01-17

### Added
- CLI CRUD операции для планировщика задач:
  - `--schedule-create` — создание запланированной задачи
  - `--schedule-update TASK_ID` — обновление задачи
  - `--schedule-delete TASK_ID` — удаление задачи
  - `--schedule-toggle TASK_ID` — включение/выключение задачи
  - `--schedule-preview` — просмотр предстоящих запусков
- Preset шаблоны для расписаний:
  - `workday-morning` — ежедневный утренний стендап
  - `workday-evening` — ежедневный вечерний отчёт
  - `weekly-meeting` — еженедельная встреча
  - `hourly-screenshot` — ежечасный скриншот
  - `30min-interval` — каждые 30 минут
  - `--list-presets` — показать список presets
- Unified контракты данных (`core/contracts.py`):
  - `RecordingParams` — унифицированные параметры записи
  - `ScheduleParams` — унифицированные параметры расписания
  - Pydantic валидация параметров
- Модуль `cli/scheduler.py` с функциями CRUD для scheduler
- Модуль `cli/templates.py` с preset шаблонами
- Юнит-тесты для CLI scheduler (39 тестов)
- Добавлена зависимость `requests>=2.31.0` для CLI scheduler

### Changed
- Минимальная версия Python повышена с 3.9 до 3.11
- Обновлены импорты для Python 3.11+:
  - Использование `X | None` вместо `Optional[X]`
  - Использование `enum.StrEnum` вместо `str, Enum`
  - Импорт `Callable` из `collections.abc`
  - Использование `datetime.UTC` вместо `timezone.utc`
- Удалён неиспользуемый `core/recording_mapper.py`
- Удалены устаревшие typing imports (Dict, List, Tuple)

### Fixed
- Исправлены тесты для `GUIRecordingBackend` с полными аргументами `CaptureRequest`
- Исправлены ошибки линтера ruff в cli/ и core/
- Все пропущенные тесты теперь проходят

## [1.3.0] - 2026-03-23

### Added
- Headless-friendly `RecordingService` for unified start/stop/pause/status flow.
- Domain event bus (`core/event_bus.py`) for recording lifecycle events.
- Real-time event manager (`api/websocket.py`) ready for WebSocket/SSE transport.
- API endpoints for recent events and event stats:
  - `GET /api/events/recent`
  - `GET /api/events/stats`
- Observability endpoints:
  - `GET /api/observability/metrics`
  - `GET /api/observability/baseline`
- New unit tests for recording service and event layer.

### Changed
- Screen capture backend migrated to `windows-capture` (removed `mss` usage).
- API server lifecycle improved with managed waitress shutdown.
- API error payload standardized to a unified contract:
  `success=false`, `error={code,message,details}`, `trace_id`.
- Atomic persistence for config and scheduler task files.
- Health endpoint `GET /health` extended with `version`, `uptime_seconds`
  and real-time transport stats (`websocket`).
- Updated app version metadata to `1.3.0`.

### Reliability
- Strengthened API rate limiting coverage on write endpoints.
- Expanded integration and unit test coverage for API/server/recorder/scheduler paths.
- Stabilized Windows test teardown for temporary directories in CI.

### Automation
- CI expanded to Python matrix (`3.10`, `3.11`) on Windows.
- Added non-blocking security audit job (`pip-audit`) in CI.
- Added tag-based release workflow (`v*`) with build artifacts and `SHA256SUMS`.
