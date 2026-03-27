"""
CLI функции для работы с планировщиком задач.
=============================================

Реализует CRUD операции для запланированных задач через API.
"""

import json
import os
import sys
from datetime import datetime
from typing import Any

from logger_config import get_module_logger

logger = get_module_logger(__name__)


def get_api_headers() -> dict[str, str]:
    """
    Получение заголовков для API запросов с аутентификацией.

    Returns:
        Словарь с заголовками, включая API ключ если он установлен.
    """
    from api.auth import API_KEY_ENV_VAR, API_KEY_HEADER

    api_key = os.environ.get(API_KEY_ENV_VAR)
    if api_key:
        return {API_KEY_HEADER: api_key}
    return {}


def _make_api_request(
    method: str,
    endpoint: str,
    config: dict[str, Any],
    data: dict[str, Any] | None = None,
) -> tuple[int, dict[str, Any]]:
    """
    Выполняет API запрос.

    Args:
        method: HTTP метод (GET, POST, PUT, DELETE)
        endpoint: Эндпоинт API (без базового URL)
        config: Конфигурация с API хостом и портом
        data: Данные для отправки (для POST/PUT)

    Returns:
        Кортеж (status_code, response_data)
    """
    try:
        import requests
    except ImportError:
        print(
            "Ошибка: библиотека requests недоступна. "
            "Установите: pip install requests",
            file=sys.stderr,
        )
        return 1, {"error": "requests недоступен"}

    api_url = f"http://{config['api']['host']}:{config['api']['port']}"
    url = f"{api_url}{endpoint}"
    headers = get_api_headers()

    try:
        if method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        elif method == "POST":
            response = requests.post(
                url, json=data, headers=headers, timeout=10
            )
        elif method == "PUT":
            response = requests.put(
                url, json=data, headers=headers, timeout=10
            )
        elif method == "DELETE":
            response = requests.delete(url, headers=headers, timeout=10)
        else:
            return 1, {"error": f"Неподдерживаемый метод: {method}"}

        return response.status_code, response.json()

    except requests.exceptions.ConnectionError:
        return 503, {"error": "API сервер не доступен"}
    except requests.exceptions.Timeout:
        return 504, {"error": "Таймаут запроса"}
    except json.JSONDecodeError:
        return 500, {"error": "Некорректный JSON ответ"}
    except Exception as e:
        return 500, {"error": str(e)}


def create_schedule(config: dict[str, Any]) -> int:
    """
    Создание новой запланированной задачи через CLI.

    Args:
        config: Конфигурация с параметрами задачи

    Returns:
        Код выхода (0 - успех, 1 - ошибка)
    """
    scheduler_config = config.get("scheduler", {})
    recording_config = config.get("recording", {})

    # Проверка на preset
    preset_name = scheduler_config.get("preset")
    if preset_name:
        from cli.templates import get_preset

        preset = get_preset(preset_name)
        if not preset:
            print(
                f"Ошибка: Preset '{preset_name}' не найден",
                file=sys.stderr,
            )
            return 1

        # Используем preset как базу, переопределяем параметрами из CLI
        task_data = dict(preset)
        if scheduler_config.get("name"):
            task_data["name"] = scheduler_config["name"]

        # Переопределение параметров из CLI
        cli_params = {}
        if recording_config.get("area_type"):
            cli_params["area"] = recording_config["area_type"]
        if recording_config.get("audio_type"):
            cli_params["audio"] = recording_config["audio_type"]
        if recording_config.get("duration"):
            cli_params["duration"] = recording_config["duration"]

        if cli_params:
            if "params" not in task_data:
                task_data["params"] = {}
            task_data["params"].update(cli_params)
    else:
        # Формирование данных задачи без preset
        task_data = {
            "name": scheduler_config.get("name", "Запланированная запись"),
            "enabled": scheduler_config.get("enabled", True),
        }

    # Определение триггера
    trigger = scheduler_config.get("trigger")
    if scheduler_config.get("cron"):
        task_data["trigger"] = "cron"
        task_data["cron_expression"] = scheduler_config["cron"]
    elif trigger:
        task_data["trigger"] = trigger

        if trigger == "once":
            datetime_str = scheduler_config.get("datetime")
            if not datetime_str:
                print(
                    "Ошибка: Для триггера 'once' требуется параметр --datetime",
                    file=sys.stderr,
                )
                return 1
            task_data["datetime"] = datetime_str

        elif trigger in ("daily", "weekly"):
            time_str = scheduler_config.get("time")
            if not time_str:
                print(
                    f"Ошибка: Для триггера '{trigger}' требуется параметр --time",
                    file=sys.stderr,
                )
                return 1
            task_data["time"] = time_str

            if trigger == "weekly":
                days = scheduler_config.get("days_of_week")
                if not days:
                    print(
                        "Ошибка: Для триггера 'weekly' требуется параметр --days",
                        file=sys.stderr,
                    )
                    return 1
                task_data["days_of_week"] = days

        elif trigger == "interval":
            hours = scheduler_config.get("interval_hours", 0)
            minutes = scheduler_config.get("interval_minutes", 0)
            if hours == 0 and minutes == 0:
                print(
                    "Ошибка: Для триггера 'interval' требуется --interval-hours или --interval-minutes",
                    file=sys.stderr,
                )
                return 1
            task_data["hours"] = hours
            task_data["minutes"] = minutes

    # Параметры записи
    task_data["params"] = {
        "area": recording_config.get("area_type", "full"),
        "window_title": recording_config.get("window_title"),
        "rect": recording_config.get("rect_coords"),
        "audio": recording_config.get("audio_type", "none"),
        "output_path": recording_config.get("output_path"),
        "fps": recording_config.get("fps", 30),
        "codec": recording_config.get("codec", "libx264"),
        "bitrate": recording_config.get("bitrate", "2M"),
        "duration": recording_config.get("duration"),
    }

    # Удаление None значений
    task_data["params"] = {
        k: v for k, v in task_data["params"].items() if v is not None
    }

    # Отправка запроса
    status_code, response = _make_api_request(
        "POST",
        "/api/schedule",
        config,
        task_data,
    )

    if status_code == 401:
        print(
            "Ошибка: Требуется аутентификация. Установите переменную окружения "
            "MIA_SCREEN_CAPTURE_API_KEY",
            file=sys.stderr,
        )
        return 1

    if status_code == 200 and response.get("success"):
        task_id = response.get("data", {}).get("task_id")
        print(f"Задача создана: {task_id}")
        return 0
    else:
        error = response.get("error", "Неизвестная ошибка")
        print(f"Ошибка создания задачи: {error}", file=sys.stderr)
        return 1


