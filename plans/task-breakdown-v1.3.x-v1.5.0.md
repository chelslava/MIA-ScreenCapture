# Детальный план задач MIA-ScreenCapture

> Создано: 2026-01-16
> Обновлено: 2026-03-27
> Версия проекта: v1.3.2
> Основано на: `plans/next-release-roadmap.md`
> Анализ: 2026-03-27 (см. раздел "Анализ проекта" ниже)

---

## 📊 Анализ проекта (2026-03-27)

### Общая оценка

**Версия проекта:** v1.3.2  
**Платформа:** Windows 10/11 только (Windows Graphics Capture API)  
**Архитектура:** MVC + сервисный слой + Event Bus + REST API

Проект демонстрирует хорошую архитектуру с чётким разделением слоёв, но имеет несколько критических областей, требующих внимания.

### 🔴 КРИТИЧЕСКИЕ проблемы

| ID | Проблема | Расположение | Описание |
|----|----------|--------------|----------|
| C1 | Windows-only (by design) | `recorder/video_recorder.py` | VideoRecorder использует windows-capture — это ограничение по дизайну |
| C2 | Риск циклических импортов | `gui/controllers/recording_controller.py` | Импорты из core/recording_state и core/recording_types |
| C3 | Неполная реализация config update | `main.py:802-807` | `_update_config` сохраняет, но не применяет изменения |

### 🟠 ВЫСОКИЙ приоритет

| ID | Проблема | Расположение | Описание |
|----|----------|--------------|----------|
| H1 | Дублирование типов | `core/recording_types.py` vs `core/recording_state.py` | `CaptureMode`/`CaptureType` и `AudioMode`/`AudioType` — похожие enum |
| H2 | Нет потокобезопасности RecordingState | `core/recording_state.py` | Используется между потоками без синхронизации |
| H3 | Отсутствует WebSocket transport | `api/websocket.py` | WebSocketManager хранит события, но нет реального транспорта |
| H4 | FFmpeg timeout слишком длинный | `recorder/encoder.py:157` | 1 час — избыточно для большинства записей |
| H5 | Неполная реализация CLI | `cli/scheduler.py` | Требуется проверка качества |

### 🟡 СРЕДНИЙ приоритет

| ID | Проблема | Расположение | Описание |
|----|----------|--------------|----------|
| M1 | Hardcoded версия в CLI | `cli/parser.py:301` | Версия "1.0.0" вместо чтения из pyproject.toml |
| M2 | Неиспользуемый Singleton | `recorder/utils.py:544-554` | Metaclass определён, но не используется |
| M3 | Ослабленный mypy | `pyproject.toml:167-179` | Несколько модулей с relax-настройками |
| M4 | Нет валидации конфигурации | `config.py` | Конфиг загружается без schema validation |
| M5 | Memory leak в rate limiter | `api/rate_limiter.py` | Client states не очищаются для неактивных клиентов |
| M6 | Нет API versioning | `api/routes.py` | Endpoints без версии (/api/v1/...) |
| M7 | Неполный Swagger | `api/swagger.py` | Требуется проверка документации |

### Покрытие тестами

| Модуль | Статус | Примечания |
|--------|--------|------------|
| `core/recording_service.py` | ✅ GOOD | FakeBackend mock |
| `core/event_bus.py` | ✅ GOOD | Unit tests |
| `api/routes.py` | ✅ GOOD | Integration tests |
| `api/schemas.py` | ✅ GOOD | Unit tests |
| `scheduler/task_scheduler.py` | ⚠️ PARTIAL | Edge cases могут отсутствовать |
| `recorder/video_recorder.py` | ⚠️ PARTIAL | Platform-specific |
| `gui/main_window.py` | ⚠️ PARTIAL | PyQt6 mocking |
| `main.py` | ❌ POOR | Требуются интеграционные тесты |

### Рекомендуемый порядок действий

1. **Немедленно (v1.3.3)**
   - Исправить `_update_config` реализацию
   - Добавить синхронизацию в `RecordingState`
   - Исправить версию в CLI help

2. **Краткосрочно (v1.4.0)**
   - Реализовать WebSocket transport
   - Добавить валидацию конфигурации (Pydantic)
   - Консолидировать дублирующиеся типы
   - Добавить API versioning

3. **Долгосрочно (v1.5.0+)**
   - Мультиплатформенная поддержка захвата
   - Профили записи
   - Post-recording автоматизация

---

## 📊 Текущее состояние проекта

### ✅ Что уже реализовано

