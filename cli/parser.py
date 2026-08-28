"""
Модуль парсера CLI
==================

Разбор аргументов командной строки для видеозаписи.
Поддерживает запуск записей, проверку статуса и режим без интерфейса.
"""

import argparse
from pathlib import Path
from typing import Any

from core.i18n import _, ngettext
from logger_config import get_module_logger
from version import get_version

logger = get_module_logger(__name__)


def create_parser() -> argparse.ArgumentParser:
    """
    Создание парсера аргументов для видеозаписи.

    Returns:
        Настроенный экземпляр ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog="mia-screencapture",
        description="Профессиональный видеозаписывающий рекордер экрана с поддержкой GUI, API и CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  %(prog)s --gui                          Запуск с GUI (по умолчанию)
  %(prog)s --start                        Начать запись с параметрами по умолчанию
  %(prog)s --start --area rect --rect 100 100 800 600
  %(prog)s --start --audio mic --duration 60
  %(prog)s --stop                         Остановить текущую запись
  %(prog)s --status                       Показать статус записи
  %(prog)s --headless                     Запуск без GUI (только API)
        """,
    )

    # Выбор режима
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--gui",
        action="store_true",
        default=True,
        help="Запуск с графическим интерфейсом (по умолчанию)",
    )
    mode_group.add_argument(
        "--headless",
        action="store_true",
        help="Запуск в режиме без интерфейса (без GUI, только API)",
    )
    mode_group.add_argument(
        "--start",
        action="store_true",
        help="Начать запись немедленно с указанными параметрами",
    )
    mode_group.add_argument(
        "--stop", action="store_true", help="Остановить текущую запись"
    )
    mode_group.add_argument(
        "--status", action="store_true", help="Показать текущий статус записи"
    )
    mode_group.add_argument(
        "--schedule-list",
        action="store_true",
        help="Список запланированных задач",
    )
    mode_group.add_argument(
        "--schedule-create",
        action="store_true",
        help="Создать новую запланированную задачу",
    )
    mode_group.add_argument(
        "--schedule-update",
        type=str,
        metavar="TASK_ID",
        help="Обновить запланированную задачу по ID",
    )
    mode_group.add_argument(
        "--schedule-delete",
        type=str,
        metavar="TASK_ID",
        help="Удалить запланированную задачу по ID",
    )
    mode_group.add_argument(
        "--schedule-toggle",
        type=str,
        metavar="TASK_ID",
        help="Включить/выключить запланированную задачу",
    )
    mode_group.add_argument(
        "--schedule-preview",
        action="store_true",
        help="Показать предстоящие запуски задач",
    )
    mode_group.add_argument(
        "--list-presets",
        action="store_true",
        help="Показать список preset шаблонов",
    )
    mode_group.add_argument(
        "--plugins-list",
        action="store_true",
        help="Показать список установленных плагинов",
    )
    mode_group.add_argument(
        "--plugins-info",
        type=str,
        metavar="PLUGIN_NAME",
        help="Показать подробную информацию о плагине",
    )
    mode_group.add_argument(
        "--plugins-enable",
        type=str,
        metavar="PLUGIN_NAME",
        help="Включить плагин",
    )
    mode_group.add_argument(
        "--plugins-disable",
        type=str,
        metavar="PLUGIN_NAME",
        help="Отключить плагин",
    )
    mode_group.add_argument(
        "--service",
        type=str,
        choices=["install", "start", "stop", "restart", "uninstall", "status"],
        metavar="ACTION",
        help="Управление службой Windows (install, start, stop, restart, uninstall, status)",
    )

    parser.add_argument(
        "--service-startup",
        type=str,
        choices=["auto", "manual"],
        default="auto",
        help="Тип запуска службы Windows при установке (auto или manual, по умолчанию: auto)",
    )

    # Параметры записи
    record_group = parser.add_argument_group("Параметры записи")

    record_group.add_argument(
        "--area",
        choices=["full", "window", "rect"],
        default="full",
        help="Тип области захвата (по умолчанию: full)",
    )

    record_group.add_argument(
        "--rect",
        type=int,
        nargs=4,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Координаты прямоугольника для захвата (x1 y1 x2 y2)",
    )

    record_group.add_argument(
        "--window",
        type=str,
        metavar="TITLE",
        help="Заголовок окна для захвата (частичное совпадение)",
    )

    record_group.add_argument(
        "--audio",
        choices=["mic", "system", "none", "both"],
        default="none",
        help="Источник аудио (по умолчанию: none)",
    )

    record_group.add_argument(
        "--output",
        "-o",
        type=str,
        metavar="PATH",
        help="Путь к выходному файлу",
    )

    record_group.add_argument(
        "--fps",
        type=int,
        default=30,
        help="Кадров в секунду (по умолчанию: 30)",
    )

    record_group.add_argument(
        "--codec",
        type=str,
        default="libx264",
        help="Видеокодек (по умолчанию: libx264)",
    )

    record_group.add_argument(
        "--bitrate",
        type=str,
        default="2M",
        help="Битрейт видео (по умолчанию: 2M)",
    )

    record_group.add_argument(
        "--duration",
        "-d",
        type=int,
        metavar="SECONDS",
        help="Длительность записи в секундах",
    )

    record_group.add_argument(
        "--monitor",
        type=int,
        default=0,
        metavar="INDEX",
        help="Индекс монитора для захвата (0 = primary, по умолчанию: 0)",
    )

    record_group.add_argument(
        "--cursor",
        action="store_true",
        default=False,
        help="Включить курсор в захват (по умолчанию: выключен)",
    )

    # Конфигурация API
    api_group = parser.add_argument_group("Конфигурация API")

    api_group.add_argument(
        "--api-host",
        type=str,
        default="127.0.0.1",
        help="Хост API сервера (по умолчанию: 127.0.0.1)",
    )

    api_group.add_argument(
        "--api-port",
        type=int,
        default=5000,
        help="Порт API сервера (по умолчанию: 5000)",
    )

    api_group.add_argument(
        "--no-api", action="store_true", help="Отключить API сервер"
    )

    # Конфигурация планировщика
    scheduler_group = parser.add_argument_group("Конфигурация планировщика")

    scheduler_group.add_argument(
        "--schedule",
        type=str,
        metavar="CRON",
        help="Запланировать запись с cron выражением",
    )

    scheduler_group.add_argument(
        "--schedule-name",
        type=str,
        metavar="NAME",
        help="Имя для запланированной задачи",
    )

    scheduler_group.add_argument(
        "--trigger",
        choices=["once", "daily", "weekly", "interval", "cron"],
        help="Тип триггера для задачи (once, daily, weekly, interval, cron)",
    )

    scheduler_group.add_argument(
        "--time",
        type=str,
        metavar="HH:MM",
        help="Время запуска для daily/weekly расписания (формат: HH:MM)",
    )

    scheduler_group.add_argument(
        "--days",
        type=str,
        metavar="DAYS",
        help="Дни недели для weekly расписания (0-6, через запятую, 0=Понедельник)",
    )

    scheduler_group.add_argument(
        "--interval-hours",
        type=int,
        metavar="HOURS",
        help="Интервал в часах для interval расписания",
    )

    scheduler_group.add_argument(
        "--interval-minutes",
        type=int,
        metavar="MINUTES",
        help="Интервал в минутах для interval расписания",
    )

    scheduler_group.add_argument(
        "--datetime",
        type=str,
        metavar="DATETIME",
        help="Дата и время для once расписания (формат: YYYY-MM-DD HH:MM)",
    )

    scheduler_group.add_argument(
        "--enabled",
        type=lambda x: x.lower() in ("true", "1", "yes", "on"),
        default=True,
        help="Включить/выключить задачу (true/false, по умолчанию: true)",
    )

    scheduler_group.add_argument(
        "--preset",
        type=str,
        metavar="NAME",
        help="Использовать preset шаблон (workday-morning, weekly-meeting, etc.)",
    )

    # Другие опции
    other_group = parser.add_argument_group("Другие опции")

    other_group.add_argument(
        "--config", type=str, metavar="PATH", help="Путь к файлу конфигурации"
    )

    other_group.add_argument(
        "--verbose",
        "-v",
        action="count",
        default=0,
        help="Увеличить детальность вывода (можно использовать несколько раз)",
    )

    other_group.add_argument(
        "--quiet", "-q", action="store_true", help="Подавить вывод"
    )

    other_group.add_argument(
        "--language",
        "--lang",
        type=str,
        default=None,
        metavar="LANG",
        help="Язык интерфейса / Language (auto, en, ru)",
    )

    other_group.add_argument(
        "--version", action="version", version=f"%(prog)s {get_version()}"
    )

    return parser


