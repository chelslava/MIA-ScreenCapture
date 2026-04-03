# Changelog

## [Unreleased]

### Fixed
- Добавлен pre-start health-check FFmpeg перед запуском записи:
  если FFmpeg недоступен во время работы приложения, запись теперь не
  стартует и возвращает понятную ошибку вместо позднего сбоя в процессе.
- Улучшена обработка потери захвата экрана во время записи:
  для `window capture` добавлено автоматическое восстановление захвата,
  при окончательной потере корректно отправляется ошибка пользователю,
  сохраняется последний доступный кадр и выполняется предсказуемая
  финализация ресурсов.
- Исправлена интерпретация cron `day_of_week` в планировщике:
  значения в стандартном формате crontab (например, `1-5`) теперь
  корректно означают `понедельник-пятница`, а не смещённые дни недели.

### Changed
- Проверка доступности FFmpeg кэшируется на короткий TTL в
  `RecordingController`, чтобы единообразно покрывать GUI/API/scheduler
  path без лишних повторных вызовов `ffmpeg -version`.

### Tests
- Добавлены unit-тесты на отказ старта без FFmpeg и на поведение
  TTL-кэша проверки перед записью.
- Добавлены unit-тесты на reconnect/finalization сценарии при потере
  захвата экрана.
- Добавлен regression test на cron weekday semantics в scheduler.

## [1.4.7] - 2026-04-03

### Fixed
- Убраны всплывающие консольные окна при запуске GUI: все FFmpeg/FFprobe
  процессы запускаются с флагом `CREATE_NO_WINDOW`.
- Запись теперь создаёт директорию вывода, если она отсутствует.

### Tests
- Актуализированы unit-тесты subprocess-запусков с учётом скрытия консоли.

## [1.4.6] - 2026-04-03

### Fixed
- Исправлена запись FFmpeg через stdin: включён бинарный режим, кадры
  пишутся без ошибок типов.
- Исправлена финализация записи: кодирование идёт во временный файл,
  перенос в итоговый путь выполняется безопасно с обработкой
  `PermissionError`.
- Исправлена обработка пути вывода: если указана директория, имя файла
  генерируется автоматически; при отсутствии расширения добавляется
  `.mp4`.
- Исправлена проверка свободного места для путей с расширением файла.
- Обновлён пример расписания в Swagger: дата всегда в будущем.
- Уменьшено потребление памяти при захвате кадра: убрано лишнее копирование.

### Changed
- Добавлен fallback сохранения в `Videos\\Recordings`, если запись нельзя
  переместить в целевую директорию.

### Tests
- Стабилизированы unit-тесты FFmpeg/Encoder под бинарный stdin и
  временный выходной файл.
- Устранены зависания unit-тестов: мокированы проверка bind-адреса и
  поток записи аудио.
- Стабилизирован тест на timing-атаку: увеличен размер выборки и
  использована медианная оценка.

### Added
- **WebSocket Transport** (этап 1-2): Real-time транспорт для событий записи
  - Endpoint `/ws` для WebSocket подключений
  - Протокол с каналами: `recording`, `system`, `api`, `metrics`
  - Аутентификация через `X-API-Key` или query-параметр `token`
  - Heartbeat (ping/pong) с таймаутом 45 секунд
  - Начальный snapshot при подключении
  - Зависимости: `flask-sock`, `simple-websocket`

### Fixed
- **FFmpeg process leak**: При `BrokenPipeError` процесс теперь корректно
  завершается через `_terminate_process_safely()`, файл помечается как
  повреждённый.
- **Silent fallback при ненайденном окне**: `CaptureArea.from_window()` 
  теперь принимает параметр `raise_if_not_found`. API/scheduler пути
  используют строгий режим с ошибкой при ненайденном окне.

### Changed
- Усилен coverage gate в CI:
  `coverage` job теперь использует `--cov-fail-under=60` и
  дополнительно проверяет покрытие изменённых production Python-файлов
  через `scripts/check_diff_coverage.py` (порог `35%` на файл).
- Устранена гонка планировщика с `APScheduler JobLookupError`:
  разовые задачи с временем в прошлом больше не отправляются в
  APScheduler, а переводятся в отключённое состояние без запуска.
