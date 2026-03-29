# TODO: Краткосрочные Задачи До `v1.4.5`

> Обновлено: 2026-03-29
> Статус: активный список до ближайшего релиза

## P0 (обязательно до релиза)

- [ ] Выполнить ручной 30+ минутный GUI smoke-run API-вкладки с открытым
  окном логов и зафиксировать результат в
  `plans/release-note-v1.4.5-smoke.md`.

## P1 (следующий приоритет)

- [ ] Расширить блокирующий `mypy`-scope в CI
  по модулям API/GUI/recorder без возврата `continue-on-error`.

## P2 (после стабилизации релиза)

- [ ] Реализовать асинхронную очередь GUI-команд для API (`start/stop/pause`)
  вместо прямых вызовов GUI-потока.
- [ ] Добавить watchdog для FFmpeg pipeline с чистым восстановлением
  после зависания/ошибок финализации.
- [ ] Добавить ring-buffer для live-логов вкладки API, чтобы избежать лагов
  UI при burst-логировании.
- [ ] Перевести access-логи API в JSON-формат (`trace_id`, `request_id`,
  `latency_ms`, `status`) для ускорения диагностики.
- [ ] Перевести длительности рекордера на monotonic clock вместо
  `time.time()`, чтобы устранить ошибки при смене системного времени.
- [ ] Добавить debounce/батчинг для `_save_tasks()` в scheduler, чтобы
  снизить лишний дисковый I/O.
- [ ] Оптимизировать расчёт перцентилей latency в observability без
  полной сортировки массива на каждый запрос.
- [ ] Добавить мягкий таймаут/защиту остановки `TaskScheduler.stop()`
  при зависших job callback.
- [ ] Добавить release-gate по observability baseline
  (`p95`, `error_rate`, `rss_mb`) перед публикацией релиза.

### Security (безопасность)

- [ ] Добавить валидацию IP-заголовков в `rate_limiter.py`
  (`X-Forwarded-For`, `X-Real-IP`) — защита от IP spoofing.
- [ ] Валидация path traversal в `config.py:409-418` для `default_path`.
- [ ] Установить ограничительные права доступа для `config/` и `logs/`
  директорий (только для текущего пользователя).
- [ ] Добавить лимит максимального значения `bitrate` в `schemas.py:44-47`
  для защиты от DoS через завышенные параметры.
- [ ] Экранировать спецсимволы в PowerShell toast скрипте
  `gui/notifications.py:89-108` — защита от injection.
- [ ] Валидация координат `rect` в `schemas.py:33-37` — ограничить
  максимальные размеры экрана.
- [ ] Добавить лимит `duration` в `schemas.py:47-53` — защита от исчерпания
  диска через бесконечную запись.
- [ ] Валидация `output_path` на недопустимые символы и зарезервированные
  имена Windows (CON, PRN, NUL) в `api/schemas.py`.
- [ ] Audit logging для изменений API key в `api/auth.py`.

### Stability (стабильность)

- [ ] Добавить проверку свободного места на диске перед началом записи.
- [ ] Обработка потери capture-сессии с попыткой переподключения
  в `video_recorder.py:197-210`.
- [ ] Очистка operation store в `api/server.py` по таймеру,
  а не только при `get()` — избежать memory leak.
- [ ] Добавить синхронизацию `pause/resume` с capture thread
  в `video_recorder.py:476-478` — устранить race condition.
- [ ] Использовать `threading.Event.wait()` вместо busy-wait
  в headless режиме `main.py:373-380`.
- [ ] Устранить потенциальный deadlock между `_settings_lock` и `_save_lock`
  в `config.py:270-271`.
- [ ] Не держать `self._lock` во время `join()` capture thread
  в `video_recorder.py:384-386,504-508`.
- [ ] Логировать context в `core/event_bus.py:96-99` — какой handler упал.
- [ ] Добавить метрики dropped audio chunks в `recorder/audio_recorder.py`
  для мониторинга.
- [ ] Очищать metrics counters (`_status_counts`, `_method_counts`,
  `_path_counts`) в `api/server.py` — избежать unbounded growth.
- [ ] Обработка disconnect аудиоустройства во время записи
  в `recorder/audio_recorder.py:224-243`.
- [ ] Логировать fallback на primary monitor при неверном `monitor_index`
  в `video_recorder.py:61-67`.
