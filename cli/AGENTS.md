<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-05-07 -->

# cli/

## Purpose
CLI-интерфейс приложения. Разбирает аргументы командной строки, поддерживает управление записью без GUI (`--start`, `--stop`, `--status`), планировщиком (`schedule` подкоманды) и режим headless. Точка входа — `main.py`, который использует `cli/parser.py`.

## Key Files

| Файл | Описание |
|------|----------|
| `parser.py` | `create_parser()` — argparse парсер со всеми CLI-аргументами и подкомандами |
| `scheduler.py` | CLI-команды для работы с планировщиком (list/add/delete/enable/disable задач) |
| `templates.py` | Шаблоны вывода CLI: форматирование статуса, списков записей, задач планировщика |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Все аргументы документированы в `parser.py` с примерами (epilog).
- При добавлении новых CLI-команд: добавь аргументы в `parser.py`, обработку в `main.py`.
- `templates.py` — только форматирование, без бизнес-логики.
- CLI в headless-режиме (`--headless`) запускает только API сервер без GUI.

### Testing Requirements
- `tests/unit/test_cli_parser.py` — тесты парсера аргументов
- `tests/unit/test_cli_scheduler.py` — тесты CLI команд планировщика
- Запуск: `uv run pytest tests/unit/test_cli_parser.py tests/unit/test_cli_scheduler.py`

### Common Patterns
```bash
# Режимы запуска
uv run python main.py --gui           # GUI (по умолчанию)
uv run python main.py --headless      # только API
uv run python main.py --start         # начать запись
uv run python main.py --stop          # остановить
uv run python main.py --status        # статус

# Параметры записи
uv run python main.py --start --area rect --rect 0 0 1920 1080
uv run python main.py --start --fps 60 --audio mic --duration 120
```

## Dependencies

### Internal
- `logger_config.py` — логирование
- `core/application_facade.py` — выполнение команд (через `main.py`)

### External
- `argparse` — стандартная библиотека
- `importlib.metadata` — получение версии пакета

<!-- MANUAL: -->
