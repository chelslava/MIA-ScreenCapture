# Changelog

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