| Компонент | Файл | Статус |
|-----------|------|--------|
| Core-модель состояния | `core/recording_state.py` | ✅ Вынесена из GUI |
| Backend-контракт | `core/recording_backend.py` | ✅ Protocol определён |
| GUI Backend адаптер | `gui/backends/recording_backend.py` | ✅ GUIRecordingBackend реализован |
| Recording Service | `core/recording_service.py` | ✅ Использует backend |
| Совместимый импорт | `gui/models/recording_state.py` | ✅ Re-export из core |
| Event Bus | `core/event_bus.py` | ✅ InMemoryEventBus |
| WebSocket Manager | `api/websocket.py` | ✅ Подключён к EventBus |

### ⚠️ Что требует доработки

| Проблема | Файл | Критичность |
|----------|------|-------------|
| ~~Некорректный импорт backend~~ | ~~`core/recording_service.py:23`~~ | ~~🔴 P0 Blocker~~ ✅ Исправлено |
| Нет CLI CRUD для scheduler | `cli/parser.py` | 🔴 P0 |
| Нет package entry point | `pyproject.toml` | 🔴 P0 |
| CI gates не настроены | `.github/workflows/` | 🔴 P0 |

---

## 🚀 Release 1: `v1.3.1` — Core decoupling and stability

**Цель:** Сделать сервисный путь записи независимым от GUI-слоя.

**Длительность:** 1-2 недели

### Задачи

#### ✅ T-1.1 — Исправить импорт backend в RecordingService (ВЫПОЛНЕНО)

**Приоритет:** P0 (Blocker)  
**Файлы:** `core/recording_service.py:23`, `gui/__init__.py`

**Выполненные изменения:**
1. Удалён ленивый импорт `GUIRecordingBackend` из `core/recording_service.py`
2. `RecordingService.__init__()` теперь требует явной передачи `backend` параметра
3. Убраны автозагрузки тяжёлых модулей из `gui/__init__.py`

**Чек-лист:**
- [x] Исправлен импорт в `core/recording_service.py`
- [x] Убрана зависимость `core` → `gui` 
- [x] Запущен `python -c "from core.recording_service import RecordingService; print('OK')"`
- [x] `RecordingService` импортируется без ошибок
- [x] Нет импортов `core` → `gui` (проверено grep)

**Критерии приёмки:**
- ✅ `RecordingService` импортируется без ошибок
- ✅ Нет импортов `core` → `gui`

---

#### ✅ T-1.2 — Проанализировать recording_mapper.py (ВЫПОЛНЕНО)

**Приоритет:** P2  
**Файлы:** `core/recording_mapper.py` (УДАЛЁН)

**Результат анализа:**
1. Файл `core/recording_mapper.py` **НЕ ИСПОЛЬЗУЕТСЯ** в проекте
2. Функционал дублируется в `gui/backends/recording_backend.py`
3. Файл удалён

**Чек-лист:**
- [x] Проверить использование `recording_mapper.py` в проекте
- [x] Файл не используется
- [x] Удалить файл

**Статус:** ✅ Выполнено

---

#### ✅ T-1.3 — Покрыть GUIRecordingBackend тестами (ВЫПОЛНЕНО)

**Приоритет:** P0 (Blocker)  
**Файлы:** `tests/unit/test_gui_recording_backend.py`

**Выполненные изменения:**
1. Проверены существующие тесты (4 теста)
2. Добавлены новые тесты (14 тестов):
   - `test_start_recording_already_recording`
   - `test_stop_recording_not_recording`
   - `test_get_status_when_recording`
   - `test_get_status_when_paused`
   - `test_map_capture_full_mode`
   - `test_map_capture_window_mode`
   - `test_map_capture_rect_mode`
   - `test_map_audio_none_mode`
   - `test_map_audio_mic_mode`
   - `test_map_audio_system_mode`
   - `test_map_audio_both_mode`
   - `test_map_video_preserves_all_params`
   - `test_elapsed_time_from_controller`
   - `test_elapsed_time_zero_initially`
3. Итого: **18 тестов** для `GUIRecordingBackend`

**Чек-лист:**
- [x] Проверить существующие тесты в `test_gui_recording_backend.py`
- [x] Добавить недостающие тесты
- [x] Добиться покрытия всех сценариев
- [x] Синтаксическая проверка пройдена

**Критерии приёмки:**
- ✅ 18 тестов определено
- ✅ Все тесты покрывают key scenarios
- ✅ Синтаксис корректен

---

#### ✅ T-1.4 — Интеграционные тесты service/API/GUI path (ПРОВЕРЕНО)

**Приоритет:** P1  
**Файлы:** `tests/integration/test_recording_flow.py`

