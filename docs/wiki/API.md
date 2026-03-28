# API

## Swagger

- UI: `http://127.0.0.1:<port>/api/docs`
- Spec: `http://127.0.0.1:<port>/api/swagger.json`

## Авторизация

Передавайте заголовок:

`X-API-Key: <your_token>`

## Базовые эндпоинты

- `GET /health`
- `GET /api/v1/status`
- `POST /api/v1/start`
- `POST /api/v1/stop`
- `POST /api/v1/pause`
- `GET /api/v1/config`
- `PUT /api/v1/config`

## Пример старта записи с путём

```json
{
  "area": "full",
  "audio": "mic",
  "fps": 30,
  "codec": "libx264",
  "bitrate": "5M",
  "output_path": "D:/Recordings/session_001.mp4"
}
```

`output_path` поддерживает:

- полный путь к файлу
- путь без расширения (расширение добавится)
- путь к папке (имя файла сгенерируется)