def process_args(args: argparse.Namespace) -> dict[str, Any]:
    """
    Обработка разобранных аргументов и возврат словаря конфигурации.

    Args:
        args: Пространство имён разобранных аргументов

    Returns:
        Словарь с обработанной конфигурацией
    """
    config: dict[str, Any] = {
        "mode": "gui",  # Режим по умолчанию
        "recording": {},
        "api": {},
        "scheduler": {},
    }

    if getattr(args, "language", None):
        config["language"] = args.language

    # Определение режима
    if args.headless:
        config["mode"] = "headless"
    elif args.start:
        config["mode"] = "start"
    elif args.stop:
        config["mode"] = "stop"
    elif args.status:
        config["mode"] = "status"
    elif args.schedule_list:
        config["mode"] = "schedule_list"
    elif args.schedule_create:
        config["mode"] = "schedule_create"
    elif args.schedule_update:
        config["mode"] = "schedule_update"
        config["schedule"]["task_id"] = args.schedule_update
    elif args.schedule_delete:
        config["mode"] = "schedule_delete"
        config["schedule"]["task_id"] = args.schedule_delete
    elif args.schedule_toggle:
        config["mode"] = "schedule_toggle"
        config["schedule"]["task_id"] = args.schedule_toggle
    elif args.schedule_preview:
        config["mode"] = "schedule_preview"
    elif args.list_presets:
        config["mode"] = "list_presets"
    elif args.plugins_list:
        config["mode"] = "plugins_list"
    elif args.plugins_info:
        config["mode"] = "plugins_info"
        config["plugin_name"] = args.plugins_info
    elif args.plugins_enable:
        config["mode"] = "plugins_enable"
        config["plugin_name"] = args.plugins_enable
    elif args.plugins_disable:
        config["mode"] = "plugins_disable"
        config["plugin_name"] = args.plugins_disable
    elif args.service:
        config["mode"] = "service"
        config["service_action"] = args.service
        config["service_startup"] = getattr(args, "service_startup", "auto")
    else:
        config["mode"] = "gui"

        # Параметры записи
    config["recording"] = {
        "area_type": args.area,
        "rect_coords": args.rect,
        "window_title": args.window,
        "audio_type": args.audio,
        "output_path": args.output,
        "fps": args.fps,
        "codec": args.codec,
        "bitrate": args.bitrate,
        "duration": args.duration,
        "monitor_index": args.monitor,
        "include_cursor": args.cursor,
    }

    # Конфигурация API
    config["api"] = {
        "enabled": not args.no_api,
        "host": args.api_host,
        "port": args.api_port,
    }

    # Конфигурация планировщика
    config["scheduler"] = {
        "enabled": False,
        "name": args.schedule_name or "Запланированная запись",
    }

    if args.schedule:
        config["scheduler"]["enabled"] = True
        config["scheduler"]["cron"] = args.schedule

    if args.trigger:
        config["scheduler"]["enabled"] = True
        config["scheduler"]["trigger"] = args.trigger

    if args.time:
        config["scheduler"]["time"] = args.time

    if args.days:
        config["scheduler"]["days_of_week"] = [
            int(d.strip()) for d in args.days.split(",")
        ]

    if args.interval_hours is not None:
        config["scheduler"]["interval_hours"] = args.interval_hours

    if args.interval_minutes is not None:
        config["scheduler"]["interval_minutes"] = args.interval_minutes

    if args.datetime:
        config["scheduler"]["datetime"] = args.datetime

    if hasattr(args, "enabled"):
        config["scheduler"]["enabled"] = args.enabled

    if args.preset:
        config["scheduler"]["preset"] = args.preset

    # Другие опции
    config["config_path"] = args.config
    config["verbose"] = args.verbose
    config["quiet"] = args.quiet

    return config