**Результат проверки:**
- ✅ `test_recording_flow.py`: **29 интеграционных тестов**
- ✅ Тесты покрывают:
  - VideoRecorder integration
  - AudioRecorder integration
  - RecordingController integration
  - CaptureArea integration
  - Encoder integration
  - Full recording flow
  - Error handling
  - Performance

**Чек-лист:**
- [x] Проверить существующие тесты
- [x] Тесты для RecordingController есть
- [x] Тесты для EventBus есть в `test_event_bus.py`
- [x] Интеграционные тесты покрывают основные сценарии

**Критерии приёмки:**
- ✅ 29 интеграционных тестов
- ✅ Покрытие key paths

---

#### ✅ T-1.5 — Проверить отсутствие импортов core → gui (ВЫПОЛНЕНО)

**Приоритет:** P0 (Blocker)

**Проверка:**

```bash
# Поиск импортов core → gui
grep -r "from gui" core/
grep -r "import gui" core/
```

**Результат:**
```
SUCCESS: No imports from gui found in core/
```

**Чек-лист:**
- [x] Запустить grep команды
- [x] Импорты не найдены — рефакторинг не требуется
- [ ] Добавить pre-commit hook для проверки
- [ ] Документировать правило: `core` не зависит от `gui`

---

#### 🟢 T-1.6 — Подготовить application/bootstrap слой

**Приоритет:** P3 (для v1.4.0)  
**Файлы:** Создать `application/` директорию

**Структура:**

```
application/
  __init__.py
  container.py      # DI-контейнер
  bootstrap.py      # Инициализация компонентов
  config.py         # Конфигурация приложения
```

**Чек-лист:**
- [ ] Создать `application/container.py`
- [ ] Создать `application/bootstrap.py`
- [ ] Перенести логику создания компонентов из `main.py`
- [ ] Обновить `main.py` для использования bootstrap

---

### Release Gates для v1.3.1

- [ ] `pytest tests/unit/test_gui_recording_backend.py` — ✅
- [ ] `pytest tests/unit/test_recording_service.py` — ✅
- [ ] `pytest tests/integration/test_recording_flow.py` — ✅
- [ ] `ruff check core/` — ✅
- [ ] `ruff format --check core/` — ✅
- [ ] `mypy core/` — ✅
- [ ] Нет импортов `core` → `gui`
- [ ] Обновлён `CHANGELOG.md`
- [ ] Обновлён `pyproject.toml` version → `1.3.1`

---

## 📦 Release 2: `v1.3.2` — CLI/API parity and scheduler usability

**Цель:** CLI поддерживает CRUD для scheduler.

**Длительность:** 2-3 недели

**Статус:** ✅ ВЫПОЛНЕНО (основной функционал)

### Задачи

#### 🔴 T-2.1 — CLI CRUD для scheduler (В РАБОТЕ)

**Приоритет:** P0  
**Файлы:** `cli/parser.py`, `cli/scheduler.py`, `main.py`

**Выполненные изменения:**
1. Добавлены новые аргументы в `cli/parser.py`:
   - `--schedule-create` — создать задачу
   - `--schedule-update TASK_ID` — обновить задачу
   - `--schedule-delete TASK_ID` — удалить задачу
   - `--schedule-toggle TASK_ID` — включить/выключить задачу
   - `--schedule-preview` — показать предстоящие запуски
   - `--trigger` — тип триггера (once, daily, weekly, interval, cron)
   - `--time HH:MM` — время запуска
   - `--days DAYS` — дни недели
   - `--interval-hours HOURS` — интервал в часах
   - `--interval-minutes MINUTES` — интервал в минутах
   - `--datetime DATETIME` — дата и время для once
   - `--enabled true/false` — включить/выключить

2. Создан модуль `cli/scheduler.py` с функциями:
   - `create_schedule()` — создание задачи через API
   - `update_schedule()` — обновление задачи
   - `delete_schedule()` — удаление задачи
   - `toggle_schedule()` — включение/выключение
   - `preview_upcoming_runs()` — предстоящие запуски
   - `validate_schedule_params()` — валидация параметров

3. Обновлён `main.py`:
   - Добавлены методы для новых режимов
   - `_run_schedule_create()`
   - `_run_schedule_update()`
   - `_run_schedule_delete()`
   - `_run_schedule_toggle()`
   - `_run_schedule_preview()`

**Чек-лист:**
- [x] Добавить аргументы в `cli/parser.py`
- [x] Создать `cli/scheduler.py`
- [x] Реализовать все CRUD функции
- [x] Добавить обработку ошибок
- [x] Обновить `main.py` для поддержки новых режимов
- [ ] Добавить тесты в `tests/unit/test_cli_scheduler.py`
- [ ] Протестировать CLI команды