- [ ] Добавить состояние `ERROR` в `RecordingStatus` для failed recordings
  в `core/recording_state.py:17-22`.
- [ ] Валидация `task.next_run` в будущем при scheduling
  в `scheduler/task_scheduler.py:447-448`.
- [ ] Проверка длины пути `get_output_path()` против Windows MAX_PATH
  в `config.py:498-526`.

### Performance (производительность)

- [ ] Кэширование `get_available_windows()` и `get_audio_devices()` с TTL
  для снижения системных вызовов.
- [ ] Убрать лишнюю копию массива `np.array(bgr, copy=True)`
  в `video_recorder.py:193-195` — использовать buffer protocol.
- [ ] Вынести захардкоженные таймауты в конфигурацию:
  `capture_stop_timeout`, `audio_queue_max_chunks`,
  `audio_queue_get_timeout`, FFmpeg-таймауты.
- [ ] Ограничить `ThreadPoolExecutor` queue в `api/server.py:186-189`
  для предотвращения memory growth.
- [ ] Добавить upper bound для rate limiter client cleanup interval
  в `api/rate_limiter.py:113-143`.

### Code Quality (качество кода)

- [ ] Вынести magic numbers в константы:
  `video_recorder.py:567` (0.9), `main_window.py:109` (100ms timer),
  `tray_icon.py:200` (500ms animation), `core/lifecycle.py:245` (30s timeout).
- [ ] Разбить `main.py:VideoRecorderApp` на отдельные классы
  (SRP violation — 50+ методов).
- [ ] Разбить `api/routes.py:535-1143` `register_routes()` на группы:
  `_register_status_routes()`, `_register_recording_routes()`,
  `_register_schedule_routes()`.
- [ ] Разбить `gui/scheduler_tab.py:67-210` `TaskDialog._setup_ui()`
  на подсекции.
- [ ] Устранить циклическую зависимость `gui.models.recording_state`
  -> `core.recording_state`.
- [ ] Документировать state machine transitions для `RecordingStatus`
  и предотвратить невалидные переходы (например, `IDLE -> PAUSED`).

### Error Handling (обработка ошибок)

- [ ] Заменить `except Exception: pass` на логирование в:
  `api/auth.py:78,109,127,143`, `video_recorder.py:243,628`,
  `ffmpeg_writer.py:268`, `hotkeys.py:151`, `notifications.py:136,151`.
- [ ] Возвращать копию `recent_recordings` в `gui/models/recording_state.py`
  вместо прямой ссылки.
- [ ] Не терять user config при ошибке парсинга в `config.py:297-330`
  — логировать и валидировать поля по отдельности.
- [ ] Добавить версионирование конфига для миграции при смене схемы
  в `config.py:275-295`.
- [ ] Проверка на пустые `rect_coords` в `gui/main_window.py:433-451`.
- [ ] Null check для `time_of_day` в `scheduler/task_scheduler.py:482-484`.
- [ ] Валидация пустых путей в `recorder/encoder.py:111-119`.

### Logging (логирование)

- [ ] Добавить debug logging для device selection в
  `recorder/audio_recorder.py:222-262`.
- [ ] Изменить FFmpeg not found с `warning` на `error`
  в `main.py:232-235`.
- [ ] Добавить `trace_id` в business logic logs в `api/routes.py`.
- [ ] Добавить session/recording ID для корреляции логов
  в `core/recording_service.py`.
- [ ] Timing metrics для task execution в
  `scheduler/task_scheduler.py:535-569`.

### API Design (дизайн API)

- [ ] Добавить error codes для business logic errors:
  `recording_already_active`, `scheduler_unavailable`, `ffmpeg_not_found`.
- [ ] Добавить error codes для auth: `AUTH_MISSING_KEY`, `AUTH_INVALID_KEY`.
- [ ] Унифицировать response format: `data` vs `error` ключи
  в `api/routes.py:628-635`.
- [ ] Добавить пагинацию для `get_recordings()`, `get_recent_events()`,
  `get_schedule()` — защита от больших ответов.
- [ ] Покрыть `_ERROR_CODE_BY_STATUS` все коды: 500, 502, 503
  в `api/routes.py:32-40`.
- [ ] Mark legacy routes как deprecated с timeline
  в `api/routes.py:1116-1142`.

### Platform (платформенные особенности)

