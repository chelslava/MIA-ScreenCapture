# План улучшений MIA-ScreenCapture — 2026-11-04

> База анализа: репозиторий v1.7.0 (коммит 26ba944), 164 закрытых issue,
> база знаний (kb: projects/mia-screencapture), сравнение с OBS, ShareX,
> ScreenToGif, Camtasia, Loom.

## Текущее состояние (что уже сильно)

- **Ядро записи**: WGC API, multi-monitor + hot-swap, сегменты, crash-recovery,
  disk-monitoring, проверка целостности после записи, HW-кодирование
  h264/hevc (NVENC/AMF/QSV) с auto-fallback.
- **API**: REST v1 + WebSocket + HMAC-webhook, auth (Credential Manager),
  rate limiting, idempotency, circuit breaker, Swagger; CORS только localhost.
- **Экосистема**: планировщик APScheduler, профили, библиотека с миниатюрами,
  постобработка (GIF, обрезка, Whisper-транскрипция), плагины, облако,
  авто-обновление (GitHub Releases + дельта-патчи), Inno-инсталлятор, i18n
  (ru/en), темы, доступность.
- **Качество**: покрытие 76,9% (gate 70% + diff-coverage), CI matrix
  Windows py3.11/3.12 (unit/integration/quality/coverage/security),
  Dependabot weekly, 0 TODO/FIXME, нет `shell=True`.

## Выводы анализа — главные пробелы

1. **Функциональность**: нет webcam PiP, эффектов курсора/кликов, обратного
   отсчёта, AV1, шумоподавления микрофона, авто-zoom. Это стандартный набор
   туториал-рекордеров, по которому проект проигрывает OBS/ShareX/Camtasia.
2. **UX**: в выделении области нет лупы и индикации размеров; нет онбординга
   первого запуска и поиска по настройкам.
3. **Производительность**: метрики FPS/jitter есть (`recorder/frame_metrics.py`),
   но нет автоматического регрессионного бенчмарка — деградации ловятся руками.
4. **Стабильность**: длинные записи (часы) покрыты unit-тестами логики, но нет
   scheduled soak-прогона на утечки/дрейф A/V.
5. **Безопасность**: транспорт API — открытый HTTP; для headless-развёртываний
   в LAN нужен опциональный TLS. Релизные артефакты не подписаны, SBOM нет.
6. **Архитектура**: `main.py` — 2274 строки, `VideoRecorderApp` ~2000 строк
   (прецедент декомпозиции — закрытые #115/#164).
7. **Гигиена**: мусор в корне рабочей копии (`C:/`, `tab_block.tmp`,
   `task_block.tmp`, `tmp_pytest_run*`), мёртвые кроссплатформенные
   зависимости (`python-xlib`, darwin-маркер `pygetwindow`) в Windows-only
   проекте.

## Бэклог → issue

| # | Тема | Категория | Приоритет | Issue |
|---|------|-----------|-----------|-------|
| 1 | Веб-камера PiP-оверлеем | functionality | P1 | [#165](https://github.com/chelslava/MIA-ScreenCapture/issues/165) |
| 2 | Подсветка курсора и эффекты кликов | functionality/ux | P2 | [#166](https://github.com/chelslava/MIA-ScreenCapture/issues/166) |
| 3 | Обратный отсчёт перед стартом | functionality/ux | P3 | [#167](https://github.com/chelslava/MIA-ScreenCapture/issues/167) |
| 4 | Аппаратное кодирование AV1 | functionality/perf | P2 | [#168](https://github.com/chelslava/MIA-ScreenCapture/issues/168) |
| 5 | Шумоподавление микрофона | functionality | P3 | [#169](https://github.com/chelslava/MIA-ScreenCapture/issues/169) |
| 6 | Zoom-pan автоэффекты постобработки | functionality | P3 | [#170](https://github.com/chelslava/MIA-ScreenCapture/issues/170) |
| 7 | Лупа и размеры в выборе области | ux/ui | P2 | [#171](https://github.com/chelslava/MIA-ScreenCapture/issues/171) |
| 8 | Онбординг + поиск по настройкам | ux | P3 | [#172](https://github.com/chelslava/MIA-ScreenCapture/issues/172) |
| 9 | Регрессионный бенчмарк hot-path в CI | performance/devops | P3 | [#173](https://github.com/chelslava/MIA-ScreenCapture/issues/173) |
| 10 | Soak-тест длинных записей по расписанию | stability/devops | P2 | [#174](https://github.com/chelslava/MIA-ScreenCapture/issues/174) |
| 11 | Опциональный HTTPS/TLS для API | security/api | P2 | [#175](https://github.com/chelslava/MIA-ScreenCapture/issues/175) |
| 12 | Декомпозиция `VideoRecorderApp` | refactoring/tech-debt | P2 | [#176](https://github.com/chelslava/MIA-ScreenCapture/issues/176) |
| 13 | Подпись артефактов, SBOM, attestations | devops/security | P2 | [#177](https://github.com/chelslava/MIA-ScreenCapture/issues/177) |
| 14 | Чистка мусора в корне и мёртвых зависимостей | tech-debt | P3 | [#178](https://github.com/chelslava/MIA-ScreenCapture/issues/178) |
| 15 | Обновление пользовательской документации | documentation | P3 | [#179](https://github.com/chelslava/MIA-ScreenCapture/issues/179) |

## Что сознательно НЕ включено (уже сделано или не обосновано)

- Ноль-копирование кадров (shared memory) — #125 закрыт.
- Health-check/рекавери FFmpeg — #112 закрыт.
- Mica/Acrylic, drag-n-drop, мульти-выбор, плавающий виджет — #157–#160 закрыты.
- Whisper-транскрипция, GIF, обрезка — реализованы в `core/post_processing/`.
- Хранение токена в Credential Manager — #111, `api/auth.py`.
- pip-audit в CI — job «Security Audit» в `ci.yml`.
- Режим Windows Service — #122 закрыт (`cli/windows_service.py`).
- Мульти-язычность сверх ru/en — пользователей не подтверждено.

## Порядок работы (рекомендация)

1. **Быстрые победы** (неделя): #14 (чистка), #3 (отсчёт), #7 (лупа).
2. **Стратегические фичи**: #1 (webcam PiP) → #2 (курсор) → #4 (AV1).
3. **Надёжность/безопасность**: #10 (soak) → #11 (TLS) → #13 (подписи).
4. **Инженерное качество**: #12 (декомпозиция main.py) → #9 (бенчмарк).
5. **Полировка**: #5, #6, #8, #15.