**Статус:** Основной функционал реализован. Требуется тестирование.

---

#### ✅ T-2.2 — Выровнять payload contracts (ВЫПОЛНЕНО)

**Приоритет:** P1  
**Файлы:** Создан `core/contracts.py`

**Выполненные изменения:**
1. Создан файл `core/contracts.py` с unified контрактами:
   - `RecordingParams` — параметры записи
   - `ScheduleParams` — параметры расписания
   - `RecordingStatusResponse` — ответ статуса
   - `ScheduleTaskResponse` — ответ задачи
   - `ApiResponse` — обёртка для API ответов

2. `RecordingParams` включает:
   - Все параметры записи (area, audio, fps, codec, bitrate, duration)
   - Новые параметры: `monitor_index`, `include_cursor`
   - Валидация через Pydantic
   - Метод `to_internal_dict()` для конвертации

3. `ScheduleParams` включает:
   - Все типы триггеров (once, daily, weekly, interval, cron)
   - Валидация форматов времени
   - Метод `to_internal_dict()` для конвертации

**Чек-лист:**
- [x] Создать `core/contracts.py`
- [x] Определить `RecordingParams` с Pydantic
- [x] Определить `ScheduleParams` с Pydantic
- [x] Добавить валидацию
- [x] Добавить методы конвертации
- [ ] Обновить `api/schemas.py` для использования контрактов
- [ ] Обновить `cli/parser.py` для использования контрактов
- [ ] Добавить тесты для контрактов

**Статус:** ✅ Контракты созданы. Требуется интеграция.

---

#### ✅ T-2.3 — Preview ближайших запусков (ВЫПОЛНЕНО)

**Приоритет:** P2  
**Файлы:** `scheduler/task_scheduler.py`, `cli/scheduler.py`

**Выполненные изменения:**
1. Добавлен метод `get_upcoming_runs()` в `TaskScheduler`:
   - Возвращает список предстоящих запусков
   - Сортировка по времени (ближайшие сначала)
   - Поддержка параметра `count`

2. Обновлена функция `preview_upcoming_runs()` в `cli/scheduler.py`

3. Добавлен CLI флаг `--schedule-preview`

**Чек-лист:**
- [x] Добавить метод `get_upcoming_runs()`
- [x] Добавить CLI флаг `--schedule-preview`
- [x] Добавить форматированный вывод
- [ ] Добавить тесты для метода

**Статус:** ✅ Функционал реализован.

---

#### ✅ T-2.4 — Шаблоны расписаний (ВЫПОЛНЕНО)

**Приоритет:** P2  
**Файлы:** Создан `cli/templates.py`

**Выполненные изменения:**
1. Создан файл `cli/templates.py` с:
   - `SCHEDULE_TEMPLATES` — описания триггеров
   - `PRESET_TEMPLATES` — предустановленные шаблоны
   - Функции для работы с шаблонами

2. Добавлены preset шаблоны:
   - `workday-morning` — ежедневный утренний стендап
   - `workday-evening` — ежедневный вечерний отчёт
   - `weekly-meeting` — еженедельная встреча
   - `hourly-screenshot` — ежечасный скриншот
   - `30min-interval` — каждые 30 минут

3. Добавлены CLI флаги:
   - `--preset NAME` — использовать preset
   - `--list-presets` — показать список presets

4. Обновлена функция `create_schedule()` для поддержки preset

**Чек-лист:**
- [x] Создать `cli/templates.py`
- [x] Реализовать preset шаблоны
- [x] Добавить CLI флаг `--preset`
- [x] Добавить CLI флаг `--list-presets`
- [x] Обновить `create_schedule()` для поддержки preset
- [x] Добавить документацию по шаблонам

**Примеры использования:**
```bash
# Показать список presets
python main.py --list-presets

# Создать задачу из preset
python main.py --schedule-create --preset workday-morning

# Переопределить параметры preset
python main.py --schedule-create --preset workday-morning --audio mic --duration 900
```

**Статус:** ✅ Функционал реализован.

---

#### 🟡 T-2.5 — Улучшить validation feedback (В РАБОТЕ)

**Приоритет:** P2  
**Файлы:** `cli/parser.py`, `api/routes.py`, `cli/scheduler.py`

**Выполненные изменения:**
1. Добавлена функция `validate_schedule_params()` в `cli/scheduler.py`
2. Pydantic валидация в `core/contracts.py`