- [ ] DPI scaling для screen geometry в `gui/main_window.py:122-131`
  и `video_recorder.py:54-78`.
- [ ] Обработка локализованных имён аудиоустройств (не только "loopback")
  в `recorder/audio_recorder.py:509-517`.
- [ ] Уточнить сообщение об ошибке для `monitor_index`
  в `video_recorder.py:152-154` (0-based vs 1-based).

### Dependencies (зависимости)

- [ ] Добавить `tzlocal` в `pyproject.toml` — используется в
  `api/schemas.py:161` и `scheduler/task_scheduler.py:190`.
- [ ] Добавить upper bounds для критичных зависимостей:
  `pydantic`, `flask`, `PyQt6`, `windows-capture`.
- [ ] Проверить и добавить `requests` в dependencies
  (используется в `main.py`, `cli/scheduler.py`).

### Observability (наблюдаемость)

- [ ] Prometheus/OpenMetrics metrics export endpoint.
- [ ] Histogram buckets для latency tracking.
- [ ] Recording duration metrics.
- [ ] Disk space metrics в observability.
- [ ] Health check расширить: FFmpeg availability, audio devices,
  output directory permissions.
- [ ] Liveness vs readiness probe distinction.
- [ ] OpenTelemetry tracing для API calls и recording operations.

### UX (пользовательский опыт)

- [ ] Показывать предупреждение пользователю если FFmpeg не найден
  в `main.py:230-235`.
- [ ] Логировать fallback при window not found
  в `video_recorder.py:103-106`.
- [ ] Добавить progress indicator при финализации видео
  в `gui/main_window.py:476-486`.
- [ ] Визуальный индикатор paused state (цвет/иконка)
  в `gui/main_window.py:488-495`.
- [ ] Сброс состояния кнопок при ошибке stop
  в `gui/main_window.py:476-486`.
- [ ] Добавить tooltips для capture modes, preset, audio modes
  в GUI views.
- [ ] Confirmation dialog для clear recent recordings
  в `gui/main_window.py:688-692`.
- [ ] Предупреждение об активной записи при выходе в tray icon.
- [ ] Улучшить error messages — добавить диагностическую информацию
  вместо generic сообщений.

### CLI (командная строка)

- [ ] Валидация cron expression syntax для `--schedule`
  в `cli/parser.py:221-227`.
- [ ] Различные exit codes по типу ошибки:
  2 (invalid args), 3 (connection), 4 (auth), 5 (not found).
- [ ] Добавить `--dry-run` для проверки параметров без выполнения.
- [ ] Расширить help text с примерами для `--window`, `--monitor`.

### Accessibility (доступность)

- [ ] Добавить `accessibleName`/`accessibleDescription` для widgets.
- [ ] Text alternative для tray icon state (color-blind users).
- [ ] Keyboard navigation для `TaskDialog`.
- [ ] High contrast theme support.

### Testing (покрытие тестами)

- [ ] Тесты для `core/recording_service.py` (unit).
- [ ] Тесты для `api/websocket.py` event handling.
- [ ] Тесты edge cases: multi-monitor disconnect, audio device hot-plug,
  disk full, rapid start/stop.
- [ ] Integration tests для WebSocket real-time events.
- [ ] Тесты FFmpeg writer failure scenarios.
- [ ] Тесты scheduler persistence после restart.
- [ ] Тесты concurrent recording requests.
- [ ] Тесты rate limiter edge cases.
- [ ] GUI unit tests для `TaskDialog` validation.

### Legacy Cleanup (очистка legacy)

- [ ] Deprecate `gui/models/recording_state.py` — использовать прямой
  импорт из `core.recording_state`.
- [ ] Deprecate `CaptureType`/`AudioType` aliases в
  `core/recording_types.py:42-43`.
- [ ] Рассмотреть удаление `_record_loop_pyaudio()` fallback
  в `recorder/audio_recorder.py:364-391`.

## P3 (функциональные улучшения)

- [ ] Реализовать реальный WebSocket транспорт вместо заглушки
  в `api/websocket.py`.
- [ ] Механизм backup/restore конфигурации.
- [ ] Восстановление записи после краша приложения.
- [ ] Batch операции в API (`start/stop/status` для нескольких задач).
- [ ] Диалог горячих клавиш в GUI.
- [ ] Абстрагировать общую логику `pause/resume/stop`
  из `video_recorder` и `audio_recorder` — устранить дублирование.