def parse_args(argv: list[str] | None = None) -> dict[str, Any]:
    """
    Разбор аргументов командной строки.

    Args:
        argv: Список аргументов (по умолчанию: sys.argv)

    Returns:
        Словарь с разобранной конфигурацией
    """
    parser = create_parser()
    args = parser.parse_args(argv)
    return process_args(args)


def validate_recording_params(
    params: dict[str, Any],
) -> tuple[bool, str | None]:
    """
    Валидация параметров записи.

    Args:
        params: Словарь параметров записи

    Returns:
        Кортеж (валиден, сообщение_об_ошибке)
    """
    # Валидация типа области
    area_type = params.get("area_type", "full")
    if area_type not in ("full", "window", "rect"):
        return False, _("Неверный тип области: {area_type}").format(
            area_type=area_type
        )

    # Валидация координат прямоугольника
    if area_type == "rect":
        rect = params.get("rect_coords")
        if not rect or len(rect) != 4:
            return False, _(
                "Требуются координаты прямоугольника для режима rect"
            )
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            return (
                False,
                _(
                    "Неверные координаты прямоугольника (x2 должен быть > x1, y2 должен быть > y1)"
                ),
            )

    # Валидация заголовка окна
    if area_type == "window" and not params.get("window_title"):
        return False, _("Требуется заголовок окна для режима window")

    # Валидация FPS
    fps = params.get("fps", 30)
    if fps < 1 or fps > 120:
        return False, _("Неверный FPS: {fps} (должен быть 1-120)").format(
            fps=fps
        )

    # Валидация длительности
    duration = params.get("duration")
    if duration is not None and duration < 1:
        return (
            False,
            _(
                "Неверная длительность: {duration} (должна быть положительной)"
            ).format(duration=duration),
        )

    # Валидация пути вывода
    output_path = params.get("output_path")
    if output_path:
        path = Path(output_path)
        if path.exists() and not path.is_file():
            return (
                False,
                _(
                    "Путь вывода существует, но не является файлом: {output_path}"
                ).format(output_path=output_path),
            )

    return True, None


