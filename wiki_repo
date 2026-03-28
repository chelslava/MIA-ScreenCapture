# Troubleshooting

## Swagger не открывается

1. Убедитесь, что API запущен.
2. Проверьте правильный порт в настройках API.
3. Проверьте `GET /health`.

## 401 Unauthorized

Передайте `X-API-Key`.

## 404 not_found для config

Используйте versioned путь:

`/api/v1/config`

## Ошибки валидации schedule

Поля зависят от `trigger`:

- `once` -> `datetime`
- `daily` -> `time`
- `weekly` -> `time`, `day_of_week`
- `interval` -> `hours`/`minutes`
- `cron` -> `cron_expression`

## Ошибки FFmpeg

- Проверьте `ffmpeg -version`
- Убедитесь, что путь записи доступен
- Смотрите `logs/` и `logs/api/`
