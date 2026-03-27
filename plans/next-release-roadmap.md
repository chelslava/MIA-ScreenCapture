# Roadmap: Release Train 2026

## Контекст

Этот документ описывает ближайший практический цикл развития `MIA-ScreenCapture` после `v1.3.0`.

**⚠️ Важно:** Проект работает **исключительно на Windows 10/11**. Используется Windows Graphics Capture API через библиотеку `windows-capture`. Поддержка Linux/macOS не планируется.

Фокус roadmap:
- убрать архитектурную связность между `core` и `gui`
- выровнять UX и контракты между GUI, API, CLI и scheduler
- усилить release engineering и предсказуемость поставки
- подготовить базу для real-time интеграций и более зрелой дистрибуции

## Принципы

- Сначала закрываются риски надежности и архитектурные зависимости, затем добавляются новые feature-слои.
- Каждый релиз должен оставаться usable, а не быть промежуточной недоделанной стадией.
- Scope фиксируется заранее; переносы и исключения отмечаются явно.
- Готовность релиза подтверждается воспроизводимым прогоном тестов и quality gates.

## Релизный ритм

Для ближайших 4 релизов используется одинаковый ритм фиксации:

1. `Scope Freeze`
   Список задач релиза зафиксирован. Новая feature-задача может попасть в релиз только вместо другой задачи того же уровня.
2. `Code Freeze`
   Разрешены только bugfix, тесты, документация и release-note изменения.
3. `RC`
   Выпущен release candidate. Открыты только regression и release-blocker дефекты.
4. `GA`
   Финальная поставка, обновление changelog и status-analysis.

Рекомендуемая длина цикла:
- patch-релизы: 1 неделя реализации + 2 дня stabilization
- minor-релизы: 2-3 недели реализации + 3-5 дней stabilization

## Release 1: `v1.3.1` - Core decoupling and stability

### Цель релиза

Сделать сервисный путь записи независимым от GUI-слоя и зафиксировать устойчивый headless/API сценарий без регрессии текущего GUI.

### Критерии готовности

- `core/recording_service.py` больше не зависит от GUI-моделей состояния.
- Shared-модель состояния записи живет в `core`.
- Введен backend-контракт записи, который можно подменять в сервисных тестах.
- Существующие GUI-, API- и integration-сценарии проходят без поведенческой регрессии.

### Точки фиксации

- `Scope Freeze`: shared state вынесен в `core`, зафиксирован целевой backend-контракт.
- `Code Freeze`: `RecordingService` использует backend-адаптер вместо прямой GUI-связности.
- `RC`: проходят targeted unit/integration тесты для service/API/GUI controller path.
- `GA`: обновлены changelog и status-analysis по архитектурному изменению.

### Задачи по приоритету

1. Вынести модель состояния записи и связанные типы из `gui` в `core` с совместимым импортом.
2. Ввести `RecordingBackend` как core-контракт исполнения записи.
3. Реализовать `GUIRecordingBackend` как адаптер к текущему `RecordingController`.
4. Перевести `RecordingService` на backend-зависимость и обновить его тесты.
5. Сузить роль `core/recording_mapper.py` или удалить его, если он перестанет быть нужен.
6. Подготовить следующий вынос orchestration из `main.py` в отдельный application/bootstrap слой.

### Release blockers

- Любая прямая зависимость `core` от `gui` в сервисном пути записи.
- Непокрытый тестами backend-адаптер.
- Поведенческая регрессия `start/stop/pause/status`.

## Release 2: `v1.3.2` - CLI/API parity and scheduler usability

### Цель релиза

Сделать автоматизацию через CLI, API и scheduler одинаково понятной, предсказуемой и применимой без ручного редактирования файлов конфигурации.

### Критерии готовности

- CLI поддерживает базовый CRUD для задач scheduler.
- Scheduler имеет понятный flow создания, просмотра и изменения задач.
- API, CLI и scheduler используют одинаковые payload contracts и близкие ошибки.
- Пользователь может создать и проверить автозапись без обращения к внутренним JSON-файлам.

### Точки фиксации

- `Scope Freeze`: утвержден минимальный parity scope для CLI/API/scheduler.
- `Code Freeze`: реализован CLI CRUD, preview ближайших запусков и базовая диагностика пользовательских ошибок.
- `RC`: проходят smoke-тесты CLI/API/scheduler и regression-тесты основного GUI-flow.
- `GA`: обновлены README, CLI help и release notes.

### Задачи по приоритету

1. Добавить в CLI команды создания, просмотра, изменения и удаления задач расписания.
2. Выровнять доменные payload contracts между API, CLI и scheduler.
3. Добавить preview ближайших запусков и базовую проверку конфликтов задач.
4. Добавить шаблоны типовых расписаний: once, daily, weekly, interval.
5. Улучшить ошибки пользователя и validation feedback в CLI и API.
6. Добавить smoke-тесты цепочки `scheduler -> service -> recording flow`.

