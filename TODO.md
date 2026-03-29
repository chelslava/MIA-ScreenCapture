# TODO: Рефакторинг-План До `v1.4.6`

> Обновлено: 2026-03-30  
> Фокус релиза: устойчивый рефакторинг без регрессий поведения

## P0 (обязательно в `v1.4.6`)

- [ ] Разбить `main.py:VideoRecorderApp` на координирующие компоненты:
  `ApiRuntimeCoordinator`, `GuiRuntimeCoordinator`,
  `RecordingRuntimeCoordinator` с явными зонами ответственности.
- [ ] Декомпозировать `api/routes.py:register_routes()` на группы роутов
  (`status`, `recording`, `config`, `schedule`, `observability`)
  и убрать единый «монолитный» регистратор.
- [ ] Вынести lifecycle API-сервера в отдельный stateful-менеджер
  (`created -> starting -> running -> stopping -> stopped`) и закрыть
  гонки `start/stop/restart` на Windows.
- [ ] Устранить дубли модели состояния записи:
  `gui.models.recording_state` -> единый источник истины в `core`.
- [ ] Ввести транзакционное обновление конфигурации:
  `load -> validate -> apply -> persist` без частичных записей.
- [ ] Провести контрактный рефакторинг API ошибок:
  единый формат, стабильные `error.code`, без смешения `data/error`.
- [ ] Закрыть технический долг по типизации для рефакторинга:
  добавить strict-проверку `mypy` для модулей, затронутых в этом релизе.
- [ ] Добавить «защитные» тесты рефакторинга:
  snapshot/contract tests для API и интеграционные smoke-тесты lifecycle.

## P1 (важно, если успеваем до code freeze)

- [ ] Вынести слой сервисов для FFmpeg-пайплайна:
  отдельные `ProcessSupervisor`, `FinalizeService`, `RecoveryPolicy`.
- [ ] Зафиксировать детерминированный shutdown потоков/процессов записи:
  единый протокол `stop -> join(timeout) -> force cleanup`.
- [ ] Протащить `request_id/trace_id` в фоновые API-операции
  и связанные бизнес-логи для end-to-end корреляции.
- [ ] Вынести request lifecycle middleware (`before/after_request`)
  в отдельный слой, отделив от bootstrap-кода `APIServer`.

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
