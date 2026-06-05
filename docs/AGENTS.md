<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-29 | Updated: 2026-06-05 -->

# docs/

## Purpose
Документация проекта для пользователей и разработчиков. Публикуется как GitHub Wiki через `scripts/publish_github_wiki.ps1`.

## Key Files

| Файл | Описание |
|------|----------|
| `API.md` | Справочник REST API: все endpoint'ы, схемы запросов/ответов, аутентификация |

## Subdirectories

| Директория | Назначение |
|-----------|---------|
| `wiki/` | Markdown-статьи GitHub Wiki (см. `wiki/AGENTS.md`) |

## For AI Agents

### Working In This Directory
- Документация пишется на русском языке.
- При изменении API, CLI или настроек — обновляй соответствующие wiki-статьи.
- Публикация на GitHub: `scripts/publish_github_wiki.ps1`.

### Common Patterns
```bash
# Публикация wiki на GitHub
pwsh scripts/publish_github_wiki.ps1
```

## Dependencies

### External
- GitHub Wiki (публикуется через PowerShell скрипт)

<!-- MANUAL: -->