- `TaskScheduler._unschedule_job` сделан идемпотентным:
  добавлена безопасная проверка наличия job и точечная обработка
  `JobLookupError` без побочных сбоев в потоках планировщика.
- Добавлены защитные integration-тесты рефакторинга API:
  `tests/integration/test_api_contract_snapshots.py` фиксирует
  snapshot/contract для `/health`, `/api/v1/status`, `/api/v1/config`.
- Усилен lifecycle smoke API сервера:
  `tests/integration/test_api_server_lifecycle.py` теперь покрывает
  несколько циклов `start/stop` для проверки стабильности оркестрации.
- Расширен CI-охват строгой типизации (`mypy`) для модулей
  `main.py`, `logger_config.py`, `core/container.py`;
  дополнительно устранены ошибки `mypy` в `main.py` без изменения
  runtime-поведения.
- Добавлен единый маппинг исключений доменного слоя в API-контракт:
  `api/error_mapping.py` нормализует `MIAError` и связанные исключения
  в `(status_code, error.code, message, details)`.
- В `api/routes.py` обработка `except Exception` переведена
  на централизованный `_exception_response(...)`, чтобы доменные ошибки
  возвращались в стандартизированном JSON-формате.
- Обработчики исключений в `api/server.py` приведены к единому контракту
  ошибки (`success/error/details`) без legacy-формата строкового `error`.
- Request lifecycle middleware API (`before_request`/`after_request`)
  вынесен из `APIServer` в отдельный модуль `api/request_lifecycle.py`
  с сохранением контрактов `/health`, `X-Request-ID` и access-логов.
- В `main.py` продолжена P0-декомпозиция `VideoRecorderApp`:
  операции записи (`status/start/stop/pause/recordings`) выделены
  в `RecordingRuntimeCoordinator` с делегированием из `VideoRecorderApp`.
- Завершён шаг декомпозиции `VideoRecorderApp` по coordinator-слоям:
  API-операции вынесены в `ApiRuntimeCoordinator`, теперь GUI/API/recording
  делегируются отдельным координаторам с явными зонами ответственности.
- Stateful lifecycle API вынесен в отдельный менеджер
  `core/api_lifecycle_manager.py` (`created/starting/running/stopping/stopped`);
  `ApiRuntimeManager` переведён на использование этого слоя для
  более безопасной обработки `start/stop/restart`.
- Подтверждён единый источник модели состояния записи:
  `gui.models.recording_state` используется как совместимый shim-реэкспорт
  типов из `core.recording_state` без дублирования доменной модели.
- В `ApiRuntimeManager.apply_api_settings` внедрён транзакционный путь
  для API-настроек: `validate -> apply -> persist`, rollback при ошибке
  сохранения и отсутствие частичных side-effect обновлений токена.
- В `main.py::_update_config` внедрён транзакционный путь обновления
  секций конфигурации: предварительная валидация секций, apply только
  после успешной проверки и rollback при ошибке `config.save()`.
- `main.py` делегирует API runtime-операции в отдельный менеджер
  `core/api_runtime_manager.py` для снижения связности и подготовки
  дальнейшей декомпозиции `VideoRecorderApp`.
- Убраны silent-except ветки в runtime-коде:
  `scheduler/task_scheduler.py`, `recorder/video_recorder.py`,
  `gui/hotkeys.py`; вместо подавления ошибок добавлено логирование.
- Усилена остановка видеозаписи:
  `VideoRecorder.stop()` теперь выполняет более детерминированный
  shutdown потока захвата (`stop session -> join(timeout) -> cleanup`)
  с явной диагностикой таймаутов.
- В `ApiRuntimeManager` чтение API-ключа сделано без побочных эффектов;
  миграция legacy ключа из config вынесена в явный шаг при старте API.
- Загрузка `.env` в `main.py` переведена из import-time side effect в
  явный bootstrap-шаг `_load_environment()` внутри `main()`.
- Введён единый `RequestContext` (`request_id`, `trace_id`, `client_ip`)
  для API; контекст теперь формируется централизованно и используется
  в middleware сервера и нормализации API-ответов.
