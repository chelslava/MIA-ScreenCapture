# MIA-ScreenCapture Wiki

Полная документация по приложению MIA-ScreenCapture:
запуск, настройка, GUI, REST API, CLI, планировщик, логи и диагностика.

## Содержание

- [Установка](Installation)
- [Быстрый старт](Quick-Start)
- [Конфигурация и переменные окружения](Configuration-and-Environment)
- [Работа с GUI](GUI)
- [REST API](API)
- [CLI](CLI)
- [Планировщик задач](Scheduler)
- [Логи и диагностика](Logs-and-Diagnostics)
- [Архитектура](Architecture)
- [Troubleshooting](Troubleshooting)

## Что умеет приложение

- Запись экрана Windows 10/11 с выбором области: `full`, `window`, `rect`.
- Запись звука: `mic`, `system`, `both`, `none`.
- Управление из GUI, через REST API и через CLI.
- Планировщик задач записи (once/daily/weekly/interval/cron).
- Встроенная документация API (Swagger UI).
- Реальное время логов API во вкладке GUI.
- Логи API в отдельной папке `logs/api` с разделением по дням.

## Поддерживаемая платформа

- Windows 10/11 (проект целевой только для Windows).
- Python 3.11+.
- FFmpeg должен быть доступен в `PATH`.

## Рекомендованный порядок начала

1. Прочитайте [Установка](Installation).
2. Выполните шаги из [Быстрый старт](Quick-Start).
3. Настройте токен и порт по [Конфигурация и переменные окружения](Configuration-and-Environment).
4. Для интеграций перейдите в [REST API](API).
