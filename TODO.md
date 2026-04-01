# TODO: План Развития До `v1.5.0`

> Обновлено: 2026-04-01
> Текущая версия: 1.4.6-dev
> Целевой релиз: 1.5.0

## P0 (обязательно в `v1.5.0`)

### Критичные (HIGH) — стабильность

- [x] **FFmpeg process leak при BrokenPipeError**: В `ffmpeg_writer.py:261-287`
  - **Выполнено** (commit: fb71bb0): добавлен метод `_terminate_process_safely()`

- [ ] **Daemon-потоки с ресурсами**: Потоки захвата создаются как `daemon=True`
  - **Отложено**: требует архитектурного рефакторинга, отдельный PR

- [x] **Silent fallback при ненайденном окне**: `CaptureArea.from_window()`
  - **Выполнено** (commit: e815393): добавлен параметр `raise_if_not_found`

### WebSocket Transport

- [x] **WebSocket Transport**: Реализовать реальный транспорт для событий записи
  - Этап 1-4: ✅ Выполнено (commit: 86fa106 и последующие)

- [x] **DST/Timezone тесты scheduler**: Добавить интеграционные тесты
  - **Выполнено**: TestDSTTimezoneHandling класс добавлен

### CI

- [x] **Lint ошибки (F401, F841, I001)**: Исправлены все lint ошибки
  - **Выполнено** (commits: 35918f6, eeb0b85, a6743c5, 94ed14d, fcd8120)

- [ ] **Tests timeout (30 мин)**: Нагрузочные тесты WebSocket слишком медленные
  - **Требуется**: оптимизировать test_websocket_load.py или увеличить timeout

## P1 (важно, если успеваем до code freeze)

### Архитектура и декомпозиция

- [ ] **Декомпозиция runtime-модулей**: Рефакторинг крупных файлов:
  - `main.py` (1359 строк) → цель <400 строк
  - `api/server.py` (1124 строки) → цель <400 строк
  - `api/routes.py` (994 строки) → цель <400 строк
- [ ] **Слой сервисов FFmpeg-пайплайна**: Вынести отдельные компоненты:
  `ProcessSupervisor`, `FinalizeService`, `RecoveryPolicy`.
  Снижение связности в `recorder/encoder.py`.
- [ ] **Типизированные API-операции**: Заменить `dict[str, Any]` на
  dataclass/Pydantic модели в runtime-слое API.
- [ ] **Унификация RecordingState**: Enum дублируется в `core/recording_state.py`
  и `recorder/video_recorder.py:34-40`. Оставить одно определение.

### Надёжность и устойчивость

- [ ] **Race condition в capture loop**: `_capture_lost` устанавливается без
  защиты `_lock` (`video_recorder.py:528-565`). Использовать `threading.Event`
  или атомарный флаг.
- [ ] **Timeout инициализации windows-capture**: `capture.start_free_threaded()`
  без таймаута (`video_recorder.py:224`). Добавить таймаут на первый кадр.
- [ ] **Точечные обработчики исключений**: Снизить число `except Exception`
  в критичных путях API/recording/scheduler. Заменить на конкретные типы.
- [ ] **Детерминированный shutdown**: Зафиксировать протокол
  `stop -> join(timeout) -> force cleanup` для всех потоков записи.
- [ ] **Ring-buffer для GUI-логов**: Ограничить память для долгих сессий
  API-вкладки (профилирование показало лаги при >30 мин).
- [ ] **Health-check FFmpeg pipeline**: Детекция зависания writer и
  авто-рекавери (снижение кейсов `moov atom not found`).
- [ ] **Потеря аудио-чанков**: При переполнении очереди чанки отбрасываются
  (`audio_recorder.py:416-436`), но нет уведомления пользователя через GUI.
  Пробросить через event bus.
- [ ] **Валидация rect_coords**: Некорректные координаты молча заменяются
  на fallback (`recording_service.py:232-248`). Добавить валидацию с ошибкой.
