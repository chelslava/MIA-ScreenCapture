# TODO: Краткосрочные Задачи До `v1.4.5`

> Обновлено: 2026-03-29
> Статус: активный список до ближайшего релиза

## P0 (обязательно до релиза)

- [ ] Выполнить ручной 30+ минутный GUI smoke-run API-вкладки с открытым
  окном логов и зафиксировать результат в
  `plans/release-note-v1.4.5-smoke.md`.

## P1 (следующий приоритет)

- [ ] Расширить блокирующий integration-suite в CI
  до полного целевого набора `tests/integration/` (legacy + v1).
- [ ] Расширить блокирующий `mypy`-scope в CI
  по модулям API/GUI/recorder без возврата `continue-on-error`.

## P2 (после стабилизации релиза)

- [ ] Реализовать асинхронную очередь GUI-команд для API (`start/stop/pause`)
  вместо прямых вызовов GUI-потока.
- [ ] Добавить watchdog для FFmpeg pipeline с чистым восстановлением
  после зависания/ошибок финализации.
- [ ] Добавить ring-buffer для live-логов вкладки API, чтобы избежать лагов
  UI при burst-логировании.
- [ ] Перевести access-логи API в JSON-формат (`trace_id`, `request_id`,
  `latency_ms`, `status`) для ускорения диагностики.
- [ ] Перевести длительности рекордера на monotonic clock вместо
  `time.time()`, чтобы устранить ошибки при смене системного времени.
- [ ] Добавить debounce/батчинг для `_save_tasks()` в scheduler, чтобы
  снизить лишний дисковый I/O.
- [ ] Оптимизировать расчёт перцентилей latency в observability без
  полной сортировки массива на каждый запрос.
- [ ] Добавить мягкий таймаут/защиту остановки `TaskScheduler.stop()`
  при зависших job callback.
- [ ] Добавить release-gate по observability baseline
  (`p95`, `error_rate`, `rss_mb`) перед публикацией релиза.

### Security (безопасность)

- [ ] Добавить валидацию IP-заголовков в `rate_limiter.py`
  (`X-Forwarded-For`, `X-Real-IP`) — защита от IP spoofing.
- [ ] Валидация path traversal в `config.py:409-418` для `default_path`.
- [ ] Установить ограничительные права доступа для `config/` и `logs/`
  директорий (только для текущего пользователя).
- [ ] Маскировать API key в `get_api_key()` вместо возврата полного ключа.
- [ ] Добавить лимит максимального значения `bitrate` в `schemas.py:44-47`
  для защиты от DoS через завышенные параметры.

### Stability (стабильность)

- [ ] Добавить проверку свободного места на диске перед началом записи.
- [ ] Обработка потери capture-сессии с попыткой переподключения
  в `video_recorder.py:197-210`.
- [ ] Очистка operation store в `api/server.py` по таймеру,
  а не только при `get()` — избежать memory leak.
- [ ] Добавить синхронизацию `pause/resume` с capture thread
  в `video_recorder.py:476-478` — устранить race condition.
- [ ] Использовать `threading.Event.wait()` вместо busy-wait
  в headless режиме `main.py:373-380`.

### Performance (производительность)

- [ ] Кэширование `get_available_windows()` и `get_audio_devices()` с TTL
  для снижения системных вызовов.
- [ ] Убрать лишнюю копию массива `np.array(bgr, copy=True)`
  в `video_recorder.py:193-195` — использовать buffer protocol.
- [ ] Вынести захардкоженные таймауты в конфигурацию:
  `capture_stop_timeout`, `audio_queue_max_chunks`,
  `audio_queue_get_timeout`, FFmpeg-таймауты.

## P3 (функциональные улучшения)

- [ ] Реализовать реальный WebSocket транспорт вместо заглушки
  в `api/websocket.py`.
- [ ] Механизм backup/restore конфигурации.
- [ ] Восстановление записи после краша приложения.
- [ ] Batch операции в API (`start/stop/status` для нескольких задач).
- [ ] Диалог горячих клавиш в GUI.
- [ ] Абстрагировать общую логику `pause/resume/stop`
  из `video_recorder` и `audio_recorder` — устранить дублирование.

## Правило ведения TODO

- Закрытые задачи удаляем из файла, не оставляем в виде `[x]`.
- Незакрытые задачи переносим в новый TODO ближайшего релиза.
