# CLI

## Базовые команды

```bash
uv run python main.py --gui
uv run python main.py --headless
uv run python main.py --start
uv run python main.py --stop
uv run python main.py --status
```

## Параметры записи

```bash
uv run python main.py --start --area full --audio mic --fps 30 --bitrate 5M
uv run python main.py --start --area rect --rect 100 100 1920 1080
uv run python main.py --start --area window --window "Telegram"
uv run python main.py --start --output "D:/Recordings/demo.mp4"
```

## Параметры API

```bash
uv run python main.py --headless --api-host 127.0.0.1 --api-port 5010
uv run python main.py --headless --no-api
```

## Параметры планировщика

```bash
uv run python main.py --schedule-list
uv run python main.py --schedule-create --trigger daily --time 10:00
uv run python main.py --schedule-update TASK_ID --time 11:00
uv run python main.py --schedule-delete TASK_ID
uv run python main.py --schedule-toggle TASK_ID --enabled false
uv run python main.py --schedule-preview
uv run python main.py --list-presets
```

## Диагностические опции

```bash
uv run python main.py --config config/config.json
uv run python main.py -v
uv run python main.py -vv
uv run python main.py -q
```