- Для фоновой API-операции `stop` добавлен явный проброс
  `request_id/trace_id/client_ip` в operation metadata и ответы
  `/api/v1/stop` + `/api/v1/operations/{id}` для сквозной корреляции.
- Оптимизирован `WebSocketManager.get_recent_events()`:
  чтение последних событий теперь выполняется по хвосту `deque`
  без полного копирования буфера на каждый запрос.
- Для фоновых API-операций внедрён bounded executor
  (`workers + queue capacity`) с политикой отказа при переполнении
  и метриками saturation в observability payload.
- Начат декомпозиционный рефакторинг `TaskScheduler`:
  storage-слой вынесен в отдельный модуль `scheduler/task_storage.py`,
  trigger-builder вынесен в `scheduler/trigger_builder.py`,
  execution-engine вынесен в `scheduler/execution_engine.py`,
  а `_load_tasks/_save_tasks`, `_create_trigger` и `_execute_task`
  в `TaskScheduler` переведены на тонкие обёртки над выделенными слоями.
- В `main.py` начало P0-декомпозиции `VideoRecorderApp`:
  GUI bootstrap вынесен в отдельный `GuiRuntimeCoordinator`, а
  `_run_gui()` и `_restart_api_server()` переведены на явную делегацию
  координаторам runtime-слоя.
- Добавлен централизованный маппинг доменных исключений
  (`MIAError` и наследники) в стабильный API-контракт ошибок
  через `api/error_mapping.py`; роуты `api/routes.py` теперь
  используют этот маппинг вместо универсального fallback `500`.
- В `main.py` начат P0-рефакторинг декомпозиции `VideoRecorderApp`:
  выделен `GuiRuntimeCoordinator`, а запуск GUI (`_run_gui`) переведён
  на явное делегирование координатору без изменения поведения.

### Tests
- Расширены unit-тесты устойчивости API runtime-хранилищ:
  добавлены edge/race сценарии для `APIIdempotencyStore`
  (`abort`, `in_progress`, `5xx` без replay) и `APIOperationStore`
  (`runner exception`, `submit after stop`, `wait unknown id`)
  в `tests/unit/test_api_server.py`.
- Добавлены integration-проверки v1 lifecycle/idempotency контрактов:
  `/api/v1/stop` (`202` при `running`), `/api/v1/operations/{id}` (`200/404`),
  `idempotency_in_progress` и слишком длинный `Idempotency-Key`
  в `tests/integration/test_api_recording_routes.py`.
- Добавлены regression-тесты scheduler на устойчивость к
  `JobLookupError` в путях `remove_task`, `update_task`,
  `enable_task(..., False)` в `tests/unit/test_scheduler.py`.
- Добавлен regression-тест на поведение разовой задачи в прошлом:
  задача сохраняется, но не планируется в APScheduler
  (`tests/unit/test_scheduler.py`).
- Добавлены unit-тесты маппинга исключений:
  `tests/unit/test_api_error_mapping.py`.
- Расширены интеграционные проверки обработки ошибок:
  `tests/integration/test_api_error_handling.py` теперь покрывает
  доменные исключения (`RecordingNotActiveError`, `ConfigurationError`).
- Добавлены unit-тесты middleware request lifecycle:
  `tests/unit/test_request_lifecycle.py`.
- Расширены unit-тесты runtime-декомпозиции `main.py`:
  добавлена проверка делегирования `stop_recording` в
  `RecordingRuntimeCoordinator`.
- Добавлены unit-проверки lifecycle-состояния API runtime и сценария
  отказа старта при переходном состоянии в
  `tests/unit/test_main_api_runtime.py`.
- Добавлены unit-тесты lifecycle-менеджера API:
  `tests/unit/test_api_lifecycle_manager.py`.
- Добавлен unit-тест делегирования API-старта в coordinator:
  `tests/unit/test_main_api_runtime.py::
  test_start_api_server_delegates_to_api_runtime_coordinator`.
- Добавлен защитный unit-тест совместимости GUI/core модели состояния:
  `tests/unit/test_gui_models.py::TestGuiCoreRecordingStateCompatibility`.