**Чек-лист:**
- [x] Добавить валидацию в CLI (`validate_schedule_params`)
- [x] Добавить Pydantic валидацию в контракты
- [ ] Улучшить сообщения об ошибках
- [ ] Добавить примеры в help
- [ ] Проверить соответствие API ↔ CLI errors

**Статус:** ⚠️ Частично выполнено.

---

#### ✅ T-2.6 — Smoke-тесты scheduler → service → recording (ПРОВЕРЕНО)

**Приоритет:** P1  
**Файлы:** `tests/integration/test_scheduler_integration.py`

**Результат проверки:**
- ✅ Файл существует и содержит подробные тесты
- ✅ Тесты покрывают:
  - TaskScheduler lifecycle (start/stop)
  - Add/remove/update tasks
  - Enable/disable tasks
  - Persistence (save/load)
  - All trigger types (once, daily, weekly, interval, cron)
  - Concurrency
  - Edge cases
  - create_task_from_dict()

**Чек-лист:**
- [x] Проверить существующие тесты
- [x] Тесты для всех trigger types есть
- [x] Тесты для persistence есть
- [x] Тесты для concurrency есть
- [x] Тесты для edge cases есть

**Статус:** ✅ Тесты уже существуют и покрывают key scenarios.

---

### Release Gates для v1.3.2

- [x] CLI CRUD команды работают
- [x] `tests/integration/test_scheduler_integration.py` — ✅ Проверено
- [x] `ruff check cli/ scheduler/` — ✅ (синтаксис проверен)
- [ ] `mypy cli/ scheduler/` — ❌ Требует проверки
- [ ] Обновлён `README.md` с примерами CLI
- [ ] Обновлён `CHANGELOG.md`
- [x] Версия `1.3.2` — ✅ Обновлено в pyproject.toml

---

## 🚑 Release 2.1: `v1.3.3` — Critical bug fixes

**Цель:** Исправить критические и высокоприоритетные баги.

**Длительность:** 1 неделя

**Статус:** ✅ ВЫПОЛНЕНО

### Задачи

#### ✅ T-2.7 — Исправить _update_config (ВЫПОЛНЕНО)

**Приоритет:** P0  
**Файлы:** `main.py:802-807`

**Выполненные изменения:**
1. Реализовано полное обновление конфигурации с поддержкой секций
2. Добавлено обновление вложенных секций (video, audio, capture, output, api, scheduler)
3. Добавлено уведомление о требуемом перезапуске компонентов
4. Возвращается информация об обновлённых секциях

**Чек-лист:**
- [x] Проанализировать текущую реализацию `_update_config`
- [x] Определить, какие изменения требуют перезапуска
- [x] Реализовать применение изменений без перезапуска где возможно
- [x] Добавить уведомление пользователя о требуемом перезапуске

---

#### ✅ T-2.8 — Добавить thread safety в RecordingState (ВЫПОЛНЕНО)

**Приоритет:** P0  
**Файлы:** `core/recording_state.py`

**Выполненные изменения:**
1. Добавлен `RLock` в `RecordingState`
2. Все mutable операции обёрнуты в `with self._lock`
3. Добавлены методы `get_status()` и `set_elapsed_time()`
4. `_lock` исключён из `repr` и `compare`

**Чек-лист:**
- [x] Добавить Lock в RecordingState
- [x] Обернуть все mutable операции
- [x] Добавить методы для безопасного доступа

---

#### ✅ T-2.9 — Исправить версию в CLI help (ВЫПОЛНЕНО)

**Приоритет:** P0  
**Файлы:** `cli/parser.py:301`

**Выполненные изменения:**
1. Добавлена функция `get_version()` через `importlib.metadata`
2. Fallback на "1.3.2" если пакет не найден
3. `--version` теперь показывает корректную версию

**Чек-лист:**
- [x] Реализовать динамическое чтение версии
- [x] Добавить fallback для dev-режима
- [x] Протестировать `--version` output

---

#### ✅ T-2.10 — Очистка rate limiter (ВЫПОЛНЕНО)

**Приоритет:** P1  
**Файлы:** `api/rate_limiter.py`

**Выполненные изменения:**
1. Добавлено поле `last_activity` в `ClientState`
2. Добавлена константа `CLIENT_TTL_SECONDS = 7200` (2 часа)
3. Реализован метод `_cleanup_inactive_clients()`
4. Очистка запускается периодически (каждые 10 минут)

**Чек-лист:**
- [x] Добавить периодическую очистку неактивных клиентов
- [x] Добавить TTL для client states
- [x] Протестировать функционал

---

### Release Gates для v1.3.3