def print_status(status: dict[str, Any]) -> None:
    """
    Вывод статуса записи в консоль.

    Args:
        status: Словарь статуса
    """
    if status.get("is_recording"):
        state = _("ПАУЗА") if status.get("is_paused") else _("ЗАПИСЬ")
        elapsed = status.get("elapsed_time", 0)
        print(f"{_('Статус')}: {state}")
        print(
            f"{_('Время')}: {int(elapsed // 60):02d}:{int(elapsed % 60):02d}"
        )
        if status.get("current_file"):
            print(f"{_('Файл')}: {status['current_file']}")
    else:
        print(f"{_('Статус')}: {_('ОЖИДАНИЕ')}")


def print_schedule_list(tasks: list[dict[str, Any]]) -> None:
    """
    Вывод запланированных задач в консоль.

    Args:
        tasks: Список словарей задач
    """
    if not tasks:
        print(_("Нет запланированных задач"))
        return

    header = ngettext(
        "Запланированная задача ({count}):",
        "Запланированные задачи ({count}):",
        len(tasks),
    ).format(count=len(tasks))
    print(header)
    print("-" * 60)
    for task in tasks:
        status = _("ВКЛЮЧЕНО") if task.get("enabled") else _("ВЫКЛЮЧЕНО")
        print(f"ID: {task.get('id')}")
        print(f"  {_('Имя')}: {task.get('name')}")
        print(f"  {_('Тип')}: {task.get('schedule_type')}")
        print(f"  {_('Статус')}: {status}")
        if task.get("next_run"):
            print(f"  {_('Следующий запуск')}: {task['next_run']}")
        print()


def print_plugins_list(plugins: list[dict[str, Any]]) -> None:
    """
    Вывод списка установленных плагинов в консоль.

    Args:
        plugins: Список словарей метаданных плагинов.
    """
    if not plugins:
        print(_("Установленные плагины не обнаружены."))
        return

    header = ngettext(
        "Установленный плагин ({count}):",
        "Установленные плагины ({count}):",
        len(plugins),
    ).format(count=len(plugins))
    print(header)
    print("-" * 60)
    for p in plugins:
        status = p.get("status", "unknown").upper()
        name = p.get("name", "unknown")
        version = p.get("version", "unknown")
        desc = p.get("description", "")
        print(f"* {name} (v{version}) [{status}]")
        if desc:
            print(f"  {desc}")
    print()


def print_plugin_info(info: dict[str, Any]) -> None:
    """
    Вывод подробной информации о плагине в консоль.

    Args:
        info: Словарь метаданных плагина.
    """
    print(f"{_('Информация о плагине')}: {info.get('name')}")
    print("-" * 60)
    print(f"  {_('Версия')}:      {info.get('version', 'unknown')}")
    print(f"  {_('Статус')}:      {info.get('status', 'unknown').upper()}")
    print(f"  {_('Автор')}:       {info.get('author', _('н/д'))}")
    print(f"  {_('Сайт')}:        {info.get('homepage', _('н/д'))}")
    print(f"  {_('Описание')}:    {info.get('description', _('н/д'))}")
    if info.get("error_message"):
        print(f"  {_('Ошибка')}:      {info.get('error_message')}")
    if info.get("config"):
        print(f"  {_('Настройки')}:   {info.get('config')}")
    if info.get("settings_schema"):
        print(f"  {_('JSON Schema')}: {info.get('settings_schema')}")
    print()


if __name__ == "__main__":
    # Тест парсера
    config = parse_args()
    print(f"Разобранная конфигурация: {config}")
