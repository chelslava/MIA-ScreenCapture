# Скрипт создания GitHub Milestones и Issues для Roadmap 2026-2027

Write-Host "Создание Milestones..."

# Фаза 1
gh api repos/{owner}/{repo}/milestones -f title="Phase 1: Performance & UX (Q3-Q4 2026)" -f state="open" -f description="Аппаратное ускорение, техдолг API и Windows 11 UX." --silent
$m1 = (gh api repos/{owner}/{repo}/milestones -q ".[0].number")

# Фаза 2
gh api repos/{owner}/{repo}/milestones -f title="Phase 2: AI-First Features (Q1-Q2 2027)" -f state="open" -f description="AI аудио, умный монтаж, Whisper транскрипция, семантический поиск." --silent
$m2 = (gh api repos/{owner}/{repo}/milestones -q ".[0].number")

# Фаза 3
gh api repos/{owner}/{repo}/milestones -f title="Phase 3: Cloud & Collaboration (Q3 2027)" -f state="open" -f description="S3 интеграции, редактор постобработки." --silent
$m3 = (gh api repos/{owner}/{repo}/milestones -q ".[0].number")

# Фаза 4
gh api repos/{owner}/{repo}/milestones -f title="Phase 4: Enterprise & Streaming (Q4 2027)" -f state="open" -f description="Live streaming, Service mode, плагины." --silent
$m4 = (gh api repos/{owner}/{repo}/milestones -q ".[0].number")

Write-Host "Создание Issues для Фазы 1..."

$i1_1 = @"
## Описание
Внедрить поддержку аппаратного ускорения (Hardware Encoding) для FFmpeg.
Текущий программный кодек `libx264` сильно нагружает CPU. Необходимо использовать возможности видеокарт пользователя.

## Задачи
- [ ] Определение поддерживаемых кодеков (NVIDIA NVENC, AMD AMF, Intel QSV).
- [ ] Интеграция `hevc_nvenc`, `h264_nvenc` и т.д. в команду FFmpeg.
- [ ] Fallback на `libx264` при отсутствии поддерживаемой GPU.
- [ ] Добавление переключателя "Аппаратное ускорение" в настройки GUI.
"@
gh issue create --title "Feature: Аппаратное ускорение кодирования (NVENC, AMF, QSV)" --body $i1_1 --label "enhancement,performance" --milestone $m1

$i1_2 = @"
## Описание
Обновление внешнего вида приложения до современных стандартов Windows 11.

## Задачи
- [ ] Использование Mica/Acrylic материалов для главного окна.
- [ ] Скругленные углы, плавная анимация.
- [ ] Улучшение плавающего виджета записи, добавление инструментов рисования на экране.
"@
gh issue create --title "UX: Модернизация GUI до стандартов Windows 11 (Mica/Acrylic)" --body $i1_2 --label "enhancement,gui" --milestone $m1

Write-Host "Создание Issues для Фазы 2 (AI)..."

$i2_1 = @"
## Описание
Интеграция локальных ИИ моделей (например, RNNoise) для подавления шумов микрофона (стук клавиатуры, эхо, фон) в реальном времени.

## Задачи
- [ ] Исследование легковесных моделей шумоподавления для Python/Windows.
- [ ] Внедрение фильтра аудио через виртуальный кабель или фильтры FFmpeg (arnndn).
- [ ] Тоггл в настройках звука "AI Шумоподавление".
"@
gh issue create --title "AI Feature: Умное шумоподавление аудио в реальном времени" --body $i2_1 --label "enhancement,ai,audio" --milestone $m2

$i2_2 = @"
## Описание
Автоматический анализ движения мыши (событий клика и ввода) во время записи, и генерация "наездов" камеры (Smart Zoom) при постобработке.

## Задачи
- [ ] Трекинг координат курсора во время записи (новый сервис).
- [ ] Алгоритм создания ключевых кадров для наезда камеры (zoom).
- [ ] Применение фильтров crop/zoompan через FFmpeg.
"@
gh issue create --title "AI Feature: Smart Zoom (Автоматический наезд камеры на курсор)" --body $i2_2 --label "enhancement,ai,video" --milestone $m2

$i2_3 = @"
## Описание
Интеграция локальной модели Whisper.cpp для генерации субтитров (.srt/.vtt) без интернета.

## Задачи
- [ ] Интеграция бинарников или python-биндингов whisper.cpp.
- [ ] Внедрение шага транскрипции в пайплайн обработки записи.
- [ ] Настройки модели (tiny, base, small) и языка.
"@
gh issue create --title "AI Feature: Локальная транскрипция аудио через Whisper.cpp" --body $i2_3 --label "enhancement,ai,audio" --milestone $m2

$i2_4 = @"
## Описание
Использование LLM (локальных или API) для создания Summary (главных мыслей), Action Items и таймкодов (глав) на основе транскрипции.

## Задачи
- [ ] Интеграция с Ollama (локально) / OpenAI API (облако).
- [ ] Составление промпта для суммаризации текста.
- [ ] Вывод результата пользователю по окончанию записи.
"@
gh issue create --title "AI Feature: Генерация Summary и таймкодов записи" --body $i2_4 --label "enhancement,ai" --milestone $m2

$i2_5 = @"
## Описание
Локальное распознавание и блюр приватных данных на видео.

## Задачи
- [ ] Распознавание лиц, email, паролей.
- [ ] Применение эффекта размытия при постобработке.
"@
gh issue create --title "AI Feature: Privacy Blur (авто-размытие данных)" --body $i2_5 --label "enhancement,ai,video" --milestone $m2

Write-Host "Создание Issues для Фазы 3..."
gh issue create --title "Feature: Модульная авто-загрузка (S3, GDrive, OneDrive)" --body "Загрузка записи в облако сразу после окончания и копирование ссылки в буфер обмена." --label "enhancement,cloud" --milestone $m3
gh issue create --title "Feature: Легкий Post-Recording Редактор (обрезка, аннотации)" --body "Встроенный редактор для быстрого тримминга и кропа видео с помощью FFmpeg (без перекодирования)." --label "enhancement,gui" --milestone $m3

Write-Host "Создание Issues для Фазы 4..."
gh issue create --title "Feature: Поддержка RTMP/HLS Streaming" --body "Трансляция видеопотока на сервера вроде Twitch или YouTube." --label "enhancement,core" --milestone $m4
gh issue create --title "Feature: Service Mode (Запуск ядра как службы Windows)" --body "Отвязка от сессии пользователя, работа в фоне для мониторинга серверов." --label "enhancement,architecture" --milestone $m4

Write-Host "Готово!"