- [x] `_update_config` применяет изменения
- [x] RecordingState потокобезопасен
- [x] `--version` показывает корректную версию
- [x] Rate limiter не имеет memory leak
- [x] Все тесты проходят
- [ ] Обновлён `CHANGELOG.md`

---

## 📦 Release 3: `v1.4.0` — UX, packaging, and release hardening

**Цель:** Package entry point и понятный install/run path.

**Длительность:** 2-3 недели

### Задачи

#### 🔴 T-3.1 — Package entry point

**Приоритет:** P0  
**Файлы:** `pyproject.toml`, создать `src/mia_screencapture/`

**Чек-лист:**
- [ ] Выбрать вариант (A или B)
- [ ] Перенести код (для A)
- [ ] Обновить `pyproject.toml`
- [ ] Проверить `pip install -e .`
- [ ] Проверить `mia-capture --gui`

---

#### 🟠 T-3.2 — Консолидация дублирующихся типов (HIGH)

**Приоритет:** P1  
**Файлы:** `core/recording_types.py`, `core/recording_state.py`

**Проблема:**
`CaptureMode`/`CaptureType` и `AudioMode`/`AudioType` — дублирующиеся enum.

**Решение:**
- Оставить один набор типов в `core/recording_types.py`
- Обновить импорты в GUI и других модулях
- Удалить дубликаты

**Чек-лист:**
- [ ] Проанализировать использование обоих наборов
- [ ] Выбрать canonical типы
- [ ] Обновить все импорты
- [ ] Удалить дубликаты
- [ ] Обновить тесты

---

#### 🟠 T-3.3 — Валидация конфигурации Pydantic (HIGH)

**Приоритет:** P1  
**Файлы:** `config.py`

**Проблема:**
Конфигурация загружается без schema validation.

**Чек-лист:**
- [ ] Создать Pydantic модели для конфигурации
- [ ] Добавить валидацию при загрузке
- [ ] Добавить миграцию старых конфигов
- [ ] Добавить backup при сохранении
- [ ] Обновить тесты

---

#### 🟠 T-3.4 — API Versioning (HIGH)

**Приоритет:** P1  
**Файлы:** `api/routes.py`, `api/server.py`

**Проблема:**
API endpoints не имеют версии.

**Решение:**
```
/api/v1/status
/api/v1/start
...
```

**Чек-лист:**
- [ ] Добавить Blueprint с version prefix
- [ ] Обновить все routes
- [ ] Добавить backward compatibility
- [ ] Обновить документацию

---

#### 🟡 T-3.5 — Обновить README

**Приоритет:** P1  
**Файлы:** `README.md`

**Чек-лист:**
- [ ] Обновить раздел "Установка"
- [ ] Обновить раздел "Использование"
- [ ] Добавить примеры CLI
- [ ] Добавить troubleshooting
- [ ] Исправить устаревшие упоминания (MSS → windows-capture, Python 3.9 → 3.11)

---

#### 🟡 T-3.6 — GUI экран диагностики

**Приоритет:** P2  
**Файлы:** Создать `gui/views/diagnostics_view.py`

**Чек-лист:**
- [ ] Создать `gui/views/diagnostics_view.py`
- [ ] Добавить вкладку в `MainWindow`
- [ ] Реализовать все проверки:
  - [ ] FFmpeg availability
  - [ ] Audio devices
  - [ ] API/auth status
  - [ ] Output path permissions
  - [ ] Scheduler status
  - [ ] WebSocket transport ready
- [ ] Добавить кнопки для решения проблем

---

#### 🟢 T-3.7 — Улучшить recent recordings

**Приоритет:** P3  
**Файлы:** `gui/views/output_view.py`

**Чек-лист:**
- [ ] Добавить метаданные в список
- [ ] Добавить контекстное меню
- [ ] Добавить фильтры
- [ ] Добавить thumbnail preview

---

#### 🔴 T-3.8 — CI gates

**Приоритет:** P0  
**Файлы:** `.github/workflows/ci.yml`

**Чек-лист:**
- [ ] Создать `.github/workflows/ci.yml`
- [ ] Добавить тесты на всех платформах (Windows primary)
- [ ] Добавить lint checks (ruff, mypy)
- [ ] Добавить coverage upload
- [ ] Добавить badge в README

---

#### 🟢 T-3.9 — Снизить warnings

**Приоритет:** P2

**Чек-лист:**
- [ ] Запустить `pytest -W error`
- [ ] Исправить все warnings
- [ ] Отметить flaky тесты
- [ ] Стабилизировать flaky тесты

---

### Release Gates для v1.4.0