def update_schedule(config: dict[str, Any]) -> int:
    """
    Обновление запланированной задачи через CLI.

    Args:
        config: Конфигурация с параметрами задачи

    Returns:
        Код выхода (0 - успех, 1 - ошибка)
    """
    scheduler_config = config.get("scheduler", {})
    recording_config = config.get("recording", {})

    task_id = scheduler_config.get("task_id")
    if not task_id:
        print("Ошибка: Не указан ID задачи", file=sys.stderr)
        return 1

    # Формирование данных для обновления
    task_data: dict[str, Any] = {"id": task_id}

    if scheduler_config.get("name"):
        task_data["name"] = scheduler_config["name"]

    if scheduler_config.get("enabled") is not None:
        task_data["enabled"] = scheduler_config["enabled"]

    if scheduler_config.get("time"):
        task_data["time"] = scheduler_config["time"]

    if scheduler_config.get("days_of_week"):
        task_data["days_of_week"] = scheduler_config["days_of_week"]

    # Параметры записи
    params = {}
    if recording_config.get("area_type"):
        params["area"] = recording_config["area_type"]
    if recording_config.get("audio_type"):
        params["audio"] = recording_config["audio_type"]
    if recording_config.get("duration"):
        params["duration"] = recording_config["duration"]

    if params:
        task_data["params"] = params

    # Отправка запроса
    status_code, response = _make_api_request(
        "PUT",
        f"/api/schedule/{task_id}",
        config,
        task_data,
    )

    if status_code == 200 and response.get("success"):
        print(f"Задача обновлена: {task_id}")
        return 0
    else:
        error = response.get("error", "Неизвестная ошибка")
        print(f"Ошибка обновления задачи: {error}", file=sys.stderr)
        return 1


def delete_schedule(config: dict[str, Any]) -> int:
    """
    Удаление запланированной задачи через CLI.

    Args:
        config: Конфигурация с ID задачи

    Returns:
        Код выхода (0 - успех, 1 - ошибка)
    """
    scheduler_config = config.get("scheduler", {})
    task_id = scheduler_config.get("task_id")

    if not task_id:
        print("Ошибка: Не указан ID задачи", file=sys.stderr)
        return 1

    # Отправка запроса
    status_code, response = _make_api_request(
        "DELETE",
        f"/api/schedule/{task_id}",
        config,
    )

    if status_code == 200 and response.get("success"):
        print(f"Задача удалена: {task_id}")
        return 0
    else:
        error = response.get("error", "Неизвестная ошибка")
        print(f"Ошибка удаления задачи: {error}", file=sys.stderr)
        return 1


