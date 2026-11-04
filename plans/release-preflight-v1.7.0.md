# Release Preflight Checklist `v1.7.0`

> Цель: единая проверка качества перед публикацией релиза.
> Обновлено: 2026-11-04

## 1. Версия и документация

- [x] Версия `1.7.0` синхронизирована: `pyproject.toml`, `uv.lock`,
      заголовки `README.md` / `README.ru.md`.
- [x] `CHANGELOG.md` дополнен секцией `[1.7.0]` по фактическим изменениям
      (редизайн GUI, страница «Записи», геометрия окна, безопасность).
- [x] Выбрана версия `1.7.0` (не `1.6.1`): релиз содержит новую
      функциональность (страница настроек-категорий, отдельная страница
      записей, пункт трея «Настройки», сохранение геометрии окна) —
      по semver минорный бамп.

## 2. Качество кода

- [x] `uv run ruff check .` — All checks passed
- [x] `uv run ruff format --check .` — 344 files already formatted
- [x] `uv run mypy .` — no issues found in 173 source files
- [x] `uv run pytest tests/unit/` — 2924 passed, 78 skipped
- [x] `uv run pytest tests/integration/test_api_server_lifecycle.py
      test_api_health_metrics.py test_api_error_handling.py
      test_api_recording_routes.py` — 36 passed
- [x] CI на `main` (run 41744724483, commit 1f5291c) — success

## 3. API smoke

- [x] Headless-сервер: `uv run python main.py --headless` — API поднят на
      127.0.0.1:5000, ключ из Credential Manager (`api.auth.get_stored_api_key`).
- [x] `uv run python scripts/api_smoke_run.py --base-url
      http://127.0.0.1:5000 --api-key <stored> --duration-minutes 2
      --interval-seconds 15` — 24/24 запросов со статусом 200
      (`/health` 8, `/api/v1/status` 8, `/api/v1/config` 8), ошибок нет.
      Примечание: интервал 5с упирается в rate limiter (#152) — штатный
      интервал 15с проходит без ограничений.

## 4. Release-артефакты

- [x] Сборка артефактов выполняется release-workflow на теге `v*`
      (Python-пакет, Windows EXE, инсталлятор, `SHA256SUMS`).
- [x] Авто-обновление #128 читает GitHub Releases — публикация через
      `softprops/action-gh-release` с `generate_release_notes: true`.

## 5. CI и публикация

- [ ] Release workflow выполнен успешно на теге `v1.7.0` (после пуша тега).