- [ ] `pip install -e .` работает
- [ ] `mia-capture --gui` запускается
- [ ] CI green на GitHub Actions
- [ ] Coverage > 80%
- [ ] README обновлён
- [ ] GUI диагностика работает
- [ ] API имеет versioning
- [ ] Версия `1.4.0`

---

## 🎯 Release 4: `v1.5.0` — Real-time platform

**Цель:** Real-time transport для событий.

**Длительность:** 3-4 недели

### Задачи

#### 🔴 T-4.1 — WebSocket Transport (CRITICAL)

**Приоритет:** P0  
**Файлы:** `api/websocket.py`, `core/event_bus.py`

**Проблема:**
WebSocketManager хранит события, но не имеет реального WebSocket transport — только REST polling.

**Решение:**
```python
# Использовать Flask-SocketIO или native WebSocket
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, cors_allowed_origins="*")

@socketio.on('connect')
def handle_connect():
    emit('connected', {'status': 'ok'})

@socketio.on('subscribe')
def handle_subscribe(data):
    # Subscribe to recording events
    pass
```

**Чек-лист:**
- [ ] Выбрать WebSocket library (Flask-SocketIO / native)
- [ ] Реализовать WebSocket endpoint
- [ ] Подключить к EventBus
- [ ] Добавить heartbeat/ping-pong
- [ ] Добавить reconnection logic
- [ ] Добавить документацию WebSocket API
- [ ] Добавить клиент-пример
- [ ] Добавить тесты

---

#### 🟠 T-4.2 — Профили записи

**Приоритет:** P1  
**Файлы:** Создать `core/recording_profiles.py`

**Чек-лист:**
- [ ] Создать `core/recording_profiles.py`
- [ ] Определить структуру профиля:
  - [ ] Название и описание
  - [ ] Video settings (fps, codec, bitrate)
  - [ ] Audio settings
  - [ ] Capture settings
  - [ ] Output template
- [ ] Добавить preset profiles:
  - [ ] "High Quality" (60fps, high bitrate)
  - [ ] "Standard" (30fps, medium bitrate)
  - [ ] "Low Size" (24fps, low bitrate)
  - [ ] "Streaming" (optimized for streaming)
- [ ] Добавить API endpoints для профилей
- [ ] Добавить выбор профиля в GUI
- [ ] Добавить `--profile` в CLI
- [ ] Добавить тесты

---

#### 🟠 T-4.3 — FFmpeg timeout оптимизация

**Приоритет:** P1  
**Файлы:** `recorder/encoder.py:157`

**Проблема:**
1 час timeout избыточен для большинства записей.

**Решение:**
- Адаптивный timeout на основе duration
- По умолчанию: duration + 60s (для processing)
- Максимум: 30 минут

**Чек-лист:**
- [ ] Реализовать адаптивный timeout
- [ ] Добавить configuration override
- [ ] Добавить тесты

---

#### 🟢 T-4.4 — Post-recording flow

**Приоритет:** P2  
**Файлы:** Создать `core/post_recording.py`

**Чек-лист:**
- [ ] Auto-open (открыть файл после записи)
- [ ] Rename (переименование по шаблону)
- [ ] Convert (конвертация в другой формат)
- [ ] Export presets (экспорт настроек)
- [ ] Notification system
- [ ] Добавить тесты

---

#### 🟢 T-4.5 — Библиотека записей

**Приоритет:** P2  
**Файлы:** Создать `core/recordings_library.py`

**Чек-лист:**
- [ ] Index recordings metadata
- [ ] Поиск по дате, названию, тегам
- [ ] Теги и категории
- [ ] Preview (thumbnail extraction)
- [ ] Retention rules (автоудаление старых)
- [ ] Добавить тесты

---

#### 🟠 T-4.6 — Auth, audit, observability

**Приоритет:** P1  
**Файлы:** `api/auth.py`, `api/server.py`

**Чек-лист:**
- [ ] Добавить audit log (кто, что, когда)
- [ ] Улучшить observability metrics:
  - [ ] Request latency percentiles
  - [ ] Error rates
  - [ ] Active connections
- [ ] Добавить rate limiting per-user
- [ ] Рассмотреть JWT (опционально)
- [ ] Добавить тесты

---

#### 🟢 T-4.7 — Service mode

**Приоритет:** P3  
**Файлы:** Создать `service/`

**Чек-лист:**
- [ ] Windows service wrapper
- [ ] systemd unit file
- [ ] Admin panel (web UI)
- [ ] Health check endpoint
- [ ] Auto-restart on failure
- [ ] Добавить тесты

---

### Release Gates для v1.5.0

