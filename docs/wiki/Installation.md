# Installation

## Требования

- Windows 10/11.
- Python 3.11 или выше.
- FFmpeg в `PATH`.
- `uv` (рекомендуется для установки и запуска).

## 1. Клонирование репозитория

```bash
git clone https://github.com/chelslava/MIA-ScreenCapture.git
cd MIA-ScreenCapture
```

## 2. Установка зависимостей

```bash
uv sync
```

## 3. Проверка FFmpeg

```bash
ffmpeg -version
```

Если команда не найдена, установите FFmpeg и добавьте его в `PATH`.

## 4. Проверка окружения Python

```bash
uv run python --version
```

Ожидается `Python 3.11+`.

## 5. Первый запуск

GUI:

```bash
uv run python main.py --gui
```

Headless (только API):

```bash
uv run python main.py --headless
```

## 6. Проверка API после запуска

```powershell
Invoke-WebRequest http://127.0.0.1:5000/health -UseBasicParsing
```

Если в GUI выбран другой порт, замените `5000` на ваш порт.
