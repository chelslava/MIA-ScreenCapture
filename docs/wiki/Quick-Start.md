# Quick Start

## GUI режим

```bash
uv run python main.py --gui
```

## Headless режим (только API)

```bash
uv run python main.py --headless
```

## Проверка health

```powershell
Invoke-WebRequest http://127.0.0.1:5010/health -UseBasicParsing
```

Порт берётся из настроек API.