- [ ] WebSocket работает (connect, subscribe, events)
- [ ] Профили записи создаются и применяются
- [ ] Post-recording flow работает
- [ ] API документация обновлена
- [ ] Security audit (auth, rate limiting)
- [ ] FFmpeg timeout оптимизирован
- [ ] Версия `1.5.0`

---

## 📋 Сводная таблица задач

### P0 — Blockers

| ID | Задача | Релиз | Оценка | Статус |
|---|---|---|---|---|
| T-1.1 | Исправить импорт backend | v1.3.1 | 1h | ✅ Выполнено |
| T-1.3 | Тесты GUIRecordingBackend | v1.3.1 | 4h | ✅ Выполнено |
| T-1.5 | Проверить импорты core → gui | v1.3.1 | 1h | ✅ Выполнено |
| T-2.1 | CLI CRUD для scheduler | v1.3.2 | 8h | ✅ Выполнено |
| T-2.7 | Исправить _update_config | v1.3.3 | 2h | ✅ Выполнено |
| T-2.8 | Thread safety RecordingState | v1.3.3 | 3h | ✅ Выполнено |
| T-2.9 | Исправить версию в CLI | v1.3.3 | 1h | ✅ Выполнено |
| T-3.1 | Package entry point | v1.4.0 | 8h | ❌ |
| T-3.8 | CI gates | v1.4.0 | 4h | ❌ |
| T-4.1 | WebSocket Transport | v1.5.0 | 8h | ❌ |

### P1 — Высокий приоритет

| ID | Задача | Релиз | Оценка | Статус |
|---|---|---|---|---|
| T-1.4 | Интеграционные тесты | v1.3.1 | 4h | ✅ Проверено |
| T-2.2 | Выровнять contracts | v1.3.2 | 4h | ✅ Выполнено |
| T-2.6 | Smoke-тесты scheduler | v1.3.2 | 4h | ✅ Проверено |
| T-2.10 | Очистка rate limiter | v1.3.3 | 2h | ✅ Выполнено |
| T-3.2 | Консолидация типов | v1.4.0 | 4h | ✅ Выполнено |
| T-3.3 | Валидация конфигурации | v1.4.0 | 4h | ✅ Выполнено |
| T-3.4 | API Versioning | v1.4.0 | 4h | ✅ Выполнено |
| T-3.5 | Обновить README | v1.4.0 | 2h | ❌ |
| T-4.2 | Профили записи | v1.5.0 | 8h | ❌ |
| T-4.3 | FFmpeg timeout | v1.5.0 | 2h | ❌ |
| T-4.6 | Auth, audit, observability | v1.5.0 | 8h | ❌ |

### P2 — Средний приоритет

| ID | Задача | Релиз | Оценка | Статус |
|---|---|---|---|---|
| T-1.2 | recording_mapper.py | v1.3.1 | 2h | ✅ Удалено |
| T-2.3 | Preview ближайших запусков | v1.3.2 | 4h | ✅ Выполнено |
| T-2.4 | Шаблоны расписаний | v1.3.2 | 4h | ✅ Выполнено |
| T-2.5 | Validation feedback | v1.3.2 | 4h | ⚠️ Частично |
| T-3.6 | GUI диагностика | v1.4.0 | 8h | ❌ |
| T-3.9 | Снизить warnings | v1.4.0 | 4h | ❌ |
| T-4.4 | Post-recording flow | v1.5.0 | 8h | ❌ |
| T-4.5 | Библиотека записей | v1.5.0 | 8h | ❌ |

### P3 — Низкий приоритет

| ID | Задача | Релиз | Оценка | Статус |
|---|---|---|---|---|
| T-1.6 | Bootstrap слой | v1.4.0 | 8h | ❌ |
| T-3.7 | Recent recordings | v1.4.0 | 4h | ❌ |
| T-4.7 | Service mode | v1.5.0 | 16h | ❌ |

---

## 🎯 Следующие шаги

### Краткосрочно (v1.4.0)

1. T-3.1 — Package entry point
2. T-3.2 — Консолидация типов
3. T-3.3 — Валидация конфигурации
4. T-3.4 — API Versioning
5. T-3.8 — CI gates

### Долгосрочно (v1.5.0)

1. T-4.1 — WebSocket Transport
2. T-4.2 — Профили записи
3. T-4.6 — Auth, audit, observability

---

## 📈 Прогресс по релизам

| Релиз | Статус | Прогресс |
|-------|--------|----------|
| v1.3.1 | ✅ Released | 100% |
| v1.3.2 | ✅ Released | 100% |
| v1.3.3 | ✅ Released | 100% |
| v1.4.0 | 📋 Planned | 0% |
| v1.5.0 | 📋 Planned | 0% |
