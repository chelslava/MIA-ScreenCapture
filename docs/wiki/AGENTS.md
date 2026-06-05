<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-06-05 | Updated: 2026-06-05 -->

# docs/wiki/

## Purpose
Markdown-статьи GitHub Wiki проекта MIA-ScreenCapture. Документация ориентирована на пользователей и публикуется автоматически через `scripts/publish_github_wiki.ps1`.

## Key Files

| Файл | Описание |
|------|----------|
| `Home.md` | Главная страница Wiki: обзор проекта, навигация |
| `Installation.md` | Установка: требования, зависимости, FFmpeg, запуск |
| `Quick-Start.md` | Быстрый старт: первый запуск, базовые сценарии |
| `API.md` | REST API: все endpoint'ы, примеры curl, аутентификация |
| `CLI.md` | CLI-интерфейс: все флаги и подкоманды |
| `GUI.md` | GUI-руководство: описание вкладок и элементов интерфейса |
| `Scheduler.md` | Планировщик: типы расписаний, примеры настройки |
| `Configuration-and-Environment.md` | Конфигурация: `config.json`, переменные окружения, `.env` |
| `Logs-and-Diagnostics.md` | Логи и диагностика: расположение логов, уровни, диагностические endpoint'ы |
| `Troubleshooting.md` | Устранение неполадок: типичные ошибки и их решения |
| `Architecture.md` | Архитектурный обзор: слои, компоненты, паттерны |

## Subdirectories

Нет поддиректорий.

## For AI Agents

### Working In This Directory
- Статьи пишутся на **русском языке**.
- При изменении API, CLI, настроек или поведения приложения — обновляй соответствующую статью.
- `Home.md` содержит навигационные ссылки — обновляй при добавлении новых статей.
- Публикация на GitHub: `pwsh scripts/publish_github_wiki.ps1`.
- Не создавай дубликатов: справочник API в `API.md`, не в `docs/API.md`.

### Common Patterns
```bash
# Публикация всей Wiki на GitHub
pwsh scripts/publish_github_wiki.ps1

# Локальный просмотр (если установлен grip или аналог)
grip docs/wiki/Home.md
```

## Dependencies

### Internal
- `scripts/publish_github_wiki.ps1` — скрипт публикации

### External
- GitHub Wiki (публикуется через PowerShell скрипт)

<!-- MANUAL: -->
