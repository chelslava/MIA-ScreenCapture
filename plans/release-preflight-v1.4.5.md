# Release Preflight Checklist `v1.4.5`

> Цель: единая проверка качества перед публикацией релиза.
> Обновлено: 2026-03-29

## 1. Версия и документация

- [ ] Версия `1.4.5` синхронизирована в runtime и документации.
- [ ] `CHANGELOG.md` обновлён по фактическим изменениям релиза.
- [ ] `TODO.md` очищен от закрытых задач и перенесён на следующий цикл.

## 2. Качество кода

- [ ] `uv run ruff check .`
- [ ] `uv run ruff format --check .`
- [ ] `uv run mypy exceptions.py core/recording_types.py`
- [ ] `uv run pytest tests/unit/`
- [ ] `uv run pytest tests/integration/test_api_server_lifecycle.py`
- [ ] `uv run pytest tests/integration/test_api_health_metrics.py`
- [ ] `uv run pytest tests/integration/test_api_error_handling.py`
- [ ] `uv run pytest tests/integration/test_api_recording_routes.py`

## 3. API/GUI smoke evidence

- [x] Выполнен 30+ минутный smoke-run API-вкладки GUI.
- [ ] Проверены сценарии `start/stop/restart` при открытом live-логе.
- [x] Результат smoke-run зафиксирован в
  `plans/release-note-v1.4.5-smoke.md`.

## 4. Release-артефакты

- [ ] Сборка артефактов прошла без ошибок.
- [ ] Файл `SHA256SUMS` сгенерирован и приложен к релизу.
- [ ] Проверены имена и размеры итоговых артефактов.

## 5. CI и публикация

- [ ] Последний workflow `CI` на `main` имеет статус `success`.
- [ ] Release workflow выполнен успешно на теге `v1.4.5`.
- [ ] В заметках релиза нет блокирующих известных дефектов.