### Release blockers

- CLI по-прежнему не покрывает основной automation flow.
- Scheduler parity реализован через отдельные несовместимые форматы.
- Нет smoke-проверки end-to-end пути автозаписи.

## Release 3: `v1.4.0` - UX, packaging, and release hardening

### Цель релиза

Сделать продукт проще в установке, понятнее в повседневном использовании и надежнее как релизный артефакт.

### Критерии готовности

- Есть package entry point и понятный install/run path без обязательного `python main.py`.
- README описывает один основной путь установки и запуска.
- В GUI есть базовая диагностика зависимостей и среды.
- CI стабильно прогоняет ключевые тесты, lint и typed checks перед релизом.

### Точки фиксации

- `Scope Freeze`: зафиксирован минимальный состав packaging/UX задач без расширения в redesign.
- `Code Freeze`: реализованы entry point, onboarding, диагностика и release gates.
- `RC`: green CI по test/quality jobs и воспроизводимый локальный smoke run.
- `GA`: обновлены install docs, changelog и status-analysis.

### Задачи по приоритету

1. Добавить package entry point и выровнять запуск приложения.
2. Обновить onboarding и README под один основной сценарий установки и запуска.
3. Добавить в GUI экран диагностики: FFmpeg, audio devices, API/auth, output path, scheduler status.
4. Улучшить recent recordings: метаданные, быстрые действия, фильтрация.
5. Усилить CI-гейт: `pytest`, `ruff`, `ruff format --check`, `mypy`, targeted smoke tests.
6. Снизить остаточные warnings и flaky-сценарии в критичных модулях.

### Release blockers

- Нет стабильного entry point и воспроизводимого install path.
- CI не отражает фактические требования релиза.
- Базовая диагностика среды отсутствует.

## Release 4: `v1.5.0` - Real-time platform and automation depth

### Цель релиза

Превратить проект из локального рекордера в платформу автоматизированного capture с наблюдаемым event-flow и более зрелыми unattended-сценариями.

### Критерии готовности

- Есть real-time transport для доменных событий, не завязанный на GUI.
- API поддерживает стабильный сценарий удаленного управления и наблюдения.
- Реализованы профили записи и предсказуемый post-recording flow.
- Есть минимальная стратегия управления библиотекой записей.

### Точки фиксации

- `Scope Freeze`: выбран один transport path и один минимальный automation scope.
- `Code Freeze`: transport, профили записи и базовый post-recording flow реализованы без расползания в отдельную медиаплатформу.
- `RC`: проходят event-flow и unattended-сценарии, зафиксированы API contracts.
- `GA`: опубликованы release notes и status-analysis по новой платформенной поверхности.

### Задачи по приоритету

1. Подключить полноценный live transport для доменных событий.
2. Добавить профили записи и шаблоны имен файлов.
3. Реализовать post-recording flow: auto-open, rename, convert, export presets.
4. Развить библиотеку записей: поиск, теги, preview, retention rules.
5. Усилить auth, audit и observability для удаленного сценария.
6. Подготовить основу для service mode или lightweight admin panel.

### Release blockers

- Real-time слой опирается на нестабильный внутренний контракт.
- Отсутствует базовый unattended event-flow.
- Платформенные задачи смешаны с крупным redesign и не удерживаются в scope.

## Release Gates

Перед каждым релизом должны быть выполнены одинаковые gates:

1. Пройден воспроизводимый прогон `pytest`.
2. Пройден `ruff check`.
3. Пройден `ruff format --check`.
4. Пройден `mypy` для затронутых typed-модулей или явно зафиксировано допустимое исключение.
5. Нет открытых P0/P1 дефектов в критичном пути релиза.
6. Обновлены changelog и status-analysis или другой актуальный релизный документ.
7. Для релиза зафиксированы перенесенные и отклоненные задачи, чтобы scope не размывался постфактум.

## Приоритеты по потоку работ

### Поток A. Архитектура и надежность

1. Завершить `v1.3.1`: shared state -> backend contract -> adapter -> service cleanup.
2. Затем сократить ручную сборку в `main.py` и подготовить application/bootstrap слой.
3. Только после этого расширять transport и unattended automation.

### Поток B. Автоматизация и parity

1. Довести scheduler/CLI до законченного сценария.
2. Зафиксировать единые contracts между API, CLI и scheduler.
3. После parity добавлять real-time automation.

### Поток C. Продукт и release engineering

1. Упростить install/run path и документацию.
2. Усилить CI gates и smoke-проверки.
3. Затем добавлять UX-слой диагностики и библиотеку записей.

## Рекомендуемая последовательность

1. Закрыть `v1.3.1`, чтобы убрать архитектурную связность сервисного слоя.
2. Выпустить `v1.3.2`, если нужен быстрый рост automation usability.
3. Затем идти в `v1.4.0` как релиз packaging/UX hardening.
4. Только после этого открывать `v1.5.0` как платформенный этап.