- Добавлены unit-тесты транзакционного обновления API-настроек:
  атомарность при валидационной ошибке и rollback при ошибке persist
  в `tests/unit/test_main_api_runtime.py`.
- Добавлены unit-тесты транзакционности для `main.py::_update_config`:
  атомарность при валидации и rollback при ошибке сохранения
  (`tests/unit/test_main_api_runtime.py`).
- Добавлены/обновлены unit-тесты устойчивости:
  `tests/unit/test_hotkeys.py`,
  `tests/unit/test_scheduler.py`,
  `tests/unit/test_video_recorder.py`,
  `tests/unit/test_main_api_runtime.py`.
- Добавлены unit-тесты entrypoint-bootstrap логики:
  `tests/unit/test_main_entrypoint.py`.
- Добавлены unit-тесты request-контекста:
  `tests/unit/test_request_context.py`.
- Обновлены интеграционные тесты записи
  `tests/integration/test_api_recording_routes.py` для проверки
  request-context полей в payload операции остановки.
- Добавлены unit-тесты bounded executor операций API:
  `tests/unit/test_api_server.py::TestAPIOperationStore`.
- Добавлены unit-тесты storage-слоя scheduler:
  `tests/unit/test_task_storage.py`.
- Добавлены unit-тесты trigger-builder scheduler:
  `tests/unit/test_trigger_builder.py`.
- Добавлены unit-тесты execution-engine scheduler:
  `tests/unit/test_execution_engine.py`.
- Добавлены unit-тесты маппинга исключений API:
  `tests/unit/test_api_error_mapping.py`.
- Расширены интеграционные тесты API-ошибок:
  `tests/integration/test_api_error_handling.py`
  (маппинг `ValueError -> 400 validation_error`,
  `RecordingStateError -> 409 conflict`).
- Обновлены unit-тесты runtime-декомпозиции `main.py`:
  добавлена проверка делегации `_run_gui()` координатору и
  обновлён сценарий делегации `_restart_api_server()`.
- Добавлен unit-тест делегирования GUI-рантайма:
  `tests/unit/test_main_api_runtime.py::
  test_run_gui_delegates_to_gui_runtime_coordinator`.

### Planned for 1.5.0
- Формирование scope следующего релиза после стабилизации `1.4.5`.

## [1.4.5] - 2026-03-29

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
- Блокирующий `mypy`-scope в CI расширен на `api/auth.py`;
  устранены типовые проблемы в модуле аутентификации.
- Блокирующий `mypy`-scope в CI расширен на `api/rate_limiter.py`.
- Убрано искусственное ограничение таймаута GUI для API `stop`:
  остановка записи теперь ожидает завершение без `TimeoutError`.
- Обновлён unit-тест runtime API (`tests/unit/test_main_api_runtime.py`)
  для проверки сценария stop без таймаута GUI.
- Блокирующий integration-step в CI расширен:
  добавлен `tests/integration/test_api_extended.py`.
- Блокирующий integration-step в CI расширен:
  добавлен `tests/integration/test_full_workflow.py`.
- Блокирующий integration-step в CI расширен:
  добавлены `tests/integration/test_recording_flow.py` и
  `tests/integration/test_scheduler_integration.py`.
- Блокирующий `mypy`-scope в CI расширен на
  `api/schemas.py`, `gui/models/recording_state.py`,
  `recorder/encoder.py`.
- Блокирующий `mypy`-scope в CI расширен на
  `api/routes.py`, `api/websocket.py`,
  `gui/notifications.py`, `gui/tray_icon.py`,
  `recorder/ffmpeg_writer.py`.
- `api/rate_limiter.py` переведен на `time.monotonic()` для окон
  rate limit и блокировок, добавлены unit-тесты на monotonic-сценарии
  в `tests/unit/test_rate_limiter.py`.
- `get_api_key()` в `api/auth.py` теперь возвращает маскированный ключ
  для безопасного отображения; добавлены unit-тесты маскирования
  (длинный/короткий/пустой ключ).
- Устранены точечные type-замечания для `mypy` в
  `gui/hotkeys.py`, `gui/scheduler_tab.py`,
  `recorder/audio_recorder.py`.
