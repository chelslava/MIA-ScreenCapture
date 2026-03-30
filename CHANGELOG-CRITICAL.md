# Changelist: Исправление критических проблем

> Дата: 2026-03-30
> Коммитов: 10

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

### Исправления CI

- **UnicodeEncodeError в diff coverage скрипте** (commit: 3484450)
  - Файл: `scripts/check_diff_coverage.py`
  - Использование `TextIOWrapper` с UTF-8 для stdout/stderr

- **Удаление неиспользуемого импорта** (commit: beda190)
  - Файл: `gui/controllers/recording_controller.py`
  - Удалён неиспользуемый импорт `DiskSpaceError`

## Изменённые файлы

```
api/auth.py              - Безопасное хранение API key
api/rate_limiter.py      - Валидация IP-адресов
gui/controllers/recording_controller.py - Проверка диска
recorder/ffmpeg_writer.py - Обработка повреждённых файлов
recorder/utils.py        - Функции check_disk_space, get_available_disk_space
recorder/video_recorder.py - Race condition fixes, corrupted file handling
scheduler/task_scheduler.py - Валидация cron_expression
scripts/check_diff_coverage.py - UTF-8 encoding fix
tests/unit/test_api_auth.py - Обновлены тесты для нового поведения
```

## Статистика

- Строк добавлено: ~200
- Строк удалено: ~20
- Файлов изменено: 10
- Тестов обновлено: 3
