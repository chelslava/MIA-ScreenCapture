<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# MIA-ScreenCapture

## Purpose
Профессиональный рекордер экрана для Windows 10/11 с поддержкой GUI (PyQt6), REST API (Flask), CLI и планировщика задач. Использует Windows Graphics Capture API для захвата видео и APScheduler для задач по расписанию.

## Subdirectories

| Директория | Назначение |
|-----------|---------|
| `api/` | REST API сервер: Flask routes, аутентификация, WebSocket, Swagger (см. `api/AGENTS.md`) |
| `core/` | Доменное ядро: бизнес-логика, event bus, lifecycle, DI-контейнер (см. `core/AGENTS.md`) |
| `gui/` | PyQt6 GUI: MVC (views/controllers/models), трей, горячие клавиши, бэкенды записи, темы (см. `gui/AGENTS.md`) |
| `recorder/` | Физический захват: видео (WGC API), аудио (sounddevice), FFmpeg кодирование (см. `recorder/AGENTS.md`) |
| `scheduler/` | Планировщик записей на APScheduler: разовые/ежедневные/cron задачи (см. `scheduler/AGENTS.md`) |
| `cli/` | CLI интерфейс: argparse парсер, команды запуска/остановки (см. `cli/AGENTS.md`) |
| `app_runtime/` | Runtime координаторы: связующий слой между core и GUI/API (см. `app_runtime/AGENTS.md`) |
| `config/` | JSON-файлы конфигурации: `config.json`, `tasks.json` |
| `tests/` | Тесты: 65+ unit + 10 интеграционных (см. `tests/AGENTS.md`) |
| `docs/` | Документация GitHub Wiki (см. `docs/AGENTS.md`) |
| `scripts/` | Утилиты разработки: smoke-тест API, diff-coverage (см. `scripts/AGENTS.md`) |
| `plans/` | Планы разработки и дорожные карты |

## Key Files

| Файл | Описание |
|------|----------|
| `main.py` | Точка входа: разбор CLI, инициализация GUI или headless режима |
| `config.py` | Dataclass-конфигурация приложения, чтение/запись `config/config.json` |
| `exceptions.py` | Иерархия исключений: `MIAError`, `RecordingError`, `ConfigurationError` и др. |
| `logger_config.py` | Централизованная настройка логирования: `get_module_logger(__name__)` |
| `pyproject.toml` | Метаданные проекта, зависимости (управляются через UV) |

---

# Guidelines for Python Development in MIA-ScreenCapture

## Общие принципы
- Код пишется на **Python 3.11+** (проект требует 3.11 и выше).
- **Платформа: Windows 10/11 только** — проект использует Windows Graphics Capture API через библиотеку `windows-capture`.
- Следуй принципам чистого кода: осмысленные имена, единственная ответственность функции, отсутствие дублирования.
- Все комментарии, docstring и сообщения коммитов пиши на **русском языке**. Комментарии объясняют «почему», а не «что» (последнее должно быть очевидно из кода).

## Стиль кода и форматирование
- Строго соблюдай **PEP 8**: отступы — 4 пробела, максимальная длина строки — 79 символов (для docstring и комментариев — 72).
- Для автоматического форматирования используй **ruff** (или **black**). Настрой форматирование в редакторе «на сохранение».
- Импорты группируй и сортируй: сначала стандартная библиотека, затем сторонние пакеты, потом локальные модули. Каждая группа отделяется пустой строкой. Используй **ruff** для автоматической сортировки.
- Не оставляй закомментированный код — удаляй его сразу.

## Именование
- Переменные, функции, методы, модули — `snake_case`.
- Классы, исключения, type aliases — `CamelCase`.
- Константы (значения, не изменяемые во время работы программы) — `UPPER_CASE`.
- «Приватные» атрибуты и методы (внутренняя реализация) начинай с одного подчёркивания: `_internal`.
- Сигналы Qt — `snake_case` (например, `recording_started`).

## Типизация (type hints)
- Все функции должны иметь аннотации типов для аргументов и возвращаемого значения. Исключение — очень короткие скрипты.
- Для опциональных значений используй `T | None` (Python 3.10+).
- Для сложных типов создавай type aliases (`MyType = list[dict[str, int]]`).
- Используй `Final` для констант, если это улучшает читаемость.
- Всегда проверяй типы с помощью **mypy** в строгом режиме (проект имеет некоторые ослабленные настройки для legacy модулей, но стремись к полному покрытию).

