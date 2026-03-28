# Аудит Точек Улучшения (2026-03-28)

## Топ-10 доработок для ближайших релизов

1. **P0** — Убрать блокирующие вызовы GUI из API callbacks через job-очередь
   с backpressure и отдельным worker.
   Эффект: меньше таймаутов `POST /api/v1/stop`, стабильнее API при нагрузке.
   Сложность: **L**.
   Файлы: `main.py`, `api/routes.py`, `core/recording_service.py`.

2. **P0** — Ввести идемпотентность команд `start/stop/pause` через
   `Idempotency-Key`.
   Эффект: исключение дублей операций при повторной отправке запросов.
   Сложность: **M**.
   Файлы: `api/routes.py`, `api/server.py`, `api/schemas.py`.

3. **P0** — Заменить in-memory `operation_store` на TTL-хранилище с лимитами и
   фоновой очисткой.
   Эффект: предсказуемое потребление памяти при длинной сессии API.
   Сложность: **M**.
   Файлы: `api/server.py`, `api/routes.py`.

4. **P1** — Вынести запись токена в ОС-хранилище секретов (Windows
   Credential Manager) с fallback на env.
   Эффект: снижение риска компрометации токена в конфиге/логах.
   Сложность: **M**.
   Файлы: `api/auth.py`, `main.py`, `config.py`, `gui/views/api_settings_view.py`.

5. **P1** — Добавить health-check FFmpeg pipeline с детекцией зависания writer
   и авто-рекавери.
   Эффект: меньше кейсов `moov atom not found`, стабильная финализация файла.
   Сложность: **L**.
   Файлы: `recorder/ffmpeg_writer.py`, `recorder/encoder.py`,
   `recorder/recording_controller.py`.

6. **P1** — Ввести bounded ring-buffer для live-логов GUI с incremental diff и
   защитой от burst-логирования.
   Эффект: меньше лагов интерфейса на длинном прогоны API-вкладки.
   Сложность: **M**.
   Файлы: `gui/views/api_settings_view.py`, `logger_config.py`.

7. **P1** — Починить DX тестов на Windows: изоляция temp/cache директорий в
   `tests/.local_tmp` + bootstrap для `pytest`.
   Эффект: устранение массовых `WinError 5`, стабильный локальный/CI прогон.
   Сложность: **S**.
   Файлы: `tests/conftest.py`, `pyproject.toml`, `.github/workflows/release.yml`.

8. **P1** — Добавить интеграционные API тесты на реальный lifecycle:
   `start -> status -> stop -> operation polling`.
   Эффект: раннее обнаружение регрессий в критичном API пути.
   Сложность: **M**.
   Файлы: `tests/integration/`, `api/routes.py`, `api/server.py`.

9. **P2** — Включить структурированные JSON-логи для API (по флагу) и поля:
   `trace_id`, `request_id`, `latency_ms`, `status`.
   Эффект: проще разбор инцидентов и downstream-анализ.
   Сложность: **M**.
   Файлы: `logger_config.py`, `api/server.py`.

10. **P2** — Добавить профилирование hot-path захвата кадра и метрики jitter FPS.
    Эффект: измеримое улучшение производительности записи и UI-отзывчивости.
    Сложность: **M**.
    Файлы: `recorder/video_recorder.py`, `core/recording_service.py`,
    `api/routes.py`.