def toggle_schedule(config: dict[str, Any]) -> int:
    """
    Включение/выключение запланированной задачи через CLI.

    Args:
        config: Конфигурация с ID задачи и состоянием

    Returns:
        Код выхода (0 - успех, 1 - ошибка)
    """
    scheduler_config = config.get("scheduler", {})
    task_id = scheduler_config.get("task_id")
    enabled = scheduler_config.get("enabled", True)

    if not task_id:
        print("Ошибка: Не указан ID задачи", file=sys.stderr)
        return 1

    # Отправка запроса
    status_code, response = _make_api_request(
        "POST",
        f"/api/schedule/{task_id}/toggle",
        config,
        {"enabled": enabled},
    )

    if status_code == 200 and response.get("success"):
        state = "включена" if enabled else "выключена"
        print(f"Задача {task_id} {state}")
        return 0
    else:
        error = response.get("error", "Неизвестная ошибка")
        print(f"Ошибка переключения задачи: {error}", file=sys.stderr)
        return 1


def preview_upcoming_runs(config: dict[str, Any], count: int = 5) -> int:
    """
    Показать предстоящие запуски задач.

    Args:
        config: Конфигурация
        count: Количество запусков для показа

    Returns:
        Код выхода (0 - успех, 1 - ошибка)
    """

    # Получение списка задач
    status_code, response = _make_api_request(
        "GET",
        "/api/schedule",
        config,
    )

    if status_code != 200 or not response.get("success"):
        error = response.get("error", "Неизвестная ошибка")
        print(f"Ошибка получения задач: {error}", file=sys.stderr)
        return 1

    tasks = response.get("data", [])

    # Фильтрация и сортировка по next_run
    upcoming = []
    for task in tasks:
        if task.get("enabled") and task.get("next_run"):
            upcoming.append(task)

    upcoming.sort(key=lambda x: x.get("next_run", ""))
    upcoming = upcoming[:count]

    if not upcoming:
        print("Нет предстоящих запусков")
        return 0

    print(f"Предстоящие запуски (показано {len(upcoming)} из {count}):")
    print("-" * 70)
    print(f"{'ID':<12} {'Имя':<25} {'Следующий запуск':<20} {'Тип':<10}")
    print("-" * 70)

    for task in upcoming:
        task_id = task.get("id", "")[:10]
        name = task.get("name", "")[:23]
        next_run = task.get("next_run", "")[:19]
        task_type = task.get("schedule_type", "")
        print(f"{task_id:<12} {name:<25} {next_run:<20} {task_type:<10}")

    return 0


def validate_schedule_params(params: dict[str, Any]) -> tuple[bool, str]:
    """
    Валидация параметров расписания.

    Args:
        params: Словарь параметров расписания

    Returns:
        Кортеж (валиден, сообщение_об_ошибке)
    """
    import re

    errors = []

    # Проверка времени
    if "time" in params:
        time_str = params["time"]
        if not re.match(r"^\d{2}:\d{2}$", time_str):
            errors.append(
                f"Время должно быть в формате HH:MM (например, '09:30'), "
                f"получено: '{time_str}'"
            )
        else:
            hour, minute = map(int, time_str.split(":"))
            if hour < 0 or hour > 23:
                errors.append(f"Час должен быть 0-23, получено: {hour}")
            if minute < 0 or minute > 59:
                errors.append(f"Минута должна быть 0-59, получено: {minute}")

    # Проверка дней недели
    if "days_of_week" in params:
        days = params["days_of_week"]
        if isinstance(days, str):
            try:
                days = [int(d.strip()) for d in days.split(",")]
            except ValueError:
                errors.append(
                    f"Дни недели должны быть числами через запятую (0-6), "
                    f"получено: '{days}'"
                )
                days = []

        for day in days:
            if day < 0 or day > 6:
                errors.append(
                    f"День недели должен быть 0-6 (0=Пн, 6=Вс), получено: {day}"
                )

    # Проверка datetime
    if "datetime" in params:
        datetime_str = params["datetime"]
        try:
            datetime.strptime(datetime_str, "%Y-%m-%d %H:%M")
        except ValueError:
            errors.append(
                f"Datetime должен быть в формате 'YYYY-MM-DD HH:MM' "
                f"(например, '2026-01-20 09:30'), получено: '{datetime_str}'"
            )

    # Проверка интервала
    hours = params.get("interval_hours", 0)
    minutes = params.get("interval_minutes", 0)
    if hours < 0 or minutes < 0:
        errors.append("Интервал должен быть положительным числом")
    elif hours == 0 and minutes == 0 and params.get("trigger") == "interval":
        errors.append(
            "Для интервального расписания укажите --interval-hours или --interval-minutes "
            "(например, --interval-hours 1 или --interval-minutes 30)"
        )

    # Проверка cron выражения
    if "cron_expression" in params:
        cron = params["cron_expression"]
        if not re.match(r"^[\d\*\/\-,\s]+$", cron):
            errors.append(
                f"Cron выражение содержит недопустимые символы: '{cron}'\n"
                f"Примеры cron: '0 9 * * 1-5' (каждый будний день в 9:00), "
                f"'*/30 * * * *' (каждые 30 минут)"
            )

    if errors:
        return False, "\n".join(errors)

    return True, ""