- [ ] **Обработка TimeoutError в `_run_on_gui_thread`**: Метод выбрасывает
  `TimeoutError`, но в `_execute_scheduled_task` нет обработки
  (`main.py:877-901`).

### Тестирование и качество

- [ ] **GUI smoke-тесты**: Добавить базовые проверки view-контрактов,
  уменьшить долю пропущенных тестов.
- [ ] **Benchmark-suite для hot-path API**: `/health`, `/api/v1/status`,
  recent events, idempotency replay с порогом регрессии.
- [ ] **Property-based тесты**: Для `api/schemas.py` и преобразований
  scheduler payload через `hypothesis`.

## P2 (после стабилизации P0/P1)

### Производительность

- [ ] **Блокирующий sleep в capture loop**: `time.sleep(sleep_time * 0.9)`
  (`video_recorder.py:608-611`) — неточный метод контроля FPS.
  Использовать `time.perf_counter()` с `Event.wait()`.
- [ ] **Копирование кадров**: `np.array(bgr, copy=True)` на каждом кадре
  (`video_recorder.py:204`). Рассмотреть zero-copy подход.
- [ ] **Оптимизация observability-метрик**: Перцентили без полной
  сортировки на каждый запрос (алгоритм P-square или histogram).
- [ ] **Унификация time.monotonic()**: Перевести все критичные тайминги
  записи на единый util-слой.
- [ ] **Профилирование hot-path захвата**: Метрики jitter FPS,
  оптимизация пути кадра от capture до encode.
- [ ] **Incremental diff для GUI-логов**: Добавить inotify/file watcher
  вместо периодического чтения файла.
- [ ] **Кэш списка аудиоустройств**: `sd.query_devices()` при каждом
  `start()` (`audio_recorder.py:237-257`). Кешировать с TTL.

### Техдолг и поддержка

- [ ] **Deprecation-политика для legacy API**: Timeline удаления
  `/api/*` routes (без `v1`) с тестами обратной совместимости.
- [ ] **Разделение DTO и доменных моделей**: Adapter-layer между
  `api/*` и `core/*` для изоляции слоёв.
- [ ] **Диагностика output path на Windows**: Заменить `os.access` на
  пробную запись/удаление temp-файла для надёжной проверки прав.
- [ ] **JSON-логи для API**: Опционально (по флагу) структурированные
  логи с `trace_id`, `request_id`, `latency_ms`, `status`.
- [ ] **Кэширование expensive queries**: `get_audio_devices()` и
  `get_available_windows()` вызываются при каждом запросе `/devices`,
  `/windows`. Добавить TTL-кэш.
- [ ] **Конфигурируемые таймауты FFmpeg**: Вынести `_FFMPEG_CLOSE_TIMEOUT_SECONDS`
  и другие таймауты в конфигурацию (`ffmpeg_writer.py:22-25`).
- [ ] **Обработка PermissionError при создании директории**: Явная обработка
  ошибок при `mkdir()` в `video_recorder.py:416` и `audio_recorder.py:196`.

### Pre-commit и CI

- [ ] **Обязательный mypy в pre-commit**: Расширить quality gates.
- [ ] **Быстрый smoke-набор тестов**: Для pre-commit hook (<30 сек).

## Рефакторинг-Стандарты

- [ ] Не менять внешние API-контракты без явной миграции и changelog entry.
- [ ] Каждый рефакторинг-коммит сопровождается тестом, доказывающим
  сохранение поведения.
- [ ] Запрет на «большие смешанные» PR: одна архитектурная цель на PR.
- [ ] Для новых модулей: обязательные docstring, type hints, явные
  зависимости через конструктор.

## Release Gates для `v1.5.0`

- [ ] Все P0 задачи закрыты.
- [ ] CI полностью зелёный на `main` минимум в двух последовательных прогонах.
- [ ] Ручной regression checklist для GUI/API выполнен и приложен в `plans/`.
- [ ] Обновлены `CHANGELOG.md`, `README.md`, версия в `pyproject.toml`.
- [ ] Подготовлен release preflight-чеклист `plans/release-preflight-v1.5.0.md`.
