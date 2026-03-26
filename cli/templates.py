"""
Шаблоны расписаний для CLI.

Предоставляет предустановленные шаблоны для часто используемых расписаний.
"""

from typing import Any

SCHEDULE_TEMPLATES: dict[str, dict[str, Any]] = {
    "once": {
        "trigger": "once",
        "description": "Разовый запуск в указанное время",
        "required": ["datetime"],
        "example": "--trigger once --datetime '2026-01-20 09:30'",
    },
    "daily": {
        "trigger": "daily",
        "description": "Ежедневно в указанное время",
        "required": ["time"],
        "example": "--trigger daily --time '09:30'",
    },
    "weekly": {
        "trigger": "weekly",
        "description": "Еженедельно в указанные дни",
        "required": ["time", "days"],
        "example": "--trigger weekly --time '14:00' --days '0,2,4'",
    },
    "interval": {
        "trigger": "interval",
        "description": "Через указанный интервал",
        "required": ["interval-hours или interval-minutes"],
        "example": "--trigger interval --interval-hours 2",
    },
    "cron": {
        "trigger": "cron",
        "description": "Cron выражение (для продвинутых пользователей)",
        "required": ["cron-выражение"],
        "example": "--trigger cron --schedule '0 9 * * 1-5'",
    },
}

# Предустановленные шаблоны для часто используемых сценариев
PRESET_TEMPLATES: dict[str, dict[str, Any]] = {
    "workday-morning": {
        "name": "Ежедневный утренний стендап",
        "trigger": "daily",
        "time": "09:30",
        "params": {
            "area": "full",
            "audio": "mic",
            "duration": 1800,  # 30 минут
        },
    },
    "workday-evening": {
        "name": "Ежедневный вечерний отчёт",
        "trigger": "daily",
        "time": "18:00",
        "params": {
            "area": "full",
            "audio": "mic",
            "duration": 900,  # 15 минут
        },
    },
    "weekly-meeting": {
        "name": "Еженедельная встреча",
        "trigger": "weekly",
        "time": "14:00",
        "days_of_week": [0, 2, 4],  # Пн, Ср, Пт
        "params": {
            "area": "window",
            "audio": "both",
            "duration": 3600,  # 1 час
        },
    },
    "hourly-screenshot": {
        "name": "Ежечасный скриншот",
        "trigger": "interval",
        "interval_hours": 1,
        "params": {
            "area": "full",
            "audio": "none",
            "duration": 10,  # 10 секунд
        },
    },
    "30min-interval": {
        "name": "Каждые 30 минут",
        "trigger": "interval",
        "interval_minutes": 30,
        "params": {
            "area": "full",
            "audio": "none",
            "duration": 60,  # 1 минута
        },
    },
}


def get_template(name: str) -> dict[str, Any] | None:
    """Получение шаблона по имени.

    Args:
        name: Имя шаблона (например, "daily")

    Returns:
        Словарь с параметрами шаблона или None если не найден
    """
    return SCHEDULE_TEMPLATES.get(name)


def get_preset(name: str) -> dict[str, Any] | None:
    """Получение preset шаблона по имени.

    Args:
        name: Имя preset (например, "workday-morning")

    Returns:
        Словарь с параметрами preset или None если не найден
    """
    return PRESET_TEMPLATES.get(name)


def list_templates() -> list[dict[str, Any]]:
    """Получение списка всех доступных шаблонов.

    Returns:
        Список словарей с информацией о шаблонах
    """
    result = []
    for name, template in SCHEDULE_TEMPLATES.items():
        result.append(
            {
                "name": name,
                "trigger": template["trigger"],
                "description": template["description"],
                "required": template["required"],
                "example": template["example"],
            }
        )
    return result


def list_presets() -> list[dict[str, Any]]:
    """Получение списка всех preset шаблонов.

    Returns:
        Список словарей с информацией о presets
    """
    result = []
    for name, preset in PRESET_TEMPLATES.items():
        result.append(
            {
                "name": name,
                "display_name": preset["name"],
                "trigger": preset["trigger"],
                "params": preset.get("params", {}),
            }
        )
    return result


def print_templates_help() -> None:
    """Вывод справки по шаблонам в консоль."""
    print("Доступные триггеры для расписания:")
    print("-" * 70)
    print(f"{'Триггер':<12} {'Описание':<35} {'Пример'}")
    print("-" * 70)

    for name, template in SCHEDULE_TEMPLATES.items():
        print(f"{name:<12} {template['description']:<35}")
        print(f"{'':>12} Пример: {template['example']}")
        print()


def print_presets_help() -> None:
    """Вывод справки по preset шаблонам в консоль."""
    print("Доступные preset шаблоны:")
    print("-" * 70)
    print(f"{'Preset':<25} {'Триггер':<12} {'Описание'}")
    print("-" * 70)

    for name, preset in PRESET_TEMPLATES.items():
        trigger_info = preset["trigger"]
        if preset["trigger"] == "weekly" and "days_of_week" in preset:
            days = ", ".join(str(d) for d in preset["days_of_week"])
            trigger_info = f"weekly ({days})"
        elif preset["trigger"] == "interval":
            if preset.get("interval_hours"):
                trigger_info = f"every {preset['interval_hours']}h"
            elif preset.get("interval_minutes"):
                trigger_info = f"every {preset['interval_minutes']}m"

        print(f"{name:<25} {trigger_info:<12} {preset['name']}")

    print()
    print("Использование:")
    print("  python main.py --schedule-create --preset workday-morning")


if __name__ == "__main__":
    print_templates_help()
    print()
    print_presets_help()
