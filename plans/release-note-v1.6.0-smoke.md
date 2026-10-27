# Smoke Run Report

## Авто-отчёт smoke-run

- Старт: `2026-10-27T21:18:45.918348+00:00`
- Финиш: `2026-10-27T21:20:47.709994+00:00`
- Base URL: `http://127.0.0.1:5000`
- Длительность: `2` минут
- Интервал цикла: `5` секунд
- Всего запросов: `72`
- Успешных (200): `72`
- Ошибок: `0`

### Детализация по endpoint

- `/health`: ok=24, failed=0, last_status=200
- `/api/v1/status`: ok=24, failed=0, last_status=200
- `/api/v1/config`: ok=24, failed=0, last_status=200


### Живые сценарии релиза v1.6.0 (headless, 2026-10-27)

- `GET /api/v1/recording/finalization-status` (#151): idle →
  `{"active": false, "elapsed_s": null}`; после записи →
  `{"active": true, "percent": 100.0, "stage": "Завершено"}`.
- Автоостановка по duration (#153): `POST /api/v1/start` с
  `duration: 6` → `/health checks.recording.status`: active (t=2..8) →
  `idle` (t=9); до фикса статус оставался `active` бессрочно. Файл
  записи сохранён и финализирован.
- `GET /api/v1/recording/metrics` содержит `dropped_audio_chunks` (#154).
- Сервер стартует с настройками `api.rate_limit` из config.json (#152);
  rate limiter отклонил чрезмерный поток запросов кодом 429.