## Работа с данными
- Для форматирования строк всегда используй f-строки (вместо `%` или `.format()`).
- Для конкатенации большого количества строк применяй `str.join()`, избегай многократного `+=`.
- Для преобразования коллекций отдавай предпочтение list comprehensions и генераторам перед `map`/`filter`, если они не ухудшают читаемость.
- Избегай «магических чисел»: выноси числовые литералы в именованные константы.
- Для работы с датами и временем всегда используй модуль `datetime`, не занимайся ручными расчётами.
- При работе с файлами, сетевыми соединениями и другими ресурсами обязательно применяй контекстные менеджеры (`with`).
- Не храни секреты (пароли, токены) в коде. Используй переменные окружения или специальные инструменты (например, `.env` с `python-dotenv`).

## Обработка ошибок
- Обрабатывай исключения точечно: `except SpecificError as e:`. Избегай голого `except:`.
- Не подавляй исключения без необходимости. Если блок `except` пустой — это почти всегда ошибка.
- Создавай собственные классы исключений, если это помогает лучше передать смысл ошибки. В проекте используется иерархия из `exceptions.py`:
  - Базовый класс `MIAError`.
  - `RecordingError`, `RecordingStateError`, `ConfigurationError` и другие.
- Для логирования ошибок используй модуль `logging`, а не `print`. Настраивай уровни логирования.

## Современные возможности Python (3.10+)
- Для ветвления по типу или значению используй `match`/`case` (структурное сопоставление с образцом).
- Для объединения типов применяй синтаксис `X | Y` (например, `int | None`).
- Оператор `:=` (walrus) допускается только в тех местах, где он действительно улучшает читаемость, и не должен быть нагромождён.
- Для создания перечислений используй `enum.Enum` или `enum.StrEnum` (Python 3.11+).

## Импорты и структура проекта
- Избегай циклических импортов — проектируй модули так, чтобы зависимости были направлены в одну сторону.
- Внутри пакета используй относительные импорты (`.module`) для соседних модулей.
- Для управления проектом, виртуальным окружением и зависимостями используй **UV**.
- Все зависимости фиксируй в `pyproject.toml` или `requirements.txt` с указанием точных версий (или диапазонов, если это библиотека).

### Структура проекта MIA-ScreenCapture
```
api/           REST API (Flask routes, schemas, auth, websocket)
cli/           Command-line interface parser and scheduler commands
config.py      Configuration management with dataclasses
core/          Domain logic (event bus, recording service, types)
exceptions.py  Custom exception hierarchy
gui/           PyQt6 UI (views, controllers, models, backends)
logger_config.py  Logging configuration
main.py        Entry point
recorder/      Screen capture, audio recording, FFmpeg encoding
scheduler/     APScheduler task management
tests/
  unit/        Unit tests (mocked dependencies)
  integration/ Integration tests
  conftest.py  Shared fixtures and PyQt6 mocks
```

## Документирование
- Все публичные функции, классы и методы должны иметь docstring. Описывай назначение, аргументы (с типами), возвращаемое значение и возможные исключения.
- Используй единый стиль docstring (например, **Google style** или **reStructuredText**). Пример для Google style:
  ```python
  def add(a: int, b: int) -> int:
      """Складывает два числа.

      Args:
          a: Первое слагаемое.
          b: Второе слагаемое.

      Returns:
          Сумма a и b.
      """
      return a + b
  ```

## Инструменты и окружение
- Перед коммитом обязательно проверяй код с помощью **ruff** (линтер и форматтер) и **mypy** (проверка типов).
- Настрой **pre-commit** хуки, чтобы эти проверки выполнялись автоматически.
- Для тестов используй **pytest** (или **unittest**). Пиши хотя бы базовые тесты для ключевой логики.
- В тестах применяй параметризацию, фикстуры и моки (pytest-mock) для изоляции.
- Стремись к покрытию кода тестами (хотя бы 70–80% для важных модулей).

### Команды для работы с проектом (через uv)
```bash
# Установка зависимостей
uv sync                    # Все зависимости (включая dev)
uv sync --no-dev           # Только production

# Запуск тестов
uv run pytest                           # Все тесты
uv run pytest tests/unit/               # Только unit
uv run pytest tests/integration/        # Только интеграционные
uv run pytest tests/unit/test_config.py # Конкретный файл
uv run pytest --cov=. --cov-report=html # С покрытием

# Линтинг и форматирование
uv run ruff check .        # Проверка
uv run ruff format .       # Форматирование
uv run ruff check --fix .  # Автоисправление
uv run mypy .              # Проверка типов

# Запуск приложения
uv run python main.py      # GUI режим
uv run python main.py --headless  # Только API
```

