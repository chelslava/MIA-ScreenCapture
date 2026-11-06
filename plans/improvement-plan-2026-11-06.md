# План улучшений MIA-ScreenCapture — 2026-11-06

> База анализа: репозиторий v1.7.1 (коммит `43b7cae`), 185 закрытых issue,
> база знаний (`projects/mia-screencapture`), инвентаризации recorder/core,
> GUI/UX и API/security/DevEx. Прошлый цикл — `improvement-plan-2026-11-04.md`
> (issues #165–#179) и perf-серия #180–#185 — полностью закрыт в v1.7.1.

## Текущее состояние (что уже сильно)

- **Захват/кодирование**: WGC, multi-monitor + hot-swap, сегменты,
  crash-recovery, HW h264/hevc/av1 (NVENC/AMF/QSV) с auto-fallback,
  preset «auto», BGRA passthrough, адаптивный frame-skip, замер
  FPS/jitter (`recorder/frame_metrics.py`).
- **Фичи v1.7.1**: веб-камера PiP, подсветка курсора и кольца кликов,
  обратный отсчёт, лупа в выборе области, мастер первого запуска и
  поиск по настройкам, авто-zoom, шумоподавление микрофона.
- **API**: REST v1 + WebSocket + HMAC-webhook, auth (Credential
  Manager), rate limiting, idempotency, circuit breaker, Swagger,
  опциональный TLS (#175), observability-метрики.
- **Экосистема**: планировщик (cron/interval/once), профили, плагины
  постобработки, облако (S3/Google Drive/OneDrive/WebDAV), авто-обновление
  с delta-детектом, Windows Service, i18n (ru/en), темы.
- **Качество**: 3386 unit + 282 интеграционных, ruff/mypy strict на 190
  файлах, diff-coverage gate, pip-audit, CodeQL, еженедельные soak (#174)
  и benchmark (#173) с авто-issue, SBOM + sigstore attestations (#177).

## Метод аудита

Три параллельные инвентаризации кода (capture/encode/audio/post;
GUI/UX; API/security/DevEx) с вердиктами ЕСТЬ/НЕТ и file:line,
сверка с закрытым бэклогом (#111–#185) против дублирования,
сверка со стратегическим направлением базы знаний
(«AI & Enterprise против Loom/OBS/ShareX»).

## Главные пробелы

1. **Функциональность**: нет скриншот-режима, стриминга (RTMP/SRT),
   многодорожечного аудио (жёсткий XOR mic/system), MKV-контейнера,
   маркеров/глав, экспорт-пресетов платформ, авто-стопов по событиям.
2. **UX**: написанная библиотека `LibraryView` не подключена к окну
   (мёртвый код 449 строк), системные toast-уведомления — мёртвый код,
   нет пост-редактора, хоткеи не настраиваемы, нет live-превью.
3. **Стабильность**: нет миграций/backup конфига (битый файл молча
   теряет настройки), нет отката обновления (Expand-Archive поверх без
   бэкапа), нет crash-handling (excepthook/faulthandler/watchdog).
4. **Безопасность**: токен WebSocket передаётся в query string,
   один всемогущий API-ключ без scopes, нет аудит-лога мутаций.
5. **Корректность**: геометрия захвата без DPI-awareness — риск
   «съехавшей» записи на mixed-DPI мультимониторах.
6. **Производительность**: постобработка всегда на CPU (ни одного
   hwaccel в шагах).
7. **DevEx/DevOps**: CLI без `--json`/exit-кодов, нет secrets/license
   сканов, инсталлятор собирается только в релизе, нет portable zip
   и winget.
8. **Архитектура**: четыре god-файла (main_window 1699, ffmpeg_writer
   1590, video_recorder 1437, utils 1313) и дубли схем в config.py.
9. **i18n**: десятки хардкод-русских строк мимо `_()` — en-локаль
   частично нерабочая.

## Бэклог → issue

| # | Тема | Категория | Приоритет | Issue |
|---|------|-----------|-----------|-------|
| 1 | Подключить LibraryView (поиск/теги/сортировка/grid) + переименование и детали | ux | P1 | [#186](https://github.com/chelslava/MIA-ScreenCapture/issues/186) |
| 2 | Режим скриншота (экран/окно/область, хоткей/API/CLI) | functionality | P1 | [#187](https://github.com/chelslava/MIA-ScreenCapture/issues/187) |
| 3 | Многодорожечный аудио: mic+system одновременно, микшер, выбор устройства по id | functionality/perf | P1 | [#188](https://github.com/chelslava/MIA-ScreenCapture/issues/188) |
| 4 | Убрать API-токен из query string WebSocket | security | P1 | [#189](https://github.com/chelslava/MIA-ScreenCapture/issues/189) |
| 5 | Миграции схемы конфига (schema_version) и backup | stability | P2 | [#190](https://github.com/chelslava/MIA-ScreenCapture/issues/190) |
| 6 | Откат неудачного обновления и реальное применение delta-патчей | stability | P2 | [#191](https://github.com/chelslava/MIA-ScreenCapture/issues/191) |
| 7 | Crash-handling (excepthook/faulthandler/minidump) + watchdog Service | stability | P2 | [#192](https://github.com/chelslava/MIA-ScreenCapture/issues/192) |
| 8 | AI-главы, саммари и семантический поиск по транскриптам (локально) | functionality | P2 | [#193](https://github.com/chelslava/MIA-ScreenCapture/issues/193) |
| 9 | Пост-редактор записи: аннотации, водяной знак, визуальный trim | ux | P2 | [#194](https://github.com/chelslava/MIA-ScreenCapture/issues/194) |
| 10 | Настраиваемые горячие клавиши с детектом конфликтов | ux | P2 | [#195](https://github.com/chelslava/MIA-ScreenCapture/issues/195) |
| 11 | Контейнер MKV + параметры кодирования (keyint, RC-режимы HW, Opus) | functionality | P2 | [#196](https://github.com/chelslava/MIA-ScreenCapture/issues/196) |
| 12 | Стриминг в реальном времени (RTMP/SRT) | functionality | P2 | [#197](https://github.com/chelslava/MIA-ScreenCapture/issues/197) |
| 13 | Scopes API-ключей (read-only/control) и аудит-лог мутаций | security | P2 | [#198](https://github.com/chelslava/MIA-ScreenCapture/issues/198) |
| 14 | Системные toast-уведомления и звуковые сигналы start/stop | ux | P2 | [#199](https://github.com/chelslava/MIA-ScreenCapture/issues/199) |
| 15 | DPI-awareness геометрии захвата (mixed-DPI) | stability | P2 | [#200](https://github.com/chelslava/MIA-ScreenCapture/issues/200) |
| 16 | Live-превью кадра и метрики записи в главном окне | ux | P3 | [#201](https://github.com/chelslava/MIA-ScreenCapture/issues/201) |
| 17 | Выбор области: пресеты, цифровой ввод, snap к окнам, last-area | ux | P3 | [#202](https://github.com/chelslava/MIA-ScreenCapture/issues/202) |
| 18 | Авто-остановка по простою, тишине и размеру файла | functionality | P3 | [#203](https://github.com/chelslava/MIA-ScreenCapture/issues/203) |
| 19 | GPU-ускорение постобработки (hwaccel в шагах) | performance | P3 | [#204](https://github.com/chelslava/MIA-ScreenCapture/issues/204) |
| 20 | Экспорт-пресеты платформ и конвертация из UI | functionality | P3 | [#205](https://github.com/chelslava/MIA-ScreenCapture/issues/205) |
| 21 | CLI `--json` и контракт exit-кодов | devex | P3 | [#206](https://github.com/chelslava/MIA-ScreenCapture/issues/206) |
| 22 | CI: secrets/license-скан, сборка инсталлятора на PR; дистрибуция: portable zip, winget | devops | P3 | [#207](https://github.com/chelslava/MIA-ScreenCapture/issues/207) |
| 23 | Декомпозиция god-файлов и дубли схем конфига | refactoring | P3 | [#208](https://github.com/chelslava/MIA-ScreenCapture/issues/208) |
| 24 | i18n-дыры (хардкод-строки) и полиш иконок/стилей | tech-debt | P3 | [#209](https://github.com/chelslava/MIA-ScreenCapture/issues/209) |

## Порядок работы (рекомендация)

1. **Быстрые победы** (неделя): #186 (LibraryView уже написана —
   wire-in), #199 (toast+звуки — код есть), #189 (WS-токен — точечный
   фикс), #206 (CLI `--json`).
2. **Надёжность**: #190 (конфиг) → #192 (crash) → #191 (updater) →
   #200 (DPI).
3. **Флагманы функциональности**: #188 (многодорожечный аудио) →
   #187 (скриншот) → #193 (AI-главы/саммари/поиск).
4. **Продвинутые**: #194 (пост-редактор) → #195 (хоткеи) → #196
   (MKV/кодирование) → #197 (стриминг) → #198 (scopes/аудит).
5. **Полировка**: #201, #202, #203, #204, #205, #207, #208, #209.

## Что сознательно НЕ включено

- **Сцены/композитор как в OBS** (несколько источников в один кадр) —
  вне DNA продукта (recorder, не студия); PiP-камера (#165) уже
  закрывает типовой случай.
- **HDR/10-bit захват** — сложный WGC HDR-пайплайн при недоказанном
  спросе; вернуться при запросах пользователей.
- **Телеметрия/аналитика** — осознанный privacy-friendly выбор;
  отсутствие данных о падениях закрывается #192.
- **Языки сверх ru/en** — пользователей не подтверждено (решение
  2026-11-04 остаётся в силе).
- **MSIX/Store/chocolatey/scoop** — winget (#207) покрывает основную
  дистрибуцию; Store — только при доказанном спросе.
- **Фильтрация подписок WebSocket по типам событий, heartbeat** —
  мелочь, отложено без отдельного issue.
- **Dropbox/прямая загрузка на YouTube** — S3/GDrive/OneDrive/WebDAV
  уже покрывают облако; YouTube API требует OAuth-клиента и ревью.
