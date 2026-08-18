import json
import subprocess


def run_cmd(cmd):
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding="utf-8"
    )
    if result.returncode != 0:
        print(f"Error running {' '.join(cmd)}: {result.stderr}")
    return result.stdout.strip()


def create_milestone(title, description):
    print(f"Creating milestone: {title}")
    out = run_cmd(
        [
            "gh",
            "api",
            "repos/{owner}/{repo}/milestones",
            "-f",
            f"title={title}",
            "-f",
            "state=open",
            "-f",
            f"description={description}",
        ]
    )
    if out:
        try:
            return json.loads(out).get("number")
        except json.JSONDecodeError:
            pass
    return None


def create_issue(title, body, labels, milestone):
    print(f"Creating issue: {title}")
    cmd = [
        "gh",
        "issue",
        "create",
        "--title",
        title,
        "--body",
        body,
        "--label",
        labels,
    ]
    if milestone:
        cmd.extend(["--milestone", str(milestone)])
    run_cmd(cmd)


# Milestones
m1 = create_milestone(
    "Phase 1: Performance & UX (Q3-Q4 2026)",
    "Аппаратное ускорение, техдолг API и Windows 11 UX.",
)
m2 = create_milestone(
    "Phase 2: AI-First Features (Q1-Q2 2027)",
    "AI аудио, умный монтаж, Whisper транскрипция, семантический поиск.",
)
m3 = create_milestone(
    "Phase 3: Cloud & Collaboration (Q3 2027)",
    "S3 интеграции, редактор постобработки.",
)
m4 = create_milestone(
    "Phase 4: Enterprise & Streaming (Q4 2027)",
    "Live streaming, Service mode, плагины.",
)

# Issues Phase 1
create_issue(
    "Feature: Аппаратное ускорение кодирования (NVENC, AMF, QSV)",
    "## Описание\nВнедрить поддержку аппаратного ускорения (Hardware Encoding) для FFmpeg. Текущий программный кодек `libx264` сильно нагружает CPU. Необходимо использовать возможности видеокарт пользователя.\n\n## Задачи\n- [ ] Определение поддерживаемых кодеков (NVIDIA NVENC, AMD AMF, Intel QSV).\n- [ ] Интеграция `hevc_nvenc`, `h264_nvenc` и т.д. в команду FFmpeg.\n- [ ] Fallback на `libx264` при отсутствии поддерживаемой GPU.\n- [ ] Добавление переключателя 'Аппаратное ускорение' в настройки GUI.",
    "enhancement,performance",
    m1,
)

create_issue(
    "UX: Модернизация GUI до стандартов Windows 11 (Mica/Acrylic)",
    "## Описание\nОбновление внешнего вида приложения до современных стандартов Windows 11.\n\n## Задачи\n- [ ] Использование Mica/Acrylic материалов для главного окна.\n- [ ] Скругленные углы, плавная анимация.\n- [ ] Улучшение плавающего виджета записи, добавление инструментов рисования на экране.",
    "enhancement,gui",
    m1,
)

# Issues Phase 2
create_issue(
    "AI Feature: Умное шумоподавление аудио в реальном времени",
    "## Описание\nИнтеграция локальных ИИ моделей для подавления шумов микрофона (стук клавиатуры, эхо, фон) в реальном времени.\n\n## Задачи\n- [ ] Исследование легковесных моделей шумоподавления для Python/Windows.\n- [ ] Внедрение фильтра аудио через виртуальный кабель или фильтры FFmpeg (arnndn).\n- [ ] Тоггл в настройках звука 'AI Шумоподавление'.",
    "enhancement,ai,audio",
    m2,
)

create_issue(
    "AI Feature: Smart Zoom (Автоматический наезд камеры на курсор)",
    "## Описание\nАвтоматический анализ движения мыши (событий клика и ввода) во время записи, и генерация 'наездов' камеры (Smart Zoom) при постобработке.\n\n## Задачи\n- [ ] Трекинг координат курсора во время записи (новый сервис).\n- [ ] Алгоритм создания ключевых кадров для наезда камеры (zoom).\n- [ ] Применение фильтров crop/zoompan через FFmpeg.",
    "enhancement,ai,video",
    m2,
)

create_issue(
    "AI Feature: Локальная транскрипция аудио через Whisper.cpp",
    "## Описание\nИнтеграция локальной модели Whisper.cpp для генерации субтитров (.srt/.vtt) без интернета.\n\n## Задачи\n- [ ] Интеграция бинарников или python-биндингов whisper.cpp.\n- [ ] Внедрение шага транскрипции в пайплайн обработки записи.\n- [ ] Настройки модели (tiny, base, small) и языка.",
    "enhancement,ai,audio",
    m2,
)

create_issue(
    "AI Feature: Генерация Summary и таймкодов записи",
    "## Описание\nИспользование LLM (локальных или API) для создания Summary (главных мыслей), Action Items и таймкодов (глав) на основе транскрипции.\n\n## Задачи\n- [ ] Интеграция с Ollama (локально) / OpenAI API (облако).\n- [ ] Составление промпта для суммаризации текста.\n- [ ] Вывод результата пользователю по окончанию записи.",
    "enhancement,ai",
    m2,
)

create_issue(
    "AI Feature: Privacy Blur (авто-размытие данных)",
    "## Описание\nЛокальное распознавание и блюр приватных данных на видео.\n\n## Задачи\n- [ ] Распознавание лиц, email, паролей.\n- [ ] Применение эффекта размытия при постобработке.",
    "enhancement,ai,video",
    m2,
)

# Issues Phase 3
create_issue(
    "Feature: Модульная авто-загрузка (S3, GDrive, OneDrive)",
    "## Описание\nЗагрузка записи в облако сразу после окончания и копирование ссылки в буфер обмена.",
    "enhancement,cloud",
    m3,
)

create_issue(
    "Feature: Легкий Post-Recording Редактор (обрезка, аннотации)",
    "## Описание\nВстроенный редактор для быстрого тримминга и кропа видео с помощью FFmpeg (без перекодирования).",
    "enhancement,gui",
    m3,
)

# Issues Phase 4
create_issue(
    "Feature: Поддержка RTMP/HLS Streaming",
    "## Описание\nТрансляция видеопотока на сервера вроде Twitch или YouTube.",
    "enhancement,core",
    m4,
)

create_issue(
    "Feature: Service Mode (Запуск ядра как службы Windows)",
    "## Описание\nОтвязка от сессии пользователя, работа в фоне для мониторинга серверов.",
    "enhancement,architecture",
    m4,
)

print("Все issues и milestones созданы!")
