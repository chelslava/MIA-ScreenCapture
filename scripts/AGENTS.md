<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-04-29 -->

# scripts/

## Purpose
Вспомогательные скрипты для разработки: smoke-тестирование API, проверка diff-покрытия тестами, публикация документации.

## Key Files

| Файл | Описание |
|------|----------|
| `api_smoke_run.py` | Smoke-тест: запускает API сервер и проверяет базовые endpoint'ы |
| `check_diff_coverage.py` | Проверяет, покрыты ли изменённые строки тестами (используется в CI) |
| `publish_github_wiki.ps1` | PowerShell скрипт публикации `docs/wiki/` на GitHub Wiki |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- `check_diff_coverage.py` используется в CI для контроля порога diff-покрытия.
- `api_smoke_run.py` запускается вручную для быстрой проверки API после изменений.
- PowerShell скрипт требует доступ к GitHub и настроенный remote.

### Testing Requirements
```bash
# Smoke-тест API
uv run python scripts/api_smoke_run.py

# Проверка diff-покрытия
uv run python scripts/check_diff_coverage.py
```

## Dependencies

### Internal
- `api/server.py` — smoke-тест запускает реальный API сервер

### External
- `requests` — HTTP-запросы в smoke-тесте
- PowerShell — для публикации wiki

<!-- MANUAL: -->
