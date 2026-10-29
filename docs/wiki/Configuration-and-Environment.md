# Configuration and Environment

## Файлы конфигурации

- Основной файл: `config/config.json`.
- Файл задач планировщика: `config/tasks.json`.
- Локальный `.env` в корне проекта может задавать переменные окружения.

## Переменные окружения

Ключевая переменная:

- `MIA_API_KEY` — токен API.

## Приоритет токена API

Токен выбирается в таком порядке:

1. `MIA_API_KEY` из окружения.
2. `api.api_key` из `config/config.json`.
3. Если оба отсутствуют, при запуске API генерируется новый токен.

## Поведение при запуске

- `.env` загружается в `main.py` до инициализации модулей.
- В GUI-режиме при открытии вкладки API показываются актуальные настройки.
- При сохранении токена через GUI он синхронизируется в окружение текущего процесса.

## Пример секции API в `config/config.json`

```json
{
  "api": {
    "enabled": true,
    "host": "127.0.0.1",
    "port": 5010,
    "api_key": "test1234",
    "rate_limit": {
      "enabled": true,
      "requests_per_minute": 60,
      "requests_per_hour": 1000,
      "burst_limit": 10,
      "block_duration": 10,
      "whitelist": ["127.0.0.1"],
      "auth_max_attempts": 5,
      "auth_base_delay": 60
    }
  }
}
```

## Тонкие параметры записи (#155)

Секция `recording_tunables` в `config/config.json` — frame-skip, попытки восстановления, пороги диска, лимиты сегментов. Дефолты идентичны прежнему поведению:

```json
{
  "recording_tunables": {
    "enable_frame_skip": false,
    "max_recovery_attempts": 3,
    "audio_max_recovery_attempts": 3,
    "disk_warning_mb": 1024.0,
    "disk_critical_mb": 100.0,
    "disk_check_interval_s": 30.0,
    "max_segment_size_mb": null,
    "max_segment_duration_s": null,
    "health_check_interval_s": 1.0
  }
}
```

Те же параметры редактируются в GUI («Настройки» → «Расширенные параметры записи»). Невалидные значения отклоняются при загрузке конфигурации.

## Rate limiting (#152)

Лимиты запросов настраиваются в `api.rate_limit` (см. пример выше) и применяются при старте API-сервера:

- `requests_per_minute` / `requests_per_hour` — лимиты на клиента;
- `burst_limit` + `block_duration` — защита от всплесков (лимит в секунду и длительность блокировки);
- `whitelist` — IP-адреса без ограничений;
- `auth_max_attempts` + `auth_base_delay` — лимитер неудачных аутентификаций.

Невалидные значения отклоняются при загрузке конфигурации (ошибка в логе, применяются дефолты). Подробности — в [API](API).

## Рекомендации по секретам

- Не коммитьте реальные токены в git.
- Используйте `MIA_API_KEY` в `.env` или в системном окружении.
- Для CI используйте секреты GitHub Actions.

## Связанные страницы

- [GUI](GUI)
- [API](API)
- [Logs and Diagnostics](Logs-and-Diagnostics)
