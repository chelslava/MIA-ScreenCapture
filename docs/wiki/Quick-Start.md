# Quick Start

## Вариант 1: GUI + API

1. Запустите приложение:

```bash
uv run python main.py --gui
```

2. Откройте вкладку `API`.
3. Укажите порт и токен, нажмите `Сохранить настройки`.
4. Нажмите `Запустить` или `Перезапустить`.
5. Проверьте здоровье API:

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health -UseBasicParsing
```

## Вариант 2: Headless (без GUI)

```bash
uv run python main.py --headless --api-host 127.0.0.1 --api-port 5010
```

Проверьте:

```powershell
Invoke-WebRequest http://127.0.0.1:5010/health -UseBasicParsing
```

## Swagger

- UI: `http://127.0.0.1:<port>/api/docs`
- JSON: `http://127.0.0.1:<port>/api/swagger.json`

## Первый авторизованный запрос

```powershell
$headers = @{ "X-API-Key" = "test1234" }
Invoke-RestMethod http://127.0.0.1:5000/api/v1/status -Headers $headers
```

Если получаете `401`, проверьте токен в GUI и в заголовке `X-API-Key`.
