# TODO: Рефакторинг-План До `v1.4.6`

> Обновлено: 2026-03-30  
> Фокус релиза: устойчивый рефакторинг без регрессий поведения

## P0 (обязательно в `v1.4.6`)

- [x] ~~Добавить валидацию свободного места на диске перед стартом записи~~
  (commit: 8b35cf7). Функция `check_disk_space()` в `recorder/utils.py`.
- [x] ~~Предотвратить повреждение видео при ошибке FFmpeg write~~
  (commit: b864177). Флаг `is_corrupted`, метод `cleanup_corrupted_file()`.
- [x] ~~Исправить race condition при потере capture-сессии~~
  (commit: ca8fb16). Проверка `is_capture_lost` до/после `read_frame()`.
- [x] ~~Валидация X-Forwarded-For против IP spoofing~~
  (commit: beca1f4). Паттерны IPv4/IPv6, валидация перед использованием.
- [x] ~~Устранить утечку API key через env fallback~~
  (commit: ecb0cb5). Credential Manager — единственное хранилище.
- [x] ~~Валидация cron_expression перед созданием scheduler task~~
  (commit: e6682be). Валидация через `CronTrigger.from_crontab()`.

## P1 (важно, если успеваем до code freeze)

- [ ] Вынести слой сервисов для FFmpeg-пайплайна:
  отдельные `ProcessSupervisor`, `FinalizeService`, `RecoveryPolicy`.
- [ ] Зафиксировать детерминированный shutdown потоков/процессов записи:
  единый протокол `stop -> join(timeout) -> force cleanup`.
- [ ] Протащить `request_id/trace_id` в фоновые API-операции
  и связанные бизнес-логи для end-to-end корреляции.
- [ ] Продолжить декомпозицию крупных runtime-модулей:
  `main.py`, `api/server.py`, `api/routes.py`.
- [ ] Снизить число широких `except Exception` в критичных путях
  API/recording/scheduler и заменить на точечные обработчики.
- [ ] Снизить риск регрессий GUI: уменьшить долю `skip`-тестов
  и добавить smoke-проверки view-контрактов.
- [ ] Зафиксировать корректный shutdown debounce-сохранения конфига:
  без потери последних изменений и без висячих таймеров.
- [ ] Добавить DST/timezone интеграционные тесты scheduler
  для `daily/weekly/cron` сценариев.
- [ ] Ввести типизированную модель API-операций вместо
  неструктурированных `dict[str, Any]` в runtime-слое.

### P1-Critical (блокирующие проблемы)

- [x] ~~Уведомлять пользователя при потере audio chunks~~
  (commit: e0ccca2). Callback `on_chunks_dropped`, property `dropped_chunks`.
- [x] ~~Исправить potential deadlock в video_recorder.stop()~~
  Уже исправлено в текущем коде - lock освобождается до join().
- [x] ~~Устранить утечку FFmpeg stderr reader thread~~
  Откат select-based решения из-за несовместимости с Windows.
  Закрытие stream в _stop_stderr_reader() достаточно.
- [x] ~~Валидация rect coordinates против frame bounds~~
  Уже реализовано в `_WindowsCaptureSession.on_frame_captured()`.
- [x] ~~Уведомлять при fallback на full screen при window not found~~
  (commit: cd6f4c4). Улучшено логирование, сохраняется искомый заголовок.
- [x] ~~Ограничить memory growth в API idempotency store~~
  (commit: 670245c). Лимит `_MAX_PATH_ENTRIES = 100` для path_counts.
- [x] ~~Возвращать ошибку при невалидном state transition в pause_recording~~
  (commit: 3d40121). `pause_recording()` и `resume_recording()` возвращают bool.

## P2 (после стабилизации P0/P1)

- [ ] Ввести ring-buffer для live-логов GUI и ограничение памяти
  для долгих сессий.
- [ ] Оптимизировать observability-метрики:
  перцентили без полной сортировки на каждый запрос.
- [ ] Перевести критичные тайминги записи на `time.monotonic()`
  с единым util-слоем времени.
- [ ] Ввести deprecation-политику для legacy API routes
  с timeline удаления и тестами обратной совместимости.
- [ ] Разделить DTO API и внутренние доменные модели записи через
  adapter-layer между `api/*` и `core/*`.
- [ ] Добавить benchmark-suite для hot-path API
  (`/health`, `/api/v1/status`, recent events, idempotency replay)
  с базовой линией и порогом регрессии.
- [ ] Разобрать слой `core/contracts.py`:
  интегрировать в реальный runtime/CLI поток или удалить как legacy.
- [ ] Усилить диагностику output path на Windows:
  заменить `os.access` на пробную запись/удаление temp-файла.
- [ ] Добавить property-based/табличные тесты для `api/schemas.py`
  и преобразований scheduler payload.
- [ ] Расширить pre-commit quality gates:
  обязательный `mypy` и быстрый smoke-набор тестов.

## Рефакторинг-Стандарты `v1.4.6`

- [ ] Не менять внешние API-контракты без явной миграции и changelog entry.
- [ ] Каждый рефакторинг-коммит должен сопровождаться тестом,
  который доказывает сохранение поведения.
- [ ] Запрет на «большие смешанные» PR:
  одна архитектурная цель на один логический набор изменений.
- [ ] Для новых модулей: обязательные docstring, type hints,
  явные зависимости через конструктор.

## Release Gates для `v1.4.6`

- [ ] Все P0 задачи закрыты и удалены из этого файла.
- [ ] `CI` полностью зелёный на `main` минимум в двух последовательных прогонах.
- [ ] Ручной regression checklist для GUI/API выполнен и приложен в `plans/`.
- [ ] Обновлены `CHANGELOG.md`, `plans/release-preflight-v1.4.6.md`,
  релизные заметки и wiki.