## Контроль версий (Git)
- Сообщения коммитов пиши на русском языке.
- Следуй общепринятому формату: краткий заголовок (до 50 символов), затем пустая строка и развёрнутое описание (если нужно).
- Заголовок должен отвечать на вопрос «Что изменилось?» и начинаться с глагола в повелительном наклонении («Добавить», «Исправить», «Обновить»).
- Не коммить случайные файлы, используй `.gitignore`.
- Делай коммиты часто и логически завершёнными (одна задача — один коммит).

## Логирование
- Используй модуль `logging` через централизованную настройку из `logger_config.py`:
  ```python
  from logger_config import get_module_logger
  logger = get_module_logger(__name__)
  ```
- Уровни логирования:
  - `logger.info` — нормальные операции (запись начата, задача выполнена).
  - `logger.warning` — неожиданные ситуации, которые не нарушают работу.
  - `logger.error` — ошибки, требующие внимания.
  - `logger.debug` — детали для отладки.

## Тестирование
- **Юнит-тесты** — в `tests/unit/` (моки внешних зависимостей).
- **Интеграционные тесты** — в `tests/integration/` (взаимодействие с реальными компонентами).
- Используй фикстуры из `conftest.py` (`temp_dir`, `mock_config_manager` и др.).
- PyQt6 мокируется в `conftest.py` для headless тестирования.
- Имена тестовых классов: `Test<FeatureName>`.
- Имена тестовых методов: `test_<description>`.

### Пример теста
```python
class TestVideoSettings:
    def test_default_values(self):
        settings = VideoSettings()
        assert settings.fps == 30

    def test_custom_values(self):
        settings = VideoSettings(fps=60)
        assert settings.fps == 60
```

## Ключевые архитектурные паттерны проекта
1. **MVC в GUI**: Модели в `gui/models/`, Представления в `gui/views/`, Контроллеры в `gui/controllers/`.
2. **Шина событий**: Доменные события через `core/event_bus.py` для слабой связанности.
3. **Паттерн Backend**: `RecordingBackend` как протокол для абстракции между GUI и логикой записи.
4. **Внедрение зависимостей**: Сервисы получают зависимости через конструктор (`__init__`).
5. **Конфигурация**: Dataclasses в `config.py`, хранение в JSON-файле `config/config.json`.

## API и Pydantic
- Для REST API используй Flask и Pydantic-схемы (в `api/schemas.py`).
- Ответы API должны быть единообразными:
  ```python
  # Успех
  return jsonify({"success": True, "data": result})

  # Ошибка (используй _error_response)
  return _error_response(
      400,
      "validation_error",
      "Invalid parameters",
      details=[{"field": "fps", "message": "Must be 1-120"}]
  )
  ```
- Пример Pydantic-схемы:
  ```python
  from pydantic import BaseModel, Field, field_validator

  class StartRecordingRequest(BaseModel):
      area: Literal["full", "window", "rect"] = Field(default="full")
      fps: int = Field(default=30, ge=1, le=120)

      @field_validator("fps")
      @classmethod
      def validate_fps(cls, v: int) -> int:
          if v < 1:
              raise ValueError("fps must be positive")
          return v
  ```

## Код для GUI (PyQt6)
- Импортируй из `PyQt6.QtCore` и `PyQt6.QtWidgets`.
- Сигналы объявляй на уровне класса.
- Пример:
  ```python
  from PyQt6.QtCore import Qt, pyqtSignal
  from PyQt6.QtWidgets import QMainWindow, QVBoxLayout

  class MainWindow(QMainWindow):
      recording_started = pyqtSignal(str)
      error_occurred = pyqtSignal(str)

      def __init__(self, headless: bool = False):
          super().__init__()
          self._headless = headless
  ```

## Дополнительные требования
- **Платформа: Windows 10/11 только** — проект не поддерживает Linux/macOS.
- **FFmpeg** должен быть в PATH (используется для кодирования видео).
- Все секреты (токены, пароли) хранить в переменных окружения (`.env` с `python-dotenv`).
