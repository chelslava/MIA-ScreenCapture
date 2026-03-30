# Changelist: Исправление критических проблем

> Дата: 2026-03-30
> Коммитов: 15

## Исправленные проблемы

### P0-Critical (6 задач)

1. **Валидация свободного места на диске** (commit: 8b35cf7)
   - Файлы: `recorder/utils.py`, `gui/controllers/recording_controller.py`
   - Добавлена функция `check_disk_space()` с минимальным порогом 100 МБ
   - Проверка выполняется перед стартом записи

2. **Предотвращение повреждения видео при ошибке FFmpeg** (commit: b864177)
   - Файлы: `recorder/ffmpeg_writer.py`, `recorder/video_recorder.py`
   - Добавлен флаг `is_corrupted` в `FFmpegVideoWriter`
   - Метод `mark_corrupted()` помечает повреждённые файлы
   - Метод `cleanup_corrupted_file()` удаляет повреждённые файлы

3. **Race condition при потере capture-сессии** (commit: ca8fb16)
   - Файл: `recorder/video_recorder.py`
   - Проверка `is_capture_lost` перед и после `read_frame()`
   - Попытка записать последний кадр перед break

4. **Валидация X-Forwarded-For против IP spoofing** (commit: beca1f4)
   - Файл: `api/rate_limiter.py`
   - Паттерны для валидации IPv4 и IPv6 адресов
   - Логирование невалидных IP при попытке спуфинга
   - Fallback к `remote_addr` при невалидных заголовках

5. **Устранение утечки API key через env fallback** (commits: ecb0cb5, 59439d6)
   - Файлы: `api/auth.py`, `tests/unit/test_api_auth.py`
   - Credential Manager — единственное хранилище для API key
   - Ключ больше не записывается в `os.environ`
   - Предупреждение если Credential Manager недоступен

6. **Валидация cron_expression перед созданием scheduler task** (commit: e6682be)
   - Файл: `scheduler/task_scheduler.py`
   - Валидация через `CronTrigger.from_crontab()`
   - Человекочитаемое сообщение об ошибке

### P1-Critical (7 задач)

7. **Уведомление о потере audio chunks** (commit: e0ccca2)
   - Файлы: `recorder/audio_recorder.py`, `gui/controllers/recording_controller.py`
   - Callback `on_chunks_dropped` для уведомления
   - Property `dropped_chunks` для мониторинга

8. **Deadlock в video_recorder.stop()** — уже исправлено
   - Lock освобождается до `join()` в текущем коде

9. **Утечка FFmpeg stderr reader thread** — откат решения
   - select.select() несовместим с текстовыми потоками на Windows
   - Закрытие stream достаточно для освобождения thread

10. **Валидация rect coordinates** — уже реализовано
    - Координаты обрезаются до размеров кадра в `_WindowsCaptureSession`

11. **Уведомление при fallback на full screen** (commit: cd6f4c4)
    - Улучшено логирование
    - Сохранение искомого заголовка для диагностики

12. **Ограничение memory growth в API observability** (commit: 670245c)
    - Файл: `api/server.py`
    - Лимит `_MAX_PATH_ENTRIES = 100` для `path_counts`

13. **Ошибка при невалидном state transition** (commit: 3d40121)
    - Файл: `core/recording_state.py`
    - `pause_recording()` и `resume_recording()` возвращают bool

### Исправления CI

- **UnicodeEncodeError в diff coverage скрипте** (commit: 3484450)
  - Файл: `scripts/check_diff_coverage.py`
  - Использование `TextIOWrapper` с UTF-8 для stdout/stderr

- **Удаление неиспользуемого импорта** (commit: beda190)
  - Файл: `gui/controllers/recording_controller.py`
  - Удалён неиспользуемый импорт `DiskSpaceError`

- **Откат select-based stderr reader** (commit: fbaa34d)
  - Файл: `recorder/ffmpeg_writer.py`
  - Несовместимость с текстовыми потоками на Windows

## Изменённые файлы

```
api/auth.py              - Безопасное хранение API key
api/rate_limiter.py      - Валидация IP-адресов
api/server.py            - Ограничение memory growth
core/recording_state.py  - State transition с возвратом bool
gui/controllers/recording_controller.py - Проверка диска, audio callbacks
recorder/audio_recorder.py - Callback on_chunks_dropped
recorder/ffmpeg_writer.py - Обработка повреждённых файлов
recorder/utils.py        - Функции check_disk_space, get_available_disk_space
recorder/video_recorder.py - Race condition fixes, corrupted file handling
scheduler/task_scheduler.py - Валидация cron_expression
scripts/check_diff_coverage.py - UTF-8 encoding fix
tests/unit/test_api_auth.py - Обновлены тесты для нового поведения
```

## Статистика

- Строк добавлено: ~300
- Строк удалено: ~40
- Файлов изменено: 12
- Тестов обновлено: 3