## Новые задачи от 2026-03-29

- [ ] [P1][Security] Ограничить CORS-политику: заменить
  `CORS(self.app)` на allowlist (`origins`, `methods`,
  `allowed_headers`) с тестами preflight/actual request
  для разрешенного и запрещенного origin
  (`api/server.py`, `tests/integration/test_api_server_lifecycle.py`).
- [ ] [P1][Stability] Закрывать и дожидаться stderr-reader
  потока FFmpeg в `close()`/cleanup, покрыть тестом
  многократный start/stop без утечек потоков
  (`recorder/ffmpeg_writer.py`, `tests/unit/test_ffmpeg_writer.py`).
- [ ] [P1][Security] Использовать абсолютный путь к FFmpeg/FFprobe
  во всех subprocess-вызовах вместо литерала `ffmpeg`
  (`recorder/encoder.py`, `recorder/ffmpeg_writer.py`,
  `recorder/utils.py`).
- [ ] [P2][Perf] Убрать полное копирование deque в
  `get_recent_events()` и возвращать последние N событий
  без `list(self._events)` на каждый запрос
  (`api/websocket.py`, `tests/unit/test_websocket.py`).
- [ ] [P2][Stability] Сделать `setup_logger()` идемпотентным
  по `atexit` и handler lifecycle
  (`logger_config.py`, `tests/unit/test_logger_config.py`).
- [ ] [P2][Security] Нормализовать `X-Request-ID`:
  whitelist символов и лимит длины (например 64),
  при нарушении генерировать новый ID
  (`api/server.py`, `api/routes.py`,
  `tests/integration/test_api_error_handling.py`).

## Новые задачи от 2026-03-29 (итерация 2)

- [ ] [P1][Tests] Устранить нестабильность
  `tests/unit/test_config_extended.py::TestConfigSave::test_save_creates_directory`
  из-за `PermissionError (WinError 5)` при работе с временными
  каталогами (`tests/conftest.py`, `tests/unit/test_config_extended.py`).
- [ ] [P1][Tooling] Сделать `uv run mypy .` воспроизводимым:
  исключить runtime/tmp-директории (`tmp_pytest_run*`,
  `.tmp_pytest_runs`, `.pytest_local_tmp`, `.codex_tmp`)
  через конфигурацию и проверить в CI-подобном запуске
  (`pyproject.toml`, `.gitignore`).
- [ ] [P2][Testing] Снять полный `skip` с `tests/unit/test_gui_views.py`
  или вынести эти тесты в отдельный job с `pytest-qt`
  и реальным PyQt6-окружением.
- [ ] [P3][Code Quality] Закрыть техдолг в `api/routes.py`:
  либо внедрить неиспользуемые декораторы (`api_endpoint`,
  `api_callback`), либо удалить мертвый код и комментарий `TODO`.

## Новые задачи от 2026-03-29 (итерация 3)

- [ ] [P1][Scheduler] Сделать `add_task()`/`update_task()`
  атомарными: при ошибке `_schedule_job()` возвращать ошибку
  и откатывать `enabled`/изменения задачи
  (`scheduler/task_scheduler.py`).
- [ ] [P1][Scheduler] Валидация `time_of_day` (`HH:MM`)
  до вызова APScheduler: диапазон `00:00..23:59`
  и тесты для `24:00`, `09:77`, `abc`
  (`scheduler/task_scheduler.py`, `tests/unit/test_scheduler.py`).
- [ ] [P1][API] Сделать lifecycle idempotency-store корректным
  при цикле `stop -> start`: пересоздание store/cleanup-thread
  и тест `start/stop/start` (`api/server.py`,
  `tests/unit/test_api_server.py`).
- [ ] [P2][API] Ограничить конкуренцию фоновых API-операций:
  bounded `ThreadPoolExecutor` + лимит очереди
  и политика отказа (`api/server.py`).
- [ ] [P2][API] Добавить guard от запуска API без маршрутов
  (проверка ключевых routes в `start()` или
  явная регистрация в `APIServer`)
  (`api/server.py`, `main.py`, `api/routes.py`).

## Правило ведения TODO

- Закрытые задачи удаляем из файла, не оставляем в виде `[x]`.
- Незакрытые задачи переносим в новый TODO ближайшего релиза.
