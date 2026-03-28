# Scheduler

## Что поддерживается

- Создание задач.
- Обновление задач.
- Удаление задач.
- Включение и отключение задач.
- Просмотр списка задач и ближайших запусков.

## Типы триггеров

- `once`: разовый запуск, нужно поле `datetime` (ISO).
- `daily`: ежедневный запуск, нужно поле `time` (`HH:MM`).
- `weekly`: по дням недели, нужны `time` и `day_of_week` (`0..6`).
- `interval`: интервал, нужны `hours` и/или `minutes`, суммарно > 0.
- `cron`: cron-расписание, нужно `cron_expression` из 5 полей.

## Примеры валидных payload

### once

```json
{
  "name": "Разовая запись",
  "trigger": "once",
  "datetime": "2026-03-29T10:00:00+03:00",
  "params": {
    "area": "full",
    "audio": "none",
    "fps": 30
  }
}
```

### daily

```json
{
  "name": "Ежедневно в 10:00",
  "trigger": "daily",
  "time": "10:00",
  "params": {
    "area": "full",
    "audio": "mic",
    "duration": 300
  }
}
```

### weekly

```json
{
  "name": "Будни",
  "trigger": "weekly",
  "time": "10:00",
  "day_of_week": "0,1,2,3,4",
  "params": {
    "area": "window",
    "window_title": "Teams",
    "audio": "system"
  }
}
```

### interval

```json
{
  "name": "Каждые 15 минут",
  "trigger": "interval",
  "hours": 0,
  "minutes": 15,
  "params": {
    "area": "full",
    "audio": "none"
  }
}
```

### cron

```json
{
  "name": "Будни 10:00",
  "trigger": "cron",
  "cron_expression": "0 10 * * 1-5",
  "params": {
    "area": "full",
    "audio": "none"
  }
}
```

## Частые ошибки валидации

- Пустой `datetime` при `trigger = once`.
- Пустой `time` при `daily`/`weekly`.
- Пропущенный `day_of_week` при `weekly`.
- `hours = 0` и `minutes = 0` при `interval`.
- Использование поля `cron` вместо `cron_expression` для `cron`.
