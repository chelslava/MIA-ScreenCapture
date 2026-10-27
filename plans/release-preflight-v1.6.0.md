# Release Preflight Checklist `v1.6.0`

> Цель: единая проверка качества перед публикацией релиза.
> Обновлено: 2026-10-27

## 1. Версия и документация

- [x] Версия `1.6.0` синхронизирована: `pyproject.toml`, `uv.lock`,
      заголовки `README.md` / `README.ru.md`.
- [x] `CHANGELOG.md` дополнен секцией `[1.6.0]` по фактическим изменениям
      (hw-кодирование, #151, #152, #153, #154, CI-фикс diff-coverage).
- [x] Выбрана версия `1.6.0` (не `1.5.1`): релиз содержит новую
      функциональность (аппаратное кодирование, REST-эндпоинт финализации,
      конфигурируемый rate limiting) — по semver минорный бамп.

## 2. Качество кода

- [x] `uv run ruff check .` — All checks passed
- [x] `uv run ruff format --check .` — 316 files already formatted
- [x] `uv run mypy .` — no issues found in 158 source files
- [x] `uv run pytest tests/unit/` — 2604 passed, 78 skipped
- [x] `uv run pytest tests/integration/test_api_server_lifecycle.py
      test_api_health_metrics.py test_api_error_handling.py
      test_api_recording_routes.py` — 36 passed
- [x] CI на `main` (run 40582666005, commit bfadea7) — success, включая
      гейт diff-coverage по изменённым строкам (порог 70%)

## 3. API smoke

- [x] `uv run python scripts/api_smoke_run.py` — все базовые endpoint'ы
      отвечают 200 (отчёт ниже).
- [x] Новый эндпоинт `GET /api/v1/recording/finalization-status` покрыт
      unit-тестами во всех трёх состояниях (активна/завершена/не идёт) —
      `tests/unit/api/test_routes_recording_finalization.py`.

## 4. Release-артефакты

- [x] Сборка артефактов выполняется release-workflow на теге `v*`
      (Python-пакет, Windows EXE, инсталлятор, `SHA256SUMS`).
- [x] Авто-обновление #128 читает GitHub Releases — публикация через
      `softprops/action-gh-release` с `generate_release_notes: true`.

## 5. CI и публикация

- [x] Последний workflow `CI` на `main` имеет статус `success`.
- [ ] Release workflow выполнен успешно на теге `v1.6.0` (после пуша тега).
