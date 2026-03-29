# Release Preflight Checklist `v1.4.5`

> Цель: единая проверка качества перед публикацией релиза.
> Обновлено: 2026-03-29

## 1. Версия и документация

- [x] Версия `1.4.5` синхронизирована в runtime и документации.
- [x] `CHANGELOG.md` обновлён по фактическим изменениям релиза.
- [x] `TODO.md` очищен от закрытых задач и перенесён на следующий цикл.

## 2. Качество кода

- [x] `uv run ruff check .`
- [x] `uv run ruff format --check .`
- [x] `uv run mypy exceptions.py core/recording_types.py`
- [x] `uv run pytest tests/unit/`
- [x] `uv run pytest tests/integration/test_api_server_lifecycle.py`
- [x] `uv run pytest tests/integration/test_api_health_metrics.py`
- [x] `uv run pytest tests/integration/test_api_error_handling.py`
- [x] `uv run pytest tests/integration/test_api_recording_routes.py`

## 3. API/GUI smoke evidence

- [x] Выполнен 30+ минутный smoke-run API-вкладки GUI.
- [x] Проверены сценарии `start/stop/restart` при открытом live-логе.
- [x] Результат smoke-run зафиксирован в
  `plans/release-note-v1.4.5-smoke.md`.

## 4. Release-артефакты

- [x] Сборка артефактов прошла без ошибок.
- [x] Файл `SHA256SUMS` сгенерирован и приложен к релизу.
- [x] Проверены имена и размеры итоговых артефактов.

## 5. CI и публикация

- [x] Последний workflow `CI` на `main` имеет статус `success`.
- [x] Release workflow выполнен успешно на теге `v1.4.5`.
- [x] В заметках релиза нет блокирующих известных дефектов.