- Блокирующий `mypy`-scope в CI расширен на
  `gui/hotkeys.py`, `gui/scheduler_tab.py`,
  `recorder/audio_recorder.py`, `recorder/utils.py`.
- Исправлены типовые проблемы для `mypy` в
  `api/server.py` и `core/recording_service.py`
  без изменения runtime-поведения.
- Блокирующий `mypy`-scope в CI расширен на
  `api/server.py` и `core/recording_service.py`.
- Блокирующий `mypy`-scope в CI расширен на безопасные
  GUI view-модули:
  `gui/views/__init__.py`, `gui/views/audio_view.py`,
  `gui/views/capture_view.py`, `gui/views/output_view.py`,
  `gui/views/video_view.py`.
- Устранены type-замечания в `gui/views/api_settings_view.py`
  и `gui/views/diagnostics_view.py`; оба модуля включены
  в блокирующий `mypy`-scope CI.
- Устранены type-замечания в `gui/main_window.py`;
  модуль добавлен в блокирующий `mypy`-scope CI.
- Устранены type-замечания в
  `gui/controllers/settings_controller.py` и
  `gui/controllers/recording_controller.py`.
- Блокирующий `mypy`-scope в CI расширен на
  `gui/controllers/settings_controller.py`,
  `gui/controllers/recording_controller.py` и
  `gui/backends/recording_backend.py`.
- Устранены type-замечания в `recorder/video_recorder.py`
  и удалён избыточный `cast` в
  `gui/controllers/recording_controller.py`.
- Блокирующий `mypy`-scope в CI расширен на
  `recorder/video_recorder.py`.
- Для предрелизной стабильности `mypy` добавлены исключения
  служебных runtime/tmp-директорий
  (`tmp_pytest_run*`, `.tmp_pytest_runs`,
  `.pytest_local_tmp`, `.codex_tmp`, `tests/.local_tmp`).
- `.gitignore` дополнен правилами для
  `.tmp_pytest_runs/`, `.pytest_local_tmp/`, `.codex_tmp/`
  чтобы локальные служебные файлы не попадали в рабочий набор.
- Удалён неиспользуемый техдолг в `api/routes.py`:
  убраны мёртвые декораторы `api_endpoint` и `api_callback`
  вместе с устаревшим TODO-комментарием.
- CORS-политика API ограничена allowlist для localhost/127.0.0.1
  с явными `methods`/`allowed_headers`;
  добавлены интеграционные тесты preflight и actual-request
  для разрешённых и запрещённых origin.
- Запуски `ffmpeg`/`ffprobe` переведены на абсолютные пути
  через единый резолвер executable в `recorder/utils.py`;
  обновлены unit-тесты для `recorder/utils.py` и
  `recorder/ffmpeg_writer.py`.
- `FFmpegVideoWriter.close()` теперь корректно закрывает stderr stream,
  дожидается завершения stderr-reader потока и очищает его состояние;
  добавлен unit-тест на многократные `open/close` без утечек потоков.
- Жизненный цикл `idempotency store` в API исправлен для
  сценария `stop -> start`: при повторном старте сервер
  пересоздаёт хранилище и cleanup-thread;
  добавлен unit-тест `start/stop/start`.
- Стабилизирован `tests/unit/test_config_extended.py::TestConfigSave::test_save_creates_directory`
  (Windows): тест переведён на `tmp_path`, устранён флейк
  с `PermissionError (WinError 5)` при cleanup.
- Усилена устойчивость `TaskScheduler`:
  `add_task`/`update_task`/`enable_task` теперь откатывают изменения
  при ошибке планирования, а `time_of_day` валидируется в формате
  `HH:MM` с диапазоном `00:00..23:59`.
- Добавлены/обновлены unit-тесты `tests/unit/test_scheduler.py`
  для сценариев валидации времени и отката при неудачном планировании.
- Интеграционные тесты `tests/integration/test_api_extended.py`
  мигрированы на `/api/v1/*` и стабилизированы по rate-limit.
- Добавлена утилита `scripts/api_smoke_run.py` для 30+ минутного
  smoke-прогона API и автодобавления отчёта в release-note.
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
